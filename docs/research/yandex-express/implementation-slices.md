# Implementation slices: SFS Yandex

Дата: 2026-06-28

Цель: разложить интеграцию по независимым зонам работ. Это не финальный implementation plan с кодом, а аналитическая нарезка для заведения задач.

## Slice 0. Справочники и договоренности

Владелец: 1C/retail + аналитик.

Вход:

- подтверждено, что carrier в OMS остается `yandexNextDayDelivery`;
- подтверждено, что нужен новый SFS delivery type.

Что сделать:

- назначить код нового delivery type `SFS_YANDEX`;
- назначить пользовательское и учетное название;
- подтвердить barcode ТК;
- подтвердить delivery good id или необходимость нового;
- описать, как новый тип должен отображаться в 1C/ARM.

Выход:

- таблица справочных значений;
- ссылка на задачу/заявку справочника;
- дата/релиз готовности retail/1C.

## Slice 1. OMS Delivery/logistics availability

Владелец: OMS Delivery/logistics.

Что сделать:

- понять, где сейчас включается SFS CDEK по магазинам/городам/тарифам;
- добавить или настроить availability для `yandexNextDayDelivery` в SFS;
- обеспечить возможность отключить Yandex без отключения CDEK;
- проверить, что checkout получает selected interval с:
  - `deliveryTypeId = delivery`;
  - `fulfillmentTypeId = sfs`;
  - `carrierId = yandexNextDayDelivery`;
  - корректным `carrierTariffId`.

Выход:

- документированная точка управления включением carrier;
- тестовый магазин/город, где Yandex SFS включен;
- тестовый магазин/город, где остается только CDEK.

## Slice 2. OMS Delivery Yandex carrier flow

Владелец: OMS Delivery.

Что сделать:

- выбрать целевой API-паттерн для SFS Yandex:
  - courier-call service;
  - order registration/confirmation;
  - claim create/accept/info;
  - отдельный комбинированный flow;
- проверить, подходят ли существующие `YandexAnotherDay*` сервисы для pickup from store;
- если нужен courier-call, реализовать сервисы, аналогичные CDEK contract:
  - `CourierRequestService`;
  - `CallCourierStatusService`;
- определить статусную модель Yandex: какие внешние статусы обновляют OMS, какие только логируются.

Выход:

- API contract для Camunda activities;
- happy-path request/response examples без секретов;
- список ошибок и retry behavior.

## Slice 3. OMS/Camunda process

Владелец: OMS/Camunda.

Что сделать:

- обновить `releaseProcess.bpmn`, если gateway "SFS и CDEK?" должен покрывать Yandex;
- обновить `dispatchProcess.bpmn` для `carrierId == 'yandexNextDayDelivery'`;
- обновить `carrierRegistryProcess.bpmn` или создать отдельный process для Yandex SFS;
- зафиксировать, какие статусы выставляются до и после регистрации/вызова курьера;
- проверить отмену заказа после регистрации в Yandex.

Выход:

- BPMN route для SFS Yandex;
- тест процесса на Camunda test stand;
- rollback: отключить Yandex availability без изменения CDEK.

## Slice 4. Integration Service mapping

Владелец: Integration.

Что сделать после Slice 0:

- добавить `SFS_YANDEX` в `DeliveryTypeCodeEnum.php`;
- добавить имя в `DeliveryTypeCodeNameEnum.php`;
- добавить rule `DELIVERY + SFS + YANDEX -> SFS_YANDEX` в GloriaJeans mapping;
- добавить name mapping;
- добавить CBR mapping;
- добавить ветки в старом V1 order resolver и CBR mutator, если они остаются активными;
- проверить, нужен ли ecom export mapping.

Файлы-кандидаты:

- `platform/integration/integration/www/app/Service/Consts/Enums/Delivery/GloriaJeans/DeliveryTypeCodeEnum.php`
- `platform/integration/integration/www/app/Service/Consts/Enums/Delivery/GloriaJeans/DeliveryTypeCodeNameEnum.php`
- `platform/integration/integration/www/app/Service/Consts/Contracts/Maps/Delivery/GloriaJeans/DeliveryTypeCodeMapByRulesContract.php`
- `platform/integration/integration/www/app/Service/Consts/Contracts/Maps/Delivery/GloriaJeans/DeliveryTypeCodeNameMapByRulesContract.php`
- `platform/integration/integration/www/app/Service/Consts/Contracts/Maps/Delivery/Cbr/DeliveryTypeCodeMapByRulesContract.php`
- `platform/integration/integration/www/app/Service/UserApi/Services/V1/Order/OrderService.php`
- `platform/integration/integration/www/app/Service/UserApi/Mutators/V1/Order/OrderExportCbrMutator.php`

Выход:

- unit/contract tests на mapping;
- тестовый create/export order с `delivery + sfs + yandexNextDayDelivery`;
- подтверждение, что CDEK SFS не изменился.

## Slice 5. customer-api-web / Site / Mobile

Владелец: customer-api-web + frontend.

Что решить:

- Yandex SFS должен быть отдельным express-блоком или обычной courier delivery?
- Если express-блоком, классификация должна учитывать только carrier или carrier + fulfillment type?

Что сделать:

- расширить `CommonDeliveryData::isExpressDelivery()` или завести более точную классификацию;
- обновить grouping в delivery data actions;
- обновить тесты response shape;
- согласовать текст/название для пользователя.

Риск:

- `yandexNextDayDelivery` может использоваться не только для SFS. Если просто добавить его в express carriers, можно изменить отображение других сценариев.

## Slice 6. Retail/ARM/1C

Владелец: retail/ARM/1C.

Что подтвердить:

- import SFS order понимает `yandexNextDayDelivery`;
- локальный документ создается не только с `Tk.CDEK`;
- UI выдачи курьеру работает для Yandex;
- статусы уходят в Integration тем же contract;
- документ "ВыдачаКурьеру" в 1C/Rabbit содержит корректную ТК;
- релиз retail синхронизирован с ecom/OMS rollout.

Выход:

- ссылка на retail задачу/ветку;
- тестовый сценарий выдачи курьеру;
- подтверждение обратных статусов в OMS.

## Slice 7. QA / E2E rollout

Владелец: QA + все команды.

Что сделать:

- подготовить тестовый магазин с CDEK-only;
- подготовить тестовый магазин с Yandex SFS;
- подготовить товар/остаток/адрес клиента;
- выполнить happy path;
- выполнить cancellation path до и после регистрации в Yandex;
- выполнить fallback: отключение Yandex, CDEK продолжает работать;
- проверить логи Integration, OMS, OMS Delivery, retail.

Выход:

- e2e протокол;
- список order ids;
- trace/log anchors без персональных данных;
- go/no-go по rollout.

