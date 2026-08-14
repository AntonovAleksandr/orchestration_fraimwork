# OPSLOG-3461 — доработки Gloria OTS под WB FBS: рабочая постановка

**Задача:** [OPSLOG-3461](https://jira.gloria-jeans.ru/browse/OPSLOG-3461) «FBS WB_доработки ОТС»,
постановщик — Казакова А. И., исполнитель — Закомирный А. В.
**Дата документа:** 2026-08-12, актуализирован 2026-08-13
**Код:** `platform/gloriaots/gloriaots`. Якоря `file:line` даны по срезу ветки
`release` на `d1c513a0` — до наших правок, чтобы ссылки описывали исходное
состояние. Сами правки лежат в ветке `OPSLOG-3461`, коммит `0e5aa78e` (§0)
**Связанные документы:**
- `OTS-CHANGES-WB-FBS.md` — требования к OTS со стороны e-commerce (что и зачем);
  этот документ — реализация под конкретный тикет (где и как)
- `stage-16-wb-fbs-fast-track-current-warehouse.md` — быстрый путь через текущий
  склад, `stage-19-…-supply-lifecycle-design.md` — жизненный цикл поставки
- ADR по номеру заказа — `docs/architecture/2026-07-31-adr-wb-fbs-order-id.md`

**Зачем документ.** Постановка в Jira написана со стороны логистики и в терминах
1С/мастер-данных. Здесь она переведена в термины кода, дополнена тем, что из неё
выпало, и очищена от одной формулировки, которая при буквальном исполнении ломает
поток. Читать перед началом работ; расхождения из §2 согласовать с постановщиком.

## 0. Состояние работ на 2026-08-13

Код OTS — ветка `OPSLOG-3461`, один коммит `0e5aa78e`, **не запушен и не
задеплоен**. Сборка проходит. Ниже — что уже закрыто и чем это проверять.

**Сделано в базе** (прогнано на `Ordering`, `OrderingStage`, `GloriaOTS`):
скрипты `Database/DDL/35` (таблицы остатков и резервов) и `36` (процедура
резерва). Строка ТК в `dbo.Carrier` — `Id = '10'`, `warehouse_id = '9148'` —
заведена руками на всех трёх контурах.

**Сделано в коде:**

| Блок | Что именно |
|---|---|
| склад | `ONES_MSK_WB = 3` в `WarehouseType`, номер `9148` и ИДД `…229` во всех маппингах, часовой пояс МСК |
| остатки | третья ветка в `UpsertStockBatch`, `Stocks_ONES_MSK_WB` в `UNION` джоба `Goods`, ветка в `BalanceContext.GetBalanceByWarehouse` |
| ТК | `WILDBERRIES = 10`, оба маппинга, `WbFbsShipmentService`, регистрация в DI, четыре ветки в фасаде V1 |
| источник | `OrderSource.FBS_WB = 5`; числа в обоих перечислениях зафиксированы явно |
| 1С | префикс `0000370`, `idd_sender` = `MSK_LC_WB`, `idd_client` = `MSK_WB`, слаг `MSK_WB` |
| WmsSync | инстанс МСК обслуживает оба склада (`ServedWarehouseIds`), регистрация `IWmsService` |
| резерв | снятие при завершении ВБ-заказа (Р12) |
| статусы | `WbFbsOrderStatusNotifier` в отдельный топик, ключ = номер заказа; топики в `appsettings` |

**Ждёт людей, не нас:**

- правка текста пункта 3 в Jira: сделано «пустым шагом», а не пропуском
  статусов (В1);
- решение по `BalanceMoves` (Р8) — завести пустой ради буквы задачи или снять;
- топики и права в Kafka от DevOps (В10).

**Не начато:** консьюмер статусов в `wbconnector` отдельным `cmd`; отправка
`COMPLETED` из коннектора в OTS (без неё резерв не снимется); опрос остатка
коннектором и отправка в WB.

## 1. Что задача дала как исходные данные

Это те значения, которых нам не хватало для дизайна (`OTS-CHANGES-WB-FBS.md` §6,
открытые вопросы). Все — из тела задачи и из обновлённых страниц Confluence.

| Сущность | Значение | Источник |
|---|---|---|
| Код склада в OTS | `9148` | тело задачи |
| ИДД склада-отправителя (Москва ЛЦ ВБ) | `00005550031258229` | тело задачи; [63468416](https://confluence.gloria-jeans.ru/pages/viewpage.action?pageId=63468416) v35 |
| ИДД склада-получателя (м-н МСК WB FBS) | `00005550031258273` | там же |
| id новой ТК | `transport_id = 10` | тело задачи |
| Префикс 1С для нового source | `000370` (Hybris `000337`, Starfish `000352`) | [63468416](https://confluence.gloria-jeans.ru/pages/viewpage.action?pageId=63468416) v35 |
| Написание source | `FBS_WB` | там же; совпадает с договорённостью с логистикой от 2026-08-11 (`MP-WB-FBS-085`) |

**Следствие для WB Connector.** В OTS уходит `business_unit_id = "00005550031258229"`:
вход `/v2` читает это поле и переводит его в числовой склад
(`OrderController.cs:178-179`), поэтому отдельного `id_warehouse` слать не нужно.
Значение — в конфигурацию коннектора (`OTS_WAREHOUSE_MAP`).

## 2. Расхождения — зафиксировано

| # | Что | Статус | Суть |
|---|---|---|---|
| Р1 | Пункт 3 задачи называет не те статусы | **закрыто 2026-08-12: подтверждено постановщиком** | «пропускать регистрацию в ТК (статусы `ORDER_REGISTER_WAREHOUSE` и `ORDER_REGISTERED_WAREHOUSE`)». Регистрация в ТК — это `ORDER_REGISTER_TRANSPORT`/`ORDER_REGISTERED_TRANSPORT` (`OrderStatus.cs:22-23`), а `*_WAREHOUSE` — передача заказа **на склад** (`OrderStatus.cs:29-30`). Пропустить второе значит не отдать заказ в WMS, что противоречит пункту 5 той же задачи. Казакова А. И. подтвердила: имелся в виду транспорт, в постановку скопирована не та строка статусной схемы. Текст задачи в Jira поправить, реализация — по §3.4 |
| Р2 | Публикация статусов `FBS_WB` наружу | **пропущено в задаче, включено в объём; способ выбран 2026-08-12** | Нотификатор отсекает всё, кроме Starfish (`StarfishOrderStatusNotifier.cs:36`), для нового source вернёт `null`. Без этого WB Connector не увидит `PICKING`/`ORDER_PICKUP`/`SUSPENDED`, то есть не привяжет КИЗ и не обработает недобор. Делаем **отдельным топиком** и вторым нотификатором, а не расширением екомовского условия — Integration тогда не трогаем совсем (§3.7) |
| Р3 | Растущий бэклог необработанных событий | **следствие Р2, эксплуатационный риск** | skip-лист — `SPL/Unknown/ORDER_FROM_SPL/Hybris` (`OrderLaterNotificationService.cs:50-53`); `FBS_WB` в него не попадает, а при `null` от нотификатора `Notificated` не проставляется (`:69-72`). Событие перечитывается каждым проходом бесконечно |
| Р4 | Элемент `OrderSource.FBS_WB` и его ordinal | **подразумевается пунктом 4; после решения по §3.7 — гигиена, а не риск** | У `OrderSource` значения не заданы явно (`OrderSource.cs`), а в Kafka source уезжает числовым ordinal (`MP-WB-FBS-080`). Добавлять **только в конец**; заодно проставить числа всему enum. С отдельным топиком (§3.7) маршрутизация на ordinal больше не опирается, поэтому ошибка здесь ломает не разбор у нас, а трактовку истории и существующих консюмеров |
| Р5 | Наполнение справочника `Goods` по новому складу | **пропущено в задаче** | Джоб ищет неизвестные штрихкоды `UNION`'ом ровно по двум таблицам (`SyncStockGoodsWithRefernces.cs:37-39`). Товар, который есть только на ВБ-складе, в `Goods` не попадёт, а оттуда берутся `descr`/`article`/`nds`/`idd` при обогащении заказа |
| Р6 | Деплой `WmsSync` под новый склад | **пропущено в задаче** | `WmsSync` — процесс на один склад: slug читается из env и биндится в статику (`WarehouseDefaults.InitializeDefaults`, `Program.cs:104-110`). Один инстанс не может обслуживать два склада |
| Р7 | Имя элемента enum ломает сложившееся именование | **принимаем как есть, зафиксировать** | Существующие — `ONES_MOSCOW`/`ONES_NOVOSIBIRSK`, задача просит таблицы `*_ONES_MSK_WB`. Имя таблицы интерполируется из enum (см. §3.2), поэтому элемент обязан называться `ONES_MSK_WB` |
| Р9 | Процедура резерва `Do_Reserve_<склад>` для нового склада | **пропущено в задаче; блокирует пилот целиком** | Резерв делается процедурой на склад: `_connection.QueryAsync<Reserve>(sql: $"Do_Reserve_{warehouseType}", …)` (`BalanceRepository.cs:278-282`). Процедуры созданы EF-миграцией по **захардкоженному списку трёх складов** (`20231019090335_AddBalanceTypesAndFuncs.cs:27-32`), которая давно применена. Без `Do_Reserve_ONES_MSK_WB` первый же `Reserve` от коннектора упадёт на «не найдена процедура» — то есть задача 1 (три таблицы) закрывает не весь минимум по складу |
| Р10 | Резерв не обновляет `BalanceActionTimestamp` | **защита «на всякий случай», не блокер** (уточнено 2026-08-13, см. §3.3) | `UpsertStockBatch` при движении от 1С обновляет watermark (`BalanceRepository.cs:106-116`), снятие резерва — тоже (`CancelReservesAsync`, `:294`), а вот **создание** резерва внутри `Do_Reserve_*` только вставляет строку в `Reserves_*` и watermark не трогает (`20231019090335_…cs:36-56`). Выборка «что изменилось с момента X» пропускает уменьшение свободного остатка от покупки, но неверное число в WB от этого не уезжает — разбор в §3.3. Правку в процедуру **не вносим**: watermark лежит в общей на все склады `GoodBalances`, и наш резерв засветил бы товар в инкрементальной выборке екома (§3.2) |
| Р8 | `BalanceMoves_*` в коде не используется | **закрыто 2026-08-13: таблица не нужна** (§3.2) | В C# нет ни одного обращения к `BalanceMoves`, процедура резерва её не пишет, у последнего добавленного склада BetaPro такой таблицы не создавали |
| Р12 | Резерв по ВБ-заказу не снимался при завершении | **исправлено 2026-08-13** | `ORDER_TO_PICKING/Completed` снимал резерв только для самовывоза, для остальных транспортов сразу `return null`. Общий путь (`OrderTrackingService.cs:613-640`) снимает резерв на `DELIVERING/COMPLETED/LOST/CANCELLED`, но наш `GetOrderStatus` отвечает `ORDER_SPLIT`, которого в списке нет. То есть резерв висел бы вечно, свободный остаток уезжал вниз, в WB уехали бы нули. Добавили `WILDBERRIES` рядом с `OWN`; `COMPLETED` присылает коннектор по статусу от WB |
| Р13 | Полная сверка остатка не покрывает склад 9148 | **известное ограничение, не блокер** | `StockSyncRequestedConsumer` публикует под основным складом инстанса (`WarehouseDefaults.WarehouseId`), поэтому полная сверка охватит только `6003`. Инкрементальные события от 1С несут свой `id_warehouse` и работают для обоих складов. Полная сверка — механизм лечения расхождений, понадобится, когда дойдём до сверки с WB |
| Р14 | Запись ТК в справочнике `Carrier` — не данные из задачи, а условие приёма заказа | **закрыто 2026-08-13** | `HandlersValidator.ValidateTransport` ищет перевозчика по паре «транспорт + склад» и без строки отвечает `UnknownDeliveryID`. Строка заведена вручную на трёх контурах. Первую строку новому складу нельзя создать из админки: список складов в форме собирается из существующих записей `Carrier`. Дальше склад появляется в списке и поддержка работает обычным путём |
| Р11 | Снапшот модели OrderContext разошёлся с конфигурацией сущностей | **чужой дрейф, блокирует EF-путь для нас** (проверено 2026-08-13) | `dotnet ef migrations add` в этом контексте генерирует не нашу правку, а накопленные чужие изменения: обрезание `nvarchar(max)` → `nvarchar(60…3000)` по 16 колонкам `Pointouts` (EF сам предупреждает о потере данных) и индекс + каскадный `FK_GoodsStatus_Goods_GoodsId`. Пустую миграцию с одним `Sql(...)` получить нельзя, поэтому процедуру доставляем DDL-скриптом (§3.2). Отдельно: `wms.__EFMigrationsHistory` содержит одну запись из трёх миграций контекста, то есть `database update --context WmsDbContext` тоже нерабочий |

## 3. Постановка по работам

### 3.1. Мастер-данные склада — основание для всего остального

Без этого шага падают и приём заказа, и приём остатка. `WarehouseTypeHelper`
(`ApplicationCore/Constants/WarehouseTypeHelper.cs`) — единственная точка
трансляции между кодом склада, ИДД и типом.

Что добавить:

1. `WarehouseType.ONES_MSK_WB` — **в конец enum** (сейчас последний `SDT_3PL`).
   Значения не заданы явно, поэтому вставка в середину сдвинет ordinal'ы, а они
   пишутся в `OrderTrackingParams.WAREHOUSE_TYPE` как int
   (`OrderRegisterTransport.cs:82`) — то есть уже лежат в базе.
2. `ToWarehouseId`: `ONES_MSK_WB => "9148"`.
3. `FromId(string)`: и `"9148"`, и `"00005550031258229"` → `ONES_MSK_WB`
   (в существующих кейсах приняты оба вида ключа).
4. `FromOldToNewWarehouse`: `"9148" => "00005550031258229"`.
5. `FromNewToOldWarehouse`: `"00005550031258229" => "9148"`.
   **Обе стороны обязательны:** прямая нужна на входе `/v2`
   (`OrderController.cs:179`), обратная — на формировании ответа (`:181`), иначе
   запрос обработается, а ответ упадёт.
6. `VALID_WAREHOUSE_ID_LIST`: добавить `9148`. Список проверяет приём заказа
   (`OTSOrderValidator.cs:17`) и параметры баланса
   (`OtsBalanceParamsV2Validator.cs:19`). Пока 9148 там нет, `Reserve` от
   коннектора будет отклонён.
7. `WarehouseTypeTimeZoneHelper.GetWarehouseTimeZone`: `ONES_MSK_WB => МСК`.
   Формально `default` вернёт UTC и ошибки не будет, но расчёт времени отгрузки
   уедет на три часа.

Все неохваченные ветки в этих хелперах бросают `NotSupportedException` — то есть
пропущенный кейс проявится исключением, а не тихим неверным поведением. Это
хорошо, но означает, что шаг 3.1 нужно делать целиком, а не по частям.

### 3.2. Таблицы остатков, резервов и движений

**Контракт именования.** Имена таблиц не константы — они интерполируются из
значения enum:

`src/GloriaOTS.Infrastructure/Persistence/BalanceRepository/BalanceRepository.cs:158-163`

```csharp
        var query = $@"select * from GoodBalances {nameof(GoodBalance)}
                left join Stocks_{warehouseType} as {nameof(Stock)}
                on {nameof(GoodBalance)}.{nameof(GoodBalance.Id)} = {nameof(Stock)}.{nameof(Stock.Id)}
                left join Reserves_{warehouseType} as {nameof(Reserve)}
                on {nameof(GoodBalance)}.{nameof(GoodBalance.Id)} = {nameof(Reserve)}.{nameof(Reserve.GoodID)} {orderPart}
                where {nameof(GoodBalance)}.{nameof(GoodBalance.Id)} = @GoodId";
```

Отсюда жёсткое требование: **имя элемента enum побуквенно равно суффиксу имён
таблиц**. `ONES_MSK_WB` → `Stocks_ONES_MSK_WB`, `Reserves_ONES_MSK_WB`,
`BalanceMoves_ONES_MSK_WB`. Рассогласование даст ошибку не при сборке, а на
первом запросе к несуществующей таблице.

**Кто владеет схемой.** Эти таблицы **не** отображены в EF (в
`Persistence/Config/` их нет, доступ идёт через Dapper), поэтому создаются не
EF-миграцией, а скриптом развёртывания рядом с существующими —
`Database/SqlDeploy/tables/`.

**Осторожно: файлы в `SqlDeploy/tables/` устарели и копировать их нельзя.**
Там у `Stocks_ONES_MOSCOW.Id` до сих пор `nvarchar(450)`, а фактически колонка
переведена в `bigint` скриптом `Database/DDL/9-UpdateGoodsIdsTypeForWholeDB.sql`
(строки 37-47) вместе с `GoodBalances.Id`, `Reserves.GoodID` и `Goods.Barcode`.
Тем же скриптом сняты все FK на `GoodBalances` и не возвращены. Ещё две правки
мимо `SqlDeploy`: `Timestamp` в резервах (`DDL/10`) и `OrderId bigint`
(`DDL/13`). Скопируешь московский файл — получишь склад с типами, расходящимися
с остальными, и неявные приведения в каждом join.

**Эталон — самый свежий добавленный склад BetaPro** (`DDL/30`, `DDL/31`): он
заводился уже после смены типов, поэтому отражает актуальную форму. Берём её:

```sql
CREATE TABLE [dbo].[Stocks_ONES_MSK_WB](
    [Id] [bigint] NOT NULL,
    [Qty] [decimal](18, 2) NOT NULL,
    [Timestamp] [datetime2](7) NOT NULL,
    CONSTRAINT [PK_Stocks_ONES_MSK_WB] PRIMARY KEY CLUSTERED ([Id] ASC)
);

ALTER TABLE [dbo].[Stocks_ONES_MSK_WB]
    ADD DEFAULT ('0001-01-01T00:00:00.0000000') FOR [Timestamp];

CREATE TABLE [dbo].[Reserves_ONES_MSK_WB](
    [Id] [int] IDENTITY(1,1) NOT NULL,
    [GoodID] [bigint] NOT NULL,
    [Qty] [decimal](18, 2) NOT NULL,
    [ReserveEventId] [uniqueidentifier] NOT NULL,
    [OrderID] [bigint] NOT NULL,
    [Timestamp] [datetime2] NOT NULL DEFAULT (GETDATE()),
    CONSTRAINT [PK_Reserves_ONES_MSK_WB] PRIMARY KEY CLUSTERED ([Id] ASC)
);

CREATE NONCLUSTERED INDEX [IX_Reserves_ONES_MSK_WB_GoodID]
    ON [dbo].[Reserves_ONES_MSK_WB] ([GoodID]);
```

Сделано скриптом `Database/DDL/35-AddWbFbsWarehouseBalanceTables.sql` — там же,
где заводили BetaPro, и в стиле последнего скрипта каталога (охранные проверки и
`PRINT`, чтобы повторный прогон был безопасен). В `SqlDeploy/tables/` файл не
добавляем: у BetaPro его тоже нет, и половинчато верный каталог хуже явно
устаревшего (В14).

Состав колонок диктует не аналогия, а тело процедуры резерва: она пишет
`INSERT INTO Reserves_{warehouse}(GoodID, Qty, ReserveEventId, OrderID, Timestamp)`
и джойнит `Stocks_{warehouse} s on p.GoodID = s.Id` при `GoodID bigint` в TVP.
Отсюда обязательны все пять колонок и `bigint` в обоих местах.

**`BalanceMoves_ONES_MSK_WB` не нужна** — это закрывает Р8/В6 без запроса
постановщику. Процедура резерва её не трогает, обращений к `BalanceMoves` в
коде нет, и у BetaPro такой таблицы не создавали вообще. Если нужно формальное
соответствие тексту задачи — таблицу можно завести пустой, вреда нет, но в
работе она участвовать не будет.

**Индекс по `OrderID`** (снятие резерва идёт `delete ... where OrderID = @OrderId`)
ни на одном складе не заведён. Для 20 000 заданий в сутки с высокой долей отмен
его стоит добавить, но это осознанное отличие от остальных складов — вынести в
MR отдельным пунктом, а не протащить молча.

**Процедура пакетного обновления — живёт в C#, а не в базе.** Единственное место
с хардкодом складов — `UpsertStockBatch`, и она пересоздаётся при старте
приложения из строковой константы:

`src/GloriaOTS.Infrastructure/Persistence/BalanceRepository/BalanceRepository.cs:121-137`

```csharp
    public async Task InitializeAsync()
    {
        if (_initialized) return;

        using var connection = new SqlConnection(_connectionString);

        await connection.OpenAsync();

        var transaction = await connection.BeginTransactionAsync();

        await connection.ExecuteAsync(_createStockParam_TVP, commandType: CommandType.Text, transaction: transaction);
        await connection.ExecuteAsync(_createUpsertStockBatchProcedure, commandType: CommandType.Text, transaction: transaction);

        await transaction.CommitAsync();

        _initialized = true;
    }
```

Значит третью ветку добавляем в константу `_createUpsertStockBatchProcedure`
(`BalanceRepository.cs:56-119`), по образцу `IF @WarehouseName = 'ONES_MOSCOW'`,
и она задеплоится сама при перезапуске. Отдельного скрипта на процедуру не
нужно, а вручную правленная в базе процедура будет перетёрта при следующем
старте — учитывать при хотфиксах.

Параметр приходит из enum: `parameters.Add("@WarehouseName", warehouseType.ToString(), …)`
(`BalanceRepository.cs:302`), то есть значение строки в `IF` — снова имя элемента.

**Полный перечень объектов «на склад».** Собран сплошным поиском интерполяций
имён по складу в C#, чтобы не искать пропущенное по частям:

| Объект | Тип | Кто создаёт | Есть в задаче |
|---|---|---|---|
| `Stocks_<WH>` | таблица | скрипт `Database/SqlDeploy/tables/` | да |
| `Reserves_<WH>` | таблица | там же | да |
| `BalanceMoves_<WH>` | таблица | там же | да, но в коде не используется (Р8) |
| `Do_Reserve_<WH>` | **процедура** | EF-миграция по списку складов | **нет** (Р9) |
| `UpsertStockBatch` | процедура, общая | `CREATE OR ALTER` из C# при старте | нет, но нужна ветка на склад |

Больше объектов, зависящих от имени склада, в коде нет: `ReserveParam_TVP` и
`StockParam_TVP` общие, остальное работает через интерполяцию имён этих пяти.

**Как это попадает в базу — три разных механизма, автоприменения нет ни у одного.**
`README.md:462`: «Автомиграции основной БД при старте не выполняются. Базу нужно
подготовить отдельно». Проверено и по коду: вызовов `Database.Migrate()` в
приложении нет, в `.gitlab-ci.yml` шагов развёртывания схемы тоже нет.

| Объект | Механизм | Что делаем мы |
|---|---|---|
| таблицы | `Database/SqlDeploy/tables/` — декларативный проект MSBuild.Sdk.SqlProj | добавляем три `.sql` + отдаём DDL на применение |
| `Do_Reserve_<WH>` | EF-миграция (`Persistence/Migrations/`), 18 штук, последняя 05.2025 | DDL-скрипт 36 — новую миграцию сделать нельзя, см. ниже |
| `UpsertStockBatch` | `CREATE OR ALTER` из C# при старте приложения | только код, применится само |

**Состояние истории миграций (снято 2026-08-13 со всех трёх баз).**
Одна таблица `__EFMigrationsHistory` обслуживает несколько контекстов, отсюда
четыре записи `_Initial`. По основному контексту (OrderContext, схема `dbo` —
именно туда идёт процедура резерва) **все три контура совпадают**: последняя
применённая — `20250522185912_AddGoodsIndecies`. Значит скрипт по нашей миграции
получается один и тот же для дева, стейджа и прода.

**Таблиц истории больше одной, и это меняет чтение.** У WmsDbContext она своя:
`DependencyInjectionExtensions.cs:43` задаёт
`MigrationsHistoryTable(HistoryRepository.DefaultTableName, "wms")`, и выгруженный
скрипт пишет в `[wms].[__EFMigrationsHistory]`. Остальные контексты, включая наш
OrderContext, пользуются `dbo.__EFMigrationsHistory`. Поэтому «миграции нет в
истории» надо проверять в таблице **того** контекста. Побочный эффект: две ранние
миграции WmsDb (`WmsDbContextImproves`, `AddDeliveringEventsTable`) лежат в `dbo`
— они применялись до появления этой настройки, так что история контекста
расползлась по двум таблицам.

С учётом этого из двух «пропавших» миграций расхождение остаётся одно:

| Миграция | Контекст | Где искать запись | Состояние |
|---|---|---|---|
| `20250818114956_AddActiveFromColumn` | WmsDb | `wms.__EFMigrationsHistory` | в `dbo` её и не должно быть — не расхождение |
| `20260121091719_AddDpdState` | Dpd | `dbo.__EFMigrationsHistory` | на проде записи нет, а колонка `dpd.StatesHistory.Code` есть |

**Риск для чужого релиза DPD.** Скрипт
`MicroContexts/Migrations/Dpd/AddDpdState.sql` выгружен в idempotent-виде: каждый
шаг обёрнут в `IF NOT EXISTS (SELECT * FROM [__EFMigrationsHistory] WHERE
MigrationId = …)`. На проде записи нет, условие истинно — и скрипт выполнит
`ALTER TABLE [dpd].[StatesHistory] ADD [Code] int NOT NULL DEFAULT 0` по уже
существующей колонке. Ошибка 2705, откат транзакции вместе с предшествующим
`DROP INDEX`; данные не пострадают, но шаг релиза упадёт. Не наша задача,
владельцу DPD сказать стоит.

Отсюда правило для нас: **`dotnet ef database update` вслепую не запускаем**.

**Вторая мина, симметричная первой: WmsDb невозможно обновить через EF.** В
`wms.__EFMigrationsHistory` лежит **одна** запись (`AddActiveFromColumn`), а
миграций у контекста три — две ранние отмечены в `dbo`. EF смотрит только в
таблицу своего контекста, поэтому `database update --context WmsDbContext` сочтёт
`WmsDbContextImproves` и `AddDeliveringEventsTable` неприменёнными и попробует
создать уже существующие таблицы. Лечится переносом двух строк в `wms`-таблицу.
Не наша задача, но знать полезно: EF-путь в этом репозитории местами нерабочий.

**Почему процедуру всё-таки делаем DDL-скриптом, а не EF-миграцией
(проверено 2026-08-13).** Попытка сделать правильно провалилась по внешней
причине. `dotnet ef migrations add` в контексте OrderContext собирается и
проходит, но в миграцию попадает **не наша правка, а чужой незакоммиченный дрейф
модели**: конфигурация сущностей ушла вперёд снапшота. EF нагенерировал
обрезание `nvarchar(max)` до `nvarchar(60…3000)` по шестнадцати колонкам
`Pointouts` (на что сам ответил предупреждением «may result in the loss of
data») и добавление индекса плюс каскадного `FK_GoodsStatus_Goods_GoodsId`.
Пустой миграции с одним `migrationBuilder.Sql(...)` в этом контексте получить
нельзя, пока дрейф не закрыт отдельной чужой миграцией.

Вывод: пока снапшот OrderContext не приведён в соответствие с моделью, любая
новая миграция в этом контексте несёт чужие изменения схемы, часть из них
разрушающие. Поэтому процедура доставляется скриптом
`36-AddDoReserveProcedureForWbFbsWarehouse.sql`, а расхождение выносится в реестр
как Р11 и вопрос В15.

Практика применения EF-миграций в этом репозитории — выгрузка скрипта и ручной
прогон: в `Database/MigrationScripts/` лежат два таких файла, оба начинаются с
создания `__EFMigrationsHistory`, то есть сгенерированы
`dotnet ef migrations script --idempotent`. Тот же путь берём для процедуры
резерва: миграция в коде, рядом коммитим скрипт, применение — через того, кто
владеет базой.

**Где применять — три базы.** Восстановлено по конфигурации репозитория:

| Контур | Сервер и база | Откуда видно |
|---|---|---|
| прод | `LsPBridge,1436` / `GloriaOTS` | `appsettings.Production.json` |
| стейдж | `NSH-1CDB-TST\SQL2019` / `OrderingStage` | `.env.stage`, `shared.env`, `appsettings.json` |
| дев | `NSH-1CDB-TST\SQL2019` / `Ordering` | `.env`, `ots.env`, `launchSettings.json` |

Дев и стейдж — две базы на одном тестовом сервере. Ловушка: **дефолтный
`appsettings.json` указывает на `OrderingStage`**, а на `Ordering` уводят только
`launchSettings.json` и `.env`-файлы. То есть запуск «локально» без явного
окружения пишет в стейдж, а не в личную базу. Скрипты поэтому не содержат имени
базы — прогоняются как есть на всех трёх.

Отдельно: в `.env`, `ots.env`, `shared.env` и `appsettings*.json` логины и пароли
к базам лежат в открытом виде в git. К нашей задаче не относится, но команде
сказать стоит.

Отдельно про декларативный проект: в README описана команда
`dotnet publish SqlDeploy.csproj`, но **самого `SqlDeploy.csproj` в репозитории
нет** — в `.sln` каталог подключён как solution items, то есть как набор
скриптов. Команда из README как есть не отработает; уточнить у команды OTS, чем
на самом деле раскатывают таблицы (вопрос В14).

**Процедура резерва (расхождение Р9) — обязательна, иначе не поедет ничего.**
Задача просит три таблицы, но резерв делается процедурой на склад:

`src/GloriaOTS.Infrastructure/Persistence/BalanceRepository/BalanceRepository.cs:278-282`

```csharp
        var reserveResult = await _connection.QueryAsync<Reserve>(
            sql: $"Do_Reserve_{warehouseType}",
            param: new { Param = dt.AsTableValuedParameter() },
            transaction: _transaction,
            commandType: CommandType.StoredProcedure);
```

Процедуры заведены EF-миграцией по захардкоженному списку трёх складов
(`Migrations/20231019090335_AddBalanceTypesAndFuncs.cs:27-32`), и она давно
применена, поэтому её повторный прогон нового склада не добавит. Без процедуры
первый `Reserve` от коннектора падает на отсутствующем объекте — то есть пилот
не стартует вообще.

Сделано скриптом `Database/DDL/36-AddDoReserveProcedureForWbFbsWarehouse.sql`:
тело — копия из миграции с заменой имени склада, перед `CREATE OR ALTER` стоят
две проверки (есть `ReserveParam_TVP`, есть таблица резервов), чтобы прогон на
неподготовленной базе падал понятной ошибкой. Остаётся дописать то же самое
EF-миграцией — иначе развёрнутая с нуля через `dotnet ef` база получит процедуры
для трёх складов и не получит четвёртую.

**Про Р10 обновление позиции: watermark в процедуру не добавляем.** Раньше здесь
было сказано «добавляем обновление `GoodBalances.BalanceActionTimestamp` только
для нового склада». Это было сказано до того, как выяснилось, что
`UpdateBalanceActionTimestamp` делает `UPDATE GoodBalances`
(`BalanceRepository.cs:307-318`), а `GoodBalances` — **общая таблица на все
склады**, не на склад. То есть отметка на товаре от резерва по ВБ-складу
попадёт в инкрементальную выборку екома: тот увидит товар как изменившийся,
перечитает его и получит те же числа. Данные не портятся, но это лишний трафик
в чужом контуре из-за нашего склада, и решаться такое должно осознанно, а не
попутно. Поведение процедуры оставляем идентичным остальным складам; чем
закрывать окно расхождения — см. §3.3.

**Джоб наполнения `Goods` (расхождение Р5).** Добавить третий `SELECT` в `UNION`:

`src/GloriaOTS.Infrastructure/Jobs/Implementations/SyncStockGoodsWithRefernces.cs:35-48`

```csharp
        const string sql = """
            WITH ids AS (
            	SELECT Id FROM Stocks_ONES_MOSCOW
            	UNION ALL
            	SELECT Id from Stocks_ONES_NOVOSIBIRSK
            ),
```

Иначе штрихкоды, встречающиеся только на ВБ-складе, не подтянутся в справочник,
и заказ уедет в 1С/WMS без описания, артикула и НДС.

### 3.3. Приём остатка по складу 9148

Отдельного кода интеграции писать не нужно — маршрут уже общий. Путь такой:

```text
1С8 ЛЦ → AMQP (prod.all.logistics.inc.stock_ots(IDD базы).0)
  → OneSStockRmqConsumer (WmsSync): считает актуальный остаток, публикует StockUpdated
  → StockUpdatedConsumer (Web): WarehouseTypeHelper.FromId(WarehouseId) → SetStockAsync
  → UpsertStockBatch(@WarehouseName) → Stocks_<enum>
```

Единственная точка отказа сегодня — `FromId` в
`StockUpdatedConsumer.cs:17`: для `9148` он бросал `NotSupportedException`.
После шага 3.1 остаток едет в `Stocks_ONES_MSK_WB` без дополнительных правок.

**Закрыто 2026-08-13 (В16): остаток по 9148 идёт в существующую очередь МСК**, и
цепочка проходит целиком на текущем коде. Проверено по всем звеньям:

- `OneSStockRmqConsumer` склад **не фильтрует** — берёт `id_warehouse` из самого
  сообщения и кладёт его в `StockUpdated`. Значит инстанс МСК подхватит события по
  9148 из своей очереди.
- Подписка на `StockUpdated` живёт в центральном сервисе
  (`GloriaOTS.Web/Program.cs:322`) и тоже без фильтра по складу.
- `StockUpdatedConsumer` переводит номер в тип склада и зовёт `SetStockAsync`,
  который передаёт `@WarehouseName = warehouseType.ToString()`, то есть
  `ONES_MSK_WB` — ровно то имя, под которое добавлена третья ветка в
  `UpsertStockBatch` (§3.2).

Отсюда: ни секции конфига, ни новой подписки, ни отдельного инстанса под остатки
не нужно. Заодно закрывается **В2** — вопрос про базу 1С стал неактуальным, раз
очередь та же.

Единственное, что остаётся по остаткам, — ограничение Р13: полная сверка идёт под
основным складом инстанса и склад 9148 не покрывает. Инкрементальные события,
которыми остаток и приходит, работают для обоих складов.

**Обратный путь — остаток из OTS в WB — топиком не делаем.** Вопрос возник по
аналогии со статусами (§3.7), поэтому фиксируем решение и причину.

Исходящей публикации остатков в OTS нет вообще — ни в Kafka, ни в шину; остаток
отдаётся **по запросу**: `POST v2/balance` и
`GET api/v3/Balance/GetStock/{sender_idd}`. Kafka-поток дельт остатков в
ландшафте есть (`Integration`: `transfer:stock-delta:daemon`, «получение из kafka
дельт остатков и передача их в OMS»), но OTS его не наполняет, и к нашему складу
он отношения не имеет.

Топик здесь и не нужен, и опасен по существу, а не по трудозатратам:

- WB нужен **свободный** остаток, а он меняется по двум независимым событиям: от
  движения товара в 1С и от резерва внутри OTS при создании или отмене заказа.
  Топик, наполняемый из событий 1С, знал бы только первое — и WB получал бы
  товар, уже обещанный покупателю. Чтобы публиковать свободный остаток
  событиями, OTS пришлось бы эмитировать и на изменения резерва, то есть править
  путь заказа, а не «добавить топик».
- API WB устроен как «установить текущее количество»
  (`PUT /api/v3/stocks/{warehouseId}`), а не как поток дельт. На периодическую
  сверку абсолютных значений это ложится напрямую; из потока событий абсолютное
  состояние всё равно приходилось бы собирать заново.

Для остатков OTS почти ничего не требуется: `GET api/v3/Balance/GetStock/{sender_idd}`
разрешает склад через `WarehouseTypeHelper.TryFromId`, а нижележащий запрос
интерполирует `Stocks_{warehouse}`/`Reserves_{warehouse}` и уже считает
`ISNULL(s.Qty,0) - ISNULL(r.Qty,0)`, то есть свободный остаток
(`BalanceRepositoryV2.cs:20-27`). После §3.1 и §3.2 метод начинает отдавать
остаток нового склада **без новой интеграции**.

**Схему не изобретаем — повторяем Integration.** Он уже забирает остаток из OTS
именно так, двумя командами на набор складов:

- `transfer:stock:ots-init` — полный снимок (`TransferStockOtsInitCommand`);
- `transfer:stock:ots-change` — «передача изменений остатков из OTS в OMS»
  (`TransferStockOtsChangeCommand`).

Инкрементальный цикл устроен так (`TransferService.transferStockOtsChanged`,
`:1733-1819`): отметка последнего успешного забора лежит в конфиге
(`last_ots_stocks_update`), при старте из неё **вычитается перекрытие**
(`stock_ots_change_update_indent`, по умолчанию 600 секунд), при пустой отметке
берётся `-1 day`, запрос идёт постранично (`checkLastPage` по `limit` и общему
количеству), склады перебираются по списку ИДД системы OTS, и отметка
продвигается на `now` **только при успехе**. Перекрытие в десять минут — их
защита от гонок и рассинхрона часов; повторно присланное значение идемпотентно,
потому что мы отдаём в WB абсолютное количество.

Со стороны OTS всё три режима уже есть, и все возвращают свободный остаток за
вычетом резервов (`BalanceService.cs`): `GetStockChange(from, limit, offset)` —
инкремент по `BalanceActionTimestamp`; `GetFullStock(limit, offset)` — полный,
постранично; `GetStockOnline(items)` — точечная проверка по списку. Параметр
`needUpdate` в текущей реализации ни на что не влияет — чтение отметку не
двигает.

**Про blind spot резерва — уточнение, отменяющее более раннюю формулировку.**
Ранее здесь было сказано, что незакрытый watermark при создании резерва (Р10)
даёт oversell. Это преувеличение, и вот почему. В FBS продажу совершает сам WB:
он уменьшает свой счётчик и только потом присылает нам сборочное задание. Наш
инкремент этот товар не вернёт (отметка не двигалась), значит мы ничего по нему и
не отправим — и счётчик WB останется верным. А когда мы всё-таки отправляем,
значение уже посчитано с вычетом резервов. То есть пропускается **уведомление об
изменении**, а не отправляется неверное число.

Реально blind spot мешает в двух случаях, и оба закрываются полной сверкой:
товар, который больше никогда не двигается, не самоизлечится, если стороны
разошлись по любой другой причине; и резерв на этом складе от источника, о
котором WB не знает, оставит его счётчик завышенным. Именно поэтому у Integration
рядом с `ots-change` живёт `ots-init`, и у нас должно быть так же — полная сверка
здесь не подстраховка, а единственный механизм лечения. Двигать watermark в
процедуре резерва мы отказались: он лежит в общей на все склады `GoodBalances`
и задел бы выборку екома (§3.2).

Итоговый цикл для `wbconnector`: инкремент по отметке с перекрытием → маппинг
баркода в `chrtId` → `PUT /api/v3/stocks/{warehouseId}` батчами; редкая полная
сверка для лечения расхождений; при желании внеочередная отправка после событий,
которые мы породили сами. Интервал инкремента — не техническое решение, а
допустимое окно расхождения, его называет бизнес.

Полный снимок как основной режим не годится: базовый запрос идёт `from
GoodBalances` с `where 1 = 1`, то есть возвращает **весь** товарный универсум с
нулями по позициям, которых на складе нет.

**Идентификатор — вопрос снят, правок OTS не требуется.** Ответ балансового
метода уже несёт баркод: `barcode = x.Key.ToString()`, `available_quantity`,
`id_warehouse`/`business_unit_id` (`OTSBalanceMapping.cs:18-23`), а ключ там —
`GoodBalances.Id`, то есть штрихкод. Пользуемся тем же `POST /v2/balance`, что и
Integration; метод V3, отдающий только `good_idd`, просто не используем.

### 3.4. ТК «Wildberries» = 10 и пропуск регистрации в ТК

Это пункт 3 задачи с поправкой Р1, подтверждённой постановщиком 2026-08-12:
речь о регистрации в **транспорте**. То есть внешних вызовов в ТК быть не должно,
`ORDER_SPLIT` должен появиться сам, а дальше заказ обычным порядком уходит на
склад — статусы `*_WAREHOUSE` сохраняются.

**Механизм для этого уже есть** — ветка `OWN` в фасаде не ходит наружу ни при
создании, ни при опросе статуса:

`src/GloriaOTS.Infrastructure/Services/ShipmentServiceFacade.cs:138-143`

```csharp
            case ShipmentService.OWN:
                var orderInfoDoc = GetLastOtsOrderDocuments(orderTracking.Id, OTSDocumentType.OTSOrderParams);
                var restoredOtsOrderParams = ApiClientJsonConverter.Deserialize<OTSOrderParams>(orderInfoDoc.JSON);
                restoredOtsOrderParams.order.order_status = nameof(OrderStatus.ORDER_SPLIT);
                result = OTSOrderResultBuilder.BuildForUnknownShipmentService(restoredOtsOrderParams);
                break;
```

Дальше трекинг сам видит `ORDER_SPLIT` и толкает заказ в
`ORDER_REGISTER_WAREHOUSE` (`OrderTrackingService.cs:417-441`) — то есть на
склад. Это же и доказывает Р1: `*_WAREHOUSE` — не то, что пропускается.

**Где писать код.** В фасаде два параллельных набора методов. Новый, V2,
разрешает реализацию `IShipmentService` через keyed DI (`ShipmentServiceFacade.cs:262-266`),
и `OwnShipmentService` зарегистрирован именно там — но методы `*V2` **не
вызываются нигде** в `src/`. Живой поток идёт через V1: `OrderRegisterTransport.cs:41`
зовёт `TKManager.CreateOrder`, трекинг — `GetOrderStatus`, отмена —
`CancellingTransport.cs:35`. Поэтому реализация только как `IShipmentService`
никем не будет вызвана.

Образец, которому следуем, — **DPD**: это `IShipmentService`, вызываемый из
V1-ветки через конвертер результата:

`src/GloriaOTS.Infrastructure/Services/ShipmentServiceFacade.cs:308-313`

```csharp
    private async Task<OTSOrderResult> CreateDpdOrder(OTSOrderParams orderParams)
    {
        await EnrichOrderParams(orderParams);
        var result = await _dpdShipmentService.CreateOrderAsync(orderParams);
        return result.ToOtsOrderResult();
    }
```

Объём работ:

1. `ShipmentService.WILDBERRIES = 10` (`Constants/ShipmentService.cs`). Значения
   там заданы явно, 8 и 10 свободны — добавление безопасно.
2. `ShipmentServiceHelper.GetShipmentServiceBy`: `10 => WILDBERRIES`.
   `GetPvzTkIdByType`: `10 => "wb"` (значение уходит в WMS как `carriername`,
   согласовать с логистикой — вопрос В3).
   Оба метода сейчас бросают `NotImplementedException` на неизвестном id.
3. `WbFbsShipmentService : IShipmentService` — без внешних вызовов, по образцу
   `OwnShipmentService`, с обязательной поправкой из «ловушки» ниже.
4. Регистрация keyed-сервисом (`DependencyInjectionExtensions.cs:97-102`) — чтобы
   код был готов к V2, когда её начнут использовать.
5. Четыре ветки в V1-фасаде: `CreateOrder`, `UpdateOrder`, `GetOrderStatus`,
   `CancelOrder`. **Все четыре сразу:** в `CreateOrder`/`UpdateOrder` ветка
   `default` возвращает пустой `OTSOrderResult` без ошибки
   (`ShipmentServiceFacade.cs:78`, `:206`), то есть забытая ветка проявится не
   исключением, а тихо неработающим заказом. В `GetOrderStatus`/`CancelOrder`
   `default` бросает `NotImplementedException`.

**Ловушка, из-за которой сломались бы пункты 4 и 5 задачи.** `OwnShipmentService.BuildResult`
не заполняет `ShipmentBarcode` (`OwnShipmentService.cs:67-91`), а V1-конвертер
берёт именно его:

`src/GloriaOTS.ApplicationCore/OTSModels/Results/OrderIntegrationResultExtensions.cs:102-103`

```csharp
            shipment_barcode = result.ShipmentBarcode,
            TKInvoiceID = result.ExternalOrderId,
```

а обработчик пустой баркод молча не пишет в трекинг:

`src/GloriaOTS.Infrastructure/Handlers/Handlers/ORDER_TO_CHECK/OrderRegisterTransport.cs:77-80`

```csharp
        if (!string.IsNullOrEmpty(tkResult.shipment_barcode))
        {
            tracking.AddOrUpdateStringParam(OrderTrackingParams.SHIPMENT_BARCODE, tkResult.shipment_barcode);
        }
```

Итог: `/hs/EcommOrder` и `carrierBarcode1` уехали бы пустыми, без ошибок в логах.
Поэтому в `WbFbsShipmentService` **явно** проставляем
`ShipmentBarcode = order_id.ToString()` и `ExternalOrderId = order_id.ToString()`
— ровно то, что делает `BuildForUnknownShipmentService` (`OTSOrderResultBuilder.cs:101,104`).

### 3.5. Передача заказа в 1С — `/hs/EcommOrder`

Пункт 4 задачи. Всё в одном методе — `OneSService.BuildRegistryRequest`
(`Workers/GloriaOTS.WmsSync/OneS/OneSService.cs:50-86`).

**`idd_order` — префикс по source.** Сейчас:

`src/GloriaOTS.ApplicationCore/OTSModels/Params/OTSRequestParams.cs:50-62`

```csharp
    public string GetPrefix()
    {
        if (source == OrderSource.Starfish)
        {
            return "0000352";
        }
        if (source == OrderSource.RSG)
        {
            return "0000354";
        }
        return "0000337";

    }
```

Добавляем `FBS_WB => "0000370"`. Обратите внимание на семь символов и ведущий
ноль: вызывающий код заменяет первый символ на `Z`
(`OneSService.cs:55-56`, `TgwWmsMapping.cs:110-111`), давая
`Z` + `000370` + номер(10) = 17 символов, как в контракте. Значение `"000370"`
из шести символов сломает формат.

**`idd_sender` — по типу склада.** В `switch` по `WarehouseType`
(`OneSService.cs:60-72`) добавить `ONES_MSK_WB => StoresIDD.MSK_LC_WB`.
Ветки `default` там нет, поэтому пропуск даст пустую строку, а не исключение —
это ещё одно тихое поведение, которое стоит закрыть.

**`idd_client` — через `GetClientId`** (`OneSService.cs:88-109`):
`ONES_MSK_WB => StoresIDD.MSK_WB`. Первая ветка метода (`transport_id == 5`) для
нас не срабатывает, так как у нас 10, — и это ровно тот случай, ради которого в
`OTS-CHANGES-WB-FBS.md` была выбрана отдельная ТК вместо переиспользования `OWN`:
правка `GetClientId` для C&C не требуется.

Новые константы в `StoresIDD` (`Workers/GloriaOTS.WmsSync/OneS/StoresIDD.cs`),
по образцу существующей пары «ЛЦ — магазин»:

```csharp
public const string MSK_WB = "00005550031258273";     // м-н МСК WB FBS  → idd_client
public const string MSK_LC_WB = "00005550031258229";  // Москва ЛЦ ВБ    → idd_sender
```

**`shipment_barcode`.** Задача просит для склада 9148 дублировать номер заказа.
Отдельной ветки по складу не требуется: после 3.4 баркод равен номеру заказа
на уровне результата ТК и доезжает сюда через `OrderTrackingParams.SHIPMENT_BARCODE`
штатным путём. Это тот же механизм, что уже работает для C&C. Специальный
`if` по складу добавит второй источник истины — не делаем, но фиксируем как
осознанное отклонение от буквы постановки (вопрос В4).

### 3.6. Передача заказа в WMS — `carrierBarcode1`

Пункт 5 задачи. Правки не требуется:

`src/GloriaOTS.ApplicationCore/Mapping/Tgw/TgwWmsMapping.cs:148`

```csharp
                    carrierBarcode1 = shipment_barcode,
```

Поле уже заполняется из `shipment_barcode`, который после 3.4 равен номеру
заказа. Проверяем фактом на тесте (§5), а не кодом.

Отдельно посмотреть при тестировании: `ClickAndCollect` в том же маппинге
(`TgwWmsMapping.cs:163-173`) считается по `delivery.type` и `transport_id`;
для `type = 1` (курьер) даёт `0`, для неизвестного `transport_id` при `type = 2`
— тоже `0`. Мы отдаём `type = 1` (`ots/types.go`, `DeliveryTypeCourier`), так что
поведение предсказуемо, но значение стоит подтвердить со складом (вопрос В5).

### 3.7. Публикация статусов `FBS_WB` — расхождение Р2, добавляем в объём

Без этого пилот не работает: WB Connector узнаёт о сборке только из статусов OTS.

`src/GloriaOTS.Infrastructure/OrderStatusNotifiers/StarfishOrderStatusNotifier.cs:36`

```csharp
            if (result.source == OrderSource.Starfish)
```

**Решение от 2026-08-12: отдельный топик, а не общий.** Ранее (`OTS-CHANGES-WB-FBS.md`
§3.1) предполагалось публиковать `FBS_WB` в существующий топик и фильтровать по
`source` в Integration. Это выбиралось при условии «правки OTS делает чужая
команда, минимизируем их». Условие изменилось — OTS дорабатываем сами, — поэтому
берём вариант с **отдельным топиком** для `FBS_WB`.

Что это даёт:

- **Integration не трогаем вообще.** Он продолжает обслуживать поток екома, а
  WB-события до него просто не доходят. Снимается кросс-командная зависимость и
  вместе с ней ловушка порядка деплоя: раньше публикация раньше фильтра давала
  десятки тысяч бесполезных запросов в OMS в сутки (`MP-WB-FBS-080`).
- **Ветка екома не меняется.** Условие `if (result.source == OrderSource.Starfish)`
  остаётся как есть, `FBS_WB` обслуживает второй нотификатор. Правка рядом, а не
  внутри работающего пути.
- **Ordinal перестаёт быть риском на критическом пути (Р4).** Маршрутизация больше
  не опирается на числовое значение `source`: всё, что лежит в топике, — WB по
  построению. Явные значения enum остаются гигиеной, но их пропуск больше не
  ломает разбор на нашей стороне.
- **Наша недоступность не бьёт по екому.** `Notificated` проставляется по факту
  записи в брокер, поэтому лежащий коннектор не удерживает события в выборке
  `OrderLaterNotificationService`. Это главный аргумент против варианта «OTS
  зовёт наш HTTP напрямую»: там наш простой напрямую растил бы общий бэклог, а
  выборка идёт по всем непроцессированным событиям сразу, включая екомовские.

Что для этого нужно в OTS:

1. Новый `WbFbsOrderStatusNotifier : IOrderStatusNotifier` с условием по
   `FBS_WB`. Множественность нотификаторов уже заложена: они разрешаются
   коллекцией и перебираются в цикле
   (`OrderLaterNotificationService.cs:36,66-73`), а `Notificated` ставится, если
   **любой** вернул успех. Сейчас зарегистрирован ровно один
   (`DependencyInjectionExtensions.cs:226`).
2. Второй топик для публикации. `Sender` сейчас забирает топик из
   `SenderSettings.Topic` в конструкторе, а `KafkaClientHandle` и
   `KafkaDependentProducer` — синглтоны на тех же настройках
   (`Starfish/Extensions.cs`). Если новый топик в **том же** кластере, дешевле
   всего переиспользовать продюсер и передавать топик параметром в
   `NotifyAsync`; если в другом — понадобится второй handle с отдельными
   credentials.
3. Список публикуемых статусов для WB. Копировать массив из
   `StarfishOrderStatusNotifier.cs:17-32` нельзя бездумно: части статусов
   (`READY_FOR_PICKUP`, `COMPLETED` в екомовском смысле) нам не нужно, а расхождение
   двух копий со временем разъедется. Список вынести в одно место и явно указать,
   какие статусы читает WB Connector.
4. Payload не меняем: публикуем тот же `OtsOrderResultV2`
   (`ResultConversionService.ConvertToOtsOrderResultV2Async`), под который у
   коннектора уже написан и протестирован разбор.

**Реализовано 2026-08-13.** Имена топиков от владельца: `dev`, `stage` и
`prod.all.ecom.fct.order-status-wb.0`. Прописаны в `appsettings` воркера
`OrderTracking` — именно он рассылает уведомления; для дева значение приходит
переменной `WbFbsSenderSettings__Topic`.

Топик в том же кластере, поэтому переиспользован общий `KafkaClientHandle` — над
ним поднят второй типизированный продюсер `KafkaDependentProducer<string, string>`,
что и описано как штатный способ в комментарии самого класса. Подключение и
учётные данные остались в одном месте (`StarfishSenderSettings`), в
`WbFbsSenderSettings` только топик: иначе пароль лежал бы в двух местах и мог
разойтись.

Публикуются девять статусов: `CHECKED_INVALID`, `SUSPENDED`,
`ORDER_CONFIRMED_WAREHOUSE`, `PICKING`, `ORDER_PICKUP`, `CANCELLING`,
`CANCELLED`, `COMPLETED`, `LOST`. Остальное — внутренние переходы OTS, читателю от
них ничего не меняется. `COMPLETED` в списке потому, что коннектор сам его и
присылает: эхо подтверждает, что резерв снят (Р12).

Проверено, что второй нотификатор не задевает еком: цикл ставит `Notificated`
только при `notificationResult?.Success == true`
(`OrderLaterNotificationService.cs:69`), то есть `null` от чужого нотификатора
просто игнорируется. И `FBS_WB` не попадает в список источников, которые
помечаются отправленными и пропускаются (`:50-57`).

**Ключ сообщения — решение принято, публикуем с ключом.** Еком-отправитель
публикует без ключа, и это менять не стали:

`src/GloriaOTS.Infrastructure/OrderStatusNotifiers/Starfish/Sender.cs:57-59`

```csharp
                var producingResult = await _producer.ProduceAsync(
                    topic: _topic,
                    message: new Message<Null, string> { Value = messageString });
```

Без ключа сообщения раскладываются по партициям по кругу, то есть два события
одного заказа могут попасть в разные партиции. Пока консьюмер один, это не видно.
Как только реплик становится больше одной, разные партиции обслуживаются разными
процессами одновременно — и статусы одного заказа обрабатываются в произвольном
порядке. Для нового нотификатора публикуем с **`Key = order_id`**: тогда весь
жизненный цикл заказа лежит в одной партиции, порядок внутри заказа сохраняется, а
реплики масштабируются до числа партиций. Менять это на живом топике поздно —
перекладка ключей не исправляет уже записанное.

Что нужно у нас:

- **Отдельный воркер-консьюмер в `cmd`**, а не горутина внутри основного сервиса —
  чтобы масштабировать репликами и деплоить независимо. Прецедент в парке есть:
  `offers-go` собран именно так — `cmd/{api,assembler,importer,migrate}` плюс
  `internal/runtime/<binary>/app`, и внутри бинаря набор поднимаемых консьюмеров
  выбирается переменной `workerType` (`all`/`events`,
  `internal/runtime/assembler/app/app.go:113`). У нас уже есть
  `cmd/wbconnector` и `cmd/migrate`, добавляется третий бинарь.
- **Библиотека — `github.com/segmentio/kafka-go`**, как в `offers-go`
  (`go.mod: v0.4.46`). Отдельного решения по парку не требуется, прецедент
  сложился. Обёртка там тонкая (~70 строк,
  `internal/adapters/clients/kafka/consumer.go`: reader, SASL-dialer, `Close`,
  `FetchMessage`, `CommitMessages`), но лежит под `internal/` чужого модуля —
  переносим шаблон, а не импортируем. Оттуда же стоит взять устройство обвязки:
  group id вида `<base>-<consumer>`, DLQ, лимит ретраев и таймаут обработчика,
  метрики на консьюмера.
- **Монотонность статуса на приёме — наша задача, независимо от ключа.** Сейчас
  приём проставляет статус безусловно:
  `UPDATE wb_orders SET gj_status = $2 …` (`internal/adapters/pgstore/otsstatus.go:150`),
  без сравнения с текущим. То есть опоздавший `PICKING` после `ORDER_PICKUP`
  утащит заказ назад по жизненному циклу, а из статусов у нас растут команды
  (привязка КИЗ на `ORDER_PICKUP`). Ключ партиционирования делает такую
  ситуацию маловероятной, но защиту стоит поставить всё равно — сравнивать вес
  статуса и игнорировать регресс. В OTS такая шкала уже есть
  (`OrderStatus.Weight`: `ON_VALIDATION` 10 … `ORDER_PICKUP` 60 … `DELIVERING` 70),
  её порядок можно повторить у себя.
- Сам разбор сообщения уже готов: `otsStatusMessage`
  (`internal/platform/transport/otsstatus.go`) описывает ровно `OTSOrderResultV2`,
  так что меняется транспорт, а не контракт. Существующий HTTP-эндпоинт
  `POST /api/v1/ots/order-status` имеет смысл сохранить для ручного проигрывания
  событий на стенде.
- Инфраструктура: создать топик, выдать ACL и **сразу заложить число партиций** —
  оно задаёт потолок полезного числа реплик, а добавление партиций позже меняет
  раскладку ключей и рвёт гарантию порядка для заказов, живущих через изменение.
  Имя — по принятому соглашению; в `offers-go` имена собираются из контура
  (`internal/adapters/kafka/contracts`), существующий статусный топик —
  `prod.all.ecom.fct.order-status.0` (вопрос В10).

Пока публикации нет, события `FBS_WB` копятся в `OrderLaterNotificationService`
(Р3) — то есть отсутствие этой правки не «ничего не происходит», а растущая
нагрузка на общую выборку.

### 3.8. Деплой `WmsSync` — расхождение Р6

`WmsSync` привязан к одному складу: slug из env → статика
`WarehouseDefaults`, плюс фильтры подписок по `id_warehouse`:

`src/Workers/GloriaOTS.WmsSync/Program.cs:104-110`

```csharp
    WarehouseType warehouseType = warehouse switch
    {
        "MSK" => WarehouseType.ONES_MOSCOW,
        "NSK" => WarehouseType.ONES_NOVOSIBIRSK,
        _ => throw new InvalidDataException("Warehouse env var")
    };
    var warehouseId = warehouseType.ToWarehouseId();
```

**Решение изменилось 2026-08-13, отдельный инстанс не нужен.** Выяснилось, что
склад 9148 — не отдельная площадка, а виртуальная выделенная под ВБ часть
подольского склада: WMS и 1С у них общие. Второй процесс только продублировал бы
соединения к тем же системам, поэтому инстанс МСК теперь обслуживает оба склада.

Сделано так: `WarehouseDefaults.ServedWarehouseIds` — список складов инстанса
(`MSK` → `6003` и `9148`), а фильтры подписок сверяются со списком вместо одного
значения. Тонкость, на которой легко ошибиться: фильтр означает **«пропустить
событие»** (`IBus.cs:23`), поэтому условие инвертировано —
`!served.Contains(...)`. До правки инстанс МСК отбрасывал все заказы по 9148.

Slug `MSK_WB` при этом сохранён в обоих местах: если склады когда-нибудь
разъедутся физически, инстанс поднимается без правок кода.

Отсюда **В8 снят**: разговор с DevOps о размещении нового процесса не нужен.
Осталось ограничение Р13 — полная сверка остатка идёт под основным складом
инстанса и склад 9148 не покрывает.

## 4. Порядок работ

Порядок не произвольный — каждый следующий шаг опирается на предыдущий. Шаги 1–8
по стороне OTS выполнены (§0), ниже они оставлены как след: по ним удобно
восстанавливать, почему сделано именно в таком порядке, и они же задают
последовательность выкатки на контур.

1. ~~**3.1 мастер-данные**~~ — без него всё остальное падает исключениями.
2. ~~**3.2 таблицы + `Do_Reserve_ONES_MSK_WB` + ветка `UpsertStockBatch` + джоб
   `Goods`**~~ — до первого остатка и до первого резерва. Процедура резерва (Р9)
   здесь не «до остатка», а условие того, что заказ вообще примется.
3. **3.3 приём остатка** — код готов, проверяется после деплоя; нужен ответ В16.
4. ~~**3.4 ТК = 10**~~ — после этого заказ проходит до склада; здесь же появляется
   баркод, от которого зависят 3.5 и 3.6.
5. ~~**3.5 передача в 1С**~~ — проверяем префикс и пару ИДД.
6. ~~**3.8 `WmsSync`**~~ — инстанс МСК обслуживает оба склада, отдельный не нужен.
7. **топик и ACL** — заявка в инфраструктуру, у неё свой срок; запускать заранее.
8. ~~**3.7 публикация статусов** в OTS (с `Key = order_id`)~~ + **отдельный
   воркер-консьюмер в `cmd` у `wbconnector`** — не начат. Пока консьюмера нет,
   сообщения просто лежат в топике, а не теряются и никого не задевают.
   Монотонность статуса на приёме сделать до включения второй реплики.
9. **Отправка `COMPLETED` из коннектора в OTS** по статусу «продано» от WB — без
   неё резерв не снимается (Р12), а правка в OTS уже сделана.

## 5. Что проверяем на приёмке

| Проверка | Ожидание |
|---|---|
| Остаток из 1С по складу 9148 | строка в `Stocks_ONES_MSK_WB`, `GoodBalances` обновлён |
| Новый штрихкод только на ВБ-складе | после джоба появился в `Goods` |
| `Reserve` от коннектора с `business_unit_id = 00005550031258229` | принят, `id_warehouse = 9148`, резерв в `Reserves_ONES_MSK_WB` (процедура `Do_Reserve_ONES_MSK_WB` существует) |
| Полная сверка лечит расхождение | после резерва инкрементальная выборка товар не возвращает (ожидаемо, Р10), а полная — возвращает уже уменьшенный свободный остаток |
| Остаток в WB после продажи | свободный остаток уменьшился и уехал в WB в пределах согласованного окна |
| Ответ OTS на `/v2` | `business_unit_id` в ответе заполнен (обратная трансляция не упала) |
| Заказ с `transport_id = 10` | ни одного исходящего вызова в ТК; в трекинге `SHIPMENT_BARCODE` = номер заказа |
| Статусная цепочка | `ORDER_SPLIT` → `ORDER_REGISTER_WAREHOUSE` → заказ ушёл в WMS |
| Запрос в 1С `/hs/EcommOrder` | `idd_order = Z000370…`, `idd_sender = 00005550031258229`, `idd_client = 00005550031258273`, `shipment_barcode` = номер заказа |
| Телеграмма в WMS | `carrierBarcode1` = номер заказа, `OrderWwsBeleg = Z000370…` |
| Статусы наружу | событие `FBS_WB` лежит в **своём** топике, `Notificated = 1`, бэклог не растёт |
| Разделение потоков | в екомовском топике нет ни одного `FBS_WB`-события; демон Integration не получил ни одного WB-заказа |
| Приём статусов у нас | консьюмер `wbconnector` разобрал `OtsOrderResultV2`, `ots_events` пополнился, КИЗ поставлен в очередь на привязку |
| Партиционирование | все события одного заказа в одной партиции (`Key = order_id`) |
| Две реплики консьюмера | статусы одного заказа не идут вспять; регресс отбрасывается монотонной защитой |
| Отмена заказа | проходит без обращения в ТК |
| Строка ТК в справочнике | `select * from Carrier where warehouse_id = '9148'` — одна строка с `Id = '10'`; без неё заказ отклоняется как `UnknownDeliveryID` (Р14) |
| Снятие резерва | после `ORDER_TO_PICKING` + `COMPLETED` от коннектора строк по заказу в `Reserves_ONES_MSK_WB` нет, в трекинге `TRACKING_PHASE = END` (Р12) |
| Заказы обоих складов в одном инстансе | инстанс МСК обработал и заказ по `6003`, и заказ по `9148`; ни один не отброшен фильтром (§3.8) |

## 6. Вопросы

Нумерация сохраняется при закрытии вопросов — на неё есть ссылки из §3.

### Закрыто

- **В16** (2026-08-13, Казакова А. И.). Остаток по складу 9148 публикуется в
  **существующую** очередь МСК. Значит §3.3 закрыт целиком, без секции конфига и
  без нового инстанса: цепочка проходит на текущем коде, разбор в §3.3.
- **В2** (снят вместе с В16). Вопрос «ВБ-склад в той же базе 1С, что ЛЦ МСК»
  потерял смысл: очередь та же, а консьюмер берёт склад из сообщения.
- **В1** (2026-08-12, Казакова А. И.). Пункт 3 действительно про транспорт: в
  постановку скопирована не та строка статусной схемы. Реализуем по §3.4, текст
  задачи в Jira поправить. Отдельно стоит помнить: шаг регистрации у нас не
  «пропускается», а становится пустым — заказ по-прежнему проходит через
  `*_TRANSPORT`, потому что это `Status` обработчика `OrderRegisterTransport`, и
  статусы лягут в `OrderEvents`. Наружу это не видно: веса 21/22 не входят в
  список публикуемых (`StarfishOrderStatusNotifier.cs:17-32`), поэтому ни OMS,
  ни WB Connector их не увидят.

- **В6** (2026-08-13, по коду и прецеденту). `BalanceMoves_ONES_MSK_WB` не нужна:
  процедура резерва её не пишет, обращений к `BalanceMoves` в коде OTS нет, а у
  последнего добавленного склада BetaPro такой таблицы не создавали. Заводить
  можно только ради формального соответствия тексту задачи (§3.2, Р8).

### Открыто — к постановщику (Казакова А. И.)

- **В3.** Что писать в `carriername` для WMS по новой ТК (сейчас у нас `"wb"` как
  предположение) — склад должен различать WB-отгрузку штатным признаком.
- **В4.** Согласовать, что `shipment_barcode` = номер заказа достигается общим
  механизмом ТК, а не отдельным условием по складу 9148 (§3.5).
- **В5.** Значение `ClickAndCollect` в телеграмме WMS для WB-заказов (§3.6).
### Открыто — к нам

- **В9.** Прописать `business_unit_id = 00005550031258229` в конфигурацию
  `wbconnector` (`OTS_WAREHOUSE_MAP`) и проверить на стенде.
- **В12.** Владелец политики остатка FBS (`MP-WB-FBS-011`): отдаём в WB весь
  свободный остаток склада 9148 или квоту. Выделенный склад делает ответ «весь»
  естественным, но это решение бизнеса, а не техники. Отдельно — интервал
  инкрементальной сверки как допустимое окно расхождения (§3.3).
- **В13.** Может ли на складе 9148 появиться резерв или расход от источника,
  о котором WB не знает (внутреннее перемещение, заказ екома, ручная операция)?
  Если да — полная сверка нужна чаще, чем «раз в сутки» (§3.3).
- **В15.** Дрейф снапшота OrderContext (Р11): кто и когда закрывает отдельной
  миграцией. Пока он открыт, EF-путь в основном контексте недоступен всем, не
  только нам. Плюс сказать владельцам: релизный скрипт DPD на проде упадёт
  (§3.2), а `wms.__EFMigrationsHistory` недозаполнена.
- **В14.** Чем на самом деле раскатывают таблицы OTS: в README описан
  `dotnet publish SqlDeploy.csproj`, но проекта в репозитории нет — каталог
  подключён к `.sln` как набор скриптов. Заодно уточнить, кто применяет
  идемпотентные скрипты EF-миграций и на каких стендах (§3.2).
- **В10.** Топик для статусов `FBS_WB`: имя по соглашению, тот же кластер или
  отдельный, ACL для продюсера (OTS) и консьюмера (`wbconnector`), **число
  партиций** с запасом под 20 000 заданий в сутки. От «того же кластера» зависит,
  переиспользуется ли существующий `KafkaClientHandle` (§3.7).

### Снято решением от 2026-08-13

- **В8** (был: где разместить инстанс `WmsSync` и какой сетевой доступ ему нужен).
  Склад 9148 — виртуальная часть подольского склада, WMS и 1С у них общие, поэтому
  отдельный процесс не нужен: инстанс МСК обслуживает оба склада (§3.8).

### Снято решением от 2026-08-12

- **В7** (был: публикация статусов — отдельный тикет или расширяем этот?).
  Публикация делается в объёме этой задачи, отдельным топиком и вторым
  нотификатором (§3.7). Правка Integration не требуется, поэтому вопрос
  «согласовать чужой релиз» закрыт вместе с ним.

## 7. Источники

- Задача: [OPSLOG-3461](https://jira.gloria-jeans.ru/browse/OPSLOG-3461)
- Confluence: [63468353](https://confluence.gloria-jeans.ru/pages/viewpage.action?pageId=63468353)
  «1C8 ЛЦ - OTS. Изменение остатка» v25 (2026-08-10, в реестре изменений есть
  запись по этой задаче);
  [78745861](https://confluence.gloria-jeans.ru/pages/viewpage.action?pageId=78745861)
  «1C8 ЛЦ - OTS. Остаток Склада» v11 (2024-04-15, **страница не обновлялась под
  новый склад** — параметры `firm_idd`/`sender_idd` там всё ещё hardcode НСК);
  [63468416](https://confluence.gloria-jeans.ru/pages/viewpage.action?pageId=63468416)
  «OTS - 1C8 ЛЦ. РегистрСведений.ЗаказыКлиентов» v35 (2026-08-12)
- Код: `platform/gloriaots/gloriaots`, ветка `release`, HEAD `d1c513a0`
- Реестр решений: `EVIDENCE-LEDGER.md`, записи `MP-WB-FBS-078/079/080/085/086`
