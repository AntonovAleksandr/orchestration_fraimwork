# Яндекс Экспресс SFS — one-pager

**Дата актуализации:** 2026-07-10

**Источник требований:** `OPSOMN002-46`

**Статус:** уточнение контрактов и декомпозиция e-commerce scope

## Что строим

Отдельный способ доставки **«Яндекс Экспресс»**: заказ собирает магазин, Яндекс доставляет его клиенту день в день, ориентир SLA — до двух часов.

Это не `yandexNextDayDelivery`: тот сценарий относится к доставке со склада в ПВЗ. Для Express нужен отдельный carrier Starfish24, но операционный lifecycle заказа должен повторять существующий SFS CDEK.

## Что считается готовым в OMS

По сообщению команды Starfish24:

- интеграция Яндекс Экспресс есть в новых версиях OMS;
- необходима конфигурация под GJ и пилотные магазины;
- ориентир Starfish24 — 1–2 недели.

Это внешняя зависимость, а не подтвержденный e-commerce API contract. До оценки и реализации Starfish24 должен предоставить пример delivery interval и OMS order. Точный `carrierId` пока намеренно обозначается как `<STARFISH_YANDEX_EXPRESS_CARRIER_ID>`.

## Бизнес-правила MVP

- Только SFS: магазин → клиент.
- Пилот: Северо-Запад и Сибирь.
- Express показывается дополнительно к стандартной доставке, в том числе при наличии складской альтернативы.
- Магазин выбирается по полноте комплектации ↓, затем дистанции ↑.
- Стоимость динамическая, из оффера Яндекса; фиксированные 299 ₽ и free-delivery threshold не действуют.
- Только онлайн-предоплата.
- Express показывается только в рабочее окно магазина с учетом SLA сборки и передачи курьеру.
- При отсутствии/истечении оффера Яндекса Express не предлагается.

## Граница ответственности

| Зона | Ответственность |
|---|---|
| Starfish24 | Настроить готовый carrier, availability по магазинам/регионам, ranking, store hours/cutoff, dynamic quote, prepaid, registration/cancel/status flow. |
| Integration | Принять выбранный interval, передать его carrier/fulfillment/tariff/cost в OMS, добавить учетные mappings для CBR/ARM и legacy paths. |
| customer-api-web | Преобразовать новый carrier в отдельный frontend method `express`, вернуть совместимые Site/Mobile contracts и обеспечить commit выбранного interval. |
| Site | Отдельная Express-card, выбор интервала, динамическая цена, отсутствие free threshold, prepaid-only, stale-offer UX. |
| Mobile | Тот же функциональный scope; текущая кодовая база не содержит полноценного Express method/routing/state. |
| Retail/ARM/1C | Принять carrier/учетный тип в существующий SFS lifecycle и подтвердить выдачу курьеру/обратные статусы. |

## Подтвержденные e-commerce gaps

- В Integration есть только `YANDEX = yandexNextDayDelivery`; отдельного Express carrier enum/mapping нет.
- V4 order create уже generic: переносит `fulfillmentType`, `carrierId` и selected interval из server-side результата.
- customer-api-web считает Express только `carrierId == gjexpress`.
- В новом BFF contract предусмотрен method `express`, но часть response formatting не завершена.
- Site имеет поле `deliveryExpress`, но не имеет `EXPRESS` в активном `DeliveryMethodEnum` и checkout state flow.
- Mobile содержит текст «Экспресс», но не имеет полноценного method, route и selection/commit flow.

## Оценка

Старую оценку e-commerce `2–3 дня` считать недействительной. Она покрывала преимущественно Integration/customer-api-web и не учитывала Site и Mobile.

Оценивать следует параллельными потоками после получения контракта Starfish24:

1. Integration + customer-api-web.
2. Site.
3. Mobile.
4. Межкомандный E2E и rollout.

Календарный срок определяется максимумом потоков плюс готовность Starfish24/Retail, а не суммой трудозатрат.

## Обязательные открытые вопросы

1. **Starfish24:** пример JSON interval/order и точные значения `carrierId`, `carrierTariffId`, `deliveryTypeId`, `fulfillmentTypeId`, price/payment fields, offer TTL.
2. **Starfish24:** где применяется ranking полнота ↓ / дистанция ↑ и как учитываются рабочие часы источника.
3. **Retail/1C:** нужен ли отдельный учетный код `SFS_YANDEX_EXPRESS`; его code/name/barcode/good id.
4. **Продукт/операции:** точный список магазинов/городов и минимальный buffer до закрытия магазина.
5. **Release:** Site и Mobile запускаются одной волной или независимо.

## Go/no-go

Go возможен только если получен payload contract, Express появляется отдельной опцией на обоих клиентах, цена/предоплата корректны, закрытые магазины не дают offer, SFS CDEK не регрессировал и тестовый заказ прошел store → courier → delivered/cancelled.
