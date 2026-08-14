# Маркетплейсы Gloria Jeans — evidence-led исследование

**Старт:** 2026-07-23  
**Статус:** первый и второй evidence-pass завершены; контракт WB FBS снят со
свежей спеки, sandbox smoke и скан прод-каталога выполнены (Stage 20), перенос
заданий между поставками подтверждён фактом, цепочка идентификаторов
(PIM + WB Content, без WebApi) и отсечка статусов `WB_FBS` от OMS утверждены;
в коде — миграция машины состояний `wb_supplies` и клиент `wbapi`.
Открыты: prod-проверки кабинета (пункты выдачи, `decision`-статусы,
маркировочный шлюз), technical spike станции, RACI и production walkthrough
**Область:** направление маркетплейсов GJ, включая площадки, DataBird, карточки, цены,
остатки, заказы, поставки, маркировку, возвраты, взаиморасчёты и отчётность.

## Цель

Собрать долговечную и проверяемую картину работы направления маркетплейсов по
доступным источникам Jira, Confluence и локальному коду. Документы разделяют:

- **подтверждено** — есть прямой источник;
- **высокая уверенность** — несколько согласованных источников;
- **предположение** — правдоподобная связь, которой не хватает прямого подтверждения;
- **неизвестно** — данных недостаточно или источники противоречат друг другу.

Исторические документы не считаются описанием текущего процесса без проверки
свежими задачами, кодом, отчётами или подтверждением владельца процесса.

## Карта исследования

| Документ | Назначение |
|---|---|
| [`00-PLAN.md`](00-PLAN.md) | План, метод, стадии и progress tracker |
| [`00-source-inventory.md`](00-source-inventory.md) | Реестр Jira, Confluence, кода и других источников |
| [`EVIDENCE-LEDGER.md`](EVIDENCE-LEDGER.md) | Сквозные факты, противоречия, гипотезы и пробелы |
| [`TEMPLATE-stage.md`](TEMPLATE-stage.md) | Шаблон атомарного исследования |
| [`OTS-CHANGES-WB-FBS.md`](OTS-CHANGES-WB-FBS.md) | Задание на правки OTS для WB FBS (гибрид от 2026-08-03): роль OTS в потоке, 4 правки P0 + настройка мастер-данных + 3 P1 с якорями file:line, контракт вызова, приёмка |
| [`OPSLOG-3461-ots-implementation.md`](OPSLOG-3461-ots-implementation.md) | Рабочая постановка по задаче OPSLOG-3461 (2026-08-12): исходные данные (склад `9148`, ИДД, `transport_id = 10`, префикс `000370`), реестр 8 расхождений с постановкой, DDL таблиц остатков и контракт именования, точки правок в коде с якорями, порядок работ, приёмка, открытые вопросы |
| [`MARKING-WB-FBS-WITHDRAWAL.md`](MARKING-WB-FBS-WITHDRAWAL.md) | Вопросы команде маркировки (2026-08-05): вывод КМ из оборота на `sold` через `AddMarkTransaction` (`OUT`/`SALE` → ЧЗ `DISTANCE`/`OTHER`), что хранить, и главный разрыв — возврата после `sold` в FBS API нет, он в разделе коммуникаций (`claims`) |
| [`stages/stage-01-overview.md`](stages/stage-01-overview.md) | Общий контур и организационная карта |
| [`stages/stage-02-databird.md`](stages/stage-02-databird.md) | DataBird: роль, обмены и процессы |
| [`stages/stage-03-ozon.md`](stages/stage-03-ozon.md) | Ozon |
| [`stages/stage-04-wildberries.md`](stages/stage-04-wildberries.md) | Wildberries |
| [`stages/stage-05-lamoda-and-others.md`](stages/stage-05-lamoda-and-others.md) | Lamoda и прочие площадки |
| [`stages/stage-06-product-content.md`](stages/stage-06-product-content.md) | Карточки, контент, цены и остатки |
| [`stages/stage-07-supply-fulfillment.md`](stages/stage-07-supply-fulfillment.md) | Поставки, маркировка, FBO/FBS/DBS |
| [`stages/stage-08-orders-returns-finance.md`](stages/stage-08-orders-returns-finance.md) | Заказы, возвраты, комиссии и сверка |
| [`stages/stage-09-active-portfolio-ownership.md`](stages/stage-09-active-portfolio-ownership.md) | Активный портфель, lifecycle status и role-based ownership |
| [`stages/stage-10-databird-operating-model.md`](stages/stage-10-databird-operating-model.md) | Imports/exports, schedule, mapping, ошибки и ручные операции DataBird |
| [`stages/stage-11-e2e-operational-controls.md`](stages/stage-11-e2e-operational-controls.md) | Сквозные цепочки Ozon/WB, контрольные барьеры и финансовый close |
| [`stages/stage-12-wb-fbs-starfish-ots-impact.md`](stages/stage-12-wb-fbs-starfish-ots-impact.md) | WB FBS через модуль Starfish: затрагиваемые системы, stock/reserve и роль OTS |
| [`stages/stage-13-wb-fbs-gj-external-contours.md`](stages/stage-13-wb-fbs-gj-external-contours.md) | WB FBS: GJ-доработки вокруг модуля, reserve handoff, ЛЦ, КИЗ, 1С, finance/DWH и fast-track pilot |
| [`stages/stage-14-ecommerce-order-id-history.md`](stages/stage-14-ecommerce-order-id-history.md) | История `orderId/clientOrderId`: Hybris `1`, Starfish `2`, ENSI allocator, OTS/WMS/1С/DWH semantics и numeric boundaries |
| [`stages/stage-15-wb-fbs-connector-warehouse-sequence.md`](stages/stage-15-wb-fbs-connector-warehouse-sequence.md) | WB FBS Connector: sequence по ролям, API сборочных заданий/стикеров/поставок/пропусков и отдельный lifecycle КИЗ |
| [`stages/stage-16-wb-fbs-fast-track-current-warehouse.md`](stages/stage-16-wb-fbs-fast-track-current-warehouse.md) | Fast-track WB FBS через текущий OTS/WMS: реальный status contract, existing packing/print, companion baseline и tiny WMS seam |
| [`stages/stage-17-wb-fbs-1c-pallet-marking-gate.md`](stages/stage-17-wb-fbs-1c-pallet-marking-gate.md) | WB FBS: печать→PKS/ECOMAUFSTAT, `ОтборЛистПеремещ`, WMS-native owner gate, `PalNam/AUFSHPPAL`, обработка 1С и поздний `deliver` |
| [`stages/stage-18-wb-identifiers-stocks-sandbox.md`](stages/stage-18-wb-identifiers-stocks-sandbox.md) | WB FBS: `chrtId` для остатков, справочник идентификаторов МП, существующий контур чтения остатков, границы песочницы WB и prod-шлюз доступа |
| [`stages/stage-19-wb-fbs-supply-lifecycle-design.md`](stages/stage-19-wb-fbs-supply-lifecycle-design.md) | WB FBS: жизненный цикл поставки в Connector — волновая модель, состояния, ключ группировки, шлюз маркировки перед `deliver` |
| [`stages/stage-20-wb-api-contract-fresh.md`](stages/stage-20-wb-api-contract-fresh.md) | WB FBS: свежий контракт API по спеке — перенос заданий между поставками, `order-ids`, статусы `decision`, эмуляция песочницы, схема тестирования |

## Ограничения текущей версии

- Это не целевая архитектура и не проект внедрения.
- Jira и Confluence могут быть неполными или устаревшими.
- Отсутствие результатов поиска не доказывает отсутствие процесса.
- Утверждения о текущем production-состоянии требуют свежего операционного,
  API-, DB- или log-подтверждения.

## Текущий краткий срез

- DataBird документально подтверждён для цен WB, Ozon и Яндекс.
- Production `mp-connector` доступен и его внутренний PLM/1С cron успешно
  отрабатывает, но фактический вызов товарного endpoint со стороны DataBird и
  последний успешный импорт карточек не подтверждены.
- Историческая конфигурация DataBird раскрывает точные расписания и counters
  апреля 2025, но current enabled jobs, retries, alerts и SLA не установлены.
- Автоматизация карточек через DataBird не завершена: Ozon/WB в реализации,
  Яндекс приостановлен.
- Поставки, маркировка, заказы, возвраты и финансы идут отдельным контуром
  1С/WebApi/API площадок/ЭДО.
- FBO уверенно прослеживается для Ozon и в исторических процессах других
  площадок; текущие FBS/DBS нельзя назначить без проверки кабинетов.
- Lamoda имеет свежие признаки перезапуска, но целевая модель неизвестна.
- Новый пилот Мегамаркета отменён; Kaspi уверенно подтверждён только до 2025.
- Ozon и WB подтверждены как технически `active/live-like`, но active cabinets,
  последние продажи и коммерческий объём этим исследованием не доказаны.
- В Ozon и WB есть двусторонние ручные сверки, но текущие API-миграции,
  незакрытые дефекты WB и отсутствие формального close gate не позволяют
  считать финансовое закрытие доказанным.
- Core Starfish содержит FBS/WB primitives и workplace, но отдельный
  `wildberries-connector`, его лицензия, GJ deployment и production
  совместимость не подтверждены.
- При WB FBS OTS нужен только как existing WMS/1С bridge; WB API, marketplace
  supply, labels и final statuses принадлежат marketplace-модулю при покупке
  Starfish либо новому Connector при custom fast-track.
- Документированный route предполагает provisional reserve в OMS и durable
  reserve в OTS/WMS, но current OTS idempotency по reserve event ID не
  подтверждена и является blocker пилота.
- OMS threshold не channel-specific: для защиты eCom нужен отдельный logical
  WB allocation bucket поверх физического остатка.
- Заявленные Starfish шесть недель возможны только для узкого пилота на
  существующем ЛЦ; текущая evidence-based гипотеза — 6–10 недель при
  параллельной работе и 10–14+ при новом WMS/legal/accounting scope.
- Номер eCommerce-заказа является сквозным natural/idempotency key: ENSI
  `baskets.number` становится OMS `clientOrderId`, OTS/WMS order number,
  1С `idd/documentFoundation` и DWH `code`.
- Подтверждено downstream-разделение `1=Hybris`, `2=Starfish`, но первичное
  rationale выбора `2` в 2022 году не найдено; новый WB range нельзя назначать
  без namespace registry и boundary E2E test.
- Для WB FBS логическая WB-поставка создаётся до завершения физической сборки:
  добавление задания в поставку переводит его в `confirm`, что открывает
  получение стикера и передачу `sgtin`; после physical readiness поставка
  закрывается и только затем получается QR для ворот склада/СЦ.
- WMS fast-track не требует новых складских статусов: подтверждены только
  `ORDER_CONFIRMED_WAREHOUSE`, `PICKING`, `SUSPENDED`, `ORDER_PICKUP`;
  `packed/hold/supply-ready` должны жить как projection Connector, а не WMS.
- Текущий WMS печатает внутреннюю eCom-этикетку и формы, но OTS передаёт только
  `carrierBarcode1`; официальный WB sticker печатается отдельным scan-print
  рабочим местом. Склад согласовал выделенные WB-станции с двумя принтерами
  (2026-07-25), поэтому companion print стал выбранной моделью, а спайк по
  `CarrierZPL` из пилота снят.
- Текущий OTS возвращает serial марки, а WB требует полный КИЗ с GS/crypto
  tail; для `WB_FBS` нужен небольшой OTS enrichment/callback через уже
  используемый WebGJISMP.
- При условии доступа к OTS test, WMS/1С, WB token и packing station кодовый
  fast-track оценивается в 5–8 рабочих дней, production-like pilot — в 7–12;
  главным риском срока остаются контуры и release/access, а не Connector.
- Подтверждены два самостоятельных WMS→1С обмена: PKS после отбора создаёт
  `ОтборЛистПеремещ` с заказом/коробом/КМ, а
  `AUFSHP/AUPSHP/AUFSHPPAL` после паллетной отгрузки создаёт
  `Доставка/Перемещение` и `Документ.Паллет`.
- Смена владельца КМ запускается асинхронно от `ОтборЛистПеремещ`; она не
  выполняется сканом DataMatrix, передачей `sgtin` в WB или вызовом
  `deliver`. Упаковщик не ждёт этот процесс: перед штатной отгрузкой WMS сама
  вызывает `GetCheckOrder` и проверяет все КМ заказа; зеркальный scan/gate в
  Connector не нужен.
- Прямой связи `order_id → pallet_id` нет: она восстанавливается через
  `AufWwsBeleg`, короб `TeNam`, `AUPSHP.PalNam` и `Документ.Паллет`. OTS
  pallet composition сейчас не получает.
- «Подтверждение внутренней отгрузки» — не одно событие: `AUFSHPPAL`
  подтверждает физическую отгрузку WMS для 1С, `IFOUTFSRSTA=50` — успешную
  обработку telegram в 1С, а `wms_shipment` переводит заказ OTS в
  `DELIVERING`. Автоматичность и latency deployed 1С-обработки ещё нужно
  проверить.
- Остатки WB принимаются только по `chrtId`: загрузка по баркоду отключена
  20.05.2026. В 1С-справочнике идентификаторов МП `chrtID` нет, поэтому по
  текущим данным остаток на WB отправить нельзя; при этом нужное поле уже
  приходит в ответе метода, которым справочник наполняется.
- Существующий контур остатков WB работает только на чтение в BI по
  `nmId`/баркоду. Исходящая публикация остатков в WB — новый обмен без
  владельца, источника количества и политики защиты eCom-остатка.
- Поставку нельзя перевести в доставку, если в ней есть задание с обязательной
  незакреплённой маркировкой: одно задание блокирует весь рейс. Вместе с
  требованием включать задание в поставку до сборки это означает, что поставку
  нельзя держать открытой на непрерывном потоке — её якорем должна быть
  складская волна, а буфер держится до поставки.
- Перед `deliver` есть предполётная проверка `POST /api/marketplace/v3/orders/meta`
  со статусами `filled`/`optional`/`required`, поэтому блокировка рейса
  обнаруживается на закрытии волны, а не на воротах.
- Состав поставки со стороны WB больше не читается (`GET /api/v3/supplies/{supplyId}/orders`
  удалён), поэтому проекция `supply_orders` в Connector — единственный источник
  истины по составу.
- Песочница WB зеркалит домены (Marketplace и Контент отдельно) и позволяет
  пройти цепочку «карточка → `chrtID` → склад → остаток → сборочное задание →
  поставка». Она не покрывает реальный стикер, шлюз по маркировке и настоящие
  лимиты, а на production есть отдельный шлюз доступа по пунктам выдачи для
  возвратов.
- Smoke 2026-07-27 подтвердил фактом: перенос задания между поставками
  атомарен (включая reshipment из закрытой), `deliver` пустой поставки —
  `SupplyHasZeroOrders`, добавление в закрытую поставку WB не отклоняет
  (запрет — в Connector), песочница отдаёт старую схему meta без `decision`.
- Скан прод-каталога WB (2026-07-27): 82 228 карточек, 359 885 размеров;
  мультибаркодных размеров 19 (0,005%), дублей баркода между nmID нет;
  `needKiz=true` у 91% — шлюз маркировки для GJ основной рабочий случай.
- Цепочка идентификаторов утверждена: мастер `баркод ↔ vendor_code` — ENSI
  PIM; `баркод → chrtID` — WB Content; WebApi не является зависимостью
  wbconnector ни в одном варианте (целевая схема 1С → WebApi → PIM → сервисы).
- Статусы OTS→OMS идут Kafka → Integration → OMS REST → Camunda, сепарация
  только в OTS по `source`; для `FBS_WB` обязателен явный source, плюс своя
  prefix policy вместо default `0000337` (для `FBS_WB` это `000370`).
  **Уточнение 2026-08-12:** отсечка делается не skip-листом в общем потоке, а
  отдельным топиком со вторым нотификатором — Integration в WB-потоке не
  участвует вовсе (`MP-WB-FBS-087`, `OPSLOG-3461-ots-implementation.md` §3.7).

## Resume pointer

См. progress tracker в [`00-PLAN.md`](00-PLAN.md). При продолжении сначала читать
`EVIDENCE-LEDGER.md`, затем брать не новый широкий поиск, а самый приоритетный
непроверенный runtime-gap с конкретным business key.

**Состояние на 2026-07-27 (Stage 20).** Контракт WB FBS снят со свежей спеки,
sandbox smoke пройден целиком (перенос заданий подтверждён фактом — дизайн
Stage 19 разблокирован), прод-каталог снят (мультибаркод 0,005%, `needKiz` у
91%), цепочка идентификаторов утверждена (PIM + WB Content, WebApi — не
зависимость), статусная цепочка OTS→OMS и отсечка `WB_FBS` подтверждены кодом.
В коде `platform-new/wbconnector`: миграция машины состояний `wb_supplies`,
клиент `wbapi` с контрактными тестами, снимок каталога в `dev/catalog/`.

Следующие шаги по коду: `clients/pim` + таблица `product_identifiers`
(отдельная задача; основа — `platform/ensi/packages/pim-client-php`),
обработчики outbox, логика волны.

**Уточнение 2026-08-11 (встреча с логистикой).** Значение source — **`FBS_WB`**
(не `WB_FBS`, как в Stage-документах; написание сопоставляется с именем элемента
enum, поэтому это контракт, а не оформление). Отгрузку объявляет склад: кнопка в
1С передаёт массив физически присутствующих заданий и синхронно получает id
поставки WB и её QR. Из этого следуют три правки, уже внесённые в
`platform-new/wbconnector` (`internal/shipping`): состав поставки приводится к
списку 1С, не попавшие в короба задания **переносятся в следующую поставку, а не
отменяются**, а маркировочный шлюз переехал на скан укладки — на доке задание уже
в заклеенном коробе на паллете, и вынуть его нереально. Подробности — Stage 19
§4.1, реестр `MP-WB-FBS-085/086`.

Следующие проверки (дешёвые, до спайка): prod-кабинет — пункты выдачи для
возвратов (шлюз 403), реальные `decision`-статусы и `isCancellable`, отзыв
токена со страницы `88508013`, выборка `api/Ref/IdMp` по пилотным SKU.

Далее по-прежнему актуален двухдневный technical spike Stage 16 на выделенной
WB-станции: official WB sticker и его физическая печать на целевом принтере,
companion scan-print с reprint, полный KM/GS со станции и OTS handover +
1С registry. Stage 17 добавляет обязательный marked-order walkthrough:
печать→PKS/ECOMAUFSTAT, `ОтборЛистПеремещ`→GJMarkUpdate,
WMS `GetCheckOrder`, `AUFSHPPAL`→1С status 50→`wms_shipment`→OTS
`DELIVERING` и поздний WB `deliver`.
Для numbering следующий артефакт — Redmine `#99027`, sanitized OMS
`client_order_id_template` и E2E boundary matrix вокруг Int32/10-digit limits.
