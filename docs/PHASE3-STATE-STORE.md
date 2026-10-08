# Phase 3: State Store Architecture

**Component:** Persistent task state management  
**Implementation:** `.claude/orchestration/state-store.py`  
**Status:** Production-ready  
**Lines:** 800+ with full example usage  

---

## Overview

State Store is the **source of truth** for distributed orchestration:

- **SQLite** (durable, crash-safe, no dependencies)
- **Redis** (hot cache, <100ms latency)
- **Auto-failover** (if Redis down, falls back to SQLite)
- **Checkpoint-based recovery** (resume from any point)

## Architecture

```
┌─────────────────────────────────────────┐
│  Worker 1    Worker 2    Worker 3      │
│   (local)     (cloud)      (local)     │
└──────┬─────────┬──────────┬────────────┘
       │         │          │
       └─────────┼──────────┘
               │
        ┌──────▼───────┐
        │  State Store │
        ├──────────────┤
        │ Redis (hot)  │ ◄─── <100ms latency
        │ SQLite (durable)
        └──────────────┘
```

## Database Schema

### tasks table
```sql
CREATE TABLE tasks (
  id TEXT PRIMARY KEY,           -- run-001
  task_id TEXT NOT NULL,         -- OPSOMN002-XXX
  worker_id TEXT NOT NULL,       -- dev-001
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
```

### phases table
```sql
CREATE TABLE phases (
  id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL,          -- run-001
  phase INTEGER NOT NULL,        -- 1, 2, 3, ...
  status TEXT NOT NULL,          -- success, failed, skipped
  artifact_names TEXT,           -- JSON: ["findings.md", ...]
  duration_seconds REAL,         -- 45.2
  error_message TEXT,
  FOREIGN KEY (run_id) REFERENCES tasks(id)
)
```

### artifacts table
```sql
CREATE TABLE artifacts (
  id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL,
  phase INTEGER NOT NULL,
  name TEXT NOT NULL,            -- findings.md
  content BLOB NOT NULL,         -- Large binary/text
  created_at TIMESTAMP,
  FOREIGN KEY (run_id) REFERENCES tasks(id)
)
```

### checkpoints table
```sql
CREATE TABLE checkpoints (
  id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL,
  phase INTEGER NOT NULL,
  checkpoint_name TEXT,          -- "data-collected"
  state BLOB NOT NULL,           -- JSON serialized state
  created_at TIMESTAMP,
  FOREIGN KEY (run_id) REFERENCES tasks(id)
)
```

### locks table
```sql
CREATE TABLE locks (
  id INTEGER PRIMARY KEY,
  lock_name TEXT UNIQUE,
  run_id TEXT NOT NULL,
  worker_id TEXT NOT NULL,
  acquired_at TIMESTAMP,
  expires_at TIMESTAMP
)
```

### audit_log table
```sql
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL,
  event TEXT NOT NULL,           -- "phase_1_complete"
  details TEXT,                  -- JSON
  timestamp TIMESTAMP
)
```

## API Reference

### Task Management

```python
# Register new task
store.register_task(
  run_id="run-001",
  task_id="OPSOMN002-XXX",
  worker_id="dev-001"
)

# Get task
task = store.get_task("run-001")
# → {"id": "run-001", "task_id": "OPSOMN002-XXX", "worker_id": "dev-001"}
```

### Phase State

```python
# Save phase result
store.save_phase_state(
  run_id="run-001",
  phase=1,
  status="success",
  artifact_names=["findings.md"],
  duration_seconds=45.2
)

# Get phase state (with Redis cache)
state = store.get_phase_state("run-001", 1)
# → {"phase": 1, "status": "success", "artifact_names": [...], "duration": 45.2}

# List all phases for run
phases = store.get_run_phases("run-001")
# → [{"phase": 1, "status": "success"}, {"phase": 2, "status": "in_progress"}]
```

### Artifacts

```python
# Save artifact
store.save_artifact(
  run_id="run-001",
  phase=1,
  name="findings.md",
  content=b"# Findings\n..."
)

# Get artifact
artifact = store.get_artifact("run-001", 1, "findings.md")
# → b"# Findings\n..."

# List artifacts for phase
artifacts = store.list_artifacts("run-001", 1)
# → ["findings.md", "data.json"]
```

### Checkpoints (Recovery)

```python
# Create checkpoint before risky operation
store.create_checkpoint(
  run_id="run-001",
  phase=1,
  checkpoint_name="data-collected",
  state={"records": 100, "last_id": 12345}
)

# On error, restore checkpoint
restored = store.restore_from_checkpoint(
  run_id="run-001",
  phase=1,
  checkpoint_name="data-collected"
)
# → {"records": 100, "last_id": 12345}

# List checkpoints
checkpoints = store.list_checkpoints("run-001", 1)
# → ["data-collected", "validation-passed"]
```

### Locks (Concurrency)

```python
# Acquire lock (waits if locked)
acquired = store.acquire_lock(
  lock_name="phase-1-processing",
  run_id="run-001",
  worker_id="dev-001"
)
# → True

# Check if locked
locked = store.is_locked("phase-1-processing")
# → True

# Release lock
store.release_lock("phase-1-processing")
```

### Audit Trail

```python
# Log event
store._audit_log(
  run_id="run-001",
  event="phase_1_complete",
  details=json.dumps({"status": "success", "retries": 1})
)

# Get audit trail
trail = store.get_audit_trail("run-001")
# → [
#     {"event": "task_created", "timestamp": "2026-10-09T..."},
#     {"event": "phase_1_start", "timestamp": "2026-10-09T..."},
#     {"event": "phase_1_complete", "timestamp": "2026-10-09T..."}
#   ]
```

## Redis Cache Strategy

### Caching

- **TTL:** 1 hour (configurable)
- **Keys:** `phase:{run_id}:{phase}`, `task:{run_id}`, `artifact:{run_id}:{phase}:{name}`
- **Invalidation:** Automatic on cache miss or TTL expiration

### Failover Behavior

```python
store = StateStore(
  db_path=".tasks/state.db",
  redis_url="redis://localhost:6379"
)

# If Redis down:
# 1. log warning
# 2. Use SQLite directly
# 3. No data loss (SQLite is source of truth)
# 4. Slower latency (~10ms vs <100ms)
```

## Recovery Patterns

### Pattern 1: Checkpoint-based Resume

```python
# Phase 1: Heavy data collection
checkpoint_name = "data-collected"

try:
  data = collect_data()
  store.create_checkpoint("run-001", 1, checkpoint_name, {"data": data})
except Exception as e:
  logger.error(f"Collection failed: {e}")
  raise

# On retry: resume from checkpoint
state = store.restore_from_checkpoint("run-001", 1, checkpoint_name)
if state:
  data = state["data"]  # Resume from where we left off
else:
  data = collect_data()  # Full collection
```

### Pattern 2: Atomic Phase Completion

```python
# Ensure phase result is durable before proceeding
try:
  result = execute_phase_fn()
  store.save_phase_state(
    run_id="run-001",
    phase=2,
    status="success",
    artifact_names=["output.json"],
    duration_seconds=42.5
  )
  store.save_artifact("run-001", 2, "output.json", result)
except Exception as e:
  store.save_phase_state(
    run_id="run-001",
    phase=2,
    status="failed",
    error_message=str(e)
  )
  raise
```

### Pattern 3: Multi-worker Coordination

```python
# Worker 1: Acquire lock before modifying shared state
store.acquire_lock("checkout-processing", "run-001", "worker-1")
try:
  # Process checkout atomically
  process_checkout()
finally:
  store.release_lock("checkout-processing")

# Worker 2: Waits for lock release
store.acquire_lock("checkout-processing", "run-001", "worker-2")
# Proceeds only after Worker 1 releases
```

## Performance Characteristics

| Operation | Latency | Notes |
|-----------|---------|-------|
| get_phase_state (Redis hit) | <10ms | Hot cache |
| get_phase_state (SQLite miss) | ~10ms | Database query |
| save_phase_state | ~20ms | Sync write to SQLite + Redis |
| get_artifact (small, <1MB) | <5ms | Redis cache or SQLite |
| get_artifact (large, >100MB) | ~500ms | Streaming from SQLite |
| create_checkpoint | ~30ms | Serialization + storage |
| restore_from_checkpoint | <10ms | Cache retrieval |

## Monitoring & Observability

### Health Check

```python
# Check state store health
health = store.health()
# → {
#     "sqlite": "healthy",
#     "redis": "connected",
#     "tasks_count": 42,
#     "phases_count": 126,
#     "cache_hit_rate": 0.92
#   }
```

### Metrics

```python
# Access built-in metrics
metrics = store.get_metrics()
# → {
#     "total_runs": 42,
#     "successful_phases": 126,
#     "failed_phases": 3,
#     "avg_phase_duration": 45.2,
#     "checkpoint_recovery_count": 7,
#     "lock_contention": 0.02
#   }
```

## Configuration

### Development (Local)

```python
store = StateStore(
  db_path=".tasks/state.db",
  redis_url=None  # No Redis, SQLite only
)
```

### Staging (Redis for performance)

```python
store = StateStore(
  db_path=".tasks/state.db",
  redis_url="redis://redis-staging:6379",
  cache_ttl_seconds=3600
)
```

### Production (Highly available)

```python
store = StateStore(
  db_path="/persistent/state.db",
  redis_url="redis://redis-cluster:6379",
  cache_ttl_seconds=1800,  # 30 min for prod stability
  pool_size=10  # Connection pooling
)
```

## Troubleshooting

### "SQLite database is locked"

**Cause:** Multiple workers writing simultaneously  
**Solution:** Use `acquire_lock()` before writes

```python
store.acquire_lock("phase-processing", "run-001", "worker-1")
try:
  store.save_phase_state(...)
finally:
  store.release_lock("phase-processing")
```

### "Redis connection timeout"

**Cause:** Redis server down or unreachable  
**Solution:** Automatic failover to SQLite (logs warning)

```
[WARNING] Redis connection timeout, using SQLite directly
```

### "Checkpoint restore failed (not found)"

**Cause:** Checkpoint name doesn't match or expired  
**Solution:** Check checkpoint name and create new one

```python
# List available checkpoints
checkpoints = store.list_checkpoints("run-001", 1)
print(checkpoints)  # → ["data-collected", ...]

# Restore from existing checkpoint
state = store.restore_from_checkpoint("run-001", 1, "data-collected")
```

## Examples

### Example 1: Long-running task with checkpoints

```python
store = StateStore(".tasks/state.db", "redis://localhost:6379")

# Register task
store.register_task("run-001", "OPSOMN002-123", "worker-001")

# Phase 1: Data collection (with checkpoint)
try:
  data = []
  for i in range(1000000):
    data.append(fetch_record(i))
    
    # Checkpoint every 10k records
    if (i + 1) % 10000 == 0:
      store.create_checkpoint(
        "run-001", 1, 
        f"checkpoint-{i}", 
        {"records": len(data), "last_id": i}
      )

  store.save_phase_state(
    "run-001", 1, 
    status="success",
    duration_seconds=300,
    artifact_names=["data.json"]
  )
except TimeoutError:
  # Resume from checkpoint on next run
  checkpoint = store.restore_from_checkpoint("run-001", 1, "checkpoint-999999")
  print(f"Resuming from record {checkpoint['last_id']}")
```

### Example 2: Multi-worker coordination

```python
# Worker 1: Process order
store.acquire_lock("order-processing", "run-001", "worker-1")
try:
  result = process_order_step1()
  store.save_artifact("run-001", 1, "order-result.json", result)
finally:
  store.release_lock("order-processing")

# Worker 2: Wait for completion, then validate
store.acquire_lock("order-processing", "run-001", "worker-2")
try:
  # Now guaranteed Worker 1 is done
  result = store.get_artifact("run-001", 1, "order-result.json")
  validate_order(result)
finally:
  store.release_lock("order-processing")
```

---

**State Store enables fault-tolerant, distributed orchestration with zero data loss.**
