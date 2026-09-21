# Beauty / COSMETICS — BFF implementation plan

> Реализация выполняется inline в `platform/ensi/apps/customers-api-web`, ветка `OPSOMN002-15` от
> `origin/release-26.09@c8a41d70`, по TDD. Merge и push не входят в этот план.

**Цель:** Web V2 и Mobile V4 должны отдавать `types[].groups`, поддерживать `COSMETICS` в фасете размеров, а
Mobile V4 — не скрывать Product Types для Beauty-категории.

**Архитектура:** Catalog Cache остаётся источником `ProductTypeAggregate.groups`; BFF только сохраняет этот массив
в публичном ответе. Признак Beauty берётся из `Specification.category.group`, а не из `target_category_id`.
Старые API V1/Mobile V3 переводятся на новый входной DTO без расширения их публичного контракта.

## Ограничения

- `ensi/catalog-cache-client` фиксируется на `2bdd035`.
- `ensi/pim-client` фиксируется на `06d6a59`.
- Другие Composer-пакеты не обновляются.
- Публичный контракт `groups` добавляется только в Web V2 и Mobile V4.
- Генерация читает локальные `public/api-docs/v2/index.yaml` и `public/api-docs/mobile-v4/index.yaml`.

## Task 1: зависимости

**Файлы:** `composer.lock`.

- [ ] Выполнить exact Composer dry-run для двух пакетов и убедиться, что иных package operations нет.
- [ ] Обновить только `ensi/catalog-cache-client` и `ensi/pim-client`.
- [ ] Проверить `source.reference` и `dist.reference` обоих пакетов.
- [ ] Удалить metadata-noise, если версия host Composer переписала несвязанные поля lock-файла.

## Task 2: RED — Web V2

**Файлы:**

- `app/Http/ApiV2/Modules/Catalog/Tests/FacetsComponentTest.php`
- `app/Domain/Catalog/Tests/Factories/ProductTypeAggregateFactory.php`
- `app/Domain/Catalog/Tests/Factories/ProductFacetsFactory.php`

- [ ] Создать `ProductTypeAggregateFactory`, возвращающий DTO с `id`, `name`, `sort`, `groups`, `doc_count`.
- [ ] Добавить тест, в котором Catalog Cache возвращает `groups: [5]`, а
  `POST /api/v2/catalog/filters` отвечает `data.types.0.groups == [5]`.
- [ ] Добавить проверку, что размер с `group=5` отдаётся как `type=COSMETICS`.
- [ ] Запустить тест и получить ожидаемый RED: `groups` отсутствует, тип размера пустой.

## Task 3: RED — Mobile V4

**Файлы:** `app/Http/ApiMobileV4/Modules/Catalog/Tests/FacetsComponentTest.php`.

- [ ] Смоделировать текущую категорию с `group=5`, одним полом, не collection.
- [ ] Проверить, что `types` присутствует и содержит `groups: [5]`.
- [ ] Проверить `size.0.type == COSMETICS`.
- [ ] Запустить тест и получить ожидаемый RED: `types` скрыт и тип размера пустой.

## Task 4: GREEN — BFF mapping и compatibility

**Файлы:**

- `app/Domain/Catalog/Data/Search/Facets.php`
- `app/Http/ApiV2/Modules/Catalog/Resources/FacetsResource.php`
- `app/Http/ApiMobileV4/Modules/Catalog/Resources/FacetsResource.php`
- `app/Http/ApiV1/Modules/Catalog/Resources/FacetsResource.php`
- `app/Http/ApiMobileV3/Modules/Catalog/Resources/FacetsResource.php`
- `app/Http/ApiV2/Modules/Catalog/Resources/Aggregates/SizeAggregatesResource.php`
- `app/Http/ApiMobileV4/Modules/Catalog/Resources/Aggregates/SizeAggregatesResource.php`

- [ ] Добавить `Facets::isCosmetics(): bool`, сравнивающий текущую `category.group` с
  `CategoryGroupEnum::COSMETICS`.
- [ ] В Web V2/Mobile V4 принимать `ProductTypeAggregate` и возвращать `id`, `name`, `groups`.
- [ ] В Mobile V4 показывать `types`, если категория mix, collection или cosmetics.
- [ ] В обоих Size resource добавить `CategoryGroupEnum::COSMETICS => 'COSMETICS'`.
- [ ] В V1/Mobile V3 заменить только входной type hint mapper на `ProductTypeAggregate`, сохранив ответ `id/name`.
- [ ] Запустить RED-тесты и получить GREEN.

## Task 5: OpenAPI и генерация

**Файлы:**

- `public/api-docs/v2/catalog/schemas/references.yaml`
- `public/api-docs/v2/catalog/schemas/facets.yaml`
- `public/api-docs/mobile-v4/catalog/schemas/references.yaml`
- `public/api-docs/mobile-v4/catalog/schemas/facets.yaml`
- generated artifacts — только если генератор создаст ожидаемый diff.

- [ ] Добавить публичную схему Product Type с обязательными `id`, `name`, `groups: integer[]`.
- [ ] Перевести `ProductFacets.types.items` на эту схему.
- [ ] Обновить описание size type, включив `COSMETICS`.
- [ ] Выполнить `php artisan openapi:generate-server` из checkout BFF и проверить generated diff.
- [ ] Выполнить Spectral lint для V2 и Mobile V4.

## Task 6: verification и release log

- [ ] Запустить targeted component tests Web V2/Mobile V4.
- [ ] Запустить связанные V1/Mobile V3 facet tests для проверки DTO compatibility.
- [ ] Запустить PHP CS Fixer dry-run, PHPStan на изменённых production-файлах и `git diff --check`.
- [ ] Запустить полный доступный Pest suite; если инфраструктура блокирует его, записать точную причину и
  отдельно подтвердить targeted scope.
- [ ] Записать SHA клиентов, список файлов, результаты RED/GREEN и ограничения окружения в `ACTION-LEDGER.md`.
- [ ] Оставить изменения незакоммиченными до отдельной команды Александра.
