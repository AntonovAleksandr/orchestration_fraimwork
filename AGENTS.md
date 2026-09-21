# AGENTS.md

See [CLAUDE.md](./CLAUDE.md) for repository instructions.

`$WORKSPACE` in docs means the local repository root. Do not add developer-specific absolute paths to tracked files.

## Codex

- Canonical workspace instructions live in `CLAUDE.md`.
- Canonical agents and skills live in `.claude/agents/` and `.claude/skills/`.
- Codex uses generated local adapters: `.codex/agents/*.toml` and `.agents/skills/*`.
- Do not edit `.codex/` or `.agents/` by hand; edit `.claude/` and run `./scripts/generate-codex-adapters.py`.
- For GitLab MR reviews, follow the canonical skill-routing rule in `CLAUDE.md`; do not define a parallel review workflow here.
- Use named subagents when the user explicitly asks for delegation/parallel work or when a task naturally needs isolated specialist investigation.
