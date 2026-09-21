# Checkout commit interval match — BFF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** В `customers-api-web` на commit находить выбранный курьерский слот / ПВЗ / магазин по правилам spec, отдавать в IS актуальные id/склад/дату и разные тексты 400.

**Architecture:** Матч остаётся в трёх `*CommonDeliveryDataAction`. `CommonDeliveryData` несёт `intervalId` и `dispatchWarehouse` из найденного объекта. `ShippingOptions` для курьера берёт id из матча; для ПВЗ/магазина — стабильный client id, но склад из матча. `calculateDaysLimit` не трогаем.

**Tech Stack:** PHP 8.1, Laravel/Pest в `platform/ensi/apps/customers-api-web`. Тесты: `elc -w gj -c customers-api-web exec php artisan test --filter=…`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-26-checkout-commit-interval-match-design.md`.
- Не менять `filterSettings.calculateDaysLimit` (везде `1`).
- Не подставлять другой ПВЗ, другой магазин, другой курьерский календарный день.
- ПВЗ/магазин: тот же пункт → оформляем с новой датой и новым складом отгрузки.
- Курьер: день + склад те же, в IS уходит найденный `id`.
- Репозиторий: `platform/ensi/apps/customers-api-web`. Перед работой: `git status` — дерево может быть грязным; не мешать чужие изменения.
- Команды тестов — внутри elc, не host `php`.

## File Map

- Modify: `app/Domain/Orders/Actions/CourierCommonDeliveryDataAction.php`
- Modify: `app/Domain/Orders/Actions/PickupCommonDeliveryDataAction.php`
- Modify: `app/Domain/Orders/Actions/StoreCommonDeliveryDataAction.php`
- Modify: `app/Domain/Orders/Data/Order/CommonDeliveryData.php`
- Modify: `app/Domain/Orders/Data/Order/ShippingOptions.php`
- Modify: `app/Domain/Orders/Actions/CommitOrderAction.php`
- Create: `app/Domain/Orders/Actions/Tests/CourierCommonDeliveryDataActionUnitTest.php`
- Modify: `app/Domain/Orders/Actions/Tests/PickupCommonDeliveryDataActionUnitTest.php`
- Modify: `app/Domain/Orders/Actions/Tests/StoreCommonDeliveryDataActionUnitTest.php`

---

### Task 1: Курьер — дата как Y-m-d и актуальный interval id

**Files:**
- Create: `app/Domain/Orders/Actions/Tests/CourierCommonDeliveryDataActionUnitTest.php`
- Modify: `app/Domain/Orders/Actions/CourierCommonDeliveryDataAction.php`
- Modify: `app/Domain/Orders/Data/Order/CommonDeliveryData.php`
- Modify: `app/Domain/Orders/Data/Order/ShippingOptions.php`

**Interfaces:**
- Consumes: `CourierCommonDeliveryDataAction::execute(Customer, CurrentBasketData, deliveryCourierId, dispatchWarehouseId, deliveryDate, Address): ?CommonDeliveryData`
- Produces: `CommonDeliveryData.intervalId`, `CommonDeliveryData.dispatchWarehouse`; `ShippingOptions.fromRequestAndCommonDeliveryData` для `delivery` кладёт `intervalId` в `deliveryOptionId`.

- [ ] **Step 1: Написать падающие тесты курьера**

Файл `app/Domain/Orders/Actions/Tests/CourierCommonDeliveryDataActionUnitTest.php` (Pest, `uses(UnitTestCase::class)`, group `unit`, `courierCommonDeliveryData`).

Нужны фабрики: `DeliveryIntervalFactory`, `CurrentBasketFactory` / product factories как в `StoreCommonDeliveryDataActionUnitTest`, `AddressFactory` из `App\Domain\Orders\Tests\Factories\Address`, `CustomerFactory`. API version `ApiVersionEnum::V3` → мок `getDeliveryIntervalsV2`.

Кейсы:

1. `id` совпал — возвращается этот интервал, `intervalId` равен запрошенному.
2. `id` другой, но `date->toDateString()` и `dispatchWarehouse` совпадают (у интервала `date` с временем, в запросе строка `Y-m-d`) — берём этот интервал, `intervalId` = новый id.
3. Список непустой, ни id ни дата+склад — `null`.
4. `ShippingOptions::fromRequestAndCommonDeliveryData` с `deliveryType=delivery`, клиентский `deliveryCourierId=old`, `commonDeliveryData.intervalId=new` → `deliveryOptionId === 'new'`; `dispatchWarehouse` из common data.

Для (4) не обязателен полный action: достаточно собрать `CommonDeliveryData` вручную и вызвать `ShippingOptions`. Можно отдельным `test()` в том же файле.

Ожидание после Step 2: FAIL — нет `intervalId`, Carbon-where не матчит дату со временем vs `Y-m-d`.

- [ ] **Step 2: Запустить тесты — должны упасть**

```bash
elc -w gj -c customers-api-web exec php artisan test --filter=CourierCommonDeliveryData
```

Expected: FAIL (файл тестов есть, поведение старое).

- [ ] **Step 3: Реализация**

В `CourierCommonDeliveryDataAction::findByDateAndWarehouse` заменить Carbon `where` на:

```php
return $intervals->first(
    fn (DeliveryInterval $interval) =>
        $interval->date?->toDateString() === $deliveryDate
        && $interval->dispatchWarehouse === $dispatchWarehouseId,
);
```

Убрать неиспользуемый `use Illuminate\Support\Facades\Date`.

На miss после непустого списка — `Log::warning('checkout.delivery.rematch', ['type' => 'courier', 'path' => 'miss', ...])`. На date+warehouse hit — `Log::info` с `path` => `date_warehouse`.

`CommonDeliveryData::fromDeliveryInterval`:

```php
$data->intervalId = $interval->id;
$data->dispatchWarehouse = $interval->dispatchWarehouse;
```

Дописать phpdoc `@property`.

`ShippingOptions::fromRequestAndCommonDeliveryData`:

```php
$data->dispatchWarehouseId = $commonDeliveryData->dispatchWarehouse
    ?? $deliveryData['dispatchWarehouseId']
    ?? null;
$data->deliveryOptionId = $commonDeliveryData->intervalId
    ?? $data->matchDeliveryOption($deliveryData);
```

`intervalId` заполняется только из курьерского интервала, ПВЗ/магазин идут в `matchDeliveryOption`.

- [ ] **Step 4: Тесты зелёные**

```bash
elc -w gj -c customers-api-web exec php artisan test --filter=CourierCommonDeliveryData
```

Expected: PASS.

- [ ] **Step 5: Commit в репозитории customers-api-web**

```bash
cd platform/ensi/apps/customers-api-web
git add app/Domain/Orders/Actions/CourierCommonDeliveryDataAction.php \
  app/Domain/Orders/Data/Order/CommonDeliveryData.php \
  app/Domain/Orders/Data/Order/ShippingOptions.php \
  app/Domain/Orders/Actions/Tests/CourierCommonDeliveryDataActionUnitTest.php
git commit -m "$(cat <<'EOF'
fix(checkout): rematch courier interval by date+warehouse

Stale SHA interval ids no longer block commit when the same day and
warehouse are still in the one-day OMS window.
EOF
)"
```

Только если пользователь явно просил коммитить в этом репо. Иначе оставить unstaged и идти дальше.

---

### Task 2: ПВЗ — тот же пункт, склад/дата могут смениться

**Files:**
- Modify: `app/Domain/Orders/Actions/Tests/PickupCommonDeliveryDataActionUnitTest.php`
- Modify: `app/Domain/Orders/Actions/PickupCommonDeliveryDataAction.php`
- Modify: `app/Domain/Orders/Data/Order/CommonDeliveryData.php` (`fromDeliveryPickup`)

**Interfaces:**
- Consumes: `PickupCommonDeliveryDataAction::execute(basket, deliveryPickupId, dispatchWarehouseId, cityId)`
- Produces: `CommonDeliveryData` с датой пункта и `dispatchWarehouse` из пакета, где пункт нашёлся.

- [ ] **Step 1: Падающие тесты**

В существующий Pest-файл (group `pickupCommonDeliveryData`), helper корзины как в store-тесте.

Кейс A: два пакета, пункт `P1` в обоих. Запрошен склад `WH-B` → дата и `dispatchWarehouse` из пакета B.

Кейс B: пункт `P1` только в `WH-A`, запрошен `WH-MISSING` → **не null**, дата/склад из `WH-A` (это инверсия старого курьерского склада: продуктово нельзя блокировать).

Кейс C: пункта нет ни в одном пакете → `null`.

Сбор ответа — `CalculatePickupPointsDeliveryResponse` с `data` как у store-теста: `inventory.dispatchWarehouse`, `pickupPoints.list[].id/date/deliveryCost`. Смотреть `DeliveryPickupFactory` / соседние factory, если массив не парсится.

- [ ] **Step 2: Запустить — B должен упасть на текущем коде**

```bash
elc -w gj -c customers-api-web exec php artisan test --filter=pickupCommonDeliveryData
```

Expected: кейс B FAIL (`null` вместо данных).

- [ ] **Step 3: Реализация**

`calcPickupPointsDelivery`: сначала пакеты с запрошенным складом, `fromDeliveryPickup`; если пусто — все пакеты. На втором пути `Log::info(..., 'path' => 'warehouse_fallback')`.

`fromDeliveryPickup`:

```php
$data->dispatchWarehouse = $pickup->inventory->dispatchWarehouse ?? null;
```

Не ставить `intervalId` (иначе ShippingOptions перезапишет pickup id курьерским полем).

- [ ] **Step 4: Тесты зелёные**

Та же команда. Expected: PASS, включая старый тест про qty=0.

- [ ] **Step 5: Commit (если просили)** — `fix(checkout): keep same pickup point when dispatch warehouse drifts`

---

### Task 3: Магазин — тот же id+тип, склад/дата могут смениться

**Files:**
- Modify: `app/Domain/Orders/Actions/Tests/StoreCommonDeliveryDataActionUnitTest.php`
- Modify: `app/Domain/Orders/Actions/StoreCommonDeliveryDataAction.php`

**Interfaces:**
- Consumes: `StoreCommonDeliveryDataAction::execute(..., deliveryStoreId, cityId, deliveryType, ?dispatchWarehouseId)`
- Produces: `CommonDeliveryData.dispatchWarehouse` из пакета-победителя; дата из магазина.

- [ ] **Step 1: Переписать тест «returns null when no package matches warehouse»**

Тест `store delivery returns null when no package matches the committed dispatch warehouse` **заменить**: при `S1` в `WH-A` и запросе `WH-MISSING` ожидать дату `2026-06-25` и склад `WH-A`, не `null`.

Добавить кейс: `S1` есть в A и B, запрос `WH-B` → по-прежнему дата B (предпочтение склада). Существующий тест `resolves the package whose dispatch warehouse matches` оставить.

- [ ] **Step 2: Запустить — переписанный тест падает**

```bash
elc -w gj -c customers-api-web exec php artisan test --filter=storeCommonDeliveryData
```

- [ ] **Step 3: Реализация `calcDeliveryStores`**

Алгоритм: среди пакетов найти магазины с `id === deliveryStoreId` и `deliveryTypeId === deliveryType`. Если есть пакет с `dispatchWarehouse === $dispatchWarehouseId` (для pickupinstore, когда склад передан) — взять его. Иначе первый подходящий пакет. Проставить:

```php
$data->dispatchWarehouse = $package->inventory->dispatchWarehouse ?? $dispatchWarehouseId;
$data->promissedDeliveryDate = $store->date;
```

`reserveinstore`: не требовать клиентский склад; как сейчас можно не фильтровать, но fallback «тот же магазин в другом пакете» должен работать.

- [ ] **Step 4: PASS** той же командой. Не сломать тест pickup vs reserve независимо.

- [ ] **Step 5: Commit (если просили)** — `fix(checkout): keep same store when dispatch warehouse drifts`

---

### Task 4: Тексты 400 по типу доставки

**Files:**
- Modify: `app/Domain/Orders/Actions/CommitOrderAction.php`

**Interfaces:**
- Consumes: `$requestData->getDelivery()['deliveryType']`
- Produces: разные `WrongParametersException` message.

- [ ] **Step 1: Сменить throw**

Вместо одной фразы:

```php
if (!$commonDeliveryData?->promissedDeliveryDate) {
    $deliveryType = $requestData->getDelivery()['deliveryType'] ?? '';
    $message = match ($deliveryType) {
        DeliveryType::DELIVERY->value,
        DeliveryType::COURIER->value,
        DeliveryType::EXPRESS->value => 'Выбранный интервал доставки больше недоступен.',
        DeliveryType::PICKUP->value => 'Выбранный пункт выдачи больше недоступен.',
        DeliveryType::RESERVE_IN_STORE->value,
        DeliveryType::PICKUP_IN_STORE->value => 'Выбранный магазин больше недоступен.',
        default => 'Не удалось рассчитать дату доставки/самовывоза.',
    };
    throw new WrongParametersException($message);
}
```

`DeliveryType` уже импортирован в файле.

Компонентные тесты commit, если проверяют точный старый текст — обновить. Grep по репо: `Не удалось рассчитать дату доставки`.

- [ ] **Step 2:**

```bash
elc -w gj -c customers-api-web exec php artisan test --filter=CommitOrder
rg -n "Не удалось рассчитать дату доставки" app
```

Починить упавшие assert на старый message.

- [ ] **Step 3: Commit (если просили)** — `fix(checkout): split commit 400 copy by delivery type`

---

### Task 5: Регрессия трёх unit-групп

- [ ] **Step 1:**

```bash
elc -w gj -c customers-api-web exec php artisan test --group=courierCommonDeliveryData,pickupCommonDeliveryData,storeCommonDeliveryData
```

Если Pest group filter не принимает список — три команды подряд. Expected: все PASS.

- [ ] **Step 2:** Убедиться, что `SearchDeliveryIntervalsRequest` V2 по-прежнему `'calculateDaysLimit' => 1` в `fromAddressAndBasket` и `createSearchDeliveryIntervalsRequest`.
