#!/bin/bash
# Create MR with registered base branch
# Usage: create-mr-with-base-branch.sh <task-key> <source-branch> [--title "title"] [--description "desc"]

set -euo pipefail

TASK_KEY="${1:?укажите ключ задачи (e.g., PROJ-500)}"
SOURCE_BRANCH="${2:?укажите исходную ветку (e.g., task-proj-500)}"
shift 2

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASKS_DIR="${ORCH_TASKS_DIR:-$ROOT/.tasks}"
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"

# Convert key to slug
slug() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//'
}

TASK_DIR="$TASKS_DIR/$(slug "$TASK_KEY")"

# Load base branch
if [ ! -f "$TASK_DIR/.base-branch" ]; then
  echo "❌ Base branch не зарегистрирована для $TASK_KEY" >&2
  echo "   Зарегистрируйте: scripts/orch/register-base-branch.sh $TASK_KEY <base-branch>" >&2
  exit 1
fi

BASE_BRANCH=$(cat "$TASK_DIR/.base-branch")
echo "📌 Используем base branch: $BASE_BRANCH"

# Parse additional arguments
TITLE=""
DESCRIPTION=""
while [ $# -gt 0 ]; do
  case "$1" in
    --title)
      TITLE="$2"
      shift 2
      ;;
    --description)
      DESCRIPTION="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

# Set default title if not provided
[ -z "$TITLE" ] && TITLE="$TASK_KEY"

# Create MR using glab
echo ""
echo "📝 Создаём MR:"
echo "   Задача: $TASK_KEY"
echo "   Source branch: $SOURCE_BRANCH"
echo "   Target branch: $BASE_BRANCH"
echo "   Title: $TITLE"
echo ""

# Try to detect project from source branch tracking
PROJECT=$(git symbolic-ref -q --short origin/HEAD 2>/dev/null | sed 's#origin/##' || echo "")
if [ -z "$PROJECT" ]; then
  echo "⚠️  Не удалось определить проект, используйте явно через --repo" >&2
  echo "   Пример: glab mr create ... --repo group/project" >&2
  exit 1
fi

# Construct glab command
CMD="glab mr create"
CMD="$CMD --source-branch $SOURCE_BRANCH"
CMD="$CMD --target-branch $BASE_BRANCH"
CMD="$CMD --title \"$TITLE\""
[ -n "$DESCRIPTION" ] && CMD="$CMD --description \"$DESCRIPTION\""

echo "Команда: $CMD"
echo ""

# Execute
eval "$CMD"

echo ""
echo "✅ MR создана с registered base branch: $BASE_BRANCH"
