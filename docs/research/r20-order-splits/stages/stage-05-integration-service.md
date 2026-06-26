# Stage 05 — Integration Service (ИС): оркестрация сплита

**Статус:** pending · **BP-якорь:** docs/bp/04 · **Требования R-20:** FR-20, FR-22

## 0. Scope и гипотезы
- Роль ИС в потоке чекаута: baskets → ИС → order-group-service → OMS → ОТС; проброс состава и **сплита**.
- Маршрутизация и обработка состояний: неполная сборка (`OPSOMN-11606`), обновление статусов,
  проброс отмены отдельного отправления (FR-22), единый платёж за родительский (FR-20).
- **Гипотеза:** ИС оркеструет чекаут и заказ, но контракт «родитель+отправления» и проброс per-shipment
  событий/отмены — частично; уточнить, где ИС агрегирует/разбивает.

## Ключевые источники / таргеты
- Код: `platform/integration/integration/www` (+ libs logger/msq-client/health), `containers/`.
- БД/логи: `oms-is-stage-integration*`, `integration-awg-new-logs-prod`.
- Доки: `docs/bp/source/integration-processes.md`, `docs/research/2026-05-20-checkout-order-creation.md`.
- Jira: `OPSOMN-11606` (логика неполной сборки в ИС).
- Делегировать: `integration-researcher`.

## 1–8 — по `../TEMPLATE-stage.md`
