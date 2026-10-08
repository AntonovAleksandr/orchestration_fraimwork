---
name: SKILL
version: 1.0.0
layer: gj-buddy-mcp-mastery
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# gj-buddy MCP Mastery

`gj-buddy` is Gloria Jeans's internal MCP server that wraps GitLab, Jira, Confluence, logs and Context Engine. **Prefer it over manual gh/curl/kubectl** for corporate systems — but **do not use GitLab file APIs when code exists locally** under `platform/` (sync first via `./scripts/sync-platform-repos.sh`).

## Tool families

### GitLab (`mcp__gj-buddy__gitlab_*`)

**Discovery:**
- `gitlab_search_projects(query)` — find repos
- `gitlab_get_project(projectId)` — project details
- `gitlab_list_groups`, `gitlab_list_subgroups`, `gitlab_list_group_projects`

**Files without cloning (fallback only):**
- `gitlab_get_repository_file(projectId, file_path, ref)` — when `platform/` has no local clone
- `gitlab_list_repository_tree(projectId, path, ref)` — same

**Commits:**
- `gitlab_get_commit`, `gitlab_list_commits`, `gitlab_list_all_commits`
- `gitlab_list_branches`, `gitlab_list_tags`

**MRs:**
- `gitlab_list_merge_requests(projectId, state=opened|merged|closed)`
- `gitlab_get_merge_request`
- `gitlab_list_merge_request_changes` (diff)
- `gitlab_list_merge_request_commits`
- `gitlab_list_merge_request_notes` (comments)
- `gitlab_get_merge_request_approvals`

**Issues:**
- `gitlab_list_issues(projectId, state=)`
- `gitlab_get_issue`

**Activity & users:**
- `gitlab_list_project_events`
- `gitlab_list_user_events`, `gitlab_get_user_push_summary`
- `gitlab_list_contributors`
- `gitlab_search_users`, `gitlab_get_user`

**CI/CD:**
- `gitlab_list_pipelines`, `gitlab_get_pipeline`
- `gitlab_list_pipeline_jobs`, `gitlab_get_job_log`

### Jira (`mcp__gj-buddy__jira_*`)
- `jira_get_issue(issueIdOrKey)`
- `jira_get_project(projectIdOrKey)`
- `jira_search_issues(jql)` — JQL search

### Confluence (`mcp__gj-buddy__confluence_*`)
- `confluence_get_page(pageId)` — full page content
- `confluence_search_pages(query)` — text search
- `confluence_get_page_children`, `confluence_get_page_descendants`
- `confluence_get_page_comments`, `confluence_get_inline_comments`, `confluence_get_resolved_comments`
- `confluence_get_labels`, `confluence_get_content_properties`
- `confluence_get_page_attachments`
- `confluence_get_space(spaceKey)`

### Logs (`mcp__gj-buddy__logs_*`)
- `logs_list_sources` — what log sources exist
- `logs_recent(source)` — recent entries (latest activity)
- `logs_search_message(query)` — text/regex search
- `logs_search_trace(trace_id)` — distributed trace
- `logs_raw_search` — power-user query

### Context Engine (`mcp__gj-buddy__ctx_*`)
- `ctx_get_page(pageId)` — internal knowledge base entry

## Tool selection cheatsheet

| Question | Tool |
|----------|------|
| "What does file X in OMS look like?" | Local `platform/starfish24/...` after sync — **not** `gitlab_get_repository_file` |
| "Recent MRs in catalog/pim" | `gitlab_list_merge_requests(state=opened)` |
| "Why does pipeline fail?" | `gitlab_list_pipeline_jobs` → `gitlab_get_job_log` |
| "Find a ticket about offer pricing" | `jira_search_issues(jql='text ~ "offer pricing"')` |
| "How does X work?" | `confluence_search_pages` then `confluence_get_page` |
| "Service X is throwing errors" | `logs_recent(source=X)` then `logs_search_trace` |
| "Trace this request" | `logs_search_trace(trace_id)` |
| "Who touched file X recently" | `gitlab_list_commits(file=X)` |
| "Open issues in catalog group" | iterate `gitlab_list_group_projects` + `gitlab_list_issues` |

## Anti-patterns

- **`gitlab_get_repository_file` when `platform/<system>/` already has the repo** — sync + local Read/Grep
- Cloning a repo you don't have yet when you need one file — OK to use `gitlab_get_repository_file` once, then consider adding to bootstrap
- Manual `gh` CLI — it's GitHub, ours is GitLab
- Running `kubectl logs` to investigate prod — use `logs_*` tools (they're aggregated)
- Confluence search via WebFetch — auth fails; use the MCP

## Authentication

All tools authenticate automatically through user's gj-buddy config. If you get auth errors, tell the user to check their `~/.gj-buddy.yaml` or equivalent — don't try to work around them.

## Rate limits & politeness

- For bulk operations (e.g. list MRs across all 25 services), batch sensibly — don't fire 100 calls in a single turn.
- Cache results in memory during your reasoning — don't re-fetch the same MR twice.
