---
name: gj-delivery-carrier-integration
description: Use when working with Gloria Jeans delivery/carrier flows, OMS logistics, OTS carrier integrations, transport_id, carrierId, delivery_type, pickup points, Yandex/DPD/CDEK/5Post/Russian Post onboarding, SFS/Courier/PVZ delivery incidents, WMS/1C carrier mappings, or end-to-end carrier code tracing.
---

# GJ Delivery Carrier Integration

Use this skill for end-to-end delivery and carrier work across checkout, Integration, OMS, OTS, 1C/WMS, and external carriers.

## Start Here

Read the relevant maps before changing carrier behavior:

- `docs/bp/06-fulfillment-and-delivery.md`
- `docs/bp/07-post-order-and-comms.md` for cancellations/status callbacks
- `docs/bp/08-master-data-sync.md` for 1C/DWH/export impact
- `docs/research/delivery-carrier-codes-end-to-end.md`
- `docs/research/2026-06-25-yandex-express-sfs-investigation.md` for Yandex Express/SFS
- `docs/tasks/OPSOMN001-681-yandex-partial-pick-fix-spec.md` for Yandex partial-pick/cancel pitfalls
- `docs/research/2026-06-13-dpd-ora20810-letter.md` for DPD support evidence pattern

Then load platform-specific skills: `oms-stack-anatomy`, `gloriaots-stack-anatomy`, `integration-stack-anatomy`, and 1C/DevOps context as needed.

## Code Spaces Are Different

Never copy a carrier code by analogy. Confirm the code space:

- Site/Mobile/Integration selection: delivery option and user-facing selection.
- OMS: string `carrierId`, `deliveryTypeId`, `carrierTariffId`, logistics groups, intervals.
- OMS export/adapter layer: maps OMS carrier strings to downstream numeric codes.
- OTS `/v2`: numeric `transport_id`.
- OTS internal: `ShipmentService` enum and carrier handlers.
- OTS DB/WMS: `Carrier` rows, warehouse-specific availability, pickup points.
- 1C/WMS: transport company catalog code.
- 1C Ecom/export: separate `delivery_type` code.
- NSI/ARM: separate delivery type code space.

## Investigation Workflow

1. Identify delivery scenario: courier, PVZ, SFS, C&R, C&C, FF, partial-pick, cancellation, status callback, or carrier onboarding.
2. Trace from checkout selection to OMS logistics fields.
3. Trace export from OMS/Camunda to OTS/1C destination.
4. Confirm every code translation with source evidence, not numeric similarity.
5. Check carrier-specific DB/config prerequisites:
   - OTS `Carrier`
   - pickup points
   - warehouse/platform mappings
   - Helm/env configuration
   - external carrier credentials/config references
6. For runtime issues, collect logs/trace IDs and carrier request/response fragments with secrets removed.

## Guardrails

- Do not confuse `carrierId`, `transport_id`, `delivery_type`, NSI delivery type, and marketplace codes.
- Do not assume OTS implementation means WMS/1C dictionaries are ready.
- Do not treat carrier onboarding as one-service work; it usually spans OMS, adapter/export, OTS, DB dictionaries, 1C, and docs.
- Do not use `place_barcode` or article/SKU as Yandex `item_barcode` without verifying the carrier contract.
- Do not change cancellation/status behavior without checking post-order BP and Camunda state transitions.

## Output Expectations

For carrier onboarding or incident design, include:

- scenario and affected delivery types
- code-space mapping table
- required DB/config/dictionary changes
- route from checkout to OMS to OTS/1C
- external carrier contract evidence
- rollout order and rollback path
- test-stand verification steps
