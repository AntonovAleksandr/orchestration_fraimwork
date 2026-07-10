# Checkout — T3: PVZ real OMS + server-side clustering (bbox-bound) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **🔄 RE-PLAN (2026-07-02, post live-smoke).** Live smoke на stage вскрыл, что OMS v2 `pickup-points` отдаёт **GROUPED** ответ `{data:[{logisticGroupId, inventory, pickupPoints.list}], availableFiltersValues}`, а не bare-array `[]PickupPointOption`, под который сейчас смоделированы клиент `starfish-oms` и `rawPVZ`. Coverage «X из N» живёт на **группе** (`inventory.cartAvailabillity`), oversize-флаги — вложены в `limitsExceeding` на точке. **ПРЕРЕКВИЗИТ:** сначала выполнить план `docs/superpowers/plans/2026-07-02-starfish-oms-pickup-points-grouped.md` (правка клиента → `GetPickupPoints` возвращает `PickupPointsResponse`) и bump тега клиента в `checkout/go.mod`. После этого Task 2 ниже использует grouped-тип. Evidence/исходник формы: `docs/research/2026-07-02-checkout-pvz-live-smoke.md`, `fixtures/oms-live/`, `core/go/logistics/internal/domain/models.go`. `areaViewPort` подтверждён live (3967→230 точек).

**Goal:** Take PVZ (`pickup-points`) live against real OMS in the existing `delivery` domain — bbox-bound via OMS `areaViewPort`, server-clustered in-memory — and unblock the `pvz` method in the per-method digest. No new domain, no migration, no contract change: the domain layer, clustering read-function, and the `GET /checkout/{id}/pickup-points?bbox&zoom` contract are **already in place** (Plan 3). What was in place as a **bare-array** (`rawPVZ` + `normalizePickupPoints`) is **reworked to grouped** (`rawPVZResponse` + `normalizePickupPointsGrouped`) after live-smoke proved OMS v2 returns a grouped envelope (see re-plan note above). This increment replaces the deferred `Options(PVZ) → nil` stub in `OMSDeliverySource` with a real `client.GetPickupPoints` call, threads the request `bbox` through to OMS (so we never fetch the 3967-point / 2.28 MB city dump), and removes the `markPVZDeferred` digest force.

**Architecture:** Per `domain-map.md` + ADR-0001. `delivery` is a stateless capability domain; `session` is the only consistency root. The PVZ map is an **on-demand read** (ADR-0001 guardrail: браузабельные датасеты НЕ входят в ядро `CheckoutState`) — it lives behind `GET /pickup-points`, not in any command response. Clustering is a pure read-function in `delivery` (`ClusterPickupPoints`), no PostGIS. The `DeliverySource` port is consumer-defined in `delivery`; the real OMS adapter (`OMSDeliverySource`) lives in `internal/adapters/delivery/` and re-serializes the typed starfish-oms **grouped** response into the resolver's faithful `rawPVZResponse` struct (envelope + groups + group inventory + points) via the proven `reencode` bridge, then feeds `normalizePickupPointsGrouped` (coverage from the group inventory → every point in the group; oversize from per-point `limitsExceeding`) — the same shape the fixture source uses, so the risky normalization stays table-tested.

**Tech Stack:** Go 1.26, `net/http` + `chi/v5`, `gj-go-money` (int64 kopecks), `gj-go-logger`, `oapi-codegen` types-only. Real OMS via `clients/starfish-oms` (`starfishoms.GetPickupPoints`). Money: OMS rubles (`json.Number`) → kopecks in the resolver (`rublesToKopecks`), never float. Coordinates are `float64` (geo, not money — correct).

**Prereq:** Plans 1–4 complete (tag `v0.1.0`). `delivery` domain + clustering + `pickup-points` contract live (Plan 3). Real-OMS contour already wired for courier+store (`OMSDeliverySource`, `wire.DeliveryService`). Local dev: `docker compose -f dev/docker-compose.yml up -d` (Postgres :5544), `make port-forward` (OMS v1/v2), `.env` with OMS token + city. `make setup` already run (private Go modules resolve).

---

## Grounding — `areaViewPort` shape CONFIRMED live (closes spec §11.7)

The starfish-oms client models `areaViewPort` as a permissive `*map[string]interface{}`. The authoritative shape is in the OMS Go logistics service — `platform/starfish24/core/go/logistics/internal/domain/models.go` — and **confirmed by live smoke 2026-07-02** (see `docs/research/2026-07-02-checkout-pvz-live-smoke.md`): a Moscow query with `areaViewPort` returned **230 points / 134 KB** vs **3967 points / 2.28 MB** without it.

```go
type AreaViewport struct { Corners Corners `json:"corners"` }
type Corners struct {
    LeftTop     Corner `json:"leftTop"`
    RightBottom Corner `json:"rightBottom"`
}
type Corner struct { Coordinates Coordinates `json:"coordinates"` }
// Coordinates { Latitude, Longitude float64 }
```

Wire shape:
```json
"areaViewport": { "corners": {
  "leftTop":     { "coordinates": { "latitude": <lat>, "longitude": <lng> } },
  "rightBottom": { "coordinates": { "latitude": <lat>, "longitude": <lng> } } } }
```

OMS behavior (from `pickup_point_service.go`): when `CityID` is present **and** `areaViewport` is set, both apply (city resolves the logistic group, `areaViewport` filters points to the bbox). When `CityID` is empty, `areaViewport` alone determines cities. We always have a city (adapter config) → **send both**. `filterPickupPointsByAreaViewport` uses `leftTop` (NW: max lat, min lng) and `rightBottom` (SE: min lat, max lng).

Mapping from our `BBox{MinLat, MinLng, MaxLat, MaxLng}`:
- `leftTop`     = `{ latitude: MaxLat, longitude: MinLng }`
- `rightBottom` = `{ latitude: MinLat, longitude: MaxLng }`

**Do NOT use the `rectangle` (firstCorner/secondCorner) alt-format** — the v11 handler converts it to `areaViewport` internally; we send the canonical `areaViewport` directly.

---

## What is ALREADY done (do not rebuild)

| Piece | Where | Status |
|---|---|---|
| `GET /checkout/{id}/pickup-points?bbox&zoom` contract | `api/v1/paths/delivery.yaml#PickupPoints`, `components/schemas/delivery.yaml#ClusterResult` | ✅ |
| Route mounted | `internal/domains/delivery/routes.go` | ✅ |
| `handler.PickupPoints` (bbox/zoom parse → service) | `internal/domains/delivery/handler.go` | ✅ |
| `service.PickupClusters(ctx, id, box, zoom)` | `internal/domains/delivery/service.go` | ✅ (calls `src.Options(PVZ)` today — **changes in Task 4**) |
| `ClusterPickupPoints` (pure grid; `pointZoomThreshold=13`, `gridCellsForZoom`) | `internal/domains/delivery/cluster.go` + `cluster_test.go` | ✅ |
| `rawPVZ` (bare-array) + `normalizePickupPoints` | `internal/adapters/delivery/{raw,resolver}.go` | ⚠ **rework → grouped**: `rawPVZResponse`/`rawPVZGroup`/`rawPVZPoint` + `normalizePickupPointsGrouped` (Task 1) |
| Fixture path (`pickup-points.json` → normalize) | `internal/adapters/delivery/fixturesource.go` | ⚠ **rework** (Task 3): feed grouped `rawPVZResponse` |
| starfish-oms client `GetPickupPoints` + `PickupPointOption` (bare-array) | `clients/starfish-oms` | ❌ **prerequisite** — see `docs/superpowers/plans/2026-07-02-starfish-oms-pickup-points-grouped.md` (returns `PickupPointsResponse` grouped) |

**The delta is small:** port gains a bbox-aware PVZ method; the real adapter implements it with `areaViewPort`; the service calls the new method; the digest stops forcing PVZ unavailable.

---

## File Structure (this plan)

```
checkout/
├── internal/domains/delivery/
│   ├── types.go            (modify)  + PickupPoints(ctx, cart, BBox) on DeliverySource
│   └── service.go          (modify)  PickupClusters calls src.PickupPoints (bbox-aware)
├── internal/adapters/delivery/
│   ├── oms.go              (modify)  implement PickupPoints → client.GetPickupPoints(areaViewPort);
│   │                                 remove markPVZDeferred; AllOptions PVZ decision documented
│   ├── oms_test.go         (modify)  + grouped reencode round-trip; + bbox→areaViewPort; remove TestMarkPVZDeferred
│   ├── raw.go              (modify)  rawPVZ (bare-array) → rawPVZResponse/rawPVZGroup/rawPVZPoint (grouped envelope)
│   ├── resolver.go         (modify)  normalizePickupPoints → normalizePickupPointsGrouped (coverage from group inventory;
│   │                                 oversize from limitsExceeding; single date → PromisedDate)
│   ├── fixturesource.go    (modify)  implement PickupPoints (load grouped fixture → normalizePickupPointsGrouped)
│   └── viewport.go         (create)  bboxToAreaViewPort(BBox) map[string]any  (the confirmed shape)
└── docs/dev/testing-plan.md (modify)  T3 → ✅; note digest-PVZ-without-drill-in decision
```

**No migration. No OpenAPI change. No new domain.** Wire (`internal/app/wire/delivery.go`) is unchanged — the source is still built by `DeliveryService`; only the port gains a method that the existing source value satisfies.

---

## Architectural decisions baked into this plan

- **D1 — PVZ is bbox-bound at OMS, not client-side.** The request `bbox` is threaded through the port to `OMSDeliverySource`, which builds `areaViewPort` and lets OMS filter. Fetching the whole city and filtering in `ClusterPickupPoints` would reproduce the AS-IS 2.28 MB dump. The client-side `inBBox` in `ClusterPickupPoints` stays as a safe no-op belt-and-suspenders (OMS-filtered set is already inside).
- **D2 — new port method `PickupPoints(ctx, cart, BBox)`, not extending `Options`.** `Options(ctx, cart, t)` is bbox-agnostic (used for courier/store drill-in and by `SetDeliveryMethod`/digest). PVZ on the map is a different read — it carries a viewport. A dedicated method keeps `Options` honest and makes the bbox contract explicit. `Options(PVZ)` stays (digest/komplektacii list path) but for the real adapter it is implemented on top of the same `GetPickupPoints` call **without** `areaViewPort` (city-wide, for the drill-in list `komplektacii?type=pvz`).
- **D3 — digest PVZ stays preliminary, NO drill-in.** PVZ is NOT added to `AllOptions` (a city-wide pickup-points call per digest = 3967 points / 2.28 MB on every command → the exact regression we're fixing). The `pvz` card in `delivery-options` keeps `Available`/`MinCost`/`MinDays`/`FreeThreshold` from `delivery-preliminary`; `EarliestPromisedDate` stays empty for PVZ (best=nil → `continue` in `GetDeliveryDigest`). This matches ADR-0001: the digest is the compact core, the map is a separate on-demand read.
- **D4 — `markPVZDeferred` is removed.** It existed only because PVZ was unbuilt. With `Options(PVZ)` real, the `pvz` method's `Available` comes straight from `delivery-preliminary` (OMS tells us whether pickup is offered for the cart/city).
- **D5 — `areaViewPort` shape is the confirmed OMS shape** (Grounding above), not the README guess. Modeled as a typed helper `bboxToAreaViewPort` returning `map[string]any` (the client field is permissive; we fill the canonical keys).

---

## Task 1: Port — bbox-aware `PickupPoints` on `DeliverySource` + `bboxToAreaViewPort` + grouped raw structs + `normalizePickupPointsGrouped`

Adds the bbox-aware PVZ read to the consumer-defined port, a pure helper that maps `BBox` → the confirmed `areaViewPort` wire shape, the **grouped `rawPVZ*` structs** that mirror OMS v2's grouped envelope, and the **`normalizePickupPointsGrouped`** resolver (coverage from group inventory → every point in the group; oversize from per-point `limitsExceeding`). No behavior change yet (no caller).

**Files:**
- Modify: `internal/domains/delivery/types.go`
- Modify: `internal/adapters/delivery/raw.go`
- Modify: `internal/adapters/delivery/resolver.go`
- Create: `internal/adapters/delivery/viewport.go`
- Create: `internal/adapters/delivery/viewport_test.go`

- [ ] **Step 1: Port method** — append to the `DeliverySource` interface in `internal/domains/delivery/types.go`

```go
// PickupPoints resolves PVZ komplektacii for the cart BOUNDED by the viewport bbox.
// The real adapter pushes bbox to OMS via areaViewPort (never fetches the whole city);
// the fixture adapter loads the baked set and lets ClusterPickupPoints filter.
// Returns DOMAIN types — normalization of OMS shape (and rubles→kopecks) is adapter-side.
PickupPoints(ctx context.Context, cart []CartLine, box BBox) ([]Komplektaciya, error)
```

- [ ] **Step 2: `bboxToAreaViewPort` helper** — create `internal/adapters/delivery/viewport.go`

```go
package delivery

import domain "gitlab.gloria.aaanet.ru/greensight/gj/go/checkout/internal/domains/delivery"

// bboxToAreaViewPort maps the domain BBox to the OMS areaViewPort wire shape
// (confirmed in platform/starfish24/core/go/logistics/internal/domain/models.go):
//
//	areaViewport: { corners: {
//	  leftTop:     { coordinates: { latitude, longitude } },   // NW corner
//	  rightBottom: { coordinates: { latitude, longitude } } } } // SE corner
//
// BBox{MinLat,MinLng,MaxLat,MaxLng} → leftTop=(MaxLat,MinLng), rightBottom=(MinLat,MaxLng).
// Returned as map[string]any to satisfy the starfish-oms permissive AreaViewPort field.
func bboxToAreaViewPort(b domain.BBox) map[string]any {
	return map[string]any{
		"corners": map[string]any{
			"leftTop": map[string]any{
				"coordinates": map[string]any{
					"latitude":  b.MaxLat,
					"longitude": b.MinLng,
				},
			},
			"rightBottom": map[string]any{
				"coordinates": map[string]any{
					"latitude":  b.MinLat,
					"longitude": b.MaxLng,
				},
			},
		},
	}
}
```

- [ ] **Step 3: Helper test** — create `internal/adapters/delivery/viewport_test.go`

```go
package delivery

import (
	"testing"

	domain "gitlab.gloria.aaanet.ru/greensight/gj/go/checkout/internal/domains/delivery"
)

func TestBBoxToAreaViewPort_mapsCorners(t *testing.T) {
	box := domain.BBox{MinLat: 55.5, MinLng: 37.3, MaxLat: 55.9, MaxLng: 37.9}
	avp := bboxToAreaViewPort(box)

	corners, ok := avp["corners"].(map[string]any)
	if !ok {
		t.Fatal("missing corners")
	}
	lt := corners["leftTop"].(map[string]any)["coordinates"].(map[string]any)
	if lt["latitude"] != 55.9 || lt["longitude"] != 37.3 {
		t.Fatalf("leftTop wrong: %+v", lt)
	}
	rb := corners["rightBottom"].(map[string]any)["coordinates"].(map[string]any)
	if rb["latitude"] != 55.5 || rb["longitude"] != 37.9 {
		t.Fatalf("rightBottom wrong: %+v", rb)
	}
}
```

- [ ] **Step 4: Grouped raw structs** — in `internal/adapters/delivery/raw.go`, **replace** the bare-array `rawPVZ` with the grouped envelope (mirrors `starfishoms.PickupPointsResponse` 1:1, faithful-not-normalized — keep OMS quirks: `cartAvailabillity` double-l typo, `dispatchWarehouse` not `dispatchWarehouseId`, nested `limitsExceeding`, single `date`):

```go
// rawPVZResponse mirrors OMS v2 /logistics/pickup-points GROUPED response (live-confirmed).
// Coverage "X of N" lives on the GROUP inventory; the point carries geo/cost/limitsExceeding.
type rawPVZResponse struct {
	Data                 []rawPVZGroup        `json:"data"`
	AvailableFiltersValues rawAvailableFilters `json:"availableFiltersValues"`
}

type rawAvailableFilters struct {
	CarrierIds []string `json:"carrierIds"`
}

type rawPVZGroup struct {
	LogisticGroupId string             `json:"logisticGroupId"`
	LogisticRuleId  string             `json:"logisticRuleId"`
	Inventory       rawPVZInventory    `json:"inventory"`
	PickupPoints    rawPVZPointsList   `json:"pickupPoints"`
}

type rawPVZInventory struct {
	AvailableQuantity int                  `json:"availableQuantity"`
	CartAvailabillity []rawProductAvail    `json:"cartAvailabillity"` // OMS typo double-l — keep verbatim
	DispatchDate      string               `json:"dispatchDate"`
	DispatchWarehouse string               `json:"dispatchWarehouse"` // NOT dispatchWarehouseId
	FulfillmentType   string               `json:"fulfillmentType"`
}

type rawProductAvail struct {
	ProductId         string `json:"productId"`
	AvailableQuantity int    `json:"availableQuantity"`
	Available         bool   `json:"available"`
}

type rawPVZPointsList struct {
	List []rawPVZPoint `json:"list"`
}

type rawPVZPoint struct {
	Id                   string            `json:"id"`          // carrier-originalId
	Name                 string            `json:"name"`
	Type                 string            `json:"type"`        // pickupservice|postmate
	Coordinates          rawCoordinates    `json:"coordinates"` // {latitude, longitude}
	Date                 string            `json:"date"`        // single date (no separate dispatch/delivery)
	DeliveryCost         json.Number       `json:"deliveryCost"`
	ActualDeliveryCost   json.Number       `json:"actualDeliveryCost"`
	CarrierId            string            `json:"carrierId"`
	TariffId             string            `json:"tariffId"`
	LimitsExceeding      rawLimitsExceed   `json:"limitsExceeding"`
	AvailablePaymentTypes []string         `json:"availablePaymentTypes"`
	AvailableAcquirers   []string          `json:"availableAcquirers"`
	ShelfLifeDays        int               `json:"shelfLifeDays"`
}

type rawLimitsExceed struct {
	OrderDimensionsExceeded    bool `json:"orderDimensionsExceeded"`
	OrderWeightExceeded        bool `json:"orderWeightExceeded"`
	OrderPackageWeightExceeded bool `json:"orderPackageWeightExceeded"`
}
```

> Reuse the existing `rawCoordinates` if it already exists for stores/intervals (`{Latitude, Longitude float64}`); otherwise define it here. Delete the old bare-array `rawPVZ` struct (it's replaced). The old `normalizePickupPoints` is replaced in Step 5.

- [ ] **Step 5: `normalizePickupPointsGrouped`** — in `internal/adapters/delivery/resolver.go`, **replace** `normalizePickupPoints` (which took bare `[]rawPVZ`) with the grouped walker:

```go
// normalizePickupPointsGrouped converts OMS's grouped pickup-points response into
// domain Komplektaciya. Coverage (X-of-N) is on the GROUP inventory and is applied to
// EVERY point in that group; oversize flags come from the point's limitsExceeding;
// the single `date` becomes the point's PromisedDate. Money: rubles → kopecks.
func normalizePickupPointsGrouped(resp rawPVZResponse) []domain.Komplektaciya {
	var out []domain.Komplektaciya
	for _, g := range resp.Data {
		cov := coverageFromInventory(g.Inventory) // X-of-N from cartAvailabillity / availableQuantity
		for _, p := range g.PickupPoints.List {
			out = append(out, domain.Komplektaciya{
				DeliveryType:         domain.DeliveryPVZ,
				DeliveryCostKopecks:  rublesToKopecks(p.DeliveryCost),
				ActualCostKopecks:    rublesToKopecks(p.ActualDeliveryCost),
				Coverage:             cov,                  // propagated from the group
				PromisedDate:         p.Date,               // single date → PromisedDate
				Oversize: domain.OversizeFlags{             // from nested limitsExceeding
					DimensionsExceeded: p.LimitsExceeding.OrderDimensionsExceeded,
					WeightExceeded:     p.LimitsExceeding.OrderWeightExceeded,
					PackageWeightExceeded: p.LimitsExceeding.OrderPackageWeightExceeded,
				},
				Point: domain.PickupPointInfo{
					PickupPointID: p.Id,
					Name:          p.Name,
					Lat:           p.Coordinates.Latitude,
					Lng:           p.Coordinates.Longitude,
					CarrierId:     p.CarrierId,
					ShelfLifeDays: p.ShelfLifeDays,
					// availablePaymentTypes / availableAcquirers mapped to domain as needed
				},
			})
		}
	}
	return out
}
```

> Match the domain `Komplektaciya`/`PickupPointInfo`/`OversizeFlags`/`Coverage` field names to the actual structs in `internal/domains/delivery/types.go` (the old `normalizePickupPoints` shows which fields exist — reuse the same names; only the data source changes from per-point to group-inventory). `coverageFromInventory` is a small helper extracted here (count `available==true` in `CartAvailabillity`, or use `AvailableQuantity` — match what the old `normalizePickupPoints` did with `instock`). Add a table test `TestNormalizePickupPointsGrouped_*` mirroring the existing pickup-points normalize tests, but feeding `rawPVZResponse` with one group (coverage=2) + 3 points → expect 3 `Komplektaciya` all with `Coverage.Available==2`.

- [ ] **Step 6: Build (expect compile error — adapters don't implement the new method yet)**

```bash
go build ./...
```
Expected: `OMSDeliverySource` and `FixtureDeliverySource` do not satisfy `delivery.DeliverySource` (missing `PickupPoints`). Tasks 2–3 fix this. Do not commit until Task 3.

---

## Task 2: `OMSDeliverySource` — real `GetPickupPoints` (grouped) + reencode PVZ; remove `markPVZDeferred`

> 🔄 **Re-planned after live-smoke.** Assumes the client plan (`docs/superpowers/plans/2026-07-02-starfish-oms-pickup-points-grouped.md`) is **done and bumped in `go.mod`**: `GetPickupPoints` now returns `starfishoms.PickupPointsResponse{Data []PickupPointGroup, AvailableFiltersValues}`, with group-level `Inventory.CartAvailabillity` (coverage) and per-point `LimitsExceeding` (oversize). The old bare-array `[]PickupPointOption` is gone.

Implements the bbox-aware PVZ read over the published starfish-oms client, feeds OMS's grouped response through a **grouped `reencode`→`normalizePickupPointsGrouped` bridge**, and removes the digest force so `pvz` surfaces from preliminary. The risky normalization stays table-tested (T1/T3), now over the grouped shape.

**Files:**
- Modify: `internal/adapters/delivery/oms.go`
- Modify: `internal/adapters/delivery/oms_test.go`
- (Also depends on Task 1's `rawPVZResponse`/`rawPVZGroup`/`rawPVZPoint` + `normalizePickupPointsGrouped` in `raw.go`/`resolver.go`.)

- [ ] **Step 1: `PickupPoints` method** — append to `internal/adapters/delivery/oms.go`

```go
// PickupPoints resolves PVZ komplektacii for the cart BOUNDED by bbox. The bbox is
// pushed to OMS via areaViewPort (confirmed shape, see viewport.go) so OMS filters —
// we never fetch the whole city (live: 3967 points / 2.28 MB without bbox vs 230 / 134 KB
// with). City + areaViewPort are both sent (OMS uses both). OMS returns a GROUPED response
// (data[] with group inventory + pickupPoints.list); coverage "X of N" is on the GROUP
// inventory and is applied to every point in that group by normalizePickupPointsGrouped.
func (s *OMSDeliverySource) PickupPoints(ctx context.Context, cart []domain.CartLine, box domain.BBox) ([]domain.Komplektaciya, error) {
	avp := bboxToAreaViewPort(box)
	resp, err := s.client.GetPickupPoints(ctx, starfishoms.PickupPointsRequest{
		AddressTo:   starfishoms.AddressToCity{City: s.cityRef()},
		Cart:        s.cartRef(cart),
		AreaViewPort: &avp,
	})
	if err != nil {
		return nil, omsErr("pickup-points", err)
	}
	var raw rawPVZResponse
	if err := reencode(resp, &raw); err != nil {
		return nil, fmt.Errorf("oms pickup-points decode: %w", err)
	}
	return normalizePickupPointsGrouped(raw), nil
}
```

> Verify the generated `starfishoms.PickupPointsResponse`/`PickupPointGroup`/`PickupPoint`/`LimitsExceeding` field names against `openapi.gen.go` after the client regen. `rawPVZResponse` mirrors the envelope (`Data []rawPVZGroup`, `AvailableFiltersValues`); `rawPVZGroup` mirrors `inventory` + `pickupPoints.list`; `rawPVZPoint` carries `limitsExceeding` + single `date` + `shelfLifeDays` + `availableAcquirers`. `reencode` round-trips them; money fields (`deliveryCost`/`actualDeliveryCost`) stay `json.Number` on both sides.

- [ ] **Step 2: `Options(PVZ)` — city-wide (no bbox), for the `komplektacii?type=pvz` drill-in list**

Replace the deferred `case domain.DeliveryPVZ: return nil, nil` in `Options` with a city-wide call (no `areaViewPort`):

```go
case domain.DeliveryPVZ:
	// City-wide PVZ list (no bbox) — used by the komplektacii?type=pvz drill-in list.
	// The MAP path (bbox-bound) uses PickupPoints, not this.
	resp, err := s.client.GetPickupPoints(ctx, starfishoms.PickupPointsRequest{
		AddressTo: starfishoms.AddressToCity{City: s.cityRef()},
		Cart:      s.cartRef(cart),
	})
	if err != nil {
		return nil, omsErr("pickup-points", err)
	}
	var raw rawPVZResponse
	if err := reencode(resp, &raw); err != nil {
		return nil, fmt.Errorf("oms pickup-points decode: %w", err)
	}
	return normalizePickupPointsGrouped(raw), nil
```

> ⚠ Live: this is a city-wide call (3967 points / 2.28 MB for Moscow). Acceptable ONLY for the explicit drill-in list (user taps "ПВЗ" → list). Confirm with the live smoke (Task 7) that the response is tolerable; if not, gate this behind a bbox too (the list UI passes the current viewport) — Task 7 decision point. The grouped envelope at least keeps coverage on the group, so decode won't fail — but the payload is large.

- [ ] **Step 3: Remove `markPVZDeferred`** — delete the function and its call in `Digest`

In `Digest`, remove the line `markPVZDeferred(&d)` and the comment referencing it. Delete the `markPVZDeferred` function. The `pvz` method now keeps whatever `Available` OMS returned in `delivery-preliminary` (live baseline: `available:true, coverage=2`).

- [ ] **Step 4: `AllOptions` — keep PVZ deferred (D3)** — update the comment on the PVZ branch to record the decision:

```go
// PVZ is intentionally NOT resolved here (D3): a city-wide pickup-points call per
// digest = up to ~3967 points / 2.28 MB on every command (live) — the exact AS-IS
// regression. The pvz card in delivery-options keeps preliminary numbers (Available/
// MinCost/MinDays/FreeThreshold); EarliestPromisedDate stays empty (best=nil → continue
// in GetDeliveryDigest). The bbox-bound map is a separate on-demand read (PickupPoints).
```

No goroutine is added. `AllOptions` still returns only courier + the two store types.

- [ ] **Step 5: Update adapter tests** — modify `internal/adapters/delivery/oms_test.go`

1. **Delete** `TestMarkPVZDeferred` (the function it tests is gone).
2. **Replace** the reencode round-trip with the **grouped** shape (mirrors `TestReencode_preliminaryRoundTrip`):

```go
func TestReencode_pickupPointsGroupedRoundTrip(t *testing.T) {
	carrier := "cdek"
	id := "cdek-828K"
	lat := 55.75
	lng := 37.61
	cost := json.Number("299")
	grpID := "RU-77"
	dimExceeded := false
	shelf := 7
	// Coverage lives on the GROUP inventory; the point carries limitsExceeding.
	resp := starfishoms.PickupPointsResponse{Data: []starfishoms.PickupPointGroup{{
		LogisticGroupId: &grpID,
		Inventory: &starfishoms.PickupPointsInventory{
			AvailableQuantity: pint(2),
			CartAvailabillity: []starfishoms.ProductAvailability{{ /* 2 of N available */ }},
		},
		PickupPoints: &starfishoms.PickupPointsList{List: []starfishoms.PickupPoint{{
			Id: &id, CarrierId: &carrier, Name: &id, ShelfLifeDays: &shelf,
			Coordinates: &starfishoms.CoordinatesNumber{Latitude: &lat, Longitude: &lng},
			DeliveryCost: &cost,
			LimitsExceeding: &starfishoms.LimitsExceeding{OrderDimensionsExceeded: &dimExceeded},
		}}},
	}}}

	var raw rawPVZResponse
	if err := reencode(resp, &raw); err != nil {
		t.Fatalf("reencode: %v", err)
	}
	ks := normalizePickupPointsGrouped(raw)
	if len(ks) != 1 {
		t.Fatalf("want 1 pvz, got %d", len(ks))
	}
	k := ks[0]
	if k.DeliveryType != domain.DeliveryPVZ || k.Point.PickupPointID != "cdek-828K" {
		t.Fatalf("pvz mapping wrong: %+v", k)
	}
	if k.DeliveryCostKopecks.Kopecks() != 29900 {
		t.Fatalf("rubles→kopecks: want 29900, got %d", k.DeliveryCostKopecks.Kopecks())
	}
	if k.Point.Lat != 55.75 || k.Point.Lng != 37.61 {
		t.Fatalf("coords wrong: %+v", k.Point)
	}
	// Coverage is propagated from the group inventory to the point.
	if k.Coverage.Available != 2 {
		t.Fatalf("group coverage not propagated: %+v", k.Coverage)
	}
}
```

> Match the generated `starfishoms.*` field names + pointer/value conventions against `openapi.gen.go` after the client regen (helpers like `pint`/`pstr` likely already exist in the test file — reuse). Adjust `Coverage.Available` field name to whatever `normalizePickupPointsGrouped` sets (see Task 1).

- [ ] **Step 6: Build + offline test**

```bash
go build ./... && go vet ./... && go test ./internal/adapters/delivery/ -count=1
```
Expected: compile (after Task 1 defines `rawPVZResponse`/`normalizePickupPointsGrouped` and Task 3 implements `PickupPoints` on the fixture source); adapter unit tests green.

---

## Task 3: `FixtureDeliverySource` — implement `PickupPoints`

The fixture/test double must satisfy the new port method so offline e2e and `wire.DeliveryServiceWithSource(...FixtureDeliverySource{})` keep compiling.

**Files:**
- Modify: `internal/adapters/delivery/fixturesource.go`

- [ ] **Step 1: Implement `PickupPoints`** — append to `internal/adapters/delivery/fixturesource.go`

```go
// PickupPoints feeds the baked PVZ fixture through the resolver. The fixture is NOT
// bbox-filtered here (it is small and curated); ClusterPickupPoints filters by bbox
// downstream. This keeps the offline e2e shape identical to the real adapter's contract.
func (FixtureDeliverySource) PickupPoints(_ context.Context, _ []domain.CartLine, _ domain.BBox) ([]domain.Komplektaciya, error) {
	var raw rawPVZResponse
	if err := json.Unmarshal(fxPVZ, &raw); err != nil {
		return nil, err
	}
	return normalizePickupPointsGrouped(raw), nil
}
```

> `fxPVZ` (the embedded JSON in `fixturesource.go`) must be a **grouped object** now, not a bare array — re-derive it from `platform-new/checkout/fixtures/oms-live/pickup-points-areaViewPort-center-msk.json` (trim to 1 group + ~10 points to keep the embed small, but preserve the envelope `{data:[{inventory, pickupPoints.list}], availableFiltersValues}` and all field types). The `Options(PVZ)` path in `fixturesource.go` (if it still decodes `fxPVZ` into `[]rawPVZ`) must also switch to `rawPVZResponse` + `normalizePickupPointsGrouped`.

- [ ] **Step 2: Build + full offline suite**

```bash
go build ./... && go vet ./... && go test ./... -count=1
```
Expected: green (boundary tests, delivery service/handler tests, transport e2e). The existing `pickup-points` fixture path now flows through the same `normalizePickupPointsGrouped`.

- [ ] **Step 3: Commit**

```bash
git add internal
git commit -m "feat(delivery): PVZ real OMS via areaViewPort bbox + port.PickupPoints; drop markPVZDeferred (T3)"
```

---

## Task 4: `service.PickupClusters` — call the bbox-aware port method

Switch the map read from the bbox-agnostic `Options(PVZ)` to the bbox-aware `PickupPoints(cart, box)` so the viewport reaches OMS.

**Files:**
- Modify: `internal/domains/delivery/service.go`

- [ ] **Step 1: Replace the source call in `PickupClusters`**

In `internal/domains/delivery/service.go`, change:

```go
pts, err := s.src.Options(ctx, ref.Cart, DeliveryPVZ)
```
to:

```go
pts, err := s.src.PickupPoints(ctx, ref.Cart, box)
```
Keep the rest of `PickupClusters` unchanged (`ClusterPickupPoints(pts, box, zoom)` — its `inBBox` is now a safe no-op over the OMS-filtered set).

- [ ] **Step 2: Service test** — if `service_test.go` has a `PickupClusters` fake-source test, ensure the fake now implements `PickupPoints` (return the same points it returned via `Options(PVZ)`). Add a case asserting `PickupPoints` is called with the request `box` (capture the bbox arg).

- [ ] **Step 3: Build + test + commit**

```bash
go build ./... && go vet ./... && go test ./... -count=1
git add internal/domains/delivery
git commit -m "refactor(delivery): PickupClusters threads bbox to src.PickupPoints (OMS areaViewPort)"
```

---

## Task 5: Live smoke on stage (real OMS) — the truth gate

This is the increment's real verification: confirm `areaViewPort` filters, measure volume/timing, and decide the `Options(PVZ)` city-wide question (Task 2 Step 2 warning).

**Manual steps (stage, real OMS, customer 4455421 or similar):**

- [ ] **Step 1: Port-forward + run**

```bash
export KUBECONFIG=/path/to/your/kubeconfig
make port-forward   # OMS v1/v2
make migrate-up     # idempotent
make run            # :8080
```

- [ ] **Step 2: Bootstrap a session**

```bash
ID=$(curl -s -X POST localhost:8080/api/v1/checkout -d '{"customer_id":"4455421","basket_id":"<basket>"}' | jq -r .checkout_id)
```

- [ ] **Step 3: digest — `pvz` now Available from preliminary**

```bash
curl -s localhost:8080/api/v1/checkout/$ID/delivery-options | jq '.methods[] | select(.delivery_type=="pvz")'
```
Expect: `available: true` (no longer forced false), `min_cost_kopecks`/`min_days`/`free_threshold_kopecks` from preliminary; `earliest_promised_date` null (no drill-in — D3).

- [ ] **Step 4: map — bbox-bound clusters (low zoom)**

```bash
# Moscow bbox, low zoom (city) → clusters
curl -s "localhost:8080/api/v1/checkout/$ID/pickup-points?bbox=55.5,37.3,55.9,37.9&zoom=10" | jq '{clusters:(.clusters|length), points:(.points//[]|length)}'
```
Expect: `clusters` > 0, `points` null; response **<< 2.28 MB** (clusters carry only `{lat,lng,count}`). Confirm via OMS pod logs that `pickup-points` was called WITH `areaViewPort` (log line `Converted to AreaViewport` / `After AreaViewport filtering: N pickup points left`).

- [ ] **Step 5: map — high zoom → real points with coverage**

```bash
curl -s "localhost:8080/api/v1/checkout/$ID/pickup-points?bbox=55.73,37.58,55.77,37.64&zoom=15" | jq '{clusters:(.clusters//[]|length), points:(.points|length), sample:.points[0]}'
```
Expect: `points` > 0, each with `coverage` ("X из N"), `delivery_cost_kopecks`, `features.oversize`/`passport_req`; `clusters` null. Per ADR-0001 guardrail — points are on-demand, NOT in any command response.

- [ ] **Step 6: `Options(PVZ)` city-wide decision (Task 2 Step 2)**

```bash
curl -s "localhost:8080/api/v1/checkout/$ID/komplektacii?type=pvz" | jq 'length'
```
If this returns thousands (Moscow ~3967) and is slow → gate `Options(PVZ)` behind a bbox too (accept an optional `bbox` query param on `komplektacii?type=pvz`, pass to `PickupPoints`). If the list UI always has a viewport, make `bbox` mandatory for `type=pvz`. Record the decision in `testing-plan.md`.

- [ ] **Step 7: idempotency / no-regression**

```bash
# repeat the map call → same result; warm vs cold timing
curl -s "localhost:8080/api/v1/checkout/$ID/pickup-points?bbox=55.5,37.3,55.9,37.9&zoom=10" -w '%{time_total}\n' -o /dev/null
# courier + store still work (unchanged)
curl -s "localhost:8080/api/v1/checkout/$ID/komplektacii?type=courier" | jq 'length'
```

---

## Task 6: Clustering tuning + docs + tag

- [ ] **Step 1: Threshold tuning** — using the stage data from Task 5, evaluate `pointZoomThreshold=13` and `gridCellsForZoom` (`<=4 → 2`, `<=8 → 8`, `default → 32`). Goals:
  - Low zoom (city, ~10): tens of clusters, not hundreds; payload small.
  - Boundary zoom (12→13): the switch to points feels right (no cluster of 1, no point explosion).
  - Adjust constants in `cluster.go` if needed; re-run `cluster_test.go` with updated expectations.

- [ ] **Step 2: Update `docs/dev/testing-plan.md`** — in the readiness table, **T3 → ✅**; in §7 GAPs, move "ПВЗ real + серверная кластеризация" to "Сделано"; add a note on the digest-PVZ-without-drill-in decision (D3) and the `Options(PVZ)` bbox decision from Task 5 Step 6.

- [ ] **Step 3: DoD gates + tag**

```bash
make generate && make lint && go vet ./... && go test ./... -count=1
CHECKOUT_TEST_DB_DSN="postgres://checkout:checkout@127.0.0.1:5544/checkout?sslmode=disable" \
  go test ./internal/domains/session/ -run TestRepository -count=1
make docker
git add -A
git commit -m "docs(checkout): T3 PVZ real+clustering done; digest pvz from preliminary; testing-plan updated"
git tag v0.2.0-pvz
```

> Push (main + tags) is Zak's call per workspace rules — do not push automatically.

---

## Definition of Done (T3)

- **`GET /checkout/{id}/pickup-points?bbox&zoom`** is live against real OMS: bbox is pushed to OMS via `areaViewPort` (confirmed shape); low zoom → clusters `{lat,lng,count}`; high zoom → points with coverage «X из N» + cost + features.
- **No 3967-point / 2.28 MB dump**: OMS filters by `areaViewPort`; the wire payload is small at low zoom (clusters) and bounded by the viewport at high zoom (points).
- **`pvz` method is available** in `delivery-options` digest (from `delivery-preliminary`); `markPVZDeferred` removed; PVZ **not** added to `AllOptions` (no city-wide call per command — D3).
- **ADR-0001 guardrail holds**: PVZ points/clusters are an on-demand read; they are NOT part of any command's `CheckoutState` response. Verified by a test asserting the `CheckoutState` JSON has no pickup-points array.
- **Money int64 kopecks** end-to-end (reencode grouped PVZ → `normalizePickupPointsGrouped` → `rublesToKopecks`); coordinates `float64`. Coverage `int` propagated from group inventory → every point in the group.
- **Gates green:** `go build/vet/test ./...`, `make generate` (no drift), `make lint` (redocly), `make docker`; live stage smoke (Task 5) recorded; tagged `v0.2.0-pvz`.

---

## Open / follow-up (not in this plan)

- **`Options(PVZ)` city-wide gating** — resolved in Task 5 Step 6 (likely: require `bbox` for `komplektacii?type=pvz` too). If gated, add an optional `bbox` query param to the `Komplektacii` path + a small OpenAPI addition (then `make generate`).
- **PVZ caching (tech-debt)** — geo PVZ (where the points are, carrier, hours) is cart-independent and slow-changing → cacheable separately from cart-dependent coverage «X из N». Out of scope here; note in `testing-plan.md` tech-debt.
- **`SetDeliveryMethod(pvz)`** — once PVZ is selectable, `SetDeliveryMethod` calls `Options(PVZ)` (city-wide) to `pickBest`; if Task 5 Step 6 gated it behind bbox, `SetDeliveryMethod` needs a viewport too (the "best PVZ" auto-select is viewport-relative). Decide when wiring the frontend map→select flow.
- **`client_order_id` / commit** — unaffected (commit saga is still stubbed; T4 is a separate track).
