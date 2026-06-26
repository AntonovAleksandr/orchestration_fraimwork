# Stage 10 — 1С

**Статус:** pending · **BP-якорь:** docs/bp/06, docs/bp/07 · **Требования R-20:** FR-17, FR-18, FR-24

## 0. Scope и гипотезы
- Выгрузка/обмен с 1С при сплите: **отправления как подзаказы** (даты продажи/реализации по каждому, FR-17),
  **реальная стоимость доставки** от ТК для отчётов (FR-18), распределённая стоимость доставки (FR-24).
- WMS-аспект: `id_transport` (инцидент `OPSLOG-3267` — зависание на ORDER_SPLIT из-за неизвестного id_transport).
- **Гипотеза:** обмен с 1С завязан на «заказ»; модель «родитель + N отправлений-подзаказов» в выгрузке
  и корректные даты/стоимости per shipment — требуют доработки; WMS-маппинг id_transport уже болевая точка.

## Ключевые источники / таргеты
- Код/интеграции: OMS adapter/parsers (`platform/starfish24/core/{Adapter,Parsers}`), ИС обмен с 1С,
  ОТС WmsSync (`platform/gloriaots/gloriaots/src/Workers/GloriaOTS.WmsSync`).
- БД: `oms-awg-adapter-prod`, `oms-awg-order-prod`, `gloria_ots_prod`.
- Jira: `OPSLOG-3267` (1С WMS id_transport на ORDER_SPLIT).
- Делегировать: `oms-researcher`, `gloriaots-researcher`, `integration-researcher`.

## 1–8 — по `../TEMPLATE-stage.md`
