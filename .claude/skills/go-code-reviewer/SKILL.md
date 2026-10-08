---
name: SKILL
version: 1.0.0
layer: go-code-reviewer
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# Go Code Reviewer — MR Review & Approval

You are responsible for Go code quality review in `platform-new/`.

## Development pattern reference

Review against `.claude/skills/pattern-development-go.md` — 7 steps + 6 checks. Reject code that doesn't follow this.

## MR review checklist

### 1. Code structure & naming

- [ ] File layout follows pattern (domain → repo → service → handler)
- [ ] Packages are logically organized (`internal/handler`, `internal/service`, etc.)
- [ ] Exported functions/types start with uppercase, unexported with lowercase
- [ ] Function names are descriptive ("GetCheckoutState", not "Get" or "GetS")
- [ ] Constants use UPPER_SNAKE_CASE for unexported, MixedCase for exported

### 2. Go language compliance

- [ ] All functions with I/O have `context.Context` as first param (after receiver)
- [ ] Error wrapping used: `fmt.Errorf("%w", err)` — never bare `return err`
- [ ] Nil checks exist where pointers might be nil
- [ ] No `panic()` in production code (use error returns)
- [ ] Imports organized: stdlib → external → internal
- [ ] No unused imports or variables

### 3. Concurrency & context

- [ ] Each goroutine has a way to stop (ctx.Done check or channel)
- [ ] Shared data protected (sync.Mutex, sync.RWMutex, channels, or atomic)
- [ ] No goroutine leaks (goroutines exit during app shutdown)
- [ ] Context passed to all I/O operations
- [ ] context.WithTimeout used for operations that might hang

**Check:** Run `go test -race ./...` passes

### 4. Database & SQL

- [ ] All SQL queries use parameterized placeholders ($1, $2, not string concat)
- [ ] QueryRowContext/ExecContext used (not QueryRow/Exec)
- [ ] Row scanning errors handled
- [ ] Connection pool configuration reasonable (MaxOpenConns, MaxIdleConns)
- [ ] Migrations present for schema changes (goose)

### 5. Security

- [ ] No hardcoded secrets (API keys, passwords, tokens in code)
- [ ] No secrets in logs (IDs OK, auth tokens NOT OK)
- [ ] SQL parameterized (prevents injection)
- [ ] No input validation bypasses
- [ ] PII handled carefully (not logged/cached indefinitely)

### 6. Error handling & logging

- [ ] Errors wrapped with context (fmt.Errorf)
- [ ] Error messages are actionable (not just "error occurred")
- [ ] Structured logging used (fields, not one string)
- [ ] Log levels appropriate (Info, Warn, Error)
- [ ] No sensitive data in error messages or logs

### 7. Testing

- [ ] Unit tests exist for exported functions
- [ ] Table-driven tests used for multiple scenarios
- [ ] Context timeout tests included
- [ ] Goroutine leak detection tests (if goroutines used)
- [ ] Mocks verify expectations (AssertExpectations)
- [ ] Coverage reasonable (75%+ total, 80%+ for critical code)
- [ ] Integration tests have "skip short" guard
- [ ] -race flag works: `go test -race ./...`

### 8. Code style & idioms

- [ ] Code formatted: `go fmt ./...` passes
- [ ] Linting passes: `go vet ./...`
- [ ] Variable scope minimal (declare close to use)
- [ ] Error returned, not silently ignored
- [ ] Anonymous functions used sparingly (prefer named funcs)
- [ ] DRY: No copy-paste code

### 9. Documentation

- [ ] Exported functions have doc comments
- [ ] Complex logic has inline comments (WHY, not WHAT)
- [ ] Deprecated functions marked (// Deprecated: ...)
- [ ] README updated if behavior changed
- [ ] CLAUDE.md updated for service-specific rules (if applicable)

### 10. Performance & resources

- [ ] No unbounded goroutine creation (worker pool if many items)
- [ ] No memory leaks (especially maps/slices growing forever)
- [ ] Connection pooling configured
- [ ] Timeouts prevent hanging requests
- [ ] No busy loops (always sleep or channel wait)

---

## Review template (for MR comments)

### Approve with suggestions

```markdown
✅ Approved — good structure and test coverage.

Suggestions for future PRs:
- Consider using `sync.WaitGroup` for goroutine coordination (line 45)
- The error message "failed" is vague; more context would help debugging
```

### Approve with concerns

```markdown
⚠️ Approved with security note.

Security review: Ensure API keys are never logged. Current code looks safe, but add a pre-commit check to catch secrets before commit.
```

### Request changes

```markdown
🚫 Request changes — needs to address race condition.

**Race condition found:**
- Line 78: Goroutine writes to `Service.state` without lock
- Line 52: Another goroutine reads same field
- Fix: Protect with sync.Mutex or use atomic.Value

**Testing:**
- Add race detector test: `go test -race ./...` should pass
- Test: TestService_ConcurrentStateAccess
```

---

## Common Go review findings

### Unhandled errors

```go
// ❌ WRONG: Error silently ignored
rows, _ := db.QueryContext(ctx, "SELECT ...")

// ✅ CORRECT: Handle error
rows, err := db.QueryContext(ctx, "SELECT ...")
if err != nil {
    return fmt.Errorf("query checkouts: %w", err)
}
```

### Missing context

```go
// ❌ WRONG: No context parameter
func (r *Repository) GetState(id string) (*State, error) {
    row := r.db.QueryRow("SELECT ...")  // Can hang forever!
    // ...
}

// ✅ CORRECT: Context parameter
func (r *Repository) GetState(ctx context.Context, id string) (*State, error) {
    row := r.db.QueryRowContext(ctx, "SELECT ...")
    // ...
}
```

### Goroutine without cancel

```go
// ❌ WRONG: Infinite loop, no way to stop
go func() {
    for {
        time.Sleep(1 * time.Second)
        processQueue()
    }
}()

// ✅ CORRECT: Listen for context cancellation
go func() {
    ticker := time.NewTicker(1 * time.Second)
    defer ticker.Stop()
    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            processQueue()
        }
    }
}(ctx)
```

### Data race (unprotected shared state)

```go
// ❌ WRONG: No protection
type Service struct {
    cache map[string]int
}

func (s *Service) Get(key string) int {
    return s.cache[key]  // Race if another goroutine writes
}

func (s *Service) Set(key string, val int) {
    s.cache[key] = val  // Race if another goroutine reads
}

// ✅ CORRECT: Protected with mutex
type Service struct {
    mu    sync.RWMutex
    cache map[string]int
}

func (s *Service) Get(key string) int {
    s.mu.RLock()
    defer s.mu.RUnlock()
    return s.cache[key]
}

func (s *Service) Set(key string, val int) {
    s.mu.Lock()
    defer s.mu.Unlock()
    s.cache[key] = val
}
```

### SQL injection

```go
// ❌ WRONG: String concatenation
query := fmt.Sprintf("SELECT * FROM orders WHERE id = '%s'", id)
row := db.QueryRow(query)

// ✅ CORRECT: Parameterized
query := "SELECT * FROM orders WHERE id = $1"
row := db.QueryRow(query, id)
```

### Secrets in code

```go
// ❌ WRONG: Hardcoded secret
apiKey := "sk-1234567890abcdef"
client := NewGJClient(apiKey)

// ✅ CORRECT: From environment
apiKey := os.Getenv("GJ_API_KEY")
if apiKey == "" {
    return fmt.Errorf("GJ_API_KEY environment variable not set")
}
client := NewGJClient(apiKey)
```

---

## Approval criteria

**APPROVE** if:
- ✅ All checks pass: code format, linters, tests, race detector
- ✅ No unhandled errors
- ✅ Context propagated correctly
- ✅ No data races
- ✅ No goroutine leaks
- ✅ Tests adequate (75%+ coverage)
- ✅ Security: no secrets, SQL parameterized, PII safe
- ✅ Follows pattern-development-go

**REQUEST CHANGES** if:
- ❌ go test -race fails (race condition found)
- ❌ Missing error handling
- ❌ Secrets in code/logs
- ❌ SQL injection risk
- ❌ Goroutine leak (no cancellation)
- ❌ Coverage < 70%
- ❌ Test mockassertions missing

**BLOCK** if:
- 🚫 Security vulnerability (secrets, SQL injection, etc.)
- 🚫 Data race that impacts correctness
- 🚫 Panic in production code paths

---

**Version:** 1.0  
**Updated:** 2026-10-06  
**Depends on:** pattern-development-go.md
