# Реферальная программа ИМ — инвентаризация источников

Проверено через MCP Buddy + локальный grep **2026-07-02** (confidence: high для ID, содержание — на стадиях).

---

## 1. Jira

| key | Заголовок | Роль |
|---|---|---|
| **`OPSOMN001-743`** | Реферальная программа ИМ: промокод-приглашение и начисление бонусов | **Главный источник требований** |
| `OPSOMN-12294` | Доработки по промокодам APP20 (BA, Завершено) | BA по APP20 |
| `OPSOMN-12310` | Разрешить повторное использование APP20 при отмене (e-Story) | Rollback при Cancelled |
| `OPSOMN-12305` | Epic APP20 cancel restore | Эпик |
| `OPSOMN-12554` | Rollback couponTranslate в ИС (status-update) | ИС |
| `OPSOMN-12764` | Rollback в корзине / create path | ИС + ENSI |
| `OPSOMN-12799` | Откат APP20 у LOST/CANCELLED (ручной) | СС |
| `OPSOMN001-617` | APP20 не восстанавливается после отмены (регресс prod) | Инцидент / edge cases |
| `OPSOMN-12334` | МП не может применить APP20 | Канал/конфиг |
| `OPSOMN-12607` | Добавление акции APP20 в конфиг СС | Конфиг СС |

JQL для добора: `project in (OPSOMN, OPSOMN001) AND text ~ "APP20"`, `text ~ "CouponTranslate"`.

---

## 2. Confluence

### OMNIES (e-commerce) — релевантно

| page_id | Заголовок | Роль |
|---|---|---|
| `149781892` | Применение промокода | Sequence: Front → Ensi → Baskets → DS (CouponTranslate) |
| `149756449` | Использование одноразового промокода | APP20 правила + rollback + связанные Jira |
| `130154031` | OPSOMN-12310. Отмена трансляции APP20 в корзине | In-basket rollback |
| `146506730` | Rollback трансляции LOST/CANCELLED | Заказ |
| `149781894` | Удаление и rollback промокода | |
| `130133718` | Сервер скидок настройка промокодов | Конфиг DS |
| `60692563` | Функциональная нарезка Front | Единственное упоминание «реферал» в OMNIES — **проверить контекст на Stage 07** |

### DEVFIN001 — **НЕ в скоупе** (HR)

| page_id | Заголовок | Примечание |
|---|---|---|
| `130150213` | Обработка «Расчет премии Приведи друга» | HR/1C, не ИМ |
| `149765293` | Расчет премии «Приведи друга» | HR |

CQL: `text ~ "реферальн" AND space = OMNIES` → 1 hit (`60692563`).

---

## 3. Research / BP (наши доки)

| Файл | Релевантность |
|---|---|
| [`../2026-06-03-app20-cancel-restore-OPSOMN001-617.md`](../2026-06-03-app20-cancel-restore-OPSOMN001-617.md) | Path 1 vs Path 2 rollback, ghost usage |
| [`../2026-05-20-checkout-order-creation.md`](../2026-05-20-checkout-order-creation.md) | Индекс чекаута |
| [`../2026-05-29-checkout-as-is-archaeology.md`](../2026-05-29-checkout-as-is-archaeology.md) | As-is чекаут |
| `docs/bp/04-checkout-order-creation.md` | BP чекаута |
| `docs/bp/07-post-order-and-comms.md` | Пост-заказ, статусы |

---

## 4. Код (локально, после sync)

| Домен | Путь | Что искать |
|---|---|---|
| **Baskets — регистрация промо** | `platform/ensi/apps/orders/baskets/app/Domain/Discounts/Actions/RegisterPromoCodeAction.php` | CouponTranslate через DiscountApiClient |
| **Baskets — rollback** | `.../RollbackRegisteredPromoCodeAction.php` | In-basket rollback |
| **Baskets — 13-digit check** | `.../Concerns/ChecksRegisteredPromoCode.php` | Буквенный vs 13-значный купон |
| **Integration — couponTranslate** | `platform/integration/integration/www/app/Service/UserApi/Services/V1/Discount/DiscountService.php:1661` | Rollback на СС |
| **Integration — order cancel path** | `.../V1/Order/OrderService.php` (~1153, ~4915) | status-update + loyalty/return |
| **Integration — V4 create overlap** | `.../V4/Order/OrderService.php:264` | Rollback при наложении промо |
| **XmlHelper** | `.../DiscountClient/Parsers/XmlHelper.php:310` | Контракт CouponTranslate |
| **Site profile** | `platform/site/gj-ng-front/libs/modules/profile` | ЛК — **grep referral пуст на Stage 00** |
| **Mobile** | `platform/mobile-app/gj-app` | Только AppsFlyer invite / Firebase — не рефералка ИМ |
| **Customers** | `platform/ensi/apps/customers/customers` | **Нет referral/personal promo на Stage 00** |
| **OMS Camunda** | `platform/starfish24/awg/bpmn-process/process/gloriajeans/paymentFinalizationProcess.bpmn` | gjOrderLoyaltyReturn |

### Stage 00 — быстрые факты из кода

- **Referral/personal promo в ENSI customers — не найдено** (grep по `platform/ensi/apps/customers`).
- **Referral UI на Site/Mobile — не найдено** (кроме analytics AppInvite).
- **APP20 строкой в коде почти нет** — логика на стороне **Сервера скидок** (конфиг акции DS22), e-com только CouponTranslate/GetDiscount.

---

## 5. БД / логи (TBD на стадиях)

| Target | Запрос / цель |
|---|---|
| `oms-awg-order-prod` | Статусы «выкуп» (COMPLETED, delivered, partial) для APP20-заказов |
| `ensi-gs-baskets-*` | `promo_code`, `promo_code_failed_checks_count` |
| `integration-awg-new-logs-prod` | CouponTranslate, loyalty/return по orderId |
| СС (вне pg) | Настройка акции APP20 / одноразовые промо — через аналитиков СС или Confluence `130133718` |

---

## 6. Sync-заметки (2026-07-02)

```
FAIL  integration/integration  (no upstream for branch release-26.07.1)
```

Код Integration **читается локально**; перед implementation — починить tracking branch.
