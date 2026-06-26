# Stage 03 — OMS: отправление как подзаказ (workflow / статусы)

**Статус:** pending · **BP-якорь:** docs/bp/07 · **Требования R-20:** FR-13, FR-17, FR-21, FR-22, FR-25, FR-26

## 0. Scope и гипотезы
- Каждое отправление = отдельный подзаказ со своим **Camunda workflow** (FR-25): статусы, холдирование/списание,
  отмена per shipment (FR-22), даты продажи/реализации отдельно по отправлению (FR-17),
  частичная оплата при получении по отправлению (FR-21), уведомления per shipment (FR-26).
- Сверить с существующим `ORDER_SPLIT` статусом и кейсами отмены `DEVOMN001-5130/5152`.
- **Гипотеза:** статусная схема уже умеет ORDER_SPLIT, но «отправление как полноценный подзаказ со своим
  жизненным циклом + per-shipment холдирование/отмена/даты» — частично; уточнить, где граница.

## Ключевые источники / таргеты
- Код: `platform/starfish24/core/{Camunda,BPM,camunda-worker,Order,pay-service}`,
  BPMN `platform/starfish24/awg/bpmn-process/process`.
- БД: `oms-awg-camunda-prod` (procdef/exec/timer/task), `oms-awg-order-prod`, `oms-awg-pay-prod`.
- Confluence: `108038924`, `130135623`, `130135894`, `86312438`, `130133888` (статусные схемы/кейсы).
- Jira: `DEVOMN001-5130/5152` (отмена на ORDER_SPLIT), `OPSOMN-12375` (пропуск статуса).
- Делегировать: `oms-researcher`, `camunda-bpm-engineer`.

## 1–8 — по `../TEMPLATE-stage.md`
