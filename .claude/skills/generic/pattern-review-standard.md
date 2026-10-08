---
name: pattern-review-standard
version: 1.0.0
layer: generic
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---

# ✅ pattern-review-standard.md

**Категория:** [PATTERNS]  
**Используется:** обоими ревьюерами  
**Версия:** 1.0  
**Статус:** Production-ready

---

## 📋 Описание

**Явный паттерн ревью** - чеклисты для обоих ревьюеров.

Ревьюеры **ДОЛЖНЫ ВСЕГДА** следовать этим чеклистам. Нет пропусков.

---

## 👨‍💼 REVIEWER-1: Бизнес + Архитектура

### Чеклист (в порядке выполнения)

#### 1️⃣ AC Соответствие

```
✅ Все требования из постановки выполнены?
✅ Нет ли упущенных edge-cases?
✅ Все ли сервисы трогаются правильно?

Если НЕТ → [MUST FIX]
Комментарий: "AC требует X, код делает Y"
```

**Примеры [MUST FIX]:**
```
❌ "AC: новый статус видимый в UI, но кода в Site нет"
❌ "AC: обработать ошибку Y, но в коде только обработка X"
```

#### 2️⃣ Архитектурные границы

```
✅ Код не нарушает границы сервисов?
✅ OMS не вызывает напрямую Integration? (через API)
✅ Site не пишет напрямую в БД? (только через API)

Если НЕТ → [MUST FIX] или [SHOULD]
Комментарий: "Граница между сервисами нарушена"
```

**Примеры [MUST FIX]:**
```
❌ "OMS вызывает Integration handler напрямую (должно через HTTP API)"
```

**Примеры [SHOULD]:**
```
⚠️ "Можно оптимизировать вызов: вместо N запросов делать 1"
```

#### 3️⃣ Контракты между сервисами

```
✅ Если менялся контракт (API, Kafka, БД):
   ✅ Спека обновлена? (OpenAPI)
   ✅ Клиенты обновлены? (generated clients)
   ✅ Версионирование правильное?

Если НЕТ → [MUST FIX]
```

**Примеры [MUST FIX]:**
```
❌ "API контракт изменился, но OpenAPI не обновлена"
❌ "Kafka сообщение изменилось, но schema не обновлена"
```

#### 4️⃣ Расширяемость

```
✅ Код расширяем? (не hardcoded)
✅ Паттерны соблюдены? (enum не создавать за ogni раз)
✅ Нет ли магических чисел/строк?

Если НЕТ → [SHOULD] или [NIT]
```

**Примеры [SHOULD]:**
```
⚠️ "Новые статусы добавляются hardcoded, лучше использовать enum"
⚠️ "Число 3 должно быть const RETRY_ATTEMPTS"
```

#### 5️⃣ Полнота изменений

```
✅ Все затронутые места обновлены?
✅ Не забыли ли миграции, конфиги, документацию?
✅ Нет ли TODO/FIXME в коде?

Если НЕТ → [MUST FIX] или [SHOULD]
```

**Примеры [MUST FIX]:**
```
❌ "Добавлен новый enum, но миграция БД забыта"
❌ "Нужно обновить docs/service-index.md"
```

---

## 🔒 REVIEWER-2: Security + Performance + Design

### Чеклист (в порядке выполнения)

#### 1️⃣ Безопасность (Security)

**SQL Injection:**
```
✅ Параметризованные запросы? (не конкатенация!)
✅ ORM использует параметры?

❌ "SELECT * FROM orders WHERE id=" + id  (SQL injection!)
✅ "SELECT * FROM orders WHERE id=?" с параметром  (OK)
```

**XSS (если UI код):**
```
✅ User input escapeпован?
✅ innerHTML не используется с user data?

❌ element.innerHTML = userInput  (XSS!)
✅ element.textContent = userInput  (OK)
```

**Secrets:**
```
✅ Нет hardcoded passwords/API keys?
✅ Нет credentials in code?
✅ Нет secrets in logs?

❌ const API_KEY = "abc123..."  (secrets in code!)
✅ const API_KEY = process.env.API_KEY  (OK)
```

**Authentication/Authorization:**
```
✅ Проверяется ли что пользователь имеет права?
✅ Нет ли bypass auth?

❌ Прямой доступ к чужим заказам без проверки прав
✅ Проверка: this.order.userId === currentUser.id
```

**Если проблема:**
```
❌ [SECURITY] (это MUST FIX!) Описание уязвимости
```

#### 2️⃣ Производительность (Performance)

**N+1 Queries:**
```
✅ Нет ли в цикле запросов к БД?

❌ for (order in orders) { db.query("SELECT items WHERE order_id=" + order.id) }
✅ db.query("SELECT * FROM items WHERE order_id IN (?)", ids)
```

**Loops:**
```
✅ Нет ли O(N²) алгоритмов?
✅ Нет ли nested loops где не нужно?

❌ for (i: orders) { for (j: items) { if (i.id == j.order_id) } }  (O(N²)!)
✅ const itemsByOrderId = groupBy(items, 'order_id')  (O(N))
```

**Caching:**
```
✅ Кешируются ли часто используемые данные?
✅ Cache invalidation правильная?
```

**Если проблема:**
```
[PERF] Описание проблемы и рекомендация
```

#### 3️⃣ Дизайн/UI (если UI код)

**Соответствие макету (Figma):**
```
✅ Colors соответствуют design tokens?
✅ Spacing соответствует? (8px grid)
✅ Typography правильная?

❌ Цвет #FF0000 в коде, но Figma требует #E63946
```

**Responsive:**
```
✅ Работает на мобиле?
✅ Breakpoints правильные?
```

**Accessibility (a11y):**
```
✅ aria-labels на интерактивных элементах?
✅ Keyboard navigation работает?
✅ Color contrast OK?

❌ <button>кнопка</button> без aria-label
✅ <button aria-label="Удалить заказ">🗑️</button>
```

**Если проблема:**
```
[DESIGN] Описание расхождения с макетом/стандартами
```

#### 4️⃣ Readability & Maintainability

```
✅ Код понятен новому разработчику?
✅ Нет ли слишком сложных выражений?
✅ Переменные ясно названы?

⚠️ [NIT] "Может быть лучше назвать 'status' в 'orderStatus'"
```

#### 5️⃣ Tests

```
✅ Unit tests есть?
✅ Coverage >80%?
✅ E2E тесты для critical flow?

❌ Нет тестов
✅ Есть unit + integration + e2e
```

---

## 🎯 Как использовать эти чеклисты

### Для Reviewer-1

```
1. Открыть MR
2. Прочитать постановку (ЧТО, ГДЕ, КАК, РИСКИ)
3. Пройти чеклист в порядке:
   ✅ AC Соответствие
   ✅ Архитектурные границы
   ✅ Контракты
   ✅ Расширяемость
   ✅ Полнота
4. Если все OK → Approved
5. Если проблемы → [MUST FIX] / [SHOULD] / [NIT] комментарии
```

### Для Reviewer-2

```
1. Открыть MR (не ждёшь reviewer-1!)
2. Пройти чеклист в порядке:
   ✅ Security
   ✅ Performance
   ✅ Design/UI
   ✅ Readability
   ✅ Tests
3. Если все OK → Approved
4. Если проблемы → [SECURITY] / [PERF] / [DESIGN] комментарии
```

---

## 📝 Формат комментариев

```
### MUST FIX (обязательно исправить)
[MUST] Комплайент X нарушает AC Y

**Проблема:** описание
**Решение:** рекомендация
**Почему:** объяснение

---

### SHOULD (рекомендация)
[SHOULD] Можно оптимизировать

**Текущий способ:** описание
**Лучший способ:** рекомендация
**Выигрыш:** почему это лучше

---

### NIT (опционально)
[NIT] Может быть лучше

**Предложение:** опционально это улучшение
(не блокирует merge)
```

---

## ✨ Важные правила

### Правило 1: ВСЕГДА чеклист
- Не пропускать пункты
- Даже если "очевидно" - проверить

### Правило 2: MUST FIX vs SHOULD vs NIT
- [MUST] = блокирует merge
- [SHOULD] = рекомендуется но не блокирует
- [NIT] = опционально

### Правило 3: Specificity
- Не писать "код плохой"
- Писать "на строке X, функция Y делает Z, но AC требует W"
- Со ссылкой на AC/спеку

### Правило 4: Два ревьюера независимо
- Reviewer-1 не ждёт Reviewer-2
- Reviewer-2 не ждёт Reviewer-1
- Оба работают параллельно

### Правило 5: Перепроверка
- Если developer фиксил → перепроверить (5 мин)
- Все ли [MUST] исправлены?
- Не появились ли новые проблемы?

---

## 🔧 Platform-specific review skills

For deeper review aligned with language/framework, use these skills alongside this standard:

| Platform | Reviewer skill | When |
|----------|---|---|
| ENSI | ensi-gitlab-mr-review | PHP/Laravel code in ENSI services |
| OMS | oms-gitlab-mr-review | Java/Go code in OMS services, BPMN processes |
| Integration | integration-gitlab-mr-review | PHP/Lumen code, checkout APIs |
| Site | site-gitlab-mr-review | Angular/NgRx/NestJS code |
| Mobile | mobile-gitlab-mr-review | React Native/TypeScript code |
| Go (platform-new) | go-code-reviewer | Go code in checkout, intgateway, policyengine, recommendationengine |
| Gloria OTS | gloriaots-gitlab-mr-review | .NET/C# code |

---

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Статус:** Production-ready  
**Автор:** Claude Haiku 4.5 + Antonov Aleksandr (Outsource)
