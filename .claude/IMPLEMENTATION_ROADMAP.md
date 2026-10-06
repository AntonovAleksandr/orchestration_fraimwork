# 🗺️ План реализации улучшений архитектуры

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Сроки:** 4-8 дней (3 фазы)

---

## 📋 Фаза 1: Паттернизация поведения (2 дня)

### Шаг 1.1: Создать pattern-research-discovery.md

```markdown
# pattern-research-discovery.md

[RESEARCH] Явный паттерн исследования

**Используется:** всеми исследователями (Conf, Code×3, Logs, Black-box)

## 5 обязательных шагов

### 1️⃣ ПОИСК (search & identify)
- Определить ключевые слова (сущности, сервисы, API)
- Поиск в источнике по ключевым словам
- Выписать релевантные куски ТУТ ЖЕ с цитатами

### 2️⃣ ВАЛИДАЦИЯ (validate source)
- Дата источника: актуально ли? (не старше 2 недель)
- Branch/версия: правильная ли? (master/release/develop?)
- Авторство: кто писал? Доверяем ли?

### 3️⃣ КОНФЛИКТЫ (detect conflicts)
- Есть ли противоречия в этом источнике?
- Есть ли противоречия с другими выводами?
- Отметить как [CONFLICT] если есть

### 4️⃣ ПОЛНОТА (completeness check)
- Хватает ли информации?
- Есть ли пробелы? Где?
- Нужна ли доинформация? Отметить [BLOCKER]

### 5️⃣ ВЫВОД (output)
- Структурированный отчёт
- Ссылки на источники
- [BLOCKER] и [NB] вопросы явно
- Оформление: markdown, читаемо

## Шаблон вывода

```
# [Research Type] Исследование

**Источник:** [ссылка, дата, версия]
**Статус:** [актуально/потенциально устарело/конфликт]

## Ключевые факты
- факт 1 (цитата)
- факт 2 (цитата)

## Конфликты
- конфликт 1: источник-A говорит X, источник-B говорит Y
- конфликт 2: ...

## Полнота
- ✅ покрыто: X
- ❓ пробел: Y (нужна информация)

## Вопросы
- [BLOCKER] вопрос 1?
- [NB] вопрос 2?
```
```

### Шаг 1.2: Обновить research-*.md файлы

**Изменения:**
1. В начало каждого файла добавить: "Следуй pattern-research-discovery.md ВСЕГДА"
2. Добавить раздел "Обязательный порядок шагов"
3. Добавить шаблон вывода

**Файлы для обновления:**
- research-confluence.md
- research-code-ensi.md
- research-code-oms.md
- research-code-integration.md
- research-logs.md
- research-blackbox.md

### Шаг 1.3: Создать pattern-analysis-synthesis.md

```markdown
# pattern-analysis-synthesis.md

[ANALYSIS] Явный паттерн синтеза

**Используется:** аналитиком

## 5 обязательных шагов

### 1️⃣ КОНФЛИКТЫ (detect conflicts)
Для каждого вывода исследователя:
- есть ли противоречие с другими выводами?
- отметить [CONFLICT] если есть
- попробовать разрешить через анализ

### 2️⃣ ПРОБЕЛЫ (identify gaps)
- Покрыты ли все сервисы? (ГДЕ исследование?)
- Покрыты ли все API? (КАК исследование?)
- Есть ли пробелы в ТЗ? (ЧТО исследование?)

### 3️⃣ ВАЛИДАЦИЯ (validate against CLAUDE.md)
- Соответствует ли CLAUDE.md?
- Соответствует ли service-index?
- Соответствует ли типу задачи?

### 4️⃣ СТРУКТУРИРОВАНИЕ (structure requirement)
- Раздел ЧТО: требование (из ТЗ + выводы)
- Раздел ГДЕ: сервисы и компоненты (из Code-researchers)
- Раздел КАК: tests, verification (из analysis)
- Раздел РИСКИ: limitations, [BLOCKER]'s

### 5️⃣ ВЫВОД (output)
- Постановка структурирована
- [BLOCKER] вопросы явны
- [NB] вопросы явны
```

### Шаг 1.4: Обновить analyze-*.md файлы

**Изменения:**
1. Добавить ссылку на pattern-analysis-synthesis.md
2. Обновить процесс: явно КОНФЛИКТЫ → ПРОБЕЛЫ → ВАЛИДАЦИЯ → СТРУКТУРИРОВАНИЕ → ВЫВОД

**Файлы для обновления:**
- analyze-synthesis.md
- analyze-requirements.md
- analyze-blockers.md

### Результат Фазы 1

✅ Исследователи работают по явному паттерну (ВСЕГДА 5 шагов)  
✅ Аналитик работает по явному паттерну (ВСЕГДА 5 шагов)  
✅ Нет дополнительных вопросов "как делать?"

---

## 📐 Фаза 2: Frontend специализация (2-3 дня)

### Шаг 2.1: Создать пять специализированных скилов для Site

**Файлы для создания:**

```
develop-site-ui.md
  ├─ Компоненты (Angular components)
  ├─ Styling (SCSS, BEM, design-tokens)
  ├─ Responsive (breakpoints, mobile-first)
  ├─ Accessibility (aria-labels, WCAG)
  ├─ Storybook (stories для всех вариантов)
  └─ Performance (lighthouse checks)

develop-site-state.md
  ├─ NgRx state (interface + initial state)
  ├─ Actions (typed actions, payload)
  ├─ Reducer (immutable updates)
  ├─ Selectors (memoized selectors)
  ├─ Effects (side effects, error handling)
  └─ Tests (unit tests, marble testing)

develop-site-routing.md
  ├─ Routes definition (AppRoutingModule)
  ├─ Route guards (CanActivate, CanDeactivate)
  ├─ Lazy loading (loadChildren)
  ├─ Navigation (Router, routerLink)
  ├─ i18n in routes (locale prefix)
  └─ Tests (integration tests)

develop-site-ssr.md
  ├─ NestJS SSR server (main.server.ts)
  ├─ Hydration (transfer state)
  ├─ Platform detection (isPlatformBrowser)
  ├─ CSR/SSR sync (state transfer)
  └─ Tests (e2e tests)

develop-site-i18n.md
  ├─ Transloco setup
  ├─ i18n keys (naming convention)
  ├─ Plurals (plural rules)
  ├─ Locale switching (ru/en/kz)
  ├─ RTL support (if needed)
  └─ Tests (translation tests)

develop-site-testing.md
  ├─ Jest (unit tests)
  ├─ Cypress (e2e tests)
  ├─ Storybook (visual tests)
  ├─ Lighthouse (performance audit)
  └─ a11y tests
```

### Шаг 2.2: Обновить develop-site.md

**Изменение:** переименовать в `develop-site-unified.md`

**Содержание:** high-level обзор, ссылки на специализированные скилы

```markdown
# develop-site-unified.md

[DEVELOPMENT] Unified overview для Site

**Когда использовать:** большие фичи которые трогают несколько областей

**Специализированные скилы (выбрать нужные):**
- develop-site-ui.md — UI компоненты
- develop-site-state.md — NgRx state
- develop-site-routing.md — маршрутизация
- develop-site-ssr.md — NestJS SSR
- develop-site-i18n.md — локализация
- develop-site-testing.md — все тесты

**Как выбрать скилл:**
- Пишешь компонент? → develop-site-ui.md
- Меняешь state? → develop-site-state.md
- Добавляешь route? → develop-site-routing.md
- ... и т.д.
```

### Шаг 2.3: Создать review-site-specialized.md

```markdown
# review-site-specialized.md

[REVIEW] Специализированные чеклисты для Site

**Reviewer-1 (бизнес + архитектура):**
- ✅ Компонент соответствует AC?
- ✅ Route guard логика верна?
- ✅ State структура правильная?
- ✅ Контракт с BFF совпадает?
- ✅ i18n ключи добавлены для всех текстов?
- ✅ Lazy loading использован правильно?
- ✅ SSR/CSR sync работает?

**Reviewer-2 (security + perf + design):**
- ✅ XSS: user input sanitized? (формы, поиск)
- ✅ CSRF: tokens есть? (forms in POST)
- ✅ a11y: aria-labels, role, tabindex?
- ✅ Perf: bundle size не увеличился? (webpack analyze)
- ✅ Lighthouse: score >90?
- ✅ Design: соответствует Figma? Colors, spacing, typography?
- ✅ Responsive: на мобиле работает?
- ✅ Dark mode: если используется?

**Платформенные чеклисты:**
- CSS: BEM, no !important, SCSS
- Tests: unit 80%+ coverage, e2e critical flows
- Build: no console.log, no debugger
```

### Шаг 2.4: Аналогично для Mobile и других платформ (опционально)

```
mobile-ui.md — React Native UI компоненты
mobile-state.md — Redux/RTK state
mobile-navigation.md — React Navigation
mobile-native.md — нативные модули
mobile-testing.md — Detox e2e тесты
```

### Результат Фазы 2

✅ Frontend задачи имеют явные специализированные скилы  
✅ Developer выбирает нужный скилл для своей задачи  
✅ Ревьюер использует специализированные чеклисты  
✅ Context каждого скилла ~4K вместо 20K

---

## 🎛️ Фаза 3: Паттерны координатора (2-3 дня)

### Шаг 3.1: Создать coord-task-launcher.md

```markdown
# coord-task-launcher.md

[COORDINATION] Как запускать задачу

**Используется:** координатором при /task-research-and-analyze

## Параметры запуска

```bash
/task-research-and-analyze "TICKET_ID" [опции]

Опции:
  --scope [comma-separated researchers]
    Примеры:
      default: conf,code-ensi,code-oms,code-int,logs,blackbox
      ensi-only: conf,code-ensi,logs
      urgent: code-oms,logs (только критичные)

  --priority [normal/high/critical]
    normal (default): обычный порядок
    high: инициализировать как VIP
    critical: запустить сейчас, skip prepartion

  --timeout [minutes]
    default: 30 мин для Phase 1
    Может быть меньше если scope меньший

Примеры:
  /task-research-and-analyze "OPSOMN002-100"
  /task-research-and-analyze "OPSOMN002-100" --scope "conf,code-oms,logs"
  /task-research-and-analyze "OPSOMN002-100" --priority critical
```
```

### Шаг 3.2: Создать coord-monitoring-pattern.md

```markdown
# coord-monitoring-pattern.md

[COORDINATION] Как мониторить задачу

**Используется:** координатором для track progress

## Интервалы мониторинга

```
Phase 1 (Research):
  t=0-10 мин: проверить каждые 5 мин
  t=10-25 мин: проверить каждые 10 мин (если все OK)
  Признаки проблемы: если какой-то researcher не движется >5 мин

Phase 2 (Analysis):
  t=0-5 мин: проверить 1 раз (в конце фазы)
  Признаки проблемы: если [BLOCKER] появился → спросить человека

Phase 3 (Development):
  t=0-30 мин: проверить каждые 10 мин (если параллель [NB] вопросы)
  Признаки проблемы: если Developer ждёт ответа > 15 мин → помочь аналитику

Phase 4-5 (Review):
  t=0 мин: проверить (начало ревью)
  t=10 мин: проверить (ревьюеры работают)
  t=20 мин: проверить (готовы замечания)
  Признаки проблемы: если ревьювер не дал замечания > 25 мин → remind
```
```

### Шаг 3.3: Создать coord-blocker-resolution.md

```markdown
# coord-blocker-resolution.md

[COORDINATION] Как разрешать [BLOCKER] вопросы

**Используется:** координатором + аналитиком

## Типы BLOCKER'ов и действия

```
Type 1: Информационный блокер
  Пример: "Какой контракт с OMS?"
  Действие:
    1. Аналитик пытается разрешить (читает research-code-oms)
    2. Если может разрешить → обновляет постановку
    3. Если нет → спрашивает человека

Type 2: Архитектурный блокер
  Пример: "Где должна быть эта логика? В OMS или Integration?"
  Действие:
    1. Аналитик спрашивает человека СРОЧНО
    2. Ждёт ответ
    3. Обновляет постановку

Type 3: Security блокер
  Пример: "Это SQL injection risk, как исправить?"
  Действие:
    1. Если базовая issue → разрешить через OWASP rules
    2. Если edge-case → спросить нужно ли в V1 или V2
    3. Обновляет постановку или помечает как V2

## Время ожидания

⏳ 0-5 мин: OK, подождать
⚠️  5-10 мин: проверить готов ли ответ
🚨 >15 мин: напомнить человеку (escalate)
```
```

### Шаг 3.4: Создать coord-metrics-interpretation.md

```markdown
# coord-metrics-interpretation.md

[COORDINATION] Как интерпретировать метрики

**Используется:** координатором при /task-metrics

## Анализ времени

```
Норма для типовой задачи (ENSI endpoint): 100 мин
  Phase 1: 25 мин (5 研究者 параллельно)
  Phase 2: 5 мин (анализ)
  Phase 3: 45 мин (разработка)
  Phase 4-5: 20 мин (1 цикл ревью)
  Phase 6-7: 5 мин (merge)

Если фаза быстрее:
  ✅ <20 мин Phase 1 → исследование было хорошо (можно повторить scope)
  ✅ <3 мин Phase 2 → нет конфликтов (постановка была ясна)
  ✅ <30 мин Phase 3 → простая задача, хороший разработчик

Если фаза медленнее:
  ⚠️  >30 мин Phase 1 → есть проблема (research завис?)
  ⚠️  >10 мин Phase 2 → много конфликтов (исследование неполное?)
  ⚠️  >80 мин Phase 3 → задача сложнее чем ожидалось
  ⚠️  >25 мин Phase 4-5 → много замечаний (постановка была неясна?)
```

## Анализ токенов

```
Норма: ~120K всего (60K researchers + 8K analyst + 20K developer + 30K reviewers + 2K coord)

Если меньше 100K:
  ✅ Эффективно! Есть что-то хорошее в процессе

Если больше 150K:
  ⚠️  Раздут где-то (context не оптимален, ищи где)
```

## Анализ качества ревью

```
Норма: 2-3 [MUST] замечания, 3-5 [SHOULD] замечания

Если 0-1 [MUST]:
  ✅ Отличная постановка (Developer написал правильно с первого раза)
  → Сохранить эту постановку как best-practice

Если 5+ [MUST]:
  ⚠️  Плохая постановка или сложная задача
  → Анализировать что не хватало в требованиях

Если много [NIT]:
  ⚠️  Ревьювер устал (может пропустить важное)
  → Напомнить сосредоточиться на важном
```

## Рекомендации

Показывать координатору:
- ✅ Что прошло хорошо (метрика < норма)
- ⚠️  Что медленнее (метрика > норма)
- 🎯 Как улучшить следующую задачу
```
```

### Результат Фазы 3

✅ Координатор работает на паттернах  
✅ Координатор понимает когда вмешиваться  
✅ Координатор может предложить улучшения  
✅ Каждая метрика имеет явное действие

---

## 📊 Суммарный результат

### До внедрения (Baseline)

```
✅ Система работает
❓ Агенты иногда импровизируют
❓ Координатор часто вмешивается
❓ Нет явных best practices
❓ Frontend слишком общий
```

### После внедрения (Target)

```
✅ Система работает ПРЕДСКАЗУЕМО
✅ Агенты следуют ЯВНЫМ ПАТТЕРНАМ
✅ Координатор вмешивается редко (<10% задач)
✅ Best practices явные и повторяемые
✅ Frontend разбит на СПЕЦИАЛИЗИРОВАННЫЕ скилы
✅ Время на типовую задачу: 100 → 85 мин (15% ускорение)
✅ Ошибки в коде: 5-7 → 1-2 (70% уменьшение)
```

---

## 🎯 Метрики успеха

| Метрика | Target |
|---------|--------|
| Агенты следуют паттернам | 95% задач |
| Координатор вмешивается | <10% задач |
| Ошибки в ревью | 1-2 на цикл |
| Время на типовую задачу | <85 мин |
| Researcher завис | <2% исследований |
| Ревью цикл 1 vs 2+ | 70% задач закрываются за цикл 1 |

---

## 📅 График реализации

```
Неделя 1:
  День 1-2: Фаза 1 (паттернизация)
  
Неделя 2:
  День 1-3: Фаза 2 (frontend специализация)
  
Неделя 2-3:
  День 1-3: Фаза 3 (паттерны координатора)

Week 3:
  День 1: Интеграция + тестирование
  День 2: Документирование
  День 3: Запуск на production
```

---

**Версия:** 1.0  
**Статус:** Ready for implementation  
**Автор:** Claude Haiku 4.5 + Antonov Aleksandr (Outsource)

