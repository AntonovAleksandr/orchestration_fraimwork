---
name: SKILL
version: 1.0.0
layer: gj-evidence-ledger-research
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# GJ Evidence-Ledger Research

Use this skill for large cross-system investigations where the output must survive multiple sessions and support later architecture or implementation work.

## Start Here

Use the R-20 research project as the pattern:

- `docs/research/r20-order-splits/README.md`
- `docs/research/r20-order-splits/00-PLAN.md`
- `docs/research/r20-order-splits/00-source-inventory.md`
- `docs/research/r20-order-splits/EVIDENCE-LEDGER.md`
- `docs/research/r20-order-splits/TEMPLATE-stage.md`
- `docs/research/README.md`

Also load `gj-buddy-mcp-mastery` when Jira, Confluence, GitLab, logs, or DB evidence is needed.

## When To Use This Pattern

Use a staged evidence-ledger project when:

- the topic spans 3+ systems
- requirements are in Confluence/Jira and code behavior may disagree
- DB/log evidence is needed
- the work will not finish in one session
- the output is as-is/to-be/gap analysis, not immediate code

For a small incident summary, use normal `docs/research/<date>-<topic>.md` instead.

## Research Structure

Create or update:

- `README.md`: scope, disambiguation, project map, source summary
- `00-PLAN.md`: method, stages, MCP playbook, progress tracker
- `00-source-inventory.md`: Confluence, Jira, docs, code, DB, logs
- `EVIDENCE-LEDGER.md`: one row per gap/finding
- `TEMPLATE-stage.md`: consistent stage output shape
- `stages/stage-NN-<domain>.md`: one domain per stage

## Stage Workflow

1. Start from requirements and source inventory, not from code guesses.
2. Sync only the platform repos needed for the stage.
3. Collect as-is evidence from code, docs, Jira/Confluence, DB SELECTs, and logs.
4. Compare to to-be requirements.
5. Write a gap matrix with confidence and evidence anchors.
6. Append ledger rows after reviewing the stage.
7. End every stage with open questions, acceptance gates, and resume pointer.

## Evidence Rules

- Code evidence: file path and line/range anchor.
- Jira evidence: issue key and status.
- Confluence evidence: page_id and freshness/confidence.
- DB evidence: target name, query purpose, row limits, no writes.
- Log evidence: target, time window, trace_id/order_id, summarized error.
- Secrets and personal data: redact or omit.

## Guardrails

- Do not treat zero grep matches as proof; nested repos and ignored paths can hide results.
- Do not mix as-is facts and to-be design in one paragraph.
- Do not duplicate BP docs; link to them and record only deltas/gaps.
- Do not let subagents update the ledger directly without orchestrator review.
- Do not leave a session without a resume pointer if the investigation is incomplete.

## Output Expectations

Each stage should include:

- scope and hypotheses
- as-is facts
- to-be requirements
- gap matrix
- missed business risks
- open questions
- acceptance gates
- ledger rows to add
- resume pointer
