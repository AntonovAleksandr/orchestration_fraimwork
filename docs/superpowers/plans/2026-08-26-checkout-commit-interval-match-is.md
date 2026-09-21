# Checkout commit interval match — Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** В Integration V4 `order/create` искать выбранный курьерский слот / ПВЗ / магазин тем же правилом, что BFF, чтобы не резать заказ `SelectedIntervalNotFound`, если выбор клиента ещё есть в пересчёте.

**Architecture:** Вынести матч в `SelectedDeliveryMatcher` (чистый PHP, без Connector). `OrderService` V4 вызывает матчер вместо id-only / date-equality. `calculateDaysLimit: 1` не меняем.

**Tech Stack:** PHP 7.4, Lumen, PHPUnit 9. **Запрещено:** `match()`, named arguments, union types, constructor property promotion, nullsafe `?->`. Тесты — `PHPUnit\Framework\TestCase`, без бутстрапа Lumen (как `ExpressDeliveryTypeMapsTest`).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-26-checkout-commit-interval-match-design.md`.
- Код: `platform/integration/integration/www/`.
- Курьер: только тот же календарный день + склад; подставляем актуальный `id`.
- ПВЗ/магазин: тот же пункт/магазин (+ тип); дата и склад из свежего пакета.
- Не подставлять чужой пункт/магазин/день курьера.
- После матча записать в `$order['shipping']` найденные `deliveryOptionId`, `dispatchWarehouseId`, `promissedDeliveryDate` (дальше существующий fill-код читает `$selectedInterval`).

## File Map

- Create: `app/Service/UserApi/Services/V4/Order/SelectedDeliveryMatcher.php`
- Create: `tests/Unit/Service/UserApi/Services/V4/Order/SelectedDeliveryMatcherTest.php`
- Modify: `app/Service/UserApi/Services/V4/Order/OrderService.php` — `fillSelectedCourierDeliveryIntervalV4`, `fillSelectedPickupPointDeliveryInterval`, `fillSelectedPickupStoreDeliveryInterval`

---

### Task 1: Матчер + PHPUnit

**Files:**
- Create: `app/Service/UserApi/Services/V4/Order/SelectedDeliveryMatcher.php`
- Create: `tests/Unit/Service/UserApi/Services/V4/Order/SelectedDeliveryMatcherTest.php`

**Interfaces:**
- Consumes: сырые массивы OMS (как после `Connector::parse`) и `$order['shipping']`.
- Produces:
  - `findCourier(array $intervals, array $shipping): ?array` — элемент интервала или null.
  - `findPickupPoint(array $packages, array $shipping): ?array` — `['interval' => ..., 'package' => ...]` или null.
  - `findPickupStore(array $packages, array $shipping): ?array` — та же форма.

`$shipping` ключи: `deliveryOptionId`, `promissedDeliveryDate`, `dispatchWarehouseId`, `deliveryTypeId`.

Дату сравнивать через `substr((string)$date, 0, 10)` (и `Y-m-d`, и datetime).

- [ ] **Step 1: Падающие тесты (класс матчера ещё пустой / методов нет)**

`SelectedDeliveryMatcherTest extends PHPUnit\Framework\TestCase`.

Курьер:

- id совпал → этот элемент.
- id другой, date `2026-08-27T09:00:00` vs shipping `2026-08-27`, склад тот же → найден, id новый.
- id другой, день другой → null.

ПВЗ:

- пункт в пакете запрошенного склада → этот пакет (даже если дата shipping другая).
- пункт только в другом складе → fallback, новый склад.
- пункта нет → null.

Магазин:

- `pickupinstore`: id+тип в WH-B при запросе WH-B → B; при запросе WH-MISSING и наличии только WH-A → A.
- другой `id` магазина → null.
- `reserveinstore`: матч по id+типу, склад пакета обычно равен id магазина.

- [ ] **Step 2: Запустить — FAIL**

```bash
cd platform/integration/integration/www
./vendor/bin/phpunit tests/Unit/Service/UserApi/Services/V4/Order/SelectedDeliveryMatcherTest.php
```

Expected: class/method not found или assert fail.

- [ ] **Step 3: Реализация матчера (PHP 7.4)**

Курьер: цикл по id, затем цикл date+warehouse.

ПВЗ: два прохода по `$packages` — сначала `inventory.dispatchWarehouse === dispatchWarehouseId` и пункт в `pickupPoints.list`, затем любой пакет с этим пунктом. Не сравнивать даты.

Магазин: в `pickupStores.list` искать `id === deliveryOptionId` и `deliveryTypeId === shipping.deliveryTypeId` (если тип задан). Предпочесть пакет с запрошенным складом, если `$shipping['deliveryTypeId'] === DeliveryTypeIdEnum::PICKUP_IN_STORE` и склад передан; иначе первый hit.

Использовать `DeliveryTypeIdEnum` constants.

- [ ] **Step 4: PASS** той же phpunit-командой.

- [ ] **Step 5: Commit в `integration` (если просили)** — `fix(checkout): add delivery selection matcher for commit rematch`

---

### Task 2: Включить матчер в V4 OrderService

**Files:**
- Modify: `app/Service/UserApi/Services/V4/Order/OrderService.php`

**Interfaces:**
- Consumes: `SelectedDeliveryMatcher`
- Produces: те же fill-методы, другой способ выбора `$selectedInterval` / `$selectedPackage`.

- [ ] **Step 1: Курьер `fillSelectedCourierDeliveryIntervalV4`**

После проверки, что `$intervals` не пустой, заменить блок `array_column` / `in_array` на:

```php
$matcher = new SelectedDeliveryMatcher();
$selectedInterval = $matcher->findCourier($intervals, $order['shipping']);
if ($selectedInterval === null) {
    throw new DeliveryBusinessException\SelectedIntervalNotFound(/* тот же payload */, 'Выбранный интервал доставки курьером не найден');
}
$order['shipping']['deliveryOptionId'] = $selectedInterval['id'];
```

Дальше существующее заполнение `deliveryCost`, `dispatchWarehouseId` из `$selectedInterval` не трогать.

`trace('закончен поиск выбранного интервала', ...)` дополнить `'match_path'` не обязательно, если нет дешёвого сигнала из матчера; можно не усложнять.

`calculateDaysLimit => 1` оставить.

- [ ] **Step 2: ПВЗ `fillSelectedPickupPointDeliveryInterval`**

Вместо вложенного foreach с `id && warehouse && date == promissedDeliveryDate`:

```php
$found = (new SelectedDeliveryMatcher())->findPickupPoint($allIntervals, $order['shipping']);
if ($found === null) {
    throw new DeliveryBusinessException\SelectedIntervalNotFound(/* ... */, 'Выбранный интервал доставки в пвз недоступен');
}
$selectedInterval = $found['interval'];
$selectedPackage = [
    'inventory' => $found['package']['inventory'],
    'logisticGroupId' => $found['package']['logisticGroupId'] ?? null,
    'logisticRuleId' => $found['package']['logisticRuleId'] ?? null,
];
```

Ключи `logisticGroupId` в сыром JSON — как в текущем коде (`logisticGroupId` vs `logisticGroupID`): скопировать **ровно** те, что уже пишет сегодняшний fill.

- [ ] **Step 3: Магазин `fillSelectedPickupStoreDeliveryInterval`**

Аналогично `findPickupStore`. Убрать требование `$interval['date'] == $order['shipping']['promissedDeliveryDate']`. Складный фильтр — внутри матчера, не дублировать.

- [ ] **Step 4: Статический прогон**

```bash
cd platform/integration/integration/www
./vendor/bin/phpunit tests/Unit/Service/UserApi/Services/V4/Order/SelectedDeliveryMatcherTest.php
php -l app/Service/UserApi/Services/V4/Order/OrderService.php
php -l app/Service/UserApi/Services/V4/Order/SelectedDeliveryMatcher.php
```

Expected: tests PASS, php -l No syntax errors. PHP 7.4: в изменённых файлах нет `match` / `?->` / `fn (`.

- [ ] **Step 5: Commit (если просили)** — `fix(checkout): rematch selected delivery on v4 order create`

---

### Task 3: V3 не в этом MR

V3 `OrderService` содержит тот же id-only / date-equality. Прод сайт и mob v5 идут в **V4**. Не копировать матчер в V3 в этом плане. Если grep логов покажет create v3 на курьере — follow-up.

---

### Task 4: Регрессия phpunit matcher

```bash
cd platform/integration/integration/www
./vendor/bin/phpunit tests/Unit/Service/UserApi/Services/V4/Order/SelectedDeliveryMatcherTest.php
```

Expected: PASS.
