#!/usr/bin/env bash
# Pull latest changes for platform git clones (ENSI, OMS, Integration, Site, Mobile, Gloria OTS).
# Usage:
#   ./scripts/sync-platform-repos.sh                    # all repos under platform/
#   ./scripts/sync-platform-repos.sh ensi               # platform/ensi/**
#   ./scripts/sync-platform-repos.sh starfish24/core/Order

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLATFORM="${ROOT}/platform"
FILTER="${1:-}"

if [[ ! -d "${PLATFORM}" ]]; then
  echo "error: ${PLATFORM} not found — clone platforms first (see README.md Bootstrap)" >&2
  exit 1
fi

REPOS=()
while IFS= read -r repo; do
  REPOS+=("${repo}")
done < <(find "${PLATFORM}" -name .git -type d -prune 2>/dev/null | sed 's|/\.git$||' | sort)

if [[ -n "${FILTER}" ]]; then
  FILTER_PATH="${PLATFORM}/${FILTER}"
  FILTER_PATH="${FILTER_PATH%/}"
  FILTERED=()
  for repo in "${REPOS[@]}"; do
    if [[ "${repo}" == "${FILTER_PATH}" || "${repo}" == "${FILTER_PATH}/"* ]]; then
      FILTERED+=("${repo}")
    fi
  done
  REPOS=("${FILTERED[@]}")
fi

if [[ ${#REPOS[@]} -eq 0 ]]; then
  echo "error: no git repos matched filter: ${FILTER:-<all>}" >&2
  exit 1
fi

ok=0
skip=0
fail=0

for repo in "${REPOS[@]}"; do
  rel="${repo#"${PLATFORM}/"}"
  if [[ -n "$(git -C "${repo}" status --porcelain 2>/dev/null)" ]]; then
    echo "SKIP  ${rel}  (dirty working tree)"
    skip=$((skip + 1))
    continue
  fi

  branch="$(git -C "${repo}" symbolic-ref -q --short HEAD 2>/dev/null || git -C "${repo}" rev-parse --short HEAD 2>/dev/null || echo "?")"

  if ! git -C "${repo}" fetch --prune --quiet 2>/dev/null; then
    echo "FAIL  ${rel}  (fetch failed)"
    fail=$((fail + 1))
    continue
  fi

  pull_out="$(git -C "${repo}" pull --ff-only 2>&1)" || {
    echo "FAIL  ${rel}  (${pull_out//$'\n'/; })"
    fail=$((fail + 1))
    continue
  }

  if [[ "${pull_out}" == "Already up to date." ]]; then
    echo "OK    ${rel}  (${branch}, up to date)"
  else
    echo "OK    ${rel}  (${branch}, updated)"
  fi
  ok=$((ok + 1))
done

echo "---"
echo "sync done: ok=${ok} skip=${skip} fail=${fail} total=${#REPOS[@]}"
[[ "${fail}" -eq 0 ]]
