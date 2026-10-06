---
name: gj-checkout-order-flow
description: Use when working on Gloria Jeans checkout, pre-checkout, cart commit, order creation, Integration V1/V3/V4 order routes, OMS /order/create, clientOrderId idempotency, delivery interval drift, split-shipment selection, checkout incidents, or checkout TO-BE design.
---

# GJ Checkout Order Flow

Use this skill for end-to-end checkout work across Site/Mobile, ENSI baskets/customers-api-web, Integration Service, OMS, payments, delivery, and `platform-new` checkout/intgateway services.

## Start Here

Read the relevant map before changing code or making design claims:

- `docs/bp/03-browse-cart-precheckout.md`
- `docs/bp/04-checkout-order-creation.md`
- `docs/bp/e2e-happy-path.md`
- `docs/research/2026-05-29-checkout-as-is-archaeology.md`
- `docs/research/2026-05-29-order-create-contract.md`
- `docs/research/2026-05-20-checkout-order-creation.md` for prod incident context

For implementation, also load the platform skill for the file you touch: `integration-*`, `ensi-*`, `oms-*`, `site-*`, `mobile-*`, or Go skills. For Integration Service implementation, follow **`pattern-development-integration.md`** to ensure the checkout flow change follows proper development discipline.

## Core Model

- Pre-checkout is selection building: cart, recipient, address, delivery option, interval, payment option, promo intent, and checksum.
- Commit/order-create is server-side re-derivation: Integration refetches/overwrites price, stock, discounts, delivery, and totals before OMS create.
- OMS `/order/create` persists and emits `ORDER_CREATED`; Camunda confirmation starts downstream, not inside create.
- `clientOrderId` is the idempotency key. `null` means retries can create duplicate orders.
- OMS is permissive and mostly trusts submitted delivery/totals; interval drift and checksum mismatch are usually upstream Integration/checkout problems.

## Investigation Workflow

1. Identify the entrypoint: Site/Mobile, `customers-api-web`, Integration order route, OMS `/order/create`, or `platform-new`.
2. Trace the selected checkout version: V1/V3/V4 routes and whether `general-data`, `delivery/summary`, `split-shipment`, or `order/create` is involved.
3. Separate user selection from server truth:
   - selection: selected items, address, pickup point, interval, payment type, promo intent
   - server truth: price, stock, discounts, delivery cost, packages, OMS payload
4. Check `clientOrderId` stability before debugging retries or duplicate orders.
5. For totals failures, switch to `gj-money-discount-contracts`.
6. For carrier/delivery-code failures, switch to `gj-delivery-carrier-integration`.
7. Preserve evidence: file paths, route names, trace IDs, Jira keys, and exact payload fragments without secrets.

## Design Guardrails

- Do not make the frontend the source of truth for price, stock, discounts, or delivery cost.
- Do not rely on the large `general-data` matrix as the target contract; the durable output is one stable selection.
- Do not drop two-phase truth/checksum behavior without an explicit architecture decision.
- Do not let `clientOrderId` be generated late or disappear during retries.
- Treat post-create side effects (coupon/bonus spend, payment link creation) as saga/idempotency risk.
- For `platform-new`, keep internal checkout money in minor units and convert only at client boundaries.

## Output Expectations

For research, update `docs/research/<date>-<topic>.md` or an existing checkout summary.

For architecture/design, update `docs/architecture/<date>-<topic>.md` and include:

- current route and version
- involved systems and ownership
- selection vs server-truth fields
- idempotency behavior
- rollback/compensation risk
- verification plan with API/log checks
