# Checkout — создание заказа (сводка)

**Дата:** 2026-05-20 · **Статус:** prod-логи + локальный код; **prod ref сервисов не зафиксирован** (≠ `release-26.06`, если ветка ещё не выкатана).

**BP (L1):** [`../bp/03-browse-cart-precheckout.md`](../bp/03-browse-cart-precheckout.md), [`../bp/04-checkout-order-creation.md`](../bp/04-checkout-order-creation.md)

**Длинные разборы (локально, не в git):** `logs/research/` — autopsy, каталог exceptions, полный log dump.

---

## Цепочка (одним абзацем)

Site/Mobile → ENSI `customers-api-web` (корзина, commit) → Integration `POST /integration/v4/order/create` → OMS `/order/create` → Camunda `confirmationProcess`. До commit заказа в OMS **нет**. «Не могу оформить» = фазы A/B; «оформил, но пропал» = фаза C (оплата, fraud, резерв).

```
A Pre-checkout   general-data, delivery/*, basket/*     → заказа нет
B Submit         POST */checkout/commit → v4/order/create → заказ в OMS
C Post-create    BPMN, pay-service, picking, carrier     → вне ENSI-логов
```

| Канал | Submit |
|-------|--------|
| Site | `POST /api/v3/checkout/commit` |
| Mobile | `POST /api/mobile/v5/checkout/commit` |
| Integration (internal) | `POST /integration/v4/order/create` |

---

## Приоритеты (prod, 2026-05-20)

| ID | Симптом | Где | Серьёзность |
|----|---------|-----|-------------|
| **P0** | IS `v4/order/create` **400**, BFF `checkout/commit` **HTTP 200** | mob v5, `delivery/stores` 200 → create 400 | **Critical** — заказа в OMS нет, клиент может видеть «успех» |
| **P1** | «Не удалось рассчитать дату доставки/самовывоза» → commit **400**, IS **не вызывается**; часто при `delivery/courier` **200** | BFF | High |
| **P2** | «В профиле не заполнен адрес» → commit 400, без IS | BFF | Medium |
| **P3** | Auth: `users:current` 401, `auth/refresh` 500 | customer-auth / BFF | Medium (шум + mid-checkout) |
| **P4** | `basket/current` 404, merge/TTL | baskets | Medium |
| **P5** | Post-create (fraud, 24h оплата, резерв) | OMS / Camunda — **не видно** в `logs-ensi-prod` | High для жалоб «после оформления» |

### P0 — что подтверждено

- **Паттерн (5 trace):** `delivery/stores` 200 → `v4/order/create` 400 → `checkout/commit` 200 (~8 ms). Канал: **mob v5**, customer **5476895**, кластер **12:11–12:16 UTC**.
- **TraceId:** `e0a31dae-7136-40d0-87f8-cf4ce55b52c8`, `d83cea83-9be1-4566-a16d-3e6f88592cb`, `630f7cc7-3959-4325-afc8-2b0d302b062c`, `481a9d6c-a778-452d-b28a-c3c656cde777`, `82c8a9c2-986e-496d-b8dc-469d03aa7321`.
- **Механизм HTTP 200 (hypothesis по коду BFF):** при IS **400** `CommitOrderAction` возвращает `success: false` в **теле**, HTTP commit остаётся **200** — проверить на **фактическом prod ref** `customers-api-web`; мобила должна смотреть `data.success`, не только status code.
- **Причина IS 400 (unknown в prod):** body 400 в ENSI DEBUG-логах **нет**. По trace — **самовывоз** (`delivery/stores`), не курьер. Гипотеза: финальная валидация create в IS (интервал магазина / сток / сумма) после успешного quote на commit.
- **Частота:** суточный rate **не посчитан** (MCP cap 500 строк); в кластере 12:11–12:16 ≥5 P0 за ~5 мин.

### P1 — пример trace

`19c96520-8974-49d3-a3d6-6e8cf9765a70` (web): commit 400, courier 200, `v4/order/create` не вызывался.

---

## Логи (Buddy MCP)

| `target_code` | Когда |
|---------------|--------|
| `logs-ensi-prod` | **Главный** — BFF, HTTP OUT к Integration, `traceId` |
| `logs-is-awg-prod` | IS отдельно (часто пуст по тексту; для P0 body — сюда или pod logs) |
| `logs-oms-prod` | Post-create, Camunda |

**Один инцидент:** `data_logs_search_message` → failed `checkout/commit` → `data_logs_search_trace` по `traceId`. Не искать голым `400` (шум Diginetica `size=400`).

**Успешный commit:** OUT `v4/order/create` 200 → IN `checkout/commit` 200.

---

## Известные архитектурные риски (код, не привязано к prod ref)

| Риск | Суть | Куда копать |
|------|------|-------------|
| Interval id drift | OMS Settings: rolling hash от date/dispatchDate/tariff; id меняется между general-data и commit (~09:00 cache, wave склада) | OMS `core/Settings`, mobile stale `deliveryCourierId` |
| V4 courier matching | Matching по id-only на courier path (pickup store — composite) | Integration `V4/Order/OrderService` на **prod ref** |
| Split-shipment UX | UI «2 из 3» — один package в OMS на create | Integration create, BP-04 |
| BFF quote vs IS create | BFF `delivery/stores` на commit ≠ повторная валидация IS на create | Store pickup traces P0 |

Подробно: `logs/research/2026-05-16-checkout-flow.md`.

---

## Дальше (в порядке)

1. **Prod ref** Integration + `customers-api-web` (image tag / pipeline) — без этого кодовые гипотезы не для prod.
2. **P0:** IS-логи по traceId `82c8a9c2-…` — точный `message` / exception class в body 400.
3. **P0 fix (BFF):** маппинг IS 400 → HTTP 4xx **или** контракт mob v5 (`success: false`) — product decision.
4. **P1:** body BFF 400 «дата доставки» vs payload `ResolveCommonDeliveryDataAction`.
5. **Метрики:** Kibana agg: `(create OUT 400) ∧ (commit IN 200)` по `traceId` / сутки.

**Агенты:** trace → `logs-detective`; IS create → `integration-researcher`; BFF commit → `ensi-researcher`; OMS после create → `oms-researcher` + Cockpit.
