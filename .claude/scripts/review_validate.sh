#!/bin/bash
# review_validate.sh — валидатор формата code review комментариев
# Использование: ./review_validate.sh <markdown-file> [strict|warn]
#
# Возвращает: 0 если OK, 1 если ошибки (strict режим)

set -o pipefail

MODE="${2:-warn}"  # warn (default) или strict
FILE="${1:--}"     # stdin если не указано
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Цвета для вывода
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# Функции логирования
error() {
  echo -e "${RED}❌ ERROR${NC}: $1" >&2
  ((ERRORS++))
}

warn() {
  echo -e "${YELLOW}⚠️  WARN${NC}: $1" >&2
  ((WARNINGS++))
}

ok() {
  echo -e "${GREEN}✅${NC} $1"
}

# Прочитать файл (или stdin)
if [[ "$FILE" == "-" ]]; then
  CONTENT=$(cat)
else
  if [[ ! -f "$FILE" ]]; then
    error "Файл не найден: $FILE"
    exit 1
  fi
  CONTENT=$(cat "$FILE")
fi

# === ПРОВЕРКИ ===

# 1. Есть ли заголовок с типом [TYPE]?
if ! echo "$CONTENT" | grep -q '^\[MUST\]\|\[SHOULD\]\|\[NIT\]\|\[SECURITY\]\|\[PERF\]\|\[TEST\]'; then
  error "Отсутствует тип комментария: [MUST], [SHOULD], [NIT], [SECURITY], [PERF] или [TEST]"
else
  TYPE=$(echo "$CONTENT" | head -1 | grep -oE '\[(MUST|SHOULD|NIT|SECURITY|PERF|TEST)\]' | head -1)
  ok "Тип найден: $TYPE"
fi

# 2. Есть ли заголовок (не пусто после типа)?
FIRST_LINE=$(echo "$CONTENT" | head -1)
if [[ ! "$FIRST_LINE" =~ [A-Za-zА-Яа-яЁё0-9] ]]; then
  error "Заголовок пуст или слишком короткий"
else
  ok "Заголовок: ${FIRST_LINE:0:80}"
fi

# 3. Есть ли раздел **Проблема:**?
if ! echo "$CONTENT" | grep -q '^\*\*Проблема:\*\*'; then
  error "Отсутствует раздел **Проблема:**"
else
  ok "Раздел **Проблема:** найден"
fi

# 4. Есть ли раздел **Почему:** ИЛИ ссылка?
HAS_WHY=$(echo "$CONTENT" | grep -q '^\*\*Почему:\*\*' && echo "yes" || echo "no")
HAS_LINK=$(echo "$CONTENT" | grep -qE 'https?://|OPSOMN|AP-|см\.|ссылка' && echo "yes" || echo "no")

if [[ "$HAS_WHY" == "yes" ]]; then
  ok "Раздел **Почему:** найден"
elif [[ "$HAS_LINK" == "yes" ]]; then
  warn "Раздел **Почему:** не найден, но есть ссылка/ссылка на контракт"
else
  error "Отсутствует раздел **Почему:** или ссылка на внешний источник"
fi

# 5. Есть ли раздел **Решение:**?
if ! echo "$CONTENT" | grep -q '^\*\*Решение:\*\*'; then
  error "Отсутствует раздел **Решение:**"
else
  ok "Раздел **Решение:** найден"
fi

# 6. Нет ли "TODO", "FIXME", "потом", "позже"?
if echo "$CONTENT" | grep -qiE '(TODO|FIXME|HACK|потом|позже|later|later on|после|потім)'; then
  warn "Найдены временные маркеры (TODO, FIXME, потом, позже) — это для коммитов, не для review"
fi

# 7. Нет ли просто благодарностей?
if echo "$CONTENT" | grep -qiE '(спасибо|thanks|прикольно|nice|cool)' && [[ $ERRORS -eq 0 ]]; then
  warn "Найдено выражение благодарности — оставить только если в контексте проблемы"
fi

# 8. Нет ли более 3 параграфов в Проблема/Почему/Решение?
PROBLEM_SECTION=$(echo "$CONTENT" | sed -n '/^\*\*Проблема:\*\*/,/^\*\*[^*]/p' | wc -l)
if [[ $PROBLEM_SECTION -gt 10 ]]; then
  warn "Раздел **Проблема:** очень длинный (>10 строк) — рассмотреть вынос в docs/"
fi

# 9. Проверить что нет закомментированного кода внутри
if echo "$CONTENT" | grep -E '^\s*(//|#|/\*)' | grep -qv '^#'; then
  warn "Обнаружен закомментированный код — удалить"
fi

# 10. Проверить что нет "очевидно" слов
if echo "$CONTENT" | grep -qiE '(очевидно|явно что|конечно|всем известно|любой знает)'; then
  error "'Очевидно' слова = опасный антипаттерн — изъяснить конкретно"
fi

# 11. Проверить что заголовок не более 100 символов
TITLE_LENGTH=${#FIRST_LINE}
if [[ $TITLE_LENGTH -gt 100 ]]; then
  warn "Заголовок слишком длинный ($TITLE_LENGTH > 100 символов)"
fi

# 12. Для [TEST] проверить что нет расхождения (если говорит что тесты есть, но нет)
if echo "$FIRST_LINE" | grep -q '\[TEST\]'; then
  if ! echo "$CONTENT" | grep -q 'test'; then
    warn "[TEST] тип выбран, но слово 'test' в комментарии не найдено"
  fi
fi

# === ИТОГИ ===
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ $ERRORS -eq 0 && $WARNINGS -eq 0 ]]; then
  echo -e "${GREEN}✅ Комментарий соответствует формату${NC}"
  exit 0
elif [[ $ERRORS -eq 0 ]]; then
  echo -e "${YELLOW}⚠️  Найдено предупреждений: $WARNINGS${NC}"
  if [[ "$MODE" == "strict" ]]; then
    exit 1
  fi
  exit 0
else
  echo -e "${RED}❌ Найдено ошибок: $ERRORS, предупреждений: $WARNINGS${NC}"
  exit 1
fi
