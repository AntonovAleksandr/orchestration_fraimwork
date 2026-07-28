# Stage 14 — История и сквозная семантика номера eCommerce-заказа

**Дата среза:** 2026-07-24  
**Статус:** complete-for-current-pass  
**Покрытие:** Jira, Confluence, Git history ENSI Baskets, локальные snapshots
OMS/Integration/OTS/WMS, ранее выполненный production DB-срез; без исходной
Redmine-задачи `#99027`, протокола архитектурного решения 2022 года и полного
аудита типов во всех обработках 1С7/1С8  
**Уровни уверенности:** `confirmed`, `high`, `proxy`, `hypothesis`, `unknown`
в значениях из `00-PLAN.md`

## 0. Scope

Цель стадии — не подобрать новый диапазон для WB FBS, а восстановить:

1. что именно исторически называлось `orderId`, номером заказа и номером корзины;
2. где и когда появился диапазон `2xxxxxxxxx`;
3. какое значение первая цифра приобрела в downstream-системах;
4. почему номер нельзя считать локальным surrogate key одного сервиса;
5. какие ограничения подтверждены, а какие только подозреваются;
6. какие сведения об исходном выборе префикса `2` не найдены.

Термины `orderId`, `clientOrderId`, `order_id`, `idd`, `OrderNr` нельзя
смешивать: в разных системах это разные сущности, хотя часть из них получает
одно и то же значение.

## 1. Короткий вывод

`2000000001` — это не внутренний ID записи OMS. В текущем GJ-контуре это
сквозной бизнес-номер, который:

- рождается как `baskets.number` в ENSI;
- передаётся в OMS как `clientOrderId`;
- используется OMS как ключ защиты от повторного создания заказа;
- становится числовым `order_id` в OTS;
- уходит в WMS как `OrderNr`/`OrderRefNr`;
- уходит в 1С как `idd` и входит в `documentFoundation`;
- попадает в DWH как `code`;
- отображается клиенту и используется в payment/order API.

Поэтому номер одновременно является:

- клиентским номером;
- correlation key;
- idempotency/duplicate-protection key;
- warehouse execution key;
- частью идентичности документов 1С;
- analytics reconciliation key;
- в некоторых процессах — ключом промокода и shopping attempt.

Подтверждено, что downstream различает:

- `1xxxxxxxxx` — исторический Hybris;
- `2xxxxxxxxx` — Starfish/new eCommerce.

Однако **не найден первичный документ 2022 года**, в котором автор выбора
формулы написал бы: «берём `2`, потому что диапазон `1` занят Hybris» или
обосновал отказ от `0`. Это наиболее согласованное объяснение по совокупности
источников, но причинная формулировка остаётся `hypothesis`, а не `confirmed`.

## 2. Какие идентификаторы существуют сейчас

| Система / поле | Что это | Формат / тип | Как связано |
|---|---|---|---|
| ENSI `baskets.id` | Технический PK строки корзины | PostgreSQL bigint/sequence | Основа первичного номера |
| ENSI `baskets.number` | Номер корзины и будущего заказа | unique unsigned bigint | `2` + `id`, дополненный слева до 9 цифр |
| OMS `order_t.id` | Технический PK записи OMS | bigint | Не показывается клиенту |
| OMS `order_t.order_id` | Внутренний natural ID OMS | string | `tenant-clientOrderId-hash` |
| OMS `order_t.client_order_id` | Клиентский номер заказа | string | Приходит из ENSI; проверяется на дубликат |
| OTS `order.order_id` | Исполнительный номер заказа | C# `long`, SQL bigint | Integration кладёт сюда OMS `clientOrderId` |
| WMS `OrderNr`, `OrderRefNr` | Номер складского задания | string telegram fields | Строковое представление OTS `order_id` |
| 1С `idd` | Номер заказа | string, 10 | OMS `clientOrderId` |
| 1С `documentFoundation` | Уникальное основание документа | string, 17 | `0000352` + 10-значный номер |
| DWH `code` | Номер заказа в status export | string | OMS `clientOrderId` |

Evidence:

- Confluence `60692293`, v52: `id` — внутренний идентификатор OMS,
  `clientOrderId` — номер, отображаемый клиенту;
- `Order.java:52-66`: отдельные `id`, `orderId`, `clientOrderId`;
- `OrderServiceImpl.java:218-226`: внутренний `orderId` строится как
  `tenant-clientOrderId-hash`;
- `OrderExportOtsMutator.php:30-34`: OTS `order.order_id` получает
  `order.clientOrderId`;
- `OrderExportEcomMutator.php:20-23` и
  `AbstractOrderExport1CMutator.php:143-157`: `idd=clientOrderId`,
  `documentFoundation=0000352+clientOrderId`;
- Confluence `63470445`, v155: `idd` — строка 10, `documentFoundation` —
  строка 17, источник Starfish `0000352`;
- Confluence `63456564`, v34: DWH `code` — string из `clientOrderId`;
- `TgwWmsMapping.cs:103-135`: WMS получает `OrderNr` и `OrderRefNr`, а
  `OrderWwsBeleg` строится из префикса и номера.

Confidence: `confirmed`.

## 3. Историческая линия

### 3.1. Hybris: заказ наследовал номер корзины

Документ Hybris «OMS1 Модель заказа и статусная схема заказа»
(`page_id=15368628`, v289, 2022-09-09) дважды фиксирует:

> Заказ создаётся на основе корзины; номер заказа равен номеру корзины.

В старых интеграционных документах встречаются реальные 10-значные примеры:

- `1013287126` — Hybris → 1С АРМ, `page_id=44255279`, v132;
- `1019396208` — Starfish → Hybris status callback,
  `page_id=60687796`, v20;
- `1034319880` — пример `clientOrderId` в текущей 1С-спецификации,
  `page_id=63470445`.

Это подтверждает существование исторического диапазона `1xxxxxxxxx`, но не
даёт формулу генератора Hybris и не доказывает, что **каждое** значение с
первой цифрой `1` всегда принадлежало Hybris.

Confidence: `high`.

### 3.2. Starfish как продукт умел генерировать clientOrderId сам

В core OMS генератор существовал как минимум с 2020 года:

- endpoint `GET /order/create/newid` появился в commit
  `e08b4d716df04ee2ca12011cef2814bb3488a378` от 2020-05-12;
- таблица `client_order_id_template` хранит `prefix`, `month_day`,
  разделители, `min/max`, `next_value`, `source`, `brand`, `tenant`;
- `OrderServiceImpl.getOrderNewId()` инкрементирует template и строит строку;
- `next_value` позднее переведён с integer на bigint
  (`IPGJ-987/changelog-1.xml`).

Следовательно, архитектура Starfish не требует, чтобы `clientOrderId` был
числом или совпадал с PK. Это настраиваемый внешний/клиентский номер.

GJ ordinary eCommerce не использует этот генератор в основном потоке: номер
приходит из ENSI Baskets.

Confidence: `confirmed` для product capability; production-конфигурация всех
templates не исследована.

### 3.3. Появление `2 + 9 цифр` в ENSI Baskets

Самая ранняя найденная реализация:

- commit `e5af0e10ecd2e46499aafae511afe3b7b31071f1`;
- дата: 2022-12-15;
- сообщение: `#99027`;
- задача в родительской Jira `DEVOMN001-2915` названа
  «[Baskets] Сервис Корзина. Адаптация модели данных».

Этот commit одновременно:

- создал `baskets.number` как nullable unique unsigned bigint;
- добавил after-create hook;
- задал формулу:

```php
$basket->number = (int) ('2' . sprintf('%09d', (string) $basket->id));
```

9 января 2023 года commit `89401ef...` временно удалил hook в рамках `#99041`,
а `56882338...` через час вернул его с пометкой `fix tests`. Поэтому `#99041`
не является источником идеи префикса: исходная реализация уже была в `#99027`.

Текущий код сохранил формулу в
`Basket::idToNumber()` (`Basket.php:134-136`).

Что не удалось получить:

- исходную Redmine-карточку `#99027`;
- MR discussion;
- текст архитектурного решения с объяснением выбора цифры `2`;
- явное сравнение вариантов `0`, `1`, `2`.

Прямой HTTPS-запрос к `redmine.greensight.ru/issues/99027` 2026-07-24
завершился timeout; содержимое карточки не получено.

Confidence: `confirmed` для даты и реализации; `unknown` для авторской
мотивации.

### 3.4. 2023: номер стал idempotency key попытки создания заказа

Jira `DEVOMN001-6973` документирует distributed failure:

1. ENSI отправляет номер корзины как `clientOrderId`;
2. OMS может успеть создать заказ;
3. ENSI получает ошибку/timeout и сохраняет корзину;
4. повторный commit с тем же номером отклоняется как duplicate.

Решение 2023 года — выдавать корзине новый номер для части ошибок, не удаляя
её. Commit `43efaef...` от 2023-04-17 добавил endpoint обновления номера и
генерацию через следующий value той же DB sequence.

Текущий OMS перед записью выполняет lookup по `clientOrderId + tenant + brand`
и бросает `OrderAlreadyCreatedException`
(`OrderServiceImpl.java:241-246`).

Это прямое доказательство: номер — не cosmetic label, а ключ логической попытки
создания заказа и защиты от дубля.

Confidence: `confirmed`.

### 3.5. 2024: префикс участвует в маршрутизации legacy/new source

Jira `MWHNSK-7709` содержит прямое правило для возврата eCommerce, когда заказа
нет в OTS:

- номер начинается на `1` → `R000337` (`Hybris`);
- номер начинается на `2` → `R000352` (`Starfish`).

Это сильнейшее найденное доказательство, что первая цифра стала частью
интеграционного контракта и определяет source-system routing.

Оно подтверждает семантику `1=Hybris`, `2=Starfish` в downstream-процессе, но
датировано 2024 годом и не заменяет отсутствующее обоснование выбора,
сделанного в 2022 году.

Confidence: `confirmed` для operational routing, `high` для общего разделения
поколений.

### 3.6. 2024: номер корзины — ещё и identity одноразового промокода

Jira `OPSOMN-8271` объясняет, что Сервер скидок различает применения
одноразового промокода по номеру корзины. Поэтому после ручной команды
«удалить всё» номер теперь сохраняется.

Исключения:

- после успешного заказа для оставшихся недоступных товаров создаётся новая
  корзина с новым номером;
- после неоднозначной ошибки создания заказа номер может быть обновлён.

Следовательно, `baskets.number` уже не равен строго `2_000_000_000 +
baskets.id` на всём жизненном цикле строки: он может быть переиздан из
sequence. Это identity shopping/order attempt, а не простая функция текущего
PK.

Confidence: `confirmed`.

### 3.7. Сертификаты: номер без корзины

Jira `OPSOMN-10226`, comment `160333`:

- обычный номер строился из PK корзины;
- для сертификата корзины нет;
- предложено генерировать `clientOrderId` в OMS;
- чтобы избежать пересечения, предложено начинать новый диапазон с `3`.

Фактический production-срез показывает сертификаты `211xxxxxxx`, а Jira
`OPSOMN-11047`, `12177`, `11176`, `11080` содержит такие примеры.

Не найдено подтверждение:

- почему от предложения `3...` перешли к `211...`;
- кто и где зарегистрировал диапазон `211`;
- существует ли централизованный реестр диапазонов.

Confidence: `confirmed` для проблемы отсутствия корзины и предложения `3`;
`confirmed` для фактического `211`; `unknown` для причины выбора `211`.

### 3.8. 2025: рассинхрон sequence подтверждает глобальную связность

Jira `OPSOMN-11717`, `OPSOMN-12563`, `OPSOMN-13068`:

- ENSI на test/dev повторно выдавала номера, уже существовавшие в OMS;
- OMS отвечала `Order already exists with id`;
- обсуждалось выравнивание следующего ENSI `clientOrderId` относительно
  максимума OMS;
- в OMS test были старые ручные строковые и большие test IDs, из-за которых
  нельзя было просто сортировать `clientOrderId` как чистое число.

Это доказывает:

- allocator и потребитель номера разнесены по системам;
- восстановление/перенос данных требует синхронизации sequence;
- `max(clientOrderId)` небезопасен без фильтра namespace/формата;
- отсутствие централизованного registry создаёт реальный operational risk.

Confidence: `confirmed`.

### 3.9. 2025: test-stub использует отдельный диапазон `9`

Confluence `130151470`, «Номера заказов», v1:

- корзина, созданная при включённой заглушке, имеет номер на `9`;
- такой заказ не попадёт в OMS;
- обычный номер, который поедет в OMS, начинается на `2`.

Это ещё одно прямое подтверждение, что префикс несёт routing/environment
semantics.

Confidence: `confirmed`.

## 4. Почему именно `2`, а не `0` или `1`

### Что подтверждено

1. До нового ENSI flow существовали Hybris-заказы `1xxxxxxxxx`.
2. В новой Baskets-модели с первого implementation commit выбран
   `2xxxxxxxxx`.
3. Downstream позднее явно маршрутизирует `1` как Hybris, `2` как Starfish.
4. Тестовая заглушка использует `9`, чтобы заказ не уходил в OMS.

### Что можно заключить с высокой уверенностью

Диапазоны использованы для разделения поколений/источников заказов и
предотвращения пересечений.

### Что остаётся предположением

Фраза «`2` выбрали именно потому, что `1` уже занимал Hybris» не найдена в
первичном решении. Это логично и согласуется со всеми найденными фактами, но
без протокола/задачи 2022 года остаётся `hypothesis`.

### Что неизвестно про `0`

Не найдено документа, где вариант `0xxxxxxxxx` обсуждался или отвергался.
Исторические интеграции показывают чувствительность к ведущим нулям
(`MWHNSK-3152`), но это не доказательство, что именно поэтому не выбрали `0`.

## 5. Подтверждённые ограничения

### 5.1. Формат ENSI

Формула `2` + 9 цифр создаёт nominal namespace:

```text
2000000001 … 2999999999
```

То есть до 999 999 999 sequence values.

`sprintf('%09d')` задаёт **минимальную**, а не максимальную ширину. При
`id >= 1_000_000_000` результат станет 11-значным (`21000000000`), что уже
нарушит текущий 10-значный контракт 1С.

### 5.2. OMS

- `clientOrderId` — string;
- internal `orderId` — string;
- template `next_value` — bigint;
- numeric prefix не является ограничением core OMS;
- duplicate protection делает повторное использование номера
  бизнес-значимой ошибкой.

### 5.3. OTS и WMS

- OTS request model использует C# `long`;
- основные таблицы используют SQL bigint;
- WMS telegram fields `OrderNr`/`OrderRefNr` — string;
- обратный TGW mapping встречает `Convert.ToInt64(AufNr)`.

В текущем OTS-коде нет общего ограничения signed Int32 на `order_id`.

### 5.4. 1С

Current Confluence contract:

- `idd`: string length 10;
- `documentFoundation`: string length 17;
- source prefix `0000352` контролируется 1С и не должен пересекаться.

Это формальный формат, важнее того, что PHP/Java/C# способны хранить больше.

### 5.5. Int32 — реальный системный риск, но не доказанный orderId limit

Подтверждённые факты:

- Jira `MWHNSK-1106/1107` назывались `INT32. 1C7 - WMS`, но описания полей
  отсутствуют;
- Jira `OPSOMN-13708` зафиксировала реальный overflow при
  `fiscal_document_number > 2_147_483_647` в 1С/WebAPI;
- Jira `MWHNSK-3152` использовала заказ `3000000001` в тесте 1С7/WMS; дефектом
  было удаление ведущих нулей в штрихкоде, а не переполнение.

Поэтому корректный вывод:

- скрытые Int32 conversions в legacy-контуре существуют;
- прямого доказательства, что **order ID** ограничен Int32 во всех цепочках,
  нет;
- `3xxxxxxxxx` нельзя выпускать без end-to-end теста каждого маршрута;
- один успешный 1С7/WMS testcase с `3000000001` не доказывает безопасность
  всех обработок, отчётов, индексов и возвратов.

Confidence: `confirmed`.

## 6. Текущая ёмкость

Production-срез, выполненный в рамках исследования 2026-07-24:

- max обычного OMS `clientOrderId`: `2010743225`;
- max сгенерированного ENSI basket number: `2010743249`;
- max certificate namespace: `2110009330`;
- абсолютный numeric max OMS `9120807608` оказался одиночной legacy/test-like
  записью и не является текущей sequence.

До signed Int32 max от текущего ENSI number:

```text
2 147 483 647 - 2 010 743 249 = 136 740 398
```

Это не полный запас диапазона `2`, а запас до потенциальной legacy Int32
границы. Полный 10-значный namespace `2` имеет ещё почти 989 млн значений.

Ранее измеренный темп ENSI — около 215 тыс. новых basket IDs за 30 дней. При
неизменном темпе Int32 headroom измеряется десятилетиями, но FBS «одна единица
= один заказ», массовые retries и отдельные генераторы способны радикально
изменить consumption rate.

Confidence: `confirmed` для snapshot; future runway — `hypothesis`, потому что
нагрузка и правила генерации могут измениться.

## 7. Что это означает для WB FBS

До отдельного решения нельзя:

- генерировать произвольный новый 10-значный номер в WB connector;
- использовать собственный local autoincrement без coordination с ENSI/OMS;
- считать `clientOrderId` лишь отображаемым полем;
- выбирать `3000000001+` на основании того, что OTS использует `long`;
- считать `212...` безопасным только потому, что он ниже Int32.

Даже новый непересекающийся namespace требует проверки:

1. кто единственный allocator;
2. где регистрируется namespace и source/channel;
3. что является идемпотency key WB (`rid`, `srid`, assembly ID) и как он
   связывается с внутренним номером;
4. какие systems получают новый prefix;
5. что меняется в return routing (`1/2 → source`);
6. проходят ли OTS/WMS/1С creation, cancel, return, reporting, DWH и payment;
7. какая длина и numeric boundary допустимы;
8. как выполняются replay, migration и sequence recovery.

Архитектурно безопаснее хранить разные идентичности отдельно:

```text
internal order UUID/PK
business clientOrderId
channel = WB_FBS
marketplace order / rid / srid / assembly id
warehouse execution id
accounting document ids
```

И не кодировать все измерения исключительно цифрами одного номера. Но это
target principle; текущий legacy-контур всё равно требует совместимого
business number.

## 8. Противоречия и слабые места источников

1. Первичная формула найдена в Git, но rationale отсутствует.
2. Confluence Baskets и Jira BA/SA подтверждают проект, но доступная текущая
   версия страницы не содержит явного объяснения `2`.
3. Redmine `#99027` и `#99041` недоступны через Jira/Buddy.
4. Starfish поддерживает свободные string templates, но GJ downstream
   фактически наложил numeric/length semantics.
5. `clientOrderId` в OMS допускает test strings, а операционные процедуры
   иногда пытаются вычислять numeric max.
6. 1С contract объявляет string, однако связанные legacy-компоненты способны
   выполнять скрытый numeric cast.
7. Реестр занятых диапазонов `1`, `2`, `211`, `9` не найден.

## 9. Неизвестно

- Кто принял исходное решение о префиксе `2`.
- Обсуждались ли `0` и другие варианты.
- Был ли Int32 budget частью решения 2022 года.
- Почему сертификаты получили `211`, а не предложенный `3`.
- Какие ещё диапазоны зарезервированы.
- Есть ли формальный owner namespace.
- Все ли 1С7/1С8 обработки используют `idd` как string.
- Есть ли hidden numeric casts в SSIS/DWH/печати/возвратах.
- Какая production-конфигурация `client_order_id_template` действует сейчас.
- Должен ли marketplace order быть полноценным `clientOrderId` текущего
  eCommerce-контура или отдельным execution number.

## 10. Следующие проверки

1. Получить исходную Redmine `#99027` и MR discussion декабря 2022.
2. Найти/опросить BA/SA из `DEVOMN001-998/1611/2037`.
3. Выгрузить sanitized production `client_order_id_template`.
4. Составить реестр prefix ranges с владельцами.
5. Выполнить boundary E2E matrix:
   `2147483646`, `2147483647`, `2147483648`, `2120000001`,
   `2999999999`, `3000000001`.
6. Проверить creation/status/cancel/return/1C/DWH/WMS labels для каждого.
7. До WB design утвердить ADR «Order identities and namespace allocation».

## 11. Кандидаты в EVIDENCE-LEDGER

- `MP-ID-001` — `1` Hybris / `2` Starfish участвуют в downstream routing.
- `MP-ID-002` — новый ENSI range введён 2022-12-15 формулой `2 + 9 digits`.
- `MP-ID-003` — исходная причина выбора `2` документально не найдена.
- `MP-ID-004` — `clientOrderId` является cross-system natural/idempotency key.
- `MP-ID-005` — number identity распространяется в OTS/WMS/1С/DWH.
- `MP-ID-006` — 1С contract ограничивает `idd` 10 символами.
- `MP-ID-007` — Int32 conversions существуют, но universal orderId limit не
  доказан.
- `MP-ID-008` — certificate `211` и test-stub `9` показывают namespace
  partitioning без найденного центрального registry.
- `MP-ID-009` — отдельный WB range требует allocator, registry и E2E boundary
  test.

## 12. Resume pointer

Следующая атомарная стадия — не продолжать общий поиск по `orderId`, а:

1. попытаться получить Redmine `#99027`;
2. снять sanitized `client_order_id_template`;
3. построить и выполнить boundary test matrix на test contour;
4. после этого принять ADR по WB FBS numbering.
