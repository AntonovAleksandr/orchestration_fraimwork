# Checkout v1 — Plan 3: Delivery domain (§2c resolver + clustering) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **🔄 РЕ-ПЛАН (2026-05-31) под карту доменов.** Этот файл заменяет прежний single-domain план. Канон раскладки: [`platform-new/checkout/docs/architecture/domain-map.md`](../../../platform-new/checkout/docs/architecture/domain-map.md). Главные отличия от прежней версии: (1) доставка = **отдельный домен** `internal/domains/delivery` с портом `DeliverySource`→OMS; (2) нормализация-резолвер = в `internal/adapters/delivery/`; (3) выбор пишется в агрегат **через домен `session`** (он корень-оркестратор) по consumer-порту `SessionGateway`, мост — в `internal/app/wire`; (4) деньги = **`int64` копейки** (рубли OMS → копейки в резолвере, без float); (5) добавлена **серверная кластеризация ПВЗ** (in-memory, без PostGIS); (6) исправлена ошибка прежнего плана — **ПВЗ берётся из `pickup-points`, а не из `pickup-stores`** (4 формы OMS, не 3).

**Goal:** Build the `delivery` bounded-context — a `DeliverySource` port plus the §2c **resolver** (pure functions in `internal/adapters/delivery/` that normalize the **four** OMS logistics response shapes into one domain `Komplektaciya`/`DeliveryDigest`, converting rubles→kopecks), a v1 stub `DeliverySource` over real captured fixtures, **server-side PVZ clustering** (in-memory, no PostGIS), the granular delivery endpoints (digest / drill-in list / pickup-points map / set-method), and **dispatch_date pinning** — with the chosen selection persisted to the aggregate **through the `session` domain**.

**Architecture:** Per `domain-map.md`. `delivery` is a stateless capability domain: it owns the `DeliverySource` port (→OMS), the domain types (`Komplektaciya`, `DeliveryDigest`, …), the clustering read-function, and the four delivery endpoints. It does **not** write the session itself — `session` is the only consistency root. `delivery` mutates the aggregate through a consumer-defined `SessionGateway` port (declared in `delivery`, implemented by an adapter in `internal/app/wire` that wraps `*session.Service`). Normalization of the raw OMS shapes lives in `internal/adapters/delivery/` (client/DTO→domain mapping is an adapter concern); the v1 stub `DeliverySource` decodes real fixtures through the **same** normalize funcs the phase-2 starfish-oms adapter will use — so the risky logic is real and table-tested now. Domains never import each other (`boundary_test.go` enforces it); `internal/app/wire` is the only package importing both `domains/` and `adapters/`.

**Tech Stack:** Go stdlib `encoding/json` (+ `json.Number` for money) + `embed`; existing pgx repo + `gj-go-migrate`; `chi/v5`; `oapi-codegen` types-only (per-domain `include-tags`).

**Prereq:** Plans 1–2 complete (session domain renamed to `session`, Postgres + pgx repo + migration 0001 live). Local Postgres up: `docker compose -f dev/docker-compose.yml up -d` (:5544). Repo: `platform-new/checkout` (module `gj-checkout`).

**Grounding — the real OMS shapes (source of truth), captured from stage:** `platform-new/checkout/fixtures/oms/{delivery-preliminary,pickup-stores,delivery-intervals,pickup-points}.json`. Verified shapes:
- **`delivery-preliminary.json`** — `{"data":[ {deliveryTypeId, available, delivery:{minDays,minCost,freeCostCartThreshold}, availablePaymentTypes, cart:{items:[{id, available, stock:[{warehouseId,availableQuantity,available}]}]}} ]}`. 4 entries — one per `deliveryTypeId` (`delivery`,`pickup`,`pickupinstore`,`reserveinstore`). Money in **rubles** (`minCost:299`, `freeCostCartThreshold:1500`). → **per-method digest**.
- **`pickup-stores.json`** — **bare array** (64). Each: `{deliveryTypeId (only `pickupinstore`/`reserveinstore`), instock, productAvailability:[{productId,availableQuantity,available}], dispatchWarehouseId, dispatchDate, readyForPickup, logisticGroupId, carrierId, tariffId, deliveryCost(rubles, 0), coordinates:{latitude,longitude}, pickupStore:{code,name,address,storageTime,warehouseId,…}}`. **No hashed id** — selection key = `pickupStore.code` + `dispatchDate`. → **store komplektacii (C&C / C&R)**.
- **`delivery-intervals.json`** (courier) — `{"data":[ {inventory:{dispatchWarehouse, dispatchDate, availableQuantity, cartAvailabillity:[{productId,availableQuantity,available}]  // NB OMS typo: double-l}, logisticGroupId, logisticRuleId, intervals:{list:[{id(hashed,"QOOcGGOK"), date, from, to, deliveryCost(rubles,299), actualDeliveryCost(rubles,317.2), carrierId, tariffId}]}} ]}`. → **courier komplektacii**, one per interval, **hashed `id`**.
- **`pickup-points.json`** (PVZ) — **bare array** (3963 / 3.5 MB). Each: `{id(hashed,"dpd-828K"), originalId, carrierId(5post/russianpost/cdek/dpd/yandex), coordinates:{latitude,longitude}, instock, productAvailability:[…], deliveryCost(rubles), dispatchDate, name, orderDimensionsExceeded, orderWeightExceeded, orderPackageWeightExceeded, type}`. → **PVZ komplektacii** (hashed `id` + coordinates) → **clustering surface**.

**Design refs:** spec §2 (Komplektaciya model), §2c (resolver invariants), §3 (two-level delivery + PVZ viewport/clustering), §5 (money kopecks), §6 (drift / pin date). `docs/research/2026-05-30-money-kopecks-rubles.md` (money policy).

**Invariants the resolver MUST hold (and table-test on the real fixtures):**
1. **coverage «X из N»** = `count(available)` over the per-line availability list (`productAvailability` for stores/PVZ; `inventory.cartAvailabillity` for courier; `cart.items[].available` for preliminary).
2. **four shapes → one `Komplektaciya`** (+ digest from preliminary).
3. **delivery-type normalization:** `delivery`→`courier`, `pickup`→`pvz`, `pickupinstore`→`store_pickup` (C&C), `reserveinstore`→`store_reserve` (C&R).
4. **hashed `IntervalID` present** for COURIER (interval `id`) + PVZ (point `id`); **empty** for STORE (key = `pickupStore.code` + `dispatchDate`).
5. **partial availability** preserved per-item (`Items[]` keeps unavailable lines; `Coverage` counts only available).
6. **quirk** field name `cartAvailabillity` (double-l) decodes into courier items.
7. **money = int64 kopecks**: rubles in the wire (`299`, `317.2`, `1500`) → `29900`, `31720`, `150000` kopecks (string-based decimal conversion, **no float**).

---

## File Structure (Plan 3)

```
checkout/
├── migrations/0002_session_selection.{up,down}.sql      # selection + cart_snapshot JSONB
├── internal/domains/session/
│   ├── types.go            (modify)  + Selection, CartLine; Session.{Cart,Selection}; SessionStore.UpdateSelection
│   ├── service.go          (modify)  + ApplyDeliverySelection
│   ├── repository.go       (modify)  Create/Get read/write selection+cart_snapshot; + UpdateSelection
│   ├── stub.go             (modify)  InMemoryStore.UpdateSelection
│   ├── service_test.go     (modify)  + ApplyDeliverySelection test
│   └── repository_test.go  (modify)  + selection round-trip test
├── internal/domains/delivery/
│   ├── doc.go              go:generate directive (oapi-codegen, tag=delivery)
│   ├── types.go            DeliveryType, ItemAvail, Point, Features, Komplektaciya, MethodSummary,
│   │                       DeliveryDigest, BBox, Cluster, ClusterResult, CartLine, DeliverySelection,
│   │                       CheckoutRef, AppliedSelection; ports DeliverySource + SessionGateway; markers
│   ├── cluster.go          ClusterPickupPoints (pure, in-memory grid) — clustering read-function
│   ├── cluster_test.go     clustering tests (bbox filter; low-zoom→clusters; high-zoom→points)
│   ├── service.go          Service: GetDeliveryDigest, ListKomplektacii, PickupClusters, SetDeliveryMethod, pickBest
│   ├── service_test.go     service tests (fake source + fake gateway): pin date, persist via gateway
│   ├── handler.go          HTTP edge + DTO mapping (domain → apiv1)
│   ├── routes.go           Deps + Mount: GET delivery-options, GET komplektacii, GET pickup-points, PATCH delivery-method
│   ├── boundary_test.go    no upward/cross-domain/adapter imports (mirror session)
│   └── apiv1/openapi.gen.go  generated DTOs (tag=delivery)
├── internal/adapters/delivery/
│   ├── doc.go              package doc
│   ├── kopecks.go          rublesToKopecks(json.Number) int64 — float-free decimal→kopecks
│   ├── kopecks_test.go     "299"→29900, "317.2"→31720, "0"/""→0, rounding
│   ├── raw.go              raw OMS structs (4 shapes; faithful; quirks preserved; money=json.Number)
│   ├── resolver.go         normalize* funcs: raw shape → []domain.Komplektaciya / DeliveryDigest
│   ├── resolver_test.go    table tests on real fixtures (THE risk surface)
│   ├── stub.go             StubDeliverySource: embeds curated fixtures → resolver → domain types
│   └── testdata/{delivery-preliminary,pickup-stores,delivery-intervals,pickup-points}.json  (curated)
├── internal/app/wire/
│   ├── session.go          (modify)  split into SessionService + SessionHandler builders
│   └── delivery.go         (create)  sessionGateway adapter (delivery.SessionGateway → *session.Service) + Delivery builder
├── internal/app/container.go        (modify)  build session.Service once; + DeliveryHandler
├── internal/platform/transport/{routes.go,server.go}  (modify)  mount delivery
├── api/v1/openapi.yaml               (modify)  + delivery tag + 4 paths
├── api/v1/paths/delivery.yaml        (create)  delivery path items
├── api/v1/components/schemas/delivery.yaml  (create)  delivery schemas
└── api/v1/oapi-codegen-delivery.yaml (create)  per-domain codegen config (include-tags: delivery)
```

**Architectural decisions baked into this plan (deviations from the old plan3, all per `domain-map.md`):**
- **D1 — delivery is its own domain**, not folded into session/checkout. It owns `DeliverySource`, types, clustering, endpoints.
- **D2 — the write crosses through `session`** via the consumer-defined `SessionGateway` port. `delivery` never imports `session`; `wire` bridges (maps types + translates `session.ErrNotFound`→`delivery.ErrNotFound`). This is the only way to satisfy `boundary_test.go` while keeping `session` the single consistency root.
- **D3 — `session.Selection` is a slim *decision* (intent), not the rich `Komplektaciya`.** Per "store intent, not truth": session persists `{delivery_type, pinned_dispatch_date, interval_id, point_key, coverage, cart_size, delivery_cost_kopecks, snapshot}`. The rich `Komplektaciya` is mapped to this slim form at the `wire` bridge. This also keeps `session` free of `delivery`'s types.
- **D4 — PATCH delivery-method returns a delivery-owned `AppliedSelection`** (`{checkout_id, status, selection}`), not the full `CheckoutSession` (which is session-owned). Enough for the frontend; no boundary cross.
- **D5 — money is `int64` kopecks end-to-end.** Resolver converts OMS rubles→kopecks via a string-based decimal parser (`kopecks.go`), never float. (Old plan used `float64` — fixed.)
- **D6 — four shapes.** PVZ = `pickup-points` (hashed id + coords, clustered), NOT `pickup-stores`. (Old plan's `DeliveryPVZ` filter over `rawStore` was wrong.)

---

## Task 1: `session` — Selection/Cart types + persistence + `ApplyDeliverySelection`

**Files:**
- Modify: `internal/domains/session/types.go`
- Modify: `internal/domains/session/service.go`
- Modify: `internal/domains/session/repository.go`
- Modify: `internal/domains/session/stub.go`
- Create: `migrations/0002_session_selection.up.sql`, `migrations/0002_session_selection.down.sql`
- Test: `internal/domains/session/service_test.go`, `internal/domains/session/repository_test.go`

- [ ] **Step 1: Add domain types to `internal/domains/session/types.go`**

Add these types (after the existing `Session` struct). Add `import "encoding/json"` to the import block (it currently imports only `context`, `errors`).

```go
// CartLine is one snapshot cart item — the user's INTENT (productId + qty), not
// live truth. v1: populated empty (phase-2 fills from ENSI baskets). vendorCodeSku.
type CartLine struct {
	ProductID string `json:"product_id"`
	Quantity  int    `json:"quantity"`
}

// Selection is the user's chosen delivery decision, persisted on the session.
// It is a slim DECISION (intent), not the rich Komplektaciya — per "store intent,
// not truth". The delivery domain maps its Komplektaciya into this at the wire
// bridge; session never imports delivery types. Money is int64 kopecks.
type Selection struct {
	DeliveryType        string          `json:"delivery_type"`           // courier|pvz|store_pickup|store_reserve
	PinnedDispatchDate  string          `json:"pinned_dispatch_date"`    // anti-drift pin (§6)
	IntervalID          string          `json:"interval_id,omitempty"`   // hashed (courier/pvz); "" for store
	PointKey            string          `json:"point_key,omitempty"`     // store code or pickup_point_id
	Coverage            int             `json:"coverage"`                // "X из N"
	CartSize            int             `json:"cart_size"`               // N
	DeliveryCostKopecks int64           `json:"delivery_cost_kopecks"`   // int64 kopecks, never float
	Snapshot            json.RawMessage `json:"komplektaciya_snapshot,omitempty"` // advisory blob
}
```

Add two fields to the existing `Session` struct (keep existing fields):
```go
	Cart      []CartLine `json:"-"` // snapshot of intent; v1 empty
	Selection *Selection `json:"-"` // nil until a delivery method is chosen
```

Add `UpdateSelection` to the `SessionStore` interface:
```go
type SessionStore interface {
	Create(ctx context.Context, s Session) error
	Get(ctx context.Context, checkoutID string) (Session, error)
	UpdateSelection(ctx context.Context, checkoutID string, sel Selection) error
}
```

- [ ] **Step 2: Migration 0002**

`migrations/0002_session_selection.up.sql`:
```sql
ALTER TABLE checkout_sessions ADD COLUMN IF NOT EXISTS selection     jsonb NULL;
ALTER TABLE checkout_sessions ADD COLUMN IF NOT EXISTS cart_snapshot jsonb NULL;
```
`migrations/0002_session_selection.down.sql`:
```sql
ALTER TABLE checkout_sessions DROP COLUMN IF EXISTS cart_snapshot;
ALTER TABLE checkout_sessions DROP COLUMN IF EXISTS selection;
```
Run: `make migrate-up`
Expected: applies cleanly; `make migrate-version` → `version=2 dirty=false`.

- [ ] **Step 3: Write the failing test** — append to `internal/domains/session/service_test.go`

```go
func TestApplyDeliverySelection_setsSelectionAndStatus(t *testing.T) {
	store := NewInMemoryStore()
	svc := NewService(store)
	sess, err := svc.CreateSession(context.Background(), CreateSessionInput{CustomerID: "c", BasketID: "2000019994"})
	if err != nil {
		t.Fatalf("CreateSession: %v", err)
	}
	sel := Selection{DeliveryType: "courier", PinnedDispatchDate: "2026-05-31", IntervalID: "QOOcGGOK", Coverage: 2, CartSize: 4, DeliveryCostKopecks: 29900}

	got, err := svc.ApplyDeliverySelection(context.Background(), sess.CheckoutID, sel)
	if err != nil {
		t.Fatalf("ApplyDeliverySelection: %v", err)
	}
	if got.Status != StatusSelecting {
		t.Fatalf("status must advance to selecting, got %q", got.Status)
	}
	if got.Selection == nil || got.Selection.PinnedDispatchDate != "2026-05-31" {
		t.Fatal("selection (with pinned date) not set on returned session")
	}
	reloaded, err := store.Get(context.Background(), sess.CheckoutID)
	if err != nil {
		t.Fatalf("store.Get: %v", err)
	}
	if reloaded.Selection == nil || reloaded.Selection.IntervalID != "QOOcGGOK" {
		t.Fatal("selection not persisted")
	}
}

func TestApplyDeliverySelection_notFound(t *testing.T) {
	svc := NewService(NewInMemoryStore())
	_, err := svc.ApplyDeliverySelection(context.Background(), "missing", Selection{DeliveryType: "courier"})
	if !errors.Is(err, ErrNotFound) {
		t.Fatalf("expected ErrNotFound, got %v", err)
	}
}
```
Add `"errors"` to the test file imports if absent.

- [ ] **Step 4: Run → FAIL**

Run: `go test ./internal/domains/session/ -run TestApplyDeliverySelection -v`
Expected: FAIL — `svc.ApplyDeliverySelection undefined`, `store.UpdateSelection undefined`.

- [ ] **Step 5: Implement `ApplyDeliverySelection` in `internal/domains/session/service.go`**

Add (the `fmt` import is already present):
```go
// ApplyDeliverySelection persists a chosen delivery selection onto the session
// aggregate and advances the lifecycle to `selecting`. It is the ONLY way the
// delivery capability mutates the session — session stays the single consistency
// root. Returns ErrNotFound when the session does not exist.
func (s *Service) ApplyDeliverySelection(ctx context.Context, checkoutID string, sel Selection) (Session, error) {
	sess, err := s.store.Get(ctx, checkoutID)
	if err != nil {
		return Session{}, err // ErrNotFound passes through
	}
	if err := s.store.UpdateSelection(ctx, checkoutID, sel); err != nil {
		return Session{}, fmt.Errorf("apply delivery selection: %w", err)
	}
	sess.Selection = &sel
	sess.Status = StatusSelecting
	return sess, nil
}
```

- [ ] **Step 6: Implement `UpdateSelection` in `internal/domains/session/stub.go`** (InMemoryStore)

```go
func (s *InMemoryStore) UpdateSelection(_ context.Context, checkoutID string, sel Selection) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	sess, ok := s.data[checkoutID]
	if !ok {
		return ErrNotFound
	}
	sess.Selection = &sel
	sess.Status = StatusSelecting
	s.data[checkoutID] = sess
	return nil
}
```

- [ ] **Step 7: Run → PASS**

Run: `go test ./internal/domains/session/ -run TestApplyDeliverySelection -v`
Expected: PASS (both).

- [ ] **Step 8: Persist selection + cart in the Postgres repository** — modify `internal/domains/session/repository.go`

Add `"encoding/json"` to the imports. Replace `Create` and `Get`, and add `UpdateSelection`:

```go
// Create inserts a new checkout session (selection NULL; cart_snapshot from intent).
func (r *Repository) Create(ctx context.Context, s Session) error {
	var cartJSON []byte
	if len(s.Cart) > 0 {
		var err error
		if cartJSON, err = json.Marshal(s.Cart); err != nil {
			return fmt.Errorf("checkout: marshal cart: %w", err)
		}
	}
	const q = `
		INSERT INTO checkout_sessions
			(checkout_id, client_order_id, customer_id, basket_id, status, totals_checksum, cart_snapshot)
		VALUES ($1, $2, $3, $4, $5, $6, $7)`
	_, err := r.db.Exec(ctx, q,
		s.CheckoutID, s.ClientOrderID, s.CustomerID, s.BasketID, string(s.Status), s.TotalsChecksum, cartJSON)
	if err != nil {
		return fmt.Errorf("checkout: insert session: %w", err)
	}
	return nil
}

// Get returns a checkout session by id; returns ErrNotFound when absent.
func (r *Repository) Get(ctx context.Context, checkoutID string) (Session, error) {
	const q = `
		SELECT checkout_id, client_order_id, customer_id, basket_id, status, totals_checksum, selection, cart_snapshot
		FROM checkout_sessions WHERE checkout_id = $1`
	var s Session
	var status string
	var selJSON, cartJSON []byte
	err := r.db.QueryRow(ctx, q, checkoutID).Scan(
		&s.CheckoutID, &s.ClientOrderID, &s.CustomerID, &s.BasketID, &status, &s.TotalsChecksum, &selJSON, &cartJSON)
	if errors.Is(err, pgx.ErrNoRows) {
		return Session{}, ErrNotFound
	}
	if err != nil {
		return Session{}, fmt.Errorf("checkout: select session: %w", err)
	}
	s.Status = Status(status)
	if len(selJSON) > 0 {
		var sel Selection
		if err := json.Unmarshal(selJSON, &sel); err != nil {
			return Session{}, fmt.Errorf("checkout: unmarshal selection: %w", err)
		}
		s.Selection = &sel
	}
	if len(cartJSON) > 0 {
		if err := json.Unmarshal(cartJSON, &s.Cart); err != nil {
			return Session{}, fmt.Errorf("checkout: unmarshal cart: %w", err)
		}
	}
	return s, nil
}

// UpdateSelection persists the chosen selection (JSONB), advances status to
// `selecting`, and bumps updated_at. Returns ErrNotFound when the session is absent.
func (r *Repository) UpdateSelection(ctx context.Context, checkoutID string, sel Selection) error {
	b, err := json.Marshal(sel)
	if err != nil {
		return fmt.Errorf("checkout: marshal selection: %w", err)
	}
	ct, err := r.db.Exec(ctx,
		`UPDATE checkout_sessions SET selection=$2, status=$3, updated_at=now() WHERE checkout_id=$1`,
		checkoutID, b, string(StatusSelecting))
	if err != nil {
		return fmt.Errorf("checkout: update selection: %w", err)
	}
	if ct.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}
```
> NB: confirm migration 0001 created an `updated_at` column. If it did not, add `ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now()` to `0002_session_selection.up.sql` (and the matching DROP in down) — check `migrations/0001_checkout_sessions.up.sql` first.

- [ ] **Step 9: Repository round-trip test** — append to `internal/domains/session/repository_test.go`

The existing integration test in that file reads `CHECKOUT_TEST_DB_DSN` and `t.Skip`s when unset (it does **not** use a helper). Mirror that exact guard. Append:
```go
func TestRepository_SelectionRoundTrip(t *testing.T) {
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
	s := Session{CheckoutID: uuid.NewString(), ClientOrderID: "2000019994", CustomerID: "c", BasketID: "2000019994", Status: StatusDraft}
	if err := repo.Create(ctx, s); err != nil {
		t.Fatalf("Create: %v", err)
	}
	sel := Selection{DeliveryType: "courier", PinnedDispatchDate: "2026-05-31", IntervalID: "QOOcGGOK", Coverage: 2, CartSize: 4, DeliveryCostKopecks: 29900}
	if err := repo.UpdateSelection(ctx, s.CheckoutID, sel); err != nil {
		t.Fatalf("UpdateSelection: %v", err)
	}
	got, err := repo.Get(ctx, s.CheckoutID)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.Status != StatusSelecting || got.Selection == nil || got.Selection.IntervalID != "QOOcGGOK" || got.Selection.DeliveryCostKopecks != 29900 {
		t.Fatalf("selection did not round-trip: %+v", got.Selection)
	}
}
```
(The file already imports `context`, `os`, `testing`, `storage`, and `uuid` — no new imports needed.)

- [ ] **Step 10: Run + commit**

Run (with local Postgres up so the integration tests run):
```bash
export CHECKOUT_TEST_DB_DSN='postgres://checkout:checkout@127.0.0.1:5544/checkout?sslmode=disable'
go build ./... && go test ./internal/domains/session/ -count=1
```
Expected: PASS (the two new unit tests + the integration round-trip; integration tests `t.Skip` if `CHECKOUT_TEST_DB_DSN` is unset).
```bash
git add migrations internal/domains/session
git commit -m "feat(session): selection/cart types + ApplyDeliverySelection + JSONB persistence (migration 0002)"
```

---

## Task 2: `delivery` domain — types + ports + markers + boundary test

**Files:**
- Create: `internal/domains/delivery/doc.go`, `types.go`, `boundary_test.go`

- [ ] **Step 1: `internal/domains/delivery/doc.go`**

```go
// Package delivery is the delivery capability domain: it owns the DeliverySource
// port (→ OMS logistics), the normalized Komplektaciya/DeliveryDigest model, the
// PVZ clustering read-function, and the granular delivery endpoints. It is a
// STATELESS capability — it never writes the session; the chosen selection is
// applied to the aggregate through the SessionGateway port (session is the only
// consistency root). v1 runs a stub DeliverySource over real fixtures.
package delivery

//go:generate oapi-codegen --config ../../../api/v1/oapi-codegen-delivery.yaml ../../../api/v1/bundle/openapi.yaml
```

- [ ] **Step 2: `internal/domains/delivery/types.go`**

```go
package delivery

import (
	"context"
	"errors"
)

// Marker errors (handler maps these to HTTP). The wire bridge translates
// session.ErrNotFound → delivery.ErrNotFound so delivery never imports session.
var (
	ErrInvalidArgument = errors.New("invalid argument")
	ErrNotFound        = errors.New("not found")
)

// DeliveryType is the normalized fulfillment path (OMS deliveryTypeId → domain).
type DeliveryType string

const (
	DeliveryCourier      DeliveryType = "courier"       // OMS "delivery"
	DeliveryPVZ          DeliveryType = "pvz"           // OMS "pickup"        (pickup-points)
	DeliveryStorePickup  DeliveryType = "store_pickup"  // OMS "pickupinstore" (C&C)
	DeliveryStoreReserve DeliveryType = "store_reserve" // OMS "reserveinstore"(C&R)
)

// ItemAvail is per-cart-line availability within a komplektaciya. ProductID = vendorCodeSku.
type ItemAvail struct {
	ProductID         string
	AvailableQuantity int
	Available         bool
}

// Point is the fulfillment location.
type Point struct {
	WarehouseID   string
	StoreCode     string  // pickupStore.code (stores)
	PickupPointID string  // hashed id (PVZ)
	CarrierID     string
	Name          string
	Address       string
	Lat, Lng      float64 // geo (not money) — float64 is correct here
}

// Features are display/constraint flags of a komplektaciya.
type Features struct {
	TryOn       bool
	PassportReq bool
	StorageDays int
	Oversize    bool // orderDimensions/Weight/PackageWeightExceeded (PVZ)
}

// Komplektaciya is one normalized fulfillment option = inventory subset + point + interval.
// Money is int64 kopecks (resolver converts OMS rubles).
type Komplektaciya struct {
	DeliveryType        DeliveryType
	Items               []ItemAvail
	Coverage            int // count(Available) — "X из N"
	Point               Point
	IntervalID          string // hashed (courier/pvz); "" for store
	DispatchDate        string
	PromisedDate        string
	TimeFrom            string // courier only
	TimeTo              string // courier only
	CarrierID           string
	TariffID            string
	LogisticGroup       string
	DeliveryCostKopecks int64
	Features            Features
}

// MethodSummary is one card in "Способ получения" (per-method digest).
type MethodSummary struct {
	DeliveryType         DeliveryType
	Available            bool
	Coverage             int // available items count for this method
	CartSize             int // total cart lines
	MinCostKopecks       int64
	MinDays              int
	FreeThresholdKopecks int64
	PaymentTypes         []string
}

// DeliveryDigest is the compact per-method summary for the entry context.
type DeliveryDigest struct {
	Methods []MethodSummary
}

// BBox is a geographic bounding box for the PVZ map.
type BBox struct {
	MinLat, MinLng, MaxLat, MaxLng float64
}

// Cluster is an aggregated marker (no per-item coverage — only count).
type Cluster struct {
	Lat, Lng float64
	Count    int
}

// ClusterResult is the PVZ-map payload: clusters at low zoom, points at high zoom.
type ClusterResult struct {
	Clusters []Cluster       // zoomed-out
	Points   []Komplektaciya // zoomed-in (with coverage)
}

// CartLine is the delivery domain's view of a cart item (decoupled from session's
// own CartLine — domains do not share types).
type CartLine struct {
	ProductID string
	Quantity  int
}

// DeliverySelection is the slim decision the delivery domain hands to session.
type DeliverySelection struct {
	DeliveryType        DeliveryType
	PinnedDate          string
	IntervalID          string
	PointKey            string
	Coverage            int
	CartSize            int
	DeliveryCostKopecks int64
	Snapshot            []byte // json of the chosen Komplektaciya (advisory)
}

// AppliedSelection is what PATCH delivery-method returns (delivery-owned; NOT the
// full session, which belongs to the session domain).
type AppliedSelection struct {
	CheckoutID string
	Status     string
	Selection  DeliverySelection
}

// CheckoutRef is the slice of session state the delivery domain needs.
type CheckoutRef struct {
	CheckoutID string
	Cart       []CartLine
	// City string // phase-2: region/city join for cart-and-city-dependent resolve
}

// DeliverySource resolves fulfillment options for a cart. Consumer-defined port;
// v1 stub feeds fixtures, phase-2 adapter calls starfish-oms. Returns DOMAIN types —
// normalization of OMS shapes (and rubles→kopecks) happens in the adapter (§2c).
type DeliverySource interface {
	Digest(ctx context.Context, cart []CartLine) (DeliveryDigest, error)
	Options(ctx context.Context, cart []CartLine, t DeliveryType) ([]Komplektaciya, error)
}

// SessionGateway is delivery's consumer-defined port into the session aggregate.
// The wire layer implements it over *session.Service (maps types + translates
// session.ErrNotFound → delivery.ErrNotFound). delivery never imports session.
type SessionGateway interface {
	Lookup(ctx context.Context, checkoutID string) (CheckoutRef, error)
	ApplyDeliverySelection(ctx context.Context, checkoutID string, sel DeliverySelection) (AppliedSelection, error)
}
```

- [ ] **Step 3: `internal/domains/delivery/boundary_test.go`** (mirror session's, with `self` = delivery)

Copy `internal/domains/session/boundary_test.go` verbatim and change only:
- the function name to `TestBoundary_DeliveryNoUpwardOrCrossDomainImports`,
- `const self = "gj-checkout/internal/domains/delivery"`.
Keep the same `forbiddenPrefixes` (it already forbids `gj-checkout/internal/domains` — which now blocks importing `session` — and `gj-checkout/internal/adapters`). The allowed platform packages (`httpx`, `reqctx`) stay allowed by omission.

- [ ] **Step 4: Build + commit**

Run: `go build ./internal/domains/delivery/ && go test ./internal/domains/delivery/ -run TestBoundary -v`
Expected: builds; boundary test PASS.
```bash
git add internal/domains/delivery/{doc.go,types.go,boundary_test.go}
git commit -m "feat(delivery): domain types + DeliverySource/SessionGateway ports + boundary test"
```

---

## Task 3: `adapters/delivery` — kopecks helper + resolver (TDD on real fixtures)

**Files:**
- Create: `internal/adapters/delivery/doc.go`, `kopecks.go`, `kopecks_test.go`, `raw.go`, `resolver.go`, `resolver_test.go`, `testdata/*.json`

- [ ] **Step 1: Curate fixtures into adapter testdata**

```bash
mkdir -p internal/adapters/delivery/testdata
cp fixtures/oms/delivery-preliminary.json internal/adapters/delivery/testdata/
cp fixtures/oms/pickup-stores.json        internal/adapters/delivery/testdata/
cp fixtures/oms/delivery-intervals.json   internal/adapters/delivery/testdata/
cp fixtures/oms/pickup-points.json        internal/adapters/delivery/testdata/
```
Then **trim** the two large arrays so the embed is light and tests are fast, preserving the invariant-exercising structure:
- `testdata/pickup-stores.json` → keep ~4 records: ≥1 `pickupinstore` **and** ≥1 `reserveinstore`, and ≥1 with partial `productAvailability` (some `available:false`). Keep each record's full `pickupStore` object (code/name/address/coordinates/storageTime).
- `testdata/pickup-points.json` → keep ~40 records spread across several `carrierId` values and **geographically spread** (a tight cluster of ≥3 near one lat/lng + a few far-apart), so clustering is demonstrable; keep `id`, `coordinates`, `instock`, `productAvailability`, `deliveryCost`, `dispatchDate`, `carrierId`, `name`.
- Keep `delivery-preliminary.json` and `delivery-intervals.json` as-is (already small).
Use `jq` to trim, e.g. `jq '[.[0,1,2,3]]' fixtures/oms/pickup-stores.json > internal/adapters/delivery/testdata/pickup-stores.json` (pick indices that satisfy the constraints above; inspect with `jq '[.[].deliveryTypeId]'` first).

- [ ] **Step 2: `internal/adapters/delivery/doc.go`**

```go
// Package delivery (adapter) normalizes the raw OMS logistics response shapes into
// the delivery domain's Komplektaciya/DeliveryDigest model (§2c resolver) and
// provides the v1 stub DeliverySource over baked fixtures. Money fields arrive as
// OMS rubles and are converted to int64 kopecks here, on the boundary (§5).
package delivery
```

- [ ] **Step 3: `internal/adapters/delivery/kopecks.go`** — float-free rubles→kopecks

```go
package delivery

import (
	"encoding/json"
	"strconv"
	"strings"
)

// rublesToKopecks converts an OMS money value (rubles, decimal string e.g. "299",
// "317.2", "1500") to int64 kopecks WITHOUT float (money policy §5). Empty/invalid
// → 0. Rounds half-up at the 2nd decimal. Negative handled.
func rublesToKopecks(n json.Number) int64 {
	s := strings.TrimSpace(string(n))
	if s == "" {
		return 0
	}
	neg := strings.HasPrefix(s, "-")
	s = strings.TrimPrefix(s, "-")
	intPart, fracPart, _ := strings.Cut(s, ".")
	whole, err := strconv.ParseInt(intPart, 10, 64)
	if err != nil {
		return 0
	}
	// normalize fractional to at least 3 digits so we can round the 2nd decimal
	frac := fracPart + "000"
	d1 := int64(frac[0] - '0')
	d2 := int64(frac[1] - '0')
	d3 := int64(frac[2] - '0')
	kop := whole*100 + d1*10 + d2
	if d3 >= 5 {
		kop++ // round half-up
	}
	if neg {
		return -kop
	}
	return kop
}
```

- [ ] **Step 4: `internal/adapters/delivery/kopecks_test.go`**

```go
package delivery

import (
	"encoding/json"
	"testing"
)

func TestRublesToKopecks(t *testing.T) {
	cases := []struct {
		in   string
		want int64
	}{
		{"299", 29900},
		{"317.2", 31720},
		{"1500", 150000},
		{"0", 0},
		{"", 0},
		{"12.99", 1299},
		{"12.995", 1300}, // round half-up at 2nd decimal
		{"100.1", 10010},
	}
	for _, c := range cases {
		if got := rublesToKopecks(json.Number(c.in)); got != c.want {
			t.Errorf("rublesToKopecks(%q) = %d, want %d", c.in, got, c.want)
		}
	}
}
```
Run: `go test ./internal/adapters/delivery/ -run TestRublesToKopecks -v` → PASS.

- [ ] **Step 5: `internal/adapters/delivery/raw.go`** — faithful raw structs (money = `json.Number`)

```go
package delivery

import "encoding/json"

// raw* mirror the OMS logistics JSON shapes (faithful; phase-2 replaces with the
// starfish-oms client DTOs). Field names/tags MUST match the fixtures exactly.
// Money fields are json.Number (OMS rubles) — converted to kopecks in resolver.go.
// Coordinates are float64 (geo, not money).

// --- delivery-preliminary: {"data":[ ... ]} ---
type rawPreliminary struct {
	Data []rawPrelimType `json:"data"`
}
type rawPrelimType struct {
	DeliveryTypeID   string         `json:"deliveryTypeId"`
	Available        bool           `json:"available"`
	Delivery         rawPrelimDeliv `json:"delivery"`
	AvailablePayment []string       `json:"availablePaymentTypes"`
	Cart             rawPrelimCart  `json:"cart"`
}
type rawPrelimDeliv struct {
	MinDays               int         `json:"minDays"`
	MinCost               json.Number `json:"minCost"`
	FreeCostCartThreshold json.Number `json:"freeCostCartThreshold"`
}
type rawPrelimCart struct {
	Items []rawPrelimItem `json:"items"`
}
type rawPrelimItem struct {
	ID        string `json:"id"`
	Available bool   `json:"available"`
}

// --- pickup-stores: bare array (pickupinstore / reserveinstore only) ---
type rawStore struct {
	DeliveryTypeID      string         `json:"deliveryTypeId"`
	Instock             int            `json:"instock"`
	ProductAvailability []rawProdAvail `json:"productAvailability"`
	DispatchWarehouseID string         `json:"dispatchWarehouseId"`
	DispatchDate        string         `json:"dispatchDate"`
	ReadyForPickup      string         `json:"readyForPickup"`
	LogisticGroupID     string         `json:"logisticGroupId"`
	CarrierID           string         `json:"carrierId"`
	TariffID            string         `json:"tariffId"`
	DeliveryCost        json.Number    `json:"deliveryCost"`
	Coordinates         rawCoords      `json:"coordinates"`
	PickupStore         rawPickupStore `json:"pickupStore"`
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
	WarehouseID string `json:"warehouseId"`
	StorageTime int    `json:"storageTime"`
}

// --- delivery-intervals (courier): {"data":[ ... ]} ---
type rawCourier struct {
	Data []rawCourierEntry `json:"data"`
}
type rawCourierEntry struct {
	Inventory     rawInventory `json:"inventory"`
	LogisticGroup string       `json:"logisticGroupId"`
	Intervals     rawIntervals `json:"intervals"`
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
	ID           string      `json:"id"`
	Date         string      `json:"date"`
	From         string      `json:"from"`
	To           string      `json:"to"`
	DeliveryCost json.Number `json:"deliveryCost"`
	CarrierID    string      `json:"carrierId"`
	TariffID     string      `json:"tariffId"`
}

// --- pickup-points (PVZ): bare array ---
type rawPVZ struct {
	ID                  string         `json:"id"` // hashed (drifts)
	OriginalID          string         `json:"originalId"`
	CarrierID           string         `json:"carrierId"`
	Coordinates         rawCoords      `json:"coordinates"`
	Instock             int            `json:"instock"`
	ProductAvailability []rawProdAvail `json:"productAvailability"`
	DeliveryCost        json.Number    `json:"deliveryCost"`
	DispatchDate        string         `json:"dispatchDate"`
	DeliveryDate        string         `json:"deliveryDate"`
	Name                string         `json:"name"`
	TariffID            string         `json:"tariffId"`
	OrderDimExceeded    bool           `json:"orderDimensionsExceeded"`
	OrderWeightExceeded bool           `json:"orderWeightExceeded"`
	OrderPkgWtExceeded  bool           `json:"orderPackageWeightExceeded"`
}
```

- [ ] **Step 6: Write the failing resolver tests** — `internal/adapters/delivery/resolver_test.go`

```go
package delivery

import (
	"encoding/json"
	"os"
	"testing"

	domain "gj-checkout/internal/domains/delivery"
)

func loadFixture(t *testing.T, name string) []byte {
	t.Helper()
	b, err := os.ReadFile("testdata/" + name)
	if err != nil {
		t.Fatalf("read fixture %s: %v", name, err)
	}
	return b
}

func TestNormalizePickupStores_typeCoverageNoHash(t *testing.T) {
	var raw []rawStore
	if err := json.Unmarshal(loadFixture(t, "pickup-stores.json"), &raw); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	ks := normalizePickupStores(raw)
	if len(ks) == 0 {
		t.Fatal("expected store komplektacii")
	}
	sawPickup, sawReserve := false, false
	for _, k := range ks {
		switch k.DeliveryType {
		case domain.DeliveryStorePickup:
			sawPickup = true
		case domain.DeliveryStoreReserve:
			sawReserve = true
		default:
			t.Fatalf("store fixture must map to store_pickup/store_reserve, got %s", k.DeliveryType)
		}
		if k.IntervalID != "" {
			t.Fatalf("store komplektaciya must have empty IntervalID (key=code+date), got %q", k.IntervalID)
		}
		if k.Point.StoreCode == "" {
			t.Fatal("store komplektaciya must carry StoreCode")
		}
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
	if !sawPickup || !sawReserve {
		t.Fatalf("curated fixture must contain both store_pickup and store_reserve (pickup=%v reserve=%v)", sawPickup, sawReserve)
	}
}

func TestNormalizeCourier_hashedIDTypoFieldKopecks(t *testing.T) {
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
		if k.DeliveryCostKopecks <= 0 {
			t.Fatalf("courier deliveryCost must convert to positive kopecks, got %d", k.DeliveryCostKopecks)
		}
	}
	// the known fixture interval id + cost (rubles 299 → 29900 kopecks)
	if ks[0].IntervalID != "QOOcGGOK" || ks[0].DeliveryCostKopecks != 29900 {
		t.Fatalf("expected QOOcGGOK/29900, got %s/%d", ks[0].IntervalID, ks[0].DeliveryCostKopecks)
	}
}

func TestNormalizePVZ_hashedIDAndCoords(t *testing.T) {
	var raw []rawPVZ
	if err := json.Unmarshal(loadFixture(t, "pickup-points.json"), &raw); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	ks := normalizePickupPoints(raw)
	if len(ks) == 0 {
		t.Fatal("expected PVZ komplektacii")
	}
	for _, k := range ks {
		if k.DeliveryType != domain.DeliveryPVZ {
			t.Fatalf("want pvz, got %s", k.DeliveryType)
		}
		if k.IntervalID == "" || k.Point.PickupPointID == "" {
			t.Fatal("PVZ komplektaciya must carry hashed id (IntervalID + PickupPointID)")
		}
		if k.Point.Lat == 0 && k.Point.Lng == 0 {
			t.Fatal("PVZ komplektaciya must carry coordinates for clustering")
		}
	}
}

func TestNormalizePreliminary_digestFourMethodsKopecks(t *testing.T) {
	var raw rawPreliminary
	if err := json.Unmarshal(loadFixture(t, "delivery-preliminary.json"), &raw); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	d := normalizePreliminaryDigest(raw)
	if len(d.Methods) == 0 {
		t.Fatal("digest must have methods")
	}
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
	// courier method: minCost rubles 299 → 29900 kopecks; free threshold 1500 → 150000
	for _, m := range d.Methods {
		if m.DeliveryType == domain.DeliveryCourier {
			if m.MinCostKopecks != 29900 || m.FreeThresholdKopecks != 150000 {
				t.Fatalf("courier digest kopecks wrong: min=%d free=%d", m.MinCostKopecks, m.FreeThresholdKopecks)
			}
		}
	}
}
```

- [ ] **Step 7: Run → FAIL**

Run: `go test ./internal/adapters/delivery/ -run TestNormalize -v`
Expected: FAIL — `normalize*` undefined.

- [ ] **Step 8: `internal/adapters/delivery/resolver.go`** (the §2c core)

```go
package delivery

import domain "gj-checkout/internal/domains/delivery"

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

// toItems maps raw per-line availability → domain items, returning coverage = count(available).
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

// normalizePickupStores maps the bare store array → store komplektacii
// (store_pickup / store_reserve). Selection key = code + dispatchDate (no hashed id).
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
			IntervalID:          "", // stores: key = code + dispatchDate
			DispatchDate:        s.DispatchDate,
			PromisedDate:        s.ReadyForPickup,
			TariffID:            s.TariffID,
			LogisticGroup:       s.LogisticGroupID,
			DeliveryCostKopecks: rublesToKopecks(s.DeliveryCost),
			Features:            domain.Features{StorageDays: s.PickupStore.StorageTime},
		})
	}
	return out
}

// normalizeCourier maps {data:[{inventory,intervals.list}]} → one komplektaciya per
// interval (hashed IntervalID). Reads the typo field cartAvailabillity.
func normalizeCourier(raw rawCourier) []domain.Komplektaciya {
	var out []domain.Komplektaciya
	for _, e := range raw.Data {
		items, cov := toItems(e.Inventory.CartAvailability)
		for _, iv := range e.Intervals.List {
			out = append(out, domain.Komplektaciya{
				DeliveryType:        domain.DeliveryCourier,
				Items:               items,
				Coverage:            cov,
				Point:               domain.Point{WarehouseID: e.Inventory.DispatchWarehouse, CarrierID: iv.CarrierID},
				IntervalID:          iv.ID,
				DispatchDate:        e.Inventory.DispatchDate,
				PromisedDate:        iv.Date,
				TimeFrom:            iv.From,
				TimeTo:              iv.To,
				CarrierID:           iv.CarrierID,
				TariffID:            iv.TariffID,
				LogisticGroup:       e.LogisticGroup,
				DeliveryCostKopecks: rublesToKopecks(iv.DeliveryCost),
			})
		}
	}
	return out
}

// normalizePickupPoints maps the bare PVZ array → PVZ komplektacii (hashed id +
// coordinates). These feed both the drill-in list and the clustering read-function.
func normalizePickupPoints(raw []rawPVZ) []domain.Komplektaciya {
	out := make([]domain.Komplektaciya, 0, len(raw))
	for _, p := range raw {
		items, cov := toItems(p.ProductAvailability)
		out = append(out, domain.Komplektaciya{
			DeliveryType: domain.DeliveryPVZ,
			Items:        items,
			Coverage:     cov,
			Point: domain.Point{
				PickupPointID: p.ID, CarrierID: p.CarrierID, Name: p.Name,
				Lat: p.Coordinates.Latitude, Lng: p.Coordinates.Longitude,
			},
			IntervalID:          p.ID, // PVZ hashed id (drifts) — pin date anti-drift (§6)
			DispatchDate:        p.DispatchDate,
			PromisedDate:        p.DeliveryDate,
			CarrierID:           p.CarrierID,
			TariffID:            p.TariffID,
			DeliveryCostKopecks: rublesToKopecks(p.DeliveryCost),
			Features: domain.Features{
				PassportReq: true, // PVZ requires passport-name recipient (§UI)
				Oversize:    p.OrderDimExceeded || p.OrderWeightExceeded || p.OrderPkgWtExceeded,
			},
		})
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
			DeliveryType:         omsTypeToDomain(t.DeliveryTypeID),
			Available:            t.Available,
			Coverage:             cov,
			CartSize:             cartSize,
			MinCostKopecks:       rublesToKopecks(t.Delivery.MinCost),
			MinDays:              t.Delivery.MinDays,
			FreeThresholdKopecks: rublesToKopecks(t.Delivery.FreeCostCartThreshold),
			PaymentTypes:         t.AvailablePayment,
		})
	}
	return d
}
```

- [ ] **Step 9: Run → PASS**

Run: `go test ./internal/adapters/delivery/ -run TestNormalize -v`
Expected: PASS (all four).

- [ ] **Step 10: Commit**

```bash
git add internal/adapters/delivery/{doc.go,kopecks.go,kopecks_test.go,raw.go,resolver.go,resolver_test.go,testdata}
git commit -m "feat(resolver): §2c normalize 4 OMS shapes → Komplektaciya/Digest, rubles→kopecks (TDD on fixtures)"
```

---

## Task 4: Stub `DeliverySource` over fixtures

**Files:** Create `internal/adapters/delivery/stub.go`

- [ ] **Step 1: Write `stub.go`** (embeds curated fixtures, runs them through the real resolver)

```go
package delivery

import (
	"context"
	_ "embed"
	"encoding/json"

	domain "gj-checkout/internal/domains/delivery"
)

//go:embed testdata/delivery-preliminary.json
var fxPreliminary []byte

//go:embed testdata/pickup-stores.json
var fxStores []byte

//go:embed testdata/delivery-intervals.json
var fxCourier []byte

//go:embed testdata/pickup-points.json
var fxPVZ []byte

// StubDeliverySource implements domain.DeliverySource from baked fixtures, via the
// real resolver. Phase-2 RealDeliverySource calls starfish-oms then the SAME
// normalize* funcs. Cart is ignored in v1 (fixtures are fixed); phase-2 passes it
// to OMS. Compile-time assertion below guards the port contract.
type StubDeliverySource struct{}

var _ domain.DeliverySource = StubDeliverySource{}

func NewStubDeliverySource() StubDeliverySource { return StubDeliverySource{} }

func (StubDeliverySource) Digest(_ context.Context, _ []domain.CartLine) (domain.DeliveryDigest, error) {
	var raw rawPreliminary
	if err := json.Unmarshal(fxPreliminary, &raw); err != nil {
		return domain.DeliveryDigest{}, err
	}
	return normalizePreliminaryDigest(raw), nil
}

func (StubDeliverySource) Options(_ context.Context, _ []domain.CartLine, t domain.DeliveryType) ([]domain.Komplektaciya, error) {
	switch t {
	case domain.DeliveryCourier:
		var raw rawCourier
		if err := json.Unmarshal(fxCourier, &raw); err != nil {
			return nil, err
		}
		return normalizeCourier(raw), nil
	case domain.DeliveryPVZ:
		var raw []rawPVZ
		if err := json.Unmarshal(fxPVZ, &raw); err != nil {
			return nil, err
		}
		return normalizePickupPoints(raw), nil
	case domain.DeliveryStorePickup, domain.DeliveryStoreReserve:
		var raw []rawStore
		if err := json.Unmarshal(fxStores, &raw); err != nil {
			return nil, err
		}
		ks := normalizePickupStores(raw)
		out := make([]domain.Komplektaciya, 0, len(ks))
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

Run: `go build ./internal/adapters/delivery/ && go vet ./internal/adapters/delivery/`
Expected: builds (the `var _ domain.DeliverySource = StubDeliverySource{}` assertion compiles).
```bash
git add internal/adapters/delivery/stub.go
git commit -m "feat(resolver): stub DeliverySource over fixtures (uses real resolver)"
```

---

## Task 5: `delivery` — PVZ clustering read-function (pure, TDD)

**Files:** Create `internal/domains/delivery/cluster.go`, `internal/domains/delivery/cluster_test.go`

Per `domain-map.md`: clustering is a **read-function inside `delivery`**, in-memory (no PostGIS). It operates on the normalized PVZ komplektacii. Low zoom → grid-aggregated clusters (`{lat,lng,count}`, no coverage); high zoom → individual points (with coverage).

- [ ] **Step 1: Write the failing test** — `internal/domains/delivery/cluster_test.go`

```go
package delivery

import "testing"

func pvz(lat, lng float64) Komplektaciya {
	return Komplektaciya{DeliveryType: DeliveryPVZ, Coverage: 1, Point: Point{Lat: lat, Lng: lng, PickupPointID: "x"}}
}

func TestClusterPickupPoints_bboxFilter(t *testing.T) {
	pts := []Komplektaciya{pvz(55.75, 37.61), pvz(10.0, 10.0)} // second is far outside
	box := BBox{MinLat: 55.0, MinLng: 37.0, MaxLat: 56.0, MaxLng: 38.0}
	res := ClusterPickupPoints(pts, box, 16) // high zoom → points
	if len(res.Points) != 1 || len(res.Clusters) != 0 {
		t.Fatalf("bbox must drop the far point; got points=%d clusters=%d", len(res.Points), len(res.Clusters))
	}
}

func TestClusterPickupPoints_lowZoomAggregates(t *testing.T) {
	// three near + one apart, low zoom → fewer clusters than points, counts sum to 4
	pts := []Komplektaciya{pvz(55.750, 37.610), pvz(55.751, 37.611), pvz(55.752, 37.612), pvz(55.900, 37.900)}
	box := BBox{MinLat: 55.0, MinLng: 37.0, MaxLat: 56.0, MaxLng: 38.0}
	res := ClusterPickupPoints(pts, box, 8) // low zoom → clusters
	if len(res.Clusters) == 0 || len(res.Clusters) >= len(pts) {
		t.Fatalf("low zoom must aggregate: clusters=%d points-in=%d", len(res.Clusters), len(pts))
	}
	total := 0
	for _, c := range res.Clusters {
		total += c.Count
	}
	if total != 4 {
		t.Fatalf("cluster counts must sum to input size, got %d", total)
	}
	if len(res.Points) != 0 {
		t.Fatal("low zoom returns clusters, not points")
	}
}

func TestClusterPickupPoints_highZoomReturnsPoints(t *testing.T) {
	pts := []Komplektaciya{pvz(55.750, 37.610), pvz(55.751, 37.611)}
	box := BBox{MinLat: 55.0, MinLng: 37.0, MaxLat: 56.0, MaxLng: 38.0}
	res := ClusterPickupPoints(pts, box, 16)
	if len(res.Points) != 2 || len(res.Clusters) != 0 {
		t.Fatalf("high zoom returns individual points; got points=%d clusters=%d", len(res.Points), len(res.Clusters))
	}
}
```

- [ ] **Step 2: Run → FAIL**

Run: `go test ./internal/domains/delivery/ -run TestClusterPickupPoints -v`
Expected: FAIL — `ClusterPickupPoints` undefined.

- [ ] **Step 3: Implement `internal/domains/delivery/cluster.go`**

```go
package delivery

import "math"

// pointZoomThreshold is the zoom level at/above which we return individual PVZ
// points (with coverage) instead of aggregated clusters. Below it, the map is
// zoomed out and we send grid clusters {lat,lng,count} — this is the server-side
// fix for the AS-IS 3.5 MB areaViewPort dump.
const pointZoomThreshold = 13

// gridCellsForZoom returns the number of grid cells per axis for a zoom level.
// Lower zoom (city) → coarser grid (fewer, bigger cells → fewer clusters);
// higher zoom → finer grid.
func gridCellsForZoom(zoom int) int {
	switch {
	case zoom <= 4:
		return 2
	case zoom <= 8:
		return 8
	default:
		return 32
	}
}

// inBBox reports whether a point lies within the box (inclusive).
func inBBox(lat, lng float64, b BBox) bool {
	return lat >= b.MinLat && lat <= b.MaxLat && lng >= b.MinLng && lng <= b.MaxLng
}

// ClusterPickupPoints filters PVZ komplektacii to the bbox, then either returns
// them as individual points (high zoom) or grid-aggregates them into clusters
// (low zoom). Pure, in-memory — no PostGIS. Clusters carry only a count + centroid;
// per-point coverage is intentionally omitted at low zoom (§3 "разделяем гео и coverage").
func ClusterPickupPoints(pts []Komplektaciya, box BBox, zoom int) ClusterResult {
	inBox := make([]Komplektaciya, 0, len(pts))
	for _, p := range pts {
		if inBBox(p.Point.Lat, p.Point.Lng, box) {
			inBox = append(inBox, p)
		}
	}
	if zoom >= pointZoomThreshold {
		return ClusterResult{Points: inBox}
	}

	cells := float64(gridCellsForZoom(zoom))
	latSpan := box.MaxLat - box.MinLat
	lngSpan := box.MaxLng - box.MinLng
	if latSpan <= 0 {
		latSpan = 1
	}
	if lngSpan <= 0 {
		lngSpan = 1
	}
	type acc struct {
		sumLat, sumLng float64
		count          int
	}
	grid := map[[2]int]*acc{}
	for _, p := range inBox {
		ci := int(math.Floor((p.Point.Lat - box.MinLat) / latSpan * cells))
		cj := int(math.Floor((p.Point.Lng - box.MinLng) / lngSpan * cells))
		key := [2]int{ci, cj}
		a := grid[key]
		if a == nil {
			a = &acc{}
			grid[key] = a
		}
		a.sumLat += p.Point.Lat
		a.sumLng += p.Point.Lng
		a.count++
	}
	clusters := make([]Cluster, 0, len(grid))
	for _, a := range grid {
		clusters = append(clusters, Cluster{
			Lat:   a.sumLat / float64(a.count),
			Lng:   a.sumLng / float64(a.count),
			Count: a.count,
		})
	}
	return ClusterResult{Clusters: clusters}
}
```

- [ ] **Step 4: Run → PASS**

Run: `go test ./internal/domains/delivery/ -run TestClusterPickupPoints -v`
Expected: PASS (all three).

- [ ] **Step 5: Commit**

```bash
git add internal/domains/delivery/{cluster.go,cluster_test.go}
git commit -m "feat(delivery): in-memory PVZ clustering read-function (grid by zoom, no PostGIS)"
```

---

## Task 6: `delivery` service — digest / list / clusters / set-method (pin date) (TDD)

**Files:** Create `internal/domains/delivery/service.go`, `internal/domains/delivery/service_test.go`

- [ ] **Step 1: Write the failing test** — `internal/domains/delivery/service_test.go`

```go
package delivery

import (
	"context"
	"testing"
)

// fakeSource is a deterministic DeliverySource for service tests.
type fakeSource struct{}

func (fakeSource) Digest(context.Context, []CartLine) (DeliveryDigest, error) {
	return DeliveryDigest{Methods: []MethodSummary{{DeliveryType: DeliveryCourier, Available: true, Coverage: 2, CartSize: 4}}}, nil
}
func (fakeSource) Options(_ context.Context, _ []CartLine, t DeliveryType) ([]Komplektaciya, error) {
	switch t {
	case DeliveryCourier:
		return []Komplektaciya{
			{DeliveryType: t, Coverage: 1, DispatchDate: "2026-06-02", IntervalID: "late", DeliveryCostKopecks: 0},
			{DeliveryType: t, Coverage: 2, DispatchDate: "2026-05-31", IntervalID: "QOOcGGOK", DeliveryCostKopecks: 29900},
		}, nil
	case DeliveryPVZ:
		return []Komplektaciya{
			{DeliveryType: t, Coverage: 1, IntervalID: "dpd-1", Point: Point{Lat: 55.75, Lng: 37.61, PickupPointID: "dpd-1"}},
		}, nil
	default:
		return nil, nil
	}
}

// fakeGateway records the applied selection and serves a fixed CheckoutRef.
type fakeGateway struct {
	applied *DeliverySelection
	missing bool
}

func (g *fakeGateway) Lookup(_ context.Context, id string) (CheckoutRef, error) {
	if g.missing {
		return CheckoutRef{}, ErrNotFound
	}
	return CheckoutRef{CheckoutID: id, Cart: []CartLine{{ProductID: "a", Quantity: 1}}}, nil
}
func (g *fakeGateway) ApplyDeliverySelection(_ context.Context, id string, sel DeliverySelection) (AppliedSelection, error) {
	if g.missing {
		return AppliedSelection{}, ErrNotFound
	}
	g.applied = &sel
	return AppliedSelection{CheckoutID: id, Status: "selecting", Selection: sel}, nil
}

func TestSetDeliveryMethod_picksBestPinsDateAppliesViaGateway(t *testing.T) {
	gw := &fakeGateway{}
	svc := NewService(fakeSource{}, gw)

	out, err := svc.SetDeliveryMethod(context.Background(), "co1", DeliveryCourier)
	if err != nil {
		t.Fatalf("SetDeliveryMethod: %v", err)
	}
	// pickBest = max coverage, then earliest date, then cheapest → QOOcGGOK (cov 2)
	if out.Selection.IntervalID != "QOOcGGOK" {
		t.Fatalf("pickBest must choose max-coverage komplektaciya, got %q", out.Selection.IntervalID)
	}
	if out.Selection.PinnedDate != "2026-05-31" {
		t.Fatalf("dispatch_date must be pinned, got %q", out.Selection.PinnedDate)
	}
	if out.Status != "selecting" {
		t.Fatalf("status must be selecting, got %q", out.Status)
	}
	if gw.applied == nil || gw.applied.IntervalID != "QOOcGGOK" {
		t.Fatal("selection not applied through the session gateway")
	}
	if gw.applied.DeliveryCostKopecks != 29900 {
		t.Fatalf("cost must carry kopecks, got %d", gw.applied.DeliveryCostKopecks)
	}
}

func TestSetDeliveryMethod_notFound(t *testing.T) {
	svc := NewService(fakeSource{}, &fakeGateway{missing: true})
	_, err := svc.SetDeliveryMethod(context.Background(), "missing", DeliveryCourier)
	if err == nil {
		t.Fatal("expected error for missing session")
	}
}

func TestPickupClusters_lowZoomClusters(t *testing.T) {
	svc := NewService(fakeSource{}, &fakeGateway{})
	res, err := svc.PickupClusters(context.Background(), "co1", BBox{MinLat: 55, MinLng: 37, MaxLat: 56, MaxLng: 38}, 8)
	if err != nil {
		t.Fatalf("PickupClusters: %v", err)
	}
	if len(res.Clusters) == 0 {
		t.Fatal("expected clusters at low zoom")
	}
}

func TestGetDeliveryDigest_passthrough(t *testing.T) {
	svc := NewService(fakeSource{}, &fakeGateway{})
	d, err := svc.GetDeliveryDigest(context.Background(), "co1")
	if err != nil {
		t.Fatalf("GetDeliveryDigest: %v", err)
	}
	if len(d.Methods) != 1 || d.Methods[0].DeliveryType != DeliveryCourier {
		t.Fatalf("digest passthrough wrong: %+v", d.Methods)
	}
}
```

- [ ] **Step 2: Run → FAIL**

Run: `go test ./internal/domains/delivery/ -run 'TestSetDeliveryMethod|TestPickupClusters|TestGetDeliveryDigest' -v`
Expected: FAIL — `NewService`, `Service`, methods undefined.

- [ ] **Step 3: Implement `internal/domains/delivery/service.go`**

```go
package delivery

import (
	"context"
	"encoding/json"
	"fmt"
)

// Service orchestrates delivery resolution. It is stateless: it reads the session
// via the SessionGateway port, resolves options via the DeliverySource port, and
// applies the chosen selection back through the gateway (session is the consistency
// root). Both ports are required.
type Service struct {
	src DeliverySource
	gw  SessionGateway
}

// NewService builds a Service; both ports are required.
func NewService(src DeliverySource, gw SessionGateway) *Service {
	if src == nil || gw == nil {
		panic("delivery: NewService requires non-nil DeliverySource and SessionGateway")
	}
	return &Service{src: src, gw: gw}
}

// GetDeliveryDigest returns the per-method entry digest for the session's cart.
func (s *Service) GetDeliveryDigest(ctx context.Context, checkoutID string) (DeliveryDigest, error) {
	ref, err := s.gw.Lookup(ctx, checkoutID)
	if err != nil {
		return DeliveryDigest{}, err // ErrNotFound passes through
	}
	return s.src.Digest(ctx, ref.Cart)
}

// ListKomplektacii returns the drill-in list of komplektacii for a method.
func (s *Service) ListKomplektacii(ctx context.Context, checkoutID string, t DeliveryType) ([]Komplektaciya, error) {
	ref, err := s.gw.Lookup(ctx, checkoutID)
	if err != nil {
		return nil, err
	}
	return s.src.Options(ctx, ref.Cart, t)
}

// PickupClusters returns the PVZ map payload (clusters at low zoom, points at high
// zoom), bbox-bound and server-clustered (§3 viewport/clustering).
func (s *Service) PickupClusters(ctx context.Context, checkoutID string, box BBox, zoom int) (ClusterResult, error) {
	ref, err := s.gw.Lookup(ctx, checkoutID)
	if err != nil {
		return ClusterResult{}, err
	}
	pts, err := s.src.Options(ctx, ref.Cart, DeliveryPVZ)
	if err != nil {
		return ClusterResult{}, fmt.Errorf("resolve pvz points: %w", err)
	}
	return ClusterPickupPoints(pts, box, zoom), nil
}

// SetDeliveryMethod auto-resolves the best komplektaciya for the method, PINS its
// dispatch_date (§6 anti-drift), and applies the selection to the session aggregate
// through the gateway. Returns the applied selection (delivery-owned, not the full
// session). ErrInvalidArgument when no fulfillment option exists for the method.
func (s *Service) SetDeliveryMethod(ctx context.Context, checkoutID string, t DeliveryType) (AppliedSelection, error) {
	ref, err := s.gw.Lookup(ctx, checkoutID)
	if err != nil {
		return AppliedSelection{}, err
	}
	opts, err := s.src.Options(ctx, ref.Cart, t)
	if err != nil {
		return AppliedSelection{}, fmt.Errorf("resolve delivery options: %w", err)
	}
	best := pickBest(opts)
	if best == nil {
		return AppliedSelection{}, fmt.Errorf("%w: no fulfillment option for %s", ErrInvalidArgument, t)
	}
	snap, _ := json.Marshal(best) // advisory; ignore marshal error (best is a plain struct)
	pointKey := best.Point.StoreCode
	if pointKey == "" {
		pointKey = best.Point.PickupPointID
	}
	sel := DeliverySelection{
		DeliveryType:        t,
		PinnedDate:          best.DispatchDate, // the PIN
		IntervalID:          best.IntervalID,
		PointKey:            pointKey,
		Coverage:            best.Coverage,
		CartSize:            len(best.Items),
		DeliveryCostKopecks: best.DeliveryCostKopecks,
		Snapshot:            snap,
	}
	return s.gw.ApplyDeliverySelection(ctx, checkoutID, sel)
}

// pickBest is the replaceable "best interval" policy: max coverage, then earliest
// dispatch date, then cheapest. (Mirrors the IS "best interval" today.)
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
		case k.DeliveryCostKopecks < best.DeliveryCostKopecks:
			best = k
		}
	}
	return &best
}
```

- [ ] **Step 4: Run → PASS**

Run: `go test ./internal/domains/delivery/ -count=1 -v`
Expected: PASS (boundary + cluster + service tests).

- [ ] **Step 5: Commit**

```bash
git add internal/domains/delivery/{service.go,service_test.go}
git commit -m "feat(delivery): service digest/list/clusters/set-method (pickBest + pin date, apply via gateway) (TDD)"
```

---

## Task 7: OpenAPI — delivery tag, schemas, paths, per-domain codegen

**Files:**
- Modify: `api/v1/openapi.yaml`
- Create: `api/v1/paths/delivery.yaml`, `api/v1/components/schemas/delivery.yaml`, `api/v1/oapi-codegen-delivery.yaml`

- [ ] **Step 1: Add the `delivery` tag + 4 paths to `api/v1/openapi.yaml`**

Under `tags:` add:
```yaml
  - name: delivery
    description: Delivery resolution — per-method digest, drill-in komplektacii, PVZ map, set method.
```
Under `paths:` add:
```yaml
  /checkout/{checkout_id}/delivery-options:
    $ref: "./paths/delivery.yaml#/DeliveryOptions"
  /checkout/{checkout_id}/komplektacii:
    $ref: "./paths/delivery.yaml#/Komplektacii"
  /checkout/{checkout_id}/pickup-points:
    $ref: "./paths/delivery.yaml#/PickupPoints"
  /checkout/{checkout_id}/delivery-method:
    $ref: "./paths/delivery.yaml#/DeliveryMethod"
```

- [ ] **Step 2: `api/v1/components/schemas/delivery.yaml`** (snake_case; money = integer int64 kopecks)

```yaml
ItemAvail:
  type: object
  required: [product_id, available_quantity, available]
  properties:
    product_id:         { type: string }
    available_quantity: { type: integer }
    available:          { type: boolean }
Point:
  type: object
  properties:
    warehouse_id:    { type: string }
    store_code:      { type: string }
    pickup_point_id: { type: string }
    carrier_id:      { type: string }
    name:            { type: string }
    address:         { type: string }
    lat:             { type: number, format: double }
    lng:             { type: number, format: double }
Features:
  type: object
  properties:
    try_on:       { type: boolean }
    passport_req: { type: boolean }
    storage_days: { type: integer }
    oversize:     { type: boolean }
Komplektaciya:
  type: object
  required: [delivery_type, coverage, dispatch_date, delivery_cost_kopecks]
  properties:
    delivery_type: { type: string, enum: [courier, pvz, store_pickup, store_reserve] }
    items:         { type: array, items: { $ref: "#/ItemAvail" } }
    coverage:      { type: integer, description: "X из N — кол-во доступных строк" }
    point:         { $ref: "#/Point" }
    interval_id:   { type: string, description: "hashed (courier/pvz); пусто для магазина" }
    dispatch_date: { type: string }
    promised_date: { type: string }
    time_from:     { type: string }
    time_to:       { type: string }
    carrier_id:    { type: string }
    tariff_id:     { type: string }
    logistic_group: { type: string }
    delivery_cost_kopecks: { type: integer, format: int64, description: "копейки (int64)" }
    features:      { $ref: "#/Features" }
MethodSummary:
  type: object
  required: [delivery_type, available, coverage, cart_size]
  properties:
    delivery_type:          { type: string, enum: [courier, pvz, store_pickup, store_reserve] }
    available:              { type: boolean }
    coverage:               { type: integer }
    cart_size:              { type: integer }
    min_cost_kopecks:       { type: integer, format: int64 }
    min_days:               { type: integer }
    free_threshold_kopecks: { type: integer, format: int64 }
    payment_types:          { type: array, items: { type: string } }
DeliveryDigest:
  type: object
  required: [methods]
  properties:
    methods: { type: array, items: { $ref: "#/MethodSummary" } }
KomplektaciyaList:
  type: object
  required: [komplektacii]
  properties:
    komplektacii: { type: array, items: { $ref: "#/Komplektaciya" } }
Cluster:
  type: object
  required: [lat, lng, count]
  properties:
    lat:   { type: number, format: double }
    lng:   { type: number, format: double }
    count: { type: integer }
ClusterResult:
  type: object
  properties:
    clusters: { type: array, items: { $ref: "#/Cluster" } }
    points:   { type: array, items: { $ref: "#/Komplektaciya" } }
DeliverySelection:
  type: object
  required: [delivery_type, pinned_dispatch_date, coverage, cart_size, delivery_cost_kopecks]
  properties:
    delivery_type:         { type: string, enum: [courier, pvz, store_pickup, store_reserve] }
    pinned_dispatch_date:  { type: string }
    interval_id:           { type: string }
    point_key:             { type: string }
    coverage:              { type: integer }
    cart_size:             { type: integer }
    delivery_cost_kopecks: { type: integer, format: int64 }
AppliedSelection:
  type: object
  required: [checkout_id, status, selection]
  properties:
    checkout_id: { type: string, format: uuid }
    status:      { type: string }
    selection:   { $ref: "#/DeliverySelection" }
SetDeliveryMethodRequest:
  type: object
  required: [type]
  properties:
    type: { type: string, enum: [courier, pvz, store_pickup, store_reserve] }
```

- [ ] **Step 3: `api/v1/paths/delivery.yaml`**

```yaml
DeliveryOptions:
  get:
    tags: [delivery]
    operationId: getDeliveryOptions
    summary: Per-method delivery digest for the session
    security: []
    parameters:
      - { name: checkout_id, in: path, required: true, schema: { type: string, format: uuid } }
    responses:
      "200":
        description: Per-method digest
        content: { application/json: { schema: { $ref: "../components/schemas/delivery.yaml#/DeliveryDigest" } } }
      "404":
        description: Not found
        content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } }
Komplektacii:
  get:
    tags: [delivery]
    operationId: getKomplektacii
    summary: Drill-in list of komplektacii for a method
    security: []
    parameters:
      - { name: checkout_id, in: path, required: true, schema: { type: string, format: uuid } }
      - { name: type, in: query, required: true, schema: { type: string, enum: [courier, pvz, store_pickup, store_reserve] } }
    responses:
      "200":
        description: Komplektaciya list
        content: { application/json: { schema: { $ref: "../components/schemas/delivery.yaml#/KomplektaciyaList" } } }
      "400":
        description: Invalid argument
        content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } }
      "404":
        description: Not found
        content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } }
PickupPoints:
  get:
    tags: [delivery]
    operationId: getPickupPoints
    summary: PVZ map — clusters at low zoom, points at high zoom (bbox-bound)
    security: []
    parameters:
      - { name: checkout_id, in: path, required: true, schema: { type: string, format: uuid } }
      - { name: bbox, in: query, required: true, schema: { type: string }, description: "min_lat,min_lng,max_lat,max_lng" }
      - { name: zoom, in: query, required: true, schema: { type: integer } }
    responses:
      "200":
        description: Cluster result
        content: { application/json: { schema: { $ref: "../components/schemas/delivery.yaml#/ClusterResult" } } }
      "400":
        description: Invalid argument
        content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } }
      "404":
        description: Not found
        content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } }
DeliveryMethod:
  patch:
    tags: [delivery]
    operationId: setDeliveryMethod
    summary: Choose a delivery method → auto-resolve best komplektaciya, pin dispatch_date
    security: []
    parameters:
      - { name: checkout_id, in: path, required: true, schema: { type: string, format: uuid } }
    requestBody:
      required: true
      content: { application/json: { schema: { $ref: "../components/schemas/delivery.yaml#/SetDeliveryMethodRequest" } } }
    responses:
      "200":
        description: Applied selection
        content: { application/json: { schema: { $ref: "../components/schemas/delivery.yaml#/AppliedSelection" } } }
      "400":
        description: Invalid argument
        content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } }
      "404":
        description: Not found
        content: { application/json: { schema: { $ref: "../components/schemas/common.yaml#/ErrorResponse" } } }
```

- [ ] **Step 4: `api/v1/oapi-codegen-delivery.yaml`** (mirror the session config)

```yaml
# Codegen config for the `delivery` domain. Types-only + per-domain include-tags.
package: apiv1
generate:
  models: true
output: apiv1/openapi.gen.go
output-options:
  skip-prune: false
  include-tags:
    - delivery
```

- [ ] **Step 5: Generate + lint**

Run: `make generate && make lint`
Expected: `redocly lint` clean; `internal/domains/delivery/apiv1/openapi.gen.go` created with `Komplektaciya`, `DeliveryDigest`, `MethodSummary`, `ClusterResult`, `AppliedSelection`, `SetDeliveryMethodRequest`, etc. (`go generate ./internal/domains/...` picks up the new `delivery` package's directive.)
> If `go generate` errors that the `apiv1` dir is missing, `mkdir -p internal/domains/delivery/apiv1` first (oapi-codegen writes the file but may not create the dir).

- [ ] **Step 6: Build + commit**

Run: `go build ./...`
Expected: builds (generated DTOs compile).
```bash
git add api internal/domains/delivery/apiv1
git commit -m "feat(api): delivery tag + schemas + paths (digest/komplektacii/pickup-points/delivery-method) + codegen"
```

---

## Task 8: `delivery` handler + routes + DTO mapping

**Files:** Create `internal/domains/delivery/handler.go`, `internal/domains/delivery/routes.go`

- [ ] **Step 1: `internal/domains/delivery/handler.go`**

```go
package delivery

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"

	"github.com/go-chi/chi/v5"

	"gj-checkout/internal/domains/delivery/apiv1"
	"gj-checkout/internal/platform/httpx"
)

// Handler is the HTTP edge for the delivery domain.
type Handler struct {
	service *Service
	errs    *httpx.Helper
}

// NewHandler constructs a Handler.
func NewHandler(service *Service, errs *httpx.Helper) *Handler {
	return &Handler{service: service, errs: errs}
}

// DeliveryOptions handles GET /api/v1/checkout/{checkout_id}/delivery-options.
func (h *Handler) DeliveryOptions(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "checkout_id")
	d, err := h.service.GetDeliveryDigest(r.Context(), id)
	if err != nil {
		h.writeErr(w, err)
		return
	}
	writeJSON(w, http.StatusOK, toDigestDTO(d))
}

// Komplektacii handles GET /api/v1/checkout/{checkout_id}/komplektacii?type=.
func (h *Handler) Komplektacii(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "checkout_id")
	t := DeliveryType(r.URL.Query().Get("type"))
	if !validType(t) {
		h.errs.BadRequest(w, "invalid_argument", "unknown delivery type")
		return
	}
	ks, err := h.service.ListKomplektacii(r.Context(), id, t)
	if err != nil {
		h.writeErr(w, err)
		return
	}
	dtos := make([]apiv1.Komplektaciya, 0, len(ks))
	for _, k := range ks {
		dtos = append(dtos, toKomplektaciyaDTO(k))
	}
	writeJSON(w, http.StatusOK, apiv1.KomplektaciyaList{Komplektacii: dtos})
}

// PickupPoints handles GET /api/v1/checkout/{checkout_id}/pickup-points?bbox=&zoom=.
func (h *Handler) PickupPoints(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "checkout_id")
	box, err := parseBBox(r.URL.Query().Get("bbox"))
	if err != nil {
		h.errs.BadRequest(w, "invalid_argument", "bbox must be min_lat,min_lng,max_lat,max_lng")
		return
	}
	zoom, err := strconv.Atoi(r.URL.Query().Get("zoom"))
	if err != nil {
		h.errs.BadRequest(w, "invalid_argument", "zoom must be an integer")
		return
	}
	res, err := h.service.PickupClusters(r.Context(), id, box, zoom)
	if err != nil {
		h.writeErr(w, err)
		return
	}
	writeJSON(w, http.StatusOK, toClusterResultDTO(res))
}

// SetDeliveryMethod handles PATCH /api/v1/checkout/{checkout_id}/delivery-method.
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
	applied, err := h.service.SetDeliveryMethod(r.Context(), id, t)
	if err != nil {
		h.writeErr(w, err)
		return
	}
	writeJSON(w, http.StatusOK, toAppliedDTO(applied))
}

// writeErr maps domain markers → HTTP envelopes.
func (h *Handler) writeErr(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, ErrNotFound):
		h.errs.JSON(w, http.StatusNotFound, "not_found", "checkout session not found")
	case errors.Is(err, ErrInvalidArgument):
		h.errs.BadRequest(w, "invalid_argument", err.Error())
	default:
		h.errs.Internal(w, "internal", "internal error")
	}
}

func validType(t DeliveryType) bool {
	switch t {
	case DeliveryCourier, DeliveryPVZ, DeliveryStorePickup, DeliveryStoreReserve:
		return true
	default:
		return false
	}
}

func parseBBox(s string) (BBox, error) {
	parts := strings.Split(s, ",")
	if len(parts) != 4 {
		return BBox{}, errors.New("bbox needs 4 comma-separated floats")
	}
	vals := make([]float64, 4)
	for i, p := range parts {
		v, err := strconv.ParseFloat(strings.TrimSpace(p), 64)
		if err != nil {
			return BBox{}, err
		}
		vals[i] = v
	}
	return BBox{MinLat: vals[0], MinLng: vals[1], MaxLat: vals[2], MaxLng: vals[3]}, nil
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

// --- domain → generated DTO mapping ---

func toDigestDTO(d DeliveryDigest) apiv1.DeliveryDigest {
	ms := make([]apiv1.MethodSummary, 0, len(d.Methods))
	for _, m := range d.Methods {
		minCost := m.MinCostKopecks
		minDays := m.MinDays
		free := m.FreeThresholdKopecks
		pt := append([]string(nil), m.PaymentTypes...)
		ms = append(ms, apiv1.MethodSummary{
			DeliveryType:         string(m.DeliveryType),
			Available:            m.Available,
			Coverage:             m.Coverage,
			CartSize:             m.CartSize,
			MinCostKopecks:       &minCost,
			MinDays:              &minDays,
			FreeThresholdKopecks: &free,
			PaymentTypes:         &pt,
		})
	}
	return apiv1.DeliveryDigest{Methods: ms}
}

func toKomplektaciyaDTO(k Komplektaciya) apiv1.Komplektaciya {
	items := make([]apiv1.ItemAvail, 0, len(k.Items))
	for _, it := range k.Items {
		items = append(items, apiv1.ItemAvail{ProductId: it.ProductID, AvailableQuantity: it.AvailableQuantity, Available: it.Available})
	}
	itemsPtr := &items
	lat, lng := k.Point.Lat, k.Point.Lng
	point := &apiv1.Point{
		WarehouseId: strPtr(k.Point.WarehouseID), StoreCode: strPtr(k.Point.StoreCode),
		PickupPointId: strPtr(k.Point.PickupPointID), CarrierId: strPtr(k.Point.CarrierID),
		Name: strPtr(k.Point.Name), Address: strPtr(k.Point.Address), Lat: &lat, Lng: &lng,
	}
	feat := &apiv1.Features{
		TryOn: boolPtr(k.Features.TryOn), PassportReq: boolPtr(k.Features.PassportReq),
		StorageDays: intPtr(k.Features.StorageDays), Oversize: boolPtr(k.Features.Oversize),
	}
	return apiv1.Komplektaciya{
		DeliveryType:        string(k.DeliveryType),
		Items:               itemsPtr,
		Coverage:            k.Coverage,
		Point:               point,
		IntervalId:          strPtr(k.IntervalID),
		DispatchDate:        k.DispatchDate,
		PromisedDate:        strPtr(k.PromisedDate),
		TimeFrom:            strPtr(k.TimeFrom),
		TimeTo:              strPtr(k.TimeTo),
		CarrierId:           strPtr(k.CarrierID),
		TariffId:            strPtr(k.TariffID),
		LogisticGroup:       strPtr(k.LogisticGroup),
		DeliveryCostKopecks: k.DeliveryCostKopecks,
		Features:            feat,
	}
}

func toClusterResultDTO(res ClusterResult) apiv1.ClusterResult {
	var out apiv1.ClusterResult
	if len(res.Clusters) > 0 {
		cs := make([]apiv1.Cluster, 0, len(res.Clusters))
		for _, c := range res.Clusters {
			cs = append(cs, apiv1.Cluster{Lat: c.Lat, Lng: c.Lng, Count: c.Count})
		}
		out.Clusters = &cs
	}
	if len(res.Points) > 0 {
		ps := make([]apiv1.Komplektaciya, 0, len(res.Points))
		for _, p := range res.Points {
			ps = append(ps, toKomplektaciyaDTO(p))
		}
		out.Points = &ps
	}
	return out
}

func toAppliedDTO(a AppliedSelection) apiv1.AppliedSelection {
	return apiv1.AppliedSelection{
		CheckoutId: a.CheckoutID,
		Status:     a.Status,
		Selection: apiv1.DeliverySelection{
			DeliveryType:        string(a.Selection.DeliveryType),
			PinnedDispatchDate:  a.Selection.PinnedDate,
			IntervalId:          strPtr(a.Selection.IntervalID),
			PointKey:            strPtr(a.Selection.PointKey),
			Coverage:            a.Selection.Coverage,
			CartSize:            a.Selection.CartSize,
			DeliveryCostKopecks: a.Selection.DeliveryCostKopecks,
		},
	}
}

func strPtr(s string) *string { return &s }
func boolPtr(b bool) *bool    { return &b }
func intPtr(i int) *int       { return &i }
```
> **NB on generated field types:** `oapi-codegen` makes non-required properties **pointers** and uses Go-cased names (`ProductId`, `CheckoutId`, `IntervalId`). After `make generate`, OPEN `internal/domains/delivery/apiv1/openapi.gen.go` and reconcile this mapping to the **actual** generated field names/types (pointer vs value, `Id` vs `ID`). The required scalars (`Coverage`, `CartSize`, `DeliveryCostKopecks`, `DispatchDate`, `DeliveryType`, `CheckoutId`, `Status`) are value types; optional ones are pointers — adjust `strPtr/boolPtr/intPtr` use to match. Also confirm `AppliedSelection.CheckoutId` is `string` (we mapped `checkout_id` as `format: uuid` → oapi-codegen may emit `string` or `uuid.UUID`; if `uuid.UUID`, parse with `uuid.MustParse` like session's `toSessionDTO`).

- [ ] **Step 2: `internal/domains/delivery/routes.go`**

```go
package delivery

import "github.com/go-chi/chi/v5"

// Deps carries dependencies required to mount delivery routes.
type Deps struct{ Handler *Handler }

// Mount registers delivery routes under the checkout resource. Caller scopes them
// under /api/v1. These are sub-resources of /checkout/{checkout_id}.
func Mount(r chi.Router, deps Deps) {
	r.Route("/checkout/{checkout_id}", func(rr chi.Router) {
		rr.Get("/delivery-options", deps.Handler.DeliveryOptions)
		rr.Get("/komplektacii", deps.Handler.Komplektacii)
		rr.Get("/pickup-points", deps.Handler.PickupPoints)
		rr.Patch("/delivery-method", deps.Handler.SetDeliveryMethod)
	})
}
```
> NB: session already mounts `GET /checkout/{checkout_id}`. chi allows multiple `Route`/handlers on overlapping path prefixes as long as the (method, full-pattern) pairs are distinct — these four are distinct sub-paths, so there is no collision with session's `GET /checkout/{checkout_id}`. If chi panics on a duplicate route at mount time, fold both domains' sub-routes under one parent in `transport/routes.go` instead (see Task 9 note).

- [ ] **Step 3: Build + commit**

Run: `go build ./... && go vet ./internal/domains/delivery/`
Expected: builds (after reconciling the DTO mapping in Step 1's NB).
```bash
git add internal/domains/delivery/{handler.go,routes.go}
git commit -m "feat(delivery): HTTP handler + routes + domain→DTO mapping"
```

---

## Task 9: Wire + mount + e2e + DoD

**Files:**
- Modify: `internal/app/wire/session.go`
- Create: `internal/app/wire/delivery.go`
- Modify: `internal/app/container.go`, `internal/platform/transport/routes.go`, `internal/app/app.go`

- [ ] **Step 1: Split the session wiring** — replace `internal/app/wire/session.go`

```go
package wire

import (
	"gj-checkout/internal/domains/session"
	"gj-checkout/internal/platform/httpx"

	"github.com/jackc/pgx/v5/pgxpool"
)

// SessionService builds the session service over a pgx-backed repository. Returned
// so both the session handler AND the delivery gateway adapter can share one service.
func SessionService(db *pgxpool.Pool) *session.Service {
	return session.NewService(session.NewRepository(db))
}

// SessionHandler builds the session HTTP handler over an already-constructed service.
func SessionHandler(svc *session.Service, errs *httpx.Helper) *session.Handler {
	return session.NewHandler(svc, errs)
}
```
> This drops the old `Session(cfg, db, errs)` builder; `config` is no longer needed here. Update the container accordingly (Step 3).

- [ ] **Step 2: Create the gateway bridge + delivery wiring** — `internal/app/wire/delivery.go`

```go
package wire

import (
	"context"
	"encoding/json"

	adapter "gj-checkout/internal/adapters/delivery"
	"gj-checkout/internal/domains/delivery"
	"gj-checkout/internal/domains/session"
	"gj-checkout/internal/platform/httpx"
)

// Delivery builds the delivery handler. It injects a stub DeliverySource (fixtures)
// and a sessionGateway adapter bridging delivery.SessionGateway → *session.Service.
// This package is the ONLY place that imports both domains — domains never import
// each other (boundary_test enforces it).
func Delivery(sessionSvc *session.Service, errs *httpx.Helper) *delivery.Handler {
	gw := &sessionGateway{svc: sessionSvc}
	src := adapter.NewStubDeliverySource()
	svc := delivery.NewService(src, gw)
	return delivery.NewHandler(svc, errs)
}

// sessionGateway implements delivery.SessionGateway over *session.Service. It maps
// types across the domain boundary and translates session.ErrNotFound →
// delivery.ErrNotFound so the delivery handler emits the right HTTP status.
type sessionGateway struct {
	svc *session.Service
}

var _ delivery.SessionGateway = (*sessionGateway)(nil)

func (g *sessionGateway) Lookup(ctx context.Context, checkoutID string) (delivery.CheckoutRef, error) {
	s, err := g.svc.GetSession(ctx, checkoutID)
	if err != nil {
		return delivery.CheckoutRef{}, mapSessionErr(err)
	}
	cart := make([]delivery.CartLine, 0, len(s.Cart))
	for _, l := range s.Cart {
		cart = append(cart, delivery.CartLine{ProductID: l.ProductID, Quantity: l.Quantity})
	}
	return delivery.CheckoutRef{CheckoutID: s.CheckoutID, Cart: cart}, nil
}

func (g *sessionGateway) ApplyDeliverySelection(ctx context.Context, checkoutID string, sel delivery.DeliverySelection) (delivery.AppliedSelection, error) {
	s, err := g.svc.ApplyDeliverySelection(ctx, checkoutID, session.Selection{
		DeliveryType:        string(sel.DeliveryType),
		PinnedDispatchDate:  sel.PinnedDate,
		IntervalID:          sel.IntervalID,
		PointKey:            sel.PointKey,
		Coverage:            sel.Coverage,
		CartSize:            sel.CartSize,
		DeliveryCostKopecks: sel.DeliveryCostKopecks,
		Snapshot:            json.RawMessage(sel.Snapshot),
	})
	if err != nil {
		return delivery.AppliedSelection{}, mapSessionErr(err)
	}
	return delivery.AppliedSelection{
		CheckoutID: s.CheckoutID,
		Status:     string(s.Status),
		Selection:  sel,
	}, nil
}

// mapSessionErr translates session markers into delivery markers (boundary
// decoupling — delivery must not import session, but wire may import both).
func mapSessionErr(err error) error {
	switch {
	case err == nil:
		return nil
	case isSessionNotFound(err):
		return delivery.ErrNotFound
	default:
		return err
	}
}
```
Add a tiny helper in the same file (kept separate so the `errors.Is` import is local):
```go
// isSessionNotFound reports whether err is session.ErrNotFound.
func isSessionNotFound(err error) bool {
	return errorsIs(err, session.ErrNotFound)
}
```
…and at the top of the file add `"errors"` to imports and define:
```go
func errorsIs(err, target error) bool { return errors.Is(err, target) }
```
> (Or simply `import "errors"` and call `errors.Is(err, session.ErrNotFound)` directly inside `mapSessionErr` — the indirection above is optional. Prefer the direct form: replace `isSessionNotFound(err)` with `errors.Is(err, session.ErrNotFound)` and drop the two helpers.)

- [ ] **Step 3: Update `internal/app/container.go`**

Add the import `"gj-checkout/internal/domains/delivery"`. Add the field and build both handlers from one service:
```go
	SessionHandler  *session.Handler
	DeliveryHandler *delivery.Handler
```
Replace the `c.SessionHandler = wire.Session(cfg, pool, c.ErrorsHelper)` line with:
```go
	sessionSvc := wire.SessionService(pool)
	c.SessionHandler = wire.SessionHandler(sessionSvc, c.ErrorsHelper)
	c.DeliveryHandler = wire.Delivery(sessionSvc, c.ErrorsHelper)
```

- [ ] **Step 4: Mount delivery routes** — `internal/platform/transport/routes.go`

Add import `"gj-checkout/internal/domains/delivery"`. Add to `Dependencies`:
```go
	Delivery delivery.Deps
```
In `registerRoutes`, inside the `/api/v1` group, after `session.Mount`:
```go
		session.Mount(rr, deps.Session)
		delivery.Mount(rr, deps.Delivery)
```
> **Route-collision note:** session mounts `POST /checkout` + `GET /checkout/{checkout_id}`; delivery mounts `GET/PATCH /checkout/{checkout_id}/<sub>`. chi keys routes by (method, full pattern) and supports the same prefix across separate `Route` calls. If `Mount`-time chi panics with a duplicate-route error, refactor so a single `rr.Route("/checkout", …)` in `transport/routes.go` hosts both domains' sub-handlers (pass both `Deps` in). Verify at boot (Step 7) — the smoke test will surface a panic immediately.

- [ ] **Step 5: Pass the delivery Deps in `internal/app/app.go`**

Add import `"gj-checkout/internal/domains/delivery"`. In the `transport.NewServer(cfg, transport.Dependencies{…})` literal add:
```go
		Delivery: delivery.Deps{Handler: container.DeliveryHandler},
```

- [ ] **Step 6: Build + full test + gates**

Run (local Postgres up; export the test DSN so session integration tests run, not skip):
```bash
export CHECKOUT_TEST_DB_DSN='postgres://checkout:checkout@127.0.0.1:5544/checkout?sslmode=disable'
go build ./... && go vet ./... && go test ./... -count=1
make generate && make lint
```
Expected: all green. `make generate` produces no diff (bundle + DTOs already committed).

- [ ] **Step 7: e2e smoke against the running service**

```bash
make migrate-up && make run &   # or run in a second terminal
sleep 2
ID=$(curl -s -X POST localhost:8080/api/v1/checkout -d '{"customer_id":"c1","basket_id":"2000019994"}' | jq -r .checkout_id)
echo "checkout_id=$ID"
curl -s localhost:8080/api/v1/checkout/$ID/delivery-options | jq '.methods[] | {type:.delivery_type, coverage, cart_size, min_cost_kopecks}'
curl -s "localhost:8080/api/v1/checkout/$ID/komplektacii?type=courier" | jq '.komplektacii[] | {interval_id, coverage, dispatch_date, delivery_cost_kopecks}'
curl -s "localhost:8080/api/v1/checkout/$ID/pickup-points?bbox=55.0,37.0,56.0,38.0&zoom=8" | jq '{clusters:(.clusters|length), points:(.points|length)}'
curl -s "localhost:8080/api/v1/checkout/$ID/pickup-points?bbox=55.0,37.0,56.0,38.0&zoom=16" | jq '{clusters:(.clusters|length), points:(.points|length)}'
curl -s -X PATCH localhost:8080/api/v1/checkout/$ID/delivery-method -d '{"type":"courier"}' | jq '{status, sel:.selection}'
curl -s localhost:8080/api/v1/checkout/$ID | jq '{status}'   # session now "selecting"
```
Expected:
- digest lists 4 methods with coverage «X из N» and kopecks (`min_cost_kopecks:29900` for courier);
- courier komplektacii include `interval_id:"QOOcGGOK"`, `delivery_cost_kopecks:29900`;
- pickup-points at `zoom=8` → `clusters>0, points=0`; at `zoom=16` → `clusters=0, points>0` (server-side clustering working);
- PATCH returns `status:"selecting"` + selection with `pinned_dispatch_date` + courier interval `QOOcGGOK`;
- GET session afterward → `status:"selecting"` (write went through the session aggregate).
Stop the service (`kill %1` or Ctrl-C).

- [ ] **Step 8: Commit + tag**

```bash
git commit -am "feat(checkout): wire delivery domain (stub source + session gateway bridge) + mount routes; e2e green" --allow-empty
git tag v0.0.3-resolver
```

---

## Definition of Done (Plan 3)

- **`delivery` is its own domain** (`internal/domains/delivery/`) owning the `DeliverySource` port, the model, the clustering read-function, and the four delivery endpoints; `boundary_test` green (no cross-domain/adapter/upward imports).
- **Resolver** (`internal/adapters/delivery/`) normalizes **all 4** OMS shapes → `Komplektaciya`/`Digest`, table-tested on **real** fixtures: coverage «X из N»; 4 shapes (preliminary digest / stores no-hash / courier hashed / PVZ hashed+coords); hashed-id presence rules; partial availability; `cartAvailabillity` typo; **rubles→int64 kopecks** (no float).
- **PVZ clustering** is an in-memory grid read-function inside `delivery` (no PostGIS): bbox-bound, low-zoom→clusters, high-zoom→points; tested.
- **`GET …/delivery-options`** → per-method digest; **`GET …/komplektacii?type=`** → drill-in list; **`GET …/pickup-points?bbox=&zoom=`** → clusters/points; **`PATCH …/delivery-method`** → resolves best komplektaciya, **pins dispatch_date**, and **persists the selection THROUGH the `session` aggregate** (session → `selecting`).
- Stub `DeliverySource` runs the **real** resolver over real (curated) fixtures.
- Selection persisted as JSONB (migration 0002); repository round-trip tested on real Postgres.
- `go build/vet ./...`, `go test ./... -count=1`, `make generate`, `make lint` green; e2e create→digest→komplektacii→pickup-points→set-method→get-session passes on stubs; `v0.0.3-resolver` tagged.

## Self-review notes (spec coverage)

- §2c invariants 1–6 → Task 3 table tests; invariant "best policy" (6 in spec) → `pickBest` (Task 6); volatility/revalidate (7) and city re-resolve (8) → **Plan 4 / phase 2** (not v1 stubs — noted, not silently dropped); two-level digest vs drill-in (9) → digest + komplektacii endpoints.
- §3 PVZ viewport/clustering → Task 5 + pickup-points endpoint.
- §5 money kopecks → `kopecks.go` + int64 everywhere; OpenAPI `format: int64`.
- §6 pin dispatch_date → `SetDeliveryMethod` pins `best.DispatchDate`; **commit-time reconciliation by `(date,warehouse,window,carrier,tariff)` (not full id hash)** is **Plan 4** (commit saga) — out of scope here, flagged.
- Out of v1 (deferred, not dropped): real OMS adapter, city/region join (`CheckoutRef.City`), cart population from baskets, drift-reconcile-on-commit, partial-availability 409 policy.
