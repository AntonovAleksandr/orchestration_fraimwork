# IntGateway recommendations — latency optimization (single catalog-cache round-trip + drop server sort)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut `/api/v1/recommendations/similar` latency by removing the duplicate catalog-cache round-trip in the temporary stub path, and by dropping the redundant server-side sort in the hydrator.

**Architecture:** The recommendations domain orchestrates `region resolve (bu) → source → trim → hydrate`. Today the catalog-cache **stub source** does a `cards:search` to harvest `vendor_code`s, then the **hydrator** does a *second* catalog-cache call (`cards:search-ordered-by-field`) to fetch the full cards for the trimmed ids — two calls to the same store for the same products. This plan adds an **optional `CardProvider` capability**: a source that already has full cards returns them directly, and the Service skips hydration (one catalog-cache call instead of two). Separately, the hydrator already re-orders results to the input order in Go, so its server-side `sort_field=vendor_code` is redundant — switch it to the plain `cards:search`.

**Measured baseline (test stand, avg per upstream call):** bu `search_regions` ≈ 62 ms · catalog-cache `search` (source) ≈ 131 ms · catalog-cache `search_ordered` (hydrator) ≈ 173 ms — strictly sequential ≈ 366 ms. Removing the second catalog-cache call saves ≈ the hydrator's ~170 ms for the stub path.

**Tech Stack:** Go 1.26, net/http + chi, `gj-go-httpclient` substrate, published `catalogcacheclient` v0.2.0. Repo: `platform-new/intgateway` (it IS listed in `platform-new/go.work`, so plain `go build/test ./...` works — do **not** use `GOWORK=off`). Deploy: pushing to `master` auto-builds and auto-deploys to the **test** stand (CI `test:build` + `test:deploy`); stage/prod are manual.

**Scope guardrails (read before coding):**
- This is two independent optimizations. Change #3 (hydrator sort) is tiny and low-risk; Change #1 (single round-trip) is the bigger one. They compose: after #1 the **stub never calls the hydrator**, so #3 only affects the **future real-engine path** (engine → ids → hydrate). Both are worth shipping now.
- Do **not** break the consumer-defined port boundary (ADR-0010/§3.1): `RecommendationSource.Similar → []ProductID`, `ProductHydrator.Hydrate → []ProductCard`. The fast path is an **optional** interface the Service detects via type assertion; the engine source keeps using source→hydrate.
- Do **not** touch `internal/domains/recommendations/apiv1/` (generated) or `api/v1/bundle/` by hand. No OpenAPI change is needed (behavior/contract unchanged).
- Follow `intgateway/CLAUDE.md` conventions. No `utils.go`. Errors wrapped with `%w`.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `internal/domains/recommendations/service.go` | orchestration + ports | Add optional `CardProvider` interface; Service.Similar uses it (skip hydrator) when the source implements it. |
| `internal/adapters/recommendations/catalogcache_source.go` | catalog-cache stub source | Extract a private `search(...)` helper; add `SimilarCards(...)` implementing `CardProvider` (one call, with includes, mapped via `mapCard`). |
| `internal/adapters/recommendations/hydrator.go` | catalog-cache hydrator | Switch `SearchProductCardsOrderedByField` → plain `SearchProductCards` (drop `SortField`); update the consumer interface. Go-side reordering stays. |
| `internal/adapters/recommendations/catalogcache_source_test.go` | stub source tests | Add `SimilarCards` test (one call → mapped cards, region+view_target filter, dedupe). |
| `internal/adapters/recommendations/hydrator_test.go` | hydrator tests | Fake implements `SearchProductCards`; drop `SortField` assertion; keep region_id + include + order assertions. |
| `internal/app/wire/recommendations_test.go` | wire e2e | Adjust: stub path is now a single catalog-cache call returning cards directly. |

---

## Task 1: Hydrator — drop the redundant server-side sort (Change #3)

The hydrator builds a `byVendor` map and restores **input order** in Go (`for _, id := range ids { ... }`), so the server-side `sort_field=vendor_code` does nothing useful. Switch to the plain `cards:search`.

**Files:**
- Modify: `internal/adapters/recommendations/hydrator.go`
- Test: `internal/adapters/recommendations/hydrator_test.go`

- [ ] **Step 1: Update the hydrator's consumer interface to the plain search method**

In `internal/adapters/recommendations/hydrator.go`, replace the interface:

```go
// catalogCacheClient is the consumer-defined surface the hydrator needs.
// *catalogcache.Client satisfies it.
type catalogCacheClient interface {
	SearchProductCards(ctx context.Context,
		req catalogcache.SearchProductCardsRequest,
	) (catalogcache.SearchProductCardsResponse, error)
}
```

(was `SearchProductCardsOrderedByField` / `SearchProductCardsOrderedByFieldRequest`.)

- [ ] **Step 2: Build a plain `SearchProductCardsRequest` (no SortField) and call SearchProductCards**

Replace the request block (the `filter := ...` through `resp, err := h.client.SearchProductCardsOrderedByField(ctx, req)` lines) with:

```go
	filter := map[string]interface{}{"vendor_code": vendorCodes}
	if regionID != "" {
		filter["region_id"] = regionID
	}
	include := []string{"offers", "images", "modifications", "labels", "messages"}
	limit := len(ids)
	pgType := "offset"
	// Plain cards:search — we already restore input order in Go below, so the
	// server-side ordering (cards:search-ordered-by-field) was redundant work.
	req := catalogcache.SearchProductCardsRequest{
		Filter:     &filter,
		Include:    &include,
		Pagination: &catalogcache.OffsetPagination{Limit: &limit, Type: &pgType},
	}

	resp, err := h.client.SearchProductCards(ctx, req)
```

Leave everything else in `Hydrate` unchanged (the `byVendor` map + input-order loop + `mapCard(pc, len(cards))` + `h.metrics.observe(...)`).

- [ ] **Step 3: Update the hydrator test fake to the new method**

In `internal/adapters/recommendations/hydrator_test.go`, change `fakeClient` to implement `SearchProductCards`:

```go
type fakeClient struct {
	resp catalogcache.SearchProductCardsResponse
	err  error
	got  catalogcache.SearchProductCardsRequest
}

func (f *fakeClient) SearchProductCards(_ context.Context, req catalogcache.SearchProductCardsRequest) (catalogcache.SearchProductCardsResponse, error) {
	f.got = req
	return f.resp, f.err
}
```

Then in `TestHydrate_BuildsRequestAndPreservesOrder`, **delete** the `SortField` assertion block:

```go
	if fc.got.SortField != "vendor_code" {
		t.Fatalf("sort_field: want vendor_code, got %q", fc.got.SortField)
	}
```

Keep the `fc.got.Include == nil` check and the `region_id == "77"` check (they read `fc.got.Include` / `fc.got.Filter`, both present on `SearchProductCardsRequest`).

- [ ] **Step 4: Run hydrator tests**

Run: `cd platform-new/intgateway && go test ./internal/adapters/recommendations/... -run TestHydrate -v`
Expected: PASS (all `TestHydrate_*`).

- [ ] **Step 5: Commit**

```bash
cd platform-new/intgateway
git add internal/adapters/recommendations/hydrator.go internal/adapters/recommendations/hydrator_test.go
git commit -m "perf(recommendations): hydrator uses plain cards:search (drop redundant server sort)

The hydrator already restores input order in Go, so cards:search-ordered-by-field's
server-side sort_field=vendor_code was wasted work. Switch to plain cards:search.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Add the `CardProvider` fast path (Change #1, part A — domain)

Add an **optional** capability so a source that already produced full cards returns them directly; the Service skips the separate hydration call.

**Files:**
- Modify: `internal/domains/recommendations/service.go`
- Test: `internal/domains/recommendations/service_test.go`

- [ ] **Step 1: Write a failing test for the fast path**

In `internal/domains/recommendations/service_test.go`, add a fake source that also implements the (not-yet-defined) `CardProvider`, and assert the hydrator is **not** called:

```go
type fakeCardSource struct {
	cards        []ProductCard
	hydratorUsed *bool
}

func (f fakeCardSource) Similar(_ context.Context, _ ProductID, _ SimilarOpts) ([]ProductID, error) {
	// should not be used when SimilarCards is available
	ids := make([]ProductID, len(f.cards))
	for i, c := range f.cards {
		ids[i] = ProductID(c.Identifier)
	}
	return ids, nil
}

func (f fakeCardSource) SimilarCards(_ context.Context, _ ProductID, _ SimilarOpts) ([]ProductCard, error) {
	return f.cards, nil
}

// markingHydrator flips a flag if Hydrate is ever called.
type markingHydrator struct{ used *bool }

func (m markingHydrator) Hydrate(_ context.Context, ids []ProductID, _ string) ([]ProductCard, error) {
	*m.used = true
	cards := make([]ProductCard, len(ids))
	return cards, nil
}

func TestSimilar_CardProviderSkipsHydrator(t *testing.T) {
	used := false
	src := fakeCardSource{cards: []ProductCard{
		{Identifier: "a"}, {Identifier: "b"}, {Identifier: "c"},
	}}
	svc := NewService(src, markingHydrator{used: &used}, fakeResolver{})

	cards, err := svc.Similar(context.Background(), "p", SimilarOpts{Limit: 2, RegionFias: "rf"})
	if err != nil {
		t.Fatalf("similar: %v", err)
	}
	if used {
		t.Fatalf("hydrator must NOT be called when source provides cards")
	}
	if len(cards) != 2 {
		t.Fatalf("limit must be honored: want 2, got %d", len(cards))
	}
	if cards[0].Identifier != "a" {
		t.Fatalf("order must be preserved: got %q", cards[0].Identifier)
	}
}
```

- [ ] **Step 2: Run it to verify it fails (compile error: CardProvider/SimilarCards undefined)**

Run: `cd platform-new/intgateway && go test ./internal/domains/recommendations/... -run TestSimilar_CardProviderSkipsHydrator`
Expected: FAIL (does not compile — `SimilarCards`/`CardProvider` not yet referenced by production code; the fake compiles but the Service does not use it, so `used` stays false only after Step 3 — at this step the build is fine but the test would pass *accidentally* only if Service already skips hydrator, which it does not → hydrator runs → `used==true` → FAIL). Confirm it FAILS with "hydrator must NOT be called".

- [ ] **Step 3: Add the `CardProvider` interface and the fast path in Service**

In `internal/domains/recommendations/service.go`, add the interface just below `RegionResolver`:

```go
// CardProvider is an OPTIONAL capability a RecommendationSource may implement: it
// returns fully hydrated cards directly, letting the Service skip the separate
// ProductHydrator round-trip. The catalog-cache stub source implements it (it
// already fetches cards from the same store); the real recommendation-engine
// source does not (it returns only ids, so hydration via catalog-cache is needed).
type CardProvider interface {
	SimilarCards(ctx context.Context, productID ProductID, opts SimilarOpts) ([]ProductCard, error)
}
```

Then in `Similar`, right **after** `opts.RegionID = regionID` and **before** `ids, err := s.source.Similar(...)`, insert the fast path:

```go
	// Fast path: if the source can produce cards directly (e.g. the catalog-cache
	// stub, which already fetched them), use them and skip the hydration round-trip.
	if cp, ok := s.source.(CardProvider); ok {
		cards, err := cp.SimilarCards(ctx, productID, opts)
		if err != nil {
			return nil, fmt.Errorf("%w: %w", ErrSourceUnavailable, err)
		}
		if opts.Limit > 0 && len(cards) > opts.Limit {
			cards = cards[:opts.Limit]
		}
		return cards, nil
	}
```

Leave the existing `source.Similar → trim → hydrator.Hydrate` block below as the fallback (engine path).

- [ ] **Step 4: Run the service tests**

Run: `cd platform-new/intgateway && go test ./internal/domains/recommendations/...`
Expected: PASS (new test + all existing `TestSimilar*`).

- [ ] **Step 5: Commit**

```bash
cd platform-new/intgateway
git add internal/domains/recommendations/service.go internal/domains/recommendations/service_test.go
git commit -m "feat(recommendations): optional CardProvider fast path (skip hydration when source has cards)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Stub source implements `CardProvider` (Change #1, part B — adapter)

The stub source fetches showable cards from catalog-cache; make it return full mapped cards in **one** call, reusing `mapCard` (same package, `mapping.go`).

**Files:**
- Modify: `internal/adapters/recommendations/catalogcache_source.go`
- Test: `internal/adapters/recommendations/catalogcache_source_test.go`

- [ ] **Step 1: Extract a private search helper (DRY) and reuse it in `Similar`**

In `internal/adapters/recommendations/catalogcache_source.go`, add a private helper and refactor `Similar` to use it. The helper builds the `view_target=carousel` (+ `region_id`) filtered request; `withIncludes` decides whether to ask catalog-cache to build full cards.

```go
// search runs the carousel-showable cards query, scoped to opts.RegionID.
// withIncludes asks catalog-cache to build full cards (offers/images/…) — needed
// for the card fast path, skipped when only vendor codes are required.
func (s *CatalogCacheStubSource) search(ctx context.Context, opts domain.SimilarOpts, withIncludes bool) (catalogcache.SearchProductCardsResponse, error) {
	limit := s.pool
	pgType := "offset"
	filter := map[string]interface{}{"view_target": []string{viewTargetCarousel}}
	if opts.RegionID != "" {
		filter["region_id"] = opts.RegionID
	}
	req := catalogcache.SearchProductCardsRequest{
		Filter:     &filter,
		Pagination: &catalogcache.OffsetPagination{Limit: &limit, Type: &pgType},
	}
	if withIncludes {
		include := []string{"offers", "images", "modifications", "labels", "messages"}
		req.Include = &include
	}
	return s.client.SearchProductCards(ctx, req)
}
```

Replace the body of `Similar` so it calls the helper (no includes) and keeps the existing dedupe/extract-ids loop:

```go
func (s *CatalogCacheStubSource) Similar(ctx context.Context, _ domain.ProductID, opts domain.SimilarOpts) ([]domain.ProductID, error) {
	resp, err := s.search(ctx, opts, false)
	if err != nil {
		return nil, err
	}
	seen := make(map[string]struct{}, len(resp.Data))
	out := make([]domain.ProductID, 0, len(resp.Data))
	for _, c := range resp.Data {
		if c.VendorCode == "" {
			continue
		}
		if _, dup := seen[c.VendorCode]; dup {
			continue
		}
		seen[c.VendorCode] = struct{}{}
		out = append(out, domain.ProductID(c.VendorCode))
	}
	return out, nil
}
```

- [ ] **Step 2: Add `SimilarCards` implementing the domain `CardProvider`**

Append to `catalogcache_source.go`:

```go
// SimilarCards returns carousel-showable cards in ONE catalog-cache call, scoped
// to opts.RegionID. Implements recommendations.CardProvider so the domain Service
// skips the separate hydration round-trip. Dedupes per-region duplicates and
// preserves catalog-cache order.
func (s *CatalogCacheStubSource) SimilarCards(ctx context.Context, _ domain.ProductID, opts domain.SimilarOpts) ([]domain.ProductCard, error) {
	resp, err := s.search(ctx, opts, true)
	if err != nil {
		return nil, err
	}
	seen := make(map[string]struct{}, len(resp.Data))
	cards := make([]domain.ProductCard, 0, len(resp.Data))
	for _, c := range resp.Data {
		if c.VendorCode == "" {
			continue
		}
		if _, dup := seen[c.VendorCode]; dup {
			continue
		}
		seen[c.VendorCode] = struct{}{}
		cards = append(cards, mapCard(c, len(cards)))
	}
	return cards, nil
}
```

> Note: `mapCard(src catalogcache.ProductCard, pos int) domain.ProductCard` lives in `internal/adapters/recommendations/mapping.go` (same package) — call it directly. `pos` is the compact output index (use `len(cards)`), matching the hydrator's convention so `Sort` is 1..N with no gaps.

- [ ] **Step 3: Add a test for `SimilarCards`**

In `internal/adapters/recommendations/catalogcache_source_test.go`, add:

```go
func TestCatalogCacheStubSource_SimilarCards_OneCallMapsAndDedupes(t *testing.T) {
	client := &fakeSearchClient{resp: catalogcache.SearchProductCardsResponse{Data: []catalogcache.ProductCard{
		{VendorCode: "A1", Identifier: "a1", Status: catalogcache.REGULAR, Name: "A one"},
		{VendorCode: "A1", Identifier: "a1", Status: catalogcache.DIFFERENTREGULAR, Name: "A one (region)"}, // dup
		{VendorCode: "", Identifier: "blank"},                                                                // dropped
		{VendorCode: "B2", Identifier: "b2", Status: catalogcache.REGULAR, Name: "B two"},
	}}}

	src := NewCatalogCacheStubSource(client)
	cards, err := src.SimilarCards(context.Background(), "ignored", domain.SimilarOpts{Limit: 10, RegionID: "77"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// region + view_target pushed server-side; includes requested for full cards
	if (*client.lastReq.Filter)["region_id"] != "77" {
		t.Fatalf("region_id filter: got %v", (*client.lastReq.Filter)["region_id"])
	}
	if client.lastReq.Include == nil {
		t.Fatalf("includes must be requested for the card fast path")
	}
	if len(cards) != 2 {
		t.Fatalf("want 2 deduped cards, got %d", len(cards))
	}
	if cards[0].Identifier != "a1" || cards[1].Identifier != "b2" {
		t.Fatalf("identity/order wrong: %+v", cards)
	}
	if cards[0].Sort != 1 || cards[1].Sort != 2 {
		t.Fatalf("Sort must be compact 1..N: %d,%d", cards[0].Sort, cards[1].Sort)
	}
}
```

> The existing `fakeSearchClient` (in `catalogcache_source_test.go`) already records `lastReq` and implements `SearchProductCards` — reuse it. Set `Identifier`/`Name` on the input cards so `mapCard` produces a recognizable domain card. Verify `mapCard` reads `Identifier`/`Name` (it does); add `Price`/`Offers` only if `mapCard` requires them to avoid a panic — check `mapping.go` and adjust the fixture so the mapping does not dereference a nil pointer.

- [ ] **Step 4: Run adapter tests**

Run: `cd platform-new/intgateway && go test ./internal/adapters/recommendations/...`
Expected: PASS (new `SimilarCards` test + existing source/hydrator/region tests).

- [ ] **Step 5: Commit**

```bash
cd platform-new/intgateway
git add internal/adapters/recommendations/catalogcache_source.go internal/adapters/recommendations/catalogcache_source_test.go
git commit -m "perf(recommendations): stub source returns cards in one catalog-cache call (CardProvider)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Fix the wire e2e test for the single-call stub path

With the fast path, the stub flow makes **one** catalog-cache call (`view_target` filter, no `vendor_code`) returning cards with offers, which become the items directly. The existing fake already returns a 12-card pool (with offers) for the no-`vendor_code` branch, so the assertions should still hold — verify and adjust only if needed.

**Files:**
- Modify (if needed): `internal/app/wire/recommendations_test.go`

- [ ] **Step 1: Run the wire test as-is**

Run: `cd platform-new/intgateway && go test ./internal/app/wire/... -run TestRecommendations -v`
Expected: `TestRecommendations_CatalogCachePath` PASS (10 items, `id-*`, 1 size) and `TestRecommendations_MissingRegionIsBadRequest` PASS.

- [ ] **Step 2: If `TestRecommendations_CatalogCachePath` fails**

The likely cause is that the fast path now needs the pool cards to carry `offers` so `mapCard` produces `Sizes`. The fake's pool branch already includes an `offers` array per card — confirm the pool-branch card map includes the same `offers`/`status`/`price` fields as the vendor_code branch. If the assertion `len(out.Items[0].Sizes) != 1` fails, ensure the pool cards in `catalogCacheStub()` include the `offers` field (copy it from the per-`vc` card map). Make the minimal edit so a single search returns full cards.

- [ ] **Step 3: Commit (only if the test was edited)**

```bash
cd platform-new/intgateway
git add internal/app/wire/recommendations_test.go
git commit -m "test(recommendations): wire e2e covers single-call stub card path

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Full verification + ship

- [ ] **Step 1: Build, vet, test the whole module**

Run:
```bash
cd platform-new/intgateway
go build ./... && go vet ./... && go test ./...
```
Expected: build clean, vet clean, all packages `ok`, no `FAIL`.

- [ ] **Step 2: Push to master (auto-deploys to test)**

```bash
cd platform-new/intgateway
git push origin master
```

- [ ] **Step 3: After the pipeline deploys, verify on the test stand**

Run:
```bash
curl -sS 'https://api-int-test.gloria-jeans.ru/api/v1/recommendations/similar?product_id=GKT028479-2&region_id=0c5b2444-70a0-4932-980c-b4dc0d3f02b5&city_id=0c5b2444-70a0-4932-980c-b4dc0d3f02b5&limit=20' | python3 -m json.tool | head
```
Expected: HTTP 200, 20 distinct items with sizes/price — same shape as before, **faster**.

- [ ] **Step 4: Confirm the second catalog-cache call is gone (metrics)**

Run:
```bash
curl -sS 'https://api-int-test.gloria-jeans.ru/metrics' | grep 'httpclient_requests_total'
```
Expected: for the stub path you now see catalog-cache `op="search"` calls but **no** `op="search_ordered"` increments per request (the hydrator is not called on the stub path), and `ecom_gateway_recommendations_hydration_ratio_count` stops increasing for stub requests. `bu` `search_regions` still appears (region resolve). End-to-end `time_total` for the curl should drop by roughly the old hydrator latency (~150–170 ms server-side).

---

## Self-review checklist (for the implementer, before pushing)

1. **Port boundary intact:** `RecommendationSource.Similar` still returns `[]ProductID`; `CardProvider` is additive and optional; the engine source (`EngineSource`) does **not** implement `CardProvider`, so it still goes source→hydrate. Confirm `EngineSource` was not given a `SimilarCards` method.
2. **No behavior/contract change:** response JSON shape identical; `region_id` still required; dedupe + region scoping preserved on the single-call path.
3. **`mapCard` safety:** the `SimilarCards` test fixtures don't trip a nil-pointer in `mapCard` (check `mapping.go` for pointer fields like `Price`/`OldPrice`/`Offers` and populate the fixture accordingly).
4. **Metrics:** losing `op="search_ordered"` on the stub path is expected (hydrator skipped). The hydrator still uses `op="search"` for the future engine path — that's fine because there the source is the engine (different `service` label), so no collision.
5. **No `GOWORK=off`** needed here — intgateway is in `platform-new/go.work`.
