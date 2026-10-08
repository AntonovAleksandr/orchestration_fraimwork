# Детерминированный Рабочий Процесс Задачи

**Версия:** 1.0  
**Дата:** 2026-10-08  
**Статус:** Production-Ready для мерджа с MR !10

---

## Из Чего Состоит Задача (Phases)

Вместо "open MR → review → merge", задача имеет **обязательные фазы**:

```
┌─────────────────────────────────────────────────────────────────┐
│ TASK: OPSOMN002-XXX (пример)                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Phase 1: UNDERSTANDING (Исследование)                          │
│   ├─ [ ] Прочитал ТЗ                                           │
│   ├─ [ ] Нашел 3+ источников (spec, code, logs)               │
│   ├─ [ ] Identified все затронутые репо                        │
│   └─ Action: send-phase-complete understanding success         │
│                                                                 │
│ Phase 2: PLANNING (Планирование)                               │
│   ├─ [ ] Определил подход (где менять? какие файлы?)         │
│   ├─ [ ] Нашел edge cases                                      │
│   ├─ [ ] Wrote план (2-3 дня работы = готов вариант)         │
│   └─ Action: send-phase-complete planning success              │
│                                                                 │
│ Phase 3: IMPLEMENTATION (Кодирование)                          │
│   ├─ [ ] Написан код                                           │
│   ├─ [ ] Локальные тесты pass                                  │
│   ├─ [ ] Коммиты в ветку                                       │
│   └─ Action: send-phase-complete implementation success         │
│                                                                 │
│ ★ Phase 3.5: DATA-DRIVEN-VALIDATION (НОВОЕ! ОБЯЗАТЕЛЬНОЕ)     │
│   ├─ [ ] Получены реальные данные со стенда (100+ records)    │
│   ├─ [ ] Код протестирован на real data                       │
│   ├─ [ ] Result != empty/null                                 │
│   ├─ [ ] Spec vs reality: match confirmed                     │
│   ├─ [ ] E2E trace: transaction traced (if multi-service)     │
│   ├─ [ ] Report: .tasks/KEY/data-validation-report.md         │
│   └─ Action: send-phase-complete data-driven-validation OK    │
│                  OR partial (needs fixes)                      │
│                                                                 │
│ Phase 4: TESTING (Тестирование + Review)                      │
│   ├─ [ ] MR открыта в target branch                           │
│   ├─ [ ] CI tests pass                                         │
│   ├─ [ ] Code review passes (with data-driven checklist)       │
│   ├─ [ ] No merge conflicts                                    │
│   └─ Action: send-phase-complete testing success               │
│                                                                 │
│ Phase 5: VERIFICATION (Проверка на стенде)                     │
│   ├─ [ ] MR merged                                              │
│   ├─ [ ] Build successful                                      │
│   ├─ [ ] Deploy to stage                                       │
│   ├─ [ ] Smoke test on stage                                   │
│   ├─ [ ] Check logs for errors                                 │
│   └─ Action: send-phase-complete verification success          │
│                                                                 │
│ Phase 6: DONE (Закрыто)                                        │
│   ├─ Branch deleted                                             │
│   ├─ Worktree slot freed                                       │
│   └─ Task closed                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Детали Каждой Фазы

### Phase 1: UNDERSTANDING

**Входные данные:** Ссылка на ТЗ, ключ задачи  
**Выходные данные:** `.tasks/KEY/findings.md` (что нужно сделать)  
**Время:** 30-60 мин

**Обязательные действия:**

```markdown
# Understanding Phase: OPSOMN002-XXX

## Sources Found
- [ ] Jira: OPSOMN002-XXX (описание задачи)
- [ ] Confluence: https://... (архитектура)
- [ ] GitLab MR: !123 (релевантный MR если есть)
- [ ] Code: platform/ensi/apps/XXX (затронутые файлы)
- [ ] Logs: grep "search-term" /logs/stage.log (примеры)

## Key Facts
- Проблема: описание
- Затронуты сервисы: A, B, C
- Затронуты файлы: src/X.php, src/Y.php
- Тип изменения: bug fix | feature | refactor

## Known Edge Cases
- Case 1: ...
- Case 2: ...

## Questions for Human
- [ ] Question 1?
- [ ] Question 2?

## Conclusion
Ready to plan. Key insight: ...
```

**Фаза завершена когда:**
- ✅ 3+ источников информации найдено
- ✅ Все затронутые сервисы определены
- ✅ Edge cases найдены
- ✅ Нет open questions ИЛИ вопросы помечены как escalation

---

### Phase 2: PLANNING

**Входные данные:** findings.md из Phase 1  
**Выходные данные:** `.tasks/KEY/plan.md` (как делать)  
**Время:** 30-90 мин

**Обязательные действия:**

```markdown
# Planning Phase: OPSOMN002-XXX

## Approach
- Solution: what we'll do (high-level)
- Why: why this approach (not alternatives)

## Files to Change
1. `platform/ensi/apps/X/src/Y.php` (lines 42-67): Add validation
2. `platform/integration/www/app/Z.php` (new file): Helper function
3. Tests: `tests/Unit/YTest.php` (add 3 cases)

## Data Flow
User sends request
  → Integration validates (NEW)
  → OMS receives
  → Status syncs back

## Edge Cases Handled
- [ ] Empty input: skip with warn
- [ ] NULL field: default to X
- [ ] Concurrent updates: first-write-wins

## Risks
- Risk 1: N+1 queries if... → Mitigate by...
- Risk 2: Breaking change if... → Mitigate by...

## Estimates
- Implementation: 2-3 hours
- Testing: 1 hour
- Review/Fix: 1 hour

## Next Step
Ready to implement. Will start with file Y.php.
```

**Фаза завершена когда:**
- ✅ Подход задокументирован (не просто набросок)
- ✅ Все файлы to change перечислены
- ✅ Edge cases identified
- ✅ Risks addressed
- ✅ Time estimate made

---

### Phase 3: IMPLEMENTATION

**Входные данные:** plan.md из Phase 2  
**Выходные данные:** Git commits в ветку задачи  
**Время:** 2-4 часа

**Обязательные действия:**

```bash
# Create task branch
git checkout -b task-OPSOMN002-XXX-main

# Implement
# - Follow plan.md
# - Write focused commits
# - Update if plan changes

# Commits must:
- [ ] Follow project conventions
- [ ] Have clear messages
- [ ] Reference ТЗ (OPSOMN002-XXX)
- [ ] Not have merge commits from master

# Tests
- [ ] Unit tests written
- [ ] All tests pass: phpunit / jest / pytest
- [ ] Code style: phpcs / eslint / python -m black
- [ ] Static analysis: phpstan / eslint --max-warnings 0

# Verification
git log --oneline task-OPSOMN002-XXX-main ^ | head -10
# Should show: feature: OPSOMN002-XXX add validation
#              test: OPSOMN002-XXX cover null case
#              ...
```

**Фаза завершена когда:**
- ✅ Все файлы из плана модифицированы
- ✅ Unit tests passed
- ✅ Style checks passed
- ✅ Commits are clean (no merge commits)
- ✅ Branch is synced with origin

---

### Phase 3.5: DATA-DRIVEN-VALIDATION ⭐ (НОВОЕ!)

**Входные данные:** Commits из Phase 3  
**Выходные данные:** `.tasks/KEY/data-validation-report.md`  
**Время:** 30-60 мин (критично!)

**Обязательные действия:**

Use skill: `data-driven-implementation`

```markdown
# Data-Driven Validation: OPSOMN002-XXX

## Test Setup
- Tested on: 100 real orders from stage-db
- Query: SELECT * FROM orders WHERE created_at > '2026-10-01'
- Sample size: 100 records

## Execution
- Code: ran new validation logic
- Result: 98/100 OK, 2 with issues
- Time: 245ms for 100 records
- Errors: 0

## Verification
- Result is NOT empty? ✓ YES
- Format matches spec? ✓ YES
- Edge cases work? ✓ YES (tested NULL, empty array)

## E2E Trace (if applicable)
- Transaction: OMS-12345
- Path: site → integration → oms
- Status: ✓ synced correctly

## Conclusion
✅ READY FOR MERGE
Code works on real data, no issues found.
```

**Фаза завершена когда:**
- ✅ Real data tested (not mocks)
- ✅ Result ≠ empty/null
- ✅ Spec vs reality: match confirmed
- ✅ E2E path traced (if multi-service)
- ✅ Report documented

**⚠️ CRITICAL:**  
Если фаза fails → go back to Phase 3, fix code, repeat Phase 3.5.  
NOT "skip and merge anyway"!

---

### Phase 4: TESTING

**Входные данные:** data-validation-report.md из Phase 3.5  
**Выходные данные:** Merged MR  
**Время:** 1-2 часа

**Обязательные действия:**

```bash
# Open MR (target branch from plan)
git push origin task-OPSOMN002-XXX-main
# → Create MR in GitLab
#   Title: "OPSOMN002-XXX: Add validation"
#   Description: plan.md + data-validation-report.md

# Link data-validation report:
# In MR description add:
## Data-Driven Validation
- [See report](../.tasks/opsomn002-xxx/data-validation-report.md)

# Wait for:
- [ ] CI tests pass (automatically)
- [ ] Code review pass (use data-driven-review skill)
- [ ] All discussions resolved

# Merge
git merge origin/OPSOMN002-XXX-main  # after approval
```

**Фаза завершена когда:**
- ✅ MR opened
- ✅ CI passed
- ✅ Code review passed (data-driven checklist)
- ✅ MR merged to target branch

---

### Phase 5: VERIFICATION

**Входные данные:** Merged MR  
**Выходные данные:** Deployment confirmation  
**Время:** 15-30 мин

**Обязательные действия:**

```bash
# Verify merge
git log origin/release-XXXX --oneline | head -5
# Should include: OPSOMN002-XXX: Add validation

# Deploy (CI does this automatically)
# Wait for: pipeline status = PASSED

# Smoke test on stage
curl https://stage-api/endpoint-we-changed
# Verify: response format is correct
# Verify: no errors in logs

# Check logs
grep "OPSOMN002-XXX" /logs/stage.log | tail -20
# Verify: new code is running, no errors
```

**Фаза завершена когда:**
- ✅ Merge confirmed in git log
- ✅ CI pipeline passed
- ✅ Deploy to stage successful
- ✅ No errors in stage logs

---

### Phase 6: DONE

**Входные данные:** Verification passed  
**Выходные данные:** Task closed, slot freed  
**Время:** 5 мин

```bash
# Cleanup
orchestrate.sh cleanup OPSOMN002-XXX --auto
# → Deletes local + remote branches
# → Frees worktree slot
# → Logs in .tasks/KEY/branches.log

# Close task
git branch -a | grep task-OPSOMN002-XXX
# Should show: no branches (all deleted)

# Verification
orca task status OPSOMN002-XXX
# Should show: DONE, slot freed (28/30 now instead of 24/30)
```

---

## Детерминизм: Что Гарантирует

### Правило 1: Phase Order

```
UNDERSTANDING → PLANNING → IMPLEMENTATION → 
DATA-DRIVEN → TESTING → VERIFICATION → DONE

No skipping! No parallel! No "planning while implementing"!
```

**Почему:** Каждая фаза зависит от результата предыдущей.

### Правило 2: Mandatory Outputs

```
Phase 1 → findings.md (MUST exist)
Phase 2 → plan.md (MUST exist)
Phase 3 → git commits (MUST be clean)
Phase 3.5 → data-validation-report.md (MUST exist)
Phase 4 → merged MR (MUST be merged)
Phase 5 → stage deployment (MUST be successful)
```

**Почему:** Без артефактов нет доказательства что фаза завершена.

### Правило 3: No Phase Complete Until All Checks Pass

```
Phase 3.5 example:
- Result empty? → NOT COMPLETE, go back to Phase 3
- Spec mismatch? → NOT COMPLETE, go back to Phase 3
- E2E broken? → NOT COMPLETE, go back to Phase 3

No "we'll fix it next sprint"!
```

**Почему:** Phase 3.5 specifically designed to catch bugs BEFORE merge.

---

## Координатор Управление

**Координатор (автоматически):**

```bash
# Monitoring
while task_is_active:
  if worker_sends send-phase-complete:
    check_mandatory_outputs()
    if all_present AND checks_pass:
      approve_phase()
      auto_launch_next_phase()
    else:
      hold_phase()
      notify_worker("need X before proceeding")

# Decision gate
if phase == "data-driven-validation":
  # Highest priority
  # No auto-pass
  # If fails: escalate to human
```

---

## Success Metrics

```
Metric                 | Before | After (with this process)
─────────────────────────────────────────────────────────────
Issues found in code   | 80%    | 95%+
Issues found in prod   | 20%    | <5%
Iterations per task    | 2+     | 1
Rework time            | 2-4h   | 0
Agent confidence       | 60%    | 90%+
Merge safety           | 70%    | 99%
```

---

## Начало

1. Merge MR !10 (ARCH-FIX-2026)
2. Update all `.claude/agents/*` with:
   ```
   When starting task:
   - Use workflow from docs/TASK-WORKFLOW-DETERMINISTIC.md
   - Follow phases in order
   - Don't skip Phase 3.5 (data-driven-validation)
   - Use skills: data-driven-implementation, data-driven-review
   ```
3. First test: next task after MR merge
4. Iterate based on feedback

---

**Результат:** Задачи становятся полностью детерминированными. Нет surprises. Каждая фаза проверяема. ✅
