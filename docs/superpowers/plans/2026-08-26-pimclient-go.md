# PIM Go Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать `pimclient` — тонкий типизированный Go-клиент ENSI PIM по канону уже существующих Go-клиентов парка, с единственным методом «найти SKU по фильтру».

**Architecture:** Повторяет `platform-new/clients/catalog-cache` один в один: consumer-defined подмножество OpenAPI руками → Redocly bundle → `oapi-codegen` генерирует **только DTO** → методы пишутся руками поверх `gj-go-httpclient`. Клиент домен-агностичен: он моделирует контракт PIM и ничего не знает о потребителях.

**Tech Stack:** Go 1.26.0, `gitlab.gloria.aaanet.ru/go-pkg/gj-go-httpclient v0.1.1`, `github.com/oapi-codegen/runtime v1.4.1`, `oapi-codegen` (types-only), `@redocly/cli` через `npx`, `httptest` + JSON-фикстуры.

## Global Constraints

- Репозиторий уже создан: `https://gitlab.gloria.aaanet.ru/greensight/gj/go/clients/pimclient`.
- Module path: `gitlab.gloria.aaanet.ru/greensight/gj/go/clients/pimclient`. Пакет — `pim`. Правило парка: модуль `<имя>client`, пакет — короткое имя (`offersclient`/`offers`, `catalogcacheclient`/`catalogcache`, `buclient`/`bu`).
- `openapi.gen.go` — **генерируемый файл, руками не править**.
- Генерируются только модели (`generate: models: true`). Методы — руками, как во всех клиентах парка.
- Спека — **не** копия апстрима, а честное подмножество того, что клиент реально использует, в snake_case. Поддерживается руками.
- PIM **не требует авторизации**: в спеке PIM нет `security`, у группы `ApiV1` только `->middleware('api')`. Сверено 2026-08-26 по `platform/ensi/apps/catalog/pim`.
- `baseURL` — только схема и хост, без `/api/v1`: префикс входит в константы путей внутри клиента (как в `catalog-cache`).
- Ошибки не заворачивать: наружу отдаётся `*httpclient.Error` из подложки, потребитель классифицирует через `errors.Is` по сентинелам `httpclient`.
- `.gitlab-ci.yml` в клиентских репозиториях нет — не добавлять.
- Потребители подключают клиент по semver-тегу (`v0.1.0`), а не по ветке.

## File Map

Все пути — от корня клонированного `pimclient`.

| Файл | Ответственность |
|---|---|
| `go.mod` | module path, Go 1.26.0, две прямые зависимости |
| `doc.go` | doc-комментарий пакета + директива `go:generate` |
| `client.go` | `New`, константы путей, руками написанные методы |
| `client_test.go` | контрактные тесты на `httptest` + фикстуры |
| `openapi.gen.go` | генерируется, в git коммитится |
| `api/v1/openapi.yaml` | корень спеки, `$ref` на paths/schemas |
| `api/v1/paths/sku_products.yaml` | описание операции поиска |
| `api/v1/components/schemas/sku_products.yaml` | схемы запроса/ответа |
| `api/v1/oapi-codegen.yaml` | конфиг генератора |
| `api/v1/bundle/openapi.yaml` | результат Redocly bundle, коммитится |
| `.redocly.yaml` | отключение неприменимых правил линтера |
| `Makefile` | bundle / generate / lint / build / test / tidy |
| `README.md` | Install, Usage, Contract maintenance, Develop |
| `testdata/sku_products_search.json` | реальный по форме ответ PIM |

---

### Task 1: Каркас модуля и спека

**Files:**
- Create: `go.mod`, `doc.go`, `.redocly.yaml`, `Makefile`
- Create: `api/v1/openapi.yaml`, `api/v1/paths/sku_products.yaml`, `api/v1/components/schemas/sku_products.yaml`, `api/v1/oapi-codegen.yaml`

**Interfaces:**
- Produces: сгенерированные типы `SearchSkuProductsRequest`, `SearchSkuProductsResponse`, `SkuProduct`, `CursorPagination`.

- [ ] **Step 1: Клонировать и инициализировать модуль**

```bash
cd $WORKSPACE/platform-new/clients
git clone git@gitlab.gloria.aaanet.ru:greensight/gj/go/clients/pimclient.git pim
cd pim
go mod init gitlab.gloria.aaanet.ru/greensight/gj/go/clients/pimclient
go get gitlab.gloria.aaanet.ru/go-pkg/gj-go-httpclient@v0.1.1
go get github.com/oapi-codegen/runtime@v1.4.1
```

Сверить `go.mod` с эталоном: `rg -n "^go |gj-go-httpclient|oapi-codegen/runtime" ../catalog-cache/go.mod`.

- [ ] **Step 2: Скопировать обвязку из эталона**

```bash
cp ../catalog-cache/.redocly.yaml ../catalog-cache/Makefile .
```

Ничего в них менять не нужно: `Makefile` параметризован путями `api/v1/...`, а `.redocly.yaml` отключает `security-defined`, `info-license` и `operation-4xx-response`.

- [ ] **Step 3: Написать `doc.go`**

```go
// Package pim is a generated, typed client for ENSI PIM, built on the
// gj-go-httpclient substrate. It is domain-agnostic: it models the PIM wire
// contract and nothing about consumers.
//
// PIM needs no authentication: its ApiV1 route group carries only the `api`
// middleware and the spec declares no security scheme.
package pim

//go:generate oapi-codegen --config api/v1/oapi-codegen.yaml api/v1/bundle/openapi.yaml
```

- [ ] **Step 4: Конфиг генератора `api/v1/oapi-codegen.yaml`**

```yaml
# Types-only: генерируем DTO, методы пишем руками (канон парка клиентов).
# Читает bundled-спеку: oapi-codegen не ходит по кросс-файловым $ref.
# `output` разрешается относительно cwd `go generate` — корня репозитория.
package: pim
generate:
  models: true
output: openapi.gen.go
output-options:
  skip-prune: false
```

- [ ] **Step 5: Схемы `api/v1/components/schemas/sku_products.yaml`**

Поля взяты из `platform/ensi/apps/catalog/pim/public/api-docs/v1/sku_products/schemas/sku_products.yaml`; включено только то, что нужно потребителю.

```yaml
CursorPagination:
  type: object
  description: |
    Курсорная пагинация. В PIM `pagination` — это oneOf курсорной и
    offset-формы, и по умолчанию применяется offset, поэтому `type` надо
    задавать явно.
  properties:
    cursor:
      type: string
      description: Курсор следующей страницы из meta.pagination предыдущего ответа.
    limit:
      type: integer
      example: 1000
    type:
      type: string
      enum: [cursor]

SkuProduct:
  type: object
  description: SKU-уровень товара. Мастер связки «баркод ↔ артикул» (MP-WB-FBS-077).
  required: [id, barcode, vendor_code, product_vendor_code, external_id]
  properties:
    id:
      type: integer
      format: int64
      example: 407792
    product_id:
      type: integer
      format: int64
      nullable: true
    product_vendor_code:
      type: string
      description: Артикул товара (СС) — уровень модели с цветовым вариантом.
      example: "GAS011429-1"
    vendor_code:
      type: string
      description: Артикул SKU — то, что уезжает в OTS как article_id.
      example: "GAS011429F0002"
    external_id:
      type: string
      description: IDD.
      example: "00055550005552694"
    barcode:
      type: string
      description: Штрихкод (EAN13). Единственный ключ, общий с WB и OTS.
      example: "4660207658280"
    size_external_id:
      type: string
      nullable: true
    mark_type:
      type: integer
      nullable: true
      description: Тип маркировки. В проде встречается 0, не только null.
      example: 0
    type_of_good:
      type: integer
      nullable: true

SearchSkuProductsRequest:
  type: object
  properties:
    sort:
      type: array
      items:
        type: string
      description: Разрешён только `id` (SkuProductsQuery.allowedSorts).
      example: ["id"]
    filter:
      type: object
      additionalProperties: true
      description: |
        Разрешены `id` (range), `vendor_code`, `barcode`, вложенный
        `product_status` и `type_of_good`. Имя строится как
        `baseName + suffixes[type]`, а карта суффиксов ставит `equal` в пустую
        строку — поэтому равенство это `barcode` без суффикса, а диапазоны и
        подстроки идут через ДВОЙНОЕ подчёркивание: `id__gt`, `barcode__like`.
        Значение-массив превращается в whereIn, поэтому список баркодов
        передаётся как есть.
    pagination:
      $ref: '#/CursorPagination'

SearchSkuProductsResponse:
  type: object
  required: [data, meta]
  properties:
    data:
      type: array
      items:
        $ref: '#/SkuProduct'
    meta:
      type: object
      properties:
        pagination:
          type: object
          properties:
            cursor:
              type: string
              nullable: true
            limit:
              type: integer
```

- [ ] **Step 6: Операция `api/v1/paths/sku_products.yaml`**

```yaml
SkuProductsSearch:
  post:
    operationId: searchSkuProducts
    summary: Поиск SKU, удовлетворяющих фильтру
    tags: [sku-products]
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '../components/schemas/sku_products.yaml#/SearchSkuProductsRequest'
    responses:
      '200':
        description: OK
        content:
          application/json:
            schema:
              $ref: '../components/schemas/sku_products.yaml#/SearchSkuProductsResponse'
```

- [ ] **Step 7: Корень спеки `api/v1/openapi.yaml`**

```yaml
openapi: 3.0.3
info:
  title: pim client contract
  description: |
    Consumer-defined contract for ENSI PIM. A faithful snake_case subset of the
    upstream wire format, covering only what this client uses. Maintained by
    hand (see README); not auto-pulled from the upstream repo.
  version: 1.0.0
servers:
  - url: /api/v1
tags:
  - name: sku-products
    description: SKU registry — the master of barcode ↔ vendor code.
paths:
  /products/sku-products:search:
    $ref: './paths/sku_products.yaml#/SkuProductsSearch'
```

- [ ] **Step 8: Сгенерировать и собрать**

```bash
make lint && make generate && make build
```

Expected: линтер без ошибок, появился `api/v1/bundle/openapi.yaml` и `openapi.gen.go`, сборка проходит.

- [ ] **Step 9: Коммит**

```bash
git add -A && git commit -m "feat: module skeleton and consumer-defined PIM contract"
```

---

### Task 2: Клиент и контрактные тесты

**Files:**
- Create: `client.go`, `client_test.go`, `testdata/sku_products_search.json`

**Interfaces:**
- Consumes: типы из Task 1.
- Produces:
  - `pim.New(baseURL string, opts ...httpclient.Option) *Client`
  - `(*Client).SearchSkuProducts(ctx context.Context, req SearchSkuProductsRequest) (SearchSkuProductsResponse, error)`

- [ ] **Step 1: Фикстура из реальных данных**

`testdata/sku_products_search.json` — форма ответа PIM с настоящими значениями прод-БД (товарные данные, без ПДн):

```json
{
  "data": [
    {
      "id": 407791,
      "product_id": 39498,
      "product_vendor_code": "GAS011429-1",
      "vendor_code": "GAS011429F0001",
      "external_id": "00055550005552693",
      "barcode": "4660207658273",
      "size_external_id": "00055550001364843",
      "mark_type": 0,
      "type_of_good": null
    },
    {
      "id": 407792,
      "product_id": 39498,
      "product_vendor_code": "GAS011429-1",
      "vendor_code": "GAS011429F0002",
      "external_id": "00055550005552694",
      "barcode": "4660207658280",
      "size_external_id": "00055550001364842",
      "mark_type": 0,
      "type_of_good": null
    }
  ],
  "meta": {"pagination": {"cursor": "eyJpZCI6NDA3NzkyfQ", "limit": 2}}
}
```

- [ ] **Step 2: Написать падающие тесты**

Стиль — как `../catalog-cache/client_test.go`: поднять `httptest`, проверить метод, путь и тело запроса, отдать фикстуру, проверить разбор.

```go
package pim

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestSearchSkuProducts_HappyPath(t *testing.T) {
	var gotPath, gotMethod string
	var gotBody map[string]any
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotMethod, gotPath = r.Method, r.URL.Path
		_ = json.NewDecoder(r.Body).Decode(&gotBody)
		w.Header().Set("Content-Type", "application/json")
		http.ServeFile(w, r, "testdata/sku_products_search.json")
	}))
	defer srv.Close()

	limit := 2
	out, err := New(srv.URL).SearchSkuProducts(context.Background(), SearchSkuProductsRequest{
		Sort:       &[]string{"id"},
		Filter:     &map[string]interface{}{"barcode": []string{"4660207658273", "4660207658280"}},
		Pagination: &CursorPagination{Type: ptr(CursorPaginationTypeCursor), Limit: &limit},
	})
	if err != nil {
		t.Fatalf("call: %v", err)
	}

	if gotMethod != http.MethodPost {
		t.Errorf("method = %s, want POST", gotMethod)
	}
	if gotPath != "/api/v1/products/sku-products:search" {
		t.Errorf("path = %s, want the sku-products search path", gotPath)
	}
	// Фильтр равенства по баркоду — без суффикса: карта суффиксов PIM ставит
	// `equal` в пустую строку. Регресс сюда означает 0 найденных SKU в проде.
	if _, ok := gotBody["filter"].(map[string]any)["barcode"]; !ok {
		t.Errorf("filter = %v, want the bare `barcode` key", gotBody["filter"])
	}

	if len(out.Data) != 2 {
		t.Fatalf("data = %d rows, want 2", len(out.Data))
	}
	if out.Data[1].Barcode != "4660207658280" || out.Data[1].VendorCode != "GAS011429F0002" {
		t.Errorf("row = %+v, want the SKU vendor code for that barcode", out.Data[1])
	}
	if out.Meta == nil || out.Meta.Pagination == nil || out.Meta.Pagination.Cursor == nil {
		t.Fatal("cursor is missing — a full walk could not continue")
	}
}

func TestSearchSkuProducts_UpstreamErrorReachesTheCaller(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()

	if _, err := New(srv.URL).SearchSkuProducts(context.Background(), SearchSkuProductsRequest{}); err == nil {
		t.Fatal("err = nil, want the substrate error passed through")
	}
}
```

Точные имена сгенерированных полей и указателей сверить по `openapi.gen.go` после Task 1 и привести тест к ним; хелпер `ptr` при необходимости объявить в тесте.

- [ ] **Step 3: Прогнать — должны упасть**

Run: `go test ./... -v`
Expected: FAIL — `New`/`SearchSkuProducts` ещё нет.

- [ ] **Step 4: Написать `client.go`**

```go
package pim

import (
	"context"
	"net/http"

	httpclient "gitlab.gloria.aaanet.ru/go-pkg/gj-go-httpclient"
)

const (
	serviceName          = "pim"
	pathSkuProductsSearch = "/api/v1/products/sku-products:search"
)

// Client is a typed PIM client over the shared HTTP substrate.
type Client struct{ hc *httpclient.Client }

// New builds a PIM client. baseURL is scheme+host (no /api/v1). opts pass
// through to gj-go-httpclient (WithRequestDecorator for X-Request-ID
// propagation, WithMetrics to share the fleet metric set, …). PIM needs no
// token, so no auth option is required.
func New(baseURL string, opts ...httpclient.Option) *Client {
	return &Client{hc: httpclient.New(serviceName, baseURL, opts...)}
}

// SearchSkuProducts returns the SKU rows matching req.Filter. Two usage shapes
// matter to callers: a full walk (sort ["id"] plus cursor pagination, following
// meta.pagination.cursor until it is empty) and a targeted lookup (filter
// {"barcode": [...]}, which PIM turns into whereIn).
//
// There is no filter on update time, so an incremental sweep by timestamp is
// not possible — a refresh is either a full walk or a targeted batch.
func (c *Client) SearchSkuProducts(
	ctx context.Context, req SearchSkuProductsRequest,
) (SearchSkuProductsResponse, error) {
	var out SearchSkuProductsResponse
	err := c.hc.DoJSON(ctx, "sku_products_search", http.MethodPost, pathSkuProductsSearch, req, &out)
	return out, err
}
```

- [ ] **Step 5: Прогнать — должны пройти**

Run: `go test ./... -v`
Expected: PASS.

- [ ] **Step 6: Коммит**

```bash
git add -A && git commit -m "feat: typed SKU search over the shared HTTP substrate"
```

---

### Task 3: README, проверка против живого PIM и релиз

**Files:**
- Create: `README.md`
- Create: `docs/superpowers/plans/2026-08-26-pimclient-go.md` (копия этого файла — канон парка: клиент несёт свои документы)

- [ ] **Step 1: README**

Разделы как у `catalog-cache`: `Install`, `Usage`, `Contract maintenance`, `Develop`. Обязательно упомянуть:

- авторизация не нужна;
- `baseURL` без `/api/v1`;
- имена фильтров: равенство без суффикса (`barcode`), диапазоны и подстроки через двойное подчёркивание (`id__gt`, `barcode__like`);
- `pagination.type` надо задавать явно, дефолт в PIM — offset;
- фильтра по времени нет, поэтому инкремент по `updated_at` невозможен;
- `openapi.gen.go` руками не править, менять спеку и делать `make generate`.

- [ ] **Step 2: Проверка против живого PIM (stage)**

Одноразовый скрипт, в репозиторий не коммитить:

```bash
go run - <<'EOF'
// подставить актуальный stage-хост PIM из ms-helm-values/stage/common-env.yaml
EOF
```

Ожидание: непустой `data`, непустой `cursor`, а для запроса с `filter{"barcode": ["4660207658280"]}` — ровно одна строка с `vendor_code = GAS011429F0002`. Это проверяет самое хрупкое место — имя фильтра.

- [ ] **Step 3: Тег и публикация**

```bash
git push origin master
git tag v0.1.0 && git push origin v0.1.0
```

- [ ] **Step 4: Проверить, что модуль резолвится потребителем**

```bash
cd $WORKSPACE/platform-new/wbconnector
GOPRIVATE=gitlab.gloria.aaanet.ru go get gitlab.gloria.aaanet.ru/greensight/gj/go/clients/pimclient@v0.1.0
```

Expected: `go.mod` пополнился строкой с `v0.1.0`, сборка проходит. Если модуль не тянется — проверять Nexus-прокси и `GOPRIVATE`, а не править `go.work`: локальный `go.work` в git не попадает и в CI не участвует.

## Final Verification Gate

- [ ] `make lint`, `make generate`, `make build`, `make test` — все зелёные.
- [ ] `openapi.gen.go` и `api/v1/bundle/openapi.yaml` закоммичены.
- [ ] Тест проверяет и путь, и **имя фильтра равенства** (`barcode` без суффикса).
- [ ] Проверка против живого stage-PIM прошла: адресный запрос по баркоду вернул ожидаемый `vendor_code`.
- [ ] Тег `v0.1.0` в GitLab, `go get` из `wbconnector` работает.
- [ ] `.gitlab-ci.yml` не добавлен.

## Вне объёма

- Любые методы PIM, кроме поиска SKU. Спека — consumer-defined подмножество; расширять по мере надобности отдельными задачами.
- Кеш, ретраи и бизнес-логика: это уровень потребителя (`wbconnector`, задачи 3–5 плана `2026-08-25-wbconnector-pim-identifiers.md`).
- Запись в PIM. Клиент только читает.

## Ловушки, проверенные по коду

1. **Имя фильтра равенства — без суффикса.** `BundleFilter::input('barcode')` строит имя как `baseName + suffixes[type]`, а конфиг пакета `query-builder-extension` ставит `'equal' => ''` и PIM его не переопределяет (в `pim/config/` есть только `query-builder.php`). Поэтому это `barcode`, а не `barcode_equal`. Диапазоны и подстроки — через двойное подчёркивание: `__gt`, `__gte`, `__like`, `__empty`.
2. **Курсорную пагинацию надо запросить явно.** `pagination` в PIM — `oneOf` курсорной и offset-формы; без `type: cursor` применится offset, и обход большого объёма пойдёт по страницам с растущим смещением.
3. **Фильтра по времени нет.** `SkuProductsQuery` разрешает только `id` (range), `vendor_code`, `barcode`, вложенный `product_status`, `type_of_good` и сорт по `id`. Инкремент по `updated_at` невозможен.
4. **Soft-delete в `sku_products` отсутствует** — нет ни `deleted_at`, ни колонки статуса. Отсутствие строки означает настоящее отсутствие SKU.
5. **`mark_type` в проде бывает `0`, а не только `null`** — не трактовать 0 как «не задано».
6. **Баркод — единственный общий ключ с WB.** Модельные коды не совпадают текстуально: у WB в карточке `GAS011429/коричневый`, в PIM `product_vendor_code = GAS011429-1`. Соединять по `product_vendor_code` нельзя без сопоставления цветов.

## Источники

- Эталон: `platform-new/clients/catalog-cache` — `doc.go`, `client.go`, `api/v1/oapi-codegen.yaml`, `Makefile`, `.redocly.yaml`, `client_test.go`.
- Апстрим-спека: `platform/ensi/apps/catalog/pim/public/api-docs/v1/sku_products/`.
- Разрешённые фильтры: `platform/ensi/apps/catalog/pim/app/Http/ApiV1/Modules/Products/Queries/SkuProductsQuery.php`.
- Генерация имён фильтров: `platform/ensi/packages/query-builder-extension/src/{BundleFilter.php,Filters/NameGenerator.php}` и `config/query-builder-extensions.php`.
- Пагинация: `platform/ensi/apps/catalog/pim/public/api-docs/v1/common_schemas.yaml`.
- Потребитель и зачем всё это: `docs/superpowers/plans/2026-08-25-wbconnector-pim-identifiers.md`.
- Значения фикстуры: прод-БД PIM (`ensi-gs-pim-prod`), SKU 407791/407792, снято 2026-08-26.
