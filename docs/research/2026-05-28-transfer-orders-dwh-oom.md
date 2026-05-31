# `transfer:orders:dwh` OOM — исследование и план решения

**Дата:** 2026-05-28
**Симптом:** Cron `transfer:orders:dwh` падает на prod с PHP Fatal `Allowed memory size of 4294967296 bytes exhausted` в `app/Service/Connector/Traits/ResponseParser.php:76` (`json_decode`).
**Влияние:** Файл `_reportDWH.csv` не выгружается в DWH — потеря дневных данных для аналитики/отчётности.
**Сервис:** [`avg-integration-service/integration`](https://gitlab.gloria.aaanet.ru/avg-integration-service/integration), ветка `production`. PHP-cron, контейнер `integration-cron`.

---

## 1. Срочность

* Cron бежит ежедневно в **21:30 UTC**.
* **CSV-файл DWH успешно выгружался каждый день с 19 по 26 мая** (маркеры `'CSV собран и сохранён'` + `'csv выгружен'` в логах в `TransferService.php:3633`/`3649`). DWH-получатель (Лаврова Д.) подтверждает: проблема **только сегодня (27.05)**.
* 27.05 — **первое** падение в наблюдаемом окне. И сразу **втрое быстрее** обычного: 6.5 минут до OOM vs 15-21 минут полного успеха.
* Длительность **успешного** прогона по дням росла: 15→16→16→18→18→19→19→**21** минут (24→26 мая → +6 минут к концу периода). Тенденция к границе.

### Полная таблица прогонов

| Дата | "CSV собран и сохранён" UTC | "csv выгружен" UTC | Длительность | Статус |
|---|---|---|---|---|
| 19.05 | 21:48:19 | 21:48:20 | 18 мин | ✓ |
| 20.05 | 21:46:21 | 21:46:24 | 16 мин | ✓ |
| 21.05 | 21:46:43 | 21:46:50 | 16 мин | ✓ |
| 22.05 | 21:49:25 | 21:49:28 | 19 мин | ✓ |
| 23.05 | 21:48:13 | 21:48:16 | 18 мин | ✓ |
| 24.05 | 21:45:26 | 21:45:33 | 15 мин | ✓ |
| 25.05 | 21:49:54 | 21:49:54 | 19 мин | ✓ |
| 26.05 | 21:51:13 | 21:51:13 | **21 мин** | ✓ |
| **27.05** | **—** | **—** | **~6.5 мин** | **OOM** |

И `transfer:order-status:dwh` (22:10 UTC, другая команда через `TransferService.php:2556/2572`) **отрабатывает стабильно каждый день** в ~22:10:05-22:10:10 — то есть это **не общая деградация сервиса**, а конкретно `transfer:orders:dwh`.
* Связанные тикеты: [OPSOMN-13161](https://jira.gloria-jeans.ru/browse/OPSOMN-13161), [OPSOMN-12536](https://jira.gloria-jeans.ru/browse/OPSOMN-12536), [OPSOMN-14564](https://jira.gloria-jeans.ru/browse/OPSOMN-14564) — открыты.
* Серия «обрезанных» / непрошедших ReportDWH с весны 2025: 11871, 11962, 12096, 12538, 12920, 13198, 13375, 13456, 13475, 13893, 14103 — большинство закрыто частично, симптом повторяется.

### Длительность работы команды по дням (последний trace из `TransferService.php:4XXX`)

| Дата | Последний trace UTC | Время от старта | Что было |
|---|---|---|---|
| 19.05 | 21:48:17 | ~18 мин | стабильно |
| 22.05 | 21:49:24 | ~19 мин | +1 мин |
| 25.05 | 21:49:50 | ~20 мин | +1 мин |
| 26.05 | 21:51:09 | ~21 мин | +1 мин |
| **27.05** | **21:36:36** | **~6.5 мин** | **резкий обрыв** |

Тенденция выглядит как: **что-то накапливается между прогонами** (отсюда +1 минуту в день), плюс **27 мая отдельный триггер** (резкое падение длительности).

Возможные накапливающиеся вещи между прогонами:
* Количество ордеров в окне `subDays(2)` растёт (нагрузка магазина растёт)
* Кеш ПВЗ деградирует (всё больше cache-miss → `Artisan::call('pickup_info')` внутри fillCsvByOrderList)
* Какие-то Redis-структуры (если используются) забиваются

---

## 1.0.0 ⭐ Корневая причина (найдена через OMS DB на 2026-05-28)

**Аномальный пик обновлений статусов заказов на 25-27.05.** Соотношение `last_status_update_time / created_date_time` дошло до **2.03** (на 26.05) при норме ~1.0 и **апрельском пике ~1.27**.

### Сравнение пиков April vs May

| | April | May |
|---|---|---|
| Дата create-пика | 17.04 (5908 заказов) | 17.04 (5212 заказов) |
| Дата update-пика | 21.04 | **26.05** ← на ~5-7 дней позже create-пика |
| Update-пик абсолютно | 4631 | **8051** ← в 1.74× больше April |
| Update/create ratio в эти дни | 1.27 | **2.03** |
| dwh-cron в эти дни | ✓ работал | ✗ OOM |

### Что значит для cron'a

`transferOrdersToDwh` начинается с `Connector::sendAndWait([order_history => getOrderStatusHistoryFind($dateFrom, $dateTo), item_history => getItemsStatusHistory(...)])` (стр. 3258-3261). `getOrderStatusHistoryFind` тянет **все заказы у которых статус обновлялся в окне 2 дней**, и для каждого возвращает **полную структуру заказа + history**.

| Период | Заказов в окне 2 дней | Размер history-выгрузки |
|---|---|---|
| 17.05 (норма) | 3597 + 3821 = **~7 400** | ~25-30 МБ JSON |
| 27.05 (инцидент) | 7362 + 8051 = **~15 400** | **~50-60 МБ JSON** ⚠ |

После history-обработки `transferOrdersToDwh` идёт постранично `Connector::sendAndParse(getOrders(..., $page, $limit=50, ...))`. **При увеличенной выборке прошлой фазой** и пикnut page response — Guzzle буферизует ответ через `psr7/Utils::copyToString` → OOM.

### Что вызвало пик update на 25-27 мая

Скорее всего сочетание факторов:
1. **Длинные майские праздники 1-9.05** — заказы могли накопиться в неотгруженных статусах
2. **Распродажа 17-24.05** (пик create 5079-5212 заказов в день)
3. **Заказы из (1) и (2) "доезжают" одновременно** через жизненный цикл (отгрузка / доставка / закрытие / отмена) — это раздувает `last_status_update_time` на 25-27.05

Это **business event**, не bug в коде. В апреле похожая динамика была (пик 21.04), но **существенно слабее** (ratio 1.27 vs 2.03) — там уложилось в 4 ГБ.

### Почему наш патч это лечит

`page_size 50 → 10` снижает **page response в 5×**. Даже при удвоенной выборке (ratio 2.03 вместо ~1) реальный pageResponse становится 12-15 МБ вместо 60+ МБ. Это **с запасом** компенсирует текущую аномалию.

Дополнительно `stream $csv` + `gc_collect_cycles` + cleanup payload в WARNING/ERROR — снижают **heap baseline** на 200-500 МБ, оставляя больше места под пиковую аллокацию.

### При каких условиях может повториться

Если ratio дойдёт до **3-4×** (например, новогодняя распродажа + длинные новогодние праздники → ещё больший лаг и больше отложенных update'ов), даже page_size=10 может не хватить. Это аргумент в пользу **архитектурного решения** (master-child паттерн как у recon — раздел 8.3).

---

## 1.0.1 ⚠ Изначальная гипотеза "распродажа = больше заказов" опровергнута

**Изначально считалось** (от бизнес-стороны): на 25-28 мая идёт распродажа, заказов больше нормы. Эта гипотеза казалась объясняющей все факты.

**После доступа к OMS DB (`oms-awg-order-prod`)** — гипотеза **не подтверждается**.

### Кол-во заказов по дням (UTC), таблица `order_t`

| Дата | Заказов | Cron состояние |
|---|---|---|
| 28.05 (не полный) | 1 440 | OOM |
| **27.05** | **3 859** | **OOM** |
| 26.05 | 3 958 | ✓ 21 мин (рекорд) |
| 25.05 | 4 172 | ✓ 19 мин |
| **24.05** | **5 079** | **✓ 15 мин** (max за период) |
| 23.05 | 4 627 | ✓ 18 мин |
| 22.05 | 4 735 | ✓ 19 мин |
| 21.05 | 3 927 | ✓ 16 мин |
| 20.05 | 4 046 | ✓ 16 мин |
| 19.05 | 3 984 | ✓ 18 мин |
| 18.05 | 4 279 | ? |
| **17.05** | **5 212** | **? (наверняка ✓)** |
| 16.05 | 4 654 | ? |

27.05 — **меньше** заказов чем в дни когда cron проходил. 24.05 и 17.05 (5079 и 5212 заказов) — cron работал. Никакого "роста на распродаже" в OMS-данных **не видно**.

### Outliers по items на заказ (за 2 дня)

| Дата | Заказов | max items | заказов с 30+ | с 40+ |
|---|---|---|---|---|
| **27.05 (OOM)** | 3859 | 35 | **3** | **0** |
| 26.05 | 3958 | **49** | 4 | 1 |
| 25.05 | 4172 | 28 | 0 | 0 |
| **24.05 (cron ✓)** | 5079 | 42 | 4 | **1** |
| **16.05 (cron ✓)** | 4654 | 42 | **6** | **1** |

На 27.05 outliers **меньше**, чем в дни когда cron проходил. Заказов с 30+ items: на 27.05 — 3, на 16.05 — 6 (вдвое больше, cron работал).

### status_history rows (входной поток для history-запросов)

| Дата | status_history rows | Cron |
|---|---|---|
| **27.05 (OOM)** | **28 078** | OOM |
| 26.05 | 30 532 | ✓ |
| 25.05 | 32 091 | ✓ |
| **24.05 (cron ✓)** | **35 074** | ✓ max |
| 22.05 | 31 973 | ✓ |
| 17.05 | 34 095 | ✓ |

27.05 — status_history **меньше**, чем дни когда cron работал.

### Вывод

Все **data-side** гипотезы опровергнуты:

| Гипотеза | Данные OMS DB | Вердикт |
|---|---|---|
| Распродажа → больше заказов | 27.05 меньше нормы | ❌ |
| Outliers по items | 27.05 ниже среднего | ❌ |
| Заказ-монстр | max на 27.05 = 35 (norm) | ❌ |
| Рост status_history | 27.05 ниже нормы | ❌ |

**Что бы то ни было, причина падения 27.05 — не в данных от OMS.** Объёмы 27.05 объективно ниже многих дней, когда cron работал успешно.

### Что мог иметь в виду support, говоря "распродажа"

Возможные интерпретации:
* Распродажа на сайте (наплыв пользователей в каталог), но **заказы ещё не подскочили**.
* Запланированная кампания, которая **должна была** дать рост, но фактически дала меньше ожидаемого.
* Промо-активность в офлайн-сети, не отражённая в e-commerce orders.

Это всё **не объясняет** падение `transfer:orders:dwh` в проде.

---

## 1.1 Сравнение 26.05 (успех) vs 27.05 (падение)

Триггер на 27.05 — **это не накопительная деградация, иначе бы провал был +1 мин, не -15 мин**. Что-то изменилось разово.

**Ключевая аномалия в темпе:**

| Метрика | 26.05 (успех) | 27.05 (OOM) |
|---|---|---|
| Первый flush warning'ов из `4027` (start CSV phase) | 21:30:**40**.076 | 21:30:**27**.240 |
| Последний наблюдаемый trace | 21:51:13 | 21:36:36 |
| Период активной обработки в Elastic | ~20 мин | ~6 мин |

**27 мая первая пачка warning'ов появилась на 13 секунд РАНЬШЕ.**

Это значит, **подготовительная фаза прошла быстрее, не медленнее**: получение справочников, history по интервалам, формирование карт `$orderModifyDates` / `$skuModifyDate` / `$itemCancelledDates` — все ускорилось. И **сразу же** команда упала. Это противоречит гипотезе "данных стало больше" — иначе prepare-фаза заняла бы больше времени.

### Возможные интерпретации (исторически — на момент первой итерации анализа)

> **Замечание после получения доступа к OMS DB (см. раздел 1.0.1):** все четыре интерпретации **не подтверждаются данными**. На 27.05 в OMS DB заказов и status_history было даже **меньше** обычного. Список сохранён как **архив** хода рассуждений.

1. ~~**OMS вернул что-то неполное / битое.**~~ Не подтверждено: history-объёмы в OMS DB обычные.
2. ~~**OMS под высокой нагрузкой.**~~ Аномалии времени отклика на `/v1/order/list/full` (6.5 и 11.8 сек) видны в `ConnectorMetricMiddleware.php`, но это **пользовательский трафик** через `integration-api`. Cron работает в **другом контейнере** (integration-cron). Прямого влияния нет.
3. ~~**Разовая «взрывная» структура одного заказа.**~~ Опровергнуто: max items per order 27.05 = 35 (норма), на 16.05 и 24.05 было больше (42, 49) и cron работал.
4. ~~**Накопительный рост достиг границы.**~~ Опровергнуто: 27.05 объёмы заказов и history **ниже** дней когда cron работал.

**Что остаётся:** причина **не в данных от OMS**. См. раздел 12 за актуальными кандидатами (утечка в Integration, изменение OMS API contract, артефакты integration-cron окружения).

---

## 2. Что показывают логи прода

Индекс `integration-awg-new-*` (target `logs-is-awg-prod`). Helper'ы `logs_search_message` / `logs_recent` не работают для этого target — конфиг ссылается на `when.createdAt` / `what.message`, а реально поля называются `createdAt` / `logmsg` / `whatmessage`. Использовать `data_logs_raw_search`.

### Окно последнего падения (UTC, 2026-05-27)

| Время | Событие |
|---|---|
| 21:30:00 | старт cron'a по `Kernel.php` (`Schedule::exec('php artisan transfer:orders:dwh')->cron('30 21 * * *')`) |
| 21:30:27.240 | **первый flush** trace-буфера: 16 warning'ов `'баркод типа доставки не распознан'` из `TransferService.php:4027` + 1 error `'Не найдены данные о пвз в кеше'` (4326). Значит к этому моменту pipeline уже **прошёл** history-запросы и **начал** обработку первой страницы `getOrders` через `fillCsvByOrderList` |
| 21:30:27 – 21:36:36 | пачки warning'ов летят залпами по 10–20 событий в одну миллисекунду — `awg/logger` batched, flush'ит при достижении размера буфера |
| **21:36:36.977** | последний trace от команды — `TransferService.php:4027` warning |
| 21:36:37+ | тишина. PHP Fatal в stderr не попадает в Elastic (нативный фатал, `trace()` не вызывается) |

### Следствия

1. Команда работала **~6.5 минут**, дошла до n-ной страницы заказов и упала на `json_decode` ответа OMS.
2. **Logger batched** — буфер flush'ится по достижению size, при FATAL последний буфер теряется (heap забит). Поэтому ранние trace (`'начинаю собирать данные'`, `'получил склады'`, `'получили историю заказов'`) — в Elastic не дошли, хотя они в начале метода.
3. Последняя минута активности команды в логах **отсутствует**.

### Размер данных
Page size: `dwh_order_list_page_size = 50` ([`exchange.php`](https://gitlab.gloria.aaanet.ru/avg-integration-service/integration/-/blob/production/www/app/Service/Exchange/config/exchange.php)).
Окно выгрузки: `subDays(2)` (захардкожено в `transferOrdersToDwh`).

---

## 3. Анализ кода (production-версия)

`App\Service\Exchange\Services\V1\Common\TransferService::transferOrdersToDwh` — порядок:

```php
$dateFrom = Carbon::now('UTC')->subDays(2);                  // окно — 2 дня
$dateTo   = Carbon::now('UTC');
$limit    = config('exchange.dwh_order_list_page_size', 50); // 50

// 1) Справочник складов
$warehouses = Connector::sendAndParse(OmsClient::getWarehouseList());

// 2) ⚠ История за 2 дня — без пагинации, два больших ответа одновременно
$responses = Connector::sendAndWait([
    'order_history' => OmsClient::getOrderStatusHistoryFind($dateFrom, $dateTo),
    'item_history'  => OmsClient::getItemsStatusHistory($dateFrom, $dateTo),
]);
$orderHistory = Connector::parse($responses['order_history']);  // json_decode здесь
$itemHistory  = Connector::parse($responses['item_history']);   // и здесь

// 3) Карты, держатся весь pipeline
$orderModifyDates    = $this->getOrderModifyDates($orderHistory, $orderIds);
$itemCancelledDates  = ...;
$skuModifyDate       = ...;
$orderIds            = ...;
unset($orderHistory, $itemHistory);

// 4) Цикл по страницам заказов с CSV-генерацией в строку $csv
$csv = '';
$page = 0;
while (true) {
    $orders = Connector::sendAndParse(OmsClient::getOrders(…, $page, $limit, …));  // ⚠ json_decode здесь
    if (empty($orders)) break;
    $this->fillCsvByOrderList($csv, $orders, …);  // $csv растёт в памяти
    if (count($orders) < $limit) break;
    $page++;
}

// 5) ⚠ Второй цикл — собирает ВСЕ изменённые-но-старше-2-дней заказы в один массив
$orderList = [];
while (true) {
    $orders = Connector::sendAndParse(OmsClient::getOrders(…, ids: $ids, $page, $limit));
    foreach ($orders as $order) { $orderList[] = $order; … }  // ⚠ накапливаем все
    …
}
```

### Что раздувает heap

| Структура | Где растёт | Оценка |
|---|---|---|
| `$orderHistory` / `$itemHistory` | history-запросы без пагинации (`subDays(2)`) | большой JSON в одном куске → PHP-array в 5-10× больше |
| `$orderModifyDates`, `$skuModifyDate`, `$itemCancelledDates`, `$orderIds` | карты "по всем заказам / SKU за 2 дня" | держится весь pipeline |
| `$csv` | CSV-строка всего файла | растёт линейно с числом заказов |
| `$orderList` (второй цикл) | накапливает изменённые-но-старые заказы | потенциально неограничен |
| `trace(..., ['orders' => $orders, 'csv' => $csv, 'order_history' => $orderHistory, ...])` | каждый trace копирует контент в буфер logger'а | удваивает пиковый расход |

### Почему `json_decode` — последняя капля

Не сам по себе response гигантский — heap уже забит другими структурами к моменту вызова. Поэтому fatal при попытке выделить даже 4096 байт.

### PHP-окружение
`containers/integration-cron/php.ini`:
* `memory_limit = 4096M`
* `max_execution_time = 1600`
* PHP **7.4** (`base-images/php_7_4-fpm-alpine`) — на 15-20% медленнее на JSON-decode, чем 8.x.

---

## 4. История попыток и тикеты

| Тикет | Дата | Статус | Содержание |
|---|---|---|---|
| [OPSOMN-12096](https://jira.gloria-jeans.ru/browse/OPSOMN-12096) | 2025-03 | Завершено | Уменьшили окно (`subDays`) — отсюда текущие 2 дня |
| [OPSOMN-12536](https://jira.gloria-jeans.ru/browse/OPSOMN-12536) | 2025-04 | Новый | "Исследовать ошибки transfer:orders:dwh" — без комментариев |
| [OPSOMN-12538](https://jira.gloria-jeans.ru/browse/OPSOMN-12538) | 2025-04 | Завершено | "Не работает исправление по уменьшению периода" |
| [OPSOMN-13161](https://jira.gloria-jeans.ru/browse/OPSOMN-13161) | 2025-05 | Новый | `Undefined variable: pickedSku` (другой баг в `fillFields`/`fillCsvByOrderList`, **не OOM**) — без комментариев |
| [OPSOMN-13972](https://jira.gloria-jeans.ru/browse/OPSOMN-13972) | 2025-09 | **В работе** | Миграция cron'ов в k8s CronJob |
| [OPSOMN-14564](https://jira.gloria-jeans.ru/browse/OPSOMN-14564) | 2025-12 | Зарегистрирован | "Неправильно отрабатывает retry при выгрузке DWH" |
| [OPSOMN-14584](https://jira.gloria-jeans.ru/browse/OPSOMN-14584) | 2025-12 | Приостановлено | **Recon-fix** — состояние из которого можно клонировать паттерн для dwh |

`OPSOMN-14584` в **массовом переводе техдолга в "Приостановлено"** 2026-05-04 — значит активной работы над dwh-аналогом сейчас нет.

---

## 3.1 Состояние recon в проде (важная аномалия)

При расследовании обнаружены **две** реализации recon в production одновременно:

| Файл | Что внутри | Что делает |
|---|---|---|
| [`AbstractReconService.php`](https://gitlab.gloria.aaanet.ru/avg-integration-service/integration/-/blob/production/www/app/Service/Exchange/Services/V1/Order/AbstractReconService.php) | **новая** master-child архитектура из OPSOMN-14584 | state-table, memory_limit restart, shell_exec |
| [`AbstractReconServiceHotfix.php`](https://gitlab.gloria.aaanet.ru/avg-integration-service/integration/-/blob/production/www/app/Service/Exchange/Services/V1/Order/AbstractReconServiceHotfix.php) | **СТАРАЯ** in-memory версия (`$csv .= ...`, `$foundedOrders = []`, тяжёлые trace) — точно как `transferOrdersToDwh` сейчас | накапливает CSV в памяти, без рестартов |

И в проде **последний успешный recon-прогон каждый день** (с 19 по 27 мая в ~23:15-23:24 UTC) идёт **из `AbstractReconServiceHotfix.php:204`**, не из новой версии. Время растёт с 23:15:46 (19.05) до 23:24:41 (27.05) — +9 минут за 8 дней, та же закономерность что у dwh.

### Что это означает

* **In-memory подход у recon работает в проде** на текущих объёмах. То есть recon-fix через master-child мог быть избыточен — старая версия укладывалась в `memory_limit=4096M`.
* Возможно, hotfix — это **rollback** новой архитектуры, если она оказалась проблемной. Или это запасной путь, который иногда дёргают вручную.
* Это **меняет прогноз для dwh**: «копирование recon-паттерна» — не единственный путь. Если у recon hotfix влезает в память, то и для dwh **возможно достаточно меньших правок** (cleanup в 8.2), без полной master-child архитектуры.
* Нужно понять, **через какую команду** запускается `AbstractReconServiceHotfix` и почему в проде используются обе версии. Это отдельный архитектурный долг.

---

## 4.1 Контекст автора фикса (важно!)

Сообщения Андрея Шапошникова в Teams от 13.12.2025 (момент финального деплоя recon-фикса). Автор сейчас не работает в компании.

> *«Я уже всё сделал... Просто только что доотладил... Я сотворил лютый пиздец с state-хранилищем в базе... И **забивши полный хер на жор памяти. Я в душе не чаю как с ним бороться. Я перепробовал всё**... Но поскольку мы не можем победить жопу — надо её возглавить!»*

> *«Локально у меня всё супер, **но не могу протестить рестарт по "память кончилась". Мне нечем забить память**»*

> *«Да, я там и сейчас **кривой traceId** — каждый child-process порождает новый... И в консоли слегка жопа без возможности вывести жор памяти»*

> *«Можно сделать **отдельное state-хранилище для DELIVERING**, тогда обработка DELIVERING быстрее будет, так как она в любом случае "исторически-накопительная" — её можно сохранять даже между выгрузками — в "прошлом" не должны статусы меняться никогда по идее. **Но пока я этим не парился**»*

### Следствия

1. **Recon-fix — это workaround, не лечение.** Корневая причина утечки не найдена. Автор честно говорит «перепробовал всё, не знаю как бороться».
2. **2 ГБ и 50 рестартов** — захардкоженные эмпирические значения, не из анализа.
3. **Поведение под нагрузкой проверено только в проде** — локально нечем забить память.
4. **Сквозной trace через master + child'ов отсутствует** — каждый child получает новый traceId, корреляция возможна только по `process_id` (явно в БД) или по времени. Это объясняет, почему в моих запросах в Elastic не собиралась полная история прогона.
5. **Есть нереализованная идея**: persistent state для DELIVERING-истории. Если статусы в прошлом не меняются, эта карта может жить **между выгрузками**, а не строиться каждый раз с нуля. Это сэкономит самый дорогой history-запрос.

### Что это значит для плана dwh

При копировании паттерна recon → dwh мы **унаследуем workaround**, не решение. Будет работать через 50×2 ГБ рестартов. Это приемлемо как первый шаг (recon полгода стабилен), но **до этого стоит проверить, можно ли найти что течёт** — у нас есть несколько неисследованных гипотез, по которым автор не копал глубоко.

См. раздел **8.0 «Альтернативная ветка плана: найти root cause»** ниже.

---

## 5. Готовый паттерн фикса (применён к `transfer:orders:recon`)

MR-ветка [OPSOMN-14584](https://gitlab.gloria.aaanet.ru/avg-integration-service/integration/-/tree/OPSOMN-14584), главный merge — [MR !710](https://gitlab.gloria.aaanet.ru/avg-integration-service/integration/-/merge_requests/710).

### 5.1 Архитектурные элементы

| Элемент | Файл |
|---|---|
| State-таблица `order_filter` (process_id tinyint, type_id varchar(5), order_id varchar(40)) | [`2025_12_12_130000_create_order_filter_table.php`](https://gitlab.gloria.aaanet.ru/avg-integration-service/integration/-/blob/production/www/app/Service/Exchange/database/migrations/2025_12_12_130000_create_order_filter_table.php) |
| Enum типов (`UNIQ`, `DELIVERING`, `DELIVERING_LOADED`, `ENDED`, `STATUS`) | `OrderFilterTypeEnum` |
| Eloquent-модель | `OrderFilter` |
| Репозиторий с операциями init/insert/check/setStatus/getStatus/setEnded | `OrderFilterRepository` |
| Master CLI: `transfer:orders:recon` | `TransferOrderReconCommand` |
| Child CLI: `transfer:orders:recon:child {system} {process_id}` | `TransferOrderReconChildCommand` |
| Helper для batched OMS-загрузки через файлы | `LoadOmsPagesCommand` (signature `transfer:http:omsload`) — оставлен в кодовой базе, но в финальном пути не используется |
| Конфиги | `recon_memory_limit_mb=2048`, `recon_memory_limit_retries=50`, `recon_order_list_page_size=50` |

### 5.2 Поток master → child

`AbstractReconService::sendRecon(stdout, process_id=0)`:

```php
if ($process_id === 0) {
    // MASTER ветка
    $process_id = $repository->initProcessId();                   // round-robin 1..100
    $orderListFilters[...]($collector);                            // одноразово подгрузить history → DELIV в БД
    $repository->setStatus($process_id, first_key, 0);
    $fp = fopen("recon-temp-{$process_id}.csv", 'w');
    fwrite($fp, $converter->getHead()); fclose($fp);
    while (!$repository->checkEnded($process_id) && $tryCount < 50) {
        shell_exec("php artisan transfer:orders:recon:child cbr {$process_id}");
        $tryCount++;
    }
    return OK;
}

// CHILD ветка (process_id != 0)
$status = $repository->getStatus($process_id);                     // {key, page}
$fp = fopen("recon-temp-{$process_id}.csv", 'a');                  // append!
foreach ($getters as $key => $getter) {
    if (!$status['checked']) {
        if ($status['key'] != $key) continue;                       // пропускаем уже обработанные getters
        $status['checked'] = true;
    }
    $page = $status['page'];
    while ($lastPageNotFound) {
        $orders = Connector::sendAndParse($getter($page));
        foreach ($orders as $order) {
            if ($repository->checkFilter($process_id, UNIQ, $order['order']['id'])) continue;
            $repository->insertFilter($process_id, UNIQ, $order['order']['id']);
            if ($orderItemFilters[$key]($order['order']['id'], $process_id)) continue;
            $mutated = $mutator->mutate($order);
            fwrite($fp, $converter->toCsvRow($mutated));
            unset($mutated);
        }
        unset($orders);
        $repository->setStatus($process_id, $key, $page);
        $page++;
        if (memory_get_usage(true) / 1048576 >= $memory_limit_mb) {
            return OK;                                              // graceful exit, master запустит следующий child
        }
    }
}
fclose($fp);
$result = Connector::sendAndParse($this->getFileSenderRequest($fp_read));  // отправка через stream
$repository->setEnded($process_id);
```

### 5.3 Ключевые принципы

* **Heap возвращается ОС'у только через рестарт процесса** (PHP не отдаёт памяти после free). Поэтому `shell_exec` нового child'а, а не цикл внутри одного процесса.
* **State в БД** — не данные, а только прогресс (key/page) и фильтры дедупликации.
* **Данные в файле** — append-режим, child продолжает с того же места.
* **Memory check после каждой страницы**, а не после каждого order — компромисс между точностью и накладными.
* **Лимит на 50 рестартов** — чтобы вечно не зависать.
* **Round-robin process_id 1..100** — старые записи в `order_filter` подтираются на init.

---

## 6. Эволюция recon-фикса — что **НЕ** сработало

11–13 декабря, 18 MR'ов за 4 дня:

| Этап | MR | Подход | Почему не зашло |
|---|---|---|---|
| 1 | [!699-701](https://gitlab.gloria.aaanet.ru/avg-integration-service/integration/-/merge_requests/701) | Только CSV-в-файл (без БД) | Остались тяжёлые in-memory `$foundedOrders`, `$collector['order_has_delivering']` |
| 2 | [!702-704](https://gitlab.gloria.aaanet.ru/avg-integration-service/integration/-/merge_requests/704) | "fix history load" — освободить `$orderHistory` раньше | Не сняло основной перерасход |
| 3 | [!705-708](https://gitlab.gloria.aaanet.ru/avg-integration-service/integration/-/merge_requests/708) | Хотfix'ы прямо в prod, 4 "test commit" подряд | Ловили частные проблемы |
| 4 | [!709](https://gitlab.gloria.aaanet.ru/avg-integration-service/integration/-/merge_requests/709) | `LoadOmsPagesCommand` — межпроцессный обмен через файлы | Помогло частично, но архитектура неустойчивая, перепиывает Connector |
| **5** | [!710-713](https://gitlab.gloria.aaanet.ru/avg-integration-service/integration/-/merge_requests/710) | **State-table + master-child + memory_limit restart** | **Сработало.** Recon живой |

**Урок:** для dwh **идти сразу на шаг 5**, не повторять шаги 1–4.

---

## 7. Параллельная инициатива OPSOMN-13972 (k8s CronJob)

Pershin Grigoriy с сентября 2025 переносит cron'ы в k8s CronJob (репо [`gloria-ci`](https://gitlab.gloria.aaanet.ru/avg-integration-service/gloria-ci), ветка `OPSOMN-13972`).

* На stage уже:
  * `e462d8a6` [OPSOMN-13972] **disable transfer:orders:dwh cronjob** (2025-09-05)
  * `9883e1af` **disable rest cronjobs** (2025-09-16)
  * MR в `gloria-ci` создаёт k8s CronJob resources
* На prod **миграция не выкачена** — `Kernel.php` в `production`-ветке всё ещё содержит cron-расписание `transfer:orders:dwh`.

### Что даст k8s CronJob

* Внешний scheduler вместо `php artisan schedule:run` → проще мониторить, есть метрики, retry policy.
* Каждый запуск — отдельный pod → ресурсы изолированы, k8s рестартанёт pod при OOMKilled.
* Возможность задать `resources.limits.memory` и `backoffLimit`.

### Что НЕ даст

* **Не лечит сам OOM** — внутри pod'а та же PHP-CLI с тем же `memory_limit=4096M` и тем же кодом.
* Если data вырастет — снова `Allowed memory size exhausted`, pod упадёт, k8s рестартанёт, снова упадёт. **CrashLoopBackOff гарантирован** без архитектурного фикса.
* `subDays(2)` останется → каждый рестарт будет тянуть всю историю заново → ещё хуже.

**Вывод:** k8s миграция и архитектурный фикс — комплементарны, но не заменяют друг друга. Дешёвый workaround "просто перейти в k8s" не сработает.

---

## 8. План решения

### 8.0 Альтернативная ветка: найти корневую причину утечки (1-3 дня исследования)

**Зачем:** автор recon-fix явно сдался без анализа. Если найдём, что течёт, то:
* можно делать **настоящий fix**, а не workaround
* паттерн master-child может не понадобиться вообще, или 50→2 рестартов
* recon станет быстрее как побочный эффект

**Гипотезы по подозреваемым** (в порядке вероятности и дешевизны проверки):

#### 8.0.1 `awg-packages/logger` retain после flush
Возможно, после flush'a logger держит ссылку на буфер или message-объекты. Андрей сам говорит «в консоли слегка жопа без возможности вывести жор памяти».

**Проверка:** запустить локально с **выключенным** logger handler'ом (заглушка `NullLogger`) и сравнить рост памяти с включённым.

#### 8.0.2 Laravel/Lumen Query Log
По умолчанию в CLI Eloquent держит log всех запросов. В recon на каждой странице — несколько `checkFilter`/`insertFilter` через Eloquent, за прогон в несколько часов это сотни тысяч SQL.

**Проверка:** одна строка в начале команды:
```php
\DB::connection()->disableQueryLog();
```
И посмотреть на разницу.

#### 8.0.3 Symfony Response / Guzzle response body retention
В `Connector::sendAndWait` parallel-вызов держит `Response` objects до конца promise pool. Если pool retains references — body не освобождается.

**Проверка:** добавить явные `unset($responses)` после `Connector::parse`. Возможно, retain — в DI-сингах connector'а.

#### 8.0.4 PHP 7.4 GC циклические ссылки
`Carbon\Carbon` объекты и `Eloquent Model` собирают через GC, но 7.4 ленивее 8.x.

**Проверка:** `gc_collect_cycles()` после каждой страницы. Если падает peak — виноват GC.

#### 8.0.5 Mutator / Converter retain через закрытия
`$mutator->mutate($order)` и `$converter->toCsvRow($mutated)` могут retains state в closures.

**Проверка:** profile xdebug на staging — какие функции аккумулируют память.

#### 8.0.6 Реальный размер карт за 2 дня
Возможно, объёмы выросли больше, чем кажется. Карта `$skuModifyDate` — это число уникальных SKU × штамп. Если за 2 дня поменялись все 200k+ SKU — это уже 200k ключей в PHP-array, что само по себе ~50 МБ только на структуру.

**Проверка:** SQL в OMS — сколько уникальных order_id, sku, item_id меняло статус за 2 дня в среднем.

### Минимальный профилировочный патч (0.5 дня)

Дописать в `transferOrdersToDwh` checkpoints с потреблением памяти, пишущие **напрямую в файл**, минуя `trace()` (чтобы не потерялись при FATAL):

```php
$memlog = fopen('/tmp/dwh-mem-' . date('Ymd-His') . '.log', 'w');
$log = function(string $tag) use ($memlog) {
    fwrite($memlog, sprintf(
        "%s\t%s\treal=%dMB\tusage=%dMB\tpeak=%dMB\n",
        microtime(true), $tag,
        memory_get_usage(true) / 1048576,
        memory_get_usage(false) / 1048576,
        memory_get_peak_usage(true) / 1048576
    ));
    fflush($memlog);
};

$log('start');
$warehouses = Connector::sendAndParse(...);
$log('after_warehouses');
$responses = Connector::sendAndWait([...]);
$log('after_history_response');
$orderHistory = Connector::parse($responses['order_history']);
$log('after_order_history_parse');
$itemHistory = Connector::parse($responses['item_history']);
$log('after_item_history_parse');
$orderModifyDates = $this->getOrderModifyDates(...);
$log('after_modify_dates_map');
// ... и т.д. после каждой границы

while (true) {
    $orders = Connector::sendAndParse(...);
    $log('after_page_' . $page);
    $this->fillCsvByOrderList(...);
    $log('after_csv_page_' . $page);
    // ...
}
```

Запустить разово в проде (или на staging с реальными объёмами OMS). По графику роста сразу видно, что именно течёт.

**Это рекомендую сделать перед любым архитектурным фиксом.**

---

### 8.1 Срочно (день, прод)

* **Поднять `memory_limit`** в `containers/integration-cron/php.ini` до 8-12 ГБ (минимально инвазивно). Даёт несколько недель воздуха.
* Альтернатива: запустить вручную с `php -d memory_limit=16G artisan transfer:orders:dwh`, чтобы закрыть текущий день.

### 8.2 Среднесрочно — минимальный refactor (1-2 дня)

В файле `TransferService.php`, метод `transferOrdersToDwh` + помощники `fillCsvByOrderList` / `fillFields`:

1. **Убрать тяжёлые массивы из `trace(...)`**: оставить только `page`, `count`, `min_date`. Убрать `orders`, `csv`, `order_history`, `item_history`, `order_modify_dates`, `sku_modify_date`, `item_cancelled_dates`. Это разгрузит logger-буфер и сократит пиковый расход в 2-3×.
2. **Стримить CSV в файл** (`fopen` + `fwrite`), а не `$csv .= ...`. Финальная отправка через stream resource (паттерн из recon: `getFileSenderRequest($fp)`).
3. **Не накапливать `$orderList` во втором цикле** (≈3422-3500). Считать `minCreatedDate` и писать в файл на лету.

Это даст ещё одну итерацию воздуха (вероятно, прогон проходит до конца на текущем объёме).

### 8.2.bis Дешёвые «cleanup» правки до архитектуры (полдня)

Эти правки **рекомендуются** в `transferOrdersToDwh` (и опционально в recon при следующем касании) **независимо от** того, копируем мы master-child или нет:

```php
public function transferOrdersToDwh(...) {
    \DB::connection()->disableQueryLog();                       // см. 8.0.2

    $previousMemoryLimit = ini_get('memory_limit');
    // ... основной код ...

    foreach (страницы) {
        $orders = Connector::sendAndParse(...);
        $this->fillCsvByOrderList(...);
        unset($orders);
        gc_collect_cycles();                                    // см. 8.0.4
    }
}
```

Каждая из строк — копеечная. Если хотя бы одна попадёт в подозреваемого — может быть, master-child вообще не понадобится.

### 8.3 Архитектурный фикс — копия паттерна recon (3-5 дней)

#### 8.3.1 Расширить `OrderFilterTypeEnum`

Добавить dwh-специфичные типы:
```php
const DWH_UNIQ          = 'DUNIQ';     // дедупликация по обработанным заказам
const DWH_MOD_DATE      = 'DMOD';      // {order_id, modified_at}
const DWH_SKU_MOD       = 'DSMOD';     // {sku, modified_at}
const DWH_ITEM_CANCEL   = 'DCANC';     // {item, cancelled_at}
const DWH_STATUS        = 'DSTAT';     // {key, page} — прогресс
const DWH_ENDED         = 'DEND';      // флаг "всё"
```

(Альтернатива: завести вторую таблицу `dwh_filter`, если не хочется смешивать с recon.)

Поскольку нужно хранить **дополнительные данные** (даты модификации заказа/SKU/item, не только id) — `order_id varchar(40)` для DWH-MOD_DATE и т.п. можно использовать как JSON value (как уже сделано для `STAT` → `json_encode(['key' => ..., 'page' => ...])`). Это уже принятый в recon паттерн.

#### 8.3.2 Реализовать master/child

* `App\Service\Exchange\Services\V1\Common\TransferService::transferOrdersToDwh` рефакторить в master + child:
  * **Master** (`TransferOrderToDwhCommand`, сигнатура без изменений): инициализирует `process_id`, грузит history однократно в state-таблицу (через подходящий цикл по `explodeDateTimeInterval` — он уже есть и используется в recon), пишет header CSV в файл, циклом запускает child через `shell_exec` до `setEnded` или 50 итераций.
  * **Child** (`TransferOrderToDwhChildCommand`, сигнатура `transfer:orders:dwh:child {process_id}`): читает `{key, page}` из БД, продолжает с этой страницы, на каждой странице проверяет `memory_get_usage`, при достижении лимита graceful exit.
* Бо́льшую часть кода можно вынести в общий `AbstractMasterChildExportService` (recon переписан в этом стиле — переиспользовать), но это требует ещё одного refactor — стоит делать после стабилизации dwh.

#### 8.3.3 Пагинировать history-запросы

`getOrderStatusHistoryFind` / `getItemsStatusHistory` сейчас вызываются **одним** запросом за 2 дня. В recon уже сделано `explodeDateTimeInterval` с лимитом `history_request_interval_limit = 259200` секунд (3 дня), но **бьётся на интервалы внутри окна**. Применить тот же приём для dwh — конфиг `dwh.history_request_interval_limit` уже **существует** в [`exchange.php`](https://gitlab.gloria.aaanet.ru/avg-integration-service/integration/-/blob/production/www/app/Service/Exchange/config/exchange.php) (значение 259200), но в коде dwh не используется.

#### 8.3.4 Добавить конфиги

```php
'dwh_memory_limit_mb'      => (int) env('EXCHANGE_DWH_MEMORY_LIMIT_MB', 2048),
'dwh_memory_limit_retries' => (int) env('EXCHANGE_DWH_MEMORY_LIMIT_RETRIES', 50),
```

#### 8.3.5 Регистрация

В `ExchangeServiceProvider::registerCommands()` — добавить `TransferOrderToDwhChildCommand` (по аналогии с `TransferOrderReconChildCommand`).

#### 8.3.6 Сквозной traceId master → child

Андрей оставил «кривой traceId» — каждый child porodит новый. Это сильно затрудняет отладку. Передавать `--trace-id={uuid}` из master в child как аргумент команды и устанавливать через logger context. Тогда все события одного прогона будут собираемы по trace_id в Kibana. Дешёвая правка, можно сделать в том же MR.

#### 8.3.7 Persistent state для DELIVERING (Андрей предлагал, но не делал)

Андрей упоминал: «*статусы в прошлом не должны меняться никогда по идее. Её можно сохранять даже между выгрузками*». Если для dwh есть аналогичная "исторически-накопительная" сущность (например, `$orderHistory` за прошлые дни), её можно держать в отдельной таблице `dwh_history_cache` и обновлять только инкрементально. Это самый дорогой запрос — `getOrderStatusHistoryFind` за 2 дня. Если кешировать, остаётся подгружать только последние X часов.

**Стоит обсудить с DWH-владельцем**: можно ли считать, что статус-история заказа за прошлые сутки не меняется? Если да — это огромный quick win.

### 8.4 Долгосрочно — синхронизироваться с k8s миграцией

* Если [OPSOMN-13972](https://jira.gloria-jeans.ru/browse/OPSOMN-13972) близка к деплою на prod, паттерн master-child из 8.3 **всё равно нужен** — k8s pod упадёт без него.
* Альтернатива: в k8s можно реализовать "rerun on OOM" более красиво — `restartPolicy: OnFailure`, `backoffLimit`, ресурсы pod'а 8-12 ГБ. Но это не убирает потребность дробить выгрузку.
* Координация с Першиным Г. — обсудить, входит ли `transfer:orders:dwh` в первую волну миграции, и в какой последовательности (фикс → миграция, миграция → фикс).

---

### 8.4.bis Самый дешёвый практический шаг сегодня

Учитывая, что:
* команда **успешно отрабатывала каждый день** 8 дней подряд до 27.05;
* `transfer:order-status:dwh` (родственная команда) сегодня тоже работает стабильно;
* OMS под нагрузкой давал аномальные времена отклика 27.05;
* в коде между 26.05 и 27.05 ничего не меняли (`production` ветка стоит на месте);

…вероятно, **27.05 был разовый incident** (либо OMS отдал что-то ненормальное, либо граница накопления данных пробита впервые). Простой и дешёвый шаг:

1. **Перезапустить команду сегодня вручную**:
   ```bash
   # внутри integration-cron pod, под user app
   php artisan transfer:orders:dwh
   ```
   Желательно — за один уход (1) сохранить stderr в файл (`>> /tmp/dwh-rerun.log 2>&1`), (2) увеличить memory_limit (`php -d memory_limit=12G ...`).

2. **Если пройдёт** → инцидент разовый, дыра в данных DWH только за 27.05. Заводить тикет на "наблюдение за памятью" (см. 8.0 профилировка) на следующий неудачный день, чтобы поймать живой пик.

3. **Если упадёт снова** → проблема **воспроизводимая** на текущих объёмах — переходим к 8.1 (поднять `memory_limit`) + 8.2 (cleanup в `trace()` + `disableQueryLog` + `gc_collect_cycles`). Это закроет проблему на ещё 1-2 недели роста объёма.

4. Параллельно — **профилировочный патч** (8.0) на следующий деплой, чтобы поймать конкретного "пожирателя" памяти.

5. Если проблема рецидивна и регулярна → 8.3 архитектурный refactor (master-child).

---

### 8.5 Финальный рекомендуемый порядок

**Главное переосмысление после доступа к OMS DB:** причина **неизвестна**. Все data-side гипотезы (распродажа, outliers, history-рост) **опровергнуты** — 27.05 был тише дней когда cron работал. Митигация снижает peak, но **не лечит корень**.

#### Сегодня (час работы) — закрыть дыру за 27.05

1. **Узнать у DevOps** реальный pod memory limit / RAM ноды для контейнера integration-cron. Без этого нельзя безопасно поднять PHP-лимит.
2. **Поднять `memory_limit`** для CLI до **8 ГБ** (если pod позволяет) — либо через env var, либо через `php -d memory_limit=8G artisan transfer:orders:dwh`.
3. **Ручной перезапуск** под увеличенный лимит. Stream stderr в файл, чтобы видеть финал.
4. Если прошёл — CSV за 27.05 ушёл, отчитаться Лавровой.

#### На неделе (1-2 дня работы) — снизить peak heap

Cleanup-патч (после всех корректировок предложения):

1. **Минимизировать payload в WARNING/ERROR trace'ах** — заменить `'order' => $order` на `'order_id' => $order['order']['id'] ?? null` в строках **3831, 3957, 4017, 4031, 4044, 4075, 4095, 4115, 4135, 4196, 4319, 4332** файла `TransferService.php`. Главный эффект: каждый WARNING сейчас весит 13 KB JSON (полный `$order`), после правки — ~100 байт. На 3-5 тысяч заказов это **снижение logger-буфера на ~50-200 МБ**.
2. **Stream `$csv` в файл** между страницами + поправка `addOrderFieldsToCsv` под флаг "header written". Снимает основной накопитель.
3. **`gc_collect_cycles()`** после `unset($orders)` в обоих циклах + после `unset($dataHistory)` в history-цикле.

В сумме реалистично снизит пик памяти **в 2-3 раза**. Должно закрыть текущий инцидент, но не гарантирует устойчивость — корневая причина не найдена.

#### В спринт (3-5 дней работы) — закрыть навсегда

Один из двух путей (либо оба):

**(a) Миграция в k8s CronJob.** Координация с Першиным Г. ([OPSOMN-13972](https://jira.gloria-jeans.ru/browse/OPSOMN-13972), миграция в работе с сентября 2025). На stage уже отключены PHP-cron'ы, в проде ждёт деплоя. После миграции:
* `resources.limits.memory: 16Gi` без касания PHP-кода
* `restartPolicy: OnFailure` + `backoffLimit` из коробки
* Внешний мониторинг и алерты

Сам по себе **не лечит OOM**, но даёт более просторный budget + рестарты автоматом.

**(b) Master-child паттерн как у recon ([OPSOMN-14584](https://jira.gloria-jeans.ru/browse/OPSOMN-14584)).** State-таблица `dwh_filter` + child-процессы с memory-based restart. Гарантирует работу на **любых** объёмах. См. раздел 8.3 этого документа за деталями.

Оптимально — **(a) + (b) вместе**: k8s CronJob как execution environment + master-child как алгоритм. Тогда и Чёрная пятница, и Новый год отрабатывают без вмешательства.

#### Что **снято** из рекомендаций (после корректировок)

* ❌ `DB::disableQueryLog()` — query log не накапливается (нигде не enable'нут)
* ❌ `gc_enable()` — gc по умолчанию включён
* ❌ Cleanup большинства trace'ов в `transferOrdersToDwh` — они на TRACE-severity и **отбрасываются** в helpers.php до обработки payload
* ❌ Закомментировать debug-трейсы в `fillCsvByOrderList` — они тоже на TRACE-severity, **бесплатны**
* ✅ Профилировочный патч с memory checkpoints — НУЖЕН на следующий деплой (корневая причина не найдена, нужно собирать данные при следующем падении)
* ❌ Гипотезы про OMS-incident, разовые "взрывные" заказы, query log

#### Что **осталось** в рекомендациях

* ✅ Поднять memory_limit (но согласовать с pod limit)
* ✅ Минимизировать payload в WARNING/ERROR trace'ах
* ✅ Stream `$csv` в файл
* ✅ `gc_collect_cycles()` после крупных аллокаций
* ✅ Master-child или k8s CronJob в спринт

---

## 11. Тех-вывод одной фразой

**Корневая причина:** на 25-27.05 в OMS произошёл **аномальный пик обновлений статусов** — соотношение `update / create` дошло до **2.03** (норма ~1.0, апрельский пик 1.27). Из-за этого `getOrderStatusHistoryFind` на 27.05 возвращает в окне 2 дней **~15 000 заказов вместо обычных ~7 400** — каждый с полной структурой. Response пробивает 60 МБ → Guzzle OOM. Наш патч (`page_size 50 → 10` + stream CSV + cleanup payload) **точечно компенсирует 2× рост выборки** через 5× снижение page response — **должен закрыть инцидент**.

---

## 12. Что осталось для **настоящего** поиска корня

После доступа к OMS DB и опровержения всех data-side гипотез — корневая причина **не данные**. Кандидаты сужаются:

### 12.1 Реальная утечка в Integration

Что-то на стороне самого PHP-приложения накапливает память. Возможные точки:
* **`awg/logger`** — batched buffer. Хотя TRACE-severity фильтруется на helpers.php (early return), buffer для WARNING/ERROR накапливает контент. Возможно после flush ссылки не освобождаются.
* **`Connector` (Guzzle PSR-7)** — `Utils::copyToString` буферизует response в строку целиком. Если pool retains references на response object'ы — body не освобождается. Возможные точки: DI singletons, promise pool retention.
* **Eloquent ORM cache** — Laravel может неявно держать model instances.
* **Redis-driver state** — для race-condition locks и `delivery_point_*` cache.

### 12.2 Изменение в OMS API contract

В OMS DB **самих заказов** не выросло, но **API response** может содержать новые поля. Это не видно через прямой SQL — только через API logs или сравнение reuqests/responses 24.05 vs 27.05.

* Кто-то в OMS-команде мог добавить поле в response (`product.attributes`, `customer.history`, etc.) — поле могло раздуть единичный response.
* Или OMS изменил формат `product.sku[]` — например, начал возвращать **все** SKU сущности (с картинками) для каждого item, а не только нужный SKU.

### 12.3 Артефакты integration-cron окружения

* В контейнере `integration-cron` рядом с CLI-cron-задачами работают **supervisord daemon'ы** (`transfer:business-unit:daemon`, `transfer:product:daemon`, `transfer:order-status:daemon`, `transfer:order-message:daemon`). Они **постоянно крутятся** и могут влиять на доступную ОС-память.
* Каждый CLI-cron получает свой PHP-процесс, но если на host'е RAM забита daemon'ами — у cron'а меньше доступного места до OS-OOM.
* Стоит проверить **k8s pod memory** или `htop` на хосте в момент падения cron'а.

### 12.4 Что нужно сделать для настоящего корня

#### Шаг 1 — добавить наблюдаемость (срочно, час)

В `transferOrdersToDwh` добавить запись `memory_get_usage(true)` в **файл** на каждой границе:
* После warehouses
* После history-парсинга
* После каждой страницы (с № страницы)
* После history-интервалов
* Перед SFTP

Запись через `file_put_contents(..., FILE_APPEND)` минуя `trace()` — чтобы данные **гарантированно** сохранились при OOM.

См. раздел 8.0 этого документа за готовым snippet'ом.

#### Шаг 2 — после следующего падения проанализировать профиль

По файлу видна **кривая** потребления:
* Если рост **линейный** между страницами → накапливающийся аккумулятор
* Если **скачок на одной странице** → конкретный response от OMS
* Если **плато потом скачок в конце** → SFTP / final processing

#### Шаг 3 — изоляция компонента

Запустить с **выключенным `awg/logger`** (мок NullLogger) и сравнить. Если падает → не logger. Если проходит → причина в logger retention.

Аналогично можно мокать `Connector::sendAndParse` для возврата фиксированных небольших данных — изолировать roll'а Guzzle.

#### Шаг 4 — посмотреть commits OMS за последние месяцы

В `platform/starfish24/core/Order` — посмотреть, что менялось в response контракте `getOrders` / `getOrderStatusHistoryFind`. Через `mcp__gj-buddy__gitlab_*`.

---

## 13. Финальное завершение (после доступа к OMS DB)

**Корневая причина НАЙДЕНА** (см. раздел 1.0.0): аномальный пик `last_status_update_time` на 25-27.05 (ratio 2.03 vs норма ~1.0, апрельский пик 1.27), вызванный сочетанием майских праздников + распродажи 17-24.05.

**Митигация применена** ([патч на ветке `OPSOMN001-580`](https://gitlab.gloria.aaanet.ru/avg-integration-service/integration/-/tree/OPSOMN001-580)) и **точечно лечит причину**:
- `page_size 50 → 10` компенсирует 2× раздутую выборку через 5× снижение page response
- `stream $csv` + cleanup payload + `gc_collect_cycles()` снижают heap baseline

При нормализации ratio (после 28-29.05 пик update'ов должен спадать) команда **сама** заработает на старом конфиге, но патч уже даст запас прочности.

### Рекомендации

1. **Применить hotfix сейчас** — закроет текущий инцидент.
2. **Закрыть [OPSOMN001-580](https://jira.gloria-jeans.ru/browse/OPSOMN001-580)** после успешного прогона.
3. **Сохранить документ как baseline** для будущего отслеживания: формула «ratio update/create > 1.5 в 2-дневном окне → риск OOM при текущей page_size».
4. **Архитектурное решение** ([OPSOMN-13972](https://jira.gloria-jeans.ru/browse/OPSOMN-13972) k8s CronJob, master-child паттерн как у recon) — для устойчивости к ratio 3-4× (новогодняя распродажа + длинные январские каникулы). Не срочно, но в спринт.
5. **Мониторинг** — настроить алерт в Grafana: «daily ratio of `last_status_update_time` updates / `created_date_time` orders за 2 дня выше 1.5 — предупреждать команду dwh».

---

## 9. Открытые вопросы

1. **Точное место OOM** — на какой странице `getOrders` и в каком из двух циклов падение? Логи Elastic обрезаны последней минутой буфера. Чтобы получить ответ — либо добавить `Log::flush()` после каждой страницы в trace'е (одна строка кода), либо разово запустить с увеличенным `memory_limit` и стримом stderr в файл, либо профилировочный патч из 8.0.
2. **Объёмы данных** — сколько заказов реально приходит за 2 дня сейчас? Сравнить с месяцем назад / 3 месяца назад. На момент исследования `oms-awg-order-prod` отвечал upstream error, не получилось снять метрики. **Retry позже.**
3. **Связан ли OPSOMN-13161** (`Undefined variable: pickedSku`) с текущим OOM? Скорее всего нет — там exception во время `fillFields`, тут OOM. Но оба указывают на код вокруг `fillCsvByOrderList`.
4. **`transfer:order-status:dwh` (22:10 UTC) тоже падает?** Это **другая** команда, использует SFTP, имеет свою историю проблем (OPSOMN-14103). Стоит проверить, проходит ли она сейчас стабильно.
5. **Кто владелец продукта DWH?** Лаврова Д. чаще всего регистрирует тикеты. Сообщить о статусе (CSV не приходит >неделю) и плане.
6. **`AbstractReconServiceHotfix.php` — что это, почему в проде есть и работает?** Если старая in-memory версия recon успешно отрабатывает каждый день, то жор памяти recon **сам по себе перестал быть проблемой** (либо объёмы recon меньше, либо OPSOMN-14584 — это превентивный фикс). Это меняет приоритеты для dwh — можно начать с минимального cleanup и проверить, влезает ли в `memory_limit`. Запросить у DevOps / Зверева Д. историю — кто и когда внедрил Hotfix-версию.
7. **Что было 27 мая** для резкого обрыва длительности? Деплоев в `production`-ветке не было. Внешние факторы? (например, всплеск заказов, проблема в OMS API, проблема в Redis-кеше ПВЗ)
8. **Помещается ли в БД интеграционного сервиса state-таблица как у recon?** Нужно прикинуть размер. Если в `order_filter` за один прогон recon — ~50k уникальных order_id × 100 байт ≈ 5 МБ. Для dwh с двумя дополнительными типами фильтров (modify_date, sku_modify) — возможно 20-30 МБ за прогон. Терпимо.

---

## 10. Связанные artefakts

* MR с финальным recon-фиксом: [!710](https://gitlab.gloria.aaanet.ru/avg-integration-service/integration/-/merge_requests/710)
* Production `AbstractReconService`: `www/app/Service/Exchange/Services/V1/Order/AbstractReconService.php` (ветка `production`)
* Production `TransferService::transferOrdersToDwh`: `www/app/Service/Exchange/Services/V1/Common/TransferService.php` (ветка `production`, метод начинается ~стр. 3220 по локальной ветке — в prod номера могут отличаться)
* k8s-cron репо: [`avg-integration-service/gloria-ci`](https://gitlab.gloria.aaanet.ru/avg-integration-service/gloria-ci), ветка `OPSOMN-13972`
