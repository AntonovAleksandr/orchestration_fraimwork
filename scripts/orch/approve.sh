#!/usr/bin/env bash
# Подтверждение внешнего действия пользователем. Запускает человек, не работник.
#   approve.sh            — список действий, ждущих подтверждения
#   approve.sh <код>      — разрешить ровно одно действие с этим кодом (однократно)
# Код выдаёт хук, когда блокирует действие (git-guard.py, approval-guard.py).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASKS=${ORCH_TASKS_DIR:-$ROOT/.tasks}
BASE="$TASKS/approvals"
PENDING="$BASE/pending"

if [ $# -eq 0 ]; then
  if [ ! -d "$PENDING" ] || [ -z "$(ls -A "$PENDING" 2>/dev/null)" ]; then
    echo "ждущих подтверждения действий нет"
    exit 0
  fi
  for f in "$PENDING"/*; do
    echo "$(basename "$f"): $(head -c 300 "$f")"
  done
  exit 0
fi

CODE=$1
if ! [[ "$CODE" =~ ^[0-9a-f]{12}$ ]]; then
  echo "код должен быть 12 шестнадцатеричных символов" >&2
  exit 2
fi
if [ ! -f "$PENDING/$CODE" ]; then
  echo "нет ждущего действия с кодом $CODE" >&2
  exit 1
fi
mkdir -p "$BASE"
mv "$PENDING/$CODE" "$BASE/$CODE"
echo "разрешено однократно:"
head -c 300 "$BASE/$CODE"
echo
