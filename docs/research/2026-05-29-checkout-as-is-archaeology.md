# Checkout AS-IS — археология (general-data, перерисовки, комплектация)

**Дата:** 2026-05-29
**Статус:** факты из кода (read-only), 4 параллельных расследования: site (главный), integration, ENSI, mobile.
**Цель:** разобрать как РЕАЛЬНО устроен текущий чекаут перед проектированием «идеального». НЕ переписываем — восстанавливаем «разумное зерно» и отделяем его от костылей.
**Связанные:** [`2026-05-20-checkout-order-creation.md`](2026-05-20-checkout-order-creation.md), [`../bp/03-browse-cart-precheckout.md`](../bp/03-browse-cart-precheckout.md), [`../bp/04-checkout-order-creation.md`](../bp/04-checkout-order-creation.md).

---

## 0. TL;DR — корень боли в одном абзаце

`general-data` — это **один жирный aggregate, материализующий декартово произведение** «способ доставки × склад/магазин × поштучная доступность каждой позиции корзины». Его производит OMS Logistics (комплектация и интервалы), Integration фанит-ином 4 способа доставки в одну матрицу, ENSI `customers-api-web` отдаёт её фронту целиком. **Состояние нигде не персистится** — OMS пересчитывает комплектацию и **регенерирует id интервалов на каждый вызов** от полного содержимого корзины. Фронт зеркалит этот жирный объект как один плоский signal-срез, который при любой смене параметра **перезаписывается целиком** (`patchState` рвёт все ссылки, селекторы без equality) → каждый `| async` перерисовывается = «моргание». А поскольку id интервала между `general-data` и commit разные, commit ловит **400 SelectedIntervalNotFound**. Это не баг в одном месте — это **структурное свойство контракта**, продублированное на всех четырёх слоях.

«Разумное зерно» существует и его видно (см. §8): единый консолидированный расчёт доставки + чистый пайплайн `validate→price→discount→ship→create` + типизированные DTO. Костыли — это отсутствие гранулярности, отсутствие персистентности выбора и наслоения версий V1→V4.

---

## 1. Сквозная цепочка (кто что делает)

```
                    ┌─────────────────────────── general-data (pre-checkout) ───────────────────────────┐
 Site (NgRx-less    │                                                                                     │
 SignalStore)  ─────┤  GET /api/v2|mobile-v5/checkout/general-data                                        │
 Mobile (Apollo     │     ENSI customers-api-web : GetCheckoutGeneralDataV2Action  (~8 апстримов)         │
 makeVar)      ─────┤        └─ GET /integration/delivery/summary                                         │
                    │              Integration V2 DeliveryService  (до 8 round-trip в OMS, async-пул)     │
                    │                 └─ OMS Logistics /logistics/{delivery-intervals,pickup-stores,…}    │
                    │                       КОМПЛЕКТАЦИЯ + интервалы (id регенерируются на каждый вызов)   │
                    └─────────────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────── commit (создание заказа) ──────────────────────────┐
                    │  POST /api/v3|mobile-v5/checkout/commit                                             │
                    │     ENSI CommitOrderAction  (локальная валидация → ResolveCommonDeliveryData)       │
                    │        └─ POST /integration/v4/order/create                                         │
                    │              Integration V4 OrderService  (СТЕЙТЛЕСС: всё пересчитывает заново,      │
                    │                 RE-FETCH интервалов → match по id → 400 если drift)                 │
                    │                 └─ OMS POST /order/create → Camunda confirmationProcess             │
                    └─────────────────────────────────────────────────────────────────────────────────────┘
```

| Канал | general-data | commit | Состояние чекаута |
|-------|-------------|--------|-------------------|
| Site | `GET /api/v2/checkout/general-data` | `POST /api/v3/checkout/commit` | самописный **SignalStore** (`order.store.ts`, 1907 строк) |
| Mobile | `GET /api/mobile/v5/checkout/general-data` | `POST /api/mobile/v5/checkout/commit` | **Apollo `makeVar`** (отдельная модель от всего приложения) |
| Integration (internal) | `GET /integration/delivery/summary` | `POST /integration/v4/order/create` | **нет состояния** — пересчёт с нуля |

---

## 2. general-data: форма и почему распухшая

**Где собирается:** ENSI `customers-api-web` → `GetCheckoutGeneralDataV2Action::execute` (`app/Domain/Orders/Actions/GetCheckoutGeneralDataV2Action.php:60-132`), отдаётся `CheckoutGeneralDataResource` (`.../Resources/CheckoutGeneralData/CheckoutGeneralDataResource.php:11-21`).

**5 верхнеуровневых секций:** `additionalSales`, `recipient`, `delivery`, `storesData`, `productsData`.

**Жир сидит в `delivery`** (`DeliveryResource.php:13-20`) — отдаёт **ОДНОВРЕМЕННО все 4 способа доставки** плюс преференсы:
- `previousDelivery`, `customerPreferences`
- `delivery` (курьер), `pickup` (ПВЗ), `pickupInStore` (самовывоз), `reserveInStore` (резерв)

Каждый способ → `inventories[]` → `inventory` → **`cartAvailability`** = построчная доступность КАЖДОЙ позиции корзины (`StoreInventoryResource` → `CommonInventoryResource`). Итог: один ответ = **матрица `способ × склад/магазин × позиция_корзины`**. Нет способа спросить «только курьер для города X» — поэтому смена любого параметра требует перезапроса ВСЕГО.

**Апстримы на один general-data (~8 вызовов, ENSI-сторона):** customers.getCustomer, baskets.searchBasketCustomer, catalog-cache.searchProductCards (enrichment корзины), bu.resolveRegion, customers.searchDeliveryPreferences **×2** (дубль: по всем городам + по выбранному, merge в коде — `GetCheckoutGeneralDataV2Action.php:82-90`), `integration/delivery/summary`, bu.searchStores, baskets.searchAdditionalSales.

**Хорошая новость (зерно):** basket берётся с `withAdditionalRequests:false` (`GetCurrentBasketAction.php:120`), тяжёлый delivery-расчёт **консолидирован** в один `/integration/delivery/summary`, enrichment корзины — один батч в catalog-cache по offer_id (без N+1 на уровне HTTP). Раздувается не число запросов, а **размер ответа** (inventory-матрица).

---

## 3. Производитель матрицы — Integration `delivery/summary`

`V2 DeliveryService::getDeliverySummary` (`app/Service/UserApi/Services/V2/Delivery/DeliveryService.php:514-867`).

На **один** summary — до **8 round-trip в OMS** (часть параллельно через Guzzle async-пул `Connector.php:61-94`):
1. OMS city golden-record (зависимость для остального)
2. `/logistics/delivery-preliminary` с `returnStock=true` (поштучный сток для PVZ — раздувает payload)
3. concurrent: `/logistics/pickup-stores/v1` (самовывоз-интервалы) + `/logistics/delivery-intervals` (курьер); PVZ — БЕЗ отдельного вызова, реверс-инжиниринг из `preliminary.cart` (OPSOMN001-488, `:577-617`)
4. условно: pickup-point info, warehouse list, warehouse info (per missing id), 2× Settings (MAX_WAITING_DAYS)

Затем тяжёлый ре-шейпинг в PHP (`remapDeliveryCourier`, `sortWarehouses`, `compactStores`, `array_merge(...array_map(...))` по вложенным `inventories[].options[]`) — матрица `способ × склад × поштучная-доступность` собирается целиком в PHP из OMS-payload’ов.

**Вывод:** распухшая general-data — это **OMS-образные данные, фанящиеся-ин и пере-пивотящиеся в PHP**, плюс условные follow-up вызовы.

---

## 4. Перерисовка «по любому чиху» — механизм на фронте (Site)

> Главный канал. Ветка клона — `stage`; новый чекаут за GrowthBook-флагом `NEW_CHECKOUT`.

**Классического NgRx у чекаута НЕТ** (`order.effects.ts` пустой). Состояние — самописный **`GJSignalStore`** (`libs/core/src/lib/services/gj-signal-store.service.ts`), весь general-data в `OrderStateInterface` — **один плоский объект ~50 полей** (`order.store.ts:63-124`), включая ~15 полей `checkoutV2*`. Фасад — `order.facade.ts` (785 строк, ~40 селекторов).

Корень «моргания» — комбинация трёх вещей:

**(A) Coarse-grained refetch.** Есть ровно один «загрузить всё»: `initOrderMutation` / `initOrderFromV2Mutation` (`order.store.ts:906-1055`). Дёргается из **~14 мест**: смена способа доставки, адреса, города/региона, количества, промокода, выбор комплектации — всё сводится к POST `customerDeliveryPreferences` + **полный refetch general-data** (часто 2-3 round-trip подряд).

**(B) `patchState` рвёт все ссылки.** `gj-signal-store.service.ts:250-252` — `const next = {...current}` на каждый patch; `transform` пересобирает `delivery`/`recipients`/`paymentMethods` как НОВЫЕ объекты/массивы. `select()` сравнивает по `Object.is` **без кастомного equality** (`:293-312`) → после refetch каждый селектор отдаёт новую ссылку → каждый `toObservable` эмитит → каждый `| async` перерисовывается.

**(C) Усугубители:**
- корневой `CheckoutPageComponent` — **без OnPush** (default CD, `checkout-page.component.ts:63`)
- `checkout-delivery.component.html` — **119 `| async`** в одном шаблоне
- дедуп только местами и дорогой: `distinctUntilChanged((p,c)=>JSON.stringify(p)===JSON.stringify(c))` на горячем пути (`checkout-page.component.ts:180,276,299`)
- фасадные селекторы вообще без `distinctUntilChanged`

**SSR-дыра:** SSR должен быть выключен для чекаута (`rendering-strategy-resolver-options.ts:8` исключает `'checkout'`), но реальный URL — `cart/confirmation` (`routes.ts:52`), подстроку `checkout` не содержит → страница **SSR-ится по умолчанию**; `ngOnInit` зовёт `init()` без `isPlatformBrowser`-гарда → **двойной фетч general-data** (SSR + гидрация) + риск hydration-mismatch = вклад в стартовое «моргание».

**(D) Подтверждённый каскад (2026-05-30): предвыбранный ПВЗ → delivery/cost → пересчёт корзины → refetch general-data.** При загрузке чекаута, если предвыбрана точка (из customerPreferences), фронт зовёт `GET /api/v3/checkout/delivery/cost?cityId=&regionId=&pickupPointId=dpd-4247` (узнать cost+дату+комплектацию точки) → это **пересчитывает корзину** → фронт **снова дёргает general-data**. Т.е. сам ВХОД в чекаут с сохранённой точкой = каскад (delivery/cost → cart recalc → general-data). Ровно «моргание» + «комплектация привязана к корзине».

**Важно: гранулярные ИС-эндпоинты УЖЕ существуют** — `delivery/cost` (per-point), `delivery/courier`, `delivery/points`, `delivery/stores` отдают фрагмент (один способ/точку). Проблема НЕ в отсутствии гранулярности на backend, а в том, что **фронт после каждого гранулярного вызова перезапрашивает ВСЮ general-data + пересчитывает корзину**. Ответ `delivery/cost` — это **4-я форма комплектации** (`equipments[]`: `dispatchWarehouseId, cost, date, instock, items[]`, + `storage`, `availablePaymentAcquirers`).

> **Следствие для TO-BE:** новый checkout чинит ОБА конца — (1) гранулярный backend-фрагмент по точке/способу (как `delivery/cost`, но единый контракт), (2) фронт обновляет ТОЛЬКО фрагмент + итоги, БЕЗ refetch всей general-data и БЕЗ пере-рендера корзины. Резолвер обязан нормализовать и эту `equipments`-форму (теперь форм OMS/ИС уже ≥4: preliminary / pickup-stores / delivery-intervals / delivery-cost-equipments).

**(E) Каскад выбора комплектации (2026-05-30): `set-equipment` → refetch `basket/current` → re-quote скидок.** Выбор размера/состава пакета в UI = `POST /api/v2/basket/set-equipment` `{products:[{offerId, qty}]}` (qty=1 — в пакет, qty=0 — исключить) → мутирует корзину на сервере → фронт перезапрашивает **всю** корзину `GET /api/v3/basket/current?packageIsSelected=true`, которая **пере-считывает скидки** (состав пакета меняет применимость акций, напр. «1+1=3») и возвращает **полную каталожную матрицу размеров каждого товара**. Два round-trip + полный refetch + поход в сервер скидок на каждый клик = ещё один источник тормозов и «моргания». Детальный разбор — §5.

---

## 5. Комплектация ↔ корзина

**Алгоритм владеет OMS Logistics, НЕ Integration.** Комплектация = блок `inventory` + `logisticGroupId` + `logisticRuleId` в ответах `/logistics/delivery-intervals|pickup-stores|pickup-points`. Каждый «package» в ответе OMS = один вариант комплектации (по складу / логистическому правилу / ТК).

**Почему «привязан к корзине»:** каждый вызов Integration шлёт корзину (`buildDeliveryRequestBody(city, cart)`), OMS **пересчитывает комплектацию от текущих item+qty+city на каждый вызов**, результат **нигде не кэшируется**. Меняешь корзину (или просто повторно зовёшь) → другой split, другие склады, **другие id интервалов**.

**UI-мутация комплектации = `set-equipment` + полный refetch корзины (2026-05-30, с препрода).** Выбор размера/включения позиции в чекауте:
- `POST /api/v2/basket/set-equipment` `{products:[{offerId, qty}]}` — `qty:1` кладёт конкретный SKU (размер) в пакет, `qty:0` исключает (но **НЕ удаляет** из корзины). Т.е. один payload и выбирает размер (через offerId), и определяет вхождение.
- затем `GET /api/v3/basket/current?packageIsSelected=true` — перезапрос **всей** корзины. Три проблемы:

1. **Два round-trip на один клик** (mutate + refetch), refetch — не дельта, а вся корзина целиком.
2. **Ответ несёт ВСЮ size-matrix каждого товара** — каталожные данные инлайн в корзине. Реальный ответ: джинсы `GJN035587` отдают **8 размеров** (6 из них `SOLD_OUT`) ради одного `isCurrent:true`; легинсы — 4 размера. Исключённые позиции (`qty:0`) едут целиком (`isSelected:true`, `priceSum:0`). Cart-эндпоинт смешивает в одном объекте: (a) выбор `qty per offer`, (b) каталожную матрицу всех вариантов, (c) цены, (d) скидки, (e) суммы доставки — «распухшая general-data» уже на уровне самой корзины.
3. **Смена состава пакета → re-quote сервера скидок** (гипотеза Zak, согласуется с механикой): акция зависит от того, ЧТО в пакете (1+1=3 и т.п.), поэтому каждый toggle комплектации тянет сервер скидок (вне контура екома, латентность) → блокирует рендер. Это и есть «пересчёт комплектаций привязан к корзине», развёрнутый в скидки.

**Деньги в ответе — снова рассинхрон форматов** (см. money-doc §квирки): `price:3098` (number ₽), `courierSum:"1500"` (**строка**), `pickupSum:""` (**пустая строка**, не 0/null), `bonusSum:0` (number), `priceSum` = number | `null` (у не-current размеров) | `0` (у `qty:0`). Разнотипица в одном payload — тот же класс багов, что копейки↔рубли.

**Несостыковка счётчиков выбора:** `countSelectedProducts:2`, `countProduct:2`, `price:3098` (=599+2499, два выбранных), но в `products[]` **все 4 товара с `isSelected:true`**. Selected-state размазан между `qty`, `isSelected`, `priceSum`, `countSelectedProducts` — единого поля «что в заказе» нет, фронт собирает истину из нескольких признаков.

### ✅ Подтверждено по коду (2026-05-30, ensi-researcher + integration-researcher)

Хост `customer-gui-web-preprod` = ENSI **`customers-api-web`**. Роуты: `set-equipment` (`ApiV2/.../routes.php:26` → `BasketsController::setBasketEquipment`), `basket/current` (`ApiV3/.../routes.php:14` → `getCurrentBasket`). Оба делегируют в доменные Actions, дальше — в апстрим-сервис `baskets`.

**1. set-equipment мутирует корзину в сервисе `baskets`** (`orders/baskets/.../SetBasketEquipmentAction.php:18-42`): ставит `qty` из тела каждому item (отсутствующим — `qty=0`, **строка НЕ удаляется**), пересчитывает `total_price`, ставит `package_is_selected=true`, и **диспатчит `ChangedBasketByCustomerEvent`**. `init_qty` хранит исходное кол-во комплектации (по нему item делится valid/invalid). **🔴 Метод НИЧЕГО не возвращает** — `customers-api-web BasketsController::setBasketEquipment` → `return new EmptyResource()`, `SetBasketEquipmentAction::execute(): void`, baskets `setEquipment(): EmptyResource`. → фронт **обязан** следом дёрнуть `basket/current`, чтобы узнать результат мутации. Второй round-trip — **не опциональная неэффективность, а вынужденный контрактом** (пустой ответ не даёт фронту пересчитанную корзину).

**2. 🔴 Скидки пересчитываются СИНХРОННО внутри `baskets` — НЕ через Integration.** `ChangedBasketByCustomerEvent` → `BasketDiscountsCalculatedListener` (`EventServiceProvider.php:25-28`, listener НЕ queued = синхронный) → `CalculateBasketDiscountsAction` → `SetBasketDiscountAction` → `GetDiscountAction.php:120` → **`DiscountApiClient::getDiscounts`** (`baskets/.../DiscountsApi/DiscountApiClient.php`) — прямой HTTP POST XML на **сервер скидок** (env **`DISCOUNT_API_URL`**, checksum `md5(baseStoreCode+word+salt)`, retry×3, `baseStoreCode` из `bu` по региону оффера). Ответ мерджит скидки/бонусы на item-ы и пишет в БД `baskets`. **Гипотеза Zak про «1+1=3» подтверждена**: состав пакета → другой XML `<Good>`-набор → другой результат акции. Каждый toggle комплектации = синхронный round-trip к серверу скидок ДО ответа фронту.

**3. basket/current может пересчитать скидки ПОВТОРНО (read-with-side-effect).** `baskets/.../GetCustomerBasketAction.php:30-91`: если `packageIsSelected` пришёл и **отличается** от `basket.package_is_selected` И есть item с `qty != init_qty` → снова `ChangedBasketByCustomerEvent` (→ ещё один вызов сервера скидок). Т.е. пересчёт скидок возможен и на write (set-equipment), и на read (basket/current). Обычно флаг уже выставлен set-equipment'ом → повтор не происходит, но рассинхрон флага = двойной поход за скидками.

**4. Поля ответа — источники:** `price`(=totalPrice/100, уже СО скидкой), `discounts`, `bonusSum`, `promoCode` — pass-through из `VerboseBasket` (`baskets`); `bonusBalance` — отдельный запрос в `customers` (только V3/MOB_V5); `courierSum`/`pickupSum` — считаются в `customers-api-web` из методов доставки (`bu` GetAvailableDelivery), `(string)null=""`; `discountRate` — локальный `CalculateDiscountRateAction` (производная, не от сервера скидок); **size-matrix** (`products[].sizes[]`, все размеры вкл. SOLD_OUT) — catalog-cache `searchProductCards` include `offers` инлайнится в каждый item корзины (`GetCurrentBasketAction.php:149-154`, `BasketProductData.php:67-68`).

**5. 🔴 ДВА клиента к ОДНОМУ серверу скидок (WWWDK_API legacy XML `/api/Query`):**
| Клиент | Сервис | env base_url | Когда зовётся |
|---|---|---|---|
| `DiscountApiClient` | ENSI **`baskets`** | `DISCOUNT_API_URL` | на каждом изменении корзины/комплектации (синхронно, через event) |
| `DiscountClient` | **Integration** | `SALE_SERVICE_CLIENT_BASE_URL` | только на `order/create` (quote `GetDiscount` Type=1 до OMS + spend `BONUS_SPEND_EXT` Type=21 после) |
Контракт XML/checksum дублируется в двух кодовых базах. На commit Integration делает СВОЙ quote заново (не доверяет корзинной скидке) — двойной расчёт скидки в двух местах разными клиентами.

> **Следствие для TO-BE:** (1) `set-equipment` сейчас возвращает `EmptyResource` (пусто) → refetch вынужден; **изменить контракт** — мутация возвращает СЛИМ-дельту (выбор + пересчитанные итоги), тогда второй round-trip исчезает. **Размеры ОСТАЮТСЯ в корзине** — инлайн-смена размера прямо в корзине = ядро UX (нельзя выносить в каталог). Но: список размер-опций каталожно-статичен → кэшировать/не перешивать на каждый recompute; на пересчёте патчить только волатильное (выбор, тоталы, наличие per-size). (2) выбор хранить как явный first-class `Selection` (`offerId→qty`), один источник правды (см. design §2); (3) **re-quote скидок — только когда меняется Good-set, уходящий серверу скидок.** ⚠️ **Поправка (2026-05-30): `<Good>` = SKU вендор-код (размер-специфичный!), НЕ product-карточка и НЕ offerId.** `XmlHelper.php:109 addChild('Good', $product['product_id'])`, `product_id = $item['productId']` (`DiscountService.php:457`), `productId` = `vendorCodeSku` типа `GDR026602F0006` (суффикс `F0006`=размер). **Модель:** product-card/`vendorCodeCC` (`GDR026602`) ⊃ SKU/`vendorCodeSku` (`GDR026602F0006`=размер, идёт в `<Good>`) ⊃ offer/`offerId` (число, =SKU в конкретном магазине+регионе; Selection корзины=`offerId→qty`). **Значит смена размера = другой SKU = другой `<Good>` = re-quote НУЖЕН** (изменится ли результат — решает сервер скидок, клиентски не предсказать; промо может быть размер-/sell-off-/сток-специфичным). Прежнее «смена размера бесплатна» — СНЯТО. Что выживает: (a) кэш/dedupe по ТОЧНОМУ Good-set (возврат к ранее посчитанному составу → cache hit); (b) debounce; (c) НЕ дёргать скидки на не-товарных изменениях (адрес, способ/точка доставки Good-set не трогают); (d) индикативный показ + авторитет на commit. debounce/async, не блокируя рендер. Сейчас arch re-quote'ит ВСЕГДА (slepo фаерит `ChangedBasketByCustomerEvent` на любое изменение). (4) **консолидировать ДВА клиента скидок в один** (наш `clients/discount` уже готов) — единый расчёт, один контракт, единая идемпотентность (DOC=`0000352`+clientOrderId).

**На фронте — двойной счёт.** Комплектация-VM производится из состояния корзины (`checkout-delivery.component.ts:435-459`, `basketFacade.checkoutEquipmentVm$`), а фильтрация «что влезает» — `CheckoutService.getAvailableEquipments` (`checkout.service.ts:14-52`) с честным `//TODO Переписать !!!! O(log*n * n*8)` — гоняется против `basketStore.state()` на каждый refetch general-data. То есть комплектация считается **двумя путями сразу** (локальный basket-VM + backend cartAvailability), которые надо держать синхронными.

**На commit комплектация фактически теряется.** Integration `addPackages()` (`V1 OrderService.php:3181-3203`) игнорирует OMS-split и шлёт в OMS **одну захардкоженную посылку** `GJ<id>` (вес 900/шт по умолчанию, габариты 0.1³). Multi-package комплектация, посчитанная для интервалов, в `/order/create` **не отражается** — несётся только выбранный интервал/склад/fulfillment.

---

## 6. Interval-id drift и 400 на commit

**Корень разобран до конца** (oms-researcher, 2026-05-29). Это **и контракт OMS, и gap Integration одновременно — но корень в OMS-контракте**, и он **дёшево чинится**.

**Как генерится id интервала:** `id` — НЕ случайный, это **детерминированный SHA-256** от 8 полей (`logistics/pkg/utils/cart_utils.go:324-341`): `warehouseId, cityId, deliveryDate, carrierId, tariffId, from, to, deliveryCost`. Для побайтово одинаковых входов id воспроизводим.

**Почему дрейфит:** один из 8 входов хэша — **`deliveryDate`, выводимый из `time.Now()`** через picking-wave / cut-off / ёмкость склада (`delivery_intervals.go:878-915` → `external_warehouse_service.go:401,720-800`). При том же cart+city два вызова в разные моменты дают разный `deliveryDate` → разный хэш → **разный id**. Главный триггер — **пересечение picking-wave / границы дня** между general-data и commit (подтверждает гипотезу «~09:00 cache / wave склада»). Доп. триггеры: добили ёмкость склада, сдвинулся сток (другой `fullestStock`/склад), обновились skip-dates, изменился `deliveryCost` (порог бесплатной доставки).

**OMS УМЕЕТ пинить дату — Integration не пользуется.** Если `ctx[SystemDispatchDate]` непустой, OMS берёт дату оттуда, а не из `now()` (`external_warehouse_service.go:329,393-399`; handler читает `req.SystemSettings.DispatchDate`, `delivery_intervals.go:61,70`). Но Integration `buildDeliveryRequestBody` **не шлёт `dispatchDate`** (`OmsClientV2/Client.php:100-159`) ни в summary, ни на commit-re-fetch (`V4 OrderService.php:560-561`), потом делает голый `in_array` по id (`:592-606`). OMS снова берёт `now()` → match ломается → **400 `SelectedIntervalNotFound`** (`:597`).

**Match-условия Integration (узкие):** курьер — id (`:592-606`); самовывоз — id **И** `date==promissedDeliveryDate` **И** dispatchWarehouse (`:705-733`); PVZ — id **И** dispatchWarehouse **И** date (`:860-877`). Фолбэка/примирения нет.

**Персистентности нет:** `delivery_intervals.go` не читает Redis/БД — каждый вызов чистый пересчёт. «Smart cache» кэширует комбинации складов для метрик, НЕ интервалы с id.

**Комплектация (split):** `logisticGroupId` (геомаршрут по полигонам) и `logisticRuleId` (правило БД) — детерминированы для города. Но **сам split** (какие склады, сколько посылок) НЕ гарантированно стабилен: зависит от живого стока (`selectFullestStock`/`findMinDispatchDate`, `delivery_rule.go:211-213`) и `CalculateDispatchDate` (время/ёмкость). Сдвиг стока/волны → другой склад → ломается узкий match самовывоза/ПВЗ по date+warehouse.

> **Следствие для TO-BE:** drift закрывается тремя способами по возрастанию инвазивности — (a) Integration пинит `systemSettings.dispatchDate` из выбора пользователя на commit-re-fetch (дёшево, закрывает wave-roll, можно даже в legacy); (b) убрать `deliveryDate` из хэша id, матчить по сохранённой дате с серверным фолбэком; (c) персистить выбор (interval+dispatchDate+warehouse) в сессии чекаута. Вариант (a) — кандидат на быстрый interim-фикс боли ещё до новой платформы.

**P0 для самовывоза** — отдельная причина: `OrderCreateRequest.php:131-132` требует `coordinates.latitude/longitude` для ВСЕХ способов, включая самовывоз (рядом закомментированные условия — следы метаний). Плюс `calculateTotals` (`V1:3212-3255`) кидает 400 `InvalidateTotalCost` при float-`!=` расхождении сумм клиента и пересчёта.

---

## 7. Контракт commit «лжёт» про HTTP-статус (P0)

Integration отдаёт **честные коды** (`ExceptionConverter.php:25-49` — реальные 400/500, без маскировки). Маскировка — **в ENSI** `CommitOrderAction.php:109-128`: `OmsClientException` (включая IS 400) **проглатывается** и превращается в нормальный возврат `CreateOrderResponse::error(...)` → `CommitOrderResource` рендерит `{success:false}` → Laravel отдаёт **HTTP 200**.

Это **закреплено тестом** `CommitOrderComponentTest.php:205-269` («200 failed commit order»). Маппинг непоследователен: локальные ошибки BFF (адрес/дата/пустая корзина) → 400; ошибки апстрима (IS/OMS) → 200 success:false. Статус commit означает «прошла ли локальная валидация BFF», а НЕ «создан ли заказ».

- **Mobile защищён:** V2-экран явно проверяет `data.data.success` (`CheckoutScreenV2.tsx:932,1004`) → 200+success:false корректно уводит в `handleCreateOrderError()` (при условии что BFF реально кладёт `success:false`).
- **Site:** трактовку `data.success` vs HTTP-код нужно подтвердить (не закрыто в этом раунде).

---

## 8. Разумное зерно vs костыли (главная развилка)

### ✅ Разумное зерно (сохранить в TO-BE)
| Зерно | Где |
|-------|-----|
| Единый консолидированный расчёт доставки (один `delivery/summary`, не размазанный по 3 эндпоинтам) | Integration V2 DeliveryService; ENSI basket без доп-запросов |
| Чистый стейтлесс-пайплайн commit: `validate→stock→price→discount→ship→create` | Integration V4 OrderService |
| Типизированные DTO-контракты (order/items/shipping/customer/marketing) | оба слоя |
| Enrichment корзины одним батчем по offer_id | ENSI GetCurrentBasketAction |
| Async-пул к OMS (concurrent intervals) | Integration Connector |
| Защита от гонок при быстром переключении способов (`flowId`) | Site order.facade |

### ❌ Костыли / наслоения (распутать)
| Костыль | Где | Эффект |
|---------|-----|--------|
| **general-data = декартова матрица без гранулярности** | ENSI DeliveryResource, Integration summary | перезапрос всего на любой параметр |
| **Нет персистентности выбора** (комплектация/интервал пересчитываются каждый раз, id регенерируются) | Integration (нет Redis/state) + OMS Logistics | interval drift → 400 |
| **`patchState` рвёт все ссылки + select без equality** | Site GJSignalStore | массовый re-render |
| **Один coarse refetch на ~14 триггеров** | Site order/basket facade | «моргание» |
| **Комплектация считается двумя путями** (front basket-VM + backend cartAvailability) | Site checkout.service O(n·m) | рассинхрон, нагрузка |
| **Контракт commit 200/success:false** | ENSI CommitOrderAction | «успех» без заказа |
| **`addPackages` одна захардкоженная посылка** | Integration V1 OrderService:3181 | комплектация теряется при создании |
| **Глубокая инheritance V1→V4 (Order и Delivery)** | Integration | поведение размазано по 4 файлам, ~60 `@throws` |
| **coordinates required для самовывоза** | Integration OrderCreateRequest:131 | P0 pickup 400 |
| **Дубль версий v1/v2 + legacy `checkout-old/`** | Site (15 полей checkoutV2*), Mobile (legacy `api/checkout` + V2) | двойное обслуживание, дрейф |
| **SSR не выключен на `cart/confirmation`** | Site rendering-strategy | двойной фетч + hydration mismatch |
| **Версии API вперемешку** (general-data v5, prefs v1, status v3) | Mobile checkoutV2/index.ts | хрупкость |
| **Field drift** `fiasCity`↔`cityFias` между версиями | Mobile | «undefined» при миксе версий |

---

## 9. Открытые вопросы

1. ~~**OMS Logistics: стабильны ли id интервалов**~~ — **ЗАКРЫТО** (2026-05-29, см. §6). id = детерминированный SHA-256, но включает время-зависимый `deliveryDate` → дрейфит при пересечении wave/дня; OMS умеет пиннинг через `systemSettings.dispatchDate`, Integration его не шлёт; персистентности нет.
2. **Site: как реально трактуется `data.success`** vs HTTP-код на commit (mobile закрыт, site — нет).
3. ~~**Prod-частоты:**~~ — **ЗАКРЫТО** (2026-05-29, см. §11). interval-drift доминирует.
4. **Реальный объём general-data по сети** (КБ, latency на refetch) — нужен прод-замер/логи.
5. **Состояние `NEW_CHECKOUT` в GrowthBook** по окружениям — какая ветка кода живая в проде.
6. ~~**`option.CostForCustomer` (часть хэша id): время/сток-зависим?**~~ — **ЗАКРЫТО** (2026-05-30, по реальной general-data). `deliveryCost` ВХОДИТ в хэш id и **зависит от суммы корзины через порог бесплатной доставки**: та же корзина — сырой OMS `delivery-intervals` дал `id=QOOcGGOK, deliveryCost=299`, а general-data (после применения free-threshold >1500) — `id=vn14dWsQ, deliveryCost=0`. Дата/склад/ТК те же → **id плывёт при пересечении порога бесплатной доставки** (ещё один вектор drift помимо даты/волны). Пин даты этот вектор НЕ закрывает — нужно пиннить/фиксировать и стоимость, либо матчить интервал не по полному хэшу. Учесть в resolver/commit нового checkout.

---

## 10. Что это значит для TO-BE (forward pointer, НЕ дизайн)

Археология указывает на три структурных рычага, которые TO-BE должен закрыть (детали — в отдельном brainstorm дизайна, не здесь):

1. **Гранулярность вместо монолита.** Разбить general-data на «контекст шага» — отдавать выбор/сводку, а не декартову матрицу всех вариантов. Способ доставки запрашивается по требованию.
2. **Персистентная сессия чекаута.** Зафиксировать выбор (интервал/комплектация/склад) на сервере с устойчивым id, примирять drift на сервере (фолбэк), а не валить 400 на клиента.
3. **Один источник правды для комплектации.** Считать в одном месте (OMS/новый домен), не дублировать на фронте; нести комплектацию в `/order/create`, а не схлопывать в одну посылку.

Плюс честный контракт commit (HTTP-код = создан ли заказ) и единая модель состояния на фронте с гранулярными селекторами.

---

## 11. Prod-цифры (2026-05-29, окно 24ч / 1ч, `logs-ensi-prod`)

> Источник: BFF пишет `HTTP IN/OUT REQUEST/RESPONSE`; реальный статус OUT-вызова к Integration — в хвосте `what.message`, тело ошибки — в `what.customParameters.body`. Агрегации в MCP-обёртке таймаутят (агг по proxy), поэтому считал постранично (`_source:false`, `row_count`); тела классифицировал сэмплом. IS-логи (`logs-is-awg-prod`) **пусты по тексту** — весь сигнал в `logs-ensi-prod`.

**Объём чекаута:**
- `v4/order/create` (OUT к Integration): **~190 вызовов/час → ~4,5k/сутки**.
- `checkout/commit` (IN от клиента, web+mob): >500 за ~2ч13м → того же порядка.

**Провалы создания заказа (`order/create` OUT):**
| Статус | За 24ч | ~% от создания |
|--------|--------|----------------|
| `400` | **77** | ~1.7% |
| `500` | **15** | ~0.3% |
| **итого fail** | **~92/сутки** | **~2%** |

**Раскладка причин `400` (сэмпл последних 12 тел):**
| errorCode | Сообщение | Доля в сэмпле |
|-----------|-----------|---------------|
| **1002** | «Выбранный интервал доставки **курьером** не найден» | 8/12 |
| **1002** | «Выбранный интервал доставки **в магазин** недоступен» | 2/12 |
| **1022** | «Ожидаемая сумма заказа… отличается от полученной» (`InvalidateTotalCost`) | 2/12 |

→ **~83% всех create-400 = interval drift** (`errorCode 1002`, §6), ~17% = рассинхрон суммы (`InvalidateTotalCost`, float-`!=`, §7). Координатных/pickup-validation 400 в сэмпле **нет** — P0 «координаты для самовывоза» сейчас не доминирует; **главная реальная боль — interval drift**.

**P0-маскировка (подтверждена косвенно):** `commit` IN-ответы (сэмпл 500 за ~2ч): 487×`200`, 8×`400`, 3×`500`, 2×`422`. Локальных commit-400 мало (~1.6%, валидация адреса/даты на BFF), а ~77/сутки OMS-провалов **не видны в статусе commit** — они уходят клиенту как `200 {success:false}` (web-риск «успех без заказа»; mobile парирует проверкой `data.success`).

**Не измерено:** почасовое распределение interval-drift (date_histogram недоступен через proxy — агг таймаутит); по сэмплу видна минутная кластеризация courier-1002, что согласуется с wave-механизмом, но точную привязку к ~09:00/границе суток подтвердить через Kibana DSL напрямую.

**Грубый вывод для приоритизации:** ~**77 заказов/сутки** срываются на interval-drift и (на web) маскируются под успех. Это и есть «#1 боль в цифрах». Interim-фикс пиннинга `dispatchDate` (§6 вариант «a») целит ровно сюда.

---

## Приложение: ключевые файлы

**ENSI** `platform/ensi/apps/customers-api-web/app/`
- `Domain/Orders/Actions/{GetCheckoutGeneralDataV2Action,GetCheckoutAbstractAction,CommitOrderAction}.php`
- `Domain/Orders/Client/OmsClient.php`, `Domain/Orders/Exceptions/OmsClientException.php`
- `Http/ApiV2/Modules/Orders/Resources/CheckoutGeneralData/*`, `.../CommitOrderResource.php`
- `Http/ApiV3/Modules/Orders/Tests/CommitOrderComponentTest.php`

**Integration** `platform/integration/integration/www/app/Service/UserApi/`
- `Services/V2/Delivery/DeliveryService.php`, `Services/V4/Order/OrderService.php`, `Services/V1/Order/OrderService.php` (addPackages/calculateTotals/processPositionItems)
- `Http/Controllers/V4/Order/OrderActionController.php`, `Http/Requests/V4/Order/System/OrderCreateRequest.php`
- `routes/api.php`, `Connector/Connector/Connector.php`

**Site** `platform/site/gj-ng-front/libs/`
- `data-access/src/lib/signals/order/order.store.ts`, `.../store/checkout/order/order.facade.ts`, `.../store/basket/basket.facade.ts`
- `core/src/lib/services/gj-signal-store.service.ts`, `data-access/src/lib/store/checkout/service/checkout.service.ts`
- `modules/checkout/src/lib/{checkout-page,checkout-delivery}/*`, `server/src/app/config/rendering-strategy-resolver-options.ts`, `routing/src/lib/routes.ts`

**Mobile** `platform/mobile-app/gj-app/packages/gj/src/`
- `api/checkoutV2/index.ts` (+ legacy `api/checkout/index.ts`)
- `screens/Checkout/CheckoutScreen/{CheckoutScreenV2.tsx,checkout-screen-model-v2.ts}`, `constants/api.ts`
