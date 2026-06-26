# Service Index

Реестр всех сервисов и пакетов в GJ-Ecommerce, сгруппированный по платформам.

---

## Платформа ENSI (`platform/ensi/`)

### Apps (`platform/ensi/apps/`)

#### Catalog
| Сервис | Путь | Назначение | Шаблон |
|--------|------|-----------|--------|
| pim | `platform/ensi/apps/catalog/pim` | Product Information Management — товары, категории, бренды, атрибуты | swoole-8.1 |
| offers | `platform/ensi/apps/catalog/offers` | Прайсинг, скидки, акции (PHP) | swoole-8.1 |
| offers-go | `platform/ensi/apps/catalog/offers-go` | Прайсинг (Go re-implementation) | — |
| offers-ui | `platform/ensi/apps/catalog/offers-ui` | UI для offers | — |
| feed | `platform/ensi/apps/catalog/feed` | Генерация фидов (Yandex.Market, Google и т.п.) | swoole-8.1 |
| catalog-cache | `platform/ensi/apps/catalog/catalog-cache` | Кэш для публичной выдачи каталога | swoole-8.1 |

#### CMS
| Сервис | Путь | Назначение | Шаблон |
|--------|------|-----------|--------|
| cms | `platform/ensi/apps/cms/cms` | Контент-страницы, баннеры, лэндинги | swoole-8.1 |

#### Customers
| Сервис | Путь | Назначение | Шаблон |
|--------|------|-----------|--------|
| customers | `platform/ensi/apps/customers/customers` | Профили клиентов, адреса, избранное | swoole-8.1 |
| customer-auth | `platform/ensi/apps/customers/customer-auth` | Аутентификация покупателей (JWT) | swoole-8.1 |

#### Orders (часть ENSI; OMS отдельно в platform/starfish24/)
| Сервис | Путь | Назначение | Шаблон |
|--------|------|-----------|--------|
| baskets | `platform/ensi/apps/orders/baskets` | Корзина, валидация состава | swoole-8.1 |
| order-group-service | `platform/ensi/apps/orders/order-group-service` | Группировка заказов | — |

#### Units
| Сервис | Путь | Назначение | Шаблон |
|--------|------|-----------|--------|
| admin-auth | `platform/ensi/apps/units/admin-auth` | Аутентификация админов | swoole-8.1 |
| bu | `platform/ensi/apps/units/bu` | Business Units (юр.лица) | swoole-8.1 |

#### Admin GUI
| Сервис | Путь | Назначение | Шаблон |
|--------|------|-----------|--------|
| admin-gui-backend | `platform/ensi/apps/admin-gui/admin-gui-backend` | BFF для админки | swoole-8.1 |
| admin-gui-frontend | `platform/ensi/apps/admin-gui/admin-gui-frontend` | SPA админки | nodejs |

#### Customer-facing API
| Сервис | Путь | Назначение | Шаблон |
|--------|------|-----------|--------|
| customers-api-web | `platform/ensi/apps/customers-api-web` | Публичный API для сайта/мобильного | swoole-8.1 |

#### Connectors
| Сервис | Путь | Назначение | Шаблон |
|--------|------|-----------|--------|
| webapi-connector | `platform/ensi/apps/connectors/webapi-connector` | Внешние WebAPI | swoole-8.1 |
| cdn-adapter | `platform/ensi/apps/connectors/cdn-adapter` | CDN/imgproxy интеграция | swoole-8.1 |
| ensi-connector | `platform/ensi/apps/connectors/ensi-connector` | Internal ENSI connector | swoole-8.1 |
| audit | `platform/ensi/apps/connectors/audit` | Аудит-лог в Elasticsearch | swoole-8.1 |
| event-dispatcher | `platform/ensi/apps/connectors/event-dispatcher` | Kafka event dispatcher (PHP) | — |

#### Go services (`platform/ensi/apps/go/`)
| Сервис | Путь | Назначение |
|--------|------|-----------|
| event-dispatcher | `platform/ensi/apps/go/event-dispatcher` | Event dispatcher на Go |
| gj-go-logger | `platform/ensi/apps/go/gj-go-logger` | Go-библиотека логирования |

### Packages (`platform/ensi/packages/`)

Переиспользуемые PHP-клиенты, генерируются из OpenAPI-спек.

| Пакет | Для какого сервиса |
|-------|-------------------|
| `admin-auth-client-php` | units/admin-auth |
| `audit-client-php` | connectors/audit |
| `audit-collector` | (библиотека сбора аудита) |
| `baskets-client-php` | orders/baskets |
| `bu-client-php` | units/bu |
| `cms-client-php` | cms/cms |
| `customer-auth-client-php` | customers/customer-auth |
| `customers-client-php` | customers/customers |
| `feed-client-php` | catalog/feed |
| `offers-client-php` | catalog/offers |
| `pim-client-php` | catalog/pim |
| `query-builder-extension` | (общее расширение query-builder) |

### DevOps (`platform/ensi/devops/`)

| Каталог | Назначение |
|---------|-----------|
| `elc-workspace` | Канонический workspace.yaml (gitlab репо) |
| `infra` | Инфраструктурные конфиги |
| `helm-infra` | Helm для инфры (k8s) |
| `ms-helm-chart` | Базовый helm chart для микросервиса |
| `ms-helm-values` | Values для микросервисов |
| `gitlab-ci` | Общие .gitlab-ci.yml templates |
| `cicd-to-many` | CI/CD для многорепозиторных pipelines |
| `php-base-image` | Базовый PHP Docker образ |
| `k8s-manifests` | Сырые манифесты для k8s |
| `dummy` | Шаблон для нового сервиса |
| `highload-tank` | Нагрузочное тестирование (Yandex.Tank) |

### Зоны зависимостей ENSI

```
admin-gui-frontend ──→ admin-gui-backend ──→ (все *-client-php) ──→ остальные сервисы
                                                                 ↓
customers-api-web ──→ customers, customer-auth, pim-client, offers-client, baskets-client, ...
                                                                 ↓
                                                              [Kafka events]
                                                                 ↓
                                                              connectors/event-dispatcher
                                                              connectors/audit (consume → ES)
```

Все сервисы зависят от инфры: `database (postgres+postgis)`, `proxy (nginx)`, частично `elastic`, `redis`, `kafka`.

---

## Платформа Starfish / OMS (`platform/starfish24/`)

**Статус:** клонировано (32 репо — все из `starfish-oms/cloud/*` под awg/ и core/).

**GitLab группа:** `starfish-oms/cloud/*`

**Назначение:** исполнение заказов — логистика, доставка, оркестрация бизнес-процессов через Camunda BPM.

### Раскладка (зеркалит GitLab)

```
platform/starfish24/
├── awg/                # GJ-specific overlay
└── core/               # Starfish core (Java + 1 Go)
    └── go/
        └── logistics/  # единственный Go-сервис
```

### `awg/` — GJ-специфичная интеграция (4 репо)

| Репо | Путь | Branch | Назначение |
|------|------|--------|-----------|
| integration-gj | `awg/integration-gj/` | `develop` | Почти пустой (README placeholder) |
| bpmn-process | `awg/bpmn-process/` | `main` | BPMN XML — процессы для Camunda (`process/*.bpmn`) |
| cloud-configs | `awg/cloud-configs/` | `CLD-17047` | per-service per-env YAML конфиги (Spring Cloud Config) |
| gloria_ci | `awg/gloria_ci/` | `main` | Jenkinsfile пайплайны (deploy, go-services, oms-deploy-staging/prod) |

### `core/` — Starfish core

**Java orchestration:**
| Сервис | Путь | Branch | Роль |
|--------|------|--------|------|
| Order | `core/Order/` | `master` | Заказы — CRUD, lifecycle |
| Stock | `core/Stock/` | `master` | Склад / inventory |
| Delivery | `core/Delivery/` | `19783+19795` | Доставка |
| Dictionary | `core/Dictionary/` | `master` | Справочники |
| Camunda | `core/Camunda/` | `master` | Camunda BPM engine (Spring Boot) |
| BPM | `core/BPM/` | `master` | BPM-related сервис |
| camunda-worker | `core/camunda-worker/` | `master` | External task workers |

**Java domain:**
| Сервис | Путь | Роль |
|--------|------|------|
| Settings | `core/Settings/` | Настройки |
| SSO | `core/SSO/` | Single Sign-On |
| API-Gateway | `core/API-Gateway/` | API шлюз |
| Cloud-config-server | `core/Cloud-config-server/` | Spring Cloud Config server |
| Parsers | `core/Parsers/` | Парсеры внешних форматов |
| Adapter | `core/Adapter/` | Generic adapter |
| Cloud-Message-Gateway | `core/Cloud-Message-Gateway/` | Messaging gateway |
| Websocket | `core/Websocket/` | WS real-time |
| OMS-UI | `core/OMS-UI/` | Админ-UI |
| oms-alerts | `core/oms-alerts/` | Алёртинг |
| product | `core/product/` | Product info (OMS-сторона) |
| pay-service | `core/pay-service/` (branch `CLD-1840`) | Платежи |
| reports | `core/reports/` | Отчёты |
| 5post-connector | `core/5post-connector/` | 5post коннектор |

**Java shared libs (через Maven):**
| Lib | Путь | Branch |
|-----|------|--------|
| oms-objects | `core/oms-objects/` | `master` | shared DTOs |
| oms-json | `core/oms-json/` | `master` | JSON utils |
| telemetry-starter | `core/telemetry-starter/` | `master` | Spring Boot starter (telemetry) |
| cdek-api-sdk | `core/cdek-api-sdk/` | `CLD-4877` | СДЭК API SDK |
| russian-post-api-sdk | `core/russian-post-api-sdk/` | `master` | Почта России API SDK |
| local-discovery-client | `core/local-discovery-client/` | `master` | Service discovery client |

**Go services:**
| Сервис | Путь | Branch | Особенности |
|--------|------|--------|-------------|
| logistics | `core/go/logistics/` | `master` | Pricing/availability rule engine. **Имеет собственный `.claude/` с 7 агентами и подробный `CLAUDE.md`.** |

### Go agents

`core/go/logistics/` имеет собственные agent definitions в `core/go/logistics/.claude/agents/`; для работы прямо в logistics использовать их локально.

Корневые Go-агенты `.claude/agents/go-*` предназначены для non-OMS Go-контура `platform-new/`: services, shared libs, generated clients and API contracts.

### Стек

- **Java**: Spring Boot, Maven (`pom.xml`), Lombok (`lombok.config`), JKS truststore (`client.truststore.jks`), Spring Cloud Config, Spring Cloud Discovery
- **Go**: Gin, Kafka, Redis, Clean Architecture
- **Camunda BPM**: engine + external task workers + BPMN/DMN XML
- **CI/CD**: Jenkins (canonical), плюс местами `bitbucket-pipelines.yml` (legacy) и `.gitlab-ci.yml`
- **Per-env config**: централизованно через `awg/cloud-configs/<service>-gj-{preprod,prod,staging}.{yml,yaml}` (расширения непоследовательны)

### Зависимости

- **OMS ← Integration** (`platform/integration/`): orders приходят сюда от Integration через REST/Kafka
- **OMS → Carriers**: через SDK libs (`cdek-api-sdk`, `russian-post-api-sdk`) + connector-сервисы (`5post-connector`, и т.д.)
- **OMS → Pay**: через `pay-service`
- **OMS → UI**: через `Websocket` и `OMS-UI`
- **OMS ↔ ENSI**: вероятно через Integration (а не напрямую)

---

## Платформа Integration (`platform/integration/`)

**Статус:** клонировано (4 репо из 18 в группе).

**GitLab группа:** `avg-integration-service/*`

**Назначение:** интеграционный слой между сайтом/мобильным приложением и backend (ENSI, OMS) для чекаута. Также cron-задачи синков и фидов.

### Клонированные репозитории (`platform/integration/` — плоская раскладка)

| Репо | Путь | Branch | Стек | Назначение |
|------|------|--------|------|-----------|
| integration | `platform/integration/integration/` | `dev` | PHP/Lumen | Главный monorepo: `www/` (app) + `containers/` (deploy) |
| logger | `platform/integration/logger/` | `main` | PHP | Логирование (обёртка над Monolog) |
| msq-client | `platform/integration/msq-client/` | `main` | PHP | Message queue client (с DB-миграциями) |
| health | `platform/integration/health/` | `main` | PHP | Health/readiness endpoints |

### Главный `integration` monorepo

```
integration/
├── www/                 # Lumen application code
│   ├── app/             # Http/Controllers, Console/Commands (cron), Services, Models, Jobs
│   ├── config/, routes/, database/migrations/, tests/
│   ├── composer.json, phpstan.neon, phpunit.xml
│   └── artisan
└── containers/          # Docker configs — НЕ application code
    ├── integration-api/   # HTTP deploy: Dockerfile + nginx + php-fpm + supervisor + filebeat
    └── integration-cron/  # Cron deploy: Dockerfile + crontab-php + supervisor + filebeat
```

**Две деплой-цели из одного codebase:**
- `integration-api` — HTTP API (nginx + PHP-FPM)
- `integration-cron` — cron tasks (cron + supervisor), регистрируются в `containers/integration-cron/crontab-php`

### Не клонированные репозитории группы `avg-integration-service` (доступ через gitlab MCP)

| Категория | Репо |
|-----------|------|
| Placeholder | `integration-api`, `integration-cron` (актуальный код — в `integration/`) |
| New platform (Java/Maven) | `new-platform/service/stock`, `new-platform/jobs/yandex-procontext-feed`, `new-platform/service/load-test`, `new-platform/ci/ci-cd` |
| DevOps | `helm`, `helm-cron`, `base-images`, `gloria-ci`, `prod-deploy-ci`, `devops/helm-chart`, `devops/helm-values`, `devops/gitlab-ci` |

### Зависимости

- Frontend (mobile, site) ← Integration ← ENSI (`customers-api-web`, `baskets`, `offers`, `pim`) / OMS (`integration-gj` в `starfish-oms/cloud/awg/`)
- Internal PHP libs: `logger`, `msq-client`, `health` (через composer)
- Логи: `storage/logs/` → filebeat → ELK

---

## Платформа Site (`platform/site/`)

**Статус:** клонировано (1 репо).

**GitLab группа:** `site-front/*`

**Стек:** Angular 20 + Nx 21 monorepo + NgRx 20 + NestJS 11 SSR + Transloco i18n + Storybook 9 + Jest + Cypress 13 + GrowthBook. npm, Node 20.9 (Volta).

### Клонированный репозиторий

| Репо | Путь | Branch | Назначение |
|------|------|--------|-----------|
| gj-ng-front | `platform/site/gj-ng-front/` | `release/production` | Главный Nx monorepo сайта |

### Структура `gj-ng-front` (Nx monorepo)

**Apps (`apps/`)** — тонкие оболочки, по одной на локаль:

| App | Назначение |
|-----|-----------|
| `site-ru` | Российский сайт (основной прод) |
| `site-en` | Английский (feature) |
| `site-kz` | Казахский |
| `site-{ru,en,kz}-e2e` | Cypress e2e тесты для каждой локали |

**Libs (`libs/`)** — основной код:

| Lib | Назначение |
|-----|-----------|
| `analytics` | Трекинг |
| `core` | i18n, store setup, services, utils, models |
| `data-access` | API клиенты (вызовы в Integration / ENSI) |
| `modules/basket` | Feature: корзина |
| `modules/catalog` | Feature: каталог |
| `modules/checkout` | Feature: оформление заказа |
| `modules/home` | Feature: главная |
| `modules/profile` | Feature: профиль |
| `routing` | Глобальный routing |
| `server` | NestJS SSR + mock API |
| `shared` | Общие компоненты/пайпы/директивы |
| `ui` | Высокоуровневые UI-компоненты (+ Storybook) |
| `ui-kit` | UI-примитивы (+ Storybook) |

**Tools & configs:**
- `tools/generators/` — nx-генераторы (включая `generate-build-version.js`)
- `configs/` — общие конфиги (svgo и т.п.)
- `.devserver/` — локальный mock API
- `.storybook/` — глобальный storybook config
- `deprecated/` — legacy код (не модифицировать)

### Build-флейворы

`development`, `demo`, `testing`, `staging`, `production` — каждый app/server/api может собираться под любой профиль.

### Не клонированные репозитории группы `site-front`

| Категория | Репо |
|-----------|------|
| Shared lib | `greensight-lib` |
| Tools | `gj-front-external-configurator`, `mobile-dummy` |
| DevOps | `prod-deploy-ci`, `ssh-keys`, `devops/{helm-chart,helm-values,gitlab-ci}` |

Доступны через `mcp__gj-buddy__gitlab_*`.

### Зависимости

- Сайт ходит в backend через `libs/data-access/` — вероятно в `platform/integration/` (чекаут, корзина) и далее в `platform/ensi/apps/customers-api-web/` (каталог, профиль).
- i18n: ru / en / kz через Transloco.

---

## Платформа Mobile App (`platform/mobile-app/`)

**Статус:** клонировано.

**GitLab группа:** `mobapp/*`

**Стек:** React Native 0.74.1 + React 18 + TypeScript 5, yarn workspaces, styled-components 6, Firebase, Reactotron, patch-package, YooKassa SDK.

### Репозитории

| Репо | Путь | GitLab | Назначение |
|------|------|--------|-----------|
| gj-app | `platform/mobile-app/gj-app/` | `mobapp/gj-app` | Главный RN monorepo |
| mobapp-api-types | `platform/mobile-app/mobapp-api-types/` | `mobapp/mobapp-api-types` | Общие TS-типы для API-контрактов между mobile и backend |

### gj-app monorepo (yarn workspaces)

| Пакет | Путь | Назначение |
|-------|------|-----------|
| GloriaJeans (`gj`) | `platform/mobile-app/gj-app/packages/gj/` | Основное RN-приложение |
| ui-kit | `platform/mobile-app/gj-app/packages/ui-kit/` | Компоненты, ассеты, стили, типы, утилиты |
| rn-yookassa-sdk | `platform/mobile-app/gj-app/packages/rn-yookassa-sdk/` | Обёртка над YooKassa native SDK |

### Build flavors

| Flavor | Env file | API endpoint |
|--------|----------|-------------|
| development | `packages/gj/.env.development` | dev backend |
| staging | `packages/gj/.env.staging` | staging backend |
| production | `packages/gj/.env.production` | production backend |

Скрипты в корневом `package.json`: `gj:ios:{development,staging,production}`, `gj:android:{development,staging,staging-release,production}`.

### Зависимости

- Backend API: интеграция через `platform/integration/` + `platform/ensi/apps/customers-api-web/`.
- API типы: `mobapp-api-types/` (вероятно, генерируются из OpenAPI ENSI / Integration).
- Платежи: `rn-yookassa-sdk` → YooKassa native.

---

## Платформа Gloria OTS (`platform/gloriaots/`)

**Статус:** клонировано (1 репо из группы `gloriaots/`).

**GitLab группа:** `gloriaots/*`

**GitLab репо:** https://gitlab.gloria.aaanet.ru/gloriaots/gloriaots

**Домен:** логистика Gloria Jeans — **Order Transport System (OTS)**. Не ядро e-commerce, но участвует в исполнении заказов интернет-магазина (экспорт из OMS, статусы, остатки, WMS, ТК).

### Клонированный репозиторий

| Репо | Путь | Branch | Назначение |
|------|------|--------|-----------|
| gloriaots | `platform/gloriaots/gloriaots/` | `master` | Главный monorepo: Web + workers + Database |

### Смежный репозиторий группы (не клонирован по умолчанию)

| Репо | GitLab | Назначение |
|------|--------|-----------|
| wmsinserter-2.0 | `gloriaots/wmsinserter-2.0` | WMS inserter |

### Структура monorepo

```
gloriaots/
├── src/
│   ├── GloriaOTS.Web/                 # HTTP API (v1–v3 order/balance), admin API, Swagger, Hangfire, React SPA
│   ├── GloriaOTS.ApplicationCore/       # домен, DTO, interfaces, OTSModels, events
│   ├── GloriaOTS.Infrastructure/        # EF Core, ShipmentServices (ТК), WmsServices, order handlers, jobs
│   ├── GloriaOTS.EventBus/              # RabbitMQ bus
│   └── Workers/
│       ├── GloriaOTS.OrderTracking/     # фоновый трекинг, cancel, FORWARD_STATUS
│       └── GloriaOTS.WmsSync/           # WMS/TGW/1C; env Warehouse=NSK|MSK|…
├── Database/                          # SQL Server: SqlDeploy, MigrationScripts, DDL
├── Docs/                              # заметки по интеграциям ТК (CDEK, DPD, ПР, …)
├── docker-compose*.yml                  # local / stage / prod (RND, NSK, MSK)
└── GloriaOTS.sln
```

### Runtime-сервисы (деploy targets)

| Сервис | Проект | Роль |
|--------|--------|------|
| web | `GloriaOTS.Web` | API + admin SPA + Hangfire dashboard |
| order-tracking | `GloriaOTS.OrderTracking` | Статусы ТК/WMS, уведомления |
| wms-sync | `GloriaOTS.WmsSync` | Отдельный инстанс на склад |

### Стек

- **.NET 10**, ASP.NET Core, EF Core, Hangfire
- **SQL Server** (Ordering + Hangfire; колляция `Cyrillic_General_CI_AS`)
- **RabbitMQ** (internal + external event bus)
- **Redis**
- **React + Vite** (`ClientApp/`)
- **Docker Compose** + **GitLab CI** (stage; prod по площадкам RND/NSK/MSK)

### Зависимости (e-commerce)

- **OMS ← → OTS:** выгрузка заказов (`core/Adapter`, BPMN export); статусы обратно (`DELIVERING (OTS)`, BP-OMS-11)
- **Integration ↔ OTS:** `OtsClient`, `OrderExportOtsMutator`, cron stock init/delta (BP-INT-25), Kafka daemons статусов (BP-INT-30/31)
- **OTS → WMS/1C:** `GloriaOTS.WmsSync` (TGW telegram, реестры 1C)
- **OTS → carriers:** `Infrastructure/Services/ShipmentServices/*` (CDEK, DPD, Russian Post, Yandex, Own, …)

См. также `docs/bp/08-master-data-sync.md`, Confluence INT 132.65.x (OMS ↔ OTS).

### Агенты / скилл

- `gloriaots-navigator`, `gloriaots-researcher`, `gloriaots-engineer`
- `gloriaots-stack-anatomy`

### Bootstrap

```bash
mkdir -p platform/gloriaots && cd platform/gloriaots
git clone git@gitlab.gloria.aaanet.ru:gloriaots/gloriaots.git
```

---

## Дополнительные зоны `platform/`

Эти каталоги лежат рядом с основными платформами, но относятся к смежным контурам или инфраструктуре. Вложенные каталоги остаются отдельными git-репозиториями и игнорируются корневым workspace-репозиторием; верхнеуровневые `README.md` служат tracked-описаниями зон.

### 1C 8 Enterprise (`platform/1s8-enterprise/`)

| Репо | Путь | Назначение |
|------|------|------------|
| 1c-lc | `platform/1s8-enterprise/1c-lc` | 1C logistics / LC контур |
| 1c-retail | `platform/1s8-enterprise/1c-retail` | 1C retail контур, магазинные процессы |

### ARM / Retail Store Systems (`platform/arm/`)

| Зона | Примеры репозиториев | Назначение |
|------|----------------------|------------|
| Store order / POS | `gloria-jeans-cashier`, `gloria-jeans-orders`, `gloria-jeans-pos-ui`, `gloria-jeans-ui-server` | магазинное исполнение заказов, касса, POS/UI |
| Stock / receiving / catalog | `gloria-jeans-stock`, `gloria-jeans-receiving`, `gloria-jeans-catalog`, `gloria-jeans-core` | остатки, приемка, каталог, общие доменные библиотеки |
| Devices / labels / TSD | `gloria-jeans-device`, `gloria-jeans-label-service`, `gloria-jeans-label-ui`, `gloria-jeans-tsd-ui` | оборудование, печать labels, ТСД |
| Deploy / support | `devops`, `gloria-jeans-ansible`, `gloria-jeans-deployment`, `gloria-jeans-docker-images`, `gloria-jeans-export`, `gloria-jeans-onec-db-mapper` | deployment, export, 1C mapping, support tooling |

### Data Analytics (`platform/data-analytics/`)

| Репо | Путь | Назначение |
|------|------|------------|
| airflow-aero | `platform/data-analytics/airflow-aero` | Airflow DAGs / pipelines |
| airflow-gj | `platform/data-analytics/airflow-gj` | Airflow DAGs / pipelines for GJ |
| analytics-scripts | `platform/data-analytics/analytics-scripts` | analytical scripts |
| dbt | `platform/data-analytics/dbt` | dbt models / warehouse transformations |

### DevOps (`platform/devops/`)

| Репо | Путь | Назначение |
|------|------|------------|
| ms-helm-values | `platform/devops/ms-helm-values` | Helm values and environment runtime settings |

### Non-Platform / Adjacent Services (`platform/non-platform/`)

| Репо | Путь | Назначение |
|------|------|------------|
| ecom-auto-merch | `platform/non-platform/ecom-auto-merch` | auto-merchandising |
| ecom-stat-service | `platform/non-platform/ecom-stat-service` | e-commerce statistics service |
| event-dispatcher | `platform/non-platform/event-dispatcher` | event dispatching |
| feed-generator | `platform/non-platform/feed-generator` | feed generation |
| stock-inventory-service | `platform/non-platform/stock-inventory-service` | stock / inventory adjacent service |
| dwh-exporter | `platform/non-platform/dwh-exporter` | data warehouse export |
| OzonReviews | `platform/non-platform/OzonReviews` | reviews integration/tooling |
| GjReportViwer | `platform/non-platform/GjReportViwer` | report viewer |
| bots | `platform/non-platform/bots` | support/automation bots |

---

## Новые ignored workspaces вне `platform/`

### New Platform (`platform-new/`)

**Статус:** полностью ignored корневым git. Используется для новых Go-сервисов, shared clients и библиотек нового e-commerce контура.

| Репо / зона | Путь | Назначение |
|-------------|------|------------|
| checkout | `platform-new/checkout` | stateful Go checkout service / strangler over legacy Integration |
| intgateway | `platform-new/intgateway` | stateless Go BFF / integration gateway |
| policyengine | `platform-new/policyengine` | checkout policy evaluation service |
| recomendationengine | `platform-new/recomendationengine` | similar products / recommendation backend |
| recomendationenginegui | `platform-new/recomendationenginegui` | recommendation admin UI |
| clients | `platform-new/clients/*` | generated/shared Go clients for ENSI/OMS and adjacent services |
| gj-go-* | `platform-new/gj-go-httpclient`, `platform-new/gj-go-logger`, `platform-new/gj-go-migrate`, `platform-new/gj-go-money` | shared Go libraries |

### Platform Next (`platform-next/`)

**Статус:** полностью ignored корневым git. Используется для experimental `mini` / `mini-gj` AI-native platform workspaces.

| Workspace | Путь | Назначение |
|-----------|------|------------|
| mini | `platform-next/mini` | generic `mini` platform and reusable packages (`mini-ecom`, auth, redis, kafka, admin, etc.) |
| gj | `platform-next/gj` | GJ-specific implementation on top of `mini`: `mini-gj`, `mini-gj-ecom`, facade, admin, target docs |
