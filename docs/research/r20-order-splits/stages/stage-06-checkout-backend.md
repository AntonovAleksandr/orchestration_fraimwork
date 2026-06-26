# Stage 06 — Чекаут (бэкенд-поток)

**Статус:** pending · **BP-якорь:** docs/bp/03, docs/bp/04 · **Требования R-20:** FR-15, FR-16 (+ пересчёт по региону)

## 0. Scope и гипотезы
- Поток чекаута: baskets → ИС → order-group-service → OMS; на чекауте показать **плановые сроки** (FR-15)
  и **составы каждого отправления** (FR-16).
- Пересчёт корзины по доступности/ценам при смене региона (бизнес-требование) — в т.ч. со сплитом.
- **Гипотеза:** чекаут считает один заказ/один склад («мультисклад = первый склад» — наблюдение из surf
  stage-06); вывод нескольких отправлений с составами/сроками — нет.

## Ключевые источники / таргеты
- Код: `platform/ensi/apps/orders/{baskets,order-group-service}`, `platform/ensi/apps/customers-api-web`.
- БД: `ensi-gs-baskets-*`, order-group-service БД, `ensi-gs-customers-*`.
- Доки: `docs/research/2026-05-29-checkout-as-is-archaeology.md`,
  `docs/research/surf-mini-rewrite/deep-dive/stages/stage-06-checkout-order-creation.md`, `docs/bp/03`.
- Confluence: `165391028` (Задачи чекаута).
- Делегировать: `ensi-researcher`.

## 1–8 — по `../TEMPLATE-stage.md`
