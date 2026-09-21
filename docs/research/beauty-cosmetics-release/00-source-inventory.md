# Beauty / COSMETICS — источники истины

Снимок локальных checkout: 2026-07-17. Перед конкретным MR или production-релизом ветки и SHA сверяются повторно.

## Код и контракты

| Система | Репозиторий / источник | Проверенный якорь | Что доказывает |
|---|---|---|---|
| PIM | `platform/ensi/apps/catalog/pim` | `app/Domain/Classifiers/Enums/CategoryGroup.php` | Доменный enum группы категории |
| PIM | тот же | `public/api-docs/v1/categories/enums/category_group_enum.yaml` | Каноническая release-спека для server/client generation |
| PIM | тот же | `config/openapi-server-generator.php` | Generator читает локальный `public/api-docs/v1/index.yaml` |
| PIM | тот же | `app/Domain/Products/Actions/Products/ImportProductAction.php:89` | Ключ категории: `target_group + department + category`; запись через `syncWithoutDetaching` |
| PIM | тот же | `public/api-docs/v1/categories/schemas/categories.yaml` | Для create API обязательны `name_ru`, `type`; для процесса дополнительно нужны `group`, `external_id` и связь с parent |
| PIM client | `platform/ensi/packages/pim-client-php` | commit `0784094` | Нормализация пяти ключей generated-looking DTO, которую нельзя потерять без отдельного решения |
| PIM client generation | PIM `openapitools.json` + одноразовый output | OpenAPI Generator `4.3.1` | Воспроизводимый raw generator diff затрагивает 421 файл и непригоден для полного переноса в CategoryGroup-задаче |
| Admin GUI FE | `platform/ensi/apps/admin-gui/admin-gui-frontend` | `src/views/catalog/categories/[id]/FormChildren.tsx:19` | Список групп захардкожен и сейчас содержит только `1–4` |
| CMS | `platform/ensi/apps/cms/cms` | `public/api-docs/v1/productsTypes/schemas/products_types.yaml` | Product Type и обязательные поля `name_ru`, `is_active`, `size_group` |
| CMS | тот же | `products_type_category_links.yaml` | Связь Product Type ↔ category по `product_type_id`, `category_id` |
| Catalog Cache | `platform/ensi/apps/catalog/catalog-cache` | `app/Domain/Offers/Actions/FillCategoriesAction.php:27` | Источник категорий — `product.categoryLinks` |
| Catalog Cache | тот же | `FillCategoriesAction.php:104` | Product Types берутся через `category.productTypes` |
| Catalog Cache | тот же | `composer.json`, `composer.lock` | Потребитель требует `ensi/pim-client: dev-master`; lock фиксирует commit клиента |

## Данные и внешние входы

| Источник | Назначение | Статус |
|---|---|---|
| PLM/import payload | `target_group`, `department`, `category` для построения точного leaf `external_id` | Пять комбинаций подтверждены на stage |
| Утверждённый manifest 74 товаров | Безопасный replay, удаление Buffer-link и точечный reindex | Обязательный production-вход; в репозитории пока отсутствует |
| PIM DB | Категории и `category_product_links` | Только read-only проверки до согласованной мастер-операции |
| CMS DB | Product Types и `product_type_category_links` | Мастер-данные создаёт/переиспользует контент-команда через Admin |
| Catalog Cache DB + Elasticsearch | Синхронизация сущностей и конечный индекс | Проверять после consumers/sync и reindex |
| `POST /mobile/v4/catalog/filters` | Контракт MD-006: `types[].groups` | Финальный API acceptance gate |

## Точные пять ключей PIM-import

```text
Girls 13+ Color Cosmetics Lips
Girls 13+ Color Cosmetics Eyes
Girls 13+ Color Cosmetics Face
Girls 2-8 Color Cosmetics Lips
Girls 13+ Accessories Beauty Color cosmetic
```

Эти строки должны быть `external_id` конечных категорий без изменения регистра, пробелов и порядка частей.

## Результат проверки raw generation клиента

- Версия generator в PIM и metadata клиента совпадает: `4.3.1`.
- Для совпадения структуры DTO нужны как минимум `invokerPackage=Ensi\\PimClient`, `modelPackage=Dto`,
  `apiPackage=Api`.
- Даже с этими параметрами raw output отличается от текущего клиента в 421 существующем файле.
- Нужный функциональный delta сосредоточен в `lib/Dto/CategoryGroupEnum.php`: описание, константы
  `COSMETICS/HOME`, элементы allowable values.
- Generated `test/Model/CategoryGroupEnumTest.php` содержит пустой test body; перед изменением enum требуется
  добавить реальные assertions.
- Generated output пытается убрать `: array` у `getAllowableEnumValues()`; это посторонний regression и не
  переносится.
- `ImportProductRequest` из raw output удаляет ключи, защищённые commit `0784094`; файл не переносится.
