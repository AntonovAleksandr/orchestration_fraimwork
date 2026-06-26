# Migrate Go Services & Clients to `greensight/gj/go` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-home the 9 local Go repos currently under `gitlab.gloria.aaanet.ru/e-commerce/platform/*` into the new group `gitlab.gloria.aaanet.ru/greensight/gj/go/*`, preserving full git history, canonicalizing module paths, and rewriting the cross-module dependency graph so every repo builds standalone.

**Architecture:** Each repo is migrated independently in dependency order (leaf client libs first, then services). For each repo we (1) rewrite module path + all imports + go.mod require/replace, (2) commit, (3) re-point `origin` to the new GitLab project, (4) push all branches + tags (history preserved), (5) for client libs, cut a new `v0.2.0` tag on the post-rewrite commit because the old tags carry the old module path and Go would reject the import-path mismatch. The root `go.work` keeps local cross-module dev working throughout.

**Tech Stack:** Go 1.26, Go workspaces (`go.work`), GitLab SSH remotes, semantic-version module tags.

---

## Decisions locked (from user)

1. `ecom-gateway` → renamed to **`intgateway`** (repo + module path).
2. go-pkg shared libs (`gj-go-httpclient`, `gj-go-logger`, `gj-go-migrate`) **stay in `go-pkg/`** — their import paths are NOT touched.
3. **Preserve full git history** (re-point origin, push all branches + tags).
4. **Canonicalize** service module paths to full URL form.

## Module-path & remote mapping (single source of truth)

| Local dir | Old module path | New module path | New SSH remote |
|---|---|---|---|
| `checkout` | `gj-checkout` | `gitlab.gloria.aaanet.ru/greensight/gj/go/checkout` | `git@gitlab.gloria.aaanet.ru:greensight/gj/go/checkout.git` |
| `ecom-gateway` | `gj-ecom-gateway` | `gitlab.gloria.aaanet.ru/greensight/gj/go/intgateway` | `git@gitlab.gloria.aaanet.ru:greensight/gj/go/intgateway.git` |
| `clients/baskets` | `…/e-commerce/platform/clients/baskets` | `…/greensight/gj/go/clients/basketclient` | `git@gitlab.gloria.aaanet.ru:greensight/gj/go/clients/basketclient.git` |
| `clients/bu` | `…/clients/bu` | `…/greensight/gj/go/clients/buclient` | `…:greensight/gj/go/clients/buclient.git` |
| `clients/catalog-cache` | `…/clients/catalog-cache` | `…/greensight/gj/go/clients/catalogcacheclient` | `…:greensight/gj/go/clients/catalogcacheclient.git` |
| `clients/customers` | `…/clients/customers` | `…/greensight/gj/go/clients/customerclient` | `…:greensight/gj/go/clients/customerclient.git` |
| `clients/discount` | `…/clients/discount` | `…/greensight/gj/go/clients/discountclient` | `…:greensight/gj/go/clients/discountclient.git` |
| `clients/offers` | `…/clients/offers` | `…/greensight/gj/go/clients/offersclient` | `…:greensight/gj/go/clients/offersclient.git` |
| `clients/starfish-oms` | `…/clients/starfish-oms` | `…/greensight/gj/go/clients/starfishclient` | `…:greensight/gj/go/clients/starfishclient.git` |

`…` = `gitlab.gloria.aaanet.ru`. Target GitLab project IDs: checkout=919, intgateway=918, basketclient=920, buclient=921, catalogcacheclient=922, customerclient=923, discountclient=924, offersclient=925, starfishclient=926. All target projects are **empty** (no branches) → pushes are clean.

## Facts established during recon

- **Clients are leaf modules**: none import another client or a service. Each client depends only on go-pkg libs (unchanged). → a client migration = rewrite its OWN path + push.
- **Services import only 3 clients** in `.go` code: `baskets`, `catalog-cache`, `starfish-oms`. The other 4 clients migrate as standalone repos, unused by these services.
- **Internal imports** use the bare module name: 25 distinct `gj-checkout/internal/...` in checkout, 18 distinct `gj-ecom-gateway/internal/...` in ecom-gateway. Canonicalizing the module path rewrites all of them.
- **Tags today**: clients have `v0.1.0`/`v0.1.1`; checkout has `v0.1.0`,`v0.0.x-*`; ecom-gateway has none.
- **No `.gitlab-ci.yml`** in any repo. Old paths appear only in `go.mod`, `README.md`, and a few historical `docs/` files.
- `ecom-gateway/go.mod` has `replace` directives pointing to `../clients/*` and `../gj-go-*` (local-dev crutch). These break standalone CI builds and are **removed** during migration (the root `go.work` already provides local cross-module resolution).
- Root `platform-new/go.work` lists: `./checkout ./clients/baskets ./clients/catalog-cache ./clients/starfish-oms ./ecom-gateway ./gj-go-httpclient ./gj-go-logger`. Local dir names are NOT changed (only module paths + remotes), so go.work `use` paths stay valid; only `ecom-gateway` may optionally be moved to `intgateway` at the very end.

## Key risk & invariant

**Go module path / tag invariant:** an existing tag (e.g. `clients/baskets@v0.1.1`) points at a commit whose `go.mod` still says `module …/clients/baskets`. After we push that history to `basketclient`, any consumer requiring `…/clients/basketclient@v0.1.1` makes Go fetch v0.1.1, read its go.mod, and reject it (path mismatch). **Therefore every client gets a fresh `v0.2.0` tag on the post-rewrite commit**, and services require `…@v0.2.0`. Old tags are still pushed (history) but are not used as module versions under the new path.

**Verification baseline:** local builds run inside the `go.work` workspace, so `go build ./...` resolves cross-module deps from local dirs regardless of tags. Standalone (CI-style) resolution is verified separately with `GOWORK=off` AFTER tags are pushed (Task 12).

---

## Task 0: Pre-flight — backup, access, baseline

**Files:** none (verification only)

- [ ] **Step 1: Confirm clean working trees in every repo**

Run:
```bash
cd $WORKSPACE/platform-new
for r in checkout ecom-gateway clients/baskets clients/bu clients/catalog-cache clients/customers clients/discount clients/offers clients/starfish-oms; do
  printf '%-28s %s\n' "$r" "$(git -C "$r" status --porcelain | wc -l | tr -d ' ') dirty files"
done
```
Expected: every repo `0 dirty files`. If any are dirty, STOP and resolve (commit/stash) before migrating.

- [ ] **Step 2: Create a safety backup bundle of every repo (full history)**

Run:
```bash
cd $WORKSPACE/platform-new
mkdir -p /tmp/gj-migration-backup
for r in checkout ecom-gateway clients/baskets clients/bu clients/catalog-cache clients/customers clients/discount clients/offers clients/starfish-oms; do
  name=$(echo "$r" | tr '/' '-')
  git -C "$r" bundle create "/tmp/gj-migration-backup/$name.bundle" --all
done
ls -la /tmp/gj-migration-backup/
```
Expected: 9 `.bundle` files. These are full-history restore points if any push goes wrong.

- [ ] **Step 3: Verify SSH push access to the new group**

Run:
```bash
ssh -T git@gitlab.gloria.aaanet.ru 2>&1 | head -3
```
Expected: a "Welcome"/authenticated message (not "Permission denied"). If denied, STOP — resolve SSH key / group membership before continuing. Push tasks below will fail otherwise.

- [ ] **Step 4: Confirm baseline workspace build is green BEFORE any change**

Run:
```bash
cd $WORKSPACE/platform-new
go build ./... 2>&1 | tail -20 ; echo "exit=$?"
```
Expected: `exit=0`. This is the reference state — the same command must stay green after each repo migration.

---

## Task 1: Migrate `clients/baskets` → `basketclient` (fully-worked reference procedure)

Tasks 1–7 are **byte-identical** except for the three substituted values `OLDPATH`, `NEWPATH`, `REMOTE`. This task shows every command in full; Tasks 2–7 give only the substitution values and reuse this exact procedure.

For this task:
- `OLDPATH` = `gitlab.gloria.aaanet.ru/e-commerce/platform/clients/baskets`
- `NEWPATH` = `gitlab.gloria.aaanet.ru/greensight/gj/go/clients/basketclient`
- `REMOTE`  = `git@gitlab.gloria.aaanet.ru:greensight/gj/go/clients/basketclient.git`
- `DIR`     = `clients/baskets`

**Files:**
- Modify: `clients/baskets/go.mod` (module line)
- Modify: all `clients/baskets/**/*.go` containing the old self-import path
- Modify: `clients/baskets/README.md` (install/import examples)

- [ ] **Step 1: Rewrite every occurrence of OLDPATH → NEWPATH in tracked text files**

Run:
```bash
cd $WORKSPACE/platform-new/clients/baskets
OLD='gitlab.gloria.aaanet.ru/e-commerce/platform/clients/baskets'
NEW='gitlab.gloria.aaanet.ru/greensight/gj/go/clients/basketclient'
git grep -lF "$OLD" | while read -r f; do
  LC_ALL=C sed -i '' "s#$OLD#$NEW#g" "$f"
done
```
Note: `sed -i ''` is the BSD/macOS form. On Linux use `sed -i`.

- [ ] **Step 2: Verify zero old references remain**

Run:
```bash
cd $WORKSPACE/platform-new/clients/baskets
git grep -nF 'e-commerce/platform/clients/baskets' ; echo "matches above (want none)"
head -1 go.mod
```
Expected: no matches; `head -1 go.mod` shows `module gitlab.gloria.aaanet.ru/greensight/gj/go/clients/basketclient`.

- [ ] **Step 3: Verify the package still builds (standalone, from its own dir)**

Run from inside the client dir with the workspace disabled — this works for ALL clients regardless of `go.work` membership (bu/customers/discount/offers are NOT in go.work) and matches standalone resolution. go-pkg deps are fetched from GitLab (published versions exist).
```bash
cd $WORKSPACE/platform-new/clients/baskets
out=$(GOWORK=off go build ./... 2>&1); rc=$?; echo "$out" | tail -10; echo "exit=$rc"
```
Expected: `exit=0`. (Do NOT use `go build ./clients/<dir>/...` from the workspace root — for the 4 non-workspace clients it fails with "directory prefix … does not contain modules listed in go.work", a false negative.)

- [ ] **Step 4: Commit the rewrite**

Run:
```bash
cd $WORKSPACE/platform-new/clients/baskets
git add -A
git commit -m "chore: rehome module to greensight/gj/go/clients/basketclient

Module path migrated from e-commerce/platform/clients/baskets.
Part of Go fleet migration to greensight/gj/go group."
```
Expected: a new commit on `main`.

- [ ] **Step 5: Re-point origin to the new remote**

Run:
```bash
cd $WORKSPACE/platform-new/clients/baskets
git remote set-url origin git@gitlab.gloria.aaanet.ru:greensight/gj/go/clients/basketclient.git
git remote -v
```
Expected: origin fetch+push both show the basketclient.git URL.

- [ ] **Step 6: Push all branches and existing tags (history preserved)**

Run:
```bash
cd $WORKSPACE/platform-new/clients/baskets
git push origin --all
git push origin --tags
```
Expected: new branch `main` created on the empty target; old tags `v0.1.0`,`v0.1.1` pushed.

- [ ] **Step 7: Cut and push the new `v0.2.0` module tag on the post-rewrite commit**

Run:
```bash
cd $WORKSPACE/platform-new/clients/baskets
git tag -a v0.2.0 -m "First release under greensight/gj/go/clients/basketclient module path"
git push origin v0.2.0
git tag --sort=-v:refname | head -3
```
Expected: `v0.2.0` present and pushed. This is the version services will require.

---

## Tasks 2–7: Migrate the remaining 6 clients

Apply the **exact same 7-step procedure as Task 1**, substituting the three values below. Each task ends with a pushed `v0.2.0` tag. Build-verify each before committing with `cd clients/<DIR> && GOWORK=off go build ./...` → `exit=0` (NOT the workspace-root form — bu/customers/discount/offers are outside go.work).

- [ ] **Task 2 — `clients/bu` → `buclient`**
  - `OLD` = `gitlab.gloria.aaanet.ru/e-commerce/platform/clients/bu`
  - `NEW` = `gitlab.gloria.aaanet.ru/greensight/gj/go/clients/buclient`
  - `REMOTE` = `git@gitlab.gloria.aaanet.ru:greensight/gj/go/clients/buclient.git`
  - sanity grep after rewrite: `git grep -nF 'e-commerce/platform/clients/bu'` → none. (`bu` is short — confirm the sed used the full `clients/bu` path, never bare `bu`.)

- [ ] **Task 3 — `clients/catalog-cache` → `catalogcacheclient`**
  - `OLD` = `gitlab.gloria.aaanet.ru/e-commerce/platform/clients/catalog-cache`
  - `NEW` = `gitlab.gloria.aaanet.ru/greensight/gj/go/clients/catalogcacheclient`
  - `REMOTE` = `git@gitlab.gloria.aaanet.ru:greensight/gj/go/clients/catalogcacheclient.git`
  - Also rewrite the two docs files: `docs/superpowers/plans/2026-05-29-catalog-cache-client.md`, `docs/superpowers/specs/2026-05-29-catalog-cache-client-design.md` (the `git grep -lF` loop already covers them).

- [ ] **Task 4 — `clients/customers` → `customerclient`**
  - `OLD` = `gitlab.gloria.aaanet.ru/e-commerce/platform/clients/customers`
  - `NEW` = `gitlab.gloria.aaanet.ru/greensight/gj/go/clients/customerclient`
  - `REMOTE` = `git@gitlab.gloria.aaanet.ru:greensight/gj/go/clients/customerclient.git`

- [ ] **Task 5 — `clients/discount` → `discountclient`**
  - `OLD` = `gitlab.gloria.aaanet.ru/e-commerce/platform/clients/discount`
  - `NEW` = `gitlab.gloria.aaanet.ru/greensight/gj/go/clients/discountclient`
  - `REMOTE` = `git@gitlab.gloria.aaanet.ru:greensight/gj/go/clients/discountclient.git`

- [ ] **Task 6 — `clients/offers` → `offersclient`**
  - `OLD` = `gitlab.gloria.aaanet.ru/e-commerce/platform/clients/offers`
  - `NEW` = `gitlab.gloria.aaanet.ru/greensight/gj/go/clients/offersclient`
  - `REMOTE` = `git@gitlab.gloria.aaanet.ru:greensight/gj/go/clients/offersclient.git`

- [ ] **Task 7 — `clients/starfish-oms` → `starfishclient`**
  - `OLD` = `gitlab.gloria.aaanet.ru/e-commerce/platform/clients/starfish-oms`
  - `NEW` = `gitlab.gloria.aaanet.ru/greensight/gj/go/clients/starfishclient`
  - `REMOTE` = `git@gitlab.gloria.aaanet.ru:greensight/gj/go/clients/starfishclient.git`
  - Also rewrite `docs/superpowers/specs/2026-05-30-starfish-oms-client-design.md` (covered by the loop).

- [ ] **Checkpoint after Task 7: all 7 clients pushed with v0.2.0**

Run:
```bash
cd $WORKSPACE/platform-new
for r in baskets bu catalog-cache customers discount offers starfish-oms; do
  printf '%-16s origin=%s  v0.2.0=%s\n' "$r" \
    "$(git -C clients/$r remote get-url origin)" \
    "$(git -C clients/$r tag -l v0.2.0)"
done
```
Expected: every origin points to `greensight/gj/go/clients/*client.git` and every repo lists `v0.2.0`.

---

## Task 8: Update `go.work` to keep local cross-module resolution coherent

The `go.work` `use` paths are unchanged (local dirs kept their names), so no edit is strictly required. Confirm the workspace still resolves the renamed modules.

**Files:** `platform-new/go.work` (verify only; no change expected)

- [ ] **Step 1: Confirm the workspace resolves the new module paths**

Run:
```bash
cd $WORKSPACE/platform-new
go list -m all 2>&1 | grep -E 'greensight/gj/go/clients' | sort
```
Expected: the renamed client modules (`basketclient`, `catalogcacheclient`, `starfishclient`, …) appear, resolved to local dirs. If a module is missing, ensure its dir is listed in `go.work use(...)`.

---

## Task 9: Migrate `checkout` (canonicalize + rewrite client requires)

`checkout` depends on `baskets`, `catalog-cache`, `starfish-oms` (now `*client@v0.2.0`) plus go-pkg libs (unchanged). It has no `replace` directives.

**Files:**
- Modify: `checkout/go.mod` (module line + 3 require lines)
- Modify: all `checkout/**/*.go` with `gj-checkout/...` self-imports and the 3 old client import paths
- Modify: `checkout/README.md`

- [ ] **Step 1: Rewrite self module path `gj-checkout` → canonical, in all tracked files**

Run:
```bash
cd $WORKSPACE/platform-new/checkout
NEWSELF='gitlab.gloria.aaanet.ru/greensight/gj/go/checkout'
# module line
LC_ALL=C sed -i '' "s#^module gj-checkout#module $NEWSELF#" go.mod
# self imports: gj-checkout/...  ->  NEWSELF/...   (match only when followed by '/')
git grep -lF 'gj-checkout/' | while read -r f; do
  LC_ALL=C sed -i '' "s#gj-checkout/#$NEWSELF/#g" "$f"
done
```

- [ ] **Step 2: Rewrite the 3 client import paths (path + name change)**

Run:
```bash
cd $WORKSPACE/platform-new/checkout
declare -a MAP=(
  "gitlab.gloria.aaanet.ru/e-commerce/platform/clients/baskets|gitlab.gloria.aaanet.ru/greensight/gj/go/clients/basketclient"
  "gitlab.gloria.aaanet.ru/e-commerce/platform/clients/catalog-cache|gitlab.gloria.aaanet.ru/greensight/gj/go/clients/catalogcacheclient"
  "gitlab.gloria.aaanet.ru/e-commerce/platform/clients/starfish-oms|gitlab.gloria.aaanet.ru/greensight/gj/go/clients/starfishclient"
)
for pair in "${MAP[@]}"; do
  OLD="${pair%%|*}"; NEW="${pair##*|}"
  git grep -lF "$OLD" | while read -r f; do LC_ALL=C sed -i '' "s#$OLD#$NEW#g" "$f"; done
done
```

- [ ] **Step 3: Pin the 3 client requires to `v0.2.0` in go.mod**

Run:
```bash
cd $WORKSPACE/platform-new/checkout
LC_ALL=C sed -i '' -E 's#(greensight/gj/go/clients/(basketclient|catalogcacheclient|starfishclient)) v[0-9].*#\1 v0.2.0#' go.mod
grep -nE 'greensight/gj/go/clients|module ' go.mod
```
Expected: module line is the canonical checkout path; the 3 client requires read `… v0.2.0`.

- [ ] **Step 4: Verify zero stale references**

Run:
```bash
cd $WORKSPACE/platform-new/checkout
git grep -nE 'gj-checkout|e-commerce/platform' ; echo "matches above (want none)"
```
Expected: no matches.

- [ ] **Step 5: Build in the workspace (local resolution via go.work)**

Run:
```bash
cd $WORKSPACE/platform-new
go build ./checkout/... 2>&1 | tail -20 ; echo "exit=$?"
go vet ./checkout/... 2>&1 | tail -10 ; echo "vet=$?"
```
Expected: `exit=0` and `vet=0`. (go.work resolves the clients locally even though v0.2.0 isn't fetched.)

- [ ] **Step 6: Commit**

Run:
```bash
cd $WORKSPACE/platform-new/checkout
git add -A
git commit -m "chore: rehome module to greensight/gj/go/checkout

Canonicalize module path (was bare gj-checkout) and repoint client
deps to greensight/gj/go/clients/*client@v0.2.0.
Part of Go fleet migration to greensight/gj/go group."
```

- [ ] **Step 7: Re-point origin and push history + tags**

Run:
```bash
cd $WORKSPACE/platform-new/checkout
git remote set-url origin git@gitlab.gloria.aaanet.ru:greensight/gj/go/checkout.git
git push origin --all
git push origin --tags
git remote -v
```
Expected: origin = checkout.git; `main` + existing tags (`v0.1.0`, `v0.0.x-*`) pushed.

---

## Task 10: Migrate `ecom-gateway` → `intgateway` (canonicalize, drop replace directives, rename)

`ecom-gateway` depends on `baskets`, `catalog-cache` + go-pkg libs, and currently carries `replace` directives to `../clients/*` and `../gj-go-*`. Those relative paths break standalone builds and are removed (go.work covers local dev).

**Files:**
- Modify: `ecom-gateway/go.mod` (module line, 2 client requires, remove 4 replace lines)
- Modify: all `ecom-gateway/**/*.go` with `gj-ecom-gateway/...` self-imports and the 2 old client paths
- Modify: `ecom-gateway/README.md` and `docs/` references

- [ ] **Step 1: Rewrite self module path `gj-ecom-gateway` → canonical intgateway path**

Run:
```bash
cd $WORKSPACE/platform-new/ecom-gateway
NEWSELF='gitlab.gloria.aaanet.ru/greensight/gj/go/intgateway'
LC_ALL=C sed -i '' "s#^module gj-ecom-gateway#module $NEWSELF#" go.mod
git grep -lF 'gj-ecom-gateway/' | while read -r f; do
  LC_ALL=C sed -i '' "s#gj-ecom-gateway/#$NEWSELF/#g" "$f"
done
```

- [ ] **Step 2: Rewrite the 2 client import paths**

Run:
```bash
cd $WORKSPACE/platform-new/ecom-gateway
declare -a MAP=(
  "gitlab.gloria.aaanet.ru/e-commerce/platform/clients/baskets|gitlab.gloria.aaanet.ru/greensight/gj/go/clients/basketclient"
  "gitlab.gloria.aaanet.ru/e-commerce/platform/clients/catalog-cache|gitlab.gloria.aaanet.ru/greensight/gj/go/clients/catalogcacheclient"
)
for pair in "${MAP[@]}"; do
  OLD="${pair%%|*}"; NEW="${pair##*|}"
  git grep -lF "$OLD" | while read -r f; do LC_ALL=C sed -i '' "s#$OLD#$NEW#g" "$f"; done
done
```

- [ ] **Step 3: Remove the relative-path `replace` directives and pin client requires to v0.2.0**

Run:
```bash
cd $WORKSPACE/platform-new/ecom-gateway
# drop every replace line that points to a relative ../ path
LC_ALL=C sed -i '' '/^replace .*=> \.\..*/d' go.mod
# pin the 2 migrated client requires to v0.2.0
LC_ALL=C sed -i '' -E 's#(greensight/gj/go/clients/(basketclient|catalogcacheclient)) v[0-9].*#\1 v0.2.0#' go.mod
# remove now-blank double newlines left by deletions
awk 'NF{c=0} !NF{c++} c<2' go.mod > go.mod.tmp && mv go.mod.tmp go.mod
cat go.mod
```
Expected: no `replace` lines remain; `basketclient`/`catalogcacheclient` requires read `v0.2.0`; go-pkg requires (`gj-go-httpclient v0.1.1`, `gj-go-logger v1.0.5`) unchanged.

- [ ] **Step 4: Verify zero stale references**

Run:
```bash
cd $WORKSPACE/platform-new/ecom-gateway
git grep -nE 'gj-ecom-gateway|e-commerce/platform' ; echo "matches above (want none)"
```
Expected: no matches.

- [ ] **Step 5: Build + vet in workspace**

Run:
```bash
cd $WORKSPACE/platform-new
go build ./ecom-gateway/... 2>&1 | tail -20 ; echo "exit=$?"
go vet ./ecom-gateway/... 2>&1 | tail -10 ; echo "vet=$?"
```
Expected: `exit=0`, `vet=0`.

- [ ] **Step 6: Commit**

Run:
```bash
cd $WORKSPACE/platform-new/ecom-gateway
git add -A
git commit -m "chore: rename module to greensight/gj/go/intgateway

Rehome + rename ecom-gateway -> intgateway, canonicalize module path,
repoint client deps to greensight/gj/go/clients/*client@v0.2.0, and
drop local-dev replace directives (go.work covers local resolution).
Part of Go fleet migration to greensight/gj/go group."
```

- [ ] **Step 7: Re-point origin to intgateway and push**

Run:
```bash
cd $WORKSPACE/platform-new/ecom-gateway
git remote set-url origin git@gitlab.gloria.aaanet.ru:greensight/gj/go/intgateway.git
git push origin --all
git push origin --tags
git remote -v
```
Expected: origin = intgateway.git; `main` pushed (ecom-gateway had no tags).

---

## Task 11: Update root `go.work` replace coherence + rename local dir (optional)

- [ ] **Step 1: Confirm whole-workspace build is still green**

Run:
```bash
cd $WORKSPACE/platform-new
go build ./... 2>&1 | tail -20 ; echo "exit=$?"
```
Expected: `exit=0` — matches the Task 0 baseline.

- [ ] **Step 2 (optional): rename the local `ecom-gateway` dir to `intgateway` and update go.work**

Run:
```bash
cd $WORKSPACE/platform-new
git -C ecom-gateway rev-parse --is-inside-work-tree >/dev/null && mv ecom-gateway intgateway
LC_ALL=C sed -i '' 's#\./ecom-gateway#./intgateway#' go.work
go build ./... 2>&1 | tail -5 ; echo "exit=$?"
```
Expected: `exit=0`. Skip this step if you prefer to keep the local dir name; it has no effect on the remote (module path + origin already point to intgateway).

---

## Task 12: Standalone (CI-style) resolution verification — proves tags work

This is the real test that the `v0.2.0` tags + new module paths resolve WITHOUT the workspace. Run it AFTER all clients' v0.2.0 tags are pushed (Task 7 checkpoint).

**Files:** none (verification only)

- [ ] **Step 1: Resolve checkout standalone with the workspace disabled**

Run:
```bash
cd $WORKSPACE/platform-new/checkout
GOWORK=off GOFLAGS=-mod=mod go mod download 2>&1 | tail -20 ; echo "exit=$?"
GOWORK=off go build ./... 2>&1 | tail -20 ; echo "build=$?"
```
Expected: `exit=0`, `build=0`. Go fetches `…/clients/basketclient@v0.2.0` etc. from GitLab and the import paths match. If you see "invalid version: …go.mod has non-… module path", a client tag was cut on the wrong (pre-rewrite) commit — re-tag v0.2.0 on the rewrite commit and re-push.

- [ ] **Step 2: Restore go.sum under the workspace and commit if changed**

Run:
```bash
cd $WORKSPACE/platform-new/checkout
git status --porcelain go.sum
# if go.sum changed (new tag hashes), commit it:
git add go.sum && git commit -m "chore: update go.sum for greensight client v0.2.0 modules" || echo "no go.sum change"
git push origin HEAD
```

- [ ] **Step 3: Repeat Step 1 for intgateway**

Run:
```bash
cd $WORKSPACE/platform-new/intgateway 2>/dev/null || cd $WORKSPACE/platform-new/ecom-gateway
GOWORK=off GOFLAGS=-mod=mod go mod download 2>&1 | tail -20 ; echo "exit=$?"
GOWORK=off go build ./... 2>&1 | tail -20 ; echo "build=$?"
git add go.sum 2>/dev/null && git commit -m "chore: update go.sum for greensight client v0.2.0 modules" 2>/dev/null && git push origin HEAD || echo "no go.sum change"
```
Expected: `exit=0`, `build=0`.

---

## Task 13: GitLab project settings + closeout

- [ ] **Step 1: Set default branch to `main` on every new project**

For each target project (IDs 918–926) the pushed code lives on `main`, but the project default is `master`. Set default to `main` via the GitLab UI (Settings → Repository → Default branch) or API for: checkout(919), intgateway(918), basketclient(920), buclient(921), catalogcacheclient(922), customerclient(923), discountclient(924), offersclient(925), starfishclient(926).

Verify per project:
```bash
# example check (read-only) — repeat per project path
echo "check default_branch is 'main' for each greensight/gj/go/* project"
```
Expected: each project's default branch is `main`.

- [ ] **Step 2: Final fleet audit**

Run:
```bash
cd $WORKSPACE/platform-new
for r in checkout ecom-gateway clients/baskets clients/bu clients/catalog-cache clients/customers clients/discount clients/offers clients/starfish-oms; do
  d="$r"; [ -d intgateway ] && [ "$r" = ecom-gateway ] && d=intgateway
  printf '%-26s -> %s\n' "$d" "$(git -C "$d" remote get-url origin 2>/dev/null)"
done
```
Expected: every origin is under `greensight/gj/go/…`; none under `e-commerce/platform`.

- [ ] **Step 3: Decide fate of old `e-commerce/platform/*` repos (manual)**

The old GitLab repos still exist with full history. Recommended: archive them (GitLab → Settings → General → Archive project) or add a README note pointing to the new location. Do NOT delete until the new repos are confirmed building in CI. This step is a manual decision, not a script.

---

## Self-Review checklist (run before executing)

- **Spec coverage:** 9 repos migrated (Tasks 1–7 clients, 9 checkout, 10 intgateway); history preserved (push --all/--tags in each); module paths canonicalized (Tasks 9/10 Step 1); go-pkg untouched (verified — no go-pkg path in any sed); cross-module graph rewritten (Tasks 9/10 Step 2–3); standalone build proven (Task 12). ✓
- **Tag invariant:** every client gets fresh v0.2.0 post-rewrite (Task 1 Step 7 + Tasks 2–7); services require v0.2.0 (Tasks 9/10 Step 3); validated by GOWORK=off resolution (Task 12). ✓
- **Ordering:** clients (leaf) before services; tags pushed before standalone verification. ✓
- **Reversibility:** Task 0 Step 2 bundles are full-history restore points; old repos left intact until Task 13 Step 3. ✓
- **Platform/sed portability:** all `sed -i ''` calls are macOS/BSD form (the working machine is darwin). On Linux switch to `sed -i`. Flagged in Task 1 Step 1.
```
