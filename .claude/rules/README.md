# Project rules (`.claude/rules/`)

Канонические rules в формате `.mdc`. Cursor подключает их через симлинки:

```
.cursor/rules/*.mdc  →  ../../.claude/rules/*.mdc
```

**Не дублируйте** текст в `.cursor/rules/` — меняйте только файлы здесь.

Полные соглашения (agent-agnostic, что куда класть, Claude vs Cursor) — в [README.md § Правила для агентов](../../README.md#agent-rules).

`CLAUDE.md` — основная карта workspace; `rules/` — короткие обязательные ограничения и таблица адаптеров IDE.

## Файлы в этой папке

| Файл | Назначение |
|------|-----------|
| `code-comments.md` | Правила для комментариев в коде (не для review comments) |
| **`code-review-comments-format.md`** | **Обязательный формат для комментариев code review (inline + separate notes)** |
| `local-code-first.mdc` | Приоритет локальной разработки над CloudIDEs |
| `workspace.mdc` | Рабочие пространства и окружение |

## Интеграция code-review-comments-format

**Все агенты code-review ДОЛЖНЫ следовать** `.claude/rules/code-review-comments-format.md`:

- Используется: `ensi-gitlab-mr-review`, `site-gitlab-mr-review`, `integration-gitlab-mr-review`, `mobile-gitlab-mr-review`, `oms-gitlab-mr-review`, `gloriaots-*-review`
- Валидация: `./.claude/scripts/review_validate.sh <comment.md>`
- Интеграция в skills: см. `.claude/guides/code-review-comments-checklist.md`
- Обязательные типы: `[MUST]`, `[SHOULD]`, `[NIT]`, `[SECURITY]`, `[PERF]`, `[TEST]`
