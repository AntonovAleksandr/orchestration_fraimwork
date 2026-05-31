# Checkout v1 — Plan 4: Commit Saga (honest, idempotent, on stub ports) Implementation Plan

> ⚠️ **ТРЕБУЕТ РЕ-ПЛАНИРОВАНИЯ под domain-map (2026-05-30) — НЕ исполнять как есть.** План написан до карты доменов (`platform-new/checkout/docs/architecture/domain-map.md`). По новой карте: сага-оркестрация — в **`internal/domains/session/service.go`** (session = корень). Порты распределить по доменам: `Pricer`+`DiscountSink` → домен **`pricing`**; способ оплаты/payment-link → домен **`payment`**; получатель (recipient/address) → домен **`recipient`**; `OrderSink` (создание заказа в OMS) → adapter `internal/adapters/oms/` за портом, объявленным в session. Остальные мутации (promo/payment-method/recipient) — в соответствующих доменах, session их оркеструет. Честный 201/409/4xx + идемпотентность по client_order_id остаются. Переписать по writing-plans перед запуском.

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** Complete the walking skeleton — remaining session mutations (recipient/address/promo/payment-method) + a durable, **honest** commit: re-validate → reconcile delivery → two-phase-truth checksum → build clean OMS payload → saga (order create → discount spend → payment) → spill → status. Status is honest (`201`/`409`/real 4xx — never `200 {success:false}`), idempotent by `client_order_id`, all upstreams stubbed.

**Architecture:** Commit orchestration in `internal/domains/checkout/service.go` over consumer-defined ports (`CartValidator`, `Pricer`, `OrderSink`, `DiscountSink`) — all stubbed deterministically in `internal/adapters/checkout/`. Conflicts are a typed `ErrConflict{Code}` → handler maps to HTTP 409. This proves the contract and saga shape before real clients (phase 2) land.

**Prereq:** Plans 1–3 complete.

**Design:** spec §4 (commit flow), §5 (clean payload — drop qty-explosion/side-channel/hardcoded package), §6 (honest status, 409, idempotency, drift reconcile), §2a (spend-on-create saga; reserve window accepted), §2b (one order + spill).

---

## File Structure (Plan 4)

```
checkout/
└── internal/
    ├── domains/checkout/
    │   ├── types.go      + Recipient, Address, PromoIntent, PaymentMethod, CommitResult, ErrConflict, commit ports
    │   ├── service.go    + SetRecipient/SetAddress/SetPromo/SetPaymentMethod + Commit (saga)
    │   ├── service_test.go + commit tests (happy / 409 / idempotent)
    │   ├── handler.go    + recipient/address/promo/payment-method/commit handlers (honest status)
    │   └── routes.go     + the PATCH/POST routes
    └── adapters/checkout/
        └── commit_stubs.go  stub CartValidator/Pricer/OrderSink/DiscountSink
```

---

## Task 1: Remaining session mutations

**Files:** Modify `types.go`, `service.go`, `repository.go`/`stub.go`, OpenAPI, `handler.go`, `routes.go`.

- [ ] **Step 1: Domain types** (add to `types.go`)

```go
type Recipient struct {
	FirstName string `json:"first_name"`
	LastName  string `json:"last_name"`
	Phone     string `json:"phone"`
}
type Address struct {
	FiasCity, Street, House, Flat, Entrance, Floor, Intercom, Comment string
	Lat, Lng float64
}
type PromoIntent struct {
	PromoCode string `json:"promo_code"`
	BurnBonus bool   `json:"burn_bonus"`
}
type PaymentMethod string
const (
	PaySBP        PaymentMethod = "sbp"
	PayCardOnline PaymentMethod = "card_online"
	PayOnReceipt  PaymentMethod = "on_receipt"
)
```
Add to `Session`: `Recipient *Recipient`, `Address *Address`, `Promo *PromoIntent`, `Payment PaymentMethod`. Persist these in the `selection`-style JSONB (extend the JSONB column already added in Plan 3, or add columns — simplest: add a single `details jsonb` column via migration 0003 holding recipient/address/promo/payment). Add a generic `UpdateDetails(ctx, checkoutID, Session) error` to `SessionStore`, `Repository`, `InMemoryStore`.

> Decision: add migration `0003_session_details.up.sql` → `ALTER TABLE checkout_sessions ADD COLUMN IF NOT EXISTS details jsonb;` (down: drop). `details` stores `{recipient,address,promo,payment}`. Keeps schema flat for the skeleton.

- [ ] **Step 2: Service setters** (add to `service.go`) — each loads session, sets field, persists, returns session. Example:

```go
func (s *Service) SetRecipient(ctx context.Context, id string, r Recipient) (Session, error) {
	sess, err := s.store.Get(ctx, id)
	if err != nil { return Session{}, err }
	if r.FirstName == "" || r.LastName == "" || r.Phone == "" {
		return Session{}, fmt.Errorf("%w: recipient first_name/last_name/phone required", ErrInvalidArgument)
	}
	sess.Recipient = &r
	if err := s.store.UpdateDetails(ctx, id, sess); err != nil { return Session{}, err }
	return sess, nil
}
```
Write `SetAddress`, `SetPromo`, `SetPaymentMethod` to the same shape (validate: address requires FiasCity; payment must be one of the 3 enum values).

- [ ] **Step 3: OpenAPI + handlers + routes** — add `PATCH /checkout/{id}/recipient|address|promo|payment-method`, each body→`CheckoutSession`. Handlers mirror Plan 3's `SetDeliveryMethod` shape (decode body → service setter → 200/400/404). Routes:
```go
		rr.Patch("/{checkout_id}/recipient", deps.Handler.SetRecipient)
		rr.Patch("/{checkout_id}/address", deps.Handler.SetAddress)
		rr.Patch("/{checkout_id}/promo", deps.Handler.SetPromo)
		rr.Patch("/{checkout_id}/payment-method", deps.Handler.SetPaymentMethod)
```
Run `make generate && make lint && go build ./... && go test ./...`.

- [ ] **Step 4: Commit**

```bash
git add migrations api internal
git commit -m "feat(checkout): recipient/address/promo/payment-method mutations"
```

---

## Task 2: Commit ports + deterministic stubs

**Files:** Modify `types.go` (ports + result/error); Create `internal/adapters/checkout/commit_stubs.go`.

- [ ] **Step 1: Ports + result + conflict error** (`types.go`)

```go
// CartValidation reports whether the snapshot still matches live cart+stock.
type CartValidation struct {
	Changed       bool
	Unavailable   []string // productIds no longer available
}
// Totals are the server-re-derived money figures.
type Totals struct {
	Total          float64
	DeliveryCost   float64
	Discount       float64
	BonusAccrued   int
}
// OrderRef identifies the created OMS order.
type OrderRef struct {
	ClientOrderID string
	OMSOrderID    string
}

// Commit-time ports (consumer-defined; v1 stubbed). All idempotent where noted.
type CartValidator interface {
	Revalidate(ctx context.Context, s Session) (CartValidation, error)
}
type Pricer interface {
	Quote(ctx context.Context, s Session) (Totals, error)
}
type OrderSink interface {
	// Create is idempotent by s ClientOrderID (retry → same OrderRef, no dup).
	Create(ctx context.Context, s Session, totals Totals) (OrderRef, error)
}
type DiscountSink interface {
	// Spend is idempotent by clientOrderID (DOC). No-op if already spent.
	Spend(ctx context.Context, clientOrderID string, promo *PromoIntent) error
	Rollback(ctx context.Context, clientOrderID string) error
}

// CommitResult is returned to the caller on success.
type CommitResult struct {
	Order        OrderRef
	PaymentToken string // online payment widget token; empty for on-receipt
	Status       Status
}

// ErrConflict signals a 409 (cart/selection/totals changed). Code is user-safe.
type ErrConflict struct{ Code, Message string }
func (e ErrConflict) Error() string { return e.Code + ": " + e.Message }

// ErrUpstream signals an upstream/order failure → 502.
var ErrUpstream = errors.New("upstream unavailable")
```

- [ ] **Step 2: Stubs** (`internal/adapters/checkout/commit_stubs.go`)

```go
package checkout

import (
	"context"
	"sync"

	domain "gj-checkout/internal/domains/checkout"
)

// StubCartValidator: snapshot always valid (no change) in v1.
type StubCartValidator struct{}
func (StubCartValidator) Revalidate(context.Context, domain.Session) (domain.CartValidation, error) {
	return domain.CartValidation{Changed: false}, nil
}

// StubPricer: deterministic totals derived from selection cost.
type StubPricer struct{}
func (StubPricer) Quote(_ context.Context, s domain.Session) (domain.Totals, error) {
	deliv := 0.0
	if s.Selection != nil && s.Selection.Komplektaciya != nil {
		deliv = s.Selection.Komplektaciya.DeliveryCost
	}
	return domain.Totals{Total: 5396 + deliv, DeliveryCost: deliv, Discount: 0, BonusAccrued: 25}, nil
}

// StubOrderSink: idempotent in-memory order book keyed by clientOrderID.
type StubOrderSink struct {
	mu   sync.Mutex
	book map[string]domain.OrderRef
}
func NewStubOrderSink() *StubOrderSink { return &StubOrderSink{book: map[string]domain.OrderRef{}} }
func (o *StubOrderSink) Create(_ context.Context, s domain.Session, _ domain.Totals) (domain.OrderRef, error) {
	o.mu.Lock(); defer o.mu.Unlock()
	if ref, ok := o.book[s.ClientOrderID]; ok { // idempotent
		return ref, nil
	}
	ref := domain.OrderRef{ClientOrderID: s.ClientOrderID, OMSOrderID: "OMS-" + s.ClientOrderID}
	o.book[s.ClientOrderID] = ref
	return ref, nil
}

// StubDiscountSink: idempotent spend ledger keyed by DOC (clientOrderID).
type StubDiscountSink struct {
	mu    sync.Mutex
	spent map[string]bool
}
func NewStubDiscountSink() *StubDiscountSink { return &StubDiscountSink{spent: map[string]bool{}} }
func (d *StubDiscountSink) Spend(_ context.Context, clientOrderID string, _ *domain.PromoIntent) error {
	d.mu.Lock(); defer d.mu.Unlock()
	d.spent[clientOrderID] = true // idempotent no-op on retry
	return nil
}
func (d *StubDiscountSink) Rollback(_ context.Context, clientOrderID string) error {
	d.mu.Lock(); defer d.mu.Unlock()
	delete(d.spent, clientOrderID); return nil
}
```

- [ ] **Step 3: Build + commit**

`go build ./...`.
```bash
git add internal
git commit -m "feat(checkout): commit ports + deterministic stubs (cart/pricer/order/discount)"
```

---

## Task 3: Commit saga in service (TDD)

**Files:** Modify `service.go`, `service_test.go`.

- [ ] **Step 1: Failing tests** (append to `service_test.go`)

```go
func commitSvc(t *testing.T) (*Service, *InMemoryStore) {
	store := NewInMemoryStore()
	svc := NewServiceFull(store, stubSrc{}, stubCart{}, stubPricer{}, newStubOrder(), newStubDiscount())
	return svc, store
}

func TestCommit_happy(t *testing.T) {
	svc, _ := commitSvc(t)
	sess, _ := svc.CreateSession(context.Background(), CreateSessionInput{CustomerID: "c", BasketID: "2000019994"})
	_, _ = svc.SetDeliveryMethod(context.Background(), sess.CheckoutID, DeliveryCourier)

	res, err := svc.Commit(context.Background(), sess.CheckoutID)
	if err != nil { t.Fatalf("Commit: %v", err) }
	if res.Order.OMSOrderID == "" { t.Fatal("expected order ref") }
	if res.Status != StatusCommitted { t.Fatalf("want committed, got %s", res.Status) }
}

func TestCommit_idempotent(t *testing.T) {
	svc, _ := commitSvc(t)
	sess, _ := svc.CreateSession(context.Background(), CreateSessionInput{CustomerID: "c", BasketID: "b1"})
	_, _ = svc.SetDeliveryMethod(context.Background(), sess.CheckoutID, DeliveryCourier)
	r1, _ := svc.Commit(context.Background(), sess.CheckoutID)
	r2, err := svc.Commit(context.Background(), sess.CheckoutID) // retry
	if err != nil { t.Fatalf("retry: %v", err) }
	if r1.Order.OMSOrderID != r2.Order.OMSOrderID { t.Fatal("idempotent commit must return same order") }
}

func TestCommit_conflict_totalsChanged(t *testing.T) {
	svc, store := commitSvc(t)
	sess, _ := svc.CreateSession(context.Background(), CreateSessionInput{CustomerID: "c", BasketID: "b2"})
	_, _ = svc.SetDeliveryMethod(context.Background(), sess.CheckoutID, DeliveryCourier)
	// stale checksum that won't match the pricer quote → 409
	stale := 1.0
	s, _ := store.Get(context.Background(), sess.CheckoutID)
	s.TotalsChecksum = &stale
	_ = store.UpdateDetails(context.Background(), sess.CheckoutID, s)

	_, err := svc.Commit(context.Background(), sess.CheckoutID)
	var conflict ErrConflict
	if !errors.As(err, &conflict) || conflict.Code != "totals_changed" {
		t.Fatalf("want ErrConflict{totals_changed}, got %v", err)
	}
}

func TestCommit_requiresSelection(t *testing.T) {
	svc, _ := commitSvc(t)
	sess, _ := svc.CreateSession(context.Background(), CreateSessionInput{CustomerID: "c", BasketID: "b3"})
	_, err := svc.Commit(context.Background(), sess.CheckoutID) // no delivery chosen
	if !errors.Is(err, ErrInvalidArgument) { t.Fatalf("want ErrInvalidArgument, got %v", err) }
}
```
Add local fakes (`stubCart`, `stubPricer`, `newStubOrder`, `newStubDiscount`) at the end of the test file mirroring the adapter stubs (or import the adapter package — but the domain test importing the adapter would violate the boundary; keep small local fakes in the test).

- [ ] **Step 2: Run → FAIL** (`NewServiceFull`, `Commit` undefined).

- [ ] **Step 3: Implement** (`service.go`)

```go
// Service gains the commit ports.
type Service struct {
	store    SessionStore
	delivery DeliverySource
	cart     CartValidator
	pricer   Pricer
	orders   OrderSink
	discount DiscountSink
}

func NewServiceFull(store SessionStore, d DeliverySource, cv CartValidator, p Pricer, o OrderSink, ds DiscountSink) *Service {
	s := NewServiceWithDelivery(store, d)
	s.cart, s.pricer, s.orders, s.discount = cv, p, o, ds
	return s
}

// Commit creates the order from the chosen komplektaciya. Honest + idempotent.
// One order + spill leftover (current mechanic; §2b). Saga: create → spend → pay.
func (s *Service) Commit(ctx context.Context, checkoutID string) (CommitResult, error) {
	sess, err := s.store.Get(ctx, checkoutID)
	if err != nil {
		return CommitResult{}, err
	}
	// idempotent: already committed → return the existing order ref.
	if sess.Status == StatusCommitted {
		ref, _ := s.orders.Create(ctx, sess, Totals{}) // book is keyed by clientOrderID → returns existing
		return CommitResult{Order: ref, Status: StatusCommitted}, nil
	}
	if sess.Selection == nil || sess.Selection.Komplektaciya == nil {
		return CommitResult{}, fmt.Errorf("%w: delivery method not selected", ErrInvalidArgument)
	}

	// 1. re-validate cart/stock (no pre-reserve; §2a)
	cv, err := s.cart.Revalidate(ctx, sess)
	if err != nil {
		return CommitResult{}, fmt.Errorf("%w: %w", ErrUpstream, err)
	}
	if cv.Changed {
		return CommitResult{}, ErrConflict{Code: "cart_changed", Message: "cart changed, please review"}
	}

	// 2. reconcile delivery with PINNED date (re-resolve; v1 stub is stable).
	// (real adapter: re-fetch with Selection.PinnedDate; if interval id drifts → conflict.)

	// 3. two-phase truth: re-derive totals server-side, compare to last-shown checksum.
	totals, err := s.pricer.Quote(ctx, sess)
	if err != nil {
		return CommitResult{}, fmt.Errorf("%w: %w", ErrUpstream, err)
	}
	if sess.TotalsChecksum != nil && *sess.TotalsChecksum != totals.Total {
		return CommitResult{}, ErrConflict{Code: "totals_changed", Message: "total changed, please confirm"}
	}

	// 4–5. build clean payload (implicit in OrderSink.Create) + durable saga.
	sess.Status = StatusCommitting
	_ = s.store.UpdateDetails(ctx, checkoutID, sess)

	ref, err := s.orders.Create(ctx, sess, totals) // idempotent by clientOrderID
	if err != nil {
		sess.Status = StatusFailed
		_ = s.store.UpdateDetails(ctx, checkoutID, sess)
		return CommitResult{}, fmt.Errorf("%w: order create: %w", ErrUpstream, err)
	}
	if err := s.discount.Spend(ctx, sess.ClientOrderID, sess.Promo); err != nil {
		// compensation: order exists, discount failed → roll back order intent in real impl.
		_ = s.discount.Rollback(ctx, sess.ClientOrderID)
		sess.Status = StatusFailed
		_ = s.store.UpdateDetails(ctx, checkoutID, sess)
		return CommitResult{}, fmt.Errorf("%w: discount spend: %w", ErrUpstream, err)
	}

	// 6. spill leftover → new basket (current mechanic). v1 stub: no-op (logged).
	// 7. done.
	sess.Status = StatusCommitted
	_ = s.store.UpdateDetails(ctx, checkoutID, sess)

	token := ""
	if sess.Payment == PaySBP || sess.Payment == PayCardOnline {
		token = "stub-payment-token-" + sess.ClientOrderID // real: getlink token
	}
	return CommitResult{Order: ref, PaymentToken: token, Status: StatusCommitted}, nil
}
```
> Update `wire.Checkout` (Task 5) to use `NewServiceFull`. Keep `NewServiceWithDelivery` for Plan 3 tests.

- [ ] **Step 4: Run → PASS** (`go test ./internal/domains/checkout/ -run TestCommit -v`). Commit.

```bash
git add internal/domains/checkout/{service.go,service_test.go}
git commit -m "feat(checkout): commit saga — revalidate/reconcile/checksum/create/spend, honest+idempotent (TDD)"
```

---

## Task 4: Commit endpoint — honest status mapping

**Files:** OpenAPI (`POST /checkout/{id}/commit` → `CommitResult` | 409/4xx), `handler.go`, `routes.go`, `handler_test.go`.

- [ ] **Step 1: Failing handler test** (append `handler_test.go`)

```go
func TestCommit_409_onConflict(t *testing.T) {
	// service whose pricer returns a total != stale checksum → ErrConflict
	store := NewInMemoryStore()
	svc := NewServiceFull(store, stubSrc{}, stubCart{}, conflictPricer{}, newStubOrder(), newStubDiscount())
	h := NewHandler(svc, httpx.NewHelper())
	sess, _ := svc.CreateSession(context.Background(), CreateSessionInput{CustomerID: "c", BasketID: "b"})
	_, _ = svc.SetDeliveryMethod(context.Background(), sess.CheckoutID, DeliveryCourier)
	stale := 1.0; s, _ := store.Get(context.Background(), sess.CheckoutID); s.TotalsChecksum = &stale; _ = store.UpdateDetails(context.Background(), sess.CheckoutID, s)

	req := httptest.NewRequest(http.MethodPost, "/api/v1/checkout/"+sess.CheckoutID+"/commit", nil)
	rctx := chi.NewRouteContext(); rctx.URLParams.Add("checkout_id", sess.CheckoutID)
	req = req.WithContext(context.WithValue(req.Context(), chi.RouteCtxKey, rctx))
	rec := httptest.NewRecorder()
	h.Commit(rec, req)
	if rec.Code != http.StatusConflict { t.Fatalf("want 409, got %d: %s", rec.Code, rec.Body.String()) }
	if !strings.Contains(rec.Body.String(), `"error":"totals_changed"`) { t.Fatalf("body: %s", rec.Body.String()) }
}
```
(add `conflictPricer` fake returning a non-matching total.)

- [ ] **Step 2: Run → FAIL.** Implement `handler.go`:

```go
// Commit handles POST /api/v1/checkout/{checkout_id}/commit. HONEST status:
// 201 created | 409 conflict | 400 invalid | 404 | 502 upstream | 500. NEVER 200+success:false.
func (h *Handler) Commit(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "checkout_id")
	res, err := h.service.Commit(r.Context(), id)
	if err != nil {
		var conflict ErrConflict
		switch {
		case errors.As(err, &conflict):
			h.errs.JSON(w, http.StatusConflict, conflict.Code, conflict.Message)
		case errors.Is(err, ErrNotFound):
			h.errs.JSON(w, http.StatusNotFound, "not_found", "session not found")
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
```
Write `toCommitDTO` (CommitResult → `apiv1.CommitResult{OrderId, ClientOrderId, PaymentToken, Status}`). Add route `rr.Post("/{checkout_id}/commit", deps.Handler.Commit)`. Run `make generate && make lint`.

- [ ] **Step 3: Run → PASS + commit**

```bash
git add api internal/domains/checkout
git commit -m "feat(checkout): POST /commit endpoint — honest status (201/409/4xx), never 200-mask"
```

---

## Task 5: Wire + full e2e + DoD

- [ ] **Step 1: Wire all stubs** (`internal/app/wire/checkout.go`)

```go
src := adapter.NewStubDeliverySource()
svc := checkout.NewServiceFull(
	store, src,
	adapter.StubCartValidator{}, adapter.StubPricer{},
	adapter.NewStubOrderSink(), adapter.NewStubDiscountSink(),
)
return checkout.NewHandler(svc, errs)
```

- [ ] **Step 2: Full e2e (the walking skeleton, end to end)**

```bash
make migrate && make run
ID=$(curl -s -X POST :8080/api/v1/checkout -d '{"customer_id":"c1","basket_id":"2000019994"}' | jq -r .checkout_id)
curl -s :8080/api/v1/checkout/$ID/delivery-options | jq '.methods[].coverage'
curl -s -X PATCH :8080/api/v1/checkout/$ID/delivery-method -d '{"type":"courier"}' >/dev/null
curl -s -X PATCH :8080/api/v1/checkout/$ID/recipient -d '{"first_name":"A","last_name":"B","phone":"+7900"}' >/dev/null
curl -s -X PATCH :8080/api/v1/checkout/$ID/payment-method -d '{"type":"sbp"}' >/dev/null
curl -is -X POST :8080/api/v1/checkout/$ID/commit | head -1          # 201
curl -s  -X POST :8080/api/v1/checkout/$ID/commit | jq '{order:.oms_order_id, status}'  # idempotent: same order
```
Expected: commit → `201` with `oms_order_id`, `status:"committed"`; retry → same order (idempotent); a stale-checksum/no-selection path → `409`/`400` (verify via unit tests).

- [ ] **Step 3: Full gates + tag**

`go test ./...` (+ integration with `CHECKOUT_TEST_DB_DSN`), `make generate && make lint && go vet ./...`, `make docker`.
```bash
git commit -am "test(checkout): full create→select→commit e2e on stubs green" --allow-empty
git tag v0.1.0
```

## Definition of Done (Plan 4 = v1 walking skeleton complete)
- Full flow on stubs: create → delivery-options → delivery-method (pinned) → recipient/address/promo/payment → **commit**.
- Commit is **honest**: `201` created | `409` `{cart_changed|totals_changed}` | `400` no-selection | `502` upstream | never `200 {success:false}`.
- Commit is **idempotent** by `client_order_id` (retry → same order; no double spend).
- Saga shape (create → spend → pay) with compensation hook; spill is a documented no-op stub.
- All stub ports deterministic; `go test ./...`, `make generate/lint`, `vet`, `docker` green; tagged `v0.1.0`.

---

## v1 → phase 2 handoff (after walking skeleton)
- Replace stub ports with real adapters in `internal/adapters/checkout/` over the published clients: `starfish-oms` (DeliverySource real: call OMS → existing `normalize*` funcs; OrderSink: `/order/create`; payment getlink), `baskets`/`offers` (CartValidator/Pricer), `discount` (DiscountSink: GetDiscount quote + BonusSpend, idempotent by DOC). Wire switches stub↔real by config (mirror ecom-gateway `RECOMMENDATIONS_HYDRATOR` pattern).
- Then Track B: `clients/checkout` + ecom-gateway onboarding (backlog `2026-05-30-starfish-client-and-gateway-prep-backlog.md`).
