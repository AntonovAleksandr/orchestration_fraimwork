---
name: SKILL
version: 1.0.0
layer: go-debugger
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# Go Debugger — Diagnosis & Root Cause Analysis

You are a Go debugging specialist — finding and explaining bugs without writing fixes.

## Development pattern reference

Refer to `.claude/skills/pattern-development-go.md` **Security section** for bug classes:
- SQL injection (string concatenation)
- Goroutine leaks (missing cancellation)
- Deadlocks (channel misuse)
- Resource exhaustion (unbounded goroutine creation)
- Nil pointer dereference
- Secrets in code/logs

## Debugging workflow

### 1. Collect evidence

```bash
# Service logs (structured logging)
kubectl logs -f <pod-name> | grep -i error

# System logs (kernel/OS events)
journalctl -u myservice -n 50

# Traces (if OpenTelemetry or similar)
# Check observability platform (e.g., Jaeger, DataDog)

# Core dump (if available)
gdb ./binary core.dump
```

### 2. Analyze panic traces

```
panic: runtime error: invalid memory address or nil pointer dereference
[signal SIGSEGV: segmentation violation code=0x1 addr=0x0 pc=0x659a1a]

goroutine 42 [running]:
main.(*Handler).GetState(...)
    /app/internal/handler/checkout.go:45
main.(*CheckoutHandler).ServeHTTP(...)
    /app/internal/handler/handler.go:12
```

**Decode:**
- Line 45 of checkout.go had nil pointer dereference
- Goroutine 42 was handling the request
- Likely `state.ID` where `state == nil`

### 3. Race detector output

```
WARNING: DATA RACE
Write at 0x00c0001f8000 by goroutine 45:
    main.(*Service).updateStatus()
        /app/internal/service/order.go:78 +0x94

Previous read at 0x00c0001f8000 by goroutine 44:
    main.(*Service).getStatus()
        /app/internal/service/order.go:52 +0x78

Goroutine 45 (running) created at:
    main.main()
        /app/cmd/main.go:25 +0x3a8
```

**Fix approach:**
- Line 78 writes to shared variable (state)
- Line 52 reads from same variable
- **Solution:** protect with sync.Mutex or sync.RWMutex

### 4. Goroutine leak detection

**Symptom:** Memory grows, no panics, service slows down

```bash
# Check via runtime metrics
curl http://localhost:6060/debug/pprof/goroutine?debug=1 | head -20

# Look for repeated goroutine blocks
# Count: "goroutine 12345 [chan send]" growing over time
```

**Common causes:**
- Channel send without receiver: `ch <- data` with no one reading
- Infinite loop without cancellation: `for { work() }` no `ctx.Done()` check
- Forgotten `defer cancel()` after `context.WithCancel()`

## Profiling (pprof)

### CPU profiling

```bash
# Generate 30-second CPU profile
go tool pprof -http=:8080 "http://localhost:6060/debug/pprof/profile?seconds=30"

# Or collect and analyze locally
curl "http://localhost:6060/debug/pprof/profile?seconds=30" > cpu.prof
go tool pprof cpu.prof
# In pprof shell: top10, list main.someFunction
```

**Read output:** top consumers of CPU time

### Memory profiling

```bash
# Heap (allocations)
curl http://localhost:6060/debug/pprof/heap > heap.prof
go tool pprof -http=:8080 heap.prof

# Goroutine count
curl http://localhost:6060/debug/pprof/goroutine > goroutine.prof
go tool pprof goroutine.prof
```

**Look for:** growing allocations, stuck goroutines

### Enable pprof in service

```go
// main.go or internal/app/app.go
import _ "net/http/pprof"

func main() {
    // Start pprof server on separate port
    go func() {
        log.Println(http.ListenAndServe("localhost:6060", nil))
    }()

    // ... start main app
}
```

## Debugger (dlv)

### Attach to running process

```bash
# Run with debug flags
GOGC=off go run -gcflags="all=-N -l" ./cmd/app

# In another terminal, find PID
ps aux | grep app

# Attach debugger
dlv attach <PID>

# Set breakpoint and inspect
(dlv) break main.GetCheckoutState
(dlv) continue
(dlv) print ctx
(dlv) print state
(dlv) next  # step through
```

### Remote debugging

```bash
# Terminal 1: Run dlv headless
dlv exec ./binary --listen=:2345 --headless

# Terminal 2: Connect
dlv connect localhost:2345
```

## Common bug patterns

### Nil pointer dereference

```go
// ❌ WRONG: No nil check
func (h *Handler) GetState(w http.ResponseWriter, r *http.Request) {
    state, _ := h.service.GetState(r.Context(), id)
    return state.ID  // Panics if state == nil
}

// ✅ CORRECT: Check first
func (h *Handler) GetState(w http.ResponseWriter, r *http.Request) {
    state, err := h.service.GetState(r.Context(), id)
    if err != nil || state == nil {
        http.Error(w, "Not found", http.StatusNotFound)
        return
    }
    return state.ID
}
```

### Goroutine leak

```go
// ❌ LEAK: No cancellation signal
go func() {
    for {
        time.Sleep(1 * time.Second)
        doWork()  // Runs forever, even after shutdown!
    }
}()

// ✅ CORRECT: Listen for ctx.Done()
go func() {
    ticker := time.NewTicker(1 * time.Second)
    defer ticker.Stop()
    
    for {
        select {
        case <-ctx.Done():
            return  // Exit when context cancelled
        case <-ticker.C:
            doWork()
        }
    }
}(ctx)
```

### Deadlock

```go
// ❌ DEADLOCK: Channel with no buffer, sender waits for receiver
ch := make(chan int)  // Unbuffered

go func() {
    ch <- 1  // Blocks — nobody reading!
}()

val := <-ch  // This line never reached
```

```go
// ✅ CORRECT: Buffered or separate goroutine
ch := make(chan int, 1)  // Buffer size 1

go func() {
    ch <- 1  // Doesn't block
}()

val := <-ch  // Reads
```

### Context not propagated

```go
// ❌ WRONG: Ignores request deadline
func (s *Service) FetchData(id string) (*Data, error) {
    // No context parameter — can hang indefinitely
    return s.repo.Get(id)
}

// ✅ CORRECT: Pass context through
func (s *Service) FetchData(ctx context.Context, id string) (*Data, error) {
    return s.repo.Get(ctx, id)  // Respects deadline
}
```

### Resource exhaustion

```go
// ❌ WRONG: Creates unbounded goroutines
func (s *Service) ProcessItems(items []Item) {
    for _, item := range items {
        go s.process(item)  // 10000 items = 10000 goroutines!
    }
}

// ✅ CORRECT: Worker pool with limit
func (s *Service) ProcessItems(ctx context.Context, items []Item) error {
    workers := 10
    semaphore := make(chan struct{}, workers)
    
    for _, item := range items {
        select {
        case <-ctx.Done():
            return ctx.Err()
        case semaphore <- struct{}{}:
            go func(i Item) {
                defer func() { <-semaphore }()
                s.process(ctx, i)
            }(item)
        }
    }
    return nil
}
```

## Log analysis

### Structured logging

Look for:
```json
{
  "level": "error",
  "msg": "failed to get checkout state",
  "error": "context deadline exceeded",
  "checkout_id": "co-123",
  "duration_ms": 5000
}
```

**Diagnose:** Takes 5000ms → hit timeout context

### Stack trace in logs

If logged with `%+v` on error with stack:
```
failed to get checkout state: scan checkout
  /app/internal/repository/checkout.go:78
failed to get state
  /app/internal/service/checkout.go:45
```

**Trace:** Error originated at line 78 (SQL scan failure)

## Diagnostic checklist

```
[ ] Collect panic/error logs and timestamps
[ ] Run go test -race locally to find data races
[ ] Check goroutine count: curl http://localhost:6060/debug/pprof/goroutine
[ ] Review recent code changes in error area
[ ] Test error scenario locally with small input
[ ] Profile if performance degradation (pprof)
[ ] Check if context deadline exceeded errors in logs
[ ] Verify all goroutines have cancellation (ctx.Done)
[ ] Verify mocks in tests match real behavior
```

---

**Version:** 1.0  
**Updated:** 2026-10-06  
**Depends on:** pattern-development-go.md (Security checks section)
