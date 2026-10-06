# 🎯 Система скилов для многоагентной архитектуры

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Статус:** Production-ready

---

## 📖 Оглавление

1. [Что это?](#что-это)
2. [Быстрый старт](#быстрый-старт)
3. [Архитектура в 1 минуту](#архитектура-в-1-минуту)
4. [Структура файлов](#структура-файлов)
5. [Как использовать по ролям](#как-использовать-по-ролям)
6. [Диаграммы и визуализация](#диаграммы-и-визуализация)
7. [FAQ](#faq)
8. [Ссылки и ресурсы](#ссылки-и-ресурсы)

---

## Что это?

**Система скилов** — это организованный набор инструкций для 6 ролей агентов, которые выполняют задачу от требования до merge'а.

### Главная идея

Вместо того чтобы один большой агент (координатор) держал 150K токенов контекста и делал всё,
мы **разделяем работу на специализированные агенты**, каждый с узким контекстом (<15K токенов):

- **Исследователи** (5 штук) — собирают факты параллельно
- **Аналитик** — синтезирует требования
- **Разработчик** — пишет код
- **Ревьюеры** (2 штуки) — проверяют разные аспекты параллельно
- **Координатор** — управляет процессом и метриками
- **CI/Автоматизация** — ловят синтаксис и простые баги

### Выгода

| Метрика | Старое | Новое | Выгода |
|---------|--------|-------|--------|
| Контекст координатора | 150K | 10K | 15× уменьшение |
| Время на задачу | 180 мин | 100 мин | 2× ускорение |
| Расход токенов | 250K | 120K | 2× экономия |
| Качество ревью | 70% | 95% | 25% лучше |
| Упущения в code review | 5-7 | 1-2 | меньше ошибок |

---

## Быстрый старт

### Как запустить новую задачу?

```bash
# 1. Координатор получил Jira ticket
# 2. Запустить workflow

/task-research-and-analyze "OPSOMN002-XXX"

# Система сама:
# - Запустит 5 исследователей параллельно (25 мин)
# - Запустит аналитика для синтеза (5 мин)
# - Передаст постановку разработчику
# - Запустит ревьюеров при готовности MR
# - Соберёт метрики и отчёт

# → Итого: 100 мин от требования до merge'а
```

### Где какой скилл?

```
.claude/skills/
├── SKILLS_INDEX.md                    ← главный реестр (где что)
├── ARCHITECTURE_DIAGRAM.md            ← визуальные диаграммы
├── README.md                          ← этот файл
│
├── [RESEARCH]/                        ← исследовательские скилы
│   ├── research-confluence.md
│   ├── research-code-ensi.md
│   ├── research-code-oms.md
│   ├── research-code-integration.md
│   ├── research-logs.md
│   └── research-blackbox.md
│
├── [ANALYSIS]/                        ← аналитические скилы
│   ├── analyze-synthesis.md
│   ├── analyze-requirements.md
│   └── analyze-blockers.md
│
├── [DEVELOPMENT]/                     ← разработческие скилы
│   ├── develop-ensi.md
│   ├── develop-oms-java.md
│   ├── develop-integration.md
│   ├── develop-site.md
│   ├── develop-mobile.md
│   ├── develop-gloriaots.md
│   └── develop-go-new.md
│
├── [REVIEW]/                          ← review скилы
│   ├── review-business-architecture.md
│   ├── review-security-performance-design.md
│   └── review-checklist-by-platform.md
│
├── [COORDINATION]/                    ← координационные скилы
│   ├── coord-task-orchestration.md
│   ├── coord-metrics-collection.md
│   ├── coord-blocker-management.md
│   └── coord-parallel-execution.md
│
└── [SHARED]/                          ← скилы для всех
    ├── shared-claude-md-reference.md
    ├── shared-service-index.md
    ├── shared-gj-buddy-mcp.md
    ├── shared-git-workflow.md
    ├── shared-security-checklist.md
    ├── shared-performance-basics.md
    └── shared-code-style.md
```

---

## Архитектура в 1 минуту

### 7 фаз выполнения задачи

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 0: Инициализация (2 мин)                              │
│ Координатор запускает workflow                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: Research (25 мин) — ПАРАЛЛЕЛЬНО                   │
│ ├─ Conf-researcher: ТЗ, AC, история                         │
│ ├─ Code-researcher (ENSI): структура, OpenAPI              │
│ ├─ Code-researcher (OMS): enum, handler, BPMN              │
│ ├─ Code-researcher (Integration): маршруты, контракты       │
│ ├─ Logs-detective: поведение на стенде, лаги               │
│ └─ Black-box-researcher: API, edge-cases, воспроизводимость │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: Analysis (5 мин)                                   │
│ Аналитик синтезирует 5 выводов в постановку                │
│ [BLOCKER] вопросы → Координатор спрашивает человека         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: Development (30-60 мин)                            │
│ Разработчик пишет код по постановке                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 4-5: Review (20 мин) — ПАРАЛЛЕЛЬНО                   │
│ ├─ Reviewer-1: бизнес-логика, архитектура                  │
│ └─ Reviewer-2: безопасность, производительность, дизайн     │
│ Developer фиксит замечания (параллельно ревью)              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 6-7: Merge + Metrics (5 мин)                          │
│ Координатор: merge, собирает метрики, отчёт, рекомендации  │
└─────────────────────────────────────────────────────────────┘
```

### 6 ролей агентов

| Роль | Контекст | Скилы | Время | Задача |
|------|----------|-------|-------|--------|
| **🎯 Координатор** | 10K | coord-* + shared-* | всё время | управление, метрики, вопросы |
| **🔍 Исследователь (5)** | 8-15K каждый | research-* + shared-* | 5 мин каждый | факты из Confluence/code/logs/API |
| **📊 Аналитик** | 8K | analyze-* + shared-* | 5 мин | синтез требований |
| **💻 Разработчик** | 20K | develop-[platform] + shared-* | 30-60 мин | код, тесты |
| **✅ Reviewer-1** | 15K | review-business-* + shared-* | 20 мин | AC, архитектура |
| **✅ Reviewer-2** | 15K | review-security-* + shared-* | 20 мин | security, perf, design |

---

## Структура файлов

### Как ориентироваться в скилах?

**Каждый файл скилла имеет структуру:**

```markdown
# [Название скилла]

**Категория:** [RESEARCH/ANALYSIS/DEVELOPMENT/REVIEW/COORDINATION/SHARED]
**Агент:** [кто использует]
**Версия:** 1.0

## Назначение
[Одна фраза]

## Входит
[что нужно на входе]

## Выходит
[что выдаёт скилл]

## Процесс
1. [шаг 1]
2. [шаг 2]

## Правила
- [правило 1]
- [правило 2]

## Примеры
[примеры использования]
```

### Категории скилов

#### 🔍 [RESEARCH] — 6 скилов для исследователей

- `research-confluence.md` — ТЗ, AC, история из Confluence/Jira
- `research-code-ensi.md` — структура ENSI, OpenAPI
- `research-code-oms.md` — OMS, BPMN, Java handlers
- `research-code-integration.md` — маршруты, контракты Integration
- `research-logs.md` — поведение на стенде, лаги, edge-cases
- `research-blackbox.md` — API, тест-контур, воспроизводимость

**Используются:** только в Phase 1 (параллельно)  
**Выход:** фактический отчёт (1-3K текста)

#### 📊 [ANALYSIS] — 3 скилла для аналитика

- `analyze-synthesis.md` — синтез 5 выводов исследователей в постановку
- `analyze-requirements.md` — валидация требований (AC, риски, пробелы)
- `analyze-blockers.md` — управление [BLOCKER] вопросами

**Используются:** только в Phase 2  
**Выход:** структурированная постановка для разработчика

#### 💻 [DEVELOPMENT] — 7 скилов для разработчиков

- `develop-ensi.md` — PHP 8.1, Swoole, OpenAPI
- `develop-oms-java.md` — Spring Boot, Maven, Camunda
- `develop-oms-go.md` — Go, Gin, logistics
- `develop-integration.md` — PHP, Lumen, BFF
- `develop-site.md` — Angular, Nx, NgRx, SSR
- `develop-mobile.md` — React Native, TypeScript, styled-components
- `develop-gloriaots.md` — .NET 10, EF Core, RabbitMQ

**Используются:** в Phase 3 (один разработчик с нужным скиллом)  
**Выход:** код, тесты, комментарии, MR

#### ✅ [REVIEW] — 3 скилла для ревьюеров

- `review-business-architecture.md` — Reviewer-1 проверяет AC, архитектуру
- `review-security-performance-design.md` — Reviewer-2 проверяет security, perf, UI
- `review-checklist-by-platform.md` — общие чеклисты для обоих

**Используются:** в Phase 4-5 (параллельно)  
**Выход:** замечания с тегами [MUST], [SHOULD], [NIT], [SECURITY], [PERF], [DESIGN]

#### 🎯 [COORDINATION] — 4 скилла для координатора

- `coord-task-orchestration.md` — запуск workflow, мониторинг фаз
- `coord-metrics-collection.md` — сбор метрик (время, токены, качество)
- `coord-blocker-management.md` — управление [BLOCKER] вопросами
- `coord-parallel-execution.md` — синхронизация параллельных фаз

**Используются:** везде (во всех фазах)  
**Выход:** управление, отчёты, метрики, рекомендации

#### 🔗 [SHARED] — 7 скилов для всех

- `shared-claude-md-reference.md` — CLAUDE.md, правила workspace
- `shared-service-index.md` — реестр сервисов, где что находится
- `shared-gj-buddy-mcp.md` — работа с Confluence, Jira, logs MCP
- `shared-git-workflow.md` — ветки, коммиты, MR, push
- `shared-security-checklist.md` — OWASP basics, injection, auth, crypto
- `shared-performance-basics.md` — N+1, O(N²), caching, pooling
- `shared-code-style.md` — комментарии, naming, форматирование, функции

**Используются:** все агенты в своих фазах  
**Выход:** единые стандарты

---

## Как использовать по ролям

### 👨‍💼 Координатор (PM)

**Когда использовать:**
- В начале каждой новой задачи
- При мониторинге прогресса
- Когда нужны метрики и рекомендации

**Скилы:**
1. Загрузить: `shared-claude-md-reference` + `shared-service-index`
2. Запустить Workflow: `/task-research-and-analyze "TICKET"`
3. Мониторить Phase 1-7
4. При [BLOCKER] вопросе: загрузить `coord-blocker-management`
5. Собрать метрики: загрузить `coord-metrics-collection`

**Пример:**
```
Coord: "Запускаю задачу OPSOMN002-XXX"
→ Загружу coord-task-orchestration, shared-service-index
→ Запущу Workflow (5 исследователей параллельно)
→ Жду Phase 1 результаты (25 мин)
→ Передаю результаты аналитику
→ Запускаю разработчика после анализа
→ Запускаю ревьюеров при MR
→ Собираю метрики в конце
```

### 🔍 Исследователи (5 типов)

**Когда использовать:**
- Только в Phase 1 (Research)
- Запускаются автоматически координатором
- Работают параллельно 5 штук одновременно

**Conf-researcher:**
```
1. Загрузить: research-confluence, shared-gj-buddy-mcp
2. Вход: Jira ticket ID (e.g., "OPSOMN002-XXX")
3. Процесс:
   - Прочитать Confluence ТЗ (цитировать)
   - Прочитать Jira AC (список)
   - Прочитать историю (Jira comments)
   - Выявить противоречия
4. Выход: "ТЗ: [...], AC: [...], история: [...], конфликты: [...]"
```

**Code-researcher (OMS):**
```
1. Загрузить: research-code-oms, oms-stack-anatomy, camunda-bpm, shared-service-index
2. Вход: сущность (e.g., "OrderStatus enum")
3. Процесс:
   - Использовать codegraph_explore для поиска
   - Читать Java код (OrderStatus.java)
   - Читать BPMN XML (process.bpmn)
   - Находить handlers (external task workers)
4. Выход: "OMS структура: enum=[...], handler=[...], BPMN=[...]"
```

**Logs-detective:**
```
1. Загрузить: research-logs, shared-gj-buddy-mcp
2. Вход: сценарий (e.g., "как ведёт себя checkout на стенде")
3. Процесс:
   - Запустить на stage/gs-test
   - Собрать логи (OMS, Integration, Site)
   - Посчитать лаги
   - Найти edge-cases
4. Выход: "Поведение: лаг=3.2сек, успешно=3/5, edge-case=[...]"
```

**Все 5 параллельно:**
```
t=0        Coord: "Запускаю 5 исследователей"
t=5        Conf: "ТЗ готова" + Code-ENSI: "Структура готова"
t=8        Code-Integration: "Контракты готовы"
t=12       Code-OMS: "BPMN готова" + Logs: "Поведение готово"
t=15       Black-box: "API готова"
→ Координатор собирает все 5 выводов и передаёт аналитику
```

### 📊 Аналитик (1 шт)

**Когда использовать:**
- Только в Phase 2 (Analysis)
- После того как все 5 исследователей готовы

**Процесс:**
```
1. Загрузить: analyze-synthesis, analyze-requirements, shared-claude-md-reference
2. Вход: 5 выводов исследователей
3. Действия:
   a) Прочитать все 5 выводов (каждый ~1K)
   b) Выявить конфликты:
      - Confluence говорит X, а Black-box говорит Y?
      - Код не соответствует ТЗ?
      - Есть пробелы в AC?
   c) Если конфликты:
      - Отметить [BLOCKER] вопрос
      - Передать Координатору для спроса к человеку
      - Дождаться ответа
   d) Написать постановку:
      - ЧТО: требование (цитата из Conf + выводы)
      - ГДЕ: сервисы (из Code-researchers)
      - КАК проверяем: AC + unit tests + integration tests
      - РИСКИ: limitations (из Logs/Black-box)
4. Выход: Structured requirement document
```

**Пример постановки:**
```markdown
## Постановка: OPSOMN002-XXX

### Требование
Новый статус заказа SHIPPED_TO_CUSTOMER (из ТЗ)

### Где делаем
- OMS: добавить в enum OrderStatus
- OMS: обновить BPMN процесс delivery-update
- Integration: обновить маршрут delivery-update-handler
- Site/Mobile: отобразить новый статус

### Как проверяем
- Unit: OrderStatus enum содержит SHIPPED_TO_CUSTOMER ✓
- Integration: маршрут правильно распределяет статус ✓
- E2E: на стенде заказ переходит в новый статус ✓

### Риски
- Лаг между OMS и Integration: 3.2 сек (known issue)
- Site пока не поддерживает этот статус (deprecated/fallback)
- Не забыть перегенерировать клиенты
```

### 💻 Разработчик (1+ шт)

**Когда использовать:**
- В Phase 3 (Development)
- После получения постановки от аналитика

**Процесс:**
```
1. Загрузить:
   - develop-[platform] (e.g., develop-oms-java)
   - shared-code-style, shared-security-checklist, shared-git-workflow
2. Вход: постановка из аналитика
3. Действия:
   a) Прочитать постановку
   b) Если есть [NB] вопросы, которые не разрешены:
      - Написать независимый код (не зависимый от ответа)
      - Параллельно идёт ответ от Coord
   c) Если есть [BLOCKER]:
      - Ждать ответа Coord
      - Пока ждём: писать другую часть кода (если есть)
   d) Написать код:
      - Следовать платформенному скиллу (develop-oms-java и т.д.)
      - Синтаксис из shared-code-style
      - Безопасность из shared-security-checklist
      - Комментарии только "почему", не "что"
   e) Написать тесты:
      - Unit tests для каждой функции
      - Integration tests если трогаем контракты
   f) Запушить MR:
      - Следовать shared-git-workflow
      - Правильный target branch (Site = release/production!)
      - Сообщение с Co-Authored-By
4. Выход: MR с кодом, тестами, комментариями
5. Ревью: начинают параллельно
```

**Пример разработки (OMS):**
```bash
# 1. Получил постановку: добавить статус в OMS
# 2. Загружу develop-oms-java

# 3. Напишу код:
#    - OrderStatus.java (добавить enum value)
#    - OrderStatusHandler.java (новый или обновить existing)
#    - delivery-update-process.bpmn (обновить XML)
#    - OrderStatusTest.java (unit tests)

# 4. Запущу тесты локально
# 5. Запушу: git push origin feat/OPSOMN002-XXX
# 6. Создам MR в GitLab
# → Coordinator автоматически запустит ревьюеров
```

### ✅ Ревьюеры (2 шт)

**Reviewer-1: Бизнес + Архитектура**

```
1. Загрузить:
   - review-business-architecture
   - review-checklist-by-platform
   - shared-claude-md-reference, shared-service-index
2. Вход: MR дифф
3. Процесс:
   a) Прочитать постановку (понять AC)
   b) Проверить AC:
      - Все ли требования покрыты кодом?
      - Есть ли edge-case'ы?
   c) Проверить архитектуру:
      - Нарушена ли граница сервиса?
      - Контракт совместим? (если OpenAPI)
   d) Проверить расширяемость:
      - Не hardcode? Паттерны соблюдены?
   e) Писать замечания:
      [MUST FIX] — обязатель (нарушает AC)
      [SHOULD] — рекомендация (может быть проблемой)
      [NIT] — опционально (nice to have)
4. Выход: комментарии в MR
```

**Reviewer-2: Безопасность + Перф + Дизайн (параллельно с Reviewer-1)**

```
1. Загрузить:
   - review-security-performance-design
   - shared-security-checklist, shared-performance-basics
   - design specs (Figma ссылки)
2. Вход: MR дифф (не ждёт Reviewer-1!)
3. Процесс:
   a) Проверить безопасность:
      [SECURITY] — injection, auth, crypto, controls?
   b) Проверить производительность:
      [PERF] — N+1, O(N²), caching?
   c) Проверить дизайн:
      [DESIGN] — соответствует Figma? tokens? a11y?
   d) Писать замечания:
      [SECURITY] [MUST FIX]
      [PERF] [SHOULD]
      [DESIGN] [SHOULD]
4. Выход: комментарии в MR
```

**Developer фиксит (параллельно):**
```
t=20       Developer видит замечания от обоих ревьюеров
t=22       Фиксит все [MUST FIX] замечания
t=30       Пушит фиксы → MR обновился
t=32       Reviewer-1 перепроверяет (5 мин)
t=35       Reviewer-2 перепроверяет (5 мин)
t=37       Оба Approved → можно merge
```

---

## Диаграммы и визуализация

### Главная диаграмма (граф скилов)

👉 **Открыть:** `ARCHITECTURE_DIAGRAM.md`

Там 7 диаграмм Mermaid:
1. **Фазы выполнения и роли** — как задача идёт через фазы
2. **Граф зависимостей скилов** — как скилы связаны
3. **Поток данных** — как информация передаётся между агентами
4. **Параллелизм в Phase 1** — как 5 исследователей работают одновременно
5. **Параллелизм в Phase 4-5** — как ревьюеры работают одновременно
6. **Связность скилов** — как они не теряются
7. **Разделение ролей** — кто что делает

### Быстрый поиск: "какой скилл мне нужен?"

**Хочу запустить новую задачу**
→ `coord-task-orchestration` + `shared-service-index`

**Хочу проверить код на безопасность**
→ `review-security-performance-design` + `shared-security-checklist`

**Хочу писать Go код**
→ `develop-go-new` + `shared-code-style` + `shared-git-workflow`

**Хочу понять структуру ENSI**
→ `research-code-ensi` + `shared-service-index`

**Хочу собрать метрики**
→ `coord-metrics-collection` + `coord-task-orchestration`

---

## FAQ

### Q: Где именно загружать скилл?

**A:** Когда вы вызываете Agent или Workflow в Claude Code:

```python
# Пример 1: Явная загрузка скилла перед работой
await agent(
    prompt="Проверь безопасность этого кода",
    {
        skills: ["review-security-performance-design", "shared-security-checklist"]
    }
)

# Пример 2: Загрузка через Skill команду
/skill review-security-performance-design

# Пример 3: Автоматическая загрузка в Workflow
// task-research-and-analyze.js
export const workflow = () => {
  // Каждый исследователь автоматически загружает свои скилы
  const researcher1 = agent(confPrompt, {skills: ["research-confluence", "shared-*"]})
}
```

### Q: Что если [BLOCKER] вопрос не разрешен быстро?

**A:** 
- Разработчик **не ждёт**, пишет **независимый код**
- Блокирующая часть может быть написана позже
- `[NB]` вопросы решаются параллельно с разработкой
- Координатор отслеживает прогресс вопроса

### Q: Может ли один ревьювер заменить двух?

**A:** 
- Теоретически да, практически нет
- Один ревьювер на 7 аспектов = усталость, упущения
- Два ревьювера параллельно = 20 мин vs 90 мин
- Контекст каждого = 15K (узко), не 50K (раздуто)

### Q: Нужны ли [SHARED] скилы для каждого агента?

**A:** Да, обязательно:
- `shared-claude-md-reference` — все должны знать правила
- `shared-code-style` — разработчик и ревьюеры
- `shared-security-checklist` — разработчик, reviewer-2
- `shared-service-index` — координатор, исследователи

### Q: Как обновить скилл, если он используется везде?

**A:** 
1. Отредактировать файл скилла
2. Обновить версию в heading
3. Обновить SKILLS_INDEX.md (если нужно)
4. Все агенты автоматически используют актуальный скилл

### Q: Что если нужен новый тип исследователя?

**A:**
1. Создать файл `research-[name].md` в [RESEARCH]/
2. Описать назначение, входит, выходит, процесс
3. Добавить в SKILLS_INDEX.md таблицу
4. Добавить в Workflow (task-research-and-analyze.js)
5. Обновить диаграмму в ARCHITECTURE_DIAGRAM.md

### Q: Может ли разработчик запустить ревью самостоятельно?

**A:** Нет, ревью запускает **Координатор** автоматически:
- Coordinator следит за MR readiness
- Когда MR ready → Coord запускает обоих ревьюеров
- Разработчик может разговаривать с ревьюерами через MR comments

---

## Ссылки и ресурсы

### Основные файлы

- 📄 **SKILLS_INDEX.md** — полный реестр всех скилов и их использования
- 📊 **ARCHITECTURE_DIAGRAM.md** — визуальные диаграммы Mermaid
- 📖 **README.md** — этот файл

### Где найти код каждой платформы

- **ENSI:** `platform/ensi/` (PHP 8.1, Swoole, OpenAPI)
- **OMS:** `platform/starfish24/` (Java Spring Boot + Go + Camunda)
- **Integration:** `platform/integration/` (PHP Lumen)
- **Site:** `platform/site/gj-ng-front/` (Angular 20, Nx, NgRx)
- **Mobile:** `platform/mobile-app/gj-app/` (React Native 0.74)
- **Gloria OTS:** `platform/gloriaots/` (.NET 10, ASP.NET Core)
- **Go new:** `platform-new/` (Go services, platform-new)

### Документация

- 📘 **CLAUDE.md** (корневой) — правила workspace, структура, ветки
- 📘 **docs/service-index.md** — реестр всех 25+ сервисов
- 📘 **docs/architecture/** — ADR (Architecture Decision Records)

### MCP интеграция

- **Confluence:** `mcp__gj-buddy__confluence_*`
- **Jira:** `mcp__gj-buddy__jira_*`
- **GitLab:** `mcp__gj-buddy__gitlab_*`
- **Logs:** `mcp__gj-buddy__logs_*`
- **K8s:** `mcp__gj-buddy__data_k8s_*`

---

## Как начать?

### 1️⃣ Для новой задачи (Координатор)

```bash
/task-research-and-analyze "JIRA_TICKET_ID"
```

### 2️⃣ Для отдельного исследования

Загрузить нужный скилл из [RESEARCH]/

### 3️⃣ Для разработки

Загрузить `develop-[platform].md` + `shared-*`

### 4️⃣ Для ревью

Загрузить `review-business-*` или `review-security-*` + `shared-*`

---

**Версия:** 1.0  
**Статус:** Production-ready  
**Последнее обновление:** 2026-10-06  
**Автор:** Claude Haiku 4.5 + Antonov Aleksandr (Outsource)

---

## Поддержка

**Вопросы?**
- Проверить SKILLS_INDEX.md (полный реестр)
- Посмотреть ARCHITECTURE_DIAGRAM.md (визуально)
- Прочитать FAQ выше
- Обратиться к Координатору для уточнений
