# 01 — Product & Content Lifecycle

**Value Stream:** VS-1 (Product to Shelf) + VS-7 (Master Data Sync — частично)  
**Главные системы:** ENSI (PIM, offers, offers-go, feed, catalog-cache, cdn-adapter, cms, bu)  
**Источник:** [`source/ensi-processes.md`](source/ensi-processes.md) разделы 1–2, 6  
**Confluence:** BP-1 «Формирование каталога» (page `60692611`), серия BP-1.* подпроцессов

---

## Цель

Поддерживать актуальный, согласованный набор товаров и контента, который потребляют витрины (Site, Mobile) и внешние каналы (маркетплейсы, рассылки). Покрывает три параллельных потока:

- **Контент** — товар как карточка (атрибуты, описание, медиа, категории, SEO).
- **Коммерция** — цены, скидки, остатки, акции, обсолетность.
- **Дистрибуция** — фиды (Яндекс.Маркет, ВК, Flocktory, MindBox и др.), CDN-картинки.

---

## Перечень процессов

| ID | Название | Триггер | Owner |
|---|---|---|---|
| BP-CAT-01 | Заведение и обновление карточки товара | Контент-менеджер вручную через admin-gui | PIM |
| BP-CAT-02 | Импорт товаров и start-date цен (Excel) | Загрузка XLSX в админке | PIM |
| BP-CAT-03 | Импорт изображений | Загрузка ZIP/каталог | PIM + cdn-adapter |
| BP-CAT-04 | Экспорт товаров | Admin-инициированный download | PIM |
| BP-CAT-05 | Категории, рекомендации, атрибуты | Контент-менеджер | PIM |
| BP-CAT-06 | Индексация для публичной выдачи | Kafka events из PIM/offers/cms | catalog-cache |
| BP-CAT-07 | Генерация и отгрузка фидов | Cron + on-demand | feed (12 реализаций) |
| BP-OFF-01 | Импорт цен и пересборка офферов (PHP) | Pull из WebAPI | offers |
| BP-OFF-02 | Параллельная пересборка через Go | Дублирует BP-OFF-01 | offers-go |
| BP-OFF-03 | Сток (остатки) — Kafka push-flow | Push из 1C/OTS → Integration → ENSI | offers + Integration |
| BP-OFF-04 | SKU obsolete (вывод из ассортимента) | Бизнес-правило | offers |
| BP-OFF-05 | Промо и акции на товары | Внешний PromotionService | offers + cms |
| BP-CMS-01 | Контент-страницы (CMS) | Контент-менеджер | cms |

---

## BP-CAT-01 — Заведение и обновление карточки товара

**Цель:** контент-менеджер создаёт карточку с описанием, атрибутами, медиа, ценой и публикует её на витрине.

**Акторы:** контент-менеджер (через admin-gui), система (Kafka observers).

**Сервисы:** `catalog/pim` → Kafka → `catalog/catalog-cache` → ENSI BFF → витрина.

### Шаги

1. **Создание Product** в admin-gui → запись в PIM (`platform/ensi/apps/catalog/pim`).
2. PIM срабатывает Kafka-observer (синхронный produce) и публикует событие:
   - `pim_product_created` / `pim_product_updated`
   - `pim_offer_created` (когда привязали SKU)
   - `pim_brand_*`, `pim_category_*` — на изменения связанных
3. Подписчики:
   - **`catalog-cache`** — индексирует, готовит представление для фронта (см. BP-CAT-06).
   - **`feed`** — пересобирает фиды (см. BP-CAT-07).
   - **`event-dispatcher`** — внешние интеграции (если product попадает в фильтр).
4. Картинки загружаются через `cdn-adapter`, который хранит и отдаёт URL (BP-CAT-03).
5. После публикации товар становится видим:
   - на витрине — через `customers-api-web` → `catalog-cache`,
   - в фидах — после следующего прогона.

### Сущности

- `Product`, `Sku` (PIM)
- `Brand`, `Category` (PIM)
- `Offer` (offers) — связь product↔SKU↔price↔stock

### Quirks

- **Sync produce** в Kafka из PIM-observer — может удлинять API-запрос; нет outbox-паттерна (риск двойной записи при ошибках).
- Изменения каскадируются через ~30+ Kafka-топиков ENSI — карта в [`source/ensi-processes.md`](source/ensi-processes.md#сводная-карта-kafka-топиков-исходящие-из-ensi).

### Код

- PIM observers: `platform/ensi/apps/catalog/pim/app/Domain/Catalog/Observers/`
- Kafka producers: `platform/ensi/apps/catalog/pim/app/Domain/Catalog/Kafka/`

---

## BP-CAT-02 — Импорт товаров и start-date цен (Excel)

**Цель:** массовое создание/обновление товаров и цен через загрузку XLSX.

**Триггер:** контент-менеджер загружает файл в admin-gui.

### Шаги

1. XLSX парсится в PIM (отдельный action-класс).
2. Каждая строка → upsert `Product`/`Sku`.
3. Цены с `start_date` в будущем — попадают в офферы как **отложенные** (применяются по cron, см. BP-OFF-01).
4. Логируется батч-операция (audit).

### Quirks

- Формат жёстко привязан к шаблону Excel — изменения требуют синхронизации с командой мерчандайзинга.
- Большие импорты могут блокировать таблицы; обычно гоняют ночью.

---

## BP-CAT-03 — Импорт изображений

**Цель:** массово загрузить медиа для SKU.

**Сервисы:** `catalog/pim` + `connectors/cdn-adapter`.

### Шаги

1. Контент-менеджер заливает ZIP/каталог изображений (имена соответствуют артикулам).
2. PIM передаёт файл в `cdn-adapter` → CDN.
3. URL картинки записывается на `Product.images[]`.
4. Kafka-event `pim_product_updated` → catalog-cache + feed.

---

## BP-CAT-04 — Экспорт товаров

Backoffice-инструмент: выгрузить текущий каталог в Excel для проверок и подготовки правок.

---

## BP-CAT-05 — Категории, рекомендации, атрибуты

**Цель:** структура каталога (дерево категорий), атрибуты товаров, перекрёстные рекомендации.

### Шаги

1. Контент-менеджер правит дерево категорий → `pim_category_updated` Kafka-event.
2. Атрибуты (свойства товара) ведутся как справочник + значения на SKU.
3. Рекомендации (related products, cross-sell) — backoffice-таблица. Возможно дополняется ML-логикой во внешнем сервисе (см. open question в `source/ensi-processes.md`).

---

## BP-CAT-06 — Индексация для публичной выдачи (catalog-cache)

**Цель:** поддерживать денормализованное представление каталога для фронта (поиск, фильтры, карточки).

**Сервис:** `catalog/catalog-cache`.

### Шаги

1. Слушает **28 Kafka-топиков** от PIM, offers, cms, bu.
2. По каждому событию — пересчитывает представление товара (атрибуты, цена, наличие, картинки, категории, акции).
3. Витрина (Site/Mobile через `customers-api-web`) ходит за каталогом сюда.

### Quirks

- ES 7.9.2 в качестве search-engine.
- При лагах Kafka — каталог-cache отстаёт от PIM; редкие визуальные несоответствия в админке vs на сайте.

### Код

- `platform/ensi/apps/catalog/catalog-cache/app/Domain/Kafka/Listeners/`

---

## BP-CAT-07 — Генерация и отгрузка фидов

**Цель:** регулярно собирать товарные фиды для маркетинга и маркетплейсов.

**Сервис:** `catalog/feed`.

### Известные реализации (12 шт)

- Yandex.CC (Yandex content catalog)
- Yandex SKU (Yandex.Market товарный фид)
- Marketplace (универсальный)
- MindBox (CRM/маркетинг)
- Flocktory (ретаргетинг)
- VK
- … (полный список — `source/ensi-processes.md`)

### Шаги (общая схема)

1. Cron по расписанию запускает feed-job для конкретной интеграции.
2. Job читает `catalog-cache` (или PIM напрямую), собирает XML/CSV.
3. Файл загружается на FTP/S3/HTTP receiver партнёра.
4. Лог + audit.

### Quirks

- Каждая интеграция — отдельный класс/команда. Дубль логики между ними.

---

## BP-OFF-01 — Импорт цен и пересборка офферов (PHP)

**Сервис:** `catalog/offers` (PHP).

### Шаги

1. Cron pull'ит цены из WebAPI (внешний прайс-провайдер).
2. Сохраняет в `Offer.prices` с `start_date`.
3. Cron же активирует «вступающие в силу» цены (когда `now() >= start_date`).
4. Kafka produce: `offers_offer_price_updated`, `offers_offer_updated`.
5. catalog-cache подхватывает → витрина.

### Quirks

- `WebAPI` — это XML-API внешнего 1С-провайдера.
- Хардкод нескольких справочников (sizeMap и т.п.).

### Код

- `platform/ensi/apps/catalog/offers/app/Domain/Offers/`

---

## BP-OFF-02 — Параллельная пересборка через Go (`offers-go`)

**Сервис:** `catalog/offers-go`.

**Зачем:** Go-реализация того же импорта — пишется как замена PHP-варианту. Сейчас работают **обе** (legacy в проде, Go как пилот).

### Quirks

- **Двойная истина** — пока обе крутятся, нужны проверки consistency.
- Open question: когда выпиливают PHP?

---

## BP-OFF-03 — Сток (остатки) — Kafka push-flow

**Цель:** держать актуальные остатки в offers / catalog-cache.

### Шаги

1. **Источник** — 1C/OTS/Retail через Integration (см. BP-INT-25, BP-INT-26 в `08-master-data-sync.md`).
2. Integration публикует Kafka-события со стоками.
3. `offers` consumes → `Offer.stocks` per warehouse.
4. `catalog-cache` consumes → пересчитывает «есть/нет» для витрины.

### Quirks

- Несколько источников (OTS init+delta, CB-1C-Retail init+auto+retry, OMS notification poll) — путаница в **главном источнике правды**.

---

## BP-OFF-04 — SKU obsolete

**Цель:** управление SKU, выводимыми из ассортимента.

**Документация:** 4 ревизии Confluence (см. `source/confluence-findings.md`).

### Шаги

1. Бизнес-правило (например, нет продаж N месяцев + остаток < X) ставит флаг `obsolete`.
2. catalog-cache фильтрует obsolete SKU из поиска.
3. Внешние фиды получают сигнал depubliсh.

---

## BP-OFF-05 — Промо и акции

**Внешний сервис:** PromotionService (не входит в ENSI).

### Шаги

1. Маркетинг заводит акцию во внешнем сервисе.
2. Акция применяется при расчёте корзины (см. `03-browse-cart-precheckout.md` BP-BSK-03).
3. Витрина показывает плашку «акция» через catalog-cache.

### Quirks

- Описание промо-сценариев фрагментировано (см. Confluence: AKZ-*/MARKMTG-* спейсы).

---

## BP-CMS-01 — Контент-страницы

**Сервис:** `cms/cms`.

Хранение баннеров, лендингов, блоков на главной, SEO-метаданных. Публикуется через тот же BFF.

---

## Сводная карта Kafka-исходящих из ENSI

(сокращённо; полная — в `source/ensi-processes.md`)

| Топик | Источник | Потребители |
|---|---|---|
| `pim_product_*` | pim | catalog-cache, feed, event-dispatcher |
| `pim_offer_*` | pim | catalog-cache, offers |
| `pim_category_*`, `pim_brand_*` | pim | catalog-cache |
| `offers_offer_*` | offers | catalog-cache |
| `offers_stock_*` | offers | catalog-cache |
| `customers_*` | customers | order-group, baskets |
| `baskets_*` | baskets | offers (на checkout), audit |
| `cms_*` | cms | catalog-cache |
| `orders_order_*` | order-group | baskets, customers, audit, event-dispatcher |

---

## Системные quirks (доменные)

1. **Sync Kafka-produce** в большинстве observers — нет outbox, риск дрейфа.
2. **PHP + Go двойник** для offers — open question по дате замораживания PHP.
3. **XML-API** для импорта цен — формат жёсткий, изменения требуют согласования с поставщиком.
4. **Размерная сетка** — хардкоды в нескольких местах.
5. **catalog-cache** слушает 28 топиков — точка единого консолидирования, но при инцидентах в Kafka вся витрина отстаёт.

---

## Связанные сервисы

- `connectors/audit` — пишет лог всех мутаций PIM/offers.
- `connectors/cdn-adapter` — хранение медиа (см. BP-CAT-03).
- `connectors/event-dispatcher` (PHP + Go) — отправка внешних webhook'ов по order-событиям (используется в `07-post-order-and-comms.md`, не в этом домене).
- `units/bu` — справочник складов и юр.лиц. Слушает изменения у себя, эмитит → catalog-cache и Integration (BP-INT-28).

---

## Confluence — главные страницы

| Тема | Confluence page |
|---|---|
| BP-1 Формирование каталога | `60692611` |
| Серия BP-1.1, BP-1.2 … подпроцессы | дочерние от `60696260` |
| Функциональная нарезка: Catalog, Offers, Feed | `60689793` (индекс) |
| Промо/Акции | в спейсах AKZ-* / MARKMTG-* |

Полная сводка — [`source/confluence-findings.md`](source/confluence-findings.md) разделы 1, 2.

---

**Дата создания:** 2026-05-16  
**Поддерживается:** команда контента и архитектуры ENSI
