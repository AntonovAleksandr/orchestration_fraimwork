# 08 — Master Data Sync & Financial Reporting

**Value Stream:** VS-7 (Master Data Sync)  
**Главные системы:** Integration (cron-tasks + Kafka daemons) ↔ ENSI / OMS / OTS / 1C-ECOM / 1C-CBR / 1C-RETAIL / DWH / ATOL  
**Источник:** [`source/integration-processes.md`](source/integration-processes.md) разделы BP-INT-10..14, 22..32  
**Confluence:** разделы 3, 13 в `source/confluence-findings.md`

---

## Цель

Поддерживать единое состояние мастер-данных (стоки, цены, юр.лица, продукты, статусы заказов) между **e-commerce платформой** и **корпоративными ERP/POS-системами**. Финансовая отчётность и фискализация.

---

## Перечень процессов

### Outbound (наружу из OMS/ENSI)

| ID | Что | Триггер | Получатель |
|---|---|---|---|
| BP-INT-10 | Order status sync | cron | DWH |
| BP-INT-11 | Full order export | cron | DWH |
| BP-INT-12 | Reconciliation (ecom & cbr) | cron | DWH compare |
| BP-INT-13 | Order export to OTS / 1C-ECOM / 1C-CBR | service-side | OTS, 1C |
| BP-INT-14 | ATOL фискализация (батч) | cron | ATOL / ОФД |

### Inbound (внутрь, в ENSI/OMS)

| ID | Что | Триггер | Источник |
|---|---|---|---|
| BP-INT-22 | Pickup-points cache rebuild | cron | carriers API (CDEK/5post/…) |
| BP-INT-24 | Stock notification poll | cron | OMS (poll) → consumers |
| BP-INT-25 | Stock transfer OTS ↔ OMS (init + delta) | cron | OTS |
| BP-INT-26 | Stock transfer CB-1C-Retail (init + auto + retry) | cron | 1C-Retail |
| BP-INT-27 | Stock delta daemon (dormant) | — | — |
| BP-INT-28 | Business-unit Kafka daemon | Kafka | OMS / 1C |
| BP-INT-29 | Product Kafka daemon | Kafka | OMS / 1C |
| BP-INT-30 | Order status Kafka daemon (OTS → OMS) | Kafka | OTS |
| BP-INT-31 | Order message Kafka daemon | Kafka | OTS |
| BP-INT-32 | Event dispatcher Kafka daemon (dormant) | Kafka | — |

---

## Карта систем мастер-данных

```
                                 ┌─────────────────────────────┐
                                 │   1C-RETAIL (магазины)      │
                                 │     • stock per shop        │
                                 │     • loyalty / cards       │
                                 └───────┬──────────┬──────────┘
                                         │          │
                       BP-INT-26 (cron)  │          │ XML-API
                                         ▼          │ (BP-CUS-04)
                                  ┌──────────────────────┐
                                  │  Integration         │
                                  │  (cron + daemons)    │
                                  └──┬───────────────┬───┘
                                     │               │
                  BP-INT-25 (cron)   │               │ BP-INT-30 daemon
                                     ▼               ▼
                              ┌─────────┐      ┌────────┐
                              │   OTS   │      │  OMS   │
                              │ tracking│      │        │
                              └────┬────┘      └────────┘
                                   │ BP-INT-24 (cron poll, stock)
                                   ▼
                                  ENSI offers + catalog-cache

   1C-ECOM (заказы)  ◀── BP-INT-13 ──   ┐
   1C-CBR  (бухгалтерия) ◀── BP-INT-13 ─┤
   DWH                  ◀── BP-INT-10/11/12 ─ Integration cron
   ATOL OFD             ◀── BP-INT-14 ──┘
```

---

## Outbound к DWH и финансам

### BP-INT-10 — Order status sync (DWH)

Cron: каждые N минут опрашивает OMS на изменённые статусы → шлёт батчем в DWH.

### BP-INT-11 — Full order export (DWH)

Cron (раз в день): полная выгрузка заказов (для аналитических нужд). Тяжёлая операция, обычно ночью.

### BP-INT-12 — Reconciliation (ecom & cbr)

Cron сверяет два среза в DWH:
- `ecom`-таблица (наш срез заказов),
- `cbr`-таблица (бухгалтерский срез).

Если расхождения — алерт в OPSEC.

### BP-INT-13 — Export to OTS / 1C-ECOM / 1C-CBR

**Service-side** (вызывается из других процессов, не cron). При **финализации** заказа (releaseProcess в OMS) триггерится экспорт в:
- **OTS** (Order Tracking System) — оперативная база статусов для магазинов;
- **1C-ECOM** — бухгалтерский учёт e-commerce заказов;
- **1C-CBR** — корпоративная бухгалтерия.

### BP-INT-14 — ATOL фискализация (батч)

Cron собирает чеки за период и грузит в ATOL Online → ОФД → налоговая.

**Quirk:** см. quirk в `05-payment.md` — фискализация выглядит как батч, а не real-time. Возможно, real-time реализован отдельно, нужно проверить.

---

## Inbound — стоки

Самая критичная часть: **остатки** идут из 5+ источников и должны сойтись в одну истину.

### BP-INT-24 — Stock notification poll (OMS → consumers)

Cron опрашивает OMS на резервы/изменения → пушит во внутренних consumers (ENSI offers и др.).

### BP-INT-25 — OTS ↔ OMS (init + delta)

Cron-задачи:
- **Init** — полная синхронизация (раз в сутки / при перезагрузке).
- **Delta** — инкрементальный.

Источник правды для OMS Stock на оперативные изменения.

### BP-INT-26 — CB-1C-Retail (init + auto + retry)

Три варианта:
- **Init** — полная.
- **Auto** — периодический инкрементальный.
- **Retry** — повтор failed.

Источник правды для физических остатков в магазинах.

### BP-INT-27 — Stock delta daemon

**Dormant** — не запущен (см. quirk в `source/integration-processes.md`).

### Quirks стоков

- **Несколько источников** (1С-Retail, OTS, OMS) — конкуренция между ними; правила приоритета неочевидны.
- При расхождениях overselling возможен (см. BP-OMS-10 в `06-fulfillment-and-delivery.md`).
- Open question: какой источник — мастер для **доступности на витрине**?

---

## Inbound — справочники

### BP-INT-28 — Business-units (склады, магазины, юр.лица)

Persistent Kafka daemon, забирает из ENSI `units/bu` или 1С обновления справочника business-units → пишет в OMS / OTS.

### BP-INT-29 — Products (карточки товаров)

Persistent Kafka daemon, синхронизирует базовые product-данные в OMS (нужно ему для отгрузки, фильтрации).

### Quirks

- **Hardcoded tenant** в нескольких daemon'ах — мульти-тенантность не поддерживается.

---

## Inbound — статусы

### BP-INT-30 — Order status (OTS → OMS)

Kafka daemon. Когда магазин в OTS меняет статус (например, «выдан»), событие летит в Kafka → daemon забирает → пишет в OMS.

### BP-INT-31 — Order message

Канал текстовых сообщений по заказу (комментарии, …) → пишутся в OMS.

### BP-INT-32 — Event dispatcher (dormant)

Старый daemon, **autoStartup=false**. Open question: можно удалить?

---

## Inbound — pickup-points

### BP-INT-22 — Pickup-points rebuild

Cron ходит во все carriers (CDEK, 5post, RPost, …) и собирает список ПВЗ → пишет в локальную БД Integration → отдаёт UI на pre-checkout (см. `03-browse-cart-precheckout.md` BP-CHK-PRE-05).

**Quirk:** при устаревании кеша — ПВЗ может исчезнуть из UI или, наоборот, доставка уйдёт в «несуществующую» точку.

---

## Recap quirks

1. **Dormant daemons** (BP-INT-27, BP-INT-32) — мёртвый код, сбивающий новых инженеров с толку.
2. **Hardcoded tenant** в daemon'ах.
3. **Stocks: несколько источников правды**.
4. **ATOL — батч**, не real-time (если только нет отдельной real-time линии).
5. **Recon (BP-INT-12) шумит** — частые расхождения, мало правил автомата.
6. **Sync HTTP в BP-INT-13** — при недоступности 1С → блокирует release заказа.

---

## Конфигурация cron

Все cron'ы запускаются в **`integration-cron`** deploy (отдельный pod от `integration-api`). Расписание — в `containers/cron/crontab`.

---

## Confluence

| Тема | Confluence |
|---|---|
| Стоки / резервирование | разрозненно |
| BP / Заказы / DWH | `60696260` поддерево |
| ATOL / Фискализация | внутренние страницы |

См. [`source/confluence-findings.md`](source/confluence-findings.md) разделы 3, 13.

---

**Дата создания:** 2026-05-16  
**Поддерживается:** команда Integration + DWH + финансы
