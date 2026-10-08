---
description: Agent MR workflow — no new MRs for fixes; update existing MR via new commits to same branch
alwaysApply: true
---

# Agent MR workflow rule

## Principle

**Agents MUST NOT open new merge requests for fixes or follow-ups.** Instead, push additional commits to the **same branch** to update an existing MR. One MR per logical feature/fix — do not fragment.

## When to update an existing MR (expected path)

1. **Review feedback** — reviewer comments on MR → push new commits to same branch → MR auto-updates
2. **Test failures** — CI fails → fix code → push commit → re-run pipeline
3. **Lint/format** → autofix → push commit
4. **Missing piece discovered** — (e.g., forgot a migration, test, or OpenAPI spec) → add commit → MR updates
5. **Refactor after review** — address architectural feedback → push commits

All of these **update the existing MR**, preserve review history, and show the full evolution of the work.

## When to create a NEW MR (rare exceptions)

Only when the work is **fundamentally separate** and the existing MR is already:
- **Merged to main** (cannot be updated), OR
- **Closed/abandoned**, OR  
- **For a different target branch** (e.g., existing MR → `release/3.34`, new work → `develop`)

**Never** open a new MR just because you found bugs in code from a previous MR on the same branch. Push fixes to the original branch instead.

## Validation checklist before pushing fixes

- [ ] Same branch as original MR (`git branch` shows the feature branch, not `main`)
- [ ] Target repo and remote are correct (`git remote -v` shows the right origin)
- [ ] Commits are reachable from the MR branch (`git log origin/branch --oneline`)
- [ ] No stray commits on `main` or other branches
- [ ] Commit message is clear and follows project conventions

## Example: fixing review feedback

```bash
# Original MR opened on feat/my-feature against main
# Reviewer comments: "Missing validation in action"

# Fix locally on the same branch
git checkout feat/my-feature
git log --oneline -3  # verify you're on the right branch
# ... make changes ...
git add src/app/Actions/MyAction.php
git commit -m "fix(my-feature): add request validation"

# Push to same branch — MR auto-updates
git push origin feat/my-feature

# MR #1234 now shows new commit; full history is preserved
```

## Example: adding missing test after review

```bash
# MR !567 has review feedback: "Need test for edge case"
git checkout feat/checkout-redesign
git add tests/Unit/CheckoutValidatorTest.php
git commit -m "test(checkout): add edge case for partial stock"
git push origin feat/checkout-redesign

# MR !567 updated; no new MR created
```

## Example: multi-step fix across files

```bash
# Original MR opened, Lint fails: missing type hints, and OpenAPI spec is stale
git checkout feat/new-endpoint
git add src/app/Http/ApiV1/NewEndpoint/Action.php  # add types
git commit -m "refactor(new-endpoint): add type hints"

git add openapi/customers.yaml  # update spec
git commit -m "docs(openapi): sync customers endpoint schema"

git push origin feat/new-endpoint
# One MR, multiple focused commits, all history visible
```

## Agent responsibilities

When acting as an engineer (ensi-backend-engineer, site-engineer, etc.):

1. **Before pushing**, confirm the MR exists: `git log -1 --format=%B origin/<branch>` shows it's pushed
2. **Never** `git checkout main && git pull && git checkout -b new-fix-branch` when you should be on the original feature branch
3. **If starting work on an existing MR**, fetch the branch: `git fetch origin feat/xxx && git checkout feat/xxx`
4. **Before declaring done**, ensure all commits are reachable: `git log origin/branch --oneline -10` includes your fixes
5. **Report the MR number**, not new commits — the MR is the unit of delivery

## How this affects review and CI

- **Review history** remains unbroken — reviewers see the original MR and all follow-up commits
- **CI re-runs** on each push — tests validate each iteration
- **Approval state** may change (depends on GitLab config), but the conversation and context stay in one thread
- **Merge commit** happens once, at the end, keeping the branch history clean

## When an agent is asked to "push a fix"

**Do not interpret this as "open a new MR."** Push to the existing branch. If the MR was closed or doesn't exist, ask for clarification: which branch should the fix go to?

## Conflict resolution

If the existing MR branch has conflicts with the target branch (e.g., main has moved):

```bash
git fetch origin
git rebase origin/main  # or merge, depending on project convention
# Resolve conflicts
git push origin feat/xxx --force-with-lease
```

The MR is still one; it now includes rebase/merge commits. **Still do not create a new MR.**
