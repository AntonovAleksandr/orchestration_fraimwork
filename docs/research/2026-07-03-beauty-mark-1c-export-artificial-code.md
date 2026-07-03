# Косметика: передача марки в выгрузку 1С + искусственный 13-значный код (результаты сессии 2026-07-03)

> **Тип:** research / handoff (продолжить правку документации в новой сессии). Документацию по итогам ещё НЕ правили — этот файл фиксирует выводы.
> **Скоуп:** как марка косметики доходит до `serial_number` в выгрузке 1С по цепочке **ОТС (gloriaots) → ИС (Integration) → OMS (Starfish) → 1С**, и как встроить **искусственный 13-значный код** без доработки OMS.
> **Связанный документ:** `research/2026-07-01-beauty-marking-process.md` (общий процесс/резки). Здесь — фокус на 1С-выгрузку + искусственный код + модель хранения OMS.
> **Вне скоупа:** разрешительный режим ТС ПИОТ (`inst`/`version`) — `research/2026-06-19-rr-tspot-inst-ver-dorabotki.md`.
> Секреты (JWT/токены из логов) не приводятся.

---

## 1. Новая вводная (постановка)

- У косметики serial КМ = **6 символов** (у своей); у «не своей» косметики длина заранее неизвестна.
- Команда маркировки будет **дополнительно генерить в WebGJISMP 13-значный «искусственный» код**, передаваемый вместе с настоящим КМ.
- Нам нужно: **пробросить искусственный 13 в OMS вместе с настоящим и отдавать его в выгрузке в 1С** (`serial_number`).
- При этом **OMS в ТК и чек отдаёт реальную марку как сейчас**.
- Ограничение: **не добавлять новое табличное поле в OMS** — использовать кастомные атрибуты.

## 2. Ключевые факты по коду (проверено этой сессией)

### ОТС (`gloriaots`, `platform/gloriaots/gloriaots`)
- Марка в БД: таблица **`GoodsStatus`**, колонка **`DataMatrix`** = **serial** (без криптохвоста). Криптохвост нигде не персистится.
- Сборка КМ: `MarkUtils.BuildKmCode` = `010+GTIN+21+serial` (length-транспарентно: одежда 31 / косметика 24).
- Обогащение криптохвостом — **в памяти**: `OrderToPickup.BuildParamsWithMarksAndCrypto` → `WebGjIsmpClient` `POST /api/KM/GetKMFull?from=OTS` → пишет `good_id_mark_cryptotail`.
- **Куда уходит криптохвост:** обогащённые `newOrderParams` → `tkOrderManager.UpdateOrder` (`IShipmentServiceFacade`, `OrderToPickup.cs:63`) = **в ТК/перевозчика**. В Kafka к OMS уведомление строится из **исходных** `ctx.OtsOrderParams` (`OrderToPickup.cs:69`) → **serial + validation, БЕЗ криптохвоста**.
- **Резка №1:** `WebGjIsmpResponse.GetMarkSerial() = km.Substring(18,13)` (хардкод 13) при сопоставлении ответа WebGJISMP с позицией (`OrderToPickup.cs:153`). Для косметики (serial 6) не сойдётся → криптохвост не привяжется. **Зона влияния — ТК, не OMS/чек.**

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

### Прод-логи (2026-07-03, read-only, `integration-awg-new-logs-prod`)
- **1С-выгрузка (ЦБР):** `POST /api/Starfish/Orders` в `gloria_jeans_1c_cbr` (через WebApi `rnd-webapi-bal`). XML `<order_entry>` с `quantity=1` на позицию и `<serial_number>5AA0…</serial_number>` (13 симв.). Схема фиксированная — **customAttributes в 1С-payload нет** (искусственный код должен идти в `serial_number`).
- **OMS отдаёт per-item customAttributes:** ответ `POST /v1/order/list/full` (`displayableFields.customAttributes=true`) — у позиций реальные `customAttributes[]`: `categoryName`, `barcode`, `priceType`, `baseStoreCode`, `couponId`, `cancellationStage`; рядом `datamatrixCode:"5AA…"` (13), `markable:true`.

## 3. Целевой дизайн (без доработки OMS)

1. **Источник искусственного 13:** WebGJISMP `getKMFull` возвращает его новым полем в ответе → **ИС берёт оттуда** (ОТС не трогаем; ИС уже ходит в getKMFull).
2. **Хранение в OMS:** per-item customAttribute (`owner="Item"`, `objectId=itemId`, напр. `name="artificial_serial"`) через `OmsClient::addItemCustomAttribute` → `POST /item/{itemId}/customattributes`. **Новое поле/правки OMS не нужны** — механизм есть, OMS уже так хранит `categoryName` и др.
3. **Выгрузка в 1С:** подставлять искусственный 13 в `serial_number` вместо `substr(18,13)` реальной марки. Для этого ИС на входе экспорта должен видеть customAttributes: либо **тянуть заказ с `customAttributes=true`**, либо **добавить правило `items.*.customAttributes` в `ExportOrderRequest`** (иначе `validated()` режет).
4. **OMS → ТК/чек:** реальный `datamatrixCode` — как сейчас, **не трогаем**.
5. **Дискриминатор косметика/одежда:** уже доступен — `categoryName` в item customAttributes (или длина serial 6 vs 13).

**Итог:** искусственный код физически в OMS (`custom_attribute` по `itemId`), OMS его хранит/отдаёт, генерит/использует ИС. Java-код OMS не правим.

## 4. Открытые вопросы (статус)

### A — наша зона (закрыто кодом/логами)
- **A1 (хранение per-item без правок OMS):** ✅ `/item/{itemId}/customattributes` + `addItemCustomAttribute`.
- **A2 (OMS отдаёт customAttributes):** ✅ подтверждено проде (`/v1/order/list/full`). Остаток: путь `/order/export` режет их (`validated()`) → правка ИС (правило/fetch с customAttributes=true).
- **A3 (точка подстановки):** ✅ `serial_number` в `AbstractOrderExport1CMutator` — подтверждено 1С-трафиком.
- **A4 (формат в ОТС):** одежда 13 (`5AA…`), поштучно; косметику увидеть на ИФТ (SQL по `GoodsStatus.DataMatrix`).

### B — WebGJISMP / команда маркировки (внешнее)
- **B1:** имя/формат поля искусственного 13 в ответе `getKMFull`.
- **B2:** кто генерит, стабилен ли (персистится), поштучно ли уникален, детерминирован ли при повторном запросе.
- **B3:** нужен ли криптохвост косметике вообще (SYS-MRK-10 `[ТРЕБУЕТ УТОЧНЕНИЕ]`) — влияет на резку №1 (ТК).

### C — команда 1С (внешнее; база Ecomm/ЦБР не в клонах)
- **C1:** что ждут в `serial_number` для косметики (искусственный 13) и делает ли 1С своё добивание Z, или принимает готовый 13.

### D — WMS → ОТС (контракт)
- **D1:** формат `good_id_mark` для косметики (чистый serial vs 24 vs 13-с-Z).

## 5. Что доправить в документации (для новой сессии)

- `research/2026-07-01-beauty-marking-process.md` — добавить раздел «искусственный 13-значный код» и целевой дизайн из §3 этого файла; синхронизировать §4 (дискриминатор — `categoryName` уже есть в customAttributes) и §5 (доработки: запись `addItemCustomAttribute`, правило/fetch в `ExportOrderRequest`, подстановка в `serial_number`).
- Уточнить, что резка №1 (ОТС) влияет на ТК, не на OMS/чек (уже поправлено в §3 mermaid того файла — свериться).
- Не заводить дизайн в `architecture/2026-06-03-marking-process-map.md` — там только карта; ссылка достаточно.

## 6. Ссылки (код)

- **ОТС:** `gloriaots/src/GloriaOTS.ApplicationCore/Utils/MarkUtils.cs`; `.../Handlers/ORDER_TO_PICKING/OrderToPickup.cs` (`:63` ТК, `:69` уведомление, `:153` матч); `.../ApiClients/WebGjIsmp/Models/WebGjIsmpResponse.cs` (`GetMarkSerial :51-54`); `.../OrderStatusNotifiers/Starfish/Sender.cs`; БД: `Persistence/Migrations/OrderContextModelSnapshot.cs` (таблица `GoodsStatus`).
- **ИС:** `.../Exchange/Services/V1/Common/TransferService.php:2108-2110`; `.../UserApi/Services/V1/Order/OrderService.php` (`export :832`, `ECOM_1C :873`, `CBR_1C :984`, `fillCryptoDatamatrixCodes :4961-4996`); `.../UserApi/Mutators/V1/Order/AbstractOrderExport1CMutator.php:1165`; `.../Http/Requests/V1/Order/System/ExportOrderRequest.php`; `.../Http/Controllers/V1/Order/OrderActionController.php:32-40`; `.../OmsClient/Clients/Client.php` (`addItemCustomAttribute :841`, order fetch customAttributes=true `:262-270`); `app/Service/UserApi/routes/api.php:92`.
- **OMS:** `Order/src/main/java/com/starfish24/entities/Item.java:34-97`; `.../entities/CustomAttributes.java`; `.../services/itemService/ItemServiceImpl.java` (`splitItemsByQuantity :311`, customAttributes persist `:201-203`,`:1108`, read `:886`, `updateItemsStatus :539`); `.../controller/ItemController.java:50-68,120`; `.../dto/item/ItemStatusInfoDto.java:22-27`; `.../services/converter/ItemConverter.java`; `pay-service/.../OnlinePaymentServiceImpl.java:304-319`.
- **WebGJISMP:** `platform/marks/WebGJISMP/WebGJISMP/WebGJISMP.Common/PGUtil.cs` (chemistry→ISMP5), `.../KMCollection.cs`, `.../WebGJISMP/Controllers/KMController.cs` (`GetKMFull`).

## 7. Ссылки (Confluence / Jira)

- Confluence: корень beauty `165406763`; ТЗ `165408124` (маркировка), `165408218` (OMS), `165408217` (ИС), `165397174` (косметика в складских системах, OPSLOG).
- Jira: `OPSOMN002-25` ([ИС] Beauty: требования + блок.вопросы), `OPSOMN002-18` (маркировка), `OPSLOG-3053/3054/3064/3111` (косметика в складских системах, 13+Z), `CLD-27103` (OMS inst/version — сделано).

## 8. Resume pointer (следующая сессия)

1. Получить у маркировки ответы **B1–B2** (формат/генерация искусственного кода) — они разблокируют финальный контракт.
2. По ним обновить `2026-07-01-beauty-marking-process.md` (§3 дизайн, §5 доработки ИС).
3. При наличии тестовых косметических заказов — прогнать SQL по `GoodsStatus.DataMatrix` (A4) и сквозную трассировку (getKMFull → OMS custom_attribute → 1С serial_number).
4. Согласовать с 1С (C1) и WMS/ОТС (D1) контракт формата.
