# Code Review Comments Format — Quick Start

**Задача:** Создать обязательный формат для комментариев code-review, используемый `review_post.py` и агентами.

**Статус:** ✅ Готово (версия 1.0)

---

## Созданные файлы

### 1. **`.claude/rules/code-review-comments-format.md`** (обязательное правило)

Основной документ с обязательным форматом для всех комментариев code-review.

**Содержит:**
- Два формата: inline (в коде на строке) и separate notes (общие замечания)
- Обязательная структура: [ТИП] + Проблема + Почему + Решение
- Типы комментариев: [MUST], [SHOULD], [NIT], [SECURITY], [PERF], [TEST]
- Примеры хороших и плохих комментариев
- Запреты (что не писать)
- Интеграция с `review_post.py`

**Используется:** Все агенты code-review (ensi-gitlab-mr-review, site-gitlab-mr-review, и т.д.)

**Как читать:** Перед каждым code-review открыть этот файл и проверить структуру.

---

### 2. **`.claude/scripts/review_validate.sh`** (валидатор)

Bash-скрипт для автоматической проверки формата комментариев.

**Проверяет:**
- ✅ Есть ли [ТИП] ([MUST], [SHOULD], [NIT], [SECURITY], [PERF], [TEST])?
- ✅ Есть ли раздел **Проблема:**?
- ✅ Есть ли раздел **Почему:** или ссылка?
- ✅ Есть ли раздел **Решение:**?
- ✅ Нет ли "TODO", "FIXME", "потом", "позже"?
- ✅ Нет ли благодарностей и эмодзи?
- ✅ Заголовок не более 100 символов?

**Использование:**
```bash
# Проверить комментарий
./.claude/scripts/review_validate.sh comment.md

# Strict режим (отклонит даже предупреждения)
./.claude/scripts/review_validate.sh comment.md strict

# Из stdin
cat comment.md | ./.claude/scripts/review_validate.sh -
```

**Вывод:**
```
❌ ERROR: Отсутствует раздел **Решение:**
❌ ERROR: Отсутствует тип комментария
⚠️  WARN: Раздел **Проблема:** очень длинный (>10 строк)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ Найдено ошибок: 2, предупреждений: 1
```

---

### 3. **`.claude/guides/code-review-comments-checklist.md`** (checklist для ревьюеров)

Пошаговая инструкция для code-review агентов и разработчиков.

**Содержит:**
- Шаг 1: Определить тип (MUST, SHOULD, NIT, SECURITY, PERF, TEST)
- Шаг 2: Проверить структуру
- Шаг 3: Запустить валидацию
- Шаг 4: Проверить запреты
- Примеры по каждому типу комментария
- Плохо → Хорошо трансформации
- Интеграция в skills
- Exit checklist перед завершением ревью

---

### 4. **`.claude/guides/code-review-integration-example.md`** (примеры интеграции)

Конкретные примеры как использовать формат в разных skills и на разных платформах.

**Содержит:**
- Шаблон для обновления skill-документа
- Примеры для ENSI, Site, Mobile, OMS, Integration, Gloria OTS
- CI/CD интеграция (GitLab CI, GitHub Actions)
- Как интегрировать в `review_post.py`

---

### 5. **`.claude/rules/README.md`** (обновлено)

Обновлена таблица файлов в папке rules с указанием на новый файл.

---

## Как использовать

### Для агентов code-review

**1. Перед написанием комментария:**
```bash
# Прочитать формат
cat .claude/rules/code-review-comments-format.md

# Или быстро:
head -100 .claude/rules/code-review-comments-format.md
```

**2. Написать комментарий в формате:**
```markdown
[MUST] SQL injection на стр. 42

**Проблема:** 
SELECT * FROM orders WHERE id=$id — прямая конкатенация

**Почему:** 
SQL injection (OWASP); пользователь может удалить таблицу

**Решение:**
→ $stmt = $pdo->prepare("SELECT * FROM orders WHERE id=?");
→ $stmt->execute([$id]);
```

**3. Валидировать:**
```bash
./.claude/scripts/review_validate.sh my_comment.md
# Результат: ✅ Комментарий соответствует формату
```

**4. Отправить в GitLab** (через MR API или вручную)

---

### Для review_post.py (скрипт Anatoliy'я)

```python
# Pseudocode
from review_post import ReviewComment, ReviewCommentValidator

# Прочитать комментарий
comment_text = """
[MUST] Отсутствует проверка прав

**Проблема:** ...
**Почему:** ...
**Решение:** ...
"""

# Валидировать
validator = ReviewCommentValidator()
is_valid, errors = validator.validate(comment_text)

if not is_valid:
    print("Ошибка формата:")
    for error in errors:
        print(f"  ❌ {error}")
    exit(1)

# Отправить в GitLab MR
mr = gitlab.projects.get(project_id).mergerequests.get(mr_id)
mr.notes.create({'body': comment_text})

# Если [MUST] → запросить изменения
if '[MUST]' in comment_text:
    mr.notes.create({'body': '/request_changes'})
```

---

### Для проверки в CI/CD

**GitLab CI:**
```yaml
validate_review_format:
  stage: test
  script:
    - ./.claude/scripts/review_validate.sh .review_comment.md strict
  only:
    - merge_requests
```

**GitHub Actions:**
```yaml
- name: Validate review format
  run: ./.claude/scripts/review_validate.sh .review_comment.md strict
```

---

## Типы комментариев — таблица

| Тип | Блокирует | Когда | Пример |
|-----|-----------|-------|--------|
| **[MUST]** | ✅ Да | Нарушение AC / контракта / безопасности / архитектуры | "SQL injection", "API спека не обновлена" |
| **[SHOULD]** | ❌ Нет | Рекомендация (оптимизация, паттерн, улучшение) | "Оптимизировать N+1 query", "Использовать enum" |
| **[NIT]** | ❌ Нет | Опциональное улучшение (имя переменной, стиль) | "Переименовать `x` в `order_count`" |
| **[SECURITY]** | ✅ Да | Уязвимость (SQL injection, XSS, auth bypass) | "Прямой доступ к чужому заказу" |
| **[PERF]** | ❌ Нет | Проблема производительности | "N+1 queries", "O(N²) алгоритм" |
| **[TEST]** | Зависит | Отсутствие или неправильность тестов | "Нет e2e для нового flow" |

---

## Валидация — чек-лист

**Каждый комментарий ДОЛЖЕН иметь:**

- ✅ `[ТИП]` в первой строке
- ✅ Заголовок (не пусто, макс 100 символов)
- ✅ Раздел `**Проблема:**` (что конкретно неправильно)
- ✅ Раздел `**Почему:**` или ссылка на источник (контракт, AC, задача)
- ✅ Раздел `**Решение:**` (конкретное действие)

**Что НЕ писать:**

- ❌ Процесс / историю ("на ревью заметили", "потом сделайте")
- ❌ "TODO", "FIXME", "потом", "позже"
- ❌ Закомментированный код
- ❌ Благодарности / эмодзи
- ❌ "Очевидно", "любой знает", "ясно же"
- ❌ Ссылки без контекста

---

## Примеры — быстрый старт

### ✅ Хороший [MUST]

```
[MUST] SQL injection на стр. 42

**Проблема:** SELECT * FROM orders WHERE id=$id

**Почему:** SQL injection (OWASP); пользователь может удалить таблицу

**Решение:**
→ $stmt = $pdo->prepare("SELECT * FROM orders WHERE id=?");
→ $stmt->execute([$id]);
```

### ✅ Хороший [SHOULD]

```
[SHOULD] Оптимизировать N+1 запрос

**Проблема:** Цикл запрашивает цену каждого товара отдельно (100 товаров = 100 запросов)

**Почему:** 100 запросов × 50ms = 5 секунд задержки; batch-запрос = 50ms

**Решение:**
Использовать catalog.getPrices([ids]) вместо getPrice(id) в цикле
```

### ✅ Хороший [SECURITY]

```
[SECURITY] Прямой доступ к чужим заказам

**Проблема:** GET /api/orders/{id} не проверяет userId; может получить чужой заказ

**Почему:** Утечка адресов, платежей, личных данных; нарушение авторизации (OWASP)

**Решение:**
1. if (order.userId !== currentUser.id) return 403
2. Добавить e2e тест: user A пытается получить order user B → 403
```

---

## Интеграция с skills

Каждый skill code-review **ДОЛЖЕН** упомянуть формат:

```markdown
## Формат комментариев (обязательно!)

Все комментарии следуют `.claude/rules/code-review-comments-format.md`:
- [MUST], [SHOULD], [NIT], [SECURITY], [PERF], [TEST]
- Структура: Проблема + Почему + Решение
- Валидировать: ./.claude/scripts/review_validate.sh comment.md
```

**Эффект:**
- Все ревьюеры пишут в едином формате
- Агенты могут автоматизировать проверку
- `review_post.py` может парсить и отправлять правильно
- CI/CD может валидировать в pipelines

---

## История версий

| Версия | Дата | Статус | Изменения |
|--------|------|--------|-----------|
| **1.0** | 2026-10-08 | ✅ Production-ready | Первоначальный формат (inline + separate), валидатор, примеры интеграции |

---

## Файлы для быстрого доступа

```
.claude/
├── rules/
│   ├── code-review-comments-format.md  ← ЧИТАТЬ ЭТОТ
│   ├── code-comments.md                ← Для комментариев в коде
│   └── README.md
├── scripts/
│   └── review_validate.sh              ← ЗАПУСКАТЬ ЭТОТ
└── guides/
    ├── code-review-comments-checklist.md         ← Checklist для ревьюеров
    ├── code-review-integration-example.md        ← Примеры по платформам
    └── code-review-format-README.md              ← Этот файл (overview)
```

---

## Следующие шаги (для team leads / Anatoliy'я)

1. **Прочитать** `.claude/rules/code-review-comments-format.md`
2. **Интегрировать** в `review_post.py`:
   - Парсить [ТИП] из комментария
   - Валидировать структуру (Проблема + Почему + Решение)
   - Отправлять в GitLab (inline или общий note)
   - Если [MUST] → `/request_changes`
3. **Обновить** skills (ensi-gitlab-mr-review и т.д.):
   - Добавить ссылку на `.claude/rules/code-review-comments-format.md`
   - Добавить в exit checklist валидацию
4. **Добавить в CI/CD:**
   - `review_validate.sh` в pipelines (optional, для строгости)
5. **Обучить** агентов:
   - Добавить в system prompts все skills
   - Связать с `.claude/guides/code-review-comments-checklist.md`

---

**Вопросы?** Смотри `.claude/guides/code-review-comments-checklist.md` или примеры в `.claude/guides/code-review-integration-example.md`.

**Статус:** ✅ Готово к использованию в production.
