# Code-space mapping: SFS Yandex

Дата: 2026-06-28

Цель: не смешивать разные идентификаторы доставки. Для этой задачи похожие значения живут в разных системах и не являются взаимозаменяемыми.

## Основная таблица

| Пространство | Текущее/целевое значение | Где живет | Статус | Комментарий |
|---|---|---|---|---|
| OMS carrier id | `yandexNextDayDelivery` | OMS / Integration | подтверждено | Carrier уже есть в Integration и OMS Delivery. |
| Integration OMS carrier enum | `CarrierIdEnum::YANDEX = 'yandexNextDayDelivery'` | `platform/integration/integration/www/app/Service/Consts/Enums/Delivery/Oms/CarrierIdEnum.php` | подтверждено | Это carrier, а не delivery type. |
| OMS Delivery carrier enum | `YANDEX_NEXT_DAY_DELIVERY("yandexNextDayDelivery")` | `platform/starfish24/core/Delivery/src/main/java/com/starfish24/delivery/service/carrier/CarrierEnum.java` | подтверждено | Используется в Yandex Next Day сервисах. |
| OMS delivery type | `delivery` | order shipping payload | гипотеза target | Как у SFS CDEK courier delivery. |
| OMS fulfillment type | `sfs` | order shipping payload | гипотеза target | Доставка из магазина. |
| Новый 1C/retail delivery type | `SFS_YANDEX = <код>` | 1C/retail справочник, Integration enum | открыто | Код должен дать владелец справочника. |
| Существующий Integration delivery type | `YANDEX = 10` | `DeliveryTypeCodeEnum.php` | подтверждено | Не переиспользовать для SFS без подтверждения. |
| Существующий SFS CDEK type | `SFS_CDEK = 111` | `DeliveryTypeCodeEnum.php` | подтверждено | Эталон для нового SFS Yandex правила. |
| Существующий SFS GJ Express type | `SFS_GLORIAJEANS_EXPRESS = 114` | `DeliveryTypeCodeEnum.php` | подтверждено | Не равен Yandex SFS. |
| Carrier barcode | `CarrierBarcodeEnum::YANDEX = '4660651329002'` | Integration GloriaJeans mapping | подтверждено | Нужно подтвердить, использовать ли его для `SFS_YANDEX`. |
| Delivery good id | `YANDEX => 'UPR010640F0001'` | `DeliveryGoodIdMap.php` | подтверждено | Good id доставки не доказывает готовность SFS-типа. |
| OTS carrier id | `9` для Yandex | Integration OTS mapping | подтверждено, но не target | Для SFS OTS не должен участвовать. |
| customer-api-web express carrier | `gjexpress` | `CommonDeliveryData::EXPRESS_CARRIER_ID` | подтверждено | Сейчас `yandexNextDayDelivery` не попадет в express-блок. |
| ARM transport company enum | `Tk.CDEK` в найденном SFS main-коде | Gloria Retail / ARM | подтверждено для CDEK, открыто для Yandex | Нужна retail-ветка/релиз с Yandex. |

## Target mapping rule

Целевое правило в Integration:

```text
deliveryTypeId = delivery
fulfillmentTypeId = sfs
carrierId = yandexNextDayDelivery
=> delivery_type_code = SFS_YANDEX
=> delivery_type_name = <название из справочника>
=> barcode = <подтвердить: CarrierBarcodeEnum::YANDEX или новый код>
```

## Что нельзя считать эквивалентным

- `CarrierIdEnum::YANDEX` не равен `DeliveryTypeCodeEnum::YANDEX`.
- `DeliveryTypeCodeEnum::YANDEX = 10` не равен новому `SFS_YANDEX`.
- OTS Yandex carrier id `9` не означает, что OTS участвует в SFS.
- `DeliveryGoodIdMap` не заменяет delivery type mapping.
- `gjexpress` в customer-api-web не означает Yandex Express.

## Файлы для проверки при реализации

Integration:

- `platform/integration/integration/www/app/Service/Consts/Enums/Delivery/Oms/CarrierIdEnum.php`
- `platform/integration/integration/www/app/Service/Consts/Enums/Delivery/GloriaJeans/DeliveryTypeCodeEnum.php`
- `platform/integration/integration/www/app/Service/Consts/Enums/Delivery/GloriaJeans/DeliveryTypeCodeNameEnum.php`
- `platform/integration/integration/www/app/Service/Consts/Enums/Delivery/GloriaJeans/CarrierBarcodeEnum.php`
- `platform/integration/integration/www/app/Service/Consts/Maps/Delivery/Arm/DeliveryGoodIdMap.php`
- `platform/integration/integration/www/app/Service/Consts/Contracts/Maps/Delivery/GloriaJeans/DeliveryTypeCodeMapByRulesContract.php`
- `platform/integration/integration/www/app/Service/Consts/Contracts/Maps/Delivery/GloriaJeans/DeliveryTypeCodeNameMapByRulesContract.php`
- `platform/integration/integration/www/app/Service/Consts/Contracts/Maps/Delivery/Cbr/DeliveryTypeCodeMapByRulesContract.php`
- `platform/integration/integration/www/app/Service/UserApi/Services/V1/Order/OrderService.php`
- `platform/integration/integration/www/app/Service/UserApi/Mutators/V1/Order/OrderExportCbrMutator.php`

OMS:

- `platform/starfish24/core/Delivery/src/main/java/com/starfish24/delivery/service/carrier/CarrierEnum.java`
- `platform/starfish24/core/Delivery/src/main/java/com/starfish24/delivery/service/carriers/yandexNextDayDelivery/YandexNextDayDeliveryCalculationServiceImpl.java`
- `platform/starfish24/core/Delivery/src/main/java/com/starfish24/delivery/service/carriers/yandexAnotherDay/YandexAnotherDayOrderRegistrationServiceImpl.java`
- `platform/starfish24/core/Delivery/src/main/java/com/starfish24/delivery/service/carriers/yandexAnotherDay/YandexAnotherDayTrackingRequestServiceImpl.java`
- `platform/starfish24/awg/bpmn-process/process/gloriajeans/releaseProcess.bpmn`
- `platform/starfish24/awg/bpmn-process/process/gloriajeans/dispatchProcess.bpmn`
- `platform/starfish24/awg/bpmn-process/process/gloriajeans/carrierRegistryProcess.bpmn`

customer-api-web:

- `platform/ensi/apps/customers-api-web/app/Domain/Orders/Data/Checkout/CommonDeliveryData.php`
- `platform/ensi/apps/customers-api-web/app/Domain/Orders/Actions/GetDeliveryDataAction.php`
- `platform/ensi/apps/customers-api-web/app/Domain/Orders/Actions/GetDeliveryDataV2Action.php`
- `platform/ensi/apps/customers-api-web/app/Domain/Orders/Actions/GetCheckoutGeneralDataDeliveryDataAction.php`

