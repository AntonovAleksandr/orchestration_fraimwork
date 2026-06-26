# Checkout Increment 5 — Every command returns full CheckoutState

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every mutating command (`PATCH delivery-method`, `PATCH recipient`, `PATCH payment-method`, `PATCH promo`) return the full authoritative `CheckoutState` (ADR-0001) instead of a slim per-domain `Applied*` delta — closing frontend Pain #1 (single authoritative session, no client re-stitching).

**Architecture:** Extract the read-model assembly that already lives inline in `session.Handler.Get` into a reusable `session.StateAssembler` (session aggregate + live cart + delivery digest + re-quoted totals → `apiv1.CheckoutState`). The session domain stays the single owner of the `CheckoutState` projection. Each capability domain (delivery/recipient/payment/pricing) gains a narrow consumer-defined port `StateView` that returns the assembled state as an opaque `any` — so the capability never imports `session` (boundary_test stays green). One `wire.stateAssemblerView` adapter (its method set satisfies all four `StateView` interfaces structurally) bridges the port to the assembler. Each capability handler, after a successful mutation, asks the port to assemble and writes the full state. The OpenAPI contract for the four PATCH responses is re-pointed from the slim `Applied*` schemas to the shared `checkout.yaml#/CheckoutState`.

**Tech Stack:** Go 1.26, chi v5, oapi-codegen v2.4.1 (types-only, per-domain `include-tags` over a bundled spec), redocly CLI (lint/bundle), pgx v5. Money: **int64 kopecks internally, rubles on the wire to the frontend** (unchanged — the edge conversion `kopecksToRubles` already lives in the projection).

**Repo:** `platform-new/checkout` (local clients resolved via `go.work`; live runs via `make port-forward` + `.env`). Money discipline and the CheckoutState contract are governed by `checkout/docs/architecture/adr/0001-checkout-state-contract.md`.

**Boundary invariant (do not break):** `internal/domains/<capability>` must not import `gj-checkout/internal/domains/...` (enforced per-domain by `boundary_test.go`). The `any`-typed `StateView` port is what keeps this true — the capability handler JSON-encodes the assembled value without naming `session/apiv1.CheckoutState`.

---

## File Structure

**Created:**
- `internal/domains/session/assembler.go` — `StateAssembler` type + `Assemble` + the read-model projection funcs moved out of `handler.go`.
- `internal/app/wire/state.go` — `stateAssemblerView` adapter (`AssembleState(ctx, id) (any, error)`), satisfies all four capability `StateView` ports.

**Modified:**
- `internal/domains/session/handler.go` — drop the 3 reader fields + `With*` methods + projection funcs; hold `*StateAssembler`; `Get` delegates to it.
- `internal/app/wire/session.go` — add `StateAssembler(...)` builder; slim `SessionHandler(...)`.
- `internal/app/wire/{delivery,recipient,payment,pricing}.go` — builders accept `asm *session.StateAssembler`, inject `stateAssemblerView{asm}`.
- `internal/app/container.go` — build the assembler once, pass to all handler builders.
- `internal/domains/{delivery,recipient,payment,pricing}/types.go` — add `StateView` port.
- `internal/domains/{delivery,recipient,payment,pricing}/handler.go` — store the port; flip the PATCH method to assemble + write full state; drop the slim DTO mapping + now-unused imports.
- `api/v1/paths/{delivery,payment,recipient,pricing}.yaml` — PATCH 200 response → `checkout.yaml#/CheckoutState`.
- `api/v1/components/schemas/{delivery,recipient,payment,pricing}.yaml` — remove the now-unreferenced `Applied*` response schemas.
- `internal/domains/{delivery,recipient,payment,pricing}/apiv1/openapi.gen.go` — regenerated (`make generate`).
- `internal/platform/transport/e2e_test.go` — PATCH responses now decode as `sessionapiv1.CheckoutState`; assert full-state fields.

---

## Task 1: Extract `session.StateAssembler` (pure refactor — GET behaviour unchanged)

**Files:**
- Create: `internal/domains/session/assembler.go`
- Modify: `internal/domains/session/handler.go`
- Modify: `internal/app/wire/session.go`
- Modify: `internal/app/container.go:55-62`
- Modify: `internal/platform/transport/e2e_test.go:38` (session handler construction in `buildDeps`)
- Create/extend test: `internal/domains/session/assembler_test.go`

- [ ] **Step 1: Create `assembler.go` with the type + builders + `Assemble`, moving the projection funcs out of `handler.go`.**

Create `internal/domains/session/assembler.go`:

```go
package session

import (
	"context"
	"encoding/json"
	"strings"

	"github.com/google/uuid"

	"gj-checkout/internal/domains/session/apiv1"
)

// StateAssembler builds the CheckoutState read-model (ADR-0001): the session
// aggregate plus three OPTIONAL, best-effort projections — live cart, per-method
// delivery digest, and re-quoted totals. It is the single owner of the
// CheckoutState projection; the session GET handler and every capability command
// (delivery/recipient/payment/promo) render their response through it.
type StateAssembler struct {
	service *Service
	cart    CartReader   // optional; nil → CheckoutState.cart stays null
	digest  DigestReader // optional; nil → CheckoutState.delivery.methods empty
	totals  TotalsReader // optional; nil → CheckoutState.totals stays null
}

// NewStateAssembler constructs an assembler over the session service. Readers are
// attached via the With* builders (wired in app/wire).
func NewStateAssembler(service *Service) *StateAssembler {
	if service == nil {
		panic("session: NewStateAssembler requires a non-nil Service")
	}
	return &StateAssembler{service: service}
}

// WithCartReader attaches a live cart reader (baskets + catalog-cache).
func (a *StateAssembler) WithCartReader(c CartReader) *StateAssembler { a.cart = c; return a }

// WithDigestReader attaches a per-method delivery digest reader.
func (a *StateAssembler) WithDigestReader(d DigestReader) *StateAssembler { a.digest = d; return a }

// WithTotalsReader attaches a totals re-quoter.
func (a *StateAssembler) WithTotalsReader(t TotalsReader) *StateAssembler { a.totals = t; return a }

// Assemble loads the session and projects the full CheckoutState. The session
// fetch is authoritative (ErrNotFound propagates); cart/digest/totals are
// best-effort — an upstream failure leaves that section empty rather than failing
// the whole render.
func (a *StateAssembler) Assemble(ctx context.Context, checkoutID string) (apiv1.CheckoutState, error) {
	sess, err := a.service.GetSession(ctx, checkoutID)
	if err != nil {
		return apiv1.CheckoutState{}, err
	}

	var cart []CartItem
	if a.cart != nil && sess.CustomerID != "" {
		if items, cErr := a.cart.ResolveCart(ctx, sess.CustomerID); cErr == nil {
			cart = items
		}
	}
	var methods []DeliveryMethodView
	if a.digest != nil {
		if ms, dErr := a.digest.ReadDeliveryDigest(ctx, sess.CheckoutID); dErr == nil {
			methods = ms
		}
	}
	var totals *TotalsView
	if a.totals != nil {
		var dc int64
		promo, burn := "", false
		if sess.Selection != nil {
			dc = sess.Selection.DeliveryCostKopecks
		}
		if sess.Promo != nil {
			promo, burn = sess.Promo.PromoCode, sess.Promo.BurnBonus
		}
		if tv, tErr := a.totals.ReadTotals(ctx, dc, promo, burn); tErr == nil {
			totals = tv
		}
	}
	return toCheckoutStateDTO(sess, cart, methods, totals), nil
}

// internal delivery type → OMS-aligned (CheckoutState canon: delivery/pickup/…).
var omsDeliveryType = map[string]string{
	"courier":       "delivery",
	"pvz":           "pickup",
	"store_pickup":  "pickupinstore",
	"store_reserve": "reserveinstore",
}

// internal PaymentMethod → frontend OrderPaymentTypeEnum (prepaid/cod/sbp).
var frontendPayment = map[PaymentMethod]apiv1.CheckoutPaymentSelected{
	PaymentSBP:        apiv1.CheckoutPaymentSelectedSbp,
	PaymentCardOnline: apiv1.CheckoutPaymentSelectedPrepaid,
	PaymentOnReceipt:  apiv1.CheckoutPaymentSelectedCod,
}

func kopecksToRubles(k int64) float32 { return float32(k) / 100 }

// toCheckoutStateDTO projects the session aggregate + read-model sections into the
// CheckoutState read-model (ADR-0001). Money → RUBLES at this edge (internal
// kopecks ÷100).
func toCheckoutStateDTO(s Session, cart []CartItem, methods []DeliveryMethodView, totals *TotalsView) apiv1.CheckoutState {
	st := apiv1.CheckoutState{
		CheckoutId:    uuid.MustParse(s.CheckoutID),
		ClientOrderId: s.ClientOrderID,
		CustomerId:    s.CustomerID,
		BasketId:      s.BasketID,
		Status:        apiv1.CheckoutStateStatus(s.Status),
		Cart:          toCartDTO(cart),
		Delivery:      apiv1.CheckoutDelivery{Methods: toDeliveryMethodsDTO(methods)},
		Totals:        toTotalsDTO(totals),
		Payment: apiv1.CheckoutPayment{Methods: []apiv1.CheckoutPaymentMethods{
			apiv1.CheckoutPaymentMethodsPrepaid,
			apiv1.CheckoutPaymentMethodsCod,
			apiv1.CheckoutPaymentMethodsSbp,
		}},
	}
	if sel := s.Selection; sel != nil {
		cost := kopecksToRubles(sel.DeliveryCostKopecks)
		cov := sel.Coverage
		pinned := sel.PinnedDispatchDate
		st.Delivery.Selected = &apiv1.CheckoutSelectedDelivery{
			Type:       apiv1.CheckoutSelectedDeliveryType(omsDeliveryType[sel.DeliveryType]),
			PinnedDate: &pinned,
			Coverage:   &cov,
			Cost:       &cost,
			Point:      pointFromSnapshot(sel.Snapshot),
		}
	}
	if r := s.Recipient; r != nil {
		name := strings.TrimSpace(r.FirstName + " " + r.LastName)
		ph := r.Phone
		st.Recipient = &apiv1.CheckoutRecipient{Name: &name, Phone: &ph}
	}
	if p, ok := frontendPayment[s.PaymentMethod]; ok {
		sel := p
		st.Payment.Selected = &sel
	}
	return st
}

// toCartDTO projects the resolved enriched cart into CheckoutState.cart. Money →
// RUBLES. Returns nil when the cart is empty/unresolved.
func toCartDTO(items []CartItem) *apiv1.CheckoutCart {
	if len(items) == 0 {
		return nil
	}
	products := make([]apiv1.CheckoutCartProduct, 0, len(items))
	countSelected := 0
	for _, it := range items {
		if it.IsSelected {
			countSelected++
		}
		price := kopecksToRubles(it.PriceKopecks)
		cur := apiv1.CheckoutCartSize{OfferId: it.OfferID, Price: &price}
		if it.VendorCodeSKU != "" {
			sku := it.VendorCodeSKU
			cur.VendorCodeSku = &sku
		}
		p := apiv1.CheckoutCartProduct{
			Name:       it.Name,
			Qty:        it.Quantity,
			IsSelected: it.IsSelected,
			Image:      it.ImageID,
			Current:    &cur,
		}
		if it.VendorCodeCC != "" {
			cc := it.VendorCodeCC
			p.VendorCodeCc = &cc
		}
		products = append(products, p)
	}
	return &apiv1.CheckoutCart{Products: products, Count: len(products), CountSelected: countSelected}
}

// toTotalsDTO projects the re-quoted totals into CheckoutState.totals (RUBLES).
func toTotalsDTO(t *TotalsView) *apiv1.CheckoutTotals {
	if t == nil {
		return nil
	}
	items := kopecksToRubles(t.ItemsKopecks)
	disc := kopecksToRubles(t.DiscountKopecks)
	deliv := kopecksToRubles(t.DeliveryKopecks)
	grand := kopecksToRubles(t.GrandTotalKopecks)
	return &apiv1.CheckoutTotals{Items: &items, Discount: &disc, Delivery: &deliv, GrandTotal: &grand}
}

// toDeliveryMethodsDTO projects the per-method digest into CheckoutState.delivery.methods.
func toDeliveryMethodsDTO(views []DeliveryMethodView) []apiv1.CheckoutDeliveryMethod {
	out := make([]apiv1.CheckoutDeliveryMethod, 0, len(views))
	for _, v := range views {
		cov, cs, md := v.Coverage, v.CartSize, v.MinDays
		mc := kopecksToRubles(v.MinCostKopecks)
		fr := kopecksToRubles(v.FreeThresholdKopecks)
		m := apiv1.CheckoutDeliveryMethod{
			Type:          apiv1.CheckoutDeliveryMethodType(omsDeliveryType[v.Type]),
			Available:     v.Available,
			Coverage:      &cov,
			CartSize:      &cs,
			MinCost:       &mc,
			MinDays:       &md,
			FreeThreshold: &fr,
		}
		if v.EarliestPromisedDate != "" {
			epd := v.EarliestPromisedDate
			m.EarliestPromisedDate = &epd
		}
		if len(v.PaymentTypes) > 0 {
			pt := append([]string(nil), v.PaymentTypes...)
			m.PaymentTypes = &pt
		}
		out = append(out, m)
	}
	return out
}

// pointFromSnapshot reads the chosen point's display fields from the stored
// komplektaciya snapshot. Returns nil if absent/empty.
func pointFromSnapshot(raw json.RawMessage) *apiv1.CheckoutPoint {
	if len(raw) == 0 {
		return nil
	}
	var snap struct {
		Point struct {
			WarehouseID, StoreCode, PickupPointID, CarrierID, Name, Address string
			Lat, Lng                                                        float64
		}
	}
	if err := json.Unmarshal(raw, &snap); err != nil {
		return nil
	}
	p, pt, set := snap.Point, &apiv1.CheckoutPoint{}, false
	str := func(dst **string, v string) {
		if v != "" {
			s := v
			*dst = &s
			set = true
		}
	}
	str(&pt.WarehouseId, p.WarehouseID)
	str(&pt.StoreCode, p.StoreCode)
	str(&pt.PickupPointId, p.PickupPointID)
	str(&pt.Name, p.Name)
	str(&pt.Address, p.Address)
	if p.CarrierID != "" {
		c := apiv1.CheckoutPointCarrierId(p.CarrierID)
		pt.CarrierId = &c
		set = true
	}
	if p.Lat != 0 {
		pt.Lat = &p.Lat
		set = true
	}
	if p.Lng != 0 {
		pt.Lng = &p.Lng
		set = true
	}
	if !set {
		return nil
	}
	return pt
}
```

- [ ] **Step 2: Slim down `handler.go` — hold the assembler, delegate `Get`, delete the moved code.**

In `internal/domains/session/handler.go`:

1. Replace the `Handler` struct + `NewHandler` + the three `With*` methods (lines 16–46) with:

```go
// Handler is the HTTP edge for the checkout bounded context.
type Handler struct {
	service   *Service
	assembler *StateAssembler
	errs      *httpx.Helper
}

// NewHandler constructs a Handler. The assembler renders the CheckoutState
// read-model for GET (and is shared with the capability commands via app/wire).
func NewHandler(service *Service, errs *httpx.Helper, assembler *StateAssembler) *Handler {
	if assembler == nil {
		panic("session: NewHandler requires a non-nil StateAssembler")
	}
	return &Handler{service: service, assembler: assembler, errs: errs}
}
```

2. Replace the `Get` method body (lines 89–131) with:

```go
// Get handles GET /api/v1/checkout/{checkout_id} — full CheckoutState (ADR-0001).
func (h *Handler) Get(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "checkout_id")
	state, err := h.assembler.Assemble(r.Context(), id)
	if err != nil {
		if errors.Is(err, ErrNotFound) {
			h.errs.JSON(w, http.StatusNotFound, "not_found", "checkout session not found")
			return
		}
		h.errs.Internal(w, "internal", "internal error")
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(state)
}
```

3. Delete from `handler.go` (now living in `assembler.go`): `omsDeliveryType`, `frontendPayment`, `toCheckoutStateDTO`, `kopecksToRubles`, `toCartDTO`, `toTotalsDTO`, `toDeliveryMethodsDTO`, `pointFromSnapshot` (lines ~186–370). KEEP `Create`, `Commit`, `toCommitDTO`, `toSessionDTO`.

4. Fix imports: `handler.go` keeps `encoding/json`, `errors`, `net/http`, `strings`? — `strings` was only used by the moved `toCheckoutStateDTO`; **remove `strings` from handler.go imports**. `toSessionDTO` still uses `uuid` → keep `uuid`. Keep `chi`, `apiv1`, `httpx`.

- [ ] **Step 3: Add `wire.StateAssembler` builder + slim `wire.SessionHandler`.**

In `internal/app/wire/session.go`, replace `SessionHandler` (lines 32–47) with:

```go
// StateAssembler builds the CheckoutState read-model assembler, wiring the live
// cart resolver (when configured), the delivery digest reader, and the v1 totals
// re-quoter (stub, matched to the commit-saga pricer). Shared by the session GET
// handler AND every capability command's full-state response.
func StateAssembler(svc *session.Service, resolver *cartadapter.Resolver, deliverySvc *delivery.Service) *session.StateAssembler {
	a := session.NewStateAssembler(svc)
	if resolver != nil {
		a.WithCartReader(sessionCartReader{r: resolver})
	}
	if deliverySvc != nil {
		a.WithDigestReader(sessionDigestReader{svc: deliverySvc})
	}
	a.WithTotalsReader(sessionTotalsReader{quoter: pricing.StubQuoter{}})
	return a
}

// SessionHandler builds the session HTTP handler over the shared service + assembler.
func SessionHandler(svc *session.Service, errs *httpx.Helper, asm *session.StateAssembler) *session.Handler {
	return session.NewHandler(svc, errs, asm)
}
```

(The bridge types `sessionCartReader`, `sessionDigestReader`, `sessionTotalsReader` stay where they are — `sessionTotalsReader`+`sessionCartReader` in `session.go`, `sessionDigestReader` in `delivery.go`. They are now consumed by `StateAssembler` instead of by `SessionHandler`.) Imports in `session.go` are unchanged.

- [ ] **Step 4: Build the assembler once in the container.**

In `internal/app/container.go`, replace lines 55–62 with:

```go
	sessionSvc := wire.SessionService(pool)
	cartRes := wire.BuildCartResolver(cfg) // shared by read-model assembler + delivery
	deliverySvc := wire.DeliveryService(sessionSvc, cfg, cartRes)
	asm := wire.StateAssembler(sessionSvc, cartRes, deliverySvc)
	c.DeliveryHandler = wire.DeliveryHandler(deliverySvc, c.ErrorsHelper)
	c.SessionHandler = wire.SessionHandler(sessionSvc, c.ErrorsHelper, asm)
	c.RecipientHandler = wire.Recipient(sessionSvc, c.ErrorsHelper)
	c.PaymentHandler = wire.Payment(sessionSvc, c.ErrorsHelper)
	c.PricingHandler = wire.Pricing(sessionSvc, c.ErrorsHelper)
```

(Only `SessionHandler` changes signature in this task. The capability builders gain `asm` in Tasks 2–5.)

- [ ] **Step 5: Update `buildDeps` in the e2e test to construct the assembler.**

In `internal/platform/transport/e2e_test.go`, replace line 38 (`sh := session.NewHandler(svc, errs)`) and the delivery line 39 so the assembler is built and shared:

```go
	deliverySvc := wire.DeliveryService(svc, config.Config{}, nil) // stub source, no network
	asm := wire.StateAssembler(svc, nil, deliverySvc)
	sh := session.NewHandler(svc, errs, asm)
	dh := wire.DeliveryHandler(deliverySvc, errs)
```

- [ ] **Step 6: Write a focused assembler unit test.**

Create `internal/domains/session/assembler_test.go`:

```go
package session

import (
	"context"
	"testing"
)

func TestStateAssembler_AssembleCore(t *testing.T) {
	store := NewInMemoryStore()
	svc := NewService(store)
	asm := NewStateAssembler(svc) // no readers → cart/methods/totals empty

	created, err := svc.CreateSession(context.Background(), CreateSessionInput{CustomerID: "cust-1", BasketID: "basket-1"})
	if err != nil {
		t.Fatalf("create: %v", err)
	}

	st, err := asm.Assemble(context.Background(), created.CheckoutID)
	if err != nil {
		t.Fatalf("assemble: %v", err)
	}
	if st.CheckoutId.String() != created.CheckoutID {
		t.Fatalf("checkout_id: want %q, got %q", created.CheckoutID, st.CheckoutId.String())
	}
	if string(st.Status) != string(StatusDraft) {
		t.Fatalf("status: want draft, got %q", st.Status)
	}
	if st.Cart != nil {
		t.Fatalf("cart: want nil (no reader), got %+v", st.Cart)
	}
	if len(st.Payment.Methods) != 3 {
		t.Fatalf("payment.methods: want 3, got %d", len(st.Payment.Methods))
	}
}

func TestStateAssembler_AssembleNotFound(t *testing.T) {
	asm := NewStateAssembler(NewService(NewInMemoryStore()))
	if _, err := asm.Assemble(context.Background(), "00000000-0000-0000-0000-000000000000"); err == nil {
		t.Fatal("expected ErrNotFound for unknown checkout")
	}
}
```

> Note: confirm the in-memory store constructor name is `NewInMemoryStore` (used in `e2e_test.go:34`). If `stub.go` exports a different name, match it.

- [ ] **Step 7: Verify build, tests, and no contract drift.**

Run: `cd platform-new/checkout && go build ./... && go vet ./... && go test ./...`
Expected: PASS (assembler tests green; existing `handler_test.go`, `service_test.go`, both e2e tests green — GET behaviour is unchanged).

Run: `make generate && git diff --stat -- internal/domains/*/apiv1/`
Expected: NO diff (no OpenAPI change in this task).

Run: `make lint`
Expected: redocly lint clean.

- [ ] **Step 8: Commit.**

```bash
git add internal/domains/session/assembler.go internal/domains/session/assembler_test.go \
        internal/domains/session/handler.go internal/app/wire/session.go \
        internal/app/container.go internal/platform/transport/e2e_test.go
git commit -m "refactor(session): extract StateAssembler from GET handler (inc 5 prep)"
```

---

## Task 2: Delivery `PATCH delivery-method` → full CheckoutState

**Files:**
- Create: `internal/app/wire/state.go`
- Modify: `internal/domains/delivery/types.go` (add `StateView` port)
- Modify: `internal/domains/delivery/handler.go` (flip `SetDeliveryMethod`; drop `toAppliedDTO` + `uuid` import)
- Modify: `internal/app/wire/delivery.go` (`DeliveryHandler` takes `asm`)
- Modify: `internal/app/container.go` (pass `asm` to `DeliveryHandler`)
- Modify: `internal/platform/transport/e2e_test.go:39` (`dh := wire.DeliveryHandler(deliverySvc, errs, asm)`)
- Modify: `api/v1/paths/delivery.yaml` (PATCH 200 → CheckoutState)
- Modify: `api/v1/components/schemas/delivery.yaml` (remove `AppliedSelection` + `DeliverySelection`)
- Regenerate: `internal/domains/delivery/apiv1/openapi.gen.go`

- [ ] **Step 1: Create the shared `wire.stateAssemblerView` adapter.**

Create `internal/app/wire/state.go`:

```go
package wire

import (
	"context"

	"gj-checkout/internal/domains/session"
)

// stateAssemblerView adapts *session.StateAssembler to the capability domains'
// StateView ports. Its single method `AssembleState(ctx, id) (any, error)` has the
// same signature in delivery/recipient/payment/pricing, so this one type satisfies
// all four interfaces structurally. The `any` return is what keeps the boundary
// intact — a capability handler JSON-encodes the value without naming
// session/apiv1.CheckoutState (which it may not import; see boundary_test).
type stateAssemblerView struct{ asm *session.StateAssembler }

func (v stateAssemblerView) AssembleState(ctx context.Context, checkoutID string) (any, error) {
	return v.asm.Assemble(ctx, checkoutID)
}
```

- [ ] **Step 2: Add the `StateView` port to the delivery domain.**

In `internal/domains/delivery/types.go`, add:

```go
// StateView assembles the full CheckoutState for a checkout session (ADR-0001:
// command → full state). Consumer-defined port; the session StateAssembler
// implements it via the app/wire bridge. The return is `any` (the assembled
// session/apiv1.CheckoutState) — delivery must not import the session domain.
type StateView interface {
	AssembleState(ctx context.Context, checkoutID string) (any, error)
}
```

> Confirm `context` is already imported in `delivery/types.go`; add it if not.

- [ ] **Step 3: Flip the delivery handler to return full state.**

In `internal/domains/delivery/handler.go`:

1. Add a field + constructor param:

```go
// Handler is the HTTP edge for the delivery domain.
type Handler struct {
	service *Service
	state   StateView
	errs    *httpx.Helper
}

// NewHandler constructs a Handler. `state` renders the full CheckoutState returned
// by the delivery-method command (ADR-0001).
func NewHandler(service *Service, state StateView, errs *httpx.Helper) *Handler {
	return &Handler{service: service, state: state, errs: errs}
}
```

2. Replace `SetDeliveryMethod` (the `applied, err := ...` + `writeJSON(... toAppliedDTO(applied))` tail) so it assembles after mutating:

```go
// SetDeliveryMethod handles PATCH /api/v1/checkout/{checkout_id}/delivery-method.
// Mutates the session (auto-resolve best komplektaciya + pin dispatch_date), then
// returns the full CheckoutState (ADR-0001).
func (h *Handler) SetDeliveryMethod(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "checkout_id")
	var body apiv1.SetDeliveryMethodRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		h.errs.BadRequest(w, "invalid_argument", "malformed JSON body")
		return
	}
	t := DeliveryType(body.Type)
	if !validType(t) {
		h.errs.BadRequest(w, "invalid_argument", "unknown delivery type")
		return
	}
	if _, err := h.service.SetDeliveryMethod(r.Context(), id, t); err != nil {
		h.writeErr(w, err)
		return
	}
	state, err := h.state.AssembleState(r.Context(), id)
	if err != nil {
		// The session was just mutated successfully; an assemble failure is an
		// infra error (not a client/not-found case) → 500.
		h.errs.Internal(w, "internal", "internal error")
		return
	}
	writeJSON(w, http.StatusOK, state)
}
```

3. Delete `toAppliedDTO` (lines ~233–247) and remove the `"github.com/google/uuid"` import (it was only used there).

- [ ] **Step 4: Wire the assembler into `DeliveryHandler`.**

In `internal/app/wire/delivery.go`, change `DeliveryHandler`:

```go
// DeliveryHandler builds the delivery HTTP handler over an already-constructed
// service + the shared state assembler (full-state command responses).
func DeliveryHandler(svc *delivery.Service, errs *httpx.Helper, asm *session.StateAssembler) *delivery.Handler {
	return delivery.NewHandler(svc, stateAssemblerView{asm: asm}, errs)
}
```

> `session` is already imported in `delivery.go`.

- [ ] **Step 5: Update the container + e2e wiring for the new signature.**

In `internal/app/container.go`, change the delivery line:

```go
	c.DeliveryHandler = wire.DeliveryHandler(deliverySvc, c.ErrorsHelper, asm)
```

In `internal/platform/transport/e2e_test.go`, change the delivery handler build (in `buildDeps`):

```go
	dh := wire.DeliveryHandler(deliverySvc, errs, asm)
```

- [ ] **Step 6: Re-point the contract — delivery PATCH 200 → CheckoutState.**

In `api/v1/paths/delivery.yaml`, the `DeliveryMethod.patch.responses.200` block (lines 67–69) becomes:

```yaml
      "200":
        description: Full checkout state (authoritative core, ADR-0001)
        content: { application/json: { schema: { $ref: "../components/schemas/checkout.yaml#/CheckoutState" } } }
```

In `api/v1/components/schemas/delivery.yaml`, **delete** the now-unreferenced `AppliedSelection` and `DeliverySelection` schemas (keep `SetDeliveryMethodRequest`, `DeliveryDigest`, `MethodSummary`, `Komplektaciya`, `KomplektaciyaList`, `ClusterResult`, `Cluster`, `Point`, `Features`, `ItemAvail`, and any other still-referenced types). Verify nothing else `$ref`s `DeliverySelection`/`AppliedSelection`: `grep -rn "AppliedSelection\|DeliverySelection" api/`.

- [ ] **Step 7: Regenerate DTOs.**

Run: `cd platform-new/checkout && make generate`
Expected: `internal/domains/delivery/apiv1/openapi.gen.go` regenerated — `AppliedSelection`/`DeliverySelection` types removed (pruned), `CheckoutState` + its transitive schemas (`CheckoutCart*`, `CheckoutDelivery*`, `CheckoutSelectedDelivery`, `CheckoutPoint`, `CheckoutPayment`, `CheckoutTotals`, `CheckoutRecipient`) now generated into `delivery/apiv1` (mechanical; unused by the handler, which writes the session-assembled value via `any` — they document the contract). Other domains' `apiv1` files unchanged.

Run: `git diff --stat -- internal/domains/*/apiv1/`
Expected: only `internal/domains/delivery/apiv1/openapi.gen.go` changed.

- [ ] **Step 8: Update the e2e assertions for delivery (full-state response).**

In `internal/platform/transport/e2e_test.go`, in `TestE2E_DeliveryFlowOverMountedRouter` step 6 (lines 169–189), replace the slim `deliveryapiv1.AppliedSelection` decode with a `sessionapiv1.CheckoutState` decode + full-state assertions:

```go
	// ── 6. PATCH /checkout/{id}/delivery-method {"type":"courier"} → 200 full CheckoutState ──
	resp = doPatch(t, c, fmt.Sprintf("%s/checkout/%s/delivery-method", base, checkoutID), `{"type":"courier"}`)
	assertStatus(t, "PATCH .../delivery-method", resp, http.StatusOK)
	var afterPatch sessionapiv1.CheckoutState
	decode(t, resp, &afterPatch)
	if afterPatch.Status != sessionapiv1.CheckoutStateStatusSelecting {
		t.Fatalf("PATCH delivery-method: expected status %q, got %q", sessionapiv1.CheckoutStateStatusSelecting, afterPatch.Status)
	}
	if afterPatch.Delivery.Selected == nil {
		t.Fatal("PATCH delivery-method: expected delivery.selected to be set")
	}
	if got := afterPatch.Delivery.Selected.Type; got != sessionapiv1.CheckoutSelectedDeliveryTypeDelivery {
		t.Fatalf("PATCH delivery-method: expected selected.type %q (courier→OMS canon), got %q", sessionapiv1.CheckoutSelectedDeliveryTypeDelivery, got)
	}
	if afterPatch.Delivery.Selected.PinnedDate == nil || *afterPatch.Delivery.Selected.PinnedDate == "" {
		t.Fatal("PATCH delivery-method: expected non-empty pinned_date")
	}
	// methods digest is carried in the full state too (assembler digest reader)
	if len(afterPatch.Delivery.Methods) != 4 {
		t.Fatalf("PATCH delivery-method: expected 4 methods in full state, got %d", len(afterPatch.Delivery.Methods))
	}
```

If `deliveryapiv1` is now used only in earlier steps (DeliveryDigest/KomplektaciyaList/ClusterResult/MethodSummary decodes remain), keep the import; it is still referenced.

- [ ] **Step 9: Verify.**

Run: `go build ./... && go vet ./... && go test ./...`
Expected: PASS (delivery boundary_test green — no session import; both e2e tests green).

Run: `make lint`
Expected: redocly lint clean.

- [ ] **Step 10: Commit.**

```bash
git add internal/app/wire/state.go internal/domains/delivery/types.go \
        internal/domains/delivery/handler.go internal/app/wire/delivery.go \
        internal/app/container.go internal/platform/transport/e2e_test.go \
        api/v1/paths/delivery.yaml api/v1/components/schemas/delivery.yaml \
        api/v1/bundle/openapi.yaml internal/domains/delivery/apiv1/openapi.gen.go
git commit -m "feat(delivery): PATCH delivery-method returns full CheckoutState (ADR-0001, inc 5)"
```

---

## Task 3: Recipient `PATCH recipient` → full CheckoutState

**Files:**
- Modify: `internal/domains/recipient/types.go` (add `StateView` port)
- Modify: `internal/domains/recipient/handler.go` (flip `SetRecipient`; drop `uuid` import + slim DTO)
- Modify: `internal/app/wire/recipient.go` (`Recipient` takes `asm`)
- Modify: `internal/app/container.go` (pass `asm`)
- Modify: `api/v1/paths/recipient.yaml`, `api/v1/components/schemas/recipient.yaml`
- Regenerate: `internal/domains/recipient/apiv1/openapi.gen.go`

- [ ] **Step 1: Add the `StateView` port.**

In `internal/domains/recipient/types.go`, add (and ensure `context` is imported):

```go
// StateView assembles the full CheckoutState (ADR-0001: command → full state).
// Consumer-defined; the session StateAssembler implements it via app/wire. Return
// is `any` — recipient must not import the session domain.
type StateView interface {
	AssembleState(ctx context.Context, checkoutID string) (any, error)
}
```

- [ ] **Step 2: Flip the recipient handler.**

In `internal/domains/recipient/handler.go`:

1. Struct + constructor:

```go
type Handler struct {
	service *Service
	state   StateView
	errs    *httpx.Helper
}

func NewHandler(service *Service, state StateView, errs *httpx.Helper) *Handler {
	return &Handler{service: service, state: state, errs: errs}
}
```

2. Replace `SetRecipient`'s success tail (the `_ = json.NewEncoder(w).Encode(apiv1.AppliedRecipient{...})`) so it assembles:

```go
// SetRecipient handles PATCH /api/v1/checkout/{checkout_id}/recipient. Validates +
// applies the recipient, then returns the full CheckoutState (ADR-0001).
func (h *Handler) SetRecipient(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "checkout_id")
	var body apiv1.SetRecipientRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		h.errs.BadRequest(w, "invalid_argument", "malformed JSON body")
		return
	}
	if _, err := h.service.SetRecipient(r.Context(), id, Recipient{
		FirstName: body.FirstName, LastName: body.LastName, Phone: body.Phone,
	}); err != nil {
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
	state, err := h.state.AssembleState(r.Context(), id)
	if err != nil {
		h.errs.Internal(w, "internal", "internal error")
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(state)
}
```

3. Remove the `"github.com/google/uuid"` import (only used by the deleted `AppliedRecipient` mapping).

- [ ] **Step 3: Wire the assembler.**

In `internal/app/wire/recipient.go`, change `Recipient`:

```go
// Recipient builds the recipient handler over the shared session service + assembler.
func Recipient(svc *session.Service, errs *httpx.Helper, asm *session.StateAssembler) *recipient.Handler {
	return recipient.NewHandler(recipient.NewService(&recipientGateway{svc: svc}), stateAssemblerView{asm: asm}, errs)
}
```

In `internal/app/container.go`:

```go
	c.RecipientHandler = wire.Recipient(sessionSvc, c.ErrorsHelper, asm)
```

In `internal/platform/transport/e2e_test.go` (`buildDeps`):

```go
	rh := wire.Recipient(svc, errs, asm)
```

- [ ] **Step 4: Re-point the contract.**

In `api/v1/paths/recipient.yaml`, `SetRecipient.patch.responses.200` (lines 19–24) becomes:

```yaml
      "200":
        description: Full checkout state (authoritative core, ADR-0001)
        content:
          application/json:
            schema:
              $ref: "../components/schemas/checkout.yaml#/CheckoutState"
```

In `api/v1/components/schemas/recipient.yaml`, **delete** `AppliedRecipient` and the `Recipient` response schema (keep `SetRecipientRequest`). Verify: `grep -rn "AppliedRecipient" api/` returns nothing after the path edit; confirm `Recipient` is not referenced elsewhere (`grep -rn "recipient.yaml#/Recipient\b" api/`).

- [ ] **Step 5: Regenerate.**

Run: `make generate && git diff --stat -- internal/domains/*/apiv1/`
Expected: only `internal/domains/recipient/apiv1/openapi.gen.go` changed (AppliedRecipient/Recipient pruned; CheckoutState + transitive generated).

- [ ] **Step 6: Verify + commit.**

Run: `go build ./... && go vet ./... && go test ./... && make lint`
Expected: PASS + lint clean. (`TestE2E_FullCommitFlow` PATCH recipient step asserts only HTTP 200 and closes the body — still valid; no decode change needed there.)

```bash
git add internal/domains/recipient/types.go internal/domains/recipient/handler.go \
        internal/app/wire/recipient.go internal/app/container.go \
        internal/platform/transport/e2e_test.go \
        api/v1/paths/recipient.yaml api/v1/components/schemas/recipient.yaml \
        api/v1/bundle/openapi.yaml internal/domains/recipient/apiv1/openapi.gen.go
git commit -m "feat(recipient): PATCH recipient returns full CheckoutState (ADR-0001, inc 5)"
```

---

## Task 4: Payment `PATCH payment-method` → full CheckoutState

**Files:**
- Modify: `internal/domains/payment/types.go` (add `StateView` port)
- Modify: `internal/domains/payment/handler.go` (flip `SetPaymentMethod`; drop `uuid` import + slim DTO)
- Modify: `internal/app/wire/payment.go` (`Payment` takes `asm`)
- Modify: `internal/app/container.go`, `internal/platform/transport/e2e_test.go`
- Modify: `api/v1/paths/payment.yaml`, `api/v1/components/schemas/payment.yaml`
- Regenerate: `internal/domains/payment/apiv1/openapi.gen.go`

- [ ] **Step 1: Add the `StateView` port.**

In `internal/domains/payment/types.go` (ensure `context` imported):

```go
// StateView assembles the full CheckoutState (ADR-0001: command → full state).
// Consumer-defined; bridged to the session StateAssembler in app/wire. `any` return
// keeps payment from importing the session domain.
type StateView interface {
	AssembleState(ctx context.Context, checkoutID string) (any, error)
}
```

- [ ] **Step 2: Flip the payment handler.**

In `internal/domains/payment/handler.go`:

1. Struct + constructor:

```go
type Handler struct {
	service *Service
	state   StateView
	errs    *httpx.Helper
}

func NewHandler(service *Service, state StateView, errs *httpx.Helper) *Handler {
	return &Handler{service: service, state: state, errs: errs}
}
```

2. Replace `SetPaymentMethod`'s success tail (the `apiv1.AppliedPayment{...}` encode):

```go
// SetPaymentMethod handles PATCH /api/v1/checkout/{checkout_id}/payment-method.
// Applies the method, then returns the full CheckoutState (ADR-0001).
func (h *Handler) SetPaymentMethod(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "checkout_id")
	var body apiv1.SetPaymentMethodRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		h.errs.BadRequest(w, "invalid_argument", "malformed JSON body")
		return
	}
	if _, err := h.service.SetPaymentMethod(r.Context(), id, Method(body.Type)); err != nil {
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
	state, err := h.state.AssembleState(r.Context(), id)
	if err != nil {
		h.errs.Internal(w, "internal", "internal error")
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(state)
}
```

3. Remove the `"github.com/google/uuid"` import.

- [ ] **Step 3: Wire the assembler.**

In `internal/app/wire/payment.go`:

```go
// Payment builds the payment handler over the shared session service + assembler.
func Payment(svc *session.Service, errs *httpx.Helper, asm *session.StateAssembler) *payment.Handler {
	return payment.NewHandler(payment.NewService(&paymentGateway{svc: svc}), stateAssemblerView{asm: asm}, errs)
}
```

In `internal/app/container.go`:

```go
	c.PaymentHandler = wire.Payment(sessionSvc, c.ErrorsHelper, asm)
```

In `internal/platform/transport/e2e_test.go` (`buildDeps`):

```go
	ph := wire.Payment(svc, errs, asm)
```

- [ ] **Step 4: Re-point the contract.**

In `api/v1/paths/payment.yaml`, `SetPaymentMethod.patch.responses.200` (lines 19–24):

```yaml
      "200":
        description: Full checkout state (authoritative core, ADR-0001)
        content:
          application/json:
            schema:
              $ref: "../components/schemas/checkout.yaml#/CheckoutState"
```

In `api/v1/components/schemas/payment.yaml`, **delete** `AppliedPayment` (keep `SetPaymentMethodRequest`). Verify: `grep -rn "AppliedPayment" api/`.

- [ ] **Step 5: Regenerate.**

Run: `make generate && git diff --stat -- internal/domains/*/apiv1/`
Expected: only `internal/domains/payment/apiv1/openapi.gen.go` changed.

- [ ] **Step 6: Verify + commit.**

Run: `go build ./... && go vet ./... && go test ./... && make lint`
Expected: PASS + lint clean. (`TestE2E_FullCommitFlow` payment step asserts HTTP 200 + closes body — unchanged.)

```bash
git add internal/domains/payment/types.go internal/domains/payment/handler.go \
        internal/app/wire/payment.go internal/app/container.go \
        internal/platform/transport/e2e_test.go \
        api/v1/paths/payment.yaml api/v1/components/schemas/payment.yaml \
        api/v1/bundle/openapi.yaml internal/domains/payment/apiv1/openapi.gen.go
git commit -m "feat(payment): PATCH payment-method returns full CheckoutState (ADR-0001, inc 5)"
```

---

## Task 5: Pricing `PATCH promo` → full CheckoutState

**Files:**
- Modify: `internal/domains/pricing/types.go` (add `StateView` port)
- Modify: `internal/domains/pricing/handler.go` (flip `SetPromo`; drop `uuid` import + slim DTO)
- Modify: `internal/app/wire/pricing.go` (`Pricing` takes `asm`)
- Modify: `internal/app/container.go`, `internal/platform/transport/e2e_test.go`
- Modify: `api/v1/paths/pricing.yaml`, `api/v1/components/schemas/pricing.yaml`
- Regenerate: `internal/domains/pricing/apiv1/openapi.gen.go`

> Consistency note: the full-state `totals` block is re-quoted by the assembler's `TotalsReader` (the same `pricing.StubQuoter` the pricing command uses), reading the just-persisted `session.Promo` + delivery cost. So the totals in the returned CheckoutState reflect the applied promo — no divergence between the command's quote and the rendered state.

- [ ] **Step 1: Add the `StateView` port.**

In `internal/domains/pricing/types.go` (ensure `context` imported):

```go
// StateView assembles the full CheckoutState (ADR-0001: command → full state).
// Consumer-defined; bridged to the session StateAssembler in app/wire. `any` return
// keeps pricing from importing the session domain.
type StateView interface {
	AssembleState(ctx context.Context, checkoutID string) (any, error)
}
```

- [ ] **Step 2: Flip the pricing handler.**

In `internal/domains/pricing/handler.go`:

1. Struct + constructor:

```go
type Handler struct {
	service *Service
	state   StateView
	errs    *httpx.Helper
}

func NewHandler(service *Service, state StateView, errs *httpx.Helper) *Handler {
	return &Handler{service: service, state: state, errs: errs}
}
```

2. Replace `SetPromo`'s success tail (the `apiv1.AppliedPromo{...}` build + encode):

```go
// SetPromo handles PATCH /api/v1/checkout/{checkout_id}/promo. Records the promo
// intent + re-quotes totals, then returns the full CheckoutState (ADR-0001).
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
	if _, err := h.service.SetPromo(r.Context(), id, promo); err != nil {
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
	state, err := h.state.AssembleState(r.Context(), id)
	if err != nil {
		h.errs.Internal(w, "internal", "internal error")
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(state)
}
```

3. Remove the `"github.com/google/uuid"` import.

- [ ] **Step 3: Wire the assembler.**

In `internal/app/wire/pricing.go`, change `Pricing`:

```go
// Pricing builds the pricing handler over the shared session service + assembler.
func Pricing(svc *session.Service, errs *httpx.Helper, asm *session.StateAssembler) *pricing.Handler {
	gw := &pricingGateway{svc: svc}
	return pricing.NewHandler(pricing.NewService(pricing.StubQuoter{}, gw), stateAssemblerView{asm: asm}, errs)
}
```

In `internal/app/container.go`:

```go
	c.PricingHandler = wire.Pricing(sessionSvc, c.ErrorsHelper, asm)
```

In `internal/platform/transport/e2e_test.go` (`buildDeps`):

```go
	prh := wire.Pricing(svc, errs, asm)
```

- [ ] **Step 4: Re-point the contract.**

In `api/v1/paths/pricing.yaml`, `SetPromo.patch.responses.200` (lines 19–24):

```yaml
      "200":
        description: Full checkout state (authoritative core, ADR-0001)
        content:
          application/json:
            schema:
              $ref: "../components/schemas/checkout.yaml#/CheckoutState"
```

In `api/v1/components/schemas/pricing.yaml`, **delete** `AppliedPromo` and the `Totals` response schema (keep `SetPromoRequest`). Verify: `grep -rn "AppliedPromo\|pricing.yaml#/Totals" api/`.

- [ ] **Step 5: Regenerate.**

Run: `make generate && git diff --stat -- internal/domains/*/apiv1/`
Expected: only `internal/domains/pricing/apiv1/openapi.gen.go` changed.

- [ ] **Step 6: Add an e2e promo step asserting full-state totals.**

In `internal/platform/transport/e2e_test.go`, in `TestE2E_FullCommitFlow` after the payment-method step and before commit, add:

```go
	// promo → 200 full CheckoutState with re-quoted totals
	resp = doPatch(t, c, fmt.Sprintf("%s/checkout/%s/promo", base, id), `{"promo_code":"SALE","burn_bonus":false}`)
	assertStatus(t, "PATCH promo", resp, http.StatusOK)
	var afterPromo sessionapiv1.CheckoutState
	decode(t, resp, &afterPromo)
	if afterPromo.Totals == nil || afterPromo.Totals.GrandTotal == nil {
		t.Fatal("PATCH promo: expected totals.grand_total in full state")
	}
```

> `sessionapiv1` is already imported in the test.

- [ ] **Step 7: Verify + commit.**

Run: `go build ./... && go vet ./... && go test ./... && make lint`
Expected: PASS + lint clean.

```bash
git add internal/domains/pricing/types.go internal/domains/pricing/handler.go \
        internal/app/wire/pricing.go internal/app/container.go \
        internal/platform/transport/e2e_test.go \
        api/v1/paths/pricing.yaml api/v1/components/schemas/pricing.yaml \
        api/v1/bundle/openapi.yaml internal/domains/pricing/apiv1/openapi.gen.go
git commit -m "feat(pricing): PATCH promo returns full CheckoutState (ADR-0001, inc 5)"
```

---

## Task 6: Live verification on stage + docs

**Files:**
- Modify: `checkout/docs/architecture/adr/0001-checkout-state-contract.md` (mark command-returns-state implemented)
- (After merge, separately) update memory `project_checkout.md`.

- [ ] **Step 1: Full offline gate.**

Run from `platform-new/checkout`:
```bash
go build ./... && go vet ./... && go test ./... && make generate && git status --porcelain api/ internal/domains/*/apiv1/ && make lint
```
Expected: tests PASS; `make generate` leaves NO drift (clean `git status`); lint clean.

- [ ] **Step 2: Boundary guard — confirm no capability imports session.**

Run: `go test ./internal/domains/... -run TestBoundary`
Expected: PASS for delivery/recipient/payment/pricing/session (the `any`-port kept the boundary; the only place importing both is `internal/app/wire`).

- [ ] **Step 3: Live run against stage (real OMS + cart).**

```bash
make port-forward          # checkout/scripts/dev-port-forward.sh (stage; needs KUBECONFIG=<path-to-ecom-kubeconfig> current-context)
# in another shell, with checkout/.env loaded:
make migrate-up
make run                   # :8090 (per memory live-session notes)
```

Drive the flow on the known live customer 4455421 (cart resolved server-side):
```bash
CID=$(curl -s localhost:8090/api/v1/checkout -d '{"customer_id":"4455421","basket_id":"<live-basket#>"}' | jq -r .checkout_id)

# Each PATCH must now return the FULL CheckoutState (not a slim delta):
curl -s -X PATCH localhost:8090/api/v1/checkout/$CID/delivery-method -d '{"type":"courier"}' | jq '{status, has_cart: (.cart!=null), methods: (.delivery.methods|length), selected: .delivery.selected.type, grand: .totals.grand_total}'
curl -s -X PATCH localhost:8090/api/v1/checkout/$CID/recipient -d '{"first_name":"Иван","last_name":"Петров","phone":"+79001112233"}' | jq '{status, recipient}'
curl -s -X PATCH localhost:8090/api/v1/checkout/$CID/payment-method -d '{"type":"sbp"}' | jq '{status, payment_selected: .payment.selected}'
curl -s -X PATCH localhost:8090/api/v1/checkout/$CID/promo -d '{"promo_code":"","burn_bonus":false}' | jq '{status, totals}'
```
Expected for every PATCH: a full `CheckoutState` body — `checkout_id`, `status`, `cart.products[]` (4 real items, **rubles**), `delivery.methods[]` (4), `delivery.selected` after the delivery PATCH, `payment.selected` after the payment PATCH, `recipient` after the recipient PATCH, `totals.grand_total` in rubles. Confirm money is rubles on the wire (e.g. `grand_total` ≈ 5396, not 539600). Confirm 404 on an unknown checkout id and 400 on a bogus delivery `type` still return the honest error envelope (NOT a CheckoutState).

- [ ] **Step 4: Note the increment as done in the ADR.**

In `checkout/docs/architecture/adr/0001-checkout-state-contract.md`, add a short status line under the decision: "Implemented 2026-06-03 — GET and all four mutating commands (delivery-method/recipient/payment/promo) return the full CheckoutState via `session.StateAssembler`; capability domains stay decoupled through the `any`-typed `StateView` port."

```bash
git add checkout/docs/architecture/adr/0001-checkout-state-contract.md
git commit -m "docs(adr-0001): command→full-state implemented for all capability PATCHes (inc 5)"
```

- [ ] **Step 5: Hand back to Zak for push.** Do NOT `git push` (per standing instruction — push is Zak's). Summarize commits + the live-verification output.

---

## Self-Review

**Spec coverage:**
- "вынести общий StateAssembler (session+cart+digest+totals, что уже в session-handler)" → Task 1 (extract `session.StateAssembler`, move the exact projection + best-effort readers out of `handler.go`).
- "подключить к 4 capability-хендлерам" → Tasks 2–5 (delivery/recipient/payment/pricing each flip to assemble + return full state via the `StateView` port).
- "поправить responses в контракте" → each capability task Step 4 re-points the PATCH 200 to `checkout.yaml#/CheckoutState` and removes the dead `Applied*` schema; bundle + per-domain regen in Step 5/7.
- "Деньги: копейки внутри / рубли во фронт" → projection keeps int64 kopecks internally; `kopecksToRubles` at the edge only (unchanged); Task 6 Step 3 verifies rubles on the wire. No new float in money paths.
- "Коммить по репо, push не делай" → one commit per task in `platform-new/checkout`; Task 6 Step 5 explicitly hands push to Zak.
- Boundary preserved → `StateView` returns `any`; boundary_test asserted in Task 6 Step 2.

**Placeholder scan:** every code step contains full code; commands have explicit expected output. The only soft spots are deliberately flagged with `>` notes to confirm at execution (in-memory store constructor name; `context` import presence in each `types.go`; the live basket number).

**Type consistency:** `StateView.AssembleState(ctx, checkoutID string) (any, error)` is identical across the four domains and matched by `wire.stateAssemblerView.AssembleState`. `session.NewHandler(service, errs, assembler)`, `delivery.NewHandler(service, state, errs)`, `recipient/payment/pricing.NewHandler(service, state, errs)` — note the **delivery** constructor orders args `(service, state, errs)` to match its existing `(service, errs)` extended with `state` in the middle; recipient/payment/pricing follow the same `(service, state, errs)` order. `wire.StateAssembler(svc, resolver, deliverySvc)` and `wire.SessionHandler(svc, errs, asm)` are used consistently in `container.go` and `e2e_test.go`. `apiv1.CheckoutState` field/enum names (`CheckoutStateStatusSelecting`, `CheckoutSelectedDeliveryTypeDelivery`, `CheckoutPaymentMethodsPrepaid`, `Totals.GrandTotal`) match the generated session DTOs already used in `handler.go`/`e2e_test.go`.
