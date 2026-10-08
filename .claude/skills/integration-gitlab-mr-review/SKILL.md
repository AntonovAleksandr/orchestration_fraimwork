---
name: SKILL
version: 1.0.0
layer: integration-gitlab-mr-review
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# Integration GitLab MR Review

**BASELINE:** Apply `gj-gitlab-mr-review` once if it is not already active; never reload it recursively.

Load `integration-stack-anatomy` and `integration-php-conventions`. Add `integration-deployment` for runtime/container/worker changes and the relevant checkout, money, delivery, marking, or DWH skill for business flows. Consult `integration-architect` read-only when responsibility moves across systems; do not create architecture artifacts during review unless explicitly requested.

## Integration Architecture Pass

- Classify the MR as application, shared library, runtime/deployment, or docs/CI. Apply only relevant branches; do not force the V1-V4 application trace onto a docs-only change.
- Trace the executable path from the current tree: route or command -> provider/registration -> controller/handler -> service/mutator -> client/topic/DB state -> deployed API or worker process.
- Review every affected V1/V2/V3/V4 route and consumer. A fix in one version is not coverage for active Site/Mobile fallback versions.
- Derive PHP/Lumen compatibility from current `composer.json`, bootstrap, and Docker files. Do not assume full Laravel features or a newer PHP runtime.
- Keep the API and background-worker deployments distinct. For commands, verify schedule, command registration, supervisor/daemon reachability, locking, shutdown, retry, and duplicate execution.
- For Kafka, queues, outbox, or persistent retries, inspect envelope/contract, commit semantics, idempotency, ordering, poison messages, trace propagation, and replay.
- Trace partial success after external side effects: OMS order creation, payment link, coupon/loyalty operation, 1C/OTS export, stock/status update. Require stable `clientOrderId` and compensation or reconciliation where needed.
- Review auth, request/response logging, PII/payment/token redaction, timeouts, error mapping, and production configuration. Ensure test doubles do not hide an upstream contract break.
- For `logger`, `msq-client`, or `health`, inventory all package consumers and review public API/config/schema compatibility, Composer version/lock and release order, `msq-client` migrations, and log/probe contract changes.

## Integration Boundary Escalation

Map the exact contract on both sides:

- Site/Mobile -> Integration version, auth, request/response and fallback behavior;
- ENSI -> basket/customer/catalog truth, quantities, delivery preference, prices and claims;
- Integration -> OMS payload, totals, intervals, carrier codes, payment type and idempotency;
- Integration <-> OTS/1C/DWH/ATOL topics, mappings, retries, status and reconciliation;
- legacy Integration vs `platform-new/checkout` or `intgateway` ownership.

Do not accept one successful HTTP response as proof that the complete async business process finished.

## Development workflow

For MRs that introduce new features or significant changes, verify the author followed **`pattern-development-integration.md`** — the 7-step structured development cycle covering understanding, planning, implementation, security, testing, commit, and merge request discipline. This skill focuses on review criteria; the pattern guides development discipline.
