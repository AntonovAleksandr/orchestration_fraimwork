---
name: SKILL
version: 1.0.0
layer: gj-multirepo-navigation
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# Multi-Repo Navigation in GJ-Ecommerce

Workspace разделён по платформам — каждая в `platform/<system>/`. **Все 6 платформ клонированы локально** (~63 git-репозитория). ENSI — ~5.9GB, ~25 сервисов.

**Перед чтением/правкой кода:** `./scripts/sync-platform-repos.sh [filter]` — pull свежих изменений (см. `.claude/rules/local-code-first.mdc`).

## Иерархия

```
GJ-Ecommerce/
├── platform/
│   ├── ensi/                        # клонировано, ~5.9GB
│   │   ├── apps/
│   │   │   ├── admin-gui/           (admin-gui-backend, admin-gui-frontend)
│   │   │   ├── catalog/             (pim, offers, offers-go, offers-ui, feed, catalog-cache)
│   │   │   ├── cms/                 (cms)
│   │   │   ├── connectors/          (audit, cdn-adapter, ensi-connector, webapi-connector, event-dispatcher)
│   │   │   ├── customers/           (customers, customer-auth)
│   │   │   ├── customers-api-web/
│   │   │   ├── go/                  (event-dispatcher, gj-go-logger)
│   │   │   ├── orders/              (baskets, order-group-service)
│   │   │   └── units/               (admin-auth, bu)
│   │   ├── packages/                (*-client-php, audit-collector, query-builder-extension)
│   │   ├── workspace/               (elc workspace.yaml)
│   │   ├── devops/                  (elc-workspace, helm-*, gitlab-ci, ms-helm-chart, ...)
│   │   └── internal/
│   ├── starfish24/                  # клонировано (~32 репо: awg/ + core/)
│   ├── integration/                 # клонировано (integration + logger, msq-client, health)
│   ├── site/                        # клонировано (gj-ng-front)
│   ├── mobile-app/                  # клонировано (gj-app + mobapp-api-types)
│   └── gloriaots/                   # клонировано (gloriaots monorepo)
```

## Стратегии поиска (от дешёвой к дорогой)

### 1. **Точечный grep — когда сервис известен**
```bash
grep -rn "validat" platform/ensi/apps/orders/baskets/app/Domain/
```

### 2. **Поиск по domain-моделям**
```bash
grep -rln "class Offer extends Model" platform/ensi/apps/*/*/app/Domain/
```

### 3. **Поиск API-эндпоинта**
```bash
grep -rn "'baskets/{id}/checkout'" platform/ensi/apps/*/*/routes/ platform/ensi/apps/*/*/openapi/
```

### 4. **Kafka топик**
```bash
grep -rn "'topic_name'" platform/ensi/apps/*/*/config/ platform/ensi/apps/*/*/app/Listeners/
```

### 5. **Когда ownership неизвестен — широкий поиск с exclude**
```bash
grep -rln --include="*.php" --exclude-dir=vendor --exclude-dir=node_modules \
  "RocketDataFeed" platform/ensi/apps/ platform/ensi/packages/
```

Или быстрее через `rg` (ripgrep) — он уважает `.gitignore` по умолчанию:
```bash
rg "RocketDataFeed" platform/ensi/apps/ platform/ensi/packages/
```

### 6. **GitLab MCP — только если локального клона нет** (или MR/CI/логи):
```
mcp__gj-buddy__gitlab_list_merge_requests(projectId="...", state="opened")
mcp__gj-buddy__gitlab_get_repository_file(...)  # fallback when platform/ path missing
```

GitLab-группы:
- ENSI → `greensight/gj/*` (уже клонировано в `platform/ensi/`)
- OMS → `starfish-oms/cloud/*` (заготовка `platform/starfish24/`)
- Integration → `avg-integration-service/*` (заготовка `platform/integration/`)
- Site → `site-front/gj-ng-front` (заготовка `platform/site/`)
- Mobile → `mobapp/*` (`platform/mobile-app/`)
- Gloria OTS → `gloriaots/gloriaots` (`platform/gloriaots/gloriaots/`)

## Обязательные exclude при grep по platform/ensi/

- `--exclude-dir=vendor` (composer)
- `--exclude-dir=node_modules`
- `--exclude-dir=.git`
- `--exclude-dir=storage` (Laravel cache/logs)

## Полезные glob-паттерны

| Что найти | Glob |
|-----------|------|
| Все PHP-сервисы | `platform/ensi/apps/*/*/composer.json` |
| Все OpenAPI-спеки | `platform/ensi/apps/*/*/openapi/*.yaml` |
| Все Laravel-роуты | `platform/ensi/apps/*/*/routes/*.php` |
| Все миграции | `platform/ensi/apps/*/*/database/migrations/*.php` |
| Все клиенты | `platform/ensi/packages/*-client-php/` |
| Все helm-values | `platform/ensi/devops/ms-helm-values/**/values*.yaml` |

## Анти-паттерны

- `find <workspace> -name "*.php"` — сканирует node_modules/vendor/.git → минуты.
- `grep -r "x" .` от корня — то же самое.
- **`gitlab_get_repository_file` для кода, который уже есть в `platform/`** — читай локально после sync.
- Начинать code task без `./scripts/sync-platform-repos.sh` — локальный код может быть устаревшим.
- GitLab MCP для «где определён класс X» в клонированном сервисе — используй `Grep`/`SemanticSearch` локально.
