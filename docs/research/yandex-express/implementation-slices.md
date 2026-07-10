# Implementation slices: Yandex Express SFS

Дата актуализации: 2026-07-10

Это аналитическая нарезка для Epic/Jira, не implementation plan. Оценки выдаются после Slice 0.

## Slice 0. Contract freeze

Владельцы: Starfish24 + e-commerce analyst + Retail/1C.

Получить:

- test delivery interval и resulting OMS order от Starfish24;
- точные carrier/tariff/delivery/fulfillment ids;
- поля dynamic price, payment types и quote TTL;
- OMS version и перечень конфигурации на 1–2 недели;
- источник timezone/working hours/special schedule и cutoff formula;
- Retail/1C решение по accounting type, name, barcode и delivery good id;
- пилотные магазины/города и Mobile release wave.

Выход:

- заполненный `code-space-mapping.md` без placeholder в target contract;
- payload examples без персональных данных/секретов;
- owners и test-stand dates;
- обновленная оценка четырех потоков.

Статус: **открытый вопрос Starfish24 намеренно оставлен блокером**.

## Slice 1. Starfish24 configuration and acceptance

Владелец: Starfish24.

Scope по заявлению команды — настройка существующего capability, ориентир 1–2 недели:

- отдельный carrier Яндекс Экспресс для GJ;
- пилот СЗ/Сибирь и независимый enable/disable по магазинам;
- ranking: fullness desc, distance asc;
- store timezone, regular/special hours, picking SLA и handover cutoff;
- fail-closed при неполной конфигурации магазина;
- dynamic Yandex quote и prepaid-only;
- coexistence с CDEK и warehouse option;
- registration/courier call/cancel/status flow;
- test evidence и rollback switch.

Не включать в e-commerce estimate разработку Yandex connector без отдельного change request от Starfish24.

## Slice 2. Retail/ARM/1C readiness

Владелец: Retail/ARM/1C.

- определить, нужен ли новый `SFS_YANDEX_EXPRESS` accounting type;
- назначить code/name/barcode/good id либо подтвердить переиспользование общего SFS-кода;
- проверить import нового carrier;
- проверить обычную сборку SFS;
- убрать/расширить CDEK-only ограничения выдачи курьеру;
- подтвердить обратные статусы через Integration;
- провести store UAT без изменения операционной инструкции, если процесс действительно идентичен CDEK SFS.

Выход: release/config evidence и один тестовый документ заказа.

## Slice 3. Integration Service

Владелец: Integration.

### Carrier and accounting mappings

- добавить отдельный carrier enum после ответа Starfish24;
- не менять `YANDEX = yandexNextDayDelivery`;
- добавить/подтвердить `SFS_YANDEX_EXPRESS` code/name;
- добавить GloriaJeans/CBR rules;
- обновить active V1 SFS resolver and CBR mutator hardcodes;
- добавить/подтвердить ARM delivery good/barcode mapping;
- проверить recon/export paths;
- не добавлять OTS mapping, если target route — `1c-cbr`.

### Order create contract

- доказать тестом, что V4 переносит selected interval carrier/tariff/fulfillment/store/cost;
- revalidate selected interval at commit;
- возвращать business error при expired/unavailable Express option;
- не подменять Express на CDEK автоматически;
- сохранить `clientOrderId` при повторном выборе доставки/retry.

### Tests

- mapping tests для нового carrier;
- create-order contract fixture из Starfish24 payload;
- stale quote/unavailable interval;
- CDEK SFS regression;
- Yandex Next Day regression.

## Slice 4. customer-api-web

Владелец: ENSI customer-api-web.

- классифицировать новый carrier как Express, не затрагивая NDD;
- old APIs: вернуть его в `deliveryExpress`;
- General Data: вернуть delivery method `express`;
- обработать `EXPRESS` в `DeliveryType::toClientResponse()`;
- передать dynamic cost, prepaid-only, store/interval identity;
- сохранить warehouse and standard courier options;
- поддержать explicit selected Express interval;
- обработать commit error и refresh/reselection;
- contract tests для Site APIs и Mobile V4/V5.

Рекомендуемая модель: reusable semantic method `express`, а не новый frontend API method с carrier-specific именем.

## Slice 5. Site

Владелец: Site frontend.

- добавить `EXPRESS` в active `DeliveryMethodEnum` и checkout state;
- преобразовать BFF `method=express`/`deliveryExpress` в отдельную card;
- показать название, SLA и dynamic price;
- реализовать выбор Express interval/store id;
- переиспользовать courier address без смешения selected methods;
- не применять free-delivery threshold;
- оставить только prepaid и сбросить COD при переключении;
- не скрывать Express из-за warehouse/courier alternative;
- stale offer: refresh и явный выбор клиента;
- analytics: impression/select/unavailable/price/order result;
- component/state/e2e tests.

## Slice 6. Mobile

Владелец: Mobile.

- добавить Express delivery method;
- добавить route/screen mode или безопасно переиспользовать courier screen;
- добавить Express в checkout state, preview и commit;
- показать dynamic price/SLA;
- не применять free threshold;
- prepaid-only и reset incompatible payment;
- coexistence with standard courier;
- stale offer UX;
- analytics и tests;
- server/config gating по поддерживаемым версиям приложения.

Текущая строка `express: "Экспресс"` не уменьшает этот slice: активный method/routing/selection flow отсутствует.

## Slice 7. Cross-system QA

Владельцы: QA + все команды.

Подготовить:

- по одному test store в нескольких timezone пилота;
- store with regular hours, closed store, near-cutoff store, special-day schedule;
- cart available in store and warehouse simultaneously;
- cart available in several stores with different fullness/distance;
- Yandex quote success/unavailable/expired/changed price;
- CDEK-only store and store with both carriers;
- supported Site and Mobile clients.

Собрать evidence:

- raw interval payload;
- selected interval at BFF/Integration;
- OMS order shipping fields;
- Retail document;
- Yandex external id without secrets;
- status/cancellation traces;
- final order/item/payment state.

## Slice 8. Rollout and operations

Владельцы: Product + Operations + Starfish24 + e-commerce.

- independent enable switch per store/region;
- dashboards for quote availability, commit rejection, registration failure and delivery SLA;
- staged enablement across СЗ/Сибирь;
- customer support scripts for stale/unavailable Express;
- rollback by disabling new offers while existing orders finish;
- CDEK availability preserved.

## Dependency graph

```text
Slice 0 Contract freeze
  ├── Slice 1 Starfish24 config
  ├── Slice 2 Retail readiness
  ├── Slice 3 Integration
  ├── Slice 4 customer-api-web
  │      ├── Slice 5 Site
  │      └── Slice 6 Mobile
  └── all ready → Slice 7 E2E → Slice 8 Rollout
```

Site and Mobile should be estimated independently; they may run in parallel after the BFF contract is fixed.
