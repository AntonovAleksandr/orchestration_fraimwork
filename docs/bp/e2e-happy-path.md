# E2E Happy Path — «Купить футболку курьерской доставкой»

**Назначение:** показать **сквозной** путь данных по всем 5 системам на одном примере. Это **не** замена детальных L1-файлов; это **карта-навигатор**: для каждого шага есть ссылка, где смотреть подробности.

**Сценарий:** анонимный пользователь заходит на сайт, ищет футболку, добавляет в корзину, регистрируется, оформляет курьерскую доставку с оплатой картой, получает товар.

---

## Главные участники

```
User → Site (Angular) → ENSI customers-api-web → ENSI core
                       ↘ Integration → OMS → Camunda
                                              → Carrier (CDEK)
                                              → YooKassa
```

---

## Сквозная sequence-диаграмма

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant Site
    participant BFF as customers-api-web
    participant CC as catalog-cache
    participant BSK as baskets
    participant Auth as customer-auth
    participant Cus as customers
    participant Int as Integration
    participant OMS as OMS Order
    participant Cam as Camunda
    participant YK as YooKassa
    participant CDEK as CDEK

    Note over U,Site: ① Browse (см. 01, 03)
    U->>Site: главная
    Site->>BFF: GET catalog
    BFF->>CC: query
    CC-->>BFF: items
    BFF-->>Site: items

    Note over U,Site: ② Карточка → корзина
    U->>Site: «купить»
    Site->>BFF: POST /basket/items
    BFF->>BSK: add item
    BSK-->>BFF: basket state
    BFF-->>Site: basket

    Note over U,Auth: ③ Регистрация (см. 02)
    U->>Site: ввод телефона
    Site->>BFF: POST /auth/otp/request
    BFF->>Auth: request OTP
    Auth->>Auth: Devino SMS
    U->>Site: ввод кода
    Site->>BFF: POST /auth/otp/verify
    BFF->>Auth: verify
    Auth->>Cus: create Customer
    Auth-->>Site: tokens
    Note over BSK: корзина merge с серверной

    Note over U,Int: ④ Pre-checkout (см. 03)
    U->>Site: «Перейти к оформлению»
    Site->>Int: GET /general-data
    Int->>BFF: get basket + profile
    BFF->>BSK: read
    BFF->>Cus: read profile
    Int->>OMS: GET /delivery/intervals
    OMS-->>Int: inventories[]
    Int->>OMS: GET /payments/methods
    OMS-->>Int: methods[]
    Int-->>Site: aggregated data

    Note over U,OMS: ⑤ Submit (см. 04)
    U->>Site: «Оплатить»
    Site->>Int: POST /api/v2/checkout/order
    Int->>BFF: revalidate basket
    Int->>Int: build OMS DTO (V4)
    Int->>OMS: POST /order/create
    OMS->>OMS: validate + persist
    OMS->>Cam: start confirmationProcess
    Cam->>OMS: reserve stock (Stock service)
    OMS-->>Int: orderId, paymentUrl
    Int-->>Site: orderId, paymentUrl

    Note over U,YK: ⑥ Платёж (см. 05)
    Site->>U: redirect → YooKassa
    U->>YK: вводит карту
    YK->>OMS: webhook payment.succeeded
    OMS->>Cam: signal paymentProcess
    YK-->>U: thank-you redirect

    Note over Cam,CDEK: ⑦ Fulfillment + Dispatch (см. 06)
    Cam->>OMS: trigger pickingProcess
    OMS->>OMS: exportForPicking → WMS
    OMS->>OMS: exportAfterPicking → ready
    Cam->>OMS: trigger dispatchProcess
    OMS->>CDEK: register shipment
    CDEK-->>OMS: waybill, tracking#
    OMS->>OMS: status = handed-over

    Note over OMS,U: ⑧ Notifications + Tracking (см. 07)
    OMS->>U: SMS «передан в доставку, трекинг #»
    CDEK->>OMS: webhook «in transit»
    CDEK->>OMS: webhook «delivered»
    OMS->>OMS: status = delivered
    OMS->>U: SMS «получено»

    Note over OMS: ⑨ Финализация
    Cam->>OMS: paymentFinalizationProcess
    Cam->>OMS: releaseProcess
    Note over OMS,Int: ⑩ Экспорт в 1C / DWH / ATOL (см. 08)
    Int->>OMS: cron BP-INT-13 → 1C
    Int->>OMS: cron BP-INT-10 → DWH
    Int->>OMS: cron BP-INT-14 → ATOL
```

---

## Пошаговая разбивка с ссылками

### ① Browse

- Анонимный посетитель → главная страница.
- Site → BFF → catalog-cache.
- См. [`01-product-content-lifecycle.md`](01-product-content-lifecycle.md) BP-CAT-06, [`03-browse-cart-precheckout.md`](03-browse-cart-precheckout.md) BP-BFF-01.

### ② Карточка → корзина

- Добавление товара создаёт корзину с TTL 24h.
- Корзина живёт в `baskets`.
- См. [`03-browse-cart-precheckout.md`](03-browse-cart-precheckout.md) BP-BSK-01.

### ③ Регистрация (SMS OTP)

- Пользователь вводит телефон → Devino SMS → ввод кода → создаётся `Customer`.
- Корзина анонимной сессии **мерджится** с серверной.
- См. [`02-customer-lifecycle.md`](02-customer-lifecycle.md) BP-CUS-01.

### ④ Pre-checkout (general-data + delivery quote)

- Site/Mobile запрашивает у Integration `general-data` — он агрегирует basket + addresses + intervals + payment methods.
- Integration зовёт OMS Settings (`/delivery/intervals`) → получает `inventories[]` со списком интервалов.
- ⚠️ Здесь работает «interval-id rolling hash» (см. ниже).
- См. [`03-browse-cart-precheckout.md`](03-browse-cart-precheckout.md) BP-CHK-PRE-01, BP-CHK-PRE-02, и [`../research/2026-05-16-checkout-flow.md`](../research/2026-05-16-checkout-flow.md).

### ⑤ Submit (POST /order/create)

- Integration валидирует, строит OMS Order DTO (V4 путь), вызывает OMS `/order/create`.
- OMS персистит, стартует `confirmationProcess.bpmn`.
- Стартует резервирование стока.
- См. [`04-checkout-order-creation.md`](04-checkout-order-creation.md) BP-CHK-01..04, BP-OMS-01, BP-OMS-02.

### ⑥ Платёж

- YooKassa hosted page → webhook к OMS pay-service.
- OMS signal'ит Camunda → confirmationProcess продолжается.
- См. [`05-payment.md`](05-payment.md) BP-PAY-01, BP-PAY-02, BP-OMS-06.

### ⑦ Fulfillment + Dispatch

- `pickingProcess` → WMS собирает.
- `dispatchProcess` → CDEK API регистрирует shipment, возвращает waybill.
- См. [`06-fulfillment-and-delivery.md`](06-fulfillment-and-delivery.md) BP-OMS-03, BP-OMS-04, BP-OMS-12.

### ⑧ Notifications + Tracking

- На каждом ключевом статусе — SMS и email через `notifications.bpmn`.
- CDEK шлёт webhook'и со статусами «in transit» / «delivered».
- См. [`07-post-order-and-comms.md`](07-post-order-and-comms.md) BP-OMS-09, BP-DEL-01..02.

### ⑨ Финализация

- `paymentFinalizationProcess` + `releaseProcess`.
- См. [`06-fulfillment-and-delivery.md`](06-fulfillment-and-delivery.md) BP-OMS-15, [`05-payment.md`](05-payment.md) BP-OMS-07.

### ⑩ Master-data export

- DWH / 1C / ATOL получают заказ через cron-задачи Integration.
- См. [`08-master-data-sync.md`](08-master-data-sync.md) BP-INT-10, 11, 13, 14.

---

## Точки наибольшего риска (по этому сценарию)

| Точка | Риск | Подробнее |
|---|---|---|
| ④ Pre-checkout | Stale interval-id (non-idempotent hash) | [`../research/2026-05-16-checkout-flow.md`](../research/2026-05-16-checkout-flow.md) |
| ⑤ Submit | 4 версии endpoint'а; не идемпотентный submit (двойной POST = двойной заказ) | `04-checkout-order-creation.md` |
| ⑥ Платёж | Lock-in на YooKassa; webhook idempotency | `05-payment.md` |
| ⑦ Dispatch | `russian-post-api-sdk` пустой; Yandex-NDD на test endpoint | `06-fulfillment-and-delivery.md` |
| ⑧ Notifications | Voximplant включён не для всех сценариев | `07-post-order-and-comms.md` |
| ⑩ Master-data | Несколько источников правды по стокам; recon шумит | `08-master-data-sync.md` |

---

## Если что-то пошло не так — где ловить

### Submit не прошёл

1. Site/Mobile логи (на клиенте).
2. Integration logs — `logs_search_message` через gj-buddy MCP (`mcp__gj-buddy__logs_*`).
3. OMS Order — `core/Order` логи + Camunda Cockpit (для incidents).

### Платёж завис

1. YooKassa dashboard.
2. OMS `pay-service` логи.
3. Camunda Cockpit — paymentProcess в инцидентах.

### Stock reservation failed

1. OMS `core/Stock` логи.
2. Recon (BP-INT-12) — расхождения 1C-Retail vs OMS.
3. Confluence: «overselling» страницы.

### Заказ не уехал к carrier

1. OMS `core/Delivery` логи.
2. dispatchProcess в Camunda Cockpit.
3. Per-carrier connector логи (CDEK / 5post / RPost).

---

## Альтернативные счастливые пути

| Сценарий | Отличия | См. |
|---|---|---|
| Самовывоз ПВЗ (CDEK PVZ) | На ④ выбирается `pickup_in_store`; на ⑦ dispatch везёт в ПВЗ; ⑧ — уведомление «прибыл в ПВЗ»; client сам забирает | `06-` BP-OMS-12 |
| Click & Collect (магазин GJ) | Picking на полке магазина; dispatch нулевой; SMS «готов к выдаче» | `06-` |
| Оплата при получении (cash) | ⑥ skipped — paymentUrl=null; oплата при выдаче через POS терминал; ATOL фискализация постфактум | `05-` BP-PAY-06 |
| Подели (BNPL) | ⑥ — Подели взимает рассрочкой, GJ получает деньги сразу | `05-` BP-PAY-04 |
| Покупка сертификата | Нет picking, нет dispatch; вместо tracking — email с кодом | `05-` BP-PAY-07 + `07-` BP-OMS-14 |

---

## Альтернативные **несчастливые** пути

- **Отмена клиентом** — BP-OMS-08 (`07-post-order-and-comms.md`).
- **Auto-cancel по timeout** (не оплачено за 24h) — confirmationProcess timer → cancellationProcess.
- **Out of stock на picking** — repick / cancel.
- **Carrier отказ** — cancel или замена carrier.
- **Fraud rejected** — на этапе ⑤ submit.
- **Возврат** — BP-RET-01, BP-RET-02 (`07-`).

---

**Дата создания:** 2026-05-16
