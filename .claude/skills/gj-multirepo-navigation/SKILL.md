---
name: gj-multirepo-navigation
description: Use when you need to find code/configs across the ~25 ENSI services in GJ-Ecommerce. Triggers on questions like "which service does X", "find all uses of Y", "search across catalog". Explains how to efficiently navigate platform/ensi/{apps,packages,devops} without scanning 5.9GB unnecessarily. Also when to query non-cloned platforms (starfish24/integration/site/mobile-app) via gj-buddy gitlab tools instead.
---

# Multi-Repo Navigation in GJ-Ecommerce

Workspace разделён по платформам — каждая в `platform/<system>/`. ENSI занимает ~5.9GB и содержит ~25 git-репозиториев. Остальные платформы не клонированы локально.

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
│   ├── starfish24/                  # НЕ клонировано → gitlab MCP
│   ├── integration/                 # НЕ клонировано → gitlab MCP
│   ├── site/                        # НЕ клонировано → gitlab MCP
│   └── mobile-app/                  # НЕ клонировано → gitlab MCP
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

### 6. **Для НЕ-ENSI платформ (starfish24, integration, site, mobile-app)** — НЕ клонируй, используй gj-buddy MCP:
```
mcp__gj-buddy__gitlab_list_repository_tree(projectId="starfish-oms/cloud/<svc>", path="...")
mcp__gj-buddy__gitlab_get_repository_file(projectId="starfish-oms/cloud/<svc>", file_path="...", ref="master")
```

GitLab-группы:
- ENSI → `greensight/gj/*` (уже клонировано в `platform/ensi/`)
- OMS → `starfish-oms/cloud/*` (заготовка `platform/starfish24/`)
- Integration → `avg-integration-service/*` (заготовка `platform/integration/`)
- Site → `site-front/gj-ng-front` (заготовка `platform/site/`)
- Mobile → `mobapp/gj-app` (заготовка `platform/mobile-app/`)

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
- Клонировать OMS/Integration/site/mobile-app локально, чтобы прочитать один файл — используй `gitlab_get_repository_file`.
- Искать в `platform/site/` локально — он пустой; иди через gj-buddy.
