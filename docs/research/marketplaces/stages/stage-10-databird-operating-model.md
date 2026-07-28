# Stage 10 — DataBird: операционная модель

**Дата среза:** 2026-07-23  
**Статус:** complete-for-current-pass  
**Уровень покрытия:** substantial для Jira/Confluence; partial для runtime  
**Связанный обзор:** [stage-02-databird.md](stage-02-databird.md)

## 0. Scope

Этот документ углубляет общий обзор DataBird до операционной модели:

- какие сущности DataBird используются;
- откуда и куда идут данные;
- какие расписания были выгружены из DataBird;
- как сопоставляются товары;
- какие формулы и приоритеты цены документированы;
- как выглядят ошибки, контроль и ручные операции;
- кто фигурирует как владелец/поддержка;
- насколько продвинулся контур карточек Ozon, WB и Яндекс Маркета;
- что подтверждено только документами, а что подтверждено текущим runtime.

Вне scope:

- договор и SLA с поставщиком DataBird;
- изменение конфигурации DataBird;
- проверка личных кабинетов маркетплейсов;
- проверка секретов и их ротация;
- поставки, заказы и финансы, если они не пересекаются с DataBird.

### 0.1. Шкала доказательности

| Статус | Значение |
|---|---|
| `confirmed-live` | проверено в runtime на дату среза |
| `confirmed-source` | прямо записано в первичном Jira/Confluence/config snapshot |
| `high` | согласуется в нескольких источниках, но live-прохождение не проверено |
| `proxy` | косвенный признак, проектный статус или старый конфигурационный снимок |
| `unknown` | доказательств недостаточно |

Ключевой принцип: закрытая Jira-задача и конфигурация 2025 года не равны
подтвержденному успешному обмену в июле 2026 года.

## 1. Executive summary

1. **Цены — наиболее зрелый контур.** Документирована цепочка
   `Price Formation → ApiGW → DataBird catalog → compare with marketplace →
   marketplace export` для WB, Ozon и Яндекс Маркета. Jira-истории по ценам
   закрыты в 2025 году. В Confluence лежат выгрузки реальных конфигураций
   импортов со schedule, mapping, lastSync и counters.
2. **Точные найденные schedule относятся к снимкам апреля 2025 года.**
   Они доказывают, что импорты были настроены и запускались тогда, но не
   являются текущим live-расписанием.
3. **Карточки остаются программой внедрения.** Ozon и WB в последних Jira-
   статусах находятся в реализации; Яндекс приостановлен. По Ozon подтверждена
   частичная выгрузка атрибутов и подготовка пилотного exporter, но не полный
   промышленный поток.
4. **В production жив `mp-connector`.** На 2026-07-23 deployment и pod готовы,
   внутренний daily cron успешно завершался 22 и 23 июля. Это подтверждает
   подготовительный контур ENSI, но не вызов endpoint со стороны DataBird и не
   прием данных маркетплейсом.
5. **Операционная модель содержит ручной труд.** Excel overrides, blacklist,
   исправление объединенных карточек WB, чистка каталога, повторные проливки,
   проверка ошибок по SKU и контроль schedule после редактирования — штатные
   документированные операции.
6. **Полноценные retries, alerting, SLA и RACI не найдены.** Есть UI-status,
   детализация ошибок по SKU, логирование PF API в Kibana и рекомендация
   мониторить health endpoint DataBird. Подтверждения, что alert создан и
   маршрутизируется владельцу, нет.

## 2. Карта источников и свежесть

| Источник | Срез источника | Что подтверждает | Ограничение |
|---|---:|---|---|
| Confluence `149765159`, v6, «ADR Databird — Загрузка цен в Маркетплейсы» | updated 2025-08-05 | архитектура цен, формулы, ручные операции; config attachments | страница имеет статус «Черновик» |
| Attachments к `149765159`, IDs `149765163`—`149765188` | config state/lastSync в основном 2025-04 | реальные schedule, mappings, counters и state импортов | исторические snapshots, не текущий кабинет |
| Confluence `130141740`, v6 | updated 2025-02-13 | PF API действующей промо-цены, daily/on-demand, поля и логирование | не подтверждает вызов DataBird сегодня |
| Confluence `82015904`, v8 | updated 2023-10-02 | PF API обычных цен, incremental interval, поля | старая страница; получатель указан как ENSI Catalog |
| Confluence `149768494`, v29, `[draft]` | updated 2025-07-11 | AS-IS и TO-BE карточек | проектный черновик |
| Confluence `165381358`, v4 | updated 2026-04-09 | API справочника идентификаторов МП | не доказана связь именно с текущим DataBird exporter |
| Confluence `165400156`, v7 | updated 2026-04-10 | DataBird как инициатор чтения WB-замеров | периодичность «по необходимости» |
| Jira epic `OPSMPC-549` | updated 2025-09-30, Open | состав программы DataBird | epic stale относительно части дочерних задач |
| Jira `OPSMPC-550`, `620`, `636` | updated 2025-05/06, Done | цены WB/Ozon/Yandex завершены как работа | production-success не приложен |
| Jira `OPSMPC-697`, `834` | updated 2026-03, Implementation/In Progress | карточки и mapping Ozon еще не завершены | нет acceptance evidence |
| Jira `OPSMPC-862`, `863` | updated 2026-03/2025-12, Implementation/Development | карточки и mapping WB еще не завершены | нет acceptance evidence |
| Jira `OPSMPC-717` | updated 2025-09, Suspended | карточки Яндекс приостановлены | статус может быть не обновлен вне Jira |
| GitLab project `820`, HEAD `3b6dba3e` | HEAD dated 2025-12-23 | код `mp-connector`, endpoint и cron | наличие кода не равно DataBird ingestion |
| K8s `prod/mp-connector-master-ms` | observed 2026-07-23 | deployment/pod/service/ingress готовы | не показывает вызывающую сторону |
| ENSI prod logs, `mp-connector` | 2026-07-22/23 | daily cron Running/Completed | не показывает вызов `/updated-products` |

## 3. Сущности DataBird и направление обменов

ADR `149765159` определяет три основные сущности:

- **catalog / КТ** — карточка DataBird, в которой хранятся идентификаторы,
  атрибуты и цены;
- **import / источник** — получает данные из внешней системы, сопоставляет поля
  и обновляет/создает позиции каталога;
- **export** — преобразует данные каталога в формат приемника и отправляет их
  наружу.

### 3.1. Документированный ценовой цикл

| Шаг | Направление | Содержание | Evidence | Confidence |
|---|---|---|---|---|
| 1 | PF → ApiGW → DataBird | обычные цены | `149765159`, `82015904` | confirmed-source |
| 2 | PF → ApiGW → DataBird | действующие промо-цены | `149765159`, `130141740` | confirmed-source |
| 3 | WB/Ozon/Yandex → DataBird | фактические цены площадки; Ozon также отдает атрибуты | config attachments `149765175`, `149765178`; ADR | confirmed-source, historical |
| 4 | DataBird catalog | mapping, приоритеты, blacklist, нормализация | `149765159` | confirmed-source |
| 5 | DataBird catalog | сравнение целевого и фактического состояния | `149765159` | confirmed-source |
| 6 | DataBird → marketplace | экспорт только при расхождении | `149765159`; Done issues `550/620/636` | high, not live-confirmed |

### 3.2. Источники обычных и промо-цен

`page_id=82015904` описывает метод PF для обычных цен:

- transport JSON over HTTP(S);
- запуск раз в сутки или по запросу;
- отбор по интервалу редактирования price orders;
- при отсутствии `from` используется текущее время минус семь дней;
- для первой выгрузки допускается историческая дата;
- обязательный ключ магазина/склада `StoreIDD`;
- ответ содержит `sku_article`, `barcode`, `price`, `old_price`,
  `validity_date_start`, `store_code`, `prc_type`, `time_stamp`.

`page_id=130141740` описывает метод действующей промо-цены:

- раз в сутки или по запросу;
- отбор по `TargetDate`, `StoreIDD`, optional `Offset`;
- завершившаяся акция возвращает цену `0`;
- выбирается последний утвержденный приказ по акции;
- ответ содержит `sku_article`, `barcode`, `price`, `store_code`,
  `prc_type`, `time_stamp`.

ADR указывает, что DataBird фильтрует обычные цены по
`validity_date_start <= начало текущего дня`.

### 3.3. Дополнительные справочники

Исторические config snapshots показывают отдельные импорты:

- `1C_Ref_Assortment` — по barcode обновляет признак ассортимента;
- `1C_Ref_Style_Variant` — по barcode обновляет `variant_no` и модель;
- `NEW_SKU` для WB/Ozon — создает позицию каталога по данным PF без цен.

Отдельный свежий интерфейс `165381358` предоставляет другим системам справочник
`ИдентификаторыМП`, включая идентификатор площадки, объединенную карточку,
размер, владельца и другие поля. Jira `OPSMPC-868` закрыта 2026-05-13.

Это подтверждает наличие централизованного справочного контура, но не
подтверждает, что именно он является текущим ключевым источником DataBird для
всех карточек.

`page_id=165400156` фиксирует DataBird как инициатора чтения замеров WB:

- endpoint `api/Hybris/WhMeas`;
- barcode, marketplace ID, width/length/height/volume, measurement date;
- периодичность — по необходимости обновления.

## 4. Расписания: что известно точно

Ниже приведены **расписания из config attachments** страницы `149765159`.
Это не live-конфигурация на 2026-07-23.

| Import snapshot | Schedule | Последний state в snapshot | Назначение |
|---|---:|---|---|
| `PF_WB_NEW_SKU` (`149765163`) | daily 23:00 | failed, credential error on 2025-04-16 | создание новых SKU WB без цен |
| `PF_OZON_NEW_SKU` (`149765164`) | daily 23:00 | failed, credential error on 2025-04-16 | создание новых SKU Ozon без цен |
| `WB_source` (`149765175`) | daily 23:30 | ok, 2025-04-16; 299040 inserted, 13 mistakes | цены/discount/article из WB |
| `PF_WB_prices` (`149765173`) | daily 00:05 | ok, 2025-04-16; 15077 inserted, 0 mistakes | обычные цены WB |
| `PF_WB_PromoPrices` (`149765172`) | daily 00:10 | ok, 2025-04-16; 22206 inserted, 0 mistakes | промо-цены WB |
| `PF_OZON_prices` (`149765171`) | daily 00:05 | ok, 2025-04-16; 15077 inserted, 0 mistakes | обычные цены Ozon |
| `PF_OZON_PromoPrices` (`149765170`) | daily 00:10 | ok, 2025-04-16; 21880 inserted, 0 mistakes | промо-цены Ozon |
| `OZON_source` (`149765178`) | daily 00:45 | ok, 2025-04-16; 171519 inserted, 0 mistakes | цены и атрибуты из Ozon |
| `1C_Ref_Assortment` (`149765167`) | daily 00:12 | ok, 2025-04-16; 33378 inserted, 0 mistakes | признак ассортимента |
| `1C_Ref_Style_Variant` (`149765166`) | daily 01:45 | ok, 2025-04-16; 82059 inserted, 0 mistakes | variant/model |
| `PF_YA_prices` (`149765177`) | daily 04:05 | ok, 2025-04-17; 15077 inserted, 0 mistakes | обычные цены Яндекс |
| `PF_YA_PromoPrices` (`149765176`) | daily 04:10 | ok, 2025-04-17; 21898 inserted, 0 mistakes | промо-цены Яндекс |
| `PF_YA_prices Compare` (`149765188`) | daily 00:05 | ok, 0 inserted | раннее сравнение с импортом 04:05 |
| `PF_YA_PromoPrices Compare` (`149765187`) | daily 00:10 | ok, 0 inserted | раннее сравнение с импортом 04:10 |
| `XLS_MAX_wb_price` (`149765168`) | manual | ok, 2025-04-03 | ручной override current price |
| `XLS_MAX_wb_old_price` (`149765169`) | manual | ok, 2025-04-01 | ручной override old price |

В manifest также есть snapshots с повторными временными слотами для PF-цен
WB/Ozon (`01:10/01:15`, `02:45/02:50`) и источниками Ozon/WB около полуночи.
Без live-кабинета нельзя подтвердить, какие из них были активными одновременно,
резервными копиями или этапами перенастройки.

### 4.1. Важное противоречие

`NEW_SKU` snapshots показывают ошибку credentials 2025-04-16, а истории цен
WB/Ozon были закрыты позднее, в мае 2025 года. Это означает только, что в
конкретном старом снимке был сбой. Нельзя переносить его в текущий production и
нельзя считать закрытие Jira доказательством конкретного исправления.

## 5. Ключи сопоставления

| Контур | Ключ/поле | Evidence | Риск |
|---|---|---|---|
| DataBird catalog | EAN13/barcode как `ID товара` | `149765159`; PF/1C snapshots | barcode может отсутствовать/дублироваться |
| PF imports | `barcode`; рядом доступен `sku_article` | attachments `149765163`, `166`, `167`, `170`—`177` | в export UI могла быть иная key formula |
| WB source import | barcode → catalog ID; отдельно WB article | `149765175` | дополнительные barcode в одной WB-card |
| WB price export | WB article, не barcode | `149765159` | объединенная ошибочная карточка не дает разные цены размерам |
| Ozon source import | marketplace article → catalog ID | `149765178` | точная связь с GJ SKU требует проверки |
| MP identifiers | marketplace ID + owner + merged-card ID + size | `165381358` | использование DataBird напрямую не доказано |

ADR описывает эффект WB article-key: если в карточку WB добавлены дополнительные
barcode, которых нет в PF, цена может примениться и к ним через общий артикул.
Обратная сторона — ошибочно объединенные карточки WB требуют ручной обработки.

## 6. Формулы и приоритеты цен

Все правила ниже взяты из чернового ADR `149765159` и исторических config
snapshots. Они не проверены на текущей live-конфигурации.

### 6.1. Общие правила

- promo price имеет приоритет над regular/current PF price;
- Excel override может иметь приоритет над PF;
- canceled/replaced assortment исключается через `Assortment=1`;
- общий `black_list` исключает товар из всех площадок;
- отдельные blacklist-поля исключают товар из конкретной площадки;
- цены PF `<= 1` не должны экспортироваться после `OPSMPC-810`;
- promo imports могут очищать promo field, если товар перестал приходить;
- imports из marketplace могут очищать цену DataBird, если она отсутствует в
  очередном ответе площадки.

### 6.2. Ozon

Приоритет текущей цены:

`XLS_ozon_price > PF promo > PF current`.

Приоритет old price:

`XLS_ozon_old_price > PF old`.

Документированные ограничения:

- PF current ниже 69 поднимается до 69;
- PF old ниже 179 поднимается до 179;
- при слишком малой скидке old price корректируется вверх;
- при скидке около/выше 90% old price корректируется, чтобы пройти ограничение
  площадки;
- export выполняется при отличии calculated current/old от значений Ozon.

Точные ветви формулы задокументированы в `149765159`, но должны быть повторно
сняты из live exporter перед использованием как бизнес-спецификация.

### 6.3. Wildberries

Приоритет текущей цены:

`XLS_MAX_wb_price > PF promo > PF current`.

Приоритет old price:

`XLS_MAX_wb_old_price > XLS_wb_old_price > PF old`.

Дополнительные правила:

- минимумы PF current/old — 69/179;
- рассчитывается процент скидки WB;
- применяется специальное округление процента;
- пропускаются `Assortment=1`, общий blacklist и `bl_WB`;
- отдельные позиции могут быть исключены из DataBird из-за внешнего
  динамического ценообразования;
- export выполняется при отличии price/discount от WB.

Для ошибочно объединенных WB cards используется ручной импорт `WB_MAX`.

### 6.4. Яндекс Маркет

Приоритет current:

`PF promo > PF current`.

Приоритет old:

`XLS_yandex_old_price > PF old`.

Дополнительные правила:

- минимумы current/old — 69/179 при применимости old price;
- old price очищается, когда равен current;
- old price корректируется при слишком маленькой или слишком большой скидке;
- пропускаются price `<=1`, `Assortment=1` и общий blacklist;
- export выполняется при расхождении с current/old Яндекса.

`OPSMPC-639` фиксировал архитектурную проблему: импорт шел с уровня кабинета,
а export — в магазин, поэтому сравнение было невозможно. Задача закрыта
2025-06-02, но описание конкретного решения не найдено.

## 7. Imports from marketplaces

### 7.1. WB

Snapshot `149765175`:

- тип connector — `WILD`;
- карточки каталога не создаются;
- сопоставление — barcode;
- импортируются WB article, current price и discount;
- при отсутствии цены в очередном предложении поле `wb_price` очищается;
- последний записанный запуск имел 13 mistakes на 299040 inserted.

Ошибки отдельных SKU требуют просмотра внутри конкретного import, а не только
общего зеленого статуса.

### 7.2. Ozon

Snapshot `149765178`:

- тип connector — `OZON`;
- сопоставление — article;
- импортируются current/old prices и набор контентных атрибутов: category,
  colors, images, объединение карточки, hashtags, annotation, rich content,
  keywords, model parameters, collection, material, gender, composition,
  season, warranty, care, packaging;
- присутствует поле остатков с названием FBS, но историческая JSONata formula
  выбирает запись с `type="fbo"`.

Последнее — потенциальное несоответствие имени поля и формулы. Без просмотра
live-config нельзя определить, это ошибка, технический компромисс или устаревший
snapshot.

## 8. Error handling, retries и monitoring

### 8.1. Что подтверждено

| Механизм | Evidence | Статус |
|---|---|---|
| Общий state и время последнего запуска в списке imports/exports | `149765159` | documented |
| Counters `inserted`, `mistakes`, duration и state в config snapshots | attachments `149765163`—`188` | historical confirmed |
| Drill-down в import/export для ошибок конкретных SKU | `149765159` | documented |
| PF API логируется в Kibana по аналогии с базовым PF interface | `130141740`, `82015904` | source-side documented |
| Health endpoint DataBird предложено поставить на мониторинг | `OPSMPC-831` | recommendation only |
| Успешный cron `mp-connector` 22/23 июля 2026 | prod logs | confirmed-live |

### 8.2. Что не подтверждено

- retry count, backoff и dead-letter/replay policy;
- автоматический повтор export после ошибки конкретного SKU;
- idempotency guarantees;
- alert threshold по количеству mistakes;
- созданный availability check для DataBird health;
- канал оповещения, on-call и SLA реакции;
- сквозной trace от PF до marketplace;
- dashboard полноты: PF count → DataBird count → accepted marketplace count.

В config snapshots есть `repeat=true`, однако этого недостаточно, чтобы
называть механизм retry: по структуре API import это может быть повтор
пагинации/получения следующих данных.

`OPSMPC-655` содержит пример повторной отправки атрибутов Ozon: ошибка hashtag
исчезла при повторной загрузке. Это операционный случай, а не формализованная
retry policy.

### 8.3. Зафиксированные инциденты/сбои

| Случай | Evidence | Что известно | Что неизвестно |
|---|---|---|---|
| нестабильный доступ из офиса | `OPSMPC-831`, Done 2025-12-24 | локализовался сетевой hop; vendor предложил health monitoring | создан ли монитор и устранена ли первопричина |
| стерлись первоначальные цены Ozon 8–12 августа | `OPSMPC-857`, Done 2025-09-23 | вручную перезагрузили 8 августа и два месяца PF history | root cause и защита от повторения |
| price=1 мог уходить в marketplace | `OPSMPC-810`, Done 2025-08-09 | потребовалось изменить filters | live formula и regression check |
| Ozon hashtag intermittently failed | comment `OPSMPC-655`, 2025-04-28 | повторный upload прошел | частота и platform response |
| `NEW_SKU` wrong credentials | config snapshots `149765163/164`, 2025-04-16 | оба исторических import state failed | когда/как исправлено |

## 9. Ручные операции

### 9.1. Ручная корректировка данных

ADR разрешает:

- менять атрибуты и цены через DataBird UI;
- загружать Excel overrides;
- применять отдельные overrides current/old price;
- использовать `WB_MAX` для ошибочно объединенных WB cards;
- вести общий и marketplace-specific blacklist.

### 9.2. Контроль после изменения конфигурации

После редактирования import/export оператор должен проверить schedule:
по ADR он может автоматически переключиться в `manual`.

Это важный операционный риск: успешное изменение mapping может незаметно
остановить регулярный запуск.

### 9.3. Очистка каталога

ADR описывает ручную процедуру при приближении к лимиту каталога `XL200000`:

1. получить даты вывода товаров от online planning;
2. выбрать товары, выведенные более полугода назад у всех площадок;
3. найти пересечение списков;
4. загрузить временный признак в поле комментария;
5. проверить отсутствие товаров в актуальных PF price imports;
6. сохранить удаляемый набор в Excel;
7. удалить позиции с возможностью обратной загрузки.

`OPSMPC-627` подтверждает, что задача удаления старых моделей возникла на Ozon,
но относится ко всем площадкам из-за общего каталога.

### 9.4. Восстановление истории

`OPSMPC-857` фиксирует ручной replay:

- после потери первоначальных цен Ozon перезагрузили snapshot на дату;
- затем загрузили историю PF за два месяца.

Регулярный автоматический механизм replay не найден.

## 10. Ownership и support

### 10.1. Что видно из источников

- epic `OPSMPC-549`, большинство дочерних задач и координационная задача
  `OPSMPC-219` назначены одному специалисту направления маркетплейсов;
- задачи настройки формул WB/Ozon (`OPSMPC-557`, `622`) прямо указывают
  совместную работу с vendor support DataBird;
- `OPSMPC-831` показывает взаимодействие внутреннего специалиста, администраторов
  и vendor support по доступности.

### 10.2. Чего нет

- формального RACI;
- резервного владельца;
- 1st/2nd/3rd line support;
- графика контроля;
- SLA DataBird и marketplace APIs;
- владельцев formula approval, manual override и catalog cleanup;
- владельца security hygiene конфигураций.

Поэтому Jira assignment можно считать признаком фактической координации, но не
доказанным устойчивым operating model.

## 11. Карточки товаров

### 11.1. Target design

Draft `149768494` описывает:

`PLM + 1C + media → PIM ENSI → approval → feed/API → DataBird mapping →
WB/Ozon/Yandex`.

Планировались:

- автоматическое получение медиа с сетевого диска;
- связывание с карточкой в PIM;
- обогащение PLM/1C;
- ручное заполнение недостающих marketplace attributes;
- approval в PIM;
- feed по расписанию или ручному запуску;
- преобразование и отправка через DataBird.

Это TO-BE, а не подтвержденный текущий процесс.

### 11.2. Живой upstream: `mp-connector`

GitLab project `820` подтверждает отдельный Go-сервис:

- `GET /api/v1/updated-products` отдает обновленные product/SKU данные ENSI PIM;
- internal cron `plm_modelcolor_sync` синхронизирует предыдущие 24 часа;
- default `SYNC_CRON` — `0 5 * * *`;
- commits `ff10bb7c` и `501b154b` добавляли синхронизацию 1C/PLM, WebAPI upsert и
  scheduler;
- HEAD `3b6dba3e` датирован 2025-12-23.

Runtime на 2026-07-23:

- deployment `prod/mp-connector-master-ms` — `1/1/1` desired/ready/available;
- running pod использует image `master-3b6dba3e`;
- service `80 → 8080`;
- ingress публикует только `/api/v1/updated-products` на TLS host
  `marketplace-connector.gloria-jeans.ru`;
- `SYNC_CRON` override не обнаружен, следовательно используется default;
- logs содержат Running/Completed 2026-07-22 и 2026-07-23; последний запуск
  завершился примерно за 13 секунд.

**Что это подтверждает:** production-компонент подготовки/выдачи данных жив,
его internal daily sync выполняется.

**Чего это не подтверждает:** что DataBird вызвал endpoint, получил response,
применил mapping и обновил marketplace card.

Поиск `updated-products`/host в доступном ENSI log target за 30 дней не дал
результатов. В этом target нет гарантированного ingress/access-log coverage,
поэтому ноль результатов не является доказательством отсутствия вызовов.

### 11.3. Ozon

| Evidence | Состояние |
|---|---|
| `OPSMPC-691` architecture | In Progress, updated 2025-05-19 |
| `OPSMPC-697` products | Implementation, updated 2026-03-05 |
| comment `OPSMPC-697`, 2025-06-02 | часть attributes выгружалась из DataBird в Ozon |
| comment `OPSMPC-697`, 2026-03-05 | pilot exporter с formulas на завершающей стадии; далее сравнение с consolidated Excel template |
| `OPSMPC-834` mapping formulas | In Progress, updated 2026-03-17 |
| `OPSMPC-655` rating attributes | In Progress, updated 2026-03-17 |

Вывод: partial/pilot integration подтверждена, full production acceptance —
нет.

### 11.4. Wildberries

| Evidence | Состояние |
|---|---|
| `OPSMPC-862` products | Implementation, updated 2026-03-05 |
| comment `OPSMPC-862`, 2026-03-05 | formulas consolidated template переводятся в JSONata |
| `OPSMPC-863` mapping formulas | Development, updated 2025-12-18 |

Вывод: mapping implementation подтверждена как незавершенная; successful
production export карточек не подтвержден.

### 11.5. Яндекс Маркет

| Evidence | Состояние |
|---|---|
| `OPSMPC-717` products | Suspended, updated 2025-09-25 |
| `OPSMPC-718` architecture | New, updated 2025-05-27 |
| `OPSMPC-719` rating attributes | New, updated 2025-05-27 |

Вывод: автоматизация карточек через DataBird не подтверждена и по Jira
приостановлена.

## 12. Documented vs live-confirmed

| Capability | Documented | Runtime evidence | Итог |
|---|---|---|---|
| PF regular/promo import в DataBird | да | нет текущего DataBird run | high, not live |
| Marketplace price import | да, snapshots WB/Ozon | нет текущего DataBird run | high, historical |
| Price compare/export WB/Ozon/Yandex | да; Jira Done | нет marketplace acceptance | high, not live |
| Manual Excel overrides | да | не проверен текущий кабинет | documented |
| Per-SKU error drilldown | да | не проверен UI | documented |
| DataBird health monitoring | recommendation | monitor/alert не найден | unknown |
| `mp-connector` internal sync | код + config | successful prod logs 22/23 July | confirmed-live |
| DataBird call to `updated-products` | target design | нет reliable access evidence | unknown |
| Ozon full card export | partial/pilot | нет end-to-end proof | not confirmed |
| WB full card export | implementation | нет end-to-end proof | not confirmed |
| Yandex card export | suspended | нет | not confirmed |

## 13. Противоречия и слабые места

1. **Draft ADR vs completed price stories.** Техническое описание осталось
   черновиком, хотя Jira считает price stories завершенными.
2. **Epic stale.** `OPSMPC-549` открыт, но не обновлялся после сентября 2025;
   дочерние product stories обновлялись в марте 2026.
3. **Config snapshots old.** Они дают точную операционную механику апреля 2025,
   но не показывают кабинет июля 2026.
4. **Yandex level mismatch.** Issue закрыта без описания решения.
5. **Ozon stock field naming.** Поле названо FBS, formula выбирала `fbo`.
6. **Service live, consumer unknown.** `mp-connector` работает, но DataBird
   consumption не подтвержден.
7. **Нет сквозного SLO.** Отдельно видны PF logs, DataBird UI-status и internal
   cron, но нет единого контроля до acceptance marketplace.
8. **Security hygiene.** В исторических конфигурационных вложениях обнаружены
   встроенные учетные реквизиты. Значения в research не перенесены. Требуются
   удаление/ограничение исходных attachments и ротация, если реквизиты еще
   действуют.

## 14. Gap matrix

| Область | Документировано | Live подтверждено | Gap | Риск |
|---|---|---|---|---|
| imports inventory | names/config snapshots 2025 | нет | нет текущего списка enabled imports | пропущенный источник |
| exports inventory | formulas/narrative | нет | нет текущего списка exporters/accounts | неизвестный blast radius |
| schedules | historical exact times | только `mp-connector` cron | DataBird schedule неизвестен | задержка цен/контента |
| matching | barcode/article rules | нет sample trace | нет проверки 1 SKU end-to-end | mislink карточки |
| formula approval | ADR rules | нет versioned approval | кто утвердил live formula неизвестно | неверная цена |
| retries | отдельные ручные повторения | нет | policy отсутствует | тихая потеря обновлений |
| monitoring | UI/Kibana/health recommendation | cron logs | нет alert routing и completeness | зеленый компонент, плохой бизнес-результат |
| manual overrides | Excel/UI documented | нет audit sample | owner/expiry/audit неизвестны | override остается навсегда |
| catalog cleanup | manual runbook-like text | нет latest execution | нет owner/frequency | лимит каталога |
| Ozon cards | partial/pilot | endpoint upstream live | нет marketplace acceptance | неполные карточки |
| WB cards | JSONata implementation | endpoint upstream live | нет marketplace acceptance | ручной fallback |
| Yandex cards | target design | нет | suspended | автоматизации нет |
| ownership | Jira assignee/vendor interaction | нет RACI | single-person dependency | operational fragility |
| credentials | старые configs содержат auth material | validity unknown | rotation/cleanup | unauthorized access |

## 15. Неизвестно

- Список enabled imports/exports сегодня.
- Текущие schedule и timezone DataBird.
- Дата и результат последних 30 запусков каждого job.
- Какие кабинеты, магазины, юрлица и `StoreIDD` подключены.
- Текущая версия formulas и кто ее утвердил.
- Есть ли automatic retry и сколько попыток.
- Есть ли health, business completeness и error-rate alerts.
- Кто ежедневно разбирает SKU mistakes.
- Какой срок действия у manual override и blacklist.
- Когда последний раз чистился catalog.
- Вызывает ли DataBird `updated-products`.
- Какие Ozon/WB cards реально прошли целиком.
- Почему Yandex product stream приостановлен и есть ли дата возобновления.
- Исправлены ли найденные security issues.

## 16. Вопросы владельцам

1. Можно ли выгрузить read-only inventory всех enabled imports/exports без
   credentials?
2. Какие jobs считаются production и какой у них SLA?
3. Где хранится runbook при `mistakes > 0`, failed state и credential error?
4. Кто подтверждает корректность formula после изменения правил площадки?
5. Кто владелец Excel overrides, blacklist и WB_MAX, каков их expiry?
6. Есть ли alert на DataBird health и кому он приходит?
7. Есть ли ежедневная сверка количества PF SKU, DataBird proposals и accepted
   marketplace updates?
8. Можно ли показать один price trace и один card trace для Ozon/WB?
9. Какие consumer/access logs подтверждают вызов `updated-products` DataBird?
10. Как оформлена vendor escalation и SLA?

## 17. Acceptance gates

### Gate DB-OPS-1 — Current configuration inventory

- read-only export всех enabled imports/exports;
- account/store/legal entity;
- schedule + timezone;
- mapping key;
- last successful/failed run;
- counters за 30 дней;
- без credentials.

### Gate DB-OPS-2 — Price end-to-end

Для одного SKU каждой площадки:

1. PF regular/promo source;
2. DataBird import;
3. calculated current/old;
4. export payload/result;
5. accepted marketplace value;
6. timestamps и error-free evidence.

### Gate DB-OPS-3 — Monitoring and recovery

- health check существует и алерт доставляется;
- defined thresholds для failed/mistakes/staleness;
- retry/replay runbook;
- owner и SLA;
- тестовый recovery выполнен без ручного изменения исходной цены.

### Gate DB-OPS-4 — Ozon cards

- один approved PIM product;
- DataBird вызвал `updated-products`;
- mapping/exporter version зафиксирована;
- Ozon принял card и media;
- errors/warnings сохранены;
- результат сравнен с consolidated Excel template.

### Gate DB-OPS-5 — WB cards

- JSONata mapping покрывает обязательные attributes;
- один approved product прошел в WB;
- объединение размеров/цветов проверено;
- barcode/article mapping подтвержден;
- marketplace acceptance сохранен.

### Gate DB-OPS-6 — Security

- старые config attachments очищены или доступ ограничен;
- обнаруженные credentials проверены и при необходимости ротированы;
- secrets вынесены из экспортируемой конфигурации;
- аудит доступа зафиксирован.

## 18. Кандидаты в EVIDENCE-LEDGER

Оркестратору предлагается рассмотреть:

- **MP-DB-OPS-01** — price contour подробно документирован, но current DataBird
  runs не подтверждены; `149765159`, `550/620/636`; `high`.
- **MP-DB-OPS-02** — config attachments содержат historical exact schedules и
  counters апреля 2025; `149765163`—`188`; `confirmed-source/historical`.
- **MP-DB-OPS-03** — `mp-connector` и internal daily sync live на 2026-07-23,
  но DataBird consumer неизвестен; project `820`, K8s deployment/logs;
  `confirmed-live` только для upstream.
- **MP-DB-OPS-04** — Ozon card flow partial/pilot, WB mapping in development,
  Yandex suspended; `697/834/862/863/717`; `high`.
- **MP-DB-OPS-05** — formal retry, alert routing, SLA и RACI не найдены;
  `149765159`, `831`; `unknown/gap`.
- **MP-DB-OPS-06** — manual Excel overrides, blacklist, cleanup и replay входят
  в фактическую operating model; `149765159`, `627`, `857`;
  `confirmed-source`.
- **MP-DB-OPS-07** — исторические attachments содержат credential material;
  `149765159`; `confirmed-source/security-gap`, значения не копировать.

## 19. Resume pointer

Следующий шаг должен быть не очередным поиском проектных документов, а
read-only operational evidence:

1. получить sanitized inventory DataBird imports/exports;
2. снять последние 30 запусков и SKU errors;
3. найти consumer/access evidence вызова `updated-products`;
4. провести по одному price trace WB/Ozon/Yandex;
5. провести один card trace Ozon и один WB;
6. проверить наличие health/business alerts и recovery runbook;
7. подтвердить remediation обнаруженных credentials.

После этого можно обновить статусы `high` до `confirmed-live` либо зафиксировать
точные эксплуатационные gaps.
