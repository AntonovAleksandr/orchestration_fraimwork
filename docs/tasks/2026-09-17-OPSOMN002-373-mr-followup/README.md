# OPSOMN002-373: корректировка MR — фиксируем цену выбранного Express-интервала

Нужно доработать существующие MR по приведённым ниже diff и обновить тесты. Патчи подготовлены для обсуждения и не применены к исходникам сервисов. Они содержат production-код; изменение тестов и фикстур — отдельный обязательный шаг в этом поручении.

## 1. Контекст и согласованное поведение

При повторном расчёте Яндекс Express меняет стоимость, из-за этого меняется OMS ID интервала. Нужно найти тот же слот и сохранить цену предложения, выбранного клиентом.

Команда OMS подтвердила: `shipping.deliveryCost` OMS не перезаписывает; стоимость перевозчика может обновляться в `actualDeliveryCost`. OMS менять не требуется.

**Согласованное правило:** клиентская цена доставки привязана к выбранному предложению, адресу, складу, перевозчику, тарифу и временному слоту. Товары, количества и сумма корзины не входят в контекст токена. Это сознательное бизнес-решение: изменение комплектации само по себе не отменяет обещанную цену, включая случаи уменьшения или увеличения стоимости свежего расчёта.

Пример: клиент получил предложение 500 ₽, затем выбрал частичную комплектацию. Если оформление приходит с тем же действующим токеном, при свежем расчёте 300 ₽ или 700 ₽ клиентская доставка остаётся 500 ₽. Если фронт показал новое предложение 300 ₽ и вернул его новый токен, сохраняем 300 ₽.

Токены выдаются вместе с вариантами доставки, а на оформлении проверяется только токен выбранного варианта. Сохранение интервалов на сервере не требуется.

Область действия — только тройка:

```text
deliveryTypeId = expressdelivery
carrierId = yandex
tariffId = yataxi_two_hours_delivery
```

Изменения только в Integration и customers-api-web. Не добавлять Redis/БД, endpoints или поля API. Фронты и OMS не менять.

## 2. Почему меняем текущую реализацию

### Привязка корзины в токене слишком строгая

В исходном ТЗ и MR цена дополнительно привязана к составу, количествам и сумме товаров. В мобильном есть штатная ветка: ввод адреса → единственная Express-комплектация → `setEquipment`. Она может уменьшить количество с 5 до 2, оставив прежний ID интервала. Текущая подпись затем даёт `context_mismatch`, хотя адрес и слот остались прежними.

Убираем корзину из контекста подписи. Штатное оформление продолжает проверять остатки на складе, доступность товаров, актуальные цены, скидки и совпадение суммы товаров. Сообщение «Состав заказа обновился» и проверки корзины не отключаем. Эти проверки не являются универсальным сравнением старого и нового состава: например, перестановка товаров при одинаковой сумме может пройти. Новое правило цены это допускает.

### Глобальную замену `initQty → qty` отменяем

Она больше не нужна для совпадения контекста токена и затрагивает общий поиск доставки. `initQty` — количество покупателя, ограниченное региональными остатками; `qty` — выбранная комплектация. После выбора частичной комплектации у исключённого товара может быть `qty=0`, хотя товар не распродан.

При смене адреса внутри Express старые выбранные количества могут сохраниться. Если искать только по `qty`, новый запрос не содержит ранее исключённые товары и не может найти для них доставку с другого магазина. Поэтому оба общих форматтера возвращаем к поведению до второго коммита MR822.

Замеченное расхождение «количества по initQty, сумма по qty» сохраняется как отдельная задача. В рамках фиксации цены не исправлять его глобальной заменой полей. `formatEquipmentProducts` и построение фактически оформляемых позиций не менять.

### Закрываем unsigned → signed подмену

Старый открытый checkout может содержать обычный ID и показанную цену 550 ₽. После включения выдачи токенов свежий запрос отдаст тот же слот за 560 ₽ уже с токеном. Сейчас legacy-подбор BFF может выбрать единственный подходящий интервал и передать в ИС его свежую цену и токен. Подпись корректна, но клиент это предложение не выбирал.

В legacy-ветке BFF, после поиска и до создания `CommonDeliveryData`, нужно отклонить найденный подписанный интервал существующей ошибкой обновления checkout. Исходный подписанный токен клиента при штатном оформлении сохраняем до ИС и не заменяем свежим.

## 3. Базы патчей и файлы

Это изменения поверх следующих проверенных ревизий MR, а не diff относительно target branch:

| Сервис | MR | База для приложенного патча |
|---|---|---|
| Integration | [!911](https://gitlab.gloria.aaanet.ru/avg-integration-service/integration/-/merge_requests/911) | `79426492c0c35178542e8dd0a24fbaa38fbfae1f` |
| customers-api-web | [!822](https://gitlab.gloria.aaanet.ru/greensight/gj/customer-gui/customers-api-web/-/merge_requests/822) | `faeac0bd72c5517da20289a472a828e1353c12d5` |

Если MR продвинулись, перенести изменения на актуальную ветку с учётом новых правок; не откатывать весь репозиторий к этим SHA.

### Integration — `platform/integration/integration`

1. `www/app/Service/UserApi/Support/ExpressQuote/ExpressQuoteSpec.php` — оставить в `buildContext` только адрес; удалить агрегацию позиций и суммы.
2. `www/app/Service/UserApi/Support/ExpressQuote/ExpressQuoteContext.php` — обновить переходники courier, summary и create; удалить неиспользуемый сбор позиций.
3. `www/app/Service/UserApi/Services/V4/Order/OrderService.php` — обновить вызов контекста и комментарий. Остальные проверки заказа оставить.

### BFF — `platform/ensi/apps/customers-api-web`

1. `app/Domain/Orders/Support/ExpressQuote/ExpressQuoteSpec.php` — тот же адресный контекст, байт-в-байт совместимый с ИС.
2. `app/Domain/Orders/Support/ExpressQuote/ExpressQuoteContext.php` — прекратить передавать товары и сумму в контекст.
3. `app/Domain/Orders/Data/Logistics/Product.php` — вернуть прежнее использование `initQty`, удалить добавленное пропускание `qty<=0`.
4. `app/Domain/Orders/Data/Logistics/V2/Product.php` — то же для компактной формы и разворачивания по одной штуке.
5. `app/Domain/Orders/Actions/CourierCommonDeliveryDataAction.php` — отказ при unsigned → signed в legacy-ветке, актуализировать комментарий проверки контекста.

## 4. Порядок выполнения

1. Прочитать локальные инструкции сервисов, проверить состояние веток и актуальные diff MR. Сохранить чужие изменения.
2. Добавить или скорректировать тесты на новое правило цены и unsigned → signed сценарий. До исправления соответствующие новые проверки должны падать по ожидаемой причине.
3. В обоих сервисах одновременно изменить контракт контекста: только нормализованный адрес. Слотовые поля, цена, срок и HMAC остаются в подписанном payload. Не заменять удаляемый контекст корзины пустой константой: адрес должен продолжать проверяться.
4. Обновить все production-вызовы `buildContext` и `fromOrderCreate`, удалить неиспользуемый сбор позиций. Приведённые diff покрывают вызовы на указанных базах; на свежих ветках проверить новые использования.
5. В BFF отменить только глобальные изменения двух форматтеров из второго коммита MR822. Добавить отказ unsigned → signed.
6. Синхронно обновить общие JSON-векторы и тесты, перечисленные ниже. Не сохранять старые ожидания, что смена количества или суммы ломает токен.
7. Запустить изменённые тесты и существующие проверки оформления web V3 / mobile V5, форматтеров и остальных способов доставки. Проверить итоговый diff: никаких изменений фронтов, OMS и общей логики расчёта товаров.
8. Вернуть результаты тестов, невыполненные проверки и актуальные SHA обоих MR. Выкладка — отдельный согласованный шаг.

## 5. Полный production-diff Integration

Отдельный файл: [integration.patch](integration.patch).

```diff
diff --git a/www/app/Service/UserApi/Support/ExpressQuote/ExpressQuoteSpec.php b/www/app/Service/UserApi/Support/ExpressQuote/ExpressQuoteSpec.php
--- a/www/app/Service/UserApi/Support/ExpressQuote/ExpressQuoteSpec.php
+++ b/www/app/Service/UserApi/Support/ExpressQuote/ExpressQuoteSpec.php
@@ -143,20 +143,13 @@
     // ---------------------------------------------------------------- контекст
 
     /**
-     * Канонический контекст расчёта доставки.
-     *
-     * Вход намеренно приведён к «корзине, участвующей в расчёте доставки»: это ровно то,
-     * что каждый из участников и так отправляет в OMS (см. compactCart в OmsClientV2).
-     *
-     * @param array{city?: array{fiasId?: string|null, name?: string|null},
-     *              street?: array{fiasId?: string|null, name?: string|null},
-     *              building?: array{fiasId?: string|null, name?: string|null}} $address
-     * @param array<int, array{id?: string|null, quantity?: int|float|string|null}> $items
-     * @param int|float|string|null $totalPrice рубли
-     *
+     * Контекст обещанной цены доставки: только адрес назначения.
+     * Слот подписан отдельно; товары и суммы проверяются штатным оформлением заказа.
+     *
+     * @param array<string, array<string, mixed>> $address
      * @return array{canonical: string, hash: string, city: string, errors: array<int, string>}
      */
-    public static function buildContext(array $address, array $items, $totalPrice): array
+    public static function buildContext(array $address): array
     {
         $errors = [];
 
@@ -181,51 +174,8 @@
             $errors[] = 'building';
         }
 
-        $aggregated = [];
-        foreach ($items as $item) {
-            $id = isset($item['id']) && is_string($item['id']) ? trim($item['id']) : '';
-            if ($id === '') {
-                continue;
-            }
-
-            $quantity = $item['quantity'] ?? null;
-            if (!is_int($quantity) && !is_float($quantity) && !(is_string($quantity) && is_numeric($quantity))) {
-                continue;
-            }
-
-            $quantity = (int) $quantity;
-            if ($quantity <= 0) {
-                continue;
-            }
-
-            if (!isset($aggregated[$id])) {
-                $aggregated[$id] = 0;
-            }
-            $aggregated[$id] += $quantity;
-        }
-
-        if ($aggregated === []) {
-            $errors[] = 'items';
-        }
-
-        // Порядок позиций и порядок ключей JSON на контекст не влияют: сортируем байтово.
-        ksort($aggregated, SORT_STRING);
-
-        $cartParts = [];
-        foreach ($aggregated as $id => $quantity) {
-            $cartParts[] = $id . ':' . $quantity;
-        }
-
-        $total = self::toKopecks($totalPrice);
-        if ($total < 0) {
-            $errors[] = 'total';
-            $total = 0;
-        }
-
         $canonical = 'v' . self::VERSION
-            . '|addr:' . $city . ';' . $street . ';' . $building
-            . '|cart:' . implode(',', $cartParts)
-            . '|total:' . $total;
+            . '|addr:' . $city . ';' . $street . ';' . $building;
 
         return [
             'canonical' => $canonical,
diff --git a/www/app/Service/UserApi/Support/ExpressQuote/ExpressQuoteContext.php b/www/app/Service/UserApi/Support/ExpressQuote/ExpressQuoteContext.php
--- a/www/app/Service/UserApi/Support/ExpressQuote/ExpressQuoteContext.php
+++ b/www/app/Service/UserApi/Support/ExpressQuote/ExpressQuoteContext.php
@@ -5,9 +5,8 @@
 /**
  * Переходники от реальных форм запросов ИС к каноническому контексту (OPSOMN002-373).
  *
- * Контекст строится из «корзины и адреса, участвующих в расчёте доставки» — ровно из того,
- * что и так уходит в OMS за интервалами. Координаты, индекс, fullAddress, filterSettings
- * и AB-параметры в контекст не входят.
+ * Контекст строится из адреса назначения в запросах выдачи и оформления.
+ * Товары, количества и сумма корзины не ограничивают обещанную цену доставки.
  */
 class ExpressQuoteContext
 {
@@ -35,11 +34,7 @@
             ],
         ];
 
-        return ExpressQuoteSpec::buildContext(
-            $address,
-            self::items($data, ['products']),
-            self::value($data, ['totalItemPrice'])
-        );
+        return ExpressQuoteSpec::buildContext($address);
     }
 
     /**
@@ -68,24 +63,17 @@
             ],
         ];
 
-        return ExpressQuoteSpec::buildContext(
-            $address,
-            self::items($data, ['products', 'items']),
-            self::value($data, ['products', 'totalItemPrice'])
-        );
+        return ExpressQuoteSpec::buildContext($address);
     }
 
     /**
-     * Создание заказа V4: тело запроса плюс корзина из prepareCartForDelivery().
-     *
-     * Сумма — totalCost заказа до прибавления доставки; в корзине лежит она же.
+     * Адрес назначения из запроса создания заказа V4.
      *
      * @param array<mixed, mixed> $order тело запроса создания заказа
-     * @param array<mixed, mixed> $cart  результат prepareCartForDelivery(): items[{id,quantity,price}], totalPrice
      *
      * @return array{canonical: string, hash: string, city: string, errors: array<int, string>}
      */
-    public static function fromOrderCreate(array $order, array $cart): array
+    public static function fromOrderCreate(array $order): array
     {
         $address = [
             'city' => [
@@ -103,43 +91,7 @@
             ],
         ];
 
-        // Сумма — строго order.totalCost, как в контракте: правило валидации V4 делает её
-        // обязательной, а запасной ход на cart.totalPrice дал бы другое число и молча
-        // разошёлся бы с контекстом выдачи.
-        $total = self::value($order, ['order', 'totalCost']);
-
-        return ExpressQuoteSpec::buildContext($address, self::items($cart, ['items']), $total);
-    }
-
-    /**
-     * Позиции корзины, приведённые к паре «идентификатор + количество».
-     *
-     * @param array<mixed, mixed> $data
-     * @param array<int, string> $path
-     *
-     * @return array<int, array{id: string|null, quantity: mixed}>
-     */
-    private static function items(array $data, array $path): array
-    {
-        $rows = self::value($data, $path);
-        if (!is_array($rows)) {
-            return [];
-        }
-
-        $items = [];
-        foreach ($rows as $row) {
-            if (!is_array($row)) {
-                continue;
-            }
-
-            $id = $row['id'] ?? null;
-            $items[] = [
-                'id' => is_string($id) ? $id : null,
-                'quantity' => $row['quantity'] ?? null,
-            ];
-        }
-
-        return $items;
+        return ExpressQuoteSpec::buildContext($address);
     }
 
     /**
diff --git a/www/app/Service/UserApi/Services/V4/Order/OrderService.php b/www/app/Service/UserApi/Services/V4/Order/OrderService.php
--- a/www/app/Service/UserApi/Services/V4/Order/OrderService.php
+++ b/www/app/Service/UserApi/Services/V4/Order/OrderService.php
@@ -851,9 +851,9 @@
             return null;
         }
 
-        $context = ExpressQuoteContext::fromOrderCreate($order, $cart);
-
-        // Неполный контекст (нет города, дома или позиций) совпадением не считается:
+        $context = ExpressQuoteContext::fromOrderCreate($order);
+
+        // Неполный контекст (нет города или дома) совпадением не считается:
         // обещать по нему показанную цену нечем.
         if ($context['errors'] !== []) {
             throw $this->expressQuoteRefusal(
```

## 6. Полный production-diff BFF

Отдельный файл: [bff.patch](bff.patch).

```diff
diff --git a/app/Domain/Orders/Support/ExpressQuote/ExpressQuoteSpec.php b/app/Domain/Orders/Support/ExpressQuote/ExpressQuoteSpec.php
--- a/app/Domain/Orders/Support/ExpressQuote/ExpressQuoteSpec.php
+++ b/app/Domain/Orders/Support/ExpressQuote/ExpressQuoteSpec.php
@@ -127,22 +127,13 @@
     // ---------------------------------------------------------------- контекст
 
     /**
-     * Канонический контекст расчёта доставки.
+     * Контекст обещанной цены доставки: только адрес назначения.
+     * Слот подписан отдельно; товары и суммы проверяются штатным оформлением заказа.
      *
-     * Вход намеренно приведён к «корзине и адресу, участвующим в расчёте доставки»: это ровно то,
-     * что каждая сторона и так отправляет в ИС за интервалами. Цены позиций в контекст не входят —
-     * они не сопоставимы между точками.
-     *
-     * Типы входа намеренно свободные: данные приходят из разных DTO, проверка их формы —
-     * часть контракта, а не забота вызывающего кода.
-     *
-     * @param array<string, array<string, mixed>> $address уровни city/street/building с ключами fiasId и name
-     * @param iterable<array<string, mixed>> $items позиции с ключами id и quantity
-     * @param int|float|string|null $totalPrice рубли
-     *
+     * @param array<string, array<string, mixed>> $address
      * @return array{canonical: string, hash: string, city: string, errors: array<int, string>}
      */
-    public static function buildContext(array $address, iterable $items, mixed $totalPrice): array
+    public static function buildContext(array $address): array
     {
         $errors = [];
 
@@ -167,51 +158,8 @@
             $errors[] = 'building';
         }
 
-        $aggregated = [];
-        foreach ($items as $item) {
-            $id = isset($item['id']) && is_string($item['id']) ? trim($item['id']) : '';
-            if ($id === '') {
-                continue;
-            }
-
-            $quantity = $item['quantity'] ?? null;
-            if (!is_int($quantity) && !is_float($quantity) && !(is_string($quantity) && is_numeric($quantity))) {
-                continue;
-            }
-
-            $quantity = (int) $quantity;
-            if ($quantity <= 0) {
-                continue;
-            }
-
-            if (!isset($aggregated[$id])) {
-                $aggregated[$id] = 0;
-            }
-            $aggregated[$id] += $quantity;
-        }
-
-        if ($aggregated === []) {
-            $errors[] = 'items';
-        }
-
-        // Порядок позиций и порядок ключей JSON на контекст не влияют: сортируем байтово.
-        ksort($aggregated, SORT_STRING);
-
-        $cartParts = [];
-        foreach ($aggregated as $id => $quantity) {
-            $cartParts[] = $id . ':' . $quantity;
-        }
-
-        $total = self::toKopecks($totalPrice);
-        if ($total < 0) {
-            $errors[] = 'total';
-            $total = 0;
-        }
-
         $canonical = 'v' . self::VERSION
-            . '|addr:' . $city . ';' . $street . ';' . $building
-            . '|cart:' . implode(',', $cartParts)
-            . '|total:' . $total;
+            . '|addr:' . $city . ';' . $street . ';' . $building;
 
         return [
             'canonical' => $canonical,
diff --git a/app/Domain/Orders/Support/ExpressQuote/ExpressQuoteContext.php b/app/Domain/Orders/Support/ExpressQuote/ExpressQuoteContext.php
--- a/app/Domain/Orders/Support/ExpressQuote/ExpressQuoteContext.php
+++ b/app/Domain/Orders/Support/ExpressQuote/ExpressQuoteContext.php
@@ -37,12 +37,6 @@
             ],
         ];
 
-        // Позиции — ровно те, что уходят в запрос интервалов. Цены позиций в контекст не входят.
-        $items = [];
-        foreach ($request->products ?? [] as $product) {
-            $items[] = ['id' => data_get($product, 'id'), 'quantity' => data_get($product, 'quantity')];
-        }
-
-        return ExpressQuoteSpec::buildContext($address, $items, $request->totalItemPrice);
+        return ExpressQuoteSpec::buildContext($address);
     }
 }
diff --git a/app/Domain/Orders/Data/Logistics/Product.php b/app/Domain/Orders/Data/Logistics/Product.php
--- a/app/Domain/Orders/Data/Logistics/Product.php
+++ b/app/Domain/Orders/Data/Logistics/Product.php
@@ -24,16 +24,7 @@
             if (!$currentSku?->message) {
                 continue;
             }
-
-            // OPSOMN002-373: доставка считается по qty — тому количеству, которое реально уедет
-            // в заказ. initQty здесь остался от OMNIES-7441, где на «полную комплектацию»
-            // переводили и количество, и сумму; денежная половина того решения давно вернулась
-            // к qty (params->price), а количественная осталась, и запрос стал противоречивым.
-            if ($basketProduct->qty <= 0) {
-                continue;
-            }
-
-            $product = new Product(['id' => $vendorCodeSKu, 'quantity' => $basketProduct->qty]);
+            $product = new Product(['id' => $vendorCodeSKu, 'quantity' => $basketProduct->initQty]);
             $products->push($product);
         }
 
diff --git a/app/Domain/Orders/Data/Logistics/V2/Product.php b/app/Domain/Orders/Data/Logistics/V2/Product.php
--- a/app/Domain/Orders/Data/Logistics/V2/Product.php
+++ b/app/Domain/Orders/Data/Logistics/V2/Product.php
@@ -26,18 +26,8 @@
                 continue;
             }
 
-            // OPSOMN002-373: количество берём из qty — того, что реально уедет в заказ.
-            // initQty здесь остался от OMNIES-7441 (2108b5b5), где на «полную комплектацию»
-            // переводили и количество, и сумму. Денежная половина того решения давно вернулась
-            // к qty: totalItemPrice этого же запроса берётся из params->price, а params->initPrice
-            // в боевом коде не используется вовсе. В результате запрос сообщал OMS количество по
-            // одной мерке, а сумму по другой.
-            if ($basketProduct->qty <= 0) {
-                continue;
-            }
-
             if ($withQuantityOne) {
-                for ($i = 0; $i < $basketProduct->qty; $i++) {
+                for ($i = 0; $i < $basketProduct->initQty; $i++) {
                     $product = new Product([
                         'id' => $vendorCodeSKu,
                         'quantity' => 1,
@@ -49,7 +39,7 @@
             } else {
                 $product = new Product([
                     'id' => $vendorCodeSKu,
-                    'quantity' => $basketProduct->qty,
+                    'quantity' => $basketProduct->initQty,
                     'price' => (float) self::formattingPrice($basketProduct->basketItemPriceTotal),
                 ]);
 
diff --git a/app/Domain/Orders/Actions/CourierCommonDeliveryDataAction.php b/app/Domain/Orders/Actions/CourierCommonDeliveryDataAction.php
--- a/app/Domain/Orders/Actions/CourierCommonDeliveryDataAction.php
+++ b/app/Domain/Orders/Actions/CourierCommonDeliveryDataAction.php
@@ -83,6 +83,11 @@
             $dispatchWarehouseId,
         );
 
+        // Клиент не подтверждал цену свежего токена: не подменяем им старый обычный ID.
+        if ($selectedInterval !== null && ExpressQuoteToken::looksLikeToken($selectedInterval->id)) {
+            $this->refuseExpressQuote($deliveryCourierId, 'unsigned_selection');
+        }
+
         return $selectedInterval ? CommonDeliveryData::fromDeliveryInterval($selectedInterval) : null;
     }
 
@@ -96,7 +101,7 @@
     {
         $context = ExpressQuoteContext::fromSearchDeliveryIntervalsRequest($request);
 
-        // Неполный контекст (нет города, дома или позиций) совпадением не считается:
+        // Неполный контекст (нет города или дома) совпадением не считается:
         // с такими данными токен не выдаётся, сверять нечего.
         if ($context['errors'] !== []) {
             $this->refuseExpressQuote($token, 'context_mismatch', $context['errors']);
```

## 7. Тесты и общие фикстуры — обязательно обновить

Патчи выше не содержат изменений тестов. Их нельзя считать готовой к merge правкой без этого шага.

### Integration

- `www/tests/Unit/Service/UserApi/Support/ExpressQuote/ExpressQuoteContextTest.php`
- `www/tests/Unit/Service/UserApi/Support/ExpressQuote/ExpressQuoteSpecTest.php`
- `www/tests/Unit/Service/UserApi/Support/ExpressQuote/ExpressQuoteTokenTest.php`
- `www/tests/Unit/Service/UserApi/Services/V2/Delivery/ExpressQuoteIssuanceTest.php`
- `www/tests/Unit/Service/UserApi/Services/V4/Order/ExpressQuoteOrderPriceTest.php`
- `www/tests/mocks/data/express-quote-vectors.json`

### BFF

- `app/Domain/Orders/Tests/ExpressQuoteContractUnitTest.php`
- `app/Domain/Orders/Actions/Tests/CourierCommonDeliveryDataActionUnitTest.php`
- `app/Domain/Orders/Tests/Fixtures/express-quote-vectors.json`
- Существующие тесты `formatProducts` и оформления в `app/Http/ApiV3/Modules/Orders/Tests/CommitOrderComponentTest.php`, `app/Http/ApiMobileV5/Modules/Orders/Tests/CommitOrderComponentTest.php` — прогнать; добавить сценарии при отсутствии покрытия.

В обеих копиях общих векторов пересчитать `canonical`, `hash`, `payload.ctx`, подписи и зависящие от них отрицательные примеры. Проверки изменения количества и суммы становятся положительными: адресный контекст совпадает. Изменение адреса остаётся отрицательным. Удалить/заменить ожидания агрегации SKU в строке контекста. Одинаковые векторы должны приниматься обоими сервисами.

### Сценарии приёмки

| Сценарий | Ожидание |
|---|---|
| Подписанный клиентский интервал 550 ₽; свежий тот же слот 560 ₽ или 540 ₽ | В BFF и запросе OMS `deliveryCost=550`; ИС передаёт актуальный сырой OMS ID |
| `actualDeliveryCost` отличается от обеих клиентских цен | Берётся именно одноимённое поле свежего ответа OMS |
| Тот же токен, адрес и слот; количество 5 → 2, товары/сумма изменились, штатные проверки заказа проходят | Нет `context_mismatch` из-за корзины; цена из исходного токена |
| Количество увеличилось, остатки достаточны, тот же слот доступен | То же правило сохранения клиентской цены |
| Новый показанный интервал 300 ₽ и его новый токен | В заказ уходит 300 ₽, а не цена прежнего токена |
| Другой адрес/дом | Отказ по контексту, без создания заказа |
| Изменённая подпись или цена без корректной подписи; истёкший срок | Отказ без перехода на свежую цену |
| Другой склад/тариф/время либо исходный слот исчез | Отказ, не выбирать ближайший или первый интервал |
| Несколько совпадений полного ключа слота | Отказ как неоднозначный выбор |
| Старый raw ID 550 ₽ → единственный свежий подписанный интервал 560 ₽ | Отказ в BFF до create, исходный ID не превращается в новую котировку |
| Корректный исходный токен 550 ₽ → свежий токен 560 ₽ | BFF передаёт в ИС исходный токен, не свежий |
| Оформляемое количество превышает остаток или клиентская сумма товаров не совпадает с пересчётом | Штатная ошибка оформления сохраняется |
| Полная корзина A+B, выбранная комплектация A, затем повторный поиск | Общие форматтеры сохраняют прежнее поведение `initQty`; товар B не исключается только из-за `qty=0` |
| Остальные способы доставки / нецелевые Express-тарифы | Поведение до MR сохранено |
| Одинаковое предложение выдано повторно | Токен детерминирован; `selectedInterval` и `isSelected` согласованы |

Проверить полный backend-путь: ИС выдаёт токен → BFF проверяет его → ИС create проверяет тот же токен. Сток, скидки, OMS и платежи подменять тестовыми ответами; реальные списания для проверки не инициировать.

## 8. Порядок включения

До выдачи нового формата контекста оба сервиса должны работать с одинаковым контрактом и общим ключом окружения. Использовать существующий флаг выдачи ИС `user-api.delivery.express_quote_token.is_issue_enabled`.

Если механизм ещё не включали: обновить BFF и ИС с выключенной выдачей, проверить совместимость, затем включить выдачу и выполнить согласованный stage-сценарий. Во время смешанных версий выдачу не включать.

Если уже выдавались токены прежнего контекста с корзиной: после смены контракта они получат `context_mismatch` и потребуют обновления checkout. Это ожидаемое поведение; не добавлять fallback, который молча принимает свежую цену. Перед rollout учесть также открытые checkout с обычными ID. Выключение флага останавливает выдачу, но само по себе не делает старые подписанные токены совместимыми с другим проверяющим кодом.

На stage проверить выбранную цену в созданном заказе и сумме платежа; строку доставки в чеке — на доступном тестовом фискальном сценарии. Если какой-то этап недоступен, отметить его непроверенным.

## 9. Что уже проверено при подготовке предложения

Патчи проверены на применимость к указанным SHA и на PHP-синтаксис. На извлечённых классах выполнено 11 локальных проверок: совместимость контекста ИС/BFF, независимость от корзины, отказ при смене адреса/подписи/срока, сохранение исходной цены, запрет unsigned → signed и отказ при другом слоте. Это ограниченные проверки без полного приложения и внешних запросов, не полный тестовый прогон сервисов и не stage-проверка заказа/оплаты.

Исходники сервисов, MR, окружения и реальные заказы при подготовке предложения не менялись.
