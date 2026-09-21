# Beauty / COSMETICS Production Release Implementation Plan

> **Для agentic workers:** выполнять по одному репозиторию/операционному gate; после каждого действия обновлять
> `ACTION-LEDGER.md`. Кодовые задачи реализовывать с TDD, production data operations — только по утверждённому
> manifest и с read-only pre/post-checks.

**Цель:** провести MD-006 от появления `CategoryGroup.COSMETICS=5` в PIM до корректного массива уникальных
`types[].groups` в `POST /mobile/v4/catalog/filters` для 74 Beauty-товаров.

**Архитектура:** PIM владеет категориями и `category_product_links`; CMS владеет Product Types и
`product_type_category_links`; Catalog Cache объединяет эти данные и индексирует их в Elasticsearch. Кодовые
релизы выполняются до мастер-данных и replay, затем запускаются синхронизация и ограниченный reindex.

**Стек:** Laravel/PHP 8.1, OpenAPI generated PHP client, Admin GUI React/TypeScript, PostgreSQL, Kafka consumers,
Elasticsearch, BFF/mobile API.

## Глобальные ограничения

- Release-база PIM: `release-26.09`; feature-ветка: `OPSOMN002-15`.
- Значения enum фиксированы: `COSMETICS=5`, `HOME=6`; миграция PIM DB не нужна.
- PIM server generation выполняется из release checkout и читает локальный `public/api-docs/v1/index.yaml`.
- `pim-client` генерируется сначала во временную директорию; полный слепой overwrite запрещён.
- Commit клиента `0784094` нельзя потерять без отдельного решения по `OPSOMN-14572`.
- Категории `group=COSMETICS` не создавать до деплоя PIM с поддержкой значения `5`.
- Replay не удаляет Buffer-link: `syncWithoutDetaching` только добавляет новую связь.
- `target_category_id` не считать источником `types[].groups`.
- Production reindex ограничить утверждённым manifest 74 товаров; широкий reindex требует отдельного согласования.
- CMS L1 «Косметика» — отдельная навигационная задача и не заменяет PIM category group.

---

## 1. Состояние систем и полный release-checklist

| # | Система / ветка | Тип действия | Что меняется или создаётся | Источник данных | Зависимость | Проверка и критерий готовности | Deploy / replay / consumer / reindex |
|---|---|---|---|---|---|---|---|
| 1 | PIM `OPSOMN002-15` от `release-26.09` | Разработка + генерация | Domain enum, OpenAPI enum, переводы, generated server enum, component test для `5/6` | Jira `OPSOMN002-15`, локальная release-спека | Нет | Tests `11 passed`; Spectral clean; generated diff только по enum; API enum возвращает `5/Косметика`, `6/Home` | Нужен deploy PIM; migration и reindex не нужны |
| 2 | `pim-client-php`; результат должен попасть в `master` | Безопасная генерация | Только ожидаемый enum-related generated diff из PIM release-спеки | PIM `OPSOMN002-15/public/api-docs/v1/index.yaml` | Шаг 1, согласованная судьба `OPSOMN-14572` | Temp diff проверен; `0784094` сохранён либо его удаление отдельно утверждено; client tests green | Публикация/merge в `master`; отдельного runtime deploy нет |
| 3 | Catalog Cache feature branch от актуальной release-базы | Dependency update | `composer.lock` переводится на точный commit `pim-client`, содержащий enum `5/6` | `pim-client master` | Шаг 2 | `composer show ensi/pim-client` и lock `source.reference` указывают на нужный commit | Входит в deploy Catalog Cache |
| 4 | Admin GUI frontend feature/release branch | Разработка | В форме Каталог → Категории добавлены варианты `Косметика=5`, `Home=6`; обновлены TS-константы/контракты, если они не generated | PIM CategoryGroup contract | Шаг 1 по контракту; для контент-команды нужен deploy | В UI можно создать/изменить тестовую категорию с group 5/6; запрос уходит с числом 5/6 | Нужен deploy Admin GUI FE; replay/reindex не нужны |
| 5 | PIM production master data | Контент-команда / админка | Создаются два department-узла `Color Cosmetics`, отдельный `Accessories Beauty` и пять leaf-категорий с group 5 | PLM-поля и утверждённая иерархия ниже | Deploy PIM; при работе через UI — deploy Admin GUI | Все пять exact `external_id` существуют один раз, активны, group=5, type=category и имеют правильного parent | Deploy нет; публикация/consumer категорий может потребоваться |
| 6 | CMS production master data | Контент-команда / админка | Создаются или переиспользуются Product Types `Lips`, `Eyes`, `Face`, `Color cosmetic`; добавляются links к пяти leaf-категориям | Справочник Product Types + созданные PIM category IDs | Шаг 5 | Нет дублей по смыслу/коду; типы активны; links существуют ровно для нужных category IDs | Deploy нет; CMS Kafka consumer/sync в Catalog Cache обязателен |
| 7 | Catalog Cache | Разработка | `types[].groups`: массив уникальных `categories.group` всех связанных с Product Type категорий; mapping, data DTO, facet aggregation, OpenAPI и тесты | `product.categoryLinks → category.productTypes`; PIM client enum | Шаги 2–3 | Integration tests покрывают несколько категорий, дубликаты group и group=5; OpenAPI lint и полный релевантный suite green | Нужен deploy Catalog Cache; затем consumers/sync и reindex |
| 7a | Catalog Cache, фильтр `Размер` | Разработка | Существующий `sizes[].group` начинает принимать `COSMETICS=5`; Beauty-размеры индексируются с этой макрогруппой | `category_product_links → category.group`; PIM client enum | Шаги 2–3 и Beauty category links | В ES/API Beauty size aggregate содержит `group=5`, fashion-группы `1–3` не изменились | Тот же deploy Catalog Cache и reindex затронутых Beauty-товаров |
| 7b | `catalog-cache-client-php` | Генерация / разработка | Добавляются typed DTO `ProductType`/`ProductTypeAggregate` с `groups: int[]`; `ProductCard.types` и `ProductFacets.types` переводятся на них | Зафиксированная локальная OpenAPI-спека Catalog Cache из шага 7 | Шаг 7 contract | Targeted contract/serialization test green; полный generated overwrite не выполнен; diff содержит только ожидаемые DTO/ссылки/docs | Отдельный deploy не нужен; commit должен попасть в `master`, затем потребители обновляют `composer.lock` |
| 8 | `customers-api-web`, Web V2 / Mobile V4 | Разработка | Обновляются `catalog-cache-client` и `pim-client`; mapper `types` принимает `ProductTypeAggregate` и отдаёт `groups`; size mapper поддерживает `COSMETICS`; Mobile V4 возвращает `types` для Cosmetics; обновляются factories, OpenAPI и component tests | `catalog-cache-client@2bdd035`; `pim-client@06d6a59`; фактический Catalog Cache response | Шаги 3 и 7b; оба client commit должны быть в `master` | `POST /api/v2/catalog/filters` и `POST /api/mobile/v4/catalog/filters` сохраняют уникальные `types[].groups=[5]`; Beauty sizes имеют `type=COSMETICS`; старые группы `1–3` не изменились | Нужен deploy `customers-api-web` из `release-26.09` |
| 9 | Site / Mobile / API types | Анализ и при необходимости generation | Typed models должны принимать `groups`; UI рендерит уникальные группы и локально фильтрует types | BFF mobile filter response | Шаг 8 | Typecheck/tests; Cosmetics появляется один раз, types фильтруются без дублей | Клиентский release только при изменении типов/логики; backend gate проверяется отдельно |
| 10 | PIM production products | Контент/интеграция | Повторно импортируются ровно 74 товара; появляется Beauty-link; затем удаляется старый Buffer-link | Утверждённый manifest 74 товаров + исходный PLM payload | Шаг 5; PIM deploy | У каждого manifest-product есть ожидаемый Beauty leaf-link и нет Buffer-link; `target_category_id` не является gate | Нужен replay; consumer событий проверить; повторять только failed subset |
| 11 | Catalog Cache DB/ES | DevOps / эксплуатация | Досинхронизируются categories, Product Types и links; переиндексируются затронутые товары | PIM/CMS events + manifest 74 | Шаги 6, 7, 10 и deploy Catalog Cache | В Cache DB присутствует полная цепочка; в ES `types[].groups` содержит `5`; нет дублей | Consumers/sync + точечный reindex обязательны |
| 12 | MD-006 | QA | End-to-end проверка БД → ES → mobile filters → frontend filter | Manifest, ожидаемые Product Types и group 5 | Все предыдущие gates | `POST /mobile/v4/catalog/filters` возвращает уникальный `5` в нужных `types[].groups`; UI показывает Cosmetics и корректные types | Нового deploy нет; дефекты возвращаются владельцу слоя |
| 13 | CMS L1 «Косметика» | Отдельный контентный поток | Создаётся/настраивается навигационный пункт, ссылки и merchandising | Контентная модель CMS | Может идти параллельно, но не закрывает MD-006 | Навигация ведёт на согласованный landing/listing | Отдельная публикация CMS; не заменяет шаги 5–12 |

## 2. Иерархия PIM и точные leaf external_id

Не создавать отдельный корень `Beauty`. Использовать существующие target-group узлы в актуальном production-дереве;
их numeric IDs перед операцией определить поиском, не переносить stage IDs в production.

```text
Girls 13+                                      TARGET_GROUP (существующий)
├── Color Cosmetics                           DEPARTMENT, group=5 (новый)
│   ├── Lips                                   CATEGORY, group=5 (новая)
│   ├── Eyes                                   CATEGORY, group=5 (новая)
│   └── Face                                   CATEGORY, group=5 (новая)
└── Accessories Beauty                        DEPARTMENT, group=5 (новый отдельный узел)
    └── Color cosmetic                         CATEGORY, group=5 (новая)

Girls 2-8                                     TARGET_GROUP (существующий)
└── Color Cosmetics                           DEPARTMENT, group=5 (новый)
    └── Lips                                   CATEGORY, group=5 (новая)
```

Нельзя переиспользовать старый `Accessories Beauty` из группы Accessories, если он относится к group `2` или уже
связан с non-Beauty товарами. Для Cosmetics нужен отдельный department в правильной ветке с group `5`.

| Parent | Department | Leaf name | Точный leaf `external_id` |
|---|---|---|---|
| Girls 13+ | Color Cosmetics | Lips | `Girls 13+ Color Cosmetics Lips` |
| Girls 13+ | Color Cosmetics | Eyes | `Girls 13+ Color Cosmetics Eyes` |
| Girls 13+ | Color Cosmetics | Face | `Girls 13+ Color Cosmetics Face` |
| Girls 2-8 | Color Cosmetics | Lips | `Girls 2-8 Color Cosmetics Lips` |
| Girls 13+ | Accessories Beauty | Color cosmetic | `Girls 13+ Accessories Beauty Color cosmetic` |

Минимум для intended master data: `name_ru`, уникальный `code`, правильный `type`, `group=5`, leaf `external_id`,
`is_active=true`, связь с точным parent. Для department `external_id` не выдумывать: он не участвует в текущем
`ImportProductAction`; заполнять только по утверждённому PLM/master-data правилу.

## 3. Безопасная генерация `pim-client`

1. Зафиксировать commit PIM со spec `5/6`.
2. Генерировать клиент из `OPSOMN002-15/public/api-docs/v1/index.yaml` во временный каталог.
3. Сравнить temp-output с `pim-client-php` на `0784094`.
4. Не переносить raw output целиком: фактическая проверка показала drift в 421 существующем файле.
5. Сначала добавить реальный test на `COSMETICS=5`, `HOME=6` и полный `getAllowableEnumValues()`; получить RED.
6. Перенести вручную только подтверждённый enum-related diff, сохранив `getAllowableEnumValues(): array`.
7. Не менять `ImportProductRequest`; таким образом commit `0784094` сохраняется независимо от решения по
   `OPSOMN-14572`.
8. Если `OPSOMN-14572` формально закрыта/отменена, удаление её DTO-полей допустимо только отдельным review; это не
   должно быть скрытым побочным эффектом задачи CategoryGroup.
9. Прогнать client tests и отдельно проверить serialization test `ImportProductRequest`.
10. Merge результата в `pim-client master`, потому что Catalog Cache требует `dev-master`.
11. В Catalog Cache выполнить целевое обновление `composer update ensi/pim-client --with-dependencies` и проверить,
   что `composer.lock` фиксирует нужный client SHA. Полный бесконтрольный `composer update` не выполнять.

## 4. Replay 74 товаров

`ImportProductAction` вычисляет:

```text
external_id = target_group + " " + department + " " + category
```

После поиска категории выполняется `syncWithoutDetaching`, поэтому replay добавит новую Beauty-связь, но не удалит
старую Buffer-связь и не заполнит `target_category_id`.

Безопасный порядок:

1. Зафиксировать immutable manifest из 74 `product_id`/`vendor_code` и ожидаемого leaf `external_id`.
2. Pre-check: все товары существуют; все пять leaf-категорий существуют; распределение manifest по комбинациям
   равно `26/23/14/10/1` для Lips13+/Eyes13+/Face13+/Lips2-8/Color cosmetic.
3. Выполнить replay manifest.
4. Проверить появление ожидаемой строки в `category_product_links`.
5. Удалить Buffer-link только у товаров manifest и только после успешного Beauty-link.
6. Повторно проверить: ровно один ожидаемый Beauty leaf-link, Buffer-link отсутствует, посторонние links сохранены.
7. Не использовать `target_category_id IS NULL` как причину повторного replay и не обновлять его ради MD-006.

## 5. Product Types

В CMS/Admin Каталог → Типы товаров для каждого имени сначала искать существующий активный тип по коду и названию.
Переиспользовать семантически тот же тип; не создавать дубликат только ради Beauty.

| Product Type | Связать с leaf-категориями |
|---|---|
| Lips | Girls 13+ / Color Cosmetics / Lips; Girls 2-8 / Color Cosmetics / Lips |
| Eyes | Girls 13+ / Color Cosmetics / Eyes |
| Face | Girls 13+ / Color Cosmetics / Face |
| Color cosmetic или согласованный существующий Accessories Beauty type | Girls 13+ / Accessories Beauty / Color cosmetic |

Минимальные обязательные поля нового Product Type: `name_ru`, `is_active=true`, `size_group` по бизнес-правилу;
`code`, `name_en`, `sort` — по действующему справочнику. Связь хранится в `product_type_category_links`.

## 6. Порядок деплоев и операционных действий

```text
PIM code
  → pim-client master
  → Catalog Cache dependency + feature code
  → catalog-cache-client master
  → Admin GUI FE
  → BFF/API-types dependency update и deploy при подтверждённом contract diff
  → PIM categories master data
  → CMS Product Types + category links
  → category/Product Type consumers or explicit sync
  → replay 74 products
  → remove Buffer links for successful subset
  → targeted reindex
  → DB/ES/API/UI QA (MD-006)
```

Admin GUI можно разрабатывать параллельно PIM и Catalog Cache. Его deploy должен завершиться до того, как
контент-команда будет создавать категории через форму. PIM categories и CMS Product Types можно готовить в
runbook заранее, но создавать/линковать только после соответствующих code gates.

## 7. Read-only контрольные точки

Названия connection targets уточняются перед production-проверкой. Все запросы только `SELECT`.

### PIM: пять leaf-категорий

```sql
SELECT id, name_ru, type, "group", external_id, is_active
FROM categories
WHERE external_id IN (
  'Girls 13+ Color Cosmetics Lips',
  'Girls 13+ Color Cosmetics Eyes',
  'Girls 13+ Color Cosmetics Face',
  'Girls 2-8 Color Cosmetics Lips',
  'Girls 13+ Accessories Beauty Color cosmetic'
)
ORDER BY external_id, id;
```

Критерий: пять строк, каждый `external_id` уникален, `type=4` (CATEGORY), `group=5`, `is_active=true`.

### PIM: непосредственные parents

```sql
SELECT child.external_id,
       parent.id AS parent_id,
       parent.name_ru AS parent_name,
       parent.type AS parent_type,
       parent."group" AS parent_group
FROM category_links cl
JOIN categories child ON child.id = cl.category_id
JOIN categories parent ON parent.id = cl.parent_category_id
WHERE child.external_id IN (
  'Girls 13+ Color Cosmetics Lips',
  'Girls 13+ Color Cosmetics Eyes',
  'Girls 13+ Color Cosmetics Face',
  'Girls 2-8 Color Cosmetics Lips',
  'Girls 13+ Accessories Beauty Color cosmetic'
)
ORDER BY child.external_id, parent.id;
```

Критерий: каждый leaf имеет ровно один ожидаемый непосредственный department parent с `type=3`, `group=5`.

### PIM: связи товаров

```sql
SELECT p.id,
       p.vendor_code,
       c.external_id,
       c."group",
       c.type
FROM products p
JOIN category_product_links cpl ON cpl.product_id = p.id
JOIN categories c ON c.id = cpl.category_id
WHERE p.id = ANY(:manifest_product_ids)
ORDER BY p.id, c.id;
```

Критерий: все manifest IDs покрыты; у каждого есть ожидаемый Beauty leaf group `5`; Buffer-link удалён только после
успешной Beauty-связи; прочие допустимые связи не потеряны.

### CMS: Product Types и links

```sql
SELECT pt.id,
       pt.code,
       pt.name_ru,
       pt.is_active,
       ptcl.category_id
FROM product_types pt
JOIN product_type_category_links ptcl ON ptcl.product_type_id = pt.id
WHERE ptcl.category_id = ANY(:beauty_category_ids)
ORDER BY pt.id, ptcl.category_id;
```

Критерий: каждый из пяти category IDs связан с согласованным активным Product Type; случайных дублей нет.

### Catalog Cache DB и Elasticsearch

В Cache DB повторить проверку локальных копий `categories`, `product_types`, `product_type_category_links` и
`category_product_links` для manifest. В Elasticsearch получить документы строго по manifest IDs и проверить:

- `types` содержит ожидаемый Product Type;
- `types[].groups` является массивом;
- `5` присутствует один раз на тип, даже если тип связан с двумя Cosmetics-категориями;
- старые корректные groups не потеряны.

### Mobile API

```http
POST /mobile/v4/catalog/filters
```

Использовать тот же Beauty scope/категорию, что в MD-006. Критерий: соответствующие types содержат уникальный
`groups: [5, ...]`; frontend показывает Cosmetics один раз и локально оставляет только связанные Product Types.

## 8. Минимальный критический путь MD-006

1. Merge и deploy PIM `CategoryGroup 5/6`.
2. Безопасно обновить `pim-client master` и lock Catalog Cache.
3. Реализовать и deploy Catalog Cache `types[].groups`.
4. Deploy Admin GUI с group `5/6` либо предоставить контент-команде проверенный PIM API-runbook.
5. Создать правильную PIM-иерархию и пять exact leaf `external_id`.
6. Создать/переиспользовать Product Types и links в CMS.
7. Дождаться/запустить синхронизацию категорий, типов и links в Catalog Cache.
8. Replay 74 товаров, проверить Beauty-link, удалить Buffer-link у успешного subset.
9. Точечно переиндексировать manifest.
10. Пройти PIM DB → CMS DB → Cache DB → ES → mobile API → UI acceptance.

## 9. Что можно делать параллельно

- Admin GUI FE и Catalog Cache feature после фиксации enum-контракта.
- Исследование BFF/Web/Mobile typed contracts без deploy.
- Подготовка manifest 74 товаров и read-only SQL runbook.
- Дедупликационный аудит Product Types в CMS.
- Подготовка CMS L1 навигации как отдельного контентного потока.

## 10. Что не запускать раньше времени

- Не создавать group `5` categories до deploy PIM.
- Не генерировать `pim-client` слепым overwrite поверх `0784094`.
- Не обновлять весь Composer dependency graph Catalog Cache.
- Не выполнять replay до создания всех пяти exact leaf-категорий.
- Не удалять Buffer-link до подтверждения Beauty-link по каждому товару.
- Не запускать reindex до синхронизации Product Types/category links и deploy новой mapping/data logic.
- Не запускать широкий reindex всего Beauty/catalog без отдельного scope и оценки нагрузки.
- Не закрывать MD-006 только по `target_category_id`; проверять полную каноническую цепочку.

## 11. Открытые release-gates

| Gate | Владелец решения | Условие закрытия |
|---|---|---|
| PIM MR/deploy отсутствует | Александр / PIM developer | Локальный commit `eab4b1c8` pushed, MR создан в `release-26.09`, затем PIM deployed |
| Admin GUI MR/deploy отсутствует | Александр / Admin GUI developer | Локальный commit `0ce1536e` pushed, reviewed и deployed после PIM |
| Полное выравнивание клиента с PIM spec | Product/PIM owner | Вынесено в отдельную задачу; не входит в selective enum update и не блокирует его |
| Manifest 74 отсутствует в release artifacts | Контент/интеграция | Утверждён список IDs/vendor codes и expected external_id |
| Catalog Cache dependency lock закоммичен, но не опубликован | Александр / Catalog developer | Commits `e028f77` и `f39997a` reviewed, pushed/MR в `release-26.09`; полный Pest suite остаётся green |
| Catalog Cache commit/MR/deploy отсутствует | Александр / Catalog developer | Локальный diff `OPSOMN002-15` reviewed, committed, pushed и deployed из `release-26.09`; новый product index создан и наполнен |
| `catalog-cache-client` опубликован, BFF commit не опубликован | Александр / BFF developer | BFF commit `eb626a3b7` reviewed и pushed/MR в `release-26.09` |
| `pim-client` lock обновлён локально во всех backend-потребителях | Александр / Catalog и BFF developers | Catalog Cache commit `f39997a` и BFF dependency diff опубликованы в release-ветках |
| BFF готов локально; Web/Mobile frontend impact не закрыт | Владельцы frontend | Frontend-команды подтверждают поддержку `groups` и `COSMETICS`; BFF diff reviewed, committed и deployed после Catalog Cache |
| Production IDs категорий неизвестны | Контент-команда | После создания выгружены пять IDs и переданы CMS/runbook |
| Способ точечного reindex не зафиксирован | DevOps/Catalog owner | Утверждена команда/endpoint и лимитированный manifest scope |

**Resume pointer:** PIM-код `5/6` закоммичен локально в `OPSOMN002-15` как `eab4b1c8` и не pushed; selective enum
update `pim-client@06d6a59` опубликован в `master`. Admin GUI закоммичен
локально в `OPSOMN002-15` как `0ce1536e`: enum и hardcoded category select дополнены группами `5/6`, regression test
добавлен; Jest `9/9`, targeted ESLint, standalone `tsc --noEmit` и production build проходят. Admin GUI также не
pushed. Catalog Cache реализован локальным commit `e028f77` в `OPSOMN002-15` от `release-26.09@4325ce2d`: отдельный
`ProductTypeData`, уникальные `category.group`, ES mapping/compound, card/facet resources, OpenAPI и rolling fallback
`groups: []`; отдельный commit `f39997a` точечно обновляет `composer.lock` с `pim-client@ab1abb5` на `06d6a59`,
другие пакеты не менялись; полный Pest suite `374/374`, Composer validate и diff checks проходят. Ветка не pushed.
`catalog-cache-client-php@2bdd035` опубликован в
`master`: добавлены `ProductType`/`ProductTypeAggregate` и typed-ссылки карточки/фасетов, targeted PHPUnit проходит
`4 tests, 6 assertions`. В `customers-api-web` создана локальная `OPSOMN002-15` от `release-26.09@c8a41d70`:
lock содержит `catalog-cache-client@2bdd035` и `pim-client@06d6a59`; Web V2/Mobile V4 отдают `types[].groups`,
размеры Beauty получают `type=COSMETICS`, Mobile V4 показывает types для category group `COSMETICS`; V1/Mobile V3
адаптированы к новому внутреннему DTO без расширения ответа. Изменения закоммичены как `eb626a3b7`. Связанные facet suites — `38 passed`; полный suite —
`1374 passed`, `12 skipped`, `4` несвязанных baseline failures в V2/V3 commit-order OpenAPI tests. BFF diff пока не
pushed; публикация остальных веток — отдельный gate.
