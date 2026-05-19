# Project rules (`.claude/rules/`)

Канонические rules в формате `.mdc`. Cursor подключает их через симлинки:

```
.cursor/rules/*.mdc  →  ../../.claude/rules/*.mdc
```

**Не дублируйте** текст в `.cursor/rules/` — меняйте только файлы здесь.

Полные соглашения (agent-agnostic, что куда класть, Claude vs Cursor) — в [README.md § Правила для агентов](../../README.md#agent-rules).

`CLAUDE.md` — основная карта workspace; `rules/` — короткие обязательные ограничения и таблица адаптеров IDE.
