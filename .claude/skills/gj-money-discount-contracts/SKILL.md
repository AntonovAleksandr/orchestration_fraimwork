---
name: gj-money-discount-contracts
description: Use when working with Gloria Jeans money amounts, rubles vs kopecks, discounts, promo codes, coupons, loyalty bonuses, certificates, checkout totals, OMS InvalidateTotalCost, YooKassa/ATOL payment amounts, discount server clients, or Go Money/client contract changes.
---

# GJ Money And Discount Contracts

Use this skill whenever a task can change or diagnose price, discount, bonus, coupon, certificate, delivery cost, payment, refund, or fiscal amount semantics.

## Start Here

Read before changing contracts or money-handling code:

- `docs/research/2026-05-30-money-kopecks-rubles.md`
- `docs/bp/03-browse-cart-precheckout.md`
- `docs/bp/04-checkout-order-creation.md`
- `docs/bp/05-payment.md`
- `docs/bp/08-master-data-sync.md` for DWH/reconciliation impact
- `docs/research/2026-06-03-app20-cancel-restore-OPSOMN001-617.md` for promo/coupon rollback risk
- relevant `docs/superpowers/plans/*discount*` or `*money*` plans for Go client history

Load platform-specific skills after that: ENSI, Integration, OMS Java/Camunda, Go, or frontend/mobile.

## Canonical Rules

- Internal service logic should use integer minor units (`int64` kopecks) or a typed Money value.
- Never use `float64` for monetary arithmetic.
- JSON numeric money should be decoded losslessly, for example `json.Number` in Go clients.
- XML discount-server money is decimal text; preserve as string at the client boundary and normalize in adapters.
- ENSI offers/catalog prices are commonly stored as integer kopecks.
- Target ENSI ↔ Integration ↔ OMS checkout contracts are rubles with two decimal places at the boundary.
- Convert explicitly at each boundary; never infer units from field name alone.
- One payload must not mix item prices in kopecks with totals in rubles.

## Investigation Workflow

1. Identify each money field and its unit at source, transport, and target.
2. Build a small table: field, system, sample value, unit, type, conversion point.
3. Check whether discounts were recalculated on commit or only trusted from basket/frontend state.
4. For `InvalidateTotalCost`, compare:
   - item prices
   - item discounts
   - delivery cost
   - totalCost/payableCost
   - promo/coupon/bonus application state
5. Check rollback paths for coupons, bonuses, certificates, and payment links after order create.
6. For fiscal/payment changes, include YooKassa, ATOL, OMS pay-service, and DWH/reconciliation impact.

## Guardrails

- Do not fix a mismatch by adding another implicit conversion near the symptom.
- Do not parse decimal money through binary floats.
- Do not assume `0`, empty string, and `null` mean the same thing; document boundary behavior.
- Do not let ENSI basket discount and Integration discount quote silently diverge.
- Do not change OpenAPI money types without checking generated clients and downstream consumers.

## Output Expectations

For findings, update the relevant `docs/research/` summary.

For design, include:

- money-field unit table
- canonical source of each amount
- conversion boundaries
- rounding rule
- generated-client impact
- idempotency/rollback handling for spend and refund operations
- verification examples with concrete values
