---
name: gloriaots-stack-anatomy
description: Use when working with Gloria OTS (Order Transport System) in platform/gloriaots/. Explains monorepo layout, .NET projects, workers, WMS/carrier integrations, RabbitMQ event bus, and ties to OMS/Integration e-commerce flows. Trigger on anything related to GloriaOTS, OTS, gloriaots/.
---

# Gloria OTS Stack Anatomy

`platform/gloriaots/gloriaots/` — один monorepo (GitLab `gloriaots/gloriaots`, branch `master`).

**Домен:** логистика Gloria Jeans (не ядро e-commerce, но критичен для исполнения заказов интернет-магазина).

## Solution layout

```
GloriaOTS.sln
├── src/GloriaOTS.ApplicationCore/   # домен, DTO, interfaces, OTSModels, events (no entry point)
├── src/GloriaOTS.EventBus/          # RabbitMQ abstractions + conventions
├── src/GloriaOTS.Infrastructure/    # EF Core, repos, ShipmentServices, WmsServices, handlers, Hangfire
├── src/GloriaOTS.Web/               # HTTP API, Swagger, Hangfire dashboard, React admin SPA
└── src/Workers/
    ├── GloriaOTS.OrderTracking/     # фоновый трекинг, cancel flow, FORWARD_STATUS
    └── GloriaOTS.WmsSync/           # WMS/TGW/1C sync — один процесс на склад (Warehouse=NSK|MSK)
```

Dependency direction:

```text
EventBus → ApplicationCore → Infrastructure → Web | OrderTracking
WmsSync → ApplicationCore (+ own TGW logic)
```

## Runtime components

| Process | Role |
|---------|------|
| `GloriaOTS.Web` | Entry point: order/balance API v1–v3, admin API, SignalR, jobs trigger |
| `GloriaOTS.OrderTracking` | Polls TK/WMS statuses, notifications, cancellation |
| `GloriaOTS.WmsSync` | Consumes `Tgw*Event`, writes WMS DB, 1C registry; env `Warehouse=` |

## Infrastructure deps

- SQL Server: `ConnectionStrings__Ordering`, `ConnectionStrings__Hangfire`
- RabbitMQ: `EventBusRabbitMQSettingsInternal` (+ external for WmsSync)
- Redis: distributed lock / cache
- DB bootstrap: `Database/SqlDeploy` (no auto-migrate on startup)

## Key integration areas

### Transport companies (ТК)

- Contract: `IShipmentService` in `ApplicationCore/Interfaces/TKManager/`
- Implementations: `Infrastructure/Services/ShipmentServices/*`
- Orchestration: `ShipmentServiceFacade.cs` (must wire new carriers here)
- Enum + routing: `ApplicationCore/Constants/ShipmentService.cs`, `ShipmentServiceHelper.cs`
- DI: `Infrastructure/Services/DependencyInjectionExtensions.cs`

### WMS / warehouses

- Contract: `IWmsService` in `ApplicationCore/Interfaces/WMSServices/`
- Orchestration in Web: `Infrastructure/Services/WmsServices/WmsService.cs`
- Execution in worker: `Workers/GloriaOTS.WmsSync/Tgw/TgwWmsService.cs`
- Warehouse enum: `ApplicationCore/Constants/WarehouseTypeHelper.cs`
- One worker instance per warehouse slug (`NSK`, `MSK`, …)

### Order handlers (status workflow)

Handlers live under `Infrastructure/` (e.g. `Handlers/ORDER_TO_CHECK/`, `CancellingHandlers/`).
Main API actions: `ORDER_TO_CHECK`, `ORDER_TO_PICKING`, `ORDER_TO_PICKUP`, `ORDER_TO_EDIT`.

## E-commerce neighbors

| System | Integration |
|--------|-------------|
| **OMS (Starfish)** | BPMN export via `orderExportWithFeedbackActivity` → `Adapter` → OTS; statuses back to OMS |
| **Integration** | `OtsClient`, `OrderExportOtsMutator`, cron stock sync, Kafka daemons BP-INT-30/31 |
| **ENSI offers** | Stock push flows reference OTS as source (via Integration) |

See `docs/bp/08-master-data-sync.md`, `docs/bp/glossary.md` (OTS).

## Docs in repo

- Root `README.md` — dev guides (new TK, new WMS, API list, deploy)
- `src/Workers/GloriaOTS.OrderTracking/README.md`
- `src/Workers/GloriaOTS.WmsSync/README.md`
- `src/GloriaOTS.EventBus/README.md`
- `Docs/` — carrier client notes (CDEK, DPD, Russian Post, …)

## Local dev commands

```bash
cd platform/gloriaots/gloriaots
docker compose -f docker-compose.yml up -d rabbitmq redis aspire-dashboard
dotnet run --project src/GloriaOTS.Web
dotnet run --project src/Workers/GloriaOTS.OrderTracking
# WmsSync: Warehouse=NSK dotnet run --project src/Workers/GloriaOTS.WmsSync
```

## Deploy notes

- GitLab CI: `.gitlab-ci.yml` — build/push images, stage + prod (RND / NSK / MSK)
- Prod splits: `web`+`order-tracking` on RND; `wms-sync` per region
- Config override: env vars `SECTION__KEY` (standard ASP.NET Core)

## When repo is not cloned

Use Buddy MCP `gitlab_get_repository_file`, `gitlab_list_repository_tree` on project `gloriaots/gloriaots`.
