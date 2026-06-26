---
name: gj-workspace-maintenance
description: "Use when maintaining the GJ-Ecommerce workspace metadata and agent layer: CLAUDE.md, README.md, docs/service-index.md, docs/onboarding.md, .gitignore, .claude/agents, .claude/skills, generated .codex/agents, generated .agents/skills, platform/platform-new/platform-next descriptions, counts, indexes, and source-of-truth cleanup."
---

# GJ Workspace Maintenance

Use this skill when changing the workspace map, agent/skill catalog, ignored local clones, or generated Codex adapters.

## Source of Truth

- Canonical agents: `.claude/agents/*.md`.
- Canonical skills: `.claude/skills/*/SKILL.md`.
- Canonical workspace map: `CLAUDE.md`, `README.md`, `docs/service-index.md`, `docs/onboarding.md`, tracked README pointers under `platform/*/README.md`.
- Generated local adapters: `.codex/agents/*.toml`, `.agents/skills/*`. They must stay ignored and regenerated, not manually edited.

## Maintenance Workflow

1. Inspect current state before editing:
   - `git status --short --ignored`
   - `find .claude/agents -maxdepth 1 -name '*.md' | sort`
   - `find .claude/skills -maxdepth 2 -name SKILL.md | sort`
   - `rg -n "<old-name>|<new-name>|<old-count>|platform-new|platform-next" README.md CLAUDE.md docs/service-index.md docs/onboarding.md .gitignore .claude`
2. Edit only canonical files first:
   - add/update/delete `.claude/agents/*.md`
   - add/update/delete `.claude/skills/*/SKILL.md`
   - update README/CLAUDE/onboarding/service-index counters and tables
   - update `.gitignore` for ignored generated/local workspace paths
3. Keep generated adapters out of source control:
   - `.codex/` and `.agents/` must be ignored
   - do not hand-edit `.codex/agents/*.toml` or `.agents/skills/*`
4. Regenerate adapters after any `.claude/agents` or `.claude/skills` change:
   - `./scripts/generate-codex-adapters.py`
5. Verify consistency before saying done.

## Required Checks

Run the relevant checks for every workspace maintenance change:

```bash
python3 -m unittest tests/test_generate_codex_adapters.py
./scripts/generate-codex-adapters.py
printf 'claude_agents=' && find .claude/agents -maxdepth 1 -name '*.md' | wc -l
printf 'codex_agents=' && find .codex/agents -maxdepth 1 -name '*.toml' | wc -l
printf 'claude_skills=' && find .claude/skills -maxdepth 2 -name SKILL.md | wc -l
printf 'codex_skills=' && find .agents/skills -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l
rg '^model\s*=' .codex/agents || true
git diff --check -- .claude README.md CLAUDE.md docs/service-index.md docs/onboarding.md .gitignore scripts tests
```

Also verify agent filenames match frontmatter:

```bash
python3 - <<'PY'
from pathlib import Path
bad=[]
for p in sorted(Path('.claude/agents').glob('*.md')):
    name=None
    for line in p.read_text().splitlines()[:20]:
        if line.startswith('name:'):
            name=line.split(':',1)[1].strip().strip('"\'')
            break
    if name != p.stem:
        bad.append(f'{p}: name={name} stem={p.stem}')
if bad:
    print('\n'.join(bad)); raise SystemExit(1)
print('all agent names match filenames')
PY
```

## Count Updates

When adding or deleting agents/skills, update every visible count:

- `README.md` top repo inventory
- `README.md` agents section
- `docs/onboarding.md` tree
- `docs/onboarding.md` agent/skill headings
- any grouped category count affected by the change

Do not guess counts. Compute them from the filesystem and then patch docs.

## Common Traps

- Leaving stale names in `README.md`, `CLAUDE.md`, `docs/onboarding.md`, or `docs/service-index.md`.
- Updating `.claude/agents` but forgetting to regenerate `.codex/agents`.
- Adding `model` to Codex TOML. Codex adapters should omit model-specific Claude settings.
- Tracking generated `.codex/` or `.agents/` content.
- Duplicating full instructions into `AGENTS.md`; root `AGENTS.md` should stay a pointer to `CLAUDE.md`.
- Treating nested platform repos as root repo content. `platform/`, `platform-new/`, and `platform-next/` are local workspace clones and should remain ignored except tracked pointer READMEs.
