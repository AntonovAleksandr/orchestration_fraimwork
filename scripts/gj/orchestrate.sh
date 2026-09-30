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
#   orchestrate.sh say   <dispatch> <текст>    вмешаться: дослать указание; висит вопрос
#                                              этого работника — ответ идёт на него (reply)
#   orchestrate.sh questions [dispatch]        открытые вопросы работников
#   orchestrate.sh answer <dispatch|msg_id> <текст>  ответить на вопрос (reply)
#   orchestrate.sh wait  [мс]                  ждать worker_done / вопроса / эскалации
#   orchestrate.sh release <dispatch|все>      отпустить терминал завершённого (все —
#                                              по всем Run, с отчётом о неотпущенных)
#   orchestrate.sh retain  <dispatch>          оставить терминал живым: воркеру будет ещё работа
#   orchestrate.sh sweep                       release все — для ежедневного прогона
#   orchestrate.sh run                         показать привязанный Run
#
# Переменные: GJ_MAX_AGENTS (4), GJ_MIN_FREE_MB (2048), GJ_FORCE=1 — обойти заслон,
#             GJ_WORKTREE (current) — куда сажать работника, GJ_AGENT (claude).
#             GJ_RETAIN=1 — wait не закрывает терминал по worker_done.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASKS=${GJ_TASKS_DIR:-$ROOT/.tasks}
ORCA=${GJ_ORCA_BIN:-orca}
AGENT=${GJ_AGENT:-claude}
# Дерево задаём ЯВНО по каталогу скрипта. `--worktree current` берёт активное дерево
# интерфейса Orca, а не место запуска: работник может уйти совсем не туда, где его ждут.
# Проверено 17.09 — запуск из flyingfish посадил работника в основное дерево.
WORKTREE=${GJ_WORKTREE:-path:$ROOT}
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

# Есть ли в дереве вложенные клоны платформ. Рабочее дерево git содержит только
# отслеживаемые файлы, а platform/* — отдельные клоны, в worktree они НЕ попадают:
# там остаются одни README. Работник получает вводную и не находит файлов.
# Так сорвалась OPSOMN002-422: два работника сидели в дереве без customers-api-web.
platform_repos() {
  local root=${1:-$ROOT} n=0
  for g in "$root"/platform/*/*/.git "$root"/platform/*/*/*/.git; do
    [ -e "$g" ] && n=$((n+1))
  done
  echo "$n"
}

# Каталог дерева, куда реально сядет работник. Проверять надо ЕГО, а не каталог
# скрипта: запуск из дерева без клонов с явным GJ_WORKTREE иначе отбивался зря.
# Путь известен заранее только у формы `path:<путь>`; при другой проверять нечего.
target_dir() {
  case "$WORKTREE" in
    path:*) printf '%s' "${WORKTREE#path:}" ;;
    *)      printf '' ;;
  esac
}

check_tree() {
  local dir n; dir=$(target_dir)
  [ -n "$dir" ] || { echo "дерево задано не путём ($WORKTREE) — проверку клонов пропускаю" >&2; return 0; }
  n=$(platform_repos "$dir")
  [ "$n" -gt 0 ] && { echo "дерево: $dir (репозиториев платформ: $n)" >&2; return 0; }
  echo "СТОП: в дереве $dir нет ни одного клона platform/*/ — только README." >&2
  echo "      Рабочие деревья git не содержат вложенных клонов, и работник не найдёт файлов." >&2
  echo "      Запускать из основного дерева, направить туда работника (fleet.sh run КЛЮЧ@main)" >&2
  echo "      либо подтянуть клоны:" >&2
  echo "        scripts/sync-platform-repos.sh" >&2
  echo "      Обойти (задача не трогает platform/*): GJ_SKIP_TREE_CHECK=1" >&2
  return 1
}

# Вводная заполнена или осталась шаблоном. Пустая постановка = работа не начиналась.
brief_filled() {
  local b=$1
  [ -f "$b" ] || return 1
  grep -q 'заполняется в начале сессии' "$b" && return 1
  return 0
}

skills_for() {
  case "$1" in
    task)   echo "gj-task-orchestration, gj-task-execution, gj-subagent-delegation" ;;
    front)  echo "gj-task-orchestration, gj-task-execution, gj-subagent-delegation, mobile-rn-conventions" ;;
    review) echo "gj-review-delegation" ;;
    done)   echo "gj-task-orchestration, gj-gitlab-git, gj-subagent-delegation" ;;
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

ПЕРВЫЙ ШАГ: перевести $key в Jira в статус «В работе» — jira_list_transitions, переход
с целевым статусом «В работе», jira_transition_issue. Уже «В работе» или дальше — не
трогать. Не вышло — записать причину во вводную и продолжать (раздел 1 скилла).

ИЗМЕНЕНИЕ: довести задачу до готовой правки в ветках задачи. Запросы на слияние
не открывать — это отдельный шаг сдачи по явной команде.

ОГРАНИЧЕНИЯ: работать по фазам скилла gj-task-orchestration с потолками контекста.
Независимые команды складывать в ОДИН ход через ; или && — замер: 1,04 команды на ход,
а ходы только с оболочкой дают 74,6% расхода, потому что каждый перечитывает контекст.
Промежуточные «сейчас проверю» не писать, писать результат.
Разведку вести подагентами и codegraph, полные кадры экрана в контекст не тянуть.
Деплой, анализ веток и статуса, исследование, ревью — фоновыми подагентами по скиллу
gj-subagent-delegation: задание по его шаблону с «уже установлено», agentId записать в
.tasks/<ключ>/agents.tsv, на ВОПРОС подагента отвечать SendMessage в том же ходе.
Ветки брать из docs/deploy/branch-registry.md, заново не выяснять.
В прод-ветки (master ENSI, production ИС, release/production витрины) не трогать ничего.

ВЛАДЕНИЕ: только репозитории, затронутые этой задачей. Чужие ветки и незнакомые
изменённые файлы не трогать — рабочие деревья делят соседние сессии.

ПРИЗНАК ГОТОВНОСТИ: правка внесена, форма контроля пройдена (бэк — локальный прогон
плюс phpstan и cs-fixer; вёрстка — orca emulator ax и scripts/gj/golden.sh check),
во вводной дописано что сделано и что осталось.

Вопросы задавать командой ask из преамбулы, а не в свой терминал. Человеку выносить
только то, на что не нашлось ответа ни в ТЗ, ни в коде.
КАК СПРАШИВАТЬ: ask всегда с --timeout-ms 110000 (Bash рвёт команду на 120 с). Таймаут
оставляет вопрос открытым — продолжать ТОЛЬКО через ask --resume <message_id>, новый
вопрос с тем же текстом не задавать. Ответа нет 15 минут — один раз send --type escalation
с сутью вопроса и делать то, что можно без ответа; к ожиданию возвращаться между шагами.
Нужно действие человека (кнопка в GitLab, доступ, решение владельца) — сразу escalation,
а не ask: координатор его сделать не может.

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

# Открытые вопросы работников. Ответ `reply` ложится в тред вопроса (thread_id = id
# вопроса), поэтому открытый — это question, в треде которого нет других сообщений.
# `say`/`send` вопрос НЕ закрывают: ask у работника ждёт ответа именно на своё сообщение.
# Замер 16–30.09: 0 вызовов reply против 25 say/send, ни один вопрос не получил ответа.
#   open_questions [dispatch|msg_id]  → строки «id<TAB>dispatch<TAB>run<TAB>минут<TAB>текст»
open_questions() {
  # Вопросы завершённых диспетчей не показываем: отвечать там уже некому. Состояние
  # берём через worker-show по каждому диспетчу — worker-list в терминале, привязанном
  # к Run, видит только работников этого Run.
  "$ORCA" orchestration inbox --limit 500 --json 2>/dev/null | FILTER="${1:-}" ORCA_BIN="$ORCA" python3 -c '
import json,sys,os,subprocess,datetime as dt
_st={}
def live(d):
    if d not in _st:
        try:
            r=subprocess.run([os.environ["ORCA_BIN"],"orchestration","worker-show","--dispatch",d,"--json"],capture_output=True,text=True,timeout=20)
            _st[d]=json.loads(r.stdout)["result"]["dispatch"]["status"] in ("dispatched","created","pending")
        except Exception: _st[d]=True
    return _st[d]
try: m=json.load(sys.stdin)["result"]["messages"]
except Exception: raise SystemExit
f=os.environ.get("FILTER","").replace("dispatch:","")
answered={x.get("thread_id") for x in m if x.get("thread_id") and x.get("thread_id")!=x.get("id")}
now=dt.datetime.now(dt.timezone.utc)
for x in sorted(m,key=lambda x:x.get("created_at","")):
    if x.get("type")!="question" or x["id"] in answered: continue
    d=str(x.get("from_handle","")).replace("dispatch:","")
    try: d=json.loads(x.get("payload") or "{}").get("dispatchId") or d
    except Exception: pass
    if f and f not in (d,x["id"]): continue
    if not f and not live(d): continue
    try: age=int((now-dt.datetime.fromisoformat(x["created_at"].replace("Z","+00:00"))).total_seconds()//60)
    except Exception: age=-1
    body=" ".join(str(x.get("body","")).split())
    print("\t".join([x["id"],d,str(x.get("run_id","")),str(age),body]))'
}

reply_to() {                       # reply_to <msg_id> <run_id> <текст>
  "$ORCA" orchestration reply --id "$1" ${2:+--run "$2"} --body "$3" --json 2>&1 | python3 -c '
import json,sys
raw=sys.stdin.read()
try: d=json.loads(raw)
except Exception: print(raw[:300]); raise SystemExit(1)
if d.get("ok"): print("ответ доставлен на", sys.argv[1])
else: print("reply не прошёл:", (d.get("error") or {}).get("message","")[:300]); raise SystemExit(1)' "$1"
}

print_questions() {                # print_questions [dispatch] — с готовой командой ответа
  local rows; rows=$(open_questions "${1:-}")
  [ -z "$rows" ] && { echo "открытых вопросов нет"; return 0; }
  printf '%s\n' "$rows" | while IFS=$'\t' read -r id d run age body; do
    local mark=""; [ "$age" -ge "${GJ_ASK_ESCALATE_MIN:-15}" ] 2>/dev/null && mark=" · ВЫНЕСТИ ЧЕЛОВЕКУ"
    echo "ВОПРОС $d ($id), ${age} мин без ответа${mark}"
    echo "  «${body:0:400}»"
    echo "  → scripts/gj/orchestrate.sh answer $d \"…\""
  done
}

# Закрытие терминала завершённого работника. Orca сама терминал не закрывает: по
# worker_done решает координатор — отдать под новый диспетч, оставить или отпустить.
# Успех проверяем по состоянию в ответе, а не по ok: release_unknown приходит с ok=true.
# Замер 30.09: из 13 «отпущенных» по ok четыре остались release_unknown.
release_one() {                    # release_one <dispatch> → released|retained|pending|unknown
  # release_unknown выходит с кодом 1 — под set -e/pipefail это оборвало бы скрипт до разбора.
  { "$ORCA" orchestration worker-release --dispatch "$1" --json 2>&1 || true; } | python3 -c '
import json,sys
d=sys.argv[1]
try: r=json.load(sys.stdin)
except Exception: print("unknown\t%s: ответ не разобран" % d); raise SystemExit
res=r.get("result") or {}; err=r.get("error") or {}
st=res.get("state") or err.get("code") or "?"
if st in ("released","already_released"): print("released\t%s отпущен" % d)
elif st=="retained": print("retained\t%s оставлен: %s" % (d, res.get("retainedReason") or res.get("reason") or "по решению"))
elif st=="release_pending": print("pending\t%s закрывается" % d)
elif st=="release_unknown": print("unknown\t%s НЕ отпущен: терминал потерян (перезапуск Orca?) — закрыть вкладку вручную" % d)
else: print("unknown\t%s НЕ отпущен: %s %s" % (d, st, (err.get("message") or res.get("lastError") or "")[:160]))' "$1"
}

# Все Run: worker-list без --run в привязанном терминале видит только свой Run.
all_runs() {
  "$ORCA" orchestration run-list --json 2>/dev/null | python3 -c '
import json,sys
try: [print(x["id"]) for x in json.load(sys.stdin)["result"]["runs"]]
except Exception: pass'
}

workers_in() {                     # workers_in <run> <terminal-state> → dispatch<TAB>причина
  "$ORCA" orchestration worker-list --run "$1" --terminal-state "$2" --limit 100 --json 2>/dev/null | python3 -c '
import json,sys
try: w=json.load(sys.stdin)["result"]["workers"]
except Exception: raise SystemExit
for x in w:
    r=x.get("resource") or {}
    print("%s\t%s" % (x["dispatchId"], r.get("retainedReason") or r.get("releaseError") or ""))'
}

sweep() {
  local run d why n=0 bad=0
  for run in $(all_runs); do
    while IFS=$'\t' read -r d why; do
      [ -n "$d" ] || continue
      line=$(release_one "$d"); echo "  ${line#*$'\t'}"; n=$((n+1))
      case "$line" in released*|retained*|pending*) ;; *) bad=$((bad+1)) ;; esac
    done < <(workers_in "$run" reclaimable)
  done
  echo "отпущено из reclaimable: $n, не вышло: $bad"
  local left=""
  for run in $(all_runs); do
    for st in release_unknown retained; do
      while IFS=$'\t' read -r d why; do
        [ -n "$d" ] && left="$left\n  $st  $d  ${why:0:90}"
      done < <(workers_in "$run" "$st")
    done
  done
  [ -n "$left" ] && printf "закрыть руками или решить (Orca сама не закроет):%b\n" "$left"
  return 0
}

retain_list() { printf '%s\n' "${TASKS}/.retain"; }

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
  [ "${GJ_SKIP_TREE_CHECK:-}" = "1" ] || check_tree || return 1
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
    if ! brief_filled "$BRIEF"; then
      echo "СТОП: вводная $BRIEF осталась шаблоном — постановка не заполнена." >&2
      echo "      Значит работа по задаче не начиналась либо шла мимо вводной." >&2
      echo "      Сдавать нечего: сначала заполнить цель и критерий готовности." >&2
      exit 1
    fi
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
          # Висит вопрос этого работника — отвечаем на него: send его ask не разблокирует.
          Q=$(open_questions "$D" | head -1)
          if [ -n "$Q" ]; then
            IFS=$'\t' read -r QID _ QRUN _ _ <<<"$Q"
            reply_to "$QID" "$QRUN" "$*"
          else
            case "$D" in *:*) TO=$D ;; *) TO="dispatch:$D" ;; esac
            "$ORCA" orchestration send --to "$TO" --subject "указание координатора" \
              --body "$*" --json >/dev/null && echo "передано (открытого вопроса нет)"
          fi ;;
  questions) print_questions "${1:-}" ;;
  answer) T=${1:?укажите dispatch или id вопроса}; shift
          [ -n "$*" ] || { echo "укажите текст ответа" >&2; exit 1; }
          Q=$(open_questions "$T" | head -1)
          [ -n "$Q" ] || { echo "открытого вопроса у $T нет — для указания без вопроса есть say" >&2; exit 1; }
          IFS=$'\t' read -r QID _ QRUN _ _ <<<"$Q"
          reply_to "$QID" "$QRUN" "$*" ;;
  wait)   MS=${1:-900000}
          # Сначала то, что уже ждёт ответа: check --wait отдаёт только новое.
          print_questions
          # Пачка переигрывается, пока её не подтвердить: подтверждаем прошлую при следующем
          # wait — к этому моменту её события уже разобраны.
          mkdir -p "$TASKS"; LAST="$TASKS/.last-delivery"
          ACK=(); [ -s "$LAST" ] && ACK=(--ack "$(cat "$LAST")")
          OUT=$("$ORCA" orchestration check ${ACK[@]+"${ACK[@]}"} --wait --types "worker_done,escalation,question" --timeout-ms "$MS" --json 2>/dev/null || true)
          printf '%s' "$OUT" | python3 -c '
import json,sys
try: d=json.load(sys.stdin).get("result") or {}
except Exception: raise SystemExit
print(d.get("deliveryId") or "")' > "$LAST.new" 2>/dev/null; mv "$LAST.new" "$LAST"
          DONE=$(printf '%s' "$OUT" | python3 -c '
import json,sys
try: d=json.load(sys.stdin).get("result") or {}
except Exception: print("события не разобраны", file=sys.stderr); raise SystemExit
ms=d.get("messages") or []
if not ms: print("событий нет (таймаут — это точка проверки, а не сбой)", file=sys.stderr)
for x in ms:
    t=x.get("type"); frm=str(x.get("from_handle","")).replace("dispatch:","")
    try: p=json.loads(x.get("payload") or "{}")
    except Exception: p={}
    who=p.get("dispatchId") or frm
    print("%-11s %s  %s" % (t, who, " ".join(str(x.get("subject","")).split())[:80]), file=sys.stderr)
    if t in ("escalation","worker_done"): print("  «%s»" % " ".join(str(x.get("body","")).split())[:400], file=sys.stderr)
    if t=="worker_done" and p.get("dispatchId"): print(p["dispatchId"])')
          # worker_done — терминал больше не нужен: вывод архивируется, журнал сессии остаётся.
          for D in $DONE; do
            if [ "${GJ_RETAIN:-}" = "1" ] || grep -qx "$D" "$(retain_list)" 2>/dev/null; then
              echo "  $D оставлен (retain) — отпустить: orchestrate.sh release $D"
            else
              line=$(release_one "$D"); echo "  ${line#*$'\t'}"
            fi
          done
          print_questions | grep -v "^открытых вопросов нет$" || true ;;
  release) D=${1:?укажите dispatch либо «все»}
          if [ "$D" = "все" ]; then sweep; else
            line=$(release_one "$D"); echo "${line#*$'\t'}"
            case "$line" in released*|retained*|pending*) ;; *) exit 1 ;; esac
          fi ;;
  retain) D=${1:?укажите dispatch}; mkdir -p "$TASKS"; echo "$D" >> "$(retain_list)"
          "$ORCA" orchestration worker-retain --dispatch "$D" --json >/dev/null 2>&1 \
            && echo "оставлен $D: wait его не закроет; отпустить — release $D" ;;
  sweep)  sweep ;;
  run)    "$ORCA" orchestration run-current 2>&1 | head -10 ;;

  *) sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
