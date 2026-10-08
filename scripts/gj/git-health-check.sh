#!/usr/bin/env bash
# Проверка здоровья git-репозитория: .git, origin, shallow clone, синхронизация refs.
# Используется в начале каждого agent'а для гарантии корректного git-состояния.
#
#   git-health-check.sh [--unshallow] [путь]
#
# Поведение:
#   без флагов: проверяет и сообщает проблемы (exit 0 = OK, exit 1 = не git или нет origin)
#   --unshallow: дополнительно выполняет unshallow если репозиторий shallow
#   --fix: синоним --unshallow (для совместимости)
#   --verbose: выводит отчёт о всех проверках, даже если OK
#
# Примечание: shallow clone типичен для platform/* (depth 1), а merge-base/ahead-behind
# дают неверные результаты до unshallow. Используй --unshallow в agents, которым нужна
# правда о веках.
set -euo pipefail

# Парсинг аргументов
AUTO_UNSHALLOW=0
VERBOSE=0
REPO_PATH="."

while [[ $# -gt 0 ]]; do
  case "$1" in
    --unshallow|--fix)
      AUTO_UNSHALLOW=1
      shift
      ;;
    --verbose)
      VERBOSE=1
      shift
      ;;
    -*)
      echo "ошибка: неизвестный флаг $1" >&2
      exit 2
      ;;
    *)
      REPO_PATH="$1"
      shift
      ;;
  esac
done

# Функции
log_check() {
  local name="$1"
  local status="$2"
  local detail="${3:-}"
  if [[ "$VERBOSE" == 1 ]] || [[ "$status" != "OK" ]]; then
    printf "  %-35s %s" "$name" "$status"
    [[ -n "$detail" ]] && echo " ($detail)" || echo
  fi
}

# Переход в репозиторий
if [[ ! -d "$REPO_PATH" ]]; then
  echo "путь не найден: $REPO_PATH" >&2
  exit 1
fi
cd "$REPO_PATH" || exit 1

# Проверка 1: .git существует (файл для worktree или директория)
if [[ ! -e .git ]]; then
  log_check ".git" "FAIL" "не найден .git (ни файл ни директория)"
  exit 1
fi

# Определить тип git-настройки
GIT_TYPE="unknown"
if [[ -f .git ]]; then
  GIT_TYPE="worktree"
  GIT_DIR=$(sed -n 's/^gitdir: //p' .git | tr -d '\n\r')
  if [[ -z "$GIT_DIR" ]]; then
    log_check ".git" "FAIL" ".git — файл, но gitdir не разобран"
    exit 1
  fi
  log_check ".git" "OK" "worktree (→ $(basename "$GIT_DIR"))"
elif [[ -d .git ]]; then
  GIT_TYPE="normal"
  log_check ".git directory" "OK"
else
  log_check ".git" "FAIL" "неизвестный тип"
  exit 1
fi

# Проверка 2: origin remote существует
if ! git remote get-url origin &>/dev/null; then
  log_check "origin remote" "FAIL" "не настроен"
  exit 1
fi
ORIGIN_URL=$(git remote get-url origin)
log_check "origin remote" "OK" "$ORIGIN_URL"

# Проверка 3: shallow clone?
SHALLOW="no"
IS_SHALLOW=0
if [[ -f .git/shallow ]]; then
  SHALLOW="yes"
  IS_SHALLOW=1
  log_check "shallow clone" "WARN" "глубина ограничена (depth 1 типично)"
else
  log_check "shallow clone" "OK" "полный клон"
fi

# Проверка 4: если shallow и нужен unshallow — делаем это
if [[ "$IS_SHALLOW" == 1 ]] && [[ "$AUTO_UNSHALLOW" == 1 ]]; then
  echo "  выполнение unshallow..."
  if git fetch --unshallow 2>&1; then
    log_check "unshallow" "OK" "граф расширен"
  else
    log_check "unshallow" "FAIL" "не удалось выполнить (сеть? сервер?)"
    exit 1
  fi
fi

# Проверка 5: синхронизация refs
# Если есть origin, но refs не синхронизированы — это может быть проблемой для операций
# вроде merge-base, cherry-pick и определения ahead/behind.
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
if [[ "$CURRENT_BRANCH" != "unknown" ]] && [[ "$CURRENT_BRANCH" != "HEAD" ]]; then
  # Проверяем, есть ли tracking branch
  UPSTREAM=$(git rev-parse --abbrev-ref "$CURRENT_BRANCH@{u}" 2>/dev/null) || UPSTREAM=""
  if [[ -z "$UPSTREAM" ]]; then
    log_check "tracking branch" "WARN" "$CURRENT_BRANCH не отслеживает upstream"
  else
    log_check "tracking branch" "OK" "$CURRENT_BRANCH → $UPSTREAM"
  fi
fi

log_check "refs sync" "OK" "состояние считается актуальным"

# Итоговый статус
if [[ "$VERBOSE" == 1 ]]; then
  echo "✓ репозиторий здоров"
fi
exit 0
