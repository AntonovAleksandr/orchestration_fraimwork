---
name: evidence-ledger-research
version: 1.0.0
layer: evidence-ledger-research
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# Evidence-Ledger Research

Use this skill for large cross-system investigations where the output must survive multiple sessions and support later architecture or implementation work.

## Start Here

Create a research project directory (for example `docs/research/<topic>/`) with the files listed under Research Structure, and keep a `docs/research/README.md` index.

Also load the skill for your tracker, wiki, VCS, log or DB access tools when such evidence is needed.

## When To Use This Pattern

Use a staged evidence-ledger project when:

- the topic spans 3+ components
- requirements are in a wiki or tracker and code behavior may disagree
- DB/log evidence is needed
- the work will not finish in one session
- the output is as-is/to-be/gap analysis, not immediate code

For a small incident summary, use normal `docs/research/<date>-<topic>.md` instead.

## Research Structure

Create or update:

- `README.md`: scope, disambiguation, project map, source summary
- `00-PLAN.md`: method, stages, MCP playbook, progress tracker
- `00-source-inventory.md`: wiki, tracker, docs, code, DB, logs
- `EVIDENCE-LEDGER.md`: one row per gap/finding
- `TEMPLATE-stage.md`: consistent stage output shape
- `stages/stage-NN-<domain>.md`: one domain per stage

## Stage Workflow

1. Start from requirements and source inventory, not from code guesses.
2. Sync only the repositories needed for the stage.
3. Collect as-is evidence from code, docs, tracker/wiki, DB SELECTs, and logs.
4. Compare to to-be requirements.
5. Write a gap matrix with confidence and evidence anchors.
6. Append ledger rows after reviewing the stage.
7. End every stage with open questions, acceptance gates, and resume pointer.

## Evidence Rules

- Code evidence: file path and line/range anchor.
- Tracker evidence: issue key and status.
- Wiki evidence: page id and freshness/confidence.
- DB evidence: target name, query purpose, row limits, no writes.
- Log evidence: target, time window, trace_id/entity id, summarized error.
- Secrets and personal data: redact or omit.

## Guardrails

- Do not treat zero grep matches as proof; nested repos and ignored paths can hide results.
- Do not mix as-is facts and to-be design in one paragraph.
- Do not duplicate existing process docs; link to them and record only deltas/gaps.
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
