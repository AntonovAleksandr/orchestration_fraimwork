# OTS/WMS: физически отправленные заказы остаются `PICKING`

**Дата:** 2026-08-26 · **Статус:** read-only code investigation; per-order production logs/DB not available in this session.

## Summary

В текущем коде OTS физическая отгрузка `WMS.AUFSHP` может быть принята и сохранена в `Deliverings`, но не переводит `TGW_CREATE_ORDER_PHASE` в `SHIPMENT`. `WmsService` вернёт `DELIVERING` только когда уже обработан TGW status `AufStatus=4` (`ORDER_PICKUP`). Поэтому при пришедшем `AUFSHP` без доступного/обработанного status-telegram `AufStatus=4` заказ закономерно остаётся в OMS на `PICKING`. Это правдоподобный общий механизм для всей выборки, но не доказательство по каждому заказу без строк WMS/OTS и логов.

## Evidence per order

| `client_order_id` | Сообщённый факт | WMS → OTS receipt/persist | OTS → OMS notification | Итог в этом исследовании |
|---|---|---|---|---|
| 2007129792 | created 2026-08-22, shipped | не проверено | не проверено | нет runtime evidence |
| 2006976659 | 2026-08-22, shipped | не проверено | не проверено | нет runtime evidence |
| 2011122543 | 2026-08-23, shipped | не проверено | не проверено | нет runtime evidence |
| 2010432534 | 2026-08-23, shipped | не проверено | не проверено | нет runtime evidence |
| 2011159967 | 2026-08-23, collected | не проверено | не проверено | нет runtime evidence |
| 2010847134 | 2026-08-23, shipped | не проверено | не проверено | нет runtime evidence |
| 2011116195 | 2026-08-24, collected | не проверено | не проверено | нет runtime evidence |
| 2010868905 | 2026-08-21, shipped | не проверено | не проверено | нет runtime evidence |
| 2011144458 | 2026-08-22, shipped | не проверено | не проверено | нет runtime evidence |
| 2011124675 | 2026-08-22, shipped | не проверено | не проверено | нет runtime evidence |
| 2011053519 | 2026-08-24, shipped | не проверено | не проверено | нет runtime evidence |
| 2010992069 | 2026-08-24, shipped | не проверено | не проверено | нет runtime evidence |
| 2010269407 | shipped, date not supplied | не проверено | не проверено | нет runtime evidence |

The `gj-buddy` production-log/DB tools are not configured in this session; no local log contains these IDs. Local `ots.env` points to a test SQL Server, so it was not used as production evidence.

## Expected chain and likely boundary

1. Non-listener `WmsSync` polls `OTS_TELEGRAM_STORE` for `WMS.AUFSHP`, publishes `TgwSync_IF_OUT_Event(..., SHIPMENT)`, then acknowledges the transaction. `TgwSyncDeliveringLaterReaderService.cs:65-67, 81-94`.
2. `GloriaOTS.Web` consumes it. `TgwSyncEventConsumer.ProcessShipment` only inserts `DeliveringEvent`; the prior phase-changing logic is commented out. `TgwSyncEventConsumer.cs:62-100`.
3. In the tracking loop `WmsService.GetOrderStatus` returns `DELIVERING` only for `TGW_CREATE_ORDER_PHASE=SHIPMENT`, or, in `READED`, when a stored TGW `AufStatus=4` first yields `ORDER_PICKUP` and a `DeliveringEvent` exists. `WmsService.cs:215-236, 279-375`.
4. The tracking worker writes an `OrderEvent`; the notifier publishes only Starfish-source supported states to Kafka. `OrderTrackingService.cs:200-278`, `StarfishOrderStatusNotifier.cs:34-66`, `Starfish/Sender.cs:35-89`.

**Likely boundary:** after WMS physical shipment but before OTS produces its `DELIVERING` `OrderEvent` (high confidence in the code mechanism; low confidence that every listed order follows it). The key missing predicate is an OTS `OrderStatuses` record with `AufStatus=4` and a `Deliverings` record for the same order, or a tracking phase already equal to `SHIPMENT`.

## Outliers and clustering

- All 13 reported states are `shipped` or `collected`, which are compatible with the same `AUFSHP` / status-4 gate.
- Warehouse clustering cannot be concluded: local production compose has independent `NSK` and `MSK` WmsSync pollers and queues, but no order-to-warehouse runtime data was available. `docker-compose.nsk.prod.yml:4-41`, `docker-compose.msk.prod.yml:4-41`.
- `OrderLaterNotificationService` is not in the worker health check, so an OMS-notification backlog is a separate possible downstream boundary. It would require `OrderEvents.Notificated=false` or Starfish Kafka publish errors, not merely OMS status `PICKING`.

## Safe next checks and owners

1. **OTS/WMS owner:** for every ID, query `OTS_TELEGRAM_STORE`/`OTS_TRANSACTIONS`, `IFOUT_T` (`IFOUTFSRSTA`, `ALARMTXT`, `TRXID`) and OTS `OrderStatuses`, `Deliverings`, `OrderTrackingParams`, `OrderEvents`. Establish received → persisted → emitted timestamps and warehouse.
2. **OTS owner:** search `WmsSync`/`Web` logs by order ID and `TRXID` for `WMS.AUFSHP`, `TgwSync_IF_OUT_Event`, `Error process event`, `Incomplete transaction`, `Unknown order id`; confirm worker health and the single active non-listener poller for the affected warehouse.
3. **OTS owner:** if `Deliverings` exists but no status-4, validate/repair the missing WMS status feed before any replay. If status-4 and `Deliverings` both exist but no `DELIVERING` `OrderEvent`, investigate cache/phase/worker execution and use an audited, idempotent compensating event only under the OTS runbook.
4. **Integration/OMS owner:** only after OTS has a `DELIVERING` `OrderEvent`, check Starfish Kafka publish and BP-INT-30 consumption. Do not manually alter OMS first: it would mask the missing OTS state and leave retries non-idempotent.

**Root-cause confidence:** 0.75 for an OTS state-gate defect as a class mechanism; 0.20 for attribution to every specific order until production data is collected.
