---
name: SKILL
version: 1.0.0
layer: go-service-engineer
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# Go Service Engineer — platform-new Development

You are building stateful and stateless Go services in `platform-new/`.

## Development pattern reference

**Follow `.claude/skills/pattern-development-go.md`** — 7-step structured development lifecycle + 6 Go-specific security checks:

1. **ПОНИМАНИЕ** (Understanding) — Read spec, identify goroutines, context, error handling needs
2. **ПЛАН** (Planning) — File structure (domain → repo → service → handler), dependencies
3. **КОД** (Implementation) — Write handlers, services, domain models; context is ALWAYS first arg
4. **SECURITY** — SQL injection, goroutine leaks, deadlocks, resource exhaustion, nil pointers, secrets
5. **ТЕСТЫ** (Testing) — Table-driven tests, context timeout tests, goroutine leak detection
6. **КОММИТ** (Commit) — go fmt, go vet, go test -race (MANDATORY)
7. **MR** (Merge Request) — Structured description, mention goroutines/channels, -race passing

## Service repositories (platform-new)

| Service | Use case | Key stack |
|---------|----------|-----------|
| `checkout` | Stateful checkout orchestration | chi, pgx, goose, goose migrations |
| `intgateway` | Stateless BFF / integration gateway | chi, generated client DTOs, GJ clients |
| `policyengine` | Stateful policy evaluation | chi, pgx, goose |
| `recommendationengine` | Similar-products recommendations | Fiber, PostgreSQL |

Before editing, consult the service's own:
- `README.md` — overview
- `CLAUDE.md` — service-specific rules (if present)
- `docs/architecture/` — ADRs and architecture decisions
- `Makefile` — build/test/lint commands
- `go.mod` — dependencies and versions

## HTTP Handler patterns

### Chi routing (chi/v5)

```go
// cmd/<service>/main.go or internal/app/app.go
package main

import "github.com/go-chi/chi/v5"

func setupRoutes(h *handler.Handler) chi.Router {
    r := chi.NewRouter()
    
    // Global middleware
    r.Use(middleware.Logger)
    r.Use(middleware.RequestID)  // for trace propagation
    
    // Subrouter for API
    r.Route("/api/v1", func(r chi.Router) {
        r.Route("/checkouts", func(r chi.Router) {
            r.Post("/", h.CreateCheckout)        // POST /api/v1/checkouts
            r.Get("/{checkoutID}/state", h.GetState)  // GET /api/v1/checkouts/{id}/state
            r.Post("/{checkoutID}/commit", h.Commit)  // POST /api/v1/checkouts/{id}/commit
        })
    })
    
    return r
}
```

### Handler method structure

```go
// internal/handler/checkout.go
package handler

import (
    "net/http"
    "encoding/json"
    
    "myservice/internal/service"
)

type CheckoutHandler struct {
    service service.CheckoutService
    logger  logger.Logger  // or your logging interface
}

// ✅ MANDATORY: method signature
func (h *CheckoutHandler) GetState(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()  // Extract context from HTTP request (includes deadlines)
    
    // Extract path params (using chi)
    checkoutID := chi.URLParam(r, "checkoutID")
    
    // Call service (context propagates)
    state, err := h.service.GetState(ctx, checkoutID)
    if err != nil {
        h.logger.Error("failed to get checkout state", "error", err)
        http.Error(w, "Internal Server Error", http.StatusInternalServerError)
        return
    }
    
    // Return JSON
    w.Header().Set("Content-Type", "application/json")
    if err := json.NewEncoder(w).Encode(state); err != nil {
        h.logger.Error("failed to encode response", "error", err)
    }
}
```

## Database / Repository layer

### Context with timeout

```go
// internal/repository/checkout.go
package repository

import (
    "context"
    "time"
)

func (r *Repository) GetState(ctx context.Context, id string) (*State, error) {
    // Add query-specific timeout (if not already limited by HTTP deadline)
    queryCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()
    
    // Use QueryRowContext, not QueryRow
    row := r.db.QueryRowContext(queryCtx,
        `SELECT id, status, total FROM checkouts WHERE id = $1`,
        id,  // Parameterized — NEVER string concat
    )
    
    var s State
    if err := row.Scan(&s.ID, &s.Status, &s.Total); err != nil {
        return nil, fmt.Errorf("scan checkout: %w", err)  // MANDATORY: wrap with %w
    }
    
    return &s, nil
}
```

### Migration management (goose)

```bash
# Discover which migrations exist
ls -la internal/db/migrations/

# Add new migration (creates timestamp_name.sql)
goose create AddCheckoutStateColumn sql

# Run migrations (in Dockerfile or dev container)
goose up
```

File format: `<timestamp>_<name>.sql`

```sql
-- internal/db/migrations/20261006_create_checkouts.sql
-- +goose Up
CREATE TABLE checkouts (
    id UUID PRIMARY KEY,
    status VARCHAR(50) NOT NULL,
    total DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- +goose Down
DROP TABLE checkouts;
```

## Service layer

```go
// internal/service/checkout.go
package service

import (
    "context"
    "fmt"
    
    "myservice/internal/repository"
)

type CheckoutService struct {
    repo repository.CheckoutRepository
}

// ✅ MANDATORY: context as first parameter after receiver
func (s *CheckoutService) GetState(ctx context.Context, id string) (*State, error) {
    state, err := s.repo.GetState(ctx, id)
    if err != nil {
        return nil, fmt.Errorf("get checkout state: %w", err)
    }
    return state, nil
}
```

## Goroutine patterns

### ❌ WRONG: Unmanaged goroutine

```go
// This goroutine may run after shutdown!
go func() {
    time.Sleep(30 * time.Second)
    doSomething()
}()
```

### ✅ CORRECT: Context-aware goroutine

```go
// Launches a background worker
func (a *App) StartWorker() error {
    a.ctx, a.cancel = context.WithCancel(context.Background())
    
    go func() {
        ticker := time.NewTicker(30 * time.Second)
        defer ticker.Stop()
        
        for {
            select {
            case <-a.ctx.Done():
                return  // Graceful shutdown
            case <-ticker.C:
                a.doSomething()
            }
        }
    }()
    
    return nil
}

func (a *App) Stop() {
    if a.cancel != nil {
        a.cancel()  // Signal goroutine to exit
    }
}
```

## Configuration

### Environment-based config

```go
// internal/config/config.go
package config

import "os"

type Config struct {
    DBHost     string
    DBPort     string
    HTTPPort   string
}

func LoadConfig() *Config {
    return &Config{
        DBHost:   os.Getenv("DB_HOST"),   // Required; fail if empty
        DBPort:   os.Getenv("DB_PORT"),
        HTTPPort: os.Getenv("HTTP_PORT"),
    }
}

// Validate checks required fields
func (c *Config) Validate() error {
    if c.DBHost == "" {
        return fmt.Errorf("DB_HOST is required")
    }
    return nil
}
```

### Docker env in Dockerfile

```dockerfile
FROM golang:1.21 AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o app ./cmd/app

FROM golang:1.21
ENV DB_HOST=postgres
ENV DB_PORT=5432
ENV HTTP_PORT=8080
COPY --from=builder /app/app /app
ENTRYPOINT ["/app"]
```

## Makefile conventions

Standard targets for Go services:

```makefile
.PHONY: build test lint fmt generate

generate:
	@echo "Generating code (OpenAPI, sqlc, etc.)"
	# go generate ./...
	# or specific tools like: openapi-generator, oapi-codegen, etc.

fmt:
	@echo "Formatting code"
	go fmt ./...

lint:
	@echo "Running linters"
	go vet ./...
	# Optional: golangci-lint, etc.

test:
	@echo "Running tests"
	go test -race -cover ./...

build:
	@echo "Building binary"
	go build -o bin/app ./cmd/app

run:
	@echo "Running app"
	go run ./cmd/app

docker-build:
	docker build -t myservice:latest .
```

**MANDATORY checks before commit:**

```bash
make fmt      # Must pass
make lint     # Must pass
make test     # Must pass (includes -race)
```

## Error handling and logging

### Error wrapping

```go
// ✅ CORRECT: wrap with %w for error chain preservation
if err != nil {
    return nil, fmt.Errorf("fetch product %s: %w", productID, err)
}

// ❌ WRONG: loses error chain
if err != nil {
    return nil, errors.New("failed to fetch")
}

// ❌ WRONG: unwrapped
if err != nil {
    return nil, err
}
```

### Structured logging

```go
import "log/slog"  // or use your structured logger

logger.InfoContext(ctx, "checkout created",
    "checkout_id", checkoutID,
    "user_id", userID,
    "total", total,
)

logger.ErrorContext(ctx, "checkout validation failed",
    "error", err,
    "checkout_id", checkoutID,
)
```

**Never log secrets** (passwords, tokens, API keys).

## Testing conventions

### Table-driven tests

```go
func TestGetState(t *testing.T) {
    tests := []struct {
        name       string
        checkoutID string
        want       *State
        wantErr    bool
    }{
        {
            name:       "valid checkout",
            checkoutID: "co-123",
            want:       &State{ID: "co-123", Status: "pending"},
            wantErr:    false,
        },
        {
            name:       "not found",
            checkoutID: "invalid",
            want:       nil,
            wantErr:    true,
        },
    }
    
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := svc.GetState(context.Background(), tt.checkoutID)
            if (err != nil) != tt.wantErr {
                t.Errorf("GetState() error = %v, wantErr %v", err, tt.wantErr)
            }
            if !tt.wantErr && got.ID != tt.want.ID {
                t.Errorf("GetState() ID = %v, want %v", got.ID, tt.want.ID)
            }
        })
    }
}
```

### Context timeout tests

```go
func TestGetState_ContextTimeout(t *testing.T) {
    ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
    defer cancel()
    
    // Simulate slow DB
    time.Sleep(200 * time.Millisecond)
    
    _, err := svc.GetState(ctx, "co-123")
    if err != context.DeadlineExceeded {
        t.Errorf("expected DeadlineExceeded, got %v", err)
    }
}
```

### Goroutine leak detection

```go
func TestGoroutineLeaks(t *testing.T) {
    before := runtime.NumGoroutine()
    
    // Run operation
    app := NewApp()
    app.Start()
    time.Sleep(100 * time.Millisecond)
    app.Stop()
    
    // Give goroutines time to exit
    time.Sleep(100 * time.Millisecond)
    
    after := runtime.NumGoroutine()
    if after > before {
        t.Errorf("goroutine leak: before=%d, after=%d", before, after)
    }
}
```

**Run tests with -race:**

```bash
go test -race ./...
```

## Common pitfalls

| Pitfall | Fix |
|---------|-----|
| `context.Background()` inside request handler | Always use `r.Context()` — it includes HTTP deadline |
| Goroutine without cancel signal | Use `select { case <-ctx.Done(): return }` |
| Error not wrapped | Use `fmt.Errorf("%w", err)` |
| DB query without context | Use `QueryRowContext`, `ExecContext`, not `QueryRow` / `Exec` |
| Hardcoded secrets in code | Read from env vars or config files |
| Secrets in logs | Never log API keys, passwords, or auth tokens |
| Nil pointer dereference | Check for nil before dereferencing |
| Channel send/recv without buffer or listener | Use buffered channels or ensure both sides ready |

## Checklist before commit

```
[ ] go fmt ./... passed
[ ] go vet ./... passed
[ ] go test -race ./... passed
[ ] All handlers accept context.Context from r.Context()
[ ] All I/O functions have context as first param (after receiver)
[ ] Error wrapping used everywhere (fmt.Errorf with %w)
[ ] Goroutines have cancellation signal (ctx.Done)
[ ] No secrets in code or logs
[ ] Table-driven tests for main paths
[ ] Context timeout tests exist
[ ] Goroutine leak tests exist (if goroutines used)
[ ] Makefile targets (fmt, lint, test, build) all pass
[ ] No TODOs without associated tickets
```

---

**Version:** 1.0  
**Updated:** 2026-10-06  
**Depends on:** pattern-development-go.md
