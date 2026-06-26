# GJ-Ecommerce — Agentic Workspace для Gloria Jeans

Workspace для разработки **e-commerce платформы Gloria Jeans** и смежных логистических систем. Код организован в независимые платформенные зоны: основные e-commerce платформы живут в `platform/<system>/`, а новые/экспериментальные контуры — в `platform-new/` и `platform-next/`. Настроены: **ENSI**, **Mobile App**, **Integration**, **Site**, **Starfish (OMS)**, **Gloria OTS**, плюс смежные зоны **ARM**, **1C**, **Data Analytics**, **DevOps** и **Non-Platform**.

В документах `$WORKSPACE` означает локальный корень этого клона (`GJ-Ecommerce/`). Не подставляй абсолютный путь конкретного разработчика в tracked файлы.

## Структура корня

```
GJ-Ecommerce/
├── platform/
│   ├── ensi/         — ENSI: CMS, PIM, Offers, Customers, Admin GUI, Connectors (PHP/Swoole + Go)
│   ├── starfish24/   — OMS (Starfish): 32 репо — Java Spring Boot + 1 Go (logistics) + Camunda BPM + GJ overlay (awg/)
│   ├── integration/  — Integration Service: integration (Lumen) + logger/msq-client/health (PHP libs)
│   ├── site/         — Frontend сайт: gj-ng-front (Angular 20 + Nx monorepo + NgRx + NestJS SSR)
│   ├── mobile-app/   — Мобильное приложение: gj-app (RN monorepo) + mobapp-api-types
│   ├── gloriaots/    — Gloria OTS: Order Transport System (.NET 10, SQL Server, RabbitMQ)
│   ├── 1s8-enterprise/ — 1C enterprise configs: retail / logistics contours
│   ├── arm/          — retail-store ARM/POS/order/stock services
│   ├── data-analytics/ — Airflow, dbt, analytics scripts
│   ├── devops/       — shared deployment values/configs
│   └── non-platform/ — adjacent services: feeds, merch, reports, stock, bots
├── platform-new/     — new e-commerce Go services / clients / libs (ignored by root git)
├── platform-next/    — mini / mini-gj experimental workspaces (ignored by root git)
├── docs/             — service-index, onboarding, architecture (ADRs)
├── .claude/          — канон: agents/, skills/, rules/ (в git); GSD/hooks — локально
├── .cursor/rules/    — симлинки на .claude/rules/ (для Cursor)
└── CLAUDE.md         — этот файл
```

## Платформа ENSI (`platform/ensi/`)

```
platform/ensi/
├── apps/        — ~25 микросервисов
├── packages/    — переиспользуемые PHP-клиенты
├── workspace/   — elc workspace.yaml (контейнерная оркестрация)
├── devops/      — helm charts, gitlab-ci, base-image, ms-helm-chart
└── internal/    — внутренние generated клиенты
```

**Стек:** PHP 8.1/Swoole (большинство сервисов), местами FPM 8.1, Node для фронта админки, плюс Go-сервисы. PostgreSQL 13 + PostGIS, Elasticsearch 7.9.2, Kafka, Redis 6. CI/CD через GitLab + Helm. **OpenAPI-first** дизайн API.

### Где что искать в ENSI

| Задача | Путь |
|--------|------|
| Каталог товаров (PIM) | `platform/ensi/apps/catalog/pim` |
| Цены и акции | `platform/ensi/apps/catalog/offers` (PHP) / `platform/ensi/apps/catalog/offers-go` (Go) |
| Фиды | `platform/ensi/apps/catalog/feed` |
| Кеш каталога для фронта | `platform/ensi/apps/catalog/catalog-cache` |
| Контент-страницы | `platform/ensi/apps/cms/cms` |
| Профили покупателей | `platform/ensi/apps/customers/customers` |
| Аутентификация админов | `platform/ensi/apps/units/admin-auth` |
| Аутентификация покупателей | `platform/ensi/apps/customers/customer-auth` |
| Корзина | `platform/ensi/apps/orders/baskets` |
| Группировка заказов | `platform/ensi/apps/orders/order-group-service` |
| Бизнес-юниты (юр.лица) | `platform/ensi/apps/units/bu` |
| Адмика backend | `platform/ensi/apps/admin-gui/admin-gui-backend` |
| Адмика frontend | `platform/ensi/apps/admin-gui/admin-gui-frontend` |
| Публичный API для сайта/моб. | `platform/ensi/apps/customers-api-web` |
| Аудит-лог | `platform/ensi/apps/connectors/audit` |
| Внешние API | `platform/ensi/apps/connectors/{webapi,ensi}-connector` |
| Картинки/CDN | `platform/ensi/apps/connectors/cdn-adapter` |
| Event dispatch | `platform/ensi/apps/connectors/event-dispatcher` (PHP) + `platform/ensi/apps/go/event-dispatcher` (Go) |
| Inter-service PHP-клиенты | `platform/ensi/packages/*-client-php` |

Полный реестр сервисов — `docs/service-index.md`.

## Платформа Starfish / OMS (`platform/starfish24/`)

```
platform/starfish24/
├── awg/                              # GJ-specific overlay (4 репо)
│   ├── integration-gj/               # almost empty (README placeholder)
│   ├── bpmn-process/process/         # BPMN XML — процессы для Camunda
│   ├── cloud-configs/                # per-service per-env YAML (Spring Cloud Config)
│   └── gloria_ci/                    # Jenkinsfile пайплайны
└── core/                             # 27 репо ядра OMS (Starfish)
    ├── go/logistics/                 # ⭐ Go-сервис с собственным .claude/ + CLAUDE.md
    ├── Order, Stock, Delivery, Dictionary  # core domain
    ├── Camunda, BPM, camunda-worker        # workflow engine + workers
    ├── Settings, SSO, API-Gateway, Cloud-config-server
    ├── Parsers, Adapter, Cloud-Message-Gateway, Websocket, OMS-UI, oms-alerts
    ├── product, pay-service, reports, 5post-connector
    └── oms-objects, oms-json, telemetry-starter, cdek-api-sdk, russian-post-api-sdk, local-discovery-client (shared libs)
```

**Стек:** **Java Spring Boot** (Maven, Lombok, JKS truststore) для большинства сервисов · **Go** (Gin + Kafka + Redis, Clean Architecture) для `logistics` · **Camunda BPM** как orchestration core (engine + external task workers + BPMN-процессы в `awg/bpmn-process`) · **Spring Cloud Config** (per-env values в `awg/cloud-configs/`) · **Jenkins** для CI/CD (`awg/gloria_ci/Jenkinsfile*`).

**Особенности:**
- Многие default-branch ≠ master/main: `Delivery` (`19783+19795`), `pay-service` (`CLD-1840`), `cdek-api-sdk` (`CLD-4877`), `cloud-configs` (`CLD-17047`), `integration-gj` (`develop`)
- В `platform/starfish24/core/go/logistics/.claude/` — готовый набор Go-агентов от команды logistics; для работы прямо в logistics использовать локальные агенты этого репо.
- Подробнее: `.claude/skills/oms-stack-anatomy/SKILL.md`, `.claude/skills/oms-java-conventions/SKILL.md`, `.claude/skills/camunda-bpm/SKILL.md`, плюс `platform/starfish24/core/go/logistics/CLAUDE.md` для Go-специфики

## Платформа Site (`platform/site/`)

```
platform/site/gj-ng-front/        # Nx monorepo — branch: release/production (!)
├── apps/
│   ├── site-ru/, site-en/, site-kz/         # 3 локализованных Angular apps
│   └── site-{ru,en,kz}-e2e/                 # Cypress e2e
├── libs/
│   ├── core/                                # i18n, store, services, utils, models
│   ├── data-access/                         # API клиенты
│   ├── modules/{basket,catalog,checkout,home,profile}/  # feature-модули
│   ├── routing/, server/ (NestJS SSR), shared/, analytics/
│   ├── ui/ (high-level + storybook), ui-kit/ (primitives + storybook)
├── tools/generators/                        # nx generators
├── configs/, .devserver/ (mock API), .storybook/, deprecated/
└── nx.json / package.json (npm) / tsconfig.base.json
```

**Стек:** **Angular 20** + Angular SSR (Universal) + Angular Material/CDK · **Nx 21.6.8 monorepo** · **NestJS 11** (хостит SSR + mock API) · **NgRx 20** (store/effects/entity/component-store/router) · **TypeScript 5.9** · **Transloco** (ru/en/kz) · **SCSS** + stylelint · **Storybook 9** · **Jest** + **Cypress 13** · **GrowthBook** · **npm** + **Volta** (Node 20.9). 5 build-флейворов: `development`/`demo`/`testing`/`staging`/`production`.

**Default branch — `release/production`** (нестандартно). Активная разработка обычно на `develop` и feature-ветках.

**Назначение:** публичный сайт GJ (RU+EN+KZ). Ходит в backend через `libs/data-access/` (вероятно в Integration → ENSI).

**Команды (из `platform/site/gj-ng-front/`):**
```bash
npm install                       # установить deps (Volta → Node 20.9.0)
npm run start:mock                # site-ru + mock API
npm run dev                       # SSR + mock
npm run test:all                  # Jest все проекты
npm run lint:all && npm run stylelint:all
nx build site-ru --configuration production
nx dep-graph                      # визуальный граф зависимостей
```

Подробнее: `.claude/skills/site-stack-anatomy/SKILL.md`, `.claude/skills/site-nx-commands/SKILL.md`, `.claude/skills/site-angular-conventions/SKILL.md`.

## Платформа Integration (`platform/integration/`)

```
platform/integration/
├── integration/        # главный monorepo (Lumen, branch dev): www/ (PHP app) + containers/ (Docker)
│   ├── www/            # Lumen application (artisan, composer, phpunit, phpstan)
│   └── containers/     # 2 deploy: integration-api (HTTP) + integration-cron (scheduler)
├── logger/             # PHP lib — логирование (обёртка над Monolog)
├── msq-client/         # PHP lib — message queue client (с DB-миграциями для outbox)
└── health/             # PHP lib — health/readiness endpoints
```

**Стек:** PHP + **Lumen** (lightweight Laravel), Composer, phpstan, phpunit. Runtime: PHP-FPM + nginx + supervisor + filebeat (ELK). **Два деплоя из одного codebase:** `integration-api` (HTTP) и `integration-cron` (cron tasks через `crontab-php`).

**Назначение:** связующий слой между сайтом/мобильным приложением и backend (ENSI, OMS) для чекаута. Также cron-задачи для синков и фидов.

Подробнее: `.claude/skills/integration-stack-anatomy/SKILL.md`, `.claude/skills/integration-deployment/SKILL.md`, `.claude/skills/integration-php-conventions/SKILL.md`.

## Платформа Mobile App (`platform/mobile-app/`)

```
platform/mobile-app/
├── gj-app/                       # React Native monorepo (yarn workspaces)
│   ├── packages/gj/              # основное RN-приложение (workspace "GloriaJeans")
│   │   ├── android/, ios/        # нативные платформы
│   │   ├── src/                  # TS source
│   │   └── .env.{development,staging,production}
│   ├── packages/ui-kit/          # компоненты, ассеты, стили, типы
│   └── packages/rn-yookassa-sdk/ # обёртка YooKassa (платежи)
└── mobapp-api-types/             # общие TS-типы для API-контрактов
```

**Стек:** React Native 0.74.1 + React 18 + TypeScript 5, yarn workspaces, styled-components 6, Firebase, Reactotron, patch-package. 3 build-flavor: `development` / `staging` / `production`. iOS через Cocoapods, Android через gradle. Hooks: husky + lefthook + lint-staged.

**Команды (из `platform/mobile-app/gj-app/`):**
```bash
yarn                          # установить все workspaces
yarn yookassa:prepare         # bootstrap YooKassa
yarn gj:pod-install           # iOS pods
yarn gj:start                 # Metro
yarn gj:ios:staging           # запустить iOS staging
yarn gj:android:production    # сборка Android prod
yarn lint && yarn gj:ts       # проверки
```

Подробнее: `.claude/skills/mobile-build-commands/SKILL.md`, `.claude/skills/mobile-stack-anatomy/SKILL.md`, `.claude/skills/mobile-rn-conventions/SKILL.md`.

## Платформа Gloria OTS (`platform/gloriaots/`)

```
platform/gloriaots/
└── gloriaots/                              # monorepo (GitLab: gloriaots/gloriaots, branch master)
    ├── src/
    │   ├── GloriaOTS.Web/                  # ASP.NET Core API, Hangfire, React/Vite admin SPA
    │   ├── GloriaOTS.ApplicationCore/      # домен, контракты, OTSModels
    │   ├── GloriaOTS.Infrastructure/       # EF Core, ShipmentServices, WmsServices, handlers
    │   ├── GloriaOTS.EventBus/             # RabbitMQ
    │   └── Workers/
    │       ├── GloriaOTS.OrderTracking/    # трекинг заказов, cancel flow
    │       └── GloriaOTS.WmsSync/          # WMS/TGW/1C — отдельный процесс на склад (NSK, MSK, …)
    ├── Database/                           # SQL Server (SqlDeploy, migrations)
    └── Docs/                               # документация интеграций с ТК
```

**Стек:** **.NET 10** + ASP.NET Core · **SQL Server** · **RabbitMQ** (internal/external bus) · **Redis** · **Hangfire** · **React + Vite** (admin UI) · Docker Compose + GitLab CI.

**Домен:** логистика Gloria Jeans — **Order Transport System (OTS)**. Не ядро e-commerce, но критична для исполнения заказов: экспорт из OMS, статусы в магазины/склады, синхронизация остатков, интеграции с ТК (CDEK, DPD, Почта России, …) и WMS.

**Связи с e-commerce:**
- **OMS** → OTS: выгрузка заказов через `Adapter` / BPMN (`orderExportWithFeedbackActivity`)
- **Integration** ↔ OTS: `OtsClient`, export mutators, Kafka daemons (статусы BP-INT-30, stock BP-INT-25)
- **OTS** → WMS/1C/ТК: workers и `ShipmentServices`

**Команды (из `platform/gloriaots/gloriaots/`):**
```bash
docker compose -f docker-compose.yml up -d rabbitmq redis aspire-dashboard
dotnet run --project src/GloriaOTS.Web
dotnet run --project src/Workers/GloriaOTS.OrderTracking
# WmsSync: Warehouse=NSK dotnet run --project src/Workers/GloriaOTS.WmsSync
```

Подробнее: `.claude/skills/gloriaots-stack-anatomy/SKILL.md`, README внутри клонированного репо.

## Дополнительные зоны `platform/`

| Зона | Назначение | Когда смотреть |
|------|------------|----------------|
| `platform/1s8-enterprise/` | 1C retail / LC конфигурации | store-from-store, retail pickup, stock/order hypotheses involving 1C |
| `platform/arm/` | ARM/POS/store execution services | магазинное исполнение заказов, касса, остатки, labels, TSD, store UI |
| `platform/data-analytics/` | Airflow, dbt, analytics scripts | аналитические пайплайны, витрины, data lineage |
| `platform/devops/` | Shared deploy configs, currently `ms-helm-values` | environment values, helm, runtime config checks |
| `platform/non-platform/` | Adjacent services outside primary platforms | feeds, auto-merch, stats, reviews, stock inventory, support utilities |

Верхнеуровневые README этих зон трекаются в workspace-репозитории. Их вложенные репозитории игнорируются корневым git.

## Новые контуры вне `platform/`

| Зона | Назначение | Git tracking |
|------|------------|--------------|
| `platform-new/` | Go-based new e-commerce services and shared clients/libs: `checkout`, `intgateway`, `policyengine`, recommendation engine, `gj-go-*` packages, generated clients | полностью ignored в корневом git |
| `platform-next/` | Experimental `mini` / `mini-gj` AI-native platform and GJ rewrite workspaces | полностью ignored в корневом git |

## Расширение workspace

Все текущие платформенные зоны описаны. При расширении (новый сервис в OMS, новая платформа, новый ignored workspace) — клонировать в соответствующий каталог и обновить `CLAUDE.md` + `docs/service-index.md` + верхнеуровневый `README.md` зоны, если каталог находится в `platform/`.

## Методологии

- **GSD** (`.claude/commands/gsd/`) — артефакт-ориентированный цикл: `/gsd-new-project` → `/gsd-discuss-phase` → `/gsd-plan-phase` → `/gsd-execute-phase`. Артефакты в `.planning/`.
- **Superpowers** (плагин) — composable skills: `brainstorming`, `writing-plans`, `test-driven-development`, `systematic-debugging`, `subagent-driven-development`, `using-git-worktrees`, `verification-before-completion` и др.
- **ensi-platform/skills** (`.claude/skills/ensi-*`) — 9 доменных скиллов под PHP/Laravel/Swoole ENSI.
- **Кастом** — `.claude/skills/gj-*` + `.claude/skills/ensi-elc-operations` + `.claude/agents/*`.

## Кастомные агенты (`.claude/agents/`)

| Агент | Когда |
|-------|-------|
| `ensi-navigator` | "Где в ENSI-коде X?" — находит сервис/файл |
| `ensi-researcher` | "Почему ENSI ведёт себя так?" — read-only расследование поведения, workarounds, legacy |
| `ensi-backend-engineer` | Писать/менять PHP-код ENSI с соблюдением ensi-* скиллов |
| `mobile-navigator` | "Где в mobile-app X?" — находит экраны/компоненты/конфиги |
| `mobile-researcher` | "Почему мобила ведёт себя так?" — read-only, RN-специфика, patches, iOS/Android divergence |
| `mobile-engineer` | Писать/менять RN/TS код с соблюдением mobile-* скиллов |
| `integration-navigator` | "Где в Integration X?" — находит routes/controllers/cron-задачи |
| `integration-researcher` | "Почему checkout падает?" — read-only, ключевой для cross-system расследований |
| `integration-engineer` | Писать/менять PHP/Lumen-код с соблюдением integration-* скиллов |
| `site-navigator` | "Где в сайте X?" — находит компоненты, libs, NgRx-state, маршруты |
| `site-researcher` | "Почему UI ведёт себя так?" — read-only, NgRx state flow, SSR vs CSR, locale drift |
| `site-engineer` | Писать/менять Angular/NgRx/NestJS SSR код с соблюдением site-* скиллов |
| `oms-navigator` | "Где в OMS X?" — находит Java/Go-сервис, BPMN-процесс, per-env конфиг |
| `oms-researcher` | "Почему заказ застрял?" — read-only, BPMN flow, Camunda quirks, carrier integrations |
| `oms-java-engineer` | Писать/менять Spring Boot / Maven / Lombok-код с учётом oms-* скиллов |
| `camunda-bpm-engineer` | Дизайн BPMN-процессов, external task workers, миграции инстансов |
| `go-*` (7 агентов) | Go-сервисы и библиотеки `platform-new`: service/library/API-contract/test/review/debug/architecture |
| `gitlab-investigator` | MR/pipelines/файлы из любого GitLab-репо через `mcp__gj-buddy__gitlab_*` |
| `logs-detective` | Инциденты, трассировка через `mcp__gj-buddy__logs_*` |
| `architect` | Cross-service дизайн, ADR в `docs/architecture/` |
| `ensi-architect` | ENSI service ownership, OpenAPI/API, models, Kafka, PHP↔Go migration architecture |
| `integration-architect` | Integration Service architecture: API/cron split, checkout BFF, OMS/ENSI/OTS handoffs |
| `devops-architect` | DevOps/runtime architecture: Helm, CI/CD, env config, observability, rollout/rollback |
| `data-analytics-architect` | Data/DWH architecture: Airflow, dbt, lineage, metrics ownership, data quality |
| `corporate-architect` | Enterprise-level architecture across ecom, retail/ARM, 1C, DWH, DevOps, platform-new/next |
| `gloriaots-navigator` | "Где в Gloria OTS X?" — handlers, TK/WMS, workers, API |
| `gloriaots-researcher` | "Почему OTS ведёт себя так?" — read-only, интеграции OMS/Integration |
| `gloriaots-engineer` | Писать/менять .NET/C# код Gloria OTS с `gloriaots-stack-anatomy` |

## Ключевые инструменты

### elc — локальная разработка ENSI
```bash
elc workspace list                     # ожидаем: gj → <workspace>/platform/ensi/workspace
elc -w gj start --tag=backend          # поднять backend-сервисы
elc -w gj -c catalog-pim exec composer install
elc -w gj stop
```
См. `.claude/skills/ensi-elc-operations/SKILL.md`.

### gj-buddy MCP — внешние системы
- `mcp__gj-buddy__gitlab_*` — MR, issues, pipelines, jobs, файлы из репозиториев
- `mcp__gj-buddy__jira_*` — задачи, проекты
- `mcp__gj-buddy__confluence_*` — страницы, поиск
- `mcp__gj-buddy__logs_*` — `logs_search_message`, `logs_search_trace`, `logs_recent`
- `mcp__gj-buddy__ctx_get_page` — Context Engine

См. `.claude/skills/gj-buddy-mcp-mastery/SKILL.md`.

## Правила работы

1. **Платформа ↔ путь:** код каждой платформы строго в `platform/<system>/`. Не валить ничего в корень. При добавлении новой системы — отдельный `platform/<name>/`.
2. **Не делать git-операции на верхнем уровне** — это не git-репо, а набор клонов. Каждый репозиторий внутри `platform/*/` — свой git с собственной историей и веткой.
3. **Перед grep по platform/** — при новой сессии или code task сначала `./scripts/sync-platform-repos.sh [filter]`, затем локальный `Grep`/`Read`. GitLab MCP — для MR/CI и репо без локального клона, не для чтения исходников.
4. **Использовать domain-skills:** ENSI — `ensi-*`; OMS — `oms-*` + `camunda-bpm`; Site — `site-*`; Mobile — `mobile-*`; Integration — `integration-*`; Gloria OTS — `gloriaots-stack-anatomy`.
5. **OpenAPI-first в ENSI** — менять спеку перед PHP-кодом, клиенты регенерируются.
6. **Spring Cloud Config в OMS** — per-env values в `platform/starfish24/awg/cloud-configs/`, не в `application.yml`. Обновлять для всех envs (staging/preprod/prod).
7. **Nx module boundaries в Site** — не суппрессить ESLint error; либо лифтить shared код в `libs/shared/`, либо пересмотреть направление зависимости.
8. **Camunda topic name** — это контракт между BPMN XML и Java-handler. Case-sensitive. При смене — обновлять обе стороны + думать о running instances.
9. **Нестандартные default-branches:** Site — `release/production`; OMS — много feature-веток. Перед push проверять, куда идём.
