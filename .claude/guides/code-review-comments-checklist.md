# Code Review Comments Checklist

Интеграция обязательного формата из `.claude/rules/code-review-comments-format.md` в процесс code-review.

**Используют:** `ensi-gitlab-mr-review`, `site-gitlab-mr-review`, `integration-gitlab-mr-review`, `mobile-gitlab-mr-review`, `oms-gitlab-mr-review`, `gloriaots-stack-anatomy`, все агенты с code review.

---

## ✅ Перед отправкой КАЖДОГО комментария

### Шаг 1: Определить тип (обязательно)

```
Что я нашел?
├─ Нарушение AC / контракта / архитектуры? → [MUST]
├─ Уязвимость (SQL injection, XSS, auth bypass)? → [SECURITY] (это всегда [MUST])
├─ Проблема производительности (N+1, O(N²))? → [PERF]
├─ Отсутствуют или неправильные тесты? → [TEST]
├─ Рекомендация (оптимизация, паттерн)? → [SHOULD]
└─ Опциональное улучшение (имя, стиль)? → [NIT]
```

### Шаг 2: Проверить структуру

**Для inline-комментариев (на конкретной строке):**

- ✅ `[ТИП] Заголовок, 1 строка`
- ✅ `**Проблема:** что неправильно на этой строке`
- ✅ `**Почему:** объяснение / ссылка на контракт / стандарт`
- ✅ `**Решение:** конкретный код или действие`

**Для separate-note (общее замечание):**

- ✅ `## [ТИП] Заголовок`
- ✅ `**Затрагивает:** файлы / функции`
- ✅ `**Проблема:**` (пункты)
- ✅ `**Почему:**` (ссылка на источник)
- ✅ `**Решение:**` (нумерованные действия)

### Шаг 3: Валидировать

```bash
# Автоматическая проверка перед отправкой
./.claude/scripts/review_validate.sh comment.md

# Или в strict режиме (отклонит предупреждения)
./.claude/scripts/review_validate.sh comment.md strict
```

### Шаг 4: Проверить запреты

❌ **НИКОГДА не писать:**
- Процесс / историю ("на ревью заметили", "позже сделайте")
- "TODO", "FIXME", "потом", "позже"
- Закомментированный код
- Благодарности / эмодзи (за исключением контекста проблемы)
- "Очевидно", "любой знает", "ясно же"
- Ссылки без контекста

---

## Примеры по типам

### ✅ [MUST] — Блокирует merge

```
[MUST] SQL injection на стр. 42

**Проблема:** 
SELECT * FROM orders WHERE id=$id — прямая конкатенация

**Почему:** 
Пользователь может передать'; DROP TABLE--' и удалить данные (OWASP Top 10)

**Решение:**
→ $stmt = $pdo->prepare("SELECT * FROM orders WHERE id=?");
→ $stmt->execute([$id]);
```

### ✅ [SHOULD] — Рекомендация

```
[SHOULD] Оптимизировать N+1 запрос

**Проблема:**
Цикл запрашивает цену каждого товара отдельно (стр. 15-18)

**Почему:**
200 товаров = 200 запросов = 10 секунд; batch-запрос = 200ms

**Решение:**
Использовать getPrices(ids) вместо getPrice(id) в цикле
```

### ✅ [NIT] — Опционально

```
[NIT] Переименовать переменную

**Проблема:**
x, y, z не ясны — какие это переменные?

**Почему:**
Следующий читатель потратит время на разбор

**Решение:**
order_count, user_id, is_active вместо x, y, z
```

### ✅ [SECURITY] — Уязвимость (всегда [MUST])

```
[SECURITY] Прямой доступ к чужим заказам

**Проблема:**
GET /api/orders/{orderId} не проверяет права пользователя — может получить заказ любого

**Почему:**
Нарушение авторизации (OWASP Top 10); пользователь видит чужие адреса, платежи

**Решение:**
1. Добавить проверку: if (order.userId !== currentUser.id) return 403
2. Добавить e2e тест: user A пытается получить заказ user B → 403
```

### ✅ [PERF] — Производительность

```
[PERF] Регулярное пересчитывание вместо кеша

**Проблема:**
Функция catalogue.searchByFacets() пересчитывает фасеты каждый запрос (стр. 30-50)

**Почему:**
Это IO-heavy операция (Elasticsearch); пользователи видят задержку 500ms+; кеш Redis обойдётся в 50ms

**Решение:**
1. Кешировать результат в Redis на 5 минут
2. Инвалидировать кеш при изменении товара (Kafka event)
3. Сравнить результаты: 500ms → 50ms
```

### ✅ [TEST] — Тесты

```
[TEST] Отсутствует e2e для новой API

**Затрагивает:** platform/site/apps/site-*-e2e, platform/integration/

**Проблема:**
Добавлены 3 новых endpoint для экспресс-доставки, но нет cypress тестов, проверяющих полный flow

**Почему:**
AC (OPSOMN002-250) требует "проверить интеграцию"; ручные тесты не масштабируются и не ловят регрессию

**Решение:**
1. Создать cypress spec: `apps/site-ru-e2e/src/express-delivery.cy.ts`
2. Сценарий: cart → select express → checkout → success
3. Мокировать Integration responses (или использовать стенд)
4. Ожидаемое покрытие: >80% новых строк
```

---

## Чек для каждого скилла code-review

Если вы пишете / обновляете skill для code-review (ensi-gitlab-mr-review, site-gitlab-mr-review и т.д.), добавьте этот чек:

### В начало skill-документа

```markdown
# [Platform]-GitLab MR Review

## Формат комментариев (обязательно!)

Каждый комментарий должен следовать `.claude/rules/code-review-comments-format.md`:

- **Типы:** [MUST] (блокирует), [SHOULD] (рекомендация), [NIT] (опция), [SECURITY], [PERF], [TEST]
- **Структура:** 
  - Inline: [ТИП] + Проблема + Почему + Решение
  - Separate: ## [ТИП] + Затрагивает + Проблема + Почему + Решение

Перед отправкой валидировать:
```bash
./.claude/scripts/review_validate.sh comment.md
```

Запрещено: TODO/FIXME, благодарности, процесс, очевидность, ссылки без контекста.
```

### В конец skill-документа (как part of exit checklist)

```markdown
## Exit Checklist

- [ ] Каждый комментарий следует формату `.claude/rules/code-review-comments-format.md`
- [ ] Запущена валидация: `review_validate.sh` для всех замечаний
- [ ] Все [MUST] комментарии блокируют merge
- [ ] Все [SHOULD]/[NIT] опциональны
- [ ] Нет TODO/FIXME/потом в комментариях
- [ ] Каждый комментарий привязан к контракту или задаче (AC, OPSOMN002-123, etc.)
```

---

## Примеры плохих комментариев → хорошие

### ❌ → ✅ Пример 1: Слишком общий

**Плохо:**
```
[MUST] Плохой код

Здесь опасно. Нужно проверить.
```

**Хорошо:**
```
[MUST] SQL injection на стр. 42

**Проблема:** 
Прямая конкатенация $id в SQL: SELECT * FROM orders WHERE id=$id

**Почему:** 
SQL injection (OWASP); пользователь может удалить таблицу или украсть данные

**Решение:**
→ $stmt = $pdo->prepare("SELECT * FROM orders WHERE id=?");
→ $stmt->execute([$id]);
```

### ❌ → ✅ Пример 2: История вместо проблемы

**Плохо:**
```
[SHOULD] На ревью заметили

Может быть, давайте оптимизируем позже.
```

**Хорошо:**
```
[SHOULD] Оптимизировать N+1 запрос в listProducts

**Проблема:**
Цикл запрашивает цену каждого товара отдельно (стр. 15-18); 100 товаров = 100 запросов

**Почему:**
100 запросов × 50ms = 5s задержка; batch-запрос = 50ms (в 100 раз быстрее)

**Решение:**
Использовать catalog.getPrices([ids]) вместо catalog.getPrice(id) в цикле
```

### ❌ → ✅ Пример 3: Отсутствует раздел "Почему"

**Плохо:**
```
[MUST] Добавить проверку прав

**Проблема:** Не проверяется что пользователь владеет заказом

**Решение:** Добавить if check
```

**Хорошо:**
```
[MUST] Отсутствует проверка прав на заказ

**Проблема:** GET /api/orders/{id} не проверяет userId; может получить чужой заказ

**Почему:** 
AC (OPSOMN002-X) требует "пользователь видит только свои заказы"; 
нарушение приводит к утечке адресов, платежей, личных данных

**Решение:**
→ if (order.userId !== currentUser.id) return 403 Forbidden;
→ Добавить тест: user A пытается получить order user B → 403
```

---

## Автоматизация в review_post.py (если создавать скрипт)

```python
# Pseudocode интеграции в review_post.py

class ReviewCommentValidator:
    REQUIRED_SECTIONS = {
        'inline': ['**Проблема:**', '**Почему:**', '**Решение:**'],
        'separate': ['**Затрагивает:**', '**Проблема:**', '**Почему:**', '**Решение:**']
    }
    
    ALLOWED_TYPES = ['MUST', 'SHOULD', 'NIT', 'SECURITY', 'PERF', 'TEST']
    FORBIDDEN_KEYWORDS = ['TODO', 'FIXME', 'потом', 'позже', 'очевидно']
    
    def validate(self, comment_text: str) -> tuple[bool, list[str]]:
        errors = []
        
        # 1. Есть ли [ТИП]?
        if not re.search(r'\[(MUST|SHOULD|NIT|SECURITY|PERF|TEST)\]', comment_text):
            errors.append("Отсутствует тип: [MUST], [SHOULD], [NIT], [SECURITY], [PERF], [TEST]")
        
        # 2. Определить тип комментария (inline vs separate)
        is_separate = comment_text.startswith('##')
        comment_type = 'separate' if is_separate else 'inline'
        
        # 3. Проверить обязательные разделы
        for section in self.REQUIRED_SECTIONS[comment_type]:
            if section not in comment_text:
                errors.append(f"Отсутствует раздел {section}")
        
        # 4. Проверить запреты
        for keyword in self.FORBIDDEN_KEYWORDS:
            if re.search(rf'\b{keyword}\b', comment_text, re.IGNORECASE):
                errors.append(f"Найдено запрещённое слово: '{keyword}'")
        
        return len(errors) == 0, errors

# При отправке
validator = ReviewCommentValidator()
is_valid, errors = validator.validate(comment)

if not is_valid:
    print("Комментарий отклонён:")
    for error in errors:
        print(f"  ❌ {error}")
    exit(1)

# Отправить в GitLab
mr.add_comment(comment)
```

---

## Логирование отправленных комментариев

Каждый отправленный комментарий должен быть залогирован:

```
[2026-10-08T14:30:15] GitLab MR !1234
├─ Type: [MUST]
├─ File: platform/integration/www/app/Http/Controllers/CheckoutController.php
├─ Line: 42
├─ Title: SQL injection on getUserOrders
└─ Status: SENT (request_changes=true)

[2026-10-08T14:30:20] GitLab MR !1234
├─ Type: [SHOULD]
├─ Location: Separate note
├─ Title: Optimize N+1 query in listProducts
└─ Status: SENT
```

---

## Версия

**Версия:** 1.0  
**Дата:** 2026-10-08  
**Используют:** Все code-review скиллы  
**Связано с:** `.claude/rules/code-review-comments-format.md`, `.claude/scripts/review_validate.sh`
