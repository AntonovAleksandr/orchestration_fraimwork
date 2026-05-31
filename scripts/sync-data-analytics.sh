#!/usr/bin/env bash
# Mirror data-analytics repos from gitlab.com -> internal GitLab (code only).
#
# Clones each repo into platform/data-analytics/<repo> as a working clone with
# two remotes:
#   origin   -> gitlab.gloria.aaanet.ru/.../<repo>       (internal, primary)
#   external -> gitlab.com/gj-analytics/<repo>           (source of truth)
#
# Re-running fetches from external and re-pushes branches + tags to origin
# (internal), so this doubles as an ongoing sync while versions diverge.
# Variables, MRs, issues, runners and integrations are NOT handled here
# (pull those by hand).
#
# Usage:
#   ./scripts/sync-data-analytics.sh                 # all repos
#   ./scripts/sync-data-analytics.sh dbt             # one repo
#   ./scripts/sync-data-analytics.sh --mirror        # force + prune (hard mirror)
#   ./scripts/sync-data-analytics.sh --mirror dbt    # force + prune, one repo
#
# Auth: uses SSH keys by default (add your key to both GitLab instances).
# Set GIT_HTTPS=1 to use HTTPS remotes instead (credential helper / PAT).

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_DIR="${ROOT}/platform/data-analytics"

# origin = internal (primary), external = gitlab.com (source of truth)
ORIGIN_BASE="git@gitlab.gloria.aaanet.ru:e-commerce/data-analytics"
EXTERNAL_BASE="git@gitlab.com:gj-analytics"

if [[ "${GIT_HTTPS:-0}" == "1" ]]; then
  ORIGIN_BASE="https://gitlab.gloria.aaanet.ru/e-commerce/data-analytics"
  EXTERNAL_BASE="https://gitlab.com/gj-analytics"
fi

REPOS=(airflow-gj airflow-aero dbt analytics-scripts)

MIRROR=0
FILTER=""
for arg in "$@"; do
  case "${arg}" in
    --mirror) MIRROR=1 ;;
    -*) echo "error: unknown flag: ${arg}" >&2; exit 2 ;;
    *) FILTER="${arg}" ;;
  esac
done

if [[ -n "${FILTER}" ]]; then
  found=0
  for r in "${REPOS[@]}"; do [[ "${r}" == "${FILTER}" ]] && found=1; done
  if [[ "${found}" -ne 1 ]]; then
    echo "error: unknown repo '${FILTER}'. known: ${REPOS[*]}" >&2
    exit 2
  fi
  REPOS=("${FILTER}")
fi

mkdir -p "${DEST_DIR}"

ok=0
fail=0

for repo in "${REPOS[@]}"; do
  origin_url="${ORIGIN_BASE}/${repo}.git"
  external_url="${EXTERNAL_BASE}/${repo}.git"
  dir="${DEST_DIR}/${repo}"

  echo "=== ${repo} ==="

  # 1. get the code: clone from external (gitlab.com) on first run
  if [[ ! -d "${dir}/.git" ]]; then
    echo "  clone from ${external_url}..."
    if ! git clone --quiet "${external_url}" "${dir}"; then
      echo "  FAIL: clone"
      fail=$((fail + 1)); continue
    fi
  fi

  # 2. wire remotes: origin -> internal, external -> gitlab.com
  if git -C "${dir}" remote get-url origin >/dev/null 2>&1; then
    git -C "${dir}" remote set-url origin "${origin_url}"
  else
    git -C "${dir}" remote add origin "${origin_url}"
  fi
  if git -C "${dir}" remote get-url external >/dev/null 2>&1; then
    git -C "${dir}" remote set-url external "${external_url}"
  else
    git -C "${dir}" remote add external "${external_url}"
  fi

  # 3. fetch latest from external (source of truth)
  echo "  fetch external..."
  if ! git -C "${dir}" fetch external '+refs/heads/*:refs/remotes/external/*' --tags --prune --quiet; then
    echo "  FAIL: fetch external"
    fail=$((fail + 1)); continue
  fi

  # 4. push code to origin (internal)
  push_flags=()
  refspec='refs/remotes/external/*:refs/heads/*'
  if [[ "${MIRROR}" -eq 1 ]]; then
    push_flags+=(--force --prune)
  fi

  echo "  push branches -> origin (internal) $([[ ${MIRROR} -eq 1 ]] && echo '(force+prune)')"
  if ! git -C "${dir}" push "${push_flags[@]}" origin "${refspec}"; then
    echo "  FAIL: push branches (diverged? re-run with --mirror to force)"
    fail=$((fail + 1)); continue
  fi

  echo "  push tags -> origin (internal)"
  if ! git -C "${dir}" push "${push_flags[@]}" origin --tags; then
    echo "  FAIL: push tags"
    fail=$((fail + 1)); continue
  fi

  echo "  OK"
  ok=$((ok + 1))
done

echo "---"
echo "data-analytics sync: ok=${ok} fail=${fail} total=${#REPOS[@]}"
[[ "${fail}" -eq 0 ]]
