# ENSI — Карта бизнес-процессов

**Скоуп**: домены, владельцем которых выступает ENSI: catalog (PIM, offers, feed, catalog-cache), customers (customers, customer-auth), orders/baskets, customers-api-web (BFF). Связанные сервисы — audit, cdn-adapter, event-dispatcher (PHP + Go), bu — упомянуты кратко.

**Что НЕ покрыто**: чекаут-flow (см. `do../research/2026-05-20-checkout-order-creation.md`), сам Integration, OMS, Site, Mobile.

**Дата**: 2026-05-16. Ветки PIM/offers/customers — `master`/`dev-master`/`dev-release-26.06`; customers-api-web — `release-26.06`.

**Соглашение по Kafka-топикам** (см. `platform/ensi/apps/catalog/pim/app/Domain/Kafka/TopicNameBuilder.php`):
```
{contour}.{feature}.{domain}.{classification}.{description}.{version}
```
где `classification` ∈ {`fct` (fact), `inc` (increment), `cdc` (change-data-capture), `cmd` (command), `sys` (system)}. По умолчанию `feature='all'`, `domain='ecom'`, `version=0`. Пример: `prod.all.ecom.fct.cc-products.0`. **Контур** берётся из `config('kafka.contour')`.

---

## Содержание

1. Catalog Management
   - BP-CAT-01: Заведение и обновление карточки товара (Product / SKU)
   - BP-CAT-02: Импорт товаров (Excel) и start-date цен
   - BP-CAT-03: Импорт изображений
   - BP-CAT-04: Экспорт товаров (admin-инициированный)
   - BP-CAT-05: Категории, рекомендации и атрибуты (управление справочниками)
   - BP-CAT-06: Индексация для публичной выдачи (catalog-cache)
   - BP-CAT-07: Генерация и отгрузка фидов на маркетплейсы
2. Pricing & Offers
   - BP-OFF-01: Импорт цен и пересборка офферов (PHP `offers`)
   - BP-OFF-02: Пересборка офферов через Go (`offers-go`) — параллельная реализация
   - BP-OFF-03: Сток (остатки) — Kafka push-flow
   - BP-OFF-04: SKU obsolete / "выводимые из ассортимента"
   - BP-OFF-05: Промо и акции на товары
3. Customer Lifecycle
   - BP-CUS-01: Регистрация по телефону (SMS OTP)
   - BP-CUS-02: Логин и токен-flow (passport + кастомные grants)
   - BP-CUS-03: Обновление профиля и адресов
   - BP-CUS-04: Бонусная программа / Discount-карта (внешний 1С)
   - BP-CUS-05: Удаление аккаунта / персональных данных
   - BP-CUS-06: Delivery preferences (предпочтения доставки)
   - BP-CUS-A: Admin-Auth (упоминание)
4. Cart / Basket
   - BP-BSK-01: Жизненный цикл корзины (init, merge, clean)
   - BP-BSK-02: Изменение состава, isSelected и пересчёт
   - BP-BSK-03: Промо-код и купоны
   - BP-BSK-04: Реакция на изменения офферов (Kafka in)
   - BP-BSK-05: Реакция на оформленный заказ (Kafka in)
   - BP-BSK-06: Избранное (favorites — сопутствующий)
5. Customer-facing BFF — `customers-api-web` (кроме чекаута)
   - BP-BFF-01: Каталог (поиск, карточки, рекомендации)
   - BP-BFF-02: Корзина (proxy + обогащение)
   - BP-BFF-03: Профиль и его данные
   - BP-BFF-04: Notifications / SEO / Navigation / Promotions
6. Связанные сервисы
   - audit, cdn-adapter, event-dispatcher (PHP+Go), bu

---

## 1. Catalog Management

### BP-CAT-01: Заведение и обновление карточки товара (Product / SKU)

**Триггер**: контент-менеджер сохраняет карточку в admin-gui (admin-gui-backend → pim) ИЛИ внешний импорт через API.

**Акторы**: контент-менеджер, admin-gui-backend, pim-service.

**Сервисы**: `catalog/pim` → (Kafka) → `catalog/offers`, `catalog/catalog-cache`, `connectors/ensi-connector` (внешний коннектор для downstream).

**Шаги**:
1. Контроллер `App\Http\ApiV1\Modules\Products\Controllers\ProductsController` (path: `platform/ensi/apps/catalog/pim/app/Http/ApiV1/Modules/Products/Controllers/ProductsController.php`) принимает запрос.
2. Action из `app/Domain/Products/Actions/Products/` (`CreateProductAction`, `PatchProductAction`, `ReplaceProductAction`, `SetProductDataAction`, `DeleteProductAction`).
3. Eloquent persist → срабатывает observer `ProductAfterCommitObserver::created/updated/deleted` (`app/Domain/Products/Observers/ProductAfterCommitObserver.php`). **Сертификаты (`TypeOfGood::CERTIFICATE`) пропускаются** — это нетоварная сущность.
4. Observer вызывает `SendProductEventAction` и (при изменении `vendor_code`/`base_product_id`) `SendSkuProductEventAction` для каждого SkuProduct товара.
5. `SendKafkaMessageAction` (`app/Domain/Kafka/Actions/Send/SendKafkaMessageAction.php:12`) публикует через `HighLevelProducer`. **Sync produce** — внутри HTTP-запроса админки, не через outbox. → потенциальный риск частичной публикации при сбое Kafka.
6. Параллельно есть отдельный поток: `App\Domain\Products\Events\ProductChanged` → `ProductChangedMessage` (`app/Domain/Kafka/Messages/Send/Event/ProductChangedMessage.php:32` → топик `*.all.ecom.cdc.products.0`).

**Данные**:
- `products`, `sku_products`, `product_property_values`, `product_images`, `base_products`, `category_product_links`, `color_links`, `size_links`.
- Атрибуты — `properties`, `property_directory_values`.
- См. миграции: `2021_09_20_081213_init_products.php`, `2024_11_29_120822_alter_products.php`, `2025_02_18_105812_add_url_column_in_categories_table.php`.

**Исходящие события (Kafka, fact-топики)** — по моделям, через `SendXxxEventAction`:
| Топик (description) | Продюсер | Событие |
|---|---|---|
| `cc-products` | `SendProductEventAction.php:21` | create/update/delete |
| `sku-product-vendor-codes` | `SendSkuProductEventAction.php:21` | create/update/delete |
| `base-products` | `SendBaseProductEventAction.php` | create/update/delete |
| `categories` | `SendCategoryEventAction.php` | … |
| `category-links` | `SendCategoryLinkEventAction.php` | … |
| `category-product-links` | `SendCategoryProductLinkEventAction.php` | … |
| `colors` / `color-links` | `SendColorEventAction.php` / `SendColorLinkEventAction.php` | … |
| `sizes` / `size-links` | `SendSizeEventAction.php` / `SendSizeLinkEventAction.php` | … |
| `product-images` | `SendProductImageEventAction.php` | … |
| `product-property-values` | `SendProductPropertyValueEventAction.php` | … |
| `properties` | `SendPropertyEventAction.php` | … |
| `property-directory-values` | `SendPropertyDirectoryValueEventAction.php` | … |
| `recommendation-marks` | `SendRecommendationMarkEventAction.php` | … |

Дополнительно: `*.all.ecom.cdc.products.0` (CDC-style, через `ProductChangedMessage`).

Все вышеуказанные сообщения наследуют `ModelEventMessage` (`Kafka/Messages/Send/ModelEvent/ModelEventMessage.php`) с payload-полями {`dirty`, `attributes`, `event`}.

**Где смотреть в коде**:
- `platform/ensi/apps/catalog/pim/app/Domain/Products/Actions/Products/*.php`
- `platform/ensi/apps/catalog/pim/app/Domain/Products/Observers/*.php`
- `platform/ensi/apps/catalog/pim/app/Domain/Kafka/Actions/Send/`
- `platform/ensi/apps/catalog/pim/app/Domain/Kafka/Messages/Send/ModelEvent/`

**Quirks / костыли**:
- **Sync produce внутри HTTP-обзёрвера** — если Kafka недоступна, фронт-операция упадёт (или, хуже, в БД сохранится, а Kafka-сообщение — нет, в зависимости от обработки исключений).
- **Сертификаты намеренно пропускаются** в `ProductAfterCommitObserver:25,37,52`. Это сделано не везде — `SkuProductAfterCommitObserver` нужно проверить отдельно.
- На обновлении нет detection "что именно поменялось": observer тригерится на любой `update`, в Kafka летит полный snapshot + `dirty` (массив ключей изменённых полей).
- ProductChanged-event дублирует `cc-products` в CDC-топике — назначение менее очевидно (история / late consumers).

---

### BP-CAT-02: Импорт товаров и start-date цен (Excel)

**Триггер**: контент-менеджер загружает Excel в админке или вызывает API.

**Акторы**: контент-менеджер, admin-gui-backend, pim-service.

**Шаги**:
1. Файл сохраняется в storage; создаётся запись `ProductExcelImport` (?).
2. Action из `app/Domain/Imports/Actions/ProductExcel/` (Excel parsing) запускается в очереди.
3. Для каждой строки — `ImportProductAction` / `SetProductDataAction` (как в BP-CAT-01) → каскадно публикует Kafka-события на каждое изменение.
4. Также — `ImportProductsSaleStartDateAction.php` (`Domain/Products/Actions/Products/`) для массового задания дат старта продаж.

**Данные**: те же `products`, `sku_products`, но с массовым batch-write.

**Где смотреть**:
- `platform/ensi/apps/catalog/pim/app/Domain/Imports/Actions/ProductExcel/`
- `platform/ensi/apps/catalog/pim/app/Domain/Products/Actions/Products/ImportProductAction.php`

**Quirks**: Excel-импорт — синхронный? Очередь? Нужно проверить, какой queue connection используется (Laravel Horizon vs sync).

---

### BP-CAT-03: Импорт изображений

**Триггер**: админ или массовый импорт.

**Шаги**:
1. Endpoint в `Modules/Products/Controllers/` или массовый импорт.
2. `app/Domain/Imports/Actions/Images/` — загрузка / привязка изображения к товару.
3. `PreloadImageAction.php` (`Domain/Products/Actions/Products/`) — pre-fetch.
4. Файлы хранятся: см. `connectors/cdn-adapter` для URL-resolution (`MakeImgProxyUrlAction.php` — генерация ImgProxy URL).
5. Observer `ProductImageAfterCommitObserver` → `SendProductImageEventAction` → топик `*.fct.product-images.0`.

**Quirks**: imgproxy конфиг — config `services.imgproxy.base_uri` (`cdn-adapter/app/Domain/Media/Actions/MakeImgProxyUrlAction.php:17`). **Hardcoded sizeMap** (300x300, 365x246, 500x500, 515x515, 1200x1200, 762x1100) с retina-вариантами — добавление новых размеров требует деплоя.

---

### BP-CAT-04: Экспорт товаров (admin-инициированный)

**Триггер**: админ нажимает "экспорт" в admin-gui-backend для пакетной выгрузки.

**Шаги**:
1. `CreateProductExportAction.php` — создаёт `ProductExport` запись.
2. `StartExportViaQueueAction.php` — кидает в очередь.
3. `ExportProductsAction.php` (или варианты `ExportProductsOffersWithFiltersAction`, `ExportProductsWithOfferFiltersAction`) — формирует Excel.
4. `AvailableProductExportFieldsAction.php` — отдаёт список доступных колонок.

**Где**:
- `platform/ensi/apps/catalog/pim/app/Domain/Exports/Actions/*.php`
- `platform/ensi/apps/catalog/pim/app/Domain/Exports/ExcelExports/`, `ExportHandlers/`

**Quirks**: ничего необычного для админ-флоу.

---

### BP-CAT-05: Категории, рекомендации, атрибуты

**Триггер**: админ или массовый импорт.

**Сущности**: `Category`, `Property`, `PropertyDirectoryValue`, `ProductRecommendation`, `ProductRecommendationMark`.

**Шаги**:
1. CRUD через `Modules/Categories/`, `Modules/ProductRecommendations/`, `Modules/ProductRecommendationMarks/`.
2. Каждое изменение → observer → `Send*EventAction` (см. BP-CAT-01 таблицу).

**Quirks**:
- `UpdateProductsRecommendationMarksAction.php` — массовая привязка меток к товарам.
- `category-product-links` поддерживает уникальность через миграцию `2023_01_23_131858_add_unique_constraint_to_category_product_links.php`.
- `linking_priority` и `linking_is_visible` добавлены в category_product_links в `2025_02_10_073252_*`.

---

### BP-CAT-06: Индексация для публичной выдачи (catalog-cache)

**Триггер**: входящие Kafka-сообщения из PIM, offers, BU, CMS.

**Акторы**: catalog-cache как consumer.

**Сервисы**: PIM, offers, BU, CMS → Kafka → `catalog/catalog-cache` → Elasticsearch.

**Шаги**:
1. Kafka-consumer (`platform/ensi/apps/catalog/catalog-cache/app/Domain/Kafka/Actions/Listen/Listen*Action.php` — отдельный handler на каждый топик):
   - `ListenProductAction` ← `*.fct.cc-products.0`
   - `ListenSkuProductAction` ← `*.fct.sku-product-vendor-codes.0`
   - `ListenBaseProductAction` ← `*.fct.base-products.0`
   - `ListenCategoryAction`, `ListenCategoryLinkAction`, `ListenCategoryProductLinkAction`
   - `ListenColorAction`, `ListenColorLinkAction`, `ListenSizeAction`, `ListenSizeLinkAction`
   - `ListenProductImageAction`, `ListenProductPropertyValueAction`, `ListenPropertyAction`, `ListenPropertyDirectoryValueAction`
   - `ListenProductTypeAction`, `ListenProductTypeCategoryLinkAction`
   - `ListenMessageAction`, `ListenMessageBaseStoreLinkAction`, `ListenMessageProductLinkAction` (от CMS)
   - `ListenNameplateAction`, `ListenNameplateBaseStoreLinkAction`, `ListenNameplateProductLinkAction` (от CMS)
   - `ListenOfferAction` / `ListenOfferStoresAction` ← `*.fct.offers.1` / `*.fct.offer-stores.1`
   - `ListenChangedOffersAction` ← дополнительный
   - `ListenRegionAction` ← от BU
   - `ListenRecommendationMarkAction`
2. `SyncModelAction.php` upsert в PostgreSQL-реплику (модели в `Domain/Offers/Models/` — `Product`, `Offer`, `SkuProduct`, `Category`, `Color`, `Size`, и т.д.)
3. Observer на модели catalog-cache (`Domain/Offers/Observers/`) ставит **`*IndexingJob`** в очередь (`Domain/Offers/Jobs/OfferIndexingJob.php`, `ProductIndexingJob.php`).
4. Job собирает агрегат (`ComposeProductDataAction`, `ComposeSkuOfferCardsAction`, `ComposeBaseProductCardsAction`, `ComposeRegionalDataAction`) — это **денормализация в широкий ES-документ**.
5. Запись в ES — индексы `OfferIndex` / `ProductIndex` (`Domain/Offers/Elastic/`).
6. Sync*-варианты (`SyncOffersAction.php`, `SyncOfferStoresAction.php`) — batch-варианты.

**Данные**:
- Локальная PostgreSQL-реплика моделей PIM (упрощённая) — для быстрой агрегации.
- ES индексы: `OfferIndex` (по складам/регионам), `ProductIndex` (карточка для каталога).

**Quirks / костыли**:
- **catalog-cache держит копию всех catalog-моделей в собственной БД** — это создаёт лаг (несколько секунд) между публикацией товара и появлением в публичной выдаче.
- При смене схемы (миграция в PIM) нужно вручную выкатить новую миграцию в catalog-cache — нет автосинка схемы.
- `ProductIndexingJob` / `OfferIndexingJob` — если падают, потеря неконсистентности (нужна retry-стратегия — проверить).
- Топики `offers.1` и `offer-stores.1` имеют **версию 1** (не 0) — это значит, что был breaking change (см. BP-OFF-01/02).
- Listener'ов **28+** — высокая поверхность, любое изменение схемы в PIM требует синхронного апдейта здесь.

**Где**: `platform/ensi/apps/catalog/catalog-cache/app/Domain/`

---

### BP-CAT-07: Генерация и отгрузка фидов на маркетплейсы

**Триггер**: cron (Laravel scheduler) или ручной HTTP-запрос.

**Акторы**: `catalog/feed` service.

**Шаги**:
1. Action одной из 12 реализаций:
   - `YandexCcFeedCreateAction.php` (Яндекс CC)
   - `YandexSkuFeedCreateAction.php` (Яндекс SKU)
   - `MarketplaceFeedCreateAction.php`
   - `RSGFeedCreateAction.php`
   - `MindBoxFeedCreateAction.php`
   - `FlocktoryFeedCreateAction.php`
   - `RocketDataFeedCreateAction.php`
   - `RetargetingFeedCreateAction.php`
   - `DwhCatalogFeedCreateAction.php`
   - `AnyQueryFeedCreateAction.php` (универсальный)
   - `TestCcFeedCreateAction.php`
2. `ResolveAnyQueryAvailabilityAction.php` — проверка доступности.
3. Идёт в `FeedGenerators/` собирать XML/CSV (per-feed format).
4. Через `Services/SafeSftpUploader.php` — загрузка по SFTP (либо хранение в S3 — нужно проверить).

**Данные**: фид-файлы (XML/CSV), `feed_files` table (?).

**Где**:
- `platform/ensi/apps/catalog/feed/app/Domain/Feed/Actions/*.php`
- `platform/ensi/apps/catalog/feed/app/Domain/Feed/FeedGenerators/`
- `platform/ensi/apps/catalog/feed/app/Domain/Feed/Services/SafeSftpUploader.php`

**Quirks**:
- "AnyQuery" — динамические фиды (видимо параметризуемые), для нестандартных контрагентов.
- Сайтмап отдельный — `Domain/Sitemap/`.
- В feed нет прямой подписки на catalog Kafka — он **периодически pull**'ит из PIM/offers/catalog-cache через HTTP-клиенты (нужно проверить, см. `composer.json`).

---

## 2. Pricing & Offers

### BP-OFF-01: Импорт цен и пересборка офферов (PHP `offers`)

**Триггер**: cron (`Prices/Actions/FetchChangesAction.php`) или admin trigger.

**Акторы**: внешний WebAPI (мастер цен — 1С/учётка), `offers` service.

**Шаги**:
1. **Pull-модель** (см. `offers-go/docs/sa_prices.md` для архитектурного описания):
   - `RetrieveAuthTokenAction.php` — аутентификация во внешнем WebAPI.
   - `FetchChangesAction.php` — `GET ?since=last_success_ts`.
   - `ImportPriceChangesAction.php` — chunk-по-1000.
2. Внутри каждого чанка: разрешение `sku_article` → `sku_product_id` (через PIM-client), конвертация цен в копейки, фильтр невалидных.
3. `DeleteAndUpsertSkuPricesBatch`-логика (внутри Import-actions): удаление future-цен + UPSERT по `[sku, base_store, validity_date_start]`.
4. Затронутые `sku_product_id` собираются в очередь на пересборку.
5. **Сборка оффера**: для каждого `SkuProduct` + каждый активный `Region` → берётся самая свежая (`validity_date_start <= NOW()`) цена для `region.base_store_code` (`AssembleOfferPriceAction.php`, `AssembleSkuOffersAction.php`).
6. **Diffing**: новые офферы сравниваются с тек. сохранёнными. Только delta записывается в `offers`.
7. `SendUpdatedOffersAction.php` / `SendDeletedOffersAction.php` → Kafka.
8. Параллельные импорты: `ImportProhibitionsAction.php` (запреты на продажу), `ImportStartSellDatesAction.php` (даты старта продаж), `ImportEventsAction.php`, `InitProhibitionsAction.php`, `InitsEventsAction.php`.

**Данные**:
- `sku_prices` (history-table, partitioned by `validity_date_start`)
- `sku_prohibitions`, `sku_sell_start_dates`, `sku_events`
- `offers` (per region), `offer_stores` (per region per warehouse)
- `vendor_codes_of_obsolete_skus` (см. BP-OFF-04)

**Исходящие события Kafka**:
| Топик | Class | Версия |
|---|---|---|
| `*.fct.offers.1` | `OffersEventMessage.php:30` | 1 |
| `*.fct.offer-stores.1` | `OfferStoresBundleMessage.php:30` | 1 |
| `*.fct.sku-totals.0` | `SkuTotalsEventMessage.php:25` | 0 |
| ModelEvent topics (через `ModelEventMessage`) для CRUD моделей | `ModelEventMessage.php:34` | 0 |

**Где**:
- `platform/ensi/apps/catalog/offers/app/Domain/Prices/Actions/*.php`
- `platform/ensi/apps/catalog/offers/app/Domain/Offers/Actions/Offers/`
- `platform/ensi/apps/catalog/offers/app/Domain/Externals/` — клиенты внешних

**Quirks**:
- Будущие цены (`validity_date_start > today`) удаляются перед апдейтом — страховка от отменённой переоценки.
- Diffing — крайне важен: без него любое регио-широкое изменение цены порождало бы тысячи Kafka-событий.
- Bundling в `offer-stores` (см. BP-OFF-02) — несколько регионов с одинаковым `base_store_code` группируются в один JSON-message.

---

### BP-OFF-02: Пересборка офферов через Go (`offers-go`) — параллельная реализация

**Контекст**: ENSI переходит с PHP `offers` на Go `offers-go`. **Обе реализации одновременно в продакшене**, пути ещё не сходились (см. note в `CLAUDE.md`).

**Акторы**: `offers-go` service.

**Шаги** (из `offers-go/docs/sa_kafka_export.md`):
1. **Input Kafka topics** consumed by `cmd/assembler`:
   - SKU events (от PIM)
   - Region events (от BU)
   - RegionStoresWarehouses events (от BU)
   - Stocks (от внешней складской системы — push)
2. `SKUProcessor` flow:
   - Load SKU + active regions
   - Apply assembly logic (parity с PHP `AssembleSkuOffersAction`) в `internal/core/assembly/`
   - Diff vs current state → publish to Kafka
3. **Importer** (`cmd/importer`): periodic + init import из WebAPI/PIM в локальную БД offers-go.
4. **API** (`cmd/api`): HTTP-методы для поиска офферов/остатков + admin-операции.
5. **Range queue** (`assemble_range_queue.go`) — фоновый воркер пересборки по диапазонам SKU.
6. **Migrate** (`cmd/migrate`) — миграции через goose.

**Исходящие topics** (те же что PHP — это критично для downstream):
- `*.fct.offers.1` — bundled по `base_store_code`
- `*.fct.offer-stores.1` — словарь `offer_id → [store_ids]`
- `*.fct.sku-totals.0` — простая сумма стока

**Где**:
- `platform/ensi/apps/catalog/offers-go/internal/core/usecase/` (49 файлов)
- `platform/ensi/apps/catalog/offers-go/internal/adapters/{db,kafka,http,clients}/`
- `platform/ensi/apps/catalog/offers-go/docs/sa_*.md` — отличная архитектурная документация (12 файлов)

**Quirks / Risks**:
- **Дублирование с PHP `offers`**: обе реализации одновременно слушают/публикуют. Возможна гонка — кто последним записал в Kafka. **ПРОВЕРИТЬ** конфигом, кто из них сейчас "primary" producer (вероятно через consumer-group rebalancing или feature-flag).
- **Schema parity** — Go и PHP версии офферов должны выдавать одинаковый payload. Любой дрейф (типизация, поля) ломает catalog-cache.
- `assemble_range_queue_dedupe.go`, `range_processor_dedupe.go` — есть **специальная дедупликация**, что говорит о ранее реальной проблеме double-processing.
- Документация в `offers-go/docs/sa_obsolete_recalc_flow_revised.md` + `_short.md` — было несколько ревизий obsolete-flow, см. BP-OFF-04.

---

### BP-OFF-03: Сток (остатки) — Kafka push-flow

**Триггер**: внешняя WMS публикует событие в Kafka.

**Акторы**: WMS/учётка (внешняя) → Kafka → `offers` / `offers-go`.

**Шаги (PHP `offers`)**:
1. `StocksListenAction.php` (`app/Domain/Kafka/Actions/Listen/`) — consume.
2. Message — `StocksMessage` (`app/Domain/Kafka/Messages/Listen/StocksMessage.php`).
3. Apply changes к таблице `stocks` (модель `Domain/Prices/Models/Stock.php`).
4. Триггерится пересборка офферов (тот же flow что BP-OFF-01).

**Шаги (`offers-go`)**:
- `internal/core/usecase/stocks_event_handler.go`
- `internal/core/usecase/stocks_init.go` / `stocks_init_service.go` — init-режим (массовая первичная загрузка).

**Где**:
- PHP: `platform/ensi/apps/catalog/offers/app/Domain/Kafka/Actions/Listen/StocksListenAction.php`
- Go: `platform/ensi/apps/catalog/offers-go/internal/core/usecase/stocks_*.go`

**Quirks**:
- Сток — **push** (Kafka), цены — **pull** (HTTP). Это разные SLA и разные паттерны отказа.
- При init нужна полная загрузка всех стоков → `stocks_init_service.go`.

---

### BP-OFF-04: SKU obsolete / "выводимые из ассортимента"

**Триггер**: периодический cron или импорт.

**Контекст**: товары, которые перестали обновляться основным потоком, но остались на складе для распродажи. Им нужно специальное поведение — point lookup цен.

**Шаги (PHP `offers`)**:
1. `ImportSkuObsoleteItemsAction.php` (`Domain/Prices/Actions/SkuActualize/`) — массовая отметка SKU как obsolete.
2. `LoadSkusByBarcodesAction.php`, `LoadReplacementsAction.php`, `FilterReplacementsAction.php` — поиск товаров-заменителей через PIM.
3. `SaveObsoleteAction.php` — запись в `vendor_codes_of_obsolete_skus`.
4. Для obsolete SKU отдельный flow — точечный запрос цен в WebAPI (по списку vendor_code).

**Шаги (`offers-go`)**:
- Документация: `docs/sa_obsolete.md`, `sa_obsolete_recalc_flow.md`, `sa_obsolete_recalc_flow_revised.md`, `sa_obsolete_recalc_flow_short.md` (4 итерации описания процесса!)

**Quirks**:
- 4 ревизии документа сигнализируют что **процесс был переработан несколько раз** — это горячая зона.
- В `offers/database/migrations/2024_03_28_073021_create_barcodes_of_obsolete_skus.php` и `2024_06_04_084546_rename_table_barcodes_of_obsolete_skus.php` — переименование таблицы.

---

### BP-OFF-05: Промо и акции на товары

**Триггер**: акция настраивается в PIM (`Domain/Promotions/Models/ProductPromotion.php`).

**Шаги**:
1. Контент-менеджер настраивает акцию через admin-gui-backend.
2. Создаётся `ProductPromotion` (миграция: `2025_12_09_050528_craete_table_product_promotion.php` — **опечатка в имени** ("craete")).
3. Внешний клиент: `Domain/Promotions/Client/PromotionServiceClient.php` — взаимодействует с **внешним promotion service** (нужно проверить URL в config).
4. В catalog-cache promo подтягиваются через `customers-api-web` → `Domain/Promotions/Actions/ProductPromotionAction.php`.

**Где**:
- `platform/ensi/apps/catalog/pim/app/Domain/Promotions/`
- `platform/ensi/apps/customers-api-web/app/Domain/Promotions/Actions/ProductPromotionAction.php`

**Quirks**:
- **Promotions хранятся в отдельной внешней системе** (не в pim DB) — клиент `PromotionServiceClient` ходит наружу.
- Опечатка в имени миграции — типичный сигнал спешки.
- Promo-логика в чекауте — отдельно (см. checkout-flow.md, OPSOMN001-340 "site бонусные рубли").

---

## 3. Customer Lifecycle

### BP-CUS-01: Регистрация по телефону (SMS OTP)

**Триггер**: пользователь вводит телефон на сайте/мобайле → `customers-api-web` → `customer-auth`.

**Акторы**: посетитель, customers-api-web, customer-auth, customers, внешний SMS-провайдер (Devino).

**Шаги**:
1. **Site/Mobile** → `customers-api-web GenerateConfirmationCodeAction.php` (`Domain/Auth/Actions/`).
2. → `customer-auth/Domain/Users/Actions/ConfirmationCodes/GenerateConfirmationCodeAction.php`.
3. `CreateConfirmationCodeAction.php` — генерация числового кода, save в `confirmation_codes` table.
4. `SendConfirmationCodeAction.php` → `DevinoClient` (`Domain/Clients/DevinoClient.php`) — `POST /sms/messages` (Devino API).
5. Возврат на фронт: code-sent acknowledged.
6. Пользователь вводит код → `CheckConfirmationCodeAction.php` → проверка по `confirmation_code` + `User.auth_attempt_count`.
7. На success — создаётся `User` (`customer-auth/Domain/Users/Models/User.php`).
8. Параллельно — `CreateCustomerAction.php` (`customers/Domain/Customers/Actions/Customer/CreateCustomerAction.php`) создаёт профиль в `customers` service.
9. Issued tokens — Laravel Passport (`HasApiTokens` trait в `User.php`).
10. Welcome — `SendCustomerRegisteredEventAction` → Kafka топик `*.sys.email-communications.0` (через `CustomerRegisteredMessage.php:29`).

**Константы (User.php:38-42)**:
```php
CONFIRMATION_CODE_LIFE_TIME = 1            // 1 минута
CONFIRMATION_CODE_FAILURE_LIMIT = 3        // 3 попытки до блока
SHORT_USER_BLOCK_PERIOD = 2                // 2 минуты блока
ALLOWED_CODE_SEND_COUNT = 2                // 2 отправки до короткого блока
ALLOWED_CODE_SEND_COUNT_PER_DAY = 5        // 5 отправок в сутки
```

**Данные**:
- `customer-auth.users` (id, email, login=phone, is_active, auth_attempt_count, is_blocked, blocked_at)
- `customer-auth.confirmation_codes`
- `customers.customers`, `customers.addresses`, `customers.children`, `customers.recipients`, `customers.delivery_preferences`, `customers.sizes_selected`

**Исходящие Kafka events**:
- `customers` → `*.fct.customers.0` (на создание/изменение профиля, через `SendCustomerEventAction`)
- `customers` → `*.fct.ensi-customers.0` (`CustomerToDiscountMessage.php:47` — для интеграции с DiscountService)
- `customers` → `*.sys.email-communications.0` (welcome-email, `CustomerRegisteredMessage`)

**Quirks**:
- **`User.id` — `$incrementing = false`** (`User.php:43`) — id заводится извне, скорее всего из `customer-auth.RegisterCustomerAction` синхронизируется с `customers.id`.
- **Fake confirmation codes** — `Domain/Users/Actions/ConfirmationCodes/Fake/` — для dev/test окружений, обходит реальную отправку.
- Devino API — конфигурируется через `config('services.devino')`. Sender address отдельно.
- В customer-auth также есть `ExpertSenderClient` (`Domain/Clients/ExpertSenderClient.php`) — параллельный канал, видимо email-based коммуникации.

---

### BP-CUS-02: Логин и токен-flow

**Триггер**: пользователь логинится повторно (refresh token / login by code / login by avatar).

**Шаги**:
1. `customers-api-web LoginAction.php` или `LoginV2Action.php` (273 LoC, новая версия с merge-basket-on-login — OPSOMN001-182, см. checkout-flow.md).
2. → `customer-auth` Passport — кастомные grants:
   - `CodeGrant.php` (`Domain/Users/Grants/`) — для логина по SMS-коду.
   - `AvatarGrant.php` — для логина через сторонние сервисы / refresh.
3. Соответствующие repository: `CodeGrantUserRepository.php`, `AvatarGrantUserRepository.php`.
4. `ValidateForCodeGrantAction.php` / `ValidateForAvatarGrantAction.php` — проверки.
5. `RevokeTokensAction.php` — при logout.
6. На login V2 — `MergeBasketsAction` (см. BP-BSK-01).

**Где**:
- `platform/ensi/apps/customers-api-web/app/Domain/Auth/Actions/{LoginAction,LoginV2Action,GetTokenAction,RefreshTokenAction,LogoutAction}.php`
- `platform/ensi/apps/customers/customer-auth/app/Domain/Users/Grants/`

**Quirks**:
- **Два варианта login** — V1 и V2. V2 содержит merge-basket-on-login flow.
- Кастомные Passport grants — `AvatarGrant` / `CodeGrant` (не стандартные password / authorization_code).

---

### BP-CUS-03: Обновление профиля и адресов

**Триггер**: пользователь меняет данные в личном кабинете.

**Шаги**:
1. `customers-api-web` actions: `GetCustomerProfileAction`, `SetDeliveryAddressV2Action`, etc.
2. → `customers/Domain/Customers/Actions/Customer/PatchCustomerAction.php`, `ReplaceCustomerAction.php`.
3. `Customer` observer публикует Kafka event через `SendCustomerEventAction` → `*.fct.customers.0`.
4. Address: `Domain/Customers/Actions/Address/` → миграция `2024_08_27_191433_alter_addresses_add_full_address.php` добавила `full_address`. → `SendAddressEventAction` → `*.fct.addresses.0`.
5. **Children** — детская подкарта (для targeting по детским размерам): `Domain/Customers/Actions/Child/`.
6. **Recipients** — получатели (для доставки на чужое имя): `Domain/Customers/Actions/Recipients/`.

**Quirks**:
- `MakeUpperCaseCustomerEmailToLowerCaseAction.php` — нормализация email. Сигнал, что когда-то были дубли по case.
- `Duplicates/` подпапка в Actions — отдельные actions для разрешения дублей профилей: `FindAndFillCustomerCardAction.php`, `GetDuplicateCustomerFieldsAction.php`.
- В миграции `2024_08_30_125834_add_unique_on_email_column_in_customers_table.php` уникальность email появилась поздно — значит исторически были дубли.

---

### BP-CUS-04: Бонусная программа / Discount-карта (внешний 1С)

**Триггер**: customer регистрируется / совершает покупку / запрашивает баланс.

**Акторы**: customer, customers service, внешний DiscountService (1С/Loyalty system), Mindbox.

**Шаги**:
1. На создании customer'а → `DiscountServiceCreateCardAction.php` (`customers/Domain/Discounts/Actions/`) → внешний XML-API через `DiscountApiClient.php`.
2. Search: `DiscountServiceSearchAction.php`, `DiscountServiceSearchByCardAction.php`, `DiscountServiceSearchByPhoneAction.php`.
3. Подтверждение через код: `DiscountServiceGetConfirmationCodeAction.php` → внешний шаг.
4. Балансы: `DiscountServiceGetCertBalanceAction.php` (баланс подарочного сертификата), `MindboxGetCardOperationAction.php` (Mindbox операции).
5. Запросы — **XML** (через `SimpleXMLElement`), `wordKey` (`SecondaryData::DISCOUNT_SERVICE_SECRET_WORD_KEY`) — устаревший паттерн аутентификации (см. `DiscountApiClient.php:31`).
6. Создание discount card → Kafka event `*.fct.discount-card-created.0`-equivalent через `SendDiscountCardCreatedEventAction` → топик `*.sys.email-communications.0` (?) → проверить через `DiscountCardCreatedMessage.php:33` — реально использует `system('all', 'email-communications')` (для email уведомления).
7. Customer → DiscountService sync: `SendCustomerToDiscountsAction` → `*.fct.ensi-customers.0` (топик `CustomerToDiscountMessage.php:47`).
8. Обратный flow: DiscountService → `customers` через `CustomerFromDiscountListenAction.php` (`Domain/Kafka/Actions/Listen/`) — события из внешней системы об изменении карт.

**Где**:
- `platform/ensi/apps/customers/customers/app/Domain/Discounts/`
- `platform/ensi/apps/customers/customers/app/Domain/Customers/Actions/Mindbox/`

**Quirks / костыли**:
- **Внешний XML API** — `DiscountApiClient.php` использует `SimpleXMLElement`, `wordKey` (shared secret) — наследие 1С. Хрупко: невалидный XML → exception.
- `clientId = '5105'` — захардкожен как `COMMON_CLIENT_ID` (`DiscountApiClient.php:27`).
- `$word` (secret) кешируется в `$this->word` — без TTL? Нужно проверить, не утечёт ли expired секрет в long-living процессе.
- **Mindbox-интеграция параллельная** — `customer-auth/Domain/Mindbox/Actions/SendEmailWithConfirmationCodeAction.php` — Mindbox используется для emails вместо собственного SMTP.
- Сертификаты — отдельная сущность (`Domain/Customers/Models/CertificateCheckAttempt.php`), есть лимит попыток (`2023_06_22_*_add_blocked_certificate_check_untill_to_customers_table.php`).

---

### BP-CUS-05: Удаление аккаунта / персональных данных

**Триггер**: customer запрашивает удаление аккаунта (152-ФЗ).

**Шаги**:
1. `customers-api-web DeleteCustomerAccountAction.php` (`Domain/Customers/Actions/`).
2. → `customers/Domain/Customers/Actions/Customer/DeleteAccountAction.php` или `DeletePersonalDataAction.php`.
3. `DeactivateBlockedUserAction.php` — отдельный сценарий деактивации.
4. `User.DELETED_PERSONAL_DATA_LOGIN = '00000000000'` (`customer-auth/Domain/Users/Models/User.php:34`) — служебный логин-стаб для удалённых.
5. Customer model переводится в anonymized state; tokens revoked.

**Quirks**:
- `00000000000` как login для удалённых — позволяет соблюсти `NOT NULL` на login и при этом скрыть phone. **Все удалённые аккаунты будут конфликтовать по login** — нужно проверить, есть ли UNIQUE constraint на login (вероятно нет, или partial index).

---

### BP-CUS-06: Delivery preferences

**Триггер**: пользователь выбирает предпочтения доставки в чекауте или личном кабинете.

**Шаги**:
1. `customers-api-web` POST `/api/v2/customer-delivery-preferences` / mobile equivalent.
2. → `customers/Domain/Customers/Actions/DeliveryPreference/CreateDeliveryPreferenceAction.php` (`Patch`, `Delete`, `Replace`, `Get` — все CRUD).
3. Persist `DeliveryPreference` model (`Domain/Customers/Models/DeliveryPreference.php`):
   ```
   customer_id | device_id | delivery_type_id | address_id | pickup_point_id | store_id | city_fias_id | region_fias_id | payment_method
   ```
4. Миграция: `2026_02_27_140130_create_delivery_preferences_table.php` (**свежая, февраль 2026**) — это новая фича.

**Где**:
- `platform/ensi/apps/customers/customers/app/Domain/Customers/Actions/DeliveryPreference/`
- `platform/ensi/apps/customers/customers/app/Domain/Customers/Models/DeliveryPreference.php`

**Quirks**:
- Поддерживает и `customer_id` (для зареганных), и `device_id` (для анонимных) — но в чекауте mobile использует workaround `customerDeliveryPreferencesTemp` (OPSOMN001-466, см. checkout-flow.md) — значит на BFF слое флоу всё равно не cовсем чистый.
- Таблица **свежая** — много мест ещё не используют её, может быть дрейф.

---

### BP-CUS-A: Admin-Auth (кратко)

**Контекст**: `units/admin-auth` — аутентификация админов (НЕ покупателей).

**Шаги (кратко)**:
1. Login админа в admin-gui-frontend → admin-gui-backend → admin-auth.
2. JWT issuance.
3. Kafka events: при mass change / deactivation / refresh password — топики `*.fct.deactivated-user.0`, `*.fct.generated-password-token.0`, `*.fct.updated-user.0` (`MassChangeActiveAction.php:22`, `UserObserver.php:27,44`, `RefreshPasswordTokenAction.php:23`, `PatchUserAction.php:22`).

**Где**: `platform/ensi/apps/units/admin-auth/`

---

## 4. Cart / Basket

### BP-BSK-01: Жизненный цикл корзины

**Триггер**:
- Анонимный пользователь добавил товар → `customers-api-web` создаёт корзину по `device_id`.
- Зареганный пользователь → корзина по `customer_id`.
- При логине — merge гостевой и пользовательской корзин.

**Шаги**:
1. `InitBasketAction.php` (`baskets/Domain/Baskets/Actions/Basket/`) — просто `return new Basket()` (model only, sync persist в зависимости от вызывающего action).
2. На created — `Basket::booted()` (`Models/Basket.php:90-96`) автоматически генерирует **`number = static::idToNumber($basket->id)`** — какой-то детерминированный mapping. Сохраняет.
3. **MergeBasketsAction** (`Actions/Basket/MergeBasketsAction.php`):
   - Берёт `Basket::whereDeviceId($deviceId)->first()`.
   - Привязывает к customer_id.
   - Запрашивает актуальные офферы через `OffersApi::searchOffers` для пересчёта.
   - Сбрасывает equipment (`ResetBasketEquipmentAction`), регион (`SetBasketsCustomerRegionAction`).
   - Удаляет старую анонимную корзину (`DeleteBasketAction`).
4. **CleanOldBasketsAction** (`Actions/Basket/CleanOldBasketsAction.php`):
   - Удаляет корзины старше **24 часов** (`now()->subHours(24)`).
   - Chunked по 500 (memory-safe).
   - **Запускается через cron** (нужно проверить `app/Console/Kernel.php`).
5. **BlockCustomerBasketAction** / **UnlockCustomerBasketAction** — блокировка для "avatar" (внешнее B2C для сотрудников, особый flow).

**Данные**: `baskets`, `basket_items`, `basket_item_discounts`, `discounts`, `favorite_items`.

**Поля Basket** (`Models/Basket.php:19-37`):
- `number` (отдельный человекочитаемый номер)
- `customer_id` / `device_id` (alternatives)
- `promo_code`, `promo_code_ean`, `promo_code_failed_checks_count`, `promo_code_block_end_at`
- `addition_sales` (JSON — массив доп. акций)
- `bonus_sale`, `bonus_sum` — применение бонусов
- `is_changed`, `is_showed_message` — для UX: показать ли уведомление "корзина изменилась"
- `region_id`, `city_id` (FIAS) — для regional pricing
- `is_blocked_by_avatar`, `is_blocked_by_avatar_at` — особый flow B2C
- `package_is_selected` (миграция `2023_04_20_*`) — для split-shipment

**Quirks**:
- **24-часовой lifetime для анонимных корзин** — захардкожен в `CleanOldBasketsAction.php:18`.
- `ITEMS_QTY_LIMIT = 1000` (`Basket.php:46`) — максимум 1000 позиций в корзине.
- `is_blocked_by_avatar` — внутрений employee flow ("аватар" = служебный аккаунт сотрудника, оформляющего заказ за клиента). Сидит прямо в основной таблице корзин.

---

### BP-BSK-02: Изменение состава, isSelected и пересчёт

**Триггер**: пользователь добавляет/удаляет/меняет qty или toggle "isSelected" в корзине.

**Шаги**:
1. `customers-api-web` → `AddBasketItemAction`, `SetBasketItemsAction`, `SelectBasketItemsAction`, `DeleteAllBasketItemsAction`.
2. → `baskets/Domain/Baskets/Actions/SetItems/SetItemsAction.php` (orchestrator) + `Stages/` (pipeline-style — нужно проверить отдельные стейджи).
3. На каждый item event срабатывает `BasketItemChangedListener.php` (`Domain/Baskets/Listeners/`):
   - Устанавливает `basket.is_changed = true`, `is_showed_message = false`.
   - Сохраняет.
4. На фоне — `CalculateBasketDiscountsAction` пересчитывает скидки. **Только для `isSelected=true` items** (`OPSOMN001-40`).
5. **ActualizeBasketJob** (`Domain/Baskets/Jobs/ActualizeBasketJob.php`) — фоновое actualization.
6. **RecalculateBasketsTotalOldPriceJob** — отдельный recalc для `total_old_price`.
7. `BasketDiscountsCalculatedListener.php` — реакция после пересчёта.

**Миграция `is_selected`**: `2026_02_04_130302_add_is_selected_flag_in_basket_items.php` — свежая (февраль 2026), для split-shipment в чекауте.

**Quirks**:
- **`is_selected` в `basket_items` появилось в феврале 2026** — это значит весь split-shipment-flow относительно молодой. До этого все items считались selected.
- `Basket.is_changed=true` ставится один раз и до явного сброса остаётся (см. `BasketItemChangedListener.php:22-23` — early return если уже `is_changed`).

---

### BP-BSK-03: Промо-код и купоны

**Триггер**: пользователь вводит промокод в корзине.

**Шаги**:
1. `customers-api-web SetBasketPromoCodeAction.php` → `baskets`.
2. → `baskets/Domain/Discounts/Actions/RegisterPromoCodeAction.php` → внешний DiscountsApi (`Support/Client/DiscountsApi/`).
3. Запрос XML-формата (parallel to BP-CUS-04). `DiscountResponseType` (constants, не enum — есть TODO).
4. `RollbackRegisteredPromoCodeAction.php` — отмена при ошибке.
5. `GetDiscountAction.php`, `GetAdditionalSalesAction.php` — получение текущих скидок.
6. Counter попыток ввода — `promo_code_failed_checks_count`, блок — `promo_code_block_end_at` (`2023_09_28_*_add_promo_code_checks_count_to_baskets.php`).

**Quirks**:
- **`DiscountResponseType` не enum** — `// TODO - Почему это не enum?` (`baskets/Domain/Support/Client/DiscountsApi/Data/Discounts/DiscountResponseType.php:5`).
- Анти-фрод: лимит на неуспешные попытки ввода промокода.
- **Functional dead code**: `GetDiscountAction.php:81` `// TODO - Функционал не активный и на бою его быть не должно` — выключенная фича скидок (нужно расследовать что именно).

---

### BP-BSK-04: Реакция на изменения офферов (Kafka in)

**Триггер**: offers / catalog-cache публикует изменения в Kafka.

**Шаги**:
1. `UpdateBasketItemsForOfferAction.php` (`baskets/Domain/Kafka/Actions/Listen/`) consume `*.fct.offers.1` (changed).
2. `ListenChangedOffersAction.php` — отдельный consumer.
3. Apply changes к `basket_items` (цена, availability).
4. Триггерится `ChangedBasketItemFromOfferEvent` (см. BP-BSK-02) → `BasketItemChangedListener` → `basket.is_changed=true`.
5. На фронте при следующем GET basket — флаг `is_changed=true` означает "показать модалку 'корзина изменилась'".

**Где**: `platform/ensi/apps/orders/baskets/app/Domain/Kafka/Actions/Listen/`

**Quirks**:
- Изменения цен из offers применяются **немедленно** при доставке в Kafka (без TTL/grace period) — у клиента в чекауте могут резко поменяться цены.

---

### BP-BSK-05: Реакция на оформленный заказ (Kafka in)

**Триггер**: order создан (commit чекаута → Integration → OMS → Kafka event back).

**Шаги**:
1. `ListenOrderAction.php` (`baskets/Domain/Kafka/Actions/Listen/`) consume order-event message.
2. `CommitOrderEventMessage.php` — структура события.
3. На commit — `DeleteBasketAction` (или массовое удаление выбранных items) → корзина очищается.

**Также**:
- `ListenUpdateBasketDiscountsAction.php` ← `*.fct.update-basket-discounts.0` (`customers` → `baskets`, через `UpdateBasketDiscountsMessage.php:22`) — when customer discount level changed (например после покупок).

**Quirks**:
- Корзина существует **до момента подтверждения заказа в OMS** — это значит, что между Integration `POST /order/create` и подтверждением OMS возможны гонки (если юзер успеет открыть корзину).

---

### BP-BSK-06: Избранное (favorites)

**Триггер**: пользователь добавляет товар в избранное.

**Шаги**:
1. `AddBasketItemsToFavorites.php` / `SetFavoriteItemsAction.php` / `DeleteFavoriteItemAction.php`.
2. `MergeFavoriteItemsAction.php` — merge на логине.
3. `favorite_items` table (миграция `2023_06_26_*`, unique по `2024_04_10_*`).

**Где**: `platform/ensi/apps/orders/baskets/app/Domain/Baskets/Actions/Favorites/`

**Quirks**: избранное технически живёт в **baskets**-сервисе (а не отдельно). Странное решение, но исторически — наверное, общая модель item-list.

---

## 5. Customer-facing BFF — `customers-api-web`

**Контекст**: BFF (backend-for-frontend) для сайта и мобайла. Чекаут уже описан в `do../research/2026-05-20-checkout-order-creation.md` — здесь только остальные группы.

**HTTP versions**:
- `ApiV1`, `ApiV2`, `ApiV3` — web (apiV2/V3 — модули `Auth`, `Baskets`, `Catalog`, `Cms`, `Customers`, `Orders`)
- `ApiMobileV1`, `ApiMobileV3`, `ApiMobileV4`, `ApiMobileV5` — мобильные (модули `Baskets`, `Catalog`, `Orders` в V5)
- `Web` — служебные routes
- Все routes — `App/Http/{ApiV*,ApiMobileV*}/routes.php` + сгенерированный `OpenApiGenerated/routes.php`

### BP-BFF-01: Каталог (поиск, карточки, рекомендации)

**Endpoints (примерно)**:
- `POST /api/v2/catalog/products/search` → `SearchProductCardsAction.php`
- `GET /api/v2/catalog/products/{id}` → `SearchOneProductCardAction.php`
- `POST /api/v2/catalog/products/mini-search` → `SearchProductMiniCardsAction.php`
- `POST /api/v2/catalog/categories/search` → `SearchCategoriesAction.php`
- `GET /api/v2/catalog/products/{id}/sizes` → `SearchProductSizesAction.php`
- `GET /api/v2/catalog/recommendations/{productId}` → `GetProductRecommendationsAction.php`
- `GET /api/v2/catalog/suggestions?q=...` → `GetSuggestionsAction.php`
- `GET /api/v2/catalog/external` → `SearchExternalAction.php`
- `POST /api/v2/catalog/available-products` → `GetAvailableProductsAction.php` (V1) / `GetAvailableProductsV2Action.php` (V2)
- `GET /api/v2/catalog/redirect` → `GetRedirectUrlFromAnyQueryAction.php`
- `GET /api/v2/catalog/filters` → `GetAvailableFiltersAction.php`

**Backed by**:
- `catalog-cache` (ES) — основной источник.
- `pim` — fallback / детальная карточка.
- `offers` / `offers-go` — для цен (через clampToStock в баскете).

**Шаги (search)**:
1. `BuildSpecificationAction.php` → ES query spec.
2. `EnrichSpecificationWithOfferStoresAction.php` → enrichment по складам/регионам.
3. `EnrichFacetsWithOfferStoresFacetAction.php` → enrichment фасетов.
4. Запрос в ES через клиент catalog-cache.

**Quirks**:
- **Vendor-code lookup**: `SearchSkuProductsByVendorCodeAction.php` — отдельный метод.
- **Suggestions через ES** (autocomplete).
- A/B testing через `GetIdsAbGroupAction.php` в Auth domain — `Domain/Auth/Actions/GetIdsAbGroupAction.php` (для catalog/recommendations).

---

### BP-BFF-02: Корзина

**Endpoints**:
- `GET /api/v2/baskets/current` → `GetCurrentBasketAction.php`
- `POST /api/v2/baskets/items` → `AddBasketItemAction.php`, `SetBasketItemsAction.php`
- `POST /api/v2/baskets/items/select` → `SelectBasketItemsAction.php`
- `DELETE /api/v2/baskets/items` → `DeleteAllBasketItemsAction.php`
- `POST /api/v2/baskets/promo-code` → `SetBasketPromoCodeAction.php`
- `POST /api/v2/baskets/region` → `SetBasketRegionAction.php`
- `POST /api/v2/baskets/update` → `UpdateBasketAction.php`
- `GET /api/v2/baskets/status` → `GetCurrentStatusBasketAction.php`
- `GET /api/v2/baskets/bonus-balance` → `GetBonusBalanceAction.php`
- `POST /api/v2/baskets/share` → `ShareBasketAction.php`
- `GET /api/v2/baskets/shared/{token}` → `GetSharedBasketAction.php`
- `POST /api/v2/baskets/unlock` → `UnlockCustomerBasketAction.php`
- `POST /api/v2/baskets/equipment` → `SetBasketEquipmentAction.php` (split-shipment)
- `POST /api/v2/baskets/discount-rate` → `CalculateDiscountRateAction.php`

**Прокси** к `baskets` service + обогащение через `catalog-cache`/`offers`/`customers`/`bu`.

**Share-basket**: `ShareBasketAction` — отдельный сценарий "поделиться корзиной" (генерирует токен). Go event-dispatcher слушает SHARE_CART / BASKET_SHARED события (`go/event-dispatcher/internal/orderattrs/kafka_events.go:10-16`).

**Quirks**:
- `CheckOrBlockedBasketForAvatarAction.php` — отдельный action для avatar-flow (см. BP-BSK-01).

---

### BP-BFF-03: Профиль и его данные

**Endpoints**:
- `GET /api/v2/profile` → `GetCustomerProfileAction.php`
- `POST /api/v2/profile` → patch profile (через `customers` service)
- `GET /api/v2/profile/addresses` → `GetAddressAction.php`
- `POST /api/v2/profile/addresses` → `SetDeliveryAddressV2Action.php` (V1 + V2)
- `POST /api/v2/profile/reset-address` → `ResetCustomerAddressAction.php`
- `GET /api/v2/profile/recipients` → `GetCurrentRecipientsAction.php`
- `POST /api/v2/profile/recipients` → `CreateRecipientAction.php`, `DeleteRecipientAction.php`
- `POST /api/v2/profile/feedback` → `SendFeedbackAction.php`
- `POST /api/v2/profile/delete-account` → `DeleteCustomerAccountAction.php` (BP-CUS-05)
- `GET /api/v2/profile/status` → `GetCustomerStatusAction.php` (+ `GetCustomerStatusWithChildrenAction`, `GetCustomerStatusWithUnderageChildrenBirthdayAction`)
- `GET /api/v2/profile/discount-card` → `DiscountServiceGetMostRelevantCustomerAction.php`, `GetOrCreateCustomerCard.php`
- `GET /api/v2/profile/size` → `GetCustomerSizeValueAction.php`, `SetCustomerSizeValueAction.php`
- `GET /api/v2/profile/certificate/balance` → `CheckCertificateBalanceAction.php` (через DiscountService XML API)
- `GET /api/v2/profile/delivery-preference` → `GetDeliveryPreferenceAction.php`

**Quirks**:
- **Children-aware status** — отдельные actions для customer'ов с детьми (`GetCustomerStatusWithChildrenAction`, `GetCustomerStatusWithUnderageChildrenBirthdayAction`) — видимо для семейных скидок / детских коллекций.
- **Size value** — пользователь сохраняет свой размер для UX-pre-fill в каталоге.

---

### BP-BFF-04: Notifications / SEO / Navigation / Promotions / Favorites / Certificates

**Notifications** (`Domain/Notifications/Actions/`):
- `GetNotificationsAction.php`, `GetUnreadNotificationsCountAction.php` — пользовательские уведомления.
- Бэкенд: `Client/` — клиент к внешнему notification service.

**SEO** (`Domain/Seo/Actions/`):
- SEO-метаданные страниц для рендера.

**Navigation** (`Domain/Navigation/`):
- Меню/категории — Loaders + Actions.

**Promotions** (`Domain/Promotions/Actions/`):
- `ProductPromotionAction.php` — единственный action — отдаёт promo-баннеры на карточке.

**Favorites** (`Domain/Favorites/`):
- Actions + Data + Loaders — прокси к baskets favorite_items.

**Certificates** (`Domain/Certificates/`):
- Подарочные сертификаты — отдельная сущность с Actions/Data/Enums.

**Classifiers** — справочники (только Tests директория видна, возможно generated).

---

## 6. Связанные сервисы (кратко)

### `connectors/audit` — аудит-лог

- **Что делает**: централизованный аудит-лог всех изменений сущностей.
- **Источник данных**: вероятно Kafka topics — каждый сервис ENSI пишет в audit-топик через `ensi/audit-collector` package (см. `customers/app/Domain/Customers/Models/DeliveryPreference.php` — `use Ensi\AuditCollector\Transform`).
- **Storage**: Elasticsearch (`Domain/Audit/Elastic/AuditIndex.php`).
- **Чтение**: `ExtractAuditRecordsAction.php` — cursor-paginated.
- **Enrichment**: `EnrichAuditDataAction.php`, `ResolveAdminUsersAction.php`, `ResolveProductsAction.php`, `ResolveFilesAction.php`, `DecodeTermsAction.php`.
- **Reports**: `BuildReportJob.php` (`Domain/Audit/Jobs/`).
- **Где**: `platform/ensi/apps/connectors/audit/`

### `connectors/cdn-adapter` — медиафайлы

- **Что**: генерация URL для imgproxy + видео.
- **Endpoints**: `MakeImgProxyUrlAction.php`, `MakeVideoUrlAction.php`, `SearchMediaFileAction.php`, `DownloadImageAction.php`, `ParseMediaFileFilterAction.php`.
- **Где**: `platform/ensi/apps/connectors/cdn-adapter/`
- **Quirks**: hardcoded `$sizeMap` для image resize presets — добавление нового размера = деплой.

### `connectors/event-dispatcher` (PHP) — внешние интеграции по order-событиям

- **Что**: слушает события order-lifecycle (от OMS) и публикует во внешние системы (Mindbox, Google Analytics, DataGo).
- **События** (`Domain/Order/Events/`):
  - `OrderCreatedEvent`, `OrderCancelledEvent`, `OrderCancelledClientEvent`, `OrderPartCancelledEvent`, `OrderFullCancelledEvent`, `OrderCompletedDeliveryEvent`, `OrderCompletedPupEvent`, `OrderDeliveringEvent`, `OrderFinishedEvent`, `OrderOnValidationEvent`, `OrderReadyForPickupEvent`, `PushOrderReadyForPickupEvent`.
- **Подписчики** (`EventServiceProvider.php`):
  - Mindbox listeners (×11)
  - GoogleAnalytics4 listeners (×2: created, cancelled)
  - DataGo listeners (×2: created, cancelled)
- **Клиенты**: `Clients/Customers/`, `Clients/DataGo/`, `Clients/GoogleAnalytics/`, `Clients/Mindbox/`, `Clients/Oms/`, `Clients/Pim/`.
- **Где**: `platform/ensi/apps/connectors/event-dispatcher/`

### `go/event-dispatcher` (Go) — параллельная реализация

- **Что**: Go-воркер, который слушает Kafka и маршрутизирует по `statusId` + `deliveryTypeId` + `cancellationReasonId` в события.
- **Routing rules** (`internal/triggers/*.go` — один файл на триггер):
  - `statusId=ON_VALIDATION` → `ORDER_CREATED`
  - `statusId=DELIVERING` → `ORDER_SENT_TO_DELIVERY`
  - `statusId=READY_FOR_PICKUP` + `deliveryTypeId in (reserveinstore, pickupinstore)` → `ORDER_READY_FOR_PICKUP_STORE_GJ`
  - `statusId=READY_FOR_PICKUP` + `deliveryTypeId=pickup` → `ORDER_READY_FOR_PICKUP_PVZ`
  - `statusId=COMPLETED` + `deliveryTypeId=delivery` → `order-completed-delivery`
  - `statusId=COMPLETED` + `deliveryTypeId=pickup` → `order-completed-pup`
  - `statusId=CANCELLED` + `cancellationReasonId` ∈ client-list → `order-cancelled-client`
  - `statusId=CANCELLED` + `cancellationReasonId=orderCorrection` → `order-cancelled-partial-gj`
  - `statusId=CANCELLED` + `cancellationReasonId in (expiredShelfLife, createNewOrder, fraud, notAvailable)` → `order-cancelled-full-gj`
  - `items[].deleted=true` → `order-items-deleted`
  - `eventId in (SHARE-CART, SHARE_CART, CART-SHARED, CART_SHARED, BASKET-SHARED, BASKET_SHARED)` → `share-cart`
- **Где**: `platform/ensi/apps/go/event-dispatcher/internal/{triggers,dispatcher,events,orderattrs}/`
- **Docs**: `docs/overview.md`, `setup.md`, `components.md`, `mindbox_discrepancies.md`.

**Quirks (event-dispatcher)**:
- **PHP и Go версии одновременно** — нужно понимать, кто из них владелец какого триггера. Go-версия имеет более тонкий routing (по `cancellationReasonId`), PHP — по типам событий.
- `mindbox_discrepancies.md` в Go-docs — сигнал, что Mindbox-mapping расходится между PHP и Go версиями.
- Legacy event names с подчёркиванием (`SHARE_CART`) vs новым с дефисом (`SHARE-CART`) — оба поддерживаются (`kafka_events.go:10-16`).

### `units/bu` — бизнес-юниты, склады, юр.лица

- **Что**: справочник продавцов, складов, магазинов (физических точек).
- **Сущности**: `Sellers/`, `Stores/`, `Migrations/` (для DaData справочников?), `Dadata/` (геоданные — кеш FIAS).
- **SellerUsers/** — связь юзеров с продавцами (multi-tenancy).
- **Исходящие topics**:
  - `*.fct.region-base-store.0` (`SendRegionBaseStoreEventAction.php`)
  - `*.fct.region-store-warehouse.0` (`SendRegionStoreWarehouseEventAction.php`)
  - `*.fct.business-units.0` (`connectors/ensi-connector/.../WarehouseMessage.php:26`)
  - `*.cdc.warehouses.0` (`bu/.../WarehouseChangedMessage.php:32`)
  - `*.fct.*.0` для CRUD моделей через `ModelEventMessage`
- **Слушатели**: `Stores/Listeners/` — реакция на изменения.
- **Где**: `platform/ensi/apps/units/bu/`
- **Quirks**: BU критичен для catalog-cache (регионы) и offers-go (RegionStoresWarehouses events). Изменение здесь каскадно перетряхивает офферы и индексы.

### `cms/cms` — контент

- **Сущности**: `Bundles/`, `Contents/`, `Plates/` (нашлёпки на товаре?), `Messages/`, `Nameplates/`, `SitePages/`, `Stories/`, `SpecialOffers/`, `BaseStoreLinks/`, `Promotions/`, `FiltersAndFacets/`, `ProductsTypes/`, `Navigation/`, `SeoSettings/`.
- **Исходящие topics**:
  - `messages` (`SendMessageEventAction.php`)
  - `nameplates` (`SendNameplateEventAction.php`)
  - `message-product-links`, `nameplate-product-links` (`SendProductLinkEventAction.php` — диспетчер по `ProductLinkType`)
  - `product-types`, `product-type-category-links`
  - **Закомментировано** в `SendBaseStoreLinkEventAction.php`: `bundle`, `footer-call-centre`, `footer-contact` — старые/спланированные топики, не активные.
- **Где**: `platform/ensi/apps/cms/cms/`

---

## Сводная карта Kafka-топиков (исходящие из ENSI)

| Топик | Источник | Назначение | Класс |
|---|---|---|---|
| `*.fct.cc-products.0` | pim | Товар | fact |
| `*.fct.sku-product-vendor-codes.0` | pim | SKU | fact |
| `*.fct.base-products.0` | pim | Base product | fact |
| `*.fct.categories.0` | pim | Категории | fact |
| `*.fct.category-links.0` | pim | Привязки категорий | fact |
| `*.fct.category-product-links.0` | pim | Категория↔товар | fact |
| `*.fct.colors.0` / `color-links.0` | pim | Цвета | fact |
| `*.fct.sizes.0` / `size-links.0` | pim | Размеры | fact |
| `*.fct.product-images.0` | pim | Изображения | fact |
| `*.fct.product-property-values.0` | pim | Атрибуты | fact |
| `*.fct.properties.0` | pim | Свойства | fact |
| `*.fct.property-directory-values.0` | pim | Значения | fact |
| `*.fct.recommendation-marks.0` | pim | Метки рекомендаций | fact |
| `*.cdc.products.0` | pim | Product CDC | cdc |
| `*.fct.offers.1` | offers / offers-go | Офферы (price+stock+availability per region) | fact v1 |
| `*.fct.offer-stores.1` | offers / offers-go | Склады для оффера | fact v1 |
| `*.fct.sku-totals.0` | offers / offers-go | Суммарный сток | fact |
| `*.fct.customers.0` | customers | Профили | fact |
| `*.fct.addresses.0` | customers | Адреса | fact |
| `*.fct.ensi-customers.0` | customers | Sync к DiscountService | fact |
| `*.fct.update-basket-discounts.0` | customers | Триггер пересчёта баскета | fact |
| `*.sys.email-communications.0` | customers | Email-нотификации (welcome, discount-card) | system |
| `*.fct.region-base-store.0` | bu | Регион↔магазин | fact |
| `*.fct.region-store-warehouse.0` | bu | Регион↔склад↔магазин | fact |
| `*.fct.business-units.0` | ensi-connector | BU | fact |
| `*.cdc.warehouses.0` | bu | Warehouse CDC | cdc |
| `*.fct.messages.0` | cms | Сообщения | fact |
| `*.fct.nameplates.0` | cms | Шильдики | fact |
| `*.fct.message-product-links.0` / `nameplate-product-links.0` | cms | Привязки | fact |
| `*.fct.product-types.0` / `product-type-category-links.0` | cms | Типы | fact |
| `*.fct.deactivated-user.0` | admin-auth | Деактивация админа | fact |
| `*.fct.updated-user.0` | admin-auth | Обновление админа | fact |
| `*.fct.generated-password-token.0` | admin-auth | Сброс пароля | fact |

**Sink-точки в ENSI**: `catalog/catalog-cache`, `orders/baskets`, `customers/customers` (получает обратно `CustomerFromDiscount`), `customer-auth` (слушает email/sms-messages), `offers` (слушает sku-product, region, stocks, region-stores-warehouses), `offers-go` (то же), `connectors/event-dispatcher` (слушает OMS-события — внешний контур).

---

## Системные quirks и архитектурные риски

1. **Дублирующиеся реализации PHP/Go**:
   - `offers` (PHP) vs `offers-go` (Go) — оба активны, одинаковые output-топики. Производитель-консьюмер race.
   - `connectors/event-dispatcher` (PHP, Laravel events) vs `go/event-dispatcher` (Go, Kafka-driven). PHP реагирует на orchestrated events; Go — на raw Kafka.
2. **Sync produce в HTTP-флоу**: PIM observer'ы публикуют Kafka синхронно. Сбой Kafka может разрушить транзакцию или (хуже) оставить рассинхрон БД↔Kafka.
3. **catalog-cache как denormalization layer** — лаг публикации, кастомные миграции, 28+ Kafka listener'ов. Высокая поверхность для синхронной поломки.
4. **Внешний DiscountService (XML/SOAP-like)** — паттерны `wordKey`, `SimpleXMLElement`, hardcoded `clientId='5105'`. Уязвим к внешнему таймауту.
5. **24-часовой TTL анонимных корзин** в `CleanOldBasketsAction:18` — хардкод. Любой A/B флоу с долгим returning user'ом теряет корзину.
6. **`User.id = $incrementing = false`** в customer-auth — id заводится извне для синхронизации с customers-service. Если рассинхронизируется — auth не находит профиль.
7. **OPSOMN001-466**: customerDeliveryPreferencesTemp в mobile — workaround вокруг анонимного flow delivery_preferences. Хорошо бы убрать когда `device_id`-based path стабилизируется на BFF.
8. **Hardcoded sizeMap в cdn-adapter** — добавление нового image preset требует деплоя.
9. **Опечатки в миграциях** (`craete_table_product_promotion`) — типичный сигнал, что миграции пишутся в спешке без code review.
10. **Mindbox через два пути**: PHP event-dispatcher listeners + Go event-dispatcher trigger rules. Согласно `mindbox_discrepancies.md` — есть расхождения.

---

## Открытые вопросы для следующей итерации

1. **Owner offers vs offers-go**: кто реально primary producer для `*.fct.offers.1`? Feature flag или consumer-group?
2. **Outbox pattern в PIM**: запланирован ли переход с sync-produce на outbox-via-DB?
3. **Audit pipeline**: какие топики consumed audit-сервисом? Все CDC? Или только специальные `audit.*`?
4. **catalog-cache reindex**: что происходит если массовый bulk-update в PIM (5000 товаров за раз) — успевает ли ES обработать всё через 28 listener'ов?
5. **Promotion service**: внешний URL и контракт `PromotionServiceClient`? Что если он недоступен — graceful degradation?
6. **delivery_preferences vs customerDeliveryPreferencesTemp**: когда планируется убрать temp-storage и положиться на `device_id`-aware BFF?

---

## Cross-system delegation

| Вопрос | Делегировать к |
|---|---|
| Чекаут-flow целиком | `do../research/2026-05-20-checkout-order-creation.md` (готов) |
| Что Integration делает с корзиной/чекаутом? | `integration-researcher` |
| Что OMS делает с order'ом после `POST /order/create`? | `oms-researcher` |
| Как сайт показывает результаты ENSI? | `site-researcher` |
| Mobile-specific quirks (yookassa, RN) | `mobile-researcher` |
| Архитектура offers-go vs offers PHP | `architect` (после ответа на open-question #1) |

