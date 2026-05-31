# catalog-cache client — design

**Дата:** 2026-05-28
**Статус:** на ревью
**Автор:** Zak + Claude (brainstorming)
**Сервис:** `ecom-gateway` (`platform-new/ecom-gateway/`)

## 1. Контекст и цель

`ecom-gateway` — stateless Go/Fiber BFF, v1 которого реализован walking-skeleton-ом (см. `2026-05-27-ecom-gateway-design.md`). В v1 единственный домен `recommendations` использует два **стаб-порта**: `RecommendationSource` (источник кандидатов) и `ProductHydrator` (гидратор карточек). Этот спек закрывает второй из них — заменяет `stubHydrator` на **реальный HTTP-клиент к ENSI `catalog-cache`**.

После реализации этого спека: фронт запрашивает `GET /api/v1/recommendations/similar?product_id=…`, BFF фанит в rec-сервис (по-прежнему стаб, пользователь пишет его отдельно) за списком артикулов, потом в catalog-cache за полными карточками, отдаёт фронту массив `ProductCard` в форме, **совпадающей с frontend'овой `ProductInterface`** (никакой доработки фронта не требуется).

### Решения, зафиксированные на брайнсторме

- **Stack:** Go/`net/http`+chi (ADR-0002), оstается.
- **Codegen-стиль:** types-only через `oapi-codegen` (ADR-0001), оstается; применяем тот же подход к внешнему клиенту.
- **Layout:** `platform/clients/<service>/` (расширение ADR-0003).
- **External contract:** consumer-defined OpenAPI в нашем репо, не вендоринг upstream'а (см. секцию 6 и новый ADR-0008).
- **Shape:** `recommendations.ProductCard` = generated DTO из нашего OpenAPI, повторяет frontend's `ProductInterface` (24 поля).
- **Hexagonal adapter:** `recohydrator/` живёт в `platform/clients/catalogcache/`, импортирует домен (единственное место, где платформа смотрит «внутрь» домена).
- **Misses semantics:** skip-missing + Prometheus метрики (счётчик + ratio-histogram).
- **Error mapping:** все upstream-ошибки → BFF возвращает 502 `source_unavailable`. 400 catalog-cache — тоже 502 (это **наша** ошибка как клиента, а не клиента BFF).
- **Codegen-philosophy:** не оптимизируем generated размер (генерим все типы, что есть в нашем consumer-spec'е) — фильтры добавим, если станет больно.

### Out of scope для v1 этого спека

- Реальный rec-сервис (`RecommendationSource` остаётся стаб; пользователь пишет отдельно).
- Auth-контур для персональных рекомендаций (`sessionctx`, customer JWT).
- OTel tracing outbound HTTP-вызовов (заложено архитектурно через middleware, но включается отдельным циклом).
- Реальный catalog-cache в CI (тестируем через `httptest.NewServer`).
- Кэширование на стороне BFF (catalog-cache уже сам кэш).
- Compound вызовы catalog-cache (несколько ручек за запрос).

## 2. Архитектура и границы

Hexagonal pattern. Port `ProductHydrator` определён в `domains/recommendations` (consumer-defined). Real-адаптер живёт **снаружи домена**, рядом с HTTP-клиентом catalog-cache.

### Файловая структура

```
api/external/catalog-cache/v1/
├── openapi.yaml                                  ⬅ hand-crafted spec (decision 5B.1)
└── oapi-codegen.yaml                             types-only

internal/platform/clients/catalogcache/
├── doc.go                                        //go:generate директива
├── openapi.gen.go                                GENERATED — DTO catalog-cache
├── client.go                                     *Client, NewClient(cfg) +
│                                                 SearchProductCardsOrderedByField(ctx, req)
├── errors.go                                     ErrNotFound, ErrBadRequest, ErrUpstream
├── metrics.go                                    catalogcache_requests_*, catalogcache_request_duration_*
├── client_test.go                                httptest.NewServer тесты
└── recohydrator/                                 адаптер: catalog-cache → recommendations port
    ├── hydrator.go                               реализация recommendations.ProductHydrator
    ├── mapping.go                                catalog-cache ProductCard → наш ProductCard
    ├── enums.go                                  AvailableStatusEnum → PriceStatusEnum translator
    ├── metrics.go                                recommendations_hydration_misses_total,
    │                                             recommendations_hydration_ratio
    └── hydrator_test.go
```

### Импортные правила (расширяем ADR-0003)

- `catalogcache/` — **НЕ импортирует** ничего из `domains/`. Доменно-агностичный.
- `catalogcache/recohydrator/` — импортирует и parent (`catalogcache`), и `domains/recommendations` (port + типы). Это **единственное** место, где платформенный пакет легально импортирует домен. Адаптер — литерально мост.
- `domains/recommendations/` — **НЕ импортирует** `platform/clients/*`. `boundary_test.go` forbidden расширяется на `internal/platform/clients`.
- `internal/app/wire_recommendations.go` — единственный импортёр И `recohydrator`, И `recommendations` (composition root).

### Доменная модель — упрощение

`recommendations.ProductCard` (Go struct в `types.go`) **удаляется**. Используем **generated `ProductCard`** из нашего OpenAPI напрямую. Обоснование: BFF без бизнес-логики над ProductCard, два изоморфных типа = dead weight. Что остаётся в `recommendations/types.go`:

```go
type ProductID string
type SimilarOpts struct { Limit int }
var (
    ErrInvalidArgument   = errors.New("invalid argument")
    ErrSourceUnavailable = errors.New("recommendation source unavailable")
)
```

Port (без изменений по сигнатуре, но возвращаемый тип меняется):
```go
type ProductHydrator interface {
    Hydrate(ctx context.Context, ids []ProductID) ([]ProductCard, error) // ProductCard = generated DTO
}
```

`stub.go` обновляется: заполняет полный `ProductCard` (все 24 поля, фейк-данные).

## 3. Контракт нашего API + data flow

### Изменения в `api/v1/`

- `components/schemas/recommendations.yaml`: схема `SimilarItem` **переименовывается в `ProductCard`** и расширяется до 24 полей, повторяющих frontend's `ProductInterface`. `SimilarResponse.items` теперь `[ProductCard]`.
- `components/schemas/common.yaml`: добавляются nested-схемы `Media`, `Size`, `Modification`, `Label`, `Tag`, `Message`, `Property`, `RecommendationMark`, плюс `PriceStatusEnum`. Каждая — точная зеркальная копия соответствующего frontend interface.

После `make bundle` + `make generate` → новые типы в `internal/domains/recommendations/openapi.gen.go`.

### Shape ProductCard (наш OpenAPI = frontend ProductInterface)

```yaml
ProductCard:
  type: object
  required: [uuid, vendorCodeCc, identifier, name, price, availableStatus,
             images, videos, sizes, modifications, availability_button]
  properties:
    uuid:                  { type: string }              # catalog-cache product_id stringified
    vendorCodeCc:          { type: string }              # catalog-cache vendor_code
    identifier:            { type: string }              # slug
    name:                  { type: string }
    description:           { type: string, nullable: true }
    text:                  { type: string, nullable: true }
    price:                 { type: number }
    oldPrice:              { type: number, nullable: true }
    discountRate:          { type: number, nullable: true }   # computed на BFF
    availableStatus:       { $ref: '#/PriceStatusEnum' }     # enum translated
    hierarchyCode:         { type: string, nullable: true }
    qty:                   { type: integer, nullable: true }
    availability_button:   { type: boolean }              # snake_case — legacy фронт
    availabilityButton:    { type: boolean, nullable: true } # camelCase дубль — legacy фронт
    images:                { type: array, items: { $ref: '../common.yaml#/Media' } }
    videos:                { type: array, items: { $ref: '../common.yaml#/Media' } }
    sizes:                 { type: array, items: { $ref: '../common.yaml#/Size' } }
    modifications:         { type: array, items: { $ref: '../common.yaml#/Modification' } }
    labels:                { type: array, items: { $ref: '../common.yaml#/Label' }, nullable: true }
    additionalLabels:      { type: array, items: { $ref: '../common.yaml#/Label' }, nullable: true }
    messages:              { type: array, items: { $ref: '../common.yaml#/Message' }, nullable: true }
    properties:            { type: array, items: { $ref: '../common.yaml#/Property' }, nullable: true }
    categories:            { type: array, items: { $ref: '../common.yaml#/Tag' }, nullable: true }
    recommendationMarks:   { type: array, items: { $ref: '../common.yaml#/RecommendationMark' }, nullable: true }

PriceStatusEnum:
  type: string
  enum: [available, out_of_stock, on_request, archived]    # подгоняется под фронт PriceStatusEnum
```

### Сквозной flow одного запроса

```
client → GET /api/v1/recommendations/similar?product_id=119871&limit=10
  ↓
recommendations.handler.Similar: parse + validate
  ↓
recommendations.service.Similar(ctx, productID, opts)
  ids := RecommendationSource.Similar(...)            # v1 = stub
  if len(ids)==0 → return []ProductCard{}, nil         # 200 пустая карусель
  cards := ProductHydrator.Hydrate(ctx, ids)          # реальный recohydrator
  ↓
recohydrator.Hydrate(ctx, []ProductID{"ABC52688712-1", …}):
  req := catalogcache.SearchProductCardsOrderedByFieldRequest{
    SortField: "vendor_code",
    Filter:    {"vendor_code": []string{…}},
    Include:   {sizes:1, modifications:1, medias:1, labels:1,
                properties:1, categories:1, messages:1,
                recommendation_marks:1, nameplates:1},
    Pagination:{Limit: len(ids), Type: "offset"},
  }
  ↓
catalogcache.Client.SearchProductCardsOrderedByField(ctx, req):
  POST {baseURL}/api/v1/offers/cards:ordered-by-field-search
  headers: X-Request-ID (из reqctx), Authorization (если token configured)
  per-request deadline = cfg.UpstreamTimeout (800ms default — закрываем TODO из wire_recommendations.go)
  → catalogcache.SearchProductCardsResponse{data: [catalogcache.ProductCard…]}
  ↓
recohydrator маппит each catalogcache.ProductCard → recommendations.ProductCard:
  • field-by-field copy + enum translation + nested types
  • discountRate computed: (old_price - price) / old_price if old_price > price else nil
  • view_target filter: если "card" не в view_target → skip товар (не считается miss)
  • len(result) < len(ids) → metric recommendations_hydration_misses_total++
  • catalog-cache сохраняет порядок sort_field → recohydrator не пересортирует
  ↓
recommendations.handler.toSimilarResponse([]ProductCard) → SimilarResponse{items}:
  identity mapping (ProductCard и SimilarItem совпадают — единый generated тип)
  ↓
client получает SimilarResponse{items:[…]} JSON
```

### Маппинг catalog-cache → наш ProductCard

| Catalog-cache (snake_case) | Наш ProductCard | Заметка |
|---|---|---|
| `product_id` (int) | `uuid` (string) | `strconv.Itoa` |
| `vendor_code` | `vendorCodeCc` | как есть |
| `name`, `description`, `text`, `identifier`, `hierarchy_code` | одноимённые camelCase | как есть |
| `price`, `old_price` | `price`, `oldPrice` | как есть |
| (вычисляется на BFF) | `discountRate` | (old_price - price) / old_price, иначе null |
| `status` (`AvailableStatusEnum`) | `availableStatus` (`PriceStatusEnum`) | **enum translator** |
| `view_target` (array) | (НЕ маппим — фильтр) | если не содержит `"card"` → skip товар |
| `availability_button` | `availability_button` + `availabilityButton` | оба дубля заполняем одним значением |
| `medias` (через include) | `images` + `videos` | по `image_view_type`: image_* → images, video → videos |
| `sizes`, `modifications`, `labels`, `nameplates`, `messages`, `properties`, `categories`, `recommendation_marks` | соответствующие массивы | поэлементный sub-mapper |

## 4. Ошибки и метрики

### Маппинг ошибок

| Источник | Ситуация | Marker в `catalogcache` | recohydrator вверх | Handler → клиент |
|---|---|---|---|---|
| HTTP 200, ответ короче запроса | Часть `vendor_code` не в кэше | (не ошибка) | результат + `misses_total{outcome="partial"}++` | 200, карусель короче |
| HTTP 200, пусто | rec выдал ids, ничего не найдено | (не ошибка) | `[]ProductCard{}` + `misses_total{outcome="full_empty"}++` | 200 `{items:[]}` |
| HTTP 400 | Бракованный запрос с нашей стороны | `ErrBadRequest` | `recommendations.ErrSourceUnavailable` | **502** `source_unavailable` |
| HTTP 404 | Endpoint не существует | `ErrNotFound` | `ErrSourceUnavailable` | **502** |
| HTTP 5xx | Авария catalog-cache | `ErrUpstream` | `ErrSourceUnavailable` | **502** |
| Context deadline | Долгий ответ (>UpstreamTimeout) | `ErrUpstream` + `context.DeadlineExceeded` в unwrap | `ErrSourceUnavailable` | **502** |
| Network error (DNS/refused/EOF) | catalog-cache unreachable | `ErrUpstream` | `ErrSourceUnavailable` | **502** |

400-ошибки → 502 наружу: это наша ошибка как клиента, не клиента BFF.

### Метрики

**Технические (в `catalogcache` пакете):**

| Метрика | Тип | Лейблы |
|---|---|---|
| `catalogcache_requests_total` | counter | `operation`, `outcome` (`success`/`bad_request`/`not_found`/`upstream`/`timeout`/`network`) |
| `catalogcache_request_duration_seconds` | histogram | `operation` |
| `catalogcache_requests_in_flight` | gauge | `operation` |

**Доменные (в `recohydrator/`, namespace `recommendations`):**

| Метрика | Тип | Лейблы |
|---|---|---|
| `recommendations_hydration_misses_total` | counter | `outcome` (`partial`/`full_empty`) |
| `recommendations_hydration_ratio` | histogram | — (buckets: `[0, 0.5, 0.75, 0.9, 0.95, 1.0]`) |

### Логирование (gj-go-logger)

Каждый HTTP-вызов к catalog-cache → одна structured-запись:
```json
{"msg":"catalogcache_call","operation":"search_ordered","method":"POST",
 "path":"/api/v1/offers/cards:ordered-by-field-search","status":200,
 "duration_ms":47,"requested_ids":10,"returned_items":8,"request_id":"…"}
```
Никогда не логируем тело ответа (PII-сейф). На ошибке — добавляем `error`, `error_kind`.

## 5. Тестирование

| Уровень | Где | Цель |
|---|---|---|
| Unit | `catalogcache/client_test.go` | HTTP-клиент: marshalling, statuses → markers, ctx cancellation, timeout, headers |
| Unit | `catalogcache/recohydrator/hydrator_test.go` | mapping, enum translator, view_target filter, discountRate, misses, order |
| Unit | `recommendations/service_test.go` | без изменений |
| Integration | `recommendations/handler_test.go` | дополнительный кейс с реальным recohydrator поверх httptest.NewServer |
| Contract | `catalogcache/testdata/` golden-fixtures | byte-сравнение request body + parsing response fixtures |

### Что особенно покрыть

**`catalogcache/client_test.go`:**
1. Happy path: 200 → правильное тело request + парсинг response.
2. Per-status mapping: 400→ErrBadRequest, 404→ErrNotFound, 5xx→ErrUpstream через `errors.Is`.
3. Context cancellation: cancel ДО ответа → ошибка с `context.Canceled` в unwrap.
4. Timeout: server спит дольше `UpstreamTimeout` → ошибка с `context.DeadlineExceeded` в unwrap.
5. Headers: `X-Request-ID` из `ctx` (через `reqctx.RequestID`); Bearer при наличии токена.
6. JSON content-type на запрос/ответ.

**`recohydrator/hydrator_test.go`:**
1. Field mapping: full ProductCard → проверка точного соответствия всех 24 полей.
2. `product_id` int → `uuid` string.
3. Enum translator: матрица всех значений `AvailableStatusEnum` → `PriceStatusEnum`.
4. view_target filter: товар без `"card"` → НЕ попадает в результат, не считается miss.
5. discountRate: `100→80` ⇒ `0.2`, `null` → `null`, `old<price` → `null`.
6. Misses-счётчик: `partial` vs `full_empty`.
7. Order preservation.
8. Nested mapping: `medias` → images vs videos по `image_view_type`.
9. Error propagation: mock client возвращает `ErrUpstream` → hydrator возвращает `ErrSourceUnavailable`.

Мок catalog-cache `Client` — через **consumer-defined интерфейс** в hydrator-пакете:
```go
type catalogCacheClient interface {  // consumer-defined в recohydrator
    SearchProductCardsOrderedByField(ctx context.Context,
        req catalogcache.SearchProductCardsOrderedByFieldRequest,
    ) (catalogcache.SearchProductCardsResponse, error)
}
```
Реальный `*catalogcache.Client` сатисфицирует автоматически. Fakes — обычные структуры, не mock-фреймворки.

### Golden fixtures в `catalogcache/testdata/`

- `request_search_ordered.json` — образец того, что мы шлём.
- `response_search_ordered_full.json` — полный ответ catalog-cache (рукописный, fixture).
- `response_search_ordered_partial.json` — частичный ответ (миссы).
- `response_search_ordered_view_target_filter.json` — товары без `"card"`.

Назначение: при обновлении наших Go-типов из своего OpenAPI fixtures могут разойтись → тест падает → разработчик осознанно решает.

## 6. External contract vendoring (consumer-defined)

### Решение

Catalog-cache OpenAPI **не вендорится из upstream-репо**. Вместо этого пишем **свой OpenAPI для catalog-cache в нашем репо**, который:
- Описывает только ту часть, которую реально используем (1 эндпоинт + транзитивные схемы).
- Повторяет **текущий wire-формат** catalog-cache (snake_case как есть). Это «consumer-defined contract», но строго совместимый с текущим upstream.
- Обновляется вручную при изменениях upstream (тесты + observability ловят дрейф).

### Альтернативы и почему не они

- **Bundled upstream copy (через `redocly bundle`):** автоматический sync, но 100% upstream формы и 7 эндпоинтов вместо нужного 1. В контексте «мы переписываем на Go» — спорно тащить полный спек.
- **Git submodule на catalog-cache:** жёсткая привязка по SHA, но overhead для одного спека; тащит весь catalog-cache.
- **Build-time path в чужой репо:** хрупко в изолированной CI-сборке.

### Структура файлов

```
api/external/catalog-cache/v1/
├── openapi.yaml              hand-crafted, snake_case, минимальный
└── oapi-codegen.yaml         types-only, output → catalogcache/openapi.gen.go
```

`PULL.md` **не пишется** — спек не пуллится, а сопровождается вручную. Дрейф ловится тестами и метриками upstream-ошибок в проде.

### Makefile

Новая запись в `generate`:
```makefile
generate: bundle
	go generate ./internal/domains/...
	go generate ./internal/platform/clients/...   # ⬅ новое
```

И `go generate ./internal/platform/clients/catalogcache/...` запускает `oapi-codegen` на `api/external/catalog-cache/v1/openapi.yaml`. Никаких изменений в bundle pipeline для нашего own API (это про другой спек).

### ADR-0008 — «External contract vendoring (consumer-defined)»

Зафиксируем отдельным ADR как **общее правило для всех будущих ENSI-клиентов** (offers, pim, baskets…):
- **Status:** Accepted
- **Decision:** для каждого внешнего сервиса, к которому нужен HTTP-клиент из ecom-gateway, **пишем свой OpenAPI в `api/external/<service>/<version>/`**, описывающий только используемое подмножество, повторяющий текущий wire-формат upstream.
- **Alternatives rejected:** bundled-копия upstream (полная), git submodule, build-time path.
- **Consequences:** контроль над собственным consumer-spec'ом, минимальный generated объём, **обязанность ручного sync при изменениях upstream** (компенсируется метриками + интеграционными тестами в staging).

## 7. Конфигурация

| ENV | Default | Required when | Назначение |
|---|---|---|---|
| `RECOMMENDATIONS_HYDRATOR` | `catalogcache` | always | `catalogcache` (real client) или `stub` (для локалки без ENSI) |
| `CATALOG_CACHE_BASE_URL` | — | `RECOMMENDATIONS_HYDRATOR=catalogcache` | напр. `http://catalog-cache.ensi.svc.cluster.local`. Без `/api/v1`, клиент сам приклеит. |
| `CATALOG_CACHE_BEARER_TOKEN` | `""` | optional | Bearer-токен (если cluster потребует). Пустое значение → header не отсылается. |
| `UPSTREAM_TIMEOUT_MS` | `800` | (уже есть) | Per-request deadline на вызов catalog-cache. Закрывает TODO в `wire_recommendations.go`. |

Расширение `internal/platform/config/Config`:
```go
type Config struct {
    AppName, Env    string
    HTTP            HTTPConfig
    UpstreamTimeout time.Duration
    Recommendations RecommendationsConfig   // new
    CatalogCache    CatalogCacheConfig      // new
}

type RecommendationsConfig struct { Hydrator string }   // "catalogcache" | "stub"
type CatalogCacheConfig    struct { BaseURL, BearerToken string }
```

`Config.Validate()` (новый метод) фейлит startup, если `Hydrator=="catalogcache" && BaseURL==""`. Guard от misconfig в k8s.

## 8. Definition of Done

**Код:**
- `api/external/catalog-cache/v1/openapi.yaml` — hand-crafted (описывает 1 endpoint + транзитивные схемы).
- `api/external/catalog-cache/v1/oapi-codegen.yaml` — types-only.
- `internal/platform/clients/catalogcache/{doc,client,errors,metrics}.go` + generated DTO.
- `internal/platform/clients/catalogcache/recohydrator/{hydrator,mapping,enums,metrics}.go`.
- `internal/domains/recommendations/types.go` — `ProductCard` Go-тип убран; `ProductID`/`SimilarOpts`/markers остаются. `boundary_test.go` forbidden расширен.
- `internal/domains/recommendations/stub.go` — обновлён под новый shape.
- `internal/domains/recommendations/handler.go` — `toSimilarResponse` упрощён до identity.
- `internal/app/wire_recommendations.go` — case-switch по `Hydrator`.
- `internal/platform/config/config.go` — новые поля + `Validate()`.

**Контракт:**
- `api/v1/components/schemas/recommendations.yaml` — `SimilarItem` → `ProductCard`.
- `api/v1/components/schemas/common.yaml` — 8 nested-схем + `PriceStatusEnum`.
- `make bundle` + `make generate` без drift.
- `make lint` clean.

**Тесты:**
- Все новые `*_test.go` зелёные.
- `go test -race ./...` clean.

**Docs/ADR:**
- ADR-0008 «External contract vendoring (consumer-defined)» committed.
- `CLAUDE.md` обновлён (новая `platform/clients/` структура).
- `docs/configuration.md` — новые env.
- `docs/runbook.md` — секция «add new ENSI client».
- `docs/architecture/code-organization-contract.md` — boundary rules updated.

**Smoke:**
- `RECOMMENDATIONS_HYDRATOR=stub` → поведение как до изменений.
- `RECOMMENDATIONS_HYDRATOR=catalogcache` + mock catalog-cache (httptest) → similar возвращает полный ProductCard shape, метрики счётчики тикают.

## 9. Explicitly out of scope

- Реальный rec-сервис (отдельный цикл; пользователь пишет сам).
- Auth-контур (`sessionctx`/customer JWT) для персональных рекомендаций.
- OTel tracing outbound HTTP.
- Реальный catalog-cache в CI.
- Кэширование на стороне BFF (catalog-cache сам — кэш).
- Compound вызовы (несколько ручек catalog-cache за запрос).

## 10. References

- Walking-skeleton spec: `docs/superpowers/specs/2026-05-27-ecom-gateway-design.md`
- ADR-0001 (types-only codegen), ADR-0002 (net/http+chi), ADR-0003 (platform/domains layout), ADR-0004 (split OpenAPI), ADR-0008 (external contract vendoring — этот спек его инициирует).
- Catalog-cache OpenAPI (reference): `platform/ensi/apps/catalog/catalog-cache/public/api-docs/v1/index.yaml`.
- Frontend's `ProductInterface`: `platform/site/gj-ng-front/libs/data-access/src/lib/models/catalog/product/product.interface.ts`.
