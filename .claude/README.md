# `.claude/` — canonical agent layer

Единый источник правды для **Claude Code** и **Cursor**. В git коммитим только содержимое репозитория GJ, не вывод инсталляторов.

## В git (коммитим)

| Путь | Назначение |
|------|------------|
| `agents/` | 24 сабагента (`ensi-navigator`, `gloriaots-engineer`, …) — Cursor: `Task(subagent_type=…)` |
| `skills/` | 25 доменных скилла GJ (`ensi-*`, `gloriaots-*`, `gj-buddy-*`, …) — подхватываются обоими IDE |
| `rules/` | Проектные rules (`.mdc`) — в Cursor через симлинки в `.cursor/rules/` |

Корневой **`CLAUDE.md`** — главная карта workspace (читается Claude Code и Cursor).

## Локально, не в git (регенерировать после clone)

| Путь | Как восстановить |
|------|------------------|
| `commands/gsd/`, `get-shit-done/`, `hooks/`, `settings.json` | `npx get-shit-done-cc@latest --claude --local --profile=core` |
| `settings.local.json` | личные allow-листы Claude Code |

Опционально для GSD в Cursor (skills `gsd-*`):  
`npx get-shit-done-cc@latest --cursor --local --profile=core` → пишет в **`.cursor/`** (тоже не в git).

## Superpowers

Методология [obra/superpowers](https://github.com/obra/superpowers) — **не** в `.claude/skills/`. Ставится плагином **per harness** (Claude Code → `~/.claude/plugins/`, Cursor → marketplace `/add-plugin superpowers`, Codex → `/plugins`, …). См. [README → Superpowers](../README.md#superpowers-install).
