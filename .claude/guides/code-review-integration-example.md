# Code Review Format Integration Example

Пример того, как интегрировать обязательный формат `.claude/rules/code-review-comments-format.md` в существующий code-review skill.

---

## Шаблон для обновления skill

### Для ensi-gitlab-mr-review / site-gitlab-mr-review / и т.д.

**Добавить в начало skill-документа:**

```markdown
## Формат комментариев (ОБЯЗАТЕЛЬНО!)

Все комментарии code review **ДОЛЖНЫ** следовать `.claude/rules/code-review-comments-format.md`.

Это обеспечивает:
- Консистентность между ревьюерами
- Автоматизацию через `review_post.py`
- Понимание developer-ом что нужно исправить

### Структура комментария

Выбирите **один из двух форматов:**

#### 1. Inline (на конкретной строке)

```
[ТИП] Заголовок в одну строку

**Проблема:** что неправильно на этой строке
**Почему:** объяснение / ссылка на контракт / стандарт / задачу
**Решение:** конкретный код или действие
```

#### 2. Separate note (общее замечание)

```
## [ТИП] Заголовок

**Затрагивает:** файлы / функции

**Проблема:**
- пункт 1
- пункт 2

**Почему:**
- ссылка на контракт / AC / стандарт
- объяснение риска

**Решение:**
1. действие 1
2. действие 2
```

### Типы комментариев

| Тип | Блокирует | Когда использовать |
|-----|-----------|-------------------|
| `[MUST]` | ✅ Да | Нарушение AC, контракта, безопасности, архитектуры |
| `[SHOULD]` | ❌ Нет | Рекомендация (оптимизация, паттерн, улучшение) |
| `[NIT]` | ❌ Нет | Опциональное улучшение (имя переменной, стиль) |
| `[SECURITY]` | ✅ Да | Уязвимость (SQL injection, XSS, auth bypass) |
| `[PERF]` | ❌ Нет | Проблема производительности (N+1, O(N²)) |
| `[TEST]` | Зависит от AC | Отсутствие или неправильность тестов |

### Запрещено писать

❌ Процесс / историю ("на ревью заметили", "позже исправьте")  
❌ "TODO", "FIXME", "потом", "позже"  
❌ Закомментированный код  
❌ Благодарности / эмодзи (кроме контекста проблемы)  
❌ "Очевидно", "любой знает", "ясно же"  
❌ Ссылки без контекста (ссылка должна быть в разделе **Почему**)  

### Валидация

Перед отправкой комментария — запустить валидацию:

```bash
./.claude/scripts/review_validate.sh comment.md
```

Это проверит:
- ✅ Есть ли [ТИП]?
- ✅ Есть ли **Проблема:**?
- ✅ Есть ли **Почему:** или ссылка?
- ✅ Есть ли **Решение:**?
- ✅ Нет ли "TODO", "FIXME", "потом"?
- ✅ Нет ли благодарностей / эмодзи?

### Примеры

#### ✅ Хороший inline-comment

```
[MUST] SQL injection на стр. 42

**Проблема:** 
SELECT * FROM orders WHERE id=$id — прямая конкатенация

**Почему:** 
SQL injection (OWASP Top 10); пользователь может передать'); DROP TABLE--' и удалить данные

**Решение:**
→ $stmt = $pdo->prepare("SELECT * FROM orders WHERE id=?");
→ $stmt->execute([$id]);
```

#### ✅ Хороший separate-note

```
## [SHOULD] Оптимизировать N+1 запрос в listProducts

**Затрагивает:** platform/integration/www/app/Services/ProductService.php

**Проблема:**
- Функция листит товары в цикле
- Каждый раз запрашивает цену и скидку отдельно
- При 100 товарах = 200 запросов

**Почему:**
- 200 запросов × 50ms = 10s задержка
- Batch-запрос обойдётся в 50ms
- 10s → 50ms = в 200 раз быстрее

**Решение:**
1. Использовать batch-запрос: catalog.getPrices([id1, id2, ...])
2. Кешировать в Redis на 5 минут
3. Ожидаемый выигрыш: 200 запросов → 2 запроса
```

#### ❌ Плохой комментарий

```
[MUST] Плохо

Здесь опасно. Нужно проверить.
```

**Почему плохо:** Нет **Почему**, нет **Решения**, неясно ЧТО конкретно.
```

markdown

### Exit Checklist (для завершения ревью)

Перед тем как завершить ревью, проверить:

- [ ] Каждый комментарий имеет [ТИП]
- [ ] Каждый комментарий следует структуре (Проблема + Почему + Решение)
- [ ] Все [MUST] комментарии блокируют merge
- [ ] Валидация пройдена: `review_validate.sh`
- [ ] Нет TODO/FIXME/потом в комментариях
- [ ] Каждый комментарий привязан к контракту или задаче (AC, OPSOMN002-123, etc.)

```

---

## Где найти эти файлы

- **Формат:** `.claude/rules/code-review-comments-format.md` (обязательно читать)
- **Валидатор:** `.claude/scripts/review_validate.sh` (запускать перед отправкой)
- **Интеграция:** `.claude/guides/code-review-comments-checklist.md` (примеры интеграции в skills)

---

## Примеры для разных платформ

### ENSI code-review (PHP, Laravel, Swoole)

```markdown
## [MUST] OpenAPI спека не обновлена

**Затрагивает:** platform/ensi/apps/catalog/pim/openapi.yaml, platform/ensi/packages/pim-client-php

**Проблема:**
- Добавлено новое поле `assortment` в PIM API
- OpenAPI спека не обновлена
- Клиенты (admin-gui-backend, vitrine) используют старую спеку

**Почему:**
- Контракт между сервисами нарушен (openapi-first дизайн)
- Клиенты не видят нового поля, code generation ломается
- В CI регенерация клиентов откатит изменения

**Решение:**
1. Обновить `openapi.yaml`: добавить `assortment: string` в ProductResponse
2. Запустить оapi-codegen: `make regenerate-clients`
3. Проверить: пим-клиенты обновлены, новое поле есть
4. Комитить спеку и клиентов вместе
```

### Site code-review (Angular, Nx, NgRx)

```markdown
[MUST] Нарушение module boundaries

**Проблема:**
На стр. 25 libs/modules/basket/ импортирует из libs/modules/checkout/

**Почему:**
Nx ESLint правило: boundaries не должны быть циклическими; это блокирует рефакторинг и делает module-ы неподеляемыми

**Решение:**
1. Переместить shared логику в libs/shared/models/order.ts
2. Обновить импорт: basket → shared/models, checkout → shared/models
3. Запустить: `nx run-many --target=lint`
```

### Mobile code-review (React Native, TypeScript)

```markdown
[SECURITY] Прямое обращение к чужому заказу

**Проблема:**
На экране OrderDetails (стр. 42) используется orderId из navigation params без проверки прав

**Почему:**
Пользователь A может открыть заказ пользователя B, передав orderId в URL параметр

**Решение:**
1. На сервере: GET /orders/{id} должна возвращать 401 если не владелец
2. На клиенте: добавить проверку (опциональный слой, но не полагаться на неё)
3. Добавить e2e тест: detox попытка открыть чужой заказ → 401 error screen
```

### OMS code-review (Java, Spring Boot, Camunda)

```markdown
[MUST] BPMN process не обновлён при смене topic name

**Затрагивает:** platform/starfish24/awg/bpmn-process/order-fulfillment.bpmn20.xml, platform/starfish24/core/camunda-worker/

**Проблема:**
- В Java Worker переименовано поле: orderId → order_id
- В BPMN XML это свойство не обновлено
- External task worker читает из переменной ${orderId} которой больше нет

**Почему:**
- Контракт между BPMN и Worker нарушен (topic name = контракт)
- Running instances зависнут в процессе
- Новые заказы упадут с ошибкой
- OPSOMN002-X требует "обновить процесс при смене контракта"

**Решение:**
1. Обновить BPMN: заменить ${orderId} на ${order_id}
2. Обновить Worker: убедиться что читает order_id
3. Миграция running instances (Camunda API)
4. Тест: запустить процесс, проверить что переменная передаётся
```

### Integration code-review (PHP, Lumen)

```markdown
[MUST] Отсутствует обработка ошибки OMS API

**Затрагивает:** platform/integration/www/app/Http/Controllers/CheckoutController.php

**Проблема:**
- На стр. 67 вызов к OMS может вернуть 500
- Ошибка не обработана, пользователь видит 500 Internal Server Error
- Нет fallback логики

**Почему:**
- AC (BP-INT-30) требует "обработать ошибки OMS с graceful degradation"
- Чекаут падает при проблеме на стороне OMS
- Нет логирования, сложно отладить

**Решение:**
1. Обернуть в try-catch
2. Залогировать ошибку с trace_id
3. Вернуть пользователю: "Не удалось подтвердить заказ, попробуйте позже"
4. Добавить метрику: oms_checkout_error_count
5. Тест: мокировать OMS 500 → проверить что возвращается 503 Service Unavailable
```

### Gloria OTS code-review (.NET, C#, Hangfire)

```markdown
[PERF] Синхронный вызов к WMS блокирует UI

**Затрагивает:** platform/gloriaots/src/GloriaOTS.Web/ShipmentServices/WmsSyncService.cs

**Проблема:**
На стр. 30 вызов await wmsSyncClient.GetInventory() блокирует весь endpoint

**Почему:**
- GetInventory делает 3 nested запроса к WMS (каждый 200ms)
- Конечный response = 600ms + processing = 800ms
- Пользователь видит задержку 800ms на каждый refresh статуса

**Решение:**
1. Параллелизировать: Task.WhenAll([call1, call2, call3])
2. Добавить кеш на Redis (5 минут)
3. Инвалидировать при shipment status change
4. Benchmark: 800ms → 150ms (с кешем)
5. Тест: мерить timing, проверить что параллель работает
```

---

## Как запустить валидацию на CI

### GitLab CI пример

```yaml
code_review_format_check:
  stage: test
  script:
    # Собрать все review комментарии в файл (если используется review_post.py)
    - find . -name ".review_comments*.md" | head -10
    # Валидировать каждый
    - for file in $(find . -name ".review_comments*.md"); do
        ./.claude/scripts/review_validate.sh "$file" strict || exit 1;
      done
  allow_failure: false
  only:
    - merge_requests
```

### GitHub Actions пример

```yaml
name: Code Review Format Check

on: [pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Validate review comments format
        run: |
          for file in $(find . -name ".review_comments*.md"); do
            ./.claude/scripts/review_validate.sh "$file" strict || exit 1
          done
```

---

## Версия

**Версия:** 1.0  
**Дата:** 2026-10-08  
**Статус:** Production-ready  

**Связанные файлы:**
- `.claude/rules/code-review-comments-format.md` (обязательный формат)
- `.claude/scripts/review_validate.sh` (валидатор)
- `.claude/guides/code-review-comments-checklist.md` (checklist для ревьюеров)
