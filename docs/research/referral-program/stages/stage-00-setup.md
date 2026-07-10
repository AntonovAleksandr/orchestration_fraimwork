# Stage 00 — Setup / источники / requirements / ledger seed

**Дата:** 2026-07-02 · **Статус:** done  
**Jira:** OPSOMN001-743 · **BP-якорь:** docs/bp/04-checkout-order-creation.md

---

## 0. Scope

- Снять требования из Jira OPSOMN001-743.
- Собрать inventory источников (Jira, Confluence, код).
- Дизамбигуация HR «Приведи друга» vs ИМ-рефералка.
- Первичный grep as-is: есть ли зачатки referral в e-com.
- Засеять EVIDENCE-LEDGER.

---

## 1. As-is — первичные факты

### 1.1 Jira OPSOMN001-743 (confirmed)

- **Summary:** Реферальная программа ИМ: промокод-приглашение и начисление бонусов пригласившему.
- **Status:** Новая · **Priority:** High · **Type:** e-Task.
- **Comments:** 0 (на 2026-07-02).
- Полный текст FR → [`../00-requirements.md`](../00-requirements.md).

### 1.2 Confluence

- **OMNIES:** нет отдельной страницы «реферальная программа ИМ». Есть документация **APP20 / одноразовых промо** (`149756449`, `149781892`).
- **DEVFIN001:** «Приведи друга» — HR-премии (`130150213`, `149765293`) — **не e-commerce**.

### 1.3 Код — referral не реализован

| Область | Поиск | Результат |
|---|---|---|
| `platform/ensi/apps/customers` | referral, invite, personal promo | **0** (кроме composer referral URLs) |
| `platform/site/gj-ng-front/libs/modules/profile` | promo, loyalty, referral | **0** |
| `platform/mobile-app/gj-app` | referral | только AppsFlyer/Firebase app invite |
| Workspace root grep | referral, реферал | **0** |

**Вывод:** фича **greenfield** в e-com контуре; опираемся на APP20 как reference implementation скидки.

### 1.4 Код — промо-контур (exists, reusable)

**Baskets — регистрация буквенного промокода:**

```17:27:platform/ensi/apps/orders/baskets/app/Domain/Discounts/Actions/RegisterPromoCodeAction.php
    public function execute(SetBasketDiscountDto $data, int $basketNumber): ?string
    {
        $requestData = (new DiscountRequest())
            ->setType(DiscountResponseType::REGISTER_PROMOCODE_TYPE)
            ->setSalt(random_int(1, DiscountRequest::MAX_INT_32))
            ->setPromocode($data->promoCode)
            ->setEmail($data->email)
            ->setBasketNumber($basketNumber);

        return retry(3, fn () => $this->apiClient->registerPromoCode($requestData, $data));
    }
```

**Integration — rollback трансляции:**

```1661:1693:platform/integration/integration/www/app/Service/UserApi/Services/V1/Discount/DiscountService.php
    public function couponTranslate(
        string $orderId,
        string $customerEmail,
        string $promoCode,
        bool $rollback = false,
        ...
    ) {
        ...
        DiscountClient::couponTranslate(..., $rollback)
        ...
    }
```

**APP20 в коде:** строковых констант APP20 в Integration/ENSI **нет** — акция живёт в **конфиге Сервера скидок** (Jira OPSOMN-12607 «Добавление акции APP20 в конфиг СС»).

### 1.5 Связанный инцидент APP20

[`../2026-06-03-app20-cancel-restore-OPSOMN001-617.md`](../2026-06-03-app20-cancel-restore-OPSOMN001-617.md) — rollback трансляции при Cancelled: Path 1 (Camunda → loyalty/return) vs Path 2 (status-update). **Рефералка наследует те же риски** при cancel/reuse.

---

## 2. To-be (кратко)

См. [`../00-requirements.md`](../00-requirements.md) — FR-01…FR-08.

---

## 3. Gap-матрица (seed)

| Под-область | FR | Verdict | Комментарий |
|---|---|---|---|
| ЛК: показ unique promo | FR-01 | 🔴 | UI не найден |
| Хранение кодов + связей | FR-01,02 | 🔴 | customers — пусто |
| −20% как APP20 | FR-03 | 🟡 | CouponTranslate есть; нужен новый тип на СС |
| Web-only | FR-03 | TBD | Stage 03 |
| +500 через 14d | FR-04 | 🔴 | паттерн не найден |
| Cancel/return rules | FR-05 | 🟡 | APP20 rollback частично; return TBD |

---

## 4. Упущенные моменты

- **Частичный выкуп** — в тикете «выкуп», но в OMS есть partial fulfillment; может ли это триггерить +500?
- **Ghost usage** (трансляция без заказа) — см. OPSOMN001-617; актуально и для referral promo.
- **Multi-email customer** — rollback APP20 ломался на `customer.emails[0]` ≠ email трансляции.

---

## 5. Открытые вопросы

→ [`../00-requirements.md`](../00-requirements.md) § Q2–Q8.

---

## 6. Acceptance-gates (Stage 00)

- [x] Jira requirements captured
- [x] Source inventory started
- [x] Disambiguation HR vs IM documented
- [x] Ledger seeded
- [ ] Stage 01 APP20 deep-dive

---

## 7. Ledger updates

GAP-00-1 … GAP-00-12 → [`../EVIDENCE-LEDGER.md`](../EVIDENCE-LEDGER.md)

---

## 8. Resume pointer

**Next:** Stage 01 — APP20 as-is по Confluence `149781892` + `149756449`, конфиг СС (`130133718`), код baskets rollback + ИС OrderService paths.  
**Sync:** починить `integration/integration` branch tracking перед edit-сессией.
