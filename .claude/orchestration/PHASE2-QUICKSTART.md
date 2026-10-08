# Phase 2 Quick Start (Weeks 5-8)

**Версия:** 1.0  
**Статус:** Ready to Launch  
**Цель:** 10/10 Hybrid System LIVE

---

## 🚀 Как Запустить Phase 2

### Шаг 1: Запустить Пилотную Задачу

```bash
# Создать новую задачу с Phase 2 включённым
orca task create \
  --key OPSOMN002-XXX \
  --title "Phase 2 Pilot: Test Hybrid System" \
  --phase2-enabled \
  --enable-parallel \
  --enable-data-driven

# Результат: задача создана, Phase 1 (UNDERSTANDING) запущена
```

### Шаг 2: Worker Выполняет Phase 1 (UNDERSTANDING)

**Agent:** любой (ensi-navigator, site-researcher, etc.)  
**Skill:** gj-task-docs  
**Output:** `.tasks/OPSOMN002-XXX/findings.md`

```bash
# Worker пишет findings.md:
# - Sources найдены
# - Key facts описаны
# - Open questions listed

# Когда готово:
send_phase_complete(
  task_key="OPSOMN002-XXX",
  phase=1,
  status="success",
  data={"findings_file": ".tasks/OPSOMN002-XXX/findings.md"}
)
```

### Шаг 3: Worker Выполняет Phase 2 (PLANNING)

**Agent:** architect (для сложных) или engineer  
**Skill:** gj-task-docs  
**Output:** `.tasks/OPSOMN002-XXX/plan.md`

```bash
# Worker пишет plan.md:
# - Approach описан
# - Files listed
# - Success criteria defined

send_phase_complete(
  task_key="OPSOMN002-XXX",
  phase=2,
  status="success",
  data={"plan_file": ".tasks/OPSOMN002-XXX/plan.md"}
)
```

### Шаг 4: Worker Выполняет Phase 3 (IMPLEMENTATION) ⚡ NEW

**Agent:** ensi-backend-engineer, site-engineer, etc.  
**Skills:** framework-specific + gj-task-docs  
**Output:** код + коммиты

```bash
# Worker пишет код, коммитит, открывает MR

# ВАЖНО: НЕ ЖДАТЬ REVIEW!
# Отправить сообщение асинхронно:

send_phase_complete(
  task_key="OPSOMN002-XXX",
  phase=3,
  status="success",
  data={
    "branch": "feat/assortment",
    "commit": "abc123def",
    "mr_number": 1234
  }
)
# ← Async! Coordinator будет слушать, но не блокируется
```

### Шаг 5: Coordinator Запускает Phase 3.5 + 4 ПАРАЛЛЕЛЬНО ⚡ NEW

**Trigger:** Phase 3 complete message received  
**Action:** Start both phases in parallel!

```
Phase 3: IMPLEMENTATION ✅ (worker завершил)
  ↓
Coordinator: слышит сообщение, запускает:
  ├─ Phase 3.5: DATA-DRIVEN-VALIDATION (data-driven-implementation skill)
  └─ Phase 4: TESTING (gj-reviewer + CI tests)
     └─ Обе идут ОДНОВРЕМЕННО!

Результат: экономия 1.5-2 часа per task! ⚡
```

### Шаг 6: Phase 3.5 (DATA-DRIVEN-VALIDATION)

**Agent:** data-driven-implementation  
**Duration:** 30-60 мин  
**Output:** `.tasks/OPSOMN002-XXX/data-validation-report.md`

```bash
# Agent получает:
# - Код с Phase 3
# - Доступ к stage database
# - Test fixtures

# Проверяет:
# 1. SELECT ... FROM real_table → результат не пуст
# 2. Количество полей matches spec
# 3. Types соответствуют
# 4. E2E flow работает

# Отправляет результат:
send_phase_complete(
  task_key="OPSOMN002-XXX",
  phase=3.5,
  status="success",  # или "partial" / "blocked"
  data={
    "report_file": ".tasks/OPSOMN002-XXX/data-validation-report.md",
    "records_tested": 150,
    "performance_ms": 245
  }
)
```

### Шаг 7: Phase 4 (TESTING) ⚡ PARALLEL

**Agent:** gj-reviewer (independent agent, doesn't write code)  
**Duration:** 1-2 часа  
**Output:** комментарии в MR

```bash
# gj-reviewer:
# 1. Читает MR diff
# 2. Проверяет 8-point checklist:
#    - Correctness
#    - Tests
#    - Performance
#    - Code Quality
#    - API Contracts
#    - Migration
#    - Documentation
#    - Integration

# Отправляет комментарии в MR:
# [MUST] = блокирует
# [SHOULD] = рекомендует
# [NIT] = опционально

# Отправляет результат:
send_phase_complete(
  task_key="OPSOMN002-XXX",
  phase=4,
  status="success",  # если нет [MUST] issues
  data={
    "must_comments": 0,
    "should_comments": 2,
    "nit_comments": 1,
    "ci_tests_pass": True
  }
)
```

### Шаг 8: Coordinator Ждёт Both Phase 3.5 AND 4

```
Phase 3.5: DATA-DRIVEN ━━━━━━━━━━━━┓
                                    ├─→ Both complete? YES
Phase 4: TESTING ━━━━━━━━━━━━━━━┛

→ Move to Phase 5 (VERIFICATION)
```

### Шаг 9: Worker Выполняет Phase 5 (VERIFICATION)

**Agent:** worker / CI  
**Duration:** 1 час  
**Output:** merged MR + deploy to stage

```bash
# Проверки:
# 1. Нет [MUST] issues в review ✓
# 2. CI tests pass ✓
# 3. MR merged ✓
# 4. Build successful ✓
# 5. Deploy to stage ✓
# 6. Smoke test pass ✓

send_phase_complete(
  task_key="OPSOMN002-XXX",
  phase=5,
  status="success",
  data={
    "mr_merged": True,
    "build_id": "build-12345",
    "stage_deployed": True,
    "smoke_test_pass": True
  }
)
```

### Шаг 10: Worker Завершает Phase 6 (DONE)

**Output:** `.tasks/OPSOMN002-XXX/summary.md` + cleanup

```bash
# Worker создаёт summary.md:
# - What was done
# - Results
# - Learnings
# - Metrics

# Cleanup:
# - Delete branch
# - Free worktree slot
# - Archive task

send_phase_complete(
  task_key="OPSOMN002-XXX",
  phase=6,
  status="success",
  data={
    "summary_file": ".tasks/OPSOMN002-XXX/summary.md",
    "total_time": "8 hours",
    "commits": 4,
    "files_changed": 7
  }
)

# Task complete! 🎉
```

---

## 📊 Expected Timings (Phase 2)

```
Phase 1: UNDERSTANDING           30-60 min
Phase 2: PLANNING                30-60 min
─────────────────────────────────────────
Phase 3: IMPLEMENTATION          2-4 hours
  └─ Triggers parallel:
    ├─ Phase 3.5: DATA-DRIVEN    30-60 min (PARALLEL!)
    └─ Phase 4: TESTING          1-2 hours (PARALLEL!)
                                 ─────────────
                                 max(1.5, 2) = 2 hours
─────────────────────────────────────────
Phase 5: VERIFICATION           1 hour
Phase 6: DONE                   15 min
─────────────────────────────────────────
TOTAL:                          8 hours ⚡

Vs Phase 1 (before):            20+ hours

SAVINGS:                        2.5x faster! 🚀
```

---

## 🎯 Week-by-Week Checklist

### Week 5: Integration
- [ ] Worker-messaging system tested locally
- [ ] Parallel phase execution tested
- [ ] gj-task-docs used in Phase 1
- [ ] First pilot task started
- [ ] Phase 3 → Phase 3.5 parallel working

### Week 6: Parallel System Live
- [ ] Phase 3.5 + 4 running in parallel
- [ ] Data-driven validation on real data
- [ ] Auto-cleanup branches working
- [ ] 2-3 tasks completed with Phase 2

### Week 7: Knowledge Base
- [ ] KB patterns captured
- [ ] Learnings extracted from tasks
- [ ] Similar tasks found + suggested
- [ ] 4-5 tasks completed

### Week 8: 10/10 System Ready
- [ ] 10/10 system LIVE ✅
- [ ] 5+ real tasks completed via Phase 2
- [ ] Metrics collected and analysed
- [ ] Feedback gathered
- [ ] Ready for Phase 3! 🚀

---

## 📈 Success Metrics (Week 8)

```
✅ System Performance:
   └─ Avg task time: 8 hours (was 20+ hours)

✅ Documentation:
   └─ 100% of tasks: findings.md ✓ plan.md ✓ summary.md ✓

✅ Review Quality:
   └─ Avg comments: 7.2 (within budget)
   └─ [MUST] blocks: 1.3 per review

✅ Data-Driven:
   └─ Bugs found: 15+ per week
   └─ False positives: <5%

✅ Parallel Execution:
   └─ Phase 3.5 + 4: always parallel
   └─ Time saved: 1.5-2 hours per task

✅ Live Tasks:
   └─ 5+ successfully completed

✅ System Score:
   └─ 10/10 ✅ (PERFECT!)
```

---

## 🚨 Troubleshooting

### Worker-Messaging Not Working

```bash
# Check if message file exists:
ls -la .tasks/OPSOMN002-XXX/phase-3.msg

# If not, worker didn't send:
# - Verify send_phase_complete() was called
# - Check for Python errors in logs
# - Manual send:
python3 .claude/orchestration/worker-messaging.py
```

### Phase 3.5 + 4 Not Parallel

```bash
# Check coordinator logs:
# - Should see: "Running Phase 3.5 and Phase 4 in parallel"
# - If sequential: check orchestration config

# Verify parallel setting:
grep "parallel_with" .claude/orchestration/phases-parallel.yaml
# Should output: parallel_with: "phase_4" (for 3.5) and vice versa
```

### Data-Driven Validation Failing

```bash
# Check data-validation-report.md:
cat .tasks/OPSOMN002-XXX/data-validation-report.md

# Common issues:
# 1. "Result is empty (0 records)"
#    → Table exists but query doesn't match real data
#    → Check WHERE clause / field names
#
# 2. "Type mismatch"
#    → Expected string, got integer
#    → Add CAST or update code
#
# 3. "Query timeout"
#    → Table too large or missing index
#    → Optimize query or add index to stage DB
```

### Worktree Slots Exhausted

```bash
# Check current usage:
git worktree list | wc -l

# If >25 (of 30):
# - Check if some branches are stuck
# - Manually cleanup:
git worktree remove worktrees/feature-branch
git branch -D feature-branch

# Or restart auto-cleanup:
python3 .claude/orchestration/auto-cleanup.py --force
```

---

## 🎁 What Happens in Phase 3 (After Week 8)

Once Phase 2 is live and working (week 8), Phase 3 will add:

```
PHASE 3 (Weeks 9-26): Architecture 12+/10

1. STATE STORE (PostgreSQL)
   └─ Task state persisted to DB (not files)

2. AUTONOMOUS WORKERS
   └─ Self-healing, auto-retry, no human needed

3. CLOUD BRANCHES
   └─ Unlimited worktree slots (no 30-slot limit)

4. RETRY & CIRCUIT BREAKER
   └─ Resilient to transient failures

5. LIVE DASHBOARD
   └─ Real-time task progress visualization

6. KNOWLEDGE GRAPH
   └─ Advanced cross-task learnings

→ Result: 12+/10 Enterprise system ✅
```

But that's Phase 3! For now: **let's get to 10/10 in week 8** 🚀

---

## 🏁 Ready to Start Phase 2?

```bash
# 1. Review this file
# 2. Check worker-messaging.py works
# 3. Pick first pilot task
# 4. Run: orca task create --phase2-enabled ...
# 5. Let's go! 🚀
```

**Target: Week 8 = 10/10 LIVE SYSTEM ✅**
