# Карта бизнес-процессов GJ E-commerce

**Назначение:** единый каталог сквозных бизнес-процессов e-commerce платформы Gloria Jeans — от заведения карточки товара до доставки и возврата. Документ привязан к коду 5 платформ (ENSI / Integration / OMS / Site / Mobile) и параллельно ссылается на бизнес-описания в Confluence.

**Аудитория:** product, аналитики, инженеры всех платформ, новые сотрудники, архитекторы.

> Если ты пришёл сюда **что-то понять или починить** — открой соответствующий L1-файл (см. ниже) и далее иди по ссылкам в `source/` или Confluence.

---

## Методология

Структурируем процессы по трём уровням (классическая иерархия APQC PCF / eTOM):

- **L0 — Value Streams** (потоки ценности) — 7 сквозных направлений жизненного цикла.
- **L1 — Major Processes** (главные процессы) — основные бизнес-процессы внутри каждого потока. Они каталогизируются в файлах `01-..08-..` этой папки.
- **L2 — Sub-processes / Tasks** (подпроцессы) — конкретные технические реализации. Живут в `source/<platform>-processes.md` (детальные dump'ы по платформам) и в коде сервисов.

Каждый L1-процесс имеет уникальный ID:

| Префикс | Домен | Документ |
|---|---|---|
| `BP-CAT-*` | Catalog (PIM, рекомендации, фиды) | `01-product-content-lifecycle.md` |
| `BP-OFF-*` | Pricing / Offers / Stock (ENSI) | `01-product-content-lifecycle.md` |
| `BP-CUS-*` | Customer lifecycle (регистрация, auth, профиль) | `02-customer-lifecycle.md` |
| `BP-BSK-*` | Basket / Cart | `03-browse-cart-precheckout.md` |
| `BP-BFF-*` | BFF / Storefront API | `03-browse-cart-precheckout.md` |
| `BP-INT-*` | Integration Service (BFF-routing) | разнесены по 03–08 |
| `BP-OMS-*` | OMS / Camunda BPMN | 04–07 |

> **Принцип:** один процесс — один ID. Имя процесса берётся **из домена**, а не из сервиса. Например, «оформление заказа» — это `BP-CHK-*`, даже если фактически работают Integration + OMS + ENSI.

---

## L0 — Value Streams (потоки ценности)

```
┌────────────────────────────────────────────────────────────────────────┐
│ VS-1  Product to Shelf  (товар на полку)                               │
│  заведение карточки → фид → catalog-cache → выдача на витрине          │
├────────────────────────────────────────────────────────────────────────┤
│ VS-2  Customer Acquisition  (привлечение и идентификация клиента)      │
│  регистрация → SMS OTP → профиль → адреса → бонусная карта             │
├────────────────────────────────────────────────────────────────────────┤
│ VS-3  Browse to Cart  (просмотр → корзина)                             │
│  каталог → карточка → корзина → промокод → pre-checkout (расчёт)       │
├────────────────────────────────────────────────────────────────────────┤
│ VS-4  Order to Cash  (создание заказа → оплата)                        │
│  submit → split-shipment → /order/create в OMS → платёж → confirm      │
├────────────────────────────────────────────────────────────────────────┤
│ VS-5  Order to Delivery  (фулфилмент → доставка)                       │
│  резервирование → picking → carrier dispatch → tracking → выдача       │
├────────────────────────────────────────────────────────────────────────┤
│ VS-6  Post-purchase  (отмены, возвраты, коммуникация)                  │
│  статусы → notifications → returns → refunds → loyalty compensation    │
├────────────────────────────────────────────────────────────────────────┤
│ VS-7  Master Data Sync  (синхронизация мастер-данных и финреп)         │
│  OTS ↔ 1C ↔ Retail ↔ OMS ↔ DWH; ATOL фискализация; recon              │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Архитектурный контур

```
   Site (Angular 20)          Mobile (React Native 0.74)
        │                            │
        └──────── HTTP ──────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
  ┌──────────────────┐  ┌────────────────────┐
  │ ENSI             │  │ Integration        │
  │ customers-api-web│  │ Service (Lumen)    │
  │  (BFF, OpenAPI)  │  │  pre-checkout      │
  │                  │  │  /order/create     │
  └──────┬───────────┘  │  cron-exports      │
         │              │  Kafka-daemons     │
         ▼              └────────┬───────────┘
  ┌────────────────────┐         │
  │ ENSI core (~25)    │         │
  │  • PIM             │         │
  │  • offers / -go    │         │
  │  • catalog-cache   │         ▼
  │  • baskets         │   ┌─────────────────┐
  │  • customers       │   │ OMS / Starfish  │
  │  • customer-auth   │   │ (Spring Boot +  │
  │  • bu              │   │  Camunda BPM +  │
  │  • cms             │   │  Go logistics)  │
  │  • cdn-adapter     │   │  • Order/Stock  │
  │  • feed            │   │  • Delivery     │
  │  • audit           │   │  • Carriers (×17)│
  │  • event-dispatcher│   │  • pay-service  │
  └────────────────────┘   │  • camunda-     │
                           │     worker      │
                           └────────┬────────┘
                                    │
                            ┌───────┴────────┐
                            ▼                ▼
                       Carriers           1C / OTS / DWH / ATOL
                       CDEK, 5post,
                       RPost, DPD, …
```

Полный сервис-реестр и стек — `docs/service-index.md` + `CLAUDE.md`.

---

## Содержание

| # | Файл | Поток L0 | Главные процессы |
|---|---|---|---|
| 01 | [01-product-content-lifecycle.md](01-product-content-lifecycle.md) | VS-1 + VS-7 | Заведение карточки, импорты, фиды, цены, стоки, акции |
| 02 | [02-customer-lifecycle.md](02-customer-lifecycle.md) | VS-2 | Регистрация, OTP, login, профиль, адреса, бонусная карта, 152-ФЗ |
| 03 | [03-browse-cart-precheckout.md](03-browse-cart-precheckout.md) | VS-3 | Витрина, корзина, промокод, delivery quote / split-shipment / payment options |
| 04 | [04-checkout-order-creation.md](04-checkout-order-creation.md) | VS-4 | Submit, валидация, V1↔V4 пути Integration, `/order/create` в OMS, `confirmationProcess.bpmn` |
| 05 | [05-payment.md](05-payment.md) | VS-4 | YooKassa, СБП, Подели, hold-then-capture, refund, ATOL |
| 06 | [06-fulfillment-and-delivery.md](06-fulfillment-and-delivery.md) | VS-5 | OMS lifecycle, picking, dispatch, carriers (CDEK/5post/RPost/Yandex/IML+), tracking |
| 07 | [07-post-order-and-comms.md](07-post-order-and-comms.md) | VS-6 | Статусы, notifications (SMS/email/push), отмены, возвраты, loyalty return |
| 08 | [08-master-data-sync.md](08-master-data-sync.md) | VS-7 | Стоки (OTS/CB-1C-Retail), цены, DWH export, recon, ATOL fiscalization, business-units |
| — | [e2e-happy-path.md](e2e-happy-path.md) | — | Сквозной сценарий «купить футболку самовывозом» по системам |
| — | [glossary.md](glossary.md) | — | Глоссарий терминов |

---

## Источники

### Сырые исследования по платформам (`source/`)

Глубокие выгрузки кода и поведения — на них опираются финальные L1-файлы.

- [`source/ensi-processes.md`](source/ensi-processes.md) (1011 строк, 28 процессов) — ENSI (PIM, offers, baskets, customers, BFF, audit, cdn-adapter, event-dispatcher)
- [`source/integration-processes.md`](source/integration-processes.md) (768 строк, 36 процессов) — Integration Service (V1/V4 pre-checkout, order submit, payment, cron, Kafka-daemons)
- [`source/oms-processes.md`](source/oms-processes.md) (780 строк, 16 процессов + 16 BPMN) — OMS / Starfish (Camunda BPMN, fulfillment, carriers, pay-service)
- [`source/confluence-findings.md`](source/confluence-findings.md) (773 строки) — что есть в Confluence (BP-1..5, OMS-3..8, TS.1..10, функциональная нарезка, gaps)

### Существующие артефакты

- [`../research/2026-05-16-checkout-flow.md`](../research/2026-05-16-checkout-flow.md) (668 строк) — глубокое расследование pre-checkout / interval-id non-idempotency (5 ресёрчеров параллельно). Опорный артефакт для L1 03–04.
- [`../service-index.md`](../service-index.md) — реестр всех сервисов с владельцами и стеком.
- [`../architecture/`](../architecture/) — ADR (когда появятся).

### Confluence (главные индексы)

- **BP-1..BP-5 серия** (родитель `60696260`) — официальная разбивка e-commerce по доменам.
- **OMS-3..OMS-8 серия** — детальный чекаут, модель заказа, статусы, шаблоны уведомлений.
- **Функциональная нарезка** (`60689793`) — 26 нарезок по сервисам.
- **TS.1..TS.10** — test-scenario серия (2025–2026) по MobApp.
- **L1 БП Ecom_L1_20241001** — pptx-файл, прикреплён к странице `130123785`. Текущий снимок L1 верхнеуровневого пайплайна (октябрь 2024).

Полная сводка с ID-страницами — в [`source/confluence-findings.md`](source/confluence-findings.md).

---

## Соглашения

- **Sequence-диаграммы** — Mermaid. Рендерятся прямо в GitLab/GitHub/Confluence (export).
- **Имена сущностей** — на английском, как в коде (`Order`, `Shipping`, `Item`). Имена бизнес-объектов — на русском (заказ, отгрузка).
- **Ссылки на код** — относительный путь от корня workspace: `platform/<system>/...:<line>`.
- **Известные quirks** — выносим в отдельный блок процесса. Не прячем.
- **Cross-platform** — если процесс пересекает 3+ системы, описываем «оркестратор» (тот, кто инициирует и видит весь flow), остальные участники указываются как `delegates: [...]`.

---

## Поддержание

При **любых изменениях бизнес-логики**, затрагивающих процесс из этого каталога:

1. Обновить соответствующий L1-файл и проставить дату в блоке «Изменено».
2. Если меняется BPMN-процесс в OMS — обновить `06-fulfillment-and-delivery.md` (раздел с диаграммой) и `source/oms-processes.md`.
3. Если меняются route'ы Integration — обновить `03–05.md` плюс `source/integration-processes.md`.
4. Если появляется новый процесс — добавить в L0-таблицу + создать раздел в подходящем L1.

ADR / архитектурные решения по новому процессу — кладём в `docs/architecture/`.

---

**Версия документа:** 1.0  
**Создано:** 2026-05-16  
**Поддерживается:** командой архитектуры GJ + владельцами доменов
