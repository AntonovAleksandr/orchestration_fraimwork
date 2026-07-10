# Реферальная программа ИМ — мастер-план исследования

**Цель:** для [`OPSOMN001-743`](https://jira.gloria-jeans.ru/browse/OPSOMN001-743) — по доменам сверить **as-is**
(промокоды APP20, CouponTranslate, лояльность, OMS-статусы) с **требованиями** (`00-requirements.md`),
зафиксировать **разрывы**, спроектировать **to-be** и план внедрения.

**Эталонная механика скидки:** APP20 (одноразовый промокод, CouponTranslate, rollback при Cancelled/LOST).

> ⚠️ **Все стадии — research only.** Цель — as-is / to-be / gap / архитектурные развилки.
> Implementation начинается только после Stage 09 (synthesis) и явного решения заказчика.
> Сводка «какие системы и какие доработки» → [`systems-impact.md`](systems-impact.md).

---

## 1. Метод (каждая стадия)

Каждая стадия → `stages/stage-NN-<domain>.md` по `TEMPLATE-stage.md`:

1. **As-is** — код `platform/*`, Confluence/Jira, SELECT+LIMIT в БД, логи.
2. **To-be** — FR из `00-requirements.md`.
3. **Gap-матрица** — 🟢/🟡/🟠/🔴 + evidence.
4. **Ledger** — строки в `EVIDENCE-LEDGER.md`.
5. **Resume pointer** — что осталось.

### Правила

- Перед grep по `platform/*` — `./scripts/sync-platform-repos.sh <platform>`.
- Grep **скоупить** к конкретному репо (`integration/www`, `ensi/apps/orders/baskets`, …).
- Не путать HR «Приведи друга» (DEVFIN001) с ИМ-рефералкой.
- APP20 — reference, не duplicate scope.

---

## 2. Порядок стадий

| # | Стадия | Домен | Главный вопрос | FR |
|---|---|---|---|---|
| 00 | Setup / источники / ledger | — | База готова? | — |
| 01 | **APP20 as-is** (reference) | СС, baskets, ИС, OMS | Как работает одноразовый −20% сегодня? | FR-03, FR-05 |
| 02 | **Уникальный промокод + referrer↔referee** | ENSI customers, offers, Admin | Где генерировать/хранить код и связь? | FR-01, FR-02, Q2, Q6 |
| 03 | **Чекаут + канал web-only** | Integration, baskets, Site, Mobile | Как ограничить ИМ и не сломать МП? | FR-03 |
| 04 | **Триггер «выкуп»** | OMS, Camunda, DWH | Какой статус/событие = выкуп для FR-04? | FR-04, Q7 |
| 05 | **Отложенное начисление 500 бонусов** | ПЛ, СС, ИС cron/events | Cron +14d или event-driven? | FR-04, Q3 |
| 06 | **Отмена/возврат edge cases** | ИС, OMS, СС | Паритет с APP20 rollback + новые правила | FR-05 |
| 07 | **Frontend ЛК + шеринг** | Site (+ ECD) | UI блок, copy/share, лендинг? | FR-01, FR-08 |
| 08 | **Аналитика** | Site, Mobile, WA | События воронки | FR-07 |
| 09 | **Синтез** | — | To-be архитектура, roadmap, оценка | все |

> Stage 01 — фундамент (без понимания APP20 рефералку проектировать опасно).  
> Stage 05 — highest risk (отложенное начисление в ПЛ может не иметь готового паттерна).

---

## 3. MCP-плaybook

**Confluence (OMNIES):**

- `149781892` — Применение промокода (sequence diagram)
- `149756449` — Использование одноразового промокода (APP20 rollback)
- `130154031` — OPSOMN-12310 отмена трансляции APP20 в корзине
- `146506730` — Rollback при LOST/CANCELLED
- `130133718` — Сервер скидок: настройка промокодов
- CQL: `text ~ "APP20" AND space = OMNIES`

**Jira:**

- `OPSOMN001-743` — эпик/задача рефералки
- `OPSOMN-12294`, `OPSOMN-12310`, `OPSOMN-12554`, `OPSOMN-12764` — APP20
- `OPSOMN001-617` — регресс rollback APP20
- JQL: `project = OPSOMN001 AND key = OPSOMN001-743`

**Postgres (read-only):** `oms-awg-order-prod` (статусы выкупа), `ensi-gs-baskets-*`, `ensi-gs-customers-*`.

**Логи:** `integration-awg-new-logs-prod`, `logs-ensi-prod` — CouponTranslate, loyalty return.

**Код (локально):**

| Домен | Путь |
|---|---|
| Baskets / CouponTranslate | `platform/ensi/apps/orders/baskets` |
| Customers | `platform/ensi/apps/customers/customers` |
| Offers | `platform/ensi/apps/catalog/offers` |
| Integration promo/loyalty | `platform/integration/integration/www/app/Service/UserApi` |
| Site profile | `platform/site/gj-ng-front/libs/modules/profile` |
| OMS loyalty return | `platform/starfish24/core/Camunda`, BPMN `paymentFinalizationProcess` |

---

## 4. Progress tracker

- [x] Stage 00 — Setup / источники / requirements / ledger seed (2026-07-02)
- [ ] Stage 01 — APP20 as-is (reference)
- [ ] Stage 02 — Уникальный промокод + referrer↔referee
- [ ] Stage 03 — Чекаут + web-only
- [ ] Stage 04 — Триггер «выкуп»
- [ ] Stage 05 — Отложенное начисление бонусов
- [ ] Stage 06 — Отмена/возврат
- [ ] Stage 07 — Frontend ЛК
- [ ] Stage 08 — Аналитика
- [ ] Stage 09 — Синтез

### Resume pointer (текущая сессия)

**Следующий шаг:** Stage 01 — разобрать APP20 end-to-end (Confluence `149781892` + baskets `RegisterPromoCodeAction` + ИС `couponTranslate` + правила СС DS22).  
**Блокер sync:** `integration/integration` — dirty/untracked branch `release-26.07.1` (sync fail); код читается локально, но перед правками нужен clean pull.
