---
name: integration-stack-anatomy
description: Use when working with the Integration Service. Explains the structure of platform/integration/ — main monorepo (Lumen app in www/, deploy configs in containers/), and 3 PHP libraries (logger, msq-client, health) used by the app. Trigger on anything related to platform/integration/.
---

# Integration Service Anatomy

`platform/integration/` (flat layout, 4 repos):

```
platform/integration/
├── integration/                # main monorepo — branch: dev
├── logger/                     # PHP lib — branch: main
├── msq-client/                 # PHP lib (message queue) — branch: main
└── health/                     # PHP lib — branch: main
```

## `integration/` — main monorepo

```
integration/
├── www/                        # Lumen application code (the actual PHP)
│   ├── app/
│   │   ├── Console/Commands/   # cron commands (run by integration-cron deploy)
│   │   ├── Http/Controllers/   # HTTP handlers (run by integration-api deploy)
│   │   ├── Jobs/, Services/, Models/, Listeners/, Providers/
│   │   └── (more — varies)
│   ├── bootstrap/
│   ├── config/                 # app config
│   ├── database/               # migrations, seeds, factories
│   ├── public/                 # web entrypoint (index.php → Lumen)
│   ├── resources/
│   ├── routes/                 # Lumen route files
│   ├── storage/                # logs, framework cache
│   ├── tests/                  # phpunit suites
│   ├── artisan                 # Lumen CLI
│   ├── composer.json           # PHP deps
│   ├── composer.lock
│   ├── phpstan.neon            # static analysis
│   ├── phpunit.xml
│   ├── .env.base               # base env values
│   ├── .env.example            # template for dev .env
│   ├── _ide_helper.php         # PHPStorm autocomplete (Lumen extension)
│   └── _ide_helper_models.php
├── containers/                 # Docker / runtime configs — NOT application code
│   ├── integration-api/        # HTTP deploy: Dockerfile + nginx + php-fpm + lumen.conf + supervisor + filebeat
│   └── integration-cron/       # scheduled deploy: Dockerfile + crontab-php + supervisor + filebeat
├── .gitlab-ci.yml
└── README.md
```

### Key insight: same codebase, two deploys

The same `www/` code is packaged into two Docker images, each tuned differently:

| Deploy | Container | Runtime | Triggers |
|--------|-----------|--------|----------|
| `integration-api` | `containers/integration-api/Dockerfile` | nginx + PHP-FPM + supervisor + filebeat | HTTP requests (Lumen routes) |
| `integration-cron` | `containers/integration-cron/Dockerfile` | crontab-php + supervisor + filebeat (no nginx) | scheduled times (crontab) |

So a code change can affect one or both deploys depending on what it touches.

### Crontab

`containers/integration-cron/crontab-php` schedules Lumen commands from `www/app/Console/Commands/`. Format: standard cron + PHP artisan invocation. Adding a new cron task means:
1. Implement the `Command` class in `www/app/Console/Commands/`
2. Register it (Lumen registration via Kernel or bootstrap/app.php — check current pattern)
3. Add a line to `crontab-php`
4. Rebuild & deploy `integration-cron`

## `logger/` — shared PHP logging lib

```
logger/
├── src/
└── composer.json
```

Used in `integration/www/` via composer (likely as a path/VCS repo). Wraps Monolog or similar with Gloria conventions.

## `msq-client/` — message queue client

```
msq-client/
├── src/
├── config/
├── migrations/      # DB migrations (MQ state stored in DB)
└── composer.json
```

The presence of `migrations/` is a strong hint that this client persists queue state in DB (not pure broker-based). Probably outbox-pattern or job-storage-in-DB. Inspect `migrations/` and `config/` to understand the schema before changing anything.

## `health/` — health check lib

```
health/
├── src/
└── composer.json
```

Exposes health/readiness endpoints — used by k8s probes.

## Stack reminders

- **Lumen** ≠ full Laravel. Verify a feature exists. Lumen historically lacks:
  - Session middleware by default
  - Blade views by default (in API)
  - Some facades without manual binding
- **No Swoole here** — standard PHP-FPM. Don't expect coroutines.
- **No OpenAPI tooling visible** — endpoints may not have generated specs. Verify before assuming.
- **Filebeat** ships logs from `storage/logs/` to ELK. Don't write to stdout from custom Logger calls expecting them to appear there — they go through filebeat.

## Where Integration sits in the architecture

- **Talks to mobile and site (frontend)** via REST API for checkout flow
- **Talks to ENSI** (`platform/ensi/apps/customers-api-web`, `baskets`, `offers`, `pim`) via internal HTTP calls (likely via `*-client-php` packages or direct curl/Guzzle)
- **Talks to OMS** (`starfish-oms/cloud/awg/integration-gj` — separate repo in OMS group, not cloned)
- **Talks to message broker** (RabbitMQ/Kafka?) via `msq-client`
- **Logs flow:** app → `storage/logs/` → filebeat → ELK

## Development workflow

For writing or changing Integration code, load **`pattern-development-integration.md`** alongside this skill. It covers the 7-step development cycle: understanding, planning, implementation, security checks, testing, commit, and merge request.

Related skills:
- `integration-php-conventions` — Lumen coding patterns, internal libs, structure
- `integration-deployment` — Docker, runtime config, two-deploy model
- `integration-gitlab-mr-review` — MR review checklist, architecture passes
