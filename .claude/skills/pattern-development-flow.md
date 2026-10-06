# 💻 pattern-development-flow.md

**Категория:** [PATTERNS]  
**Используется:** всеми разработчиками  
**Версия:** 1.0  
**Статус:** Production-ready

---

## 📋 Описание

**Явный паттерн разработки** - как разработчик пишет код по постановке.

Разработчик **ДОЛЖЕН ВСЕГДА** следовать этим 7 шагам. Нет импровизации.

---

## 🎯 7 обязательных шагов

### 1️⃣ ПОНИМАНИЕ (Understanding)

**Что делать:**
- Прочитать ПОЛНУЮ постановку (ЧТО, ГДЕ, КАК, РИСКИ)
- Понять требование (ЧТО нужно делать?)
- Понять сервисы (ГДЕ писать код?)
- Понять верификацию (КАК проверяем?)
- Понять риски (Какие [BLOCKER]?)

**Процесс:**
```
ЧТО? "Добавить новый статус SHIPPED_TO_CUSTOMER"
      ✅ Понял: новый enum value

ГДЕ? "OMS OrderStatus, Integration route, Site component"
      ✅ Понял: 3 места

КАК? "Unit + Integration + E2E тесты"
      ✅ Понял: как проверяем

РИСКИ? "[BLOCKER] нет (есть лаг но не блокирует)"
      ✅ Понял: могу начинать писать

✅ ПОНИМАНИЕ ЗАВЕРШЕНО → переход на шаг 2
```

**Если не понял:**
- Спросить аналитика
- Не начинать писать "наугад"

---

### 2️⃣ ПЛАН (Planning)

**Что делать:**
- Какие файлы трогаем?
- Какой порядок имплементации?
- Какие есть зависимости?
- Есть ли [NB] вопросы которые не решены?

**Процесс:**
```
Файлы:
✅ platform/starfish24/core/Order/OrderStatus.java
✅ platform/starfish24/core/Order/DeliveryHandler.java
✅ platform/integration/www/routes/delivery-update.php
✅ platform/site/gj-ng-front/libs/ui/order-status.component.ts

Порядок:
1. OrderStatus enum (первое, от этого зависит остальное)
2. DeliveryHandler (зависит от 1)
3. Integration route (зависит от 1, 2)
4. Site component (зависит от 3)

[NB] вопросы:
- нужны ли миграции БД? → можно параллельно
- нужны ли перегенерировать клиенты? → потом
```

---

### 3️⃣ КОД (Implementation)

**Что делать:**
- Писать код по плану
- Следовать shared-code-style (комментарии, naming, форматирование)
- Комментарии только "ПОЧЕМУ", не "ЧТО"
- Переменные ясные, функции <30 строк

**Процесс:**
```
// ✅ ХОРОШО:
// Новый статус для когда товар отправлен до адреса доставки
const SHIPPED_TO_CUSTOMER = "SHIPPED_TO_CUSTOMER";

// ❌ ПЛОХО:
// Добавить новый статус
const STC = "STC";  // непонятно что это
```

**Правила:**
- shared-code-style обязателен
- Нет закомментированного кода
- Нет console.log (только если debug)
- Нет magic numbers (использовать const/enum)

---

### 4️⃣ SECURITY (Security Checks)

**Что проверять:**
- Нет SQL injection? (параметризованные запросы)
- Нет XSS? (escaping input)
- Нет secrets in code? (no hardcoded passwords/tokens)
- Нет PII in logs? (не логируем sensitive data)

**Процесс:**
```
SQL: SELECT * FROM orders WHERE status = ? (параметр) ✅
XSS: statusName = sanitize(input) ✅
Secrets: нет hardcoded API keys ✅
Logs: не логируем user_id, email ✅

✅ SECURITY OK → переход на шаг 5
```

**Если нашёл проблему:**
- Немедленно фиксить
- Не пушить код с security issues

---

### 5️⃣ ТЕСТЫ (Testing)

**Что писать:**
- Unit tests: для каждой функции
- Integration tests: если API
- Edge-cases: граничные значения

**Процесс:**
```
// Unit test
test("OrderStatus contains SHIPPED_TO_CUSTOMER") {
  expect(OrderStatus.values()).toContain(SHIPPED_TO_CUSTOMER)
}

// Integration test
test("delivery-update route handles new status") {
  POST /delivery-update {status: "SHIPPED_TO_CUSTOMER"}
  → проверяем что попал в БД, отправился в Site
}

// Edge-case test
test("handles rapid status transitions") {
  // быстро переходим PENDING → SHIPPED → DELIVERED
  // проверяем что всё OK (нет race condition)
}

✅ TESTS COMPLETE (>80% coverage) → переход на шаг 6
```

---

### 6️⃣ КОММИТ (Commit)

**Что делать:**
- Правильная ветка: feature/*, fix/*, refactor/*
- Сообщение ясное: feat(order): добавить статус SHIPPED_TO_CUSTOMER
- Co-Authored-By добавить
- Все тесты зелёные

**Процесс:**
```bash
# Проверка перед коммитом
git status           # только нужные файлы?
npm run lint         # нет ошибок стиля?
npm run test         # все тесты зелёные?

# Коммит
git commit -m "feat(order): добавить статус SHIPPED_TO_CUSTOMER

- добавить enum value в OrderStatus
- создать handler в DeliveryHandler
- обновить Integration route
- добавить UI component в Site

AC выполнены:
- Unit тесты: ✅
- Integration тесты: ✅
- E2E тесты: ✅

Co-Authored-By: Claude Haiku <noreply@anthropic.com>"
```

---

### 7️⃣ MR (Merge Request)

**Что делать:**
- Правильный target branch (обычно main, Site = release/production)
- Описание: ссылка на OPSOMN, краткое описание
- Все тесты зелёные в CI

**Процесс:**
```bash
git push origin feature/OPSOMN002-XXX

# Создать MR через GitLab/GitHub
Title: "feat(order): добавить статус SHIPPED_TO_CUSTOMER"

Description:
"## Summary
Добавляем новый статус заказа SHIPPED_TO_CUSTOMER

## Changes
- OMS: OrderStatus enum + DeliveryHandler
- Integration: route обновлена
- Site: компонент создан

## Test plan
- Unit тесты: ✅
- Integration: маршрут работает ✅
- E2E: на стенде переход работает ✅

## Fixes
Closes OPSOMN002-XXX"

✅ MR ГОТОВ → передаём Ревьюерам
```

---

## ✨ Важные правила

### Правило 1: ВСЕГДА 7 шагов
- Нет сокращений
- Нет "напишу как думаю"
- Даже если просто, пройти все 7 шагов

### Правило 2: ПОНИМАНИЕ перед кодом
- Если не понял постановку → спросить, не писать
- [BLOCKER] вопросы должны быть разрешены перед кодом

### Правило 3: Security обязателен
- Не пушить код с security issues
- Даже если "потом фиксим"

### Правило 4: Тесты обязательны
- Нет тестов → нет кода
- >80% coverage

### Правило 5: Стиль обязателен
- shared-code-style
- Нет стилевых ошибок → нет кода

---

## 🎓 Полный пример

```
ШАГ 1: ПОНИМАНИЕ
✅ Прочитал постановку
✅ Новый статус SHIPPED_TO_CUSTOMER
✅ ТРИ места: OMS, Integration, Site
✅ Нет [BLOCKER], могу писать

ШАГ 2: ПЛАН
✅ Файлы определены (3 файла)
✅ Порядок: OrderStatus → Handler → Route → Component
✅ Зависимости понял

ШАГ 3: КОД
✅ Написал код в 3 файлах
✅ Следовал shared-code-style
✅ Комментарии только "почему"

ШАГ 4: SECURITY
✅ SQL параметризован
✅ Нет hardcoded secrets
✅ Нет PII in logs

ШАГ 5: ТЕСТЫ
✅ Unit: OrderStatus enum содержит новый статус
✅ Integration: route распределяет статус
✅ Edge-case: быстрые переходы
✅ Coverage: 85%

ШАГ 6: КОММИТ
✅ Ветка feature/OPSOMN002-XXX
✅ Сообщение ясное
✅ Co-Authored-By добавлен

ШАГ 7: MR
✅ MR создан
✅ Описание полное
✅ Все тесты зелёные

→ ГОТОВО! MR передан ревьюерам
```

---

## 🚀 Как использовать

1. **Ты разработчик?** → Загрузить этот файл
2. **Получил постановку?** → Следовать 7 шагам ВСЕГДА
3. **Готовишь MR?** → Проверить что все 7 шагов выполнены
4. **Есть вопросы?** → Перечитать этот файл

---

## 🔧 Platform-specific patterns

These 7 steps are the foundation. Each platform has **platform-specific pattern** with additional language/framework rules:

| Platform | Pattern file | Language | When to use |
|----------|--------------|----------|------------|
| ENSI | pattern-development-ensi.md | PHP + Laravel | Checkout, Offers, PIM, catalog-cache, Integration connectors |
| OMS | pattern-development-oms.md | Java + Camunda | Order, Delivery, Stock, BPM processes, workers |
| Integration | pattern-development-integration.md | PHP + Lumen | Checkout routes, order-create, cron tasks, Kafka |
| Site | pattern-development-site.md | Angular + NgRx | Frontend, SSR, state management |
| Mobile | pattern-development-mobile.md | React Native + Redux | Mobile app, iOS/Android, builds |
| Go (platform-new) | pattern-development-go.md | Go + chi/Fiber | Checkout, intgateway, policyengine, recommendationengine |
| Gloria OTS | pattern-development-gloriaots.md | .NET + C# | Order transport system, logistics, RabbitMQ |

**Usage:** After understanding the base 7 steps, load the platform-specific pattern and follow its additional checks.

---

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Статус:** Production-ready  
**Автор:** Claude Haiku 4.5 + Antonov Aleksandr (Outsource)
