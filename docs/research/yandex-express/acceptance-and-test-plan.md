# Acceptance and test plan: Yandex Express SFS

Дата актуализации: 2026-07-10

## Preconditions

- Starfish24 provided and approved interval/order payload contract.
- Exact Express carrier/tariff identifiers are configured on test stand.
- Retail/1C mapping decision is documented.
- At least two test stores in different pilot timezones are configured.
- Site and supported Mobile versions understand `method=express`.
- CDEK remains enabled for regression/parallel availability.

## Contract acceptance

### C1. Starfish24 interval

For an eligible store/address/cart the response contains:

- separate Yandex Express carrier id;
- `fulfillmentTypeId = sfs`;
- selected source `dispatchWarehouseId`;
- carrier tariff id;
- dynamic delivery cost;
- only `prepaid` payment type;
- same-day interval/SLA data;
- quote expiration or documented validity semantics.

The carrier id must not equal `yandexNextDayDelivery`.

### C2. Ranking

- highest quantity/fullness store wins;
- on equal fullness, nearest store wins;
- result is deterministic for equal inputs;
- client is not offered unordered intervals from all SFS stores.

### C3. Working hours

- local source-store timezone is used;
- closed store produces no Express offer;
- open store near closing produces no offer when picking+handover cannot finish;
- special/holiday schedule overrides regular schedule;
- missing timezone/hours fails closed and is observable;
- a store in another timezone is evaluated using its own local time.

### C4. Coexistence

- warehouse availability does not hide Express;
- CDEK and Yandex Express can be shown together;
- disabling Yandex does not disable CDEK.

## E-commerce acceptance

### E1. customer-api-web

- old response groups the new carrier into `deliveryExpress`;
- General Data exposes separate `method=express`;
- `yandexNextDayDelivery` is not grouped as Express;
- dynamic cost and prepaid-only reach clients unchanged;
- no Express method is returned when there is no valid offer.

### E2. Site

- separate «Яндекс Экспресс» card is visible next to standard delivery;
- card shows SLA and dynamic price;
- global free-delivery threshold never changes Express price;
- only online payment is selectable;
- selecting Express sends its interval id/store/carrier to commit;
- warehouse option remains visible;
- stale offer triggers refresh/reselection, not silent CDEK substitution.

### E3. Mobile

- same functional behavior as Site;
- Express has a real method/route/state, not only a label;
- unsupported old app versions do not auto-select an unknown method;
- prepaid-only and dynamic price survive preview and commit.

### E4. Integration

- V4 order create preserves selected server-side interval fields;
- resulting OMS order has SFS + exact Starfish24 carrier/tariff/store;
- dynamic cost is not replaced by 299 ₽/0 ₽ threshold logic;
- accounting/CBR/ARM mapping resolves to the approved Retail value;
- SFS order does not enter OTS route;
- `clientOrderId` remains stable on retry after delivery refresh.

## Fulfillment acceptance

### F1. Store lifecycle

- Retail imports the order;
- usual SFS assembly task is available;
- store hands order to Yandex courier without a CDEK-only UI/block;
- status returns through existing Integration contract;
- no mandatory new store operation is introduced for MVP.

### F2. Starfish24 carrier lifecycle

- registration/courier call creates an external id;
- retries are idempotent;
- technical failure is observable;
- cancellation before and after registration is handled;
- duplicate/out-of-order callbacks do not corrupt OMS state;
- final order/item state is correct.

## Test matrix

| ID | Scenario | Expected result |
|---|---|---|
| T-01 | Eligible SFS store, Yandex quote available | Separate Express option with dynamic price and prepaid. |
| T-02 | Cart available in store and warehouse | Express and standard warehouse delivery both visible. |
| T-03 | CDEK and Yandex enabled for same store | Both options visible and selectable independently. |
| T-04 | Several stores, different fullness | Store with greater fullness selected. |
| T-05 | Equal fullness, different distance | Nearest store selected. |
| T-06 | Store closed in its timezone | Express absent; other methods remain. |
| T-07 | Store open but cutoff passed | Express absent. |
| T-08 | Stores in different timezones | Each evaluated in local source-store time. |
| T-09 | Special holiday schedule | Special schedule determines availability. |
| T-10 | Missing timezone/schedule | Express absent and configuration error observable. |
| T-11 | Yandex quote unavailable | Express absent; CDEK/other delivery unaffected. |
| T-12 | Dynamic price above/below free threshold | Exact Yandex price displayed and charged. |
| T-13 | Previously selected COD, then Express | Payment resets/restricts to prepaid. |
| T-14 | Quote expires before commit | Business error; methods refresh; explicit reselection. |
| T-15 | Quote price changes before commit | Updated price flow follows approved confirmation contract. |
| T-16 | Successful Site order | Correct interval/carrier/store/cost in OMS and Retail. |
| T-17 | Successful Mobile order | Same contract and lifecycle as Site. |
| T-18 | Cancel before Yandex registration | OMS/Retail/payment consistent; no external orphan. |
| T-19 | Cancel after Yandex registration | External cancellation idempotent; OMS compensation completes. |
| T-20 | Duplicate Yandex callback | No duplicate transition/payment side effect. |
| T-21 | Disable Yandex for store | New Express offers disappear; existing orders continue. |
| T-22 | CDEK regression | Existing SFS CDEK happy/cancel paths unchanged. |
| T-23 | Yandex Next Day regression | Warehouse→PVZ behavior and UI classification unchanged. |
| T-24 | Unsupported Mobile version | No broken/auto-selected Express state. |

## Evidence to collect

- Jira issue `OPSOMN002-46` and approved payload contract reference;
- Starfish24 OMS version/config id;
- interval response without personal data;
- source-store timezone/hours/ranking evidence;
- BFF response for Site and Mobile;
- Integration order-create fields;
- OMS order/process/external carrier id;
- Retail/ARM document and handover event;
- payment type and charged delivery cost;
- cancellation/status traces;
- CDEK and NDD regression results.

## Go/no-go

Go:

- C1–C4, E1–E4 and F1–F2 passed;
- required Site/Mobile wave passed its client tests;
- closed/cutoff stores do not produce offers;
- dynamic price and prepaid-only are proven end to end;
- CDEK/NDD regressions are green;
- independent disable switch and rollback owner are known.

No-go:

- no exact payload contract from Starfish24;
- target carrier is confused with `yandexNextDayDelivery`;
- Express can be created from a closed/late store;
- warehouse availability hides Express;
- frontend applies free-delivery threshold or allows COD;
- Site/Mobile cannot persist selected Express interval;
- Retail cannot accept/handover the order;
- cancellation/status ownership is unresolved.
