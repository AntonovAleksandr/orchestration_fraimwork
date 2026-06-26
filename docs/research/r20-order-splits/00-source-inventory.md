# R-20 «Сплиты заказов» — инвентаризация источников

Все источники для исследования. ID проверены через MCP Buddy 2026-06-17 (confidence: high для существования,
содержание сверяется на стадиях).

## 1. Confluence (space OMNIES)

| page_id | Заголовок | Роль |
|---|---|---|
| `108057394` | **R-20 Сплиты заказов** | Главный источник требований (v22) |
| `73794036` | CR37 — СТАРАЯ ВЕРСИЯ Сплит заказов | Дочерняя к R-20; история требований |
| `165406777` | Многоместные отправления | Смежная (не путать со сплитом заказа) |
| `108038924` | 5 [Кейс Склад FF Курьер] Собран в полном объёме… до COMPLETED | Статусная схема отправлений |
| `130135623` | 6 [Кейс CC] Перемещение Click&Collect Московский склад | Кейс C&C |
| `130135894` | Схема движения складских заказов | Жизненный цикл складского заказа |
| `86312438` / `130133888` | [НСК]/[МСК Новый склад] PICKING-DELIVERING | Складские статусы по площадкам |
| `118314641` | 6. Шпаргалка для ОТС | Контекст ОТС-интеграции |
| `165391028` | Задачи чекаута | Бэклог чекаута |
| `165397824/826/828` | Интеграция Яндекс Пэй и СПЛИТ (+ API/Интеграции) | ⚠️ Яндекс.Сплит = ОПЛАТА, не R-20. Только дизамбигуация |

**Вложения R-20 (`108057394`) — выгрузить на Stage 01:**

| attach_id | Файл | Тип | Зачем |
|---|---|---|---|
| `108064181` | Сплит vs Мультизаказ (1).docx | docx | Концептуальное различие сплит/мультизаказ |
| `108061905` | Сплит заказы | drawio (mxfile) | Схема решения |
| `108061906` | Сплит заказы.png | png | Та же схема (картинкой) |
| `108059749` | image-2024-4-10_13-41-3.png | png | Пример реализации отправлений на Ozon |
| `108059751` | image-2024-4-10_13-46-40.png | png | Пример расчёта (склады) |
| `108057436-439` | image2023-3-9_*.png | png | Демо-решение Starfish 22.02.2023 |
| — | excellentable (в теле, macro-id `89493144…`) | таблица | **Модель состава отправлений** (поля родитель/отправление) |

> Выгрузка вложений: прямого download-tool в MCP нет (есть только upload/update). Варианты на Stage 01:
> скачать вручную из Confluence в `logs/research/r20-order-splits/` (gitignored) и разобрать, либо
> восстановить модель данных по `excellentable` через API контента. drawio — экспортнуть в png для чтения.

## 2. Jira

| key | Заголовок | Роль |
|---|---|---|
| `OPSOMN-343` | **Сплит заказа (доставка по частям)** (e-Story, Новый, 2023) | Jira-counterpart R-20 |
| `OPSOMN-13343` | Сайт+МП: Интеграция Яндекс.Сплит (Epic) | ⚠️ Яндекс.Сплит-ОПЛАТА (дизамбигуация) |
| `OPSLOG-3267` | [Yandex] Заказ застревает на ORDER_SPLIT из-за id_transport в 1С WMS | **ORDER_SPLIT существует**; 1С/WMS |
| `OPSLOG-3169` | [DPD] ОТС не может получить статус ORDER_SPLIT для курьерских DPD | ORDER_SPLIT в ОТС/ТК |
| `DEVOMN001-5130` / `-5152` | [Курьер]/[ПВЗ] Отмена на ORDER_SPLIT | Отмена отправления; статус ORDER_SPLIT |
| `OPSOMN-11606` | [ИС] Логика обновления статуса заказа при неполной сборке | ИС ↔ OMS неполная сборка (FR-13) |
| `OPSLOG-1344` / `DEVLOG001-1603` | Удаление строк из split order в транзакцию | **Таблица `split order` в логистике** |
| `OPSOMN-7274` | Пересмотр выгрузки pickedSKU/fulfilledSKU в DWH | DWH-выгрузка заказов (FR-18) |
| `OPSOMN-9426` / `-9803` / `-14175` | Некомплект / checked_invalid складских заказов | Краевые случаи фулфилмента |

JQL для добора: `project in (OPSOMN001,OPSOMN,OPSLOG,DEVOMN001,DEVLOG001) AND text ~ "ORDER_SPLIT"`,
`text ~ "отправлени"`, `text ~ "докомплект"`.

## 3. Наши BP / research доки (не дублировать — ссылаться)

| Файл | Релевантность |
|---|---|
| `docs/bp/04-checkout-order-creation.md` | Чекаут / создание заказа (Stage 06) |
| `docs/bp/06-fulfillment-and-delivery.md` | Фулфилмент, доставка, НСИ, ОТС (Stage 02,04) |
| `docs/bp/07-post-order-and-comms.md` | Пост-заказ, статусы, уведомления (Stage 03,13) |
| `docs/bp/03-browse-cart-precheckout.md` | Корзина / pre-checkout (Stage 06) |
| `docs/research/2026-05-20-checkout-order-creation.md` | Индекс по чекауту |
| `docs/research/2026-05-29-checkout-as-is-archaeology.md` | As-is археология чекаута |
| `docs/research/delivery-carrier-codes-end-to-end.md` | Коды ТК/доставки (Stage 04) |
| `docs/research/surf-mini-rewrite/deep-dive/stages/stage-06-checkout-order-creation.md` | Split в чекауте (наблюдение: «мультисклад = первый склад») |
| `docs/research/surf-mini-rewrite/deep-dive/stages/stage-09b-ots-dpd-cdek-pvz.md` | ОТС/DPD/CDEK/PVZ |

## 4. Код (локально, после `./scripts/sync-platform-repos.sh`)

| Домен | Путь(и) |
|---|---|
| OMS заказ/сток/доставка | `platform/starfish24/core/{Order,Stock,Delivery,Dictionary}` |
| OMS процессы/воркеры | `platform/starfish24/core/{Camunda,BPM,camunda-worker}`, BPMN: `platform/starfish24/awg/bpmn-process/process` |
| OMS логистика (Go, split) | `platform/starfish24/core/go/logistics` |
| OMS конфиги ЛГ (per-env) | `platform/starfish24/awg/cloud-configs` |
| ОТС / ТК | `platform/gloriaots/gloriaots/src` (ShipmentServices, OrderTracking, WmsSync, EventBus) |
| Integration Service | `platform/integration/integration/www` (+ libs logger/msq-client/health) |
| ENSI корзина/чекаут | `platform/ensi/apps/orders/{baskets,order-group-service}`, `platform/ensi/apps/customers-api-web` |
| Сервер скидок (клиент) | искать в ENSI/ИС: discount client (`docs/superpowers/plans/2026-05-30-discount-client.md`) |
| Admin GUI | `platform/ensi/apps/admin-gui/{admin-gui-backend,admin-gui-frontend}` |
| Сайт | `platform/site/gj-ng-front` (libs/modules/checkout) |
| Мобайл | `platform/mobile-app/gj-app/packages/gj` |

## 5. БД / логи (MCP `data_*`) — см. §3 в `00-PLAN.md`

Перед стадией уточнять каталог через `data_list_targets`. Ключевые: `oms-awg-order-prod`,
`oms-awg-stock-prod`, `oms-awg-camunda-prod`, `oms-logistics-prod`, `gloria_ots_prod`,
ENSI `ensi-gs-baskets-*` / order-group-service, ИС `oms-is-stage-integration*`.
Логи: `logs-oms-prod`, `integration-awg-new-logs-prod`, `logs-notigo-prod`.
