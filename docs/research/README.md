# Research Findings

Per-investigation findings produced by `*-researcher` агентами (`ensi-researcher`, `oms-researcher`, `integration-researcher`, `site-researcher`, `mobile-researcher`).

## Naming

Файлы — `<YYYY-MM-DD>-<topic>.md`:
- `2026-05-16-checkout-fails-with-promo.md`
- `2026-05-20-stock-drift-between-ensi-and-oms.md`

## Структура findings документа

```markdown
# <topic>

**Investigated by:** <list of researchers used (e.g. integration-researcher → ensi-researcher → oms-researcher)>
**Date:** YYYY-MM-DD

## Question
<the exact thing being investigated>

## Summary
<TL;DR — 1-2 sentences>

## Cross-system flow
<ASCII или текстовая диаграмма куда заходит запрос/данные>

## Evidence trail
<numbered list of file:line, commits, MRs, logs, Jira>

## Workarounds / legacy in play
<list of non-obvious code patterns relevant to the issue>

## Root cause
<the actual answer>

## Suggested next steps
<actions, with owner agent indicated>
```

## Когда сохранять

- Если research занял > 5 минут или включал > 1 систему — сохранять
- Если research быстрый одно-системный — может остаться в чате
- Финдинги переиспользуются: при похожей проблеме в будущем — researcher сначала grep'ит `docs/research/`

## Лицензия

Внутренние данные Gloria Jeans. Не публиковать.
