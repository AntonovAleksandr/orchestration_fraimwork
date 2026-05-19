# Onboarding — Как работать в GJ-Ecommerce

Краткий гайд для Claude Code и **Cursor**. Каноническая конфигурация агентов — в `.claude/`; полный контекст — в `CLAUDE.md`.

## Bootstrap после клонирования репозитория

Этот репо трекает только нашу интеллектуальную собственность (агенты, скиллы, docs). GSD-инсталлятор и Superpowers-плагин восстанавливаются локально — там абсолютные пути, специфичные для машины.

```bash
# 1. Клонировать рабочие платформы (каждая в свой platform/<system>/)
#    См. README.md → раздел Bootstrap + docs/service-index.md (GitLab URLs).
#    ENSI клонируется через elc (не руками):
#      git clone git@gitlab.gloria.aaanet.ru:greensight/gj/devops/elc-workspace.git \
#        platform/ensi/workspace
#      elc workspace add gj <workspace>/platform/ensi/workspace
#      elc -w gj clone --tag=code     # клонирует apps + packages из workspace.yaml
#    Остальные платформы — обычный git clone (см. README.md → Bootstrap)

# 2. Установить GSD для Claude Code (не коммитится)
cd <workspace>
npx get-shit-done-cc@latest --claude --local --profile=core

# 2b. (опционально) GSD в Cursor — skills gsd-* в .cursor/, не в git
# npx get-shit-done-cc@latest --cursor --local --profile=core

# 3. Superpowers (опционально) — ставится ОТДЕЛЬНО в каждой IDE, не в git:
#    Claude Code:
#      claude plugin install superpowers@claude-plugins-official --scope project
#    Cursor Agent chat:
#      /add-plugin superpowers
#    Codex CLI: /plugins → superpowers → Install Plugin
#    Codex App: Plugins → Superpowers → +
#    Прочее: https://github.com/obra/superpowers#installation

# 4. (опционально) Зарегистрировать elc workspace для ENSI
elc workspace add gj <workspace>/platform/ensi/workspace
```

После этого: агенты и скиллы GJ из `.claude/` (в git); GSD — `/gsd:*` в Claude Code или `gsd-*` skills в Cursor (локально).

## Карта проекта (TL;DR)

```
GJ-Ecommerce/
├── platform/
│   ├── ensi/         — ENSI: ~25 микросервисов (PHP/Swoole + Go)        — 5.9 GB
│   ├── starfish24/   — OMS (Starfish): 32 репо (Java + 1 Go + Camunda) — 455 MB
│   ├── site/         — gj-ng-front (Angular 20 + Nx + NgRx + NestJS SSR) — 129 MB
│   ├── mobile-app/   — gj-app + mobapp-api-types (React Native)         — 67 MB
│   └── integration/  — integration + 3 libs (PHP/Lumen)                 — 49 MB
├── docs/
│   ├── service-index.md  — полный реестр сервисов всех платформ
│   ├── onboarding.md     — этот файл
│   └── architecture/     — ADR-документы (создаются `architect`-агентом)
├── .claude/              — канон: agents, skills, rules (в git)
│   ├── agents/           — 21 сабагент (Cursor: Task)
│   ├── skills/           — 24 скилла GJ
│   ├── rules/            — project rules (.mdc)
│   └── commands/gsd/     — GSD slash-команды (локально, не в git)
├── .cursor/rules/        — симлинки → .claude/rules/ (для Cursor UI)
└── CLAUDE.md             — top-level orientation, автозагрузка
```

## Агенты (21)

Вызываются через `Agent` tool с `subagent_type=<name>`.

### Per-platform navigators (read-only, "где X?")
| Агент | Платформа |
|-------|-----------|
| `ensi-navigator` | ENSI — `platform/ensi/apps/`, `packages/` |
| `oms-navigator` | OMS — `platform/starfish24/{awg,core,core/go}/` |
| `site-navigator` | Site — Nx-monorepo `platform/site/gj-ng-front/` |
| `mobile-navigator` | Mobile — RN-monorepo `platform/mobile-app/gj-app/` |
| `integration-navigator` | Integration — `platform/integration/integration/www/` |

### Per-platform researchers (read-only, "почему так работает?")
Расследуют поведение, ищут workarounds и legacy-костыли, трассируют данные через систему. **НЕ пишут код** — на выходе findings-документ. Делегируют друг другу для cross-system флоу.

| Агент | Специфика расследования |
|-------|------------------------|
| `ensi-researcher` | OpenAPI vs runtime drift, multi-app patterns, Kafka topics, legacy migration (PHP↔Go) |
| `oms-researcher` | BPMN flow / Camunda versioning, carrier integrations, multi-tenant, JKS truststore, per-env config drift |
| `integration-researcher` | Checkout BFF, Lumen vs Laravel gaps, outbox via msq-client, two-deploy diffs (api vs cron) |
| `site-researcher` | NgRx state flow, SSR vs CSR, locale drift (ru/en/kz), `deprecated/`, GrowthBook flags |
| `mobile-researcher` | iOS/Android divergence, patch-package patches, env-flavors, YooKassa native bridge |

Findings сохраняются в `docs/research/<YYYY-MM-DD>-<topic>.md` (см. `docs/research/README.md`).

### Per-platform engineers (write — пишут/меняют код)
| Агент | Стек |
|-------|------|
| `ensi-backend-engineer` | PHP 8.1 + Swoole + Laravel + OpenAPI |
| `oms-java-engineer` | Java + Spring Boot + Maven + Lombok |
| `camunda-bpm-engineer` | BPMN + external task workers + DMN |
| `site-engineer` | Angular 20 + NgRx + NestJS SSR + Nx |
| `mobile-engineer` | React Native + TS + styled-components |
| `integration-engineer` | PHP + Lumen + composer |

### Go-агенты для OMS (импортированы из `logistics/.claude/`, имеют logistics-контекст)
- `oms-go-expert-coder` — concurrency, perf, idioms
- `oms-go-quality-analyzer` — review
- `oms-go-test-automation` — test code
- `oms-go-test-strategist` — test strategy
- `oms-go-solution-architect` — design (planning mode)
- `oms-go-technical-debugger` — debugging
- `oms-go-knowledge-keeper` — knowledge management

⚠️ При работе прямо в `logistics` — лучше использовать оригиналы из `platform/starfish24/core/go/logistics/.claude/agents/`.

### Cross-cutting (работают со всеми платформами)
| Агент | Использовать когда |
|-------|--------------------|
| `gitlab-investigator` | MR/pipelines/jobs/файлы из GitLab через `mcp__gj-buddy__gitlab_*` |
| `logs-detective` | Инциденты, trace, ошибки через `mcp__gj-buddy__logs_*` |
| `architect` | Cross-system дизайн, ADR в `docs/architecture/<YYYY-MM-DD>-<topic>.md` |

## Скиллы (24) — авто-активируются по описанию

### ENSI (9, из ensi-platform/skills + кастом)
`ensi-api-design`, `ensi-code-style`, `ensi-models`, `ensi-openapi`, `ensi-meta`, `ensi-query-builder`, `ensi-kafka`, `ensi-tests`, `ensi-elc-operations`, плюс `ansible-component`

### OMS (3)
`oms-stack-anatomy`, `oms-java-conventions`, `camunda-bpm`

### Site (3)
`site-stack-anatomy`, `site-nx-commands`, `site-angular-conventions`

### Mobile (3)
`mobile-stack-anatomy`, `mobile-build-commands`, `mobile-rn-conventions`

### Integration (3)
`integration-stack-anatomy`, `integration-deployment`, `integration-php-conventions`

### Cross-cutting (2)
`gj-multirepo-navigation` — поиск по 6+ GB кода
`gj-buddy-mcp-mastery` — когда какой MCP-инструмент

### Superpowers (плагин, ~14; не в git)

Устанавливается **отдельно в каждой IDE** — см. [README → Superpowers](../README.md#superpowers-install). Не путать со скиллами GJ в `.claude/skills/`.

`brainstorming`, `writing-plans`, `executing-plans`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`, `subagent-driven-development`, `dispatching-parallel-agents`, `using-git-worktrees`, `requesting-code-review`, `receiving-code-review`, `writing-skills`, и др.

## Команды GSD (`.claude/commands/gsd/`)

Для крупных кусков работы:
- `/gsd-new-project` — research → requirements → roadmap (создаст `.planning/`)
- `/gsd-discuss-phase` → `/gsd-plan-phase` → `/gsd-execute-phase`

Для одиночных задач (фикс бага, мелкое изменение) — GSD необязателен.

## Типичные сценарии

### "Добавить эндпоинт в каталог ENSI"
1. `Agent → ensi-navigator` — найди сервис (catalog/pim?) и OpenAPI spec
2. Скилл `ensi-openapi` — обнови YAML в `platform/ensi/apps/catalog/pim/openapi/`
3. `Agent → ensi-backend-engineer` — реализует Action + Pest тесты (`ensi-tests`, `ensi-api-design`, `ensi-code-style`)
4. `elc -w gj -c catalog-pim exec composer test`

### "Добавить экран в мобильном приложении"
1. `Agent → mobile-navigator` — найди feature-модуль / ui-kit
2. `Agent → mobile-engineer` — RN-компонент + styled-components, типы из `mobapp-api-types`
3. `yarn lint && yarn gj:ts && yarn gj:ios:development` для проверки

### "Изменить BPMN-процесс в OMS"
1. `Agent → oms-navigator` — найди BPMN в `platform/starfish24/awg/bpmn-process/process/*.bpmn` + связанный worker в `core/camunda-worker/`
2. `Agent → camunda-bpm-engineer` — изменения + migration plan для running instances
3. `Agent → oms-java-engineer` — синхронизировать handler если topic изменился

### "Добавить feature в сайт (Angular)"
1. `Agent → site-navigator` — какой `libs/modules/<feature>/` нужен или новый
2. `Agent → site-engineer` — standalone-компонент + NgRx slice + Transloco i18n + SSR-safe
3. `nx test <project>`, `nx build site-ru --configuration production`

### "Прод-инцидент: 500 на checkout"
1. `Agent → logs-detective` — найди trace_id, проследи через Integration → ENSI/OMS
2. `Agent → gitlab-investigator` — recent pipelines/deploys affected services
3. Соответствующий `*-engineer` агент — фикс
4. MR вручную в нужный репозиторий

### "Cross-system фича (например, новый способ оплаты)"
1. `Agent → architect` — обзор: какие сервисы вовлечены (probably `Integration` + ENSI `customers-api-web` + OMS `pay-service` + Site `libs/modules/checkout` + Mobile `packages/gj/src/...`)
2. ADR в `docs/architecture/YYYY-MM-DD-<topic>.md`
3. Декомпозиция, делегирование `*-engineer` агентам по платформам

### "Расследование cross-system бага"
Пример: "промо-код не применяется на чекауте"
1. `Agent → integration-researcher` — пройди flow от Integration: где валидируется промо, какие API вызываются
2. Integration делегирует → `ensi-researcher` (offers / promo logic в ENSI catalog/offers)
3. ENSI находит legacy костыль или drift → возвращает findings
4. integration-researcher агрегирует, сохраняет `docs/research/YYYY-MM-DD-promo-not-applied.md`
5. Затем — `ensi-backend-engineer` (или architect если нужно решение) делает фикс на основе findings

## Локальная разработка — по платформам

### ENSI (elc)
```bash
elc -w gj start --tag=backend
elc -w gj -c catalog-pim exec composer install
elc -w gj -c catalog-pim exec composer test
elc -w gj stop
```
См. `.claude/skills/ensi-elc-operations/SKILL.md`.

### Mobile (yarn workspaces)
```bash
cd platform/mobile-app/gj-app
yarn                           # установить
yarn yookassa:prepare          # bootstrap YooKassa
yarn gj:pod-install            # iOS pods
yarn gj:start                  # Metro
yarn gj:ios:development        # запустить iOS
yarn lint && yarn gj:ts
```
См. `.claude/skills/mobile-build-commands/SKILL.md`.

### Site (Nx + npm)
```bash
cd platform/site/gj-ng-front
npm install                    # Volta → Node 20.9
npm run start:mock             # site-ru + mock API
npm run dev                    # SSR + mock
npm run test:all
nx build site-ru --configuration production
nx dep-graph                   # граф зависимостей
```
См. `.claude/skills/site-nx-commands/SKILL.md`.

### Integration (PHP внутри Docker)
```bash
cd platform/integration/integration
# composer/phpunit/phpstan — внутри Docker-контейнера integration-api
docker compose up -d integration-api
docker compose exec integration-api composer install
docker compose exec integration-api vendor/bin/phpunit
```
См. `.claude/skills/integration-deployment/SKILL.md`.

### OMS (Java + Maven)
```bash
cd platform/starfish24/core/<Service>
mvn clean verify               # build + test
mvn -pl <module> test          # multi-module: один модуль
# docker-compose.yml на репо есть для локальной инфры
```

### OMS / Go (logistics)
```bash
cd platform/starfish24/core/go/logistics
make build-local               # = go build -o logistics-service cmd/server/main.go
make test                      # = go test ./...
make run-local                 # docker-compose из deployments/docker/
```
В этом каталоге есть собственный `CLAUDE.md` с богатой спецификой.

## Разрешения / hooks

- **`settings.json`** — авто-allow для read-only MCP-инструментов gj-buddy и безопасных Bash (git status/log/diff, ls, grep, rg, find, elc workspace list/show)
- **`settings.local.json`** — личные approve-всё (не комитить, gitignored локально)
- **GSD hooks** — SessionStart, PreToolUse, PostToolUse: следят за context bloat, prompt injection, read-before-edit

## gj-buddy MCP — внешние системы

Использовать вместо ручного `gh`/`curl`/`kubectl`:

- `mcp__gj-buddy__gitlab_*` — MR, issues, pipelines, jobs, файлы (для нелокальных репо или конкретных файлов)
- `mcp__gj-buddy__jira_*` — задачи, проекты
- `mcp__gj-buddy__confluence_*` — страницы, поиск
- `mcp__gj-buddy__logs_*` — `logs_search_trace` (распределённый trace), `logs_search_message`, `logs_recent`
- `mcp__gj-buddy__ctx_get_page` — Gloria Context Engine

См. `.claude/skills/gj-buddy-mcp-mastery/SKILL.md`.

## Что НЕ делать

- ❌ git-операции на верхнем уровне `GJ-Ecommerce/` — это набор клонов, не git-репо
- ❌ `composer test` / `php artisan` на host для ENSI — нужен `elc -c <svc> exec`
- ❌ `mvn clean install` без проверки multi-module (см. `pom.xml` → `<modules>`)
- ❌ `npm install` в Mobile (yarn-only) или Site без Volta-pinned Node
- ❌ Ручной `grep -r` без exclude `vendor/`, `node_modules/`, `target/`, `dist/`, `.git/`
- ❌ Изменять BPMN в `awg/bpmn-process/` без думы о running instances (нужен migration plan)
- ❌ Редактировать `client.truststore.jks` напрямую — использовать `keytool`
- ❌ Добавлять config-ключ в OMS-сервис без обновления `awg/cloud-configs/<svc>-gj-<env>.{yml,yaml}` для ВСЕХ envs
- ❌ `elc destroy` без явного подтверждения (удаляет volumes)
- ❌ Push в `release/production` Site без проверки — это default-branch, но не для активной разработки

## Cross-platform data flow

```
                       ┌──────────────┐  ┌──────────────┐
                       │  mobile-app  │  │     site     │
                       │  (RN/Yandex) │  │  (Angular)   │
                       └──────┬───────┘  └──────┬───────┘
                              │                 │
                              ▼                 ▼
                       ┌────────────────────────────────┐
                       │       Integration (Lumen)      │
                       │   integration-api / -cron      │
                       └──────┬─────────────────┬───────┘
                              │                 │
                  ┌───────────┘                 └───────────┐
                  ▼                                         ▼
        ┌────────────────────┐                  ┌────────────────────┐
        │     ENSI (PHP)     │                  │   OMS (Starfish)   │
        │ catalog, customers,│ ◀──── Kafka ────▶│ Order, Camunda,    │
        │ orders/baskets, …  │                  │ Delivery, …        │
        │ (~25 services)     │                  │ (Java + 1 Go)      │
        └────────────────────┘                  └─────────┬──────────┘
                                                          │
                                                          ▼
                                              ┌────────────────────┐
                                              │ Carriers, payments │
                                              │ (СДЭК, Поч.России, │
                                              │  5post, YooKassa)  │
                                              └────────────────────┘
```

Подробный реестр сервисов по каждой платформе — `docs/service-index.md`.

## Расширение

- **Новый сервис в существующую платформу:** клонировать в правильное место (`platform/ensi/apps/<group>/`, `platform/starfish24/core/`, и т.д.), обновить `docs/service-index.md`. Если стек новый — добавить агента/скилл.
- **Новая платформа:** создать `platform/<name>/`, обновить `CLAUDE.md` (новая секция) + `docs/service-index.md` + 2-3 агента + 2-3 скилла + memory entry.
- **Полный GSD** (66 skills вместо 7): `cd <workspace> && npx get-shit-done-cc@latest --claude --local --profile=full`
- **Новый агент / скилл:** файл с frontmatter `---\nname: ...\ndescription: ...\n---`. Описание `description` должно быть детальным — по нему Claude решает когда активировать.
