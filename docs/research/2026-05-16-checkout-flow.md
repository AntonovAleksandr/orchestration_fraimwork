# Checkout Flow — Cross-System Autopsy

**Investigated by:** integration-researcher + ensi-researcher + oms-researcher + site-researcher + mobile-researcher (parallel)
**Date:** 2026-05-16
**Branches:** `release-26.06` (Integration, ENSI customers-api-web), `stage` (Site), `release-3.31.0` (Mobile), `master` / `19783+19795` (OMS)
**Main epic:** **OPSOMN001-27** (split-shipment + new general-data) + **OPSOMN001-209** (site redesign) + **OPSOMN001-173** (mobile redesign)

---

## Executive Summary

### Корневая причина non-idempotent interval id (найдена)

Источник — **OMS Settings** (`core/Settings`, не Delivery!), файл `DeliveryIntervalsByLogisticGroups.java:981`. Id интервала — это **rolling hash** от 7-9 полей (`HashUtil.getRollingHash` в `core/Settings/.../HashUtil.java:9-36`). Хеш сам по себе детерминированный. **Но** входами в хеш являются `date` и `dispatchDate`, которые вычисляются из `ZonedDateTime.now()` склада в момент запроса — при пересечении wall-clock времени последней picking-wave склада эти даты прыгают на +1 день → хеш меняется → id меняется.

Дополнительный источник дрейфа: `actualDeliveryCost` приходит из `CachedTariffRequestService` с ежедневной кэш-эвикцией в 09:00 (cron `0 0 9 * * *`). После эвикции carrier-tariff пересчитывается с актуальной ценой → значение меняется → хеш меняется.

OMS-team сама знает о проблеме — в коде есть `deduplicateById` с комментарием `//todo delete and found real cause of duplication` (Settings service, line 321). Но они её не чинят: за 6 месяцев есть 8+ коммитов в Settings, которые "патчат симптомы" (timezone, special days, calculateDaysLimit) вместо root cause.

**Дополнительная находка**: в OMS Settings **существуют ДВА варианта набора полей для хеша** — `DeliveryIntervalsMapper.toHashString` использует 7 полей, `generateDeliveryIntervalId` (endpoint `/delivery/intervals/generate`) использует 9 полей. Любой внешний попытка верифицировать id через `/generate` даст другой хеш. Это **скрытый bug в OMS**.

### Самое плохое место

**Mobile (`release-3.31.0`)** при `POST /api/mobile/v5/checkout/commit` отправляет `delivery.deliveryCourierId` = id из ранее загруженного `/general-data`, **без revalidation**. Если между двумя запросами OMS перегенерировал id (а это почти гарантированно через 09:00 cache-эвикцию или wave-rollover) — заказ пойдёт со stale id. На бэке OMS Order сохраняет это как **opaque string** на `shipping.deliveryIntervalId`, BPMN не валидирует — **тихая порча данных** в БД, выявляется только при ручном разборе.

**Integration V4 courier path** имеет ту же проблему: `OPSOMN-11195` сделал rollback на V1-формат matching, но только для pickup_in_store / pickup_points. Для courier matching остался **по `deliveryOptionId` (id)** — file `V4/Order/OrderService.php:439-606`. Это **известная регрессия в коде**.

### Что работает правильно

- **Integration V1 `isSelectedCourierInterval`** — matching по 7 полям (`dispatchWarehouse, date, dispatchDate, carrierId, tariffId, from, to`) — file `V1/Delivery/DeliveryService.php:287-303`.
- **Site `general-data-v2-order.mapper.ts:1347-1386`** — graceful fallback: если id не нашёл → берёт первый available option в той же inventory-группе. **Outgoing `customerDeliveryPreferences` не содержит `selectedIntervalId`** — только `carrierId`, бэк сам выбирает интервал.
- **Mobile `OrderListScreenV2.tsx:173-185`** — единственное место в mobile с composite-key matching (`dispatchDate + dispatchWarehouse + from + to`). На главном `CheckoutScreenV2` — silent fallback на `inventories[0].options[0]` без уведомления (`useDeliveryCostV2.ts:38-48`).

### Структурное несоответствие — split-shipment

Фича "комплектации 2 из 3, 4 из 5" живёт **только на этапе delivery quote** (ENSI customers-api-web возвращает `inventories[]` с `cartAvailability`). При `POST /order/create` Integration **собирает всё обратно в один `packages[0]`** (`V1/Order/OrderService.php:3181 addPackages`). OMS заказ всегда single-shipment. То есть split — это **UI-конструкт для UX**, не реальное физическое разделение поставки. Если product team считает, что split-shipment должен материализоваться в OMS — это требует OMS-изменений, которые мы делать **не можем** (вендор-локед).

---

## Cross-system architecture map

```
                 ┌─────────────┐         ┌─────────────┐
                 │   Mobile    │         │    Site     │
                 │ (release-   │         │  (stage)    │
                 │  3.31.0)    │         │             │
                 │ RN + Redux  │         │ Angular20+  │
                 │ + signal-   │         │ Nx + signal │
                 │   store     │         │   store     │
                 └──────┬──────┘         └──────┬──────┘
                        │                        │
                        │  GET/POST /api/mobile/v5/checkout/...
                        │  GET/POST /api/v2/checkout/...
                        │                        │
                        ▼                        ▼
              ┌──────────────────────────────────────┐
              │   ENSI customers-api-web (BFF)        │
              │   release-26.06                       │
              │   PHP 8.1 + Laravel + Swoole          │
              │   OpenAPI-first (mobile-v5 + v2 + v3) │
              └───┬────────────────────────────────┬──┘
                  │                                │
                  │ calls 6 ENSI services          │ POST/GET /integration/...
                  │                                │
       ┌──────────┼──────────┐                     ▼
       ▼          ▼          ▼          ┌──────────────────────┐
   ┌────────┐ ┌──────┐ ┌────────────┐   │ Integration Service  │
   │baskets │ │offers│ │catalog-    │   │ release-26.06        │
   │        │ │      │ │cache       │   │ PHP/Lumen (thin)     │
   └────────┘ └──────┘ └────────────┘   │ NO DB cart, stateless│
   ┌────────┐ ┌──────┐ ┌────────────┐   └────┬─────────────────┘
   │customers│ │bu   │ │customer-auth│       │ POST /logistics/...
   └─────────┘ └─────┘ └─────────────┘       │ POST /order/create
                                              │
                                              ▼
                              ┌─────────────────────────────────┐
                              │   OMS / Starfish (vendor-locked)│
                              │                                 │
                              │  core/Settings ★ ★ ★            │
                              │   └─ /delivery/intervals        │
                              │      ⚠ id = rolling hash        │
                              │        of date+dispatchDate+    │
                              │        +5-7 more fields         │
                              │      ⚠ date depends on now()    │
                              │                                 │
                              │  core/Delivery (carrier tariffs)│
                              │  core/Order   (/order/create)   │
                              │  core/Camunda (BPMN engine)     │
                              │  core/camunda-worker            │
                              │                                 │
                              │  awg/bpmn-process/process/      │
                              │     confirmationProcess.bpmn    │
                              │     dispatchProcess.bpmn        │
                              │                                 │
                              │  awg/cloud-configs/ (env values)│
                              └─────────────────────────────────┘
```

**Key observation:** интервалы живут в **core/Settings** (не Delivery!). Делегация: Settings берёт carrier-prices из Delivery (`/carrier/{id}/price/request`), warehouse picking-waves из своей БД, и **локально синтезирует** интервалы + минтит id.

---

## Главный flow: что происходит при чекауте

### Phase 1: Mobile/Site открывает чекаут
```
Mobile: GET /api/mobile/v5/checkout/general-data
Site:   GET /api/v2/checkout/general-data
```
↓
ENSI `GetCheckoutGeneralDataV2Action` (customers-api-web):
1. `getBasket()` → baskets-service (фильтрация по `isSelected = true`)
2. `getDeliveryPreferences()` × 2 (customer + city) → customers service
3. `getSummaryData()` → OMS `GET /integration/delivery/summary` через Integration
4. `DeliveryData::fromArray()` → builds typed objects (CourierDeliveryData / PickupDeliveryData / StoreDeliveryData)
5. `remapStoresData()` → enriches с BU метаданными
↓
Integration `DeliveryService::getDeliverySummary()`:
- Делает **3 параллельных** OMS вызова:
  - `POST /logistics/delivery-preliminary`
  - `POST /logistics/pickup-stores`
  - `POST /logistics/delivery-intervals` (для courier)
- Сшивает в `{delivery, pickup, pickupinstore, reserveinstore, storesData}`
↓
OMS Settings `DeliveryIntervalsByLogisticGroups`:
- Берёт carrier-tariffs из Delivery (через `CachedTariffRequestService`)
- Вычисляет warehouse `dispatchDate` через `calculateDispatchTariffDate` (зависит от `now()`)
- Генерирует interval objects
- `HashUtil.getRollingHash(date, dispatchDate, from, to, tariffId, dispatchWarehouse, deliveryCost, carrierId, actualDeliveryCost)` → 10-char id
- Возвращает `inventories[].options[]` с `id` каждого интервала

### Phase 2: Пользователь выбирает интервал курьера
Mobile path (новый чекаут):
```
1. Open OrderListScreenV2 (выбор комплектации курьера)
2. user тапает на inventory[i].options[0] (один вариант на комплектацию)
3. dispatch: setSelectedDeliveryData(option)
4. Redux store: state.checkout.selectedCourier = {id, from, to, carrierId, tariffId, ...}
5. setEquipment(items) → POST /api/mobile/v4/basket/set-equipment → baskets recalc
6. fetchCheckoutData() → /general-data повторно
7. ✓ В OrderListScreenV2 есть composite-key matching (line 173-185)
   → если id поменялся, новый id корректно подставится по dispatchDate+warehouse+from+to
```

Site path:
```
1. CheckoutDeliveryComponent → setCourierEquipment
2. v2 path: persistCustomerDeliveryPreferencesV2 → POST customerDeliveryPreferences
   (только carrierId, БЕЗ id) → backend resolveит интервал сам
3. reloadCheckoutGeneralData(true) → GET /general-data заново
4. mapper general-data-v2-order.mapper.ts:1347-1386 ищет старый id в новых options
5. Strict match? → use. Иначе: первая option в той же группе → use.
   ⚠ Это НЕ matching by carrierId+tariffId+from+to. Just "first available".
```

### Phase 3: Пересчёт при изменениях
Любое из:
- Смена интервала
- Смена адреса
- Смена payment method (Site v2 only)
- Смена региона
- Промокод (Site v2 пропускает promoCode без auth)
- Изменение состава корзины

→ ENSI отправляет в OMS новый product list (с обновлёнными `isSelected`, ценами, qty)
→ OMS получает новый shape → **regenerates intervals → new id хеши**

**КЛЮЧЕВОЕ**: время между Phase 1 (загрузка чекаута) и Phase 4 (commit) может быть больше, чем picking-wave threshold (например, 16:00 МСК) или 09:00 cache-эвикция. Тогда `dispatchDate` сместится → ВСЕ интервалы получат новые id, даже если basket не менялся.

### Phase 4: Commit
Mobile:
```
POST /api/mobile/v5/checkout/commit body: {
  delivery: {
    deliveryCourierId: state.selectedCourier.id,  // ⚠ может быть stale
    deliveryPickupId: state.selectedPickup?.id,
    ...
  },
  recipient, paymentMethod, ...
}
```
↓
ENSI `CommitOrderAction` → Integration `POST /integration/v4/order/create`
↓
Integration `V4/Order/OrderService::create()`:
1. setCityData / loadBaseStore / checkStock / validateAvailable
2. loadPrices / calculateDiscounts / calculateTotals
3. **`calculateShippingV4()`**:
   - `DELIVERY` → `fillSelectedCourierDeliveryIntervalV1()` (OPSOMN-11195 rollback)
     → OMS `POST /logistics/delivery-intervals/v1` **СНОВА**
     → matching по interval `id` (НЕ по полям!) — line 439-606
     → ⚠ ВЫСОКАЯ ВЕРОЯТНОСТЬ MISMATCH, throws `SelectedIntervalNotFound`
   - `PICKUP_IN_STORE` / `RESERVE_IN_STORE` → matching by `(id, date, dispatchWarehouse, deliveryTypeId)` ✓
   - `PICKUP_POINTS` → matching by `(id, date, dispatchWarehouse)` ✓
4. `addPackages()` — **схлопывает все items в `packages[0]`** (split исчезает!)
5. `OmsClient::createOrder()` → OMS `POST /order/create`
6. OMS Order сохраняет `shipping.deliveryIntervalId` как **opaque string**. BPMN не валидирует.
7. createPaymentLink (если PREPAID) → YooKassa

---

## Per-system findings

### 🟦 Integration Service (release-26.06)

**Stack:** PHP/Lumen monorepo. `www/` — code, `containers/` — Docker (api + cron). Stateless (no DB cart). All checkout endpoints under prefix `/integration/...`. Auth — basic-auth.

**Новый endpoint для split-shipment:** `GET /integration/delivery/summary` (OPSOMN001-17 / -27 / -488 / -502). Реализация: `V2/Delivery/DeliveryService::getDeliverySummary()`. Параллельно бросает 3 OMS-вызова, сшивает в `{delivery, pickup, pickupinstore, reserveinstore, storesData}`. Для PVZ комплектация всегда одна — берётся из `delivery-preliminary.data[pickup].cart` БЕЗ дополнительного `/pickup-points` запроса (OPSOMN001-488).

**Workaround "matching by params" — где именно:**
| File:line | Match key | Used for |
|-----------|-----------|----------|
| `V1/Delivery/DeliveryService.php:287-303` `isSelectedCourierInterval` | 7 полей: `dispatchWarehouse, date, dispatchDate, carrierId, tariffId, from, to` (strict `===`) | V1 и V2 `getCourierDeliveryIntervals*` |
| `V4/Order/OrderService.php:705-733` `fillSelectedPickupStoreDeliveryInterval` | `id, date, dispatchWarehouse, deliveryTypeId` | pickup_in_store, reserve_in_store |
| `V4/Order/OrderService.php:860-877` `fillSelectedPickupPointDeliveryInterval` | `id, date, dispatchWarehouse` | pickup_points |
| `V4/Order/OrderService.php:439-606` **РЕГРЕССИЯ — courier path** | `deliveryOptionId === interval.id` (id-only) | DELIVERY at commit — OPSOMN-11195 rollback не покрыл courier |

**Frontend контракт `deliveryIntervalFilter`:** 7 required-with-полей (`GetCourierIntervalsAndSuitesRequest.php:88-118`). Фронт обязан отправлять.

**Outbox / MQ events на commit:** **НЕТ.** Все checkout endpoints синхронные. Async — только в `integration-cron` daemons (OrderEventDispatcher, OrderStatus, OrderMessage и т.д.) — они тянут от OMS отдельно.

**TODO в коде**:
- `V4/Order/OrderService.php:1076` — `// TODO: контроль значения токен - сейчас вальнет с любым (OPSOMN-11413)`
- `V4/Order/OrderService.php:712,719,720` — commented-out conditions для pickup_store match (relaxed match keys — возможно были root cause workaround)
- `getDeliverySummary` НЕ в `V2/Delivery/DeliveryServiceContract` — contract drift

**Recent activity:** 18 commits last month, авторы: Andrey Shaposhnikov (10), Aleksandr Z. (4), Vasiliy Lukyanov (4). Hot file: `V2/Delivery/DeliveryService.php` (19 изменений за месяц).

### 🟧 ENSI customers-api-web (release-26.06)

**Stack:** PHP 8.1 + Laravel + Swoole, OpenAPI-first. Публичный BFF для site/mobile. На этой ветке — **+19641 / -263 строк** vs master (мажорный рефакторинг).

**Active layer для мобайла:** `ApiMobileV5/`. Для веба — `ApiV2/` / `ApiV3/`.

**Inter-service calls (выходящие):**
- `baskets` (dev-release-26.06) — `CustomerBasketsApi`, `SharedBasketsApi`
- `catalog-cache` (dev-master) — `OffersApi::searchProductCards` (обогащение карточками)
- `offers` (dev-master, классический PHP, **НЕ offers-go**) — только `clampToStock` при add to basket
- `customers` (dev-release-26.06) — профили, адреса, deliveryPreferences, бонусы
- `bu` — warehouses, picking-points (метаданные)
- `customer-auth` — только в auth flow
- `oms` (raw REST через `App\Domain\Orders\Client\OmsClient`) — все checkout

**Basket recalc → почему OMS меняет ids:**
1. Пользователь меняет состав → `BasketItemChangedListener` в baskets-service → `is_changed=true`, обновляет `is_selected` per item, пересчитывает discounts (только для `is_selected=true` items, новое в OPSOMN001-40)
2. ENSI на следующем запросе делает `filterSelectedBasket()` (`GetCheckoutAbstractAction.php:227-236`) — отбрасывает items с `isSelected=false`
3. Через `Product::formatProducts()` (`Logistics/V2/Product.php:17-51`) формирует product list для OMS. С `withQuantityOne=true` — массив N×{quantity:1}
4. OMS получает новый product set → перераскладывает на логистические группы/склады → **новый interval shape → новые id**

**Новая checkout data model (release-26.06):** целая папка `Domain/Orders/Data/Checkout/V2/` (22 файла):
- `CommonInventoryData` — одна комплектация (`dispatchWarehouse`, `dispatchDate`, `availableQuantity`, `cartAvailability[]`)
- `CommonOptionData` — option = интервал (id, date, from/to, deliveryCost, carrierId, tariffId, turnOnTime, cutOffTime, availablePaymentTypes, availableAcquirers)
- `CourierDeliveryData` / `PickupDeliveryData` / `StoreDeliveryData` — обёртки с `inventories: Collection<*InventoryData>`
- `CheckoutGeneralData` — корневой объект

**Известная typo в контракте OMS** (`CommonInventoryData.php:23`):
```php
// костыль нормализации ошибочного нейминга
$inv['cartAvailability'] ?? $inv['cartAvailabillity']   // с двумя 'l'
```
OMS контракт содержит typo (`cartAvailabillity`), ENSI нормализует. Это сигнал об **отсутствии contract testing** между ENSI и OMS.

**Major refactors на release-26.06:**
- `GetCheckoutGeneralDataV2Action` (285 строк, новый) — заменяет old `getCheckoutData`
- `GetCheckoutPickupPointsLightV2Action` (новый)
- `GetDeliveryDataV2Action` (336 строк, новый)
- `LoginV2Action` (273 строки) — теперь mergeBasketsCheckout при логине
- `CommitOrderAction` дискриминирует MOB_V5/V3 → `createOrderV4`

**TODO**:
- `Data/Address/City.php:35` — `carrierCityId = fias_id` (`//#TODO Поле обязательное, не знаем как его получать`)
- `GetCheckoutGeneralDataV2Action.php:79-80` — закомментирована A/B gravity, может вернуться

**Recent activity:** 250+ commits на ветке. Top authors: shapavalov (86), avartevanov (51+21=72), Andrey Gurin (42), Lukyanov (31+26=57). Главные эпики: **OPSOMN001-27** (split-shipment), **OPSOMN001-40** (basket isSelected, в baskets repo), **OPSOMN001-182** (merge basket on login).

### 🟥 OMS / Starfish (vendor-locked)

**Кто отвечает за интервалы:** `core/Settings` (НЕ Delivery!). Главный класс — `DeliveryIntervalsByLogisticGroups.java` (~1160 строк) + `DeliveryController.java` (REST endpoints под `/delivery/*`).

**API contract**:
- **`POST /delivery/intervals`** — главный (storefront-side через Integration)
- `POST /delivery/intervals/info` — lookup persisted by id (работает только пока interval в DB, неясная политика purge)
- `POST /delivery/intervals/generate` — пересчитывает hash от 9 полей (**но другой набор, чем в основном пути — bug в OMS**)
- `GET /delivery/interval/get?id=...` — single fetch

**Response header `CHECKSUM`** — Settings прикладывает sha-сумму ответа. Можно использовать для drift detection (Integration не использует!).

**Generation mechanism (root cause non-idempotency):**
```java
// DeliveryIntervalsMapper.java:81-84
String toHashString(Interval dto) {
    return HashUtil.getRollingHash(
        dto.from, dto.to, dto.tariffId, dto.date,
        dto.dispatchWarehouse, dto.deliveryCost, dto.carrierId
    );  // 7 fields
}
```
vs.
```java
// generateDeliveryIntervalId (DeliveryIntervalsByLogisticGroups.java:1073-1076)
HashUtil.getRollingHash(
    dto.from, dto.to, dto.tariffId, dto.date,
    dto.dispatchWarehouse, dto.deliveryCost, dto.carrierId,
    dto.actualDeliveryCost, dto.dispatchDate    // +2 fields
);  // 9 fields
```

**Hash function** — polynomial с prime=419, mod=10^10+19, zero-padded до 10 chars (`HashUtil.java:9-36`). Детерминирован при одинаковых входах. Дрейф — только во входах.

**Источники дрейфа input'ов:**

1. **`date` / `dispatchDate` зависят от now()** — `calculateDispatchTariffDate` (`DeliveryIntervalsByLogisticGroups.java:1016-1060`):
   ```java
   warehouseNowDateTime = nowDateTime.withZoneSameInstant(warehouse.timezone)
   while (warehouseNowDateTime.toLocalTime() > lastPickingWave.time) {
       skipDay++;
       dispatchDate = dispatchDate.plusDays(1);
   }
   ```
   Когда юзер делает чекаут до 16:00 МСК — `dispatchDate = today`. После 16:00 — `dispatchDate = tomorrow` → новый hash.

2. **`actualDeliveryCost` через daily cache** (`CachedTariffRequestService.java:44-77`, eviction cron `0 0 9 * * *`):
   ```java
   @Cacheable(value = "tariffCache", key = "tenantId :: cityFrom :: cityTo :: carrierId :: carrierTariffId")
   ```
   После 09:00 эвикции — live carrier call (CDEK SDK, Поч.России, etc.) может вернуть слегка другую `price` → `actualDeliveryCost` дрейфует → hash меняется.

3. **`dispatchWarehouse` зависит от stock** (`getWarehouses` + `partialDelivery`). При изменении остатков склад может поменяться.

4. **`from`/`to` стабильны per-tariff** (admin-controlled в Dictionary), но если админ отредактирует — все hash'и для carrier меняются.

**Stable fields для безопасного matching:**
- `tariffId` ★
- `carrierId` ★
- `dispatchWarehouse` ★
- `logisticGroupId`
- `deliveryRuleId`
- `from`, `to` (admin-controlled — стабильны в production day-to-day)
- `deliveryTypeId`
- `fulfillmentType`

**Carriers генерят свои id?** НЕТ. Все интервал-id минтятся в Settings. CDEK SDK (`cdek-api-sdk`) возвращает только `CalculatedTariff{price, period_min, period_max}` (SLA), не интервалы. Russian Post — то же. 5post — нет intervals API. Dalli — есть свой каталог интервалов, но Settings всё равно перехеширует. **Все id — наши.**

**Order create:**
- Endpoint: `POST /order/create` (`Order/OrderController.java:108-111`)
- Body: `OrderDto` с `shipping: ShippingDto`. Поле `deliveryIntervalId` (string) + все relevant fields отдельно (`carrierId`, `carrierTariffId`, `dispatchWarehouseId`, `logisticGroupId`, `dispatchDate`, `from`, `to`, ...).
- **OMS НЕ валидирует id** — сохраняет как opaque. BPMN (`confirmationProcess.bpmn`) не использует id. Это значит: stale id порождает **тихую порчу данных**, выявляется только при manual cross-check OMS DB.

**Recent activity:** Settings team активно патчит `dispatchDate` symptoms (`CLD-25276`, `CLD-24991`, `CLD-24727`, `CLD-25044`, `IPIDBBP-2336`, `IPIDBBP-1632` — все за 6 мес). Root cause (id-from-now) не трогают. Order / camunda-worker — без interval-touching commits.

### 🟩 Site (gj-ng-front, stage)

**Stack:** Angular 20 + Nx + кастомный `GJSignalStore` (signal-based, mutations вместо reducers+effects) + Transloco + NestJS SSR + GrowthBook. **Не классический NgRx** (нет `createReducer/createAction/createEffect`).

**Feature flag toggle:**
- `GrowthBookFeaturesEnum.NEW_CHECKOUT = 'newCheckout'` — переключатель old/new
- `NEW_CHECKOUT_PROGRESS_BAR = 'newCheckoutProgressBar'` — нигде в checkout не используется (dead?)
- `CheckoutPageTestWrapperComponent` — A/B selector

**Структура:**
- `libs/modules/checkout/src/lib/checkout-page-test-wrapper/` — A/B wrapper
- `libs/modules/checkout/src/lib/checkout-page/` — новый чекаут (`checkout-page.component.ts`, 441 LoC)
- `libs/modules/checkout/src/lib/checkout-old/` — legacy, не трогать
- `libs/modules/checkout/src/lib/equipment-card/` + `equipments-list/` — отображение комплектаций
- `libs/ui/src/lib/stock-counter/stock-counter.component.ts` — "X из Y" компонент

**Store:**
- `libs/data-access/src/lib/signals/order/order.store.ts` (1639 LoC) — `OrderStore extends GJSignalStore`
- `libs/data-access/src/lib/store/checkout/order/order.facade.ts` (614 LoC) — public API для компонентов
- Mutations вместо actions: `initOrderMutation`, `initOrderFromV2Mutation`, `setAddressMutation`, `setDeliveryCostMutation`, `persistCustomerDeliveryPreferencesMutation`, `getPointsMutation`, `createOrderMutation`

**State (упрощённо):**
```ts
{
  deliveryCourier: EquipmentsInterface[],          // available комплектации courier
  deliveryPickup, deliveryStores: Entity<...>,
  selectedCourierEquipment: DeliveryCourierInterface,  // выбранный интервал (с id!)
  selectedPickupEquipment, selectedPickupPoint,
  deliveryCourierId: string,                       // == selectedCourierEquipment.id
  // ... много полей
  generalDataSource: 'v1' | 'v2' | null,
  courierDefaultIntervalId: string | null,
  checkoutV2CustomerPreferences: ...,
}
```

**Stale id handling (`general-data-v2-order.mapper.ts:1347-1386`):**
1. Strict: `findCourierOption(courier, intervalId)` через все inventories.options
2. Fallback 1: `pickInventoryGroupBySelectedOption()` — группа где id есть в options ИЛИ первая с непустой `cartAvailability`
3. Fallback 2: первый available courier option в выбранной группе

⚠ Это НЕ matching by params (carrierId+tariffId+from+to). Это **first available**. Если пользователь выбрал 12:00-18:00, а после recalc этот слот пропал — UI молча покажет другое время.

**Outbound preferences:**
- `buildCustomerDeliveryPreferencesPayload` НЕ отправляет `selectedIntervalId`, только `carrierId` (line 697-702). Backend сам выбирает интервал → **обходит stale-id для preferences**
- `createOrder` отправляет `delivery.deliveryCourierId` = state.selectedCourierEquipment.id → **stale id может дойти до бэка**

**Recalc triggers:**
- Выбор интервала, ПВЗ, магазина → basket setEquipment + (v2) customerDeliveryPreferences + reload general-data
- Смена способа доставки → setDeliveryMutation + basketFacade.init + reload
- Смена адреса → setAddress + (v2) prefs + reload general-data
- Промокод → setDeliveryCost + basket init
- Смена payment method → POST customerDeliveryPreferences (без reload general-data!)
- Смена региона → update basket + initOrder + basket init
- Auto-fullEquipment (`CheckoutPageComponent.ngOnInit:161-170`) — авто-выбор полной комплектации после init

**i18n drift:** `kz.json` **отсутствует** для checkout, хотя `availableLangs: ['ru', 'en', 'kz']` и `apps/site-kz/` существует. Transloco скрывает fallback'ом. RU = 271 строк, EN = 216 строк. Конкретно `checkout.intervalErrorTitle/Content` — есть в RU, нет в EN.

**TODO/FIXME важные:**
- `order.store.ts:744` — `//TODO: убрать этот метод`
- `order.store.ts:1222` — `//TODO: добавить обработку ошибок` (в `createOrderMutation` — **без error handling!**)
- `checkout.service.ts:20` — `//TODO Переписать !!!!!!!!!! O(log*n * n*8)` — split-shipment filter, hot path при каждом init v1
- `checkout-page.component.ts:257` — `//FIXME: skip(1) - временный костыль с isLoading`

**Recent activity:** 40+ коммитов last month, 2 dominant authors: shapavalov (40) и Злотников Анатолий (32). Главный epic — **OPSOMN001-209** "Redisign checkout" (десятки фиксов). Hot files: `checkout-delivery.component.{ts,html,scss}`, `i18n/ru.json`, `order.store.ts`, `order.facade.ts`, `general-data-v2-order.mapper.ts`.

### 🟪 Mobile (gj-app, release-3.31.0)

**Stack:** React Native 0.74 + Redux Toolkit + redux-saga + redux-persist + кастомный signal-store через `useGetter` + YooKassa SDK. **Не используется `@tanstack/react-query`** для чекаута.

**Feature flag:** `NEW_CHECKOUT = 'new-checkout'` (GrowthBook). `CheckoutStack.tsx` переключает V1/V2.

**Screens:**
- `CheckoutScreenV2.tsx` (1150+ LoC, "монолит") — главный
- `OrderListScreenV2.tsx` — выбор курьерской комплектации ★ единственное место с composite-key matching
- `OrderCompositionScreenV2.tsx` — просмотр "X из Y" с подсчётом через `pluralizeWord(basketQty, ['товар','товара','товаров'])`
- `CourierDeliveryScreenV2`, `PickupDeliveryV2`, `StoreInfoV2`, etc.

**State:**
- Redux slice `packages/gj/src/store/checkout/index.ts` (571 LoC), сага `sagas.ts`
- Локальный signal-store `checkout-screen-model-v2.ts` для UI-state снэпшота
- Workaround для неавторизованных: `customerDeliveryPreferencesTemp/index.ts` (**TEMPORARY FIX OPSOMN001-466**)

**API client:** `packages/gj/src/api/checkoutV2/index.ts` (511 LoC). Endpoints:
- `GET  /api/mobile/v5/checkout/general-data`
- `POST /api/mobile/v5/checkout/commit`
- `GET  /api/mobile/v5/checkout/delivery/cost`
- `POST /api/mobile/v5/checkout/delivery/deliveryCourier`
- `POST /api/mobile/v1/checkout/customerDeliveryPreferences`
- `POST /api/mobile/v5/checkout/pickup-points`
- `GET  /api/mobile/v4/checkout/pickuppoint-data`

**Stale id handling — ПЛОХО:**
- `useDeliveryCostV2.ts:38-48` — **silent fallback на `inventories[0].options[0]`** без уведомления юзера
- `orderUtilsV2.ts:46` — `delivery.deliveryCourierId = selectedCourierDelivery.id` **без revalidation перед commit**
- `OrderListScreenV2.tsx:173-185` — единственное правильное место (composite-key match by `dispatchDate + dispatchWarehouse + from + to`)

**YooKassa:**
- SDK обёртка: `packages/rn-yookassa-sdk/`
- В чекауте: `packages/gj/src/screens/Checkout/utils/getPaymentToken.ts` (tokenize), `confirmPayment3ds`
- `orderUtilsV2.ts:42` — `paymentAcquirer: "yookassa"` при PREPAID
- ShopID + clientAppKey разные между staging (`490963`) и production (`318602`)

**Platform-specific:** мелочи (`Platform.OS === "android"` для layout animation в OrderBtn), keyboard-avoiding behavior. **Нет** `*.ios.tsx` / `*.android.tsx` файлов в checkout.

**patch-package:** 12 патчей в `gj-app/patches/`, для checkout критичен `react-native-autocomplete-dropdown` (DaData) и `react-native-geolocation-service` (auto-address). YooKassa патчей **нет**.

**Env-flavor differences:**
| Var | staging | production |
|-----|---------|------------|
| API_URL | customer-gui-mob-preprod.gloria-jeans.ru | api-mob.gloria-jeans.ru |
| BASIC_LOGIN | mobile-stage | (отсутствует, prod без basic auth) |
| CLIENT_APP_KEY YooKassa | test_NDkwOTYzL... | live_MzE4NjAy... |
| SHOP_ID | 490963 | 318602 |
| `new-checkout` flag | через GrowthBook (remote config) | через GrowthBook |

**API types from `mobapp-api-types/`:** **НЕ подключены к gj-app**. `grep mobapp-api-types ./` = 0 результатов. Mobile использует только runtime yup-схему (`packages/gj/src/api/checkoutV2/schema.ts`). Все option/inventory типы — `any` cast в коде (`CourierDelivery.tsx:73`, `useDeliveryCostV2.ts:41` и т.д.). **Контракт между мобилом и customers-api-web — без compile-time checks.**

**TODO/FIXME — 52 упоминания в checkout-области.** Ключевые:
- `courier-delivery.model.ts:42, 88, 298, 463, 515` — TEMPORARY FIX OPSOMN001-466
- `checkoutV2/index.ts:453-455, 472-476` — `Legacy and deprecated - should be deleted after release 26.07` (заглушенные методы `saveDeliveryMethod` / `saveAddress`)
- `CheckoutScreenV2.tsx:215, 240, 896` — `@ts-ignore`
- `index.ts:192, 202` — `@ts-ignore` в `transformDeliveryPickup` / `Stores`

**Recent activity:** 250+ commits ОДНОГО автора — **Mikhail Gorelov** (доминирует). Главная эпика — **OPSOMN001-173**. Hot files: `StoreDelivery.tsx` (65 touches), `CheckoutScreenV2.tsx` (59), `PickupDelivery.tsx` (49), `CourierDelivery.tsx` (38), `DeliveryBlockV2.tsx` (32). Темы: внедрение `/general-data` как единого источника, pre-fill из preferences, refactor стоимости доставки, OPSOMN001-466 workaround.

---

## Risk matrix: кто обрабатывает stale id

| Layer | Где stored | Match strategy | Stale id → что происходит |
|-------|------------|----------------|---------------------------|
| **OMS Order** | `shipping.deliveryIntervalId` (opaque string) | НЕ валидирует | **Тихая порча DB** — id остаётся в записи, не attached к реальному интервалу |
| **OMS BPMN** | не использует | — | Невидимо для процесса |
| **Integration V4 courier** (`/v4/order/create`) | id из request | id-based match (`deliveryOptionId`) — line 439-606 | `throw SelectedIntervalNotFound` — пользователь видит ошибку на commit |
| **Integration V4 pickup_*** | id из request | composite-key (`id, date, warehouse, [type]`) ✓ | Находит даже при mismatch id |
| **Integration V1/V2 courier** | id из request | composite-key (7 полей) ✓ | Находит — это правильный путь |
| **ENSI customers-api-web** | не валидирует на recalc | passthrough | id passes through |
| **Site (general-data-v2 mapper)** | `state.selectedCourierEquipment.id` | strict-id → fallback to first available in same group | UI молча показывает другой интервал |
| **Site (customerDeliveryPreferences)** | НЕ отправляет id, только carrierId | — | Backend re-resolves ✓ |
| **Site (createOrder)** | id передаётся в `deliveryCourierId` | НЕ revalidate | Stale id → Integration → ошибка |
| **Mobile (useDeliveryCostV2)** | id из state | strict-id → silent fallback to `inventories[0].options[0]` | UI молча показывает первый available, без error |
| **Mobile (OrderListScreenV2)** | id из state | **composite-key match** ★ | Находит правильный интервал |
| **Mobile (createOrder)** | id из `state.selectedCourier.id` | НЕ revalidate | Stale id → Integration → ошибка |

**Worst path (наибольшая вероятность боли):**
> User заходит в чекаут в 15:50 → выбирает курьерский интервал → отвлекается → нажимает "Заказать" в 16:05 → между phase 1 и phase 4 прошёл picking-wave threshold → `dispatchDate` сместился → OMS сгенерил новые id → **mobile / site молча отправил stale id** → Integration V4 courier path не нашёл match by id → `SelectedIntervalNotFound` → юзер видит generic error на финальной кнопке "Заказать".

---

## Critical bugs / regressions identified

### 🐛 #1 (Critical) — Mobile отправляет stale interval id на commit без revalidation
**Файл:** `packages/gj/src/screens/Checkout/utils/orderUtilsV2.ts:46`
```ts
delivery: {
  deliveryCourierId: state.selectedCourier.id,  // ← может быть stale
  ...
}
```
**Impact:** падение commit для случаев, когда между phase 1 и phase 4 OMS перегенерил id.
**Fix:** перед commit либо `GET /general-data` для revalidation, либо отправлять composite-key (`from/to/carrierId/tariffId/dispatchWarehouse/dispatchDate`) и пусть бэк сам резолвит.

### 🐛 #2 (High) — Integration V4 courier path matches by id-only (regression after OPSOMN-11195)
**Файл:** `platform/integration/integration/www/app/Service/UserApi/Services/V4/Order/OrderService.php:439-606`
**Background:** OPSOMN-11195 был rollback на V1-format matching, но покрыл только pickup_*. Courier остался id-based.
**Impact:** даже если фронт отправил правильные filter поля — V4 courier игнорит и матчит по id, который мог стать stale.
**Fix:** перенести логику composite-key match (`V1::isSelectedCourierInterval`) в V4 courier path.

### 🐛 #3 (High) — Site silent fallback на "first available" может показать неправильный интервал
**Файл:** `libs/data-access/src/lib/store/checkout/mappers/general-data-v2-order.mapper.ts:1378-1383`
**Impact:** юзер выбрал 12:00-18:00, OMS вернул новые ids, mapper выбрал первый available (например, 10:00-14:00) — юзер ничего не заметил, заказ ушёл с другим временем.
**Fix:** добавить matching by composite-key (carrierId+tariffId+from+to) перед fallback, и/или показать toast "Время изменилось, проверьте".

### 🐛 #4 (Medium) — Mobile silent fallback в useDeliveryCostV2 на `inventories[0].options[0]`
**Файл:** `packages/gj/src/screens/Checkout/CheckoutScreen/useDeliveryCostV2.ts:38-48`
**Impact:** при recalc стоимости после изменения корзины — если id пропал, mobile молча подменит на первый вариант **из первой комплектации** (что вообще другая комплектация может быть).
**Fix:** добавить composite-key matching или явный re-prompt пользователя.

### 🐛 #5 (Medium) — OMS bug в `/intervals/generate` (разный набор полей в хеше)
**Files:** OMS `core/Settings/.../DeliveryIntervalsMapper.java:82-83` (7 полей) vs `DeliveryIntervalsByLogisticGroups.java:1074-1076` (9 полей)
**Impact:** любой внешний клиент, который попытается верифицировать id через `/delivery/intervals/generate`, получит другой хеш.
**Fix:** **НЕ ДЛЯ НАС** (vendor-locked). Если решим использовать `/generate` — учитывать что он lying.

### 🐛 #6 (Medium) — Integration `getDeliverySummary` отсутствует в `V2/Delivery/DeliveryServiceContract`
**File:** `platform/integration/integration/www/app/Service/UserApi/Services/V2/Delivery/DeliveryServiceContract.php`
**Impact:** contract drift — DI binding может сломаться при типизированной подмене.

### 🐛 #7 (Low) — ENSI typo workaround `cartAvailabillity` vs `cartAvailability`
**File:** `customers-api-web/app/Domain/Orders/Data/Checkout/V2/CommonInventoryData.php:23`
**Impact:** signal об отсутствии contract testing между ENSI и OMS. Если OMS однажды поправит typo — ENSI fallback продолжит работать, но появится возможность silent miss данных.

### 🐛 #8 (Low) — Site i18n drift
**Impact:** `kz.json` отсутствует, `checkout.intervalErrorTitle/Content` нет в EN. На site-kz/en показывается fallback (вероятно RU keys).

### 🐛 #9 (Low) — Site `createOrderMutation` без error handling
**File:** `order.store.ts:1222` — `//TODO: добавить обработку ошибок`
**Impact:** silently swallowed errors на финальной кнопке.

### 🐛 #10 (Critical, but vendor-locked) — OMS не валидирует `deliveryIntervalId` на /order/create
**Impact:** stale id попадает в БД как opaque string, BPMN не валидирует, силовое восстановление возможно только через manual cross-check OMS DB.
**Fix:** не на нашей стороне — мы можем только **не отправлять stale id** (см. #1, #2, #3).

---

## Известные workarounds в коде (для будущих изменений — не сломать)

| Workaround | File:line | Зачем | Что будет если убрать |
|------------|-----------|-------|----------------------|
| Composite-key match для courier V1/V2 | Integration `V1/Delivery/DeliveryService.php:287-303` | Stale id защита | Падение selectInterval validation |
| Composite-key match для pickup_store/point V4 | Integration `V4/Order/OrderService.php:705-733, 860-877` | Stale id защита (OPSOMN-11195) | SelectedIntervalNotFound на commit |
| PVZ комплектация из delivery-preliminary | Integration `V2/Delivery/DeliveryService.php:670-741` (OPSOMN001-488) | Избежать лишнего pickup-points call | Лишний OMS вызов, slower checkout |
| `cartAvailabillity` typo нормализация | ENSI `Data/Checkout/V2/CommonInventoryData.php:23` | OMS typo в контракте | Поле всегда null после OMS typo fix |
| `carrierCityId = fias_id` | ENSI `Data/Address/City.php:35` | Поле обязательное, но непонятно где брать | OMS отказ на создание заказа |
| customerDeliveryPreferencesTemp slice | Mobile `store/customerDeliveryPreferencesTemp/` (OPSOMN001-466) | Сохранение preferences для неавторизованных | Анонимные пользователи теряют preferences между сессиями |
| Mobile silent fallback в useDeliveryCostV2 | `useDeliveryCostV2.ts:38-48` | Не падать на stale id | UI ломается с белым экраном |
| Site fallback в general-data-v2-order.mapper | `general-data-v2-order.mapper.ts:1378-1383` | Не падать на stale id | UI ломается |
| `paymentAcquirer: "yookassa"` лок | Integration `V4/Order/OrderService.php:132-143` (OPSOMN-9356) | Только YooKassa разрешён | Возможность не-YooKassa acquirers, может сломать flow |
| `calculateDaysLimit: 1` для intervals | Integration в `getDeliverySummary` (OPSOMN-9747) | Уменьшение количества вариантов | Огромный response от OMS |

---

## Recommendations (только наша сторона, OMS не трогаем)

### Tier 1 — Critical, fix asap

1. **Mobile `orderUtilsV2.ts:46`** — перед commit вызвать `GET /general-data` для revalidation. Найти new id для текущего composite-key (carrierId+tariffId+from+to+dispatchWarehouse), подставить в `delivery.deliveryCourierId`. Если matching не сработал — показать модалку "Время доставки могло измениться, обновите".
2. **Integration `V4/Order/OrderService.php:439-606`** — заменить id-only matching на composite-key (как в V1 `isSelectedCourierInterval`). Это устраняет регрессию после OPSOMN-11195.
3. **Site `createOrder`** — symmetric с mobile. Перед commit revalidation id через freshly loaded general-data.

### Tier 2 — High, structural

4. **Контрактные тесты ENSI ↔ OMS.** Если бы они были — typo `cartAvailabillity` не пролетел бы. Setup contract test (pact или manual schemathesis) в CI для customers-api-web и Integration.
5. **`CHECKSUM` header** от OMS Settings — использовать в Integration для drift detection. Если CHECKSUM меняется между загрузкой и commit — форсить refetch.
6. **Mobile `mobapp-api-types`** — подключить. Сейчас все option/inventory типы — `any`. Это скрывает structural breaking changes.

### Tier 3 — Hygiene

7. **Сайт kz.json для checkout** — добавить, или явно настроить fallback на RU в config.
8. **Сайт `createOrderMutation` error handling** — `order.store.ts:1222` TODO.
9. **Integration `getDeliverySummary` в Contract** — закрыть contract drift.
10. **Mobile `Legacy and deprecated - should be deleted after release 26.07`** — выбросить после релиза.

### Не рекомендуется
- ❌ Менять OMS Settings (vendor-locked, плюс OMS team сама "патчит симптомы" без решения root cause)
- ❌ Использовать `/delivery/intervals/generate` для верификации id (другой набор полей в хеше — bug в OMS)
- ❌ Полагаться на `/delivery/intervals/info` для id-lookup (неясная политика purge persisted intervals)

---

## Open questions (ещё не дорасследованы)

1. **Когда OMS Settings persist'ит интервалы в DB и когда purg'ает?** Это влияет на работоспособность `/intervals/info` lookup. Нужен follow-up в `oms-researcher` с запросом `SELECT * FROM act_ru_*` или схожих таблиц Settings.

2. **Использует ли site/mobile `CHECKSUM` header?** Похоже что нет. Если да — где. Подтвердить через grep по `CHECKSUM` / response headers handling.

3. **Из mobile нельзя установить `package_is_selected`?** Базовый route `basket/set-equipment` в `mobile-v5` отсутствует (только в web ApiV2/ApiV1). Значит mobile **не использует комплектации**? Или использует через другой механизм? Подтвердить.

4. **ENSI customer-auth merge basket при логине** (OPSOMN001-182, `LoginV2Action` 273 LoC) — что происходит с уже выбранными интервалами при merge гостевой и пользовательской корзин? Скорее всего invalidate + reload general-data, но не подтверждено.

5. **`paymentAcquirer: "yookassa"` lock (OPSOMN-9356)** — это политика? Если product team захочет другой acquirer (СБП?), потребуется снять лок.

6. **YooKassa SDK iOS vs Android** — отдельная исследовательская тема. RN bridge level — нужен mobile-researcher для native слоя.

---

## Jira ticket inventory

### Main epic (split-shipment / new checkout)
- **OPSOMN001-27** — split-shipment в чекауте (главный, integration + ensi)
- **OPSOMN001-209** — site redesign checkout
- **OPSOMN001-173** — mobile V2 checkout (доминирующая такса Gorelov)
- **OPSOMN001-40** — baskets isSelected attribute (в baskets-service repo)

### Sub-tasks по systems
- **OPSOMN001-17** — Integration `/integration/delivery/summary` introduced
- **OPSOMN001-488** — PVZ комплектация из delivery-preliminary
- **OPSOMN001-502** — shelfLifeDays из OMS Settings
- **OPSOMN001-182** — basket merge on login (LoginV2Action)
- **OPSOMN001-466** — mobile customerDeliveryPreferences temp (anonymous workaround)
- **OPSOMN001-471** — site fix переключение магазин↔ПВЗ
- **OPSOMN001-492** — site не стирается улица/дом при смене региона
- **OPSOMN001-416** — site игнор галочек выбора + откат A/B
- **OPSOMN001-498/499** — site старый чекаут адаптив
- **OPSOMN001-196** — site редизайн способов доставки
- **OPSOMN001-202/204** — site recipient формы
- **OPSOMN001-94** — site fix auth
- **OPSOMN001-340** — site бонусные рубли

### Workaround tickets (legacy)
- **OPSOMN-11195** — Integration V4 courier rollback to V1 format (не покрыло courier path полностью)
- **OPSOMN-9356** — Integration `paymentAcquirer=yookassa` lock
- **OPSOMN-9747** — Integration `calculateDaysLimit:1`
- **OPSOMN-11413** — `// TODO: контроль значения токен`
- **OPSOMN-7983** — Integration `// TODO` (без описания)
- **OPSOMN-13100** — don't crash on broken OMS response
- **OPSOMN-14135** — cart compaction

### Mobile other recent
OPSOMN001-139, -171, -185, -279, -318, -320, -330, -337, -354, -197 (basketV2 new fields)

### OMS-side tickets (внешний контекст)
- **CLD-25276, -24991, -24727, -25044** — Settings dispatchDate fixes (нашли в OMS history)
- **CLD-1840** — pay-service feature branch (default)
- **CLD-4877** — cdek-api-sdk feature branch
- **CLD-17047** — cloud-configs feature branch
- **PT-64** — HashUtil refactor (введение `getRollingHash(Object...)`, Feb 2024) — текущий механизм
- **IPMFG-XXX**, **IPIDBBP-XXX**, **IPRC-105**, **OMS-1654** — OMS internal

---

## Next steps

1. Передать findings команде, обсудить Critical fixes (#1, #2, #3) с product/tech leads.
2. **Открыть Jira ticket** на root-cause discussion: "Stale interval id at commit — три пути исправления (mobile revalidation, Integration V4 courier fix, Site composite-key matching)".
3. После договорённости — задействовать `mobile-engineer` для #1, `integration-engineer` для #2, `site-engineer` для #3. Все три могут делаться параллельно.
4. Включить этот документ в onboarding для новых разработчиков на checkout фичу — поможет избежать повторного открытия костылей и регрессий.
5. **Запланировать follow-up research** через 2-3 месяца — после фиксов проверить, что новые костыли не наплодили.
