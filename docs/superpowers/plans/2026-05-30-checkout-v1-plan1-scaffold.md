# Checkout v1 — Plan 1: Scaffold (running skeleton) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `checkout` Go service as a running, testable walking-skeleton — boots, serves `/health/{live,ready}` + `/metrics`, and a single end-to-end vertical `POST /api/v1/checkout` (create session) backed by an in-memory stub store — mirroring the `ecom-gateway` standard exactly.

**Architecture:** net/http + chi v5; layout `internal/platform/*` (cross-cutting) + `internal/domains/checkout/*` (bounded context) + `internal/app/{container,app}` + `internal/app/wire`; OpenAPI spec-first, types-only codegen; config from env; `gj-go-logger` + Prometheus. **Stateful additions (pgx/migrations) deferred to Plan 2** — Plan 1 uses an in-memory `SessionStore` behind the port so the vertical is complete without a DB.

**Tech Stack:** Go 1.26.2, `github.com/go-chi/chi/v5`, `github.com/google/uuid`, `github.com/prometheus/client_golang`, `gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger`, `oapi-codegen` (types-only), `redocly` (lint/bundle).

**Reference (read first, copy patterns verbatim):** `platform-new/ecom-gateway/` — its `CLAUDE.md`, `docs/architecture/code-organization-contract.md`, all `internal/platform/*`, `internal/domains/recommendations/*`, `internal/app/*`, `api/v1/*`, `Makefile`, `Dockerfile`. **The `checkout` skeleton is the same shape with the module renamed and a `checkout` domain instead of `recommendations`.**

**Design source:** `docs/superpowers/specs/2026-05-29-checkout-service-design.md` (§2 session model, §3 contract).

**Conventions (from ecom-gateway, mandatory):** one bounded context = one package with `types.go/service.go/handler.go/routes.go` (+`stub.go`,`repository.go`,`boundary_test.go`); consumer-defined ports; composition root in `internal/app`+`wire/`; generated DTO in `<domain>/apiv1/` (never hand-edit); OpenAPI sources in `api/v1/{paths,components/schemas}` → `make generate` (bundle+codegen); config env-only (NO `.env` in repo); `context.Background()` banned in handlers; metrics `path` label = route template; `boundary_test.go` mandatory; commit ONLY in this repo (`platform-new/checkout`), never the workspace root.

**Module name:** `gj-checkout` (mirrors `gj-ecom-gateway`). **AppName:** `checkout`.

---

## File Structure (Plan 1)

```
checkout/
├── go.mod / go.sum                          module gj-checkout, go 1.26.2
├── Makefile                                 tidy/bundle/generate/lint/build/test/run/docker  (copy+adapt ecom-gateway)
├── Dockerfile / .dockerignore               distroless runtime  (copy+adapt ecom-gateway)
├── api/v1/
│   ├── openapi.yaml                         root: info/servers/tags + $ref paths
│   ├── paths/checkout.yaml                  POST /checkout
│   ├── components/schemas/common.yaml       ErrorResponse  (copy from ecom-gateway)
│   ├── components/schemas/checkout.yaml     CreateCheckoutRequest, CheckoutSession
│   ├── oapi-codegen-checkout.yaml           per-domain codegen config
│   └── bundle/openapi.yaml                  GENERATED (committed)
├── cmd/checkout/main.go                     thin entrypoint (≤30 lines)  (copy+adapt)
└── internal/
    ├── app/{app.go, container.go}           composition root  (adapt)
    │   └── wire/checkout.go                 wire.Checkout(cfg, metrics, errs) *checkout.Handler
    ├── platform/{config,transport,httpx,observability,health,reqctx,logger}/   (copy+adapt verbatim)
    └── domains/checkout/
        ├── doc.go                           //go:generate directive
        ├── types.go                         domain CheckoutSession + marker errors + ports
        ├── service.go                       CreateSession orchestration (SessionStore port)
        ├── stub.go                          in-memory SessionStore (Plan 2 swaps for pgx repo)
        ├── handler.go                       HTTP I/O + DTO mapping
        ├── routes.go                        Mount()
        ├── boundary_test.go                 package-boundary guard
        ├── service_test.go / handler_test.go
        └── apiv1/{doc.go, openapi.gen.go}   GENERATED DTO (package apiv1)
```

---

## Task 0: Repo skeleton — module + deps

**Files:**
- Create: `go.mod`
- Verify: `.gitignore` (already present), repo remote = `e-commerce/platform/checkout`

- [ ] **Step 1: Confirm you are in the checkout repo (not the workspace root)**

Run: `cd ~/Projects/GJ-Ecommerce/platform-new/checkout && git remote -v`
Expected: `origin git@gitlab.gloria.aaanet.ru:e-commerce/platform/checkout.git`. If it shows `development-platform`, STOP — you are in the wrong directory.

- [ ] **Step 2: Init go module**

Run:
```bash
go mod init gj-checkout
go get github.com/go-chi/chi/v5@v5.1.0
go get github.com/google/uuid@v1.6.0
go get github.com/prometheus/client_golang@v1.23.2
go get gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger@v1.0.5
```

- [ ] **Step 3: Add local replace for gj-go-logger (dev)**

Append to `go.mod`:
```
replace gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger => ../gj-go-logger
```
(The `gj-go-logger` clone sits at `platform-new/gj-go-logger`, sibling of this repo — same as ecom-gateway.)

- [ ] **Step 4: Verify**

Run: `go mod tidy && go build ./... 2>&1 | head` — Expected: no output (nothing to build yet) or clean.

- [ ] **Step 5: Commit**

```bash
git add go.mod go.sum && git commit -m "chore: init gj-checkout module + base deps"
```

---

## Task 1: Platform layer — copy & adapt from ecom-gateway

The cross-cutting platform packages are **identical to ecom-gateway modulo module rename**. Copy them verbatim, then rename the import path and AppName default. Do NOT re-derive — this is how the standard propagates.

**Files (copy from `../ecom-gateway/internal/platform/<pkg>/` → `internal/platform/<pkg>/`):**
- `config/` (config.go, config_test.go) — then **edit** per Step 2
- `transport/` (server.go, routes.go, middleware.go, middleware_test.go)
- `httpx/` (error.go, error_test.go)
- `observability/` (metrics.go, middleware.go, handler.go, routes.go, metrics_test.go)
- `health/` (handler.go, service.go, routes.go, types.go, health_test.go)
- `reqctx/` (reqctx.go, reqctx_test.go)
- `logger/` (logger.go)

- [ ] **Step 1: Copy platform packages verbatim**

```bash
mkdir -p internal/platform
cp -R ../ecom-gateway/internal/platform/{config,transport,httpx,observability,health,reqctx,logger} internal/platform/
```

- [ ] **Step 2: Rename module path in every copied file**

Run:
```bash
grep -rl 'gj-ecom-gateway' internal/platform | xargs sed -i '' 's#gj-ecom-gateway#gj-checkout#g'
```
(Linux: drop the `''` after `-i`.)

- [ ] **Step 3: Replace `config/config.go` with the checkout-specific config**

Replace `internal/platform/config/config.go` entirely with (drops Recommendations/CatalogCache; adds DB + checkout placeholders — DB used in Plan 2, declared now so config is stable):

```go
package config

import (
	"fmt"
	"net"
	"os"
	"strconv"
	"time"
)

// Config is the resolved runtime configuration for checkout.
type Config struct {
	AppName         string
	Env             string
	HTTP            HTTPConfig
	UpstreamTimeout time.Duration
	DB              DBConfig // used from Plan 2 (Postgres session store)
}

type HTTPConfig struct {
	Host string
	Port string
}

// DBConfig configures the Postgres session store (Plan 2).
type DBConfig struct {
	DSN string // empty in Plan 1 (in-memory store)
}

// Load reads configuration from the environment, applying defaults.
func Load() Config {
	return Config{
		AppName: getEnv("APP_NAME", "checkout"),
		Env:     getEnv("APP_ENV", "local"),
		HTTP: HTTPConfig{
			Host: getEnv("HTTP_HOST", ""),
			Port: getEnv("HTTP_PORT", "8080"),
		},
		UpstreamTimeout: time.Duration(clampInt(getEnvInt("UPSTREAM_TIMEOUT_MS", 800), 50, 10000)) * time.Millisecond,
		DB:              DBConfig{DSN: getEnv("CHECKOUT_DB_DSN", "")},
	}
}

func (c Config) ListenAddr() string {
	if c.HTTP.Host == "" {
		return ":" + c.HTTP.Port
	}
	return net.JoinHostPort(c.HTTP.Host, c.HTTP.Port)
}

// Validate fails fast on impossible runtime configuration.
func (c Config) Validate() error {
	if c.HTTP.Port == "" {
		return fmt.Errorf("config: HTTP_PORT is required")
	}
	return nil
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getEnvInt(key string, fallback int) int {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(v)
	if err != nil {
		return fallback
	}
	return parsed
}

func clampInt(v, min, max int) int {
	if v < min {
		return min
	}
	if v > max {
		return max
	}
	return v
}
```

- [ ] **Step 4: Fix config_test.go**

Open `internal/platform/config/config_test.go` and delete any test asserting on `Recommendations`/`CatalogCache` fields (gone). Keep/adjust tests for `ListenAddr`, default `AppName == "checkout"`, and `Validate`. If unsure, replace the file with two table tests: (a) `Load()` defaults → `AppName=="checkout"`, `Port=="8080"`, `ListenAddr()==":8080"`; (b) `Validate()` returns nil for defaults.

- [ ] **Step 5: Verify platform builds**

Run: `go build ./internal/platform/... 2>&1 | head`
Expected: no errors. If `transport/routes.go` or `transport/server.go` references `recommendations`/`observability`/`health` domains that don't exist yet, leave them — Task 5 rewrites `transport/routes.go`. For now, temporarily comment the `recommendations` import + mount in the copied `transport/routes.go` so it compiles (Task 5 replaces this file).

- [ ] **Step 6: Run platform tests**

Run: `go test ./internal/platform/... 2>&1 | tail`
Expected: PASS (health, httpx, observability, reqctx, config tests).

- [ ] **Step 7: Commit**

```bash
git add internal/platform && git commit -m "feat(platform): port cross-cutting layer from ecom-gateway (config/transport/httpx/observability/health/reqctx/logger)"
```

---

## Task 2: OpenAPI contract — create-session endpoint

**Files:**
- Create: `api/v1/openapi.yaml`, `api/v1/paths/checkout.yaml`, `api/v1/components/schemas/checkout.yaml`, `api/v1/oapi-codegen-checkout.yaml`
- Copy: `api/v1/components/schemas/common.yaml` from ecom-gateway
- Copy+adapt: `Makefile` from ecom-gateway

- [ ] **Step 1: Copy Makefile + common schema + codegen tooling**

```bash
cp ../ecom-gateway/Makefile ./Makefile
cp ../ecom-gateway/.dockerignore ./.dockerignore
cp ../ecom-gateway/Dockerfile ./Dockerfile
mkdir -p api/v1/{paths,components/schemas,bundle}
cp ../ecom-gateway/api/v1/components/schemas/common.yaml api/v1/components/schemas/common.yaml
```
Then in `Makefile` + `Dockerfile`: `sed -i '' 's#ecom-gateway#checkout#g; s#gj-ecom-gateway#gj-checkout#g'` (adapt binary/path names). Open `Makefile` and ensure the codegen target references `oapi-codegen-checkout.yaml` (rename from `-recommendations`).

- [ ] **Step 2: Write `api/v1/openapi.yaml` (root)**

```yaml
openapi: 3.0.3
info:
  title: Checkout API
  version: 1.0.0
  description: Pre-checkout session + commit (walking skeleton).
servers:
  - url: /api/v1
tags:
  - name: checkout
paths:
  /checkout:
    $ref: "./paths/checkout.yaml#/CreateCheckout"
```

- [ ] **Step 3: Write `api/v1/paths/checkout.yaml`**

```yaml
CreateCheckout:
  post:
    tags: [checkout]
    operationId: createCheckout
    summary: Create a checkout session from a basket
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: "../components/schemas/checkout.yaml#/CreateCheckoutRequest"
    responses:
      "201":
        description: Session created
        content:
          application/json:
            schema:
              $ref: "../components/schemas/checkout.yaml#/CheckoutSession"
      "400":
        description: Invalid argument
        content:
          application/json:
            schema:
              $ref: "../components/schemas/common.yaml#/ErrorResponse"
```

- [ ] **Step 4: Write `api/v1/components/schemas/checkout.yaml`** (minimal v1 shape — grows in later plans)

```yaml
CreateCheckoutRequest:
  type: object
  required: [customer_id, basket_id]
  properties:
    customer_id: { type: string }
    basket_id:   { type: string }
CheckoutSession:
  type: object
  required: [checkout_id, client_order_id, customer_id, basket_id, status]
  properties:
    checkout_id:     { type: string, format: uuid }
    client_order_id: { type: string, description: "= basket number" }
    customer_id:     { type: string }
    basket_id:       { type: string }
    status:
      type: string
      enum: [draft, selecting, revalidating, ready, committing, committed, conflict, failed, expired]
    totals_checksum: { type: number, format: double, nullable: true }
```

- [ ] **Step 5: Write `api/v1/oapi-codegen-checkout.yaml`** (mirror ecom-gateway's, change package/output/tags)

```yaml
package: apiv1
output: internal/domains/checkout/apiv1/openapi.gen.go
generate:
  models: true
output-options:
  include-tags:
    - checkout
```

- [ ] **Step 6: Generate + lint**

Run: `make generate && make lint`
Expected: `api/v1/bundle/openapi.yaml` (re)generated; `internal/domains/checkout/apiv1/openapi.gen.go` created with `CreateCheckoutRequest`, `CheckoutSession`, `ErrorResponse`; redocly lint clean. Create `internal/domains/checkout/apiv1/doc.go` with `package apiv1` doc comment if codegen doesn't emit one.

- [ ] **Step 7: Commit**

```bash
git add api Makefile Dockerfile .dockerignore internal/domains/checkout/apiv1
git commit -m "feat(api): checkout v1 contract — POST /checkout + types-only codegen"
```

---

## Task 3: checkout domain — types, ports, stub store (TDD)

**Files:**
- Create: `internal/domains/checkout/{doc.go,types.go,service.go,stub.go,service_test.go}`

- [ ] **Step 1: Write `doc.go`**

```go
// Package checkout is the checkout bounded context: pre-checkout session
// lifecycle, delivery resolution, and order commit. v1 = walking skeleton.
package checkout

//go:generate sh -c "cd ../../../ && make generate"
```

- [ ] **Step 2: Write the failing service test** — `service_test.go`

```go
package checkout

import (
	"context"
	"testing"
)

func TestCreateSession_persistsAndReturnsSession(t *testing.T) {
	store := NewInMemoryStore()
	svc := NewService(store)

	got, err := svc.CreateSession(context.Background(), CreateSessionInput{
		CustomerID: "cust-1",
		BasketID:   "2000019994",
	})
	if err != nil {
		t.Fatalf("CreateSession: %v", err)
	}
	if got.CheckoutID == "" {
		t.Fatal("expected non-empty CheckoutID")
	}
	if got.ClientOrderID != "2000019994" {
		t.Fatalf("client_order_id must equal basket number, got %q", got.ClientOrderID)
	}
	if got.Status != StatusDraft {
		t.Fatalf("new session must be draft, got %q", got.Status)
	}
	// persisted + retrievable
	again, err := store.Get(context.Background(), got.CheckoutID)
	if err != nil {
		t.Fatalf("store.Get: %v", err)
	}
	if again.CheckoutID != got.CheckoutID {
		t.Fatal("stored session mismatch")
	}
}

func TestCreateSession_requiresBasket(t *testing.T) {
	svc := NewService(NewInMemoryStore())
	_, err := svc.CreateSession(context.Background(), CreateSessionInput{CustomerID: "c"})
	if err == nil {
		t.Fatal("expected error when basket_id missing")
	}
}
```

- [ ] **Step 3: Run — verify it fails to compile**

Run: `go test ./internal/domains/checkout/ -run TestCreateSession -v`
Expected: build failure (`NewService`, `NewInMemoryStore`, types undefined).

- [ ] **Step 4: Write `types.go`** (domain model + marker errors + ports)

```go
package checkout

import (
	"context"
	"errors"
)

// Status is the checkout session lifecycle state.
type Status string

const (
	StatusDraft        Status = "draft"
	StatusSelecting    Status = "selecting"
	StatusRevalidating Status = "revalidating"
	StatusReady        Status = "ready"
	StatusCommitting   Status = "committing"
	StatusCommitted    Status = "committed"
	StatusConflict     Status = "conflict"
	StatusFailed       Status = "failed"
	StatusExpired      Status = "expired"
)

// Marker errors (handler maps these to HTTP). ErrInvalidArgument is user-safe.
var (
	ErrInvalidArgument = errors.New("invalid argument")
	ErrNotFound        = errors.New("not found")
)

// Session is the persisted checkout session (domain model). Grows in later plans
// (selection, recipient, address, promo, payment). v1 = identity skeleton.
type Session struct {
	CheckoutID     string
	ClientOrderID  string // = basket number (minted by ENSI baskets; here mirrored from BasketID)
	CustomerID     string
	BasketID       string
	Status         Status
	TotalsChecksum *float64
}

// CreateSessionInput is the input to CreateSession.
type CreateSessionInput struct {
	CustomerID string
	BasketID   string
}

// SessionStore persists checkout sessions. Consumer-defined port; v1 uses an
// in-memory implementation, Plan 2 swaps a pgx-backed repository behind it.
type SessionStore interface {
	Create(ctx context.Context, s Session) error
	Get(ctx context.Context, checkoutID string) (Session, error)
}
```

- [ ] **Step 5: Write `service.go`**

```go
package checkout

import (
	"context"
	"fmt"

	"github.com/google/uuid"
)

// Service orchestrates the checkout session lifecycle.
type Service struct {
	store SessionStore
}

// NewService builds a Service. The store port is required.
func NewService(store SessionStore) *Service {
	if store == nil {
		panic("checkout: NewService requires a non-nil SessionStore")
	}
	return &Service{store: store}
}

// CreateSession opens a new draft checkout session for a basket.
// client_order_id = basket number (idempotency key for OMS / DOC for discounts).
func (s *Service) CreateSession(ctx context.Context, in CreateSessionInput) (Session, error) {
	if in.BasketID == "" {
		return Session{}, fmt.Errorf("%w: basket_id is required", ErrInvalidArgument)
	}
	if in.CustomerID == "" {
		return Session{}, fmt.Errorf("%w: customer_id is required", ErrInvalidArgument)
	}
	sess := Session{
		CheckoutID:    uuid.NewString(),
		ClientOrderID: in.BasketID, // basket# = order#
		CustomerID:    in.CustomerID,
		BasketID:      in.BasketID,
		Status:        StatusDraft,
	}
	if err := s.store.Create(ctx, sess); err != nil {
		return Session{}, fmt.Errorf("create session: %w", err)
	}
	return sess, nil
}

// GetSession returns a session by id.
func (s *Service) GetSession(ctx context.Context, checkoutID string) (Session, error) {
	return s.store.Get(ctx, checkoutID)
}
```

- [ ] **Step 6: Write `stub.go`** (in-memory store; Plan 2 replaces with `repository.go`)

```go
package checkout

import (
	"context"
	"sync"
)

// InMemoryStore is the v1 SessionStore. Plan 2 swaps a pgx repository behind the
// same SessionStore port. Safe for concurrent use.
type InMemoryStore struct {
	mu   sync.RWMutex
	data map[string]Session
}

// NewInMemoryStore constructs an empty in-memory store.
func NewInMemoryStore() *InMemoryStore {
	return &InMemoryStore{data: make(map[string]Session)}
}

func (s *InMemoryStore) Create(_ context.Context, sess Session) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.data[sess.CheckoutID] = sess
	return nil
}

func (s *InMemoryStore) Get(_ context.Context, checkoutID string) (Session, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	sess, ok := s.data[checkoutID]
	if !ok {
		return Session{}, ErrNotFound
	}
	return sess, nil
}
```

- [ ] **Step 7: Run — verify the service test passes**

Run: `go test ./internal/domains/checkout/ -run TestCreateSession -v`
Expected: PASS (both tests).

- [ ] **Step 8: Commit**

```bash
git add internal/domains/checkout/{doc.go,types.go,service.go,stub.go,service_test.go}
git commit -m "feat(checkout): session domain — CreateSession + in-memory SessionStore (TDD)"
```

---

## Task 4: checkout handler + routes + DTO mapping (TDD)

**Files:**
- Create: `internal/domains/checkout/{handler.go,routes.go,handler_test.go}`

- [ ] **Step 1: Write the failing handler test** — `handler_test.go`

```go
package checkout

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"gj-checkout/internal/platform/httpx"
)

func newTestHandler() *Handler {
	return NewHandler(NewService(NewInMemoryStore()), httpx.NewHelper())
}

func TestCreate_201(t *testing.T) {
	h := newTestHandler()
	req := httptest.NewRequest(http.MethodPost, "/api/v1/checkout",
		strings.NewReader(`{"customer_id":"c1","basket_id":"2000019994"}`))
	rec := httptest.NewRecorder()

	h.Create(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("want 201, got %d: %s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"client_order_id":"2000019994"`) {
		t.Fatalf("body missing client_order_id: %s", rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"status":"draft"`) {
		t.Fatalf("body missing draft status: %s", rec.Body.String())
	}
}

func TestCreate_400_missingBasket(t *testing.T) {
	h := newTestHandler()
	req := httptest.NewRequest(http.MethodPost, "/api/v1/checkout",
		strings.NewReader(`{"customer_id":"c1"}`))
	rec := httptest.NewRecorder()

	h.Create(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("want 400, got %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), `"error":"invalid_argument"`) {
		t.Fatalf("want invalid_argument envelope, got %s", rec.Body.String())
	}
}
```

- [ ] **Step 2: Run — verify it fails**

Run: `go test ./internal/domains/checkout/ -run TestCreate -v`
Expected: build failure (`NewHandler`, `Handler.Create` undefined).

- [ ] **Step 3: Write `handler.go`**

```go
package checkout

import (
	"encoding/json"
	"errors"
	"net/http"

	"gj-checkout/internal/domains/checkout/apiv1"
	"gj-checkout/internal/platform/httpx"
)

// Handler is the HTTP edge for the checkout bounded context.
type Handler struct {
	service *Service
	errs    *httpx.Helper
}

// NewHandler constructs a Handler.
func NewHandler(service *Service, errs *httpx.Helper) *Handler {
	return &Handler{service: service, errs: errs}
}

// Create handles POST /api/v1/checkout.
func (h *Handler) Create(w http.ResponseWriter, r *http.Request) {
	var req apiv1.CreateCheckoutRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.errs.BadRequest(w, "invalid_argument", "malformed JSON body")
		return
	}

	sess, err := h.service.CreateSession(r.Context(), CreateSessionInput{
		CustomerID: req.CustomerId,
		BasketID:   req.BasketId,
	})
	if err != nil {
		switch {
		case errors.Is(err, ErrInvalidArgument):
			h.errs.BadRequest(w, "invalid_argument", err.Error())
		default:
			h.errs.Internal(w, "internal", "internal error")
		}
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	_ = json.NewEncoder(w).Encode(toSessionDTO(sess))
}

// toSessionDTO maps the domain session to the generated API DTO.
func toSessionDTO(s Session) apiv1.CheckoutSession {
	return apiv1.CheckoutSession{
		CheckoutId:     s.CheckoutID,
		ClientOrderId:  s.ClientOrderID,
		CustomerId:     s.CustomerID,
		BasketId:       s.BasketID,
		Status:         apiv1.CheckoutSessionStatus(s.Status),
		TotalsChecksum: s.TotalsChecksum,
	}
}
```

> If `oapi-codegen` named the request fields `CustomerId`/`BasketId` differently (e.g. `CustomerID`), open `internal/domains/checkout/apiv1/openapi.gen.go` and match the exact generated field names. Do NOT edit the generated file — adapt the mapping code.

- [ ] **Step 4: Write `routes.go`**

```go
package checkout

import "github.com/go-chi/chi/v5"

// Deps carries dependencies required to mount checkout routes.
type Deps struct{ Handler *Handler }

// Mount registers checkout routes. Caller scopes them under /api/v1.
func Mount(r chi.Router, deps Deps) {
	r.Route("/checkout", func(rr chi.Router) {
		rr.Post("/", deps.Handler.Create)
	})
}
```

- [ ] **Step 5: Run — verify handler tests pass**

Run: `go test ./internal/domains/checkout/ -run TestCreate -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add internal/domains/checkout/{handler.go,routes.go,handler_test.go}
git commit -m "feat(checkout): POST /checkout handler + routes + DTO mapping (TDD)"
```

---

## Task 5: Wiring — container, wire builder, transport routes

**Files:**
- Create: `internal/app/wire/checkout.go`
- Modify: `internal/app/container.go`, `internal/app/app.go` (copy+adapt from ecom-gateway), `internal/platform/transport/routes.go`

- [ ] **Step 1: Copy `internal/app/app.go` from ecom-gateway and rename module**

```bash
mkdir -p internal/app/wire
cp ../ecom-gateway/internal/app/app.go internal/app/app.go
sed -i '' 's#gj-ecom-gateway#gj-checkout#g' internal/app/app.go
```
(If `app.go` builds the transport `Dependencies` from `recommendations`, you'll fix that reference in Step 4 alongside `container.go`.)

- [ ] **Step 2: Write `internal/app/wire/checkout.go`**

```go
package wire

import (
	"gj-checkout/internal/domains/checkout"
	"gj-checkout/internal/platform/config"
	"gj-checkout/internal/platform/httpx"
)

// Checkout builds the checkout domain handler with its v1 in-memory store.
// Plan 2 swaps the store for a pgx repository here (signature gains the pool).
func Checkout(_ config.Config, errs *httpx.Helper) *checkout.Handler {
	store := checkout.NewInMemoryStore()
	svc := checkout.NewService(store)
	return checkout.NewHandler(svc, errs)
}
```

- [ ] **Step 3: Write `internal/app/container.go`** (adapt ecom-gateway's; replace recommendations with checkout)

```go
package app

import (
	"gj-checkout/internal/app/wire"
	"gj-checkout/internal/domains/checkout"
	"gj-checkout/internal/platform/config"
	"gj-checkout/internal/platform/health"
	"gj-checkout/internal/platform/httpx"
	"gj-checkout/internal/platform/observability"
)

// Container holds constructed dependencies, assembled once at startup.
type Container struct {
	Config config.Config

	Metrics       *observability.Metrics
	HealthHandler *health.Handler
	ErrorsHelper  *httpx.Helper

	CheckoutHandler *checkout.Handler
}

// NewContainer assembles all dependencies.
func NewContainer(cfg config.Config) *Container {
	c := &Container{Config: cfg}
	c.Metrics = observability.NewMetrics()
	c.ErrorsHelper = httpx.NewHelper()
	c.HealthHandler = health.NewHandler(health.NewService(cfg.AppName, cfg.Env, nil))
	c.CheckoutHandler = wire.Checkout(cfg, c.ErrorsHelper)
	return c
}
```

- [ ] **Step 4: Rewrite `internal/platform/transport/routes.go`** (replace the recommendations mount)

```go
package transport

import (
	"gj-checkout/internal/domains/checkout"
	"gj-checkout/internal/platform/health"
	"gj-checkout/internal/platform/observability"

	"github.com/go-chi/chi/v5"
)

// Dependencies holds per-domain Deps consumed by registerRoutes.
type Dependencies struct {
	Health        health.Deps
	Observability observability.Deps
	Checkout      checkout.Deps
}

// registerRoutes mounts observability, then health, then the versioned API.
func registerRoutes(r chi.Router, deps Dependencies) {
	observability.Mount(r, deps.Observability)
	health.Mount(r, deps.Health)

	r.Route("/api/v1", func(rr chi.Router) {
		checkout.Mount(rr, deps.Checkout)
	})
}
```

- [ ] **Step 5: Ensure `app.go` builds transport `Dependencies` from the container**

Open `internal/app/app.go`. Where it constructs `transport.Dependencies`, set:
```go
deps := transport.Dependencies{
	Health:        health.Deps{Handler: c.HealthHandler},
	Observability: observability.Deps{Metrics: c.Metrics},
	Checkout:      checkout.Deps{Handler: c.CheckoutHandler},
}
```
Match the exact `Deps` field shapes used by ecom-gateway's `app.go` (e.g. `observability.Deps` may carry `Metrics` + middleware). Add the `checkout` import. Remove any `recommendations` references.

- [ ] **Step 6: Write `cmd/checkout/main.go`**

```go
package main

import (
	"gj-checkout/internal/app"

	gjlogger "gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger"
)

func main() {
	application, err := app.New()
	if err != nil {
		gjlogger.Logger().Fatal().Err(err).Msg("bootstrap failed")
	}
	if err := application.Run(); err != nil {
		gjlogger.Logger().Fatal().Err(err).Msg("server failed")
	}
}
```

- [ ] **Step 7: Build the whole tree**

Run: `go build ./... 2>&1 | head`
Expected: no errors. Fix any remaining `recommendations` references or `Deps` field mismatches by reading the corresponding ecom-gateway file.

- [ ] **Step 8: Commit**

```bash
git add internal/app cmd internal/platform/transport/routes.go
git commit -m "feat(app): wire checkout domain into container + transport"
```

---

## Task 6: boundary test + end-to-end verification + DoD

**Files:**
- Create: `internal/domains/checkout/boundary_test.go`

- [ ] **Step 1: Write `boundary_test.go`** (adapt ecom-gateway's recommendations boundary test)

```go
package checkout_test

import (
	"strings"
	"testing"

	"golang.org/x/tools/go/packages"
)

// TestDomainBoundary asserts the checkout domain imports neither the composition
// root nor sibling domains nor most platform internals (httpx is allowed).
func TestDomainBoundary(t *testing.T) {
	forbidden := []string{
		"gj-checkout/internal/app",
		"gj-checkout/internal/app/wire",
		"gj-checkout/internal/platform/config",
		"gj-checkout/internal/platform/health",
		"gj-checkout/internal/platform/observability",
		"gj-checkout/internal/platform/transport",
		"gj-checkout/internal/platform/logger",
	}
	cfg := &packages.Config{Mode: packages.NeedImports | packages.NeedName}
	pkgs, err := packages.Load(cfg, "gj-checkout/internal/domains/checkout")
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	for _, p := range pkgs {
		for imp := range p.Imports {
			for _, f := range forbidden {
				if imp == f || strings.HasPrefix(imp, "gj-checkout/internal/domains/") && imp != "gj-checkout/internal/domains/checkout" && !strings.HasPrefix(imp, "gj-checkout/internal/domains/checkout/") {
					t.Errorf("checkout must not import %s", imp)
				}
			}
		}
	}
}
```
> Open ecom-gateway's `internal/domains/recommendations/boundary_test.go` and mirror its exact mechanism/allow-list (it may use a simpler approach without `go/packages`). Prefer matching the established pattern over the snippet above if they differ. Run `go get golang.org/x/tools/go/packages` only if that approach is used.

- [ ] **Step 2: Run the full test suite**

Run: `go test ./... 2>&1 | tail -20`
Expected: PASS across platform + domain + boundary.

- [ ] **Step 3: Generate + lint gates**

Run: `make generate && make lint && go vet ./...`
Expected: no drift in `bundle/openapi.yaml` or `openapi.gen.go` (git diff clean after generate); redocly lint clean; vet clean.

- [ ] **Step 4: Boot + smoke the service**

Run (terminal A): `make run` (or `go run ./cmd/checkout`)
Run (terminal B):
```bash
curl -is localhost:8080/health/live | head -1          # 200
curl -is localhost:8080/health/ready | head -1         # 200
curl -is localhost:8080/metrics | head -1              # 200
curl -is -X POST localhost:8080/api/v1/checkout \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"c1","basket_id":"2000019994"}' | head -20
```
Expected: create returns `201` + JSON with `checkout_id` (uuid), `client_order_id":"2000019994"`, `status":"draft"`. Missing basket → `400 {"error":"invalid_argument",...}`.

- [ ] **Step 5: Docker build**

Run: `make docker` (context = parent dir, per Dockerfile)
Expected: image builds.

- [ ] **Step 6: Commit + tag DoD**

```bash
git add internal/domains/checkout/boundary_test.go
git commit -m "test(checkout): domain boundary guard + e2e skeleton green"
git tag v0.0.1-skeleton
```

---

## Definition of Done (Plan 1)

- `go build ./...`, `go vet ./...`, `go test ./...` green.
- `make generate` produces no git diff (bundle + `openapi.gen.go` committed & current); `make lint` clean.
- Service boots; `/health/live`, `/health/ready`, `/metrics` → 200.
- `POST /api/v1/checkout` → `201` stub session (uuid id, `client_order_id`=basket#, `status`=draft); missing basket → `400` envelope.
- `boundary_test.go` enforces domain isolation.
- Docker image builds.
- Layout/conventions identical to ecom-gateway (verified against its `code-organization-contract.md`).

## Next plans (roadmap)
- **Plan 2 — Persistence:** `internal/platform/storage` (pgx pool) + `internal/domains/checkout/repository.go` (Postgres `SessionStore`) + migrations via `gj-go-migrate` + `GET /checkout/{id}`; `/health/ready` checks DB; swap `wire.Checkout` from in-memory to repo.
- **Plan 3 — Resolver (§2c):** `internal/domains/checkout` komplektaciya resolver + `DeliverySource` port + stub adapter built from `fixtures/oms/*.json`; `GET /checkout/{id}/delivery-options`, `PATCH /checkout/{id}/delivery-method`; table-driven invariant tests (coverage «X из N», 3 OMS shapes, drift, partial availability).
- **Plan 4 — Commit saga:** honest status + `409` conflict semantics + idempotency on stub ports (`OrderSink`, `PricingSource`, `DiscountSource`); remaining mutations (recipient/address/promo/payment-method); e2e create→select→commit on stubs.
