# Phase 2: Risk Assessment & Mitigation

**Версия:** 1.0  
**Статус:** Critical (read before Week 5)  
**Назначение:** Предупредить проблемы и как их избежать

---

## 🚨 Критические Риски

### РИСК 1: Worker-Messaging Race Condition

**Проблема:**
```
Scenario: Phase 3 и Phase 3.5 пишут в один файл одновременно
├─ Worker: send_phase_complete(phase=3) → пишет в phase-3.msg
├─ Coordinator: читает из .tasks/OPSOMN002-XXX/phase-3.5.msg (ждёт)
└─ Worker (Phase 3.5): пишет в phase-3_5.msg одновременно
   └─ FILE CORRUPTION или PARTIAL WRITE! 🔥
```

**Вероятность:** 15% (если много concurrent tasks)  
**Severity:** HIGH (система может потерять данные)

**Как избежать:**
```python
# ✅ РЕШЕНИЕ 1: Atomic writes с temp файлом

def send_phase_complete(task_key, phase, status, data):
    # Сначала пишем в temp файл
    temp_file = f".tasks/{task_key}/phase-{phase}.msg.tmp"
    with open(temp_file, 'w') as f:
        json.dump({"phase": phase, "status": status, ...}, f)
    
    # ПОТОМ переименовываем (atomic на POSIX)
    os.rename(temp_file, f".tasks/{task_key}/phase-{phase}.msg")
    # На POSIX (Linux/Mac) os.rename() атомичен!
    # На Windows: используй os.replace() (Python 3.3+)

# ✅ РЕШЕНИЕ 2: File locking

import fcntl
def send_phase_complete(task_key, phase, status, data):
    lock_file = f".tasks/{task_key}/.lock"
    with open(lock_file, 'w') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)  # exclusive lock
        try:
            msg_file = f".tasks/{task_key}/phase-{phase}.msg"
            with open(msg_file, 'w') as f:
                json.dump(..., f)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)  # release

# ✅ РЕШЕНИЕ 3: Message queue (Redis/RabbitMQ)
# Для Phase 3+: если нужна production-ready система
# (за пределами scope Phase 2, но помнить!)
```

**Что делать если произойдёт:**
- [ ] Коммит atomic writes в worker-messaging.py
- [ ] Добавить file locking для safety
- [ ] Test concurrent writes перед Week 5

---

### РИСК 2: Phase 3.5 Зависает на Реальных Данных

**Проблема:**
```
Scenario: Data-driven validation запускается на огромной таблице
├─ SELECT * FROM products WHERE ... (stage DB)
├─ 10M rows, query не оптимизирован
├─ Phase 3.5 запускает SELECT на неиндексированном поле
└─ TIMEOUT! Query выполняется 30+ минут 🔥

Результат: Phase 3.5 ждёт 30 мин, Phase 4 в это время тоже ждёт
→ Общее время: вместо 2 часов → 2.5+ часов!
```

**Вероятность:** 25% (если много разных задач)  
**Severity:** MEDIUM (замедление, не потеря данных)

**Как избежать:**

```python
# ✅ РЕШЕНИЕ 1: Query timeout

def data_driven_validation(code, stage_db):
    # Установить query timeout на 5 минут
    stage_db.execute("SET SESSION query_timeout = 300000")  # 5 min
    
    try:
        # Выполнить query
        result = stage_db.execute(
            "SELECT * FROM products WHERE ...",
            timeout=300  # 5 min max
        )
        if len(result) == 0:
            return "FAIL: No data"
        return "SUCCESS"
    except TimeoutError:
        return "FAIL: Query timeout (table too large or unindexed)"
        # Agent вернёт message:
        # phase_blocked(
        #   task_key, 3.5,
        #   reason="Query timeout on stage DB - check indexes"
        # )

# ✅ РЕШЕНИЕ 2: Limit результатов

def data_driven_validation(code, stage_db):
    # Вместо SELECT * → SELECT * LIMIT 1000
    result = stage_db.execute(
        "SELECT * FROM products LIMIT 1000"
    )
    # Проверить на data, но не грузить всё

# ✅ РЕШЕНИЕ 3: Pre-check stage DB

def data_driven_validation(code, stage_db):
    # Перед запуском: check table size
    size = stage_db.execute(
        "SELECT COUNT(*) FROM products"
    )[0][0]
    
    if size > 100_000_000:  # 100M rows
        return "FAIL: Table too large, manual check needed"
    
    # Только тогда выполнить query
    return execute_validation(code, stage_db)
```

**Что делать если произойдёт:**
- [ ] Добавить query timeout в data-driven-implementation skill
- [ ] Документировать: "Phase 3.5 может занять до 5 мин"
- [ ] Добавить Pre-check для больших таблиц
- [ ] Мониторить time затраты per task

---

### РИСК 3: Phase 3.5 Находит Проблемы Поздно

**Проблема:**
```
Timeline (плохой случай):
Week 6, Day 3:
├─ Phase 3: завершена (2 часа работы)
├─ Phase 3.5 + 4: запущены параллельно
├─ Phase 3.5: FAIL — "Result is empty on stage DB"
│  └─ Причина: WHERE clause не соответствует real data structure
│  └─ Worker потратил 2 часа зря! 😞
├─ Worker: нужно фиксить Phase 3 (ещё 1-2 часа!)
└─ Задача затягивается вместо 8 часов → 12+ часов

Проблема: Phase 3.5 должна была быть на стадии Phase 2 (планирования)!
```

**Вероятность:** 20% (если планирование неполное)  
**Severity:** HIGH (потеря времени)

**Как избежать:**

```markdown
# ✅ РЕШЕНИЕ 1: Early Validation в Phase 2 (PLANNING)

## Phase 2 Output (plan.md)

Обязательный раздел:

### Data Validation Strategy
- [ ] Target table(s): products, catalog_cache, etc.
- [ ] Expected query:
      ```sql
      SELECT * FROM products WHERE ...
      ```
- [ ] Expected result size: 100-1000 records
- [ ] Dry-run на stage: (Agent проверяет ЧТО-ТО перед Phase 3!)
  - Запущен на stage DB: ✓
  - Result не пуст: ✓
  - Fields match code: ✓

# ✅ РЕШЕНИЕ 2: Agent автоматически проверяет перед Phase 3

# agent-prompt (Phase 3 IMPLEMENTATION)
"""
Before you start coding:

1. Check plan.md for "Data Validation Strategy"
2. Dry-run this query on stage DB NOW:
   - If FAIL → ask to clarify data structure
   - If SUCCESS → proceed with coding
3. Report: "Data structure validated ✓"

This prevents wasting 2 hours on Phase 3 only to fail in Phase 3.5!
"""

# ✅ РЕШЕНИЕ 3: Phase 3.5 стратегия (smart approach)

if data_driven_validation_fails():
    # Вместо просто "BLOCKED", дать советы
    suggestions = [
        "Check WHERE clause: 'status = active' (prod) vs 'true' (stage)?",
        "Field name mismatch: 'product_id' vs 'id'?",
        "Data not imported: table empty on stage DB?",
    ]
    phase_blocked(
        task_key,
        phase=3.5,
        reason="Query returned 0 rows",
        escalate_to="worker",
        suggestions=suggestions  # ← Дайте подсказки!
    )
```

**Что делать если произойдёт:**
- [ ] Обновить phase-2 prompt для architect/engineer: "Dry-run query на stage!"
- [ ] Добавить Phase 2 checklist: "Data validation strategy filled"
- [ ] Phase 3.5 возвращать suggestions (не просто "FAIL")
- [ ] Документировать: "Early validation saves 2-3 hours"

---

## ⚠️ Важные Риски

### РИСК 4: Parallel Phases Conflict на Branch

**Проблема:**
```
Scenario: Phase 4 (reviewer) и Phase 3.5 (data-driven) работают на одной branch
├─ Phase 4: читает MR diff
├─ Phase 3.5: может выполнять live query
└─ Potential: если бранч удалится во время Phase 3.5?

Нет большого конфликта, но может быть timing issue
```

**Вероятность:** 10% (низко)  
**Severity:** LOW

**Как избежать:**
```python
# Phase 3.5 должна проверить что branch всё ещё существует:
if not branch_exists(task.branch):
    return phase_blocked(
        task_key, 3.5,
        reason="Branch was deleted during validation"
    )
```

---

### РИСК 5: Auto-Cleanup Удаляет Нужную Ветку

**Проблема:**
```
Scenario: Phase 6 (DONE) auto-cleanup запускается
├─ Coordinator: "Все фазы завершены, cleanup!"
├─ Script: git worktree remove worktrees/feat-X
├─ Script: git branch -D feat-X
└─ Проблема: Worker забыл что-то, нужна ветка!
   └─ Branch удалена! 💥

Рискованно, но маловероятно.
```

**Вероятность:** 5% (низко, если work-flow правильный)  
**Severity:** HIGH (если произойдёт)

**Как избежать:**
```python
# ✅ РЕШЕНИЕ 1: Dry-run mode (первые 2 недели)

def auto_cleanup(task_key, dry_run=True):
    """
    Week 5-6: dry_run=True (только логировать, не удалять)
    Week 7+: dry_run=False (реально удалять)
    """
    branch = task.branch_name
    
    if dry_run:
        print(f"[DRY-RUN] Would delete: {branch}")
        print(f"[DRY-RUN] Would remove: worktrees/{branch}")
        return
    else:
        # Реально удалять
        subprocess.run(['git', 'worktree', 'remove', ...])

# ✅ РЕШЕНИЕ 2: Grace period (48 часа)

def auto_cleanup(task_key):
    """Не удалять сразу, подождать 48 часов"""
    task_done_time = datetime.fromisoformat(
        task.metadata['phase_6_complete_time']
    )
    now = datetime.now()
    
    if (now - task_done_time).days < 2:
        # Ещё не 48 часов, не удалять
        return "SKIP: Grace period active (48h)"
    
    # Теперь удалять безопасно
    cleanup_branch(task.branch)

# ✅ РЕШЕНИЕ 3: Archive вместо delete

def auto_cleanup(task_key):
    """Вместо delete → архивировать в refs/archive/"""
    branch = task.branch_name
    
    # Создать backup ref
    subprocess.run([
        'git', 'update-ref',
        f'refs/archive/{branch}',
        'HEAD'
    ])
    
    # ПОТОМ удалить
    subprocess.run(['git', 'branch', '-D', branch])
    
    # Если нужна ветка: git show refs/archive/feat-X
```

**Что делать если произойдёт:**
- [ ] Запустить Phase 2 с dry_run=True первые 2 недели
- [ ] Добавить Grace period (48 часов)
- [ ] Архивировать branches перед delete
- [ ] Документировать: "Deleted branches recoverable from refs/archive/"

---

### РИСК 6: Knowledge Base Неполная

**Проблема:**
```
Scenario: Phase 2 Week 7 (KB initialization)
├─ Собираем learnings из первых задач
├─ Но KB может быть неполная или неточная
├─ Следующий worker получит неправильные suggestions
└─ Может привести к wrong approach

Низко-вероятно, но возможно если не проверять KB.
```

**Вероятность:** 15%  
**Severity:** MEDIUM (неправильное направление)

**Как избежать:**
```python
# ✅ РЕШЕНИЕ 1: KB validation checklist

class KnowledgeBase:
    def add_learning(self, task_key, learning_dict):
        """
        Перед добавлением в KB: валидировать
        """
        # Проверки:
        assert "task_key" in learning_dict  # Откуда это пришло
        assert "problem" in learning_dict   # Что было проблемой
        assert "solution" in learning_dict  # Что помогло
        assert "success" in learning_dict   # Работает ли решение
        
        if not all([...]):
            raise ValueError("Incomplete learning, not added to KB")
        
        # Только тогда добавить
        self.learnings.append(learning_dict)

# ✅ РЕШЕНИЕ 2: Suggestions требуют подтверждения

def suggest_similar_task(task_type, domain):
    """
    Дать suggestion, но отметить что это вспомогательно
    """
    similar = kb.find_similar(task_type, domain)
    
    if similar:
        return {
            "confidence": 0.75,  # 75% уверен
            "source_tasks": ["289", "534"],
            "suggestion": "Similar approach in task-289",
            "note": "This is a suggestion. Verify before using!"
        }

# ✅ РЕШЕНИЕ 3: Only use high-confidence learnings

def get_kb_suggestions(task_key, task_type):
    """
    Использовать только learnings с высокой уверенностью
    """
    min_confidence = 0.85  # 85% minimum
    
    suggestions = [
        learning for learning in kb.find(task_type)
        if learning["confidence"] >= min_confidence
    ]
    
    return suggestions
```

**Что делать если произойдёт:**
- [ ] Добавить KB validation перед добавлением learnings
- [ ] Suggestions всегда с confidence score
- [ ] Дать advice: "Suggestions - verify before use"
- [ ] Week 6-7: вручную review KB entries

---

## 🛡️ Профилактика Рисков (Checklist)

### Перед Week 5 (подготовка):

- [ ] **Atomic writes**: os.rename() или file locking в worker-messaging.py
- [ ] **Query timeouts**: 5 мин max в data-driven-implementation
- [ ] **Early validation**: Phase 2 checklist про dry-run на stage
- [ ] **Dry-run cleanup**: First 2 weeks с dry_run=True
- [ ] **Archive branches**: refs/archive/ backup перед delete
- [ ] **Grace period**: 48h перед удалением
- [ ] **KB validation**: Checklist перед добавлением learnings

### Week 5 (запуск):

- [ ] [ ] Test concurrent writes (simulate 3 tasks одновременно)
- [ ] Test query timeout на stage DB (большая таблица)
- [ ] Test phase 3.5 + 4 parallel (race conditions?)
- [ ] Dry-run cleanup на первых 2 задачах
- [ ] Monitor logs: ошибок нет?

### Week 6-8 (monitoring):

- [ ] Daily metrics: avg task time, failures, timeouts
- [ ] Weekly review: KB quality (suggestions working?)
- [ ] Bi-weekly: architecture review (bottlenecks?)
- [ ] Watch for: data-driven failures, phase 3.5 stuck tasks

---

## 📊 Risk Matrix

| Risk | Probability | Severity | Detection | Mitigation |
|------|-------------|----------|-----------|-----------|
| Race condition (writes) | 15% | HIGH | Logs | Atomic writes ✓ |
| Phase 3.5 timeout | 25% | MEDIUM | Monitoring | Query timeout ✓ |
| Late validation (3.5 fail) | 20% | HIGH | Logs | Early dry-run ✓ |
| Branch conflict | 10% | LOW | Tests | Check exists ✓ |
| Wrong cleanup | 5% | HIGH | Review | Dry-run + archive ✓ |
| KB incomplete | 15% | MEDIUM | Manual | Validation ✓ |

---

## 🎯 Summary: Как Избежать Проблем

```
✅ 1. Atomic writes — os.rename() in worker-messaging.py
✅ 2. Query timeouts — 5 min max per Phase 3.5 query
✅ 3. Early validation — Dry-run query in Phase 2
✅ 4. Dry-run cleanup — First 2 weeks test mode
✅ 5. Archive branches — refs/archive/ backup
✅ 6. KB validation — Checklist before adding learnings
✅ 7. Monitor daily — Track metrics, failures, timeouts
✅ 8. Test concurrent — Simulate 3+ concurrent tasks
✅ 9. Grace period — 48h before deletion
✅ 10. Suggestions flagged — Confidence scores + warnings
```

**If you do these 10 things → Phase 2 will be smooth! 🚀**

---

## История

| Версия | Дата | Изменения |
|--------|------|----------|
| 1.0 | 2026-10-08 | Initial: 6 risks + mitigations + checklist |
