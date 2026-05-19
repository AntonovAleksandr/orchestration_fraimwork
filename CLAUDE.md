# GJ-Ecommerce — Agentic Workspace для Gloria Jeans

Workspace для разработки **e-commerce платформы Gloria Jeans**. Платформа состоит из 5 независимых систем — каждая в своём подкаталоге `platform/<system>/`. Все 5 настроены: **ENSI**, **Mobile App**, **Integration**, **Site**, **Starfish (OMS)**.

## Структура корня

```
GJ-Ecommerce/
├── platform/
│   ├── ensi/         — ENSI: CMS, PIM, Offers, Customers, Admin GUI, Connectors (PHP/Swoole + Go)
│   ├── starfish24/   — OMS (Starfish): 32 репо — Java Spring Boot + 1 Go (logistics) + Camunda BPM + GJ overlay (awg/)
│   ├── integration/  — Integration Service: integration (Lumen) + logger/msq-client/health (PHP libs)
│   ├── site/         — Frontend сайт: gj-ng-front (Angular 20 + Nx monorepo + NgRx + NestJS SSR)
│   └── mobile-app/   — Мобильное приложение: gj-app (RN monorepo) + mobapp-api-types
├── docs/             — service-index, onboarding, architecture (ADRs)
├── .claude/          — агенты, скиллы, команды, hooks (GSD + Superpowers + кастом)
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
- В `platform/starfish24/core/go/logistics/.claude/` — готовый набор из 7 высококачественных Go-агентов (от команды logistics)
- В корневом `.claude/agents/` те же 7 агентов скопированы с префиксом `oms-go-*`
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

## Заготовок не осталось

Все 5 платформ настроены. При расширении (например, новый сервис в OMS или новая платформа) — клонировать в соответствующий `platform/<name>/` и обновить `CLAUDE.md` + `docs/service-index.md`.

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
| `oms-go-*` (7 агентов) | Go-специфика OMS — `expert-coder`, `quality-analyzer`, `test-automation`, `test-strategist`, `solution-architect`, `technical-debugger`, `knowledge-keeper` (адаптированы с logistics, имеют logistics-контекст) |
| `gitlab-investigator` | MR/pipelines/файлы из любого GitLab-репо через `mcp__gj-buddy__gitlab_*` |
| `logs-detective` | Инциденты, трассировка через `mcp__gj-buddy__logs_*` |
| `architect` | Cross-service дизайн, ADR в `docs/architecture/` |

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
3. **Перед grep по 6+ GB** — спроси gj-buddy (`gitlab_list_repository_tree`, `gitlab_get_repository_file`). Локально grep'ить можно с exclude `vendor/`, `node_modules/`, `target/`, `dist/`.
4. **Использовать domain-skills:** работая с ENSI — `ensi-*` скиллы; с OMS — `oms-*` + `camunda-bpm`; с Site — `site-*`; с Mobile — `mobile-*`; с Integration — `integration-*`.
5. **OpenAPI-first в ENSI** — менять спеку перед PHP-кодом, клиенты регенерируются.
6. **Spring Cloud Config в OMS** — per-env values в `platform/starfish24/awg/cloud-configs/`, не в `application.yml`. Обновлять для всех envs (staging/preprod/prod).
7. **Nx module boundaries в Site** — не суппрессить ESLint error; либо лифтить shared код в `libs/shared/`, либо пересмотреть направление зависимости.
8. **Camunda topic name** — это контракт между BPMN XML и Java-handler. Case-sensitive. При смене — обновлять обе стороны + думать о running instances.
9. **Нестандартные default-branches:** Site — `release/production`; OMS — много feature-веток. Перед push проверять, куда идём.
