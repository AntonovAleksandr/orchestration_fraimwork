# offers-go — Production-Readiness & Parity Review

**Date:** 2026-05-29
**Scope:** Is `platform/ensi/apps/catalog/offers-go` (Go rewrite) ready to replace PHP/Laravel `offers` in prod? Parity (incl. `offers-client-php`), data anomalies, additional tests.
**Method:** 4 parallel code-parity research agents (API/client, domain assembly, Kafka/cron, prior-review digest) + live analysis of `ensi-gs-offers-stage` (test, Go-written) vs `ensi-gs-offers-prod` (PHP-written) DBs + `ensi:logs:preprod`.

## Verdict: CONDITIONAL — strong parity, NOT yet ready for unconditional cutover

Functional parity is genuinely high (API/client contract complete; assembly math faithful; Kafka contract matches). The blockers are **operational/process**, not logic: DB maintenance, one failed sync, an unfinished refactor, an un-executed validation runbook, and a cutover plan for the consumer-group/offset change.

---

## Confirmed solid (parity verified)

- **HTTP API / client contract: 9/9 endpoints present**, every `offers-client-php` method served. Filters/sorts/includes, pagination `{data,meta}` and error envelopes match. 8 consumer services covered (pim, feed, catalog-cache, baskets, ensi-connector, event-dispatcher, customers-api-web, admin-gui-backend).
- **Live API works on test**: baskets + customer-gui-web (via cc) call `offers-master/offers:search` → HTTP 200.
- **Assembly math faithful**: price selection, prohibitions, stocks aggregation (store/warehouse/predefined=10), target-store selection, obsolete discover/refresh, export_date — all MATCH. CC availability SQL identical to PHP.
- **Data invariants clean** (2.3M sample): no NULL price w/ price_available, no negative/zero prices, no bad stock_available. `(sku_product_id, region_id)` UNIQUE enforced. Coverage = full SKU×region cross-product (~114.6M = 481k×234).
- **Kafka topics + payloads match**: offers.1, sku-totals.0, offer-stores.1 (produced); region-base-store.0, sku-product-vendor-codes.0, stocks.0, region-store-warehouse.0 (consumed). Go adds DLQ + internal offers-assemble-range.0 (improvements).
- **Cron/sync jobs reproduced** (prices/events/prohibitions/sell-start/assemble + obsolete + inits + check-sync).
- **`is_active`≈always-false on BOTH prod and stage** — legacy column, not a Go bug (initial scare resolved).
- **Latent divergences are dormant in real data**: 0 dup sell-start rows, 0 dup region_store_warehouses, 0 dup price keys.

---

## Data anomalies found (live)

| # | Finding | Severity | Notes |
|---|---------|----------|-------|
| D1 | **`stocks-init` sync FAILED** — `failed_attempts=3`, `last_success=NULL` (never succeeded) on test | HIGH | Stock data exists (~36M rows via Kafka stocks.0), but the bulk init never completed → possible coverage gaps. Root-cause needed. |
| D2 | **No autovacuum/analyze on big tables** — `last_analyze` NULL on ALL tables; `offers` (114M rows, ~14M dead ≈12% bloat) & `stocks` (36M) `last_autovacuum=NULL` | HIGH (at prod scale) | Stale planner stats → bad plans; unbounded bloat. Must tune autovacuum/analyze before prod volume. |
| D3 | **Vestigial tables** `base_offers` (3.85M) + `override_offers` (32.8M) in stage DB, referenced by **no code** in either service | LOW | Cruft from `offers_backup.sql` restore. Confirm droppable; not used. |
| D4 | **Orphan/stale `sync_tasks` rows** `start-sell-dates` (71d) & `full-sku` (71d) superseded by Go-named `sell-start`/`obsolete-refresh` | LOW–MED | Code uses different `code` values → if Go & PHP ever share the `sync_tasks` table, interval guard won't coordinate (double-runs / "never ready"). |
| D5 | **offers-go app logs absent from ENSI preprod ELK** (only inbound HTTP visible via callers) | MED | Observability gap; runbook assumes log access. Confirm log shipping/Grafana before prod. |

---

## Parity divergences / risks (from agents)

**Domain (latent, dormant in current data — add guards):**
- Sell-start duplicate selection: Go `MAX(updated_at)` vs PHP arbitrary `LIMIT 1` (no unique constraint). 0 dups now → add unique constraint on `sku_sell_start_dates(sku_product_id)`.
- Stock double-count if duplicate `region_store_warehouses(region_id, idd)`. 0 dups now → add unique constraint.
- Timezone day-boundary (**UNCERTAIN, verify**): PHP app TZ vs pgx session TZ vs Go process TZ must all agree, else price/ban off-by-one-day near midnight.
- `base_store_code` match: Go `EqualFold` (case-insensitive) vs PHP `===`. Latent on casing drift.

**Kafka / cutover:**
- Consumer-group rename (per-topic `-sku/-region/-stocks/...`) → **offsets NOT shared with PHP**. Need a controlled handoff plan (stop PHP consumers; Go from latest or seed via push-* commands).
- Produced messages keyed by `sku_product_id` (Go) vs likely keyless (PHP) → confirm cc-indexer/baskets partition/ordering assumptions.
- DLQ drops after N retries (default 10) where PHP retried forever → **DLQ monitoring + replay required** or data silently goes stale.
- `offers-assemble-range.0` needs adequate partitions (>10) in prod Kafka.
- `check-sync-task` alert moved Telegram→Prometheus → re-wire ops alerting.

**OPSOMN-14774 batching refactor (the entire `to-do/` set):**
- **C1 merge blocker still OPEN**: `internal/runtime/importer/recalc.go` has its own inline batching loop instead of the unified `buildBatchTasksFromIDs` helper (verify if since fixed).
- Rollout-validation runbook **never executed** (all baseline/scenario tables blank). Code review verdict: "ready for TEST contour with caveats," not prod.

**API (low / dormant):**
- Aggregate endpoint doesn't parse flat `__gt/__gte/__lt/__lte` date keys (no current consumer uses them).
- Stocks search nested `sku.*` like-filters not supported (no consumer uses them).
- Dead `*_from`/`*_to` filter branches in Go (cleanup).

---

## Recommended additional tests before prod

1. **Shadow/response-diff**: replay prod offer-search + cc-availability traffic against offers-go, diff field-by-field (esp. offset `total`, default page size, price/availability).
2. **Output-equivalence on shared input**: point Go assembler at a prod-data snapshot and diff the `offers` rows (price/availability/export flags) it produces vs PHP for a SKU sample incl. obsolete, multi-price, sale-window-boundary, sparse-stock SKUs.
3. **Execute the runbook** (scenarios A–E) with baseline capture; fix C1 first.
4. **TZ assertion test** across the day boundary.
5. **Kafka cutover dry-run**: consumer-group handoff, downstream idempotency (pim/baskets/cc-indexer), DLQ alerting + replay.
6. **Fix & re-run `stocks-init`**; verify stock coverage vs PHP.
7. **DB load test** with autovacuum/analyze tuned; confirm plans on 114M `offers`.
8. Add unique constraints (sell-start, region_store_warehouses); drop vestigial base/override tables; reconcile sync_tasks `code` naming.
