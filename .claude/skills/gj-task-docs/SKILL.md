---
name: SKILL
version: 1.0.0
layer: gj-task-docs
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---

# gj-task-docs Skill

**Версия:** 1.0  
**Статус:** Phase 1 Foundation (Неделя 1-4)  
**Назначение:** Обязательное документирование для каждой задачи

---

## Суть

Каждая задача должна иметь **три документа**, которые растут вместе с работой:

| Документ | Когда создать | Когда обновить | Что содержит |
|----------|---------------|----------------|-------------|
| **findings.md** | Phase 1 (UNDERSTANDING) | Phase 1-2 | Что нужно делать, где искать, что тебе нужно знать |
| **plan.md** | Phase 2 (PLANNING) | Phase 2-3 | Подход, файлы, edge cases, решение |
| **summary.md** | Phase 3-5 | Phase 5 (VERIFICATION) | Что было сделано, результат, learnings |

---

## 📋 findings.md (Phase 1)

**Сигнал:** Task created → Phase 1 starts → Create `.tasks/KEY/findings.md`

**Структура (Markdown):**

```markdown
# Understanding: OPSOMN002-XXX

**Created:** 2026-10-08  
**Task:** OPSOMN002-XXX  
**State:** In Progress (Phase 1)  

---

## 📌 Problem Statement

1-2 sentence: что нужно сделать

---

## 📚 Sources Found

- [ ] Jira: [OPSOMN002-XXX](link) — описание задачи
- [ ] Confluence: [Architecture](link) — контекст
- [ ] GitLab: [MR !123](link) — релевантный MR если есть
- [ ] Code: `platform/ensi/apps/XXX` — затронутые файлы
- [ ] Logs: search term на stage/preprod

---

## 🔍 Key Findings

### Затронутые Сервисы
- [ ] ENSI: catalog/pim
- [ ] OMS: Order
- [ ] Integration: checkout
- [ ] Site: basket

### Затронутые Файлы
```
platform/ensi/apps/catalog/pim/src/...
platform/integration/www/app/...
```

### Тип Изменения
- [ ] Bug fix
- [ ] Feature
- [ ] Refactor
- [ ] Config

### Ключевые Факты
- Fact 1: ...
- Fact 2: ...

---

## ⚠️ Known Edge Cases

- **Case 1:** When X, then Y might happen
  - Mitigation: ...
- **Case 2:** Historical data mismatch
  - Mitigation: ...

---

## ❓ Open Questions

- [ ] How does X interact with Y?
- [ ] Is Z still used?
- [ ] Where are tests?

---

## 🎯 Next Steps (Phase 2)

- [ ] Detailed plan
- [ ] File list
- [ ] Test strategy
```

**Обязательно:**
- Ссылки на источники (не просто текст)
- Ответы на вопросы "ЧТО?" и "ГДЕ?"
- Open questions без ответов нормально (Phase 2 даст ответы)

---

## 📊 plan.md (Phase 2)

**Сигнал:** Phase 1 complete → Phase 2 starts → Create `.tasks/KEY/plan.md`

**Структура:**

```markdown
# Plan: OPSOMN002-XXX

**Created:** 2026-10-08  
**Phase:** 2 (PLANNING)  

---

## 🎯 Approach

**High-level strategy (2-3 sentences):**

We'll fix the X by adding Y in Z. Impact: A files, B services.

---

## 📝 Detailed Plan

### Step 1: Add validation in catalog/pim
- [ ] File: `src/Models/Product.php`
- [ ] Action: Add `validateAssortment()` method
- [ ] Tests: `tests/Unit/Models/ProductTest.php`

### Step 2: Update API response
- [ ] File: `openapi/catalog.yaml`
- [ ] Action: Add `assortment` field to schema
- [ ] Tests: Contract test in `tests/API/CatalogContractTest.php`

### Step 3: Sync to cache
- [ ] File: `platform/ensi/apps/catalog/catalog-cache/src/SyncService.php`
- [ ] Action: Map assortment to cache entry
- [ ] Tests: Integration test

### Step 4: Integration test
- [ ] E2E flow: PIM → API → Cache → BFF
- [ ] Stubs: Mock OMS if needed

---

## ⚠️ Edge Cases & Mitigations

| Case | Mitigation | Risk |
|------|-----------|------|
| Historical data without assortment | Backfill on first sync | Low |
| Cache already populated | Add migration step | Medium |
| API versioning mismatch | V2 only for new field | Low |

---

## 📊 Estimated Impact

- **Files changed:** 5-7
- **Services affected:** 2-3 (ENSI, Cache, possibly BFF)
- **Test files:** 3-4
- **Data migration needed:** Yes (backfill historical)

---

## ✅ Success Criteria

- [ ] Validation works for all assortment types
- [ ] API returns field for 100% of products
- [ ] Cache reflects changes within 5 seconds
- [ ] E2E test passes on stage
- [ ] No regression in other fields

---

## 🚀 Phase 3 Entry Point

Start with: `src/Models/Product.php` → add method → tests pass locally
```

**Обязательно:**
- Конкретные файлы и строки (не общие)
- Edge cases с вероятностью риска
- Success criteria (как узнать, что готово)

---

## ✅ summary.md (Phase 5)

**Сигнал:** Phase 4 complete → Phase 5 (VERIFICATION) → Update `.tasks/KEY/summary.md`

**Структура:**

```markdown
# Summary: OPSOMN002-XXX

**Completed:** 2026-10-10  
**Total Time:** 8 hours  
**Status:** ✅ DONE  

---

## 🎯 What Was Done

We added assortment field to product catalog by:
1. Added validation in PIM
2. Updated OpenAPI spec (3 services sync)
3. Backfilled historical data (1.2M products)
4. Verified on stage (all tests pass)

---

## 📊 Results

### Code Changes
- [ ] Files: 7 changed
- [ ] Tests: 4 new + 2 updated
- [ ] Commits: 6 (atomic)
- [ ] MR: !1234 merged

### Performance Impact
- PIM: +0.5ms per product (validation overhead)
- Cache sync: +1.2s per product (backfill only)
- API response: +0.3% size (assortment field)
- **Conclusion:** Negligible impact

### Data Quality
- [ ] Backfill: 1,234,567 products processed
- [ ] Validation errors: 23 (legacy data, manually fixed)
- [ ] Cache coverage: 100%

---

## 📚 Learnings

### What Went Well
- Clear API contract made implementation straightforward
- Tests caught edge case with null assortment early
- Stage deployment smooth (no rollback needed)

### What Could Be Better
- Missing historical context in PIM schema (took 2h to research)
- Cache backfill was slower than expected (consider async in future)

### Recommendations for Similar Tasks
- Start with schema documentation (not code)
- Run load test on backfill (learned the hard way)
- Plan 30% buffer for unknown unknowns

---

## 🔗 References

- MR: !1234
- OPSOMN002-XXX: [link]
- Data validation report: `.tasks/OPSOMN002-XXX/data-validation-report.md`
- Performance metrics: `.tasks/OPSOMN002-XXX/perf-metrics.txt`

---

## 📈 Metrics

| Metric | Value |
|--------|-------|
| Total time | 8 hours |
| Code review time | 1.5 hours |
| Stage testing | 1 hour |
| Phase 3.5 (data-driven) | 1 hour |
| Bug fixes after review | 0.5 hours |
```

**Обязательно:**
- Конкретные результаты (не общие)
- Learnings для будущих задач
- Metrics для отслеживания trends

---

## 🔌 Integration

### Как это работает

1. **Worker создаёт task:**
   ```
   orca task create --key OPSOMN002-XXX --title "Fix assortment"
   ```

2. **Coordinator запускает Phase 1:**
   - Агент получает prompt
   - Обязательно: `export TASK_KEY=OPSOMN002-XXX`
   - Должен создать `.tasks/OPSOMN002-XXX/findings.md`

3. **На выходе Phase 1:**
   - `send-phase-complete understanding success`
   - findings.md должен существовать
   - Coordinator проверяет: `test -f .tasks/$TASK_KEY/findings.md`

4. **На выходе Phase 2:**
   - `send-phase-complete planning success`
   - plan.md должен существовать

5. **На выходе Phase 5:**
   - summary.md обновлён
   - Ссылка на MR
   - Metrics записаны

---

## ✅ Validation

Coordinator проверяет перед `send-phase-complete`:

```bash
# Phase 1 validation
test -f .tasks/$TASK_KEY/findings.md || die "findings.md not found"
grep -q "## Sources Found" .tasks/$TASK_KEY/findings.md || die "Missing Sources"
grep -q "## Key Findings" .tasks/$TASK_KEY/findings.md || die "Missing Findings"

# Phase 2 validation
test -f .tasks/$TASK_KEY/plan.md || die "plan.md not found"
grep -q "## Approach" .tasks/$TASK_KEY/plan.md || die "Missing Approach"
grep -q "## Success Criteria" .tasks/$TASK_KEY/plan.md || die "Missing Success Criteria"

# Phase 5 validation
grep -q "Status: ✅ DONE" .tasks/$TASK_KEY/summary.md || die "Task not complete"
grep -q "MR:" .tasks/$TASK_KEY/summary.md || die "Missing MR link"
```

---

## 🎓 Examples

### Good findings.md ✅
- Все вопросы "что", "где", "почему" имеют ответы
- Ссылки на источники (не пусто)
- Open questions явно обозначены
- Готово за 45 мин (не 2+ часа)

### Bad findings.md ❌
- Только "Нужно добавить поле X" (слишком мало деталей)
- "Смотри код" без ссылок
- Уходит в философию без фактов
- Заняло 3+ часа (слишком долго)

---

## 📋 Чек-лист для Agent'а

Перед `send-phase-complete`:

- [ ] Файл существует и не пуст
- [ ] Markdown валидный
- [ ] Все обязательные секции есть
- [ ] Нет плейсхолдеров типа "TODO" или "XXX"
- [ ] Ссылки работают (проверил вручную)
- [ ] Язык: русский (если интегрирован в GJ workspace)

---

## 🚀 Использование в Orchestration

```yaml
# orchestrate.yaml
phases:
  understanding:
    skills:
      - gj-task-docs  # обязательно документировать
    output:
      files:
        - .tasks/$TASK_KEY/findings.md
    validation:
      - must_exist: .tasks/$TASK_KEY/findings.md

  planning:
    skills:
      - gj-task-docs  # обновить findings, создать plan
    output:
      files:
        - .tasks/$TASK_KEY/plan.md
    validation:
      - must_exist: .tasks/$TASK_KEY/plan.md

  verification:
    skills:
      - gj-task-docs  # создать summary
    output:
      files:
        - .tasks/$TASK_KEY/summary.md
```

---

## История

| Версия | Дата | Изменения |
|--------|------|----------|
| 1.0 | 2026-10-08 | Initial: findings, plan, summary templates + validation |
