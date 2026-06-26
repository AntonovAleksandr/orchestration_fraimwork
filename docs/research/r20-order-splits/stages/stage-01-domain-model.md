# Stage 01 — Доменная модель сплита (родительский заказ ↔ отправления)

**Статус:** pending · **BP-якорь:** docs/bp/04, docs/bp/06 · **Требования R-20:** FR-1, FR-2, FR-3, FR-4

## 0. Scope и гипотезы
- **Фундамент всего проекта.** Как сегодня моделируется «заказ ↔ его части»: есть ли сущность «отправление»
  как первый класс, атрибут родителя (`1234/N`), состав, тип доставки на уровне отправления.
- Разобрать вложения R-20: docx «Сплит vs Мультизаказ» (`108064181`), excellentable (модель полей),
  drawio «Сплит заказы» (`108061905`).
- Сверить с `order-group-service` (ENSI) и существующими `ORDER_SPLIT` / таблицей `split order` (OMS/OTS).
- Сверить со смежной «Многоместные отправления» (`165406777`) — отделить от деления заказа.
- **Гипотеза:** деление частично существует (статус `ORDER_SPLIT`, split order в логистике), но как
  первоклассная модель «родитель+отправления с типами» в еком-контуре — вероятно нет.

## Ключевые источники / таргеты
- Confluence: `108057394` (+вложения), `73794036`, `165406777`, `130135894`.
- Jira: `OPSLOG-1344`/`DEVLOG001-1603` (split order), `OPSLOG-3267/3169` (ORDER_SPLIT).
- Код: `platform/ensi/apps/orders/{order-group-service,baskets}`, `platform/starfish24/core/Order`,
  `platform/starfish24/core/go/logistics`, `platform/gloriaots/gloriaots/src`.
- БД: `oms-awg-order-prod`, `oms-logistics-prod`, `gloria_ots_prod`, order-group-service БД.

## 1–8 — по `../TEMPLATE-stage.md`
