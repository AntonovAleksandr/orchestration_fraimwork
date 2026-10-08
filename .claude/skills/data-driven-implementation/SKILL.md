# Data-Driven Implementation

**Когда использовать:** ВСЕГДА после написания кода, который работает с данными.

**Что это:** Обязательная фаза перед "implementation complete". Проверяет что код работает на реальных данных, не только на unit test мocks.

---

## Обязательный Workflow

### Шаг 1: Определить Datasource

```bash
# Какие данные моего код трогает?
# Примеры:
# - "читаю заказы из OMS"
# - "пишу события в Kafka"
# - "обновляю остатки PIM"

DATA_SOURCE="________"  # e.g., "orders from OMS stage"
```

### Шаг 2: Получить Real Sample

```bash
# НЕ unit test fixtures, а реальные данные со стенда!

# Для ENSI (PostgreSQL):
psql -h stage-db -U readonly \
  -c "SELECT * FROM orders WHERE id IN (...) LIMIT 100" > sample.json

# Для OMS (тоже PostgreSQL):
psql -h oms-stage-db \
  -c "SELECT * FROM orders ORDER BY id DESC LIMIT 100" > sample.json

# Для Kafka (если applicable):
kafka-console-consumer --bootstrap-servers stage-kafka \
  --topic orders --from-beginning --max-messages 100 > sample.json
```

**Обязательно:**
- [ ] Реальные данные (не fixtures)
- [ ] Представительная выборка (10-100 records)
- [ ] Сохранить в `.tasks/KEY/sample-data.json`

### Шаг 3: Запустить Код На Sample

```bash
# Используй REАЛЬНЫЕ данные, не мокированные!

# Плохо:
<?php
$orders = new MockOrderRepository();  // ← TEST MODE
foreach ($orders->find() as $order) {
  process($order);
}

# Хорошо:
<?php
$sample = json_decode(file_get_contents('.tasks/KEY/sample-data.json'), true);
foreach ($sample as $order) {
  process($order);  // ← REAL DATA
}
```

### Шаг 4: Проверить Результат

```
Test on 100 real records:

✓ Result is NOT empty?
✓ Result is NOT all nulls?
✓ Result matches expected type (array, object, string)?
✓ Edge cases work (0 results, 1 result, 1000 results)?

If ANY check fails:
  → Debug on real data
  → Fix code
  → Re-test
  → Document in task findings
```

### Шаг 5: Сравнить Spec vs Reality

```yaml
# Что говорит OpenAPI spec?
Spec says:
  - Field "status" type: string
  - Field "amount" required: true
  - Field "items" type: array

# Что показывают реальные данные?
Reality shows (from sample):
  - "status": string ✓
  - "amount": null в 7% случаев ✗
  - "items": [] в 3% случаев ✗

# Вывод: Spec неполная!
Divergence found:
  - amount can be NULL despite "required: true"
  - items can be empty array
  
Fix: Update code to handle these cases
```

### Шаг 6: Трассировать E2E (если applicable)

```
Если код касается многих сервисов:

Example: site → integration → OMS

Test transaction:
  1. User creates order in site
  2. Integration receives webhook
  3. OMS creates order record
  4. Status syncs back to site

Verify:
  [ ] Order ID same in all 3 systems?
  [ ] Status transitions correct?
  [ ] Data not lost between services?
  [ ] Timestamps make sense?
```

### Шаг 7: Документировать Findings

```markdown
# Data-Driven Validation Report

## Test Setup
- Tested on: 100 real orders from stage-db
- Date: 2026-10-08
- Query: SELECT * FROM orders WHERE created_at > '2026-10-01'

## Results
- Sample size: 100 records
- Processing time: 245ms
- Errors: 0
- Empty results: 0
- Format issues: 0

## Spec Compliance
- Spec says "amount required": ✓ (matches)
- Spec says "items is array": ✓ (matches)
- Edge case "empty items": ✓ handled (added null-check)

## E2E Trace
- Order: OMS-12345
- Flow: site → integration → oms
- Status: ✓ synced correctly
- Data: ✓ complete

## Conclusion
Code is READY FOR PRODUCTION. No issues found on real data.
```

---

## Когда Можно Пропустить?

```
Пропустить data-driven, только если:
- [ ] Pure refactoring (no logic change)
- [ ] UI-only changes (no data change)
- [ ] Adding comments or documentation
- [ ] Renaming variables (no behavior change)

ВСЕ ОСТАЛЬНОЕ = обязательна data-driven фаза!
```

---

## Примеры

### ✅ Good: Data-Driven

```
Phase: implementation
- Wrote certificate import code
- Unit tests: 10/10 pass

Phase: data-driven (THIS IS NEW)
- Tested on 100 real certificates from stage
- Result: 93 imported OK, 7 with empty items
- Issue found: code doesn't handle <item/> tags
- Fixed: added null-check + logging
- Re-tested: 100/100 OK
- Ready to merge ✓
```

**Outcome:** Agent finds issue BEFORE merge. Human doesn't see it later.

### ❌ Bad: Code-Only

```
Phase: implementation
- Wrote certificate import code
- Unit tests: 10/10 pass
- Ready to merge ✓

[Merge, deploy to stage]

Human finds: 7/100 certificates failed in production
Rework: 2+ hours
```

**Outcome:** Wasted time, delayed release.

---

## Integration

This skill is **MANDATORY** in phase: `implementation` → before marking `phase_complete`.

Coordinator will check:
```
send-phase-complete() {
  if has_data_validation_report {
    // Ready to merge
  } else {
    // BLOCKED: data-driven validation required
  }
}
```
