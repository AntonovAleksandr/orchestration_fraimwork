# GJ-Ecommerce — Agentic Workspace

**Agentic workspace** для e-commerce платформы **Gloria Jeans** и смежной логистики: одна среда, в которой ИИ-агенты помогают на всём пути — от понимания ландшафта до выката и разбора инцидентов. Это не «репозиторий только для кодинга», а **операционная база знаний и ролей** поверх шести платформ (`ENSI`, `OMS`, `Integration`, `Site`, `Mobile`, `Gloria OTS`).

| Направление | Примеры задач | Чем закрываем в workspace |
|-------------|---------------|---------------------------|
| **Разработка** | эндпоинт, экран, BPMN, фикс бага | `*-engineer` агенты, доменные `skills/`, локальный запуск (elc, nx, yarn, …) |
| **Архитектура** | cross-system дизайн, ADR, trade-offs «PIM vs cache» | `architect`, `docs/architecture/`, GSD для крупных инициатив |
| **Аналитика и исследования** | «как реально работает checkout», трассировка флоу, legacy | `*-researcher`, `*-navigator`, `docs/bp/`, `docs/research/` |
| **Тестирование** | стратегия, автотесты, регресс после изменений | `ensi-tests`, `oms-go-test-*`, скиллы/агенты по стеку, CI через `gitlab-investigator` |
| **Эксплуатация** | прод-инцидент, trace, «что деплоилось» | `logs-detective`, Buddy MCP (логи, GitLab, Jira, Confluence) |

Код платформ живёт в `platform/*/` (отдельные git-клоны). **Этот репозиторий** хранит карту системы, агентов, скиллы и накопленные артефакты расследований — чтобы любая роль (разработчик, архитектор, аналитик, QA, support) начинала с одного контекста.

Проект **изначально собран под [Claude Code](https://docs.anthropic.com/en/docs/claude-code)** (GSD, slash-команды, hooks, плагины), но конфигурация агентов спроектирована **agent-agnostic**: один канонический слой в `.claude/` + `CLAUDE.md`, который без дублирования подхватывают Cursor и другие IDE с поддержкой тех же форматов.

Репозиторий трекает только **нашу интеллектуальную собственность**:
- `.claude/agents/` — 24 сабагента
- `.claude/skills/` — 25 доменных скиллов
- `.claude/rules/` — project rules (Cursor подключает через `.cursor/rules/` → симлинки)
- `docs/` и корневой `CLAUDE.md`

**Claude Code и Cursor** читают агентов и скиллы из `.claude/`; отдельно копировать в `.cursor/skills/` не нужно.

**Не трекается** (восстанавливается локально):
- `platform/` — клоны 6 платформ (каждый — свой git-репозиторий)
- GSD: `.claude/commands/`, `get-shit-done/`, `hooks/`, `settings.json` — `npx get-shit-done-cc --claude --local --profile=core`
- Опционально GSD для Cursor: `.cursor/get-shit-done/`, `.cursor/skills/gsd-*` — `--cursor --local` (см. `.claude/README.md`)
- `.claude/settings.local.json` — личные approve команды

<a id="agent-rules"></a>

## Правила для агентов (agent-agnostic)

### Идея

| Принцип | Что это значит на практике |
|---------|----------------------------|
| **Один канон** | Всё, что пишем сами, живёт в `.claude/` и `CLAUDE.md`. Не копируем агентов/скиллы/rules в `.cursor/`, не заводим второй `AGENTS.md` с тем же текстом. |
| **Имя `.claude/` — историческое** | Каталог называется так, потому что репозиторий вырос из Claude Code; содержимое формулируем **нейтрально к IDE** (платформы, сервисы, границы git, MCP), а не «только для Claude». |
| **Адаптеры снаружи** | То, что **генерирует** инсталлятор (GSD, hooks) или **требует** другой runtime (симлинки Cursor, slash-команды, `gsd-*` skills) — локально и в `.gitignore`. |
| **Claude-first bootstrap** | После clone по умолчанию ставим GSD/Superpowers под Claude Code; Cursor использует тот же канон без обязательной второй копии промптов. |

### Слои конфигурации

```
GJ-Ecommerce/
├── CLAUDE.md                 # карта workspace (нейтральный текст; читают Claude Code, Cursor, …)
├── docs/                     # service-index, bp, research, architecture, onboarding
├── .claude/                  # КАНОН агентного слоя (в git)
│   ├── agents/               # роли-сабагенты (frontmatter name + description)
│   ├── skills/               # доменные SKILL.md (триггер по description)
│   └── rules/                # короткие .mdc: границы, MCP, вызов сабагентов
├── .cursor/rules/            # только симлинки → ../.claude/rules/ (адаптер Cursor)
├── .claude/commands/ …       # GSD для Claude Code — локально, не в git
└── .cursor/skills/gsd-* …    # опциональный GSD для Cursor — локально, не в git
```

### Куда класть новое (и куда не класть)

| Задача | Куда | Не делать |
|--------|------|-----------|
| Карта платформ, «где что искать», стек, 6 `platform/*` | `CLAUDE.md` | Не раздувать rules повтором таблиц из `docs/service-index.md` |
| Короткие обязательные ограничения для **любого** агента (git root, elc, MCP, сабагенты, local-first + sync) | `.claude/rules/*.mdc` | Не писать второй раз в `.cursor/rules/` — только симлинк |
| Правила для **типа файлов** (PHP ENSI, Java OMS, Angular site) | `.claude/rules/<topic>.mdc` с `globs:` + симлинк в `.cursor/rules/` | Не смешивать с автогеном GSD |
| Новая роль «найди / напиши код» | `.claude/agents/<name>.md` | Не форкать промпт в `.cursor/` |
| Исследование «почему так работает» (без правок кода) | `docs/research/YYYY-MM-DD-<topic>.md` + `*-researcher` | Не путать с ADR — research = facts, architecture = decision |
| Архитектурное решение, ADR | `docs/architecture/YYYY-MM-DD-<topic>.md` + `architect` | Не дублировать в `docs/research/` |
| Бизнес-процессы, e2e-флоу (аналитика) | `docs/bp/` | Не копировать в `CLAUDE.md` целиком |
| Доменный how-to (OpenAPI, Camunda, Nx) | `.claude/skills/<name>/SKILL.md` | Не копировать в `.cursor/skills/` |
| Большой процесс (roadmap, фазы) | GSD → `.planning/` (опционально в git) | Не коммитить `get-shit-done/`, `commands/gsd/` |
| Только вызов инструмента IDE | `.claude/rules/workspace.mdc` (таблица Claude vs Cursor) | Не размазывать по десятку файлов |

### Как писать rules и промпты (стиль)

1. **Нейтральный язык** — «вызови сабагент `ensi-navigator`», а не «вызови Agent tool Claude». В одном месте (`workspace.mdc`) — таблица соответствия IDE (slash vs `Task`, `mcp__gj-buddy__*` vs `CallMcpTool`).
2. **Коротко и проверяемо** — один rule до ~50 строк; детали — ссылка `@docs/...` или `@CLAUDE.md`, не копипаст.
3. **Один факт — одно место** — если правило уже в `CLAUDE.md`, в `.mdc` только отсылка или исключение (glob).
4. **Frontmatter скиллов/агентов** — поле `description` должно явно говорить, *когда* активировать; от этого зависит auto-pick в Cursor и Claude.
5. **Не коммитить автоген** — всё из `npx get-shit-done-cc`, `claude plugin install`, локальные `settings.local.json`.

### Подхват в разных IDE

| Слой | Claude Code | Cursor |
|------|-------------|--------|
| Карта | `CLAUDE.md` | `CLAUDE.md` + rules из `.claude/rules/` (через `.cursor/rules/`) |
| Сабагенты | `Agent` + `subagent_type` | `Task(subagent_type=…)` — те же файлы в `.claude/agents/` |
| Скиллы GJ | `.claude/skills/` | те же `.claude/skills/` |
| GSD | `/gsd:new-project`, … | опционально `gsd-new-project` skill (`--cursor --local`) |
| Superpowers | `claude plugin install …` / `~/.claude/plugins/` | `/add-plugin superpowers` (marketplace) |

Подробнее о каталоге `.claude/` — [.claude/README.md](.claude/README.md); о формате rules — [.claude/rules/README.md](.claude/rules/README.md).

## Bootstrap после `git clone`

### 1. Установить GSD (Get Shit Done) — методология артефакт-ориентированной разработки

```bash
cd <workspace>
npx get-shit-done-cc@latest --claude --local --profile=core
```

Это создаст (не в git):
- `.claude/commands/gsd/*.md` — slash-команды `/gsd:new-project`, `/gsd:discuss-phase`, …
- `.claude/get-shit-done/` — рабочие промпты и шаблоны (~3.4 МБ)
- `.claude/hooks/*.js` — хуки на SessionStart/PreToolUse/PostToolUse
- `.claude/settings.json` — конфиг с хуками

<a id="superpowers-install"></a>

### 2. Установить Superpowers (опционально, по одному разу на IDE)

[Superpowers](https://github.com/obra/superpowers) — методология composable skills (`brainstorming`, `writing-plans`, `test-driven-development`, `systematic-debugging`, `subagent-driven-development`, `using-git-worktrees`, …). Это **не часть** канона GJ в `.claude/skills/` и **не коммитится**: ставится в каталог плагинов **вашего harness** (Claude Code, Cursor, Codex, …).

> Если пользуетесь несколькими IDE — установите Superpowers **в каждой отдельно** ([upstream](https://github.com/obra/superpowers#installation)).

#### Claude Code

В терминале из корня workspace:

```bash
claude plugin install superpowers@claude-plugins-official --scope project
```

Или в сессии Claude Code: `/plugin install superpowers@claude-plugins-official`

#### Cursor

В чате **Agent** (в этом workspace):

```text
/add-plugin superpowers
```

Или: marketplace → поиск `superpowers` → Install.  
Плагин попадает в кэш Cursor (`~/.cursor/…`), не в git-репозиторий GJ-Ecommerce.

#### Codex (CLI и приложение)

Один marketplace, разный UI:

| Среда | Действие |
|-------|----------|
| **Codex CLI** | `/plugins` → найти `superpowers` → **Install Plugin** |
| **Codex App** | боковая панель **Plugins** → секция Coding → **+** у Superpowers |

#### Другие harnesses

OpenCode, Gemini CLI, GitHub Copilot CLI, Factory Droid — см. [Installation](https://github.com/obra/superpowers#installation) в репозитории obra/superpowers.

### 3. Клонировать платформенные репозитории

Структура должна получиться:

```
<workspace>/platform/
├── ensi/                # ENSI: ~25 микросервисов (PHP/Swoole + Go)
├── starfish24/          # OMS / Starfish: 32 репо (Java Spring Boot + Go + Camunda)
├── integration/         # Integration: Lumen monorepo + 3 PHP libs
├── site/                # gj-ng-front (Angular 20 + Nx + NgRx + NestJS SSR)
├── mobile-app/          # gj-app + mobapp-api-types (React Native)
└── gloriaots/           # Gloria OTS (.NET 10, SQL Server, RabbitMQ)
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

#### Gloria OTS
```bash
mkdir -p platform/gloriaots && cd platform/gloriaots
git clone git@gitlab.gloria.aaanet.ru:gloriaots/gloriaots.git
```

### 4. (Опционально) Разрешения для удобства

`.claude/settings.json` после GSD-инсталлятора содержит дефолтные хуки, но без allowlist разрешений. Чтобы автоматически разрешить read-only MCP-инструменты (gj-buddy gitlab/jira/confluence/logs) и безопасные Bash (git status/log/diff, ls, grep, rg), добавь блок `permissions.allow` — пример из предыдущей настройки в [docs/onboarding.md](docs/onboarding.md).

## Куда смотреть дальше

| Файл | Назначение |
|------|-----------|
| [CLAUDE.md](CLAUDE.md) | Карта workspace (agent-agnostic; читается Claude Code, Cursor, …) |
| [.claude/README.md](.claude/README.md) | Что в git в `.claude/` vs что регенерировать локально |
| [.claude/rules/](.claude/rules/) | Project rules; в Cursor — симлинки из `.cursor/rules/` |
| [docs/service-index.md](docs/service-index.md) | Полный реестр сервисов всех 6 платформ + GitLab URLs |
| [docs/bp/](docs/bp/) | Бизнес-процессы и e2e-флоу (аналитика, онбординг в домен) |
| [docs/research/](docs/research/) | Findings расследований (`*-researcher`) |
| [docs/architecture/](docs/architecture/) | ADR и архитектурные решения (`architect`) |
| [docs/onboarding.md](docs/onboarding.md) | Сценарии: разработка, расследования, инциденты, GSD, MCP |

## Стек по платформам

| Платформа | Стек |
|-----------|------|
| ENSI | PHP 8.1 + Swoole + Laravel + Go, PostgreSQL+PostGIS, ES, Kafka, Redis, OpenAPI-first |
| OMS (Starfish) | Java + Spring Boot + Maven + Lombok + Camunda BPM, Go (logistics) |
| Integration | PHP + Lumen, PHP-FPM + nginx + supervisor + filebeat (ELK) |
| Site | Angular 20 + Nx + NgRx + NestJS SSR + Transloco + Storybook |
| Mobile App | React Native 0.74 + TypeScript + yarn workspaces + styled-components + YooKassa |
| Gloria OTS | .NET 10 + ASP.NET Core + SQL Server + RabbitMQ + Hangfire + React/Vite admin |

## Агенты (24)

Роли сгруппированы по **типу работы**, а не только по платформе:

| Тип | Агенты | Режим |
|-----|--------|--------|
| **Навигация** («где X в коде?») | `*-navigator` (6 платформ) | read-only |
| **Исследование** («почему так?», legacy, трассировка) | `*-researcher` (6 платформ) | read-only → `docs/research/` |
| **Реализация** | `*-engineer`, `camunda-bpm-engineer` | write code |
| **Архитектура** | `architect`, `oms-go-solution-architect` | ADR / design |
| **Качество и тесты** | `oms-go-quality-analyzer`, `oms-go-test-automation`, `oms-go-test-strategist` | review / tests |
| **Эксплуатация** | `logs-detective`, `gitlab-investigator` | MCP: логи, MR, pipelines |
| **Go / logistics** | `oms-go-*` (7) | см. `platform/starfish24/core/go/logistics/.claude/` |

Полное описание ролей и сценариев (инцидент, cross-system фича, расследование промо) — в [docs/onboarding.md](docs/onboarding.md).

## Лицензия / приватность

Внутренний репозиторий Gloria Jeans. Не публичный.
