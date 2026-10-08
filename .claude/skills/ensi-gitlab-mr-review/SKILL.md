---
name: SKILL
version: 1.0.0
layer: ensi-gitlab-mr-review
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# ENSI GitLab MR Review

> **Part of ENSI Development Pattern:** This skill covers step 8️⃣ (Commit and MR) of the [8-step ENSI development pattern](../pattern-development-ensi.md). Use this when reviewing MRs to ensure all previous 7 steps (understanding, planning, code, OpenAPI, testing, security, integration) have been properly completed.

**BASELINE:** Apply `gj-gitlab-mr-review` once if it is not already active; never reload it recursively.

Load `ensi-code-style` and `ensi-tests`. Add `ensi-api-design` + `ensi-openapi` for contracts, `ensi-models` for persistence, `ensi-kafka` for events, and the query/meta skills when those surfaces change. Consult `ensi-architect` read-only when ownership or a public/inter-service boundary changes; do not create architecture artifacts during review unless explicitly requested.

## ENSI Architecture Pass

- Confirm one service owns mutable business truth. Reject direct cross-service DB reads and a second mutable source of truth. Allow explicit projections/read models and BFF aggregation when ownership, event/API contract, rebuild/replay, and freshness/lag behavior are clear.
- For API changes, trace specification -> generated server/client artifacts -> implementation -> resources/errors -> every API version and consumer. Search both `openapi/` and `public/api-docs/` layouts.
- For model/migration changes, check nullable/default semantics, backfill, indexes/constraints, factories, mixed-version deployment, and rollback.
- For Kafka or projections, trace producer -> topic/config -> consumer -> read model/cache/index -> public API. Check transaction/after-commit timing, idempotency, update/delete handling, replay/rebuild, and observability.
- For PIM/offers/CMS changes, inspect catalog-cache/Elasticsearch/reindex effects and storefront freshness.
- Check PHP/Go parallel implementations such as offers and event-dispatcher. Prove which runtime is active and whether parity or an explicit divergence is required.
- Check admin vs customer authorization, tenant/business-unit/channel/region scope, and `ApiMultiVersion` branches.

## ENSI Boundary Escalation

Trace beyond ENSI when the MR changes:

- `customers-api-web`, baskets, checkout commit, delivery, payment, discounts, or order payloads -> Integration and OMS;
- generated clients or public APIs -> all consuming services and frontends;
- price/stock/catalog projections -> cache, Site/Mobile, imports, and DWH where applicable;
- BU/region/store/warehouse mappings -> offers/offers-go, catalog-cache, Integration, and OMS delivery availability;
- carrier, fiscal, marking, or export fields -> Integration, OMS, OTS, 1C/ARM.

Require contract/failure-path evidence for still-supported older clients and fallback routes. A passing ENSI suite alone does not prove downstream compatibility.

## Checks Learned From Past Reviews

Each rule: what to check, the trigger that should bring it to mind, how to prove it. Source in brackets.

- **Secret in an outgoing client header other than `Authorization`.** Trigger: a new HTTP client with `API-Key`, `X-Api-Key`, a token header. `w4-logger` masks only `authorization`, `password`, `x-stress-test` (`mask.keys`), and stage runs with `W4_HTTP_OUT_HEADERS=true` (`ms-helm-values/stage/common-env.yaml`), so the key lands in Elasticsearch in clear text. Require the header in the service's own `config/w4-logger.php` mask or a client factory without `GuzzleLoggerMiddleware`. P1. [2026-10-02, webapi-connector !30; `docs/tasks/2026-10-02-opsomn002-268-skills-rules.md` п. 1]
- **A field the consumer only learns from change events never reaches existing records.** Trigger: a new field in a Kafka payload feeding a projection (catalog-cache, offers). Require an initial-load step — `kafka:push-model-changes` or a one-off command — and its place in the rollout order. `push-model-changes --since` selects by `updated_at` of the published model; an import that writes a neighbour table does not touch it, so run without `--since`. Proof: count of rows with the field in the source vs the projection. [2026-10-02, catalog-cache !111; `docs/tasks/2026-10-02-opsomn002-268-skills-rules.md` п. 2]
- **Writing to a parent from a child's event loses data.** Trigger: a consumer does `Parent::find(...)` and returns when it is missing. Topic order is not guaranteed: on catalog-cache stage 27% of products were created after their first SKU. Require storing on the child and pulling into the parent when the parent is created. [2026-10-02, catalog-cache !111; `docs/tasks/2026-10-02-opsomn002-268-skills-rules.md` п. 3]
- **An event that replaces the whole set of child rows needs a message key by entity id.** `HighLevelProducer::sendOne(string $message)` takes no key; with more than one partition two events of one entity may apply out of order and the older set wins. See `ensi-kafka` › Payload Design. [2026-10-02, catalog-cache !111; `docs/tasks/2026-10-02-opsomn002-268-skills-rules.md` п. 4]
- **A lock bump to a `dev-master` commit of a generated client.** Trigger: one `reference` line changed in `composer.lock`. Check `git log old..new` in the client repo — one line may pull a major line of guzzle/psr7. Compare the package's `require` in the lock with the client's `composer.json` at the new commit, and prove runtime by running the client on the lock's versions, not by the manifest. [2026-10-02, webapi-connector !44; `docs/tasks/2026-10-02-opsomn002-268-skills-rules.md` п. 5]
- **A requirement about the shape of an upstream export.** Trigger: the spec says "one row per SKU / per key" and the code's replace logic relies on it. Check the loader's staging table (`imported_items.body`) before reviewing the replace logic: the spec promised one document per SKU, data had several for 4 292 SKUs. [2026-10-02, webapi-connector !30; `docs/tasks/2026-10-02-opsomn002-268-skills-rules.md` п. 6]
- **Remarks about schedule or overlap of ENSI jobs.** In runtime the schedule is set by `cronjobs:` in `ms-helm-values/<env>/…/<service>.yaml` with `concurrencyPolicy: Forbid` (`ms-helm-chart/templates/cron-cj.yaml`); `app/Console/Kernel.php` is not executed and `withoutOverlapping()` changes nothing. A new scheduled command without a helm `cronjobs` entry never runs in prod. [2026-10-02, webapi-connector !30; `docs/tasks/2026-10-02-opsomn002-268-skills-rules.md` п. 10]
- **Changing `ProductIndex::settings()` in catalog-cache.** New settings = new index-name hash = an empty index without an alias; cc-main's `elastic:check-index-exists` checks presence, not fill. Require the rollout order cc-indexer → queue `default` empty and document counts equal → cc-main, and a full reindex after a rollback. See `gj-ci-deploy-map` › Ловушка 5. [2026-09-25, `docs/research/2026-09-25-opsomn002-268-ops-review.md` §4]
- **An observer test on `deleted` where a sibling row goes through `updateOrCreate`.** `saved` fires even without changes, so the test passes without the delete. See `ensi-tests` › Observer Tests. [2026-10-02, catalog-cache !111; `docs/tasks/2026-10-02-opsomn002-268-skills-rules.md` п. 12]
