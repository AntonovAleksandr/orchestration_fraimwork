# Checkout v1 — Plan 4: Capability domains + Commit Saga (domain-map edition) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the v1 walking skeleton — add the remaining session mutations as three thin capability domains (`recipient`, `payment`, `pricing`) plus a durable, **honest, idempotent** commit saga in `session`, all on deterministic stub ports.

**Architecture:** Per the canonical domain-map (`platform-new/checkout/docs/architecture/domain-map.md`). `session` is the single consistency root: it owns the aggregate, persistence, and the **commit saga** (`internal/domains/session/service.go`). `recipient`/`payment`/`pricing` are stateless capability domains — each owns its `PATCH` endpoint and writes the user's decision back through a narrow consumer-defined gateway into `session` (mirrors how `delivery` was built in Plan 3). Saga-time ports (`CartValidator`, `DeliveryReconciler`, `Pricer`, `OrderSink`, `DiscountSink`, `PaymentLinker`) are consumer-defined **in `session`** and implemented by deterministic stubs in `internal/adapters/commit/`. Domains never import each other; `internal/app/wire` is the only place that bridges them (boundary tests enforce this).

**Tech Stack:** Go 1.26, `net/http` + `chi/v5`, pgx v5, `oapi-codegen` types-only (per-domain `include-tags`), redocly bundle, `gj-go-migrate` migrations, money = **`int64` kopecks** (never float). All HTTP is honest: `201`/`409`/`400`/`404`/`502` — **never `200 {success:false}`**.

**Prereq:** Plans 1–3 complete and pushed (tags `v0.0.1-skeleton` … `v0.0.3-resolver`, HEAD `91cbc1d`). Local dev Postgres up (`platform-new/checkout/dev/docker-compose.yml`, port 5544). `make setup` already run on the machine (private Go modules resolve).

**Design refs:** spec §2 (session model), §2a (store-intent saga; spend-on-create; reserve window accepted), §2b (one order + spill), §3 (granular API surface), §4 (commit flow), §5 (clean OMS payload — drop qty-explosion/side-channel/hardcoded-package), §6 (honest status, 409, idempotency, **reconcile by attributes not by full id hash**). Domain-map: "Plan 4 = `payment` + `pricing` + `recipient` + сага в `session`".

---

## Scope notes (read before starting)

- **All upstreams are STUBBED in v1.** No real OMS/ENSI/discount calls. Phase 2 replaces the stub ports with real adapters over the published clients (`starfish-oms`, `baskets`, `offers`, `discount` — all `v0.1.1`).
- **Deliberate v1 deviations from the domain-map's phase-2 wiring (documented, not accidental):**
  - `recipient` and `payment` carry **no upstream source port in v1** — they are pure write-through (record a validated decision). Phase 2 adds `CustomerSource`→ENSI and `PaymentSource`→OMS pay-service. (YAGNI: no dead ports.)
  - `pricing` **does** need a quoter to recompute totals on a promo change, so it gets a `PriceQuoter` stub port now.
  - The six **saga-time stub ports live together** in one package `internal/adapters/commit/` rather than pre-split into `adapters/{oms,pricing,cart}`. They are deterministic stubs; phase 2 splits them into per-domain real adapters (`OrderSink`→`adapters/oms`, `Pricer`/`DiscountSink`→`adapters/pricing`, `DeliveryReconciler`→ the `delivery` domain re-resolving, etc.). Keeping them together avoids four near-empty packages for v1.
- **Out of v1 scope (note, don't build):** `PATCH /identity` (anon phone+SMS — belongs to the auth contour, deferred); a separate `PATCH /address` endpoint (address is an optional sub-object the `recipient` domain may carry later — not needed for the stub commit, which only requires recipient name+phone); real spill (documented no-op).
- **Stub-coupling invariant (important):** `pricing.StubQuoter` (used by `PATCH /promo`) and `commit.StubPricer` (used by the commit re-quote) **must compute identical totals** for the same session state, or a promo→commit flow would 409 on `totals_changed`. Both use the same constants (items subtotal `539600`, promo discount `50000`, bonus `25`). A comment in each cross-references the other. Phase 2 collapses both onto the real pricing adapter.

---

## File Structure (Plan 4)

```
checkout/
├── api/v1/
│   ├── openapi.yaml                         MODIFY  + tags recipient/payment/pricing; + 4 path $refs
│   ├── paths/
│   │   ├── checkout.yaml                     MODIFY  + Commit (POST /checkout/{id}/commit, tag session)
│   │   ├── recipient.yaml                     CREATE  PATCH /checkout/{id}/recipient
│   │   ├── payment.yaml                       CREATE  PATCH /checkout/{id}/payment-method
│   │   └── pricing.yaml                       CREATE  PATCH /checkout/{id}/promo
│   ├── components/schemas/
│   │   ├── checkout.yaml                      MODIFY  + CommitResult
│   │   ├── recipient.yaml                     CREATE  SetRecipientRequest, Recipient, AppliedRecipient
│   │   ├── payment.yaml                       CREATE  SetPaymentMethodRequest, AppliedPayment
│   │   └── pricing.yaml                       CREATE  SetPromoRequest, Totals, AppliedPromo
│   ├── oapi-codegen-recipient.yaml            CREATE  include-tags: [recipient]
│   ├── oapi-codegen-payment.yaml              CREATE  include-tags: [payment]
│   └── oapi-codegen-pricing.yaml              CREATE  include-tags: [pricing]
├── migrations/
│   ├── 0003_session_details.up.sql            CREATE  ADD COLUMN details jsonb
│   └── 0003_session_details.down.sql          CREATE  DROP COLUMN details
└── internal/
    ├── domains/
    │   ├── session/
    │   │   ├── types.go        MODIFY  + Recipient/PromoIntent/PaymentMethod; + Totals/OrderRef/CommitResult/CartValidation; + ConflictError/ErrUpstream; + saga ports; + store methods
    │   │   ├── service.go      MODIFY  + ApplyRecipient/ApplyPaymentMethod/ApplyPromo; + NewServiceFull + Commit (saga)
    │   │   ├── service_test.go MODIFY  + apply + commit tests
    │   │   ├── repository.go   MODIFY  + UpdateDetails/UpdateStatus; Get reads details
    │   │   ├── repository_test.go MODIFY + details round-trip
    │   │   ├── stub.go         MODIFY  + UpdateDetails/UpdateStatus on InMemoryStore
    │   │   ├── handler.go      MODIFY  + Commit handler + toCommitDTO (honest status)
    │   │   ├── handler_test.go MODIFY  + commit 201/409/400 handler tests
    │   │   └── routes.go       MODIFY  + POST /{checkout_id}/commit
    │   ├── recipient/  CREATE  types/service/handler/routes/doc + boundary_test + apiv1/
    │   ├── payment/    CREATE  types/service/handler/routes/doc + boundary_test + apiv1/
    │   └── pricing/    CREATE  types/service/handler/routes/stub/doc + boundary_test + apiv1/
    ├── adapters/commit/
    │   └── commit_stubs.go     CREATE  StubCartValidator/StubReconciler/StubPricer/StubDiscountSink/StubOrderSink/StubPaymentLinker
    └── app/
        ├── container.go        MODIFY  + Recipient/Payment/Pricing handlers
        ├── app.go              MODIFY  + new handlers into transport.Dependencies
        └── wire/
            ├── session.go      MODIFY  SessionService → NewServiceFull(commit stubs)
            ├── recipient.go    CREATE  recipientGateway + Recipient builder
            ├── payment.go      CREATE  paymentGateway + Payment builder
            └── pricing.go      CREATE  pricingGateway + Pricing builder
    └── platform/transport/
        ├── routes.go           MODIFY  + recipient/payment/pricing Deps + Mount
        └── e2e_test.go         MODIFY  buildDeps → NewServiceFull; + full create→…→commit e2e
```

---

## Task 1: Session aggregate — detail fields, persistence, apply methods

Adds the persisted recipient/promo/payment fields to the `session` aggregate and the three apply methods the capability domains will call through their gateways. **No endpoints yet** (those land in Tasks 2–4). Pure domain + persistence + TDD.

**Files:**
- Create: `migrations/0003_session_details.up.sql`, `migrations/0003_session_details.down.sql`
- Modify: `internal/domains/session/types.go`, `service.go`, `repository.go`, `stub.go`, `service_test.go`, `repository_test.go`

- [ ] **Step 1: Migration 0003**

Create `migrations/0003_session_details.up.sql`:

```sql
ALTER TABLE checkout_sessions ADD COLUMN IF NOT EXISTS details jsonb NULL;
```

Create `migrations/0003_session_details.down.sql`:

```sql
ALTER TABLE checkout_sessions DROP COLUMN IF EXISTS details;
```

- [ ] **Step 2: Domain types** — append to `internal/domains/session/types.go`

```go
// Recipient is the order recipient (under shipping). v1: name + phone.
// Authed prefill from ENSI customers arrives in phase 2 (recipient domain).
type Recipient struct {
	FirstName string `json:"first_name"`
	LastName  string `json:"last_name"`
	Phone     string `json:"phone"`
}

// PromoIntent is the user's promo/bonus INTENT (not applied truth — re-quoted on
// commit). BurnBonus is authed-only; v1 records the flag without bonus math.
type PromoIntent struct {
	PromoCode string `json:"promo_code,omitempty"`
	BurnBonus bool   `json:"burn_bonus,omitempty"`
}

// PaymentMethod is the chosen payment method (SBP/card = prepay via YooKassa
// widget; on_receipt = pay on delivery).
type PaymentMethod string

const (
	PaymentSBP        PaymentMethod = "sbp"
	PaymentCardOnline PaymentMethod = "card_online"
	PaymentOnReceipt  PaymentMethod = "on_receipt"
)
```

Add the three fields to the `Session` struct (they are persisted in the `details` JSONB column, kept out of the wire JSON like `Cart`/`Selection`):

```go
	Recipient     *Recipient    `json:"-"`
	Promo         *PromoIntent  `json:"-"`
	PaymentMethod PaymentMethod `json:"-"`
```

Extend the `SessionStore` port with two methods (place inside the existing `interface` block):

```go
	// UpdateDetails persists recipient/promo/payment_method (+ totals_checksum)
	// from the given session and bumps updated_at. Returns ErrNotFound when absent.
	UpdateDetails(ctx context.Context, checkoutID string, s Session) error
	// UpdateStatus advances the lifecycle status and bumps updated_at.
	// Returns ErrNotFound when absent.
	UpdateStatus(ctx context.Context, checkoutID string, st Status) error
```

- [ ] **Step 3: Apply methods** — append to `internal/domains/session/service.go`

```go
// ApplyRecipient records the chosen recipient on the aggregate. Validation of
// required fields lives in the recipient capability domain; session trusts the
// decision and persists it. Returns ErrNotFound when the session is absent.
func (s *Service) ApplyRecipient(ctx context.Context, checkoutID string, r Recipient) (Session, error) {
	sess, err := s.store.Get(ctx, checkoutID)
	if err != nil {
		return Session{}, err
	}
	sess.Recipient = &r
	if err := s.store.UpdateDetails(ctx, checkoutID, sess); err != nil {
		return Session{}, fmt.Errorf("apply recipient: %w", err)
	}
	return sess, nil
}

// ApplyPaymentMethod records the chosen payment method on the aggregate.
func (s *Service) ApplyPaymentMethod(ctx context.Context, checkoutID string, m PaymentMethod) (Session, error) {
	sess, err := s.store.Get(ctx, checkoutID)
	if err != nil {
		return Session{}, err
	}
	sess.PaymentMethod = m
	if err := s.store.UpdateDetails(ctx, checkoutID, sess); err != nil {
		return Session{}, fmt.Errorf("apply payment method: %w", err)
	}
	return sess, nil
}

// ApplyPromo records the promo intent and the re-quoted totals checksum (int64
// kopecks). The pricing domain computes the checksum; session persists it so the
// commit two-phase-truth check can compare against it.
func (s *Service) ApplyPromo(ctx context.Context, checkoutID string, p PromoIntent, totalsChecksum int64) (Session, error) {
	sess, err := s.store.Get(ctx, checkoutID)
	if err != nil {
		return Session{}, err
	}
	sess.Promo = &p
	sess.TotalsChecksum = &totalsChecksum
	if err := s.store.UpdateDetails(ctx, checkoutID, sess); err != nil {
		return Session{}, fmt.Errorf("apply promo: %w", err)
	}
	return sess, nil
}
```

- [ ] **Step 4: InMemoryStore** — append to `internal/domains/session/stub.go`

```go
func (s *InMemoryStore) UpdateDetails(_ context.Context, checkoutID string, sess Session) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	cur, ok := s.data[checkoutID]
	if !ok {
		return ErrNotFound
	}
	cur.Recipient = sess.Recipient
	cur.Promo = sess.Promo
	cur.PaymentMethod = sess.PaymentMethod
	cur.TotalsChecksum = sess.TotalsChecksum
	s.data[checkoutID] = cur
	return nil
}

func (s *InMemoryStore) UpdateStatus(_ context.Context, checkoutID string, st Status) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	cur, ok := s.data[checkoutID]
	if !ok {
		return ErrNotFound
	}
	cur.Status = st
	s.data[checkoutID] = cur
	return nil
}
```

- [ ] **Step 5: Repository** — modify `internal/domains/session/repository.go`

Add a private serialization helper type near the top of the file:

```go
// detailsJSON is the shape persisted in the `details` JSONB column.
type detailsJSON struct {
	Recipient     *Recipient    `json:"recipient,omitempty"`
	Promo         *PromoIntent  `json:"promo,omitempty"`
	PaymentMethod PaymentMethod `json:"payment_method,omitempty"`
}
```

In `Get`, extend the `SELECT` to read `details` and decode it. Change the query and scan:

```go
	const q = `
		SELECT checkout_id, client_order_id, customer_id, basket_id, status, totals_checksum, selection, cart_snapshot, details
		FROM checkout_sessions WHERE checkout_id = $1`
	var s Session
	var status string
	var selJSON, cartJSON, detJSON []byte
	err := r.db.QueryRow(ctx, q, checkoutID).Scan(
		&s.CheckoutID, &s.ClientOrderID, &s.CustomerID, &s.BasketID, &status, &s.TotalsChecksum, &selJSON, &cartJSON, &detJSON)
```

After the existing `cart_snapshot` unmarshal block, add:

```go
	if len(detJSON) > 0 {
		var d detailsJSON
		if err := json.Unmarshal(detJSON, &d); err != nil {
			return Session{}, fmt.Errorf("checkout: unmarshal details: %w", err)
		}
		s.Recipient = d.Recipient
		s.Promo = d.Promo
		s.PaymentMethod = d.PaymentMethod
	}
```

Append the two new repository methods:

```go
// UpdateDetails persists recipient/promo/payment_method (JSONB) + totals_checksum
// and bumps updated_at. Returns ErrNotFound when the session is absent.
func (r *Repository) UpdateDetails(ctx context.Context, checkoutID string, s Session) error {
	b, err := json.Marshal(detailsJSON{Recipient: s.Recipient, Promo: s.Promo, PaymentMethod: s.PaymentMethod})
	if err != nil {
		return fmt.Errorf("checkout: marshal details: %w", err)
	}
	ct, err := r.db.Exec(ctx,
		`UPDATE checkout_sessions SET details=$2, totals_checksum=$3, updated_at=now() WHERE checkout_id=$1`,
		checkoutID, b, s.TotalsChecksum)
	if err != nil {
		return fmt.Errorf("checkout: update details: %w", err)
	}
	if ct.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}

// UpdateStatus advances the lifecycle status and bumps updated_at.
func (r *Repository) UpdateStatus(ctx context.Context, checkoutID string, st Status) error {
	ct, err := r.db.Exec(ctx,
		`UPDATE checkout_sessions SET status=$2, updated_at=now() WHERE checkout_id=$1`,
		checkoutID, string(st))
	if err != nil {
		return fmt.Errorf("checkout: update status: %w", err)
	}
	if ct.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}
```

- [ ] **Step 6: Failing tests** — append to `internal/domains/session/service_test.go`

```go
func TestApplyRecipient_persists(t *testing.T) {
	store := NewInMemoryStore()
	svc := NewService(store)
	sess, _ := svc.CreateSession(context.Background(), CreateSessionInput{CustomerID: "c", BasketID: "b1"})

	got, err := svc.ApplyRecipient(context.Background(), sess.CheckoutID, Recipient{FirstName: "Ann", LastName: "Lee", Phone: "+79001112233"})
	if err != nil {
		t.Fatalf("ApplyRecipient: %v", err)
	}
	if got.Recipient == nil || got.Recipient.FirstName != "Ann" {
		t.Fatal("recipient not set on returned session")
	}
	reloaded, _ := store.Get(context.Background(), sess.CheckoutID)
	if reloaded.Recipient == nil || reloaded.Recipient.Phone != "+79001112233" {
		t.Fatal("recipient not persisted")
	}
}

func TestApplyPaymentMethod_persists(t *testing.T) {
	store := NewInMemoryStore()
	svc := NewService(store)
	sess, _ := svc.CreateSession(context.Background(), CreateSessionInput{CustomerID: "c", BasketID: "b2"})

	got, err := svc.ApplyPaymentMethod(context.Background(), sess.CheckoutID, PaymentSBP)
	if err != nil {
		t.Fatalf("ApplyPaymentMethod: %v", err)
	}
	if got.PaymentMethod != PaymentSBP {
		t.Fatalf("want sbp, got %q", got.PaymentMethod)
	}
	reloaded, _ := store.Get(context.Background(), sess.CheckoutID)
	if reloaded.PaymentMethod != PaymentSBP {
		t.Fatal("payment method not persisted")
	}
}

func TestApplyPromo_setsChecksum(t *testing.T) {
	store := NewInMemoryStore()
	svc := NewService(store)
	sess, _ := svc.CreateSession(context.Background(), CreateSessionInput{CustomerID: "c", BasketID: "b3"})

	got, err := svc.ApplyPromo(context.Background(), sess.CheckoutID, PromoIntent{PromoCode: "SALE"}, 489600)
	if err != nil {
		t.Fatalf("ApplyPromo: %v", err)
	}
	if got.TotalsChecksum == nil || *got.TotalsChecksum != 489600 {
		t.Fatal("checksum not set on returned session")
	}
	reloaded, _ := store.Get(context.Background(), sess.CheckoutID)
	if reloaded.Promo == nil || reloaded.Promo.PromoCode != "SALE" || reloaded.TotalsChecksum == nil || *reloaded.TotalsChecksum != 489600 {
		t.Fatal("promo/checksum not persisted")
	}
}

func TestApplyRecipient_notFound(t *testing.T) {
	svc := NewService(NewInMemoryStore())
	_, err := svc.ApplyRecipient(context.Background(), "missing", Recipient{FirstName: "A", LastName: "B", Phone: "p"})
	if !errors.Is(err, ErrNotFound) {
		t.Fatalf("want ErrNotFound, got %v", err)
	}
}
```

- [ ] **Step 7: Run → FAIL, then verify it compiles+passes**

Run: `go test ./internal/domains/session/ -run 'TestApply' -v`
Expected first run: FAIL (apply methods / store methods undefined). After Steps 2–5 are in, re-run → PASS.

- [ ] **Step 8: Repository details round-trip test** — append to `internal/domains/session/repository_test.go`

Mirror the existing repository tests' inline DSN/skip/pool pattern (the file has no shared helper — each test opens its own pool). Add (`context`, `os`, `storage`, `uuid` are already imported in `repository_test.go`):

```go
func TestRepository_detailsRoundTrip(t *testing.T) {
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
	ctx := context.Background()

	sess := Session{
		CheckoutID:    uuid.NewString(),
		ClientOrderID: "9001",
		CustomerID:    "c",
		BasketID:      "9001",
		Status:        StatusDraft,
	}
	if err := repo.Create(ctx, sess); err != nil {
		t.Fatalf("Create: %v", err)
	}
	sess.Recipient = &Recipient{FirstName: "Ann", LastName: "Lee", Phone: "+7900"}
	sess.PaymentMethod = PaymentCardOnline
	cs := int64(489600)
	sess.TotalsChecksum = &cs
	if err := repo.UpdateDetails(ctx, sess.CheckoutID, sess); err != nil {
		t.Fatalf("UpdateDetails: %v", err)
	}
	if err := repo.UpdateStatus(ctx, sess.CheckoutID, StatusSelecting); err != nil {
		t.Fatalf("UpdateStatus: %v", err)
	}

	got, err := repo.Get(ctx, sess.CheckoutID)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.Recipient == nil || got.Recipient.LastName != "Lee" {
		t.Fatal("recipient did not round-trip")
	}
	if got.PaymentMethod != PaymentCardOnline {
		t.Fatalf("payment method: want card_online, got %q", got.PaymentMethod)
	}
	if got.Status != StatusSelecting || got.TotalsChecksum == nil || *got.TotalsChecksum != 489600 {
		t.Fatal("status/checksum did not round-trip")
	}
}
```


- [ ] **Step 9: Run gates**

Run (offline, no DB needed for the in-memory tests):
```bash
go build ./... && go vet ./... && go test ./internal/domains/session/ -run 'TestApply' -count=1
```
Expected: PASS. Then with DB up + migrated (Step 10), run the round-trip:
```bash
make migrate-up
CHECKOUT_TEST_DB_DSN="postgres://checkout:checkout@127.0.0.1:5544/checkout?sslmode=disable" go test ./internal/domains/session/ -run 'TestRepository' -count=1
```
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add migrations internal/domains/session
git commit -m "feat(session): recipient/promo/payment fields + details persistence + apply methods (migration 0003)"
```

---

## Task 2: `recipient` capability domain

A thin capability domain owning `PATCH /checkout/{id}/recipient`. Validates the recipient and writes it through a narrow gateway into `session`. Mirrors the `delivery` domain pattern (own handler/service/routes + consumer-defined gateway; writes go through `session`).

**Files:**
- Create: `internal/domains/recipient/{types.go,service.go,handler.go,routes.go,doc.go,boundary_test.go}`
- Create: `api/v1/components/schemas/recipient.yaml`, `api/v1/paths/recipient.yaml`, `api/v1/oapi-codegen-recipient.yaml`
- Modify: `api/v1/openapi.yaml`, `internal/app/wire/recipient.go` (create), `internal/app/container.go`, `internal/app/app.go`, `internal/platform/transport/routes.go`

- [ ] **Step 1: OpenAPI — schemas** — create `api/v1/components/schemas/recipient.yaml`

```yaml
SetRecipientRequest:
  type: object
  required: [first_name, last_name, phone]
  properties:
    first_name: { type: string }
    last_name:  { type: string }
    phone:      { type: string }
Recipient:
  type: object
  required: [first_name, last_name, phone]
  properties:
    first_name: { type: string }
    last_name:  { type: string }
    phone:      { type: string }
AppliedRecipient:
  type: object
  required: [checkout_id, status, recipient]
  properties:
    checkout_id: { type: string, format: uuid }
    status:      { type: string }
    recipient:   { $ref: "#/Recipient" }
```

- [ ] **Step 2: OpenAPI — path** — create `api/v1/paths/recipient.yaml`

```yaml
SetRecipient:
  patch:
    tags: [recipient]
    operationId: setRecipient
    summary: Set the order recipient
    security: []
    parameters:
      - name: checkout_id
        in: path
        required: true
        schema: { type: string, format: uuid }
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: "../components/schemas/recipient.yaml#/SetRecipientRequest"
    responses:
      "200":
        description: Recipient applied
        content:
          application/json:
            schema:
              $ref: "../components/schemas/recipient.yaml#/AppliedRecipient"
      "400": { description: Invalid argument, content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } } }
      "404": { description: Not found, content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } } }
```

- [ ] **Step 3: OpenAPI — register tag + path** — modify `api/v1/openapi.yaml`

Under `tags:` add:
```yaml
  - name: recipient
    description: Order recipient — name + phone (authed prefill in phase 2).
```
Under `paths:` add:
```yaml
  /checkout/{checkout_id}/recipient:
    $ref: "./paths/recipient.yaml#/SetRecipient"
```

- [ ] **Step 4: Codegen config** — create `api/v1/oapi-codegen-recipient.yaml`

```yaml
package: apiv1
generate:
  models: true
output: apiv1/openapi.gen.go
output-options:
  skip-prune: false
  include-tags:
    - recipient
```

- [ ] **Step 5: Domain types** — create `internal/domains/recipient/types.go`

```go
package recipient

import (
	"context"
	"errors"
)

// Marker errors (handler maps these to HTTP). The wire bridge translates
// session.ErrNotFound → recipient.ErrNotFound so recipient never imports session.
var (
	ErrInvalidArgument = errors.New("invalid argument")
	ErrNotFound        = errors.New("not found")
)

// Recipient is the order recipient decision.
type Recipient struct {
	FirstName string
	LastName  string
	Phone     string
}

// Applied is what PATCH /recipient returns (domain-owned; NOT the full session).
type Applied struct {
	CheckoutID string
	Status     string
	Recipient  Recipient
}

// Gateway is recipient's consumer-defined port into the session aggregate.
// Implemented by the wire layer over *session.Service. recipient never imports session.
type Gateway interface {
	ApplyRecipient(ctx context.Context, checkoutID string, r Recipient) (Applied, error)
}
```

- [ ] **Step 6: Domain service** — create `internal/domains/recipient/service.go`

```go
package recipient

import (
	"context"
	"fmt"
	"strings"
)

// Service validates a recipient and applies it to the session through the gateway.
// Stateless capability — session stays the single consistency root.
type Service struct {
	gw Gateway
}

// NewService builds a Service; the gateway port is required.
func NewService(gw Gateway) *Service {
	if gw == nil {
		panic("recipient: NewService requires a non-nil Gateway")
	}
	return &Service{gw: gw}
}

// SetRecipient validates required fields and applies the recipient.
func (s *Service) SetRecipient(ctx context.Context, checkoutID string, r Recipient) (Applied, error) {
	if strings.TrimSpace(r.FirstName) == "" || strings.TrimSpace(r.LastName) == "" || strings.TrimSpace(r.Phone) == "" {
		return Applied{}, fmt.Errorf("%w: first_name, last_name and phone are required", ErrInvalidArgument)
	}
	return s.gw.ApplyRecipient(ctx, checkoutID, r)
}
```

- [ ] **Step 7: Domain doc + generate directive** — create `internal/domains/recipient/doc.go`

```go
// Package recipient is the recipient capability domain: it owns the
// PATCH /checkout/{id}/recipient endpoint, validates the recipient, and writes
// the decision to the session aggregate through the Gateway port (session is the
// only consistency root). v1 is pure write-through; a CustomerSource port for
// authed prefill from ENSI customers arrives in phase 2.
package recipient

//go:generate oapi-codegen --config ../../../api/v1/oapi-codegen-recipient.yaml ../../../api/v1/bundle/openapi.yaml
```

- [ ] **Step 8: Generate DTOs**

Run: `make generate`
Expected: creates `internal/domains/recipient/apiv1/openapi.gen.go` with `SetRecipientRequest`, `Recipient`, `AppliedRecipient`, `SetRecipientJSONRequestBody`. No errors; `make lint` clean.

- [ ] **Step 9: Handler** — create `internal/domains/recipient/handler.go`

```go
package recipient

import (
	"encoding/json"
	"errors"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"gj-checkout/internal/domains/recipient/apiv1"
	"gj-checkout/internal/platform/httpx"
)

// Handler is the HTTP edge for the recipient domain.
type Handler struct {
	service *Service
	errs    *httpx.Helper
}

// NewHandler constructs a Handler.
func NewHandler(service *Service, errs *httpx.Helper) *Handler {
	return &Handler{service: service, errs: errs}
}

// SetRecipient handles PATCH /api/v1/checkout/{checkout_id}/recipient.
func (h *Handler) SetRecipient(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "checkout_id")
	var body apiv1.SetRecipientRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		h.errs.BadRequest(w, "invalid_argument", "malformed JSON body")
		return
	}
	applied, err := h.service.SetRecipient(r.Context(), id, Recipient{
		FirstName: body.FirstName, LastName: body.LastName, Phone: body.Phone,
	})
	if err != nil {
		switch {
		case errors.Is(err, ErrNotFound):
			h.errs.JSON(w, http.StatusNotFound, "not_found", "checkout session not found")
		case errors.Is(err, ErrInvalidArgument):
			h.errs.BadRequest(w, "invalid_argument", err.Error())
		default:
			h.errs.Internal(w, "internal", "internal error")
		}
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(apiv1.AppliedRecipient{
		CheckoutId: uuid.MustParse(applied.CheckoutID),
		Status:     applied.Status,
		Recipient: apiv1.Recipient{
			FirstName: applied.Recipient.FirstName,
			LastName:  applied.Recipient.LastName,
			Phone:     applied.Recipient.Phone,
		},
	})
}
```

- [ ] **Step 10: Routes** — create `internal/domains/recipient/routes.go`

```go
package recipient

import "github.com/go-chi/chi/v5"

// Deps carries dependencies required to mount recipient routes.
type Deps struct{ Handler *Handler }

// Mount registers recipient routes under the checkout resource. Caller scopes
// them under /api/v1. Explicit full path (no subrouter) to avoid shadowing the
// session GET /checkout/{id} route — same rule as the delivery domain.
func Mount(r chi.Router, deps Deps) {
	r.Patch("/checkout/{checkout_id}/recipient", deps.Handler.SetRecipient)
}
```

- [ ] **Step 11: Boundary test** — create `internal/domains/recipient/boundary_test.go`

Copy `internal/domains/session/boundary_test.go` verbatim, then change the package clause to `package recipient` and the `self` constant to:

```go
	const self = "gj-checkout/internal/domains/recipient"
```

(The `forbiddenPrefixes` list stays identical — it already forbids `internal/app`, `internal/domains`, `internal/adapters`, and the wired-by-root platform packages.)

- [ ] **Step 12: Wire bridge** — create `internal/app/wire/recipient.go`

```go
package wire

import (
	"context"
	"errors"

	"gj-checkout/internal/domains/recipient"
	"gj-checkout/internal/domains/session"
	"gj-checkout/internal/platform/httpx"
)

// recipientGateway implements recipient.Gateway over *session.Service. It maps
// types across the boundary and translates session.ErrNotFound →
// recipient.ErrNotFound. This is the only place importing both domains.
type recipientGateway struct{ svc *session.Service }

var _ recipient.Gateway = (*recipientGateway)(nil)

func (g *recipientGateway) ApplyRecipient(ctx context.Context, checkoutID string, r recipient.Recipient) (recipient.Applied, error) {
	s, err := g.svc.ApplyRecipient(ctx, checkoutID, session.Recipient{
		FirstName: r.FirstName, LastName: r.LastName, Phone: r.Phone,
	})
	if err != nil {
		if errors.Is(err, session.ErrNotFound) {
			return recipient.Applied{}, recipient.ErrNotFound
		}
		return recipient.Applied{}, err
	}
	return recipient.Applied{CheckoutID: s.CheckoutID, Status: string(s.Status), Recipient: r}, nil
}

// Recipient builds the recipient handler over the shared session service.
func Recipient(svc *session.Service, errs *httpx.Helper) *recipient.Handler {
	return recipient.NewHandler(recipient.NewService(&recipientGateway{svc: svc}), errs)
}
```

- [ ] **Step 13: Container + app + transport wiring** — modify three files

In `internal/app/container.go`: add `RecipientHandler *recipient.Handler` to the `Container` struct, import `gj-checkout/internal/domains/recipient`, and after the delivery line add:
```go
	c.RecipientHandler = wire.Recipient(sessionSvc, c.ErrorsHelper)
```

In `internal/platform/transport/routes.go`: import `gj-checkout/internal/domains/recipient`, add `Recipient recipient.Deps` to `Dependencies`, and inside the `/api/v1` group add `recipient.Mount(rr, deps.Recipient)` (before `session.Mount`).

In `internal/app/app.go`: import `gj-checkout/internal/domains/recipient` and add to the `transport.Dependencies` literal:
```go
		Recipient: recipient.Deps{Handler: container.RecipientHandler},
```

- [ ] **Step 14: Verify + commit**

Run:
```bash
make generate && make lint && go build ./... && go vet ./... && go test ./...
```
Expected: all green (boundary test for recipient passes; existing delivery e2e still passes).

```bash
git add api internal
git commit -m "feat(recipient): capability domain — PATCH /checkout/{id}/recipient (write-through to session)"
```

---

## Task 3: `payment` capability domain

Owns `PATCH /checkout/{id}/payment-method`. Validates the method enum and writes it through a gateway into `session`. Same shape as `recipient`.

**Files:**
- Create: `internal/domains/payment/{types.go,service.go,handler.go,routes.go,doc.go,boundary_test.go}`
- Create: `api/v1/components/schemas/payment.yaml`, `api/v1/paths/payment.yaml`, `api/v1/oapi-codegen-payment.yaml`
- Modify: `api/v1/openapi.yaml`, `internal/app/wire/payment.go` (create), `internal/app/container.go`, `internal/app/app.go`, `internal/platform/transport/routes.go`

- [ ] **Step 1: OpenAPI — schemas** — create `api/v1/components/schemas/payment.yaml`

```yaml
SetPaymentMethodRequest:
  type: object
  required: [type]
  properties:
    type:
      type: string
      enum: [sbp, card_online, on_receipt]
AppliedPayment:
  type: object
  required: [checkout_id, status, payment_method]
  properties:
    checkout_id:    { type: string, format: uuid }
    status:         { type: string }
    payment_method:
      type: string
      enum: [sbp, card_online, on_receipt]
```

- [ ] **Step 2: OpenAPI — path** — create `api/v1/paths/payment.yaml`

```yaml
SetPaymentMethod:
  patch:
    tags: [payment]
    operationId: setPaymentMethod
    summary: Set the payment method
    security: []
    parameters:
      - name: checkout_id
        in: path
        required: true
        schema: { type: string, format: uuid }
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: "../components/schemas/payment.yaml#/SetPaymentMethodRequest"
    responses:
      "200":
        description: Payment method applied
        content:
          application/json:
            schema:
              $ref: "../components/schemas/payment.yaml#/AppliedPayment"
      "400": { description: Invalid argument, content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } } }
      "404": { description: Not found, content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } } }
```

- [ ] **Step 3: Register tag + path** — modify `api/v1/openapi.yaml`

Under `tags:`:
```yaml
  - name: payment
    description: Payment method — SBP / card online / on receipt.
```
Under `paths:`:
```yaml
  /checkout/{checkout_id}/payment-method:
    $ref: "./paths/payment.yaml#/SetPaymentMethod"
```

- [ ] **Step 4: Codegen config** — create `api/v1/oapi-codegen-payment.yaml`

```yaml
package: apiv1
generate:
  models: true
output: apiv1/openapi.gen.go
output-options:
  skip-prune: false
  include-tags:
    - payment
```

- [ ] **Step 5: Domain types** — create `internal/domains/payment/types.go`

```go
package payment

import (
	"context"
	"errors"
)

var (
	ErrInvalidArgument = errors.New("invalid argument")
	ErrNotFound        = errors.New("not found")
)

// Method is the chosen payment method (mirrors session.PaymentMethod; decoupled
// so domains do not share types).
type Method string

const (
	MethodSBP        Method = "sbp"
	MethodCardOnline Method = "card_online"
	MethodOnReceipt  Method = "on_receipt"
)

// Applied is what PATCH /payment-method returns (domain-owned).
type Applied struct {
	CheckoutID string
	Status     string
	Method     Method
}

// Gateway is payment's consumer-defined port into the session aggregate.
type Gateway interface {
	ApplyPaymentMethod(ctx context.Context, checkoutID string, m Method) (Applied, error)
}
```

- [ ] **Step 6: Domain service** — create `internal/domains/payment/service.go`

```go
package payment

import (
	"context"
	"fmt"
)

// Service validates the payment method and applies it through the gateway.
type Service struct {
	gw Gateway
}

// NewService builds a Service; the gateway port is required.
func NewService(gw Gateway) *Service {
	if gw == nil {
		panic("payment: NewService requires a non-nil Gateway")
	}
	return &Service{gw: gw}
}

// SetPaymentMethod validates the method enum and applies it.
func (s *Service) SetPaymentMethod(ctx context.Context, checkoutID string, m Method) (Applied, error) {
	if !validMethod(m) {
		return Applied{}, fmt.Errorf("%w: unknown payment method %q", ErrInvalidArgument, m)
	}
	return s.gw.ApplyPaymentMethod(ctx, checkoutID, m)
}

func validMethod(m Method) bool {
	switch m {
	case MethodSBP, MethodCardOnline, MethodOnReceipt:
		return true
	default:
		return false
	}
}
```

- [ ] **Step 7: Domain doc** — create `internal/domains/payment/doc.go`

```go
// Package payment is the payment capability domain: it owns the
// PATCH /checkout/{id}/payment-method endpoint, validates the method enum, and
// writes the decision to the session aggregate through the Gateway port. v1 is
// pure write-through; a PaymentSource port (→ OMS pay-service for acquirers /
// payment-link) arrives in phase 2 — see the session PaymentLinker saga port.
package payment

//go:generate oapi-codegen --config ../../../api/v1/oapi-codegen-payment.yaml ../../../api/v1/bundle/openapi.yaml
```

- [ ] **Step 8: Generate**

Run: `make generate`
Expected: creates `internal/domains/payment/apiv1/openapi.gen.go` with `SetPaymentMethodRequest`, `AppliedPayment` (+ a `SetPaymentMethodRequestType` enum type for the `type` field). No errors.

- [ ] **Step 9: Handler** — create `internal/domains/payment/handler.go`

```go
package payment

import (
	"encoding/json"
	"errors"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"gj-checkout/internal/domains/payment/apiv1"
	"gj-checkout/internal/platform/httpx"
)

// Handler is the HTTP edge for the payment domain.
type Handler struct {
	service *Service
	errs    *httpx.Helper
}

// NewHandler constructs a Handler.
func NewHandler(service *Service, errs *httpx.Helper) *Handler {
	return &Handler{service: service, errs: errs}
}

// SetPaymentMethod handles PATCH /api/v1/checkout/{checkout_id}/payment-method.
func (h *Handler) SetPaymentMethod(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "checkout_id")
	var body apiv1.SetPaymentMethodRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		h.errs.BadRequest(w, "invalid_argument", "malformed JSON body")
		return
	}
	applied, err := h.service.SetPaymentMethod(r.Context(), id, Method(body.Type))
	if err != nil {
		switch {
		case errors.Is(err, ErrNotFound):
			h.errs.JSON(w, http.StatusNotFound, "not_found", "checkout session not found")
		case errors.Is(err, ErrInvalidArgument):
			h.errs.BadRequest(w, "invalid_argument", err.Error())
		default:
			h.errs.Internal(w, "internal", "internal error")
		}
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(apiv1.AppliedPayment{
		CheckoutId:    uuid.MustParse(applied.CheckoutID),
		Status:        applied.Status,
		PaymentMethod: apiv1.AppliedPaymentPaymentMethod(applied.Method),
	})
}
```

> Note: the generated enum type names (`apiv1.SetPaymentMethodRequest.Type` and `apiv1.AppliedPaymentPaymentMethod`) follow oapi-codegen's convention. If the generated names differ, match what `make generate` produced — `body.Type` is a string-backed enum, cast with `Method(string(body.Type))` if needed.

- [ ] **Step 10: Routes** — create `internal/domains/payment/routes.go`

```go
package payment

import "github.com/go-chi/chi/v5"

// Deps carries dependencies required to mount payment routes.
type Deps struct{ Handler *Handler }

// Mount registers payment routes (explicit full path; no subrouter).
func Mount(r chi.Router, deps Deps) {
	r.Patch("/checkout/{checkout_id}/payment-method", deps.Handler.SetPaymentMethod)
}
```

- [ ] **Step 11: Boundary test** — create `internal/domains/payment/boundary_test.go`

Copy `internal/domains/session/boundary_test.go`, change package clause to `package payment` and:
```go
	const self = "gj-checkout/internal/domains/payment"
```

- [ ] **Step 12: Wire bridge** — create `internal/app/wire/payment.go`

```go
package wire

import (
	"context"
	"errors"

	"gj-checkout/internal/domains/payment"
	"gj-checkout/internal/domains/session"
	"gj-checkout/internal/platform/httpx"
)

type paymentGateway struct{ svc *session.Service }

var _ payment.Gateway = (*paymentGateway)(nil)

func (g *paymentGateway) ApplyPaymentMethod(ctx context.Context, checkoutID string, m payment.Method) (payment.Applied, error) {
	s, err := g.svc.ApplyPaymentMethod(ctx, checkoutID, session.PaymentMethod(m))
	if err != nil {
		if errors.Is(err, session.ErrNotFound) {
			return payment.Applied{}, payment.ErrNotFound
		}
		return payment.Applied{}, err
	}
	return payment.Applied{CheckoutID: s.CheckoutID, Status: string(s.Status), Method: m}, nil
}

// Payment builds the payment handler over the shared session service.
func Payment(svc *session.Service, errs *httpx.Helper) *payment.Handler {
	return payment.NewHandler(payment.NewService(&paymentGateway{svc: svc}), errs)
}
```

- [ ] **Step 13: Container + app + transport wiring**

In `container.go`: add `PaymentHandler *payment.Handler`, import payment, add `c.PaymentHandler = wire.Payment(sessionSvc, c.ErrorsHelper)`.
In `transport/routes.go`: import payment, add `Payment payment.Deps` to `Dependencies`, add `payment.Mount(rr, deps.Payment)` in the group.
In `app.go`: import payment, add `Payment: payment.Deps{Handler: container.PaymentHandler},`.

- [ ] **Step 14: Verify + commit**

```bash
make generate && make lint && go build ./... && go vet ./... && go test ./...
git add api internal
git commit -m "feat(payment): capability domain — PATCH /checkout/{id}/payment-method (enum-validated write-through)"
```

---

## Task 4: `pricing` capability domain

Owns `PATCH /checkout/{id}/promo`. Records the promo intent, re-quotes totals via a `PriceQuoter` stub port, and writes promo + new checksum into `session`. This is the one capability domain that needs an upstream-ish port in v1 (it computes money).

**Files:**
- Create: `internal/domains/pricing/{types.go,service.go,handler.go,routes.go,stub.go,doc.go,boundary_test.go,service_test.go}`
- Create: `api/v1/components/schemas/pricing.yaml`, `api/v1/paths/pricing.yaml`, `api/v1/oapi-codegen-pricing.yaml`
- Modify: `api/v1/openapi.yaml`, `internal/app/wire/pricing.go` (create), `internal/app/container.go`, `internal/app/app.go`, `internal/platform/transport/routes.go`

- [ ] **Step 1: OpenAPI — schemas** — create `api/v1/components/schemas/pricing.yaml`

```yaml
SetPromoRequest:
  type: object
  properties:
    promo_code: { type: string }
    burn_bonus: { type: boolean }
Totals:
  type: object
  required: [total_kopecks, delivery_cost_kopecks, discount_kopecks, bonus_accrued]
  properties:
    total_kopecks:         { type: integer, format: int64, description: "итог в копейках" }
    delivery_cost_kopecks: { type: integer, format: int64 }
    discount_kopecks:      { type: integer, format: int64 }
    bonus_accrued:         { type: integer, format: int64, description: "начисляемые бонусы (баллы, не деньги)" }
AppliedPromo:
  type: object
  required: [checkout_id, status, totals]
  properties:
    checkout_id: { type: string, format: uuid }
    status:      { type: string }
    promo_code:  { type: string, nullable: true }
    totals:      { $ref: "#/Totals" }
```

- [ ] **Step 2: OpenAPI — path** — create `api/v1/paths/pricing.yaml`

```yaml
SetPromo:
  patch:
    tags: [pricing]
    operationId: setPromo
    summary: Set/clear the promo code or bonus-burn intent (re-quotes totals)
    security: []
    parameters:
      - name: checkout_id
        in: path
        required: true
        schema: { type: string, format: uuid }
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: "../components/schemas/pricing.yaml#/SetPromoRequest"
    responses:
      "200":
        description: Promo applied, totals re-quoted
        content:
          application/json:
            schema:
              $ref: "../components/schemas/pricing.yaml#/AppliedPromo"
      "400": { description: Invalid argument, content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } } }
      "404": { description: Not found, content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } } }
```

- [ ] **Step 3: Register tag + path** — modify `api/v1/openapi.yaml`

Under `tags:`:
```yaml
  - name: pricing
    description: Pricing — promo/bonus intent + re-quoted totals (int64 kopecks).
```
Under `paths:`:
```yaml
  /checkout/{checkout_id}/promo:
    $ref: "./paths/pricing.yaml#/SetPromo"
```

- [ ] **Step 4: Codegen config** — create `api/v1/oapi-codegen-pricing.yaml`

```yaml
package: apiv1
generate:
  models: true
output: apiv1/openapi.gen.go
output-options:
  skip-prune: false
  include-tags:
    - pricing
```

- [ ] **Step 5: Domain types** — create `internal/domains/pricing/types.go`

```go
package pricing

import (
	"context"
	"errors"
)

var (
	ErrInvalidArgument = errors.New("invalid argument")
	ErrNotFound        = errors.New("not found")
)

// PromoIntent is the user's promo/bonus intent (decoupled from session's type).
type PromoIntent struct {
	PromoCode string
	BurnBonus bool
}

// Totals are the re-quoted money figures (int64 kopecks; bonus_accrued is points).
type Totals struct {
	TotalKopecks        int64
	DeliveryCostKopecks int64
	DiscountKopecks     int64
	BonusAccrued        int64
}

// Applied is what PATCH /promo returns (domain-owned): the new totals + status.
type Applied struct {
	CheckoutID string
	Status     string
	PromoCode  string
	Totals     Totals
}

// CheckoutRef is the slice of session state pricing needs to re-quote.
type CheckoutRef struct {
	CheckoutID          string
	DeliveryCostKopecks int64
}

// PriceQuoter re-derives order totals for a cart + delivery cost + promo intent.
// Consumer-defined port; v1 stub returns deterministic figures, phase 2 calls
// ENSI offers + the discount server (re-quote by Good-set).
type PriceQuoter interface {
	Quote(ctx context.Context, deliveryCostKopecks int64, promo PromoIntent) (Totals, error)
}

// Gateway is pricing's consumer-defined port into the session aggregate.
type Gateway interface {
	Lookup(ctx context.Context, checkoutID string) (CheckoutRef, error)
	ApplyPromo(ctx context.Context, checkoutID string, p PromoIntent, t Totals) (Applied, error)
}
```

- [ ] **Step 6: Stub quoter** — create `internal/domains/pricing/stub.go`

```go
package pricing

import "context"

// Stub pricing constants. These MUST stay in sync with
// internal/adapters/commit.StubPricer (the commit re-quote): a promo set here
// then a commit there must produce the SAME total, or commit would 409 on
// totals_changed. Phase 2 collapses both onto the real pricing adapter.
const (
	stubItemsSubtotalKopecks = int64(539600) // ≈ 5396 ₽
	stubPromoDiscountKopecks = int64(50000)  // ≈ 500 ₽ flat, when a promo code is present
	stubBonusAccrued         = int64(25)
)

// StubQuoter is the v1 PriceQuoter: deterministic totals derived from the
// delivery cost and whether a promo code is present.
type StubQuoter struct{}

var _ PriceQuoter = StubQuoter{}

func (StubQuoter) Quote(_ context.Context, deliveryCostKopecks int64, promo PromoIntent) (Totals, error) {
	var discount int64
	if promo.PromoCode != "" {
		discount = stubPromoDiscountKopecks
	}
	return Totals{
		TotalKopecks:        stubItemsSubtotalKopecks + deliveryCostKopecks - discount,
		DeliveryCostKopecks: deliveryCostKopecks,
		DiscountKopecks:     discount,
		BonusAccrued:        stubBonusAccrued,
	}, nil
}
```

- [ ] **Step 7: Domain service + failing test (TDD)** — create `internal/domains/pricing/service.go` and `service_test.go`

`service.go`:

```go
package pricing

import "context"

// Service re-quotes totals on a promo change and applies promo + checksum to the
// session through the gateway. Stateless capability.
type Service struct {
	quoter PriceQuoter
	gw     Gateway
}

// NewService builds a Service; both ports are required.
func NewService(quoter PriceQuoter, gw Gateway) *Service {
	if quoter == nil || gw == nil {
		panic("pricing: NewService requires non-nil PriceQuoter and Gateway")
	}
	return &Service{quoter: quoter, gw: gw}
}

// SetPromo records the promo intent, re-quotes totals (using the session's current
// delivery cost), and persists promo + the new checksum via the gateway.
func (s *Service) SetPromo(ctx context.Context, checkoutID string, p PromoIntent) (Applied, error) {
	ref, err := s.gw.Lookup(ctx, checkoutID)
	if err != nil {
		return Applied{}, err
	}
	totals, err := s.quoter.Quote(ctx, ref.DeliveryCostKopecks, p)
	if err != nil {
		return Applied{}, err
	}
	return s.gw.ApplyPromo(ctx, checkoutID, p, totals)
}
```

`service_test.go` (local fakes — no cross-domain import):

```go
package pricing

import (
	"context"
	"errors"
	"testing"
)

type fakeGateway struct {
	deliveryCost int64
	lookupErr    error
	gotPromo     PromoIntent
	gotTotals    Totals
}

func (g *fakeGateway) Lookup(_ context.Context, id string) (CheckoutRef, error) {
	if g.lookupErr != nil {
		return CheckoutRef{}, g.lookupErr
	}
	return CheckoutRef{CheckoutID: id, DeliveryCostKopecks: g.deliveryCost}, nil
}

func (g *fakeGateway) ApplyPromo(_ context.Context, id string, p PromoIntent, t Totals) (Applied, error) {
	g.gotPromo, g.gotTotals = p, t
	return Applied{CheckoutID: id, Status: "selecting", PromoCode: p.PromoCode, Totals: t}, nil
}

func TestSetPromo_reQuotesWithDiscount(t *testing.T) {
	gw := &fakeGateway{deliveryCost: 29900}
	svc := NewService(StubQuoter{}, gw)

	applied, err := svc.SetPromo(context.Background(), "co-1", PromoIntent{PromoCode: "SALE"})
	if err != nil {
		t.Fatalf("SetPromo: %v", err)
	}
	// 539600 + 29900 - 50000 = 519500
	if applied.Totals.TotalKopecks != 519500 {
		t.Fatalf("want total 519500, got %d", applied.Totals.TotalKopecks)
	}
	if applied.Totals.DiscountKopecks != 50000 {
		t.Fatalf("want discount 50000, got %d", applied.Totals.DiscountKopecks)
	}
}

func TestSetPromo_noCode_noDiscount(t *testing.T) {
	gw := &fakeGateway{deliveryCost: 0}
	svc := NewService(StubQuoter{}, gw)
	applied, err := svc.SetPromo(context.Background(), "co-2", PromoIntent{})
	if err != nil {
		t.Fatalf("SetPromo: %v", err)
	}
	if applied.Totals.TotalKopecks != 539600 || applied.Totals.DiscountKopecks != 0 {
		t.Fatalf("unexpected totals: %+v", applied.Totals)
	}
}

func TestSetPromo_notFound(t *testing.T) {
	gw := &fakeGateway{lookupErr: ErrNotFound}
	svc := NewService(StubQuoter{}, gw)
	_, err := svc.SetPromo(context.Background(), "missing", PromoIntent{})
	if !errors.Is(err, ErrNotFound) {
		t.Fatalf("want ErrNotFound, got %v", err)
	}
}
```

Run: `go test ./internal/domains/pricing/ -v` → PASS after service.go is in place.

- [ ] **Step 8: Domain doc** — create `internal/domains/pricing/doc.go`

```go
// Package pricing is the pricing capability domain: it owns the
// PATCH /checkout/{id}/promo endpoint, records the promo/bonus intent, re-quotes
// order totals (int64 kopecks) via the PriceQuoter port, and writes promo + the
// new totals_checksum to the session aggregate through the Gateway port. v1 uses
// a deterministic StubQuoter; phase 2 wires offers + the discount server.
package pricing

//go:generate oapi-codegen --config ../../../api/v1/oapi-codegen-pricing.yaml ../../../api/v1/bundle/openapi.yaml
```

- [ ] **Step 9: Generate**

Run: `make generate`
Expected: creates `internal/domains/pricing/apiv1/openapi.gen.go` with `SetPromoRequest`, `Totals`, `AppliedPromo`.

- [ ] **Step 10: Handler** — create `internal/domains/pricing/handler.go`

```go
package pricing

import (
	"encoding/json"
	"errors"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"gj-checkout/internal/domains/pricing/apiv1"
	"gj-checkout/internal/platform/httpx"
)

// Handler is the HTTP edge for the pricing domain.
type Handler struct {
	service *Service
	errs    *httpx.Helper
}

// NewHandler constructs a Handler.
func NewHandler(service *Service, errs *httpx.Helper) *Handler {
	return &Handler{service: service, errs: errs}
}

// SetPromo handles PATCH /api/v1/checkout/{checkout_id}/promo.
func (h *Handler) SetPromo(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "checkout_id")
	var body apiv1.SetPromoRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		h.errs.BadRequest(w, "invalid_argument", "malformed JSON body")
		return
	}
	var promo PromoIntent
	if body.PromoCode != nil {
		promo.PromoCode = *body.PromoCode
	}
	if body.BurnBonus != nil {
		promo.BurnBonus = *body.BurnBonus
	}
	applied, err := h.service.SetPromo(r.Context(), id, promo)
	if err != nil {
		switch {
		case errors.Is(err, ErrNotFound):
			h.errs.JSON(w, http.StatusNotFound, "not_found", "checkout session not found")
		case errors.Is(err, ErrInvalidArgument):
			h.errs.BadRequest(w, "invalid_argument", err.Error())
		default:
			h.errs.Internal(w, "internal", "internal error")
		}
		return
	}
	dto := apiv1.AppliedPromo{
		CheckoutId: uuid.MustParse(applied.CheckoutID),
		Status:     applied.Status,
		Totals: apiv1.Totals{
			TotalKopecks:        applied.Totals.TotalKopecks,
			DeliveryCostKopecks: applied.Totals.DeliveryCostKopecks,
			DiscountKopecks:     applied.Totals.DiscountKopecks,
			BonusAccrued:        applied.Totals.BonusAccrued,
		},
	}
	if applied.PromoCode != "" {
		pc := applied.PromoCode
		dto.PromoCode = &pc
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(dto)
}
```

- [ ] **Step 11: Routes** — create `internal/domains/pricing/routes.go`

```go
package pricing

import "github.com/go-chi/chi/v5"

// Deps carries dependencies required to mount pricing routes.
type Deps struct{ Handler *Handler }

// Mount registers pricing routes (explicit full path; no subrouter).
func Mount(r chi.Router, deps Deps) {
	r.Patch("/checkout/{checkout_id}/promo", deps.Handler.SetPromo)
}
```

- [ ] **Step 12: Boundary test** — create `internal/domains/pricing/boundary_test.go`

Copy `internal/domains/session/boundary_test.go`, change package clause to `package pricing` and:
```go
	const self = "gj-checkout/internal/domains/pricing"
```

- [ ] **Step 13: Wire bridge** — create `internal/app/wire/pricing.go`

```go
package wire

import (
	"context"
	"errors"

	"gj-checkout/internal/domains/pricing"
	"gj-checkout/internal/domains/session"
	"gj-checkout/internal/platform/httpx"
)

type pricingGateway struct{ svc *session.Service }

var _ pricing.Gateway = (*pricingGateway)(nil)

func (g *pricingGateway) Lookup(ctx context.Context, checkoutID string) (pricing.CheckoutRef, error) {
	s, err := g.svc.GetSession(ctx, checkoutID)
	if err != nil {
		if errors.Is(err, session.ErrNotFound) {
			return pricing.CheckoutRef{}, pricing.ErrNotFound
		}
		return pricing.CheckoutRef{}, err
	}
	var deliv int64
	if s.Selection != nil {
		deliv = s.Selection.DeliveryCostKopecks
	}
	return pricing.CheckoutRef{CheckoutID: s.CheckoutID, DeliveryCostKopecks: deliv}, nil
}

func (g *pricingGateway) ApplyPromo(ctx context.Context, checkoutID string, p pricing.PromoIntent, t pricing.Totals) (pricing.Applied, error) {
	s, err := g.svc.ApplyPromo(ctx, checkoutID, session.PromoIntent{PromoCode: p.PromoCode, BurnBonus: p.BurnBonus}, t.TotalKopecks)
	if err != nil {
		if errors.Is(err, session.ErrNotFound) {
			return pricing.Applied{}, pricing.ErrNotFound
		}
		return pricing.Applied{}, err
	}
	return pricing.Applied{CheckoutID: s.CheckoutID, Status: string(s.Status), PromoCode: p.PromoCode, Totals: t}, nil
}

// Pricing builds the pricing handler over the shared session service.
func Pricing(svc *session.Service, errs *httpx.Helper) *pricing.Handler {
	gw := &pricingGateway{svc: svc}
	return pricing.NewHandler(pricing.NewService(pricing.StubQuoter{}, gw), errs)
}
```

- [ ] **Step 14: Container + app + transport wiring**

In `container.go`: add `PricingHandler *pricing.Handler`, import pricing, add `c.PricingHandler = wire.Pricing(sessionSvc, c.ErrorsHelper)`.
In `transport/routes.go`: import pricing, add `Pricing pricing.Deps` to `Dependencies`, add `pricing.Mount(rr, deps.Pricing)`.
In `app.go`: import pricing, add `Pricing: pricing.Deps{Handler: container.PricingHandler},`.

- [ ] **Step 15: Verify + commit**

```bash
make generate && make lint && go build ./... && go vet ./... && go test ./...
git add api internal
git commit -m "feat(pricing): capability domain — PATCH /checkout/{id}/promo (re-quote totals + checksum via StubQuoter)"
```

---

## Task 5: Commit ports + deterministic stub adapters

Defines the six consumer-defined saga ports in `session` and their deterministic stub implementations in `internal/adapters/commit/`. Adds `NewServiceFull` so the saga can be wired with ports. **No `Commit` method yet** (Task 6).

**Files:**
- Modify: `internal/domains/session/types.go` (ports + result types), `service.go` (NewServiceFull)
- Create: `internal/adapters/commit/commit_stubs.go`

- [ ] **Step 1: Saga ports + result/error types** — append to `internal/domains/session/types.go`

```go
// --- commit-time ports + types (consumer-defined; v1 stubbed in internal/adapters/commit) ---

// Totals are the server-re-derived money figures (int64 kopecks; BonusAccrued is points).
type Totals struct {
	TotalKopecks        int64
	DeliveryCostKopecks int64
	DiscountKopecks     int64
	BonusAccrued        int64
}

// OrderRef identifies the created OMS order.
type OrderRef struct {
	ClientOrderID string
	OMSOrderID    string
}

// CommitResult is returned to the caller on a successful commit.
type CommitResult struct {
	Order        OrderRef
	PaymentToken string // online-payment widget token; empty for on_receipt
	Status       Status
}

// CartValidation reports whether the snapshot still matches live cart + stock.
type CartValidation struct {
	Changed     bool
	Unavailable []string // productIds (vendorCodeSku) no longer available
}

// ConflictError signals a 409 — cart/selection/totals changed. Code is user-safe
// ("cart_changed" | "selection_changed" | "totals_changed").
type ConflictError struct {
	Code    string
	Message string
}

func (e ConflictError) Error() string { return e.Code + ": " + e.Message }

// ErrUpstream signals an upstream/order failure → handler maps to 502.
var ErrUpstream = errors.New("upstream unavailable")

// CartValidator re-validates the cart snapshot against live cart + stock (§2a:
// no pre-reserve; the oversell window is accepted). Phase 2 → ENSI baskets + stock.
type CartValidator interface {
	Revalidate(ctx context.Context, s Session) (CartValidation, error)
}

// DeliveryReconciler re-resolves the chosen delivery with the PINNED dispatch date
// and reports whether the selection materially changed. §6: match by attributes
// (date, warehouse, window, carrier, tariff) and accept a recomputed cost — NOT by
// the full interval-id hash (the free-delivery threshold changes cost → id).
// Phase 2 → the delivery domain re-resolving via DeliverySource.
type DeliveryReconciler interface {
	Reconcile(ctx context.Context, s Session) (changed bool, err error)
}

// Pricer re-derives order totals server-side for the two-phase-truth checksum.
// Phase 2 → ENSI offers + discount server. MUST match pricing.StubQuoter in v1.
type Pricer interface {
	Quote(ctx context.Context, s Session) (Totals, error)
}

// OrderSink creates the OMS order. Idempotent by s.ClientOrderID (retry → same
// OrderRef, no duplicate). Phase 2 → starfish-oms /order/create with the clean
// payload (§5): {productId, quantity, unitPrice, lineDiscount}, real packages,
// stable client_order_id — drop qty-explosion/side-channel/hardcoded-package.
type OrderSink interface {
	Create(ctx context.Context, s Session, totals Totals) (OrderRef, error)
}

// DiscountSink spends/rolls-back discounts. Idempotent by DOC (= client_order_id):
// repeat spend with the same DOC is a no-op. Phase 2 → discount server (BonusSpend).
type DiscountSink interface {
	Spend(ctx context.Context, doc string, promo *PromoIntent) error
	Rollback(ctx context.Context, doc string) error
}

// PaymentLinker generates the online-payment widget token for prepay methods.
// Phase 2 → starfish-oms CreateOrderPaymentLink (getlink).
type PaymentLinker interface {
	Link(ctx context.Context, s Session, totals Totals) (token string, err error)
}
```

> `errors` is already imported in `types.go` (used by `ErrInvalidArgument`). No new import needed.

- [ ] **Step 2: NewServiceFull** — modify `internal/domains/session/service.go`

Change the `Service` struct to carry the saga ports, and add the full constructor (keep `NewService` for the non-commit tests / delivery e2e):

```go
// Service orchestrates the checkout session lifecycle, including the commit saga.
type Service struct {
	store      SessionStore
	cart       CartValidator
	reconciler DeliveryReconciler
	pricer     Pricer
	orders     OrderSink
	discount   DiscountSink
	payment    PaymentLinker
}

// NewService builds a Service WITHOUT the commit ports — for tests and flows that
// never call Commit (create/get/apply/delivery-selection). Calling Commit on such
// a Service is a programmer error.
func NewService(store SessionStore) *Service {
	if store == nil {
		panic("session: NewService requires a non-nil SessionStore")
	}
	return &Service{store: store}
}

// NewServiceFull builds a Service wired with the commit saga ports. All ports are
// required.
func NewServiceFull(store SessionStore, cart CartValidator, reconciler DeliveryReconciler, pricer Pricer, orders OrderSink, discount DiscountSink, payment PaymentLinker) *Service {
	if store == nil || cart == nil || reconciler == nil || pricer == nil || orders == nil || discount == nil || payment == nil {
		panic("session: NewServiceFull requires non-nil store and all commit ports")
	}
	return &Service{store: store, cart: cart, reconciler: reconciler, pricer: pricer, orders: orders, discount: discount, payment: payment}
}
```

- [ ] **Step 3: Stub adapters** — create `internal/adapters/commit/commit_stubs.go`

```go
// Package commit holds deterministic v1 stub implementations of the session
// commit saga ports. They prove the saga shape + honest status before the real
// adapters (phase 2: starfish-oms, discount server, baskets) land. Phase 2 splits
// these into per-domain adapters (OrderSink→adapters/oms, Pricer/DiscountSink→
// adapters/pricing, DeliveryReconciler→the delivery domain, CartValidator→baskets).
package commit

import (
	"context"
	"sync"

	session "gj-checkout/internal/domains/session"
)

// StubCartValidator: snapshot always valid (no change) in v1.
type StubCartValidator struct{}

var _ session.CartValidator = StubCartValidator{}

func (StubCartValidator) Revalidate(context.Context, session.Session) (session.CartValidation, error) {
	return session.CartValidation{Changed: false}, nil
}

// StubReconciler: pinned-date selection stays stable in v1 (no drift).
type StubReconciler struct{}

var _ session.DeliveryReconciler = StubReconciler{}

func (StubReconciler) Reconcile(context.Context, session.Session) (bool, error) {
	return false, nil
}

// StubPricer: deterministic totals. MUST match pricing.StubQuoter (so a promo set
// via PATCH /promo then a commit re-quote produce the same total → no 409).
type StubPricer struct{}

var _ session.Pricer = StubPricer{}

const (
	stubItemsSubtotalKopecks = int64(539600)
	stubPromoDiscountKopecks = int64(50000)
	stubBonusAccrued         = int64(25)
)

func (StubPricer) Quote(_ context.Context, s session.Session) (session.Totals, error) {
	var deliv int64
	if s.Selection != nil {
		deliv = s.Selection.DeliveryCostKopecks
	}
	var discount int64
	if s.Promo != nil && s.Promo.PromoCode != "" {
		discount = stubPromoDiscountKopecks
	}
	return session.Totals{
		TotalKopecks:        stubItemsSubtotalKopecks + deliv - discount,
		DeliveryCostKopecks: deliv,
		DiscountKopecks:     discount,
		BonusAccrued:        stubBonusAccrued,
	}, nil
}

// StubOrderSink: idempotent in-memory order book keyed by client_order_id.
type StubOrderSink struct {
	mu   sync.Mutex
	book map[string]session.OrderRef
}

var _ session.OrderSink = (*StubOrderSink)(nil)

func NewStubOrderSink() *StubOrderSink { return &StubOrderSink{book: map[string]session.OrderRef{}} }

func (o *StubOrderSink) Create(_ context.Context, s session.Session, _ session.Totals) (session.OrderRef, error) {
	o.mu.Lock()
	defer o.mu.Unlock()
	if ref, ok := o.book[s.ClientOrderID]; ok {
		return ref, nil // idempotent
	}
	ref := session.OrderRef{ClientOrderID: s.ClientOrderID, OMSOrderID: "OMS-" + s.ClientOrderID}
	o.book[s.ClientOrderID] = ref
	return ref, nil
}

// StubDiscountSink: idempotent spend ledger keyed by DOC (client_order_id).
type StubDiscountSink struct {
	mu    sync.Mutex
	spent map[string]bool
}

var _ session.DiscountSink = (*StubDiscountSink)(nil)

func NewStubDiscountSink() *StubDiscountSink { return &StubDiscountSink{spent: map[string]bool{}} }

func (d *StubDiscountSink) Spend(_ context.Context, doc string, _ *session.PromoIntent) error {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.spent[doc] = true // idempotent no-op on retry
	return nil
}

func (d *StubDiscountSink) Rollback(_ context.Context, doc string) error {
	d.mu.Lock()
	defer d.mu.Unlock()
	delete(d.spent, doc)
	return nil
}

// StubPaymentLinker: deterministic token for prepay methods.
type StubPaymentLinker struct{}

var _ session.PaymentLinker = StubPaymentLinker{}

func (StubPaymentLinker) Link(_ context.Context, s session.Session, _ session.Totals) (string, error) {
	return "stub-pay-token-" + s.ClientOrderID, nil
}
```

- [ ] **Step 4: Build + commit**

```bash
go build ./... && go vet ./... && go test ./...
git add internal
git commit -m "feat(session): commit saga ports + deterministic stub adapters (cart/reconcile/pricer/order/discount/payment)"
```

---

## Task 6: Commit saga in `session.Service` (TDD)

The headline: the durable, honest, idempotent commit orchestration. Lives in `session` (the consistency root).

**Files:** Modify `internal/domains/session/service.go`, `service_test.go`.

- [ ] **Step 1: Failing tests** — append to `internal/domains/session/service_test.go`

```go
// commitSvc builds a Service with in-memory store + the commit-stub fakes (local
// to the test so the domain test does not import the adapters package).
func commitSvc(t *testing.T) (*Service, *InMemoryStore) {
	t.Helper()
	store := NewInMemoryStore()
	svc := NewServiceFull(store,
		fakeCart{}, fakeReconciler{}, fakePricer{}, newFakeOrders(), newFakeDiscount(), fakePayment{})
	return svc, store
}

// readySession creates a session and fills the commit prerequisites.
func readySession(t *testing.T, svc *Service, basketID string) Session {
	t.Helper()
	ctx := context.Background()
	sess, err := svc.CreateSession(ctx, CreateSessionInput{CustomerID: "c", BasketID: basketID})
	if err != nil {
		t.Fatalf("CreateSession: %v", err)
	}
	if _, err := svc.ApplyDeliverySelection(ctx, sess.CheckoutID, Selection{DeliveryType: "courier", PinnedDispatchDate: "2026-06-02", IntervalID: "QOOcGGOK", DeliveryCostKopecks: 29900, Coverage: 2, CartSize: 4}); err != nil {
		t.Fatalf("ApplyDeliverySelection: %v", err)
	}
	if _, err := svc.ApplyRecipient(ctx, sess.CheckoutID, Recipient{FirstName: "Ann", LastName: "Lee", Phone: "+7900"}); err != nil {
		t.Fatalf("ApplyRecipient: %v", err)
	}
	if _, err := svc.ApplyPaymentMethod(ctx, sess.CheckoutID, PaymentSBP); err != nil {
		t.Fatalf("ApplyPaymentMethod: %v", err)
	}
	got, _ := svc.GetSession(ctx, sess.CheckoutID)
	return got
}

func TestCommit_happy(t *testing.T) {
	svc, store := commitSvc(t)
	sess := readySession(t, svc, "2000019994")

	res, err := svc.Commit(context.Background(), sess.CheckoutID)
	if err != nil {
		t.Fatalf("Commit: %v", err)
	}
	if res.Order.OMSOrderID != "OMS-2000019994" {
		t.Fatalf("order ref: want OMS-2000019994, got %q", res.Order.OMSOrderID)
	}
	if res.Status != StatusCommitted {
		t.Fatalf("want committed, got %s", res.Status)
	}
	if res.PaymentToken == "" {
		t.Fatal("prepay method must return a payment token")
	}
	reloaded, _ := store.Get(context.Background(), sess.CheckoutID)
	if reloaded.Status != StatusCommitted {
		t.Fatalf("session must be committed, got %s", reloaded.Status)
	}
}

func TestCommit_idempotent(t *testing.T) {
	svc, _ := commitSvc(t)
	sess := readySession(t, svc, "b-idem")
	r1, err := svc.Commit(context.Background(), sess.CheckoutID)
	if err != nil {
		t.Fatalf("first commit: %v", err)
	}
	r2, err := svc.Commit(context.Background(), sess.CheckoutID) // retry
	if err != nil {
		t.Fatalf("retry: %v", err)
	}
	if r1.Order.OMSOrderID != r2.Order.OMSOrderID {
		t.Fatal("idempotent commit must return the same order")
	}
}

func TestCommit_requiresSelectionRecipientPayment(t *testing.T) {
	ctx := context.Background()
	svc, _ := commitSvc(t)
	sess, _ := svc.CreateSession(ctx, CreateSessionInput{CustomerID: "c", BasketID: "b-bare"})
	// no delivery / recipient / payment yet
	_, err := svc.Commit(ctx, sess.CheckoutID)
	if !errors.Is(err, ErrInvalidArgument) {
		t.Fatalf("want ErrInvalidArgument, got %v", err)
	}
}

func TestCommit_conflict_cartChanged(t *testing.T) {
	store := NewInMemoryStore()
	svc := NewServiceFull(store, fakeCart{changed: true}, fakeReconciler{}, fakePricer{}, newFakeOrders(), newFakeDiscount(), fakePayment{})
	sess := readySession(t, svc, "b-cart")
	_, err := svc.Commit(context.Background(), sess.CheckoutID)
	var conflict ConflictError
	if !errors.As(err, &conflict) || conflict.Code != "cart_changed" {
		t.Fatalf("want ConflictError{cart_changed}, got %v", err)
	}
}

func TestCommit_conflict_totalsChanged(t *testing.T) {
	svc, store := commitSvc(t)
	sess := readySession(t, svc, "b-tot")
	// poke a stale checksum that won't match the fakePricer quote → 409
	stale := int64(1)
	s, _ := store.Get(context.Background(), sess.CheckoutID)
	s.TotalsChecksum = &stale
	_ = store.UpdateDetails(context.Background(), sess.CheckoutID, s)

	_, err := svc.Commit(context.Background(), sess.CheckoutID)
	var conflict ConflictError
	if !errors.As(err, &conflict) || conflict.Code != "totals_changed" {
		t.Fatalf("want ConflictError{totals_changed}, got %v", err)
	}
}

func TestCommit_onReceipt_noPaymentToken(t *testing.T) {
	ctx := context.Background()
	svc, _ := commitSvc(t)
	sess, _ := svc.CreateSession(ctx, CreateSessionInput{CustomerID: "c", BasketID: "b-cod"})
	_, _ = svc.ApplyDeliverySelection(ctx, sess.CheckoutID, Selection{DeliveryType: "store_pickup", PinnedDispatchDate: "2026-06-02", DeliveryCostKopecks: 0})
	_, _ = svc.ApplyRecipient(ctx, sess.CheckoutID, Recipient{FirstName: "A", LastName: "B", Phone: "p"})
	_, _ = svc.ApplyPaymentMethod(ctx, sess.CheckoutID, PaymentOnReceipt)
	res, err := svc.Commit(ctx, sess.CheckoutID)
	if err != nil {
		t.Fatalf("Commit: %v", err)
	}
	if res.PaymentToken != "" {
		t.Fatalf("on_receipt must not return a payment token, got %q", res.PaymentToken)
	}
}

// --- local fakes (mirror internal/adapters/commit; kept here to respect the
// domain boundary — the session test must not import the adapters package) ---

type fakeCart struct{ changed bool }

func (f fakeCart) Revalidate(context.Context, Session) (CartValidation, error) {
	return CartValidation{Changed: f.changed}, nil
}

type fakeReconciler struct{ changed bool }

func (f fakeReconciler) Reconcile(context.Context, Session) (bool, error) { return f.changed, nil }

type fakePricer struct{}

func (fakePricer) Quote(_ context.Context, s Session) (Totals, error) {
	var deliv int64
	if s.Selection != nil {
		deliv = s.Selection.DeliveryCostKopecks
	}
	var discount int64
	if s.Promo != nil && s.Promo.PromoCode != "" {
		discount = 50000
	}
	return Totals{TotalKopecks: 539600 + deliv - discount, DeliveryCostKopecks: deliv, DiscountKopecks: discount, BonusAccrued: 25}, nil
}

type fakeOrders struct{ book map[string]OrderRef }

func newFakeOrders() *fakeOrders { return &fakeOrders{book: map[string]OrderRef{}} }

func (o *fakeOrders) Create(_ context.Context, s Session, _ Totals) (OrderRef, error) {
	if r, ok := o.book[s.ClientOrderID]; ok {
		return r, nil
	}
	r := OrderRef{ClientOrderID: s.ClientOrderID, OMSOrderID: "OMS-" + s.ClientOrderID}
	o.book[s.ClientOrderID] = r
	return r, nil
}

type fakeDiscount struct{ spent map[string]bool }

func newFakeDiscount() *fakeDiscount { return &fakeDiscount{spent: map[string]bool{}} }

func (d *fakeDiscount) Spend(_ context.Context, doc string, _ *PromoIntent) error {
	d.spent[doc] = true
	return nil
}
func (d *fakeDiscount) Rollback(_ context.Context, doc string) error { delete(d.spent, doc); return nil }

type fakePayment struct{}

func (fakePayment) Link(_ context.Context, s Session, _ Totals) (string, error) {
	return "tok-" + s.ClientOrderID, nil
}
```

- [ ] **Step 2: Run → FAIL**

Run: `go test ./internal/domains/session/ -run TestCommit -v`
Expected: FAIL — `Commit` undefined.

- [ ] **Step 3: Implement the saga** — append to `internal/domains/session/service.go`

```go
// Commit creates the order from the chosen komplektaciya. HONEST + IDEMPOTENT.
// One order + spill leftover (current mechanic; §2b). Saga: revalidate → reconcile
// → checksum → create → spend → pay, with compensation on failure. Status maps to
// HTTP in the handler: never 200 {success:false}.
func (s *Service) Commit(ctx context.Context, checkoutID string) (CommitResult, error) {
	sess, err := s.store.Get(ctx, checkoutID)
	if err != nil {
		return CommitResult{}, err // ErrNotFound passes through
	}

	// Idempotent: already committed → return the existing order ref (book keyed by
	// client_order_id) + re-issue the prepay token.
	if sess.Status == StatusCommitted {
		ref, err := s.orders.Create(ctx, sess, Totals{})
		if err != nil {
			return CommitResult{}, fmt.Errorf("%w: order create (idempotent replay): %w", ErrUpstream, err)
		}
		return CommitResult{Order: ref, PaymentToken: s.maybePaymentToken(ctx, sess, Totals{}), Status: StatusCommitted}, nil
	}

	// Required selection + recipient + payment method (§4 minimal payload).
	if sess.Selection == nil {
		return CommitResult{}, fmt.Errorf("%w: delivery method not selected", ErrInvalidArgument)
	}
	if sess.Recipient == nil {
		return CommitResult{}, fmt.Errorf("%w: recipient required", ErrInvalidArgument)
	}
	if sess.PaymentMethod == "" {
		return CommitResult{}, fmt.Errorf("%w: payment method required", ErrInvalidArgument)
	}

	// 1. Re-validate cart/stock (no pre-reserve; §2a — oversell window accepted).
	cv, err := s.cart.Revalidate(ctx, sess)
	if err != nil {
		return CommitResult{}, fmt.Errorf("%w: cart revalidate: %w", ErrUpstream, err)
	}
	if cv.Changed {
		return CommitResult{}, ConflictError{Code: "cart_changed", Message: "корзина изменилась, проверьте состав"}
	}

	// 2. Reconcile delivery with the PINNED date (match by attributes, not full id
	//    hash — §6: the free-delivery threshold changes cost → id).
	changed, err := s.reconciler.Reconcile(ctx, sess)
	if err != nil {
		return CommitResult{}, fmt.Errorf("%w: delivery reconcile: %w", ErrUpstream, err)
	}
	if changed {
		return CommitResult{}, ConflictError{Code: "selection_changed", Message: "выбор доставки обновился, подтвердите"}
	}

	// 3. Two-phase truth: re-derive totals (int64 kopecks) and compare to the
	//    last-shown checksum. Mismatch → 409 (no float epsilon).
	totals, err := s.pricer.Quote(ctx, sess)
	if err != nil {
		return CommitResult{}, fmt.Errorf("%w: re-quote: %w", ErrUpstream, err)
	}
	if sess.TotalsChecksum != nil && *sess.TotalsChecksum != totals.TotalKopecks {
		return CommitResult{}, ConflictError{Code: "totals_changed", Message: "сумма изменилась, подтвердите"}
	}

	// 4–5. Durable saga: create → spend → pay (with compensation).
	if err := s.store.UpdateStatus(ctx, checkoutID, StatusCommitting); err != nil {
		return CommitResult{}, err
	}

	ref, err := s.orders.Create(ctx, sess, totals) // idempotent by client_order_id
	if err != nil {
		_ = s.store.UpdateStatus(ctx, checkoutID, StatusFailed)
		return CommitResult{}, fmt.Errorf("%w: order create: %w", ErrUpstream, err)
	}

	if err := s.discount.Spend(ctx, sess.ClientOrderID, sess.Promo); err != nil {
		_ = s.discount.Rollback(ctx, sess.ClientOrderID) // compensation
		_ = s.store.UpdateStatus(ctx, checkoutID, StatusFailed)
		return CommitResult{}, fmt.Errorf("%w: discount spend: %w", ErrUpstream, err)
	}

	token := ""
	if isPrepay(sess.PaymentMethod) {
		token, err = s.payment.Link(ctx, sess, totals)
		if err != nil {
			_ = s.discount.Rollback(ctx, sess.ClientOrderID) // compensation
			_ = s.store.UpdateStatus(ctx, checkoutID, StatusFailed)
			return CommitResult{}, fmt.Errorf("%w: payment link: %w", ErrUpstream, err)
		}
	}

	// 6. Spill leftover → new basket (current mechanic, §2b). v1: documented no-op.
	// 7. Done.
	if err := s.store.UpdateStatus(ctx, checkoutID, StatusCommitted); err != nil {
		return CommitResult{}, err
	}
	return CommitResult{Order: ref, PaymentToken: token, Status: StatusCommitted}, nil
}

func (s *Service) maybePaymentToken(ctx context.Context, sess Session, totals Totals) string {
	if !isPrepay(sess.PaymentMethod) {
		return ""
	}
	token, _ := s.payment.Link(ctx, sess, totals)
	return token
}

func isPrepay(m PaymentMethod) bool { return m == PaymentSBP || m == PaymentCardOnline }
```

- [ ] **Step 4: Run → PASS**

Run: `go test ./internal/domains/session/ -run TestCommit -count=1 -v`
Expected: PASS (happy, idempotent, requires-prereqs, cart-conflict, totals-conflict, on-receipt-no-token).

- [ ] **Step 5: Commit**

```bash
git add internal/domains/session/service.go internal/domains/session/service_test.go
git commit -m "feat(session): commit saga — revalidate/reconcile/checksum/create/spend/pay, honest+idempotent (TDD)"
```

---

## Task 7: Commit endpoint — honest HTTP status

Exposes `POST /checkout/{id}/commit` with honest status mapping (`201`/`409`/`400`/`404`/`502`).

**Files:** Modify `api/v1/components/schemas/checkout.yaml`, `api/v1/paths/checkout.yaml`, `api/v1/openapi.yaml`, `internal/domains/session/handler.go`, `routes.go`, `handler_test.go`.

- [ ] **Step 1: OpenAPI — CommitResult schema** — append to `api/v1/components/schemas/checkout.yaml`

```yaml
CommitResult:
  type: object
  required: [order_id, client_order_id, status]
  properties:
    order_id:        { type: string, description: "OMS order id" }
    client_order_id: { type: string, description: "= basket number" }
    payment_token:   { type: string, nullable: true, description: "online-payment widget token; null for on_receipt" }
    status:          { type: string, description: "session lifecycle status (e.g. committed)" }
```

> **Why `status` is a plain string here, not an enum:** the session `apiv1` package already has the `CheckoutSessionStatus` enum (consts `Committed`, `Draft`, … — currently UNprefixed because it is the only enum in the package). Adding a second enum with the same values would force oapi-codegen to PREFIX both const sets (`CheckoutSessionStatusCommitted`, …), breaking the existing `e2e_test.go` which uses `sessionapiv1.Draft`/`Selecting`/`Committed`. Keeping `CommitResult.status` a plain string avoids the rename.

- [ ] **Step 2: OpenAPI — Commit path** — append to `api/v1/paths/checkout.yaml`

```yaml
Commit:
  post:
    tags: [session]
    operationId: commitCheckout
    summary: Commit the checkout — create the order (honest, idempotent)
    security: []
    parameters:
      - name: checkout_id
        in: path
        required: true
        schema: { type: string, format: uuid }
    responses:
      "201":
        description: Order created
        content:
          application/json:
            schema:
              $ref: "../components/schemas/checkout.yaml#/CommitResult"
      "400": { description: Invalid argument (missing selection/recipient/payment), content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } } }
      "404": { description: Not found, content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } } }
      "409": { description: Conflict — cart/selection/totals changed, content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } } }
      "502": { description: Upstream unavailable, content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } } }
```

- [ ] **Step 3: OpenAPI — register path** — modify `api/v1/openapi.yaml`, under `paths:`

```yaml
  /checkout/{checkout_id}/commit:
    $ref: "./paths/checkout.yaml#/Commit"
```

- [ ] **Step 4: Generate**

Run: `make generate`
Expected: `internal/domains/session/apiv1/openapi.gen.go` gains `CommitResult`. No errors.

- [ ] **Step 5: Failing handler test** — append to `internal/domains/session/handler_test.go`

```go
func TestCommitHandler_201_onSuccess(t *testing.T) {
	store := NewInMemoryStore()
	svc := NewServiceFull(store, fakeCart{}, fakeReconciler{}, fakePricer{}, newFakeOrders(), newFakeDiscount(), fakePayment{})
	h := NewHandler(svc, httpx.NewHelper())
	sess := readySession(t, svc, "h-201")

	rec := commitReq(t, h, sess.CheckoutID)
	if rec.Code != http.StatusCreated {
		t.Fatalf("want 201, got %d: %s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"order_id":"OMS-h-201"`) {
		t.Fatalf("body: %s", rec.Body.String())
	}
}

func TestCommitHandler_409_onConflict(t *testing.T) {
	store := NewInMemoryStore()
	svc := NewServiceFull(store, fakeCart{changed: true}, fakeReconciler{}, fakePricer{}, newFakeOrders(), newFakeDiscount(), fakePayment{})
	h := NewHandler(svc, httpx.NewHelper())
	sess := readySession(t, svc, "h-409")

	rec := commitReq(t, h, sess.CheckoutID)
	if rec.Code != http.StatusConflict {
		t.Fatalf("want 409, got %d: %s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"error":"cart_changed"`) {
		t.Fatalf("body: %s", rec.Body.String())
	}
}

func TestCommitHandler_400_onMissingPrereqs(t *testing.T) {
	store := NewInMemoryStore()
	svc := NewServiceFull(store, fakeCart{}, fakeReconciler{}, fakePricer{}, newFakeOrders(), newFakeDiscount(), fakePayment{})
	h := NewHandler(svc, httpx.NewHelper())
	sess, _ := svc.CreateSession(context.Background(), CreateSessionInput{CustomerID: "c", BasketID: "h-400"})

	rec := commitReq(t, h, sess.CheckoutID)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("want 400, got %d: %s", rec.Code, rec.Body.String())
	}
}

// commitReq drives the Commit handler with a chi route context carrying checkout_id.
func commitReq(t *testing.T, h *Handler, checkoutID string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, "/api/v1/checkout/"+checkoutID+"/commit", nil)
	rctx := chi.NewRouteContext()
	rctx.URLParams.Add("checkout_id", checkoutID)
	req = req.WithContext(context.WithValue(req.Context(), chi.RouteCtxKey, rctx))
	rec := httptest.NewRecorder()
	h.Commit(rec, req)
	return rec
}
```

> Ensure `handler_test.go` imports: `context`, `net/http`, `net/http/httptest`, `strings`, `testing`, `github.com/go-chi/chi/v5`, `gj-checkout/internal/platform/httpx`. `readySession` and the `fake*` types come from `service_test.go` (same package) — no duplication.

- [ ] **Step 6: Run → FAIL** (`Commit` handler undefined). Then implement.

Append the handler to `internal/domains/session/handler.go`:

```go
// Commit handles POST /api/v1/checkout/{checkout_id}/commit. HONEST status:
// 201 created | 409 conflict | 400 invalid | 404 not found | 502 upstream | 500.
// NEVER 200 {success:false}.
func (h *Handler) Commit(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "checkout_id")
	res, err := h.service.Commit(r.Context(), id)
	if err != nil {
		var conflict ConflictError
		switch {
		case errors.As(err, &conflict):
			h.errs.JSON(w, http.StatusConflict, conflict.Code, conflict.Message)
		case errors.Is(err, ErrNotFound):
			h.errs.JSON(w, http.StatusNotFound, "not_found", "checkout session not found")
		case errors.Is(err, ErrInvalidArgument):
			h.errs.BadRequest(w, "invalid_argument", err.Error())
		case errors.Is(err, ErrUpstream):
			h.errs.JSON(w, http.StatusBadGateway, "upstream_unavailable", "order service unavailable")
		default:
			h.errs.Internal(w, "internal", "internal error")
		}
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	_ = json.NewEncoder(w).Encode(toCommitDTO(res))
}

// toCommitDTO maps the commit result to the generated API DTO.
func toCommitDTO(res CommitResult) apiv1.CommitResult {
	dto := apiv1.CommitResult{
		OrderId:       res.Order.OMSOrderID,
		ClientOrderId: res.Order.ClientOrderID,
		Status:        string(res.Status),
	}
	if res.PaymentToken != "" {
		t := res.PaymentToken
		dto.PaymentToken = &t
	}
	return dto
}
```

> `errors`, `json`, `chi`, and `apiv1` are already imported in `handler.go`. `CommitResult.Status` is a plain `string` (see the schema note in Step 1), so `string(res.Status)` is correct.

- [ ] **Step 7: Route** — modify `internal/domains/session/routes.go`

```go
func Mount(r chi.Router, deps Deps) {
	r.Route("/checkout", func(rr chi.Router) {
		rr.Post("/", deps.Handler.Create)
		rr.Get("/{checkout_id}", deps.Handler.Get)
		rr.Post("/{checkout_id}/commit", deps.Handler.Commit)
	})
}
```

- [ ] **Step 8: Run → PASS + gates + commit**

```bash
make generate && make lint && go build ./... && go vet ./... && go test ./internal/domains/session/ -count=1
git add api internal/domains/session
git commit -m "feat(session): POST /checkout/{id}/commit — honest status (201/409/400/404/502), never 200-mask"
```

---

## Task 8: Wire the saga end-to-end + full e2e + DoD + tag

Wires the commit stubs into the live service and proves the entire walking skeleton through the mounted router.

**Files:** Modify `internal/app/wire/session.go`, `internal/platform/transport/e2e_test.go`.

- [ ] **Step 1: Wire commit stubs into the session service** — modify `internal/app/wire/session.go`

```go
package wire

import (
	"gj-checkout/internal/adapters/commit"
	"gj-checkout/internal/domains/session"
	"gj-checkout/internal/platform/httpx"

	"github.com/jackc/pgx/v5/pgxpool"
)

// SessionService builds the session service over a pgx-backed repository, wired
// with the v1 commit-saga stub ports. Returned so the session handler AND the
// capability-domain gateways can share one service.
func SessionService(db *pgxpool.Pool) *session.Service {
	repo := session.NewRepository(db)
	return session.NewServiceFull(repo,
		commit.StubCartValidator{},
		commit.StubReconciler{},
		commit.StubPricer{},
		commit.NewStubOrderSink(),
		commit.NewStubDiscountSink(),
		commit.StubPaymentLinker{},
	)
}

// SessionHandler builds the session HTTP handler over an already-constructed service.
func SessionHandler(svc *session.Service, errs *httpx.Helper) *session.Handler {
	return session.NewHandler(svc, errs)
}
```

> Argument order must match `NewServiceFull(store, cart, reconciler, pricer, orders, discount, payment)`.

- [ ] **Step 2: Update e2e buildDeps + add full commit flow** — modify `internal/platform/transport/e2e_test.go`

In `buildDeps`, replace the session service construction and add the three new handlers. Change:

```go
	store := session.NewInMemoryStore()
	svc := session.NewService(store)
	sh := session.NewHandler(svc, errs)
	dh := wire.Delivery(config.Config{}, svc, errs) // default → stub source (no network)
```
to:
```go
	store := session.NewInMemoryStore()
	svc := session.NewServiceFull(store,
		commit.StubCartValidator{}, commit.StubReconciler{}, commit.StubPricer{},
		commit.NewStubOrderSink(), commit.NewStubDiscountSink(), commit.StubPaymentLinker{})
	sh := session.NewHandler(svc, errs)
	dh := wire.Delivery(config.Config{}, svc, errs) // default → stub source (no network)
	rh := wire.Recipient(svc, errs)
	ph := wire.Payment(svc, errs)
	prh := wire.Pricing(svc, errs)
```
and extend the returned `Dependencies`:
```go
	return Dependencies{
		Health:        health.Deps{Handler: healthHandler},
		Observability: observability.Deps{Metrics: metrics},
		Session:       session.Deps{Handler: sh},
		Delivery:      delivery.Deps{Handler: dh},
		Recipient:     recipient.Deps{Handler: rh},
		Payment:       payment.Deps{Handler: ph},
		Pricing:       pricing.Deps{Handler: prh},
	}
```
Add imports: `gj-checkout/internal/adapters/commit`, `gj-checkout/internal/domains/recipient`, `gj-checkout/internal/domains/payment`, `gj-checkout/internal/domains/pricing`.

Append a new e2e test exercising the full walking skeleton (reuse the existing `doPost`/`doPatch`/`doGet`/`decode`/`assertStatus` helpers):

```go
// TestE2E_FullCommitFlow drives create → delivery-method → recipient →
// payment-method → commit through the mounted router, then a retry (idempotent),
// then a no-prereq 400.
func TestE2E_FullCommitFlow(t *testing.T) {
	r := chi.NewRouter()
	registerRoutes(r, buildDeps(t))
	srv := httptest.NewServer(r)
	t.Cleanup(srv.Close)
	base := srv.URL + "/api/v1"
	c := srv.Client()

	// create
	resp := doPost(t, c, base+"/checkout", `{"customer_id":"cust-1","basket_id":"2000019994"}`)
	assertStatus(t, "POST /checkout", resp, http.StatusCreated)
	var created sessionapiv1.CheckoutSession
	decode(t, resp, &created)
	id := created.CheckoutId.String()

	// delivery-method (courier)
	resp = doPatch(t, c, fmt.Sprintf("%s/checkout/%s/delivery-method", base, id), `{"type":"courier"}`)
	assertStatus(t, "PATCH delivery-method", resp, http.StatusOK)
	resp.Body.Close()

	// recipient
	resp = doPatch(t, c, fmt.Sprintf("%s/checkout/%s/recipient", base, id), `{"first_name":"Ann","last_name":"Lee","phone":"+79001112233"}`)
	assertStatus(t, "PATCH recipient", resp, http.StatusOK)
	resp.Body.Close()

	// payment-method (sbp)
	resp = doPatch(t, c, fmt.Sprintf("%s/checkout/%s/payment-method", base, id), `{"type":"sbp"}`)
	assertStatus(t, "PATCH payment-method", resp, http.StatusOK)
	resp.Body.Close()

	// commit → 201
	resp = doPost(t, c, fmt.Sprintf("%s/checkout/%s/commit", base, id), "")
	assertStatus(t, "POST commit", resp, http.StatusCreated)
	var commitRes sessionapiv1.CommitResult
	decode(t, resp, &commitRes)
	if commitRes.OrderId != "OMS-2000019994" {
		t.Fatalf("commit: want order OMS-2000019994, got %q", commitRes.OrderId)
	}
	if commitRes.Status != "committed" {
		t.Fatalf("commit: want status committed, got %q", commitRes.Status)
	}
	if commitRes.PaymentToken == nil || *commitRes.PaymentToken == "" {
		t.Fatal("commit: prepay must return a payment token")
	}

	// retry → still 201, same order (idempotent)
	resp = doPost(t, c, fmt.Sprintf("%s/checkout/%s/commit", base, id), "")
	assertStatus(t, "POST commit (retry)", resp, http.StatusCreated)
	var retry sessionapiv1.CommitResult
	decode(t, resp, &retry)
	if retry.OrderId != commitRes.OrderId {
		t.Fatalf("idempotent commit: want same order, got %q vs %q", retry.OrderId, commitRes.OrderId)
	}

	// session GET → committed
	resp = doGet(t, c, fmt.Sprintf("%s/checkout/%s", base, id))
	assertStatus(t, "GET committed", resp, http.StatusOK)
	var fin sessionapiv1.CheckoutSession
	decode(t, resp, &fin)
	if fin.Status != sessionapiv1.Committed {
		t.Fatalf("GET: want committed, got %q", fin.Status)
	}

	// bare session → commit 400 (no selection/recipient/payment)
	resp = doPost(t, c, base+"/checkout", `{"customer_id":"c2","basket_id":"bare-1"}`)
	var bare sessionapiv1.CheckoutSession
	decode(t, resp, &bare)
	resp = doPost(t, c, fmt.Sprintf("%s/checkout/%s/commit", base, bare.CheckoutId.String()), "")
	assertStatus(t, "POST commit (no prereqs)", resp, http.StatusBadRequest)
	resp.Body.Close()
}
```

> If `sessionapiv1.Committed` (the generated enum const for status `committed`) is named differently, match the generated name. The string compare `commitRes.Status != "committed"` works regardless because the generated `CommitResultStatus` is a string type.

- [ ] **Step 3: Run the full suite**

Run (offline — all stubs, in-memory):
```bash
go build ./... && go vet ./... && go test ./... -count=1
```
Expected: all green, including `TestE2E_FullCommitFlow` and the existing `TestE2E_DeliveryFlowOverMountedRouter` (unchanged behavior).

- [ ] **Step 4: Boot smoke against real Postgres**

```bash
make migrate-up    # applies 0003
make run &         # needs CHECKOUT_DB_DSN (.env)
sleep 2
ID=$(curl -s -X POST :8080/api/v1/checkout -d '{"customer_id":"c1","basket_id":"2000019994"}' | jq -r .checkout_id)
curl -s -X PATCH :8080/api/v1/checkout/$ID/delivery-method -d '{"type":"courier"}' >/dev/null
curl -s -X PATCH :8080/api/v1/checkout/$ID/recipient -d '{"first_name":"A","last_name":"B","phone":"+7900"}' >/dev/null
curl -s -X PATCH :8080/api/v1/checkout/$ID/payment-method -d '{"type":"sbp"}' >/dev/null
curl -is -X POST :8080/api/v1/checkout/$ID/commit | head -1            # HTTP/1.1 201 Created
curl -s  -X POST :8080/api/v1/checkout/$ID/commit | jq '{order:.order_id, status, token:.payment_token}'  # idempotent: same order
curl -s :8080/api/v1/checkout/$ID | jq .status                          # "committed"
kill %1
```
Expected: first commit `201`; retry returns the same `order_id`; session status `committed`. Confirm via DB: `SELECT status FROM checkout_sessions WHERE checkout_id='$ID';` → `committed`.

- [ ] **Step 5: Full DoD gates + tag**

```bash
make generate && make lint && go vet ./... && go test ./... -count=1
CHECKOUT_TEST_DB_DSN="postgres://checkout:checkout@127.0.0.1:5544/checkout?sslmode=disable" go test ./internal/domains/session/ -run TestRepository -count=1
make docker
git add -A
git commit -m "test(checkout): full create→select→recipient→payment→commit e2e on stubs green"
git tag v0.1.0
```

> Push (main + tags) is the user's call (per workspace rules — git operations on platform repos are Zak's). Do not push automatically.

---

## Definition of Done (Plan 4 = v1 walking skeleton complete)

- **Domains:** `recipient`, `payment`, `pricing` exist as thin capability domains, each owning its `PATCH` endpoint and writing through a narrow gateway into `session` (no cross-domain imports; per-domain `boundary_test.go` green).
- **Full flow on stubs:** `POST /checkout` → `PATCH /delivery-method` (pinned date) → `PATCH /recipient` → `PATCH /payment-method` → (`PATCH /promo` optional) → `POST /commit`.
- **Commit is HONEST:** `201` created | `409` `{cart_changed|selection_changed|totals_changed}` | `400` (missing selection/recipient/payment) | `404` | `502` upstream — **never `200 {success:false}`**.
- **Commit is IDEMPOTENT** by `client_order_id` (retry → same order; discount spend no-op by DOC).
- **Saga shape** (create → spend → pay) with compensation hooks; reconcile-by-attributes documented (§6); spill is a documented no-op stub.
- **Money is `int64` kopecks** everywhere (Totals, checksum, stub constants); checksum compared as integers.
- **Gates green:** `go build/vet/test ./...`, `make generate` (no drift), `make lint` (redocly), session repository integration test (with DB), `make docker`; tagged `v0.1.0`.

---

## v1 → phase 2 handoff (after walking skeleton)

Replace each stub with a real adapter over the published clients (`v0.1.1`), wired by config (mirror `OMS_DELIVERY_SOURCE=stub|real`):

- **`OrderSink`** → `internal/adapters/oms/` over `starfish-oms` `CreateOrder` — build the clean §5 payload from the session (`{productId, quantity, unitPrice, lineDiscount}`, real packages, stable `clientOrderId`; rubles↔kopecks at the boundary per money-doc). Drop qty-explosion / custom-attr side-channel / hardcoded package.
- **`PaymentLinker`** → `starfish-oms` `CreateOrderPaymentLink` (getlink) for the YooKassa/ЮMoney widget.
- **`Pricer` + `DiscountSink`** → `internal/adapters/pricing/` over ENSI `offers` + the `discount` client (`GetDiscount` quote → `BonusSpend`, idempotent by DOC). Collapse `pricing.StubQuoter` and `commit.StubPricer` onto this one adapter (removes the v1 stub-coupling).
- **`DeliveryReconciler`** → move into the `delivery` domain (it owns the resolver): re-resolve with `Selection.PinnedDispatchDate`, match by `(date, warehouse, window, carrier, tariff)`, accept the recomputed cost. Wire bridges it to the session port.
- **`CartValidator`** → `internal/adapters/cart/` over ENSI `baskets` + stock; re-snapshot the cart on mid-checkout login merge (memory note: snapshot-on-entry + re-validate-on-commit).
- **`recipient`** gains `CustomerSource` → ENSI customers (authed prefill); **`payment`** gains `PaymentSource` → OMS pay-service (acquirers).
- Then **Track B:** `clients/checkout` + ecom-gateway onboarding + auth contour (`X-Customer-Id` inject; anti-IDOR) + GrowthBook `NEW_CHECKOUT` on site.
