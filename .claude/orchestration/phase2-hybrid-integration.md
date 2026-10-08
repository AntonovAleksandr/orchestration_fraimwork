# Phase 2: Hybrid 10/10 Integration

**Версия:** 1.0  
**Статус:** In Progress (Week 5-8)  
**Цель:** Интегрировать Phase 1 skills в orchestration + запустить 10/10 систему

---

## 📋 Интеграция Skills

### Шаг 1: Регистрация Skills в Orchestration

```yaml
# .claude/orchestration/phase2-skills-registry.yaml

skills:
  documentation:
    - gj-task-docs:
        phases: [1, 2, 5]
        triggers:
          - phase_1_start: "create findings.md"
          - phase_2_start: "update plan.md"
          - phase_5_start: "create summary.md"
        validation:
          - must_exist: ".tasks/$TASK_KEY/findings.md"
          - must_exist: ".tasks/$TASK_KEY/plan.md"
          - must_exist: ".tasks/$TASK_KEY/summary.md"

  review:
    - gj-reviewer:
        phases: [4]
        parallel_with: [ci_tests]
        triggers:
          - phase_4_start: "send-review-comments-to-mr"
        validation:
          - mr_has_comments: true
          - no_must_comments_or_fixed: true

  protection:
    - guard_secrets:
        trigger: before_commit
        action: block_if_secrets_found
        
    - comment_budget:
        trigger: after_review_posted
        action: warn_if_exceeds_budget
```

---

## 🔄 Worker-Initiated Messaging (Phase 3.5)

### Реализация асинхронного взаимодействия

```
ТЕКУЩЕЕ (Synchronous):
Phase 3: IMPLEMENTATION (Worker пишет код)
  └─ send-phase-complete implementation success
     └─ Coordinator: ждёт ответа (BLOCKING!)

НОВОЕ (Asynchronous):
Phase 3: IMPLEMENTATION (Worker пишет код)
  └─ send-phase-complete implementation success
     └─ Coordinator: НЕ ждёт! Запускает Phase 3.5 + Phase 4
        └─ Phase 3.5 (DATA-DRIVEN): идёт ПАРАЛЛЕЛЬНО
        └─ Phase 4 (TESTING): идёт ПАРАЛЛЕЛЬНО
           └─ Оба завершаются → move to Phase 5
```

### Архитектура Messaging

```python
# .claude/orchestration/worker-messaging.py

class WorkerMessage:
    """Worker отправляет сообщение координатору"""
    
    def __init__(self, task_key, phase, status, data=None):
        self.task_key = task_key
        self.phase = phase
        self.status = status  # success, partial, blocked
        self.data = data or {}
        self.timestamp = datetime.now()
    
    def send(self):
        """Отправить сообщение асинхронно"""
        message_file = f".tasks/{self.task_key}/phase-{self.phase}.msg"
        with open(message_file, 'w') as f:
            json.dump({
                'phase': self.phase,
                'status': self.status,
                'data': self.data,
                'timestamp': self.timestamp.isoformat()
            }, f)
        
        # Optionally: push notification to coordinator
        # Coordinator не блокируется — он знает что check later


class Coordinator:
    """Координатор слушает сообщения (polling или event-driven)"""
    
    def poll_for_messages(self, task_key):
        """Проверить новые сообщения от workers"""
        messages = []
        for phase in range(1, 7):
            msg_file = f".tasks/{task_key}/phase-{phase}.msg"
            if os.path.exists(msg_file):
                with open(msg_file) as f:
                    messages.append(json.load(f))
        return messages
    
    def decide_next_phase(self, task_key, current_phase):
        """Асинхронно решить: что делать дальше"""
        msg = self.poll_for_messages(task_key)[-1]  # последнее сообщение
        
        if msg['status'] == 'success':
            # Запустить следующие фазы параллельно!
            if current_phase == 3:
                self.run_phase(task_key, 3.5)  # data-driven
                self.run_phase(task_key, 4)    # testing
                # Оба идут одновременно!
            else:
                self.run_phase(task_key, current_phase + 1)
        elif msg['status'] == 'partial':
            # Worker сказал "почти готово, но есть issues"
            self.escalate(task_key, msg['data'])
        else:
            # blocked
            self.block_task(task_key, msg['data'])
```

---

## ⚡ Параллельное Выполнение Фаз

### Phase 3.5 (DATA-DRIVEN-VALIDATION) + Phase 4 (TESTING)

```
Timeline (было):
Phase 3: IMPLEMENTATION (2-4 часа)
Phase 3.5: DATA-DRIVEN (30-60 мин) ← ждёт Phase 3
Phase 4: TESTING (1-2 часа)
─────────────────────────────────
Total: 3.5-6 часов

Timeline (новое - PARALLEL):
Phase 3: IMPLEMENTATION (2-4 часа)
Phase 3.5: DATA-DRIVEN ──────────┐ (идут одновременно!)
Phase 4: TESTING ────────────────┤ (max(3.5, 4) + overlap)
                                  │
                        Complete when both done ←
─────────────────────────────────
Total: 2-4 часа (экономия 1.5-2 часа!)
```

### Конфигурация параллелизма

```yaml
# .claude/orchestration/phases-parallel.yaml

phases:
  3_implementation:
    name: "IMPLEMENTATION"
    duration: "2-4 hours"
    agent: "ensi-backend-engineer | site-engineer | ..."
    output:
      - branch_with_code
      - local_tests_pass
    next_phase:
      - trigger: "phase_complete"
        action: "run_parallel [phase_3_5, phase_4]"
        # Не wait! Запустить обе асинхронно

  3_5_data_driven:
    name: "DATA-DRIVEN-VALIDATION"
    duration: "30-60 min"
    agent: "data-driven-implementation"
    parallel_with: "phase_4"  # ← KEY: параллельно с Phase 4
    dependencies: ["phase_3"]
    input:
      - code_from_phase_3
      - stage_database
    output:
      - data-validation-report.md
    success_criteria:
      - result != empty
      - real_data_matches_spec
    next_phase:
      - trigger: "both_phase_3_5_and_phase_4_complete"
        action: "run phase_5"

  4_testing:
    name: "TESTING"
    duration: "1-2 hours"
    agent: "gj-reviewer"
    parallel_with: "phase_3_5"  # ← KEY: параллельно с Phase 3.5
    dependencies: ["phase_3"]
    input:
      - mr_number
      - branch_name
    output:
      - review_comments
      - test_results
    success_criteria:
      - ci_tests_pass
      - no_must_comments
```

---

## 📊 Data-Driven Validation (Phase 3.5)

### Интеграция с существующими skills

```bash
# Phase 3.5 использует эти скилы:

1. data-driven-implementation
   ├─ Получает реальные данные со стенда
   ├─ Тестирует код на real data
   └─ Создаёт data-validation-report.md

2. data-driven-review (опционально)
   ├─ Проверяет валидность assumptions
   └─ Даёт feedback если spec != reality

3. Coordinator
   ├─ Если validation FAILS:
   │  └─ Escalate to worker (фикс требуется)
   └─ Если validation PASSES:
      └─ Move to Phase 5 (verification)
```

### Checklist для Phase 3.5

```markdown
# Phase 3.5: Data-Driven Validation

- [ ] Получены данные со стенда (stage database)
  └─ Минимум: 100+ записей, реальных (не мокированных)

- [ ] Код протестирован на real data
  └─ Запрос: SELECT ... FROM real_table
  └─ Result != empty (не 0, не NULL)

- [ ] Spec vs reality MATCH
  └─ Ожидаемое количество полей: N
  └─ Реальное: N (совпадает!)

- [ ] E2E trace (если multi-service)
  └─ Service A → Service B → Service C
  └─ Данные корректно передаются между ними

- [ ] Performance OK
  └─ Query time: <500ms (for 100 records)
  └─ No N+1 queries

- [ ] Report created
  └─ .tasks/$TASK_KEY/data-validation-report.md
```

---

## 🔄 Knowledge Base (Basic, Phase 2)

### File-Based KB для Phase 2

```
.tasks/SHARED/knowledge-base/
├── patterns/
│   ├── sql-injection-fixes.md
│   ├── n-plus-one-solutions.md
│   ├── null-check-patterns.md
│   └── api-versioning.md
├── learnings/
│   ├── task-289-findings.md (что научились на задаче 289)
│   ├── task-534-findings.md (что научились на задаче 534)
│   └── task-XXX-findings.md
└── registry.md (индекс всех learnings)
```

### Как использовать KB

```python
# Перед Phase 3 (IMPLEMENTATION):
# Координатор ищет похожие задачи

similar_tasks = search_kb(
    task_type="bug_fix",
    domain="catalog",
    keywords=["SKU", "validation"]
)
# Найдено: task-289 (похожая задача на SKU validation)

# Извлечь findings:
lessons = extract_lessons(similar_tasks)
# → "SKU validation: null checks important"
# → "Solution: added null-check in line 42"

# Передать worker'у:
worker_prompt = f"""
Similar tasks found:
- Task 289: {lessons}

Consider applying: {lessons['recommendations']}
"""
```

---

## 🎯 Auto-Cleanup Branches

### Автоматическая очистка worktree слотов

```bash
# После Phase 6 (DONE), удалить:
# 1. Feature branch
# 2. Worktree slot
# 3. Temporary files

# Скрипт для Coordinator:

after_phase_6():
    branch = task.branch_name  # e.g., "feat/assortment"
    
    # 1. Delete worktree
    subprocess.run([
        'git', 'worktree', 'remove',
        f'worktrees/{branch}'
    ])
    
    # 2. Delete branch locally
    subprocess.run(['git', 'branch', '-D', branch])
    
    # 3. Clean up task directory
    shutil.rmtree(f'.tasks/{task.key}')
    
    # 4. Log cleanup
    log(f"✅ Task {task.key}: cleaned up")
```

---

## 📈 Live Testing Setup

### Как запустить Phase 2 на реальных задачах

```bash
# Week 5: Запустить пилотные задачи

orca task create \
  --key OPSOMN002-XXX \
  --title "Test Phase 2 hybrid system" \
  --enable-data-driven \
  --enable-parallel-phases

# Мониторить процесс:
orca task status OPSOMN002-XXX --watch

# Собрать метрики:
orca metrics phase2 \
  --start-date 2026-10-15 \
  --end-date 2026-10-22 \
  --tasks 5  # первые 5 пилотных задач
```

### Ожидаемые результаты (неделя 8)

```
✅ Phase 2 Metrics:

Average task time:
  - Before (Phase 1): 20+ hours
  - After (Phase 2): 8 hours ⚡ (2.5x ускорение!)

Parallel execution:
  - Phase 3.5 + Phase 4: параллельно
  - Экономия: 1.5-2 часа на задачу

Data-driven catches:
  - Bugs found: 15+ per week
  - False positives: <5%

Documentation:
  - 100% of tasks have findings.md ✅
  - 100% of tasks have plan.md ✅
  - 100% of tasks have summary.md ✅

Review quality:
  - Avg comments: 7.2 (within budget)
  - [MUST] blocks: 1.3 per review (expected)
```

---

## 🚀 Phase 2 Checklist (Weeks 5-8)

### Week 5: Integration
- [ ] Worker-messaging system working
- [ ] Phase 3.5 integrated into orchestration
- [ ] Parallel phase execution tested locally
- [ ] gj-task-docs used in real task
- [ ] gj-reviewer active in Phase 4

### Week 6: Parallel Execution
- [ ] Phase 3.5 + Phase 4 run in parallel
- [ ] Data-driven validation on real data
- [ ] Auto-cleanup branches working
- [ ] No worktree slot exhaustion

### Week 7: Knowledge Base
- [ ] KB initialized with patterns
- [ ] Learnings extracted from tasks
- [ ] Similar tasks found successfully
- [ ] Worker gets KB suggestions

### Week 8: Live System
- [ ] 10/10 system LIVE ✅
- [ ] 5+ real tasks completed
- [ ] Metrics collected
- [ ] Ready for Phase 3 architecture

---

## 📊 Success Criteria for Phase 2

| Criteria | Target | Status |
|----------|--------|--------|
| **Task Time** | 8 hours | ⏳ Week 8 |
| **Parallel Phases** | 3.5 ∥ 4 | ⏳ Week 6 |
| **Data-Driven Coverage** | 100% tasks | ⏳ Week 6 |
| **Documentation** | 100% findings/plan/summary | ⏳ Week 5 |
| **Review Quality** | <10 comments avg | ⏳ Week 5 |
| **Live Tasks** | 5+ | ⏳ Week 8 |
| **System Score** | 10/10 | ⏳ Week 8 |

---

## История

| Версия | Дата | Изменения |
|--------|------|----------|
| 1.0 | 2026-10-08 | Initial: Phase 2 integration plan (worker-messaging, parallel, KB, cleanup) |
