# GJ-Ecommerce — Agentic Workspace

Рабочее окружение для разработки e-commerce платформы **Gloria Jeans** с упором на мульти-агентную разработку в Claude Code.

Репозиторий трекает только **нашу интеллектуальную собственность**:
- 21 кастомный агент в `.claude/agents/`
- 24 скилла в `.claude/skills/`
- Документация в `docs/` и `CLAUDE.md`

**Не трекается** (восстанавливается локально):
- `platform/` — клоны 5 платформ (каждый — свой git-репозиторий)
- `.claude/commands/gsd/`, `get-shit-done/`, `hooks/`, `settings.json` — GSD installer (имеет hardcoded пути, регенерируется)
- `.claude/settings.local.json` — личные approve команды

## Bootstrap после `git clone`

### 1. Установить GSD (Get Shit Done) — методология артефакт-ориентированной разработки

```bash
cd <workspace>
npx get-shit-done-cc@latest --claude --local --profile=core
```

Это создаст:
- `.claude/commands/gsd/*.md` — 7 slash-команд (`/gsd-new-project`, `/gsd-discuss-phase`, и т.д.)
- `.claude/get-shit-done/` — рабочие промпты и шаблоны (~3.4 МБ)
- `.claude/hooks/*.js` — хуки на SessionStart/PreToolUse/PostToolUse
- `.claude/settings.json` — конфиг с хуками

### 2. Установить Superpowers plugin

```bash
claude plugin install superpowers@claude-plugins-official --scope project
```

Это активирует ~14 composable skills: `brainstorming`, `writing-plans`, `test-driven-development`, `systematic-debugging`, `subagent-driven-development`, `using-git-worktrees`, и др.

### 3. Клонировать платформенные репозитории

Структура должна получиться:

```
<workspace>/platform/
├── ensi/                # ENSI: ~25 микросервисов (PHP/Swoole + Go)
├── starfish24/          # OMS / Starfish: 32 репо (Java Spring Boot + Go + Camunda)
├── integration/         # Integration: Lumen monorepo + 3 PHP libs
├── site/                # gj-ng-front (Angular 20 + Nx + NgRx + NestJS SSR)
└── mobile-app/          # gj-app + mobapp-api-types (React Native)
```

#### ENSI (через ELC — клонирует за вас)

ENSI **не клонируется руками**. ELC читает `workspace.yaml` и клонирует все apps + packages сам.

```bash
# 1. Установить elc CLI: https://github.com/ensi-platform/elc

# 2. Склонировать elc-workspace (там workspace.yaml + templates + scripts/)
git clone git@gitlab.gloria.aaanet.ru:greensight/gj/devops/elc-workspace.git \
  platform/ensi/workspace

# 3. Зарегистрировать workspace в elc
elc workspace add gj <workspace>/platform/ensi/workspace

# 4. Клонировать все ENSI-сервисы по тегу `code` (apps + packages)
elc -w gj clone --tag=code

# (опционально) devops/ репозитории — клонировать отдельно, если нужны:
# elc-workspace, infra, helm-infra, helm-cron, gitlab-ci, ms-helm-chart, ms-helm-values,
# cicd-to-many, k8s-manifests, php-base-image, dummy, highload-tank
# из группы greensight/gj/devops/
```

Поддержка клонов в актуальном состоянии: `cd platform/ensi/workspace && ./scripts/update-git-repos`.

#### OMS / Starfish (32 репо)
```bash
mkdir -p platform/starfish24/{awg,core/go}
cd platform/starfish24/awg
for repo in integration-gj bpmn-process cloud-configs gloria_ci; do
  git clone "git@gitlab.gloria.aaanet.ru:starfish-oms/cloud/awg/$repo.git" &
done
cd ../core/go && git clone git@gitlab.gloria.aaanet.ru:starfish-oms/cloud/core/go/logistics.git &
cd ..
for repo in Order Stock Delivery Dictionary Camunda BPM camunda-worker Settings SSO API-Gateway \
  Cloud-config-server Parsers Adapter Cloud-Message-Gateway Websocket OMS-UI oms-alerts \
  product pay-service reports 5post-connector oms-objects oms-json telemetry-starter \
  cdek-api-sdk russian-post-api-sdk local-discovery-client; do
  git clone "git@gitlab.gloria.aaanet.ru:starfish-oms/cloud/core/$repo.git" &
done
wait
```

#### Integration (4 репо)
```bash
mkdir -p platform/integration && cd platform/integration
for repo in integration logger msq-client health; do
  git clone "git@gitlab.gloria.aaanet.ru:avg-integration-service/$repo.git" &
done
wait
```

#### Site
```bash
mkdir -p platform/site && cd platform/site
git clone git@gitlab.gloria.aaanet.ru:site-front/gj-ng-front.git
```

#### Mobile App
```bash
mkdir -p platform/mobile-app && cd platform/mobile-app
git clone git@gitlab.gloria.aaanet.ru:mobapp/gj-app.git
git clone git@gitlab.gloria.aaanet.ru:mobapp/mobapp-api-types.git
```

### 4. (Опционально) Разрешения для удобства

`.claude/settings.json` после GSD-инсталлятора содержит дефолтные хуки, но без allowlist разрешений. Чтобы автоматически разрешить read-only MCP-инструменты (gj-buddy gitlab/jira/confluence/logs) и безопасные Bash (git status/log/diff, ls, grep, rg), добавь блок `permissions.allow` — пример из предыдущей настройки в [docs/onboarding.md](docs/onboarding.md).

## Куда смотреть дальше

| Файл | Назначение |
|------|-----------|
| [CLAUDE.md](CLAUDE.md) | Top-level orientation (читается Claude автоматически) |
| [docs/service-index.md](docs/service-index.md) | Полный реестр сервисов всех 5 платформ + GitLab URLs |
| [docs/onboarding.md](docs/onboarding.md) | Гайд по работе: агенты, скиллы, команды, сценарии |

## Стек по платформам

| Платформа | Стек |
|-----------|------|
| ENSI | PHP 8.1 + Swoole + Laravel + Go, PostgreSQL+PostGIS, ES, Kafka, Redis, OpenAPI-first |
| OMS (Starfish) | Java + Spring Boot + Maven + Lombok + Camunda BPM, Go (logistics) |
| Integration | PHP + Lumen, PHP-FPM + nginx + supervisor + filebeat (ELK) |
| Site | Angular 20 + Nx + NgRx + NestJS SSR + Transloco + Storybook |
| Mobile App | React Native 0.74 + TypeScript + yarn workspaces + styled-components + YooKassa |

## Агенты (21)

- **Per-platform navigators** (read-only): `ensi-navigator`, `oms-navigator`, `site-navigator`, `mobile-navigator`, `integration-navigator`
- **Per-platform engineers** (write): `ensi-backend-engineer`, `oms-java-engineer`, `camunda-bpm-engineer`, `site-engineer`, `mobile-engineer`, `integration-engineer`
- **OMS Go-агенты** (7, импортированы из `logistics/.claude/`): `oms-go-expert-coder`, `oms-go-quality-analyzer`, `oms-go-test-automation`, `oms-go-test-strategist`, `oms-go-solution-architect`, `oms-go-technical-debugger`, `oms-go-knowledge-keeper`
- **Cross-cutting**: `gitlab-investigator`, `logs-detective`, `architect`

Полное описание ролей — в [docs/onboarding.md](docs/onboarding.md).

## Лицензия / приватность

Внутренний репозиторий Gloria Jeans. Не публичный.
