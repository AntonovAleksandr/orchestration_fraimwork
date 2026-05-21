# Integration Service — Business Process Catalog

**Scope:** PHP/Lumen monorepo `platform/integration/integration/` plus libs `logger`, `msq-client`, `health`. Branch reference: `dev` (and `release-26.06` per checkout cross-system report).
**Companion artifact (referenced, not duplicated):** `do../research/2026-05-20-checkout-order-creation.md` — full cross-system autopsy for `/v4/order/create` + `/delivery/summary` checkout slice.
**Authored for:** `docs/bp/` business-process map.

This document catalogs the business processes that **live inside Integration** as a Lumen monorepo. Integration is the BFF/glue tier that the site/mobile/ENSI and various 1C/DWH/OMS partners go through. Most processes are synchronous HTTP (deploy `integration-api`) with a parallel async tier of Kafka daemons and DWH/1C exports (deploy `integration-cron`).

---

## Topology

```
                ┌──────────────────────────────────────────────────────┐
                │                  integration-api                     │
                │  Lumen app (nginx + php-fpm + supervisor)            │
                │  Prefix:  /integration  (basic-auth)                 │
                │  Prefix:  /             (bearer-auth — service-side) │
                └──────────────────────────────────────────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
   site/mobile via                  ENSI customers-api-web         service-side
   customers-api-web                (Laravel BFF)                  (OMS, ARM, 1C, ENSI...)
        │                              │                              │
        ▼                              ▼                              ▼
  /integration/*          /integration/* (auth basic)        /order/export, /fraud/check
                                                              /carrier/*/price/request


                ┌──────────────────────────────────────────────────────┐
                │                  integration-cron                    │
                │  supervisor: 4 always-on Kafka daemons               │
                │      transfer:business-unit:daemon                   │
                │      transfer:product:daemon                         │
                │      transfer:order-status:daemon                    │
                │      transfer:order-message:daemon                   │
                │                                                      │
                │  Laravel scheduler (Kernel::schedule):               │
                │      notification:stock:oms-change      */5 * * * *  │
                │      transfer:stock:ots-change          5..55 * * *  │
                │      transfer:stock:ots-init            0 22 * * *   │
                │      transfer:stock:cb-1c-retail-auto   0 */1 * * *  │
                │      retry:stock:cbr-1c-auto            */1 * * * *  │
                │      transfer:order-status:dwh          10 22 * * *  │
                │      transfer:orders:dwh                30 21 * * *  │
                │      transfer:orders:recon ecom         30 22 * * *  │
                │      transfer:orders:recon cbr          0 0 * * *    │
                │      pickup-points:cache                30 1 * * *   │
                └──────────────────────────────────────────────────────┘
```

**Lumen specifics:** `bootstrap/app.php` enables `$app->withFacades()` and `$app->withEloquent()`, so Eloquent and Facades are available (uncommon for vanilla Lumen, must not be assumed in similar repos). Routes are loaded from `Service/UserApi/routes/api.php` and `Service/Proxy/routes/api.php` via the service-provider pattern, **not** `routes/web.php` (that file is empty). The `/integration` prefix is **NOT** applied via the bootstrap group — providers add it explicitly per route.

**Outbox stack:** `Awg\MsqClient` (`platform/integration/msq-client/`) — single table `outbox_messages` (`migrations/create_msq_client_tables.php`), columns `lock, client, queue, tries, body, headers, properties, timestamps, deleted_at`. Default broker: Kafka (`config/msq-client.php`).

**External clients (composer-style facades):** `OmsClient`, `OmsClientV2`, `CatalogClient`, `BusinessUnitClient`, `PriceClient`, `DiscountClient` (these point to ENSI services), `OtsClient`, `Ecom1CClient`, `CB1CRetailClient`, `AsmClient`, `DwhClient`/`DwhClientV2` (SFTP), `WebGjISmpClient`. Each has its own `config/client.php` with env-driven base URL + timeouts.

---

## Process catalog

The remainder of this document enumerates the processes. Identifiers `BP-INT-NN` are stable handles for cross-references in the wider BP map.

---

### BP-INT-01 — Pre-checkout delivery quote (legacy V1/V2 path)

**Triggers (HTTP, basic-auth, `integration-api`):**
- `POST /integration/delivery/courier` → V1 (`OPSOMN-9315` precursor)
- `POST /integration/v2/delivery/courier` → V2
- `POST /integration/delivery/pickuppoint` → V1
- `POST /integration/v2/delivery/pickuppoint` → V2 (`OPSOMN-9876`)
- `POST /integration/v3/delivery/pickuppoint` → V3 (`OPSOMN-11512`)
- `POST /integration/delivery/points` → V1 (pickup points list)
- `POST /integration/v2/delivery/points` / `v3/...` → newer (`OPSOMN-9640, -9158`)
- `POST /integration/delivery/available-delivery` / `v2/...` → availability matrix (`OPSOMN-9366, -12336`)
- `POST /integration/delivery/stores`, `POST /integration/delivery/pickuppoints` (`OPSOMN-10847`)
- `GET /integration/delivery/preliminary` — bootstrap call from site/mobile
- `GET /integration/pickuppoint/list` and `v2/...` — cached PVZ list (`OPSOMN-12209, -9689`)

**Actors:** site / mobile via ENSI customers-api-web → Integration → OMS.

**Steps (e.g. `getCourierIntervals`, `V1/Delivery/DeliveryService.php:182`):**
1. Resolve city via `getCityInfo` / `getCityByGoldenRecordOrFias` → OMS `getCityGoldenRecord` or `getCitySuggestion`.
2. Build `CourierDeliveryIntervalsParameter` from incoming `data` (cart + filter).
3. Call **OMS Settings** `POST /delivery/intervals` via `OmsClient::getCourierDeliveryIntervals` (`Connector::sendAndParse`).
4. For each returned `interval`, run `isSelectedCourierInterval` (`DeliveryService.php:287-303`) — composite-key match by **7 fields** (`dispatchWarehouse, date, dispatchDate, carrierId, tariffId, from, to`, strict `===`).
5. Re-shape via presenter into `Http/Presenters/V1/Delivery/...` shape.

**External calls:**
- OMS Settings: `POST /delivery/intervals`, `POST /delivery/intervals/pickuppoint`, `POST /delivery/intervals/pickupstore`, `GET /city/golden-record`, `GET /city/suggestion`, `GET /delivery/types`, `GET /warehouses`, `GET /warehouses/stocks/fullness`, `GET /carriers`, `GET /pickup-points`, `GET /available-delivery-types`.

**Side effects:** **NONE** persisted in Integration DB. Stateless aside from local caching (`Service/Cache`).

**Known quirks:**
- V1/V2 courier path **correctly** composite-key matches (good).
- V2 also has a `getDeliveryPreliminary` and a `getCarrierListCache` (PVZ list comes from a **cron-built cache**, see BP-INT-22).
- Code path `V1/Delivery/DeliveryService.php:2306-2329` uses `V2OmsClient` (i.e. `OmsClientV2`) for some pickup point/store interval calls (an in-flight migration; both clients coexist).
- `OPSOMN-9747` introduced `calculateDaysLimit:1` to OMS interval calls to keep response payload small.

> Full sequence-with-OMS detail for this path lives in the checkout-flow autopsy. See `do../research/2026-05-20-checkout-order-creation.md` (Phase 1, "Per-system findings → Integration Service" table).

---

### BP-INT-02 — Pre-checkout delivery summary (new V4 / split-shipment path)

**Trigger:** `GET /integration/delivery/summary` — added in **`OPSOMN001-17`** as the consolidated single-call replacement for separate `courier` + `pickup` + `stores` calls.

**Actors:** ENSI customers-api-web → Integration → OMS (3 calls in parallel).

**Implementation:** `V2/Delivery/DeliveryService::getDeliverySummary()` (`Service/UserApi/Services/V2/Delivery/DeliveryService.php:514`). **Important contract drift:** this method is **not** declared in the matching `V2/Delivery/DeliveryServiceContract` interface (see bug #6 in checkout autopsy). DI binding is loose.

**Steps:**
1. Build `cart` shape via internal `compressCart` (line ~983).
2. **Fire 3 parallel OMS calls** (via `Connector` async batching):
   - `POST /logistics/delivery-preliminary`
   - `POST /logistics/pickup-stores`
   - `POST /logistics/delivery-intervals` (courier)
3. Sew responses into `{delivery, pickup, pickupinstore, reserveinstore, storesData}` envelope.
4. For PVZ комплектация (single by design) — extracted from `delivery-preliminary.data[pickup].cart` directly, **no second `/pickup-points` call** (workaround `OPSOMN001-488` — explicit perf optimization).
5. Sort warehouses (`sortWarehouses`), compact stores (`compactStores`), sort inventories — all in-PHP. Optional `selectedStoreId` / `selectedWarehouseId` driven via query.
6. Remap to V4 contract per data-shape classes in ENSI `Domain/Orders/Data/Checkout/V2/` (see autopsy).

**Known quirks:**
- `getWarehousesInfo` lookups for BU/warehouse metadata go to ENSI `BusinessUnitClient` (not OMS).
- Contract drift bug #6 in checkout autopsy.
- ENSI customer-side normalizes `cartAvailabillity` typo (OMS contract bug) — see bug #7 in autopsy.
- `OPSOMN001-502` introduced `shelfLifeDays` from OMS settings into this response.

---

### BP-INT-03 — Order submit (legacy V1)

**Trigger:** `POST /integration/order/create` (basic-auth).

**Actor:** ENSI customers-api-web (only on legacy site flow).

**Implementation:** `V1/Order/OrderService::create()` (`Service/UserApi/Services/V1/Order/OrderService.php:2671`). Long-running monolith (~250 lines). Calls many subroutines:
1. `setCityData($order)` → OMS `getCityGoldenRecord` / `getCitySuggestion`.
2. `loadBaseStore($order, $city)` → resolves baseStoreCode (used for prices, discounts).
3. `StockServiceContract::checkOrderStockAvailable($items, $warehouseId)` → ENSI catalog stock check (uses RESERVE_IN_STORE option vs dispatchWarehouse switch).
4. `validateAvailable($order, $baseStoreCode)` → exportDate + availability validation (lots of `is_enabled_availability_export_date_check` flag toggling).
5. `processPositionItems($items)` — expand to one row per quantity unit, allocate positions.
6. `loadPrices($order, $baseStoreCode)` → `PriceClient` (ENSI offers/PriceClient).
7. `addDataToOrder($order)` — enrich totals/payable, attach `isPaid=false`.
8. `DiscountServiceContract::calculateOrderDiscounts` — discounts + bonus + promo; returns `$callbacks` to commit/rollback later.
9. `calculateTotals($order, $originalTotalCost)` — final pricing.
10. `calculateShipping($order, $city)` — V1 shipping fill, uses `isSelectedCourierInterval` (composite-key) for courier.
11. `sortBySales`, `addPackages` — **packages collapsed into `packages[0]`** (see autopsy: split-shipment is a UI construct, not materialized).
12. `checkLoadTest($order)` — load-test mode short-circuit returns synthetic success.
13. `Connector::sendAndParse(OmsClient::createOrder($order))` → **OMS `POST /order/create`**.
14. `$discountService->runCallbacks($callbacks)` — commit loyalty burn / coupon redemption to ENSI Discount service.
15. `createPaymentLink($order)` — see BP-INT-06.
16. Return `{clientOrderId, orderId, paymentUrl, acquierTransactionId}`.

**Side effects:**
- Order persisted in OMS (`orderId` returned).
- Loyalty/coupon committed in ENSI discount service (after OMS success — non-transactional, see risk note below).
- Payment link minted in OMS pay-service.
- **No Integration DB writes**, **no outbox message** on commit (the autopsy explicitly confirms: "Outbox / MQ events on commit — НЕТ").

**Known quirks:**
- Non-transactional. If `runCallbacks` throws after `createOrder` succeeds — order exists in OMS but loyalty not yet committed in ENSI. The retry path is manual / via `returnLoyalty` reconciliation.
- `OPSOMN-13100` was a defensive fix to "не падать при битом ответе OMS" (lazy parse).
- V1/V2/V3/V4 coexist behind different routes; V1 is still mounted for legacy 1C/ARM callers.

---

### BP-INT-04 — Order submit V2 / V3

**Trigger:**
- `POST /integration/v2/order/create` → `V2/Order/OrderActionController@create`
- `POST /integration/v3/order/create` → `V3/Order/OrderActionController@create` (`OPSOMN-10033`)

**Implementation:** `V2/Order/OrderService::create()` and `V3/Order/OrderService::create()`. Structurally similar to V1 but with revised discount/loyalty flow (V2 adds `sortItemsByDiscountPrice`, `setDiscountIntegrationCallbackData`).

**Quirks:**
- V2 adds `updateStatusByArmV2(orderData)` for ARM/1C status updates (see BP-INT-10).
- These versions are still routable in production (some legacy callers).

---

### BP-INT-05 — Order submit V4 (current site / mobile path)

**Trigger:** `POST /integration/v4/order/create` (`OPSOMN-9602/9609/9613/9729`).

**Actor:** ENSI customers-api-web → Integration.

**Implementation:** `V4/Order/OrderService::create()` (`Service/UserApi/Services/V4/Order/OrderService.php:121`). Roughly the same shape as V1 with these differences:
1. **YooKassa-only acquirer lock** (`OPSOMN-9356`, lines 131-141): throws hard if `paymentAcquirerId !== yookassa`.
2. **`calculateShippingV4`** (line 415) replaces V1's `calculateShipping`. Dispatches to:
   - `fillSelectedCourierDeliveryInterval` (line 541) — **regression**: id-only match (see autopsy bug #2 / `OPSOMN-11195`).
   - `fillSelectedPickupStoreDeliveryInterval` (line 654) — composite-key match `(id, date, warehouse, type)`.
   - `fillSelectedPickupPointDeliveryInterval` (line 824) — composite-key match `(id, date, warehouse)`.
3. **`prepareCartForDelivery`** (line 955) — adjusts `zeroCart` shape for OMS shipping resolution.
4. `createPaymentLink` (line 996) — see BP-INT-06.

**Returned data (V4 presenter):** `{clientOrderId, orderId, paymentUrl|paymentToken|paymentConfirmation, acquierTransactionId}` — variant depends on `sourceId` (`MOB_APP` vs site) and presence of `confirmationToken`.

**Quirks (also captured in autopsy):**
- Bug #2 (regression in courier matching).
- Line 1076: `// TODO: контроль значения токен - сейчас вальнет с любым (OPSOMN-11413)`.
- Lines 712, 719, 720: commented-out conditions for pickup_store match (relaxed match keys — likely past workaround).
- Lines 1016-1025: commented-out pre-tabular `paymentChannel = 'sbp'` / `HOLD` block — "до таблицы Гульдар в рамках OPSOMN-11413".

**Side effects:** identical to V1: OMS order persisted, discount callbacks run, payment link minted.

---

### BP-INT-06 — Payment link / payment confirmation (synchronous create)

**Trigger:** inline within order-create endpoints, plus standalone:
- `POST /integration/onlinepay/{clientOrderId}/getlink` → V1
- `POST /integration/v2/onlinepay/{clientOrderId}/getlink` → V2 (`OPSOMN-10496`)

**Implementation:**
- V4 inline: `V4/Order/OrderService::createPaymentLink` (line 996-1083).
- V1 standalone: `V1/Order/OrderService::getPaymentLink` (line 1130).
- V2 standalone: `V2/Order/OrderQueryController::getPaymentLink`.

**Steps (V4 inline):**
1. Skip if `paymentTypeId !== PREPAID` (postpaid orders need no link).
2. Build payment URL by `replaceParameters(URL_ORDER_PAYMENT_TEMPLATE, {orderNumber})`.
3. Resolve `acquirerId` (defaults to `DEFAULT_PREPAID_ACQUIRER` if not set — but YooKassa lock from `OPSOMN-9356` enforces yookassa upstream).
4. `buildPaymentLinkParams($order)` → `[authorizationTypeId, paymentChannel, confirmationType, formPageLayout]`. (`paymentChannel = 'sbp'` would route to SBP via YooKassa.)
5. `OmsClient::createOrderPaymentLink(...)` — OMS pay-service (`core/pay-service`) creates the payment with YooKassa.
6. Validate non-empty `acquierId` (NOTE typo `acquierId` not `acquirerId` is the actual OMS contract). If empty → `EmptyPaymentLink` exception.
7. Branch by `sourceId === MOB_APP` and `confirmationToken` presence:
   - Mobile with token → return `paymentConfirmation`
   - Mobile without token → return `paymentUrl`
   - Web with empty token → return `paymentToken` (frontend tokenization)
   - Web with token → return `paymentUrl`

**External calls:** OMS `pay-service` via `OmsClient::createOrderPaymentLink`. No direct YooKassa call — pay-service mediates.

**Side effects:** OMS pay-service creates the payment record; Integration writes nothing.

**Quirks:**
- Typo `acquierId` / `acquierTransactionId` in OMS contract is propagated verbatim through Integration.
- `OPSOMN-11315` removed the `link` non-empty check; only `acquierId` is checked.
- SBP support flow is **commented out** awaiting "таблица Гульдар" — current effective behavior is YooKassa hold/charge per type only.

**Where webhooks are handled:** **not in Integration.** OMS `core/pay-service` listens to YooKassa webhooks. Integration only mints links via OMS and consumes payment status indirectly through OMS order status updates (see BP-INT-09).

---

### BP-INT-07 — Podeli / installment quote

**Trigger:** `POST /integration/onlinepay/podeliCalculate`.

**Implementation:** `V1/Order/OrderService::podeliCalculate` (line 5107). Thin passthrough: `OmsClient::getPodeliCalculate($data)` → return.

**External calls:** OMS pay-service `/podeli/calculate` (or similar).

**Side effects:** none.

---

### BP-INT-08 — Order confirmation (callback)

**Trigger:** `POST /integration/order/confirm` (basic-auth).

**Implementation:** `V1/Order/OrderService::orderConfirm($clientOrderId)` (line 5090). Sends OMS message `MessageIdEnum::CONFIRM` with `{clientOrderId}`. Used downstream after fraud/manual review confirms the order.

**External calls:** OMS `sendMessage(CONFIRM, ..., [clientOrderId])`.

---

### BP-INT-09 — Order status update (from ARM / 1C — synchronous)

**Triggers:**
- `POST /integration/order/status/{clientOrderId}/update` → `V1::updateStatusPublic` (line 2444)
- `POST /integration/orders/status/1c` → `V1::updateStatusByArm` (line 1900)
- `POST /integration/v2/orders/status/1c` → `V2::updateStatusByArmV2` (line 597) (`OPSOMN-10929, -10949`)

**Implementation (`updateStatusPublic`):**
1. Wrap in `safeWorkWithOrder` (lines 2503+) — catches throwables and rethrows as `OrderStatusUpdateError`.
2. Build OMS request batch:
   - `OmsClient::updateOrderStatus($orderId, $statusId)`
   - If `cancelationReasonId` present → `OmsClient::setOrderCancelationReason(...)`
3. `Connector::sendAndParse($requests)` — fan-out.

**Implementation (`updateStatusByArm`):** more elaborate, ~80 lines. Validates 1C ARM payload, batches item-level status updates (`updateOrderItemStatusByOrderId`), handles partial fulfillment counts.

**External calls:** OMS `/order/{id}/status`, `/order/{id}/cancelation-reason`, `/order/{id}/items/status`.

**Side effects:** none in Integration DB. Updates state in OMS.

**Quirks:**
- `safeWorkWithOrder` wraps almost every async-touching method — preserves error context but is a hand-rolled equivalent of a transactional wrapper.
- `OPSOMN-9091` introduced `fullAddress` handling for shipping addresses with custom attribute fallback.

---

### BP-INT-10 — Order status sync (cron: OMS → DWH)

**Trigger:** Laravel scheduler — `transfer:order-status:dwh` daily at `10 22 * * *` (UTC).

**Command:** `TransferOrderStatusDwhCommand` (`Exchange/Console/Commands/V1/Order/`).

**Implementation:** pulls last day's order status changes from OMS, dumps via SFTP (`DwhClient`) to DWH directory configured by `DWH_SFTP_CLIENT_ORDER_REMOTE_DIRECTORY`.

**External:** OMS (read), SFTP (write).

**Side effects:** file dropped on DWH SFTP.

---

### BP-INT-11 — Full order export (cron: OMS → DWH)

**Trigger:** Laravel scheduler — `transfer:orders:dwh` daily at `30 21 * * *`.

**Command:** `TransferOrderToDwhCommand` (`Exchange/Console/Commands/V1/Order/`). Delegates to `TransferServiceContract::transferOrdersToDwh`.

**External:** OMS (read), SFTP (write). May use `LoadOmsPagesCommand` helpers for paginated pulls.

---

### BP-INT-12 — Order reconciliation (cron: cbr & ecom — DWH compare)

**Trigger:** Laravel scheduler:
- `transfer:orders:recon cbr` at `0 0 * * *` UTC
- `transfer:orders:recon ecom` at `30 22 * * *` UTC

**Command:** `TransferOrderReconCommand` → spawns `TransferOrderReconChildCommand` per shard.

**Implementation:** `Exchange/Services/V1/Order/AbstractReconService.php` + `EcomReconService.php` / `CbrReconService.php`. Pulls a recon CSV from a counter-party (1C) and a parallel listing from OMS, computes diffs, raises issues. Uses `Mutators/V1/Order/{Ecom,Cbr}ReconOrderMutator.php` to canonicalize fields. Issues are logged through `Awg\Logger`.

**External:** 1C SFTP (input CSV) + OMS (current state).

---

### BP-INT-13 — Order export to OTS / 1C-ECOM / 1C-CBR (service-side, on-demand)

**Trigger:** `POST /order/export` (bearer-auth — service-side, not site/mobile).

**Implementation:** `V1/Order/OrderService::export($destination, $data)` (line 832). Switch on destination:
- `OTS` — `OrderExportOtsMutator` → `OtsClient::createOrder($mutated)` → parse OTS response into mutate/insert OMS custom attributes.
- `ECOM_1C` — filter on C&C / ECOM / ONLINE per status matrix (`OPSOMN-9091, -11783`) → `Ecom1CClient::createOrder($mutated)` → `parseEcom1CExportResponse`.
- `CBR_1C` — same shape, different filters.

**Quirks:**
- `OPSOMN-11783` introduced `validateAllKeys` for missed required fields — logs a `WARNING` but doesn't throw (graceful degradation).
- Lots of `is_enabled_availability_export_date_check` flag handling.
- Confluence page link in comments: `https://confluence.gloria-jeans.ru/pages/viewpage.action?pageId=63470445` (filter rules).

**Side effects:** OTS / 1C creates a counterparty record; Integration may write custom attributes back to OMS via `addItemCustomAttribute`, `addOrderCustomAttribute`.

---

### BP-INT-14 — Order export — ATOL fiscalization batch (cron)

**Trigger:** `export:order:atol` — invoked manually or on schedule (not in current `Kernel::schedule` — managed externally).

**Command:** `ExportOrderListForAtol` (`Exchange/Console/Commands/V1/Order/`). Pulls list of orders eligible for ATOL fiscalization → mutates via `AtolOrderMutator` → presumably writes via the fiscal service.

---

### BP-INT-15 — Fraud check (service-side)

**Trigger:** `POST /fraud/check` (bearer-auth).

**Implementation:** `V1/Order/OrderService::checkFraud($order)` (line 2539).

**Steps:**
1. Short-circuit unless `statusId === ON_VALIDATION`.
2. Personal data check — looks for `тест`/`test` substrings in names/emails. **Currently disabled** (line 2606 commented out, `NEWECOM-5404`).
3. Payment check (PREPAID only) — inspects `payments[]`.
4. Returns `$foundRuleIds` — set of `FraudRuleIdEnum::*`.

**Side effects:** none. Caller (likely OMS Camunda or ARM) decides what to do.

**Quirks:** the actual rules implementation is mostly **dead code** — primary check NEWECOM-5404'd.

---

### BP-INT-16 — Loyalty return (compensation)

**Trigger:** `POST /integration/internal/loyalty/return` (bearer-auth — service-side, e.g. called by OMS on order cancellation).

**Implementation:** `V1/Order/OrderService::returnLoyalty($orderId)` (line 4786).

**Steps:**
1. Fetch full order via `OmsClient::getOrderFull($orderId)`.
2. Read coupon id from order custom-attributes (note: the V2 logic call was preserved but commented "запретили это трогать", line 4819).
3. If no coupon — try to return loyalty bonuses: check `marketing.loyaltyPointsBurn`, `marketing.loyaltyId`, `customAttributes.usedPromoId`. If complete → `DiscountService::returnLoyaltyPoints($clientOrderId, $loyaltyId, $points, $usedPromoId, $baseStoreCode, $currencyId, $promoApplied)`.
4. If coupon present → different branch (further down, similar redemption rollback against discount service).

**External calls:** OMS `getOrderFull`, ENSI `DiscountClient::returnLoyaltyPoints`.

**Side effects:** ENSI discount-service rolls back the loyalty.

**Quirks:** ticket `OPSOMN-8636` annotated as "switched coupon resolution"; line 4819 comment indicates code-owner conflict.

---

### BP-INT-17 — Gift certificate purchase

**Trigger:** `POST /integration/order_certificate/create` (`OPSOMN-10336`).

**Implementation:** `V1/Order/OrderService::certificateCreate($order)` (line 5198).

**Steps:** custom shorter pipeline vs full order create — does **not** call `setCityData` (commented note line 5208 — `OPSOMN-10862`: format differs, country-isoCode passed at request build time as workaround). Calls OMS create-order with different shape. Then `createPaymentLink` for PREPAID certificates.

**Side effects:** new OMS order with `paymentTypeId = certificate-flow`.

**Quirks:** comments admit "по уму тут надо юзать setCityData, но формат запроса вообще другой. Потому костылим...".

---

### BP-INT-18 — Thank-you page (gift certificate)

**Trigger:** `GET /integration/certificate/thank-you-page/{clientOrderId}` (`OPSOMN-10354`).

**Implementation:** `V1/Order/OrderQueryController::getThankYouPage`. Fetches order, presents as TYP-shaped response.

---

### BP-INT-19 — Order list lookup (by shop / customer)

**Trigger:** `POST /integration/orders/points`.

**Implementation:** `V1/Order/OrderQueryController::getOrdersByShopId` → `V1::getOrderListByShopId($shopId)` (line 127). Loops over filter types (statuses), fires parallel `OmsClient::getOrders(...)` calls and aggregates. Lots of dead code with commented-out filter types (lines 280-303).

**Side effects:** none.

---

### BP-INT-20 — Proxy passthroughs to OMS

**Triggers (basic-auth, `/integration` prefix):**
- `POST /integration/order/list/full` → `ProxyController::getOrderListFull`
- `POST /integration/stock/full` → `ProxyController::getStockInit`
- `GET  /integration/settings/cancelationreason/list` (and `cancellation` typo alias, `OPSOMN-1702`) → `ProxyController::getCancelationReasonList`
- `POST /stock` → `ProxyController::getStockList` (NOTE: no `/integration` prefix on this one — service-side caller)

**Implementation:** `Service/Proxy/Services/V1/Common/ProxyService.php` — thin Guzzle/Connector forwarders to OMS. Reroutes auth, preserves headers/trace.

**Side effects:** none. Pure passthrough.

**Quirks:** the spelling alias for `cancelationreason` vs `cancellationreason` is a stable workaround.

---

### BP-INT-21 — Carrier price request (service-side)

**Triggers (bearer-auth):**
- `POST /carrier/{carrierId}/price/request` → `V1DeliveryApi\DeliveryQueryController::getCarrierTermList`
- `POST /carrier/express/tariff` → `V1DeliveryApi\CarrierQueryController::getCarrierTermList`
- `PUT  /carrier/express/tariff` → `V1DeliveryApi\CarrierActionController::setCarrierTermList`

**Actor:** **OMS Delivery → Integration**. This is the inverse direction — OMS calls Integration to resolve carrier tariffs from external carriers (CDEK, Russian Post, etc.).

**Implementation:** Integration forwards to the appropriate carrier client (5post, CDEK, Russian Post, etc. — via `WebGjISmpClient` or carrier-specific SDKs). The express tariff endpoints are for the GJ "express delivery" overlay.

**Quirks:**
- Bearer-auth — token-based service-to-service auth.
- `note: deprecated, see https://jira.awg.ru/browse/GJSTARFISH-858` — `POST /stock` is dual-routed (Proxy + this UserApi route). The bearer-auth one is deprecated; basic-auth one in Proxy is canonical.

---

### BP-INT-22 — Pickup-points cache rebuild (cron)

**Trigger:** Laravel scheduler — `pickup-points:cache` daily at `30 1 * * *` UTC (`OPSOMN-12209`).

**Command:** `PickupPointsCacheCommand` (`Exchange/Console/Commands/V1/Delivery/PickupPointsCacheCommand.php`). Optional `--carrierId` arg.

**Implementation:** Delegates to `DeliveryServiceContract::createCarrierListCache($output, $carrierId)`. Pulls full PVZ list per carrier from OMS (paginated `OmsClient::getPickupPoints` calls), stores in cache (`Service/Cache`). Endpoint `GET /integration/pickuppoint/list` and `v2/...` serve from this cache (`OPSOMN-9689`).

**Side effects:** cache populated; lock taken via `RaceConditionKeyEnum::PICKUP_POINT`.

---

### BP-INT-23 — Avatar / ASM (customer media)

**Trigger:** `POST /avatar/getlink` (bearer-auth).

**Implementation:** `V1/Avatar/AvatarService::getAsmLink(CustomerAvatar $customerAvatar, ?string $bearerToken)` (line 18) → `Connector::sendAndWait(AsmClient::getAsmAuth(...))`.

**External:** ASM service (Avatar Storage Manager) — auth handshake returning a signed link.

**Side effects:** none in Integration.

---

### BP-INT-24 — Stock changes notification (cron: OMS poll, push to consumers)

**Trigger:** Laravel scheduler — `notification:stock:oms-change` every 5 min (`*/5 * * * *`).

**Command:** `NotificationStockOmsChange` (`Exchange/Console/Commands/V1/Stock/`). Pulls OMS stock-change list (via `OmsClient::getStockChangeList`), publishes to consumers (Kafka and/or downstream callbacks).

**External:** OMS `/stock/change` (read), Kafka (write via `KafkaProducerRepository::produceStockChangedList`).

**Side effects:** Kafka events published.

---

### BP-INT-25 — Stock transfer OTS ↔ OMS (init + delta)

**Triggers (cron):**
- `transfer:stock:ots-init` once daily at `0 22 * * *` — full snapshot pull from OTS, push to OMS.
- `transfer:stock:ots-change` every 10 min `5,15,25,35,45,55 * * *` — delta.

**Commands:** `TransferStockOtsInitCommand`, `TransferStockOtsChangeCommand`.

**Implementation:** `Exchange/Services/V1/Stock/TransactionService.php`, persisted state in `Exchange/Repositories/V1/Stock/TransactionRepository.php` + Eloquent model `Exchange/Models/Database/Stock/Transaction.php` (real Integration DB table). Mutates via `OtsStockMutator` / `OmsStockMutator`.

**Side effects:** rows written to local `transactions` table for idempotency tracking; OMS stock updated via `OmsClient::sendStockList`.

---

### BP-INT-26 — Stock transfer CB-1C-RETAIL (init + auto + retry)

**Triggers (cron):**
- `transfer:stock:cb-1c-retail-init` (manual / occasional) — `TransferStockCbrInitCommand`.
- `transfer:stock:cb-1c-retail-auto` hourly `0 */1 * * *` — `TransferStockCbrAutoCommand`.
- `retry:stock:cbr-1c-auto` every minute `*/1 * * * *` — `RetryStockCbrAutoCommand` retries failed jobs.

**Commands:** `Exchange/Console/Commands/V1/Stock/*`.

**Implementation:** Pulls from CBR 1C (`CB1CRetailClient`), mutates via `CbrStockMutator`, posts to OMS.

**Side effects:** `transactions` table rows; OMS stock updated.

---

### BP-INT-27 — Stock delta generate / daemon

**Trigger:** standalone command `transfer:stock-delta:generate` (and disabled supervisor entry `transfer:stock-delta:daemon`).

**Implementation:** `StockDeltaGenerateCommand`, `StockDeltaDaemonCommand`. Reads Kafka stock deltas, applies via `StockDeltaMutator` → `TransferStockDeltaProcessor` → OMS or downstream.

**Quirks:** supervisor entry is **commented out** in `supervisor-laravel.conf` (lines 19-26) — the daemon is dormant. The on-demand `generate` is still callable.

---

### BP-INT-28 — Business-unit (warehouses, stores) sync — Kafka daemon

**Trigger:** **persistent daemon** (`integration-cron` supervisor) — `transfer:business-unit:daemon`.

**Command:** `BusinessUnitDaemonCommand` (`Exchange/Console/Daemons/V1/BusinessUnit/`). Signature `transfer:business-unit:daemon`. Consumes from a Kafka topic (`EnvelopeTypeEnum::BUSINESS_UNIT` envelopes), pushes to OMS via `TransferBusinessUnitProcessor`.

**Race-condition key:** `RaceConditionKeyEnum::BUSINESS_UNIT`.

**Companion command:** `transfer:business-unit:init` (`TransferBusinessUnitInitCommand`) — bootstrap full snapshot.

**External:** Kafka (consume), `BusinessUnitClient` (ENSI bu service) or OMS (write).

---

### BP-INT-29 — Product sync — Kafka daemon

**Trigger:** persistent daemon — `transfer:product:daemon`.

**Command:** `ProductDaemonCommand`. Consumes Kafka product envelopes, pushes to OMS.

**Companion:** `transfer:product:init` — `TransferProductInitCommand` for snapshot bootstrap.

**External:** Kafka (consume), OMS (write).

---

### BP-INT-30 — Order status — Kafka daemon (OTS → OMS)

**Trigger:** persistent daemon — `transfer:order-status:daemon`.

**Command:** `OrderStatusDaemonCommand`. Description: "получение из kafka сообщений со статусами заказа от OTS и передача их в OMS".

**Processor:** `TransferOrderStatusProcessor` (`Exchange/Processors/V1/Order/`).

**External:** Kafka (consume from OTS-producing topic), OMS (write status).

**Race-condition key:** `ORDER_STATUS`.

---

### BP-INT-31 — Order message — Kafka daemon

**Trigger:** persistent daemon — `transfer:order-message:daemon`.

**Command:** `OrderMessageDaemonCommand`. Description: "получение из kafka сообщений для OMS и последующая передача синхронно этих сообщений в OMS".

**Processor:** `TransferOrderMessageProcessor`. Sends OMS messages by topic via `KafkaProducerRepository::produceOmsMessage(messageId, orderId)`.

**External:** Kafka (consume + produce), OMS (write).

---

### BP-INT-32 — Event dispatcher — Kafka daemon (not auto-supervised)

**Trigger:** `transfer:event-dispatcher:daemon` — declared command (`OrderEventDispatcherDaemonCommand`) **but not started** by the supervisor config (`supervisor-laravel.conf` has only 4 daemons enabled).

**Description:** "получение из kafka сообщений со статусами заказа от OTS и передача их в OMS" (duplicates order-status description — looks like a leftover).

**Processor:** `TransferOrderEventDispatcherProcessor`. Repository: `KafkaProducerRepository::produceEventDispatcherMessage`.

**Status:** **dormant** in production deploy (supervisor doesn't start it). Either deprecated or selectively launched by ops.

---

### BP-INT-33 — Authentication middleware

**Implementation:**
- `basic-auth` middleware → `Service/Auth/Http/Middlewares/V1/Auth/BasicAuthMiddleware`. Used for site/mobile-facing endpoints (`/integration/*` mostly).
- `bearer-auth` middleware → `Service/Auth/Http/Middlewares/V1/Auth/BearerAuthMiddleware`. Used for service-to-service (export, fraud, carrier, avatar).

**JWT bearer scheme:** Integration **validates** tokens minted by ENSI customer-auth (or admin-auth/ASM for some endpoints). It does **not** mint tokens. ENSI auth config: `ENSI_AUTH_CREDENTIALS_CLIENT`, `ENSI_AUTH_CREDENTIALS_SECRET` (`Service/GloriaJeansSupport/config/ensi_auth.php`).

**Tenant id:** hard-coded default `gloriajeans` (`INTEGRATION_TENANT_ID` env override possible). All OMS calls tag this in `tenantId` body field.

**Quirks:** Integration does **not** proxy customer auth to a "login" endpoint — it just validates. Customer profile flows (address, preferences, history) live in ENSI customers-service, **not** Integration.

---

### BP-INT-34 — Customer profile / addresses

**Where it actually lives:** **NOT in Integration.** This domain is owned by:
- ENSI `customers` service (profiles, addresses)
- ENSI `customers-api-web` BFF (public surface for site/mobile)

Integration does not have any customer/address CRUD endpoints. Addresses are passed inline as part of `order/create` request `shipping.address` block and forwarded to OMS.

**Cross-system flow:** site/mobile → ENSI customers-api-web → ENSI customers (profile/address persistence) → only at checkout commit does an address shape pass through Integration to OMS.

> If a process map needs a customer-profile process node, it belongs in the ENSI BP catalog, not here.

---

### BP-INT-35 — Order status / history readback

**Available endpoints in Integration:**
- `POST /integration/orders/points` (BP-INT-19) — list orders by shopId.
- No dedicated public "GET order by id / customer" — site/mobile read order status via **ENSI customers-api-web**, which talks to OMS directly via its own `OmsClient`.

Integration's order-readback methods (`getOrderStatusHistory`, `getOrderFull`, `getItemsStatusHistory`) are called internally from `returnLoyalty` and `checkFraud` flows, not exposed publicly.

> Site/mobile order-history UI uses ENSI customers-api-web → OMS, **bypassing Integration**. Document that flow in the ENSI BP catalog.

---

### BP-INT-36 — Returns initiation

**Where it actually lives:** **NOT in Integration.** Returns are managed by:
- ENSI customers service (return requests, status)
- OMS `core/Order` + `core/Delivery` (physical return)
- Possibly OMS `oms-ui` for ARM-side processing

Integration's only return-adjacent function is `returnLoyalty` (BP-INT-16), which is a **compensation** for cancellations, not a customer-initiated return.

> Returns initiation BP should be sourced from ENSI / OMS researchers.

---

## Quirks & legacy in play (Integration-specific summary)

| Quirk | Where | Why introduced |
|-------|-------|----------------|
| **V1/V2/V3/V4 of `order/create` all live** | `Service/UserApi/routes/api.php` | Backward compat for 1C/ARM/legacy site; not removed because routes still hit prod |
| **`paymentAcquirerId = yookassa` lock** | `V4/Order/OrderService.php:131-141` | `OPSOMN-9356` — single-acquirer policy |
| **`paymentChannel = 'sbp'` commented out** | `V4/Order/OrderService.php:1016-1025` | Awaits "таблица Гульдар" (`OPSOMN-11413`) |
| **V4 courier matches by id only (regression)** | `V4/Order/OrderService.php:541` (`fillSelectedCourierDeliveryInterval`) | `OPSOMN-11195` rollback missed courier path |
| **`getDeliverySummary` not in contract** | `V2/Delivery/DeliveryServiceContract` (missing decl) | Contract drift; DI binds at runtime |
| **`cancelationreason` typo alias route** | `Proxy/routes/api.php` | `OPSOMN-1702` keeps both spellings working |
| **`acquierId` / `acquierTransactionId` field typos** | OMS contract, propagated as-is through `V4/Order/OrderService.php` | OMS bug; Integration doesn't normalize |
| **No outbox row on order create** | All `*Order/OrderService::create` | Sync-only by design; async via Kafka daemons for status-back |
| **Personal data fraud rule disabled** | `V1/Order/OrderService.php:2606-2611` | `NEWECOM-5404` — disabled in prod |
| **Stock delta daemon disabled** | `supervisor-laravel.conf:19-26` | Commented out — generate command still callable |
| **Event dispatcher daemon dormant** | `OrderEventDispatcherDaemonCommand` exists, supervisor doesn't start it | Likely deprecated; description duplicates order-status |
| **POST `/stock` dual-routed** | UserApi route deprecated (bearer-auth), Proxy canonical (basic-auth) | `GJSTARFISH-858` — migration |
| **fullAddress workaround** | `V1/Order/OrderService.php:5168 getShippingFullAddress` | `OPSOMN-9091, -7983` — synthesized when customAttribute absent |
| **`is_enabled_availability_export_date_check` flag spaghetti** | `V1/Order/OrderService.php` from line 3955 onward | Conditional check toggling — likely staged rollout left in code |
| **Lumen + facades + eloquent** | `bootstrap/app.php:30-34` | Not vanilla Lumen — must verify behavior on every PR |
| **All routes live in service-providers** | `Service/UserApi/Providers/UserApiServiceProvider`, `Service/Proxy/Providers/ProxyServiceProvider` | `routes/web.php` is empty — easy to miss |
| **Tenant id hardcoded default `gloriajeans`** | `config/integration.php`, used by every OMS call | Multi-tenant abstraction never used |

---

## Process taxonomy

| Tier | Processes |
|------|-----------|
| **Checkout-time (sync, public-facing)** | BP-INT-01, BP-INT-02, BP-INT-03, BP-INT-04, BP-INT-05, BP-INT-06, BP-INT-07 |
| **Order lifecycle callbacks (sync)** | BP-INT-08 (confirm), BP-INT-09 (status update), BP-INT-15 (fraud), BP-INT-16 (loyalty return), BP-INT-17 (certificate), BP-INT-18 (TYP) |
| **Order/Stock lookups (sync)** | BP-INT-19, BP-INT-20, BP-INT-21, BP-INT-23 |
| **Cron — DWH/recon exports** | BP-INT-10, BP-INT-11, BP-INT-12, BP-INT-14 |
| **Cron — Stock sync** | BP-INT-22, BP-INT-24, BP-INT-25, BP-INT-26, BP-INT-27 |
| **Persistent Kafka daemons** | BP-INT-28, BP-INT-29, BP-INT-30, BP-INT-31, BP-INT-32 (dormant) |
| **Cross-cut (auth, proxy)** | BP-INT-33, BP-INT-20 |
| **Lives elsewhere (referenced)** | BP-INT-34 (customer profile → ENSI), BP-INT-35 (order history → ENSI/OMS), BP-INT-36 (returns → ENSI/OMS) |

---

## Cross-system delegation needed for full BP map

| Process node | Owning system | Researcher |
|--------------|---------------|------------|
| Customer profile / addresses CRUD | ENSI customers + customers-api-web | `ensi-researcher` |
| Order history readback to site/mobile | ENSI customers-api-web (calls OMS) | `ensi-researcher` |
| Returns initiation flow | ENSI + OMS | `ensi-researcher` + `oms-researcher` |
| YooKassa webhook handling | OMS `core/pay-service` | `oms-researcher` |
| Camunda BPM order processes | OMS `core/Camunda` + `awg/bpmn-process` | `oms-researcher` + `camunda-bpm-engineer` |
| Interval generation root cause | OMS `core/Settings` `DeliveryIntervalsByLogisticGroups.java` | covered in `do../research/2026-05-20-checkout-order-creation.md` |
| Carrier integrations (CDEK, Russian Post, 5post, Dalli) | OMS `core/Delivery` + SDK libs | `oms-researcher` |
| Customer-auth JWT minting | ENSI `customer-auth` / `admin-auth` | `ensi-researcher` |
| Basket recalc on login (merge guest+user) | ENSI baskets + customer-auth | `ensi-researcher` |

---

## Evidence trail

Routes:
- `platform/integration/integration/www/app/Service/UserApi/routes/api.php` (public API + service API split by middleware)
- `platform/integration/integration/www/app/Service/Proxy/routes/api.php` (passthroughs)
- `platform/integration/integration/www/routes/web.php` (empty)

Bootstrap:
- `platform/integration/integration/www/bootstrap/app.php` (Lumen extended app, facades + eloquent, registers ~30 providers including msq-client, prometheus, healthcheck)

Schedules & daemons:
- `platform/integration/integration/www/app/Console/Kernel.php` (scheduler entries)
- `platform/integration/integration/containers/integration-cron/supervisor-laravel.conf` (always-on daemons)
- `platform/integration/integration/containers/integration-cron/Dockerfile`

Order services:
- `platform/integration/integration/www/app/Service/UserApi/Services/V1/Order/OrderService.php` (5200+ lines — legacy + cross-version helpers)
- `platform/integration/integration/www/app/Service/UserApi/Services/V2/Order/OrderService.php`
- `platform/integration/integration/www/app/Service/UserApi/Services/V3/Order/OrderService.php`
- `platform/integration/integration/www/app/Service/UserApi/Services/V4/Order/OrderService.php` (current site/mobile path)

Delivery services:
- `platform/integration/integration/www/app/Service/UserApi/Services/V1/Delivery/DeliveryService.php`
- `platform/integration/integration/www/app/Service/UserApi/Services/V2/Delivery/DeliveryService.php` (split-shipment summary)
- `platform/integration/integration/www/app/Service/UserApi/Services/V3/Delivery/DeliveryService.php`

OMS clients:
- `platform/integration/integration/www/app/Service/OmsClient/Clients/Client.php` (V1 client)
- `platform/integration/integration/www/app/Service/OmsClientV2/Clients/*` (V2 client)
- `platform/integration/integration/www/app/Service/OmsClient/config/client.php` (env: `OMS_SERVICE_CLIENT_BASE_URL`, `..._TIMEOUT`, `..._ACCESS_TOKEN`)

Outbox / Kafka:
- `platform/integration/msq-client/migrations/create_msq_client_tables.php` (`outbox_messages` schema)
- `platform/integration/msq-client/src/Console/MsqOutboxSendCommand.php`
- `platform/integration/msq-client/src/MsqClientManager.php`
- `platform/integration/msq-client/src/Database/OutboxMessage.php`
- `platform/integration/integration/www/app/Service/Exchange/Repositories/V1/Common/KafkaProducerRepository.php`
- `platform/integration/integration/www/config/msq-client.php` (Kafka broker config)

Console commands:
- `platform/integration/integration/www/app/Service/Exchange/Console/Commands/V1/Stock/*`
- `platform/integration/integration/www/app/Service/Exchange/Console/Commands/V1/Order/*`
- `platform/integration/integration/www/app/Service/Exchange/Console/Commands/V1/Delivery/PickupPointsCacheCommand.php`
- `platform/integration/integration/www/app/Service/Exchange/Console/Daemons/V1/*/...DaemonCommand.php`

Companion artifact (deeper for checkout):
- `do../research/2026-05-20-checkout-order-creation.md`

---

## What this catalog deliberately does **not** cover

1. **Field-level data shapes** of OMS requests/responses — read OMS researcher artifacts or the `OmsClient/Clients/Client.php` method signatures directly.
2. **ENSI customers-api-web internals** — that BFF is a separate process catalog (`ensi-researcher`).
3. **Mobile / site state machines** during checkout — covered in `do../research/2026-05-20-checkout-order-creation.md` (Site, Mobile sections).
4. **Camunda BPM processes** (post-order-create) — owned by `oms-researcher` + `camunda-bpm-engineer`.
5. **YooKassa SDK / RN bridge level** — owned by `mobile-researcher`.
6. **DBT / DWH semantics** of exported orders — beyond Integration's responsibility.

