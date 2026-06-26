# Stage 04 — OTS / ТК: сроки и стоимости доставки

**Статус:** pending · **BP-якорь:** docs/bp/06 · **Требования R-20:** FR-4, FR-15, FR-18

## 0. Scope и гипотезы
- Запрос **сроков** и **стоимости** доставки по выбранным складам/отправлениям (для чекаута, FR-15).
- Сохранение **реальной стоимости доставки от ТК** для каждого отправления (для отчётов, FR-18).
- Тип отправления по доставке (CR/CC/SFS/SFS-ПВЗ/курьер/самовывоз) — FR-4.
- ТК: CDEK, DPD, Почта России, ПВЗ/курьер.
- **Гипотеза:** ОТС умеет запрашивать у ТК по заказу, но «по комбинации складов в рамках одного
  родительского заказа (несколько отправлений)» и сохранение реальной стоимости per shipment — уточнить.

## Ключевые источники / таргеты
- Код: `platform/gloriaots/gloriaots/src` (ShipmentServices, OrderTracking, WmsSync, EventBus),
  `platform/starfish24/core/{Delivery,5post-connector,cdek-api-sdk}`.
- БД: `gloria_ots_prod`, `oms-awg-five-post-connector-prod`, `oms-awg-dictionary-prod`.
- Доки: `docs/research/delivery-carrier-codes-end-to-end.md`,
  `docs/research/surf-mini-rewrite/deep-dive/stages/stage-09b-ots-dpd-cdek-pvz.md`.
- Jira: `OPSLOG-3169` (DPD ORDER_SPLIT), `OPSOMN-8670`/`-8698` (СДЕК/складские).
- Делегировать: `gloriaots-researcher`, `oms-researcher`.

## 1–8 — по `../TEMPLATE-stage.md`
