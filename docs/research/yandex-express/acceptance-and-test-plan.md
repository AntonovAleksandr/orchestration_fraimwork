# Acceptance and test plan: SFS Yandex

Дата: 2026-06-28

Цель: определить, как понять, что интеграция SFS Yandex готова к rollout и не ломает SFS CDEK.

## Предусловия

- Есть тестовый магазин с остатком и включенным SFS Yandex.
- Есть тестовый магазин с SFS CDEK, где Yandex выключен.
- В справочнике согласован новый delivery type `SFS_YANDEX`.
- OMS Delivery/logistics возвращает interval с `carrierId = yandexNextDayDelivery` для SFS.
- Retail/ARM релиз с Yandex SFS установлен на тестовом контуре.
- Credentials/config Yandex заведены на тестовом контуре без использования production secrets в документации.

## Acceptance criteria

### A1. Checkout видит Yandex SFS

Дано: адрес клиента и магазин, где включен Yandex SFS.

Ожидаемо:

- delivery options содержат SFS Yandex interval;
- interval содержит `carrierId = yandexNextDayDelivery`;
- interval содержит `fulfillmentTypeId = sfs`;
- пользовательское отображение соответствует решению по express/courier grouping.

### A2. Заказ создается с правильными OMS fields

Дано: пользователь выбирает Yandex SFS interval.

Ожидаемо:

- Integration отправляет в OMS заказ с:
  - `deliveryTypeId = delivery`;
  - `fulfillmentTypeId = sfs`;
  - `carrierId = yandexNextDayDelivery`;
  - `carrierTariffId` из выбранного interval;
- заказ не попадает в OTS flow.

### A3. Integration export использует новый справочный тип

Дано: OMS запускает export для SFS заказа.

Ожидаемо:

- CBR/export mapping возвращает новый `SFS_YANDEX`;
- не используется старый `YANDEX = 10`;
- barcode/name соответствуют справочнику;
- CDEK SFS продолжает отдавать `SFS_CDEK`.

### A4. OMS/Camunda проходит SFS Yandex route

Дано: созданный Yandex SFS заказ.

Ожидаемо:

- `releaseProcess` идет по SFS route в `1c-cbr`;
- `dispatchProcess` выбирает Yandex-compatible route;
- `carrierRegistryProcess` или отдельный Yandex process не зависает на CDEK-only condition;
- статусы заказа и позиций соответствуют согласованному lifecycle.

### A5. OMS Delivery успешно регистрирует/вызывает Yandex

Дано: заказ готов к регистрации/вызову courier/order.

Ожидаемо:

- OMS Delivery вызывает правильный Yandex API;
- сохраняется внешний идентификатор заявки/заказа/claim;
- retry/error handling работает по согласованным правилам;
- в логах нет ошибок contract mismatch.

### A6. ARM/Gloria Retail принимает и выдает заказ

Дано: Yandex SFS заказ дошел до магазинного контура.

Ожидаемо:

- ARM import видит заказ;
- локальный документ содержит Yandex transport company, а не CDEK;
- UI выдачи курьеру доступен;
- после выдачи ARM отправляет статус в Integration;
- Integration обновляет OMS order status и item statuses.

### A7. Status lifecycle закрывается

Дано: заказ выдан курьеру и доставлен/завершен.

Ожидаемо:

- ARM statuses и Yandex tracking не конфликтуют;
- финальный OMS order status корректен;
- item statuses корректны;
- повторные callbacks/polls идемпотентны.

### A8. Carrier switch работает

Дано: Yandex выключают для тестового магазина.

Ожидаемо:

- Yandex SFS interval исчезает;
- CDEK SFS interval остается, если CDEK включен;
- новые Yandex SFS заказы не создаются;
- существующие Yandex SFS заказы продолжают свой lifecycle или обрабатываются по согласованному fallback.

## Regression checks

- SFS CDEK happy path без изменений.
- CDEK courier-call через `CdekCourierRequestServiceImpl`.
- Не-SFS Yandex scenario, если он есть на контуре, не начинает отображаться как SFS express.
- OTS warehouse Yandex/other carrier flows не затронуты.
- customer-api-web response shape совместим с site/mobile.

## Suggested test cases

| ID | Сценарий | Ожидаемый результат |
|---|---|---|
| T-01 | Получить delivery intervals для магазина с Yandex SFS | Есть interval `sfs + yandexNextDayDelivery`. |
| T-02 | Создать заказ Yandex SFS | OMS order содержит правильные shipping fields. |
| T-03 | Проверить CBR export | Delivery type = `SFS_YANDEX`. |
| T-04 | Пройти Camunda до carrier registry | Выбран Yandex route, нет CDEK-only dead end. |
| T-05 | Зарегистрировать/вызвать Yandex courier/order | Получен внешний id, process идет дальше. |
| T-06 | Импортировать заказ в ARM | ARM видит Yandex SFS и создает корректный документ. |
| T-07 | Выдать заказ курьеру в ARM | Integration получает статус, OMS обновлен. |
| T-08 | Завершить доставку | Финальные статусы корректны. |
| T-09 | Отменить до регистрации в Yandex | OMS/retail/Yandex не расходятся. |
| T-10 | Отменить после регистрации в Yandex | Внешняя отмена и OMS statuses корректны. |
| T-11 | Выключить Yandex для магазина | Новые intervals не показывают Yandex, CDEK работает. |
| T-12 | Проверить CDEK SFS regression | Старый flow проходит без изменений. |

## Evidence to collect during QA

- order id / client order id;
- selected delivery interval payload without personal data;
- Integration create-order request fields without personal data;
- OMS order shipping fields;
- Camunda process instance id;
- OMS Delivery Yandex request/response summary without secrets;
- ARM document id;
- status update request from ARM to Integration;
- final OMS order/item statuses.

## Go/no-go

Go:

- все A1-A8 выполнены на тестовом контуре;
- CDEK regression зеленый;
- есть понятный operational switch для Yandex;
- retail и OMS подтверждают готовность своих релизов.

No-go:

- нет нового справочного delivery type;
- Yandex route в Camunda зависает или проходит через CDEK-only logic;
- ARM не может принять/выдать Yandex SFS;
- невозможно отключить Yandex отдельно от CDEK;
- статусы ARM/Yandex конфликтуют и ломают финализацию заказа.

