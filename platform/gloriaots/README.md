# Platform: Gloria OTS

**Order Transport System (OTS)** — транспортно-логистическая система Gloria Jeans. Не входит в ядро e-commerce, но тесно связана с OMS, Integration и процессами исполнения заказов (экспорт заказов, статусы, остатки, WMS, ТК).

## Что здесь должно лежать

```
gloriaots/
└── gloriaots/                    # главный monorepo (GitLab: gloriaots/gloriaots)
    ├── src/
    │   ├── GloriaOTS.Web/        # ASP.NET Core API + Hangfire + React/Vite admin SPA
    │   ├── GloriaOTS.ApplicationCore/
    │   ├── GloriaOTS.Infrastructure/
    │   ├── GloriaOTS.EventBus/   # RabbitMQ event bus
    │   └── Workers/
    │       ├── GloriaOTS.OrderTracking/
    │       └── GloriaOTS.WmsSync/  # отдельный инстанс на склад (NSK, MSK, …)
    ├── Database/                 # SQL Server: SqlDeploy, migrations, DDL
    ├── Docs/                     # интеграции с ТК (CDEK, DPD, ПР, 5post, …)
    └── GloriaOTS.sln
```

Смежный репозиторий в группе `gloriaots/` (не клонирован по умолчанию):

| Репо | GitLab | Назначение |
|------|--------|-----------|
| wmsinserter-2.0 | `gloriaots/wmsinserter-2.0` | WMS inserter |

## GitLab

- Группа: https://gitlab.gloria.aaanet.ru/gloriaots
- Главный репо: https://gitlab.gloria.aaanet.ru/gloriaots/gloriaots
- Default branch: `master`

## Setup

```bash
mkdir -p platform/gloriaots && cd platform/gloriaots
git clone git@gitlab.gloria.aaanet.ru:gloriaots/gloriaots.git
```

Полный реестр и связи с e-commerce — `<workspace>/docs/service-index.md` → раздел «Платформа Gloria OTS».

## Стек

- **.NET 10** (ASP.NET Core), EF Core, Hangfire
- **SQL Server** (Ordering + Hangfire)
- **RabbitMQ** (internal + external event bus)
- **Redis**, OpenTelemetry
- **React + Vite** (admin SPA в `ClientApp/`)
- **Docker Compose** + GitLab CI для stage/prod (площадки RND, NSK, MSK)

## Связь с e-commerce

| Направление | Система | Как |
|-------------|---------|-----|
| OMS → OTS | Starfish (`Adapter`, BPMN export) | выгрузка заказов, статусы `DELIVERING (OTS)` |
| Integration ↔ OTS | `platform/integration/` | `OtsClient`, export mutators, Kafka daemons (статусы, stock) |
| OTS → WMS/1C | `GloriaOTS.WmsSync` | TGW telegram, реестры 1C по складам |
| OTS → ТК | `ShipmentServices/*` | CDEK, DPD, Почта России, Yandex, Own, … |

Подробнее: `docs/bp/08-master-data-sync.md`, `docs/bp/source/oms-processes.md` (BP-OMS-11).

## Агенты

- `gloriaots-navigator` — навигация по monorepo
- `gloriaots-researcher` — расследование поведения, интеграций OMS/Integration
- `gloriaots-engineer` — изменения .NET/C# кода

Скилл: `gloriaots-stack-anatomy`.

## Локальный запуск (кратко)

```bash
cd platform/gloriaots/gloriaots
docker compose -f docker-compose.yml up -d rabbitmq redis aspire-dashboard
dotnet run --project src/GloriaOTS.Web
# SPA: cd src/GloriaOTS.Web/ClientApp && corepack yarn dev
```

Детали — README внутри клонированного репо.
