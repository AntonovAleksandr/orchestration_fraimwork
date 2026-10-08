# How to add MR workflow rule to agent prompts

This document explains how to add `.claude/rules/git-mr-workflow.md` to agent definitions when expanding to new agents.

## Pattern for engineer agents

When adding MR workflow guidance to any **engineer** agent (one that writes/modifies code), insert this section:

### In the agent YAML frontmatter

No changes needed — the `.mdc` rule with `alwaysApply: true` applies globally.

### In the agent markdown body

Add a new section between **Workflow/Verification/Anti-patterns** (typically before "Anti-patterns"):

```markdown
## MR workflow

Follow `.claude/rules/git-mr-workflow.md`:
- **Push fixes to the existing MR branch**, not a new MR
- If review feedback arrives → commit fix → push to same branch → MR auto-updates
- One logical change = one MR; use additional commits for follow-ups
```

Also update **Verification** section to include:

```markdown
- All commits pushed to the MR branch (not a new branch)
```

## Agents that already have this guidance

As of 2026-10-08:

- ✅ `ensi-backend-engineer.md`
- ✅ `integration-engineer.md`
- ✅ `site-engineer.md`
- ✅ `mobile-engineer.md`
- ✅ `oms-java-engineer.md`
- ✅ `gloriaots-engineer.md`
- ✅ `camunda-bpm-engineer.md`
- ✅ `go-service-engineer.md`
- ✅ `go-library-engineer.md`
- ✅ `go-api-contract-engineer.md`
- ✅ `go-test-engineer.md`

## Agents that should NOT have this guidance

**Read-only** and **navigator** agents do not push commits, so they don't need MR workflow sections:

- `ensi-navigator` — read-only
- `ensi-researcher` — read-only
- `site-navigator` — read-only
- `site-researcher` — read-only
- `mobile-navigator` — read-only
- `mobile-researcher` — read-only
- `integration-navigator` — read-only
- `integration-researcher` — read-only
- `oms-navigator` — read-only
- `oms-researcher` — read-only
- `gloriaots-navigator` — read-only
- `gloriaots-researcher` — read-only
- `gitlab-investigator` — read-only
- `logs-detective` — read-only
- `go-code-reviewer` — review-only (delegates to engineers for fixes)
- `go-debugger` — investigate-only (may identify issues but doesn't fix)

## Agents where it would fit but doesn't yet

**Architect** agents are planning/decision-focused and don't typically commit code directly, but they may create ADR docs:

- `architect` — consider adding if it starts writing to `docs/architecture/`
- `ensi-architect` — consider adding
- `integration-architect` — consider adding
- `oms-architect` → use `oms-java-engineer` for implementation
- `corporate-architect` — strategic, rarely commits directly
- `go-architect` — design-phase, rarely commits directly
- `devops-architect` — commits to DevOps infra; could benefit from this guidance

## How to update when adding new engineers

1. **Create the new agent file** under `.claude/agents/<name>.md`
2. **Add the MR workflow section** after Workflow/before Anti-patterns
3. **Update Verification** to include the "all commits pushed to MR branch" check
4. **Commit as a single change** with message like:

```
feat(agents): add git-mr-workflow guidance to new-engineer

Follows .claude/rules/git-mr-workflow.md — agents push
fixes to existing MR branches, not new MRs.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

## Examples

### Example: Minimal MR workflow section

```markdown
## MR workflow

Follow `.claude/rules/git-mr-workflow.md`:
- **Push fixes to the existing MR branch**, not a new MR
- If review feedback arrives → commit fix → push to same branch → MR auto-updates
- One logical change = one MR; use additional commits for follow-ups
```

### Example: Service-specific variant

For services with unusual CI/deployment (e.g., OMS with per-env config):

```markdown
## MR workflow

Follow `.claude/rules/git-mr-workflow.md`:
- **Push fixes to the existing MR branch**, not a new MR
- If review feedback arrives → commit fix → push to same branch → MR auto-updates
- One logical change = one MR; use additional commits for follow-ups
- **Important:** After pushing config changes to `awg/cloud-configs/`, verify all affected environments are updated in the same branch before MR merge.
```

## Rationale

**One MR = one logical change**, updated incrementally through additional commits, preserves:
- **Review history** — reviewers see all feedback and fixes
- **CI traceability** — each push gets fresh test results
- **Approval workflow** — GitLab's approval state change (if configured) reflects the iterative work
- **Branch hygiene** — no orphaned feature branches with partial fixes
- **Merge clarity** — one merge commit represents the complete feature, not scattered fixes

This rule conflicts with the anti-pattern of "opening a new MR because the first one got feedback." Instead, new commits on the same branch update the existing MR.
