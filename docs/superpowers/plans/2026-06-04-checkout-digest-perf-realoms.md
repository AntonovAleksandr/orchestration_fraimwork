# Checkout Delivery-Digest Perf (real-OMS blocker #1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every checkout command/GET fast enough to run with `OMS_DELIVERY_SOURCE=real` without the client timing out, by (1) caching the delivery digest on the session keyed by cart-composition hash, (2) batching the OMS drill-ins concurrently with pickup-stores de-duplicated, and (3) raising the HTTP server write timeout for the cold path.

**Architecture:** The `StateAssembler` (the single owner of the `CheckoutState` projection) currently calls the `DigestReader` on *every* GET and PATCH. With real OMS that reader does a 1+N sequential drill-in (preliminary + courier-intervals + pickup-stores ×2) ≈ 17 s, so commands time out. We attack it on three independent layers: a **per-session digest cache** (persisted in a new `delivery_digest` JSONB column, invalidated by a cart-composition hash + a TTL) so repeated renders within a dwell make **zero** OMS calls; a **concurrent, de-duplicated batch** (`AllOptions` on the `DeliverySource` port; preliminary + all drill-ins fired in parallel, pickup-stores fetched once and split into both store types) so the unavoidable cold compute drops from ~17 s to ~3-5 s; and a **configurable, larger `WriteTimeout`** so the cold compute fits comfortably under the connection deadline. No OpenAPI contract change — this is all internal.

**Tech Stack:** Go 1.26, chi v5, pgx v5 (pgxpool), `gj-go-migrate` CLI migrations, `clients/starfishclient` (OMS), `golang.org/x/sync` (already an indirect dep), Postgres 15.4. Repo: `gitlab.gloria.aaanet.ru/greensight/gj/go/checkout` (local `platform-new/checkout`, go.work). Money: kopecks (`int64`) internally.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `internal/platform/config/config.go` | runtime config | add `HTTP.WriteTimeout`/`ReadTimeout` + root `DigestCacheTTL` |
| `internal/platform/config/config_test.go` | config tests | assert new defaults + env overrides |
| `internal/platform/transport/server.go` | http.Server timeouts | use configurable write/read timeouts |
| `internal/domains/delivery/types.go` | `DeliverySource` port | add `AllOptions` method |
| `internal/adapters/delivery/stub.go` | fixture source | implement `AllOptions` (delegates to `Options`) |
| `internal/adapters/delivery/oms.go` | real OMS source | implement `AllOptions` (concurrent + pickup-stores deduped); factor `filterByType` |
| `internal/adapters/delivery/oms_test.go` | OMS unit/live tests | `filterByType` unit test + extend live test for `AllOptions` |
| `internal/domains/delivery/service.go` | digest orchestration | run `Digest` ‖ `AllOptions` concurrently; enrich from the map |
| `internal/domains/delivery/service_test.go` | service tests | add `AllOptions` to fakes; lock the AllOptions path |
| `internal/domains/session/types.go` | session aggregate + ports | add `DigestCache` type, `Session.DeliveryDigestCache`, `UpdateDigestCache` on `SessionStore` |
| `internal/domains/session/digest.go` | **new** — cart hash | `CartHash([]CartItem) string` |
| `internal/domains/session/digest_test.go` | **new** — hash tests | stability / order-independence / sensitivity |
| `internal/domains/session/service.go` | session service | `CacheDeliveryDigest` method |
| `internal/domains/session/stub.go` | in-memory store | implement `UpdateDigestCache` |
| `internal/domains/session/repository.go` | pgx store | `Get` loads `delivery_digest`; `UpdateDigestCache` upsert |
| `internal/domains/session/repository_test.go` | repo integration | digest-cache round-trip (gated by `CHECKOUT_TEST_DB_DSN`) |
| `migrations/0004_session_digest_cache.{up,down}.sql` | **new** — schema | add/drop `delivery_digest jsonb` |
| `internal/domains/session/assembler.go` | read-model projection | cache-check (skip OMS on hit) + clock/TTL seam |
| `internal/domains/session/assembler_test.go` | assembler tests | hit / miss / cart-change / expiry |
| `internal/app/wire/session.go` | wiring | pass `cfg` → assembler TTL |
| `internal/app/container.go` | wiring | pass `cfg` to `StateAssembler` |
| `internal/app/wire/state_test.go` | (optional) | n/a |
| `checkout/docs/dev/real-delivery-source.md` | dev doc | document the cache + concurrency |
| `checkout/docs/architecture/adr/0001-checkout-state-contract.md` | ADR §Status | mark perf blocker resolved |

---

## Task 1: Configurable server write/read timeouts (Fix 3)

Smallest, fully independent change. The cold digest compute must fit under the connection deadline.

**Files:**
- Modify: `internal/platform/config/config.go`
- Modify: `internal/platform/config/config_test.go`
- Modify: `internal/platform/transport/server.go`

- [ ] **Step 1: Write the failing test** — add to `internal/platform/config/config_test.go`:

```go
func TestLoad_HTTPTimeoutDefaults(t *testing.T) {
	t.Setenv("CHECKOUT_DB_DSN", "postgres://x")
	cfg := Load()
	if cfg.HTTP.WriteTimeout != 30*time.Second {
		t.Fatalf("WriteTimeout default: want 30s, got %s", cfg.HTTP.WriteTimeout)
	}
	if cfg.HTTP.ReadTimeout != 15*time.Second {
		t.Fatalf("ReadTimeout default: want 15s, got %s", cfg.HTTP.ReadTimeout)
	}
	if cfg.DigestCacheTTL != 5*time.Minute {
		t.Fatalf("DigestCacheTTL default: want 5m, got %s", cfg.DigestCacheTTL)
	}
}

func TestLoad_HTTPTimeoutEnvOverride(t *testing.T) {
	t.Setenv("HTTP_WRITE_TIMEOUT_SECONDS", "45")
	t.Setenv("DELIVERY_DIGEST_TTL_SECONDS", "120")
	cfg := Load()
	if cfg.HTTP.WriteTimeout != 45*time.Second {
		t.Fatalf("WriteTimeout override: want 45s, got %s", cfg.HTTP.WriteTimeout)
	}
	if cfg.DigestCacheTTL != 120*time.Second {
		t.Fatalf("DigestCacheTTL override: want 120s, got %s", cfg.DigestCacheTTL)
	}
}
```

(Add `"time"` to the test imports if absent.)

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/platform/config/ -run 'HTTPTimeout' -v`
Expected: FAIL — `cfg.HTTP.WriteTimeout` / `cfg.DigestCacheTTL` undefined (compile error).

- [ ] **Step 3: Implement** — in `internal/platform/config/config.go`, extend `HTTPConfig` and `Config`, and set them in `Load()`:

```go
type HTTPConfig struct {
	Host         string
	Port         string
	WriteTimeout time.Duration // cold digest compute can take seconds; configurable
	ReadTimeout  time.Duration
}
```

Add to the `Config` struct (after `Cart`):

```go
	// DigestCacheTTL bounds how long a cached delivery digest is reused before a
	// recompute, independent of cart-composition change (delivery dates/costs drift).
	DigestCacheTTL time.Duration
```

In `Load()`, replace the `HTTP:` block and add `DigestCacheTTL`:

```go
		HTTP: HTTPConfig{
			Host:         getEnv("HTTP_HOST", ""),
			Port:         getEnv("HTTP_PORT", "8080"),
			WriteTimeout: time.Duration(clampInt(getEnvInt("HTTP_WRITE_TIMEOUT_SECONDS", 30), 5, 120)) * time.Second,
			ReadTimeout:  time.Duration(clampInt(getEnvInt("HTTP_READ_TIMEOUT_SECONDS", 15), 5, 120)) * time.Second,
		},
		UpstreamTimeout: time.Duration(clampInt(getEnvInt("UPSTREAM_TIMEOUT_MS", 800), 50, 10000)) * time.Millisecond,
		DB:              DBConfig{DSN: getEnv("CHECKOUT_DB_DSN", "")},
		DigestCacheTTL:  time.Duration(clampInt(getEnvInt("DELIVERY_DIGEST_TTL_SECONDS", 300), 10, 3600)) * time.Second,
```

(Keep the existing `OMS:` and `Cart:` blocks as-is; only the `HTTP:` block changes and `DigestCacheTTL` is added.)

- [ ] **Step 4: Use the timeouts** — in `internal/platform/transport/server.go`, replace the hard-coded `http.Server` timeouts:

```go
	srv := &stdhttp.Server{
		Addr:              cfg.ListenAddr(),
		Handler:           r,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       cfg.HTTP.ReadTimeout,
		WriteTimeout:      cfg.HTTP.WriteTimeout,
		IdleTimeout:       60 * time.Second,
	}
```

- [ ] **Step 5: Run tests + build**

Run: `go test ./internal/platform/config/ -run 'HTTPTimeout' -v && go build ./...`
Expected: PASS, build clean.

- [ ] **Step 6: Commit**

```bash
git add internal/platform/config/config.go internal/platform/config/config_test.go internal/platform/transport/server.go
git commit -m "feat(config): configurable HTTP write/read timeouts + digest cache TTL (perf #1)"
```

---

## Task 2: `AllOptions` on the `DeliverySource` port + stub + test fakes

Add the batch method to the port and every implementation in one task so the build stays green.

**Files:**
- Modify: `internal/domains/delivery/types.go`
- Modify: `internal/adapters/delivery/stub.go`
- Modify: `internal/domains/delivery/service_test.go` (fakes only — service logic is Task 4)

- [ ] **Step 1: Extend the port** — in `internal/domains/delivery/types.go`, add `AllOptions` to the `DeliverySource` interface:

```go
type DeliverySource interface {
	Digest(ctx context.Context, cart []CartLine) (DeliveryDigest, error)
	Options(ctx context.Context, cart []CartLine, t DeliveryType) ([]Komplektaciya, error)
	// AllOptions resolves drill-in komplektacii for ALL methods in a single batch.
	// Implementations dedupe shared upstream calls (one pickup-stores call serves
	// BOTH store_pickup and store_reserve) and may fan the independent calls out
	// concurrently. Best-effort: a failed sub-resolution is omitted from the map
	// rather than failing the whole batch (preliminary stays authoritative in the
	// service). PVZ is deferred (absent from the map) in this increment.
	AllOptions(ctx context.Context, cart []CartLine) (map[DeliveryType][]Komplektaciya, error)
}
```

- [ ] **Step 2: Run build to verify it fails**

Run: `go build ./...`
Expected: FAIL — `StubDeliverySource` / `OMSDeliverySource` / test fakes no longer satisfy `DeliverySource`.

- [ ] **Step 3: Implement on the stub** — append to `internal/adapters/delivery/stub.go`:

```go
// AllOptions resolves every method from fixtures by delegating to Options. The stub
// is network-free, so there is no call to dedupe — the contract (a map keyed by
// type, PVZ omitted) is what matters for parity with the real source.
func (s StubDeliverySource) AllOptions(ctx context.Context, cart []domain.CartLine) (map[domain.DeliveryType][]domain.Komplektaciya, error) {
	out := make(map[domain.DeliveryType][]domain.Komplektaciya, 3)
	for _, t := range []domain.DeliveryType{domain.DeliveryCourier, domain.DeliveryStorePickup, domain.DeliveryStoreReserve} {
		ks, err := s.Options(ctx, cart, t)
		if err != nil || len(ks) == 0 {
			continue
		}
		out[t] = ks
	}
	return out, nil
}
```

- [ ] **Step 4: Implement on the test fakes** — in `internal/domains/delivery/service_test.go`, add `AllOptions` to both fakes. After `fakeSource`'s `Options`:

```go
func (fakeSource) AllOptions(ctx context.Context, cart []CartLine) (map[DeliveryType][]Komplektaciya, error) {
	out := make(map[DeliveryType][]Komplektaciya, 3)
	for _, t := range []DeliveryType{DeliveryCourier, DeliveryStorePickup, DeliveryStoreReserve} {
		ks, _ := fakeSource{}.Options(ctx, cart, t)
		if len(ks) > 0 {
			out[t] = ks
		}
	}
	return out, nil
}
```

After `optionsErrSource`'s `Options` (it must keep the "no options resolved" semantics so the best-effort enrich test still holds):

```go
func (optionsErrSource) AllOptions(context.Context, []CartLine) (map[DeliveryType][]Komplektaciya, error) {
	return nil, nil // best-effort: nothing resolved → service keeps preliminary numbers
}
```

(`OMSDeliverySource.AllOptions` is added in Task 3 — the OMS adapter is a different package and will keep `go build ./...` red until then; that is expected and resolved in Task 3.)

- [ ] **Step 5: Run the delivery domain build + tests**

Run: `go build ./internal/domains/delivery/... && go test ./internal/domains/delivery/ -count=1`
Expected: PASS (this package no longer references the OMS adapter; it compiles with the fakes).

- [ ] **Step 6: Commit**

```bash
git add internal/domains/delivery/types.go internal/adapters/delivery/stub.go internal/domains/delivery/service_test.go
git commit -m "feat(delivery): AllOptions on DeliverySource port + stub & test fakes (perf #1)"
```

---

## Task 3: OMS adapter `AllOptions` — concurrent + pickup-stores deduped

The real win for the cold path: fire courier-intervals and pickup-stores **in parallel**, fetch pickup-stores **once**, and split it into both store types.

**Files:**
- Modify: `internal/adapters/delivery/oms.go`
- Modify: `internal/adapters/delivery/oms_test.go`

- [ ] **Step 1: Write the failing unit test** — add the pure helper test to `internal/adapters/delivery/oms_test.go` (network-free):

```go
// TestFilterByType proves the pickup-stores split: one normalized list yields the
// store_pickup subset and the store_reserve subset, with no cross-contamination.
func TestFilterByType(t *testing.T) {
	ks := []domain.Komplektaciya{
		{DeliveryType: domain.DeliveryStorePickup, IntervalID: "a"},
		{DeliveryType: domain.DeliveryStoreReserve, IntervalID: "b"},
		{DeliveryType: domain.DeliveryStorePickup, IntervalID: "c"},
	}
	pickup := filterByType(ks, domain.DeliveryStorePickup)
	reserve := filterByType(ks, domain.DeliveryStoreReserve)
	if len(pickup) != 2 {
		t.Fatalf("store_pickup: want 2, got %d", len(pickup))
	}
	if len(reserve) != 1 {
		t.Fatalf("store_reserve: want 1, got %d", len(reserve))
	}
	for _, k := range pickup {
		if k.DeliveryType != domain.DeliveryStorePickup {
			t.Fatalf("pickup contains %s", k.DeliveryType)
		}
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/adapters/delivery/ -run TestFilterByType -v`
Expected: FAIL — `filterByType` undefined.

- [ ] **Step 3: Implement** — in `internal/adapters/delivery/oms.go`, add imports `"sync"` and `gjlogger "gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger"`, add the `filterByType` helper, and implement `AllOptions`. Also refactor the existing store branch of `Options` to reuse `filterByType` (DRY).

Add the helper (near `ptrBool`):

```go
// filterByType returns the komplektacii whose DeliveryType equals t.
func filterByType(ks []domain.Komplektaciya, t domain.DeliveryType) []domain.Komplektaciya {
	out := make([]domain.Komplektaciya, 0, len(ks))
	for _, k := range ks {
		if k.DeliveryType == t {
			out = append(out, k)
		}
	}
	return out
}
```

Replace the inline filter in `Options`' `DeliveryStorePickup, DeliveryStoreReserve` branch:

```go
	case domain.DeliveryStorePickup, domain.DeliveryStoreReserve:
		resp, err := s.client.GetPickupStores(ctx, s.pickupStoresReq(cart))
		if err != nil {
			return nil, omsErr("pickup-stores", err)
		}
		var raw []rawStore
		if err := reencode(resp, &raw); err != nil {
			return nil, fmt.Errorf("oms pickup-stores decode: %w", err)
		}
		return filterByType(normalizePickupStores(raw), t), nil
```

Factor the pickup-stores request (used by both `Options` and `AllOptions`):

```go
// pickupStoresReq builds the pickup-stores request for the cart (shared by Options
// and AllOptions). One response serves both store_pickup (C&C) and store_reserve (C&R).
func (s *OMSDeliverySource) pickupStoresReq(cart []domain.CartLine) starfishoms.PickupRequest {
	return starfishoms.PickupRequest{
		AddressTo:             starfishoms.AddressToCity{City: s.cityRef()},
		Cart:                  s.cartRef(cart),
		InStockOnly:           ptrBool(false),
		FilterByLogisticGroup: ptrBool(true),
		BasketFullness:        ptrBool(false),
		ShortestDistance:      ptrBool(false),
	}
}
```

Now add `AllOptions`:

```go
// AllOptions resolves every method's drill-in concurrently, with ONE pickup-stores
// call serving both store types. Best-effort: a failed sub-call is logged and that
// method is simply absent from the map (the service keeps preliminary numbers).
// PVZ is deferred (no call, absent from the map).
func (s *OMSDeliverySource) AllOptions(ctx context.Context, cart []domain.CartLine) (map[domain.DeliveryType][]domain.Komplektaciya, error) {
	var (
		mu  sync.Mutex
		out = make(map[domain.DeliveryType][]domain.Komplektaciya, 3)
		wg  sync.WaitGroup
	)
	put := func(t domain.DeliveryType, ks []domain.Komplektaciya) {
		if len(ks) == 0 {
			return
		}
		mu.Lock()
		out[t] = ks
		mu.Unlock()
	}

	// Courier: delivery-intervals.
	wg.Add(1)
	go func() {
		defer wg.Done()
		resp, err := s.client.GetCourierDeliveryIntervals(ctx, starfishoms.CourierIntervalsRequest{
			AddressTo: starfishoms.CourierIntervalsAddressTo{City: s.cityRef()},
			Cart:      s.cartRef(cart),
		})
		if err != nil {
			gjlogger.Logger().Warn().Err(omsErr("delivery-intervals", err)).Msg("AllOptions: courier drill-in failed (best-effort)")
			return
		}
		var raw rawCourier
		if err := reencode(resp, &raw); err != nil {
			gjlogger.Logger().Warn().Err(err).Msg("AllOptions: courier decode failed (best-effort)")
			return
		}
		put(domain.DeliveryCourier, normalizeCourier(raw))
	}()

	// Stores: ONE pickup-stores call → split into store_pickup + store_reserve.
	wg.Add(1)
	go func() {
		defer wg.Done()
		resp, err := s.client.GetPickupStores(ctx, s.pickupStoresReq(cart))
		if err != nil {
			gjlogger.Logger().Warn().Err(omsErr("pickup-stores", err)).Msg("AllOptions: store drill-in failed (best-effort)")
			return
		}
		var raw []rawStore
		if err := reencode(resp, &raw); err != nil {
			gjlogger.Logger().Warn().Err(err).Msg("AllOptions: pickup-stores decode failed (best-effort)")
			return
		}
		ks := normalizePickupStores(raw)
		put(domain.DeliveryStorePickup, filterByType(ks, domain.DeliveryStorePickup))
		put(domain.DeliveryStoreReserve, filterByType(ks, domain.DeliveryStoreReserve))
	}()

	// PVZ deferred (no pickup-points call this increment).
	wg.Wait()
	return out, nil
}
```

- [ ] **Step 4: Update the `Digest` method's `pickup-stores`-via-`Options` consistency** — no change needed; `Options` still works for single-method callers (`ListKomplektacii`, `PickupClusters`, `SetDeliveryMethod`). Verify `Options` still compiles after the refactor.

Run: `go build ./internal/adapters/delivery/...`
Expected: build clean.

- [ ] **Step 5: Run the unit test + verify the OMS source satisfies the port**

Run: `go test ./internal/adapters/delivery/ -run TestFilterByType -count=1 && go vet ./internal/adapters/delivery/`
Expected: PASS, vet clean. (`var _ domain.DeliverySource = (*OMSDeliverySource)(nil)` already asserts the contract at compile time.)

- [ ] **Step 6: Extend the guarded live test** — append to `TestOMSDeliverySource_liveIntegration` in `oms_test.go`, after the existing `pvz` block:

```go
	all, err := src.AllOptions(ctx, cart)
	if err != nil {
		t.Fatalf("AllOptions: %v", err)
	}
	if len(all[domain.DeliveryCourier]) == 0 {
		t.Fatal("AllOptions: expected courier komplektacii from live OMS")
	}
	if _, ok := all[domain.DeliveryPVZ]; ok {
		t.Fatal("AllOptions: pvz must be deferred (absent from the map)")
	}
	// At least one store type should be present (a real Moscow cart has stores).
	if len(all[domain.DeliveryStorePickup]) == 0 && len(all[domain.DeliveryStoreReserve]) == 0 {
		t.Fatal("AllOptions: expected at least one store komplektaciya from live OMS")
	}
```

(This only runs with `OMS_INTEGRATION=1` + port-forward — verified live in Task 9, not in CI.)

- [ ] **Step 7: Commit**

```bash
git add internal/adapters/delivery/oms.go internal/adapters/delivery/oms_test.go
git commit -m "feat(delivery/oms): concurrent AllOptions, pickup-stores deduped across store types (perf #1)"
```

---

## Task 4: Service digest orchestration — `Digest` ‖ `AllOptions`

Run the preliminary and all drill-ins **concurrently** and enrich the digest from the batch map. This is where the 1+N sequential loop dies.

**Files:**
- Modify: `internal/domains/delivery/service.go`
- Modify: `internal/domains/delivery/service_test.go`

- [ ] **Step 1: Write the failing test** — add to `internal/domains/delivery/service_test.go` a fake that returns DIFFERENT data from `AllOptions` than from `Options`, proving the digest path uses `AllOptions`:

```go
// allOptionsOnlySource serves preliminary with one available courier method, returns
// nil from per-method Options (so the OLD 1+N loop would enrich nothing), but returns
// a real komplektaciya from AllOptions. If the digest reflects the AllOptions data,
// GetDeliveryDigest is using the batch path.
type allOptionsOnlySource struct{}

func (allOptionsOnlySource) Digest(context.Context, []CartLine) (DeliveryDigest, error) {
	return DeliveryDigest{Methods: []MethodSummary{
		{DeliveryType: DeliveryCourier, Available: true, Coverage: 0, CartSize: 2},
	}}, nil
}

func (allOptionsOnlySource) Options(context.Context, []CartLine, DeliveryType) ([]Komplektaciya, error) {
	return nil, nil // old loop would find nothing
}

func (allOptionsOnlySource) AllOptions(context.Context, []CartLine) (map[DeliveryType][]Komplektaciya, error) {
	return map[DeliveryType][]Komplektaciya{
		DeliveryCourier: {{
			DeliveryType: DeliveryCourier, Coverage: 2,
			DeliveryCostKopecks: 29900, PromisedDate: "2026-06-05",
			Items: []ItemAvail{{ProductID: "x", Available: true, AvailableQuantity: 1}},
		}},
	}, nil
}

func TestGetDeliveryDigest_usesAllOptions(t *testing.T) {
	svc := NewService(allOptionsOnlySource{}, &fakeGateway{})
	d, err := svc.GetDeliveryDigest(context.Background(), "chk-1")
	if err != nil {
		t.Fatalf("digest: %v", err)
	}
	if len(d.Methods) != 1 {
		t.Fatalf("want 1 method, got %d", len(d.Methods))
	}
	m := d.Methods[0]
	if m.Coverage != 2 || m.MinCostKopecks != 29900 || m.EarliestPromisedDate != "2026-06-05" {
		t.Fatalf("digest not enriched from AllOptions: cov=%d cost=%d date=%q", m.Coverage, m.MinCostKopecks, m.EarliestPromisedDate)
	}
}
```

(Check `fakeGateway{}` returns a non-empty `CheckoutRef` with a cart; if its zero value yields an empty cart, `pickBest` still works because `coveredValueKopecks` tolerates a missing price map — coverage is the primary key. If the existing `fakeGateway` requires a seeded cart, mirror how `TestGetDeliveryDigest_enrichesEarliestPromisedDate` constructs it.)

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/domains/delivery/ -run TestGetDeliveryDigest_usesAllOptions -v`
Expected: FAIL — current loop calls per-method `Options` (returns nil) → coverage stays 0.

- [ ] **Step 3: Implement** — in `internal/domains/delivery/service.go`, add `"sync"` to imports and rewrite `GetDeliveryDigest`:

```go
// GetDeliveryDigest returns the per-method entry digest for the session's cart.
//
// OMS preliminary carries only MinDays/raw-cost (whole-cart-thresholded — the legacy
// "free on unselected" bug). The accurate per-method numbers live at the komplektaciya
// level: when item prices are sent, OMS applies the free-delivery threshold against
// each komplektaciya's COVERED subset (OPSOMN001-221). So we drill into each method,
// pick the same best komplektaciya that SetDeliveryMethod would auto-select, and
// surface ITS coverage / cost / date — so the card's numbers are mutually consistent.
//
// Perf: preliminary and ALL drill-ins run CONCURRENTLY (AllOptions batches them and
// dedupes pickup-stores across the two store types). The preliminary result is
// authoritative (its error fails the digest); AllOptions is best-effort — a method
// absent from the map keeps its preliminary numbers.
func (s *Service) GetDeliveryDigest(ctx context.Context, checkoutID string) (DeliveryDigest, error) {
	ref, err := s.gw.Lookup(ctx, checkoutID)
	if err != nil {
		return DeliveryDigest{}, err
	}

	var (
		d    DeliveryDigest
		dErr error
		all  map[DeliveryType][]Komplektaciya
		wg   sync.WaitGroup
	)
	wg.Add(2)
	go func() { defer wg.Done(); d, dErr = s.src.Digest(ctx, ref.Cart) }()
	go func() { defer wg.Done(); all, _ = s.src.AllOptions(ctx, ref.Cart) }() // best-effort
	wg.Wait()
	if dErr != nil {
		return DeliveryDigest{}, dErr // preliminary is authoritative
	}

	prices := priceByProduct(ref.Cart)
	for i := range d.Methods {
		m := &d.Methods[i]
		if !m.Available {
			continue
		}
		best := pickBest(all[m.DeliveryType], prices)
		if best == nil {
			continue // best-effort: keep preliminary numbers
		}
		// Card reflects the default (best) komplektaciya — cost is OMS threshold-applied
		// per covered subset (when prices were sent), NOT preliminary's whole-cart cost.
		m.Coverage = best.Coverage
		m.MinCostKopecks = best.DeliveryCostKopecks
		m.EarliestPromisedDate = best.PromisedDate
	}
	return d, nil
}
```

(Remove the old per-method `s.src.Options(...)` loop and the `TODO(perf)` comment block.)

- [ ] **Step 4: Run the full delivery test suite**

Run: `go test ./internal/domains/delivery/ -count=1 -race`
Expected: PASS — including the existing `TestGetDeliveryDigest_*`, the best-effort-on-error test (now via `AllOptions` returning empty), and the new `usesAllOptions`. `-race` proves the two goroutines write disjoint vars (`d`, `all`).

- [ ] **Step 5: Commit**

```bash
git add internal/domains/delivery/service.go internal/domains/delivery/service_test.go
git commit -m "perf(delivery): run preliminary + AllOptions concurrently, drop 1+N sequential loop (perf #1)"
```

---

## Task 5: Session domain — `DigestCache`, `CartHash`, store port + service method

The cache primitives. Pure domain — no DB yet (Task 6 adds persistence).

**Files:**
- Modify: `internal/domains/session/types.go`
- Create: `internal/domains/session/digest.go`
- Create: `internal/domains/session/digest_test.go`
- Modify: `internal/domains/session/service.go`
- Modify: `internal/domains/session/stub.go`

- [ ] **Step 1: Write the failing test** — create `internal/domains/session/digest_test.go`:

```go
package session

import (
	"context"
	"testing"
)

func TestCartHash_OrderIndependentAndStable(t *testing.T) {
	a := []CartItem{
		{VendorCodeSKU: "GDR1F0006", Quantity: 1, PriceKopecks: 59900},
		{VendorCodeSKU: "GRA42F0001", Quantity: 2, PriceKopecks: 10000},
	}
	b := []CartItem{ // same composition, reversed order
		{VendorCodeSKU: "GRA42F0001", Quantity: 2, PriceKopecks: 10000},
		{VendorCodeSKU: "GDR1F0006", Quantity: 1, PriceKopecks: 59900},
	}
	if CartHash(a) != CartHash(b) {
		t.Fatal("CartHash must be order-independent")
	}
	if CartHash(a) == "" {
		t.Fatal("CartHash must be non-empty for a non-empty cart")
	}
}

func TestCartHash_SensitiveToQtyPriceSku(t *testing.T) {
	base := []CartItem{{VendorCodeSKU: "S1", Quantity: 1, PriceKopecks: 100}}
	h := CartHash(base)
	if h == CartHash([]CartItem{{VendorCodeSKU: "S1", Quantity: 2, PriceKopecks: 100}}) {
		t.Fatal("hash must change with quantity")
	}
	if h == CartHash([]CartItem{{VendorCodeSKU: "S1", Quantity: 1, PriceKopecks: 200}}) {
		t.Fatal("hash must change with price")
	}
	if h == CartHash([]CartItem{{VendorCodeSKU: "S2", Quantity: 1, PriceKopecks: 100}}) {
		t.Fatal("hash must change with sku")
	}
}

func TestCacheDeliveryDigest_RoundTrip(t *testing.T) {
	store := NewInMemoryStore()
	svc := NewService(store)
	created, err := svc.CreateSession(context.Background(), CreateSessionInput{CustomerID: "1", BasketID: "b"})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	cache := DigestCache{CartHash: "abc", Methods: []DeliveryMethodView{{Type: "courier", Available: true}}}
	if err := svc.CacheDeliveryDigest(context.Background(), created.CheckoutID, cache); err != nil {
		t.Fatalf("cache: %v", err)
	}
	got, err := svc.GetSession(context.Background(), created.CheckoutID)
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if got.DeliveryDigestCache == nil || got.DeliveryDigestCache.CartHash != "abc" {
		t.Fatalf("digest cache not persisted: %+v", got.DeliveryDigestCache)
	}
	if len(got.DeliveryDigestCache.Methods) != 1 {
		t.Fatalf("methods not persisted: %+v", got.DeliveryDigestCache.Methods)
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/domains/session/ -run 'CartHash|CacheDeliveryDigest' -v`
Expected: FAIL — `CartHash`, `DigestCache`, `CacheDeliveryDigest`, `UpdateDigestCache` undefined.

- [ ] **Step 3: Add the `DigestCache` type + Session field + port method** — in `internal/domains/session/types.go`:

Add `"time"` to imports. Add the type (near `DeliveryMethodView`):

```go
// DigestCache is a cached delivery-digest projection, keyed by the live-cart hash.
// It is a CACHE, not authoritative state: invalidated when the cart COMPOSITION
// changes (CartHash) or when older than the assembler's TTL. Persisted on the session
// row (delivery_digest JSONB) so it is shared across replicas and survives restarts.
// Delivery cost/dates are re-validated at commit (store intent, not truth) — this
// only serves the display digest fast.
type DigestCache struct {
	CartHash   string               `json:"cart_hash"`
	ComputedAt time.Time            `json:"computed_at"`
	Methods    []DeliveryMethodView `json:"methods"`
}
```

Add to the `Session` struct (after `PaymentMethod`):

```go
	DeliveryDigestCache *DigestCache `json:"-"` // cached digest projection (see DigestCache)
```

Add to the `SessionStore` interface (after `UpdateStatus`):

```go
	// UpdateDigestCache stores the delivery digest cache (delivery_digest JSONB) and
	// bumps updated_at. Returns ErrNotFound when the session is absent.
	UpdateDigestCache(ctx context.Context, checkoutID string, cache DigestCache) error
```

- [ ] **Step 4: Add `CartHash`** — create `internal/domains/session/digest.go`:

```go
package session

import (
	"crypto/sha256"
	"encoding/hex"
	"sort"
	"strconv"
	"strings"
)

// CartHash returns a stable, order-independent hash of the cart COMPOSITION that
// determines the delivery digest: per line (vendorCodeSku, quantity, unit price
// kopecks). Two carts with the same lines in any order hash equal; any change in
// sku/qty/price changes the hash. Used to invalidate the per-session digest cache.
func CartHash(cart []CartItem) string {
	parts := make([]string, 0, len(cart))
	for _, it := range cart {
		parts = append(parts, it.VendorCodeSKU+":"+strconv.Itoa(it.Quantity)+":"+strconv.FormatInt(it.PriceKopecks, 10))
	}
	sort.Strings(parts)
	sum := sha256.Sum256([]byte(strings.Join(parts, "|")))
	return hex.EncodeToString(sum[:])
}
```

- [ ] **Step 5: Add `CacheDeliveryDigest`** — in `internal/domains/session/service.go`:

```go
// CacheDeliveryDigest stores the delivery digest cache on the session. The caller
// (StateAssembler) treats a failure as non-fatal — the render proceeds either way.
func (s *Service) CacheDeliveryDigest(ctx context.Context, checkoutID string, cache DigestCache) error {
	return s.store.UpdateDigestCache(ctx, checkoutID, cache)
}
```

- [ ] **Step 6: Implement `UpdateDigestCache` on the in-memory store** — in `internal/domains/session/stub.go`:

```go
func (s *InMemoryStore) UpdateDigestCache(_ context.Context, checkoutID string, cache DigestCache) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	cur, ok := s.data[checkoutID]
	if !ok {
		return ErrNotFound
	}
	c := cache
	cur.DeliveryDigestCache = &c
	s.data[checkoutID] = cur
	return nil
}
```

- [ ] **Step 7: Run the tests + build**

Run: `go test ./internal/domains/session/ -run 'CartHash|CacheDeliveryDigest' -count=1 && go build ./...`
Expected: tests PASS. `go build ./...` will FAIL on `*Repository` (does not yet implement `UpdateDigestCache`) — that is expected and fixed in Task 6.

- [ ] **Step 8: Commit**

```bash
git add internal/domains/session/types.go internal/domains/session/digest.go internal/domains/session/digest_test.go internal/domains/session/service.go internal/domains/session/stub.go
git commit -m "feat(session): DigestCache type, CartHash, CacheDeliveryDigest + in-memory store (perf #1)"
```

---

## Task 6: Migration 0004 + pgx Repository persistence

Persist the cache so it survives restarts and is shared across replicas.

**Files:**
- Create: `migrations/0004_session_digest_cache.up.sql`
- Create: `migrations/0004_session_digest_cache.down.sql`
- Modify: `internal/domains/session/repository.go`
- Modify: `internal/domains/session/repository_test.go`

- [ ] **Step 1: Create the migration** — `migrations/0004_session_digest_cache.up.sql`:

```sql
ALTER TABLE checkout_sessions ADD COLUMN IF NOT EXISTS delivery_digest jsonb NULL;
```

`migrations/0004_session_digest_cache.down.sql`:

```sql
ALTER TABLE checkout_sessions DROP COLUMN IF EXISTS delivery_digest;
```

- [ ] **Step 2: Write the failing integration test** — add to `internal/domains/session/repository_test.go` (mirror the existing `CHECKOUT_TEST_DB_DSN` gating pattern):

```go
func TestRepository_DigestCacheRoundTrip(t *testing.T) {
	dsn := os.Getenv("CHECKOUT_TEST_DB_DSN")
	if dsn == "" {
		t.Skip("set CHECKOUT_TEST_DB_DSN (migrated) to run")
	}
	ctx := context.Background()
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatalf("pool: %v", err)
	}
	defer pool.Close()
	repo := NewRepository(pool)

	sess := Session{
		CheckoutID: uuid.NewString(), ClientOrderID: "b", CustomerID: "1", BasketID: "b", Status: StatusDraft,
	}
	if err := repo.Create(ctx, sess); err != nil {
		t.Fatalf("create: %v", err)
	}
	cache := DigestCache{CartHash: "deadbeef", Methods: []DeliveryMethodView{{Type: "courier", Available: true, Coverage: 3}}}
	if err := repo.UpdateDigestCache(ctx, sess.CheckoutID, cache); err != nil {
		t.Fatalf("update digest cache: %v", err)
	}
	got, err := repo.Get(ctx, sess.CheckoutID)
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if got.DeliveryDigestCache == nil || got.DeliveryDigestCache.CartHash != "deadbeef" {
		t.Fatalf("digest cache not loaded: %+v", got.DeliveryDigestCache)
	}
	if len(got.DeliveryDigestCache.Methods) != 1 || got.DeliveryDigestCache.Methods[0].Coverage != 3 {
		t.Fatalf("methods not round-tripped: %+v", got.DeliveryDigestCache.Methods)
	}
	if err := repo.UpdateDigestCache(ctx, uuid.NewString(), cache); err != ErrNotFound {
		t.Fatalf("absent session: want ErrNotFound, got %v", err)
	}
}
```

(Ensure `uuid` is imported in the test file; the existing tests likely already import it. If not, add `"github.com/google/uuid"`.)

- [ ] **Step 3: Run test to verify it fails** (with a migrated dev DB up):

```bash
CHECKOUT_TEST_DB_DSN='postgres://checkout:checkout@127.0.0.1:5544/checkout?sslmode=disable' \
  go test ./internal/domains/session/ -run TestRepository_DigestCacheRoundTrip -v
```
Expected: FAIL — `UpdateDigestCache` undefined and/or `delivery_digest` column missing (run `make migrate-up` first to apply 0004, see Step 5).

- [ ] **Step 4: Implement on the Repository** — in `internal/domains/session/repository.go`:

In `Get`, add `delivery_digest` to the SELECT and scan/unmarshal it:

```go
	const q = `
		SELECT checkout_id, client_order_id, customer_id, basket_id, status, totals_checksum, selection, cart_snapshot, details, delivery_digest
		FROM checkout_sessions WHERE checkout_id = $1`
	var s Session
	var status string
	var selJSON, cartJSON, detJSON, digJSON []byte
	err := r.db.QueryRow(ctx, q, checkoutID).Scan(
		&s.CheckoutID, &s.ClientOrderID, &s.CustomerID, &s.BasketID, &status, &s.TotalsChecksum, &selJSON, &cartJSON, &detJSON, &digJSON)
```

After the `details` unmarshal block, add:

```go
	if len(digJSON) > 0 {
		var dc DigestCache
		if err := json.Unmarshal(digJSON, &dc); err != nil {
			return Session{}, fmt.Errorf("checkout: unmarshal digest cache: %w", err)
		}
		s.DeliveryDigestCache = &dc
	}
```

Add the new method:

```go
// UpdateDigestCache stores the delivery digest cache (delivery_digest JSONB) and
// bumps updated_at. Returns ErrNotFound when the session is absent.
func (r *Repository) UpdateDigestCache(ctx context.Context, checkoutID string, cache DigestCache) error {
	b, err := json.Marshal(cache)
	if err != nil {
		return fmt.Errorf("checkout: marshal digest cache: %w", err)
	}
	ct, err := r.db.Exec(ctx,
		`UPDATE checkout_sessions SET delivery_digest=$2, updated_at=now() WHERE checkout_id=$1`,
		checkoutID, b)
	if err != nil {
		return fmt.Errorf("checkout: update digest cache: %w", err)
	}
	if ct.RowsAffected() == 0 {
		return ErrNotFound
	}
	return nil
}
```

- [ ] **Step 5: Apply the migration + run the integration test**

```bash
make migrate-up   # applies 0004 (delivery_digest column)
make migrate-version   # expect version=4 dirty=false
CHECKOUT_TEST_DB_DSN='postgres://checkout:checkout@127.0.0.1:5544/checkout?sslmode=disable' \
  go test ./internal/domains/session/ -run TestRepository_DigestCacheRoundTrip -count=1 -v
go build ./...
```
Expected: migration applies (version 4), integration test PASS, `go build ./...` clean.

- [ ] **Step 6: Commit**

```bash
git add migrations/0004_session_digest_cache.up.sql migrations/0004_session_digest_cache.down.sql internal/domains/session/repository.go internal/domains/session/repository_test.go
git commit -m "feat(session): persist delivery_digest cache (migration 0004 + pgx repo) (perf #1)"
```

---

## Task 7: Assembler — skip OMS on cache hit (Fix #1 wired)

The payoff: the assembler consults the cache before calling the digest reader, so repeated renders within a dwell make **zero** OMS calls.

**Files:**
- Modify: `internal/domains/session/assembler.go`
- Modify: `internal/domains/session/assembler_test.go`

- [ ] **Step 1: Write the failing test** — add to `internal/domains/session/assembler_test.go`:

```go
// countingDigestReader records how many times the digest was (re)computed.
type countingDigestReader struct {
	n       int
	methods []DeliveryMethodView
}

func (c *countingDigestReader) ReadDeliveryDigest(_ context.Context, _ string) ([]DeliveryMethodView, error) {
	c.n++
	return c.methods, nil
}

// fixedCartReader returns a controllable cart (drives the cache key).
type fixedCartReader struct{ items []CartItem }

func (f *fixedCartReader) ResolveCart(_ context.Context, _ string) ([]CartItem, error) {
	return f.items, nil
}

func TestAssembler_DigestCache_HitMissCartChangeExpiry(t *testing.T) {
	store := NewInMemoryStore()
	svc := NewService(store)
	created, err := svc.CreateSession(context.Background(), CreateSessionInput{CustomerID: "1", BasketID: "b"})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	cart := &fixedCartReader{items: []CartItem{{VendorCodeSKU: "S1", Quantity: 1, PriceKopecks: 100}}}
	dr := &countingDigestReader{methods: []DeliveryMethodView{{Type: "courier", Available: true}}}

	base := time.Unix(1_700_000_000, 0)
	clock := base
	asm := NewStateAssembler(svc).
		WithCartReader(cart).
		WithDigestReader(dr).
		WithDigestTTL(5 * time.Minute).
		withClock(func() time.Time { return clock })

	// 1) cold → miss → reader called once, cache populated.
	if _, err := asm.Assemble(context.Background(), created.CheckoutID); err != nil {
		t.Fatalf("assemble 1: %v", err)
	}
	if dr.n != 1 {
		t.Fatalf("after cold: want 1 compute, got %d", dr.n)
	}

	// 2) same cart, within TTL → hit → reader NOT called again.
	if _, err := asm.Assemble(context.Background(), created.CheckoutID); err != nil {
		t.Fatalf("assemble 2: %v", err)
	}
	if dr.n != 1 {
		t.Fatalf("after hit: want 1 compute, got %d", dr.n)
	}

	// 3) cart composition changes → miss → recompute.
	cart.items = []CartItem{{VendorCodeSKU: "S1", Quantity: 2, PriceKopecks: 100}}
	if _, err := asm.Assemble(context.Background(), created.CheckoutID); err != nil {
		t.Fatalf("assemble 3: %v", err)
	}
	if dr.n != 2 {
		t.Fatalf("after cart change: want 2 computes, got %d", dr.n)
	}

	// 4) same cart but TTL elapsed → miss → recompute.
	clock = base.Add(10 * time.Minute)
	if _, err := asm.Assemble(context.Background(), created.CheckoutID); err != nil {
		t.Fatalf("assemble 4: %v", err)
	}
	if dr.n != 3 {
		t.Fatalf("after expiry: want 3 computes, got %d", dr.n)
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/domains/session/ -run TestAssembler_DigestCache -v`
Expected: FAIL — `WithDigestTTL` / `withClock` undefined; no caching, so `dr.n` keeps incrementing.

- [ ] **Step 3: Implement** — in `internal/domains/session/assembler.go`:

Add `"time"` to imports. Extend the struct + constructor + builders:

```go
type StateAssembler struct {
	service   *Service
	cart      CartReader
	digest    DigestReader
	totals    TotalsReader
	now       func() time.Time
	digestTTL time.Duration
}

func NewStateAssembler(service *Service) *StateAssembler {
	if service == nil {
		panic("session: NewStateAssembler requires a non-nil Service")
	}
	return &StateAssembler{service: service, now: time.Now, digestTTL: 5 * time.Minute}
}
```

Add the builders (near the other `With*`):

```go
// WithDigestTTL sets the max age of a cached delivery digest before recompute.
func (a *StateAssembler) WithDigestTTL(d time.Duration) *StateAssembler {
	if d > 0 {
		a.digestTTL = d
	}
	return a
}

// withClock overrides the clock (test seam).
func (a *StateAssembler) withClock(now func() time.Time) *StateAssembler {
	if now != nil {
		a.now = now
	}
	return a
}
```

Replace the digest section inside `Assemble` (the `if a.digest != nil { ... }` block):

```go
	var methods []DeliveryMethodView
	if a.digest != nil {
		hash := CartHash(cart)
		if c := sess.DeliveryDigestCache; c != nil && c.CartHash == hash && a.now().Sub(c.ComputedAt) < a.digestTTL {
			methods = c.Methods // cache hit: NO OMS call this request
		} else if ms, dErr := a.digest.ReadDeliveryDigest(ctx, sess.CheckoutID); dErr == nil {
			methods = ms
			// Persist best-effort; a cache-write failure must not fail the render.
			_ = a.service.CacheDeliveryDigest(ctx, sess.CheckoutID, DigestCache{
				CartHash:   hash,
				ComputedAt: a.now(),
				Methods:    ms,
			})
		}
	}
```

(`cart` is the already-resolved live cart from the section just above; the cache key is computed over the same cart the digest is computed from, since both come from the shared resolver keyed by customer id.)

- [ ] **Step 4: Run the assembler tests (incl. existing best-effort + core)**

Run: `go test ./internal/domains/session/ -run 'Assembler|StateAssembler' -count=1 -v`
Expected: PASS — new cache test + existing `TestStateAssembler_AssembleCore` + `TestStateAssembler_BestEffortReadersSwallowErrors`.

- [ ] **Step 5: Commit**

```bash
git add internal/domains/session/assembler.go internal/domains/session/assembler_test.go
git commit -m "perf(session): assembler skips digest reader on cache hit (cart-hash + TTL) (perf #1)"
```

---

## Task 8: Wire the TTL from config into the assembler

**Files:**
- Modify: `internal/app/wire/session.go`
- Modify: `internal/app/container.go`

- [ ] **Step 1: Thread `cfg` into the `StateAssembler` builder** — in `internal/app/wire/session.go`, add the config import and a `cfg` parameter:

```go
import (
	// ...existing imports...
	"gitlab.gloria.aaanet.ru/greensight/gj/go/checkout/internal/platform/config"
)

// StateAssembler builds the CheckoutState read-model assembler, wiring the live cart
// resolver (when configured), the delivery digest reader, the v1 totals re-quoter,
// and the per-session digest-cache TTL (config).
func StateAssembler(svc *session.Service, resolver *cartadapter.Resolver, deliverySvc *delivery.Service, cfg config.Config) *session.StateAssembler {
	a := session.NewStateAssembler(svc)
	if resolver != nil {
		a.WithCartReader(sessionCartReader{r: resolver})
	}
	if deliverySvc != nil {
		a.WithDigestReader(sessionDigestReader{svc: deliverySvc})
	}
	a.WithTotalsReader(sessionTotalsReader{quoter: pricing.StubQuoter{}})
	a.WithDigestTTL(cfg.DigestCacheTTL)
	return a
}
```

- [ ] **Step 2: Pass `cfg` at the call site** — in `internal/app/container.go`, update the `StateAssembler` call:

```go
	asm := wire.StateAssembler(sessionSvc, cartRes, deliverySvc, cfg)
```

- [ ] **Step 3: Build + vet + full unit suite**

Run: `go build ./... && go vet ./... && go test ./... -count=1`
Expected: all PASS (unit; stub source default, no network; DB integration tests skip without `CHECKOUT_TEST_DB_DSN`).

- [ ] **Step 4: Confirm no contract drift** (no OpenAPI change in this plan):

Run: `make generate && git diff --exit-code -- '*/apiv1/openapi.gen.go' '*.yaml'`
Expected: no diff. Then `make lint` (redocly) → clean.

- [ ] **Step 5: Commit**

```bash
git add internal/app/wire/session.go internal/app/container.go
git commit -m "feat(app): wire DigestCacheTTL into the state assembler (perf #1)"
```

---

## Task 9: Verification — full gate + live on stage with real OMS

Prove the goal: real-OMS commands without client timeout, on customer 4455421.

**Files:**
- Modify: `checkout/docs/dev/real-delivery-source.md`
- Modify: `checkout/docs/architecture/adr/0001-checkout-state-contract.md`

- [ ] **Step 1: Static gate** (network-free):

```bash
go build ./... && go vet ./... && go test ./... -count=1 -race
make generate && git diff --exit-code   # no drift
make lint                               # redocly clean
```
Expected: all green; `-race` clean (proves the concurrent `Digest ‖ AllOptions` and `AllOptions` goroutines are data-race-free).

- [ ] **Step 2: Apply migration to the live dev DB + bring up port-forwards**

```bash
make migrate-up && make migrate-version   # version=4
make port-forward                          # OMS v1/v2 + baskets + catalog-cache (stage)
```

- [ ] **Step 3: Run checkout against stage with real OMS.** Ensure `.env` has `OMS_DELIVERY_SOURCE=real`, the OMS base URLs + token, `BASKETS_BASE_URL`, `CATALOG_CACHE_BASE_URL`, `CHECKOUT_DB_DSN`, `HTTP_PORT=8090`. Then:

```bash
make run    # boots on :8090 with real OMS
```

- [ ] **Step 4: Create a session for customer 4455421 + time the cold and warm renders.** (`basket_id` is stored as `client_order_id`; cart is resolved server-side by `customer_id` from baskets — use the customer's current basket number.)

```bash
# Create (no inline cart → server-side resolve from baskets+catalog)
CID=$(curl -s -XPOST localhost:8090/api/v1/checkout \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"4455421","basket_id":"4455421"}' | tee /dev/stderr | python3 -c 'import sys,json;print(json.load(sys.stdin)["checkout_id"])')

# Cold GET (cache MISS → one concurrent OMS batch). Expect a few seconds, NOT ~17s, HTTP 200.
curl -s -o /dev/null -w 'cold GET: %{http_code} in %{time_total}s\n' localhost:8090/api/v1/checkout/$CID

# Warm GET (cache HIT → zero OMS). Expect sub-second.
curl -s -o /dev/null -w 'warm GET: %{http_code} in %{time_total}s\n' localhost:8090/api/v1/checkout/$CID

# PATCH delivery-method courier (cart unchanged → cache HIT → fast, no timeout). Expect 200, status "selecting".
curl -s -w '\nPATCH delivery: %{http_code} in %{time_total}s\n' \
  -XPATCH localhost:8090/api/v1/checkout/$CID/delivery-method \
  -H 'Content-Type: application/json' -d '{"type":"delivery"}'
```

Expected:
- cold GET: 200, well under the 30 s `WriteTimeout` (target ~3-6 s — concurrent batch + cart resolve), with 4 delivery methods.
- warm GET: 200, sub-second (no OMS call — confirm in logs that no OMS request fired).
- PATCH: 200, full `CheckoutState`, `status:"selecting"`, no client timeout.

- [ ] **Step 5: Confirm the cache row in the DB:**

```bash
psql 'postgres://checkout:checkout@127.0.0.1:5544/checkout?sslmode=disable' \
  -c "SELECT checkout_id, delivery_digest->>'cart_hash' AS hash, jsonb_array_length(delivery_digest->'methods') AS n_methods FROM checkout_sessions WHERE checkout_id='$CID';"
```
Expected: one row with a non-null `hash` and `n_methods` = number of methods. Re-running GET does not change `hash` (cart unchanged).

- [ ] **Step 6: Verify cache invalidation on cart change (optional, if a set-equipment path is reachable):** change the cart composition in baskets for 4455421, GET again → first render recomputes (cache miss, hash differs), subsequent renders hit. Confirm in logs the OMS batch fires exactly once after the change.

- [ ] **Step 7: Update docs.** In `checkout/docs/dev/real-delivery-source.md`, add a "Performance" section documenting: (a) the per-session digest cache (cart-hash key + `DELIVERY_DIGEST_TTL_SECONDS`, persisted in `delivery_digest`), (b) `AllOptions` concurrency + pickup-stores dedup, (c) `HTTP_WRITE_TIMEOUT_SECONDS`. In `checkout/docs/architecture/adr/0001-checkout-state-contract.md` §Status, change the perf note from "BLOCKER" to "resolved": digest cached per session + concurrent batch; real-OMS commands verified within timeout on customer 4455421.

- [ ] **Step 8: Commit the docs.**

```bash
git add checkout/docs/dev/real-delivery-source.md checkout/docs/architecture/adr/0001-checkout-state-contract.md
git commit -m "docs(checkout): digest cache + concurrent AllOptions + write-timeout; ADR-0001 perf blocker resolved"
```

> **Do NOT `git push`** — push is the owner's (Zak's) step, per repo policy.

---

## Self-Review

**Spec coverage** (the three named fixes):
1. **Cache digest on session (key = cart hash; recompute only on composition change)** — Tasks 5 (type + hash + service), 6 (persistence + migration), 7 (assembler skips reader on hit), 8 (TTL wiring). ✅ The MAIN lever per the memory note.
2. **AllOptions in the OMS adapter (dedupe pickup-stores + concurrency of drill-ins)** — Task 2 (port + stub + fakes), 3 (OMS concurrent + dedup), 4 (service runs preliminary ‖ AllOptions). ✅
3. **Raise server WriteTimeout for the cold path** — Task 1 (configurable, default 30 s). ✅
- Live verification on customer 4455421 with `OMS_DELIVERY_SOURCE=real` — Task 9. ✅

**Placeholder scan:** every code step shows full code; every run step has the exact command + expected output. No TBD/TODO left (the old `TODO(perf)` is explicitly removed in Task 4).

**Type consistency:** `DigestCache{CartHash, ComputedAt, Methods}` used identically in types.go, digest_test, repository, assembler, stub. `CartHash([]CartItem) string` signature consistent across digest.go, assembler, tests. `AllOptions(ctx, []CartLine) (map[DeliveryType][]Komplektaciya, error)` identical on the port, stub, OMS adapter, and both test fakes. `UpdateDigestCache(ctx, checkoutID string, cache DigestCache) error` identical on the port, InMemoryStore, Repository. `CacheDeliveryDigest` on `*Service` matches the assembler call. `WithDigestTTL`/`withClock` defined in Task 7, used in Task 7 tests + Task 8 wiring.

**Boundary integrity:** no domain cross-imports introduced — the cache lives entirely inside the `session` domain; `delivery` gains only a method on its own `DeliverySource` port. The 5 `boundary_test.go` guards remain valid (verified by `go test ./...` in Task 8). No OpenAPI change → no contract drift (asserted in Task 8 Step 4).

**Out of scope (noted, not done):** the assembler resolves the live cart once for `productsData` and the digest reader resolves it again inside `Lookup` on a cache miss — a second cart resolution that could be eliminated by passing the cart through the `DigestReader` port; deferred (the cache makes cold computes rare, and this touches a port signature). PVZ drill-in stays deferred. The gateway (`intgateway`) → checkout client timeout is a separate external knob in the gateway repo (raise it there if the cold first render approaches its deadline).
