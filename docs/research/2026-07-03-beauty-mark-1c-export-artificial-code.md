# Косметика: передача марки в выгрузку 1С + искусственный 13-значный код (результаты сессии 2026-07-03)

> **Тип:** research / handoff (продолжить правку документации в новой сессии). Документацию по итогам ещё НЕ правили — этот файл фиксирует выводы.
> **Ревизия 2026-07-06:** синхронизировано с уточнениями процессов маркировки (`2026-07-03-arm-store-marking-process.md` §3.6–3.7, ревизия `2026-07-01-beauty-marking-process.md`): **марки в ТК не передаются** (криптохвост похода №1 ОТС — внутренний, поход только для COD); живой чек — **YooKassa `RECEIPT_CREATE`** в `paymentFinalizationProcess`; **marking-экспорт выполняется только для онлайн-оплаты** → для COD в OMS/1С уезжает «сырой» serial (см. §2.5 — новое следствие для дизайна).
> **Скоуп:** как марка косметики доходит до `serial_number` в выгрузке 1С по цепочке **ОТС (gloriaots) → ИС (Integration) → OMS (Starfish) → 1С**, и как встроить **искусственный 13-значный код** без доработки OMS.
> **Связанный документ:** `research/2026-07-01-beauty-marking-process.md` (общий процесс/резки). Здесь — фокус на 1С-выгрузку + искусственный код + модель хранения OMS.
> **Вне скоупа:** разрешительный режим ТС ПИОТ (`inst`/`version`) — `research/2026-06-19-rr-tspot-inst-ver-dorabotki.md`.
> Секреты (JWT/токены из логов) не приводятся.

---

## 1. Новая вводная (постановка)

- У косметики serial КМ = **6 символов** (у своей); у «не своей» косметики длина заранее неизвестна.
- Команда маркировки будет **дополнительно генерить в WebGJISMP 13-значный «искусственный» код**, передаваемый вместе с настоящим КМ.
- Нам нужно: **пробросить искусственный 13 в OMS вместе с настоящим и отдавать его в выгрузке в 1С** (`serial_number`).
- При этом **OMS в ТК и чек отдаёт реальную марку как сейчас**. *(Уточнение 2026-07-06: «в ТК» из вводной — неактуально, марки в ТК не передаются вообще, §2; реальная марка нужна только в **чеке** — YooKassa `RECEIPT_CREATE`, см. §2.5.)*
- Ограничение: **не добавлять новое табличное поле в OMS** — использовать кастомные атрибуты.

## 2. Ключевые факты по коду (проверено этой сессией)

### ОТС (`gloriaots`, `platform/gloriaots/gloriaots`)
- Марка в БД: таблица **`GoodsStatus`**, колонка **`DataMatrix`** = **serial** (без криптохвоста). Криптохвост нигде не персистится.
- Сборка КМ: `MarkUtils.BuildKmCode` = `010+GTIN+21+serial` (length-транспарентно: одежда 31 / косметика 24).
- Обогащение криптохвостом — **в памяти** и **только для COD-заказов с марками** (гейт `OrderWithMarksAndManualPayment`, `OrderToPickup.cs:53-59,174-181`): `OrderToPickup.BuildParamsWithMarksAndCrypto` → `WebGjIsmpClient` `POST /api/KM/GetKMFull?from=OTS` → пишет `good_id_mark_cryptotail`.
- **Куда уходит криптохвост (исправлено 2026-07-06): никуда внешне.** Обогащённые `newOrderParams` идут в `tkOrderManager.UpdateOrder` (`OrderToPickup.cs:63`), но **carrier-мапперы поля марки не отправляют** (CDEK/5Post/Почта/Яндекс/DPD — проверено, `2026-07-03-arm-store-marking-process.md` §3.7). В Kafka к OMS уведомление строится из **исходных** `ctx.OtsOrderParams` (`OrderToPickup.cs:69`) → **serial + validation, БЕЗ криптохвоста** (`GoodReachingService.cs:17-23`).
- **Резка №1:** `WebGjIsmpResponse.GetMarkSerial() = km.Substring(18,13)` (хардкод 13) при сопоставлении ответа WebGJISMP с позицией (`OrderToPickup.cs:153`). Для косметики (serial 6) не сойдётся → криптохвост не привяжется — **тихо, без внешнего эффекта** (криптохвост похода №1 потребителя не имеет). **Приоритет понижен**; реальный риск — возможный exception `Substring(18,13)` на коротком `km` (< 31), уронит ORDER_PICKUP для COD — проверить.

### ИС (`avg-integration-service`, `platform/integration/integration/www`)
- FF-хоп `TransferService::transferOtsOrderStatus` (`:2108-2110`): `good_id_mark` → `datamatrixCode` **без обрезки**; криптохвост из сообщения ОТС не читает (его там и нет).
- MARKING-экспорт `OrderService::fillCryptoDatamatrixCodes` (`:4961-4996`, триггер `ExportDestinationEnum::MARKING`): собирает `010+GTIN+21+serial` → `getKMFull` → перезаписывает `datamatrixCode` полным КМ в OMS.
- **Выгрузка в 1С:** `OrderService::export` (`:832`), кейсы `ECOM_1C` (`:873`→`OrderExportEcomMutator`), `CBR_1C` (`:984`→`OrderExportCbrMutator`). **Резка №2:** `AbstractOrderExport1CMutator.php:1165` — `if strlen(datamatrixCode)>13 → substr(18,13)` → `serial_number`.
- Эндпоинт экспорта: `POST /order/export` (`app/Service/UserApi/routes/api.php:92`) → `OrderActionController::export`, `$data = $request->validated()`.
- **ExportOrderRequest НЕ содержит правила `items.*.customAttributes`** → `validated()` их **срезает**. Т.е. сейчас на вход экспорта customAttributes не доходят.
- `OmsClient`: есть `addItemCustomAttribute(itemId, ...)` → `POST /item/{itemId}/customattributes`; и fetch заказа с `displayableFields.customAttributes=true` (`Client.php:262-270`).

### OMS (`Starfish`, `platform/starfish24/core/Order`)
- `Item` → таблица **`item`**; марка = колонка **`datamatrixCode`** + валидация `datamatrixCodeUuid/DateTime/Inst/Ver/RawValue`. **`inst`/`version` уже заведены (CLD-27103).**
- **qty:** `ItemServiceImpl.splitItemsByQuantity` (`:311-317`) — при `quantity>1` разбивает на строки по qty=1 → **2 шт = 2 строки, у каждой свой `datamatrixCode`**.
- **customAttributes:** отдельная таблица **`custom_attribute`** (`owner`, `objectId`, `name`, `value`), для позиции `owner="Item"`, `objectId=item.getItemId()`. Пишется/читается per-item (`ItemServiceImpl:201-203`, `:1108-1109`, `:886-887`). Эндпоинт `POST/GET /item/{itemId}/customattributes` (`ItemController:50-68`).
- **Статус-DTO `ItemStatusInfoDto` (INT 132.0.94) customAttributes НЕ содержит** (`:22-27`) — через статус-апдейт их не передать; нужен выделенный эндпоинт customattributes.
- Фискализация: `pay-service/OnlinePaymentServiceImpl.java:304-319` кладёт `datamatrixCode` в реквизиты чека.

### 2.5. Когда `datamatrixCode` в OMS — serial, а когда полный КМ (следствие ревизии 2026-07-06)

MARKING-экспорт (то самое обогащение `fillCryptoDatamatrixCodes`) вызывается **только из `paymentFinalizationProcess.bpmn`** (единственное вхождение `destination=marking` во всех GJ-процессах) и **только в ветке «Онлайн оплата?» = Да** (`paymentTypeId == 'prepaid'`), перед чеком `RECEIPT_CREATE` (YooKassa). Отсюда состояние `item.datamatrixCode` на момент 1С-выгрузки:

| Сценарий | `datamatrixCode` при выгрузке в 1С | Резка №2 (`if strlen>13 → substr(18,13)`) | `serial_number` в 1С: одежда / косметика |
|---|---|---|---|
| **Онлайн (prepaid)**, финализация | **полный КМ** (после marking-экспорта) | срабатывает | serial 13 ✅ / `serial6+мусор` ❌ |
| **COD (постоплата)**, финализация | **serial** (marking-экспорта нет) | НЕ срабатывает (13 ≤ 13; 6 ≤ 13) | serial 13 ✅ / **serial 6 как есть** (не 13!) |
| Ранние выгрузки (`export.bpmn`, `exportAfterPicking.bpmn` — `1c-ecom`/`1c-cbr` до финализации) | **serial** | НЕ срабатывает | serial 13 ✅ / serial 6 |

Следствия для искусственного кода:
1. Проблема «в 1С уезжает не-13» у косметики есть **в обоих сценариях**, но с разным содержимым: онлайн → `serial6+мусор` (резка №2), COD → чистый `serial6`. Искусственный 13 закрывает оба случая единообразно.
2. **Источник искусственного кода не может быть только marking-экспорт** (`getKMFull` похода №2): для COD он не вызывается. Значит ИС должна получать искусственный код либо отдельным вызовом `getKMFull` в момент 1С-экспорта, либо раньше (FF-хоп `transferOtsOrderStatus` / SFS-хоп от АРМ) — см. §3.
3. Для **SFS** (сборка в магазине, АРМ) картина та же: АРМ доводит до OMS serial (через ИС, `mark`→`datamatrixCode`), полный КМ появляется только на онлайн-финализации. Детали SFS-контура: `2026-07-03-arm-store-marking-process.md` §3.

### Прод-логи (2026-07-03, read-only, `integration-awg-new-logs-prod`)
- **1С-выгрузка (ЦБР):** `POST /api/Starfish/Orders` в `gloria_jeans_1c_cbr` (через WebApi `rnd-webapi-bal`). XML `<order_entry>` с `quantity=1` на позицию и `<serial_number>5AA0…</serial_number>` (13 симв.). Схема фиксированная — **customAttributes в 1С-payload нет** (искусственный код должен идти в `serial_number`).
- **OMS отдаёт per-item customAttributes:** ответ `POST /v1/order/list/full` (`displayableFields.customAttributes=true`) — у позиций реальные `customAttributes[]`: `categoryName`, `barcode`, `priceType`, `baseStoreCode`, `couponId`, `cancellationStage`; рядом `datamatrixCode:"5AA…"` (13), `markable:true`.

## 3. Целевой дизайн (без доработки OMS)

1. **Источник искусственного 13:** WebGJISMP `getKMFull` возвращает его новым полем в ответе → **ИС берёт оттуда** (ОТС не трогаем; ИС уже ходит в getKMFull). ⚠️ **Уточнение 2026-07-06 (из §2.5):** существующий вызов `getKMFull` в ИС (marking-экспорт) выполняется **только для онлайн-оплаты**; для COD-заказов ИС должна получить искусственный код **отдельным вызовом `getKMFull` в момент 1С-экспорта** (или при записи customAttribute на более раннем хопе — FF `transferOtsOrderStatus` / SFS-статус от АРМ). Точку вызова зафиксировать в контракте с маркировкой (B1).
2. **Хранение в OMS:** per-item customAttribute (`owner="Item"`, `objectId=itemId`, напр. `name="artificial_serial"`) через `OmsClient::addItemCustomAttribute` → `POST /item/{itemId}/customattributes`. **Новое поле/правки OMS не нужны** — механизм есть, OMS уже так хранит `categoryName` и др.
3. **Выгрузка в 1С:** подставлять искусственный 13 в `serial_number` вместо `substr(18,13)` реальной марки. Для этого ИС на входе экспорта должен видеть customAttributes: либо **тянуть заказ с `customAttributes=true`**, либо **добавить правило `items.*.customAttributes` в `ExportOrderRequest`** (иначе `validated()` режет). Помнить про §2.5: для COD/ранних выгрузок в `datamatrixCode` лежит **serial**, и текущая резка №2 для него не срабатывает — подстановка искусственного кода должна заменить обе ветки (и `substr(18,13)` для полного КМ, и passthrough serial).
4. **OMS → чек:** реальный `datamatrixCode` — как сейчас, **не трогаем**: полный КМ появляется в позиции на онлайн-финализации (marking-экспорт) и уходит в чек `RECEIPT_CREATE` (YooKassa) вместе с `datamatrixCodeValidation`. Про ТК не думаем — **марки в ТК не передаются вообще** (ревизия 2026-07-06). Для COD чека OMS нет (POS курьера/ТК, без марки) — выбытие через 1С-контур; т.е. для COD-косметики корректный `serial_number`/искусственный код в 1С — **единственный носитель марки**, критичность выше.
5. **Дискриминатор косметика/одежда:** уже доступен — `categoryName` в item customAttributes (или длина serial 6 vs 13).

**Итог:** искусственный код физически в OMS (`custom_attribute` по `itemId`), OMS его хранит/отдаёт, генерит/использует ИС. Java-код OMS не правим.

## 4. Открытые вопросы (статус)

### A — наша зона (закрыто кодом/логами)
- **A1 (хранение per-item без правок OMS):** ✅ `/item/{itemId}/customattributes` + `addItemCustomAttribute`.
- **A2 (OMS отдаёт customAttributes):** ✅ подтверждено проде (`/v1/order/list/full`). Остаток: путь `/order/export` режет их (`validated()`) → правка ИС (правило/fetch с customAttributes=true).
- **A3 (точка подстановки):** ✅ `serial_number` в `AbstractOrderExport1CMutator` — подтверждено 1С-трафиком.
- **A4 (формат в ОТС):** одежда 13 (`5AA…`), поштучно; косметику увидеть на ИФТ (SQL по `GoodsStatus.DataMatrix`).

### B — WebGJISMP / команда маркировки (внешнее)
- **B1:** имя/формат поля искусственного 13 в ответе `getKMFull` + допустимость вызова `getKMFull` из ИС в момент 1С-экспорта для COD-заказов (§2.5, §3 п.1).
- **B2:** кто генерит, стабилен ли (персистится), поштучно ли уникален, детерминирован ли при повторном запросе.
- **B3:** нужен ли криптохвост косметике вообще (SYS-MRK-10 `[ТРЕБУЕТ УТОЧНЕНИЕ]`) — влияет на marking-экспорт ИС (полный КМ в чек YooKassa) и на судьбу похода №1 ОТС (обновлено 2026-07-06: поход №1 внешнего потребителя не имеет, в ТК ничего не уходит — кандидат на удаление, см. `2026-07-01-beauty-marking-process.md` §6 п.3).

### C — команда 1С (внешнее; база Ecomm/ЦБР не в клонах)
- **C1:** что ждут в `serial_number` для косметики (искусственный 13) и делает ли 1С своё добивание Z, или принимает готовый 13.

### D — WMS → ОТС (контракт)
- **D1:** формат `good_id_mark` для косметики (чистый serial vs 24 vs 13-с-Z).

## 5. Что доправить в документации (статус на 2026-07-06)

- ✅ **Сделано 2026-07-06:** `2026-07-01-beauty-marking-process.md` — исправлен шаг 5 (марки в ТК не передаются), гейт похода №1 (только COD), приоритет резки №1 понижен, судьба похода №1 вынесена в открытые вопросы; `architecture/2026-06-03-marking-process-map.md` — убран криптохвост из Kafka-контракта, добавлена оговорка про ТК; создана/выверена `2026-07-03-arm-store-marking-process.md` (SFS, чек YooKassa, постоплата, §3.6–3.7).
- ⏳ Осталось: в `2026-07-01-beauty-marking-process.md` добавить раздел «искусственный 13-значный код» и целевой дизайн из §3 этого файла (после закрытия B1–B2); синхронизировать §4 (дискриминатор — `categoryName` уже есть в customAttributes) и §5 (доработки: запись `addItemCustomAttribute`, правило/fetch в `ExportOrderRequest`, подстановка в `serial_number` с учётом обеих веток §2.5).
- Не заводить дизайн в `architecture/2026-06-03-marking-process-map.md` — там только карта; ссылки достаточно.

## 6. Ссылки (код)

- **ОТС:** `gloriaots/src/GloriaOTS.ApplicationCore/Utils/MarkUtils.cs`; `.../Handlers/ORDER_TO_PICKING/OrderToPickup.cs` (`:63` ТК, `:69` уведомление, `:153` матч); `.../ApiClients/WebGjIsmp/Models/WebGjIsmpResponse.cs` (`GetMarkSerial :51-54`); `.../OrderStatusNotifiers/Starfish/Sender.cs`; БД: `Persistence/Migrations/OrderContextModelSnapshot.cs` (таблица `GoodsStatus`).
- **ИС:** `.../Exchange/Services/V1/Common/TransferService.php:2108-2110`; `.../UserApi/Services/V1/Order/OrderService.php` (`export :832`, `ECOM_1C :873`, `CBR_1C :984`, `fillCryptoDatamatrixCodes :4961-4996`); `.../UserApi/Mutators/V1/Order/AbstractOrderExport1CMutator.php:1165`; `.../Http/Requests/V1/Order/System/ExportOrderRequest.php`; `.../Http/Controllers/V1/Order/OrderActionController.php:32-40`; `.../OmsClient/Clients/Client.php` (`addItemCustomAttribute :841`, order fetch customAttributes=true `:262-270`); `app/Service/UserApi/routes/api.php:92`.
- **OMS:** `Order/src/main/java/com/starfish24/entities/Item.java:34-97`; `.../entities/CustomAttributes.java`; `.../services/itemService/ItemServiceImpl.java` (`splitItemsByQuantity :311`, customAttributes persist `:201-203`,`:1108`, read `:886`, `updateItemsStatus :539`); `.../controller/ItemController.java:50-68,120`; `.../dto/item/ItemStatusInfoDto.java:22-27`; `.../services/converter/ItemConverter.java`; `pay-service/.../OnlinePaymentServiceImpl.java:304-319`.
- **WebGJISMP:** `platform/marks/WebGJISMP/WebGJISMP/WebGJISMP.Common/PGUtil.cs` (chemistry→ISMP5), `.../KMCollection.cs`, `.../WebGJISMP/Controllers/KMController.cs` (`GetKMFull`).

## 7. Ссылки (Confluence / Jira)

- Confluence: корень beauty `165406763`; ТЗ `165408124` (маркировка), `165408218` (OMS), `165408217` (ИС), `165397174` (косметика в складских системах, OPSLOG).
- Jira: `OPSOMN002-25` ([ИС] Beauty: требования + блок.вопросы), `OPSOMN002-18` (маркировка), `OPSLOG-3053/3054/3064/3111` (косметика в складских системах, 13+Z), `CLD-27103` (OMS inst/version — сделано).

## 8. Resume pointer (следующая сессия)

1. Получить у маркировки ответы **B1–B2** (формат/генерация искусственного кода + допустимость вызова `getKMFull` на 1С-экспорте для COD, §2.5) — они разблокируют финальный контракт.
2. По ним обновить `2026-07-01-beauty-marking-process.md` (§3 дизайн, §5 доработки ИС) — с учётом двух веток из §2.5 (онлайн: полный КМ/резка №2; COD: passthrough serial).
3. При наличии тестовых косметических заказов — прогнать SQL по `GoodsStatus.DataMatrix` (A4) и сквозную трассировку **для обоих типов оплаты**: онлайн (getKMFull → полный КМ → чек YooKassa → 1С serial_number) и COD (serial passthrough → 1С).
4. Согласовать с 1С (C1) и WMS/ОТС (D1) контракт формата.
5. Проверить риск exception `GetMarkSerial`/`Substring(18,13)` на коротком `km` косметики в ОТС для COD-заказов (§2) — вместе с решением судьбы похода №1.
