# Реферальная программа ИМ — EVIDENCE-LEDGER

Сквозной реестр разрывов. **Verdict = TBD** до стадий. Оркестратор обновляет после ревью стадии.

**Легенда:** 🟢 есть/паритет · 🟡 частично · 🟠 обходной путь · 🔴 нет · `TBD` не проверено

| GAP-id | FR | Домен | Гипотеза разрыва | Verdict | Evidence | Стадия |
|---|---|---|---|---|---|---|
| GAP-00-1 | FR-01 | Site/ENSI | UI блока реферального промокода в ЛК | 🔴 | grep referral empty in profile | 00 |
| GAP-00-2 | FR-01, FR-02 | ENSI customers | Хранение unique promo + referrer↔referee | 🔴 | grep referral empty in customers | 00 |
| GAP-00-3 | FR-03 | СС/offers | Тип акции «per-user referral −20%» | TBD | APP20 = DS config, not code | 01 |
| GAP-00-4 | FR-03 | Integration/baskets | CouponTranslate path exists (reuse APP20) | 🟡 | RegisterPromoCodeAction, DiscountService::couponTranslate | 00 |
| GAP-00-5 | FR-03 | Mobile | Web-only channel guard | TBD | OPSOMN-12334 APP20 channel | 03 |
| GAP-00-6 | FR-04 | OMS | Event «выкуп» для триггера +14d | TBD | — | 04 |
| GAP-00-7 | FR-04 | ПЛ/СС | Отложенное начисление 500 бонусов | 🔴 | no delayed bonus pattern in IS grep | 05 |
| GAP-00-8 | FR-05 | ИС/OMS/СС | Rollback при cancel (APP20 ref) | 🟡 | OPSOMN001-617, Confluence 149756449 | 01 |
| GAP-00-9 | FR-05 | ИС/СС | Return после выкупа → блок reuse | TBD | APP20 = paid order blocks reuse | 06 |
| GAP-00-10 | FR-05 | ПЛ | Не списывать бонусы реферера при return | TBD | — | 06 |
| GAP-00-11 | FR-07 | Analytics | События воронки рефералки | 🔴 | open in ticket | 08 |
| GAP-00-12 | — | HR | «Приведи друга» DEVFIN001 ≠ ИМ | 🟢 | Confluence DEVFIN001 vs OMNIES | 00 |

> Добавлять GAP-NN-x по мере стадий. Stage 00 = seed из первичного сканирования.
