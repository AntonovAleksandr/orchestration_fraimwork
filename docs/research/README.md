# Research Findings

Краткие выводы cross-system расследований — в **git** (`docs/research/`). Длинные autopsy — в **`logs/research/`** (gitignored). Описание каталога: tracked [`logs/README.md`](../../logs/README.md).

## Naming (tracked summary)

`docs/research/<YYYY-MM-DD>-<topic>.md` — **один файл на тему**, ~1–2 экрана: Summary, приоритеты, traceId, «куда копать», ссылки на BP.

Пример: [`2026-05-20-checkout-order-creation.md`](2026-05-20-checkout-order-creation.md) — чекаут / commit / P0.

## Naming (local long-form)

`logs/research/<YYYY-MM-DD>-<topic>.md` — полный разбор. **Не коммитить** (gitignored). См. tracked [`logs/README.md`](../../logs/README.md).

## Структура summary (tracked)

```markdown
# <topic>

**Дата:** YYYY-MM-DD · **Статус:** prod ref / ограничения

## Summary (1 абзац)

## Приоритеты / findings (таблица)

## Логи / инструменты (коротко)

## Дальше (numbered list)

**Локально:** logs/research/…
```

## Когда что писать

| Объём | Куда |
|-------|------|
| Итог для команды, ссылки на trace | `docs/research/` — **обновить или один файл на тему** |
| > ~150 строк, autopsy, duplicate BP | `logs/research/` |
| L1 процессы | `docs/bp/` — не дублировать research |

## Методологии (переиспользуемые)

Общие методологии (оценка сроков, дисциплина research и т.п.) живут в [`docs/methodologies/`](../methodologies/README.md) —
источник истины. В проектах **ссылаться** на них, не копировать. Пример: оценка сроков под AI-разработку —
[`docs/methodologies/ai-accelerated-estimation.md`](../methodologies/ai-accelerated-estimation.md).

## Агенты

`*-researcher`: итог в `docs/research/`; детали — `logs/research/`. Сначала grep `docs/research/` по теме; не плодить новые md без необходимости — **дополнять существующий summary**.

## Лицензия

Внутренние данные Gloria Jeans. Не публиковать.
