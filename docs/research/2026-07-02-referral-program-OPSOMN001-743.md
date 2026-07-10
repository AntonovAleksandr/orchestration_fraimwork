# Реферальная программа ИМ (OPSOMN001-743)

**Дата:** 2026-07-02 · **Статус:** research started · **Jira:** [OPSOMN001-743](https://jira.gloria-jeans.ru/browse/OPSOMN001-743)

## Summary

Запущен многосессионный research-проект **«referral-program»**: уникальный промокод в ЛК, −20% приглашённому (как APP20, web-only), +500 бонусов рефереру через 14 дней после выкупа. В e-com коде **рефералки пока нет** (greenfield); переиспользуем контур CouponTranslate/APP20. HR «Приведи друга» (DEVFIN001) — **не то же самое**.

## Приоритеты / findings

| # | Finding | Verdict |
|---|---|---|
| 1 | Требования сняты с Jira, 0 comments | confirmed |
| 2 | APP20 — этalon −20% + rollback; логика на СС, не в коде | high-confidence |
| 3 | Baskets `RegisterPromoCodeAction` + ИС `couponTranslate` — готовый контур | confirmed |
| 4 | Unique promo + referrer registry — нет в ENSI customers | confirmed gap |
| 5 | Отложенное +500 бонусов — паттерн не найден | hypothesis gap |
| 6 | APP20 rollback prod-регресс (OPSOMN001-617) — риск для referral cancel path | high-confidence |

## Затронутые системы (кратко)

| Система | Reuse | New |
|---|---|---|
| Сервер скидок | APP20 rules | per-user codes, accrual +500, no-clawback |
| Integration | rollback | web gate, +14d scheduler, pending rewards |
| ENSI customers | profile | unique code, referrer graph, API |
| ENSI baskets | CouponTranslate | referral format, eligibility |
| Site | share/copy, promo field | блок в ЛК |
| Mobile | — | block apply (web-only) |
| OMS | status-update | контракт «выкуп» |

Детально: [`referral-program/systems-impact.md`](referral-program/systems-impact.md)

## Дальше (research, не код)

1. Подтвердить API начисления на СС (+500, TTL 180d) — **блокер**
2. Stage 02 — архитектура unique promo + referrer graph
3. Stage 04/05 — «выкуп» + механизм +14d

**Проект:** [`referral-program/README.md`](referral-program/README.md)
