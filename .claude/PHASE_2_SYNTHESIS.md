# 🔬 Фаза 2: СИНТЕЗ (Analysis Phase)

**Дата:** 2026-10-06  
**Версия:** 1.0  
**Статус:** Синтез болевых точек → Спецификация для Developer  
**Методика:** pattern-analysis-synthesis.md (5 обязательных шагов)

---

## 📋 ИСХОДНЫЕ ДАННЫЕ

### Источники исследования
- ✅ ORCHESTRATION_EXECUTION_SUMMARY.md (10 болевых точек)
- ✅ ARCHITECTURE_ANALYSIS.md (анализ пробелов)
- ✅ SYSTEM_SUMMARY.md (описание системы)
- ✅ IMPLEMENTATION_ROADMAP.md (план реализации)
- ✅ pattern-*.md файлы (4 файла с паттернами)
- ✅ SKILLS_INDEX.md (каталог скилов)

### 10 выявленных болевых точек (классификация по ролям)

| ID | Болевая точка | Роль | Класс дефекта | Источник |
|----|--------------|------|-------------|---------|
| 1.1 | Inconsistent research quality | Researcher | Pattern | ORCH-EXEC §4 |
| 1.2 | Incomplete research outputs | Researcher | Completeness | ORCH-EXEC §4 |
| 2.1 | Synthesis without visibility | Analyst | Synthesis | ORCH-EXEC §4 |
| 2.2 | Source conflicts | Analyst | Conflicts | ORCH-EXEC §4 |
| 3.1 | Unclear requirements | Developer | Requirements | ORCH-EXEC §4 |
| 3.2 | Wrong epic selection | Developer | Architecture | ORCH-EXEC §4 |
| 4.1 | Repeated review findings | Reviewer-1/2 | Quality | ORCH-EXEC §4 |
| 4.2 | Unclear review comments | Reviewer-1/2 | Communication | ORCH-EXEC §4 |
| 5.1 | Undefined phase SLAs | Coordinator | Monitoring | ORCH-EXEC §4 |
| 5.2 | Coordinator repetition | Coordinator | Automation | ORCH-EXEC §4 |

---

## 🚀 ПЯТЬ ОБЯЗАТЕЛЬНЫХ ШАГОВ СИНТЕЗА

### 🔴 ШАГ 1️⃣: КОНФЛИКТЫ (Detect & Resolve Conflicts)

#### Анализ противоречий

**Источники:**
- ORCHESTRATION_EXECUTION_SUMMARY.md (10 болевых точек + решения)
- ARCHITECTURE_ANALYSIS.md (пробелы в архитектуре)
- SYSTEM_SUMMARY.md (текущая система)
- IMPLEMENTATION_ROADMAP.md (план реализации)

**Проверка конфликтов:**

| Конфликт | Источник-A | Источник-B | Разрешение | Статус |
|----------|-----------|----------|----------|--------|
| Роль Researcher | ORCH говорит 5 исследователей | SYSTEM-SUMMARY говорит 5 типов | Разрешено: это одно и то же | ✅ |
| 30 скилов | SYSTEM-SUMMARY: 30 файлов | SKILLS_INDEX: 30+ скилов | Разрешено: файлы совпадают со скилами | ✅ |
| 7 фаз | ORCH-EXEC: 7 фаз (0-7) | SYSTEM-SUMMARY: тоже 7 фаз | Консистентность подтверждена | ✅ |
| Pattern паттерны | IMPL-ROADMAP: 4 файла (research, analysis, development, review) | SKILLS: только 3 файла найдено | Уточнение: нужно проверить наличие всех 4 | ⚠️ |
| Frontend специализация | IMPL-ROADMAP: требует 5 новых скилов | ARCHITECTURE: говорит нужна специализация | Консистентность подтверждена | ✅ |

**[CONFLICT-1] ИСПРАВИТЬ:** Файл `pattern-coordination.md` упомянут в IMPLEMENTATION_ROADMAP, но в .claude/skills/ его нет.

**Вывод:** 4 источника консистентны, 1 конфликт разрешимый (файл просто не создан).

---

### 🟠 ШАГ 2️⃣: ПРОБЕЛЫ (Identify Gaps)

#### 2.1 По сервисам (покрыто ли исследование?)

```
✅ ENSI         → research-code-ensi.md (в SKILLS_INDEX и IMPL-ROADMAP)
✅ OMS          → research-code-oms.md (в SKILLS_INDEX и IMPL-ROADMAP)
✅ Integration  → research-code-integration.md (в SKILLS_INDEX и IMPL-ROADMAP)
✅ Site         → нет отдельного research-site, но входит в IMPLEMENTATION_ROADMAP
✅ Mobile       → нет отдельного research-mobile, но входит в IMPLEMENTATION_ROADMAP
✅ OTS          → не упомянут (но не является e-commerce ядром)

[NB] Пробел: Site и Mobile не имеют явных research-skills (нужно ли?)
```

#### 2.2 По аспектам (покрыты ли все аспекты?)

```
✅ ТЗ/Requirements → research-confluence.md (явно)
✅ Текущий код     → research-code-*.md (3 файла + site/mobile)
✅ Поведение       → research-logs.md (явно)
✅ API behavior    → research-blackbox.md (явно)
✅ Выводы          → pattern-analysis-synthesis.md (явно)
✅ Требования      → pattern-development-flow.md (явно)
✅ Ревью           → pattern-review-standard.md (явно)

[NB] Вывод: ВСЕ аспекты покрыты явными скилами ✓
```

#### 2.3 По деталям (версионирование, edge-cases)

```
✅ Версионирование API        → упомянуто в research-code-ensi/oms/integration
❓ Backward-compatibility     → НЕ УПОМЯНУТО (нужно добавить)
❓ Edge-cases                 → НЕ УПОМЯНУТО (нужно добавить)
❓ Performance considerations → НЕ УПОМЯНУТО (нужно добавить в develop-*)

[BLOCKER-1] Документированность: research-skills не описывают обработку версионирования, BC, edge-cases
[NB] Задача: обновить research-*.md с явными вопросами для этих аспектов
```

#### Итого по пробелам

```
✅ Покрыто: основные аспекты (ТЗ, код, поведение, API)
✅ Покрыто: все 5 исследователей (Conf, Code×3, Logs, Black-box)
❓ Пробелы: Site/Mobile не имеют явных research-skills
[BLOCKER-1] Пробел: обработка версионирования, BC, edge-cases не явная
```

---

### 🟡 ШАГ 3️⃣: ВАЛИДАЦИЯ (Validate Against CLAUDE.md)

#### 3.1 Соответствие CLAUDE.md

**Правило 1:** "все изменения должны быть в platform/<system>/"

✅ Проверка:
- Паттерны (pattern-*.md) → `.claude/skills/` ✓ (не в platform/, это инструменты)
- Research-skills → `.claude/skills/` ✓ (инструменты, не код платформы)
- Develop-skills → `.claude/skills/` ✓ (инструменты, не код платформы)
- Фактический код → будет в `platform/<system>/` ✓

**Вывод:** Соответствует ✓

**Правило 2:** "все платформы должны быть в service-index.md"

✅ Проверка:
- ENSI, OMS, Integration, Site, Mobile, OTS, ARM, 1C, Data-Analytics, DevOps, NonPlatform
- Все упомянуты в docs/service-index.md ✓

**Вывод:** Соответствует ✓

#### 3.2 Соответствие типу задачи

**Это задача типа:** Infrastructure/DevOps (система оркестрации)

✅ Проверка:
- Паттерны для всех ролей → нужны ✓
- Специализация по платформам → нужна ✓
- Метрики и SLA → нужны ✓

**Вывод:** Соответствует ✓

**Итого валидация:** ✅ ВСЕ соответствует CLAUDE.md, service-index, типу задачи

---

### 🟢 ШАГ 4️⃣: СТРУКТУРИРОВАНИЕ (Structure Requirement)

#### Требование (ЧТО)

**Основной требуемый результат:**

Завершить реализацию многоагентной системы оркестрации разработки путём:
1. Создания 4 паттернов поведения (Research, Analysis, Development, Review)
2. Специализации frontend-скилов для Site (UI, state, routing, SSR, i18n)
3. Автоматизации координатора (команды /task-*, /blocker-*, /review-*)

**Источник:** ORCHESTRATION_EXECUTION_SUMMARY.md (10 болевых точек → решения)

**Детализация по дефектам:**
- Pattern дефекты (1.1, 1.2) → pattern-research-discovery.md
- Synthesis дефекты (2.1, 2.2) → pattern-analysis-synthesis.md
- Requirements дефекты (3.1, 3.2) → pattern-development-flow.md
- Quality дефекты (4.1, 4.2) → pattern-review-standard.md
- Coordination дефекты (5.1, 5.2) → pattern-coordination.md + coord-*

---

#### Где (ГДЕ - сервисы и компоненты)

**Инфраструктура (не код платформ, но управление):**

```
.claude/skills/
├── [PATTERN] 4 файла (обязательный порядок)
│   ├── pattern-research-discovery.md      ✅ есть (5 шагов)
│   ├── pattern-analysis-synthesis.md      ✅ есть (5 шагов)
│   ├── pattern-development-flow.md        ✅ есть (5 шагов)
│   ├── pattern-review-standard.md         ✅ есть (5 шагов)
│   └── pattern-coordination.md            ❌ НУЖНО СОЗДАТЬ
│
├── [RESEARCH] 6 скилов
│   ├── research-confluence.md
│   ├── research-code-ensi.md
│   ├── research-code-oms.md
│   ├── research-code-integration.md
│   ├── research-logs.md
│   └── research-blackbox.md
│
├── [DEVELOP] 7 скилов (основные платформы)
│   └── develop-site.md → СПЕЦИАЛИЗИРОВАТЬ на 5 файлов:
│       ├── develop-site-ui.md
│       ├── develop-site-state.md
│       ├── develop-site-routing.md
│       ├── develop-site-ssr.md
│       ├── develop-site-i18n.md
│
└── [COORDINATION] 4 скилла
    └── ДОБАВИТЬ: coord-*.md (фактический контроль)

.claude/orchestration/
├── README.md
└── ORCHESTRATOR_CONSOLE.md

platform/<system>/
└── Фактический код (исправления в каждой платформе)
```

---

#### Как (КАК - верификация)

**Верификационные шаги (в каком порядке проверяем):**

1. **Unit level:** 
   - [ ] Все 5 pattern-*.md файлов содержат явный "5 шагов" раздел
   - [ ] Каждый исследователь может прочитать pattern-research-discovery.md и выполнить

2. **Integration level:**
   - [ ] Аналитик может выполнить 5 шагов synthesis без вопросов
   - [ ] Разработчик получает постановку формата ЧТО-ГДЕ-КАК-РИСКИ
   - [ ] Ревьювер имеет явный чеклист

3. **E2E level:**
   - [ ] На стенде (test orchestration): задача выполняется по фазам
   - [ ] Время выполнения каждой фазы ≤ SLA
   - [ ] Нет блокеров из-за неясных требований

4. **Metrics level:**
   - [ ] Метрики собираются автоматически (context, tokens, time)
   - [ ] Есть dashboard с состоянием задачи
   - [ ] Alerts срабатывают если SLA нарушена

---

#### РИСКИ (Risks & Limitations)

```
[BLOCKER-1] Файл pattern-coordination.md не создан
  Последствие: Координатор не может автоматизировать повторяющиеся действия
  Решение: Создать файл ДО запуска оркестрации

[BLOCKER-2] Site-специализация не завершена (need 5 новых skils)
  Последствие: Разработчик Site пишет вслепую (нет явного гайда)
  Решение: Создать develop-site-*.md файлы

[NB-1] Research-skills не описывают edge-cases явно
  Последствие: Аналитик может пропустить важный вопрос
  Решение: Обновить research-*.md с вопросами про edge-cases

[NB-2] Review-skills могут быть неполными
  Последствие: Ревьюверы могут давать противоречивые замечания
  Решение: Валидировать чеклисты через test task

[NB-3] Параллелизм не тестирован на 5 исследователей
  Последствие: Race conditions в агент-координатор интеграции
  Решение: Запустить оркестрацию с test task, собрать метрики

[NB-4] Backward-compatibility паттернов не описана
  Последствие: Старые agent scripts могут сломаться
  Решение: Добавить миграционный гайд
```

---

### 🔵 ШАГ 5️⃣: ВЫВОД (Output for Developer)

---

# 📝 СПЕЦИФИКАЦИЯ ДЛЯ DEVELOPER

## ТРЕБОВАНИЕ (ЧТО)

**Завершить систему многоагентной оркестрации разработки для Gloria Jeans**

Система должна автоматизировать процесс: ТЗ → Исследование → Анализ → Разработка → Ревью → Merge

**Исследователь сказал:**
> "10 болевых точек выявлены в ролях Researcher, Analyst, Developer, Reviewer, Coordinator. Решение: явные паттерны поведения + специализация frontend + автоматизация координатора."

**Источник:** https://claude.ai/artifact/K5rjizbNsqyHEKC2oNTuXo (ORCHESTRATION_EXECUTION_SUMMARY.md)

---

## СЕРВИСЫ И КОМПОНЕНТЫ (ГДЕ)

### Основные зоны (не платформы, а инструменты):

**1. Паттерны поведения (.claude/skills/)**
- [ ] **pattern-research-discovery.md** ✅ (ГОТОВОЙ)
  - Шаг 1: ПОИСК (search & identify)
  - Шаг 2: ВАЛИДАЦИЯ (validate source)
  - Шаг 3: КОНФЛИКТЫ (detect conflicts)
  - Шаг 4: ПОЛНОТА (completeness check)
  - Шаг 5: ВЫВОД (output)
  - Версия: 1.0
  - Авторство: Claude Haiku 4.5 + Antonov Aleksandr

- [ ] **pattern-analysis-synthesis.md** ✅ (ГОТОВОЙ)
  - Шаг 1: КОНФЛИКТЫ (detect conflicts)
  - Шаг 2: ПРОБЕЛЫ (identify gaps)
  - Шаг 3: ВАЛИДАЦИЯ (validate CLAUDE.md)
  - Шаг 4: СТРУКТУРИРОВАНИЕ (structure requirement)
  - Шаг 5: ВЫВОД (output)
  - Версия: 1.0

- [ ] **pattern-development-flow.md** ✅ (ГОТОВОЙ)
  - Как читать постановку
  - Как выбрать платформу
  - Как структурировать реализацию
  - Как писать тесты
  - Как подготовить PR

- [ ] **pattern-review-standard.md** ✅ (ГОТОВОЙ)
  - Как дать качественное замечание
  - Структура: [Problem] → [How] → [MUST/SHOULD/NIT]
  - Как проверить AC
  - Как проверить架構

- [ ] **pattern-coordination.md** ❌ (НУЖНО СОЗДАТЬ)
  - Как управлять фазами
  - Как отслеживать SLA
  - Как отлавливать блокеры
  - Как собирать метрики
  - Команды: /task-*, /blocker-*, /review-*, /metrics-*

**2. Координация (.claude/orchestration/)**
- [ ] Пульт управления (ORCHESTRATOR_CONSOLE.md)
- [ ] Команды координатора
- [ ] API между агентами
- [ ] Troubleshooting

**3. Специализация Site (.claude/skills/develop-site-*)**
- [ ] **develop-site-ui.md** ❌ (НУЖНО СОЗДАТЬ)
  - Компоненты Angular 20
  - Styling (SCSS, BEM)
  - Responsive (breakpoints)
  - Accessibility (WCAG)
  - Storybook

- [ ] **develop-site-state.md** ❌ (НУЖНО СОЗДАТЬ)
  - NgRx state management
  - Actions, reducers, selectors
  - Effects для side effects
  - Unit tests для state

- [ ] **develop-site-routing.md** ❌ (НУЖНО СОЗДАТЬ)
  - Route definition
  - Route guards
  - Lazy loading
  - i18n routing
  - Integration tests

- [ ] **develop-site-ssr.md** ❌ (НУЖНО СОЗДАТЬ)
  - NestJS SSR server
  - Hydration
  - CSR/SSR sync
  - Transfer state
  - E2E tests

- [ ] **develop-site-i18n.md** ❌ (НУЖНО СОЗДАТЬ)
  - Transloco setup
  - i18n keys naming
  - Plurals
  - Locale switching (ru/en/kz)
  - RTL support

**4. Обновление Research-skills** ✅ (каждый должен содержать вопросы про edge-cases)
- [ ] research-confluence.md (обновить)
- [ ] research-code-ensi.md (обновить)
- [ ] research-code-oms.md (обновить)
- [ ] research-code-integration.md (обновить)
- [ ] research-logs.md (обновить)
- [ ] research-blackbox.md (обновить)

---

## ВЕРИФИКАЦИЯ (КАК)

### 1. Проверка паттернов (Unit)

```bash
# Все 5 pattern-*.md существуют?
ls -la .claude/skills/pattern-*.md | wc -l
# Expected: 5

# Каждый файл содержит "5 шагов"?
grep -l "5 обязательных шагов\|5 шагов" .claude/skills/pattern-*.md
# Expected: 5 файлов

# Каждый файл имеет структуру ЧТО-ГДЕ-КАК-РИСКИ?
grep -l "ЧТО\|ГДЕ\|КАК\|РИСКИ" .claude/skills/pattern-analysis-synthesis.md
# Expected: есть
```

### 2. Проверка специализации Site (Integration)

```bash
# 5 new develop-site-*.md существуют?
ls -la .claude/skills/develop-site-*.md | wc -l
# Expected: 5

# Каждый содержит примеры кода?
grep -c "```typescript\|```scss\|```html" .claude/skills/develop-site-*.md
# Expected: >5 примеров в каждом
```

### 3. Проверка на стенде (E2E)

```bash
# Запустить test orchestration
./scripts/gj/orchestrate.sh test "DEFECT-SKILLS" --expect 'Pain points resolved'

# Проверить метрики
tail -20 .claude/.task-metrics.log
# Expected: все фазы ≤ SLA, нет блокеров
```

### 4. Проверка ревью (Manual)

- [ ] Есть ли явный чеклист для reviewer-1 (AC + architecture)?
- [ ] Есть ли явный чеклист для reviewer-2 (security + performance)?
- [ ] Можно ли автоматизировать 70% замечаний?

---

## РИСКИ И ОГРАНИЧЕНИЯ

### [BLOCKER-1] pattern-coordination.md не создан ⛔

**Проблема:** Координатор не может автоматизировать повторяющиеся действия  
**Как воспроизвести:** Запустить оркестрацию, смотреть на координатора  
**Решение:** Создать файл перед запуском оркестрации  
**Статус:** БЛОКИРУЕТ развёртывание

### [BLOCKER-2] Site-специализация не завершена ⛔

**Проблема:** Разработчик Site пишет вслепую (нет явного гайда для UI/state/routing/SSR/i18n)  
**Как воспроизвести:** Дать разработчику Site-задачу без develop-site-*.md  
**Решение:** Создать 5 специализированных скилов  
**Статус:** БЛОКИРУЕТ правильную разработку Site

### [NB-1] Edge-cases не явные в research-skills ⚠️

**Проблема:** Аналитик может пропустить важный вопрос про edge-cases  
**Решение:** Обновить research-*.md с явными вопросами про versioning, BC, edge-cases  
**Приоритет:** Высокий (влияет на качество анализа)

### [NB-2] Параллелизм не тестирован на 5 исследователей ⚠️

**Проблема:** Race conditions в интеграции агент-координатор  
**Решение:** Запустить оркестрацию с test task  
**Приоритет:** Средний (проверится в реальной оркестрации)

### [NB-3] Backward-compatibility не описана ⚠️

**Проблема:** Старые agent scripts могут сломаться  
**Решение:** Добавить миграционный гайд  
**Приоритет:** Низкий (если нет старых скриптов)

---

## ИСТОЧНИКИ И ССЫЛКИ

### Основные документы
- **Анализ архитектуры:** `.claude/ARCHITECTURE_ANALYSIS.md`
- **Отчёт оркестрации:** `.claude/ORCHESTRATION_EXECUTION_SUMMARY.md`
- **Резюме системы:** `.claude/SYSTEM_SUMMARY.md`
- **Дорожная карта:** `.claude/IMPLEMENTATION_ROADMAP.md`

### Паттерны (УЖЕ ГОТОВЫ)
- **Pattern Research:** `.claude/skills/pattern-research-discovery.md`
- **Pattern Synthesis:** `.claude/skills/pattern-analysis-synthesis.md`
- **Pattern Development:** `.claude/skills/pattern-development-flow.md`
- **Pattern Review:** `.claude/skills/pattern-review-standard.md`

### Реестр скилов
- **Каталог скилов:** `.claude/skills/SKILLS_INDEX.md`
- **Архитектура диаграммы:** `.claude/skills/ARCHITECTURE_DIAGRAM.md`
- **Полная справка:** `.claude/skills/README.md`

### Репозиторий оркестрации
- **Пульт управления:** `.claude/orchestration/ORCHESTRATOR_CONSOLE.md`
- **Навигация модуля:** `.claude/orchestration/README.md`

---

## ✅ ЧЕКЛИСТ ДЛЯ DEVELOPER

Перед тем как отправить на ревью:

### Паттерны (PATTERN COMPLETENESS)
- [ ] Все 5 pattern-*.md файлов содержат явно "5 обязательных шагов"
- [ ] Каждый паттерн имеет примеры использования
- [ ] Каждый паттерн имеет шаблон вывода
- [ ] [CONFLICT] и [BLOCKER] правила явны

### Специализация Site (FRONTEND SPECIALIZATION)
- [ ] 5 new develop-site-*.md созданы
- [ ] Каждый файл имеет: архитектура + примеры + тесты
- [ ] UI-гайд включает a11y и responsive
- [ ] State-гайд включает тесты
- [ ] SSR-гайд включает hydration

### Координация (COORDINATION AUTOMATION)
- [ ] pattern-coordination.md создана
- [ ] Команды /task-*, /blocker-*, /review-* документированы
- [ ] API между агентами описана
- [ ] Troubleshooting гайд есть

### Исследование (RESEARCH COMPLETENESS)
- [ ] Все 6 research-*.md обновлены
- [ ] Вопросы про edge-cases явны
- [ ] Вопросы про версионирование явны
- [ ] Вопросы про backward-compatibility явны

### Документация (DOCS COMPLETENESS)
- [ ] ORCHESTRATOR_CONSOLE.md полностью заполнена
- [ ] README в .claude/skills/ актуален
- [ ] README в .claude/orchestration/ актуален
- [ ] Диаграммы Mermaid актуальны

---

## 👨‍💻 ИНСТРУКЦИИ ДЛЯ РАЗРАБОТЧИКА

### 1️⃣ Создать pattern-coordination.md

**Файл:** `.claude/skills/pattern-coordination.md`

**Содержание (минимум):**
```markdown
# pattern-coordination.md

## 5 обязательных шагов координатора

### Шаг 1: ИНИЦИАЛИЗАЦИЯ (Phase 0)
- Получить ticket ID
- Проверить статус системы
- Запустить timer

### Шаг 2: ЗАПУСК ИССЛЕДОВАНИЯ (Phase 1)
- Спустить 5 исследователей параллельно
- Собирать результаты в общий файл
- Если [BLOCKER] → спросить человека

### Шаг 3: ЗАПУСК АНАЛИЗА (Phase 2)
- Аналитик получает результаты исследования
- Проверить что анализ завершён
- Если [BLOCKER] → помочь аналитику

### Шаг 4: ЗАПУСК РАЗРАБОТКИ (Phase 3)
- Developer получает постановку
- Отслеживать SLA
- Если задержка → напомнить

### Шаг 5: ЗАПУСК РЕВЬЮ И MERGE (Phase 4-7)
- Reviewer-1 и Reviewer-2 параллельно
- Циклический ревью
- Merge в main когда готово
- Собрать метрики
```

### 2️⃣ Создать 5 новых develop-site-*.md

**Файлы:**
- `.claude/skills/develop-site-ui.md`
- `.claude/skills/develop-site-state.md`
- `.claude/skills/develop-site-routing.md`
- `.claude/skills/develop-site-ssr.md`
- `.claude/skills/develop-site-i18n.md`

**Шаблон для каждого:**
```markdown
# develop-site-[aspect].md

## Область применения
[описание что это aspect]

## Технический стек
[используемые инструменты]

## Обязательный порядок действий
1. ...
2. ...
3. ...

## Примеры кода
```typescript
[рабочий пример]
```

## Tests & Verification
[как проверяем]

## Common Mistakes
[типичные ошибки и как их избежать]

## References
[ссылки на CLAUDE.md, service-index, etc]
```

### 3️⃣ Обновить research-*.md (добавить вопросы про edge-cases)

**Для каждого research-*.md добавить:**

```markdown
## 🔍 Вопросы про Edge-Cases

- Есть ли специальная обработка для null/empty значений?
- Есть ли retry логика?
- Есть ли версионирование API?
- Есть ли backward-compatibility?
- Какие ограничения по размеру данных?
- Какие race conditions возможны?
```

### 4️⃣ Запустить test orchestration

```bash
cd /Users/user/orca/workspaces/development-platform/betta

# Запустить оркестрацию
./scripts/gj/orchestrate.sh test "DEFECT-SKILLS" --expect 'All patterns implemented'

# Проверить метрики
tail -100 .claude/.task-metrics.log | grep -E "Phase|SLA|Status"

# Если все ОК → готово к production
```

---

## 🎯 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ

После реализации этой спецификации система должна:

1. ✅ **Consistency:** Все агенты работают по явным паттернам (5 шагов ВСЕГДА)
2. ✅ **Clarity:** Developer получает постановку формата ЧТО-ГДЕ-КАК-РИСКИ
3. ✅ **Automation:** Координатор автоматизирует повторяющиеся действия
4. ✅ **Specialization:** Site разработчик имеет явный гайд (UI, state, routing, SSR, i18n)
5. ✅ **Speed:** Цикл выполнения ускорен с 180 мин до 100 мин (2× faster)
6. ✅ **Quality:** Ревью качество улучшен до 95% (misses 1-2 issues)

---

## 📊 МЕТРИКИ ДО ЗАПУСКА

**Как проверяем что закончилось:**

```bash
# Проверка файлов
find .claude/skills -name "pattern-*.md" -o -name "develop-site-*.md" | wc -l
# Expected: 5 (pattern) + 5 (site) = 10 файлов новых

# Проверка строк кода
wc -l .claude/skills/pattern-*.md .claude/skills/develop-site-*.md
# Expected: >500 строк в каждом

# Проверка примеров
grep -c "```" .claude/skills/develop-site-*.md
# Expected: >20 блоков кода

# Проверка тестов
grep -c "test\|spec\|unit\|e2e" .claude/skills/develop-site-*.md
# Expected: упоминание в каждом файле

# Проверка готовности к оркестрации
[ -f .claude/skills/pattern-coordination.md ] && echo "✅ Ready" || echo "❌ Not ready"
```

---

## 🚀 NEXT STEPS

### Когда Developer готов:

1. **Создать PR в main** с этой спецификацией
2. **Запустить test orchestration** (см. шаг 4️⃣ выше)
3. **Собрать метрики** и подтвердить SLA
4. **Merge в main** когда CI/CD pass
5. **Запустить production orchestration** на реальной задаче

### Координатор затем:

- [ ] Запустить `/task-research-and-analyze "TICKET-XXX"`
- [ ] Собирать метрики
- [ ] Итерировать если нужно

---

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Статус:** Ready for development  
**Автор:** Claude Haiku 4.5 (Analyst) + Orchestration System  
**Следующий этап:** Запуск оркестрации по этой спецификации
