# YooKassa Active Orders Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare a safe one-command reconciliation package for active OMS orders affected by the YooKassa callback incident.

**Architecture:** Keep the production snapshot and executable logic separate. The script calls the OMS `updatePayment=true` reconciliation endpoint once per snapshot order and continues past per-order HTTP errors. The initially planned `updatePayment=false` preflight was removed after production evidence showed that branch returning HTTP 500.

**Tech Stack:** Bash 3.2+, curl, jq, OMS REST API.

## Global Constraints

- Include only active `ON_VALIDATION` prepaid orders from the incident window.
- Dry-run is the default; production mutation requires `--execute`.
- Obtain the JWT only from `OMS_TOKEN` and the ServicePipe secret only from
  `GJ_SECRET`; never store either value in the artifact or output.
- Do not execute production reconciliation while building or testing the package.
- Stop on transport/auth/rate-limit errors; record other non-2xx responses and
  continue with the next order.

---

### Task 1: Candidate snapshot

**Files:**
- Create: `orders-active.txt`

**Interfaces:**
- Consumes: read-only `oms-awg-order-prod` query result.
- Produces: one numeric `client_order_id` per line for the runner.

- [x] Query active candidates from the production OMS database.
- [x] Export sorted unique client order IDs.
- [x] Verify count, uniqueness, status and incident-window criteria.

### Task 2: Safe bulk runner

**Files:**
- Create: `reconcile-yookassa-active.sh`

**Interfaces:**
- Consumes: `orders-active.txt`, `OMS_TOKEN`, OMS payment-list endpoint.
- Produces: a timestamped semicolon-delimited result file.

- [x] Implement dry-run and explicit `--execute` modes.
- [x] Remove the broken `updatePayment=false` preflight after production
  verification.
- [x] Reconcile snapshot orders sequentially with `updatePayment=true`.
- [x] Add fail-fast HTTP handling and token-safe result logging.
- [x] Continue after per-order HTTP errors while retaining fail-fast behavior
  for authentication, ServicePipe, rate-limit, transport and malformed-response
  failures.
- [x] Send the ServicePipe `gj-secret` header from `GJ_SECRET`.
- [x] Run syntax, static and mock-server verification.

### Task 3: Operator handoff

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: runner CLI contract.
- Produces: exact dry-run and execution commands plus operational cautions.

- [x] Document the snapshot criteria and current counts.
- [x] Document token handling, output format and execution command.
- [x] Re-read the package against the approved active-only scope.
