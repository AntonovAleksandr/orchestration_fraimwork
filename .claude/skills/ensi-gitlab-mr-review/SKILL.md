---
name: ensi-gitlab-mr-review
description: "Use when reviewing a GitLab Merge Request in an ENSI repository under greensight/gj, including PIM, offers, catalog-cache, baskets, customers-api-web, admin APIs, connectors, generated PHP clients, OpenAPI, Kafka, migrations, or PHP-to-Go parity changes."
---

# ENSI GitLab MR Review

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
