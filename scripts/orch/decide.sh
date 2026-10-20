#!/usr/bin/env bash
# Журнал решений по задаче: решения пользователя и аналитика не переоткрываются
# без новых фактов. Файл: .tasks/<ключ>/decisions.md
#   decide.sh <КЛЮЧ> "<решение>" [--from "<кто решил>"]   — записать решение
#   decide.sh <КЛЮЧ>                                       — показать журнал
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASKS=${ORCH_TASKS_DIR:-$ROOT/.tasks}
KEY=${1:?укажите ключ задачи}; shift
SLUG=$(echo "$KEY" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//')
DIR="$TASKS/$SLUG"
FILE="$DIR/decisions.md"

if [ $# -eq 0 ]; then
  [ -f "$FILE" ] && cat "$FILE" || echo "решений по $KEY нет"
  exit 0
fi

TEXT=$1; shift
FROM=""
while [ $# -gt 0 ]; do
  case "$1" in
    --from) FROM=$2; shift 2 ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
done
[ -n "$TEXT" ] || { echo "решение не может быть пустым" >&2; exit 2; }

mkdir -p "$DIR"
[ -f "$FILE" ] || printf '# Решения по %s\n\n' "$KEY" > "$FILE"
STAMP=$(date '+%Y-%m-%d %H:%M')
if [ -n "$FROM" ]; then
  printf -- '- %s — %s (от: %s)\n' "$STAMP" "$TEXT" "$FROM" >> "$FILE"
else
  printf -- '- %s — %s\n' "$STAMP" "$TEXT" >> "$FILE"
fi
echo "записано в $FILE"
