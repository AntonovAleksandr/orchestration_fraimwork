# Выгрузка сверки заказов в 1С ЦБР — AS-IS и варианты переработки

**Дата:** 2026-07-12  
**Статус:** MVP-дизайн согласован, реализация не начата  
**Контур AS-IS:** Integration Service → OMS Order API → 1С ЦБР  
**Контур TO-BE:** Kubernetes CronJob → `ecom-exporter` → OMS read replica → 1С ЦБР  
**Связанный инцидент:** trace `dbdc04ca-ec9a-4ea0-be45-9c5ecc0080b6`  
**Историческая задача:** Jira `OPSOMN-14584` — «[Prod] Не выгружается файл сверки для ЦБР», статус «Приостановлено» на 2026-07-10.

## 1. Цель исследования

Разобрать фактический контракт CSV и ответить на вопросы:

1. Какие данные действительно нужны 1С ЦБР и что означает каждая колонка?
2. Где находится источник истины каждого поля?
3. Почему текущий процесс вынужден обходить большой объём заказов и истории?
4. Можно ли заменить PHP/master-child механику сервисом на Go?
5. Как перенести выгрузку в расширяемый Go-сервис, не изменяя внешнюю OMS?

Production-код на этой стадии не меняется. В документе зафиксирован согласованный MVP-дизайн.

## 2. Краткий вывод текущей стадии

- CSV содержит **20 колонок**. Все они технически выводятся из таблиц одной БД OMS Order: `order_t`, `shipping`, `item`, `payment`, `order_custom_attribute`, `custom_attribute`, `status_history`.
- Текущий `/order/list/full` возвращает существенно больше данных, чем использует CSV: Integration запрашивает также `customer`, `marketing`, `packages` и другие секции.
- За окно 60 дней суммарный объём трёх наборов до межнаборной дедупликации составляет порядка **171,8 тыс. заказов**: `12 789` SFS, `111 173` reserve-in-store и `47 872` pickup-in-store. Для последней группы в CSV проходит около `37 733` заказов, но API сначала читает более широкий набор.
- В окне находится около **487 тыс. активных item-строк**. При page size `50` REST-путь неизбежно создаёт тысячи запросов и большое число промежуточных DTO/JSON-объектов.
- Самый тяжёлый «костыль с историей» нужен не для формирования дат CSV. История `DELIVERING` предварительно загружается, чтобы отфильтровать третью группу заказов. В SQL это выражается обычным `EXISTS`/join к `status_history`.
- OMS является внешней системой и не может быть доработана в рамках проекта. Новый сервис читает её физические таблицы через существующую read-only реплику; адрес реплики и credentials задаются только через env/Secret.
- Выбран отдельный Go-сервис `ecom-exporter`, запускаемый как конечная Kubernetes Job. Kubernetes CronJob владеет расписанием; приложение выполняет одну выбранную выгрузку и завершается.
- MVP обязан повторить текущую выгрузку 1:1. Спорные, ошибочно названные и дублирующиеся поля не исправляются до завершения миграции и подтверждения бизнес-процесса.
- Выбран пакетный способ чтения: базовые заказы и связанные данные загружаются пакетами отдельными SQL-запросами, затем маппятся в Go. Один монолитный SQL в MVP не используется.
- Обязателен `--dry-run`; сравнение старого и нового CSV выполняется отдельным миграционным скриптом.

## 3. AS-IS: текущий поток

```text
transfer:orders:recon cbr
  ├─ initProcessId() и state в Integration.order_filter
  ├─ 20 интервалов по 3 дня:
  │    GET OMS /order/status/history/find?statusId=DELIVERING
  │    → сохранить order_id в order_filter
  ├─ создать recon-temp-<process_id>.csv
  └─ многократно shell_exec transfer:orders:recon:child
       ├─ три набора фильтров
       ├─ POST OMS /order/list/full, page size 50
       ├─ UNIQUE/DELIVERING проверки через Integration DB
       ├─ PHP mutation полного OMS DTO
       ├─ построчная запись CSV
       ├─ restart при memory threshold
       └─ POST CSV → /api/Starfish/1CCBROrdersList
```

### 3.1 Три набора заказов

| Набор | Фильтр OMS | Дополнительная проверка |
|---|---|---|
| SFS | `shipping.fulfillmentTypeId = sfs` | нет |
| Reserve in store | `shipping.deliveryTypeId = reserveinstore` | нет |
| Pickup in store | `fulfillment = fulfillment`, `deliveryType = pickupinstore` | заказ должен присутствовать в истории `DELIVERING` за окно |

Окно задаётся `EXCHANGE_RECON_ORDER_ORDER_DATE_CREATED_OFFSET_DAYS`, default `60` дней.

### 3.2 Почему механизм дорогой

1. OMS API сначала выбирает страницу `order_t`, затем отдельными batch-запросами собирает shipping, attributes, items, payments и другие displayable sections.
2. Integration запрашивает все displayable sections, хотя CSV использует только часть.
3. Page size равен 50 — на текущем объёме это тысячи HTTP round trips.
4. Для каждого заказа Integration выполняет проверки/insert в `order_filter` для дедупликации и фильтра `DELIVERING`.
5. Master-child состояние, временный файл, memory restarts и локи компенсируют стоимость получения полного DTO, но сами добавляют новые классы отказов.
6. Фильтр `DELIVERING` реализован как предварительная выгрузка истории и последующий перебор заказов, хотя на уровне БД это одна semi-join операция.

## 4. Контракт CSV: field-by-field

| # | Колонка CSV | Фактическое вычисление AS-IS | Минимальный источник OMS DB | Вопрос/риск |
|---:|---|---|---|---|
| 1 | `code` | `order.clientOrderId` | `order_t.client_order_id` | Вероятно, бизнес-номер заказа. |
| 2 | `totalPrice` | `order.totalCost` | `order_t.total_cost` | Нужно подтвердить рубли/копейки и скидки. |
| 3 | `deliveryPrice` | `shipping.deliveryCost` | `shipping.delivery_cost` | Это расчётная, не `actual_delivery_cost`. |
| 4 | `totalProduct` | число неотменённых items + 1, если доставка платная | `item` + `shipping.delivery_cost` | Доставка считается «товарной строкой» — подтвердить контракт 1С. |
| 5 | `products` | число items без `canselationReasonText` | `item` + legacy `custom_attribute` | Следует сравнить с `item_status_id`/cancellation columns. |
| 6 | `redeemedProduct` | `products`, только если весь заказ `COMPLETED`, иначе 0 | `order_t.status_id` + item count | Не поддерживает частичный выкуп. Возможно, неверная семантика. |
| 7 | `checked_valid` | дата создания заказа, формат без timezone | `order_t.date_time_created` | Название не соответствует значению. |
| 8 | `datePayment` | prepaid: `timePaid` первого подходящего charged debit; COD: дата `COMPLETED` | `payment` или status-date | Нужны правила при нескольких платежах. |
| 9 | `datePicked` | custom attr `orderPickupDateTime` | `order_custom_attribute` | Можно ли использовать `status_history(ORDER_PICKUP)`? |
| 10 | `dateCreateDelivered` | custom attr `orderCompletedDateTime` | `order_custom_attribute` | Дублирует #12. |
| 11 | `dateCancelled` | custom attr `orderCancelledDateTime` | `order_custom_attribute` | First/last transition и повторные статусы не определены. |
| 12 | `orderDateDelivered` | custom attr `orderCompletedDateTime` | `order_custom_attribute` | Полный дубль #10 в AS-IS. |
| 13 | `dateLost` | custom attr `orderLostDateTime` | `order_custom_attribute` | Редкое поле; проверить обязательность. |
| 14 | `datePaymentReturn` | для prepaid с RETURNED payment берётся **дата отмены заказа** | `payment` + cancelled date | Не является временем возврата платежа. Высокий риск смысловой ошибки. |
| 15 | `paymentType` | `prepaid → ONLINE_PAYMENT`, `cod → CASH_PAYMENT` | `order_t.payment_type_id` | Явный mapping-контракт. |
| 16 | `deliveryTypeId` | rule-map по delivery type + fulfillment + carrier | `shipping` | Сейчас поддержано только шесть комбинаций. |
| 17 | `orderStatus` | текущий статус заказа | `order_t.status_id` | Snapshot на момент выгрузки. |
| 18 | `createDatePayment` | то же значение, что `datePayment` | `payment`/status-date | Полный дубль #8 в AS-IS. |
| 19 | `dateDelivering` | custom attr `orderDeliveringDateTime` | `order_custom_attribute` | История уже есть в `status_history`. |
| 20 | `sfs` | `shipping.fulfillmentTypeId == sfs` | `shipping.fulfillment_id` | Boolean `1/0`. |

### 4.1 Delivery mapping AS-IS

| OMS delivery | fulfillment | carrier | CSV code |
|---|---|---|---|
| `pickupinstore` | `fulfillment` | `gloriajeans` | `CC` |
| `reserveinstore` | любой | пусто | `CR` |
| `delivery` | `sfs` | `cdek` | SFS CDEK code |
| `pickup` | `sfs` | `pickpoint` | SFS PickPoint code |
| `pickup` | `sfs` | `russianpost` | SFS Russian Post code |
| `delivery` | `sfs` | `gjexpress` | SFS GJ Express code |

Новые/другие перевозчики дают пустой `deliveryTypeId`, пока rule-map не обновлён.

## 5. Что показала OMS DB

Источник: Buddy target `oms-awg-order-prod`, только read-only SELECT, 2026-07-10/12.

### 5.1 Физические источники

| Данные | Таблица/ключ |
|---|---|
| заказ | `order_t.id`, `order_t.order_id` |
| доставка | `shipping.order_id → order_t.id` |
| позиции | `item.order_fk → order_t.id` |
| платежи | `payment.order_id → order_t.order_id` |
| status-date атрибуты | `order_custom_attribute.order_id → order_t.order_id` |
| общие item attributes | `custom_attribute(owner='Item', object_id=item.item_id)` |
| история статусов | `status_history.order_id → order_t.order_id` |

Все 20 CSV-полей находятся в одном Postgres-контуре; cross-service join для формирования текущего CSV не требуется.

### 5.2 Объём за 60 дней

| Метрика | Значение snapshot |
|---|---:|
| SFS orders | 12 789 |
| reserve-in-store orders | 111 173 |
| pickup-in-store, просматриваемые текущим фильтром | 47 872 |
| pickup-in-store с `DELIVERING`, реально проходящие фильтр | 37 733 |
| joined order/shipping rows | 192 721 |
| активные item rows | около 487 000 |

Числа являются operational snapshot, а не SLA/постоянной оценкой.

### 5.3 Status-date custom attributes за 60 дней

| Attribute | Orders |
|---|---:|
| `orderPickupDateTime` | 171 569 |
| `orderDeliveringDateTime` | 65 715 |
| `orderCompletedDateTime` | 109 723 |
| `orderCancelledDateTime` | 73 373 |
| `orderLostDateTime` | 12 |

Следующий обязательный шаг — сравнить значения этих атрибутов с `status_history` и определить правило first/last transition. Менять источник дат на историю без parity-проверки нельзя.

## 6. Рассмотренные архитектурные варианты

### Вариант A — Go exporter через существующий OMS API

Сохраняет сервисную границу OMS, но также сохраняет REST pagination, расширенные DTO и дорогой путь получения истории. Переписывание PHP на Go устранило бы часть эксплуатационных ошибок, но не основную причину неэффективности.

### Вариант B — один большой SQL к OMS replica

Минимизирует число запросов, но создаёт сложный запрос с риском размножения строк на `items × payments × history`. Такой контракт трудно сопоставлять с текущим PHP-mutator и диагностировать при расхождении.

### Вариант C — пакетная сборка в Go (**выбран**)

1. Одним запросом получить базовые заказы по трём текущим группам.
2. Пакетами получать позиции, оплаты, атрибуты и историю статусов.
3. Собирать export-модель в Go и последовательно писать CSV.

Вариант убирает OMS API, page size 50, JSON и N+1, но сохраняет явные и тестируемые правила текущего PHP-mutator. После доказанного паритета отдельные части можно оптимизировать без изменения контракта.

## 7. Согласованный TO-BE

```text
Kubernetes CronJob
       │ запускает Job/Pod
       ▼
ecom-exporter --type=export-cbr-recon [--dry-run]
       │
       ├─ фиксирует cutoff_time и run_id
       ├─ читает базовые заказы из OMS read replica
       ├─ пакетно обогащает items/payments/attributes/status history
       ├─ повторяет текущий CBR mapper 1:1
       └─ последовательно пишет локальный временный CSV
                    │
                    ├─ dry-run → статистика + SHA-256 → exit 0
                    └─ normal → POST WebAPI ЦБР, до 3 попыток → exit 0/1
```

### 7.1 Границы ответственности

**Kubernetes CronJob:**

- расписание;
- `concurrencyPolicy: Forbid`;
- запуск и lifecycle Job/Pod;
- хранение статуса завершившихся Job.

**`ecom-exporter`:**

- выбор типа выгрузки;
- чтение источника;
- бизнес-правила отбора и маппинга;
- CSV;
- отправка, три попытки и exit code;
- структурированные логи.

Сервис не содержит HTTP server, scheduler, фоновые worker-ы и постоянное состояние.

### 7.2 CLI-контракт

```bash
ecom-exporter --type=export-cbr-recon
ecom-exporter --type=export-cbr-recon --dry-run
```

Новые выгрузки подключаются новыми значениями `--type` и отдельными bounded contexts. CLI обязан отклонять неизвестный тип до подключения к внешним системам.

### 7.3 Доменная структура

Структура повторяет шаблон существующих сервисов `platform-new`: `domains + adapters + platform + app/wire`.

```text
ecom-exporter/
├── cmd/ecom-exporter/main.go
├── internal/
│   ├── app/
│   │   ├── app.go
│   │   └── wire/export_cbr.go
│   ├── domains/
│   │   └── cbrreconciliation/
│   │       ├── types.go
│   │       ├── ports.go
│   │       ├── service.go
│   │       ├── mapper.go
│   │       └── *_test.go
│   ├── adapters/
│   │   └── cbrreconciliation/
│   │       ├── oms_repository.go
│   │       ├── cbr_client.go
│   │       └── temp_file.go
│   └── platform/
│       ├── config/
│       ├── logger/
│       ├── storage/
│       └── retry/
├── scripts/compare-cbr/
└── docs/
```

Домен определяет consumer-defined порты источника и назначения. Домен не импортирует PostgreSQL, HTTP, env/config или composition root. Сериализация 20 колонок является частью CBR-контракта и остаётся рядом с доменом; адаптер временного файла отвечает только за I/O.

## 8. Требования MVP

### 8.1 Строгий функциональный паритет

До переключения запрещено исправлять семантику текущей выгрузки. Новый сервис обязан сохранить:

- окно 60 дней;
- три текущие группы заказов;
- проверку `DELIVERING` для `fulfillment + pickupinstore`;
- правила дедупликации;
- 20 колонок, их порядок и CSV-формат;
- текущие правила вычисления каждого значения;
- текущие дубли и спорные значения, включая `checked_valid`, `datePaymentReturn`, `datePayment/createDatePayment` и `dateCreateDelivered/orderDateDelivered`;
- endpoint, content type и способ авторизации ЦБР.

Любые функциональные исправления допускаются отдельными изменениями после миграции и подтверждения бизнес-процесса.

### 8.2 Выполнение Job

1. Валидировать CLI и обязательные env-переменные.
2. Рассчитать один `cutoff_time` и создать `run_id`.
3. Открыть read-only соединение с указанной через env OMS replica.
4. Получить базовые заказы и обрабатывать их ограниченными пакетами.
5. Пакетно загрузить связанные данные и сформировать export-модели.
6. Последовательно записать CSV без удержания всей выгрузки в памяти.
7. Рассчитать row count, размер и SHA-256.
8. В `--dry-run` не обращаться к ЦБР.
9. В normal mode выполнить до трёх попыток отправки с backoff.
10. Завершиться с `0` только после полного успеха; при окончательной ошибке вернуть ненулевой exit code.

### 8.3 Временный CSV

MVP сохраняет текущую семантику: локальный временный файл создаётся внутри Job, отправляется и удаляется после успеха. S3/MinIO, архив выгрузок и production-команда повторной отправки не входят в MVP.

### 8.4 Логирование

Все этапы и три HTTP-попытки логируются структурированно через общий GJ Go logger. Обязательные безопасные поля: `run_id`, `export_type`, `dry_run`, этап, длительность, номер/размер пакета, row count, размер файла, SHA-256, номер HTTP-попытки, HTTP status и категория ошибки.

Запрещено логировать DSN, credentials, Bearer token, содержимое CSV и персональные данные заказа. Категории ошибок:

- `configuration_error`;
- `oms_connection_error`;
- `oms_query_error`;
- `mapping_error`;
- `csv_write_error`;
- `cbr_auth_error`;
- `cbr_transport_error`;
- `cbr_response_error`.

Prometheus-метрики и alert rules не входят в MVP, но структура логов должна позволять добавить мониторинг без переработки доменной логики.

## 9. Проверка паритета и rollout

Отдельный миграционный скрипт сравнивает старый и новый CSV после нормализации порядка строк. Он не является production-командой `ecom-exporter`.

Скрипт показывает:

- отсутствующие и лишние заказы;
- дубликаты;
- различия по каждой из 20 колонок;
- итоговое количество строк и статистику по группам.

Порядок переключения:

1. Зафиксировать одинаковый `cutoff_time` для обоих путей.
2. Получить reference CSV текущей реализации.
3. Запустить `ecom-exporter --type=export-cbr-recon --dry-run`.
4. Сравнить нормализованные CSV; разобрать каждое расхождение.
5. Выполнить несколько последовательных параллельных прогонов.
6. Провести один контролируемый production-запуск нового экспортёра.
7. Получить подтверждение полного бизнес-процесса со стороны ЦБР.
8. Отключить старую Cron-команду Integration, но не удалять её до завершения стабилизации.

Rollback: отключить новый CronJob и вернуть расписание старой команды.

Критерий готовности: совпадают набор заказов и значения всех 20 полей, а ЦБР подтверждает успешное прохождение процесса.

## 10. Стратегия тестирования

- unit-тесты mapper для 20 колонок и всех ветвей оплаты/статусов;
- тесты шести правил `deliveryTypeId`;
- тесты трёх групп отбора и дедупликации;
- CSV-тесты заголовка, порядка, escaping, дат и пустых значений;
- repository-тесты SQL на подготовленной PostgreSQL-схеме;
- тесты ЦБР-клиента: успех, HTTP error, timeout, три попытки;
- тест `--dry-run`, доказывающий отсутствие обращения к destination;
- boundary test, запрещающий домену импортировать `app`, `platform` и конкретные адаптеры.

## 11. Риски, которые нельзя потерять при переписывании

| Риск | Почему важен | Проверка/защита |
|---|---|---|
| Семантический drift | Названия колонок уже расходятся с фактическими значениями | Утвердить data contract с 1С/финансами |
| Snapshot consistency | Заказ, items, status и payment могут измениться между запросами | Repeatable-read snapshot либо export watermark |
| Replica lag | Свежие статусы могут не попасть в файл | Явный freshness SLA и lag metric |
| Нагрузка на OMS | 60-дневный join может задеть primary | Только replica, EXPLAIN ANALYZE, индексы |
| История статусов | У заказа могут быть повторные переходы | Зафиксировать first/last/actual rule per field |
| Частичный выкуп | AS-IS сводит `redeemedProduct` к статусу заказа | Проверить требование 1С и item statuses |
| Платежные возвраты | AS-IS подставляет cancellation date | Согласовать реальный payment return timestamp |
| Дедупликация | Три набора могут пересекаться | SQL `UNION`/business priority + unique order key |
| Повторная отправка | 1С может принять файл, а клиент не получить ответ | В MVP: три попытки и явные логи; идемпотентность остаётся последующим улучшением |
| Изменение схемы OMS | Сервис зависит от физических таблиц внешней системы | Repository contract tests, startup validation, controlled rollout |

## 12. Evidence ledger

| ID | Finding | Confidence | Evidence |
|---|---|---|---|
| CBR-01 | Падение после process ID 100 вызвано ошибкой query-builder order в `initProcessId()` | Confirmed | prod logs; `OrderFilterRepository.php:20-22` |
| CBR-02 | Повторный child `100` отправил пустое HTTP body | Confirmed | trace `dbdc04ca-ec9a-4ea0-be45-9c5ecc0080b6` |
| CBR-03 | CSV имеет ровно 20 колонок | Confirmed | `CbrReconCsvConverter.php` |
| CBR-04 | Integration запрашивает лишние extended sections OMS | Confirmed | `OmsClient/Clients/Client.php:getOrders()` |
| CBR-05 | `DELIVERING` history используется как фильтр третьего набора, а не как источник большинства CSV-дат | Confirmed | `CbrReconService.php`, mutator field logic |
| CBR-06 | Все текущие поля технически доступны в OMS Order DB | High | live information_schema + local entity/repository code |
| CBR-07 | `dateCreateDelivered=orderDateDelivered`; `datePayment=createDatePayment` | Confirmed | `CbrReconOrderMutator.php` |
| CBR-08 | `datePaymentReturn` использует cancellation date, а не payment return time | Confirmed | `CbrReconOrderMutator.php` |
| CBR-09 | Прямой SQL существенно сократит data path | High | live volumes + API implementation; benchmark ещё не выполнен |
| CBR-10 | Confluence предписывает per-order вызовы status history для status-date полей | Confirmed | Confluence page `74155886`, version 23 |
| CBR-11 | OMS нельзя дорабатывать; доступна read-only replica | Constraint | подтверждено владельцем eCommerce-контура |
| CBR-12 | Выбран пакетный Go exporter как конечная Kubernetes Job | Decision | согласованный дизайн в этом документе |

## 13. Отложенные вопросы после миграции

Эти вопросы не блокируют MVP, потому что первая версия обязана повторять AS-IS:

1. Кто формально утверждает изменения CSV-контракта после миграции?
2. Следует ли исправлять семантику `redeemedProduct`, `checked_valid` и `datePaymentReturn`?
3. Можно ли удалить дублирующиеся колонки в следующей версии контракта?
4. Нужны ли новые carrier combinations в `deliveryTypeId`?
5. Требуются ли S3/MinIO, журнал запусков и безопасная ручная переотправка?
6. Есть ли у ЦБР возможность идемпотентного приёма по run ID/checksum?
7. Какие Prometheus-метрики и alert rules должны сопровождать CronJob?

## 14. Следующие стадии

1. Подготовить implementation plan без создания production-кода.
2. Создать отдельный репозиторий `platform-new/ecom-exporter` по принятому Go-шаблону.
3. Реализовать walking skeleton CLI и boundary tests.
4. Реализовать CBR domain, OMS adapters и dry-run.
5. Создать отдельный миграционный CSV comparator.
6. Провести parity-прогоны и безопасный query benchmark на OMS replica.
7. Провести контролируемый production rollout и только затем отключить старую Cron-команду.

## 15. Resume pointer

MVP-дизайн согласован. Реализация не начата.

Продолжать с детального implementation plan для `platform-new/ecom-exporter`, сохраняя жёсткий запрет на изменение бизнес-семантики текущей CBR-выгрузки до подтверждённого parity и успешного end-to-end прогона.
