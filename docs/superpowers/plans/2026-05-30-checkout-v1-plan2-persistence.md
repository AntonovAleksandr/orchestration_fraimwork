# Checkout v1 — Plan 2: Persistence (Postgres session store) Implementation Plan

> **Domain-map (2026-05-30):** персистентность принадлежит домену **`session`** (агрегат-корень). Пути в плане перепривязаны `internal/domains/checkout`→`internal/domains/session`. Канон — `platform-new/checkout/docs/architecture/domain-map.md`. Локальная Postgres dev: `dev/docker-compose.yml` (15.4, порт 5544, DSN `postgres://checkout:checkout@127.0.0.1:5544/checkout?sslmode=disable`).

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the in-memory `SessionStore` with a Postgres-backed repository (pgx v5), apply schema via `gj-go-migrate`, make `/health/ready` verify the DB, and add `GET /checkout/{id}` — so checkout sessions persist across restarts.

**Architecture:** `internal/platform/storage` owns a `*pgxpool.Pool`; `internal/domains/session/repository.go` implements the existing `SessionStore` port over pgx. Migrations are SQL files run by the `gj-go-migrate` CLI (`migrate-runner`). The `SessionStore` port is unchanged — only the implementation swaps in `wire.Session`.

**Tech Stack:** `github.com/jackc/pgx/v5` (v5.7.2) + `pgxpool`; `gj-go-migrate` CLI (golang-migrate file source), запускается через `scripts/migrate.sh` (`go run gj-go-migrate@v1.0.5`, published-версия, Buddy-стиль — без sibling/replace); **Postgres 15.4 (prod-synced; dev via `dev/docker-compose.yml`, порт 5544)**.

**Prereq:** Plan 1 complete (running skeleton, in-memory store behind `SessionStore`).

**Reference:** `platform/non-platform/ecom-stat-service/internal/repository/*` (pgxpool repository pattern), `platform-new/gj-go-migrate/migrator.go` (CLI usage), `ecom-stat-service/migrations/` (SQL file naming).

**DB conventions:** snake_case columns; `checkout_sessions` table keyed by `checkout_id` (uuid PK); JSONB for future nested selection (added later plans); `created_at/updated_at/expires_at timestamptz`.

---

## File Structure (Plan 2)

```
checkout/
├── migrations/
│   ├── 0001_checkout_sessions.up.sql
│   └── 0001_checkout_sessions.down.sql
├── internal/platform/storage/
│   ├── postgres.go           pgxpool.New + Ping + Close
│   └── postgres_test.go      (guarded integration test)
└── internal/domains/session/
    ├── repository.go         pgx-backed SessionStore (Create/Get)
    └── repository_test.go    (guarded integration test)
```
(`stub.go` / `InMemoryStore` stays — used by unit tests of service/handler.)

---

## Task 1: Migration — `checkout_sessions` table

**Files:**
- Create: `migrations/0001_checkout_sessions.up.sql`, `migrations/0001_checkout_sessions.down.sql`
- Modify: `Makefile` (add `migrate` target)

- [ ] **Step 1: Write `migrations/0001_checkout_sessions.up.sql`**

```sql
CREATE TABLE IF NOT EXISTS checkout_sessions (
    checkout_id      uuid PRIMARY KEY,
    client_order_id  text        NOT NULL,
    customer_id      text        NOT NULL,
    basket_id        text        NOT NULL,
    status           text        NOT NULL,
    totals_checksum  bigint      NULL,   -- копейки int64 (money-policy), НЕ numeric/float
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    expires_at       timestamptz NULL
);

CREATE INDEX IF NOT EXISTS idx_checkout_sessions_customer_basket
    ON checkout_sessions (customer_id, basket_id);
```

- [ ] **Step 2: Write `migrations/0001_checkout_sessions.down.sql`**

```sql
DROP TABLE IF EXISTS checkout_sessions;
```

- [ ] **Step 3: Add `scripts/migrate.sh` + Makefile-таргеты** (Buddy-стиль). НЕ собирать gj-go-migrate из sibling и НЕ добавлять в go.mod — это `package main` CLI, тянем **опубликованной версией** через `go run …@tag` (как `gj-buddy-server/scripts/migrate.sh`). Скрипт грузит `.env`, берёт DSN из `CHECKOUT_DB_DSN` (или строит из `POSTGRES_*`, или дефолт local dev), выставляет `GOPRIVATE`/`GONOSUMDB`/`GOPROXY` (Nexus→direct).

`scripts/migrate.sh` (см. готовый в репо; ядро):
```bash
export GOPRIVATE="${GOPRIVATE:-gitlab.gloria.aaanet.ru/*}"
export GOPROXY="${GOPROXY:-https://nexus-core.gloj.ru/repository/golang-proxy/,direct}"
exec go run "gitlab.gloria.aaanet.ru/go-pkg/gj-go-migrate@${MIGRATOR_VERSION}" \
  --path "$MIGRATIONS_PATH" --database "$database_dsn" "$command_name"
```
Makefile:
```makefile
.PHONY: migrate-up migrate-version
migrate-up:
	./scripts/migrate.sh up
migrate-version:
	./scripts/migrate.sh version
```
> Резолв: Nexus go-proxy (в сети GJ) → `direct` (SSH через git `insteadOf`). В песочнице/без Nexus — `GOPROXY=direct ./scripts/migrate.sh …`. **Никаких relative-путей и sibling-сборки** — репо самодостаточен (Buddy-стиль).
> ⚠️ Runner умеет только `up`/`version`, **нет `force`**. Если миграция упадёт на полпути → `schema_migrations.dirty=true`, разлочить им нельзя. В dev лечится пересозданием БД: `docker compose -f dev/docker-compose.yml down -v && up -d`, затем `make migrate-up`.

- [ ] **Step 4: Verify migration applies (local Postgres)**

Run:
```bash
docker compose -f dev/docker-compose.yml up -d        # Postgres 15.4 на :5544 (= прод)
make migrate-up
psql 'postgres://checkout:checkout@127.0.0.1:5544/checkout?sslmode=disable' -c '\d checkout_sessions'
make migrate-version
```
Expected: таблица + индекс есть; `schema_migrations` версия 1; `migrate-version` печатает `version=1 dirty=false`.

- [ ] **Step 5: Commit**

```bash
git add migrations Makefile go.mod go.sum
git commit -m "feat(db): checkout_sessions migration + make migrate-up/version (gj-go-migrate)"
```

---

## Task 2: Postgres pool — `internal/platform/storage`

**Files:**
- Create: `internal/platform/storage/postgres.go`, `internal/platform/storage/postgres_test.go`
- Modify: `internal/platform/config/config.go` (DSN required when present), `go.mod`

- [ ] **Step 1: Add pgx dep**

Run: `go get github.com/jackc/pgx/v5@v5.7.2`

- [ ] **Step 2: Write `internal/platform/storage/postgres.go`**

```go
// Package storage owns the Postgres connection pool (cross-cutting infra).
package storage

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// NewPool opens a pgx pool and verifies connectivity with a bounded Ping.
func NewPool(ctx context.Context, dsn string) (*pgxpool.Pool, error) {
	if dsn == "" {
		return nil, fmt.Errorf("storage: empty DSN")
	}
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return nil, fmt.Errorf("storage: open pool: %w", err)
	}
	pingCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	if err := pool.Ping(pingCtx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("storage: ping: %w", err)
	}
	return pool, nil
}
```

- [ ] **Step 3: Make DSN required in config**

In `internal/platform/config/config.go`, update `Validate()`:
```go
func (c Config) Validate() error {
	if c.HTTP.Port == "" {
		return fmt.Errorf("config: HTTP_PORT is required")
	}
	if c.DB.DSN == "" {
		return fmt.Errorf("config: CHECKOUT_DB_DSN is required")
	}
	return nil
}
```

- [ ] **Step 4: Write guarded integration test `postgres_test.go`**

```go
package storage

import (
	"context"
	"os"
	"testing"
)

// Integration: set CHECKOUT_TEST_DB_DSN to run (skips otherwise).
func TestNewPool_pingsRealDB(t *testing.T) {
	dsn := os.Getenv("CHECKOUT_TEST_DB_DSN")
	if dsn == "" {
		t.Skip("set CHECKOUT_TEST_DB_DSN to run storage integration test")
	}
	pool, err := NewPool(context.Background(), dsn)
	if err != nil {
		t.Fatalf("NewPool: %v", err)
	}
	defer pool.Close()
	if err := pool.Ping(context.Background()); err != nil {
		t.Fatalf("Ping: %v", err)
	}
}

func TestNewPool_emptyDSN(t *testing.T) {
	if _, err := NewPool(context.Background(), ""); err == nil {
		t.Fatal("expected error for empty DSN")
	}
}
```

- [ ] **Step 5: Run + commit**

Run: `go build ./... && go test ./internal/platform/storage/ -v` (integration skipped without DSN).
```bash
git add internal/platform/storage internal/platform/config/config.go go.mod go.sum
git commit -m "feat(storage): pgx pool + DSN config (required)"
```

---

## Task 3: pgx-backed `SessionStore` — `repository.go` (TDD)

**Files:**
- Create: `internal/domains/session/repository.go`, `internal/domains/session/repository_test.go`

- [ ] **Step 1: Write failing integration test `repository_test.go`**

```go
package session

import (
	"context"
	"os"
	"testing"

	"gj-checkout/internal/platform/storage"
	"github.com/google/uuid"
)

// Integration: set CHECKOUT_TEST_DB_DSN (migrated DB) to run.
func TestRepository_CreateGetRoundtrip(t *testing.T) {
	dsn := os.Getenv("CHECKOUT_TEST_DB_DSN")
	if dsn == "" {
		t.Skip("set CHECKOUT_TEST_DB_DSN (migrated) to run")
	}
	pool, err := storage.NewPool(context.Background(), dsn)
	if err != nil {
		t.Fatalf("pool: %v", err)
	}
	defer pool.Close()

	repo := NewRepository(pool)
	sess := Session{
		CheckoutID:    uuid.NewString(),
		ClientOrderID: "2000019994",
		CustomerID:    "cust-1",
		BasketID:      "2000019994",
		Status:        StatusDraft,
	}
	if err := repo.Create(context.Background(), sess); err != nil {
		t.Fatalf("Create: %v", err)
	}
	got, err := repo.Get(context.Background(), sess.CheckoutID)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.ClientOrderID != "2000019994" || got.Status != StatusDraft {
		t.Fatalf("roundtrip mismatch: %+v", got)
	}
	if _, err := repo.Get(context.Background(), uuid.NewString()); err != ErrNotFound {
		t.Fatalf("want ErrNotFound for unknown id, got %v", err)
	}
}
```

- [ ] **Step 2: Run — verify fails to compile**

Run: `go test ./internal/domains/session/ -run TestRepository -v` → FAIL (`NewRepository` undefined).

- [ ] **Step 3: Write `repository.go`**

```go
package session

import (
	"context"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Repository is the Postgres-backed SessionStore (swaps InMemoryStore in prod).
type Repository struct {
	db *pgxpool.Pool
}

// NewRepository constructs a Repository. The pool is required.
func NewRepository(db *pgxpool.Pool) *Repository {
	if db == nil {
		panic("checkout: NewRepository requires a non-nil pool")
	}
	return &Repository{db: db}
}

func (r *Repository) Create(ctx context.Context, s Session) error {
	const q = `
		INSERT INTO checkout_sessions
			(checkout_id, client_order_id, customer_id, basket_id, status, totals_checksum)
		VALUES ($1, $2, $3, $4, $5, $6)`
	_, err := r.db.Exec(ctx, q,
		s.CheckoutID, s.ClientOrderID, s.CustomerID, s.BasketID, string(s.Status), s.TotalsChecksum)
	if err != nil {
		return fmt.Errorf("checkout: insert session: %w", err)
	}
	return nil
}

func (r *Repository) Get(ctx context.Context, checkoutID string) (Session, error) {
	const q = `
		SELECT checkout_id, client_order_id, customer_id, basket_id, status, totals_checksum
		FROM checkout_sessions WHERE checkout_id = $1`
	var s Session
	var status string
	err := r.db.QueryRow(ctx, q, checkoutID).Scan(
		&s.CheckoutID, &s.ClientOrderID, &s.CustomerID, &s.BasketID, &status, &s.TotalsChecksum)
	if errors.Is(err, pgx.ErrNoRows) {
		return Session{}, ErrNotFound
	}
	if err != nil {
		return Session{}, fmt.Errorf("checkout: select session: %w", err)
	}
	s.Status = Status(status)
	return s, nil
}
```

- [ ] **Step 4: Run integration test against a migrated DB**

```bash
export CHECKOUT_TEST_DB_DSN="$CHECKOUT_DB_DSN"   # the migrated local DB from Task 1
go test ./internal/domains/session/ -run TestRepository -v
```
Expected: PASS. (Unit tests still pass: `go test ./internal/domains/session/`.)

- [ ] **Step 5: Commit**

```bash
git add internal/domains/session/repository.go internal/domains/session/repository_test.go
git commit -m "feat(checkout): pgx-backed SessionStore repository (TDD, guarded integration)"
```

---

## Task 4: `/health/ready` checks DB + GET /checkout/{id}

**Files:**
- Modify: `internal/app/container.go`, `internal/app/wire/checkout.go`, `internal/app/app.go`, `api/v1/{openapi.yaml,paths/checkout.yaml}`
- Modify: `internal/domains/session/{handler.go,routes.go,handler_test.go}`

- [ ] **Step 1: Add the OpenAPI path `GET /checkout/{checkout_id}`**

In `api/v1/openapi.yaml` add under `paths`:
```yaml
  /checkout/{checkout_id}:
    $ref: "./paths/checkout.yaml#/GetCheckout"
```
In `api/v1/paths/checkout.yaml` append:
```yaml
GetCheckout:
  get:
    tags: [checkout]
    operationId: getCheckout
    parameters:
      - name: checkout_id
        in: path
        required: true
        schema: { type: string, format: uuid }
    responses:
      "200":
        description: Session
        content:
          application/json:
            schema:
              $ref: "../components/schemas/checkout.yaml#/CheckoutSession"
      "404":
        description: Not found
        content:
          application/json:
            schema:
              $ref: "../components/schemas/common.yaml#/ErrorResponse"
```
Run `make generate && make lint`. Commit nothing yet.

- [ ] **Step 2: Add `Get` handler + route** (handler_test first)

Add to `handler_test.go`:
```go
func TestGet_404_unknown(t *testing.T) {
	h := newTestHandler()
	req := httptest.NewRequest(http.MethodGet, "/api/v1/checkout/"+uuid.NewString(), nil)
	rec := httptest.NewRecorder()
	// route param via chi context:
	rctx := chi.NewRouteContext()
	rctx.URLParams.Add("checkout_id", req.URL.Path[len("/api/v1/checkout/"):])
	req = req.WithContext(context.WithValue(req.Context(), chi.RouteCtxKey, rctx))
	h.Get(rec, req)
	if rec.Code != http.StatusNotFound {
		t.Fatalf("want 404, got %d", rec.Code)
	}
}
```
(imports: `context`, `github.com/go-chi/chi/v5`, `github.com/google/uuid`.)

Run → FAIL (`Handler.Get` undefined).

Add to `handler.go`:
```go
import "github.com/go-chi/chi/v5"

// Get handles GET /api/v1/checkout/{checkout_id}.
func (h *Handler) Get(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "checkout_id")
	sess, err := h.service.GetSession(r.Context(), id)
	if err != nil {
		if errors.Is(err, ErrNotFound) {
			h.errs.JSON(w, http.StatusNotFound, "not_found", "checkout session not found")
			return
		}
		h.errs.Internal(w, "internal", "internal error")
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(toSessionDTO(sess))
}
```
Add to `routes.go` inside the `/checkout` route group:
```go
		rr.Get("/{checkout_id}", deps.Handler.Get)
```
Run → PASS.

- [ ] **Step 3: Wire DB-backed store + ready check**

`internal/app/wire/checkout.go` — change signature to accept the pool:
```go
package wire

import (
	"gj-checkout/internal/domains/session"
	"gj-checkout/internal/platform/config"
	"gj-checkout/internal/platform/httpx"

	"github.com/jackc/pgx/v5/pgxpool"
)

func Checkout(_ config.Config, db *pgxpool.Pool, errs *httpx.Helper) *checkout.Handler {
	store := checkout.NewRepository(db)
	svc := checkout.NewService(store)
	return checkout.NewHandler(svc, errs)
}
```

`internal/app/container.go` — open the pool, pass to wire, hold it for shutdown + health:
```go
// add fields: DB *pgxpool.Pool
// in NewContainer (now returns error):
pool, err := storage.NewPool(ctx, cfg.DB.DSN)
if err != nil { return nil, err }
c.DB = pool
c.HealthHandler = health.NewHandler(health.NewService(cfg.AppName, cfg.Env, func(ctx context.Context) error { return pool.Ping(ctx) }))
c.SessionHandler = wire.Session(cfg, pool, c.ErrorsHelper)
```
> The `health.NewService(name, env, checker)` 3rd arg is the readiness checker (it was `nil` in Plan 1). Pass `pool.Ping`. Confirm the exact checker signature in `internal/platform/health/service.go` and adapt (it may take `func(context.Context) error`). `/health/ready` must return 503 if the checker errors.

`internal/app/app.go` — `NewContainer` now returns `(*Container, error)`; propagate; on shutdown call `c.DB.Close()`.

- [ ] **Step 4: Build + unit tests**

Run: `go build ./... && go test ./internal/domains/session/ ./internal/platform/...`
Expected: PASS (unit; integration skipped without DSN).

- [ ] **Step 5: Commit**

```bash
git add api internal
git commit -m "feat(checkout): GET /checkout/{id} + DB-backed store + /ready DB check"
```

---

## Task 5: End-to-end with Postgres + DoD

- [ ] **Step 1: Migrate + boot against Postgres**

```bash
docker compose -f dev/docker-compose.yml up -d
make migrate-up
CHECKOUT_DB_DSN='postgres://checkout:checkout@127.0.0.1:5544/checkout?sslmode=disable' make run
```

- [ ] **Step 2: Smoke — create, then GET, then restart-persistence**

```bash
ID=$(curl -s -X POST localhost:8080/api/v1/checkout -H 'Content-Type: application/json' \
  -d '{"customer_id":"c1","basket_id":"2000019994"}' | jq -r .checkout_id)
curl -is localhost:8080/api/v1/checkout/$ID | head -1          # 200
# restart service, then:
curl -is localhost:8080/api/v1/checkout/$ID | head -1          # still 200 (persisted)
curl -is localhost:8080/health/ready | head -1                 # 200 (DB up)
```
Stop Postgres → `/health/ready` → 503.

- [ ] **Step 3: Full suite + gates**

Run: `go test ./...` (+ integration with `CHECKOUT_TEST_DB_DSN`), `make generate && make lint && go vet ./...`.

- [ ] **Step 4: Commit + tag**

```bash
git commit -am "test(checkout): e2e persistence green" --allow-empty
git tag v0.0.2-persistence
```

## Definition of Done (Plan 2)
- `make migrate-up` applies `checkout_sessions` (via gj-go-migrate built from sibling); sessions persist across restart.
- `POST /checkout` writes to Postgres; `GET /checkout/{id}` returns it; unknown → 404.
- `/health/ready` 200 when DB up, 503 when down.
- pgx repository integration test passes against a migrated DB; unit tests still green.
- `make generate`/`lint`/`vet`/`build`/`test` green.
