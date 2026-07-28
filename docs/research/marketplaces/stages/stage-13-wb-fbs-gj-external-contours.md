# Stage 13 — WB FBS: доработки и процессы GJ вокруг модуля Starfish

**Дата среза:** 2026-07-23
**Статус:** complete-for-current-pass
**Покрытие:** Jira, Confluence, локальные snapshots OMS/Integration/OTS/WMS/ARM/1С,
официальная документация WB; без дистрибутива marketplace-модуля, production
walkthrough выбранного ЛЦ, кабинета WB, deployed 1С7/SSIS и закрытого FBS-периода
**Уровни уверенности:** `confirmed`, `high`, `proxy`, `hypothesis`, `unknown`
в значениях из `00-PLAN.md`

## 0. Scope

В этой стадии модуль «Маркетплейсы» Starfish **не исключается**. Наоборот, для
проектирования условно принимается заявление поставщика, что модуль закрывает:

- WB API и получение FBS-заказов;
- выгрузку остатков в WB;
- оперативное состояние marketplace-заказа;
- workplace упаковки и оклейки;
- получение и печать стикеров заказа/поставки;
- WB supply lifecycle и обмен статусами;
- привязку и отправку КИЗ в WB;
- получение финальных статусов заказа.

Это рабочее допущение, а не production proof. Состав модуля, лицензия,
совместимость с GJ release и полнота актуального WB API остаются acceptance
gate из Stage 12.

Фокус Stage 13 — процессы и доработки **вне модуля**:

1. физический остаток, channel allocation и резерв;
2. передача заказа в OTS/WMS/1С;
3. складская сборка, shortage, КИЗ, печать и handover;
4. бухгалтерские документы, продажи, возвраты и закрытые периоды;
5. финансовая сверка и DWH;
6. операционные контроли, cutover и rollback.

Не входят в MVP без отдельного решения:

- автоматизация карточек через DataBird;
- миграция цен;
- store fulfillment;
- несколько ЛЦ и кабинетов;
- собственная разработка WB connector вместо модуля.

## 1. Executive decision

Главный вывод:

> При наличии готового marketplace-модуля основная разработка GJ находится не
> в WB API, а в безопасном соединении OMS с текущими остатками, резервом,
> OTS/WMS, 1С, маркировкой и финансовым закрытием.

Для быстрого пилота на одном уже поддержанном ЛЦ наиболее короткий
подтверждёнными компонентами маршрут:

```text
WB
  ↕ orders / stocks / metadata / labels / supplies / statuses
Marketplace-модуль Starfish
  ├─ OMS Order: operational order master
  ├─ OMS provisional reserve
  ├─ OMS-UI: pack / KIZ / WB label / supply
  └─ generic fulfillment command
         ↓
Integration
         ↓
OTS
  ├─ durable physical reserve
  ├─ correlation / retry
  ├─ WMS command
  └─ 1C registry
         ↓
WMS / 1C8 / TSD
  ├─ physical pick
  ├─ shortage
  ├─ DataMatrix scan
  └─ dock handover
         ↑ status / picked lines / KIZ
OTS → Integration → Starfish module → WB

Отдельно:
WB financial report → wb_weekly / 1C reconciliation / finance close / DWH
```

OTS для FBS не обязателен по смыслу модели, но для первого ЛЦ его
целесообразно переиспользовать как существующий generic bridge к WMS/1С.
Обход OTS оправдан только если у поставщика есть проверенный прямой adapter к
конкретному GJ WMS, покрывающий reserve, TGW, статусы, cancel, 1С registry и
обогащение КИЗ.

## 2. Что подтверждено в текущем GJ-контуре

### 2.1. Передача заказа на склад

Подтверждённый current route:

```text
OMS
  → Integration V1
  → OTS POST /v2
  → physical reserve
  → TGW/WMS ECOM task
  → registry в 1С
```

Evidence:

- Confluence `63470495`, v76 от 2026-06-10 описывает OMS→OTS, снятие
  OMS-резерва после успешной передачи и `SUSPENDED` при нехватке;
- `OrderExportOtsMutator.php:30-63,636-673` маппит OMS order в OTS contract;
- `OrderService.php:835-875` выполняет вызов OTS;
- `OrderController.cs:123-185` принимает `POST /v2`;
- `WmsService.cs:104-157` требует carrier и `SHIPMENT_BARCODE`;
- `TgwWmsService.cs:55-95` пишет TGW telegram и создаёт реестр в 1С;
- `TgwWmsMapping.cs:103-176` создаёт `WMS.ECOMAUF` с `OrderType=ECOM`;
- `OneSService.cs:50-108` поддерживает в этом builder только НСК и МСК eCom.

Confidence: `confirmed` для локальных snapshots и документации; deployed
production images не проверялись.

### 2.2. Остаток и резерв

Подтверждённый путь физического остатка:

```text
1C8
  → OTS WmsSync
  → OTS stock - OTS reserves
  → Integration cron
  → OMS Stock
```

- `OneSService.cs:23-47` читает из 1С8 `good_ean + qty`;
- `StockSyncRequestedConsumer.cs:6-30` публикует изменения по 1000 строк;
- `BalanceRepository.cs:220-268` считает OTS free stock как
  `physical stock - OTS reserves`, blocked SKU даёт 0;
- Integration забирает OTS delta каждые 10 минут и full ежедневно:
  `Kernel.php:27-30`, параметры `EXCHANGE_TRANSFER_STOCK_OTS_*` —
  `exchange.php:42-50`;
- OMS Stock считает доступность с reserve и threshold; уровни threshold:
  product+warehouse, product, warehouse, brand, default:
  `StockExternalService.java:224-279`,
  `AvailThresholdLevelEnum.java:11-16`,
  `StockMongoService.java:450-469`.

Существенное ограничение: в найденной модели threshold нет dimension
`marketplace/channel`. Порог на общем warehouse затронет доступность всех
каналов, включая eCom.

### 2.3. Складские статусы и КИЗ

Текущий WMS/OTS path уже возвращает:

- регистрацию и старт batch/picking;
- собранные и отсутствующие строки;
- `SUSPENDED` при shortage;
- DataMatrix;
- `ORDER_PICKUP`;
- подтверждаемую отмену.

Evidence:

- Confluence `49752540`, v39;
- Confluence `63453034`, v54;
- Confluence `63460277`, v28;
- `WmsStatusEventConsumer.cs:15-73`;
- `TgwWmsMapping.cs:55-100`;
- `TgwWmsService.cs:24-51`.

OTS также умеет получить полный КМ/криптохвост из WebGJISMP:
Confluence `82013706`, v16;
`WebGjIsmpClient.cs:27-58`;
`OrderToPickup.cs:130-163`.

### 2.4. Рабочие места, сканеры и принтеры

В GJ есть reusable технические primitives:

- ARM/TSD сканирует DataMatrix, проверяет SKU, уникальность марки,
  shortage/defect и завершение сборки:
  Confluence `108048195`, v63 от 2026-07-15;
  `OrdersService.java:390-545,949-1132,2118-2167`;
- ARM умеет выбрать принтер и отправить PDF:
  `PrintService.java:420-469`,
  `InternetOrdersScreenService.java:2119-2202`;
- отдельный TSD-процесс печатает внутреннюю «этикетку конечного склада»:
  Confluence `130126638`, v14 от 2026-07-20;
  Jira `OPSRTL-4553`.

Это `proxy` для WB FBS. Найденные ARM/TSD flows относятся к store/SFS либо
внутренним коробочным операциям и не являются готовым WB workplace.

### 2.5. Текущий 1С WB и финансовый контур

Подтверждённый current path:

```text
WB orders / sales / returns
  → WebApi
  → 1C7 WB / ОбменWB
  → РК+ / РК- / РРН / ПН

WB detailed financial report
  → import_weekly_WB / SSIS
  → hybris_import.dbo.wb_weekly
  → СверкаРеализаций1СВБ
  → КорректировкаWB / finance close
```

Evidence:

- `44269101`, v28 от 2026-03-26 — `api/WB/orders` и создание
  `РезервКлиента`;
- `165395786`, v6 — current `ОбменWB`;
- `165397303`, v5 и `165397510`, v2 — WB orders/sales/returns contracts;
- `165411281`, v10 — current financial report и `rrd_id`;
- `55008219`, v21 — ручная сверка по `srid`;
- Jira `OPSMPC-1051`, закрыта 2026-07-20 — active changes в `ОбменWB`;
- Jira `OPSMPC-1107`, на 2026-07-22 ожидала внутреннего тестирования новой
  weekly job/mapping после отключения старого endpoint;
- Jira `OPSMPC-431` — падение 1С на полном объёме `wb_weekly`;
- Jira `OPSMPC-979/1009` — проблемы привязки РРН.

Этот контур нельзя считать заменённым marketplace-модулем.

### 2.6. Generic OMS→DWH

Integration ежедневно выгружает в DWH заказы и статусы OMS:

- schedule: `Kernel.php:35`;
- двухдневное окно OMS: `TransferService.php:3229`;
- поля заказа/позиции и `channel`: `TransferService.php:4573`.

Но generic export не содержит `rrd_id`, settlement report ID, комиссии,
логистики, удержаний, штрафов, хранения и acquiring. Он может быть источником
operational analytics, но не financial source of truth WB.

В доступных локальных `airflow-aero`, `airflow-gj`, `dbt` и
`analytics-scripts` marketplace/WB model не найден. Известный финансовый путь
живёт вне этих repos — в SSIS, `wb_weekly` и 1С. Это lineage gap, а не
доказательство отсутствия аналитики.

## 3. Актуальные внешние ограничения WB

Официальная WB API documentation на дату среза подтверждает:

- FBS управляет assembly orders, metadata, supplies, passes и stickers;
- добавление заказа в supply переводит его `new → confirm`;
- передача supply в доставку переводит orders `confirm → complete`;
- DataMatrix/`sgtin` можно привязать только к order в `confirm`;
- обязательность metadata определяется `requiredMeta`/`optionalMeta`, но
  обязательную по закону маркировку надо передавать независимо от того, в каком
  из этих массивов она пришла;
- stickers доступны только для `confirm`/`complete`;
- supply после перевода в доставку нельзя дополнять;
- FBS virtual seller warehouse связан с конкретным WB office;
- stock API оперирует `warehouseId + chrtId + amount`.

Источники:

- `https://dev.wildberries.ru/docs/openapi/orders-fbs`;
- `https://dev.wildberries.ru/docs/openapi/work-with-products`;
- `https://dev.wildberries.ru/sandbox`.

Практическое следствие: GJ нельзя переводить supply в доставку до подтверждения
pick, загрузки необходимых metadata/KIZ и готовности labels. Это должен
контролировать модуль, но данные и физический факт приходят из GJ.

Официальная инструкция WB от 2026-05-18 отдельно предупреждает, что полный
DataMatrix содержит невидимые GS-разделители. Передача текстового значения без
них может не пройти проверку. Следовательно, контракт WMS→OTS→module должен
переносить полный код без нормализации/обрезания.

Для продаж маркированного товара юрлицам/ИП по FBS WB указывает, что продавец
сам выводит КИЗ из оборота, а после возврата самостоятельно введённый в
выбытие код надо вернуть в оборот в установленный срок. Это не заменяет
отдельного решения GJ Legal/Finance по B2C, УПД и моменту признания продажи.

## 4. Целевая граница ответственности

| Данные/процесс | Master / owner | Что делает GJ вне модуля |
|---|---|---|
| WB order, `assembly_id`, WB status | WB + marketplace-модуль | хранит cross-ID и downstream audit |
| OMS operational order | Starfish Order | создаёт generic warehouse task |
| Provisional reserve до warehouse ack | OMS | TTL, cancel, handoff |
| Physical stock и durable reserve | OTS/WMS/1С | atomic/idempotent reserve и release |
| WB channel allocation | GJ allocation projection / logical bucket | cap, allowlist, safety stock, protection eCom |
| Physical pick и shortage | WMS/TSD | line-level result |
| DataMatrix scan | WMS/TSD | полный serial, uniqueness, validation |
| Полный КМ и статус | WebGJISMP/ЦРПТ | enrichment/legal validation |
| WB metadata, parcel/supply, stickers | marketplace-модуль | получает KIZ и warehouse facts |
| Факт pack/label | module workplace | принтер, роли, exception handling |
| Факт выхода с дока | WMS/TSD или один утверждённый workplace | физический scan/event |
| WB handover status | marketplace-модуль | преобразует GJ event в WB operation |
| Бухгалтерские документы | 1С | idempotent document flow |
| Финансовые начисления | WB detailed report / `wb_weekly` | import, reconciliation, close |
| Operational analytics | OMS events / DWH | raw event lineage и SLA |
| Финансовая аналитика | `wb_weekly` + 1С/DWH | сохраняет grain `rrd_id` |

## 5. Ключевые GJ-доработки

### 5.1. Reserve handoff и идемпотентность

Рекомендуемый contract:

1. Модуль создаёт OMS order с неизменяемым WB external ID.
2. OMS создаёт provisional reserve с TTL.
3. Integration отправляет OTS команду с постоянным `event_id`.
4. OTS атомарно создаёт physical reserve и возвращает `reservation_id`,
   `event_id`, warehouse, version и requested/reserved quantities.
5. Только после ack OMS снимает provisional reserve и сохраняет token handoff.
6. Cancel/partial/timeout обрабатываются повторяемыми transition/release
   командами.

Блокирующий current gap:

- `ReserveEventId` сохраняется;
- в доступном schema primary key есть только по `Id`;
- unique index по `ReserveEventId` не найден;
- `Do_Reserve_*` выполняет insert без проверки повторного `guid`.

Evidence:

- `Reserves_ONES_MOSCOW.sql:1-10`;
- migration `20231019090335_AddBalanceTypesAndFuncs.cs:36-56`.

Следствие: timeout после успешного reserve и retry способны создать повторный
резерв. До пилота нужны idempotent inbox/unique key и возврат первоначального
результата на повторный `event_id`.

### 5.2. Channel allocation и защита eCom

Существующий OMS threshold нельзя использовать как единственный WB safety
stock на общем warehouse: он не channel-specific.

Для пилота нужен logical `channel_bucket_id`, отличный от физического
`source_business_unit_id`.

Минимальные входные данные:

```text
seller/cabinet
source_warehouse
channel_bucket_id
sku
enabled
channel_cap или allocated_quantity/share
safety_stock
protected_for_other_channels
valid_from / valid_to
version
```

Предлагаемая, ещё не утверждённая формула:

```text
WB_ATS =
  max(
    0,
    min(
      channel_cap,
      allocated_quantity,
      OTS_free_stock
        - safety_stock
        - protected_for_other_channels
        - OMS_provisional_not_handed_off
    )
  )
```

`OTS_free_stock` уже вычитает durable OTS reserves. После handoff provisional
reserve OMS должен исчезнуть, иначе один заказ будет учтён дважды.

Confluence `149758157`, v60 описывает Orders by Channels с shares/min/max/
stop-list, но это planning allocation, а не подтверждённый runtime ATS.
Контракт с ним остаётся architecture decision. Для первого пилота допустим
allowlist + фиксированные cap/safety values.

### 5.3. Master-data и cross-system IDs

До SIT должен существовать versioned mapping:

```text
WB sellerWarehouseId
  ↔ channel_bucket_id
  ↔ source_business_unit_id
  ↔ OTS WarehouseType
  ↔ 1C firm/sender IDD
  ↔ WMS warehouse

WB nmId + chrtId + supplierArticle + barcode
  ↔ GJ product/article/EAN

WB orderId + srid + gNumber/orderUid
  ↔ OMS order/clientOrderId
  ↔ OTS order_id + event_id/reservation_id
  ↔ WMS task
  ↔ 1C document IDs

OMS line
  ↔ WB assembly line
  ↔ EAN/article
  ↔ DataMatrix/KIZ

WB supply/package/sticker IDs
  ↔ GJ correlation fields and logs
```

Missing mapping не должен превращаться в silent skip: нужна exception queue с
owner и replay.

### 5.4. OTS/Integration adapter

Must-have:

- явный generic `WB_FBS_HANDOVER`/эквивалент вместо подстановки обычной ТК;
- mapping module/OMS order в existing OTS contract;
- сохранение opaque WB correlation IDs;
- idempotent create/update/cancel;
- line-level shortage и picked quantity;
- полный KIZ обратно в module;
- status reconciliation;
- feature flags по seller/warehouse/SKU.

В `CarrierIdMap.php:11-20` WB carrier отсутствует. Текущий OTS также требует
`SHIPMENT_BARCODE`, создаёт `OrderType=ECOM` и знает ограниченный warehouse
matrix. Это реальные доработки, а не настройка одного токена.

### 5.5. WMS/TSD и operating workplace

Рекомендуемая граница пилота:

- WMS/TSD — task queue, physical pick, shortage, DataMatrix, dock fact;
- marketplace workplace — pack, WB sticker, supply, WB status;
- оператор не повторяет один и тот же этап в двух UI.

Нужно реализовать/проверить:

- SLA-priority queue FBS;
- line-level full/partial/short;
- scan EAN и обязательного DataMatrix;
- запрет чужого/дублирующего/невалидного КИЗ;
- физическую передачу picked items в FBS packing zone;
- printer setup и repeat print;
- dock handover scan;
- cancel до batch, во время pick и после ready;
- return receiving SOP.

WB parcel sticker, supply QR и DataMatrix/KIZ — три разные сущности.
Внутренняя TSD «этикетка конечного склада» не заменяет WB sticker.

### 5.6. Marking/legal

Модуль может загрузить КИЗ в WB, но GJ всё равно должен:

- получить фактически отсканированный код из WMS;
- сохранить GS-разделители и криптохвост;
- проверить соответствие SKU/order line;
- проверить uniqueness и допустимый статус;
- восстановить полный КМ через WebGJISMP, если WMS отдал короткий serial;
- определить юридический документ и событие движения/выбытия;
- обработать возврат и возможный повторный ввод в оборот;
- иметь replay/reconciliation с ЭДО/ЦРПТ.

Исторический WB batch flow:

```text
1C8 ЛЦ → GJMarkUpdate → WebGJISMP → СБИС/ЦРПТ → WB acceptance → УПД
```

подтверждён страницами `118293200`, `118295722`, `118296442`, но не является
готовой юридической моделью FBS. Свежий `149774255`, v24 проектирует
`MOVE_AGENT` после приёмного акта, но помечен draft.

### 5.7. 1С и конфликт с legacy `ОбменWB`

Marketplace-модуль должен быть единственным operational master FBS-заказа.
Нельзя параллельно позволить current `api/WB/orders → ОбменWB` создавать
второй `РезервКлиента`.

До пилота нужны:

1. фильтр pilot FBS seller/warehouse/SKU из legacy order/reserve path;
2. versioned Starfish→1С event contract;
3. idempotent inbox;
4. ключ:
   `(marketplace, seller, srid/external_order_id, line_id, operation_type)`;
5. правила late event и закрытого периода;
6. связь cancellation/return с исходной продажей;
7. разделение operational amount и final settlement amount.

Страница `44269101` описывает `warehouseName`, но не показывает достаточного
FBS cutover/filter contract. Поэтому способ фильтрации надо проектировать, а не
считать существующим.

Рекомендуемая граница:

- OMS/module/OTS — order execution и warehouse registry;
- `ОбменWB`/1С — бухгалтерские документы и downstream finance;
- `wb_weekly` — итоговые суммы, комиссии, услуги и удержания.

### 5.8. Финансы и DWH

Модуль должен отдавать GJ versioned envelope:

```text
event_id
event_type
schema_version
occurred_at / source_updated_at / ingested_at
seller / cabinet / legal_entity
correlation_id
replay/backfill marker
source object version
srid / orderId / orderUid
assembly_id
supply_id / package/sticker IDs
SKU/nmId/chrtId/barcode
quantity
source and normalized status
cancel/return reason
KIZ where applicable
```

Оперативные цены из order event нельзя считать final settlement.

Financial source of truth остаётся подробный отчёт WB на grain:

```text
rrd_id
realizationreport_id
srid / assembly_id / gi_id
operation type
quantity
gross/net/forPay
commission + VAT
logistics / return logistics
fines / deductions / storage / paid acceptance / acquiring
country / currency
```

До pilot close нужны четыре независимые сверки:

1. module events ↔ 1С documents;
2. `wb_weekly` ↔ РРН/ПН;
3. planned handover ↔ physical handover/acceptance;
4. OMS/1С ↔ DWH counts, keys, latency и checksum.

Full DWH mart можно отложить, но нельзя откладывать:

- сохранение raw events и external IDs;
- batch counts/checksum;
- DLQ/replay;
- financial import;
- signed exception register и первый закрытый период.

## 6. Fast-track pilot

### 6.1. Жёсткие ограничения scope

- один seller/cabinet/legal entity;
- один уже поддержанный ЛЦ: НСК или МСК;
- один WB seller warehouse;
- 100–500 SKU allowlist;
- один тип handover;
- одна FBS packing zone и одно operational workplace;
- фиксированный channel cap/safety buffer;
- без store fulfillment;
- без multi-DC routing;
- без миграции DataBird/cards/prices;
- возвраты — обязательный SOP, automation может быть ограничена;
- ручной finance sign-off первого периода допустим.

### 6.2. Что обязательно до первого реального заказа

| Work package | Must |
|---|---|
| Module boundary | demo/contract test WB orders, stocks, metadata, labels, supplies, statuses |
| Reserve | idempotent OTS inbox/unique event, provisional→durable handoff |
| Stock | logical WB bucket, allowlist/cap/safety, protection eCom |
| Master data | warehouse/SKU/order/line/correlation mappings |
| OTS | carrier/handover mapping, barcode, status, cancel, feature flags |
| WMS/TSD | task, pick, short, DataMatrix, dock event |
| Workplace | scanners, printers, pack, reprint, exception path |
| Marking | full KIZ, GS, validation, legal decision |
| 1С | legacy cutover/filter, idempotent downstream documents |
| Finance | production-ready `wb_weekly`, first-period checklist |
| Operations | dashboards, DLQ/replay, on-call, runbook, rollback |

### 6.3. Что можно временно оставить ручным

- фиксирование allocation cap по allowlist;
- редкие исключения приёмки/УПД;
- возвратный SOP при малом объёме;
- DWH backfill/pilot dashboard;
- finance exception review и sign-off.

Нельзя оставлять ручным:

- dedupe заказа и резерва;
- release reserve при cancel;
- сохранение cross-IDs;
- обязательный KIZ;
- создание бухгалтерской цепочки;
- защита закрытого периода;
- audit trail и replay.

## 7. Оценка

Оценка является `hypothesis` до просмотра event/API capability поставляемого
модуля, выбора ЛЦ и fit-gap 1С/Legal.

| Пакет вне модуля | Person-weeks |
|---|---:|
| Architecture, contracts, master data, cutover | 3–6 |
| Integration/OTS reserve, carrier, status, cancel | 5–8 |
| Channel allocation и stock reconciliation | 3–6 |
| WMS/TSD/handover/printing | 5–10 |
| 1С receiver, documents, late events | 6–12 |
| Marking/legal/return | 3–6 |
| Finance/DWH/DQ | 3–6 |
| SIT/UAT/operations/rollback | 6–10 |
| **Итого** | **34–64 person-weeks** |

При параллельной команде и готовом модуле:

- **агрессивный best case:** 6–8 календарных недель;
- **реалистичный pilot range:** 8–10 недель;
- **если нужен новый WMS task type, новый склад или новая legal/accounting
  схема:** 10–14+ недель.

Заявленные поставщиком шесть недель возможны только для узкого пилота на
существующем ЛЦ при готовых interfaces и параллельной работе. Это не доказанная
оценка полного промышленного запуска.

## 8. Acceptance gates

### 8.1. Order и reserve

- duplicate module event создаёт один OMS/OTS/WMS/1С object;
- timeout после успешного OTS reserve и retry не увеличивает reserve;
- cancel до и после OTS ack освобождает каждый тип резерва один раз;
- partial reserve/pick не переводит WB order как полностью готовый;
- late/replayed event не переписывает закрытый документ.

### 8.2. Stock

- сверка `1C physical → OTS stock/reserve → OMS WB bucket → WB published`;
- concurrent eCom/WB order не продаёт одну единицу дважды;
- full/delta tolerates duplicate, out-of-order и replay;
- negative/stale/missing data publishes safe zero;
- WB safety stock не уменьшает eCom сверх утверждённого allocation.

### 8.3. Warehouse и marking

- маркируемый и немаркируемый SKU проходят один заказ;
- EAN вместо обязательного DataMatrix блокирует завершение;
- чужой SKU, duplicate KIZ и invalid mark отклоняются;
- full KIZ сохраняет GS и соответствует order line;
- printer/KIZ upload failure не переводит order в delivery;
- shortage, cancel before pick, cancel during pick и after ready проверены;
- handover status возникает только после физического scan;
- return проверен для good/defect/unreadable KIZ.

### 8.4. 1С, finance и DWH

- каждая order line имеет одну бухгалтерскую цепочку или signed exception;
- `rrd_id` загружен ровно один раз;
- продажи/возвраты связаны по `srid`;
- комиссия, логистика, штрафы, удержания, хранение, приёмка и acquiring
  сверены в допусках Finance;
- replay даёт те же counts/checksums;
- operational DWH хранит `srid`, `assembly_id`, `supply_id`, status,
  business time и ingestion time;
- закрыт один полный расчётный период.

## 9. Rollback

1. Выставить WB published stock в 0 и остановить приём новых заказов.
2. Дренировать уже подтверждённые заказы.
3. Снять только tagged OMS provisional WB reserves.
4. Не выполнять массовое удаление OTS physical reserves.
5. Сверить OMS/OTS/WMS/1С по watermark и business keys.
6. Legacy ingest включать только после reconciliation и установки dedupe
   watermark, иначе возможны двойные документы.
7. Штатный 1С→OTS→OMS stock sync не останавливать.

## 10. Решения, которые нужны сейчас

1. Какой ЛЦ: НСК или МСК?
2. Какой seller/cabinet/legal entity и WB seller warehouse?
3. Подтверждает ли vendor внешний event/API contract, а не только UI?
4. OTS остаётся durable reserve owner?
5. Кто владеет channel allocation и logical WB bucket?
6. Где заканчивается WMS pick и начинается module pack?
7. Где фиксируется physical handover?
8. Как фильтруется FBS в legacy `ОбменWB`?
9. Какова legal схема КИЗ для B2C/B2B и возврата?
10. Кто подписывает первый finance close?
11. Кто on-call owner module↔OTS↔WMS↔1С?

## 11. Evidence additions

- `MP-WB-FBS-010` — OMS→OTS reserve handoff документально существует, но
  OTS idempotency по event ID не обеспечена.
- `MP-WB-FBS-011` — OMS threshold не channel-specific; нужен WB logical bucket.
- `MP-WB-FBS-012` — existing OTS/WMS route reusable, но требует carrier,
  shipment barcode, ECOM mapping и ограничен НСК/МСК.
- `MP-WB-FBS-013` — legacy `ОбменWB` создаёт operational reserve и конфликтует
  с модулем без cutover/filter.
- `MP-WB-FBS-014` — current ARM/TSD scan/print primitives reusable как proxy,
  но WB sticker/KIZ/handover process не готов.
- `MP-WB-FBS-015` — module KIZ upload не заменяет GJ legal marking flow.
- `MP-WB-FBS-016` — `wb_weekly` остаётся financial source of truth.
- `MP-WB-FBS-017` — generic OMS→DWH недостаточен для WB settlement.
- `MP-WB-FBS-018` — узкий pilot оценивается в 6–10 недель, промышленный
  contingency 10–14+ недель.

## 12. Resume pointer

Следующий проход должен быть не документальным, а проектным walkthrough одного
обезличенного заказа:

1. выбрать НСК или МСК;
2. получить module event/API examples;
3. проследить один `orderId/srid` через OMS→OTS→WMS→1С;
4. провести reserve retry test;
5. построить stock reconciliation на 20 SKU;
6. пройти KIZ/label/handover на реальном scanner/printer;
7. подтвердить 1С cutover и первый `wb_weekly` close;
8. зафиксировать ADR по reserve, allocation и workplace.
