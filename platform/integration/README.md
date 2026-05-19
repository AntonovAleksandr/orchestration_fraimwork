# Platform: Integration

Интеграционный слой между сайтом/мобильным приложением и backend (ENSI, OMS) для чекаута. Также cron-задачи для синков и фидов.

## Что здесь должно лежать

```
integration/
├── integration/    # главный monorepo (Lumen, branch dev)
│   ├── www/        # Lumen application
│   └── containers/ # 2 deploy: integration-api (HTTP) + integration-cron (scheduler)
├── logger/         # PHP lib — логирование (обёртка над Monolog)
├── msq-client/     # PHP lib — message queue client (с DB-миграциями)
└── health/         # PHP lib — health/readiness endpoints
```

## GitLab

- Группа: https://gitlab.gloria.aaanet.ru/avg-integration-service

В группе ещё ~14 репо (new-platform Java сервисы, DevOps, helm — не клонируются по умолчанию). См. `<workspace>/docs/service-index.md` для списка нелокальных репо.

## Setup

См. `<workspace>/README.md` → раздел **Bootstrap → Integration**.

## Стек

PHP + **Lumen** (lightweight Laravel), Composer, phpstan, phpunit. Runtime: PHP-FPM + nginx + supervisor + filebeat (ELK).

**Два деплоя из одного codebase:** `integration-api` (HTTP) и `integration-cron` (cron tasks через `crontab-php`).

## Агенты

- `integration-navigator` — где живёт route / controller / cron-команда
- `integration-engineer` — Lumen/PHP код с учётом 3 integration-* скиллов
