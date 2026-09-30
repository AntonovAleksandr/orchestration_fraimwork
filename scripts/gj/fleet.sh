#!/usr/bin/env bash
# Пакетный запуск задач: одна команда — несколько работников, каждый со своей вкладкой.
#
# Вкладки Orca даёт сама: один работник — один терминал в дереве. Отдельное дерево
# заводится, когда задача идёт в другом контексте (другая ветка, другой релиз) —
# тогда у неё свой рабочий каталог и своя вкладка верхнего уровня.
#
#   fleet.sh run  <КЛЮЧ>[:вид][@дерево] ...   запустить пачку
#   fleet.sh status                            сводка по всем работникам
#   fleet.sh watch [мс]                        ждать событий и докладывать
#   fleet.sh stop  <dispatch|все>              остановить
#
# вид   — task (по умолчанию) | front | review
# @дерево — имя дерева Orca. Нет такого — будет создано от main. Без @ — текущее.
#
#   fleet.sh run OPSOMN002-294 OPSOMN002-295
#   fleet.sh run OPSOMN002-294 OPSOMN002-416:front@beauty-416
#
# Заслон по ресурсам наследуется от orchestrate.sh: GJ_MAX_AGENTS, GJ_MIN_FREE_MB.
# Пачка запускается последовательно и останавливается на первом отказе заслона —
# чтобы не выяснять постфактум, что половина не стартовала.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ORCA=${GJ_ORCA_BIN:-orca}
ORCH="$ROOT/scripts/gj/orchestrate.sh"
STATE=${GJ_FLEET_STATE:-$ROOT/.tasks/fleet.tsv}

have() { command -v "$ORCA" >/dev/null 2>&1; }

# Дерево по имени: вернуть путь, создав при отсутствии.
resolve_tree() {
  local name=$1 p
  p=$("$ORCA" worktree list --json 2>/dev/null | python3 -c "
import json,sys
try: ws=json.load(sys.stdin)['result']
except Exception: sys.exit(1)
ws=ws.get('worktrees') or ws.get('items') or []
for w in ws:
    if str(w.get('displayName','')).lower()=='$name'.lower() or \
       str(w.get('name','')).lower()=='$name'.lower():
        print(w.get('path','')); break
" 2>/dev/null)
  [ -n "$p" ] && { printf '%s' "$p"; return 0; }
  echo "дерева «$name» нет — создаю от main" >&2
  "$ORCA" worktree create --name "$name" --repo "path:$ROOT" --base-branch main --json >/dev/null 2>&1 \
    || { echo "не удалось создать дерево «$name»" >&2; return 1; }
  sleep 2
  resolve_tree "$name"
}

run_one() {                       # run_one <ключ> <вид> <дерево|"">
  local key=$1 kind=$2 tree=$3 dir="" out
  if [ -n "$tree" ]; then
    dir=$(resolve_tree "$tree") || return 1
    # В новом дереве нет клонов platform/* — предупреждаем сразу, а не после часа работы.
    local n=0; for g in "$dir"/platform/*/*/.git; do [ -e "$g" ] && n=$((n+1)); done
    [ "$n" -eq 0 ] && echo "  ВНИМАНИЕ: в «${tree}» нет клонов platform/* — задача по коду платформ там не пойдёт" >&2
  fi
  echo "── $key ($kind)${tree:+ → дерево ${tree}}"
  if [ -n "$dir" ]; then
    out=$(GJ_WORKTREE="path:$dir" "$ORCH" "$kind" "$key" 2>&1)
  else
    out=$("$ORCH" "$kind" "$key" 2>&1)
  fi
  [ $? -eq 0 ] || { printf '%s\n' "$out" | sed 's/^/   /'; return 1; }
  printf '%s\n' "$out" | sed 's/^/   /'
  local disp; disp=$(printf '%s' "$out" | sed -n 's/^Dispatch: *//p' | head -1)
  [ -n "$disp" ] && printf '%s\t%s\t%s\t%s\t%s\n' "$key" "$kind" "${tree:-current}" "$disp" "$(date +%FT%T)" >> "$STATE"
  return 0
}

case "${1:-}" in
  run)
    shift; [ $# -gt 0 ] || { echo "укажите ключи задач" >&2; exit 1; }
    have || { echo "orca не найдена" >&2; exit 1; }
    mkdir -p "$(dirname "$STATE")"
    ok=0; fail=0
    for spec in "$@"; do
      key=${spec%%[:@]*}
      rest=${spec#"$key"}
      kind=task; tree=""
      case "$rest" in
        :*@*) kind=${rest#:}; kind=${kind%%@*}; tree=${rest#*@} ;;
        :*)   kind=${rest#:} ;;
        @*)   tree=${rest#@} ;;
      esac
      if run_one "$key" "$kind" "$tree"; then ok=$((ok+1)); else
        fail=$((fail+1))
        echo "   остановка пачки: дальше не запускаю, чтобы не гадать что стартовало" >&2
        break
      fi
      echo
    done
    echo "запущено $ok, не удалось $fail"
    [ "$ok" -gt 0 ] && { echo; echo "следить:  scripts/gj/fleet.sh status"; echo "ждать:    scripts/gj/fleet.sh watch"; }
    ;;

  status)
    have || { echo "orca не найдена" >&2; exit 1; }
    [ -f "$STATE" ] && { echo "запуски этой пачки:"; awk -F'\t' '{printf "  %-20s %-7s %-16s %s\n",$1,$2,$3,$4}' "$STATE" | tail -12; echo; }
    "$ORCA" orchestration worker-list --include-remote 2>/dev/null | head -20 \
      || echo "работников нет либо Run не привязан"
    ;;

  watch)
    # Тот же цикл, что у оркестратора: открытые вопросы, новые события, закрытие
    # терминалов по worker_done. Своя копия разбора расходилась с ним и не закрывала ничего.
    exec "$ORCH" wait "${2:-900000}"
    ;;

  stop)
    T=${2:?укажите dispatch либо «все»}
    if [ "$T" = "все" ]; then
      [ -f "$STATE" ] || { echo "нечего останавливать"; exit 0; }
      cut -f4 "$STATE" | sort -u | while read -r d; do
        [ -n "$d" ] && { "$ORCA" orchestration worker-stop --dispatch "$d" --json >/dev/null 2>&1 && echo "  остановлен $d"; }
      done
    else
      "$ORCA" orchestration worker-stop --dispatch "$T" --json >/dev/null 2>&1 && echo "остановлен $T"
    fi
    ;;

  *) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
