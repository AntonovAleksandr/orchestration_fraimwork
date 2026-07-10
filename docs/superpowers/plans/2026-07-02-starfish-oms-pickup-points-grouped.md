# starfish-oms client — pickup-points: fix GROUPED v2 response (was bare-array) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Checkbox (`- [ ]`) tracking.

**Goal:** Fix the `GetPickupPoints` response model. The client was modelled from a stale/wrong fixture as a **bare array** `[]PickupPointOption` with coverage (`instock`/`productAvailability`) and oversize flags **on the point**. Live stage v2 returns a **grouped** envelope `{data:[{logisticGroupId, logisticRuleId, inventory, pickupPoints.list[]}], availableFiltersValues}` where coverage lives on the group's `inventory` and oversize flags are nested in `limitsExceeding`. Without this fix `client.GetPickupPoints` fails to decode on live (expects array, OMS sends object) → blocks checkout T3.

**Evidence:** `platform-new/checkout/fixtures/oms-live/{pickup-points-areaViewPort-center-msk.json (230 pts/134KB), pickup-points-no-areaViewPort-msk.json (3967 pts/2.28MB)}` (gitignored). Research note: `docs/research/2026-07-02-checkout-pvz-live-smoke.md`. OMS source of the shape: `platform/starfish24/core/go/logistics/internal/domain/models.go` (`PickupPointsResponse`, `PickupPointGroup`, `PickupPointsList`, `AreaViewport`).

**Scope:** client `platform-new/clients/starfish-oms` only — OpenAPI schema, generated types, `GetPickupPoints` return type, testdata, tests, README, design spec §4.6. Tag + bump in `checkout/go.mod` (separate follow-up, see T3 plan update).

**Faithful-not-normalized principle (unchanged):** the client returns exactly what OMS sends, quirks preserved (`cartAvailabillity` double-l typo; `dispatchWarehouse` not `dispatchWarehouseId`; `date` single field; `limitsExceeding` nested). No domain normalization here — that stays in checkout's adapter.

---

## Real v2 shape (authoritative, from live)

```jsonc
{
  "data": [ {
    "logisticGroupId": "RU-77",
    "logisticRuleId":  "...",
    "inventory": {
      "availableQuantity": int,
      "cartAvailabillity": [{ "productId": "...", "availableQuantity": int, "available": bool }],  // OMS typo double-l
      "dispatchDate":       "2026-07-02",
      "dispatchWarehouse":  "00005550015678154",   // key = dispatchWarehouse (NOT ...Id)
      "fulfillmentType":    "fulfillment..."
    },
    "pickupPoints": { "list": [ {
      "id":                  "dpd-7P49",           // = carrier-originalId
      "name":                "...",
      "type":                "pickupservice"|"postmate",
      "coordinates":         { "latitude": number, "longitude": number },
      "date":                "2026-07-03",         // single date (no separate dispatch/delivery)
      "deliveryCost":        number,               // rubles
      "actualDeliveryCost":  number,
      "carrierId":           "dpd",
      "tariffId":            "PCLPVZ",
      "limitsExceeding":     { "orderDimensionsExceeded": bool, "orderWeightExceeded": bool, "orderPackageWeightExceeded": bool },
      "availablePaymentTypes": ["cod","prepaid"],
      "availableAcquirers":    ["yookassa"],
      "shelfLifeDays":       int
    } ] }
  } ],
  "availableFiltersValues": { "carrierIds": ["cdek","dpd","5post","yandexNextDayDelivery","russianpost"] }
}
```

**`PickupPointsRequest` (unchanged):** `addressTo`, `cart`, `areaViewPort` (permissive object — confirmed shape `corners.leftTop/rightBottom.coordinates.{latitude,longitude}`; keep permissive `additionalProperties: true` so the client stays wire-faithful and callers fill it), `systemSettings.pickupPointId`, plus the shared `inStockOnly`/`filterByLogisticGroup`/`basketFullness`/`shortestDistance`. **Do NOT** type `areaViewPort` strictly — the OMS Go service accepts it permissively and the caller (checkout) owns the shape (confirmed in research note).

---

## File Structure

```
clients/starfish-oms/
├── api/v1/paths/logistics.yaml                 (modify) PickupPoints 200 response → PickupPointsResponse (object, not array)
├── api/v1/components/schemas/logistics.yaml    (modify) replace PickupPointOption(bare) with grouped: PickupPointsResponse,
│                                                         PickupPointGroup, PickupPointsInventory, PickupPointsList,
│                                                         PickupPoint, LimitsExceeding, AvailableFiltersValues
├── api/v1/bundle/openapi.yaml                  (regen)  make bundle
├── openapi.gen.go                              (regen)  oapi-codegen
├── client.go                                   (modify) GetPickupPoints → (PickupPointsResponse, error)
├── client_test.go                              (modify) update assertions to grouped shape
├── testdata/pickup-points.json                 (replace) bare-array → live grouped object (from fixtures/oms-live, small bbox)
├── README.md                                   (modify) update GetPickupPoints example + faithful note
└── docs/superpowers/specs/2026-05-30-starfish-oms-client-design.md  (modify) §4.6 grouped shape; §5 quirk #8 PVZ dispatchWarehouse on inventory
```

---

## Task 1: OpenAPI schema — grouped response types

**Files:** `api/v1/components/schemas/logistics.yaml`, `api/v1/paths/logistics.yaml`

- [ ] **Step 1: Replace `PickupPointOption` (and its coverage-form-1 comment) with the grouped types** in `api/v1/components/schemas/logistics.yaml`:

```yaml
# ── pickup-points (v2) — GROUPED response (live-confirmed 2026-07-02) ────────
# OMS returns {data:[{logisticGroupId, inventory, pickupPoints.list}], availableFiltersValues}.
# Coverage (X-of-N) lives on the GROUP inventory; the point carries geo + cost + limitsExceeding.
PickupPointsResponse:
  type: object
  properties:
    data:
      type: array
      items: { $ref: '#/PickupPointGroup' }
    availableFiltersValues: { $ref: '#/AvailableFiltersValues' }

AvailableFiltersValues:
  type: object
  properties:
    carrierIds:
      type: array
      items: { type: string }

PickupPointGroup:
  type: object
  properties:
    logisticGroupId: { type: string }
    logisticRuleId:  { type: string }
    inventory:       { $ref: '#/PickupPointsInventory' }
    pickupPoints:    { $ref: '#/PickupPointsList' }

PickupPointsInventory:
  type: object
  properties:
    availableQuantity: { type: integer }
    # NB: OMS typo double-l (same as delivery-intervals). Keep verbatim.
    cartAvailabillity:
      type: array
      items: { $ref: '#/ProductAvailability' }
    dispatchDate:      { type: string, description: "YYYY-MM-DD" }
    # NB: key = dispatchWarehouse (stores use dispatchWarehouseId). Do NOT unify.
    dispatchWarehouse: { type: string }
    fulfillmentType:   { type: string }

PickupPointsList:
  type: object
  properties:
    list:
      type: array
      items: { $ref: '#/PickupPoint' }

PickupPoint:
  type: object
  properties:
    id:                    { type: string, description: "carrier-originalId, e.g. dpd-7P49" }
    name:                  { type: string }
    type:                  { type: string, description: "pickupservice|postmate" }
    coordinates:           { $ref: '#/CoordinatesNumber' }
    date:                  { type: string, description: "single date YYYY-MM-DD (no separate dispatch/delivery)" }
    deliveryCost:          { type: number, format: double, description: "rubles" }
    actualDeliveryCost:    { type: number, format: double }
    carrierId:             { type: string }
    tariffId:              { type: string }
    limitsExceeding:       { $ref: '#/LimitsExceeding' }
    availablePaymentTypes: { type: array, items: { type: string } }
    availableAcquirers:    { type: array, items: { type: string } }
    shelfLifeDays:         { type: integer }

LimitsExceeding:
  type: object
  properties:
    orderDimensionsExceeded:      { type: boolean }
    orderWeightExceeded:          { type: boolean }
    orderPackageWeightExceeded:   { type: boolean }
```

> Reuse existing `#/ProductAvailability` and `#/CoordinatesNumber` (already defined for stores/intervals). Keep `PickupPointsRequest` and `PickupPointsSystemSettings` **as-is** (`areaViewPort` stays permissive `additionalProperties: true`). Delete the old `PickupPointOption` block.

- [ ] **Step 2: Response envelope** — in `api/v1/paths/logistics.yaml`, change `PickupPoints.200`:

```yaml
    responses:
      "200":
        description: Pickup points grouped by logistic group (with available filters).
        content:
          application/json:
            schema:
              $ref: '../components/schemas/logistics.yaml#/PickupPointsResponse'
```
Update the path `summary` from "bare array" to "grouped by logistic group; provide areaViewPort bbox".

---

## Task 2: Regenerate + `GetPickupPoints` return type

**Files:** `openapi.gen.go`, `client.go`

- [ ] **Step 1: Regen** — `make bundle && make generate` (or the repo's equivalent — check `clients/starfish-oms/Makefile`). Expect `openapi.gen.go` to gain `PickupPointsResponse`, `PickupPointGroup`, `PickupPointsInventory`, `PickupPointsList`, `PickupPoint`, `LimitsExceeding`, `AvailableFiltersValues`, and **drop** `PickupPointOption`.

- [ ] **Step 2: `GetPickupPoints` signature** — in `client.go`:

```go
// GetPickupPoints returns third-party pickup points / parcel lockers grouped by
// logistic group, with available filter values. Always provide areaViewPort in the
// request — an unbounded Moscow query returns ~3963 points (~2.3 MB).
//
// Coverage (X-of-N) lives on each group's inventory.cartAvailabillity (shared by all
// points in the group); oversize flags are nested in point.limitsExceeding.
// Errors are *httpclient.Error passed through from the substrate.
func (c *Client) GetPickupPoints(
	ctx context.Context, req PickupPointsRequest,
) (PickupPointsResponse, error) {
	ctx = withTargetEndpoint(ctx, pathPickupPoints)
	var out PickupPointsResponse
	err := c.v2.DoJSON(ctx, "pickup_points", http.MethodPost, pathPickupPoints, req, &out)
	return out, err
}
```

---

## Task 3: Testdata + tests

**Files:** `testdata/pickup-points.json`, `client_test.go`

- [ ] **Step 1: Replace testdata** — copy `platform-new/checkout/fixtures/oms-live/pickup-points-areaViewPort-center-msk.json` (230 pts, 134 KB, grouped) → `clients/starfish-oms/testdata/pickup-points.json`. This is a faithful live snapshot; small enough for a fixture. (If the repo prefers trimmed fixtures, keep 1 group + ~10 points — but preserve the envelope shape and all field types.)

- [ ] **Step 2: Update `client_test.go`** — every assertion that indexes `PickupPointOption` directly must walk `resp.Data[].PickupPoints.List[]`. Specifically:
  - the happy-path test (~line 138 "expected at least one PickupPointOption") → assert `len(resp.Data) > 0` and `len(resp.Data[0].PickupPoints.List) > 0`.
  - the `dispatchWarehouse` quirk test (~line 217/239) → assert on `resp.Data[].Inventory.DispatchWarehouse`.
  - the `Instock > 0` test (~line 291) → coverage is now `Inventory.AvailableQuantity` / `Inventory.CartAvailabillity`; update or move to group-level.
  - the `Coordinates` test (~line 357) → `resp.Data[0].PickupPoints.List[0].Coordinates`.
  - `TestTransport_HappyPathGetPickupPoints` (~line 944) → decode `PickupPointsResponse`, assert `Data` non-empty.
  - `GetPickupPoints sets X-Target-Endpoint` (~line 551/623) → signature now returns `PickupPointsResponse`; call unchanged, return-type compile fix.

- [ ] **Step 3: Run client gates**

```bash
go build ./... && go vet ./... && go test ./... -count=1
```
Expected: green. Add a new test asserting the grouped envelope: `resp.AvailableFiltersValues.CarrierIds` non-empty; `resp.Data[0].PickupPoints.List[0].LimitsExceeding` decodes (all three bools).

---

## Task 4: Docs + tag

**Files:** `README.md`, `docs/superpowers/specs/2026-05-30-starfish-oms-client-design.md`

- [ ] **Step 1: README example** — update the `GetPickupPoints` snippet to the grouped return + `areaViewPort` confirmed shape (`corners.leftTop/rightBottom.coordinates.{latitude,longitude}`). Remove the "bbox shape UNVERIFIED — keys are a guess" warning (now confirmed live).

- [ ] **Step 2: Spec §4.6 + §5** — rewrite §4.6 to the grouped shape (envelope, group inventory, `limitsExceeding`, `availableFiltersValues`, `shelfLifeDays`, single `date`). In §5 quirks: keep #8 (`dispatchWarehouse` vs `dispatchWarehouseId`) but note PVZ `dispatchWarehouse` is on `inventory`, not the point; add the `limitsExceeding` nested (was top-level in old model) and `cartAvailabillity` typo on PVZ inventory.

- [ ] **Step 3: Tag + (optional) bump**

```bash
git add api client.go client_test.go testdata README.md docs
git commit -m "fix(starfish-oms): pickup-points v2 returns GROUPED response (PickupPointsResponse{data,availableFiltersValues}); live-confirmed shape + areaViewPort"
git tag v0.X.Y   # next client tag
```

> Bump in `platform-new/checkout/go.mod` + `go.sum` is the **T3 plan's** dependency (see T3 plan update) — do it there, after this tag.

---

## Definition of Done

- `GetPickupPoints` returns `PickupPointsResponse` (`{Data []PickupPointGroup, AvailableFiltersValues}`) and **decodes live stage v2** without error.
- Coverage model is honest: `PickupPointGroup.Inventory.CartAvailabillity` (group-level, shared by points); point carries geo/cost/`limitsExceeding`/carriers — no fake `instock`/`productAvailability` on the point.
- `areaViewPort` documented as confirmed (`corners.leftTop/rightBottom.coordinates.{latitude,longitude}`), no "guess" warning.
- `testdata/pickup-points.json` is a live grouped snapshot; `go test ./...` green; README/spec updated; tagged.

## Follow-up (out of scope here)

- Bump this client tag in `checkout/go.mod` (T3 plan prerequisite).
- Checkout adapter: `rawPVZResponse`/`rawPVZGroup`/`rawPVZPoint` (grouped) + `normalizePickupPointsGrouped` (coverage from group inventory → every point in the group; oversize from `limitsExceeding`; `date` → `PromisedDate`). This rewrites T3 plan Task 2.
