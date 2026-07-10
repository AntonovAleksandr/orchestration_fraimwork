# Code-space mapping: Yandex Express SFS

Дата актуализации: 2026-07-10

Цель: не смешивать frontend method, OMS carrier, fulfillment, учетный тип Retail/1C и исторический Yandex Next Day.

## Target mapping

| Пространство | Значение | Статус | Комментарий |
|---|---|---|---|
| Frontend delivery method | `express` | принято | Отдельная карточка «Яндекс Экспресс», не обычный courier/CDEK. |
| customer-api-web grouping | новый Express carrier → `express` / `deliveryExpress` | требуется доработка | Сейчас Express определяется только через `gjexpress`. |
| OMS carrier id | `<STARFISH_YANDEX_EXPRESS_CARRIER_ID>` | **открытый вопрос Starfish24** | Должен быть отдельным от `yandexNextDayDelivery`. |
| OMS carrier tariff id | `<STARFISH_YANDEX_EXPRESS_TARIFF_ID>` | **открытый вопрос Starfish24** | Берется из delivery interval. |
| OMS delivery type | ожидаемо `delivery` | требует payload | Сохраняет CDEK-like SFS lifecycle; не фиксировать до примера Starfish24. |
| OMS fulfillment type | `sfs` | бизнес-требование | Источник — магазин. |
| OMS dispatch warehouse | id выбранного магазина | бизнес-требование | Магазин выбирается ranking rules, не фронтом. |
| Delivery cost | динамическая цена interval | бизнес-требование | Front/Integration не заменяют ее на 299 ₽ и не применяют free threshold. |
| Payment types | только `prepaid` | бизнес-требование | Должно приходить в server-side option contract. |
| Integration carrier enum | новый `YANDEX_EXPRESS = <carrierId Starfish24>` | требуется | Не менять значение существующего `YANDEX`. |
| Retail/1C delivery type | `SFS_YANDEX_EXPRESS = <код>` либо согласованный существующий SFS-код | открыто | Решение владельца справочника; отдельный UI method сам по себе не требует нового 1C-кода. |
| Delivery good id / barcode | `<подтвердить Retail/1C>` | открыто | Существующее значение Яндекса не доказывает совместимость с Express SFS. |
| OTS transport id | не используется | target boundary | SFS остается вне OTS при подтверждении Starfish24. |

## Что уже существует и не является target

| Значение | Значение в системе | Почему нельзя переиспользовать автоматически |
|---|---|---|
| `CarrierIdEnum::YANDEX` | `yandexNextDayDelivery` | Склад → ПВЗ, другой продукт и lifecycle. |
| `DeliveryTypeCodeEnum::YANDEX` | `10` | Учетный тип существующего не-SFS Яндекса. |
| `SFS_GLORIAJEANS_EXPRESS` | `114` | Существующий GJ Express, не доказано соответствие Яндекс Экспресс. |
| `CommonDeliveryData::EXPRESS_CARRIER_ID` | `gjexpress` | Текущая BFF-классификация только одного carrier. |
| `DeliveryGoodIdMap::YANDEX` | `UPR010640F0001` | Может относиться к текущему Яндекс-контракту; подтвердить у Retail/1C. |

## Ожидаемый server-side contract

До ответа Starfish24 это шаблон, а не финальная спецификация:

```json
{
  "carrierId": "<STARFISH_YANDEX_EXPRESS_CARRIER_ID>",
  "carrierTariffId": "<STARFISH_YANDEX_EXPRESS_TARIFF_ID>",
  "deliveryTypeId": "delivery",
  "fulfillmentTypeId": "sfs",
  "dispatchWarehouseId": "<store-id>",
  "deliveryCost": "<dynamic-price>",
  "availablePaymentTypes": ["prepaid"],
  "date": "<same-day>",
  "from": "<time>",
  "to": "<time>",
  "offerExpiresAt": "<if-supported>"
}
```

## Integration mapping rule

После ответа Starfish24 и Retail/1C:

```text
deliveryTypeId = <from Starfish24>
fulfillmentTypeId = sfs
carrierId = <STARFISH_YANDEX_EXPRESS_CARRIER_ID>
=> delivery_type_code = <Retail/1C decision>
=> delivery_type_name = <Retail/1C decision>
=> delivery_good_id/barcode = <Retail/1C decision>
```

V4 create-order не должен самостоятельно подменять carrier/tariff/cost: server-side selected interval остается source of truth.

## Файлы e-commerce для реализации

Integration:

- `platform/integration/integration/www/app/Service/Consts/Enums/Delivery/Oms/CarrierIdEnum.php`
- `platform/integration/integration/www/app/Service/Consts/Enums/Delivery/GloriaJeans/DeliveryTypeCodeEnum.php`
- `platform/integration/integration/www/app/Service/Consts/Contracts/Maps/Delivery/GloriaJeans/DeliveryTypeCodeMapByRulesContract.php`
- `platform/integration/integration/www/app/Service/Consts/Contracts/Maps/Delivery/Cbr/DeliveryTypeCodeMapByRulesContract.php`
- `platform/integration/integration/www/app/Service/Consts/Maps/Delivery/Arm/DeliveryGoodIdMap.php`
- `platform/integration/integration/www/app/Service/UserApi/Services/V1/Order/OrderService.php`
- `platform/integration/integration/www/app/Service/UserApi/Mutators/V1/Order/OrderExportCbrMutator.php`

customer-api-web:

- `platform/ensi/apps/customers-api-web/app/Domain/Orders/Data/Checkout/CommonDeliveryData.php`
- `platform/ensi/apps/customers-api-web/app/Domain/Orders/Data/Enums/DeliveryType.php`
- `platform/ensi/apps/customers-api-web/app/Domain/Orders/Data/Checkout/DeliveryMethodData.php`
- `platform/ensi/apps/customers-api-web/app/Domain/Orders/Data/Checkout/GeneralDeliveryMethodData.php`

Site/Mobile:

- активные delivery method enums;
- checkout state/mappers;
- delivery cards and interval selection;
- order preview/commit payload;
- payment and analytics handling.
