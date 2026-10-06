# Система скилов для многоагентной архитектуры

**Версия:** 1.0  
**Дата обновления:** 2026-10-06  
**Автор:** Claude Haiku 4.5 + Координатор

## Оглавление

1. [Обзор архитектуры](#обзор-архитектуры)
2. [Роли и скилы](#роли-и-скилы)
3. [Использование по фазам](#использование-по-фазам)
4. [Пересечение скилов](#пересечение-скилов)
5. [Инструкции по добавлению новых скилов](#инструкции-по-добавлению-новых-скилов)

---

## Обзор архитектуры

Система состоит из **7 фаз** выполнения задачи и **6 ролей** агентов:

```
ФАЗЫ ВЫПОЛНЕНИЯ:
  Phase 0: Инициализация (Координатор)
  Phase 1: Research — исследование (5 исследователей параллельно)
  Phase 2: Analysis — анализ (Аналитик)
  Phase 3: Development — разработка (Разработчик)
  Phase 4-5: Review — ревью (2 ревьювера параллельно)
  Phase 6-7: Merge + Metrics (Координатор)

РОЛИ АГЕНТОВ:
  • Координатор (PM) — управление процессом, метрики
  • Исследователь (5 типов) — сбор фактов
  • Аналитик (1) — синтез требований
  • Разработчик (1+) — написание кода
  • Ревьювер (2) — проверка (специализированные)
  • Автоматизация (CI) — синтаксис, простые баги
```

### Контекст агентов

| Роль | Контекст | Время | Скилы |
|------|----------|-------|-------|
| **Coord** | 10K | всё время | coord-* + shared-* |
| **Researcher** (каждый) | 8-15K | 5 мин | research-* + shared-* |
| **Analyst** | 8K | 5 мин | analyze-* + shared-* |
| **Developer** | 20K | 30-60 мин | develop-* + shared-* |
| **Reviewer-1** | 15K | 20 мин | review-business-* + shared-* |
| **Reviewer-2** | 15K | 20 мин | review-security-* + shared-* |

---

## Роли и скилы

### 🔍 [RESEARCH] Исследовательские скилы

**Назначение:** сбор фактов из разных источников, read-only, параллельное выполнение.

#### `research-confluence.md`
- **Агент:** Confluence-researcher
- **Входит:** Confluence links, Jira ticket ID
- **Выходит:** ТЗ, AC, история решений, известные проблемы
- **Время:** 5-8 мин
- **Скилы:** confluence_*, jira_* (read only)
- **Правила:** 
  - Не интерпретировать, только цитировать
  - Искать противоречия между Confluence и Jira
  - Отмечать [BLOCKER] если ТЗ неполное
- **Выход:** Markdown с фактами и ссылками

#### `research-code-ensi.md`
- **Агент:** Code-researcher (ENSI)
- **Входит:** service name (e.g. "catalog-pim")
- **Выходит:** структура, OpenAPI, текущая реализация, тесты
- **Время:** 10-15 мин
- **Скилы:** codegraph_explore, ensi-stack-anatomy, ensi-models, Read, Grep
- **Правила:**
  - Только ENSI код (platform/ensi/apps/*)
  - Не трогать Integration, OMS, Site
  - Обращать внимание на OpenAPI спеку
  - Выявлять unused код, deprecated параметры
- **Выход:** "Current implementation in ENSI: [сервис]"

#### `research-code-oms.md`
- **Агент:** Code-researcher (OMS)
- **Входит:** entity name или процесс
- **Выходит:** Java код, BPMN процесс, handlers, конфиги
- **Время:** 10-15 мин
- **Скилы:** codegraph_explore, oms-stack-anatomy, oms-java-conventions, camunda-bpm, Read, Grep
- **Правила:**
  - Только OMS код (platform/starfish24/)
  - BPMN процессы в awg/bpmn-process
  - Per-env конфиги в awg/cloud-configs
  - Не менять Java файлы, только читать
- **Выход:** "OMS current state: [сущность]"

#### `research-code-integration.md`
- **Агент:** Code-researcher (Integration)
- **Входит:** endpoint или сценарий
- **Выходит:** маршруты, контроллеры, интеграция с ENSI/OMS, Kafka
- **Время:** 8-12 мин
- **Скилы:** codegraph_explore, integration-stack-anatomy, integration-php-conventions, Read, Grep
- **Правила:**
  - Только Integration код (platform/integration/)
  - Смотреть контракты с ENSI и OMS
  - Не трогать мобилу и сайт
- **Выход:** "Integration routing & contracts"

#### `research-code-site-mobile.md`
- **Агент:** Code-researcher (Site/Mobile)
- **Входит:** экран или компонент
- **Выходит:** компоненты, NgRx state, RN hooks, API вызовы, макеты
- **Время:** 10-15 мин
- **Скилы:** codegraph_explore, site-stack-anatomy, mobile-stack-anatomy, site-angular-conventions, mobile-rn-conventions, Read, Grep
- **Правила:**
  - Site: platform/site/gj-ng-front
  - Mobile: platform/mobile-app/gj-app
  - Смотреть Figma ссылки в коде
  - Отмечать inconsistencies между RU/EN/KZ локалями
- **Выход:** "Frontend: [компонент] structure & contracts"

#### `research-logs.md`
- **Агент:** Logs-detective
- **Входит:** сценарий, edge-case, или "как ведёт себя на стенде?"
- **Выходит:** поведение в реальности, лаги, ошибки, edge-cases, trace path
- **Время:** 10-15 мин
- **Скилы:** mcp__gj-buddy__logs_*, mcp__gj-buddy__data_k8s_*, WebFetch, Bash
- **Правила:**
  - Только stage/gs-test логи доступны для ENSI
  - Ищи trace_id, follow message flow
  - Фиксируй лаги (если >100ms аномальный)
  - Воспроизводи edge-cases на стенде
- **Выход:** "Behavior on stage: [facts], latency: X ms, reproducibility: Y%"

#### `research-blackbox.md`
- **Агент:** Black-box-researcher
- **Входит:** API endpoint или flow
- **Выходит:** запрос/ответ, edge-cases, версионирование, workarounds
- **Время:** 8-12 мин
- **Скилы:** WebFetch, curl (Bash), test-контур access, Postman
- **Правила:**
  - Используй test-контур, не prod
  - Используй фиксированные креденшалы из .env
  - Сравнивай текущий и желаемый поведение
  - Отмечай [BLOCKER] если воспроизводить нельзя
- **Выход:** "API behavior: [current vs expected], reproducibility, edge-cases"

---

### 📊 [ANALYSIS] Аналитические скилы

**Назначение:** синтез выводов исследователей в постановку, выявление конфликтов.

#### `analyze-synthesis.md`
- **Агент:** Аналитик
- **Входит:** 5 выводов исследователей (Conf, Code×3, Logs, Black-box)
- **Выходит:** единая постановка для разработчика
- **Время:** 5 мин
- **Скилы:** shared-claude-md-reference, shared-service-index
- **Процесс:**
  1. Прочитай все 5 выводов (каждый ~1K)
  2. Выяви конфликты (если Conf говорит X, а Black-box говорит Y)
  3. Спроси исследователя/человека [BLOCKER] если неполное
  4. Напиши постановку: ЧТО делаем, ГДЕ, КАК проверяем
- **Выход:** Structured requirement document

#### `analyze-requirements.md`
- **Агент:** Аналитик
- **Входит:** постановка и скилы
- **Выходит:** валидированная постановка (или пробелы)
- **Время:** 3 мин
- **Процесс:**
  1. Все ли AC из Jira покрыты?
  2. Архитектурные границы ясны?
  3. Риски и ограничения описаны?
  4. Нет ли противоречий с CLAUDE.md?

#### `analyze-blockers.md`
- **Агент:** Аналитик
- **Входит:** [BLOCKER] вопрос из исследователя
- **Выходит:** спрос к человеку или уточнение в постановку
- **Время:** зависит от ответа человека
- **Процесс:**
  1. Спросить человека чётко
  2. Получить ответ
  3. Передать ответ исследователю/разработчику
  4. Отметить как resolved

---

### 💻 [DEVELOPMENT] Разработческие скилы

**Назначение:** написание кода в соответствии с постановкой и платформенными стандартами.

#### `develop-ensi.md`
- **Агент:** Developer (ENSI)
- **Фокус:** PHP 8.1 + Swoole, Laravel patterns, OpenAPI-first
- **Входит:** постановка, целевой сервис
- **Скилы:** ensi-code-style, ensi-models, ensi-openapi, ensi-tests, ensi-kafka, shared-code-style
- **Правила:**
  - Изменять спеку перед кодом (OpenAPI-first)
  - Использовать generated клиенты, не hand-crafted
  - Pest tests, не PHPUnit
  - После кода → регенерировать клиенты
- **Выход:** MR с кодом, тестами, спекой, комментариями

#### `develop-oms-java.md`
- **Агент:** Developer (OMS Java)
- **Фокус:** Spring Boot, Maven, Lombok, Camunda
- **Входит:** постановка, целевой сервис
- **Скилы:** oms-stack-anatomy, oms-java-conventions, camunda-bpm, shared-code-style
- **Правила:**
  - Per-env конфиги → awg/cloud-configs, не application.yml
  - BPMN XML + Java handlers в синхронии
  - Jira issue key в коммитах
- **Выход:** MR с кодом, Java tests, BPMN XML

#### `develop-integration.md`
- **Агент:** Developer (Integration)
- **Фокус:** PHP 8.1 + Lumen, BFF логика
- **Входит:** постановка, endpoint или cron task
- **Скилы:** integration-stack-anatomy, integration-php-conventions, shared-code-style
- **Правила:**
  - Два деплоя: integration-api и integration-cron
  - Контракты с ENSI/OMS важны
  - Phpstan в CI
- **Выход:** MR с кодом, тестами

#### `develop-site.md`
- **Агент:** Developer (Site)
- **Фокус:** Angular 20 + Nx + NgRx, NestJS SSR
- **Входит:** постановка, компонент или фича
- **Скилы:** site-stack-anatomy, site-nx-commands, site-angular-conventions, shared-code-style
- **Правила:**
  - Nx module boundaries соблюдать
  - NgRx actions, selectors, effects явно
  - Storybook stories для компонентов
  - E2E cypress тесты
- **Выход:** MR с компонентами, stories, tests

#### `develop-mobile.md`
- **Агент:** Developer (Mobile)
- **Фокус:** React Native 0.74 + TypeScript, styled-components
- **Входит:** постановка, экран или компонент
- **Скилы:** mobile-stack-anatomy, mobile-rn-conventions, mobile-build-commands, shared-code-style
- **Правила:**
  - yarn workspaces (gj, ui-kit, rn-yookassa-sdk)
  - patch-package для нативных модулей
  - detoxTestIds для e2e
  - 3 build-flavors: dev, staging, prod
- **Выход:** MR с компонентами, тестами, env configs

#### `develop-gloriaots.md`
- **Агент:** Developer (Gloria OTS)
- **Фокус:** .NET 10, ASP.NET Core, EF Core, SQL Server
- **Входит:** постановка, handler или worker
- **Скилы:** gloriaots-stack-anatomy, shared-code-style
- **Правила:**
  - EF Core migrations
  - RabbitMQ event handlers
  - Hangfire jobs
  - Admin SPA в React/Vite
- **Выход:** MR с handlers, migrations, tests

#### `develop-go-new.md`
- **Агент:** Developer (Go platform-new)
- **Фокус:** Go 1.22+, Gin, Clean Architecture, OpenAPI
- **Входит:** постановка, микросервис
- **Скилы:** go-service-engineer, go-library-engineer, shared-code-style
- **Правила:**
  - Clean architecture: internal/domain, adapters, platform
  - OpenAPI generation из спеки
  - Generated clients (oapi-codegen)
  - Table-driven tests
- **Выход:** MR с кодом, тестами, OpenAPI спекой

---

### ✅ [REVIEW] Review скилы

**Назначение:** проверка кода по специализированным направлениям.

#### `review-business-architecture.md`
- **Агент:** Reviewer-1 (бизнес + архитектура)
- **Входит:** MR дифф, Jira AC, service-index
- **Выходит:** замечания с тегами [MUST], [SHOULD], [NIT]
- **Время:** ~20 мин
- **Проверяет:**
  1. AC выполнены? Нет ли упущенных edge-cases?
  2. Архитектурные границы соблюдены?
  3. API контракты совместимы? (если OpenAPI)
  4. Расширяемость: не hardcode, patterns соблюдены?
  5. Naming ясное? (методы, переменные, классы)
- **Скилы:** shared-claude-md-reference, shared-service-index, review-checklist-by-platform
- **НЕ проверяет:** синтаксис (CI это сделал), security (reviewer-2), дизайн (reviewer-2)
- **Процесс:**
  - Постой, это нарушает контракт? → [MUST FIX]
  - Это может быть проблемой позже? → [SHOULD]
  - Есть более элегантный способ? → [NIT]

#### `review-security-performance-design.md`
- **Агент:** Reviewer-2 (безопасность + перф + дизайн)
- **Входит:** MR дифф, Figma ссылки, performance guidelines
- **Выходит:** замечания [SECURITY], [PERF], [DESIGN]
- **Время:** ~20 мин
- **Проверяет:**
  1. **Security:** injection, auth, crypto, controls?
  2. **Performance:** N+1, O(N²) loops, caching, DB queries?
  3. **Design:** соответствует Figma? токены? брендбук? доступность (a11y)?
  4. **UX:** flow логичен? ошибки ясные? loading states?
- **Скилы:** shared-security-checklist, shared-performance-basics, review-checklist-by-platform
- **НЕ проверяет:** бизнес-логику (reviewer-1), архитектуру (reviewer-1)
- **Процесс:**
  - Это SQL injection? → [SECURITY] [MUST FIX]
  - Это может быть медленным? → [PERF] [SHOULD]
  - Макет говорит другое цветовое решение? → [DESIGN] [SHOULD]

#### `review-checklist-by-platform.md`
- **Назначение:** платформенные чеклисты для ревьюеров
- **Содержит:**
  - ENSI: OpenAPI sync, клиент-генерация, Kafka контракты
  - OMS: BPMN sync, per-env конфиги, Camunda topic names
  - Integration: два деплоя, маршрутизация, контракты
  - Site: Nx boundaries, NgRx store, SSR, i18n, a11y
  - Mobile: workspaces, нативные модули, patch-package, device testing
  - Go: Clean arch, generated clients, error handling
- **Используется:** обоими ревьюерами для быстрых проверок

---

### 🎯 [COORDINATION] Координационные скилы

**Назначение:** управление процессом, метрики, параллелизм, блокеры.

#### `coord-task-orchestration.md`
- **Агент:** Координатор
- **Входит:** Jira ticket
- **Выходит:** запуск workflow, мониторинг фаз
- **Процесс:**
  1. Запустить Workflow (task-research-and-analyze)
  2. Дождаться Phase 1 (25 мин исследование)
  3. Phase 2 (5 мин анализ)
  4. Запустить разработчика с постановкой
  5. Параллельно запустить ревьюеры при готовности MR
  6. Собрать метрики → Phase 7
- **Скилы:** gj-task-orchestration, shared-gj-buddy-mcp
- **Инструменты:** Workflow script, MCP для обновления Jira

#### `coord-metrics-collection.md`
- **Агент:** Координатор
- **Входит:** данные из каждой фазы (логи, времена, токены)
- **Выходит:** артефакт с метриками
- **Собирает:**
  - Время в каждой фазе (Phase 1: 25 мин, Phase 2: 5 мин и т.д.)
  - Токены каждого агента
  - Вопросы к человеку, лаг ответов
  - Качество (ревьюер-1 vs ревьюер-2 замечания)
  - Пересчёты (сколько раз разработчик фиксил)
- **Выход:** таблица + рекомендации

#### `coord-blocker-management.md`
- **Агент:** Координатор + Аналитик
- **Входит:** [BLOCKER] вопрос на любой фазе
- **Выходит:** ответ человека или разрешение
- **Процесс:**
  1. Аналитик видит [BLOCKER] от исследователя
  2. Координатор спрашивает человека (в слак, в комментарий Jira)
  3. Человек отвечает
  4. Ответ передаётся исследователю/разработчику
  5. Отметить resolved, продолжить
- **Правила:** параллельные [NB] вопросы не блокируют разработку

#### `coord-parallel-execution.md`
- **Агент:** Координатор
- **Входит:** готовность фаз
- **Выходит:** синхронизация, запуск параллельных фаз
- **Схемы параллелизма:**
  - Phase 1: 5 исследователей одновременно
  - Phase 3 + Phase 4-5: разработчик начинает, ревьюеры смотрят параллельно
  - [NB] вопросы + разработка: параллельно, если не зависят
- **Инструмент:** Workflow script с `parallel()` блоками

---

### 🔗 [SHARED] Общие скилы (для всех ролей)

#### `shared-claude-md-reference.md`
- **Для:** все агенты
- **Содержит:** ссылка на CLAUDE.md, главные правила
- **Примеры:**
  - Структура platform/*/
  - Нестандартные default-branches (Site = release/production, OMS много feature-веток)
  - Правила коммитов (Co-Authored-By)
  - Когда использовать какого агента

#### `shared-service-index.md`
- **Для:** все агенты
- **Содержит:** реестр всех ~25 ENSI сервисов, OMS сервисов, где что находится
- **Назначение:** быстро ответить "где код X?"

#### `shared-gj-buddy-mcp.md`
- **Для:** агенты, которые читают Confluence/Jira/Gitlab/логи
- **Содержит:**
  - confluence_* tools
  - jira_* tools
  - gitlab_* tools (если репо нет локально)
  - logs_* tools (integration-awg-* deprecated, только raw_search)
  - data_k8s_* (для Logs-detective)
- **Правило:** никогда не писать через MCP, только читать

#### `shared-git-workflow.md`
- **Для:** разработчики, координатор
- **Содержит:**
  - Ветки: feature/*, fix/*, refactor/*
  - Коммиты: сообщения, Co-Authored-By
  - MR: title, description, target branch
  - Push: куда пушим (проверить default-branch!)
  - Merge: автоматический или вручную?
- **Правило:** перед push проверить target branch (Site = release/production!)

#### `shared-security-checklist.md`
- **Для:** все разработчики, ревьювер-2, отчасти ревьювер-1
- **Содержит:**
  - SQL injection (параметризованные запросы, ORM)
  - XSS (escaping, content-security-policy)
  - CSRF (tokens, same-site cookies)
  - Authentication (JWT, session, 2FA)
  - Authorization (roles, permissions, ACL)
  - Crypto (не hardcode ключи, использовать libraries)
  - Secrets (не в code, в env vars, .env files .gitignored)
  - Logging (не логировать PII, passwords, tokens)
- **Уровень:** OWASP top 10 basics

#### `shared-performance-basics.md`
- **Для:** разработчики, ревьювер-2
- **Содержит:**
  - N+1 queries (выявить в коде/логах)
  - O(N²) loops (в коде видно)
  - Caching (Redis, in-memory, HTTP cache)
  - DB indexes (если добавляем колонку в WHERE, нужен index)
  - Connection pooling
  - Batch operations
- **Уровень:** базовые paтterны

#### `shared-code-style.md`
- **Для:** все разработчики, ревьюеры
- **Содержит:**
  - Комментарии: только "почему", 1-3 строки, не "что"
  - Naming: ясные имена функций, переменных, классов
  - Форматирование: 2 spaces (JS/TS), 4 spaces (PHP/Java)
  - Функции: <30 строк, один уровень абстракции
  - Классы: single responsibility
  - Тесты: для each public function
  - No commented-out code, no TODO без задачи
- **Инструмент:** ESLint, Phpstan, gofmt (CI)

---

## Использование по фазам

### Phase 0: Инициализация (Координатор, 2 мин)

```
Координатор:
  1. Получил Jira ticket с требованием
  2. Загрузил скилы:
     - shared-claude-md-reference
     - shared-service-index
     - shared-gj-buddy-mcp
     - coord-task-orchestration
  3. Запустил Workflow (task-research-and-analyze)
     └─ Workflow загружает скилы для 5 исследователей
```

### Phase 1: Research (5 исследователей параллельно, 25 мин)

```
Conf-researcher:
  1. Загрузил: research-confluence, shared-gj-buddy-mcp
  2. Читает Confluence (ТЗ, docs)
  3. Читает Jira (AC, комментарии, историю)
  4. Выводит: "ТЗ: [...], AC: [...], открытые вопросы: [...]"

Code-researcher (OMS):
  1. Загрузил: research-code-oms, oms-stack-anatomy, camunda-bpm
  2. Читает OMS структуру (codegraph)
  3. Находит сущность, BPMN процесс, handlers
  4. Выводит: "OMS: enum=[...], handler=[...], BPMN=[...]"

Code-researcher (Integration):
  1. Загрузил: research-code-integration, integration-stack-anatomy
  2. Читает маршруты, контракты
  3. Выводит: "Integration: маршрут=[...], контракты=[...]"

Logs-detective:
  1. Загрузил: research-logs, shared-gj-buddy-mcp
  2. Читает логи со стенда
  3. Выводит: "Поведение: [факты], лаг: X ms, воспроизводимость: Y%"

Black-box-researcher:
  1. Загрузил: research-blackbox
  2. Делает запросы на test-контур
  3. Выводит: "API: текущее=[...], ожидаемое=[...], edge-cases=[...]"
```

### Phase 2: Analysis (Аналитик, 5 мин)

```
Аналитик:
  1. Загрузил: analyze-synthesis, analyze-requirements, shared-claude-md-reference
  2. Прочитал 5 выводов исследователей
  3. Выявил конфликты (если есть) → [BLOCKER] вопрос к человеку
  4. Написал постановку:
     - ЧТО делаем: [requirement]
     - ГДЕ: [service list]
     - КАК проверяем: [AC, tests, manual]
     - РИСКИ: [limitations, blockers]
```

### Phase 3: Development (Разработчик, 30-60 мин)

```
Разработчик:
  1. Загрузил: develop-[platform], shared-code-style, shared-security-checklist
  2. Прочитал постановку
  3. Если [NB] вопрос не разрешён → написал нативный код (не зависимый)
  4. Если [BLOCKER] → ждёт ответа (может скипнуть блокирующую часть)
  5. Написал код, тесты, комментарии (только "почему")
  6. Запушил MR → готово на ревью
  7. Параллельно: Coordinator запустил ревьюеров
```

### Phase 4-5: Review (2 ревьювера параллельно, 20 мин каждый)

```
Reviewer-1:
  1. Загрузил: review-business-architecture, shared-claude-md-reference, review-checklist-by-platform
  2. Прочитал postановку из Phase 2
  3. Прочитал дифф
  4. Проверил: AC, архитектура, контракты, расширяемость
  5. Написал замечания: [MUST FIX], [SHOULD], [NIT]
  6. Отправил в MR comments

Reviewer-2 (параллельно):
  1. Загрузил: review-security-performance-design, shared-security-checklist, shared-performance-basics
  2. Прочитал дифф (не ждёт reviewer-1)
  3. Проверил: безопасность, перф, дизайн
  4. Написал замечания: [SECURITY], [PERF], [DESIGN]
  5. Отправил в MR comments

Разработчик (параллельно):
  1. Видит замечания от обоих ревьюеров
  2. Фиксит [MUST FIX] замечания (обязательны)
  3. Обсуждает [SHOULD] если нужно
  4. Пропускает [NIT] если не согласен
  5. Запушил фиксы → MR обновился
  
Ревьюеры перепроверяют:
  1. Reviewer-1 (5 мин)
  2. Reviewer-2 (5 мин)
  3. Если всё OK → Approved
```

### Phase 6-7: Merge + Metrics (Координатор, 5 мин)

```
Координатор:
  1. Оба ревьюера одобрили → Merge (автоматический или вручную)
  2. Собрал метрики:
     - Phase 1 (Research): 25 мин
     - Phase 2 (Analysis): 5 мин
     - Phase 3 (Development): 45 мин
     - Phase 4-5 (Review): 20 мин (параллельно)
     - Phase 6-7 (Merge + Metrics): 5 мин
     - ИТОГО: 100 мин (вместо 180 мин если бы всё последовательно)
  3. Расход токенов:
     - Researchers: 5 × 12K = 60K
     - Analyst: 8K
     - Developer: 20K
     - Reviewers: 2 × 15K = 30K
     - ИТОГО: 118K (вместо 200K в одном координаторе)
  4. Написал отчёт: "Задача OPSOMN002-XXX завершена"
  5. Предложил оптимизацию: "Conf-researcher брал 8 мин, можно ускорить на 2 мин"
```

---

## Пересечение скилов

### Как скилы связаны между собой?

```mermaid
graph LR
    shared["🔗 SHARED<br/>claude-md<br/>service-index<br/>gj-buddy<br/>code-style"]
    
    research["🔍 RESEARCH<br/>conf<br/>code×3<br/>logs<br/>blackbox"]
    analyze["📊 ANALYSIS<br/>synthesis<br/>requirements<br/>blockers"]
    develop["💻 DEVELOP<br/>ensi/oms/integration<br/>site/mobile<br/>gloriaots/go"]
    review1["✅ REVIEW-1<br/>business<br/>architecture"]
    review2["✅ REVIEW-2<br/>security<br/>performance<br/>design"]
    coord["🎯 COORD<br/>orchestration<br/>metrics<br/>blockers<br/>parallel"]
    
    shared --> research
    shared --> analyze
    shared --> develop
    shared --> review1
    shared --> review2
    shared --> coord
    
    research --> analyze
    analyze --> develop
    develop --> review1
    develop --> review2
    review1 --> coord
    review2 --> coord
    
    analyze -.->|[BLOCKER]| coord
    develop -.->|[BLOCKER]| coord
```

### Правила непересечения

- **Исследователи** не пишут код, только читают
- **Аналитик** не трогает код, только синтезирует требования
- **Разработчик** не пишет спеки (OpenAPI-first) и не ревьюит себя
- **Reviewer-1** не смотрит на security/perf/design
- **Reviewer-2** не смотрит на бизнес-логику/архитектуру
- **Координатор** не пишет код, не ревьюит, не исследует

### Как избежать дублирования

- Если скилл нужен двум агентам → положить в [SHARED]
- Если скилл специфичен → [RESEARCH/ANALYSIS/etc]
- Если обновился скилл → обновить в одном месте, все используют актуальный

---

## Инструкции по добавлению новых скилов

### Когда добавлять скилл?

1. **Новая платформа** (e.g. new Go сервис в platform-new)
   → добавить `develop-go-new-[servicename].md` в [DEVELOPMENT]

2. **Новый паттерн** (e.g. распределённые транзакции)
   → добавить `shared-distributed-transactions.md` в [SHARED]

3. **Новый вид исследования** (e.g. performance-testing)
   → добавить `research-performance-testing.md` в [RESEARCH]

4. **Уточнение ревью** (e.g. accessibility checklist)
   → добавить в `review-security-performance-design.md` или новый файл

### Шаблон для нового скилла

```markdown
# [Название скилла]

**Категория:** [RESEARCH/ANALYSIS/DEVELOPMENT/REVIEW/COORDINATION/SHARED]  
**Агент:** [какой агент его использует]  
**Версия:** 1.0  

## Назначение
[Одна фраза, что делает скилл]

## Входит
- [что нужно на входе]

## Выходит
- [что выдаёт скилл]

## Процесс
1. [шаг 1]
2. [шаг 2]
...

## Правила
- [правило 1]
- [правило 2]

## Примеры
```

### Где регистрировать скилль?

1. Создать файл в `.claude/skills/[CATEGORY]/[name].md`
2. Добавить строку в этот файл (SKILLS_INDEX.md) в соответствующий раздел
3. Обновить таблицу "Роли и скилы"
4. Если это меняет граф зависимостей → обновить диаграмму в README

---

## Быстрая навигация

**Ищу скилл для:**
- ✅ Чтения Confluence? → `research-confluence.md`
- ✅ Написания PHP? → `develop-integration.md` или `develop-ensi.md`
- ✅ Ревью безопасности? → `review-security-performance-design.md` + `shared-security-checklist.md`
- ✅ Управления workflow'ом? → `coord-task-orchestration.md`
- ✅ Понимания ENSI структуры? → `research-code-ensi.md` + `shared-service-index.md`
- ✅ Проверки производительности? → `review-security-performance-design.md` + `shared-performance-basics.md`

---

**Версия:** 1.0  
**Последнее обновление:** 2026-10-06  
**Автор:** Claude Haiku 4.5 + Antonov Aleksandr (Outsource)
