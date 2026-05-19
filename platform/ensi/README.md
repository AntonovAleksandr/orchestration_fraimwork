# Platform: ENSI

E-commerce ядро Gloria Jeans на базе **Greensight ENSI** (https://ensi.tech).

## Что здесь должно лежать

```
ensi/
├── apps/        ~25 микросервисов (PHP/Swoole + Go)
├── packages/    переиспользуемые PHP-клиенты
├── workspace/   elc workspace.yaml (контейнерная оркестрация)
├── devops/      helm charts, gitlab-ci, base-image, ms-helm-chart
└── internal/    внутренние generated клиенты
```

## GitLab

- Группа: https://gitlab.gloria.aaanet.ru/greensight/gj
- ELC tool: https://github.com/ensi-platform/elc
- Skills для агентов: https://github.com/ensi-platform/skills

## Setup

ENSI клонируется **не руками** — это делает `elc` через `workspace.yaml`.

```bash
# 1. Установить elc CLI: https://github.com/ensi-platform/elc

# 2. Клонировать сам elc-workspace (там workspace.yaml + шаблоны контейнеров + scripts/)
git clone git@gitlab.gloria.aaanet.ru:greensight/gj/devops/elc-workspace.git \
  <workspace>/platform/ensi/workspace

# 3. Зарегистрировать workspace в elc (имя `gj` — конвенция проекта)
elc workspace add gj <workspace>/platform/ensi/workspace

# 4. Клонировать все ENSI-сервисы (apps + packages), описанные в workspace.yaml
elc -w gj clone --tag=code
# → apps/ и packages/ создадутся автоматически рядом с workspace/

# 5. (опционально) Обновить все клоны позже
cd <workspace>/platform/ensi/workspace && ./scripts/update-git-repos
```

После этого можно запускать сервисы:
```bash
elc -w gj start --tag=backend            # поднять backend-сервисы
elc -w gj -c catalog-pim exec composer install
```

**`devops/` и `internal/`** не входят в `workspace.yaml` — клонировать отдельно из `greensight/gj/devops/*` и `greensight/gj/internal/*` если потребуется (см. `<workspace>/docs/service-index.md`).

Полный реестр сервисов: `<workspace>/docs/service-index.md` → раздел "Платформа ENSI".

## Стек

PHP 8.1 + Swoole (большинство) / FPM 8.1, Laravel, PostgreSQL+PostGIS, Elasticsearch 7.9.2, Kafka, Redis 6. **OpenAPI-first** дизайн API.

## Агенты

- `ensi-navigator` (read-only) — где живёт X
- `ensi-backend-engineer` (write) — пишет PHP-код с учётом 9 ensi-* скиллов
