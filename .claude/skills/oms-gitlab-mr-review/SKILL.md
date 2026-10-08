---
name: SKILL
version: 1.0.0
layer: oms-gitlab-mr-review
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# OMS GitLab MR Review

**PATTERN REFERENCE:** Reviewers and developers should reference `.claude/skills/pattern-development-oms.md` for OMS development lifecycle validation, especially Camunda BPMN safety, Spring Cloud Config, database migrations, and backward compatibility checks. For changes that cross into Integration Service, also reference **`pattern-development-integration.md`** to ensure Integration development discipline is followed.

**BASELINE:** Apply `gj-gitlab-mr-review` once if it is not already active; never reload it recursively.

Load `oms-stack-anatomy`. Add `oms-java-conventions` for Java and `camunda-bpm` whenever BPMN, workers, topics, timers, variables, status, payment, cancellation, or export behavior changes. For `core/go/logistics`, read its own `CLAUDE.md` and use its repo-local `.claude/agents/` as specialist guidance rather than root `platform-new` assumptions.

## OMS Architecture Pass

- Identify `core/<service>` versus the GJ `awg/` overlay, the actual source/target branch, shared-library versions, and the real CI/deployment path.
- Resolve the concrete Jenkinsfile and target environment for changes that affect deployment, config, or BPMN. Treat GitLab/Bitbucket pipeline results as additional evidence, not proof of the deployed OMS path; if Jenkins/deploy evidence is unavailable, record the gap and do not call the verdict deployment-safe.
- For Java, inspect the root Maven structure, Lombok-generated API, shared `oms-objects`/`oms-json` contracts, tenant propagation, Kafka/retry semantics, caller-visible errors, mTLS, and config consumption.
- For BPMN, trace every changed task/gateway/variable/topic to its worker or embedded implementation. Check completion vs BPMN error vs technical retry/incident, lock duration, variable type/size, timers, and packaging/deployment.
- Explicitly assess running process instances. Renamed/removed activities, changed gateways, topics, or variable semantics require backward compatibility, a migration plan, or proof that no active instance can reach the old path.
- Treat Spring Cloud Config as deployed truth. Inspect matching staging, preprod, and prod files under `awg/cloud-configs`, including service naming, secret/certificate references, rollout, and rollback; `application.yml` defaults are insufficient.
- Identify the external commit point for reservations, payments, carrier registration, export, and status callbacks. Check idempotency, retries, deduplication, compensation, and partial-success behavior.

## OMS Boundary Escalation

For order, delivery, payment, export, cancellation, status, marking, or master-data changes, trace:

`Site/Mobile -> ENSI -> Integration route/version -> OMS fields -> BPMN/process variables -> worker/topic -> Adapter/export -> OTS or 1C/WMS/carrier -> callback/status/refund path`.

Keep code spaces distinct: OMS carrier/status fields, Adapter mappings, OTS `transport_id`, 1C delivery/transport codes, and ARM/NSI values are separate contracts. Check active and fallback processes plus deployment order across companion MRs.
