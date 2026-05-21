# Глоссарий

Термины e-commerce платформы GJ. Если встречаешь незнакомое слово в L1-файлах — оно здесь.

---

## Платформы и системы

| Термин | Расшифровка |
|---|---|
| **ENSI** | Платформа микросервисов GJ. PHP 8.1 / Swoole / Go. ~25 сервисов в `platform/ensi/apps/`. |
| **OMS** / **Starfish** | Order Management System. Vendor-locked коробка Starfish24. Java Spring Boot + Camunda BPM + Go (logistics). `platform/starfish24/`. |
| **Integration** / **Integration Service** | Тонкий PHP/Lumen сервис между Site/Mobile и (ENSI + OMS). Не имеет БД корзин. `platform/integration/`. |
| **Site** | Публичный сайт. Angular 20 + Nx monorepo + NgRx + NestJS SSR. `platform/site/gj-ng-front/`. |
| **Mobile** / **Mobile App** | Мобильное приложение. React Native 0.74. `platform/mobile-app/gj-app/`. |
| **BFF** | Backend-for-Frontend. У нас два разных BFF — ENSI `customers-api-web` (OpenAPI-first) и Integration. |
| **WMS** | Warehouse Management System. Внешняя, не в нашем monorepo. Получает picking-задания из OMS. |
| **OTS** | Order Transport System (`gloriaots/gloriaots`). Оперативная транспортно-логистическая система: заказы, статусы складов/магазинов, WMS, ТК. Интегрируется с OMS (export/status) и Integration (export, stock, Kafka). В части legacy-доков встречается расшифровка «Order Tracking System». |
| **1C-RETAIL / 1C-ECOM / 1C-CBR** | Корпоративные системы 1С: розница, e-commerce учёт, бухгалтерия. |
| **DWH** | Data Warehouse. Аналитическая БД. |
| **ATOL** / **ОФД** | Сервис фискализации чеков → Оператор Фискальных Данных → налоговая. |

---

## Сущности данных

| Термин | Значение |
|---|---|
| **Product** | Карточка товара в PIM (ENSI). |
| **SKU** / **Sku** | Stock-keeping unit. Конкретный вариант товара (цвет/размер). |
| **Offer** | Связка Product+SKU+цена+остатки. Хранится в ENSI `offers`. |
| **Basket** / **Корзина** | Состав покупки до оформления. ENSI `baskets`. |
| **Order** | Зафиксированный заказ. Канонически — в OMS `core/Order`. |
| **Shipping** | Часть заказа, описывающая отгрузку (адрес/ПВЗ, carrier, tracking). 1:1 с Order (split-shipment не материализуется). |
| **Item** | Позиция заказа. |
| **Package** | Физическая упаковка. На /order/create Integration всегда отправляет `packages[0]` = всё. |
| **Customer** | Покупатель. ENSI `customers`. |
| **CustomerAddress** | Адрес из адресной книги клиента. |
| **Business Unit (BU)** | Юр.лицо / магазин / склад. ENSI `bu`. |
| **Reservation** | Резерв стока на конкретный Order в OMS Stock. |

---

## Чекаут и логистика

| Термин | Значение |
|---|---|
| **Pre-checkout** | Этап **до** /order/create: запросы general-data + delivery quote + payment methods. |
| **General-data** | Endpoint Integration, агрегирующий всё нужное для рендера формы чекаута. |
| **Delivery quote** | Расчёт интервалов и тарифов доставки. |
| **Interval ID** | Идентификатор интервала доставки. **Rolling hash** в OMS Settings — non-idempotent (см. [`../research/2026-05-20-checkout-order-creation.md`](../research/2026-05-20-checkout-order-creation.md)). |
| **Carrier** | Перевозчик: CDEK, 5post, RPost, Yandex, DPD, IML и ещё ≈11. |
| **Tariff** | Конкретный тариф перевозчика. |
| **Waybill** | Транспортная накладная, выдаётся carrier при регистрации отгрузки. |
| **Pickup point (ПВЗ)** | Точка выдачи. Например, ПВЗ CDEK или 5post. |
| **Click & Collect** | Самовывоз в магазине GJ (товар берут с полки). |
| **Split-shipment** | UX-конструкт «комплектации 2 из 3», существует только на pre-checkout, на /order/create склеивается в один package. |
| **isSelected** | Флаг на позиции корзины: учитывать ли её в pre-checkout/order. |

---

## Платежи

| Термин | Значение |
|---|---|
| **YooKassa** | Основной платёжный провайдер (Юkassa). |
| **СБП** | Система Быстрых Платежей (QR). Через YooKassa. |
| **Sber acquiring** | Альтернативный платёжный канал; упомянут в paymentProcess BPMN. |
| **Подели** | BNPL (4 платежа). |
| **Hold / Capture** | Двухфазная авторизация платежа: блокировка → списание. |
| **Refund** | Возврат денег после captured-платежа. |
| **Postpaid / Cash on delivery** | Оплата при получении. Без онлайн-платежа. |
| **Gift certificate** | Подарочный сертификат. Покупается как обычный заказ; используется как способ оплаты. |
| **ATOL фискализация** | Отправка чека в ОФД. |

---

## Workflow / BPMN

| Термин | Значение |
|---|---|
| **Camunda BPM** | Workflow engine OMS. |
| **BPMN** | Стандарт описания процессов (XML). Лежит в `awg/bpmn-process/process/`. |
| **External task** | Подход Camunda: BPMN ставит задачу в очередь по topic, внешний worker её забирает. Используется в `camunda-worker`. |
| **Service task** | Embedded задача BPMN (выполняется в JVM Camunda). |
| **User task** | Задача для человека (через ARM / админку). |
| **Camunda message** | Триггер для запуска или продолжения процесса. |
| **Cockpit** | Веб-интерфейс Camunda для мониторинга процессов и инцидентов. |
| **cancellationStage** | Camunda-переменная, маркирующая этап отмены. **Case-sensitive**. |

---

## Лояльность / коммерция

| Термин | Значение |
|---|---|
| **Discount card** | Бонусная карта 1С Retail. Привязана к Customer. |
| **Loyalty compensation** | Возврат бонусов при возврате заказа (BP-INT-16). |
| **Promo** / **Promocode** / **Coupon** | Промокод. Применяется при расчёте корзины через внешний PromotionService. |
| **Obsolete SKU** | SKU, выводимый из ассортимента (BP-OFF-04). |

---

## Качество / observability

| Термин | Значение |
|---|---|
| **Audit** | ENSI сервис `audit` для логирования мутаций. |
| **Outbox** | Паттерн надёжной публикации Kafka events. **Не используется** в большинстве ENSI Kafka-observer'ов (см. quirk в `01-product-content-lifecycle.md`). |
| **Trace ID** | Идентификатор для трассировки запроса через сервисы. Используется в логах (см. `mcp__gj-buddy__logs_search_trace`). |
| **gj-buddy MCP** | MCP-toolkit для GitLab / Jira / Confluence / логов. `mcp__gj-buddy__*`. |
| **Functional нарезка** | Confluence-индекс `60689793`: 26 нарезок по сервисам. |

---

## Regulatory / compliance

| Термин | Значение |
|---|---|
| **152-ФЗ** | Закон РФ «О персональных данных». Удаление аккаунта = анонимизация, не perm-delete (см. `02-customer-lifecycle.md` BP-CUS-05). |
| **ОФД** | Оператор Фискальных Данных. Получает чеки от ATOL и передаёт в ФНС. |
| **PCI DSS** | Стандарт безопасности карточных данных. Карты у нас не хранятся — всё через YooKassa hosted page. |

---

## Версионирование API

| Термин | Значение |
|---|---|
| **V1 / V2 / V3 / V4** | Версии Integration `/order/create`. Все четыре живы. Site/Mobile на современных билдах = V4; legacy на V1. |
| **V5 (mobile)** | `/api/mobile/v5/checkout/*` — mobile-обёртка вокруг V4 Integration. |
| **release-26.06** | Текущая release-ветка Integration и ENSI customers-api-web (на момент создания доку). |
| **stage** | Активная ветка Site. |
| **release-3.31.0** | Активная ветка Mobile. |

---

**Дата создания:** 2026-05-16
