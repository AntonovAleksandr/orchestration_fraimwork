# Checkout v1 — Plan 3: Komplektaciya Resolver (§2c) Implementation Plan

> ⚠️ **ТРЕБУЕТ РЕ-ПЛАНИРОВАНИЯ под domain-map (2026-05-30) — НЕ исполнять как есть.** План написан до карты доменов (`platform-new/checkout/docs/architecture/domain-map.md`). По новой карте: доставка = **отдельный домен `internal/domains/delivery`** (владеет портом `DeliverySource` + эндпоинтами `GET …/delivery-options`, `PATCH …/delivery-method`), нормализация-resolver — в `internal/adapters/delivery/`, stub-`DeliverySource` из фикстур. Выбор komplektaciya мутирует агрегат **через домен `session`** (session — корень-оркестратор), а не пишется delivery напрямую. Резолвер-логика и table-тесты на реальных фикстурах — переносятся как есть, меняется только размещение пакета и проводка через session. Переписать по writing-plans перед запуском.

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** Build the §2c resolver — pure functions that normalize the **three different OMS logistics response shapes** (`delivery-preliminary`, `pickup-stores`, `delivery-intervals`) into one domain `Komplektaciya`/`DeliveryDigest` — locked in one tested place, plus a stub `DeliverySource` that feeds it the real captured fixtures. Wire the granular delivery endpoints (`GET …/delivery-options`, `PATCH …/delivery-method`) including **dispatch_date pinning** and persisting the selected komplektaciya to the session.

**Architecture:** Normalization (the resolver) lives in `internal/adapters/checkout/` (per ecom-gateway convention: client/DTO→domain mapping is an adapter concern). The domain defines the `DeliverySource` port returning **domain types**. v1 stub `DeliverySource` decodes the real fixtures (`testdata/`) through the **same normalize funcs** the real starfish-oms adapter will use in phase 2 — so the risky logic is real and table-tested now. Selection is persisted on the session (migration 0002 adds a `selection` JSONB column).

**Tech Stack:** Go stdlib `encoding/json` + `embed`; existing pgx repo.

**Prereq:** Plans 1–2 complete.

**Grounding (the real OMS shapes — the source of truth):** `platform-new/checkout/fixtures/oms/{delivery-preliminary,pickup-stores,delivery-intervals}.json` (captured from stage). Copy curated copies into `internal/adapters/checkout/testdata/`.

**Design:** spec §2 (Komplektaciya model), §2c (resolver invariants), §3 (two-level delivery: per-method digest on entry + drill-in), §6 (drift / pin date).

**Invariants the resolver MUST hold (and table-test):**
1. coverage «X из N» = `instock` (stores/pvz) / `inventory.availableQuantity` (courier) / count(`cart.items[].stock[].available`) (preliminary).
2. three shapes → one `Komplektaciya`.
3. delivery type normalization: `delivery`→COURIER, `pickup`→PVZ, `pickupinstore`→C&C, `reserveinstore`→C&R.
4. hashed `id` present for COURIER + PVZ; absent for STORE (key = store code + dispatch_date).
5. partial availability (some items unavailable) preserved per-item.
6. note quirk field name `cartAvailabillity` (double-l) in courier inventory.

---

## File Structure (Plan 3)

```
checkout/
├── migrations/0002_session_selection.{up,down}.sql
├── internal/adapters/checkout/
│   ├── raw.go            raw OMS structs (faithful to fixtures; phase-2 swaps starfish-oms DTOs)
│   ├── resolver.go       normalize* funcs: raw shape → []domain.Komplektaciya / DeliveryDigest
│   ├── resolver_test.go  table tests on fixtures (THE risk surface)
│   ├── stub.go           stub DeliverySource: embeds fixtures → resolver → domain types
│   └── testdata/{delivery-preliminary,pickup-stores,delivery-intervals}.json
└── internal/domains/checkout/
    ├── types.go          + Komplektaciya, DeliveryDigest, Selection, DeliveryType, DeliverySource port
    ├── service.go        + GetDeliveryOptions, SetDeliveryMethod (pin date, persist selection)
    ├── repository.go     + UpdateSelection
    ├── handler.go        + DeliveryOptions, SetDeliveryMethod
    └── routes.go         + GET /{id}/delivery-options, PATCH /{id}/delivery-method
```

---

## Task 1: Domain types + port + selection persistence

**Files:** Modify `internal/domains/checkout/types.go`, `repository.go`; Create `migrations/0002_session_selection.{up,down}.sql`.

- [ ] **Step 1: Add domain types to `types.go`**

```go
// DeliveryType is the normalized fulfillment path.
type DeliveryType string

const (
	DeliveryCourier      DeliveryType = "courier"        // OMS "delivery"
	DeliveryPVZ          DeliveryType = "pvz"            // OMS "pickup"
	DeliveryStorePickup  DeliveryType = "store_pickup"   // OMS "pickupinstore" (C&C)
	DeliveryStoreReserve DeliveryType = "store_reserve"  // OMS "reserveinstore" (C&R)
)

// ItemAvail is per-cart-line availability within a komplektaciya.
type ItemAvail struct {
	ProductID         string // vendorCodeSku
	AvailableQuantity int
	Available         bool
}

// Point is the fulfillment location.
type Point struct {
	WarehouseID  string
	StoreCode    string
	PickupPointID string
	CarrierID    string
	Name         string
	Address      string
	Lat, Lng     float64
}

// Features are display/constraint flags of a komplektaciya.
type Features struct {
	TryOn           bool
	PassportReq     bool
	StorageDeadline string
	Oversize        bool
}

// Komplektaciya is one normalized fulfillment option = inventory subset + point + interval.
type Komplektaciya struct {
	DeliveryType  DeliveryType
	Items         []ItemAvail
	Coverage      int // count(Available) — "X из N"
	Point         Point
	IntervalID    string // hashed (courier/pvz); "" for store
	DispatchDate  string
	PromisedDate  string
	TariffID      string
	LogisticGroup string
	DeliveryCost  float64
	Features      Features
}

// DeliveryDigest is the compact per-method summary for the entry context.
type DeliveryDigest struct {
	Methods []MethodSummary
}

// MethodSummary is one card in "Способ получения".
type MethodSummary struct {
	DeliveryType   DeliveryType
	Available      bool
	Coverage       int // best coverage among that method's komplektacii
	CartSize       int
	MinCost        float64
	MinDays        int
	FreeThreshold  float64
	PaymentTypes   []string
}

// Selection is the user's chosen komplektaciya (persisted on the session).
type Selection struct {
	DeliveryType  DeliveryType   `json:"delivery_type"`
	Komplektaciya *Komplektaciya `json:"komplektaciya,omitempty"`
	PinnedDate    string         `json:"pinned_dispatch_date"`
}

// CartLine is a snapshot cart item (intent).
type CartLine struct {
	ProductID string `json:"product_id"` // vendorCodeSku
	Quantity  int    `json:"quantity"`
}

// DeliverySource resolves fulfillment options for a cart+city. Consumer-defined
// port; v1 stub feeds fixtures, phase-2 adapter calls starfish-oms. Returns
// DOMAIN types — normalization of OMS shapes happens in the adapter (§2c).
type DeliverySource interface {
	Digest(ctx context.Context, city string, cart []CartLine) (DeliveryDigest, error)
	Options(ctx context.Context, city string, cart []CartLine, t DeliveryType) ([]Komplektaciya, error)
}
```
Add `Selection *Selection` and `Cart []CartLine` fields to `Session`.

- [ ] **Step 2: Migration 0002 — selection JSONB**

`migrations/0002_session_selection.up.sql`:
```sql
ALTER TABLE checkout_sessions ADD COLUMN IF NOT EXISTS selection jsonb NULL;
ALTER TABLE checkout_sessions ADD COLUMN IF NOT EXISTS cart_snapshot jsonb NULL;
```
`...down.sql`:
```sql
ALTER TABLE checkout_sessions DROP COLUMN IF EXISTS selection;
ALTER TABLE checkout_sessions DROP COLUMN IF EXISTS cart_snapshot;
```
Run `make migrate`.

- [ ] **Step 3: Repository — persist/read selection + cart**

Add to `repository.go`:
```go
// UpdateSelection persists the chosen selection (JSONB) and bumps updated_at.
func (r *Repository) UpdateSelection(ctx context.Context, checkoutID string, sel Selection) error {
	b, err := json.Marshal(sel)
	if err != nil {
		return fmt.Errorf("checkout: marshal selection: %w", err)
	}
	ct, err := r.db.Exec(ctx,
		`UPDATE checkout_sessions SET selection=$2, updated_at=now() WHERE checkout_id=$1`,
		checkoutID, b)
	if err != nil {
		return fmt.Errorf("checkout: update selection: %w", err)
	}
	if ct.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}
```
Extend `Create`/`Get` to read/write `cart_snapshot` + `selection` (scan JSONB into `*Selection`/`[]CartLine` with `json.Unmarshal`, handling NULL). Add `UpdateSelection` to the `SessionStore` interface in `types.go` and to `InMemoryStore` (stub.go).

- [ ] **Step 4: Build + commit**

Run `go build ./... && go test ./internal/domains/checkout/`.
```bash
git add migrations internal/domains/checkout
git commit -m "feat(checkout): komplektaciya/digest/selection domain types + selection persistence"
```

---

## Task 2: Resolver — normalize 3 OMS shapes (TDD, fixtures)

**Files:** Create `internal/adapters/checkout/{raw.go,resolver.go,resolver_test.go}` + `testdata/*.json`.

- [ ] **Step 1: Copy curated fixtures into adapter testdata**

```bash
mkdir -p internal/adapters/checkout/testdata
cp ../../checkout/fixtures/oms/{delivery-preliminary,pickup-stores,delivery-intervals}.json \
   internal/adapters/checkout/testdata/   # adjust relative path; source = repo fixtures/oms/
```
(If fixtures hold sensitive store data, trim to ~3 representative records each — keep at least one partial-coverage record.)

- [ ] **Step 2: Write `raw.go`** — faithful raw structs (only used fields; quirks preserved)

```go
package checkout

// raw* mirror the OMS logistics JSON shapes (faithful; phase-2 replaces with
// starfish-oms client DTOs). Field names/tags MUST match the fixtures exactly.

// --- delivery-preliminary: {"data":[ ... ]} ---
type rawPreliminary struct {
	Data []rawPrelimType `json:"data"`
}
type rawPrelimType struct {
	DeliveryTypeID   string          `json:"deliveryTypeId"`
	Available        bool            `json:"available"`
	Delivery         rawPrelimDeliv  `json:"delivery"`
	AvailablePayment []string        `json:"availablePaymentTypes"`
	Cart             rawPrelimCart   `json:"cart"`
}
type rawPrelimDeliv struct {
	MinDays              int     `json:"minDays"`
	MinCost              float64 `json:"minCost"`
	FreeCostCartThreshold float64 `json:"freeCostCartThreshold"`
}
type rawPrelimCart struct {
	Items []rawPrelimItem `json:"items"`
}
type rawPrelimItem struct {
	ID        string `json:"id"`
	Available bool   `json:"available"`
}

// --- pickup-stores: bare array ---
type rawStore struct {
	DeliveryTypeID      string            `json:"deliveryTypeId"`
	Instock             int               `json:"instock"`
	ProductAvailability []rawProdAvail    `json:"productAvailability"`
	DispatchWarehouseID string            `json:"dispatchWarehouseId"`
	DispatchDate        string            `json:"dispatchDate"`
	ReadyForPickup      string            `json:"readyForPickup"`
	LogisticGroupID     string            `json:"logisticGroupId"`
	CarrierID           string            `json:"carrierId"`
	TariffID            string            `json:"tariffId"`
	DeliveryCost        float64           `json:"deliveryCost"`
	Coordinates         rawCoords         `json:"coordinates"`
	PickupStore         rawPickupStore    `json:"pickupStore"`
}
type rawProdAvail struct {
	ProductID         string `json:"productId"`
	AvailableQuantity int    `json:"availableQuantity"`
	Available         bool   `json:"available"`
}
type rawCoords struct {
	Latitude  float64 `json:"latitude"`
	Longitude float64 `json:"longitude"`
}
type rawPickupStore struct {
	Code        string `json:"code"`
	Name        string `json:"name"`
	Address     string `json:"address"`
	StorageTime int    `json:"storageTime"`
}

// --- delivery-intervals (courier): {"data":[ ... ]} ---
type rawCourier struct {
	Data []rawCourierEntry `json:"data"`
}
type rawCourierEntry struct {
	Inventory     rawInventory  `json:"inventory"`
	LogisticGroup string        `json:"logisticGroupId"`
	Intervals     rawIntervals  `json:"intervals"`
}
type rawInventory struct {
	DispatchWarehouse string         `json:"dispatchWarehouse"`
	DispatchDate      string         `json:"dispatchDate"`
	AvailableQuantity int            `json:"availableQuantity"`
	CartAvailability  []rawProdAvail `json:"cartAvailabillity"` // NB: OMS typo (double l)
}
type rawIntervals struct {
	List []rawInterval `json:"list"`
}
type rawInterval struct {
	ID           string  `json:"id"`
	Date         string  `json:"date"`
	From         string  `json:"from"`
	To           string  `json:"to"`
	DeliveryCost float64 `json:"deliveryCost"`
	CarrierID    string  `json:"carrierId"`
	TariffID     string  `json:"tariffId"`
}
```

- [ ] **Step 3: Write the failing resolver tests** — `resolver_test.go`

```go
package checkout

import (
	"encoding/json"
	"os"
	"testing"

	domain "gj-checkout/internal/domains/checkout"
)

func loadFixture(t *testing.T, name string) []byte {
	t.Helper()
	b, err := os.ReadFile("testdata/" + name)
	if err != nil {
		t.Fatalf("read fixture %s: %v", name, err)
	}
	return b
}

func TestNormalizePickupStores_coverageAndType(t *testing.T) {
	var raw []rawStore
	if err := json.Unmarshal(loadFixture(t, "pickup-stores.json"), &raw); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	ks := normalizePickupStores(raw)
	if len(ks) == 0 {
		t.Fatal("expected komplektacii")
	}
	for _, k := range ks {
		if k.DeliveryType != domain.DeliveryStorePickup && k.DeliveryType != domain.DeliveryStoreReserve {
			t.Fatalf("store fixture must map to store_pickup/store_reserve, got %s", k.DeliveryType)
		}
		if k.IntervalID != "" {
			t.Fatalf("store komplektaciya must have empty IntervalID (key=code+date), got %q", k.IntervalID)
		}
		if k.Point.StoreCode == "" {
			t.Fatal("store komplektaciya must carry StoreCode")
		}
		// coverage == count(available items)
		want := 0
		for _, it := range k.Items {
			if it.Available {
				want++
			}
		}
		if k.Coverage != want {
			t.Fatalf("coverage %d != available-count %d", k.Coverage, want)
		}
	}
}

func TestNormalizeCourier_hashedIDAndTypoField(t *testing.T) {
	var raw rawCourier
	if err := json.Unmarshal(loadFixture(t, "delivery-intervals.json"), &raw); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	ks := normalizeCourier(raw)
	if len(ks) == 0 {
		t.Fatal("expected courier komplektacii")
	}
	for _, k := range ks {
		if k.DeliveryType != domain.DeliveryCourier {
			t.Fatalf("want courier, got %s", k.DeliveryType)
		}
		if k.IntervalID == "" {
			t.Fatal("courier komplektaciya must carry hashed IntervalID")
		}
		if len(k.Items) == 0 {
			t.Fatal("cartAvailabillity (typo field) must decode into Items")
		}
	}
}

func TestNormalizePreliminary_digest(t *testing.T) {
	var raw rawPreliminary
	if err := json.Unmarshal(loadFixture(t, "delivery-preliminary.json"), &raw); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	d := normalizePreliminaryDigest(raw)
	if len(d.Methods) == 0 {
		t.Fatal("digest must have methods")
	}
	// preliminary has 4 types → expect all four normalized types present
	seen := map[domain.DeliveryType]bool{}
	for _, m := range d.Methods {
		seen[m.DeliveryType] = true
		if m.CartSize == 0 {
			t.Fatal("CartSize must be set")
		}
	}
	for _, want := range []domain.DeliveryType{domain.DeliveryCourier, domain.DeliveryPVZ, domain.DeliveryStorePickup, domain.DeliveryStoreReserve} {
		if !seen[want] {
			t.Fatalf("digest missing method %s", want)
		}
	}
}
```

- [ ] **Step 4: Run — verify it fails**

Run: `go test ./internal/adapters/checkout/ -v` → FAIL (`normalize*` undefined).

- [ ] **Step 5: Write `resolver.go`** (the §2c core)

```go
package checkout

import domain "gj-checkout/internal/domains/checkout"

// omsTypeToDomain maps OMS deliveryTypeId → domain DeliveryType.
func omsTypeToDomain(t string) domain.DeliveryType {
	switch t {
	case "delivery":
		return domain.DeliveryCourier
	case "pickup":
		return domain.DeliveryPVZ
	case "pickupinstore":
		return domain.DeliveryStorePickup
	case "reserveinstore":
		return domain.DeliveryStoreReserve
	default:
		return domain.DeliveryType(t)
	}
}

func toItems(in []rawProdAvail) ([]domain.ItemAvail, int) {
	out := make([]domain.ItemAvail, 0, len(in))
	cov := 0
	for _, p := range in {
		out = append(out, domain.ItemAvail{ProductID: p.ProductID, AvailableQuantity: p.AvailableQuantity, Available: p.Available})
		if p.Available {
			cov++
		}
	}
	return out, cov
}

// normalizePickupStores maps the bare store array → store komplektacii.
// Store selection key = code + dispatchDate (no hashed IntervalID).
func normalizePickupStores(raw []rawStore) []domain.Komplektaciya {
	out := make([]domain.Komplektaciya, 0, len(raw))
	for _, s := range raw {
		items, cov := toItems(s.ProductAvailability)
		out = append(out, domain.Komplektaciya{
			DeliveryType: omsTypeToDomain(s.DeliveryTypeID),
			Items:        items,
			Coverage:     cov,
			Point: domain.Point{
				WarehouseID: s.DispatchWarehouseID, StoreCode: s.PickupStore.Code,
				CarrierID: s.CarrierID, Name: s.PickupStore.Name, Address: s.PickupStore.Address,
				Lat: s.Coordinates.Latitude, Lng: s.Coordinates.Longitude,
			},
			IntervalID:    "", // stores: key = code + dispatchDate
			DispatchDate:  s.DispatchDate,
			PromisedDate:  s.ReadyForPickup,
			TariffID:      s.TariffID,
			LogisticGroup: s.LogisticGroupID,
			DeliveryCost:  s.DeliveryCost,
			Features:      domain.Features{StorageDeadline: ""}, // storageTime→deadline computed later
		})
	}
	return out
}

// normalizeCourier maps {data:[{inventory,intervals.list}]} → one komplektaciya
// per interval (hashed IntervalID). Reads the typo field cartAvailabillity.
func normalizeCourier(raw rawCourier) []domain.Komplektaciya {
	var out []domain.Komplektaciya
	for _, e := range raw.Data {
		items, cov := toItems(e.Inventory.CartAvailability)
		for _, iv := range e.Intervals.List {
			out = append(out, domain.Komplektaciya{
				DeliveryType: domain.DeliveryCourier,
				Items:        items,
				Coverage:     cov,
				Point:        domain.Point{WarehouseID: e.Inventory.DispatchWarehouse, CarrierID: iv.CarrierID},
				IntervalID:   iv.ID,
				DispatchDate: e.Inventory.DispatchDate,
				PromisedDate: iv.Date,
				TariffID:     iv.TariffID,
				LogisticGroup: e.LogisticGroup,
				DeliveryCost: iv.DeliveryCost,
				Features:     domain.Features{},
			})
		}
	}
	return out
}

// normalizePreliminaryDigest builds the per-method entry digest from preliminary.
func normalizePreliminaryDigest(raw rawPreliminary) domain.DeliveryDigest {
	d := domain.DeliveryDigest{}
	for _, t := range raw.Data {
		cartSize := len(t.Cart.Items)
		cov := 0
		for _, it := range t.Cart.Items {
			if it.Available {
				cov++
			}
		}
		d.Methods = append(d.Methods, domain.MethodSummary{
			DeliveryType:  omsTypeToDomain(t.DeliveryTypeID),
			Available:     t.Available,
			Coverage:      cov,
			CartSize:      cartSize,
			MinCost:       t.Delivery.MinCost,
			MinDays:       t.Delivery.MinDays,
			FreeThreshold: t.Delivery.FreeCostCartThreshold,
			PaymentTypes:  t.AvailablePayment,
		})
	}
	return d
}
```

- [ ] **Step 6: Run — verify tests pass**

Run: `go test ./internal/adapters/checkout/ -v` → PASS.

- [ ] **Step 7: Commit**

```bash
git add internal/adapters/checkout/{raw.go,resolver.go,resolver_test.go,testdata}
git commit -m "feat(resolver): §2c normalize 3 OMS shapes → Komplektaciya/Digest (TDD on fixtures)"
```

---

## Task 3: Stub `DeliverySource` over fixtures

**Files:** Create `internal/adapters/checkout/stub.go`.

- [ ] **Step 1: Write `stub.go`** (embeds fixtures, runs them through the resolver)

```go
package checkout

import (
	"context"
	_ "embed"
	"encoding/json"

	domain "gj-checkout/internal/domains/checkout"
)

//go:embed testdata/delivery-preliminary.json
var fxPreliminary []byte

//go:embed testdata/pickup-stores.json
var fxStores []byte

//go:embed testdata/delivery-intervals.json
var fxCourier []byte

// StubDeliverySource implements domain.DeliverySource from baked fixtures, via
// the real resolver. Phase-2 RealDeliverySource calls starfish-oms then the same
// normalize* funcs.
type StubDeliverySource struct{}

func NewStubDeliverySource() *StubDeliverySource { return &StubDeliverySource{} }

func (StubDeliverySource) Digest(_ context.Context, _ string, _ []domain.CartLine) (domain.DeliveryDigest, error) {
	var raw rawPreliminary
	_ = json.Unmarshal(fxPreliminary, &raw)
	return normalizePreliminaryDigest(raw), nil
}

func (StubDeliverySource) Options(_ context.Context, _ string, _ []domain.CartLine, t domain.DeliveryType) ([]domain.Komplektaciya, error) {
	switch t {
	case domain.DeliveryCourier:
		var raw rawCourier
		_ = json.Unmarshal(fxCourier, &raw)
		return normalizeCourier(raw), nil
	case domain.DeliveryStorePickup, domain.DeliveryStoreReserve, domain.DeliveryPVZ:
		var raw []rawStore
		_ = json.Unmarshal(fxStores, &raw)
		ks := normalizePickupStores(raw)
		// filter to requested type
		out := ks[:0]
		for _, k := range ks {
			if k.DeliveryType == t {
				out = append(out, k)
			}
		}
		return out, nil
	default:
		return nil, nil
	}
}
```

- [ ] **Step 2: Build + commit**

Run `go build ./...`.
```bash
git add internal/adapters/checkout/stub.go
git commit -m "feat(resolver): stub DeliverySource over fixtures (uses real resolver)"
```

---

## Task 4: Service — GetDeliveryOptions + SetDeliveryMethod (pin date) (TDD)

**Files:** Modify `internal/domains/checkout/{service.go,service_test.go}`.

- [ ] **Step 1: Failing test** (append to `service_test.go`)

```go
func TestSetDeliveryMethod_pinsDateAndPersistsSelection(t *testing.T) {
	store := NewInMemoryStore()
	src := stubSrc{} // local fake implementing DeliverySource (see Step 3)
	svc := NewServiceWithDelivery(store, src)

	sess, _ := svc.CreateSession(context.Background(), CreateSessionInput{CustomerID: "c", BasketID: "b"})

	out, err := svc.SetDeliveryMethod(context.Background(), sess.CheckoutID, DeliveryCourier)
	if err != nil {
		t.Fatalf("SetDeliveryMethod: %v", err)
	}
	if out.Selection == nil || out.Selection.DeliveryType != DeliveryCourier {
		t.Fatal("selection not set to courier")
	}
	if out.Selection.PinnedDate == "" {
		t.Fatal("dispatch_date must be pinned")
	}
	reloaded, _ := store.Get(context.Background(), sess.CheckoutID)
	if reloaded.Selection == nil {
		t.Fatal("selection not persisted")
	}
}
```
Add a local fake at the bottom of the test file:
```go
type stubSrc struct{}
func (stubSrc) Digest(context.Context, string, []CartLine) (DeliveryDigest, error) { return DeliveryDigest{}, nil }
func (stubSrc) Options(_ context.Context, _ string, _ []CartLine, t DeliveryType) ([]Komplektaciya, error) {
	return []Komplektaciya{{DeliveryType: t, Coverage: 2, DispatchDate: "2026-05-31", IntervalID: "QOOcGGOK"}}, nil
}
```

- [ ] **Step 2: Run → FAIL** (`NewServiceWithDelivery`, `SetDeliveryMethod` undefined).

- [ ] **Step 3: Extend `service.go`**

```go
// add field + constructor variant
type Service struct {
	store    SessionStore
	delivery DeliverySource // may be nil in Plan-1/2 paths
}

func NewService(store SessionStore) *Service { /* unchanged: */ return &Service{store: store} }

func NewServiceWithDelivery(store SessionStore, d DeliverySource) *Service {
	s := NewService(store)
	s.delivery = d
	return s
}

// GetDeliveryOptions returns the per-method digest (entry) for the session's cart.
func (s *Service) GetDeliveryOptions(ctx context.Context, checkoutID string) (DeliveryDigest, error) {
	sess, err := s.store.Get(ctx, checkoutID)
	if err != nil {
		return DeliveryDigest{}, err
	}
	return s.delivery.Digest(ctx, sess.CustomerID /*city later*/, sess.Cart)
}

// SetDeliveryMethod auto-resolves the best komplektaciya for the method, PINS its
// dispatch_date, persists the selection, and returns the updated session.
func (s *Service) SetDeliveryMethod(ctx context.Context, checkoutID string, t DeliveryType) (Session, error) {
	sess, err := s.store.Get(ctx, checkoutID)
	if err != nil {
		return Session{}, err
	}
	opts, err := s.delivery.Options(ctx, sess.CustomerID, sess.Cart, t)
	if err != nil {
		return Session{}, fmt.Errorf("resolve delivery options: %w", err)
	}
	best := pickBest(opts)
	if best == nil {
		return Session{}, fmt.Errorf("%w: no fulfillment option for %s", ErrInvalidArgument, t)
	}
	sel := Selection{DeliveryType: t, Komplektaciya: best, PinnedDate: best.DispatchDate}
	if err := s.store.UpdateSelection(ctx, checkoutID, sel); err != nil {
		return Session{}, err
	}
	sess.Selection = &sel
	sess.Status = StatusSelecting
	return sess, nil
}

// pickBest is the replaceable "best interval" policy: max coverage, then earliest
// dispatch date, then cheapest. (Mirrors IS "best interval" today.)
func pickBest(opts []Komplektaciya) *Komplektaciya {
	if len(opts) == 0 {
		return nil
	}
	best := opts[0]
	for _, k := range opts[1:] {
		switch {
		case k.Coverage != best.Coverage:
			if k.Coverage > best.Coverage {
				best = k
			}
		case k.DispatchDate != best.DispatchDate:
			if k.DispatchDate < best.DispatchDate {
				best = k
			}
		case k.DeliveryCost < best.DeliveryCost:
			best = k
		}
	}
	return &best
}
```

- [ ] **Step 4: Run → PASS.** Commit.

```bash
git add internal/domains/checkout/{service.go,service_test.go}
git commit -m "feat(checkout): GetDeliveryOptions + SetDeliveryMethod (pin dispatch_date, persist selection) (TDD)"
```

---

## Task 5: Endpoints — GET delivery-options + PATCH delivery-method

**Files:** Modify `api/v1/{openapi.yaml,paths/checkout.yaml,components/schemas/checkout.yaml}`, `internal/domains/checkout/{handler.go,routes.go}`.

- [ ] **Step 1: OpenAPI** — add paths `GET /checkout/{checkout_id}/delivery-options` (→ `DeliveryDigest` schema) and `PATCH /checkout/{checkout_id}/delivery-method` (body `{type}` → `CheckoutSession`). Add `DeliveryDigest`, `MethodSummary`, `Komplektaciya` schemas to `components/schemas/checkout.yaml` mirroring the domain types (snake_case). Run `make generate && make lint`.

- [ ] **Step 2: Handlers** — add to `handler.go`:

```go
// DeliveryOptions handles GET /api/v1/checkout/{checkout_id}/delivery-options.
func (h *Handler) DeliveryOptions(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "checkout_id")
	digest, err := h.service.GetDeliveryOptions(r.Context(), id)
	if err != nil {
		if errors.Is(err, ErrNotFound) { h.errs.JSON(w, http.StatusNotFound, "not_found", "session not found"); return }
		h.errs.Internal(w, "internal", "internal error"); return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(toDigestDTO(digest))
}

// SetDeliveryMethod handles PATCH /api/v1/checkout/{checkout_id}/delivery-method.
func (h *Handler) SetDeliveryMethod(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "checkout_id")
	var body struct{ Type string `json:"type"` }
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		h.errs.BadRequest(w, "invalid_argument", "malformed JSON"); return
	}
	sess, err := h.service.SetDeliveryMethod(r.Context(), id, DeliveryType(body.Type))
	if err != nil {
		switch {
		case errors.Is(err, ErrNotFound): h.errs.JSON(w, http.StatusNotFound, "not_found", "session not found")
		case errors.Is(err, ErrInvalidArgument): h.errs.BadRequest(w, "invalid_argument", err.Error())
		default: h.errs.Internal(w, "internal", "internal error")
		}
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(toSessionDTO(sess))
}
```
Write `toDigestDTO` mapping `DeliveryDigest`→`apiv1.DeliveryDigest` (mirror Plan 1 `toSessionDTO` style). Add routes in `routes.go`:
```go
		rr.Get("/{checkout_id}/delivery-options", deps.Handler.DeliveryOptions)
		rr.Patch("/{checkout_id}/delivery-method", deps.Handler.SetDeliveryMethod)
```

- [ ] **Step 3: Build + test + commit**

Run `go build ./... && go test ./...`.
```bash
git add api internal
git commit -m "feat(checkout): GET delivery-options + PATCH delivery-method endpoints"
```

---

## Task 6: Wire + e2e + DoD

- [ ] **Step 1: Wire stub DeliverySource**

In `internal/app/wire/checkout.go`, build the source and use `NewServiceWithDelivery`:
```go
import adapter "gj-checkout/internal/adapters/checkout"
// ...
src := adapter.NewStubDeliverySource()
svc := checkout.NewServiceWithDelivery(store, src)
return checkout.NewHandler(svc, errs)
```
(`internal/app/wire` is the only package allowed to import both `adapters/` and `domains/` — per ecom-gateway ADR-0010/0012.)

- [ ] **Step 2: e2e smoke**

```bash
make migrate && make run
ID=$(curl -s -X POST :8080/api/v1/checkout -d '{"customer_id":"c1","basket_id":"2000019994"}' | jq -r .checkout_id)
curl -s :8080/api/v1/checkout/$ID/delivery-options | jq '.methods[] | {type:.delivery_type, coverage, cart_size}'
curl -s -X PATCH :8080/api/v1/checkout/$ID/delivery-method -d '{"type":"courier"}' | jq '{status, selection}'
```
Expected: digest lists 4 methods with coverage «X из N» (courier/pvz/store_pickup = 2/4, store_reserve differs); PATCH returns `status:"selecting"` + selection with pinned dispatch_date + courier komplektaciya (hashed interval id).

- [ ] **Step 3: Gates + commit + tag**

`go test ./... && make generate && make lint && go vet ./...`.
```bash
git commit -am "test(checkout): e2e delivery resolution green" --allow-empty
git tag v0.0.3-resolver
```

## Definition of Done (Plan 3)
- Resolver normalizes all 3 OMS shapes → `Komplektaciya`/`Digest`, table-tested on real fixtures (coverage «X из N», 3 shapes, hashed-id presence, partial availability, `cartAvailabillity` quirk).
- `GET …/delivery-options` returns per-method digest; `PATCH …/delivery-method` resolves best komplektaciya, **pins dispatch_date**, persists selection (`status→selecting`).
- Stub `DeliverySource` runs the real resolver over real fixtures.
- `go test ./...`, `make generate/lint`, `go vet` green.
