# logs/ — локальные артефакты

**Этот README в git.** Содержимое `logs/research/` и прочие dump'ы — **не коммитить** (см. `.gitignore`: `logs/*`, исключение только `logs/README.md`).

## Назначение

Длинные расследования, сырые заметки по логам, autopsy, каталоги exceptions — то, что не нужно в `docs/research/`.

## Структура

| Путь | В git |
|------|--------|
| `logs/README.md` | да |
| `logs/research/*.md` | нет (локально) |

## Checkout / order creation

| Артефакт | Где |
|----------|-----|
| Сводка для команды | [`docs/research/2026-05-20-checkout-order-creation.md`](../docs/research/2026-05-20-checkout-order-creation.md) |
| Длинные разборы (autopsy, errors catalog, log dump) | `logs/research/2026-05-16-checkout-flow.md`, `2026-05-20-order-creation-*.md` |

Новые длинные md кладите в `logs/research/`; итог обновляйте в `docs/research/`.
