# Stage 12 — WB FBS через модуль Starfish: системы GJ и роль OTS

**Дата среза:** 2026-07-23  
**Статус:** complete-for-current-pass  
**Покрытие:** письмо/предложение Starfish, Jira, Confluence и локальные snapshots
OMS/Integration/OTS; без проверки лицензии, кода поставщика, кабинета WB,
production images и реального FBS-заказа  
**Уровни уверенности:** `confirmed`, `high`, `proxy`, `hypothesis`, `unknown`
в значениях из `00-PLAN.md`.

## 0. Scope и главный вывод

Исследуется возможный переход Gloria Jeans на FBS Wildberries с использованием
отдельно лицензируемого модуля «Маркетплейсы» Starfish.

Главный вывод:

> Предложение Starfish похоже на готовый **marketplace execution layer внутри
> OMS**, но не на подключение WB «под ключ». Оно существенно сокращает разработку
> WB API, FBS lifecycle, поставок и этикеток в OMS, однако не отменяет
> GJ-specific интеграцию с остатками, WMS/1С, маркировкой, бухгалтерским
> контуром, финансовой сверкой и эксплуатацией.

Роль OTS **условна**. OTS нужен, если новый FBS-заказ будет исполняться через
существующий путь `OMS → OTS → WMS/1С`. OTS не должен становиться владельцем
WB API, FBS-поставок, этикеток WB или финальных статусов площадки. Если склад
работает непосредственно через workplace модуля Starfish и OMS интегрируется с
нужной складской системой без OTS, OTS можно не включать в целевую цепочку.

Нельзя считать подтверждёнными:

- наличие модуля в текущей лицензии GJ;
- наличие исходного кода `wildberries-connector` в доступном GJ-контуре;
- совместимость модуля с текущим fork/release Starfish;
- production-готовность заявленных функций на актуальном WB API;
- возможность запуска за шесть недель без выбора склада, stock master,
  рабочего места упаковки, бухгалтерской схемы и marking flow.

## 1. Источники и границы доказательства

| Источник | Что подтверждает | Что не подтверждает |
|---|---|---|
| Письмо бизнеса и ответ команды Starfish, переданные 2026-07-23 | Коммерческое предложение, заявленный функциональный scope, сроки и отсутствие модуля в текущей лицензии | Договорной BOM, код, deployed version, соответствие актуальному WB API и результат UAT |
| Jira `OPS-10382` | В 2024 году завершалось исследование возможности FBS/DBS WB | Результат исследования и production-запуск |
| Jira `OPSLOG-754` | Существовала отдельная задача оценки FBS | Содержание оценки: description/comments пусты |
| Confluence `118293200`, `118295722`, `118296442` | Исторический контур массовой отгрузки/маркировки `1C8 ЛЦ НСК → GJMarkUpdate → WebGJISMP → СБИС/ЦРПТ → WB` | Позаказный FBS lifecycle, OMS/OTS и рабочее место упаковки |
| Confluence `108045251`, v26 | Реальный складской scope маркировки: WMS, ТСД, короба, видеоконтроль, перемещения, печать, MarkUpdate и УПД | Что эти процессы уже подходят для FBS без доработок |
| Confluence `130125049`, v12 | Для отгрузки на МП со складов/магазинов АО уже требовались изменения интеграций и движения марок | Текущую production-версию и применимость к FBS |
| Confluence `60692097`, v41 | OMS хранит stock/reserve/threshold и считает доступность как `S - R - T`; физические остатки центральных складов приходят через OTS | Marketplace channel split и текущую конфигурацию safe stock для WB |
| Confluence `63470495`, v76 от 2026-06-10 | Действующий контракт `OMS Starfish → OTS`: создание/проверка заказа, резерв и передача в складской контур | WB-specific интеграцию |
| Confluence `149758157`, v60 от 2026-07-14 | Отдельные требования `Orders by Channels` к планированию долей WB/Ozon/eCom, min/max, stop list и manual override | Runtime allocation доступного остатка и факт production-запуска OBC |
| Локальный OMS Order, clean `master` `8ffafbef` | В core есть FBS/marketplace primitives, supply/barcode workflow и ссылка на `wildberries-connector` | Наличие connector в лицензии/deployment GJ |
| Локальные OTS/Integration/BPMN snapshots | Текущий generic путь OMS → OTS → WMS/1С и обратные статусы/марки | Совпадение с production images и готовность к WB |

## 2. Что именно продаёт Starfish

Ниже «заявлено» означает содержание ответа команды Starfish, а не независимо
подтверждённый production-факт.

| Заявленная функция | Предлагаемый владелец | Что найдено в GJ snapshot | Что ещё должен подтвердить GJ |
|---|---|---|---|
| Выгрузка остатков в WB | Marketplace module + OMS Stock | В OMS есть stock, reserve, threshold | Источник физического stock, единственный reserve owner, channel allocation, latency, replay и защита от oversell |
| Получение заказов WB | WB connector + OMS Order | В Order есть `marketplaceId`, FBS dispatch и выбор external service | Актуальный connector, dedupe/cursor, кабинеты/юрлица/склады, mapping WB ID/SKU |
| Workplace упаковки и оклейки | OMS-UI/module | В Order есть barcode scan/FBS primitives | Реальный UI release, роли, scanners/printers, partial pick, причины недосбора и recovery |
| Этикетка упаковки | WB connector/module | Есть workflow получения barcode | Формат/версия WB API, повторная печать, хранение и передача в WMS |
| Этикетка поставки | WB connector/module | Есть сущности supply/external supply barcode | Правила формирования поставки, закрытия, сроков и handover |
| Статусы поставки и заказов | WB connector ↔ OMS | Есть event-driven supply workflow | Полная status matrix WB↔OMS↔WMS, идемпотентность, таймеры и отмены |
| Передача КИЗ в WB | WB connector/module | OMS/OTS могут переносить марки из складского ответа | Где физически сканируется КИЗ, validation, агрегация и legal flow |
| Финальные статусы WB | WB connector/module | Generic OMS lifecycle есть | Как финал WB влияет на реализацию/возврат/резерв и финансовые документы |
| Омниканальный/safe stock | OMS Stock или отдельный allocation layer | Подтверждён `S - R - T` и многоуровневые thresholds в OMS | Пропорциональный split по каналам не подтверждён; нужен contract с OBC и текущим eCom |

### 2.1. Что подтверждает локальный OMS-код

В `platform/starfish24/core/Order`:

- `DispatchExternalServiceImpl.java:73` явно включает
  `wildberries-connector` в event-based FBS обработку;
- `DispatchServiceImpl.java:203` для `dispatchType=fbs` выбирает сервис по
  `marketplaceId`, а не по carrier;
- `PickItemServiceImpl.java:95` содержит FBS barcode-picking;
- `DispatchCreateStep` и handlers реализуют стадии запроса supply ID,
  добавления заказов в supply и получения barcode;
- сущности `Dispatch`/`DispatchView` содержат `marketplaceId`,
  `externalSupplyId` и external supply barcode.

В `platform/starfish24/core/OMS-UI` найдено не только generic monitoring:

- FBS workplace умеет печатать лист сборки/реестр, pallet/cargo labels,
  начинать и завершать сборку и переводить отгрузку в shipping;
- ветка WB закрывает отгрузку через `clientServiceName=wildberries-connector`;
- scanner UI различает WB/SMM package sticker и DataMatrix.

Это `high` для наличия продуктовых hooks в локальном core и только `proxy` для
готовности отдельного WB connector. Репозиторий connector и его GJ deployment
не найдены; WB-specific cloud-config route и FBS-specific GJ BPMN также не
найдены. Исторический Sber FBS config показывает происхождение generic
возможностей, но не наличие WB-модуля в GJ. Кодовая возможность не равна
лицензионному праву или production готовности.

### 2.2. Коммерческие условия из письма

Это фиксация полученного предложения, а не проверка договора или итоговой цены:

| Месячный объём | Цена за заказ без НДС |
|---:|---:|
| 200–300 тыс. | 1,84 ₽ |
| 300–400 тыс. | 1,59 ₽ |
| 400–500 тыс. | 1,46 ₽ |
| 500–650 тыс. | 1,29 ₽ |

Полный выкуп лицензии с исходным кодом заявлен как **6 960 600 ₽ без НДС**.
Рекомендация поставщика — начать с позаказной оплаты, затем выкупить лицензию.

Сроки из предложения:

- шесть недель до первого marketplace после решения о FBS;
- в среднем четыре недели на подключение/настройку одного marketplace в OMS;
- шесть недель доработок складских и учётных систем GJ.

Неизвестно, включены ли в эти суммы и сроки support/maintenance, обновления WB
API, non-prod environments, migration текущего GJ fork, GJ adapters, UAT,
security review, monitoring, rollback и последующие доработки возвратов.

## 3. Подтверждённый AS-IS вокруг WB

### 3.1. Заказы, продажи и финансы

Свежий документальный контур WB:

```text
WB orders / sales / returns
    → WebApi
    → обработка 1С «ОбменWB»
    → РК+, РК-, РРН, ПН и связанные документы
    → отдельные weekly/financial сверки
```

Evidence: Confluence `165397303`, `165397510`, `165395786`,
`165411281`, `55008219`; Jira `OPSMPC-1051`, `1047`, `1107`.

Новый OMS FBS-поток нельзя просто добавить параллельно: надо решить, какие
order-функции остаются в `ОбменWB`, а какие выключаются. Иначе появляются два
order master и риск двойных РК/РРН/статусов. Наиболее безопасная граница:

- WB/Starfish OMS — operational lifecycle заказа;
- текущий 1С WB — бухгалтерские документы, продажи/возвраты, расчёты и
  закрытие периода;
- передача в 1С — идемпотентный downstream contract по единому business key.

### 3.2. Поставки и маркировка

Исторический подтверждённый контур относится к батчевой отгрузке на МП:

```text
1C8 ЛЦ НСК / WMS / ТСД
    → перемещение и короба
    → GJMarkUpdate
    → WebGJISMP
    → СБИС / ЦРПТ
    → WB
    → акт приёмки
    → УПД / корректирующие документы
```

В Confluence `108045251` перечислены реальные операции и объекты, которых
может коснуться FBS: группировка складских заявок, отбор WMS, печать,
сканирование коробов и марок через ТСД, видеоконтроль, перемещения,
`ГостПечОтгрузкиМП`, `УПДВайлдберриз`, GJMarkUpdate и WebGJISMP.

Но эта цепочка не доказывает готовность к позаказному FBS. Для FBS требуется
отдельно подтвердить:

- сканирование КИЗ на конкретную order line/package;
- получение и печать WB package/supply labels;
- cut-off и SLA сборки;
- partial pick и отмену до/после упаковки;
- handover/drop-off и обратный статус;
- возврат КИЗ/товара и повторный ввод в доступность;
- юридическую и бухгалтерскую модель FBS вместо безусловного повторения
  текущего MOVE_STORES/УПД flow.

## 4. Целевая граница систем

```text
Wildberries API / кабинет
        ↕ WB order, stock, labels, supply/status, final state
Лицензируемый Starfish WB connector
        ↕ normalized marketplace events
Starfish OMS
   ├─ Order: operational order master
   ├─ Stock: reserve + available-to-sell
   ├─ Camunda/BPM: FBS lifecycle/retry/compensation
   ├─ OMS-UI: operations/exceptions/packing, если выбран этот workplace
   └─ Adapter/events
        ├─ [conditional] OTS → WMS/TGW/1C execution
        ├─ 1C WB/Ecom: accounting documents
        ├─ 1C8/WMS/ТSD or ARM: physical pick/pack/scan
        ├─ GJMarkUpdate/WebGJISMP/СБИС/ЦРПТ: marking/EDI
        └─ DWH/finance: completeness and settlement controls
```

### 4.1. Mastership

| Данные/событие | Предлагаемый master |
|---|---|
| Внешний заказ, WB status, label и settlement | WB |
| Оперативное состояние FBS-заказа и mapping внешних ID | Starfish Order |
| Физический остаток и складской факт | Выбранная 1С/WMS/розничная система |
| Резерв и рассчитанный available-to-sell | Один согласованный владелец; наиболее естественно OMS Stock, но current OTS reserve надо развести |
| Бухгалтерские документы | 1С |
| Юридически значимое движение КИЗ/УПД | GJMarkUpdate/WebGJISMP/СБИС/ЦРПТ вместе с 1С |
| Аналитика и контроль полноты | DWH/BI, не управляющий master |

## 5. Матрица затрагиваемых систем

| Система | Влияние | Обязательность | Нужное решение/доработка |
|---|---|---|---|
| WB кабинет/API | Высокое | обязательно | FBS warehouses, кабинеты, юрлица, токены, rate limits, assortment, fallback |
| Starfish marketplace module / WB connector | Высокое | обязательно для выбранного решения | Лицензия, BOM, source/version, deployment, API support, SLA |
| OMS Order | Высокое | обязательно | FBS order model, external IDs, dedupe, status mapping, cancellations/returns |
| OMS Stock | Высокое | обязательно | Physical stock input, reserve owner, threshold, ATS, publish SLA, reconciliation |
| Camunda/BPM и workers | Высокое | обязательно | Новый/поставляемый FBS процесс, таймеры WB, retry/DLQ, compensation |
| OMS-UI | Высокое или среднее | обязательно только если это workplace склада | Roles, scan/pack/print, exceptions; не создавать второй конкурирующий UX |
| Gloria OTS | Среднее | условно | Использовать только как transport/WMS bridge; carrier/mapping/barcode/status/warehouse worker |
| Integration / Starfish Adapter | Среднее | условно, зависит от маршрута | Corporate mapping/events; не делать storefront Integration владельцем WB order |
| 1С7 WB / `ОбменWB` | Высокое | обязательно | Разделить старую order ingestion и новый OMS flow; accounting/finance/returns; dedupe |
| 1С7 Ecom / бухгалтерский контур | Среднее/высокое | зависит от утверждённой проводочной модели | Создание/изменение документов и связь с WB settlement |
| 1С8 ЛЦ НСК / WMS / ТСД | Высокое | обязательно при исполнении с ЛЦ | Pick/pack, WB labels, KIZ, partial pick, handover, reverse flow |
| 1С Retail / ARM | Высокое | только для FBS/SFS из магазинов | Store reserve/task/UI/printing/cancel/return |
| GJMarkUpdate | Высокое | для маркируемого товара | FBS movement, order/package-level KIZ и ошибки |
| WebGJISMP / СБИС / ЦРПТ | Высокое | для маркировки/ЭДО | Legal status, validation, UPD model, replay/reconciliation |
| Orders by Channels | Среднее | interface decision | Развести planning share по ассортиментному заказу и runtime ATS/safe stock |
| DataBird / PIM / Price Formation | Низкое для order execution | не включать в MVP без отдельной причины | Сохранить текущие cards/prices; нужны только SKU/MP identifiers и граница stock |
| ENSI offers / сайт / мобильное приложение / checkout | Низкое прямое, среднее косвенное | прямые фичи не ожидаются | Не допустить, чтобы marketplace reserve/safe stock «вымывал» eCom availability |
| DWH/BI/finance | Высокое | обязательно до scale | Cross-ID, полнота, SLA, комиссия, возвраты, один закрытый период |
| Monitoring/secrets/support | Высокое | обязательно | Token rotation, freshness, backlog, 4xx/5xx/429, replay, on-call/runbook |

## 6. Роль OTS

### 6.1. Что OTS делает сейчас

Подтверждённый current route:

```text
OMS/Camunda
    → Integration mapping
    → OTS POST /v2
    → registration / shipment barcode
    → WMS event
    → WmsSync
    → TGW/WMS + registry в 1С

WMS status + DataMatrix
    → OTS
    → Kafka
    → Integration
    → OMS
```

Evidence:

- `platform/starfish24/awg/bpmn-process/.../export.bpmn:24`;
- `camunda-worker/.../OrderExportWithFeedbackHandler.java:41`;
- `integration/.../OrderExportOtsMutator.php:30`;
- `GloriaOTS.Web/.../OrderController.cs:133`;
- `GloriaOTS.Infrastructure/.../WmsService.cs:104`;
- `GloriaOTS.WmsSync/.../TgwWmsService.cs:55`;
- `GloriaOTS.ApplicationCore/.../TgwWmsMapping.cs:12`;
- Confluence `63470495`, `63453034`.

В проверенном OTS snapshot нет WB/FBS/marketplace-specific реализации. OTS
поддерживает generic transport/WMS execution, а не marketplace gateway.

### 6.2. Что OTS не должен делать

- polling/webhook WB orders;
- вычисление долей между marketplace channels;
- владение WB supply;
- получение/печать labels через WB API;
- отправка финальных статусов в WB;
- самостоятельный marketplace order master.

Эти функции должны оставаться у WB connector и OMS marketplace module.

### 6.3. Когда OTS нужен

Включать OTS следует, если выполняется хотя бы одно условие:

- FBS заказы идут в существующий NSK/MSK WMS через нынешний OTS contract;
- OTS остаётся корпоративной точкой reserve/check перед WMS;
- статусы и DataMatrix можно получить из WMS только через OTS/WmsSync;
- OTS формирует необходимый 1С registry для выбранного склада.

Тогда вероятно затрагиваются carrier dictionary/mapping, shipment barcode,
order tracking/params/documents/events/goods statuses, balances/reserves,
`TgwWmsMapping`, конкретный WmsSync worker и конфигурация склада. Для нового
склада потребуется отдельная WmsSync configuration/deployment.

### 6.4. Когда OTS можно обойти

OTS не нужен, если OMS marketplace workplace сам выполняет упаковку/сканирование
и напрямую получает необходимые факты от склада, а 1С/marking/status adapters
реализуются без существующего OTS/WMS route.

Это решение нельзя принять из коммерческого письма: сначала нужно выбрать
конкретный склад и единственное operational workplace.

## 7. Остаток, доли каналов и риск двойного резерва

### 7.1. Что уже есть

Confluence `60692097` подтверждает:

```text
OMS available = stock - reserve - threshold
```

Локальный Stock snapshot дополнительно показывает выбор одного активного
threshold по приоритету:

```text
PRODUCT_AND_WAREHOUSE
→ PRODUCT
→ WAREHOUSE
→ BRAND
→ DEFAULT
```

Это база для safe stock, но не доказательство готового пропорционального
marketplace allocation.

OTS в текущем маршруте также проверяет/резервирует товар. Поэтому включение
нового OMS reservation без изменения current contract может создать двойной
резерв или преждевременное обнуление доступности.

### 7.2. Orders by Channels — не тот же самый слой

Confluence `149758157` описывает **планирование долей заказа/ассортимента** в
WB/Ozon/eCom по процентам, min/max, stop list и manual override. Это не
подтверждённый runtime service распределения текущего sellable stock.

Поэтому правильнее не выбирать «OBC или Starfish» целиком, а зафиксировать
contract:

```text
Orders by Channels
    → плановая квота/ассортимент по каналу

Physical stock master + warehouse events
    → фактический stock

OMS Stock
    → reserve + threshold + runtime available-to-sell
    → WB connector / eCom availability
```

Неизвестно, введён ли OBC в production и должен ли его результат ограничивать
runtime marketplace stock. Это отдельный architecture gate.

## 8. Почему «доработки складских и учётных систем — 6 недель» пока не оценка

Заявленные сроки можно использовать как vendor target только после фиксации
периметра. На длительность сильнее всего влияют:

1. один склад ЛЦ или store fulfillment;
2. OMS-UI или WMS/ARM как workplace сборщика;
3. OTS в цепочке или direct OMS→WMS;
4. один или несколько кабинетов/юрлиц;
5. источник физического stock и единый reserve owner;
6. доли/safe stock и связь с Orders by Channels;
7. новая или существующая бухгалтерская схема 1С;
8. FBS marking/КИЗ/УПД и возвраты;
9. актуальность поставляемого WB connector и совместимость с GJ fork;
10. миграция/выключение order-функций текущего `ОбменWB`.

Шесть недель могут быть реалистичны для ограниченного пилота на одном складе,
если модуль действительно готов, interfaces stable, а GJ adapters малы. Для
end-to-end запуска с WMS, маркировкой, финансами, recovery и production
контролями доступные источники такой срок не подтверждают.

## 9. Решения до лицензирования

### 9.1. Коммерческий BOM

В приложении к договору должны быть перечислены:

- конкретный `wildberries-connector` и поддерживаемые WB API/версии;
- prod/non-prod instances, tenants, кабинеты, юрлица и склады;
- Order/Stock/Camunda/OMS-UI functions, labels, supplies, KIZ, cancels, returns;
- source-code/customization rights и ограничения per-order лицензии;
- совместимость с текущим GJ Starfish fork и порядок upgrade/migration;
- SLA поддержки изменений WB API, security fixes и инцидентов;
- граница vendor work и GJ-specific adapters/UAT;
- возможность shadow mode, replay и rollback.

### 9.2. Архитектурные решения

1. Какой именно FBS warehouse/cabinet/legal entity запускается первым?
2. Где физически собирают и упаковывают заказ?
3. Какой UI является единственным workplace: OMS-UI, WMS или ARM?
4. Нужен ли OTS и какие функции остаются у него?
5. Кто master физического stock, reserve и runtime ATS?
6. Как используются плановые доли Orders by Channels?
7. Какой business key связывает WB order/SRID, OMS order/dispatch, WMS task,
   package/supply, КИЗ и документы 1С?
8. Какие части `ОбменWB` остаются после cutover?
9. Кто merchant of record, кто фискализирует и кто подписывает финансовый close?
10. Кто владеет токенами, инцидентами, replay и ручным fallback?

## 10. Рекомендуемые фазы

1. **Due diligence:** vendor demo на текущем WB API, BOM, source/version,
   architecture decision, RACI и mapping систем.
2. **Shadow pilot:** один кабинет, юрлицо, склад и ограниченный ассортимент;
   читать заказы и считать stock без подтверждения операций в WB.
3. **Controlled FBS pilot:** реальные pick/pack/KIZ/labels/handover, ручной
   sign-off каждого заказа и финансового результата.
4. **Scale:** дополнительные склады/магазины, автоматические returns,
   операционные dashboards и выключение дублирующей order-логики.

Rollback пилота:

- остановить order polling/webhooks и stock publish connector;
- отключить FBS warehouse/listings в WB;
- доисполнить уже принятые заказы через утверждённый manual fallback;
- replay возобновлять по WB cursor/idempotency key без создания дублей.

## 11. Acceptance gates

- Подписан лицензионный BOM и vendor support matrix.
- Production-compatible connector предоставлен и прошёл contract tests на
  актуальном WB sandbox/test cabinet.
- Один заказ прошёл полный путь: receive → reserve → pick → KIZ → label →
  supply → handover → final status → 1С sale → financial reconciliation.
- Пройдены cancel before pick, cancel after pick, partial pick, duplicate
  delivery, timeout/replay, return и lost label.
- Повторная доставка события не создаёт дублей ни в OMS, ни в WMS, ни в 1С.
- Stock reconciliation и publish latency укладываются в SLA; oversell в пилоте
  отсутствует.
- Подтверждён ровно один reserve owner или формально описан handoff резерва.
- Warehouse UAT выполнен на реальных scanners/printers в одном workplace.
- Legal/finance подтвердили КИЗ/УПД/фискализацию и один закрытый период.
- Есть monitoring на freshness, backlog, 4xx/5xx/429, deadline breach, stock
  drift и financial incompleteness.
- Утверждены on-call, runbook, DLQ/replay и rollback drill.

## 12. Строки, перенесённые в EVIDENCE-LEDGER

- `MP-WB-FBS-001` — vendor proposal подтверждает заявленный scope, но не
  production capability.
- `MP-WB-FBS-002` — core Starfish содержит FBS/WB primitives и workplace.
- `MP-WB-FBS-003` — отдельный connector/license/config/deployment не
  подтверждены.
- `MP-WB-FBS-004` — текущий складской marking/УПД trail является batch-supply
  процессом и не доказывает готовность FBS.
- `MP-WB-FBS-005` — OTS является conditional WMS bridge, не WB gateway.
- `MP-WB-FBS-006` — single master stock/reserve/ATS не установлен.
- `MP-WB-FBS-007` — Orders by Channels описывает planned allocation, а не
  подтверждённый runtime ATS.
- `MP-WB-FBS-008` — при current ЛЦ-route затрагиваются OMS, OTS, WMS/1С,
  marking/EDI и DWH/finance.
- `MP-WB-FBS-009` — прямые изменения site/mobile/checkout не ожидаются, но
  shared availability требует защиты.

## 13. Resume pointer

Следующий проход должен закрыть пять конкретных артефактов:

1. договорной BOM/дистрибутив `wildberries-connector`;
2. deployed Starfish release и compatibility matrix;
3. выбранный склад и walkthrough его текущего pick/pack/KIZ/label flow;
4. один обезличенный current WB order + settlement trace;
5. architecture decision по `OMS reserve ↔ OTS reserve ↔ WMS/1С stock` и
   Orders by Channels.
