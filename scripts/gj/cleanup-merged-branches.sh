#!/usr/bin/env bash
# Автоматическая очистка веток после успешного merge запросов задачи.
# Удаляет локальные и удалённые ветки задачи, которые уже слиты.
#
#   cleanup-merged-branches.sh <КЛЮЧ>          очистить ветки задачи
#   cleanup-merged-branches.sh --dry-run <КЛЮЧ>  показать, что будет удалено
#   cleanup-merged-branches.sh --log <КЛЮЧ>      показать лог очистки
#
# Файлы:
#   .tasks/<ключ>/branches.log   — логирование удалённых веток и ошибок
#   .tasks/<ключ>/cleanup.state  — состояние последней очистки
#
# Переменные:
#   GJ_TASKS_DIR  (.tasks)
#   GJ_SKIP_CLEANUP=1  — не удалять ветки, только проверить и залогировать
#   GJ_DRY_RUN=1  — показать что будет удалено, но ничего не удалять
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASKS=${GJ_TASKS_DIR:-$ROOT/.tasks}

slug() { echo "$1" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//'; }

log_cleanup() {
  local key=$1 msg=$2 status=${3:-info}
  local dir="$TASKS/$(slug "$key")"
  local log="$dir/branches.log"
  mkdir -p "$dir"
  printf '[%s] %s: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$status" "$msg" >> "$log"
}

log_state() {
  local key=$1 status=$2
  local dir="$TASKS/$(slug "$key")"
  mkdir -p "$dir"
  {
    echo "last_run=$(date +%s)"
    echo "last_status=$status"
    echo "last_message_timestamp=$(date '+%Y-%m-%d %H:%M:%S')"
  } > "$dir/cleanup.state"
}

# Получить все ветки репозитория из .dispatch файла, найти репы в git-истории
find_task_repos() {
  local key=$1
  local task_dir="$TASKS/$(slug "$key")"

  # Если есть .dispatch файл, значит есть клоны платформ
  if [ ! -d "$ROOT/.git" ]; then
    echo "не git-репо: $ROOT" >&2
    return 1
  fi

  # Ищем все репозитории платформ: platform/*/*, platform-new/*, platform-next/*
  local -a repos
  repos=()
  for d in "$ROOT"/platform/*/*/.git "$ROOT"/platform-new/*/.git "$ROOT"/platform-next/*/.git "$ROOT"/platform/*/.git; do
    [ -d "$d" ] && repos+=("$(dirname "$d")")
  done

  if [ ${#repos[@]} -eq 0 ]; then
    echo "не найдено репозиториев платформ в $ROOT" >&2
    return 1
  fi

  printf '%s\n' "${repos[@]}"
}

# Получить все ветки, связанные с задачей (из комментариев коммитов, имён веток)
find_task_branches() {
  local key=$1 pattern=$2
  local -a all_branches

  for repo in $(find_task_repos "$key" 2>/dev/null); do
    [ -d "$repo/.git" ] || continue

    # Ищем локальные ветки по паттерну задачи
    while IFS= read -r branch; do
      [ -n "$branch" ] && echo "local:$repo:$branch"
    done < <(cd "$repo" && git for-each-ref --format='%(refname:short)' 'refs/heads/*' 2>/dev/null | grep -E "(^|/)$pattern(-|/|$)" || true)

    # Ищем удалённые ветки по паттерну
    while IFS= read -r branch; do
      [ -n "$branch" ] && echo "remote:$repo:$branch"
    done < <(cd "$repo" && git for-each-ref --format='%(refname:short)' 'refs/remotes/*' 2>/dev/null | grep -E "(^|/)$pattern(-|/|$)" || true)
  done
}

# Проверить, является ли ветка merged (её коммиты в main/master)
is_branch_merged() {
  local repo=$1 branch=$2
  local base_branch=''

  [ -d "$repo/.git" ] || return 1

  # Определяем базовую ветку
  cd "$repo"
  if git rev-parse --verify origin/main >/dev/null 2>&1; then
    base_branch="origin/main"
  elif git rev-parse --verify origin/master >/dev/null 2>&1; then
    base_branch="origin/master"
  elif git rev-parse --verify main >/dev/null 2>&1; then
    base_branch="main"
  elif git rev-parse --verify master >/dev/null 2>&1; then
    base_branch="master"
  else
    # Не можем определить базовую ветку
    return 1
  fi

  # Проверяем merged
  git merge-base --is-ancestor "$branch" "$base_branch" 2>/dev/null || return 1
}

# Удалить локальную ветку
delete_local_branch() {
  local repo=$1 branch=$2 dry_run=${3:-}

  [ -d "$repo/.git" ] || return 1

  if [ -n "$dry_run" ]; then
    echo "  [DRY RUN] удалить локально: $branch из $repo"
    return 0
  fi

  cd "$repo"
  if git branch -D "$branch" >/dev/null 2>&1; then
    echo "  удалена локально: $branch"
    return 0
  else
    echo "  ошибка при удалении $branch из $repo" >&2
    return 1
  fi
}

# Удалить удалённую ветку
delete_remote_branch() {
  local repo=$1 branch=$2 dry_run=${3:-}
  local remote="${branch%/*}"
  local remote_branch="${branch#*/}"

  [ -d "$repo/.git" ] || return 1

  if [ -n "$dry_run" ]; then
    echo "  [DRY RUN] удалить удалённо: $remote_branch из $remote"
    return 0
  fi

  cd "$repo"
  if git push "$remote" --delete "$remote_branch" >/dev/null 2>&1; then
    echo "  удалена удалённо: $remote_branch из $remote"
    return 0
  else
    echo "  ошибка при удалении $remote_branch из $remote" >&2
    return 1
  fi
}

# Главная функция очистки
cleanup_merged_branches() {
  local key=$1 dry_run=${2:-}
  local pattern=$(slug "$key")

  echo "Очистка веток задачи: $key (паттерн: $pattern)"
  echo

  local deleted_count=0
  local error_count=0

  # Найти все ветки по паттерну
  while IFS=: read -r branch_type repo branch; do
    [ -z "$repo" ] && continue
    [ -z "$branch" ] && continue

    # Проверяем merged-ли ветка
    if ! is_branch_merged "$repo" "$branch" 2>/dev/null; then
      echo "  [NOT MERGED] $branch в $repo — оставляем"
      continue
    fi

    echo "Удаляем: $branch из $(basename "$repo")"

    case "$branch_type" in
      local)
        if delete_local_branch "$repo" "$branch" "$dry_run"; then
          deleted_count=$((deleted_count + 1))
          log_cleanup "$key" "удалена локально: $branch из $repo" "success"
        else
          error_count=$((error_count + 1))
          log_cleanup "$key" "ошибка при удалении $branch из $repo" "error"
        fi
        ;;
      remote)
        if delete_remote_branch "$repo" "$branch" "$dry_run"; then
          deleted_count=$((deleted_count + 1))
          log_cleanup "$key" "удалена удалённо: $branch из $repo" "success"
        else
          error_count=$((error_count + 1))
          log_cleanup "$key" "ошибка при удалении $branch из $repo" "error"
        fi
        ;;
    esac
  done < <(find_task_branches "$key" "$pattern" 2>/dev/null)

  echo
  echo "=========================================="
  echo "Результат очистки для задачи: $key"
  echo "Удалено веток: $deleted_count"
  [ "$error_count" -gt 0 ] && echo "Ошибок: $error_count"
  echo "=========================================="

  if [ -z "$dry_run" ]; then
    if [ "$error_count" -eq 0 ]; then
      log_state "$key" "success"
    else
      log_state "$key" "partial_failure"
    fi
  fi

  return $((error_count > 0 ? 1 : 0))
}

# Показать лог очистки
show_cleanup_log() {
  local key=$1
  local dir="$TASKS/$(slug "$key")"
  local log="$dir/branches.log"
  local state="$dir/cleanup.state"

  if [ ! -f "$log" ]; then
    echo "нет логов очистки для задачи: $key"
    return 0
  fi

  echo "=== Логи очистки веток для задачи: $key ==="
  echo
  tail -20 "$log"
  echo

  if [ -f "$state" ]; then
    echo "=== Состояние последней очистки ==="
    cat "$state"
  fi
}

# Показать справку
show_help() {
  sed -n '2,/^#$/p' "$0" | sed 's/^# \{0,1\}//;/^$/d'
}

# Основная ветка скрипта
main() {
  local cmd="" key=""

  case "${1:-}" in
    --help|-h|"")
      show_help
      exit 0
      ;;
    --dry-run)
      GJ_DRY_RUN=1
      cmd="cleanup"
      key=${2:?укажите ключ задачи}
      ;;
    --log)
      cmd="log"
      key=${2:?укажите ключ задачи}
      ;;
    *)
      cmd="cleanup"
      key=${1:?укажите ключ задачи}
      ;;
  esac

  case "$cmd" in
    cleanup)
      cleanup_merged_branches "$key" "${GJ_DRY_RUN:-}"
      ;;
    log)
      show_cleanup_log "$key"
      ;;
  esac
}

main "$@"
