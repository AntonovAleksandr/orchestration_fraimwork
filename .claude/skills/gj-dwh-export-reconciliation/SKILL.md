---
name: SKILL
version: 1.0.0
layer: gj-dwh-export-reconciliation
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# GJ DWH Export And Reconciliation

Use this skill for operational-to-analytical data flows: Integration cron exports, DWH CSV files, reconciliation, Airflow/dbt, reporting data quality, and order/shipment analytics.

## Start Here

Read the relevant docs before changing export logic or explaining an analytics discrepancy:

- `docs/bp/08-master-data-sync.md`
- `docs/research/2026-05-28-transfer-orders-dwh-oom.md`
- `platform/data-analytics/README.md`
- `docs/research/r20-order-splits/README.md` when shipment-level analytics are involved
- `docs/research/r20-order-splits/EVIDENCE-LEDGER.md` for known DWH gaps

Then load `integration-stack-anatomy`, `integration-deployment`, `integration-php-conventions`, `data-analytics-architect`, and `gj-buddy-mcp-mastery` as needed. For Integration Service implementation, follow **`pattern-development-integration.md`** to ensure proper development discipline.

## Core Questions

- What is the operational source of truth: OMS, Integration, OTS, ENSI, ARM, 1C, or payment/fiscal system?
- Is the export snapshot, delta, status-history based, or full order payload based?
- What is the time window and timezone?
- Is the reported issue missing data, duplicated data, stale data, wrong metric definition, or pipeline failure?
- Does the export need order-level, item-level, shipment-level, payment-level, or status-history granularity?

## Investigation Workflow

1. Identify the export job, schedule, container, and output artifact.
2. Check recent successful and failed runs by logs before assuming code regression.
3. Compare volume drivers:
   - order count
   - status update count
   - item count
   - payload/page size
   - history depth
4. For OOM/slow jobs, locate the largest in-memory response and page boundary.
5. For data quality, trace one business example from source DB to export row to DWH/dbt/reporting layer.
6. Separate quick mitigation from target architecture; exports that only shrink page size may still need stream/master-child redesign later.

## Guardrails

- Do not treat a business spike as a code bug until source volumes are measured.
- Do not increase PHP memory as the only fix without documenting the payload growth mechanism.
- Do not change export semantics without checking downstream DWH/dbt/report consumers.
- Do not expose raw personal data or secret credentials in tracked research.
- Do not conflate order creation date with last status update date; DWH jobs often depend on both.

## Output Expectations

For incidents, update `docs/research/<date>-<topic>.md` with:

- schedule and affected job
- last successful run and first failed run
- volume comparison table
- root-cause hypothesis with evidence
- mitigation and architectural follow-up
- verification command/log query and downstream confirmation

For architecture, include source-of-truth, grain, lineage, freshness, backfill, reconciliation, and ownership.
