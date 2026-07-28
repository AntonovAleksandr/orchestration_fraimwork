# Stage 17 — WB FBS: 1С, паллеты и смена владельца КМ

**Дата среза:** 2026-07-24  
**Статус:** complete-for-current-pass  
**Покрытие:** текущие documentary contracts WMS→1С, локальные snapshots
1С/OTS, GJMarkUpdate и исторический warehouse SOP; без live walkthrough
выбранного ЛЦ и реального WB FBS-заказа  
**Назначение:** дополнить Stage 16 отсутствовавшими участниками и событиями:
`1С`, `ОтборЛистПеремещ`, WMS-native проверка смены владельца КМ,
формирование паллеты, штатная WMS-отгрузка, обработка результата в 1С и
поздний `deliver` WB  
**Уровни уверенности:** `confirmed`, `high`, `proxy`, `hypothesis`, `unknown`
в значениях из `00-PLAN.md`

## 0. Короткий вывод

В fast-track нужно различать четыре объекта и три разных сигнала после
физической отгрузки:

1. **Логическая поставка WB** — `wb_supply_id`, заранее создаётся Connector.
2. **Сборочное задание / GJ-заказ** — одна единица WB, исполняемая через
   OTS/WMS.
3. **Физическая паллета WMS** — `PalNam`, содержащая короба/заказы.
4. **Документы 1С** — `ОтборЛистПеремещ`, затем `Доставка` или
   `Перемещение` и связанный `Документ.Паллет`.

После штатной WMS-отгрузки нельзя употреблять одно неопределённое
«подтверждение внутренней отгрузки». Найдены три разных события:

1. `WMS.AUFSHPPAL` — бизнес-сигнал WMS→1С, что физическая паллета
   отгружена;
2. `IFOUTFSRSTA=50` — технический статус успешной обработки входящей
   WMS-транзакции в 1С;
3. `wms_shipment {orders,timestamp}` — бизнес-событие 1С→OTS после успешного
   проведения документов; в OTS оно становится `DELIVERING`.

Поставка WB не равна паллете WMS. QR WB относится к логической поставке, а не
к каждой паллете. Прямого поля `gj_order_id → pallet_id` в найденном
контракте нет; техническая связь восстанавливается косвенно:

```text
gj_order_id
  → WMS AufNr / AufWwsBeleg
  → ОтборЛистПеремещ.Товары.Заявка
  → короб TeNam
  → WMS.AUPSHP.PalNam
  → WMS.AUFSHPPAL.PalNam
  → 1С Документ.Паллет → короб → Доставка/Перемещение → заказ
```

Самые важные поправки к предыдущей схеме:

```text
скан DataMatrix
  → печать и наклейка официального WB-стикера
  → завершение упаковки
  → WMS PKS/PKSBST/PKSBSTMARK/PKSBSTABSCHL
  → 1С ОтборЛистПеремещ с заказом, коробом и КМ
  → GJMarkUpdate / УПД1 / смена владельца КМ

параллельный post-pack результат WMS
  → ECOMAUFSTAT/ECOMAUPSTAT/ECOMAUFSTATABSCHL
  → OTS ORDER_PICKUP + DataMatrix/serial

перед штатной отгрузкой
  → WMS сама вызывает GetCheckOrder по каждому заказу паллеты
  → false: штатная блокировка; true: разрешить отгрузку

штатная WMS-отгрузка
  → AUFSHP + AUPSHP с PalNam
  → AUFSHPPAL
  → 1С Доставка/Перемещение + Документ.Паллет
  → IFOUTFSRSTA=50
  → 1С wms_shipment
  → OTS DELIVERING
```

Повторного «зеркального» скана марки в Connector перед отгрузкой нет. Ранее
предложенный Connector dock preflight был ошибочным: проверка перехода права
марки уже является обязанностью WMS. Это подтверждено current API contract и
комментарием Анастасии Казковой; фактический UI/hard block выбранного ЛЦ ещё
нужно пройти вживую.

## 1. Что подтверждено в текущих контрактах

### 1.1. Регистрация заказа идёт параллельно в WMS и 1С

При текущем OTS export:

- в WMS уходит `WMS.ECOMAUF/ECOMAUP`;
- в 1С вызывается `EcommOrder/CreateOrder`;
- `OrderNr/OrderRefNr` содержат eCom order number;
- `OrderWwsBeleg` содержит 1С `idd_order`;
- registry 1С содержит order, sender/client, transport и
  `shipment_barcode`, но не `PalNam`.

Evidence:

- OTS `TgwWmsMapping.cs:103-176`;
- OTS `OneSService.cs:50-84`;
- OTS `RegRequest.cs:6-16`;
- Confluence `63468946`.

### 1.2. На рабочем месте: скан DataMatrix, печать, затем результат отбора

Уточнённый операционный порядок:

1. сотрудник выполняет **скан DataMatrix**;
2. после успешной локальной проверки печатает и наклеивает официальный
   WB-стикер и штатные внутренние формы;
3. закрывает упаковку;
4. после этого WMS формирует сообщения результата отбора.

Confluence `86314165`, v35 документирует именно результат отбора:

1. WMS отправляет `WMS.PKS`;
2. строки товара и короба приходят в `WMS.PKSBST`;
3. марки приходят в `WMS.PKSBSTMARK`;
4. завершение — `WMS.PKSBSTABSCHL`;
5. 1С по `AufWwsBeleg` находит eCom order и формирует
   `Документ.ОтборЛистПеремещ`;
6. ссылка на заказ сохраняется в `Товары.Заявка`, короб — в `Штрих`, марка —
   в табличной части марок.

Ключевые поля:

| Поле WMS | Роль в 1С |
|---|---|
| `AufNr` | номер WMS-заказа |
| `AufWwsBeleg` | поиск `ЗаказыКлиентов` / заявления-основания |
| `TeNam` | короб; для eCom документирован как номер заказа с дополнением до внутреннего формата |
| `AupNr` | ключ строки между отборочником и последующим движением |
| `ArtNr`, `BstMg` | товар и фактическое количество |
| `DataMatrix` | КМ в `ОтборЛистПеремещ.ТЧ.Марки` |

Это `confirmed` для contract/design и `high` для checked-in 1С model.
Фактический deployed handler выбранного ЛЦ ещё надо проверить.

Порядок «печать до PKS» зафиксирован как warehouse stakeholder evidence.
Найденные telegram contracts подтверждают состав PKS, но сами по себе не
доказывают момент печати.

### 1.3. WMS отдельно передаёт OTS статус и считанный DataMatrix

После завершения упаковки существует отдельная ветка WMS→OTS:

```text
WMS.ECOMAUFSTAT       — header, поле AufStatus
WMS.ECOMAUPSTAT       — строки заказа, поле DataMatrix
WMS.ECOMAUFSTATABSCHL — footer
```

В OTS `AufStatus=4` превращается в `ORDER_PICKUP`, а `DataMatrix` строки —
в `SerialNumber/good_id_mark`.

Термин **`IFStatus` здесь неверен**:

- бизнес-поле статуса заказа называется `AufStatus`;
- `IFOUTFSRSTA` — технический статус обработки telegram в интерфейсной
  таблице, а не состояние упаковки.

Current AS-IS `165410951`, v66 и локальный OTS показывают ещё одно важное
ограничение: из WMS в этой ветке приходит 13-символьный serial, а не
гарантированно полный КИЗ с GS и crypto tail. Для WB `meta/sgtin` остаётся
нужен full-KM enrichment через WebGJISMP.

PKS→1С и ECOMAUFSTAT→OTS — самостоятельные post-pack outputs WMS. В sequence
ниже они расположены в согласованном операционном порядке, но telegram
contracts не гарантируют причинный или строгий timestamp order между ними.
Если Connector будет зависеть от этого порядка, его нужно снять trace одного
реального заказа.

Local evidence:

- `TelegramTypes.cs:8-19`;
- `OrderStatusHeader.cs:3-10`;
- `OrderStatusRow.cs:3-15`;
- `TgwWmsMapping.cs:55-97,217-225`;
- `WmsStatusEventConsumer.cs:30-67`.

### 1.4. Смена владельца КМ запускается от `ОтборЛистПеремещ`

Для обычного eCom-заказа, кроме C&C, найден отдельный current marking route:

```text
1С ОтборЛистПеремещ (PLM)
  → GJMarkUpdate
  → WebGJISMP /api/SBIS/AddDoc
  → блокировка КМ
  → СБИС
  → ЦРПТ
  → обратные статусы
  → GJMarkUpdate
  → СтатусВыгрузки/GUID в 1С
```

Смысл PLM — УПД1 / `MOVE_STORES`: передача КМ от компании-владельца складского
остатка компании-продавцу интернет-заказа. В корпоративных документах это
исторически называется «ЗАО → АО», хотя актуальные юридические наименования
внутри mapping уже другие.

Evidence:

- Confluence `78755953`, v15;
- Confluence `118303811`, v30;
- Confluence `44256853`, v98;
- Jira `MWHNSK-1293`, `MWHNSK-2375`, `MWHNSK-6522`,
  `DEVLBL001-3087`.

Операция асинхронная. Скан DataMatrix, WB `meta/sgtin`, `deliver` и физическая
отгрузка сами по себе владельца КМ не меняют.

### 1.5. Перед отгрузкой WMS сама проверяет переход права марки

В current contract WMS синхронно вызывает по каждому заказу:

```http
GET /api/WH/GetCheckOrder?IDD={order_idd}
```

WebGJISMP находит КМ заказа и агрегирует результат проверки. Для online
ветки положительный ответ возможен только когда все КМ найдены, валидны,
верифицированы, разрешены к реализации, принадлежат требуемому владельцу и не
заблокированы/не проданы; для косметики дополнительно проверяется срок
годности.

Следствие для sequence:

- сотрудник **не сканирует DataMatrix второй раз** в Connector;
- Connector **не** читает owner status и не разрешает WMS-отгрузку;
- WMS проверяет право марки в своей штатной pallet/shipment операции;
- `false` должен удержать отгрузку, `true` разрешает продолжение.

Current sources подтверждают API и вычисление результата. Исторический
warehouse SOP `49752446`, v16 и Jira `MWHNSK-2387` подтверждают ожидаемый
hard-block: недоступность endpoint не позволяла отгрузить паллету. Точный
текущий экран и поведение выбранного ЛЦ остаются `high/proxy`, пока не
проведён live walkthrough.

Evidence:

- Confluence `165407793`, v34;
- Confluence `130131282`, v5;
- Jira `DEVLBL001-5905`, `DEVLBL001-5906`, `DEVLBL001-5923`;
- historical Confluence `49752446`, v16;
- historical runtime incident `MWHNSK-2387`.

### 1.6. Отгрузка паллеты — отдельный WMS→1С contract

WMS передаёт:

```text
WMS.AUFSHP          — header заказа/отгрузки
WMS.AUPSHP          — фактические строки, TeNam и PalNam
WMS.AUFSHPABSCHL    — завершение набора строк
WMS.AUFSHPPAL       — отдельное подтверждение отгрузки конкретной PalNam
```

Документы 1С создаются только после `WMS.AUFSHPPAL`.

По `ClickAndCollect`:

| Значение | Документ 1С |
|---|---|
| отсутствует | `Перемещение` + `Документ.Паллет` |
| `0` | `Доставка` + связанный `Документ.Паллет` |
| `1` или `2` | `Перемещение` + связанный `Документ.Паллет` |
| `3` | `Расходный ордер` + связанный `Документ.Паллет` |

Evidence:

- Confluence `97878157`, v86;
- Confluence `97879227`, v21;
- Jira `OPSLOG-2004`, `DEVLOG001-382`, `OPSLOG-2560`,
  `OPSLOG-2569`;
- 1С `ВзаимодействиеС_WMS/Ext/Module.bsl:218-246`.

`WMS.AUFSHPPAL` содержит только `PalNam`. Список заказов восстанавливается по
ранее полученным `WMS.AUPSHP` с той же `PalNam`.

### 1.7. Что значит «подтверждение внутренней отгрузки»

После `AUFSHPPAL` 1С должна выполнить бизнес-обработку:

1. сопоставить `AUFSHPPAL.PalNam` с ранее пришедшими `AUPSHP`;
2. создать и провести `Доставка`/`Перемещение` и `Документ.Паллет`;
3. при успехе перевести WMS-транзакции в `IFOUTFSRSTA=50`;
4. для eCom/C&C `0/1/2` опубликовать
   `wms_shipment {"orders":[...],"timestamp":"..."}`;
5. OTS оборачивает это событие в synthetic `WMS.AUFSHP` и переводит заказ в
   `DELIVERING`.

То есть:

| Сигнал | Что подтверждает | Можно ли считать финальным internal ack |
|---|---|---|
| `AUFSHPPAL` | WMS заявила физическую отгрузку паллеты | нет, документы 1С ещё могут не провести |
| `IFOUTFSRSTA=50` | конкретная входящая telegram-транзакция успешно обработана 1С | технически да для 1С, но Connector этот статус штатно не получает |
| `wms_shipment` / OTS `DELIVERING` | 1С успешно обработала shipment и уведомила OTS | лучший существующий внешний сигнал для Connector |

Отдельного business ack OTS→1С/WMS в найденном коде нет.

Критичный runtime-gap: свежая документация называет запуск внешней обработки
«Отгрузка паллет в машину из WMS (Перемещение и Доставка)» ручным и не
фиксирует расписание. Если это верно для выбранного ЛЦ, ждать OTS
`DELIVERING` перед WB `deliver` может быть слишком долго. До пилота нужно
проверить deployed EPF, способ запуска и фактическую latency.

Evidence:

- Confluence `60689538`, v81;
- Confluence `97878157`, v86;
- Confluence `97879227`, v21;
- 1С `ВзаимодействиеWMSСерверПолныеПрава/Ext/Module.bsl:279`;
- 1С `ВзаимодействиеС_WMS/Ext/Module.bsl:424,496`;
- OTS `OrderShimpentEventHandler.cs:17-61`;
- OTS `WmsStatusEventConsumer.cs:74-97`.

### 1.8. Заказ связан с паллетой через короб, а не прямым FK

В 1С `Документ.Паллет` хранит:

- `ИдПоставки`;
- `НомерПаллета`;
- `ШкПаллета`;
- документ-основание;
- список штрихкодов коробов.

Основанием строки паллеты является `Доставка`, `Перемещение` или
`РасходныйОрдер`, а не напрямую `ЗаказКлиента`.

Local evidence:

- `platform/1s8-enterprise/1c-lc/src/cf/Documents/Паллет.xml`;
- `.../Documents/ОтборЛистПеремещ.xml`;
- `.../CommonModules/ОбработкаДанныхИзТСД/Ext/Module.bsl`;
- `.../Documents/Доставка.xml`;
- `.../Documents/Перемещение.xml`.

В OTS pallet composition сейчас не возвращается:

- OTS DTO `WMS.AUFSHP` не содержит `PalNam`;
- обратное событие 1С→OTS содержит только список order IDs и timestamp;
- текущая 1С registry не содержит паллетных полей.

Следовательно, OTS нельзя считать master связи заказа с паллетой.

### 1.9. Куда передавать `wb_supply_id`

Для P0 master `wb_supply_id` остаётся Connector:

```text
wb_supply_id
  → supply_orders
  → wb_order_id
  → gj_order_id
```

Передавать supply ID в WMS для сборки не обязательно. WMS исполняет заказы,
формирует `PalNam` и самостоятельно проверяет марки перед отгрузкой. Для P0
можно открывать одну WB supply на dispatch window/рейс: тогда Connector не
нужна зеркальная pallet composition.

В `Документ.Паллет` уже есть поле `ИдПоставки`, поэтому после появления
документа его можно обогатить `wb_supply_id`. Но готовый WB FBS interface,
который это делает, не найден. Для P0 это полезный reconciliation field, а не
причина менять WMS contract.

Важно различать два WB-вызова:

1. `POST /api/v3/supplies` и add-order — **зарегистрировать/open supply** до
   складского отбора;
2. `PATCH .../deliver` — **передать уже зарегистрированную supply в
   доставку** после внутреннего shipment signal.

Каким именно shipment signal закрывать WB supply:

- предпочтительно OTS `DELIVERING`, если `wms_shipment` формируется
  автоматически и укладывается в cut-off;
- временно операционной командой дока после успешной штатной WMS-отгрузки,
  если обработка 1С ручная;
- не по `ORDER_PICKUP`: это только завершение упаковки, а не отгрузка.

Выбор между первыми двумя вариантами требует одного timestamp trace на
выбранном ЛЦ.

## 2. Смена владельца: две разные юридические ветки

### 2.1. Если eCom stock принадлежит компании складского контура

Для eCom найден маршрут:

```text
PLM / ОтборЛистПеремещ
  → MOVE / COMMISSION_UPD
  → MOVE_STORES
  → смена комиссионера/комитента
```

После фактической складской отгрузки текущий eCom route создаёт
`DO / Доставка`, по которому документирован отдельный `OUT / SALE` для
дистанционной продажи.

Для FBS нельзя автоматически считать `DO / OUT SALE` правильным actor/event:
кто выводит КМ — GJ или WB — должно быть подтверждено Legal/Marking для
конкретного договора и типа покупателя.

### 2.2. Если stock уже принадлежит АО

Тогда переход «ЗАО → АО» не требуется. Для складов/магазинов АО найден
отдельный marketplace route:

```text
1С Перемещение с единым номером поставки
  → GJMarkUpdateAO
  → MP / MOVE / NOACTION
  → смена внутренней принадлежности склад → маркетплейс
```

Страница прямо говорит, что изменения в ГИС МТ при этом не выполняются.

Evidence:

- Confluence `130124899`, v31;
- Confluence `130125049`, v12;
- Jira `DEVLBL001-4876`, `DEVLBL001-4884`, `DEVLBL001-4890`.

До выбора ЛЦ и юридического владельца остатка обе ветки нельзя смешивать в
одном target flow.

### 2.3. Почему нельзя переиспользовать historical WB batch вслепую

Для batch shipment WB найден другой маршрут:

```text
группа Перемещений по номеру поставки
  → MS / MOVE_STORES
  → приёмка WB
  → второй УПД по факту приёмки
```

Это FBO/batch-oriented процесс. Он не доказывает, что каждый WB FBS order
должен запускать `MS`, и не должен выполняться параллельно с eCom `PLM` для
того же КМ.

Evidence: Confluence `118293200`, `118295722`, `118296442`.

## 3. Исправленный end-to-end sequence

```mermaid
sequenceDiagram
    autonumber
    participant WB as "Wildberries API"
    participant C as "WB FBS Connector"
    participant O as "OTS"
    participant W as "WMS / ТСД"
    actor P as "Сборщик / упаковщик"
    participant S as "1С ЛЦ"
    participant M as "GJMarkUpdate / WebGJISMP / СБИС / ЦРПТ"
    actor D as "Док / логистика"

    C->>WB: "GET новые сборочные задания"
    C->>C: "wb_order_id ↔ gj_order_id"
    C->>O: "ON_VALIDATION: резерв"
    O-->>C: "reserve accepted"

    Note over C,WB: "Логическую поставку создаём заранее"
    C->>WB: "POST /api/v3/supplies или выбрать открытую"
    WB-->>C: "wb_supply_id"
    C->>WB: "add order to supply"
    WB-->>C: "new → confirm"
    C->>WB: "получить официальный WB-стикер"
    WB-->>C: "SVG/ZPL/PNG + barcode"

    C->>O: "WAIT_EXPORT_TO_WAREHOUSE"
    par "Текущая параллельная регистрация"
        O->>W: "WMS.ECOMAUF / ECOMAUP"
    and
        O->>S: "EcommOrder/CreateOrder"
    end

    P->>W: "скан DataMatrix"
    W-->>P: "локальная проверка пройдена"
    C-->>P: "официальный WB-стикер готов"
    W-->>P: "штатные внутренние формы GJ"
    P->>P: "напечатать и наклеить стикеры"
    P->>W: "закрыть упаковку"

    Note over W,O: "Два самостоятельных post-pack выхода; строгий технический порядок требует trace"
    W-->>S: "PKS + PKSBST + PKSBSTMARK + PKSBSTABSCHL"
    S->>S: "создать ОтборЛистПеремещ: заказ + короб + КМ"
    W-->>O: "ECOMAUFSTAT + ECOMAUPSTAT(DataMatrix) + footer"
    O->>O: "AufStatus=4 → ORDER_PICKUP; DataMatrix → serial"
    O-->>C: "ORDER_PICKUP + serial"

    Note over S,M: "Юридический обмен асинхронен; упаковщик его не ждёт"
    M->>S: "poll PLM / ОтборЛистПеремещ"
    S-->>M: "КМ и документ"
    M->>M: "MOVE_STORES / УПД1 / ЦРПТ"
    M-->>S: "СтатусВыгрузки / результат по КМ"

    O->>M: "получить полный КИЗ с GS/crypto tail [existing client, new WB_FBS gate]"
    M-->>O: "full KM"
    O-->>C: "ORDER_PICKUP + full KM [new Connector seam]"
    C->>WB: "PUT /api/v3/orders/{orderId}/meta/sgtin"
    C->>WB: "metadata readback"
    WB-->>C: "КИЗ сохранён"

    P->>W: "штатно привязать заказ/короб к PalNam"
    D->>W: "скан PalNam / команда штатной отгрузки"

    loop "Каждый заказ на паллете"
        W->>M: "GET /api/WH/GetCheckOrder?IDD={order_idd}"
        M-->>W: "true / false"
    end

    alt "Хотя бы по одному заказу false"
        W-->>D: "HOLD: переход права марки не подтверждён"
    else "WMS получила true по всем заказам"
        W->>W: "штатная отгрузка"
        W-->>S: "AUFSHP + AUPSHP(TeNam, PalNam) + ABSCHL"
        W-->>S: "AUFSHPPAL(PalNam)"
        S->>S: "Доставка/Перемещение + Документ.Паллет"
        S->>S: "успешная обработка → IFOUTFSRSTA=50"
        S-->>O: "wms_shipment {orders,timestamp}"
        O->>O: "synthetic AUFSHP → DELIVERING"
        O-->>C: "internal shipment signal: DELIVERING [new Connector seam]"

        Note over C,WB: "Если 1С event своевременен; иначе временная команда дока"
        C->>WB: "PATCH /api/v3/supplies/{supplyId}/deliver"
        WB-->>C: "confirm → complete"
        C->>WB: "GET /api/v3/supplies/{supplyId}/barcode"
        WB-->>C: "QR поставки"
        C-->>D: "QR: показать с телефона или распечатать 1 экземпляр"
        D->>WB: "машина + QR каждой WB-поставки"
    end
```

## 4. Где находится блокировка и кто ждёт

### Упаковщик

Не должен ждать:

- УПД1 и ЦРПТ;
- WB metadata readback;
- закрытия WB supply;
- формирования `Документ.Паллет`.

Он ждёт только текущую локальную проверку товара/КМ и печать.

### Паллетная/доковая операция

Здесь уже есть два разных барьера, и их нельзя склеивать.

```text
WMS hard gate:
  штатно сформирован состав паллеты
  + GetCheckOrder=true по каждому заказу
  = WMS разрешает штатную отгрузку

Connector supply gate:
  официальный WB-стикер получен
  + обязательный full KM принят WB
  + внутренний shipment signal получен
  + нет отменённого/ошибочного задания
  = Connector может вызвать WB deliver и получить QR поставки
```

WMS вызывает `GetCheckOrder` сама. Connector не должен зеркально сканировать
DataMatrix/`PalNam`, запрашивать owner status и давать сотруднику отдельное
разрешение на штатную WMS-отгрузку.

Историческая warehouse-страница `49752446`, v16 описывает тот же механизм:
WMS проверяет переход владельца всех КМ и запрещает отгрузку паллеты при
ошибке. Current contract `165407793`, v34 и `130131282`, v5 подтверждают
вызов и условия ответа; live UI выбранного ЛЦ ещё не проверен.

## 5. Минимальные доработки по системам

| Система | Что переиспользуется | Минимальный gap |
|---|---|---|
| WB FBS Connector | новый сервис | orders/supply/sticker/metadata, mapping `wb_supply_id ↔ wb_order_id ↔ gj_order_id`, idempotent `deliver`, QR |
| OTS | reserve, WMS export, 1С registry, WMS statuses, WebGJISMP client, `DELIVERING` | `WB_FBS` source/handover, full-KM callback, idempotency, signal Connector о `DELIVERING` |
| WMS | ECOM order, scan DataMatrix, PKS, ECOMAUFSTAT, упаковка, `PalNam`, `GetCheckOrder`, AUFSHP/AUFSHPPAL | для P0 без business-кода; проверить конфигурацию owner endpoint и точку печати |
| 1С ЛЦ | `ЗаказыКлиентов`, `ОтборЛистПеремещ`, `Доставка`, `Паллет`, КМ, `wms_shipment` | подтвердить WB route/`ClickAndCollect`, deployed EPF, автоматический запуск и latency до OTS |
| GJMarkUpdate | PLM/MOVE_STORES и обратные статусы | подтвердить, что WB_FBS PLM попадает в выборку и укладывается в SLA |
| Legal/Marking | действующие договоры и actor КМ | выбрать PLM или MP/MS; определить FBS withdrawal/cancel/return |

### Рекомендуемый P0

Чтобы не менять WMS:

1. один ЛЦ;
2. один seller и один юридический владелец stock;
3. одна логическая WB-поставка на dispatch window/машину;
4. одна единица WB = один GJ order = один физический package;
5. отдельный Connector scan-print для официального WB-стикера;
6. существующие PKS→1С, ECOMAUFSTAT→OTS, WMS `GetCheckOrder` и
   AUFSHP/AUFSHPPAL→1С;
7. Connector не знает `PalNam` и не дублирует маркировочный gate;
8. после OTS `DELIVERING` Connector вызывает WB `deliver` и показывает QR;
9. если deployed 1С processing пока ручной, для первого контролируемого
   прогона `deliver` запускается отдельной операционной командой дока, но не
   по `ORDER_PICKUP`.

Таким образом, из критического пути убираются WMS-доработка, зеркальный
скан и новый 1С→Connector API. Остаются проверка конфигурации существующих
контуров и маленький OTS→Connector shipment signal.

## 6. Критические решения до marked pilot

1. **Выбранный ЛЦ.** НСК и МСК имеют разные исторические варианты ожидания
   `AUFSHPPAL` и разные GJMarkUpdate instances.
2. **Владелец eCom stock.** Нужен ли PLM «Корпорация → АО» или stock уже АО.
3. **Один marking route.** Для одного КМ нельзя одновременно запускать eCom
   PLM и marketplace MS/MP.
4. **`ClickAndCollect`.** Для fast-track наиболее близок текущий eCom
   `ClickAndCollect=0 → Доставка`, но WB-specific contract ещё не утверждён.
5. **Вывод из оборота.** Нельзя автоматически перенести eCom `DO/OUT SALE`
   или historical WB batch УПД2 без решения Legal/Marking.
6. **WMS owner gate.** Проверить URL/сертификат/config switch
   `GetCheckOrder` и реальный `false/unavailable` hard-block выбранного ЛЦ.
7. **Обработка 1С.** Установить, запускается ли EPF вручную, по расписанию
   или event-driven; измерить время `AUFSHPPAL → IFOUTFSRSTA=50 →
   wms_shipment → OTS DELIVERING`.
8. **Событие для `deliver`.** Выбрать OTS `DELIVERING` или временную команду
   дока. `ORDER_PICKUP` использовать нельзя: товар ещё не отгружен.
9. **Pallet/supply grouping.** Для P0 одна supply на рейс снимает необходимость
   передавать `wb_supply_id` в WMS; для нескольких supplies правило
   физического разделения ещё должно быть согласовано.
10. **Недоступность WB API.** Определить, ждёт ли машина QR на доке и какой
    допустим timeout/retry.

## 7. Минимальный E2E walkthrough

Один маркированный заказ должен дать timestamps и IDs:

```text
wb_order_id
wb_supply_id
gj_order_id
1c_order_idd
WB sticker printed_at
PKS trxId
ОтборЛистПеремещ IDD
КМ + PLM status
ECOMAUFSTAT trxId / AufStatus
ECOMAUPSTAT DataMatrix
TeNam
PalNam
GetCheckOrder result_at
AUFSHP trxId
AUFSHPPAL trxId
Доставка/Перемещение IDD
Документ.Паллет IDD
IFOUTFSRSTA=50 at
wms_shipment published_at
OTS DELIVERING at
WB metadata accepted_at
WB deliver_at
WB QR received_at
```

Проверки:

1. После скана DataMatrix официальный WB-стикер печатается до завершения
   упаковки и отправки PKS.
2. PKS действительно создаёт PLM для WB_FBS order, а GJMarkUpdate подбирает
   его без ручного вмешательства.
3. ECOMAUFSTAT/ECOMAUPSTAT дают OTS `ORDER_PICKUP` и serial; фиксируется
   реальный порядок относительно PKS.
4. До штатной отгрузки WMS сама вызывает `GetCheckOrder`; отрицательный или
   недоступный ответ блокирует dispatch без повторного скана в Connector.
5. `AUPSHP.PalNam` связывается с тем же package/order.
6. `AUFSHPPAL` создаёт ровно один pallet document без потери других паллет.
7. 1С ставит успешным telegram status, публикует `wms_shipment`, OTS
   становится `DELIVERING`; фиксируется latency и способ запуска обработки.
8. WB `deliver` вызывается идемпотентно только по выбранному shipment signal.
9. QR относится к supply, а не ошибочно записывается как pallet label.

## 8. Уверенность и неизвестное

### Confirmed

- WMS PKS после отбора формирует в 1С `ОтборЛистПеремещ`;
- WMS отдельно отправляет `ECOMAUFSTAT/ECOMAUPSTAT`, где `AufStatus=4`
  становится OTS `ORDER_PICKUP`, а `DataMatrix` — serial марки;
- `AufWwsBeleg`, `TeNam`, `AupNr` и DataMatrix сохраняют order/box/mark
  identity;
- WMS имеет current contract прямого `GetCheckOrder` перед отгрузкой;
- WMS shipment передаёт `AUPSHP.PalNam`;
- документы отгрузки и `Документ.Паллет` создаются после `AUFSHPPAL`;
- после успешной 1С-обработки публикуется `wms_shipment`, который превращается
  в OTS `DELIVERING`;
- PLM является отдельным асинхронным owner-change route;
- OTS и initial 1С registry сейчас не содержат pallet composition;
- WB supply создаётся рано, а `deliver` и QR выполняются поздно.

### High

- owner gate должен выполняться WMS без зеркального скана Connector;
- отрицательный/недоступный `GetCheckOrder` блокирует штатную отгрузку;
- `wb_supply_id` и `PalNam` должны оставаться разными сущностями.

### Proxy

- текущий UI WMS показывает сотруднику hard-block по owner-change status;
- текущий сотрудник сканирует order, затем pallet exactly as described in
  `49752446`.

### Hypothesis

- OTS `DELIVERING` можно использовать как автоматический trigger WB `deliver`,
  если 1С-обработка запускается своевременно;
- одна WB supply на dispatch window/рейс позволит не передавать pallet
  composition в Connector для P0.

### Unknown

- deployed versions выбранного WMS/1С/GJMarkUpdate;
- точный технический порядок PKS и ECOMAUFSTAT после печати;
- deployed EPF, режим её запуска и latency до `wms_shipment`;
- фактический owner eCom stock;
- FBS-specific `ClickAndCollect`, recipient and transport master data;
- корректный FBS withdrawal/return route;
- реальная latency УПД1/ЦРПТ относительно cut-off WB;
- можно ли штатно перепаллетировать заказ после ошибки.

## 9. Источники

### GJ documentary

- Confluence `86314165`, v35 — WMS→1С результат отбора, PKS и
  `ОтборЛистПеремещ`;
- Confluence `44256853`, v98 — модель `ОтборЛистПеремещ` и КМ;
- Confluence `78755953`, v15 — PLM / owner change eCom;
- Confluence `118303811`, v30 — current GJMarkUpdate document matrix;
- Confluence `165407793`, v34 — current pick/pack и WMS
  `GetCheckOrder`;
- Confluence `130131282`, v5 — contract и aggregate result
  `GetCheckOrder`;
- Confluence `165410951`, v66 — current AS-IS WMS→OTS, serial против полного
  КИЗ;
- Confluence `60689538`, v81 — WMS→1С shipment processing и статусы;
- Confluence `97878157`, v86 — WMS pallet shipment;
- Confluence `97879227`, v21 — `AUFSHPPAL` и `Документ.Паллет`;
- Confluence `108052092`, v28 — TSD pallet formation/reformation;
- Confluence `49752446`, v16 — historical order→pallet и owner gate;
- Confluence `130124899`, v31 и `130125049`, v12 — stock already owned by
  AO;
- Confluence `118293200`, `118295722`, `118296442` — historical WB batch
  marking;
- Jira `DEVLBL001-5905`, `DEVLBL001-5906`, `DEVLBL001-5923`,
  `MWHNSK-2387`;
- Jira `OPSLOG-2004`, `OPSLOG-2560`, `OPSLOG-2569`,
  `DEVLOG001-382`, `DEVLBL001-4876`, `DEVLBL001-4884`,
  `DEVLBL001-4890`.

### Local snapshots

- `platform/gloriaots/gloriaots`;
- `platform/1s8-enterprise/1c-lc`;
- Stage 14 — order identity;
- Stage 15 — WB API/supply/KM lifecycle;
- Stage 16 — OTS/WMS fast-track.

## 10. Resume pointer

Следующий шаг — не расширять схему теоретически, а провести один marked-order
walkthrough на выбранном ЛЦ. В одном trace нужны печать→PKS→ECOMAUFSTAT,
PLM→`GetCheckOrder`, AUFSHP/AUFSHPPAL→1С status 50→`wms_shipment`→OTS
`DELIVERING`. До него режим 1С-обработки, `PLM vs MP/MS`, `ClickAndCollect`,
FBS withdrawal и реальный WMS hard gate остаются blocking решениями.
