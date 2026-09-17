#!/usr/bin/env bash
# Оркестратор задач GJ поверх надзираемых работников Orca.
#
# Почему Orca, а не свой запуск вкладок: работники Orca — обычные сессии, их расход
# виден в журналах (замерено: 10 работников на 221 млн токенов). Внутренние подагенты
# не логируются вовсе, и цена делегирования остаётся неизвестной.
#
# Почему вызовы скиллов вписываются в спецификацию: замер по 66 журналам — скиллы
# грузятся в 0,17% ходов, из 54 русских триггерных фраз в 1438 репликах встретились
# шесть. Подбор по описанию ненадёжен, текст в самой реплике срабатывает всегда.
#
#   orchestrate.sh task   <КЛЮЧ> [заголовок]   задача на бэк/общая
#   orchestrate.sh front  <КЛЮЧ> [заголовок]   задача на вёрстку
#   orchestrate.sh review <адрес запроса>      ревью
#   orchestrate.sh done   <КЛЮЧ>               сдача: MR в стейдж, деплой, заготовки в прод
#
#   orchestrate.sh list                        работники и их состояние
#   orchestrate.sh read  <dispatch> [строк]    что делает работник
#   orchestrate.sh say   <dispatch> <текст>    вмешаться: дослать указание
#   orchestrate.sh wait  [мс]                  ждать worker_done / вопроса / эскалации
#   orchestrate.sh release <dispatch>          отпустить терминал завершённого
#   orchestrate.sh run                         показать привязанный Run
#
# Переменные: GJ_MAX_AGENTS (4), GJ_MIN_FREE_MB (2048), GJ_FORCE=1 — обойти заслон,
#             GJ_WORKTREE (current) — куда сажать работника, GJ_AGENT (claude).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASKS=${GJ_TASKS_DIR:-$ROOT/.tasks}
ORCA=${GJ_ORCA_BIN:-orca}
AGENT=${GJ_AGENT:-claude}
WORKTREE=${GJ_WORKTREE:-current}
GJ_MAX_AGENTS=${GJ_MAX_AGENTS:-4}
GJ_MIN_FREE_MB=${GJ_MIN_FREE_MB:-2048}

have_orca() { command -v "$ORCA" >/dev/null 2>&1; }
slug() { echo "$1" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//'; }
jq_() { python3 -c "import json,sys;d=json.load(sys.stdin);print($1)" 2>/dev/null; }

free_mb() {
  vm_stat | awk '/page size of/{ps=$8} /Pages free/{f=$3} /Pages inactive/{i=$3}
                 END{gsub(/\./,"",f); gsub(/\./,"",i); if(!ps)ps=16384; print int((f+i)*ps/1048576)}'
}

# Память по сессиям — из Orca, она знает привязку к рабочему дереву.
sessions_mb() {
  if have_orca; then
    "$ORCA" diagnostics memory --json 2>/dev/null | python3 -c '
import json,sys
try: d=json.load(sys.stdin)["result"]
except Exception: raise SystemExit(1)
t=n=0
for w in d.get("worktrees",[]):
    for s in w.get("sessions",[]): t+=s.get("memory",0); n+=1
print("%d %d"%(n,t//1048576))' 2>/dev/null && return 0
  fi
  ps -Ao rss,comm | awk '$2 ~ /claude/ {s+=$1; n++} END {printf "%d %d\n", n, s/1024}'
}

heavy() {
  have_orca || return 0
  "$ORCA" diagnostics memory --json 2>/dev/null | python3 -c '
import json,sys
try: d=json.load(sys.stdin)["result"]
except Exception: raise SystemExit
r=[(s.get("memory",0),w.get("worktreeName","?"),s.get("pid"))
   for w in d.get("worktrees",[]) for s in w.get("sessions",[])]
for m,w,p in sorted(r,reverse=True)[:3]:
    print("      %5d МБ  %-26s pid %s"%(m//1048576,w[:26],p))' 2>/dev/null
}

# Жёсткого лимита ОЗУ на процесс в macOS нет: claude — нативный бинарь, cgroups нет.
# Ограничиваем то, что поддаётся: число сессий и свободную память на входе.
guard() {
  local n used f; read -r n used <<<"$(sessions_mb)"; f=$(free_mb)
  [ "${GJ_FORCE:-}" = "1" ] && { echo "заслон обойдён: сессий $n, свободно ${f} МБ" >&2; return 0; }
  if [ "$n" -ge "$GJ_MAX_AGENTS" ]; then
    echo "СТОП: запущено $n сессий на ${used} МБ, потолок GJ_MAX_AGENTS=$GJ_MAX_AGENTS" >&2
    heavy >&2
    echo "      закрыть: orca terminal close <id>   ·   обойти: GJ_MAX_AGENTS=8 или GJ_FORCE=1" >&2
    return 1
  fi
  if [ "$f" -lt "$GJ_MIN_FREE_MB" ]; then
    echo "СТОП: свободно ${f} МБ, нужно ${GJ_MIN_FREE_MB}. Сессия занимает 200-700 МБ и растёт." >&2
    return 1
  fi
  echo "ресурсы: сессий $n из $GJ_MAX_AGENTS на ${used} МБ, свободно ${f} МБ" >&2
}

skills_for() {
  case "$1" in
    task)   echo "gj-task-orchestration, gj-task-execution" ;;
    front)  echo "gj-task-orchestration, gj-task-execution, mobile-rn-conventions" ;;
    review) echo "gj-review-delegation" ;;
    done)   echo "gj-task-orchestration, gj-gitlab-git" ;;
  esac
}

# Спецификация работника. Скилл orchestration требует пять вещей; шестым идёт
# перечень скиллов явной строкой — иначе работник начнёт без них.
spec_for() {                       # spec_for <вид> <ключ> <заголовок> <вводная>
  local kind=$1 key=$2 title=$3 brief=$4
  cat <<EOS
Загрузи скиллы $(skills_for "$kind") ДО любых других действий. Без них не начинай.

ЦЕЛЬ: задача $key${title:+ — $title}. Вводная: $brief — начни с неё и дозаполни
цель одной фразой и критерий готовности.

ИЗМЕНЕНИЕ: довести задачу до готовой правки в ветках задачи. Запросы на слияние
не открывать — это отдельный шаг сдачи по явной команде.

ОГРАНИЧЕНИЯ: работать по фазам скилла gj-task-orchestration с потолками контекста.
Разведку вести подагентами и codegraph, полные кадры экрана в контекст не тянуть.
Ветки брать из docs/deploy/branch-registry.md, заново не выяснять.
В прод-ветки (master ENSI, production ИС, release/production витрины) не трогать ничего.

ВЛАДЕНИЕ: только репозитории, затронутые этой задачей. Чужие ветки и незнакомые
изменённые файлы не трогать — рабочие деревья делят соседние сессии.

ПРИЗНАК ГОТОВНОСТИ: правка внесена, форма контроля пройдена (бэк — локальный прогон
плюс phpstan и cs-fixer; вёрстка — orca emulator ax и scripts/gj/golden.sh check),
во вводной дописано что сделано и что осталось.

Вопросы задавать командой ask из преамбулы, а не в свой терминал. Человеку выносить
только то, на что не нашлось ответа ни в ТЗ, ни в коде.

ЗАПРЕТ НА ОТПИСКИ: «не проверено», «в коде не нашёл», «на живом контуре не смотрел»,
«тесты не гонял» — это незакрытые шаги, а не ответы. Сначала проверить самому: живые
контуры test/stage curl-ом, прод — data_pg_query и data_logs_raw_search, код — codegraph
и подагентами, тесты — локальным прогоном, сборку — джобами GitLab. Человеку уходит
результат замера. Открытым вопрос остаётся только когда решение за владельцем, источники
противоречат, оба молчат либо нужен недоступный доступ — и тогда написать, чего не хватило,
у кого и когда запрошено, и временный ли обходной путь.
Перед отправкой отчёта сверить его с самим собой: если средство проверки упомянуто где-то
ещё в отчёте, в задаче или в .env — идти проверять, а не писать «не проверено».
Код «на оба варианта», написанный потому что настоящий формат не смотрели, — это две
непроверенные гипотезы, а не запас прочности. Замерить и оставить один путь.
В «что осталось» класть только незакрытые вопросы: порядок выкатки и зависимости между
запросами идут в раздел «Выкатка».
EOS
}

run_bind() {                       # создаёт Run при отсутствии, печатает его id
  local obj=$1 cur
  cur=$("$ORCA" orchestration run-current --json 2>/dev/null | jq_ 'd.get("result",{}).get("run",{}).get("id","")') || cur=""
  if [ -z "$cur" ]; then
    cur=$("$ORCA" orchestration run-create --objective "$obj" --json 2>/dev/null | jq_ 'd["result"]["run"]["id"]') || cur=""
  fi
  printf '%s' "$cur"
}

start_worker() {                   # start_worker <вид> <ключ> <спецификация>
  local kind=$1 key=$2 spec=$3
  have_orca || { echo "orca не найдена — установите либо запускайте сессию вручную" >&2; return 1; }
  guard || return 1
  local run; run=$(run_bind "GJ $key")
  [ -n "$run" ] && echo "Run: $run"
  local out
  out=$("$ORCA" orchestration worker-start --spec "$spec" --worktree "$WORKTREE" \
        --agent "$AGENT" --task-title "$key" --json 2>&1) || {
    echo "worker-start не прошёл:" >&2; echo "$out" | head -5 >&2
    echo "не перезапускать вслепую: прочитать failedStage и residualResources в ответе" >&2
    return 1; }
  echo "$out" | python3 -c '
import json,sys
try: d=json.load(sys.stdin)["result"]
except Exception: print(sys.stdin.read()[:400]); raise SystemExit
w=d.get("dispatch") or d.get("worker") or d
print("Dispatch:", w.get("id") or w.get("dispatchId","?"))
print("Task:    ", (d.get("task") or {}).get("id","?"))' 2>/dev/null || echo "$out" | head -3
  echo
  echo "следить:   scripts/gj/orchestrate.sh list"
  echo "ждать:     scripts/gj/orchestrate.sh wait"
  echo "вмешаться: scripts/gj/orchestrate.sh say <dispatch> \"…\""
}

cmd=${1:-}; shift || true
case "$cmd" in
  task|front)
    KEY=${1:?укажите ключ задачи}; TITLE=${2:-}
    "$ROOT/scripts/gj/task.sh" "$([ "$cmd" = front ] && echo front || echo back)" "$KEY" "$TITLE" >/dev/null
    BRIEF="$TASKS/$(slug "$KEY")/brief.md"
    start_worker "$cmd" "$KEY" "$(spec_for "$cmd" "$KEY" "$TITLE" "$BRIEF")"
    ;;

  review)
    URL=${1:?укажите адрес запроса}
    KEY=$(echo "$URL" | sed -E 's#.*/([^/]+)/-/merge_requests/([0-9]+).*#\1-\2#')
    DIR="$TASKS/review-$(slug "$KEY")"; mkdir -p "$DIR"
    "$ROOT/scripts/gj/mr-brief.py" "$URL" --out "$DIR/brief.md" 2>/dev/null \
      || echo "выжимку собрать не удалось — работник соберёт сам" >&2
    SPEC="Загрузи скилл $(skills_for review) ДО любых других действий.

ЦЕЛЬ: ревью запроса $URL.
ИЗМЕНЕНИЕ: отчёт с вердиктом по формату gj-gitlab-mr-review.
ОГРАНИЧЕНИЯ: читать выжимку $DIR/brief.md вместо полного диффа; полный дифф открывать
только по правкам, которые выжимка показала единичными. Право записи в GitLab: НЕТ.
ВЛАДЕНИЕ: только чтение. Кода не править, веток и коммитов не создавать.
ПРИЗНАК ГОТОВНОСТИ: вердикт, вершина запроса, находки по серьёзности, что проверено,
что осталось открытым. Каждая находка — с командой, которая её доказывает, и её выводом.
Находка только по чтению кода, без замера, не блокирует — понижать до «требует проверки».
Прогноз «это сломает потребителя X» проверять У ПОТРЕБИТЕЛЯ, а не выводить из диффа:
как X собирается (install по локу или update), кто реально вызывает (grep по коду
потребителя), активен ли путь, что говорят прод-данные. Три ложные тревоги подряд
в этом воркспейсе были именно такими.
«Не проверял» в отчёте недопустимо: проверить самому либо назвать, какого доступа не хватило."
    start_worker review "review-$KEY" "$SPEC"
    ;;

  done)
    KEY=${1:?укажите ключ задачи}
    BRIEF="$TASKS/$(slug "$KEY")/brief.md"
    SPEC="Загрузи скиллы $(skills_for done) ДО любых других действий.

ЦЕЛЬ: сдача задачи $KEY по разделу «Сдача задачи» скилла gj-task-orchestration.
Вводная: $BRIEF. Ветки: $ROOT/docs/deploy/branch-registry.md — брать оттуда, не выяснять.
ИЗМЕНЕНИЕ: всё влито в ветки задачи → запросы в стейдж → одобрить и влить →
запустить деплой стейджа → подготовить запросы в ближайший релиз и ОСТАВИТЬ ОТКРЫТЫМИ.
ОГРАНИЧЕНИЯ: в прод не вливать ничего. Запросы в master ENSI, production ИС и
release/production витрины не открывать. Прод-джобы не запускать.
ВЛАДЕНИЕ: только репозитории этой задачи.
ПРИЗНАК ГОТОВНОСТИ: доклад — что влито, что задеплоено, какие запросы ждут и в каком
порядке выкатывать. Для мобильного приложения ОБЯЗАТЕЛЬНО указать номер сборки:
versionName и versionCode из лога успешной джобы (строки Version name / Version code),
versionCode = CI_PIPELINE_IID + 85000. Без номера сборки мобильная сдача не закрыта."
    start_worker done "done-$KEY" "$SPEC"
    ;;

  list)
    have_orca || { echo "orca не найдена"; exit 1; }
    read -r n u <<<"$(sessions_mb)"
    echo "сессий: $n из $GJ_MAX_AGENTS на ${u} МБ · свободно $(free_mb) МБ · вход от ${GJ_MIN_FREE_MB} МБ"
    heavy; echo
    "$ORCA" orchestration worker-list --include-remote --json 2>/dev/null | python3 -c '
import json,sys
try: d=json.load(sys.stdin)["result"]
except Exception: print("работников нет либо Run не привязан"); raise SystemExit
ws=d.get("workers") or d.get("rows") or []
if not ws: print("работников нет"); raise SystemExit
print("%-22s %-12s %-10s %s" % ("задача","dispatch","состояние","что дальше"))
for w in ws:
    p=w.get("projection",{}) or {}
    print("%-22s %-12s %-10s %s" % (
        str(w.get("taskTitle") or w.get("title") or "?")[:22],
        str(w.get("dispatchId") or w.get("id") or "?")[:12],
        str((p.get("liveness") or {}).get("status") if isinstance(p.get("liveness"),dict) else p.get("liveness") or "?")[:10],
        str(p.get("nextAction") or "")[:40]))' 2>/dev/null \
    || "$ORCA" orchestration worker-list --include-remote 2>&1 | head -20
    ;;

  read)   D=${1:?укажите dispatch}; N=${2:-60}
          "$ORCA" orchestration worker-read --dispatch "$D" --limit "$N" 2>&1 | tail -"$N" ;;
  say)    D=${1:?укажите dispatch}; shift
          case "$D" in *:*) TO=$D ;; *) TO="dispatch:$D" ;; esac
          "$ORCA" orchestration send --to "$TO" --subject "указание координатора" \
            --body "$*" --json >/dev/null && echo "передано" ;;
  wait)   MS=${1:-900000}
          "$ORCA" orchestration check --wait --types "worker_done,escalation,question" --timeout-ms "$MS" --json 2>&1 | head -40 ;;
  release) D=${1:?укажите dispatch}; "$ORCA" orchestration worker-release --dispatch "$D" --json >/dev/null && echo "отпущен $D" ;;
  run)    "$ORCA" orchestration run-current 2>&1 | head -10 ;;

  *) sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
