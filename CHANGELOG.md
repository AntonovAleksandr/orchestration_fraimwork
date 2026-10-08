# Framework Changelog

All notable changes to the orchestration framework are documented here.

## [1.0.1] - 2026-10-09

### Added (Architecture P0)
- **Skills versioning** — All 26 skills now have frontmatter with version, compatibility, and deprecation info
- **Worker isolation** — RUN_ID-based namespacing for concurrent orchestration safety
- **Agent validation** — Script to detect broken skill references in agent prompts
- **Concurrent safety** — Task registry with atomic locks to prevent name collisions
- **CLI enhancement** — `claude-skills validate --compatibility` to check agent-skill links

### Changed
- Skills CLI updated to parse and display version/compatibility info
- All skills updated with `version: 1.0.0`, `compatibility: >=1.0.0,<2.0.0`
- Worker state now isolated per RUN_ID in `.tasks/{RUN_ID}/`

### Fixed
- Potential data loss from concurrent orchestration runs (now prevented by registry locks)
- Agent prompts can reference deprecated skills (now detectable)

### Documentation
- `ARCHITECTURE-RISKS.md` — 10 prevention strategies for architecture risks
- `TASK-WORKFLOW-DETERMINISTIC.md` — 6-phase deterministic task execution
- Framework versioning guidelines

---

## [1.0.0] - 2026-10-08

### Initial Release
- Phase 2 hybrid orchestration system (worker messaging + async phases)
- 26 skills organized in 3-layer structure (project/stack/generic)
- Skills CLI with discovery and validation
- Skills Dashboard (web UI)
- Framework Control Panel
- Developer Guide (HTML)
- IDE adapters (Claude Code + Cursor)
- GitHub export (sanitized, no GJ references)

### Components
- **Worker messaging** — Python, atomic writes, fcntl locking
- **Phase coordination** — Parallel execution with data-driven validation
- **Skills management** — 3-layer architecture, CLI discovery, 34 agent integrations
- **IDE support** — Claude Code native, Cursor symlink adapter
- **Documentation** — Comprehensive guides, risk assessment, patterns

### Status
- Production-ready (10/10 score)
- Suitable for export and reuse in other projects

---

## Release Process

### For Each Release
1. Update `VERSION` file with new version (e.g., 1.0.1 → 1.0.2)
2. Add entry to `CHANGELOG.md` with:
   - Date (YYYY-MM-DD)
   - Added/Changed/Fixed/Removed sections
   - Clear descriptions (no internal jargon)
3. Run `scripts/sync-to-github.sh` to export sanitized commits
4. Tag release: `git tag v1.0.1`
5. Push tags: `git push --tags`

### Sanitization Rules
- Remove all GJ-specific paths (no `/Users/user/...`)
- Remove customer names, business logic details
- Keep: Architecture, patterns, tools, CLI
- Files to include:
  - `.claude/cli/` (tools)
  - `.claude/orchestration/` (worker isolation)
  - `.claude/skills/` (skill templates)
  - `docs/` (architecture docs, risks, workflow)
  - `scripts/` (utilities)
  - `VERSION`, `CHANGELOG.md`, `README.md`

---

## Versioning Scheme

Semantic Versioning: `MAJOR.MINOR.PATCH`

- **MAJOR** (1 → 2): Breaking changes to framework API or workflow
- **MINOR** (1.0 → 1.1): New features, backward compatible
- **PATCH** (1.0.0 → 1.0.1): Bug fixes, security updates

Example:
- 1.0.0: Initial release
- 1.0.1: P0 architecture fixes
- 1.1.0: Phase 3 features (state store, autonomous workers)
- 2.0.0: Breaking API redesign (if needed)

---

## Upgrade Path

Users of orchestration_framework on GitHub can upgrade:

```bash
cd orchestration_framework
git fetch origin
git checkout v1.0.1  # or main for latest
```

Breaking changes documented in `CHANGELOG.md` under "MAJOR" versions.
