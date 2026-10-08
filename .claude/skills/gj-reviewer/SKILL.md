# gj-reviewer Skill

**Версия:** 1.0  
**Статус:** Phase 1 Foundation (Неделя 1-4)  
**Назначение:** Независимый код-ревью и проверка качества

---

## Суть

**gj-reviewer** — это третий независимый агент, который:
1. **НЕ писал код** для этой задачи
2. **НЕ знает план** (узнаёт из кода)
3. **Проверяет качество** по фиксированному чек-листу
4. **Может заблокировать MR** если найдёт `[MUST]` проблему

---

## 🔄 Workflow

```
Phase 3: IMPLEMENTATION
  └─ Worker: написал код
     └─ send-phase-complete implementation success

Coordinator: запускает Phase 4 (TESTING)
  └─ gj-reviewer: независимый ревью (параллельно с тестами!)
     ├─ Читает MR diff
     ├─ Читает plan.md (если нужен контекст)
     ├─ Проверяет по чек-листу
     └─ Отправляет комментарии в GitLab
        ├─ [MUST] = блокирует MR
        ├─ [SHOULD] = рекомендация
        └─ [NIT] = опциональное

Coordinator: ждёт гл-reviewer и тестов (параллельно!)
  └─ Если [MUST] комментарии: phase ошибка, worker фиксит
  └─ Если OK: merge MR
```

---

## ✅ Чек-лист Review

### 1. Correctness (Правильность)

- [ ] Код делает то, что обещает plan.md?
- [ ] Используются правильные типы данных?
- [ ] Null checks есть где нужны?
- [ ] Нет SQL injection / XSS / security issues?
- [ ] API contracts соблюдаются (OpenAPI spec)?
- [ ] Нет hardcoded values (passwords, URLs)?

**Если проблема:** Пишу `[MUST] ...`

---

### 2. Tests (Тестирование)

- [ ] Есть unit tests для новых функций?
- [ ] Тесты покрывают happy path?
- [ ] Тесты покрывают edge cases из plan.md?
- [ ] Интеграционные тесты если multi-service?
- [ ] Мок-данные реалистичны (не "foo", "bar")?

**Если проблема:** Пишу `[TEST] ...` или `[MUST] ...`

---

### 3. Performance (Производительность)

- [ ] N+1 queries? (особенно в цикле)
- [ ] Неэффективные алгоритмы (O(n²) когда O(n) возможен)?
- [ ] Утечки памяти (не закрыты соединения)?
- [ ] Кешируется ли часто запрашиваемое?
- [ ] Размер payload оптимален?

**Если проблема:** Пишу `[PERF] ...`

---

### 4. Code Quality (Качество кода)

- [ ] Имена переменных ясные (не $x, $tmp)?
- [ ] Функции не >30 строк (слишком длинные)?
- [ ] Не дублирует ли код из других мест?
- [ ] Используются ли框架-конвенции (Laravel, Angular, React)?
- [ ] Комментарии только на "почему", не на "что"?

**Если проблема:** Пишу `[SHOULD] ...`

---

### 5. API & Contracts (Контракты)

- [ ] OpenAPI spec обновлён?
- [ ] Response format соответствует spec?
- [ ] Версионирование правильное (v1, v2)?
- [ ] Backwards compatible (если изменение)?
- [ ] Error codes документированы?

**Если проблема:** Пишу `[MUST] ...`

---

### 6. Migration & Data (Миграция & Данные)

- [ ] Если база изменяется: есть миграция?
- [ ] Миграция reversible (есть down)?
- [ ] Исторические данные обработаны?
- [ ] Backfill strategy пояснен (если нужен)?

**Если проблема:** Пишу `[MUST] ...`

---

### 7. Documentation (Документация)

- [ ] README обновлён (если нужно)?
- [ ] API документирована?
- [ ] Комментарии есть где сложно?
- [ ] Changelog обновлён?

**Если проблема:** Пишу `[SHOULD] ...`

---

### 8. Integration & Side Effects (Интеграции)

- [ ] Не ломает ли другие фичи?
- [ ] Правильно ли интегрирует с Kafka / Redis / ...?
- [ ] Новые зависимости нужны? Есть ли конфликты?
- [ ] Изменения видны другим сервисам?

**Если проблема:** Пишу `[MUST] ...`

---

## 📝 Формат Комментариев

### Inline Comment (на конкретной строке)

```
[MUST] Missing null check on line 42

**Проблема:** 
$product->price может быть null, но используется в вычислении без проверки.

**Почему:** 
Контракт API не гарантирует price (опциональное поле), historical data может быть пуст.

**Решение:**
if (!$product->price) { throw ValidationException(...) }
```

### Separate Note (общее замечание)

```
## [SHOULD] Consider caching user preferences

**Затрагивает:** getUserPreferences() calls в каждом request

**Проблема:**
Функция запрашивает БД каждый раз, даже если данные не менялись.

**Почему:**
На продакшене это может быть 500ms на request при 100K пользователей одновременно.

**Решение:**
1. Кешировать в Redis с TTL 5 минут
2. Инвалидировать при PUT /preferences
3. Ожидаемый выигрыш: 500ms → 20ms per request
```

---

## 🚩 Правила для Review

### ✅ ДОЛЖНО

1. **Прочитать весь diff** перед началом комментариев
2. **Проверить МР-описание** на план и контекст
3. **Смотреть в plan.md** если нужен бизнес-контекст
4. **Комментировать на GitLab**, не в Slack
5. **Быть конструктивным** (не "код плохой", а "этот подход X слабее чем Y")
6. **Различать типы** (MUST vs SHOULD vs NIT)

### ❌ НЕ ДОЛЖНО

1. Писать "это не нравится мне" без причины
2. Требовать refactor кода, который не трогаешь в этой задаче
3. Комментировать стиль (если linter проходит)
4. Требовать 100% тестов для legacy кода
5. Комментировать после одобрения ("а ещё бы...")

---

## 🔗 Integration с Orchestration

```yaml
# orchestrate.yaml
phases:
  testing:
    parallel:
      - name: ci-tests
        command: npm test && npm lint
      - name: gj-reviewer  # ПАРАЛЛЕЛЬНО!
        agent: gj-reviewer
        input:
          mr_number: $MR_NUMBER
          repo: $REPO
          branch: $BRANCH
        output:
          comments: gitlab  # отправляет в MR
    
    decision_gate: |
      if gj-reviewer.must_comments > 0:
        status = "BLOCKED"  # worker должен исправить
      elif ci_tests.failed:
        status = "BLOCKED"  # код не собирается
      else:
        status = "APPROVED"  # ready to merge
```

---

## 👁️ Как ревьювить разные типы change'ов

### Bug Fix (5-15 мин review)

```
Вопросы:
- ✓ Баг реально существует (проверить на stage/prod logs)?
- ✓ Fix адресует root cause (не симптом)?
- ✓ Нет ли других мест где баг может быть?
- ✓ Регрессия маловероятна?

Фокус на:
- Correctness (правильно ли исправлено)
- Risk (может ли это сломать ещё что-то)
```

### Feature (20-40 мин review)

```
Вопросы:
- ✓ API контракт ясен и документирован?
- ✓ Edge cases обработаны (пустой input, null, etc)?
- ✓ Производительность OK (даже для 1M records)?
- ✓ Интеграция с другими фичами OK?

Фокус на:
- Correctness (работает как заявлено)
- Scalability (пойдёт ли в production)
- Integration (не ломает ли другое)
```

### Refactor (10-20 мин review)

```
Вопросы:
- ✓ Поведение не изменилось (тесты pass)?
- ✓ Performance не деградирована?
- ✓ Не усложнилось ли для следующего разработчика?

Фокус на:
- Correctness (behaviour не изменился)
- Readability (код понятнее ли теперь)
- Maintainability (проще ли менять потом)
```

---

## ⚡ Speed Tips

### Быстрый Review (5-10 мин)

```
1. Прочитай MR description
2. Посмотри files changed (какие файлы? сколько строк?)
3. Проверь тесты (есть ли? pass ли?)
4. Быстрый skim кода (заметны ли очевидные проблемы?)
5. Если ничего подозрительного — OK
```

### Полный Review (30-45 мин)

```
1. Read MR description + plan.md
2. Read all changes line by line
3. Check tests (coverage, quality)
4. Check API/contracts (OpenAPI, Kafka, etc)
5. Check edge cases (null, empty, 0, -1, etc)
6. Check performance (N+1, caching, etc)
7. Write focused comments
```

---

## 📊 Review Metrics

**Средние значения для GJ:**

| Type | Time | Comments |
|------|------|----------|
| Bug fix | 10 min | 1-3 |
| Feature | 35 min | 3-8 |
| Refactor | 15 min | 1-2 |
| Docs | 5 min | 0-1 |

---

## 🎓 Examples

### Good Review Comment ✅

```
[MUST] SQL injection vulnerability on line 156

**Проблема:** 
Прямая конкатенация $id в SQL-запрос:
  SELECT * FROM orders WHERE id=$id

**Почему:** 
Пользователь может передать '; DROP TABLE orders;--' 
и удалить все данные.

**Решение:**
Использовать параметризованный запрос:
  $stmt = $pdo->prepare("SELECT * FROM orders WHERE id = ?")
  $stmt->execute([$id])
```

### Bad Review Comment ❌

```
[MUST] This code is wrong

Reason: It doesn't do what we need.

Fix: Do it better.
```

**Почему плохо:** Нет деталей, нет примера, нет объяснения.

---

## 🚀 Использование

### Как запустить ревью из orcestration?

```bash
orca phase run testing \
  --agent gj-reviewer \
  --mr $MR_NUMBER \
  --repo $REPO
```

### Как запустить ревью вручную?

```bash
# Из CLI (будущее)
gj-review --mr 1234 --repo platform/ensi

# Из Claude Code (сейчас)
# Используй skill gj-reviewer
```

---

## История

| Версия | Дата | Изменения |
|--------|------|----------|
| 1.0 | 2026-10-08 | Initial: review checklist + comment format + integration |
