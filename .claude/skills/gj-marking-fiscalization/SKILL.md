---
name: SKILL
version: 1.0.0
layer: gj-marking-fiscalization
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# GJ Marking And Fiscalization

Use this skill for legal product marking and fiscalization flows that cross OMS, OTS, Integration, 1C/WMS, WebGJISMP, YooKassa, ATOL, OFD, and external Chestny Znak/GIS MT systems.

## Start Here

Read the current process map first:

- `docs/architecture/2026-06-03-marking-process-map.md`
- `docs/tasks/rr-tspot-inst-ver-ots-integration-spec.md`
- `docs/research/2026-06-19-rr-tspot-inst-ver-dorabotki.md`
- `docs/bp/05-payment.md`
- `docs/bp/06-fulfillment-and-delivery.md`
- `docs/bp/08-master-data-sync.md`

Then load platform skills as needed: `oms-stack-anatomy`, `camunda-bpm`, `gloriaots-stack-anatomy`, `integration-stack-anatomy`, `gj-delivery-carrier-integration`, and `gj-money-discount-contracts`.

## Disambiguation

Do not confuse:

- legal marking: Chestny Znak / GIS MT / DataMatrix / mark withdrawal from circulation
- warehouse/order labeling: carrier labels, waybills, package labels
- OMS `cancellationStage`: cancellation metadata, not legal marking
- BY DataMatrix flow: regional OMS BPMN marking path

## Flow Model

- OTS/WMS supplies mark data for picked items.
- OMS requests or enriches crypto-tail/validation attributes when required.
- Permission-mode attributes such as `good_mark_validation_uuid`, `timestamp`, `inst`, and `version` must survive handoff to fiscalization.
- YooKassa/ATOL/OFD fiscalization of `full_payment` is where legal sale/withdrawal semantics matter.
- COD and prepaid flows can differ; do not assume a fake mark is allowed.

## Investigation Workflow

1. Identify market/flow: FF, SFS, BY, COD, prepaid, permission mode, emergency mode, or offline verification.
2. Trace mark fields by name and payload level: order-level vs item-level.
3. Confirm which system owns each attribute: OTS/WMS, WebGJISMP, OMS, Integration, YooKassa, ATOL.
4. Check whether empty/missing attributes are valid for the flow or should block fiscalization.
5. Preserve contract evidence: Confluence page_id, Jira key, queue/topic, endpoint, payload fragment, BPMN activity.
6. Remove or redact secrets such as API keys, RabbitMQ credentials, fiscal tokens, and personal data.

## Guardrails

- Do not collapse `uuid/timestamp` and `inst/version` into one semantic field; they have different fiscal meanings.
- Do not assume attributes are per-item when the source says order-level permission.
- Do not change fiscal payloads without checking YooKassa/ATOL/OFD and OMS pay-service behavior.
- Do not treat missing marks as a generic delivery issue; marked-product failures can be regulatory blockers.
- Do not quote or store secrets from marking/fiscal integrations in tracked docs.

## Output Expectations

For research, update `docs/research/<date>-<topic>.md`.

For architecture/design, include:

- exact marking flow and market
- attribute ownership table
- payload field-level mapping
- fiscalization impact
- compatibility with existing OMS/OTS/Integration paths
- acceptance cases for normal, emergency, missing-attribute, and rollback scenarios
