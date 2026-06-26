# OMS / Starfish — Business Processes

> Read-only research artefact for the OMS (`platform/starfish24/`) part of GJ e-commerce.
> Complements `do../research/2026-05-20-checkout-order-creation.md` (pre-checkout, intervals, capacity, Settings). This document focuses on what happens **after** an order has been created in OMS: BPMN flows, fulfilment, carrier integrations, payment lifecycle, notifications, reports.
>
> Date: 2026-05-16. Tenant context: `gloriajeans` (GJ overlay in `awg/`).

## TL;DR — process map

| # | Process | BPMN file (`awg/bpmn-process/process/gloriajeans/`) | Trigger | Owning service(s) |
|---|---------|---------------------------------------------------|---------|--------------------|
| BP-OMS-01 | Order creation / validation | — (synchronous HTTP, no BPMN) | `POST /order/create` | `core/Order` |
| BP-OMS-02 | Order confirmation flow | `confirmationProcess.bpmn` | event → `Settings.StartProcess` → `BPM` | `Camunda`, `BPM`, `camunda-worker` |
| BP-OMS-03 | Picking / fulfilment | `pickingProcess.bpmn` + `exportForPicking.bpmn` + `exportAfterPicking.bpmn` | message `PICKING_START` | `Camunda`, `Order`, `Stock`, `Adapter` |
| BP-OMS-04 | Dispatch (handover to carrier) | `dispatchProcess.bpmn` | message `TODISPATCH` | `Camunda`, `Delivery`, `camunda-worker` |
| BP-OMS-05 | Carrier registry (courier call) | `carrierRegistryProcess.bpmn` | embedded delegate `carrierRegistryActivity` | `Delivery`, `camunda-worker` |
| BP-OMS-06 | Payment lifecycle (online) | `paymentProcess.bpmn` | start event (created with confirmation) | `pay-service`, `Camunda` |
| BP-OMS-07 | Payment finalization | `paymentFinalizationProcess.bpmn` | message `PAYMENT_CANCELLATION` / `PAYMENT_FULL_CHARGE` | `pay-service`, `Camunda` |
| BP-OMS-08 | Cancellation | `cancellationProcess.bpmn` | message `CANCELLING` (catch event in every process) | `Camunda`, `Order`, `pay-service` |
| BP-OMS-09 | Customer notifications | `notifications.bpmn` | intermediate catch events from sibling processes | `Camunda`, `Cloud-Message-Gateway` |
| BP-OMS-10 | Stock reservation / mutation | — (synchronous + Kafka listeners) | `POST /reservation/{orderId}/create` + Kafka `stock-update` / `stock-delta-update` | `core/Stock` |
| BP-OMS-11 | Order export to OTS / 1C Ecom / 1C ЦБР / DWH | `export.bpmn`, `dwhStatusUpdate.bpmn`, `dwhPaymentUpdate.bpmn` | message events, called from many processes | `camunda-worker`, `Adapter` |
| BP-OMS-12 | Carrier registration (waybill / tracking) | embedded in `dispatchProcess.bpmn` | external task `carrierOrderExport`, `carrierTrackingId` | `Delivery`, carrier SDKs, `5post-connector` |
| BP-OMS-13 | Voximplant outbound call (fraud / confirmation) | `voximplant.bpmn` | message events | `BPM` |
| BP-OMS-14 | Resend gift certificate | `resendCertificateNotification.bpmn` | message events | `BPM`, `Cloud-Message-Gateway` |
| BP-OMS-15 | Release process | `releaseProcess.bpmn` | (auxiliary release / cleanup) | `Camunda` |
| BP-OMS-16 | Reports (read-only) | — (synchronous HTTP) | various `/analytics/reports/*` | `core/reports` |

## How Camunda is wired in OMS

OMS is **Camunda-orchestrated**, not service-orchestrated. Order data lives in `core/Order` (PostgreSQL/MongoDB), but the *control flow* between confirmation → picking → dispatch → payment → notifications lives in **BPMN definitions** under `platform/starfish24/awg/bpmn-process/process/gloriajeans/`.

Three Java services play different roles around Camunda:

1. **`core/Camunda`** — the Camunda BPM engine itself (deployed as a separate Spring Boot app). Exposes `/rest` for engine ops, runs the process state machine. Also has its own Kafka listener (`MessageConsumerServiceImpl`, topic `${spring.kafka.topic.camunda-message}`) to consume external Camunda messages.
2. **`core/BPM`** — a thin wrapper / facade in front of Camunda. Other OMS services do **not** call Camunda REST directly; they call `BPM` (via Feign). Endpoints: `POST /process/{processId}/start`, `POST /message/{messageId}/send`, `POST /signal/{signalId}/send`, `POST /task/{taskId}/complete`, `POST /variable/{orderId}/set`. See `core/BPM/src/main/java/com/starfish24/controllers/ProcessController.java`, `MessageController.java`, `SignalController.java`, `TaskController.java`. Also has BPM-internal scheduled / Kafka work: `core/BPM/src/main/java/com/starfish24/services/StatusUpdateServiceImpl.java` listens on `${spring.kafka.topic.status-update}` and `${spring.kafka.topic.item-status-update}`.
3. **`core/camunda-worker`** — external task workers (Camunda's "External Task Pattern"). Each handler is a Spring `@Component` annotated with `@ExternalTaskSubscription(topicName = "...")` and lives in `core/camunda-worker/src/main/java/com/starfish24/handlers/`. The handlers poll the engine for tasks of their topic and execute them out-of-process.

### Trigger chain on order creation

```
POST /order/create  (Order)
  └→ persist Order, Items, Shipping
  └→ produce Kafka event "ORDER_CREATED" (event topic)
       └→ Settings.EventProcessingServiceImpl  (listens "${spring.kafka.topic}")
            └→ Settings.StartProcess (event handler) — looks up EventProcess by eventId+tenantId
                 └→ BpmFeignClient.startProcess(processId, eventDto)
                      └→ BPM.ProcessController POST /process/{processId}/start
                           └→ Camunda runtimeService starts BPMN instance
                                └→ external task workers in camunda-worker pick up tasks
```

Evidence: `core/Settings/src/main/java/com/starfish24/service/handler/StartProcess.java:40` — `bpmFeignClient.startProcess(..., eventProcess.getProcessId(), eventDto)`. The `EventProcess` table (`Settings` DB) maps `(eventId, tenantId) → processId`, so which BPMN starts is **per-tenant configurable** in DB, not hard-coded.

## External task topics — BPMN ↔ Worker contract

These are the contractually-coupled topic names. Topic name in BPMN XML must exactly match `topicName=` in the corresponding `@ExternalTaskSubscription` handler. **Case-sensitive.** See `.claude/skills/camunda-bpm/` for the broader pattern.

| Topic name (BPMN `camunda:topic`) | Handler (`core/camunda-worker/src/main/java/com/starfish24/handlers/`) | Used in BPMN | What it does |
|----------------------------------|------------------------------------------------------------------------|--------------|--------------|
| `createReservation` | `CreateReservation.java:18` | confirmationProcess | Call Stock to create reservation by `dispatchWarehouseId` or `pickupStoreId` |
| `orderExportWithFeedbackActivity` | `OrderExportWithFeedbackHandler.java:28` | almost every BPMN | Generic "export order somewhere" (1C Ecom / 1C ЦБР / OTS / DWH / Mindbox / etc — destination is process variable) |
| `acquierChargeRequest` | `sber/AcquierChargeRequestHandler.java:40` | paymentProcess | Sber acquiring: charge (full or partial) |
| `acquierRefundRequest` | `sber/AcquierRefundRequestHandler.java:22` | paymentProcess, paymentFinalizationProcess | Sber acquiring: refund |
| `acquierPreauthCancel` | `sber/AcquierPreauthCancel.java:29` | paymentFinalizationProcess | Sber acquiring: cancel pre-auth (hold) |
| `isNeedRefund` | `sber/IsNeedRefundHandler.java:26` | paymentFinalizationProcess | Decide whether refund step is required |
| `carrierOrderExport` | `CarrierOrderExportHandler.java:31` | dispatchProcess | Register shipment in carrier system (waybill creation) |
| `carrierTrackingId` | `CarrierTrackingIdHandler.java:22` | dispatchProcess | Poll carrier for tracking number after registration |
| `carrierCourierCall` | `CarrierCourierCallHandler.java:33` | carrierRegistryProcess | Place courier-call request to carrier |
| `carrierCourierCallTracking` | `CarrierCourierCallTrackingHandler.java:27` | carrierRegistryProcess | Verify courier-call was accepted by carrier |
| `carrierOrderConfirmationActivity` | `CarrierOrderConfirmationActivity.java:32` | carrier flows | Confirm a previously-registered shipment with carrier |
| `carrierClosedDeliveryBundle` | `CarrierClosedDeliveryBundleHandler.java:22` | bundle flows | Close a delivery bundle with carrier (e.g. 5post AVD) |
| `carrierCreateDeliveryBundle` | `CarrierCreateDeliveryBundleHandler.java:27` | bundle flows | Create a new delivery bundle |
| `carrierDeleteOrdersFromDeliveryBundle` | `CarrierDeleteOrdersFromDeliveryBundle.java:21` | bundle flows | Remove order(s) from a bundle |
| `carrierYandexGetCancellationCost` | `CarrierYandexGetCancellationCost.java:43` | cancellation | Yandex Cargo-specific cancellation cost query |
| `postCarriersOrders` | `carrier/CreateCarriersOrders.java:27` | dispatchProcess | Generic POST to carrier "create order" endpoint |
| `deleteCarriersOrders` | `carrier/DeleteCarriersOrders.java:20` | cancellationProcess | Carrier order deletion |
| `getCarriersOrdersTrackingId` | `carrier/GetCarriersOrdersTrackingId.java:22` | dispatchProcess | Generic tracking-id getter |
| `postCarriersCourierCall` | `carrier/PostCarrierCallRequest.java:28` | carrierRegistryProcess | Generic courier call POST |
| `sendTransactionalMessage` | `TransactionalMessageHandler.java:21` | notifications | Send email / SMS / push via Cloud-Message-Gateway |
| `assignOrder` | `AssignOrderHandler.java:28` | confirmationProcess | Assign order to operator/warehouse |
| `checkOnlineUsers` | `CheckOnlineUsersHandler.java:23` | confirmationProcess | Check available operators (for manual review) |
| `bitrixStatusUpdate` | `BitrixStatusUpdateHandler.java:18` | side-flows | Push status to legacy Bitrix CRM |
| `mindboxStatusUpdate` | `MindboxStatusUpdateHandler.java:25` | side-flows | Push status to Mindbox CDP |
| `bntStatusChange` | `BntStatusChangeHandler.java:16` | BNT brand-specific | Notify BNT (sub-brand) of status change |
| `sisleySendStatusOms` | `SisleySendStatusOmsHandler.java:18` | Sisley brand | Notify Sisley brand of status change |
| `galamartOrderExport` | `GalamartOrderExport.java:22` | Galamart brand | Brand-specific export |
| `correctOrderInLamoda` | `CorrectOrderInLamodaHandler.java:17` | Lamoda mp | Lamoda marketplace correction |
| `ourgoldUpdateLotIds` | `OurgoldUpdateLotIdsHandler.java:20` | Ourgold brand | Update lot IDs (jewellery / serial-tracked goods); 5-min lock |
| `setWarehouseWorkingHoursActivity` | `SetWarehouseWorkingHoursActivity.java:37` | confirmation | Set order variables based on warehouse hours |
| `datamatrixCodeGetterActivity` | `BYDatamatrixCodeHandler.java:21` | BY market | Get Belarus Datamatrix code (mandatory marking) |
| `datamatrixCodeValidation` | `DatamatrixCodeValidationActivity.java:28` | BY market | Validate Datamatrix code |
| `decommissioningActivity` | `DecomissioningHandler.java:23` | BY market | Decommission Datamatrix code |
| `dispatchCreateActivity` | `DispatchCreateActivity.java:20` | dispatchProcess | Create dispatch record in Order service |
| `expirationDateTimeUpdate` | `ExpirationDateTimeUpdateHandler.java:20` | various | Update order `expirationDateTime` |
| `delayedRegistrationTimerActivity` | `DelayedRegistrationTimerActivity.java:38` | dispatchProcess | Schedule registration retry by carrier-specific timer |
| `marketplaceTrackingIdExport` | `MarketplaceTrackingIdExportHandler.java:15` | marketplaces | Push tracking-id back to marketplace |
| `changeStatusFinality` | `ChangeStatusFinalityActivity.java:20` | various | Mark order status as "final" (terminal) |
| `RRNotPicked` | `RRNotPickedHandler.java:22` | Ralf Ringer brand | Brand-specific handler |
| `400badRequest` | `BadRequestHandler.java:17` | error handling | Catches and acks 400 errors (30s lock) |
| `timeoutExternal` | `TimeoutExternalHandler.java:17` | timer simulation | Used in test/timing tasks |
| `normalExternal` | `NormalExternalHandler.java:17` | generic | Generic noop-ish |
| `NoopTask` | `NoopTaskHandler.java:16` | generic | Pure no-op for diagrams |

> **Quirk**: 7 of the handlers above (BNT, Sisley, Galamart, Lamoda, Ourgold, BY Datamatrix, RRNotPicked) are *brand-specific* hard-coded in shared `camunda-worker`. Adding a new brand means a code change in this shared service.

## Order status state machine (from BPMN service-task names)

Statuses extracted from `Смена статуса заказа на ...` service-task names across BPMNs:

| Status | Set in (BPMN) | Meaning |
|--------|---------------|---------|
| `ON_VALIDATION` | confirmationProcess | Initial state after process start; pre-validation |
| `WAIT_FRAUD_MANUAL_CHECK` | confirmationProcess | Fraud check triggered, awaiting manual review |
| `CHECKED_INVALID` | confirmationProcess, exportForPicking | Validation failed |
| `CANCELLING` | confirmationProcess, dispatchProcess, pickingProcess (& others) | Cancellation in progress, side-effects running |
| `CANCELLED` | cancellationProcess | Terminal cancel |
| `SUSPENDED` | confirmationProcess | Paused (typically awaiting payment or external action) |
| `ORDER_CONFIRMED` (event) | confirmationProcess (throws message) | Confirmation complete → triggers picking |
| `WAIT_EXPORT_TO_WAREHOUSE` | pickingProcess | Order waiting to be sent to warehouse system |
| `ORDER_CONFIRMED_WAREHOUSE` (event) | pickingProcess | Warehouse acknowledged |
| `PICKING_START` (event) | confirmationProcess | Picking should begin |
| `PICKING_COMPLETE` / `PICKING_COMPLETED` (event) | pickingProcess | Picking finished |
| `ORDER_PICKUP` | pickingProcess | Item is picked, awaiting dispatch |
| `ORDER_FOR_SHIPPING` | dispatchProcess | Order ready to hand to carrier |
| `DELIVERING` | dispatchProcess (event), various | In transit |
| `READY_FOR_PICKUP` | dispatchProcess | Available at pickup point / pickup store |
| `LOST` | dispatchProcess (event from АРМ) | Order lost in delivery |
| `COMPLETED` | various | Order delivered & closed |
| `RETURNED` | (referenced in payment flows) | Customer returned the order |

Note: actual finality of statuses is data-driven via Settings (`StatusModelDto`, `ChangeStatusFinalityActivity`) — it's not a pure enum in code. Real source-of-truth is the `Settings` service DB table for statuses.

## Camunda message catalogue

Throw / catch events ("BPMN signals" colloquially, but technically messages):

| Message name | Thrown by | Caught by |
|--------------|-----------|-----------|
| `ORDER_CONFIRMED` | confirmationProcess | dispatchProcess, pickingProcess (entry), export.bpmn, dwh* |
| `PICKING_START` | confirmationProcess | pickingProcess |
| `PICKING_COMPLETE` / `PICKING_COMPLETED` | pickingProcess | dispatchProcess, paymentProcess (`PAYMENT_PICKING_COMPLETE`) |
| `CANCELLING` | (multiple) | every process (each has an interrupting `CANCELLING` catch event) |
| `ORDER_CANCELED` | cancellationProcess | notifications, downstream exports |
| `READY_FOR_PICKUP` | dispatchProcess | notifications |
| `DELIVERING` | dispatchProcess | notifications, resendCertificate |
| `COMPLETED` | (final state) | notifications |
| `TODISPATCH` | confirmationProcess (after picking on FF) | dispatchProcess |
| `PAYMENT_RESERVATION_COMPLETE` | confirmationProcess | paymentProcess |
| `PAYMENT_PICKING_COMPLETE` | pickingProcess | paymentProcess |
| `PAYMENT_FULL_CHARGE` | paymentProcess | paymentFinalizationProcess |
| `PAYMENT_PARTIAL_CHARGE_AFTER_HOLD` | paymentProcess | paymentFinalizationProcess |
| `PAYMENT_CANCELLATION` | cancellationProcess | paymentFinalizationProcess |
| `PAYMENT_RECEIVED` | paymentProcess | cancellation, voximplant |
| `IS_PAID_CHANGED` / `IS_PAID_CHANGED_FROM_CONFIRMATION_PROCESS` | order attribute change | confirmationProcess, paymentProcess |
| `RETURN_TO_DISPATCH_AFTER_CANCELLING` | cancellation logic | dispatchProcess |
| `RETURN_TO_PICKING_AFTER_CANCELLING` | cancellation logic | pickingProcess |
| `DELIVERING_AFTER_CANCELLING_FOR_{FF,CC,SFS}` | dispatchProcess | dispatchProcess (per-channel branch) |
| `COURIER_CALLED` | carrierRegistryProcess | (acks) |
| `NOTIFICATION_*` (CANCELLED, DELIVERING, READY_FOR_PICKUP, COMPLETED) | sibling processes | notifications |
| `FRAUD_CONFIRMED` | confirmationProcess | (resumes) |

**Quirk**: The same name (e.g. `ORDER_CONFIRMED`) is declared as a `<bpmn:message>` in multiple BPMN files. Each definition is a separate Camunda message subscription; throwing it once delivers to each waiting instance.

---

## BP-OMS-01: Order creation / validation

- **Trigger**: `POST /order/create` on `core/Order` (`OrderController.java:108`).
- **BPMN**: none — this is a *synchronous* HTTP create. BPMN flow is started **later** by the `ORDER_CREATED` event consumed by Settings.
- **Actors**: Integration (BFF) ← creates the order; OMS Operator (via OMS-UI); Marketplace adapters (via /order/export).
- **Steps**:
  1. Authn check → user from token → `tenantId`.
  2. JSON-schema validation via `@ValidJson(schema = "order_create")` annotation (custom validator).
  3. Delegate to `OrderControllerDelegate.createOrder` (`Order/src/main/java/com/starfish24/controller/helper/OrderControllerDelegate.java:35`):
     - If `clientOrderId` is `null`, generate one via `orderService.getOrderNewId(sourceId, brandId, tenantId)`.
     - Build dedup cache key `(tenantId + clientOrderId + brandId)`. If another create is in-flight, **reject with 400 "Client order is pending"** — `orderCreationCacheService.saveKey` is a Redis-backed mutex.
     - Call `orderService.createOrder(orderDto, user, sendCustomerUpdate)`. Persists `Order`, `Shipping`, `Item[]`, `Package[]`, `OrderCustomAttribute[]` (`Order/src/main/java/com/starfish24/entities/order/Order.java`).
     - On `ConstraintViolationException` with INN — wraps as "Provided INN probably already exists".
     - On any error — calls `pachcaNotificationService.orderCreateExceptionNotify` (Pachca = team chat for incidents).
  4. Cache key is freed in `finally`.
  5. Returns full `OrderDto`.
- **OMS services in play**: `core/Order` (primary). Internally Order may call `core/Stock` and `core/Settings`.
- **External task topics**: none (synchronous).
- **Entities**: `Order`, `OrderDetails`, `Item`, `Shipping`, `Package`, `OrderMarketing`, `OrderCustomAttribute`, `OrderStatusHistory`, `ExportedOrder` (post-export tracking).
- **Outgoing events**: `ORDER_CREATED` Kafka event (consumed by `core/Settings/src/main/java/com/starfish24/service/EventProcessingServiceImpl.java:63`, topic `${spring.kafka.topic}`).
- **Code paths**:
  - `core/Order/src/main/java/com/starfish24/controller/OrderController.java:108`
  - `core/Order/src/main/java/com/starfish24/controller/helper/OrderControllerDelegate.java:35`
  - `core/Order/src/main/java/com/starfish24/services/orderService/OrderServiceImpl.java`
- **Per-env config**: `awg/cloud-configs/order-service-gj-prod.yaml` (102 lines), `order-service-gj-staging.yml`, `order-service-gj-preprod.yml`. Note `.yaml` vs `.yml` inconsistency.
- **Quirks**:
  - Idempotency relies on a **Redis cache mutex** — if Redis is down or partitioned, you can get duplicate creates.
  - Errors broadcast to Pachca chat (operational visibility is in chat, not metrics).
  - JSON-schema `order_create` lives in classpath resources (`@ValidJson`), not co-located with controller — invisible if you only read the controller.
  - `OrdersController` (note plural; `OrderController.java` vs `OrdersController.java`) is a parallel REST surface focused on the *client-order-id-based* paths (`/orders/client/{clientOrderId}/...`) and shipping/package CRUD — easy to confuse with `OrderController`.

## BP-OMS-02: Order confirmation flow (`confirmationProcess.bpmn`)

- **Trigger**: Kafka event `ORDER_CREATED` → `Settings.StartProcess.handle` → `BpmFeignClient.startProcess("confirmationProcess", ...)`. Mapping from event → processId is in DB table `EventProcess` (`core/Settings`).
- **BPMN**: `awg/bpmn-process/process/gloriajeans/confirmationProcess.bpmn` (2438 lines — the most complex process).
- **Actors**: Customer (online payment), OMS Operator (manual fraud check), Internal services (Stock, OTS = 1C delivery system).
- **Steps (happy path, simplified)**:
  1. **Start** → `statusUpdate` delegate sets order to `ON_VALIDATION`; item statuses → `ON_VALIDATION` (`itemsStatusUpdate`).
  2. **Fraud check** (`checkFraudActivity` delegate). Gateway: `Gateway_1sozje4` "Сработала проверка на Fraud?".
     - If fraud triggered → status → `WAIT_FRAUD_MANUAL_CHECK` → wait for operator (`userTask gjErrorProblem`, candidate group `support`) → on confirm → `FRAUD_CONFIRMED` message.
  3. **Reservation creation** (external task `createReservation`, topic `createReservation`):
     - Branch by C&R (Click&Reserve / pickup) vs FF (Fulfilment): different reservation target. C&R uses `pickupStoreId`; FF/SFS uses `dispatchWarehouseId`.
     - Result fanout — if zero reservation → cancellation path; if partial → "isNeedConfirmPartlialReserveInOts" gate decides whether to call OTS for partial reserve confirmation.
  4. **Order export to OTS** (external task `orderExportWithFeedbackActivity`, with destination param routing to OTS via `Adapter`).
  5. **Payment branch** — gateway `Онлайн оплата?`. If yes → throws `PAYMENT_RESERVATION_COMPLETE` (paymentProcess listens).
  6. **Wait for `IS_PAID_CHANGED`** with a `PT24H` timer; if not paid in 24h → `CANCELLING` → cancellation flow.
  7. On paid (or COD) → status `ORDER_CONFIRMED` (throw message) → `PICKING_START` event thrown → pickingProcess starts.
- **External task topics consumed**: `createReservation`, `orderExportWithFeedbackActivity`.
- **Embedded delegates** (`camunda:delegateExpression`, run in Camunda engine JVM, not external):
  - `${statusUpdate}` — status mutation
  - `${itemsStatusUpdate}` — item status batch mutation
  - `${itemStatusCheckActivity}` — check item status with `itemStatusValue` input
  - `${checkFraudActivity}` — fraud algorithm
  - `${reserveStatusUpdateActivity}` — close reservations
  - `${setCustomAttributes}` — write custom attribute on order (e.g. `cancellationStage`, `wasSuspended`, `nonPaymentCancellationDateTime`)
  - `${setCancellationReasonActivity}` — set cancellation reason
  - `${addHistoryActivity}` — append history entry
  - `${orderCalculate}` — recompute order totals
  - `${messageSendActivity}` — send internal notification (operator email)
- **Entities**: `Order`, `Reservation` (Stock), `OrderStatusHistory`, `OrderCustomAttribute` (storage for `cancellationStage`, `wasSuspended`, `isPaid`, `nonPaymentCancellationDateTime`, ...).
- **Outgoing events / messages**: `PAYMENT_RESERVATION_COMPLETE`, `ORDER_CONFIRMED`, `PICKING_START`, `CANCELLING`, `IS_PAID_CHANGED_FROM_CONFIRMATION_PROCESS`.
- **Where to look**:
  - BPMN: `awg/bpmn-process/process/gloriajeans/confirmationProcess.bpmn`
  - Handlers: `core/camunda-worker/src/main/java/com/starfish24/handlers/CreateReservation.java:18`, `OrderExportWithFeedbackHandler.java:28`
  - Delegate beans: search `core/Camunda/src/main/java` and `core/BPM/src/main/java` for `@Component("statusUpdate")`, `@Component("checkFraudActivity")`, etc.
- **Quirks**:
  - The user task `gjErrorProblem` blocks the process until an operator opens OMS-UI and resolves. If no operators online (`checkOnlineUsers` topic) — alerts.
  - `PT24H` non-payment timer: if a customer pays after exactly 24h, the catch-event race condition can fire both branches; defended via `Gateway_15k2ksa` "Оплачен (доп проверка, что атрибут не успел измениться)".
  - Process is **long-running** (24h+ for unpaid orders). Migrating running instances on BPMN deploy requires `processDefinitionKey` migration plan via Camunda Cockpit.
  - "C&R or SFS?" gateway logic is repeated 3+ times — refactor opportunity (but risky due to in-flight instances).

## BP-OMS-03: Picking / fulfilment (`pickingProcess.bpmn` + helpers)

- **Trigger**: Throw event `PICKING_START` from confirmationProcess. pickingProcess has start event with `PICKING_COMPLETED` catch (renamed inside same process), plus standalone `PICKING_START` message catch.
- **BPMN**: `awg/bpmn-process/process/gloriajeans/pickingProcess.bpmn` (1598 lines).
  Helpers:
  - `exportForPicking.bpmn` — export to warehouse system *before* picking (for OTS / 1C).
  - `exportAfterPicking.bpmn` — confirmation export after picking complete.
- **Actors**: Warehouse Picker (via АРМ — the warehouse desktop app, external to this codebase), `Adapter` service (1C/OTS feedback ingestion).
- **Steps (simplified)**:
  1. Wait for `PICKING_COMPLETED` external event (from АРМ via Adapter Kafka listener).
  2. Gate `Нулевая сборка?` (zero-pick): if all items cancelled → branch to cancellation.
  3. `itemStatusCheckActivity` → if any items `CANCELLED` → close partial reserve (`partialReserveCloseActivity`).
  4. Status to `WAIT_EXPORT_TO_WAREHOUSE`, then await `ORDER_CONFIRMED_WAREHOUSE`.
  5. If invalid → status `CHECKED_INVALID` → cancellation branch.
  6. SFS (Ship-from-Store) vs C&R vs FF branches diverge.
  7. Status → `ORDER_PICKUP`. Throws `PICKING_COMPLETE` to dispatchProcess and paymentProcess (latter as `PAYMENT_PICKING_COMPLETE`).
  8. PT30M timer for SFS branch — if not handed off in 30m, escalate.
- **External task topics**: `orderExportWithFeedbackActivity` (multiple service tasks: OTS confirmation, 1C ЦБР, 1C Ecom).
- **Embedded delegates**: `statusUpdate`, `itemsStatusUpdate`, `itemStatusCheckActivity`, `partialReserveCloseActivity`, `setCustomAttributes`, `setCancellationReasonActivity`, `addHistoryActivity`, `orderCalculate`, `orderExportWithFeedbackActivity` (this one is both embedded and external in different places — see Quirks).
- **Entities**: `Order`, `Item[]`, `Reservation`, `Package` (warehouse may pack multiple items into a package).
- **Outgoing events**: `PICKING_COMPLETE`, `TODISPATCH` (thrown to dispatchProcess), `CHECKED_INVALID`, `CANCELLING`, `PAYMENT_PICKING_COMPLETE`.
- **Where to look**:
  - BPMN: `pickingProcess.bpmn`, `exportForPicking.bpmn`, `exportAfterPicking.bpmn`
  - АРМ feedback ingestion: `core/Adapter/src/main/java/com/starfish24/service/OrderDataProcessingServiceImpl.java:49` (topic `${spring.kafka.topic.order}`)
- **Quirks**:
  - `orderExportWithFeedbackActivity` is referenced as **both** `camunda:delegateExpression` (embedded, e.g. "Пересчет промо в заказе") and `camunda:type="external"` (external task) — depends on whether result feedback is needed. Easy to misread.
  - PT30M SFS timer is hard-coded in BPMN — not configurable per tenant. Changes require BPMN re-deploy + migration.
  - "Нулевой резерв" / "Нулевая сборка" (zero reserve / zero pick) is a recurring branch — copy-pasted in multiple processes.

## BP-OMS-04: Dispatch — handover to carrier (`dispatchProcess.bpmn`)

- **Trigger**: Catch message `TODISPATCH` or `PICKING_COMPLETE` (depending on FF vs C&R path).
- **BPMN**: `awg/bpmn-process/process/gloriajeans/dispatchProcess.bpmn` (1028 lines).
- **Actors**: External Carrier API (CDEK, 5post, RPost, Yandex Cargo, IML, Boxberry, DPD, Topdelivery, Pickpoint, Sber Logistic, Vobaza, etc.); Warehouse Operator (via АРМ for store-dispatch).
- **Steps (simplified)**:
  1. C&R or C&C? → if C&R (Click&Reserve in store), wait for `READY_FOR_PICKUP (АРМ)` → status `READY_FOR_PICKUP`.
  2. For carrier delivery: status → `ORDER_FOR_SHIPPING`.
  3. **Register order in carrier** — external task `carrierOrderExport` (`CarrierOrderExportHandler.java:43`). Handler calls `BpmFeignClient.carrierOrderExport` → BPM → `Delivery.CarrierController POST /carrier/{particularCarrierId}/neworder/request`. Inside Delivery a per-carrier `OrderRegistrationService` (see `Delivery/src/main/java/com/starfish24/delivery/service/carriers/{cdek,fivepost,russianpost,yandex,...}/`) calls the actual external API.
  4. PT20S timer between registration and tracking-id polling.
  5. **Get tracking-id** — external task `carrierTrackingId` (`CarrierTrackingIdHandler.java:22`).
  6. Special branches:
     - CDEK gateway `CDEK?` triggers extra flow with carrier registry (courier call).
     - DPD branch: `CarrierOrderExportHandler.java:77-79` sets process variable `registrationOrder` boolean based on whether carrier returned `"OrderPending"`.
  7. Status → `DELIVERING`.
  8. Wait for terminal status: `READY_FOR_PICKUP (АРМ)` (pickup point reached), `DELIVERING (OTS)`, `LOST (АРМ)`, or completion.
- **External task topics**: `carrierOrderExport`, `carrierTrackingId`, `orderExportWithFeedbackActivity`, `postCarriersOrders` (newer generic carrier path), `getCarriersOrdersTrackingId`.
- **Embedded delegates**: `carrierRegistryActivity` (starts carrierRegistryProcess as a subprocess), `statusUpdate`, `setCustomAttributes`, `updateProcessVariables`, `createReservation` (delegate version, not external).
- **Entities**: `Order`, `Shipping`, `Package`, `ExportedShipping`, carrier-specific waybill records (in Delivery DB).
- **Outgoing events**: `DELIVERING`, `READY_FOR_PICKUP`, `COMPLETED`, `LOST`, `CANCELLING`, plus internal `DELIVERING_AFTER_CANCELLING_FOR_{FF,CC,SFS}`.
- **Where to look**:
  - BPMN: `dispatchProcess.bpmn`
  - Worker: `core/camunda-worker/src/main/java/com/starfish24/handlers/CarrierOrderExportHandler.java`, `CarrierTrackingIdHandler.java`
  - Delivery: `core/Delivery/src/main/java/com/starfish24/delivery/service/carriers/<carrier>/OrderRegistrationServiceImpl.java`
  - Connectors (separate Spring Boot apps): `core/5post-connector/`, `core/Delivery/.../cdek/` (uses `core/cdek-api-sdk`), Russian Post (uses `core/russian-post-api-sdk`, but currently POM-only — see Quirks).
- **Per-env config**: `awg/cloud-configs/delivery-gj-prod.yaml` (257 lines) holds per-carrier base URLs and credentials:
  - `cdek` (api.cdek.ru v2 OAuth)
  - `yandex` (b2b.taxi.yandex.net cargo integration v1/v2)
  - `yandex-ndd` (next-day delivery, **uses `.tst.yandex.net` host in prod config!** — see Quirks)
  - `boxberry` (api.boxberry.ru/json.php)
  - `iml` (list.iml.ru / api.iml.ru — split between region/city dict and order API)
  - `topdelivery`, `dpd`, `pickpoint`, `russianpost`, `sber`, `vobaza`, `dalli`, `cse`, `bns`, `podorozhnik`, `logsis`, `lamoda`, `lime`
- **Quirks**:
  - **`yandex-ndd` config in PROD points to `b2b.taxi.tst.yandex.net`** (`delivery-gj-prod.yaml` lines around `yandex-ndd:`). Either a Yandex-side staging-as-prod arrangement or a config bug — verify before action.
  - `russian-post-api-sdk` repo contains only `pom.xml` (no `src/`) in our clone — see Quirks section below. Russian Post integration may live in `core/Delivery/.../russianpost/` instead, or be a private artifact resolved via Nexus.
  - `CarrierOrderExportHandler` special-cases `dpd` (line 77): sets `registrationOrder=false` when DPD returns `"OrderPending"`, which gates a separate retry path in BPMN.
  - `courierServicesToIgnore40XError` — process variable letting BPMN suppress 4xx errors from certain carriers (treat as soft-fail). Set per-tenant in Settings.
  - 5post integration is a standalone connector (`core/5post-connector`) — Delivery does not call 5post directly; it goes through this connector via Feign. Adds an extra hop.
  - `getCarriersOrdersTrackingId` (topic) vs `carrierTrackingId` (topic) — two handlers exist (newer "carriers" package = generic, old "carrier" = per-carrier). Both may be live for different carriers — careful when changing.

## BP-OMS-05: Carrier registry / courier call (`carrierRegistryProcess.bpmn`)

- **Trigger**: From dispatchProcess via `carrierRegistryActivity` delegate (sub-process start).
- **BPMN**: `awg/bpmn-process/process/gloriajeans/carrierRegistryProcess.bpmn` (the simplest order process). Has `camunda:versionTag="1.0.0"` (one of few BPMNs with explicit version).
- **Actors**: Carrier API (per-carrier courier-call endpoint).
- **Steps**:
  1. Wait until "polite" courier-call time-of-day (per-store timezone). Embedded catch event "Ожидание времени вызова курьера по часовому поясу магазина".
  2. Set per-carrier deadline timer:
     - CDEK: 12:00 local
     - Pickpoint: 10:50 local
     - Russian Post: 18:00 local
  3. Embedded `carrierCourierCallActivity` → "Вызов курьера в магазин".
  4. External task `carrierCourierCallTracking` (`CarrierCourierCallTrackingHandler.java:27`) — poll carrier to confirm pickup. PT10S retry.
  5. Throws `COURIER_CALLED` message.
- **External task topics**: `carrierCourierCallTracking`.
- **Embedded delegates**: `carrierCourierCallActivity`, `setTimers`.
- **Entities**: courier-call records in Delivery DB.
- **Quirks**: Hard-coded times-of-day in BPMN per carrier — adding a new carrier requires BPMN edit and re-deploy.

## BP-OMS-06: Payment lifecycle — online (`paymentProcess.bpmn`)

- **Trigger**: Started by confirmationProcess (typically when `PAYMENT_RESERVATION_COMPLETE` message thrown). Has multiple start events for different stages.
- **BPMN**: `awg/bpmn-process/process/gloriajeans/paymentProcess.bpmn` (2175 lines).
- **Actors**: Customer (online via Sber acquiring; ЮMoney / card supported via gateway switch); `pay-service` (mediates the acquiring API); Sber webhook callbacks.
- **Steps (simplified)**:
  1. Wait `PAYMENT_RESERVATION_COMPLETE` or `PAYMENT_PICKING_COMPLETE` or `PAYMENT_FULL_CHARGE`.
  2. Gateway "Юмани или карта?" — branches by `paymentTypeId`.
  3. `getPaymentId` delegate — load `acquierOrderId`, `acquierTransactionStatusId` from order custom attributes.
  4. **Hold step**: external task `acquierChargeRequest` — performs charge (full or partial: "Списание на сумму без учета отмененных товаров" vs "Полное списание").
  5. PT1M, PT30M timers for hold expiry.
  6. **Partial refund** (cancelled items): external task `acquierRefundRequest` — "Возврат отмененных позиций".
  7. Fiscal receipts via embedded `sendEvent` delegate: "Создание чека аванса", "Чек на возврат отмененных товаров", "Чек на возврат аванса", "Получить статус чека". Receipts go to ОФД (Russian fiscal data operator) via separate flow.
- **External task topics**: `acquierChargeRequest`, `acquierRefundRequest`.
- **Embedded delegates**: `getPaymentId`, `sendEvent` (emits a generic event, picked up by Settings handlers).
- **pay-service endpoints** (`core/pay-service/src/main/java/com/starfish24/controller/`):
  - `OnlinePaymentController`:
    - `GET /onlinepay/{clientOrderId}/link` — fetch payment link
    - `POST /onlinepay/{clientOrderId}/getlink` — create payment link
    - `GET /onlinepay/{acquierOrderId}/checkstatus`
    - `POST /onlinepay/{acquierOrderId}/chargerequest`
    - `GET /onlinepay/{acquierOrderId}/preauthcancel`
    - `POST /onlinepay/{clientOrderId}/apple` — Apple Pay
    - `POST /onlinepay/{clientOrderId}/google` — Google Pay
    - `POST /onlinepay/{acquierOrderId}/refundrequest`
  - `CallbackController.handlingCallback` — `GET /onlinepay/{tenantId}/callback?orderNumber=...` — Sber acquiring webhook return URL. **Note**: it's a `GET` (Sber's return-from-payment redirect, not a POST webhook). Server-to-server status update appears to happen via `checkstatus` polling, not webhook.
- **Per-env config**: `awg/cloud-configs/pay-service-gj-{preprod,prod,staging}.yaml`. Default branch of pay-service is `CLD-1840` per repo metadata.
- **Outgoing events / messages**: `PAYMENT_FULL_CHARGE`, `PAYMENT_PARTIAL_CHARGE_AFTER_HOLD`, `PAYMENT_RECEIVED`, `IS_PAID_CHANGED`.
- **Entities**: payment records in pay-service DB; `OrderCustomAttribute` keys: `acquierOrderId`, `acquierTransactionStatusId`, `paymentTypeId`, `isPaid`.
- **Quirks**:
  - Callback uses `GET` and `tenantId` in path — non-standard, can be tricky for routing/auth filters.
  - Charge happens in **two phases** with a hold: initial reservation (hold), then either full charge or partial (cancelled items get refunded). Driven by ~30m hold timer in BPMN.
  - Fiscal receipt orchestration is intertwined with payment flow — there are at least 7 "Получение значений переменных аванса" (advance payment) data-fetch tasks scattered across the BPMN, indicating accumulated logic with no extraction.

## BP-OMS-07: Payment finalization (`paymentFinalizationProcess.bpmn`)

- **Trigger**: Message events — typically `PAYMENT_CANCELLATION` from cancellationProcess; can also be triggered standalone for refunds.
- **BPMN**: `awg/bpmn-process/process/gloriajeans/paymentFinalizationProcess.bpmn`.
- **Actors**: pay-service, Sber acquiring, ОФД (fiscal receipt operator), Loyalty backend (bonuses).
- **Steps**:
  1. External task `acquierPreauthCancel` — release the hold (`AcquierPreauthCancel.java:29`).
  2. External task `acquierRefundRequest` — refund charged amount.
  3. External task `isNeedRefund` (`IsNeedRefundHandler.java:26`) — decision gateway: are there items that need refund?
  4. Embedded `${gjOrderLoyaltyReturn}` — return spent loyalty bonuses to customer.
  5. Fiscal receipts: "Создание чека на зачет аванса", "Чек на отмену аванса", "Чек на возврат аванса", "Получить статус чека".
  6. External task `orderExportWithFeedbackActivity` x N — push to 1C Ecom, 1C ЦБР, OTS, datamatrix (BY).
- **External task topics**: `acquierPreauthCancel`, `acquierRefundRequest`, `isNeedRefund`, `orderExportWithFeedbackActivity`.

## BP-OMS-08: Cancellation (`cancellationProcess.bpmn`)

- **Trigger**: Message `CANCELLING` (every long-running process has an interrupting catch event for this). Cancel can come from: customer cancel (Integration BFF), operator cancel (OMS-UI → Order `POST /order/{orderId}/cancel`), automatic (no-payment 24h, fraud, out-of-stock).
- **BPMN**: `awg/bpmn-process/process/gloriajeans/cancellationProcess.bpmn` (2952 lines — second largest, mostly because it duplicates exports for many states).
- **Actors**: Order operator, Customer, Carrier API (cancel shipment), pay-service.
- **Steps**:
  1. Set all items → `CANCELLING` (`itemsStatusUpdate`).
  2. Get `cancellationStage` custom attribute (set in prior process — picking, dispatch, confirmation) to know how far the order progressed.
  3. Branch by stage — call carrier cancel if registered (`carrierCancelOrderActivity` delegate), close reservations (`reserveStatusUpdateActivity`).
  4. Throw `PAYMENT_CANCELLATION` → paymentFinalizationProcess (refund flow).
  5. Export to OTS / 1C Ecom / 1C ЦБР (multiple "Выгрузка заказа в ..." service tasks).
  6. Set all items → `CANCELLED`. Status → `CANCELLED`.
  7. Throw `ORDER_CANCELED` → notifications.
- **External task topics**: `orderExportWithFeedbackActivity` (heavily), `deleteCarriersOrders` (when applicable).
- **Entities**: same as Order + populates `cancellationStage`, `isOrderShipmentRegistered`, `customCancelationReason`.
- **Quirks**:
  - The `cancellationStage` attribute is the only way to know what to undo — set by `setCustomAttributes` delegate in every process at the appropriate point. If missed, cancellation can run incomplete (e.g. forget to cancel carrier shipment).
  - 8+ near-identical service tasks "Выгрузка заказа в OTS" / "1С Ecom" / "1С ЦБР" — they look duplicate but are gated by different upstream branches.

## BP-OMS-09: Customer notifications (`notifications.bpmn`)

- **Trigger**: All catch events from sibling processes — `NOTIFICATION_CANCELLED`, `NOTIFICATION_DELIVERING`, `NOTIFICATION_READY_FOR_PICKUP`, `NOTIFICATION_COMPLETED`. Also timers (P2D, P3D — "ping after 2/3 days").
- **BPMN**: `awg/bpmn-process/process/gloriajeans/notifications.bpmn`.
- **Actors**: Customer (recipient via email/SMS); `core/Cloud-Message-Gateway` (the gateway).
- **Steps**: Each catch event leads to one or more `sendTransactionalMessage` external tasks. The BPMN names tasks "email 7736", "email 7738", "email 7720", ... — those numbers are **template IDs in the messaging system** (probably Mindbox/own templates). The BPMN doesn't store template content, only the ID.
  - Customer waits ("Ожидание вежливого времени" — polite-hours catch event) before sending notification.
- **External task topics**: `sendTransactionalMessage` (handler `TransactionalMessageHandler.java:21`).
- **Worker → service**: TransactionalMessageHandler → `core/Cloud-Message-Gateway` (Feign `MessageGatewayFeignClient`).
- **Per-env config**: `awg/cloud-configs/message-gateway-service-gj-{preprod,prod,staging}.{yml,yaml}`.
- **Channels**: email, SMS, push (via NotificationChannel enum `core/oms-objects/src/main/java/com/starfish24/dto/notification/NotificationChannel.java`).
- **Quirks**:
  - Template IDs (7736, 7738, ...) are hardcoded in BPMN. Renaming/replacing a template means BPMN re-deploy.
  - "Polite hours" filter prevents 3am SMS — but defined as a Camunda intermediate catch event with no clear input doc.

## BP-OMS-10: Stock reservation / mutation

- **Trigger**:
  - HTTP: `POST /reservation/{orderId}/create` (`core/Stock/.../ReservationController.java:22`) — called by `CreateReservation` worker handler during confirmation.
  - Kafka: `stock-update` topic, `stock-delta-update` topic (`Stock/.../service/stock/StockMongoService.java:564`, `:590`).
- **BPMN**: none directly — Stock is invoked from BPMN flows.
- **Actors**: ENSI Catalog (upstream — origin of stock data, see `ensi-researcher` for ENSI side), Warehouse Management (mutations via АРМ → Kafka).
- **Steps (reservation create)**:
  1. `CreateReservation` worker (`core/camunda-worker/src/.../CreateReservation.java`) is triggered from confirmationProcess.
  2. Calls `StockFeignClient.createReservation(orderId, ReservationRequestDto)`.
  3. Stock service: `ReservationController.createReservation` → `ReservationService.createReservation`. Checks current availability per `warehouseId`+`sku`, atomically decrements, writes a `Reservation` document.
- **Steps (Kafka stock update)**:
  - `StockMongoService.@KafkaListener(topics = "${spring.kafka.topic.stock-update}")` receives full snapshot updates from ENSI / WMS.
  - `stock-delta-update` for partial deltas.
- **Per-env config**: `awg/cloud-configs/stock-gj-{preprod,prod,staging}.{yml,yaml}`.
- **Endpoints (`core/Stock/.../controller/ReservationController.java`)**:
  - `POST /reservation/{orderId}/create`
  - `GET /reservation/{reservationId}`
  - `GET /reservation/{orderId}/list`
  - `POST /reservation/{reservationId}/update`
  - `GET /reservation/{reservationId}/cancel`
  - `POST /reservation/quantity/update/{orderId}`
  - `POST /reservation/{orderId}/updatebyorderid`
  - `POST /reservation/transfer` — move a reservation from one warehouse to another (used in re-routing)
  - `POST /reservation/{orderId}/update/status`
- **Outgoing events**: `stock-events` Kafka topic (consumed by Settings: `EventProcessingServiceImpl.java:58`, autoStartup gated by `${spring.kafka.topics.stock-events.enabled:false}` — disabled by default!).
- **Entities**: `Reservation`, `Warehouse`, `Stock`, `StockQuota`, `AvailThreshold`, `DispatchCapacityLimit`.
- **Quirks**:
  - Two stock-update Kafka listeners (`stock-update`, `stock-delta-update`) coexist — older snapshot path + newer delta path. Misconfiguration on either causes drift between Stock and ENSI Catalog.
  - `StockMongoService` and `StockPostgresService` both exist — Stock has had a Mongo → Postgres migration; both DBs may be partially populated. Check which is authoritative per tenant.
  - Overselling: relies on Mongo/Postgres atomic operations; under high concurrency with multiple warehouses on the same SKU, partial reservation may succeed when full quantity should have failed. Mitigated by `dispatchCapacityLimit` and downstream OTS confirmation.
  - `stock-events` autoStartup `false` by default — events to Settings may not flow unless explicitly enabled per env. Verify in `stock-gj-prod.yaml`.

## BP-OMS-11: Order export to OTS / 1C / DWH

- **BPMN**: `export.bpmn`, `exportForPicking.bpmn`, `exportAfterPicking.bpmn`, `dwhStatusUpdate.bpmn`, `dwhPaymentUpdate.bpmn` — each is a thin BPMN with 1-3 `orderExportWithFeedbackActivity` external tasks.
- **Trigger**: Message events (catch) — e.g. `ORDER_CONFIRMED`, `PICKING_COMPLETE`, `TODISPATCH`, `ORDER_CANCELED`.
- **Handler**: `OrderExportWithFeedbackHandler.java:28` (topic `orderExportWithFeedbackActivity`).
- **What it does**:
  - Reads `destination` from process variables (OTS / 1C Ecom / 1C ЦБР / DWH / Mindbox).
  - Calls the appropriate downstream — `BpmFeignClient.exportOrder` → typically routed through `core/Adapter` (which has Feign clients to OTS, 1C systems).
  - Receives feedback (synchronous status), sets `result` process variable.
- **Adapter**: `core/Adapter` consumes Kafka topics for *inbound* status updates from those external systems (`OrderDataProcessingServiceImpl.java:49`, `CarrierDataProcessingServiceImpl.java:66`, `CarrierPackageDataProcessingServiceImpl.java:60`, `TimerProcessingServiceImpl.java:27`).
- **Quirks**:
  - Same handler topic for ~10 different destinations — destination logic is in BPMN variables, not in code. Hard to grep "where does OTS export happen?".
  - "1С ЦБР" vs "1С Ecom" — two different 1C tenants/systems. Both receive most events.

## BP-OMS-12: Carrier registration (waybill / tracking) — deep dive

(Already covered in BP-OMS-04, but expanding integration specifics.)

- **CDEK** — `core/cdek-api-sdk` (default branch `CLD-4877`). Java SDK with `OrderServiceImpl`, `CalculatorServiceImpl`, `CitiesServiceImpl`, `PickpointServiceImpl`, `UserService`. OAuth2 against `api.cdek.ru/v2/oauth/token`. Used inside `core/Delivery/.../carriers/cdek/`. Has `CdekCarrierTrackingRequestServiceImpl`. Order cancellation: `https://api.cdek.ru/v2/orders/{order_uuid}/refusal`.
- **Russian Post** — `core/russian-post-api-sdk` repo contains only `pom.xml` (no `src/`) in our clone. Russian Post integration lives in `core/Delivery/.../carriers/russianpost/`. Either the SDK is published privately via Nexus (Maven coordinates `com.starfish24:russian-post-api-sdk:1.0-SNAPSHOT`) and the src tree wasn't pushed here, or the SDK has been collapsed into Delivery directly.
- **5post** — separate Spring Boot service `core/5post-connector` (not just SDK; full service with REST API). Used by Delivery / Order via Feign. Endpoints: warehouse list, calculate delivery, AVD report tasks (`ReportTasksController.java`). Per-env config: `awg/cloud-configs/five-post-connector-gj-{preprod,prod,staging}.yml`. Note `.yml` for all three envs (not the usual `.yaml` for prod).
- **Yandex Cargo** — direct integration in Delivery (`/carriers/yandex/`). Uses `b2b.taxi.yandex.net/b2b/cargo/integration/v1` and `v2`. Separate Yandex NDD (next-day) on `b2b.taxi.tst.yandex.net` (TST — staging-ish).
- **IML, DPD, Topdelivery, Pickpoint, Boxberry, Sber Logistic, Vobaza, Dalli, CSE, BNS, Podorozhnik, Logsis, Lamoda, Lime** — each has a package under `core/Delivery/.../service/carriers/<name>/`. Direct REST clients per carrier.
- **Topdelivery cities update** — `core/Dictionary/.../carriers/TopdeliveryUpdateCitiesCodeService.java:35` listens to Kafka `${spring.kafka.topic.updatetopdelivery}` (default `dictionary-updatecity`) for city code refreshes.
- **Pickpoint updates** — `core/Dictionary/.../pickupPoint/PickupPointServiceImpl.java:184` Kafka listener `pickup-point-update-listener`.
- **Quirks**:
  - Carrier registry is **flat under `Delivery/carriers/`** — ~22 packages, no abstract factory. Adding a carrier means adding a new package + wiring in BPMN.
  - `RetrieveCarrierTokenServiceImpl` is a shared OAuth token cache for carriers; if it caches a stale token, every carrier call fails until restart.
  - The newer "carriers" package (plural, with generic `postCarriersOrders` topic) coexists with the older "carrier" (singular, per-carrier) — there are partial migrations.

## BP-OMS-13: Voximplant — outbound call (`voximplant.bpmn`)

- **Trigger**: Message events from confirmation (fraud confirmation by phone), payment received notifications.
- **Driver**: `core/BPM/src/main/java/com/starfish24/services/VoxServiceImpl.java:33` `@KafkaListener(topics = "${spring.kafka.topic.vox-send-to-queue}")` — events to dispatch outbound calls.
- **External system**: Voximplant (cloud telephony).
- **Use case**: When fraud check requires phone verification, an operator (or auto-IVR) calls the customer through Voximplant. The result (answered Y/N, confirmed Y/N) is fed back into confirmationProcess via the `Дозвонились и подтвердили?` gateway.

## BP-OMS-14: Resend gift certificate (`resendCertificateNotification.bpmn`)

- **Trigger**: Triggered when certificate (gift card) was issued but not delivered to recipient.
- **Service tasks** (delegateExpression): "SMS получателю", "Получить значение KA token", "Получить значение KA receiverPhone". KA = "корпоративный аккаунт" (corporate account) infra for gift certificates.
- Catches messages: DELIVERING, READY_FOR_PICKUP, CANCELLED, COMPLETED, plus NOTIFICATION_CANCELLED / NOTIFICATION_COMPLETED.

## BP-OMS-15: Release process (`releaseProcess.bpmn`)

- **Purpose**: Auxiliary / release-housekeeping process. Uses `orderExportWithFeedbackActivity`. Lower priority for end-to-end model — likely orchestrates DB release flags / cache invalidation on a per-release basis. Best read in conjunction with the BPMN; not exercised on every order.

## BP-OMS-16: Reporting (`core/reports`)

- **Trigger**: HTTP only — `core/reports` exposes synchronous report endpoints. No BPMN.
- **Endpoints** (`core/reports/src/main/java/com/starfish24/controllers/`):
  - `OrderReportController` — `POST /order/list/export`, `POST /analytics/reports/orders/failedCarrierRegistration`, `GET /analytics/reports/rules/orders`, `GET /analytics/reports/rules/dashboard`.
  - `SalesReportController` — `POST /products`, `POST /managers`, `POST /manager/perday`.
  - `CanceledOrderReportController` — `POST /analytics/reports/orders/canceledByOperator`.
  - `CourierCallController` — `POST /analytics/reports/courier/call`, `GET /carrier/couriercall/{reportId}`, `GET /carrier/couriercall/reports`.
  - `CallSessionController` — `GET /analytics/reports/calls/export` (Voximplant call reports).
  - `SlaReportController` — SLA dashboards, operations CSV/Excel.
  - `ItemStatusController` — `POST /statuschangeditems`.
  - `HistoryController` — `GET /item/{orderId}/status/history`.
  - `AccountingController` — `POST /accounting` (multipart upload, fiscal/accounting import).
  - `PaymentController` — `GET /payments`, `GET /prepayments`.
- **Per-env config**: `awg/cloud-configs/report-service-gj-{preprod,prod,staging}.yaml`.
- **Quirks**: Reports query Order/Stock/Settings databases directly (Mongo + Postgres). Heavy reads — historically a source of DB CPU spikes. Some endpoints stream Excel (`MediaType.APPLICATION_VND_MS_EXCEL_VALUE`).

---

## Cross-cutting: data store layout

| Service | Primary DB | Notes |
|---------|-----------|-------|
| `Order` | Postgres + Mongo | Order doc in Mongo, history/exports in Postgres |
| `Stock` | Postgres + Mongo | Both StockPostgresService and StockMongoService exist (migration ongoing) |
| `Delivery` | Postgres | Carrier configs, waybills, pickup points |
| `Dictionary` | Mongo + Postgres | Cities, streets, regions, pickup points |
| `Settings` | Postgres | Event→process mappings, status models, SLA rules |
| `Camunda` | Postgres | Camunda native schema (ACT_*) |
| `BPM` | (uses Camunda DB) | Stateless wrapper |
| `pay-service` | Postgres | Payments, receipts |
| `reports` | reads others | No own DB beyond cache |
| `Adapter` | Kafka-driven, no big DB | Message router |

## Cross-cutting: Kafka topics

| Topic (default) | Producer | Consumer | Purpose |
|------------------|----------|----------|---------|
| `${spring.kafka.topic}` (Settings events) | Order, Stock, others | Settings.EventProcessingServiceImpl | Generic OMS event bus → drives StartProcess |
| `${spring.kafka.topic.order}` | АРМ / Adapter producers | Adapter.OrderDataProcessingServiceImpl | Order updates from warehouse system |
| `${spring.kafka.topic.camunda-message}` | Various | Camunda.MessageConsumerServiceImpl | Throws BPMN messages from outside engine |
| `${spring.kafka.topic.status-update}` | Order, others | BPM.StatusUpdateServiceImpl | Status mutations |
| `${spring.kafka.topic.item-status-update}` | (same) | BPM.StatusUpdateServiceImpl | Item-level status |
| `${spring.kafka.topic.stock-update}` | ENSI/WMS | Stock.StockMongoService | Full stock snapshots |
| `${spring.kafka.topic.stock-delta-update}` | ENSI/WMS | Stock.StockMongoService | Deltas |
| `stock-events` | Stock | Settings.EventProcessingServiceImpl | Stock-related events (autoStartup `false` by default!) |
| `${spring.kafka.topic.vox-send-to-queue}` | BPM | BPM.VoxServiceImpl | Outbound calls |
| `${carrier-health.kafka.topic}` | (carrier monitors) | Settings.CarrierHealthServiceImpl | Carrier API health metrics |
| `${spring.kafka.topic.updatetopdelivery}` (default `dictionary-updatecity`) | Topdelivery sync | Dictionary.TopdeliveryUpdateCitiesCodeService | City code refresh |
| `pickup-point-update-listener` | Dictionary internal | Dictionary.PickupPointServiceImpl | Pickup point updates |

## Known quirks / legacy in play (cross-process)

1. **Two parallel "carrier" packages** in camunda-worker handlers (`handlers/Carrier*.java` per-carrier vs `handlers/carrier/*.java` generic). Partial migration to generic. Some BPMN paths use one, some the other.
2. **`russian-post-api-sdk` repo has no source** — only `pom.xml`. The actual carrier integration code is inside `Delivery/.../carriers/russianpost/`. The empty SDK repo is misleading; might be intentional (artifact-only) or an oversight.
3. **`yandex-ndd` config in prod points to `*.tst.yandex.net`** (`delivery-gj-prod.yaml`). Either a Yandex-side staging-as-prod arrangement or a config bug.
4. **`stock-events` Kafka listener `autoStartup: false`** by default in `EventProcessingServiceImpl`. If not explicitly enabled per env, stock-driven Settings events don't fire.
5. **Mongo ↔ Postgres dual storage** in `Stock` (and partially `Order`) — two services in the same JAR (`StockMongoService`, `StockPostgresService`). Migration ongoing.
6. **Brand-specific external task handlers hard-coded in shared `camunda-worker`**: BNT, Sisley, Galamart, Lamoda, Ourgold, RRNotPicked. Adding a brand = code change. Not data-driven via Settings.
7. **Notification template IDs (7720, 7736, 7738, ...) hardcoded in BPMN** — template management is out of OMS, but IDs are baked into XML. Changing a template = BPMN re-deploy.
8. **Camunda message names duplicated across BPMNs** (`ORDER_CONFIRMED` declared in 6+ files). Each is a separate subscription; throw is broadcast — verify desired fan-out.
9. **Long-running confirmation process (24h timer)** — running instances must be migrated on BPMN deploys; otherwise old instances continue on old definition (Camunda versioning behaviour).
10. **`orderExportWithFeedbackActivity` is one handler for ~10 destinations** — destination passed as process variable. No type-safe routing; misconfigured variable = silent wrong export.
11. **`OrderController` (singular) vs `OrdersController` (plural)** — two REST controllers in Order; easy to confuse. Singular is the main / write API; plural is the client-order-id-keyed one used by Integration.
12. **`@KafkaListener` topics use Spring property placeholders** — to know the actual prod topic name, read `awg/cloud-configs/<svc>-gj-prod.yaml` (where `spring.kafka.topic...` keys live), not `application.yml`.
13. **Sber callback uses GET with `tenantId` in path** — atypical for a payment webhook (usually POST + body signature). Server-to-server payment status appears to be polled rather than pushed.
14. **`courierServicesToIgnore40XError` process variable** allows BPMN to silently ignore 4xx errors from a configurable subset of carriers — useful for flaky carriers but hides real problems.
15. **Default branches that are NOT master/main** for several OMS repos: `Delivery` (`19783+19795`), `pay-service` (`CLD-1840`), `cdek-api-sdk` (`CLD-4877`), `cloud-configs` (`CLD-17047`), `integration-gj` (`develop`). When checking out for research, use the actual default branch.
16. **`OurgoldUpdateLotIdsHandler` has 5-minute (300_000 ms) lock duration** — significantly longer than other handlers (typically 30-50s). Suggests upstream Ourgold ERP latency.
17. **`awg/cloud-configs/` filename inconsistency**: `.yml` for staging/preprod, `.yaml` for prod (mostly). Some are `.yml` for all envs (e.g. `five-post-connector-*`). Drift between configs is common.

## What I could NOT determine from OMS alone

- **Exact event-id → BPMN-process mapping in production** — driven by the `EventProcess` table in `Settings` DB. Not in repo. Need DB inspection or `mcp__gj-buddy__logs_search_message` to observe.
- **Which OTS instance / 1C tenant** receives each export — destination variable comes from BPMN process variables set upstream; values appear to be in `Settings` per-tenant rules.
- **Russian Post SDK actual implementation** — `russian-post-api-sdk` repo has only `pom.xml`. Either artifact is built elsewhere (private Nexus) or src lives in `Delivery`. Need `mcp__gj-buddy__gitlab_*` to find the source repo.
- **`gj` brand vs other brands' active flows** — many BPMN tasks branch on brand (BNT, Sisley, Galamart, Lamoda, Ourgold). Which brands are alive in prod and what their flows look like end-to-end requires brand-by-brand walkthrough.
- **Whether `releaseProcess.bpmn` is currently used** — it has no clear external trigger; might be operator-launched only.
- **Stock origin flow** — Stock receives data via Kafka from ENSI/WMS, but the producer side is ENSI. Delegate to `ensi-researcher` for upstream.
- **Sber acquiring webhook (server-to-server)** — only `GET /callback` (browser return) is in this codebase. The actual money confirmation (preauthcancel, etc) seems to be polled. Need to verify with `oms-java-engineer`.
- **OMS-UI to backend communication map** — investigated as separate concern; not in this artefact.

## Suggested next steps

- `oms-java-engineer` — refactor `orderExportWithFeedbackActivity` into typed destinations (current single-topic-many-destinations is fragile).
- `camunda-bpm-engineer` — inventory which long-running confirmation instances exist on which BPMN version (Cockpit + migration plan).
- `oms-go-expert-coder` — `core/go/logistics` is a separate Go service (has own CLAUDE.md). It overlaps with Delivery but isn't covered here — separate artefact recommended.
- `integration-researcher` — to map upstream flow (site/mobile/checkout → integration → Order `POST /order/create`).
- `ensi-researcher` — to verify the producer side of `stock-update` / `stock-delta-update` topics.
- `architect` — consolidate brand-specific external task handlers via a Strategy pattern + Settings DB instead of code.
- `logs-detective` — verify `yandex-ndd` `*.tst.yandex.net` is real prod usage or a config bug; check live order traces.

## File references

Primary sources (all under `$WORKSPACE/platform/starfish24/`):

- BPMNs: `awg/bpmn-process/process/gloriajeans/*.bpmn`
- External task handlers: `core/camunda-worker/src/main/java/com/starfish24/handlers/`
- BPM facade: `core/BPM/src/main/java/com/starfish24/controllers/`, `core/BPM/src/main/java/com/starfish24/services/`
- Camunda engine: `core/Camunda/src/main/java/com/starfish24/bpm/engine/`
- Order: `core/Order/src/main/java/com/starfish24/controller/`, `services/orderService/`, `entities/order/`
- Stock: `core/Stock/src/main/java/com/starfish24/controller/`, `service/stock/`
- Delivery: `core/Delivery/src/main/java/com/starfish24/delivery/`
- pay-service: `core/pay-service/src/main/java/com/starfish24/controller/`
- Settings (event→process mappings, status models): `core/Settings/src/main/java/com/starfish24/service/handler/StartProcess.java`, `EventProcessingServiceImpl.java`
- Adapter (Kafka inbound from external systems): `core/Adapter/src/main/java/com/starfish24/service/`
- Reports: `core/reports/src/main/java/com/starfish24/controllers/`
- Notifications gateway: `core/Cloud-Message-Gateway/`
- Per-env configs: `awg/cloud-configs/<svc>-gj-<env>.{yml,yaml}`
- Related: `do../research/2026-05-20-checkout-order-creation.md` (pre-checkout, intervals, capacity).

---

## Appendix A — Full BPMN inventory (file by file)

### `confirmationProcess.bpmn` (2438 lines)

- Process id: `confirmationProcess`
- Start event: `StartEvent_1` (async before/after) — entered from `BpmFeignClient.startProcess`.
- 30+ service tasks (mix of delegate and external).
- 30+ exclusive gateways.
- Catch events: `CANCELLING`, `PT3H`, `PT24H` (non-payment timeout), `PT30M`, `PT10S`, `PT3S`, `PT1M`, `IS_PAID_CHANGED`, `CONFIRM`.
- Throw events: `PAYMENT_RESERVATION_COMPLETE`, `IS_PAID_CHANGED_FROM_CONFIRMATION_PROCESS`.
- User task: `gjErrorProblem1` — operator manual review.
- Topics consumed: `createReservation`, `orderExportWithFeedbackActivity`.
- Critical custom attributes set: `cancellationStage`, `wasSuspended`, `nonPaymentCancellationDateTime`.

### `pickingProcess.bpmn` (1598 lines)

- Process id: `pickingProcess`
- Multi start (entry from `PICKING_START` or `RETURN_TO_PICKING_AFTER_CANCELLING` message).
- Distinct branches per fulfilment type (FF / SFS / C&R).
- Catch events: `PICKING_COMPLETED`, `CANCELLING`, `ORDER_CONFIRMED_WAREHOUSE`, `CHECKED_INVALID`, `PT10S`, `PT30M`, `PT1M`.
- Throws: `PICKING_COMPLETE` (to dispatch + payment).
- Topics: `orderExportWithFeedbackActivity`.

### `dispatchProcess.bpmn` (1028 lines)

- Process id: `dispatchProcess`
- Catch events: `CANCELLING`, `DELIVERING (OTS)`, `READY_FOR_PICKUP (АРМ)`, `DELIVERING (АРМ)`, `LOST (АРМ)`, `PT20S`, `RETURN_TO_DISPATCH_AFTER_CANCELLING`, plus per-channel `DELIVERING_AFTER_CANCELLING_FOR_{FF,CC,SFS}`.
- CDEK and Yandex have dedicated gateway branches.
- Topics: `carrierOrderExport`, `carrierTrackingId`, `orderExportWithFeedbackActivity`.

### `cancellationProcess.bpmn` (2952 lines — largest)

- Process id: `cancellationProcess`
- Heavy because it has to undo every prior state. Reads `cancellationStage` and `isOrderShipmentRegistered` to decide what cleanup to run.
- Delegates: `carrierCancelOrderActivity`, `reserveStatusUpdateActivity`, `addHistoryActivity`, `getCustomAttributeActivity`.
- Topics: `orderExportWithFeedbackActivity` (many), `deleteCarriersOrders`.

### `paymentProcess.bpmn` (2175 lines)

- Process id: `paymentProcess`
- Multi-start: `PAYMENT_RESERVATION_COMPLETE`, `PAYMENT_PICKING_COMPLETE`, `PAYMENT_FULL_CHARGE`, `PAYMENT_PARTIAL_CHARGE_AFTER_HOLD`.
- Hold-then-capture pattern (typical card-payment two-stage).
- Topics: `acquierChargeRequest`, `acquierRefundRequest`.
- Embedded receipt issuance via `sendEvent`.

### `paymentFinalizationProcess.bpmn`

- Process id: `paymentFinalizationProcess`
- Topics: `acquierPreauthCancel`, `acquierRefundRequest`, `isNeedRefund`, `orderExportWithFeedbackActivity`.
- Loyalty bonus return via `gjOrderLoyaltyReturn` delegate.

### `carrierRegistryProcess.bpmn`

- Process id: `carrierRegistryProcess` (with explicit `camunda:versionTag="1.0.0"`).
- Per-carrier deadline timers hardcoded (CDEK 12:00, Pickpoint 10:50, Russian Post 18:00).

### `notifications.bpmn`

- Process id: `notifications`
- Pure fan-out from catch events to `sendTransactionalMessage` external tasks with hardcoded template IDs.
- "Polite hours" intermediate catch event.

### `export.bpmn`, `exportForPicking.bpmn`, `exportAfterPicking.bpmn`

- All thin BPMNs that invoke `orderExportWithFeedbackActivity` against OTS / 1C ЦБР / 1C Ecom.

### `dwhStatusUpdate.bpmn`, `dwhPaymentUpdate.bpmn`

- Thin BPMNs that push status / payment change events to DWH via `orderExportWithFeedbackActivity`.

### `voximplant.bpmn`

- Process id: `voximplant`. Outbound call orchestration for fraud / confirmation.

### `resendCertificateNotification.bpmn`

- Process id: `resendCertificateNotification`. Re-issues SMS/email of gift card details when needed.

### `releaseProcess.bpmn`

- Process id: `releaseProcess`. Auxiliary; likely operator-launched.

---

## Appendix B — Endpoint reference

### `core/Order` (`OrderController` `/order/*`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/order/export` | Push order to external marketplace |
| POST | `/order/create` | Create new order (main entry) |
| POST | `/order/{orderId}` | Update order details |
| DELETE | `/order/{orderId}` | Delete order |
| POST | `/order/{orderId}/customattributes` | Add custom attrs |
| GET | `/order/{orderId}/customattributes` | Read custom attrs |
| POST | `/order/{orderId}/marketing` | Set marketing data |
| GET | `/order/{orderId}/marketing` | Read marketing |
| POST | `/order/{orderId}/history` | Add history entry |
| GET | `/order/{orderId}/history` | Read history (paged) |
| POST | `/order/status/{orderId}/{statusId}/update` | Single status mutation |
| POST | `/order/status/update` | Batch status mutation |
| GET | `/order/create/newid` | Generate new clientOrderId |
| POST | `/order/{orderId}/comment` | Add comment |
| POST | `/order/calculate` | Recompute totals |
| POST | `/order/{orderId}/cancelationreason/{cancelationReasonId}/set` | Set cancel reason |
| POST | `/order/{orderId}/cancel` | Cancel order (triggers cancellation flow) |
| POST | `/order/customerservice/calculate` | Customer-service line items calc |
| GET | `/order/brand/list` | List brands |
| POST | `/order/brand/update` | Add/update brand |
| POST | `/order/link` | Set order links |
| POST | `/order/{orderId}/update/ispaid` | Mark paid |
| POST | `/order/{orderId}/dispatch` | Trigger dispatch |
| GET | `/order/{parentOrderId}/clone` | Clone order |
| POST | `/order/{orderId}/fraud/check` | Manual fraud trigger |

Plus `OrdersController` `/orders/*` for client-order-id-keyed access (Integration uses these heavily).

### `core/Stock` (`ReservationController` `/reservation/*`)

See BP-OMS-10 above.

### `core/pay-service` (`OnlinePaymentController` `/onlinepay/*`)

See BP-OMS-06 above.

### `core/BPM` (process facade)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/process/{processId}/start` | Start a BPMN process (typical caller: Settings.StartProcess) |
| POST | `/process/{processId}/start/custom` | Start with custom variables |
| POST | `/variable/{orderId}/set` | Set process variables |
| GET | `/process/order/variables/{orderId}` | Read process variables |
| POST | `/variable/{orderId}/shipping/update` | Update shipping variables |
| POST | `/variable/{orderId}/packages/update` | Update package variables |
| POST | `/signal/{signalId}/send` | Send Camunda signal |
| POST | `/message/{messageId}/send` | Send Camunda message (used for cross-process throws from outside) |
| GET | `/task/{orderId}/getbyorderid` | List tasks by order |
| POST | `/task/{taskId}/complete` | Complete user task |
| POST | `/task/{taskId}/{userId}/assign` | Assign user task |
| POST | `/templateMessage/send` | Send template message |
| POST | `/calculation/commit` | Commit order calculation |
| POST | `/owox/return/{orderId}` | OWOX analytics: return |
| POST | `/owox/create/{orderId}` | OWOX analytics: create |

### `core/Delivery` (carrier orchestration)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/carrier/{particularCarrierId}/price/request` | Quote price |
| POST | `/carrier/{particularCarrierId}/neworder/request` | Register order in carrier |
| GET | `/carrier/{carrierId}/registry` | Get registry |
| POST | `/carrier/{carrierId}/registry` | Submit registry |
| GET | `/carrier/{carrierId}/tracking/{trackingId}/request` | Track |
| GET | `/carrier/{particularCarrierId}/cancelorder/{trackingId}/request` | Cancel shipment |
| POST | `/carrier/{particularCarrierId}/confirm` | Confirm shipment |
| POST | `/carrier/{particularCarrierId}/couriercall/request` | Call courier |
| GET | `/carrier/{particularCarrierId}/couriercall/{carrierCourierCallId}/request` | Check call status |
| POST | `/carrier/{particularCarrierId}/couriercall/report` | Send call report |
| GET | `/carrier/tracking/{carrierId}/order/{orderId}` | Order tracking |
| GET | `/carrier/cdek/cities` | CDEK cities |
| GET | `/carrier/dpd/warehouse` | DPD warehouse list |
| POST | `/carrier/{particularCarrierId}/create/deliverybundle` | Create bundle |
| POST | `/carrier/{particularCarrierId}/checkin/deliverybundle` | Check in bundle |
| POST | `/carrier/{particularCarrierId}/deleteorder/deliverybundle` | Remove from bundle |

### `core/5post-connector`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/warehouse` / `/warehouse/{id}` | List/get warehouses |
| GET | `/pickuppoint/conditions` | Pickup point conditions |
| GET | `/pickuppoint/{id}/conditions` | Per-pickup conditions |
| GET | `/pickuppoint/update` | Trigger refresh |
| POST | `/reports/avds` | AVD report task |
| GET | `/reports/avds` (CronController) | AVD scheduled task |
| GET | `/calculate` / POST | Calculate delivery |
| GET | `/migration/warehouses` | Warehouse migration |

