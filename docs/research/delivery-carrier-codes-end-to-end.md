# Коды доставки/ТК сквозь все системы (Integration → OMS → OTS → 1С8 WMS / 1С Еком)

> Разбор от 2026-06-09. Контекст: онбординг Яндекс.Доставки, баги OPSLOG-3267 и OPSOMN001-634.
> Цель — карта «какой код где живёт, кто кого зовёт», чтобы заводить новую ТК осознанно.
> Источники: локальные клоны (file:line), Confluence-контракты, Jira. Где утверждение неточное — помечено ⚠️.

## 0. TL;DR

- Перевозчик путешествует по системам в РАЗНЫХ представлениях: строка в OMS → число в OTS → код справочника в 1С8.
- Каждое преобразование — отдельная точка отказа. У Яндекса их было минимум две (OPSOMN001-634 в «ИС» + OPSLOG-3267 в 1С8 WMS).
- **Числовые коды сталкиваются между контрактами**: один и тот же номер значит разное. Никогда не переносить код «по аналогии» — сверять с контрактной страницей конкретной системы.

## 1. Кодовые представления перевозчика (по слоям)

| Слой | Представление | Пример (Yandex) | Где определено |
|---|---|---|---|
| Site/Mobile → Integration(PHP) | — (проксирует выбор доставки) | — | `platform/integration` |
| OMS (Starfish) | **строка** `carrierId` | `yandexNextDayDelivery` (и/или `yandex`) | `core/Dictionary|Parsers|Delivery/.../CarrierEnum.java` (3 копии!) |
| «ИС» (OMS→внешние, экспорт) | маппинг строка→числа | → OTS `8`, → 1С Еком `5` | ⚠️ не в локальных клонах (см. §5) |
| OTS вход `/v2` | **число** `transport_id` | `8` | контракт Confluence pageId **63470495** |
| OTS внутри | enum `ShipmentService` | `YANDEX=8` | `gloriaots/.../ApplicationCore/Constants/ShipmentService.cs` |
| OTS → 1С8 WMS | строка `id_transport` (=число «в лоб») | `"8"` | `gloriaots/.../WmsSync/OneS/OneSService.cs:80` |
| 1С8 WMS | `Код` справочника «ТранспортнаяКомпания» | элемент с Код=8 | git `1s8-enterprise/1c-lc`; данные — в БД WMS |
| 1С Еком (выгрузка заказов) | число `delivery_type` | `5` | контракт Confluence pageId **63470445** |
| НСИ «ТипДоставки» / 1С АРМ выгрузка | число `DeliveryTypeCode` | DPD=60, CDEK=58 … (Яндекса нет) | Integration `DeliveryTypeCodeEnum.php` (зеркало НСИ) |

⚠️ **Это РАЗНЫЕ кодовые пространства.** Не путать `transport_id` (OTS, 8=yandex), `delivery_type` (1С Еком, 5=yandex), `DeliveryTypeCode` (НСИ, 58/60…), и маркетплейс-коды НСИ (где 5=«Самовывоз ЯндексМаркет», 8=СберМегаМаркет). Совпадение чисел — случайно.

## 2. Поток заказа (кто кого зовёт)

```
ЧЕКАУТ:
  Site/Mobile → Integration OrderService → OmsClientV2 → OMS /logistics/delivery-*
  ← carrierId/fulfillmentTypeId/tariffId (строки OMS) оседают на заказе
     (Integration: UserApi/.../OrderService.php:3590-3592)

ЭКСПОРТ заказа из OMS:
  Camunda export.bpmn (topic orderExportWithFeedback, destination=ots|1c-ecom|1c-cbr)
   → camunda-worker OrderExportWithFeedbackHandler
   → Order/OrderExternalExportServiceImpl (читает Settings "export_type")
   → ClientServiceImpl POST http://{export_type}/order/export?destination=ots
   → [«ИС»] мапит carrierId(строка) → transport_id=8 / delivery_type=5  ← OPSOMN001-634
        (starfish24/core/.../ClientServiceImpl.java; сам код маппера — см. §5)

OTS:
  POST /v2 → OTSOrderParams.order.delivery.transport_id:int
   → ShipmentServiceHelper.GetShipmentServiceBy(int)  (gloriaots Helpers/ShipmentServiceHelper.cs:9)
   → ShipmentServiceFacade switch → YandexShipmentService (Infrastructure/Services/ShipmentServices/Yandex/*)
   → HandlersValidator: Carrier из БД по transport_id (HandlersValidator.cs:71)  ← нужна строка Carrier Id="8"
   → WmsSync: OneSService.CreateRegistryAsync → POST 1С8 EcommOrder/CreateOrder, id_transport="8"
        1С8: ОбработкаДанныхEcommOrder.ЗаписатьЗаказКлиента →
             Справочники.ТранспортнаяКомпания.НайтиПоКоду("8") → пусто → 422  ← OPSLOG-3267
```

## 3. Барьеры Яндекса (карта тикетов)

| Тикет | Слой | Симптом | Причина | Фикс | Статус |
|---|---|---|---|---|---|
| **OPSOMN001-634** | «ИС» (OMS→OTS/1С Еком) | заказ → CHECKED_INVALID; ots 400 «Невозможно смаппить ТК»; 1c-ecom 422 | не было маппинга `yandexNextDayDelivery` | добавили carrier→`transport_id=8`/`delivery_type=5` + обрезку ПВЗ `yandex-nd-` | принят на тесте (комм. Данилкиной 2026-06-05) |
| **OPSLOG-3267** | 1С8 WMS | застрял на ORDER_SPLIT; 422 «Неизвестный КОД ТК» | в справочнике ТК 1С8 нет кода 8 | завести элемент «Транспортная компания» Код=8 «Яндекс» | **открыт** |

**Прецеденты онбординга/инцидентов других ТК (как делали раньше):**
- DPD: OPSLOG-3170 «ОТС не может зарегистрировать заказ ПВЗ»; контракт INT65.119; разбор в Confluence «быстрая тезисная инструкция DPD-OTS» (pageId 165404954).
- 5Post: OPSOMN-8439 «неизвестный ID ПВЗ», OPSOMN-8369 «не обновились ID ПВЗ» — синхронизация PickupPoint.
- CDEK: OPSOMN-8670 статус ACCEPTED vs CREATED; DEVLOG001-703 адрес СДЕК.

## 4. Состояние Яндекса в OTS (детально)

Яндекс — **самая полно реализованная новая ТК** в OTS:
- API-клиент: `Infrastructure/ApiClients/Yandex/IYandexApiClient.cs` (Refit, 7 методов) + `YandexApiService`.
- Бизнес-логика: `Infrastructure/Services/ShipmentServices/Yandex/YandexShipmentService.cs` (Create/Update/Status/Cancel/Points) + `OtsYandexResultAdapter` (маппинг ~40 статусов Яндекса → OrderStatus).
- DI: keyed-сервис `AddKeyedScoped<IShipmentService>(ShipmentService.YANDEX,…)` (ServiceCollectionExtensions.cs:100).
- Конфиг prod: `GloriaOTS.Web/appsettings.Production.json` — Yandex BaseUrl `b2b-authproxy.taxi.yandex.net`, `WarehousePlatformMapping` 5801/5501/6003.

**Что мешает Яндексу поехать целиком (помимо OPSLOG-3267):**
1. Таблица `Carrier` (SQL Server WMS-стороны OTS) — нужна строка `Id="8"` на КАЖДЫЙ склад, иначе `HandlersValidator.ValidateTransport` → `UnknownDeliveryID` (`CarrierRepository.cs:9`).
2. Таблица `PickupPoint` с `TkType="yandex"` для заказов type=2 (ПВЗ) — нужна синхронизация точек.
3. ⚠️ Интервалы доставки `MapTimeInterval`/`MapTimeIntervalForDestination` **закомментированы** (`OtsYandexResultAdapter.cs:303-355`) → CreateOrder уходит без даты/интервала.
4. ⚠️ `ShipmentBarcode` для Яндекса OTS формирует как `"GJ"+order_id` (не реальный трек-номер ТК); реальный `request_id` Яндекса лежит в `EXTERNAL_TK_ID`.
5. ⚠️ `WarehousePlatformMapping`: три склада на ОДИН `platform_id` — сверить с кабинетом Яндекса.

## 5. Где «ИС»-маппер carrier→число (открытый вопрос)

Маппинг `yandexNextDayDelivery → transport_id=8 / delivery_type=5` (OPSOMN001-634):
- **НЕ** в PHP `platform/integration` — там нет `yandex` ни на dev, ни на release-26.06 (`git grep` пусто).
- Поля `transport_id`/`pointout_id` — это контракт OTS `/v2` (snake_case), payload собирает OMS-side экспортёр (`ClientServiceImpl` POSTит на `http://{export_type}/order/export`).
- `{export_type}` (Settings) указывает на сервис-получатель — вероятно **`oms-awg-integration`** или **Adapter**; репо `awg/integration-gj` локально — placeholder.
- **TODO для проверки:** определить реальное значение Settings `export_type` (в БД `oms-awg-*`, не в YAML) и найти код этого сервиса. Подтвердить там блок маппинга carrier→transport_id/delivery_type и убедиться, что Яндекс в проде, а не только на тесте.

## 6. Как завести новую ТК целиком (чек-лист на будущее)

1. **OMS** `CarrierEnum` (×3 копии: Dictionary/Parsers/Delivery) — добавить строковый carrierId.
2. **OMS Delivery** — реализовать carrier (registration/calc/cancel/parser), если ТК интегрируется напрямую.
3. **«ИС»-маппер** — carrierId → OTS `transport_id` + 1С Еком `delivery_type` (+ правила ПВЗ).
4. **Integration(PHP) НСИ** — `DeliveryTypeCodeEnum` + `MapByRules` (code/barcode/name) для выгрузки в 1С АРМ; ⚠️ числовой код приходит из НСИ «ТипДоставки» (owner — команда НСИ).
5. **OTS** — `ShipmentService` enum + `IShipmentService` реализация + facade-ветки + DI.
6. **OTS БД** — строка `Carrier` (Id=код, per-warehouse) + синк `PickupPoint` (TkType).
7. **1С8 WMS** — элемент справочника «Транспортная компания» с Код=число (Autonumbering → ставить вручную).
8. **1С Еком** — код `delivery_type` в справочнике.
9. Контрактные страницы Confluence — обновить (иначе дока расходится с кодом, как `8-Hermes`).

## 7. Ключевые ссылки

**Confluence:** 63470495 (контракт OTS /v2, transport_id), 63470445 (INT 132.31.1 1С Еком выгрузка, delivery_type), 165404954 (DPD-OTS инструкция, жизненный цикл статусов), 165405310 (Яндекс доставка), 149774827 (INT236.65.2 Яндекс.Доставка — создание заказа), 49764998 (Список ИС).

**Jira:** OPSLOG-3267 (1С8 WMS, открыт), OPSOMN001-634 (ИС carrier mapping, на тесте), OPSLOG-3170/OPSOMN-8439/8670 (прецеденты DPD/5Post/CDEK).

**Код (file:line):**
- OMS: `core/Dictionary/.../CarrierEnum.java`, `core/Order/.../ClientServiceImpl.java`, `awg/bpmn-process/process/gloriajeans/export.bpmn`, `core/camunda-worker/.../OrderExportWithFeedbackHandler.java`
- OTS: `ApplicationCore/Constants/ShipmentService.cs`, `Helpers/ShipmentServiceHelper.cs:9`, `Infrastructure/Services/ShipmentServiceFacade.cs`, `.../ShipmentServices/Yandex/*`, `Workers/GloriaOTS.WmsSync/OneS/OneSService.cs:80`, `Persistence/Repositories/CarrierRepository.cs:9`
- 1С8: `1s8-enterprise/1c-lc` → `CommonModules/ОбработкаДанныхEcommOrder/Ext/Module.bsl`, `Catalogs/ТранспортнаяКомпания.xml`
- Integration(PHP): `app/Service/Consts/Enums/Delivery/GloriaJeans/DeliveryTypeCodeEnum.php`, `.../Maps/.../DeliveryTypeCodeMapByRulesContract.php`
