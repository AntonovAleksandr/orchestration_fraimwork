---
name: gj-gitlab-mr-review
description: "Use when reviewing an ENSI, Integration Service, OMS, Site, or Mobile Merge Request in Gloria Jeans GitLab, checking an MR URL or IID, deciding whether to approve, preparing review comments, or повторно проверяя исправления after author changes."
---

# GJ GitLab Merge Request Review

Review the MR that exists in GitLab, not an implementer's retelling of it. A green pipeline is evidence, never the verdict.

**REQUIRED SUB-SKILLS:** Use `gj-buddy-mcp-mastery` and `gj-multirepo-navigation`. Apply this baseline once, then load the matching platform addendum: `ensi-gitlab-mr-review`, `integration-gitlab-mr-review`, `oms-gitlab-mr-review`, `site-gitlab-mr-review`, or `mobile-gitlab-mr-review`. Never recursively reload a skill that is already active.

## Establish the Evidence

1. Resolve the project and MR IID. Fetch MR metadata, diff refs, source/target SHAs, commits, changes, notes, approvals, and pipeline/jobs through `gitlab_*` tools.
2. Extract linked Jira issues and relevant Confluence or `docs/research/` requirements. Treat the MR description and developer report as secondary evidence.
3. Sync the affected local clone according to `.claude/rules/local-code-first.mdc`. Inspect the exact MR diff plus surrounding callers, consumers, config, migrations, and tests without checking out or editing the author's branch.
4. Record the reviewed base/start/head and target SHAs plus the accepted pipeline SHA. Accept a pipeline only when it belongs to the reviewed head or reviewed merged result. Immediately before the verdict and every GitLab write, re-fetch the MR diff refs and target SHA; if either side changed, recompute the diff/merged result and review the new delta first.

If the local clone cannot be synced or the exact revision is unavailable, stop the code review with `BLOCKED BY EVIDENCE`. Do not use stale local context or substitute repository-file APIs for the required trace. You may summarize the GitLab MR diff as unverified evidence, but may not issue an approval or a clean-review verdict.

## Mandatory Review Passes

### 1. Intent and Contract

Compare the diff with acceptance criteria and the current business rule. Identify changed inputs, outputs, state transitions, errors, and compatibility promises.

### 2. Correctness and Architecture

Trace reachable execution paths through the changed code. Check ownership boundaries, validation, authorization, transactions, idempotency, retries, concurrency, error handling, security, observability, and maintainability. Load topic-specific GJ skills for checkout, money, delivery, marking, or DWH when relevant.

### 3. Cross-System Impact

Run this pass even when only one repository changed. A full downstream trace is mandatory when the diff changes an HTTP/OpenAPI contract, event/topic, enum/status/code mapping, identity/idempotency key, client/API version, persisted customer or basket context, country/region/locale/timezone, money, discount, payment, delivery, warehouse, carrier, BPMN variable, analytics identity/event, export, or environment configuration.

- Map `upstream caller -> changed system -> downstream consumers -> async side effects`.
- Use the relevant `docs/bp/01-*` through `08-*` process map as a routing aid, not as proof. Verify every active path against the reviewed revision, runtime configuration, and consumer code; report conflicts instead of inferring a topology.
- Check active paths and still-supported legacy, fallback, client-version, and feature-flag paths separately.
- Identify missing companion MRs, mixed-version compatibility, deployment order, rollback, replay/backfill, and owning teams.
- Delegate independent platform traces in parallel when useful, but keep them read-only and verify and synthesize their evidence yourself.

Do not approve a breaking cross-system change merely because the changed repository is internally consistent.

### 4. Verification and Rollout

Check whether tests exercise the changed invariant and realistic failure paths, not only DTOs or mocks. Relate pipeline results to actual coverage. Review migrations, generated clients, caches/read models, configuration across environments, metrics/logs, rollout, and rollback.

### 5. Adversarial Recheck

Before reporting each finding:

- prove a reachable input-to-failure scenario and name the observable outcome;
- search for counter-evidence, guards, tests, or an inactive path;
- classify it as a confirmed defect, material risk, or verification question;
- re-scan the diff from a fresh angle for omissions and secondary effects;
- check existing discussions to avoid duplicate comments.

For a repeat review, verify every previous finding against the corrective diff, then inspect the fix for new regressions and re-run the cross-system pass.

## Verdict and Output

Use `APPROVE`, `CHANGES REQUIRED`, or `BLOCKED BY EVIDENCE`:

- P0: widespread outage, data loss/corruption, security, regulatory, or material financial failure.
- P1: reachable business-flow, contract, idempotency, migration, or rollout defect; always blocks.
- P2: bounded correctness or material operability/maintainability defect; blocks by default.
- P3: non-blocking improvement.

A P2 waiver requires explicit user authorization plus a linked risk acceptance from the service, business, or architecture owner in the MR or Jira; the MR author's assertion alone is insufficient. Keep unverified questions separate from defects. `APPROVE` is a review recommendation, not permission to mutate GitLab.

Lead with the verdict and reviewed head SHA, then findings ordered by severity. Every finding must include:

- exact file/line or symbol;
- reachable failure scenario;
- affected business flow and systems;
- evidence and confidence;
- minimal acceptance condition that closes it.

Finish with checks performed, cross-system surfaces inspected, remaining gaps, and residual risk. If there are no findings, say so explicitly without claiming the change is risk-free.

## GitLab Writes

Default to read-only. Only write when the user explicitly asks to comment, publish drafts, resolve threads, or approve.

- Use `gitlab_create_merge_request_thread` for exact diff positions; otherwise use `gitlab_add_merge_request_note`.
- Use `gitlab_create_merge_request_draft_note` when drafts were requested and `gitlab_publish_merge_request_draft_notes` only when publication was requested.
- Re-fetch notes before writing and avoid duplicates.
- Approve with `gitlab_approve_merge_request` using the current head SHA so a concurrent push invalidates the action.
- Never approve with unresolved blocking findings or an unreviewed required cross-system surface.
