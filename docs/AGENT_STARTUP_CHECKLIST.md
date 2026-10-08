# Agent Startup Checklist

Quick reference for integrating `git-health-check.sh` into Claude Code agents.

## Quick Integration Patterns

### Pattern 1: Agent Script (Recommended)

For agents that execute Bash scripts:

```bash
#!/bin/bash
set -euo pipefail
PROJ_DIR="${CLAUDE_PROJECT_DIR:-.}"

# Git health check at startup
"$PROJ_DIR/scripts/gj/git-health-check.sh" --unshallow --verbose || exit 1

# Your agent logic here
echo "Agent ready, git state verified"
```

### Pattern 2: Agent Frontmatter (Instructions Block)

For agents defined in `.claude/agents/*.md`:

```markdown
---
name: example-agent
description: Does something with git operations
instructions: |
  Git health verification is required before starting.
  
  Run this first:
  ```bash
  "$CLAUDE_PROJECT_DIR/scripts/gj/git-health-check.sh" --unshallow --verbose
  ```
  
  If this fails, abort the task and report the error.
  
  [Rest of your agent instructions...]
---
```

### Pattern 3: Automatic Hook (Optional)

Enable automatic verification for all prompts:

```bash
scripts/gj/install-hooks.sh
```

This adds to `.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "[ -f \"$CLAUDE_PROJECT_DIR/scripts/gj/git-health-check.sh\" ] && bash \"$CLAUDE_PROJECT_DIR/scripts/gj/git-health-check.sh\" --unshallow --verbose || true",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

## Usage Reference

| Command | Purpose |
|---------|---------|
| `scripts/gj/git-health-check.sh` | Check repo health (silent if OK, exit 0) |
| `scripts/gj/git-health-check.sh --verbose` | Same + report all checks |
| `scripts/gj/git-health-check.sh --unshallow` | Check + auto-expand shallow clones |
| `scripts/gj/git-health-check.sh --unshallow --verbose` | Check + expand + detailed report |
| `scripts/gj/git-health-check.sh <path>` | Check specific directory |

## Exit Codes

- `0`: Repository healthy (or successfully fixed with `--unshallow`)
- `1`: Repository unhealthy (no .git, no origin, unshallow failed)
- `2`: Invalid argument parsing

## When to Use `--unshallow`

Use `--unshallow` when your agent needs accurate git history:

- ✓ Using `git merge-base` to find common ancestor
- ✓ Checking `ahead-behind` commits vs main branch
- ✓ Running `git cherry-pick` or `git rebase`
- ✓ Analyzing commit history graphs
- ✓ Working with code in `platform/*/` (shallow by default)

Skip `--unshallow` when:

- Quickly checking if .git exists and origin is set
- Performing operations that don't need full history
- Running in resource-constrained environments (though unshallow is usually still faster than mistakes)

## Troubleshooting

### "Exit code 1: .git directory FAIL"

You're outside a git repository. Check:

```bash
cd /Users/user/orca/workspaces/development-platform/betta
git rev-parse --show-toplevel
```

### "origin remote: FAIL"

Missing remote configuration. Fix:

```bash
git remote add origin https://gitlab.gloria.aaanet.ru/path/to/repo.git
git fetch origin
```

### "unshallow: FAIL"

Possible network issue or corrupted repo. Retry and check:

```bash
git remote -v
ping gitlab.gloria.aaanet.ru
```

## Documentation

Full integration guide: `/Users/user/orca/workspaces/development-platform/betta/docs/agent-git-health-check.md`

Script location: `/Users/user/orca/workspaces/development-platform/betta/scripts/gj/git-health-check.sh`
