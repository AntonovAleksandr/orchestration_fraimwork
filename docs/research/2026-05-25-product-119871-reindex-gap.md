# Product 119871 — PIM male=GIRL→FEMALE update did not propagate to ES facet

## Question
Атрибут "Пол" (`male`) товара изменён в PIM в 11:29 (GIRL → FEMALE/WOMAN).
PDP-крошки на сайте уже свежие ("Женщины > Футболки и лонгсливы > Футболки"),
а листинг /catalog/women-new?q=:male:GIRL — всё ещё содержит этот товар.
Где разрыв в pipeline пропагации?

## Summary (TL;DR)
PDP-крошки и facet-фильтр идут **разными путями**:
- Крошки = `customers-api-web` → CMS `NavigationTopbarApi` → `TopbarNode` (по `category_id`, который PIM отдаёт через CategoryChain). Не использует поле `male` вообще.
- Facet `male` = `customers-api-web` → `catalog-cache` ES-индекс `products` (поле `male` keyword).

Pipeline для ES: PIM Product.updated → `ProductAfterCommitObserver` → Kafka topic `cc-products`
→ `catalog-cache` `ListenProductAction` → `SyncModelAction` → mirror DB → `ProductObserver::saved`
→ `ProductIndexingJob` (`ShouldBeUnique` по `base_product_vendor_code`) → `IndexBaseProductAction` → ES bulk.

Stale facet возможен при следующих сценариях:
1. `ProductIndexingJob` упал/застрял в очереди (job unique до завершения; новый dispatch может коалесцироваться).
2. Kafka событие пришло без `male` в `dirty` (например, изменение пришло на BaseProduct, а Product не сохранялся) — SyncModelAction пропускает update.
3. Mirror DB обновился, но ES-bulk вернул ошибку — лог-only, без retry.

Safety net: `elastic:reindex` daily @ 03:00 (Console/Kernel.php:25) перебирает все товары. До 03:00 расхождение сохраняется.

## Evidence trail

### PIM (producer)
1. `platform/ensi/apps/catalog/pim/app/Domain/Products/Models/Product.php:50,110,120,142` — `male` это **поле в таблице products** (enum `Sex`), не EAV, не из категории.
2. `platform/ensi/apps/catalog/pim/app/Domain/Products/Models/BaseProduct.php:22,52,59` — `male` дублируется на `BaseProduct` (тоже field, enum).
3. `platform/ensi/apps/catalog/pim/app/Domain/Products/Observers/ProductAfterCommitObserver.php:34-46` — `updated()` шлёт `SendProductEventAction::execute(... UPDATE)` для **любого** изменения Product (кроме типа CERTIFICATE).
4. `platform/ensi/apps/catalog/pim/app/Domain/Kafka/Actions/Send/SendProductEventAction.php:15-25` — топик внутреннего имени `cc-products` через `TopicNameBuilder::fact('all', 'cc-products')`.
5. `platform/ensi/apps/catalog/pim/app/Domain/Kafka/Messages/Send/ModelEvent/ModelEventMessage.php:21` — `dirty = array_keys($model->getChanges())` — пишется в payload, **только для UPDATE**.
6. `.../Send/ModelEvent/ProductPayload.php:35` — `male` сериализуется в payload как enum-instance.
7. Аналогичный путь для `BaseProduct`: `BaseProductAfterCommitObserver.php`, `SendBaseProductEventAction.php`.

### catalog-cache (consumer + indexer)
8. `platform/ensi/apps/catalog/catalog-cache/app/Domain/Kafka/Actions/Listen/ListenProductAction.php:24-44` — `interestingFields` включает `male`. Если PIM прислал UPDATE без `male` в `dirty` — изменение **игнорируется** (см. след. файл).
9. `.../Kafka/Actions/Listen/SyncModelAction.php:24` — критический guard: `$needUpdate = ... && array_intersect($interestingUpdatedFields, $eventMessage->dirty ?? [])`. Это и есть фильтр "fast path".
10. `.../Kafka/Actions/Listen/ListenBaseProductAction.php:28` — для BaseProduct тоже слушается `male` (но в ES-карточке используется Product, не BaseProduct, см. ниже).
11. `.../Offers/Observers/ProductObserver.php:11` — после сохранения mirror-модели `ProductIndexingJob::dispatch($base_product_vendor_code)`.
12. `.../Offers/Jobs/ProductIndexingJob.php:13` — `implements ShouldBeUnique`, `uniqueId() = $baseProductVendorCode`. Job коалесцируется по vendor-коду базового товара (до момента старта обработки).
13. `.../Offers/Actions/IndexBaseProductAction.php:9` + `.../Offers/Actions/BaseIndexAction.php:42` — bulk index. Ошибки только логируются (`logError`), retry нет.
14. `.../Offers/Actions/ComposeBaseProductCardsAction.php:25-46` — индексация идёт по **`base_product_vendor_code`** (все Product одной базы переиндексируются вместе).
15. `.../Offers/Actions/FillCommonProductDataAction.php:27` — `$card->male = $product->male?->name;` (берётся именно из mirror-`Product`, не из BaseProduct).
16. `.../Offers/Elastic/ProductCardSpecification.php:38,96` — `male` сериализуется в ES-документ; `terms('males', 'male', 'male')` — это агрегация для facet.
17. `.../Offers/Elastic/ProductIndex.php:11,93` — ES-индекс называется `<contour>_<app>_products_<hash>`, поле `male` типа `keyword`.

### customers-api-web (BFF к фронту)
18. `platform/ensi/apps/customers-api-web/app/Domain/Catalog/Data/Search/Specification.php:32` — `'male' => 'male'` в `$filtersMap` (фильтр URL `?q=:male:GIRL` мапится напрямую на поле ES).
19. `.../Catalog/Loaders/FacetsAsyncLoader2.php:7-10` — ходит в `Ensi\CatalogCacheClient\Api\OffersApi::getProductFacets` → `catalog-cache` HTTP.
20. `.../catalog-cache/app/Http/ApiV1/Modules/Offers/Queries/ProductFacetsQuery.php:6,15` — `ProductIndex::aggregate()`. Тот же индекс `products`.
21. `.../catalog-cache/app/Http/ApiV1/Modules/Offers/Queries/ProductCardsQuery.php:6,15` — листинг карточек — тоже `ProductIndex::query()`.

### Pipeline крошек (для контраста — он "чистый")
22. `.../customers-api-web/app/Domain/Navigation/Actions/GetNavigationCrumbsAction.php:64-73` — для PDP крошки получаются по `vendorCodeCc` через `NavigationTopbarApi::searchOneForBreadcrumb` в **CMS**.
23. `platform/ensi/apps/cms/cms/app/Domain/Navigation/Actions/TopbarNodes/SearchTopbarNodeForBreadcrumbsAction.php:26-51` — CMS делает live-запрос в PIM `CategoriesApi::searchCategoryChains(vendor_code_cc)` и матчит с локальной таблицей `topbar_nodes` по `category_id`. **Никакой денормализации `male`**, потому крошки всегда свежие (с задержкой PIM сети, не ES).

### Safety nets / ручные команды
24. `.../catalog-cache/app/Console/Kernel.php:25` — `$schedule->command('elastic:reindex')->dailyAt('03:00')`.
25. `.../catalog-cache/app/Console/Commands/Elastic/IndexProductCommand.php:14-46` — `elastic:index-product {id|vendor_code} [--immediate] [--trace]` — точечный reindex.
26. `.../catalog-cache/app/Console/Commands/Elastic/ElasticReindexCommand.php:10-15` — `elastic:reindex` (полный).
27. `.../catalog-cache/app/Domain/Offers/Actions/IndexBy/IndexByProductIdAction.php:12-20` — есть, но **не подключён к HTTP-роутам**. Только из CLI/код.

### Релевантные commit-history артефакты
- catalog-cache `33c1b6e #104180 update only dirty fields on product topic` (Mar 2023) — ввёл сам фильтр по `dirty`. Чувствительно к качеству поля `dirty` от продьюсера.
- catalog-cache `a19c926 #104180 change kafka listen logic for create and update event` — связано.
- pim `cbfc72ca #99617 (OMNIES-4239) Изменение имени внутреннего топика товаров` — топик `cc-products`.

## Workarounds / legacy in play
- **Dirty-filter гейт** (SyncModelAction.php:24): если по любой причине `dirty` пуст или не пересекается с `interestingFields` — обновление молча проглатывается. Логируется только "Обновляемая модель не существует" (line 48), а тут сценарий другой — модель есть, но `needUpdate=false`. Тихий no-op.
- **Уникальность Job по vendor_code** (ProductIndexingJob.php:24): если предыдущий job висит/завис в очереди — следующий вызов с тем же base_product_vendor_code может не запуститься (`ShouldBeUnique` без таймаута уникальности → дефолтный).
- **BaseProduct.male ≠ Product.male**: `male` хранится и на BaseProduct, и на Product, но в ES попадает значение Product (FillCommonProductDataAction:27). Если в L2 правили только BaseProduct — Product мог не получить событие.
- **Bulk без retry** (BaseIndexAction.php:83-87): ES-ошибка только логируется.
- **`ListenChangedOffersAction.php:10` помечен `@deprecated`** — может быть переходный путь индексации.
- **Daily 03:00 full reindex** — нормальный safety net, но рассчитывать на него для in-day исправлений нельзя.

## What I could NOT determine from ENSI code alone
- Реально ли пришло Kafka-событие в `catalog-cache` (нужен `mcp__gj-buddy__logs_search_message` по `cc-products` + product_id=119871).
- Состояние очереди `ProductIndexingJob` (Redis): висит ли уникальный lock.
- Поле `dirty` в этом конкретном Kafka-сообщении — содержит ли `male`. Если изменение прошло через какой-то bulk-update в PIM, который не дергает Eloquent save() — observer мог не отстреливать, или dirty-массив мог быть нестандартным.
- В каком именно режиме L2 поменял `male` (через PIM-UI, через какой-то импорт/фид). Если через `Imports` или batch-action — observer flow может отличаться.

## Suggested next steps
- Принудительный точечный reindex (read-safe способ проверить, что ES примет правильные данные если их пересчитать): `elc -w gj -c catalog-cache exec php artisan elastic:index-product 119871 --immediate --trace` — это вызовет `IndexBaseProductAction` на product_id или vendor_code (см. IndexProductCommand.php:14-46). Если после команды фильтр `male:FEMALE` начинает отдавать товар — корень в pipeline до bulk-индексации (Kafka/Job), не в ES маппинге.
- Для root-cause: `logs-detective` по сообщениям `cc-products` около 11:29 (product_id=119871), посмотреть `dirty` payload, и логи `catalog-cache` "Product 119871 processed N" (BaseIndexAction.php:79). Если нет ни логов consumer, ни логов indexer — событие не дошло. Если есть consumer-лог, но нет indexer-лога — застрял dirty-фильтр или ShouldBeUnique-Job.
- Для архитектуры: `architect` — почему `male` это денормализованное поле в двух мирах (PIM Product + PIM BaseProduct) и при этом нет explicit re-emit при изменении BaseProduct.male в Product-mirror (BaseProductAfterCommitObserver.php в PIM шлёт sku-события только для `vendor_code` dirty).
