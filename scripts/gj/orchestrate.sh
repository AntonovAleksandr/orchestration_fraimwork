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
#   orchestrate.sh lead   <КЛЮЧ> [заголовок] [front]  отдельный агент-координатор: сам
#                                              запускает работника, следит и отвечает
#   orchestrate.sh task   <КЛЮЧ> [заголовок] [--expect '…']   задача на бэк/общая
#   orchestrate.sh front  <КЛЮЧ> [заголовок] [--expect '…']   задача на вёрстку
#   orchestrate.sh review <адрес запроса> [--expect '…']      ревью
#   orchestrate.sh research <КЛЮЧ> <вопрос>    только разведка: ответ фактами, решений не принимает;
#                                              идёт на дешёвой модели (GJ_RESEARCH_MODEL)
#   orchestrate.sh done   <КЛЮЧ> [--expect '…']               сдача: MR в стейдж, деплой, заготовки в прод
#
#   orchestrate.sh verify <КЛЮЧ|dispatch> [review]  выполнить expect.sh и показать вердикт
#   orchestrate.sh list [все]                  живые работники и координаторы (все — с завершёнными)
#   orchestrate.sh read  <dispatch> [строк]    что делает работник
#   orchestrate.sh say   <dispatch> <текст>    вмешаться: дослать указание; висит вопрос
#                                              этого работника — ответ идёт на него (reply)
#   orchestrate.sh questions [dispatch]        открытые вопросы работников
#   orchestrate.sh answer <dispatch|msg_id> <текст>  ответить на вопрос (reply)
#   orchestrate.sh wait  [мс]                  ждать worker_done / вопроса / эскалации;
#                                              при наличии expect.sh выполняет проверку
#   orchestrate.sh release <dispatch|все>      отпустить терминал завершённого (все —
#                                              по всем Run, с отчётом о неотпущенных)
#   orchestrate.sh retain  <dispatch>          оставить терминал живым: воркеру будет ещё работа
#   orchestrate.sh sweep                       release все — для ежедневного прогона
#   orchestrate.sh run                         показать привязанный Run
#
# Переменные: GJ_MAX_AGENTS (30), GJ_MIN_FREE_MB (2048), GJ_FORCE=1 — обойти заслон,
#             GJ_WORKTREE (дерево вызвавшего агента) — куда сажать работника,
#             GJ_AGENT (claude). GJ_RETAIN=1 — wait не закрывает терминал по worker_done.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASKS=${GJ_TASKS_DIR:-$ROOT/.tasks}
ORCA=${GJ_ORCA_BIN:-orca}
AGENT=${GJ_AGENT:-claude}
# Модель работника. Пусто — модель по умолчанию у агента. Разведка идёт на дешёвой:
# вопрос без принятия решений не требует сильной модели, а стоит столько же.
MODEL=${GJ_MODEL:-}
RESEARCH_MODEL=${GJ_RESEARCH_MODEL:-claude-haiku-4-5-20251001}
# Работник садится в дерево вызвавшего агента, то есть туда, откуда запустили команду.
# Причина: агент ведёт задачу в своём дереве и там же ждёт результат. Главное дерево
# по умолчанию уводило работника в чужой каталог, и правки оказывались не там, где их
# искали (так вышло на OPSOMN002-534). `--worktree current` тоже не годится: он берёт
# активное дерево интерфейса Orca, а не место запуска.
# Дерево без клонов platform/* останавливает заслон check_tree: направить в главное —
# GJ_WORKTREE=path:<путь> или fleet.sh КЛЮЧ@main, либо подтянуть клоны.
# Явный GJ_WORKTREE (его ставит fleet.sh для формы КЛЮЧ@дерево) имеет приоритет.
caller_tree() {
  local p
  p=$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null) || p=""
  if [ -n "$p" ] && [ -d "$p" ]; then printf '%s' "$p"; else printf '%s' "$ROOT"; fi
}
main_tree() {
  git -C "$ROOT" worktree list --porcelain 2>/dev/null \
    | awk 'NR==1 && $1=="worktree"{ $1=""; sub(/^ /,""); print; exit }'
}
WORKTREE=${GJ_WORKTREE:-path:$(caller_tree)}
GJ_MAX_AGENTS=${GJ_MAX_AGENTS:-30}
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
    echo "      закрыть: orca terminal close <id>   ·   обойти: GJ_MAX_AGENTS=30 или GJ_FORCE=1" >&2
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
  echo "      Направить работника в главное дерево:" >&2
  echo "        GJ_WORKTREE=path:$(main_tree) $0 …   (или fleet.sh run КЛЮЧ@main)" >&2
  echo "      либо подтянуть клоны сюда:" >&2
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
    research) echo "gj-buddy-mcp-mastery" ;;
    done)   echo "gj-task-orchestration, gj-gitlab-git, gj-subagent-delegation" ;;
  esac
}

# Спецификация работника. Скилл orchestration требует пять вещей; шестым идёт
# перечень скиллов явной строкой — иначе работник начнёт без них.
verify_expect() {                  # verify_expect <ключ> [review] — выполнить expect.sh
  local key=$1 is_review=${2:-}
  local expect_file
  if [ "$is_review" = "review" ]; then
    expect_file="$TASKS/review-$(slug "$key")/expect.sh"
  else
    expect_file="$TASKS/$(slug "$key")/expect.sh"
  fi
  if [ ! -f "$expect_file" ]; then
    echo "критерий не задан, приёмка только глазами"
    return 0
  fi
  local output verdict_code outcome=
  output=$(bash "$expect_file" 2>&1)
  verdict_code=$?

  if [ "$verdict_code" -eq 0 ]; then
    outcome="ПРИНЯТО"
    verdict_code=0
  elif [ "$verdict_code" -eq 1 ]; then
    outcome="НЕ ПРИНЯТО"
    verdict_code=1
  else
    outcome="ПРОВЕРКА НЕ ВЫПОЛНЕНА"
    verdict_code=2
  fi

  log_verdict "$key" "$verdict_code" "$outcome"
  echo "$outcome"
  if [ -n "$output" ]; then
    echo ""
    printf '%s\n' "$output"
  fi
  return "$verdict_code"
}

log_verdict() {                    # log_verdict <ключ> <код> [<исход>] — логировать вердикт
  local key=$1 code=$2 outcome=${3:-}
  local log="$TASKS/$(slug "$key")/verify.log"
  mkdir -p "$(dirname "$log")"
  if [ -z "$outcome" ]; then
    outcome="?"
  fi
  printf '%s\t%s\t%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$outcome" "$code" >> "$log"
}

check_verify_fails() {             # check_verify_fails <ключ> — вернуть число подряд идущих отказов
  local key=$1 log="$TASKS/$(slug "$key")/verify.log"
  if [ ! -f "$log" ]; then echo 0; return 0; fi
  local fails=0
  tail -5 "$log" | while read -r line; do
    local code=$(echo "$line" | cut -d$'\t' -f3)
    if [ "$code" = "0" ]; then
      fails=0
    else
      fails=$((fails+1))
    fi
  done
  echo "$fails"
}

spec_for() {                       # spec_for <вид> <ключ> <заголовок> <вводная> [--expect '<команда>']
  local kind=$1 key=$2 title=$3 brief=$4 expect_cmd=
  shift 4
  while [ $# -gt 0 ]; do
    case "$1" in
      --expect) expect_cmd=$2; shift 2 ;;
      *) shift ;;
    esac
  done
  if [ -n "$expect_cmd" ]; then
    local expect_file="$TASKS/$(slug "$key")/expect.sh"
    mkdir -p "$(dirname "$expect_file")"
    echo "#!/bin/bash" > "$expect_file"
    echo "$expect_cmd" >> "$expect_file"
    chmod +x "$expect_file"
  fi
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

Комментарии в коде — по .claude/rules/code-comments.md: только «почему так» и реальная
опасность, одна-три строки; ход работы и замеры — в коммит и docs/tasks, не в код.

ПРОГОНЫ И ОЖИДАНИЕ. Перед первым прогоном убедиться, что тестовая база СУЩЕСТВУЕТ, а не
просто вписана в .env: psql -lqt, при отсутствии создать и накатить миграции. Гонять
точечно по затронутым путям; полный набор — один раз в конце, если вообще нужен.
У любого ожидания обязан быть предел: цикл «жди, пока процесс жив» без счётчика попыток
не писать. Признак стоячего прогона, а не долгого: файл вывода не растёт И процесс на 0%
процессора И нет соединений к базе. Увидел — снимать показания и докладывать, а не ждать
дальше (замер 25.09.2026: работник простоял так 30 минут на несуществующей базе).

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
release_one() {                    # release_one <dispatch> → released|retained|pending|unknown
  local dispatch=$1
  # Проверка expect.sh перед отпусканием
  if [ "${GJ_FORCE:-}" != "1" ]; then
    for dispatch_file in "$TASKS"/*/.dispatch "$TASKS"/review-*/.dispatch; do
      if [ -f "$dispatch_file" ] && grep -qx "$dispatch" "$dispatch_file"; then
        dir=$(dirname "$dispatch_file")
        if [ -f "$dir/expect.sh" ] && [ -f "$dir/verify.log" ]; then
          local last_verdict=$(tail -1 "$dir/verify.log" | cut -d$'\t' -f2)
          local last_code=$(tail -1 "$dir/verify.log" | cut -d$'\t' -f3)
          if [ "$last_code" != "0" ]; then
            printf '%s\t%s %s\n' "unknown" "$dispatch НЕ отпущен:" "expect.sh не прошла — $last_verdict (отпустить с GJ_FORCE=1 для принятия без следа)"
            return
          fi
        fi
        break
      fi
    done
  elif [ "${GJ_FORCE:-}" = "1" ]; then
    # В режиме GJ_FORCE отдаём пояснение и проверяем результат
    for dispatch_file in "$TASKS"/*/.dispatch "$TASKS"/review-*/.dispatch; do
      if [ -f "$dispatch_file" ] && grep -qx "$dispatch" "$dispatch_file"; then
        dir=$(dirname "$dispatch_file")
        if [ -f "$dir/expect.sh" ]; then
          { "$ORCA" orchestration worker-release --dispatch "$dispatch" --json 2>&1 || true; } | python3 -c '
import json,sys
d=sys.argv[1]
try: r=json.load(sys.stdin)
except Exception: print("unknown\t%s: ответ не разобран" % d); raise SystemExit
res=r.get("result") or {}; err=r.get("error") or {}
st=res.get("state") or err.get("code") or "?"
if st in ("released","already_released"): print("released\t%s отпущен (сдача принята без следа по GJ_FORCE=1)" % d)
else: print("unknown\t%s НЕ отпущен по GJ_FORCE=1: %s" % (d, st))' "$dispatch"
          return
        fi
        break
      fi
    done
  fi
  # release_unknown выходит с кодом 1 — под set -e/pipefail это оборвало бы скрипт до разбора.
  { "$ORCA" orchestration worker-release --dispatch "$dispatch" --json 2>&1 || true; } | python3 -c '
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
else: print("unknown\t%s НЕ отпущен: %s %s" % (d, st, (err.get("message") or res.get("lastError") or "")[:160]))' "$dispatch"
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

research_spec() {                  # research_spec <ключ> <вопрос>
  local key=$1 question=$2
  cat <<EOS
Загрузи скилл $(skills_for research) ДО любых других действий.

Ты — разведчик по задаче $key. РЕШЕНИЙ НЕ ПРИНИМАЕШЬ и код не правишь: твой итог — факты
и ссылка на то, чем они доказаны. Выбор между вариантами, правки, ветки, запросы на слияние,
ответы в GitLab — не твоё. Увидел развилку — опиши её и верни координатору.

ВОПРОС:
$question

КАК ОТВЕЧАТЬ:
- каждый вывод — командой или цитатой источника, а не рассуждением;
- данные прода и стенда — data_pg_query, журналы — data_logs_raw_search, требования — Confluence
  и Jira через buddy, код — grep и чтение файла по ссылке на ветку;
- не нашёл или нет доступа — так и скажи, с указанием, чего не хватило; не домысливай;
- короткие числа и пути важнее пересказа.

ОТВЕТ присылай через worker_done: сам ответ в двух-трёх абзацах, под ним перечень команд и их вывод.
EOS
}

start_worker() {                   # start_worker <вид> <ключ> <спецификация>
  local kind=$1 key=$2 spec=$3
  local task_dir="$TASKS/$(slug "$key")"
  mkdir -p "$task_dir"
  have_orca || { echo "orca не найдена — установите либо запускайте сессию вручную" >&2; return 1; }
  [ "${GJ_SKIP_TREE_CHECK:-}" = "1" ] || check_tree || return 1
  guard || return 1
  local run; run=$(run_bind "GJ $key")
  [ -n "$run" ] && echo "Run: $run"
  local out
  if [ -n "$MODEL" ]; then
    out=$("$ORCA" orchestration worker-start --spec "$spec" --worktree "$WORKTREE" \
          --agent "$AGENT" --model "$MODEL" --task-title "$key" --json 2>&1)
  else
    out=$("$ORCA" orchestration worker-start --spec "$spec" --worktree "$WORKTREE" \
          --agent "$AGENT" --task-title "$key" --json 2>&1)
  fi
  [ $? -eq 0 ] || {
    echo "worker-start не прошёл:" >&2; echo "$out" | head -5 >&2
    echo "не перезапускать вслепую: прочитать failedStage и residualResources в ответе" >&2
    return 1; }
  echo "$out" | TASK_DIR="$task_dir" python3 -c '
import json,sys,os
try: d=json.load(sys.stdin)["result"]
except Exception: print(sys.stdin.read()[:400]); raise SystemExit
w=d.get("dispatch") or d.get("worker") or d
dispatch_id=w.get("id") or w.get("dispatchId","?")
print("Dispatch:", dispatch_id)
print("Task:    ", (d.get("task") or {}).get("id","?"))
# Сохраняем dispatch ID в файл для последующего использования при verify
task_dir=os.environ.get("TASK_DIR","")
if task_dir and dispatch_id != "?":
    try:
        with open(os.path.join(task_dir, ".dispatch"), "w") as f:
            f.write(dispatch_id)
    except: pass
' 2>/dev/null || echo "$out" | head -3
  echo
  echo "следить:   scripts/gj/orchestrate.sh list"
  echo "ждать:     scripts/gj/orchestrate.sh wait"
  echo "вмешаться: scripts/gj/orchestrate.sh say <dispatch> \"…\""
}

# Реплика координатора для lead. Пишется в файл: в --command она уходит через $(cat …),
# иначе кавычки и кириллица в реплике ломают строку запуска.
lead_spec() {                      # lead_spec <ключ> <заголовок> <вид>
  local key=$1 title=$2 kind=$3 qt=""
  [ -n "$title" ] && qt=" '$(printf '%s' "$title" | sed "s/'/'\\\\''/g")'"
  cat <<EOS
Загрузи скиллы gj-orca-workflow, gj-task-orchestration, gj-subagent-delegation ДО любых
других действий.

Ты — координатор задачи $key${title:+ — $title}. Задачу ведёт работник Orca, ты его
запускаешь, контролируешь и отвечаешь за результат. Код руками не правишь.

1. Запуск: scripts/gj/orchestrate.sh $kind $key$qt
2. Сразу после запуска — scripts/gj/orchestrate.sh wait в фоне (run_in_background) и так
   после каждого события. На ВОПРОС работника — scripts/gj/orchestrate.sh answer <dispatch>
   "…" в том же ходе. Нужно действие человека (кнопка в GitLab, доступ, решение владельца) —
   сразу вынести человеку одной строкой, работника не держать.
3. По worker_done: сверить вводную .tasks/<ключ>/brief.md — цель, критерий готовности,
   что сделано. Есть запрос на слияние — ревью: scripts/gj/orchestrate.sh review <адрес>.
   Недоделано — дослать работнику указание через say, а не делать самому.
4. Сдачу (scripts/gj/orchestrate.sh done $key) — только по явной команде человека.
5. Доклад человеку — коротко: что сделано, что ждёт его, какие запросы открыты.
6. Контекст за 250 тыс. — записать состояние в .tasks/<ключ>/state.md (Run, диспетчи,
   решения, что дальше), сказать человеку и остановиться.
EOS
}

cmd=${1:-}; shift || true
case "$cmd" in
  lead)
    KEY=${1:?укажите ключ задачи}; TITLE=${2:-}; KIND=task
    [ "${3:-}" = front ] && KIND=front
    have_orca || { echo "orca не найдена — lead без неё не запустить" >&2; exit 1; }
    [ "${GJ_SKIP_TREE_CHECK:-}" = "1" ] || check_tree || exit 1
    guard || exit 1
    DIR="$TASKS/$(slug "$KEY")"; mkdir -p "$DIR"
    lead_spec "$KEY" "$TITLE" "$KIND" > "$DIR/lead.md"
    TREE=$(target_dir); TREE=${TREE:-$ROOT}
    LAUNCH="cd '$TREE' && $AGENT \"\$(cat '$DIR/lead.md')\""
    if [ "${GJ_DRY:-}" = "1" ]; then echo "$LAUNCH"; exit 0; fi
    "$ORCA" terminal create --worktree "path:$TREE" --title "$KEY · координатор" \
      --command "$LAUNCH" --json 2>&1 | python3 -c '
import json,sys
try: d=json.load(sys.stdin)
except Exception: print("terminal create не разобран"); raise SystemExit(1)
if not d.get("ok"): print("terminal create отказал:", (d.get("error") or {}).get("message","")[:200]); raise SystemExit(1)
t=(d.get("result") or {}).get("terminal") or d.get("result") or {}
h=t.get("handle") or t.get("id") or "?"
open(sys.argv[1],"w").write(h+"\n")
print("координатор запущен:", h)' "$DIR/lead.term"
    echo "реплика: $DIR/lead.md · вкладка «$KEY · координатор»"
    ;;
  task|front)
    KEY=${1:?укажите ключ задачи}; TITLE=${2:-}; EXPECT=
    shift 2 || true
    while [ $# -gt 0 ]; do
      case "$1" in
        --expect) EXPECT=$2; shift 2 ;;
        *) shift ;;
      esac
    done
    "$ROOT/scripts/gj/task.sh" "$([ "$cmd" = front ] && echo front || echo back)" "$KEY" "$TITLE" >/dev/null
    BRIEF="$TASKS/$(slug "$KEY")/brief.md"
    start_worker "$cmd" "$KEY" "$(spec_for "$cmd" "$KEY" "$TITLE" "$BRIEF" ${EXPECT:+--expect "$EXPECT"})"
    ;;

  research)
    KEY=${1:?укажите ключ задачи}; QUESTION=${2:?укажите вопрос одной строкой}
    MODEL=${GJ_MODEL:-$RESEARCH_MODEL}
    echo "модель разведки: $MODEL"
    start_worker research "research-$KEY" "$(research_spec "$KEY" "$QUESTION")"
    ;;

  review)
    URL=${1:?укажите адрес запроса}; EXPECT=
    shift || true
    while [ $# -gt 0 ]; do
      case "$1" in
        --expect) EXPECT=$2; shift 2 ;;
        *) shift ;;
      esac
    done
    KEY=$(echo "$URL" | sed -E 's#.*/([^/]+)/-/merge_requests/([0-9]+).*#\1-\2#')
    DIR="$TASKS/review-$(slug "$KEY")"; mkdir -p "$DIR"
    if [ -n "$EXPECT" ]; then
      echo "#!/bin/bash" > "$DIR/expect.sh"
      echo "$EXPECT" >> "$DIR/expect.sh"
      chmod +x "$DIR/expect.sh"
    fi
    "$ROOT/scripts/gj/mr-brief.py" "$URL" --out "$DIR/brief.md" 2>/dev/null \
      || echo "выжимку собрать не удалось — работник соберёт сам" >&2
    SPEC="Загрузи скилл $(skills_for review) ДО любых других действий.

ЦЕЛЬ: ревью запроса $URL.
Ты и есть ревьюер: веди ревью сам по разделу «Задание ревьюеру» скилла gj-review-delegation,
orchestrate.sh review заново не запускай.
ИЗМЕНЕНИЕ: отчёт с вердиктом по формату gj-gitlab-mr-review — в $DIR/report.md; в worker_done
вердикт, вершина и путь к отчёту.
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
    KEY=${1:?укажите ключ задачи}; EXPECT=
    shift || true
    while [ $# -gt 0 ]; do
      case "$1" in
        --expect) EXPECT=$2; shift 2 ;;
        *) shift ;;
      esac
    done
    BRIEF="$TASKS/$(slug "$KEY")/brief.md"
    if [ -n "$EXPECT" ]; then
      DIR="$TASKS/$(slug "$KEY")"; mkdir -p "$DIR"
      echo "#!/bin/bash" > "$DIR/expect.sh"
      echo "$EXPECT" >> "$DIR/expect.sh"
      chmod +x "$DIR/expect.sh"
    fi
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

  verify)
    TARGET=${1:?укажите ключ задачи или dispatch}; REVIEW=
    shift || true
    [ "${1:-}" = "review" ] && REVIEW="review"
    verify_expect "$TARGET" "$REVIEW" || true
    ;;

  list)
    have_orca || { echo "orca не найдена"; exit 1; }
    read -r n u <<<"$(sessions_mb)"
    echo "сессий: $n из $GJ_MAX_AGENTS на ${u} МБ · свободно $(free_mb) МБ · вход от ${GJ_MIN_FREE_MB} МБ"
    heavy; echo
    # Названия задачи в записи работника нет — берём заголовок его вкладки.
    # Координаторы lead — обычные вкладки, не работники: ищем их lead.term во всех деревьях.
    W=$(mktemp); T=$(mktemp); R=$(mktemp)
    "$ORCA" orchestration worker-list --include-remote --json >"$W" 2>/dev/null
    "$ORCA" terminal list --json >"$T" 2>/dev/null
    "$ORCA" worktree list --json >"$R" 2>/dev/null
    python3 - "$W" "$T" "$R" "$TASKS" "${1:-}" <<'PY'
import json,sys,glob,os,time
wf,tf,rf,tasks,mode=sys.argv[1:]
def res(f):
    try: return json.load(open(f)).get("result") or {}
    except Exception: return {}
terms={t["handle"]:t for t in res(tf).get("terminals",[])}
title=lambda h: (terms.get(h) or {}).get("title") or "?"
dirs={tasks}|{os.path.join(w.get("path",""),".tasks") for w in res(rf).get("worktrees",[])}
leads=[]
for d in sorted(dirs):
    for f in glob.glob(os.path.join(d,"*","lead.term")):
        h=open(f).read().strip(); t=terms.get(h)
        if t: leads.append((os.path.basename(os.path.dirname(f)),t))
if leads:
    print("координаторы:")
    now=time.time()*1000
    for key,t in leads:
        ago=int((now-(t.get("lastOutputAt") or now))/1000)
        print("  %-40s вывод %s с назад" % (t.get("title","?")[:40], ago))
    print()
ws=res(wf).get("workers")
if ws is None: print("работников нет либо Run не привязан"); raise SystemExit
live,ask,done=[],[],[]
for w in ws:
    p=w.get("projection") or {}
    if (p.get("liveness") or {}).get("verdict")=="live": live.append(w)
    elif (p.get("attention") or {}).get("requiresAction"): ask.append(w)
    else: done.append(w)
if mode=="все": live,ask,done=live+ask+done,[],[]
def nxt(p):
    n=p.get("nextAction") or {}
    return "" if n.get("kind") in (None,"none") else " ".join(n.get("argv") or [n["kind"]])
if live:
    print("%-40s %-18s %-12s %s" % ("вкладка","dispatch","состояние","что дальше"))
    for w in live:
        p=w.get("projection") or {}
        state=(p.get("stage") or {}).get("activity") if (p.get("liveness") or {}).get("verdict")=="live" else p.get("outcome")
        print("%-40s %-18s %-12s %s" % (title(w.get("agentTerminalHandle"))[:40],
            w.get("dispatchId","?"), str(state or "?")[:12], nxt(p)[:60]))
else: print("живых работников нет")
if ask:
    print("\nзавершены, Orca просит действия (%d):" % len(ask))
    for w in ask:
        p=w.get("projection") or {}
        print("  %-18s %-10s %s" % (w.get("dispatchId","?"), p.get("outcome","?"), nxt(p) or "разобрать: read"))
if done:
    fail=sum(1 for w in done if (w.get("projection") or {}).get("outcome")=="failed")
    print("\nзавершённых без хвостов %d (неудач %d) — все: list все, убрать: sweep" % (len(done),fail))
PY
    rm -f "$W" "$T" "$R"
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
          # Контур игнорирует --types и будит на heartbeat: такие пачки подтверждаем молча
          # и ждём дальше, координатору возвращаемся только со смысловым событием.
          # Пачка переигрывается, пока её не подтвердить: прошлую подтверждаем при
          # следующем check — к этому моменту её события уже разобраны.
          mkdir -p "$TASKS"; LAST="$TASKS/.last-delivery"
          deadline=$(( $(date +%s) + MS/1000 )); DONE=""; HIT=""
          while [ "$(date +%s)" -lt "$deadline" ]; do
            left=$(( (deadline - $(date +%s)) * 1000 )); [ "$left" -gt 120000 ] && left=120000
            ACK=(); [ -s "$LAST" ] && ACK=(--ack "$(cat "$LAST")")
            OUT=$("$ORCA" orchestration check ${ACK[@]+"${ACK[@]}"} --wait --types "worker_done,escalation,question" --timeout-ms "$left" --json 2>/dev/null || true)
            RES=$(printf '%s' "$OUT" | python3 -c '
import json,sys
try: d=json.load(sys.stdin).get("result") or {}
except Exception: print("ACK"); print("RAW"); raise SystemExit
print("ACK " + (d.get("deliveryId") or ""))
ms=[x for x in (d.get("messages") or []) if x.get("type")!="heartbeat"]
if not ms: print("SKIP"); raise SystemExit
print("HIT")
for x in ms:
    t=x.get("type"); frm=str(x.get("from_handle","")).replace("dispatch:","")
    try: p=json.loads(x.get("payload") or "{}")
    except Exception: p={}
    who=p.get("dispatchId") or frm
    print("%-11s %s  %s" % (t, who, " ".join(str(x.get("subject","")).split())[:80]), file=sys.stderr)
    if t in ("escalation","worker_done"): print("  «%s»" % " ".join(str(x.get("body","")).split())[:400], file=sys.stderr)
    if t=="worker_done" and p.get("dispatchId"): print("DONE " + p["dispatchId"])')
            A=$(printf '%s\n' "$RES" | sed -n 's/^ACK //p'); printf '%s' "$A" > "$LAST" || true
            case "$RES" in *RAW*) echo "ответ check не разобран — повторяю"; sleep 2 ;; esac
            if printf '%s\n' "$RES" | grep -qx HIT; then
              HIT=1; DONE=$(printf '%s\n' "$RES" | sed -n 's/^DONE //p'); break
            fi
          done
          [ -n "$HIT" ] || echo "за $((MS/1000)) с смыслового события нет (таймаут — точка проверки, а не сбой)"
          # worker_done — терминал больше не нужен: вывод архивируется, журнал сессии остаётся.
          for D in $DONE; do
            # Проверка expect.sh, если она задана — ищем .dispatch файл с этим dispatch ID
            expect_checked=""
            for dispatch_file in "$TASKS"/*/.dispatch "$TASKS"/review-*/.dispatch; do
              if [ -f "$dispatch_file" ] && grep -qx "$D" "$dispatch_file"; then
                dir=$(dirname "$dispatch_file")
                task_key=$(basename "$dir" | sed 's/^review-//')
                is_review=$(basename "$dir" | grep -q '^review-' && echo "review" || echo "")
                if [ -f "$dir/expect.sh" ]; then
                  verify_result=$(verify_expect "$task_key" "$is_review" 2>&1)
                  verify_code=$?
                  echo "проверка $D:"
                  printf '%s\n' "$verify_result"
                  if [ $verify_code -ne 0 ]; then
                    echo "  → попробовать: scripts/gj/orchestrate.sh say $D \"…\""
                    if [ "${GJ_RETAIN:-}" != "1" ] && ! grep -qx "$D" "$(retain_list)" 2>/dev/null; then
                      echo "$D" >> "$(retain_list)"
                      "$ORCA" orchestration worker-retain --dispatch "$D" --json >/dev/null 2>&1 || true
                    fi
                  else
                    # Проверка прошла, отпускаем
                    line=$(release_one "$D"); echo "  ${line#*$'\t'}"
                  fi
                  expect_checked=1
                fi
                break
              fi
            done
            # Если expect не был проверен, то просто отпускаем
            if [ -z "$expect_checked" ]; then
              if [ "${GJ_RETAIN:-}" = "1" ] || grep -qx "$D" "$(retain_list)" 2>/dev/null; then
                echo "  $D оставлен (retain) — отпустить: orchestrate.sh release $D"
              else
                line=$(release_one "$D"); echo "  ${line#*$'\t'}"
              fi
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
