# Контракт создания заказа — Integration → OMS (якорь для TO-BE)

**Дата:** 2026-05-29
**Статус:** факты из кода (read-only), 2 расследования: integration (что ИС шлёт), oms (что OMS требует/делает).
**Зачем:** проектируем «идеальный чекаут» от замкового камня. Если зафиксировать ЧТО реально нужно OMS, чтобы создать заказ — то весь пред-чекаут это машина для сборки этого payload. «Идеальный пред-чекаут» = минимум, достаточный для этого контракта.
**Связанные:** [`2026-05-29-checkout-as-is-archaeology.md`](2026-05-29-checkout-as-is-archaeology.md).

---

## 0. Главные выводы (для дизайна)

1. **OMS — пермиссивный и доверяющий.** `OrderDto` с `@JsonIgnoreProperties(ignoreUnknown=true)` (молча роняет неизвестные поля); bean-валидация поверхностная (`shipping`/`items`/`packages`/`payment` даже не `@Valid`-каскадятся). **Реальный обязательный контракт — внешняя JSON-схема `order_create`**, Settings-driven, отдаётся отдельным сервисом (`api.validation.json_schema.external.service.name` → `GET /validation/schema/order_create`) — её НЕТ в репо Order, нужно читать живьём по env.
2. **Two-phase truth (это «разумное зерно» — сохранить).** Клиент шлёт *черновик* заказа; Integration на commit **заново фетчит цену/сток/скидки/интервалы и перезаписывает** их. Клиентский `totalCost` — лишь **checksum-тривога** (`InvalidateTotalCost` при расхождении). То есть клиент говорит ЧТО выбрано, сервер пере-выводит все деньги/сток/логистику сам.
3. **OMS доверяет выбору доставки и суммам.** На create OMS **НЕ ре-валидирует** интервал/дату/склад против logistics (единственный logistics-вызов — пороги бесплатной доставки). Суммы берёт через `getValueOrDefault(пришло, посчитано)` — т.е. доверяет присланному, расчёт лишь fallback. Значит interval-drift — целиком проблема ИС (re-fetch), не OMS.
4. **Create НЕ стартует Camunda.** OMS персистит заказ → публикует Kafka `ORDER_CREATED` → downstream `confirmationProcess` (резерв, фрод, маршрутизация, пересчёт, OTS/1C-экспорт) запускается с этого события. Резервирование и решение о маршрутизации OMS делает САМ в Camunda, не на create.
5. **Идемпотентность = `clientOrderId`** (scoped tenant+brand): Redis-lock 30с (`OrderCreationCacheServiceImpl`, key `tenantId+clientOrderId+brandId`) + DB-уникальность (`OrderAlreadyCreatedException`). **КРИТИЧНО:** если `clientOrderId=null`, OMS генерит свой → оба guard’а обходятся, каждый ретрай = новый заказ. **TO-BE обязан слать стабильный `clientOrderId`.**

---

## 1. Минимально необходимый контракт (что OMS реально нужно)

OMS создаст заказ и запустит confirmationProcess, получив:

| Группа | Минимум | Примечание |
|--------|---------|-----------|
| **clientOrderId** | стабильный уникальный id | ключ идемпотентности; минтится в пред-чекауте, НЕ null |
| **customer** | resolvable: `id` ИЛИ `phone` | OMS сам резолвит/создаёт customer, дотягивает FIO получателя из shipping |
| **recipient** | firstName, lastName (+contact email/phone) | под shipping |
| **items[]** | `productId` (артикул), `quantity`, resolved `price`, resolved `discount` | OMS не пересчитывает обязательно (доверяет) |
| **shipping selection** | `deliveryTypeId`, `deliveryIntervalId`, `promissedDeliveryDate`, `dispatchWarehouseId`/`pickupStoreId`/`pickupPointId`, `carrierId`+`carrierTariffId`, `logisticGroupId`/`deliveryRuleId`, address(fias+coords) | OMS НЕ выбирает — резервирует/экспортирует против этого |
| **totals** | `totalCost` (+payableCost) | доверяется; checksum |
| **paymentTypeId** | PREPAID/COD | оплата (getlink) — отдельный downstream-вызов, НЕ в create |
| **packages[]** | хотя бы одна | OMS хранит **как прислали** (не пересобирает) — можно слать реальный split |

Всё остальное (резерв, фрод, маршрут, пересчёт, экспорт) — OMS в Camunda.

---

## 2. Что из текущего payload — наведённый костыль (выкинуть в TO-BE)

| Костыль | Где | Почему выкинуть |
|---------|-----|-----------------|
| **qty-explosion**: `quantity=N` → N позиций по 1шт с custom-attr `position` | `V1 OrderService::processPositionItems:3263` | Артефакт ИС (для sortBySales/promo-mapping), НЕ требование OMS. OMS примет `{productId, quantity, unitPrice, lineDiscount}`. Трейт `UsesCustomAttributes` сам помечен `@deprecated`/«костыль». |
| **Одна захардкоженная посылка** `GJ<id>`, dims 0.1³, вес 900/шт | `V1 addPackages:3181` | OMS хранит packages как прислали → TO-BE может слать реальный multi-package split (он переживёт create) ИЛИ одну — на выбор. |
| **custom-attributes как side-channel**: `totalBaseAmount`, `totalDiscount`, `deliveryDaysCount`, `orderOriginalCost`, `position`, `priceType`, `discountIntegrationCallbackData`, `fullAddress` | везде | Типизированные данные, протащенные строками name/value. Промоутить в first-class поля контракта. |
| **`payableCost` == `totalCost`** | calculateTotals | избыточно |
| **`payment[].cardNumber`** | rules:145 | рудимент; реальная оплата — отдельный `/onlinepay/{id}/getlink` |
| **deep version inheritance V1→V4** + `match` по версиям в доменной логике | Order/Delivery сервисы | размазанное поведение |

---

## 3. Поток (как сейчас) и границы

```
КЛИЕНТ (черновик заказа: selection + checksum totalCost + stable clientOrderId)
  │  POST /api/.../checkout/commit  (ENSI CommitOrderAction — локальная валидация)
  ▼
INTEGRATION V4 OrderService::create  (СТЕЙТЛЕСС, 14 шагов):
  setCityData → loadBaseStore → checkStock → validateAvailable
  → processPositionItems(qty-explode) → loadPrices(перезапись) → calculateOrderDiscounts
  → calculateTotals(checksum-guard) → calculateShippingV4(RE-FETCH интервалов ← interval-drift!)
  → addPackages(одна GJ<id>) → POST /order/create (весь $order как есть)
  → [после create] prepareAndRunCallbacks (списать купон/бонус) + createPaymentLink (getlink)   ← НЕТ компенсации/саги
  ▼
OMS /order/create (OrderServiceImpl):
  Redis-lock(clientOrderId) → DB-dedup → saveOrUpdateCustomer → fillOrderForDB
  → setCalculationField(getValueOrDefault: доверяет присланному) → persist(shipping/items/packages/marketing/payment)
  → Spring ORDER_CREATED → (AFTER_COMMIT) Kafka
  ▼
CAMUNDA confirmationProcess (с Kafka-события): статус→ON_VALIDATION, фрод, РЕЗЕРВ (createReservation по dispatchWarehouseId/pickupStoreId),
  пересчёт, promo-recalc, OTS/1C-экспорт (orderExportWithFeedbackActivity)
```

**Риск без саги:** купон/бонус списываются и платёжная ссылка создаётся ПОСЛЕ create без компенсации. Падение после create-до-debit или ретрай — нет отката. TO-BE: идемпотентный create + сага/outbox.

---

## 4. Что это даёт для пред-чекаута

Раз OMS пере-выводит деньги/сток/скидки сам (или доверяет), а выбор доставки берёт готовым — **единственная задача пред-чекаута**: дать пользователю собрать валидный **selection** и выдать на commit:
- стабильный `clientOrderId`,
- выбор доставки (тип + interval id + дата + склад/ПВЗ + тариф/ТК), **согласованный во времени** (тут и нужна персистентная сессия + пиннинг даты — §6 AS-IS),
- получателя + адрес (fias + координаты),
- промо-намерение (`marketing.promoApplied`),
- checksum `totalCost`.

Это **радикально тоньше**, чем нынешняя декартова general-data. Жирная матрица «способ × склад × поштучная доступность» нужна была лишь чтобы пользователь ткнул в один вариант — а на выходе нужен только этот один выбор + его устойчивый id.

---

## 5. Открытое (добрать перед фиксацией контракта TO-BE)
- **Живая JSON-схема `order_create`** (резолвить `api.validation.json_schema.external.service.name` в `awg/cloud-configs/<env>` → `GET /validation/schema/order_create`) — единственный авторитетный список обязательных полей. → `oms-java-engineer`.
- **Где минтится `clientOrderId`** в пред-чекауте (ENSI baskets? фронт?) и гарантирована ли стабильность/уникальность. → `ensi-researcher`/`site-researcher`.
- **`ORDER_CREATED` → `confirmationProcess` binding** в `core/Camunda`. → `camunda-bpm-engineer`.

## Приложение: ключевые файлы
**Integration:** `app/Service/UserApi/Services/V4/Order/OrderService.php` (create 121-395, calculateShippingV4 415-530, createPaymentLink 996); `.../V1/Order/OrderService.php` (addPackages 3181, calculateTotals 3212, processPositionItems 3263, loadPrices 4202); `.../Http/Requests/V4/Order/System/OrderCreateRequest.php` (input rules); `app/Service/OmsClient/Clients/Client.php:665` (create) `:680` (getlink).
**OMS:** `core/Order/.../controller/OrderController.java:108`; `.../controller/helper/OrderControllerDelegate.java:34-76` (Redis-lock, clientOrderId gen); `.../dto/order/OrderDto.java` (+OrderDetails/ShippingDto/PackageDto); `.../services/orderService/OrderServiceImpl.java:244-589`; `.../services/shippingService/ShippingServiceImpl.java:178-194`; `core/oms-json/.../ExternalServiceJsonSchemaProvider.java:28-57`; `awg/bpmn-process/process/gloriajeans/confirmationProcess.bpmn`.
