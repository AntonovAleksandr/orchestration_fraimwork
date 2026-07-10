# checkout — PVZ live smoke: areaViewPort confirmed; OMS v2 response is GROUPED (client mismatch)

**Дата:** 2026-07-02 · **Статус:** live evidence (stage OMS api-gateway v2) · **Автор:** Zak + Claude
**Связано:** план `docs/superpowers/plans/2026-07-02-checkout-pvz-real-clustering.md`, спека `docs/superpowers/specs/2026-05-29-checkout-service-design.md` §3/§11.7, клиент `platform-new/clients/starfish-oms`

## Summary

Live-smoke `POST /logistics/pickup-points` v2 на stage (port-forward `api-gateway-v2` → `localhost:18081`, city `mosk-941139`, 4 SKU) дал два результата:

1. **`areaViewPort` подтверждён live — §11.7 закрыта окончательно.** Форма (из `core/go/logistics/internal/domain/models.go`) `corners.leftTop/rightBottom.coordinates.{latitude,longitude}` работает: OMS фильтрует точки по bbox.

   | Запрос | Точек | Объём | Время |
   |---|---|---|---|
   | Без `areaViewPort` (весь город) | **3967** | 2.28 МБ | 0.69с |
   | С `areaViewPort` (центр Москвы 0.06°×0.10°) | **230** | 134 КБ | 0.20с |

   Перевозчики: 5post 1766 / russianpost 999 / cdek 841 / yandexNextDayDelivery 181 / dpd 180 — совпадает с design-спекой §3 (~3963 / 3.5 МБ).

2. **Блокер: реальный v2-ответ — GROUPED, не bare-array.** OMS отдаёт
   `{data:[{logisticGroupId, logisticRuleId, inventory, pickupPoints.list[]}], availableFiltersValues}`,
   а клиент `starfish-oms` (и checkout `rawPVZ`) смоделированы по неверной фикстуре как bare-array `[]PickupPointOption` с `instock`/`productAvailability`/`orderDimensionsExceeded` **на точке**. На live `client.GetPickupPoints` упадёт при декодинге (ожидает массив, OMS шлёт object). План T3 Task 2 (`reencode PickupPointOption → rawPVZ`) невалиден as-is.

## Реальная форма v2 `pickup-points` (авторитет — live)

```
{
  "data": [ {
    "logisticGroupId": "RU-77",
    "logisticRuleId":  "...",
    "inventory": {
      "availableQuantity": int,
      "cartAvailabillity": [{productId, availableQuantity, available}],  // NB: OMS typo double-l (как в delivery-intervals)
      "dispatchDate":       "2026-07-02",
      "dispatchWarehouse":  "00005550015678154",                          // NB: key = dispatchWarehouse (не ...Id)
      "fulfillmentType":    "fulfillment..."
    },
    "pickupPoints": { "list": [ {
      "id":                   "dpd-7P49",          // = carrier-originalId
      "name":                 "...",
      "type":                 "pickupservice"|"postmate",
      "coordinates":          {latitude, longitude},
      "date":                 "2026-07-03",        // единая дата (НЕ отдельные dispatchDate/deliveryDate)
      "deliveryCost":         299,                 // рубли
      "actualDeliveryCost":   195.2,
      "carrierId":            "dpd",
      "tariffId":             "PCLPVZ",
      "limitsExceeding":      {orderDimensionsExceeded, orderWeightExceeded, orderPackageWeightExceeded},
      "availablePaymentTypes":["cod","prepaid"],
      "availableAcquirers":   ["yookassa"],
      "shelfLifeDays":        7
    } ] }
  } ],
  "availableFiltersValues": { "carrierIds": ["cdek","dpd","5post","yandexNextDayDelivery","russianpost"] }
}
```

**Ключевые отличия от текущей модели клиента/rawPVZ:**
- **coverage «X из N» на ГРУППЕ** (`inventory.cartAvailabillity`), общий для всех ПВЗ группы; у точки НЕТ `instock`/`productAvailability`.
- **oversize-флаги вложены** в `limitsExceeding{...}`, не top-level.
- У точки НЕТ `originalId`/`dispatchDate`/`deliveryDate`/`maxWaitingDays`/`paymentTypeId`; есть `date` (единая) + `shelfLifeDays` + `availableAcquirers` + `availablePaymentTypes`.
- Конверт `availableFiltersValues.carrierIds` — список перевозчиков в viewport (для фильтра карты).
- Один `logisticGroupId` (RU-77) на всю Москву — группировка пока не granular, но контракт держит.

## Приоритеты / следующие шаги

1. **Править клиент `starfish-oms` (путь A)** — реальный тип `PickupPointsResponse{Data []PickupPointGroup, AvailableFiltersValues}` + `PickupPointGroup{LogisticGroupId, LogisticRuleId, Inventory, PickupPoints.List}` + `PickupPoint{LimitsExceeding, ShelfLifeDays, AvailableAcquirers}` + `LimitsExceeding{...}`. Снять live-фикстуру → заменить `testdata/pickup-points.json` (bare-array → grouped object). Regen, тесты, тег, bump в `checkout/go.mod`. Мини-план: `docs/superpowers/plans/2026-07-02-starfish-oms-pickup-points-grouped.md` (TODO).
2. **Обновить план T3** — Task 2 переписать под grouped: `reencode PickupPointsResponse → rawPVZResponse → normalizePickupPointsGrouped` (coverage из `inventory.cartAvailabillity` группы → на каждую точку группы; oversize из `limitsExceeding`; `date` → `PromisedDate`).
3. `markPVZDeferred` удалить (D4) — baseline подтвердил: OMS preliminary отдаёт `pickup` с `available:true, coverage=2`, форс `markPVZDeferred` делает `available:false`. После D4 → `pvz` карточка покажется.

## Куда копать

- Live evidence: `platform-new/checkout/fixtures/oms-live/{pickup-points-areaViewPort-center-msk.json, pickup-points-no-areaViewPort-msk.json}` (gitignored; /tmp → fixtures).
- OMS-исходник формы: `platform/starfish24/core/go/logistics/internal/domain/models.go` (`AreaViewport`/`PickupPointsResponse`/`PickupPointGroup`), `internal/service/pickup_point_service.go` (`filterPickupPointsByAreaViewport` — leftTop/rightBottom).
- Клиент: `platform-new/clients/starfish-oms/{openapi.gen.go (PickupPointOption/PickupPointsRequest), client.go:248 GetPickupPoints, testdata/pickup-points.json, docs/superpowers/specs/2026-05-30-starfish-oms-client-design.md §4.6}`.
- Checkout адаптер: `internal/adapters/delivery/{raw.go (rawPVZ), resolver.go (normalizePickupPoints), oms.go (Options(PVZ)→nil deferred)}`.

## Trace / воспроизведение

```bash
# port-forward api-gateway-v2 → localhost:18081, .env с OMS_SERVICE_CLIENT_ACCESS_TOKEN
curl -X POST localhost:18081/v2/logistics/pickup-points \
  -H "Authorization: Bearer $OMS_SERVICE_CLIENT_ACCESS_TOKEN" -H 'Content-Type: application/json' \
  -d '{"addressTo":{"city":{"id":"mosk-941139","name":"Москва"}},
       "cart":{"items":[{"id":"GRA000042F0001","quantity":1},{"id":"GDR026602F0007","quantity":1},
                        {"id":"GHS007209F0002","quantity":1},{"id":"GJN035587F0005","quantity":1}]},
       "areaViewPort":{"corners":{"leftTop":{"coordinates":{"latitude":55.78,"longitude":37.55}},
                                  "rightBottom":{"coordinates":{"latitude":55.72,"longitude":37.65}}}}}'
```
SKU взяты из `internal/adapters/delivery/testdata/` (валидные на stage). Basket `smoke-001`, customer `4455421`.
