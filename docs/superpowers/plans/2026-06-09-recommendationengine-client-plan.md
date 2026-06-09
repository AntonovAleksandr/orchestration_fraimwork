# Recommendation-engine client + IntGateway wiring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Создать тонкий типизированный Go-клиент к сервису рекомендаций (`recomendationengine`, эндпоинт «похожие → массив id») по образцу флота `clients/*client`, и подключить его в IntGateway как реальный `RecommendationSource` вместо временного стаба.

**Architecture:** Новый отдельный Go-модуль `clients/recommendationengineclient` поверх общего сабстрата `gj-go-httpclient` (как `catalogcacheclient`), **без OpenAPI/codegen** — у движка нет спеки, ответ тривиален (`{"items":[]string}`). В IntGateway добавляется адаптер `internal/adapters/recommendations/source.go`, который мостит клиент к доменному порту `RecommendationSource`; `wire/recommendations.go` использует реальный источник, если задан base URL, иначе fallback на стаб. Существующий `CatalogCacheHydrator` (обогащение id → карточки) НЕ меняется.

**Tech Stack:** Go 1.26, `gj-go-httpclient` (substrate: `New(serviceName, baseURL, opts...)`, `DoJSON(ctx, op, method, path, body, out)`, sentinels `ErrUpstream`/`ErrTimeout`, опции `WithMetrics`/`WithRequestDecorator`), `go-chi` (в IntGateway). Без OpenAPI-генерации.

---

## Pre-flight: контекст (прочитать целиком)

**Рабочее окружение.** Всё под `/Users/zak/Projects/GJ-Ecommerce/platform-new/`. Это **go.work-воркспейс** (`platform-new/go.work`) — Go-команды запускать **без** `GOWORK=off` (наоборот, нужен go.work, чтобы локальные клиенты резолвились). Релевантные модули:
- `gj-go-httpclient/` — сабстрат (модуль `gitlab.gloria.aaanet.ru/go-pkg/gj-go-httpclient`).
- `clients/catalog-cache/` — **эталон** клиента (модуль `…/greensight/gj/go/clients/catalogcacheclient`, package `catalogcache`).
- `intgateway/` — BFF (модуль `…/greensight/gj/go/intgateway`).
- `recomendationengine/` — сам движок (для справки; его публичный API — ниже).

**Контракт движка (потребляем):**
```
GET /api/v1/client/products/{article}/similar?limit=<1..40>&section=<all|women|men|kids|teens>&exclude_product_ids=<csv>
200 → {"items": ["GFU000078-1", "GAC026361-1", ...]}    // только массив id
```
(батч `POST /products/similar` в этом плане НЕ реализуем — IntGateway-порту он не нужен.)

**Доменный порт IntGateway** (`intgateway/internal/domains/recommendations/`):
```go
type ProductID string
type SimilarOpts struct { Limit int }
type RecommendationSource interface {
    Similar(ctx context.Context, productID ProductID, opts SimilarOpts) ([]ProductID, error)
}
```
Маркер-ошибка `ErrSourceUnavailable` уже есть; **Service сам оборачивает** ошибку источника в `ErrSourceUnavailable` (адаптеру оборачивать не нужно).

**Сабстрат `gj-go-httpclient` (точные сигнатуры):**
```go
func New(serviceName, baseURL string, opts ...Option) *Client
func (c *Client) DoJSON(ctx context.Context, op, method, path string, body, out any) error
// опции: WithMetrics(*Metrics), WithRequestDecorator(func(ctx, *http.Request)), WithBearerToken, WithHeader, …
// sentinels: ErrUpstream, ErrTimeout (errors.Is)
```

**Нейминг (зафиксировано, по образцу флота):** каталог `clients/recommendation-engine/`, модуль `gitlab.gloria.aaanet.ru/greensight/gj/go/clients/recommendationengineclient`, package `recommendationengine`.

**Ветка:** работать в `intgateway` на новой ветке `task-recs-real-client` от `master`. Новый модуль `clients/recommendation-engine/` — отдельный git-репо? НЕТ: на текущем этапе он живёт локально в `platform-new/clients/recommendation-engine/` и подключается через go.work + `replace`/published. Публикацию в GitLab (как остальные клиенты) делаем отдельным шагом (Task 9) — на усмотрение владельца.

---

## Файловая карта

**Новый модуль `clients/recommendation-engine/`:**
- `go.mod` — модуль `…/clients/recommendationengineclient`, require `gj-go-httpclient`.
- `doc.go` — package doc (без `//go:generate`).
- `client.go` — `Client`, `New`, `SimilarOpts`, `Similar(...)`.
- `client_test.go` — httptest-юнит-тест.
- `README.md` — кратко.

**IntGateway:**
- `internal/adapters/recommendations/source.go` — `EngineSource` (мост клиент → `domain.RecommendationSource`).
- `internal/adapters/recommendations/source_test.go` — тест адаптера (fake client).
- `internal/platform/config/config.go` — новое поле `RecommendationEngine.BaseURL` + env.
- `internal/app/wire/recommendations.go` — реальный источник (fallback на стаб).
- `internal/app/wire/recommendations_test.go` — обновить (опц.).
- `go.mod` / `go.work` — подключить новый клиент.

---

## Task 1: Скелет нового модуля клиента

**Files:**
- Create: `platform-new/clients/recommendation-engine/go.mod`
- Create: `platform-new/clients/recommendation-engine/doc.go`

- [ ] **Step 1: go.mod**

`platform-new/clients/recommendation-engine/go.mod`:
```
module gitlab.gloria.aaanet.ru/greensight/gj/go/clients/recommendationengineclient

go 1.26.0

require gitlab.gloria.aaanet.ru/go-pkg/gj-go-httpclient v0.1.1
```

- [ ] **Step 2: doc.go**

`platform-new/clients/recommendation-engine/doc.go`:
```go
// Package recommendationengine is a thin, typed client for the GJ "similar"
// recommendation service, built on the gj-go-httpclient substrate. It models the
// service wire contract (article -> []id) and nothing about consumers. Hand-written
// (the service has no OpenAPI spec; the response is a trivial {"items":[]string}).
package recommendationengine
```

- [ ] **Step 3: добавить модуль в go.work**

Modify `platform-new/go.work` — добавить строку в блок `use (...)`:
```
	./clients/recommendation-engine
```
(порядок не важен; рядом с другими `./clients/*`).

- [ ] **Step 4: Commit**
```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new
git -C clients/recommendation-engine init 2>/dev/null; true   # если нужен отдельный git — иначе пропустить
git add go.work
git commit -m "build: scaffold recommendationengineclient module + go.work entry"
```

## Task 2: Клиент — тест на успешный Similar (TDD)

**Files:**
- Create: `platform-new/clients/recommendation-engine/client_test.go`

- [ ] **Step 1: Failing test**

`platform-new/clients/recommendation-engine/client_test.go`:
```go
package recommendationengine

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestSimilar_ReturnsIDsAndBuildsRequest(t *testing.T) {
	var gotPath string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.RequestURI()
		_ = json.NewEncoder(w).Encode(map[string]any{"items": []string{"A1", "B2", "C3"}})
	}))
	defer srv.Close()

	c := New(srv.URL)
	ids, err := c.Similar(context.Background(), "GKT028479-2", SimilarOpts{Limit: 20})
	if err != nil {
		t.Fatalf("similar: %v", err)
	}
	if len(ids) != 3 || ids[0] != "A1" {
		t.Fatalf("ids: want [A1 B2 C3], got %v", ids)
	}
	if gotPath != "/api/v1/client/products/GKT028479-2/similar?limit=20" {
		t.Fatalf("path: got %q", gotPath)
	}
}
```

- [ ] **Step 2: Run — fails to compile (New/Similar/SimilarOpts undefined)**
```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/clients/recommendation-engine && go test ./...
```
Expected: build error `undefined: New` / `SimilarOpts`.

## Task 3: Клиент — реализация

**Files:**
- Create: `platform-new/clients/recommendation-engine/client.go`

- [ ] **Step 1: client.go**

`platform-new/clients/recommendation-engine/client.go`:
```go
package recommendationengine

import (
	"context"
	"net/http"
	"net/url"
	"strconv"

	httpclient "gitlab.gloria.aaanet.ru/go-pkg/gj-go-httpclient"
)

const serviceName = "recommendation-engine"

// Client is a typed recommendation-engine client over the shared HTTP substrate.
type Client struct{ hc *httpclient.Client }

// New builds the client. baseURL is scheme+host (no /api/v1). opts pass through to
// gj-go-httpclient (WithMetrics, WithRequestDecorator for X-Request-ID, …).
func New(baseURL string, opts ...httpclient.Option) *Client {
	return &Client{hc: httpclient.New(serviceName, baseURL, opts...)}
}

// SimilarOpts are optional query parameters for Similar.
type SimilarOpts struct {
	Limit             int      // 1..40; 0 → omit (service default)
	Section           string   // all|women|men|kids|teens; "" → omit
	ExcludeProductIDs []string // omitted when empty
}

// Similar returns the ordered list of product ids similar to article. Errors are
// *httpclient.Error from the substrate; classify with errors.Is against
// httpclient.ErrUpstream / ErrTimeout.
func (c *Client) Similar(ctx context.Context, article string, opts SimilarOpts) ([]string, error) {
	q := url.Values{}
	if opts.Limit > 0 {
		q.Set("limit", strconv.Itoa(opts.Limit))
	}
	if opts.Section != "" {
		q.Set("section", opts.Section)
	}
	for _, ex := range opts.ExcludeProductIDs {
		if ex != "" {
			q.Add("exclude_product_ids", ex)
		}
	}
	path := "/api/v1/client/products/" + url.PathEscape(article) + "/similar"
	if enc := q.Encode(); enc != "" {
		path += "?" + enc
	}

	var out struct {
		Items []string `json:"items"`
	}
	if err := c.hc.DoJSON(ctx, "similar", http.MethodGet, path, nil, &out); err != nil {
		return nil, err
	}
	return out.Items, nil
}
```

- [ ] **Step 2: Run test — passes**
```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/clients/recommendation-engine && go test ./...
```
Expected: `ok  …/recommendationengineclient`. (Если go.work не подхватил — `cd platform-new && go work sync`.)

- [ ] **Step 3: Commit**
```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/clients/recommendation-engine
git add . 2>/dev/null; cd /Users/zak/Projects/GJ-Ecommerce/platform-new && git add go.work.sum 2>/dev/null
git commit -m "feat(recommendationengineclient): thin Similar(article, opts) -> []id over gj-go-httpclient"
```

## Task 4: README клиента

**Files:**
- Create: `platform-new/clients/recommendation-engine/README.md`

- [ ] **Step 1: README**

`platform-new/clients/recommendation-engine/README.md`:
```markdown
# recommendationengineclient

Тонкий типизированный Go-клиент к сервису «Похожие» (`recomendationengine`) поверх `gj-go-httpclient`.

```go
c := recommendationengine.New("http://recommendationengine:8080", httpclient.WithMetrics(m))
ids, err := c.Similar(ctx, "GKT028479-2", recommendationengine.SimilarOpts{Limit: 20})
// ids — массив артикулов; обогащение карточек делает потребитель (BFF) из catalog-cache.
```

Контракт: `GET /api/v1/client/products/{article}/similar?limit=&section=&exclude_product_ids=` → `{"items":[]string}`.
Без OpenAPI/codegen — ответ тривиален. Ошибки — `*httpclient.Error` (`errors.Is(err, httpclient.ErrUpstream/ErrTimeout)`).
```

- [ ] **Step 2: Commit**
```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/clients/recommendation-engine && git add README.md && git commit -m "docs: recommendationengineclient README"
```

## Task 5: IntGateway — config для base URL движка

**Files:**
- Modify: `platform-new/intgateway/internal/platform/config/config.go`

- [ ] **Step 1: добавить тип и поле в Config**

В `config.go`, рядом с `CatalogCacheConfig`, добавить:
```go
// RecommendationEngineConfig configures the outbound recommendation-engine client.
type RecommendationEngineConfig struct {
	BaseURL string
}
```
В структуру `Config` добавить поле (рядом с `CatalogCache`):
```go
	RecommendationEngine RecommendationEngineConfig
```

- [ ] **Step 2: загрузка из env**

В функции `Load()` (где формируется `Config{...}`), рядом с `CatalogCache: …`, добавить:
```go
		RecommendationEngine: RecommendationEngineConfig{
			BaseURL: getEnv("RECOMMENDATION_ENGINE_SERVICE_HOST", ""),
		},
```
> Валидацию НЕ добавляем (в отличие от CatalogCache): пустой BaseURL допустим — wire тогда возьмёт стаб (graceful во время раскатки движка).

- [ ] **Step 3: build**
```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/intgateway && go build ./internal/platform/config/...
```
Expected: без ошибок.

- [ ] **Step 4: Commit**
```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/intgateway
git add internal/platform/config/config.go
git commit -m "feat(config): RecommendationEngine.BaseURL (RECOMMENDATION_ENGINE_SERVICE_HOST)"
```

## Task 6: IntGateway — адаптер source (тест → реализация)

**Files:**
- Create: `platform-new/intgateway/internal/adapters/recommendations/source_test.go`
- Create: `platform-new/intgateway/internal/adapters/recommendations/source.go`

- [ ] **Step 1: Failing test**

`platform-new/intgateway/internal/adapters/recommendations/source_test.go`:
```go
package recommendations

import (
	"context"
	"errors"
	"testing"

	domain "gitlab.gloria.aaanet.ru/greensight/gj/go/intgateway/internal/domains/recommendations"
	recengine "gitlab.gloria.aaanet.ru/greensight/gj/go/clients/recommendationengineclient"
)

type fakeEngine struct {
	ids  []string
	err  error
	gotA string
	gotL int
}

func (f *fakeEngine) Similar(_ context.Context, article string, opts recengine.SimilarOpts) ([]string, error) {
	f.gotA, f.gotL = article, opts.Limit
	return f.ids, f.err
}

func TestEngineSource_MapsIDsAndOpts(t *testing.T) {
	fe := &fakeEngine{ids: []string{"A1", "B2"}}
	s := NewEngineSource(fe)
	out, err := s.Similar(context.Background(), domain.ProductID("GKT028479-2"), domain.SimilarOpts{Limit: 20})
	if err != nil {
		t.Fatalf("similar: %v", err)
	}
	if len(out) != 2 || out[0] != domain.ProductID("A1") {
		t.Fatalf("ids mapping: got %v", out)
	}
	if fe.gotA != "GKT028479-2" || fe.gotL != 20 {
		t.Fatalf("opts mapping: article=%q limit=%d", fe.gotA, fe.gotL)
	}
}

func TestEngineSource_PropagatesError(t *testing.T) {
	sentinel := errors.New("upstream boom")
	s := NewEngineSource(&fakeEngine{err: sentinel})
	_, err := s.Similar(context.Background(), "X", domain.SimilarOpts{})
	if !errors.Is(err, sentinel) {
		t.Fatalf("want wrapped sentinel, got %v", err)
	}
}
```

- [ ] **Step 2: Run — fails (NewEngineSource undefined)**
```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/intgateway && go test ./internal/adapters/recommendations/
```
Expected: build error `undefined: NewEngineSource`.

- [ ] **Step 3: source.go**

`platform-new/intgateway/internal/adapters/recommendations/source.go`:
```go
package recommendations

import (
	"context"

	domain "gitlab.gloria.aaanet.ru/greensight/gj/go/intgateway/internal/domains/recommendations"

	recengine "gitlab.gloria.aaanet.ru/greensight/gj/go/clients/recommendationengineclient"
)

// engineClient is the consumer-defined surface the source needs.
// *recengine.Client satisfies it.
type engineClient interface {
	Similar(ctx context.Context, article string, opts recengine.SimilarOpts) ([]string, error)
}

// EngineSource implements domain.RecommendationSource over the recommendation-engine client.
type EngineSource struct{ client engineClient }

// NewEngineSource builds the source.
func NewEngineSource(client engineClient) *EngineSource { return &EngineSource{client: client} }

// Similar returns candidate product ids for productID. The domain Service wraps
// any error here as ErrSourceUnavailable, so we pass it through unwrapped.
func (s *EngineSource) Similar(ctx context.Context, productID domain.ProductID, opts domain.SimilarOpts) ([]domain.ProductID, error) {
	ids, err := s.client.Similar(ctx, string(productID), recengine.SimilarOpts{Limit: opts.Limit})
	if err != nil {
		return nil, err
	}
	out := make([]domain.ProductID, len(ids))
	for i, id := range ids {
		out[i] = domain.ProductID(id)
	}
	return out, nil
}
```

- [ ] **Step 4: добавить require в intgateway/go.mod**
```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/intgateway
go get gitlab.gloria.aaanet.ru/greensight/gj/go/clients/recommendationengineclient
go mod tidy
```
> go.work уже содержит локальный модуль (Task 1) → резолвится локально. Если `go get` ругается на отсутствие в реестре — добавить в `intgateway/go.mod` строку require вручную с версией `v0.0.0-00010101000000-000000000000` (go.work перекроет на локальный), затем `go mod tidy`.

- [ ] **Step 5: Run tests — pass**
```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/intgateway && go test ./internal/adapters/recommendations/
```
Expected: `ok`.

- [ ] **Step 6: Commit**
```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/intgateway
git add internal/adapters/recommendations/source.go internal/adapters/recommendations/source_test.go go.mod go.sum
cd /Users/zak/Projects/GJ-Ecommerce/platform-new && git add go.work.sum 2>/dev/null
git commit -m "feat(intgateway): EngineSource adapter (recommendationengineclient -> RecommendationSource)"
```

## Task 7: IntGateway — wire реального источника (fallback на стаб)

**Files:**
- Modify: `platform-new/intgateway/internal/app/wire/recommendations.go`

- [ ] **Step 1: подключить клиент + источник**

В `wire/recommendations.go`:
1. добавить импорт клиента:
```go
	recengine "gitlab.gloria.aaanet.ru/greensight/gj/go/clients/recommendationengineclient"
```
2. заменить строку `source := recommendations.NewStubSource()` на:
```go
	var source recommendations.RecommendationSource
	if cfg.RecommendationEngine.BaseURL != "" {
		recClient := recengine.New(
			cfg.RecommendationEngine.BaseURL,
			httpclient.WithMetrics(hcm),
			httpclient.WithRequestDecorator(func(ctx context.Context, r *http.Request) {
				if id := reqctx.RequestIDFromContext(ctx); id != "" {
					r.Header.Set("X-Request-ID", id)
				}
				reqctx.PropagateCustomerID(ctx, r)
			}),
		)
		source = recadapter.NewEngineSource(recClient)
	} else {
		source = recommendations.NewStubSource() // fallback во время раскатки движка
	}
```
(импорты `context`, `net/http`, `recadapter`, `reqctx`, `httpclient` уже есть в файле.)

- [ ] **Step 2: build + vet**
```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/intgateway && go build ./... && go vet ./...
```
Expected: без ошибок.

- [ ] **Step 3: Commit**
```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/intgateway
git add internal/app/wire/recommendations.go
git commit -m "feat(intgateway): wire real RecommendationSource when base URL set (stub fallback)"
```

## Task 8: Полная проверка + локальный e2e против стенда

**Files:** —

- [ ] **Step 1: build/vet/test всего IntGateway + клиента**
```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/intgateway && go build ./... && go vet ./... && go test ./...
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/clients/recommendation-engine && go test ./...
```
Expected: всё `ok`, без FAIL.

- [ ] **Step 2: e2e против локального движка (если поднят стенд recomendationengine на :8090)**
```bash
# поднять движок (если не поднят): cd platform-new/recomendationengine && docker compose up -d
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/intgateway
RECOMMENDATION_ENGINE_SERVICE_HOST=http://localhost:8090 \
CATALOG_CATALOG_CACHE_SERVICE_HOST=<catalog-cache-url> \
ORDERS_BASKETS_SERVICE_HOST=<baskets-url> \
go run ./cmd/ecom-gateway &
sleep 2
curl -s 'http://localhost:8080/api/v1/recommendations/similar?product_id=GKT028479-2&limit=10' | head -c 400
kill %1 2>/dev/null
```
Expected: реальный источник вернул id похожих к `GKT028479-2` (движок), гидратор (catalog-cache) собрал карточки. (Если catalog-cache недоступен локально — источник отработает, гидрация даст пусто/ошибку: тогда проверяй сам факт вызова движка по логам клиента.)

- [ ] **Step 3: Commit (если правок не было — пропустить)**

## Task 9 (опционально, координация): публикация клиента в GitLab

- [ ] Создать репо `gitlab.gloria.aaanet.ru/greensight/gj/go/clients/recommendationengineclient` (как остальные `clients/*`), запушить модуль, протегировать `v0.1.0`, заменить в `intgateway/go.mod` псевдо-версию на `v0.1.0`. До публикации — go.work + local replace достаточно для разработки.

---

## Follow-ups / заметки
- Когда реальный источник заведён — **убрать временный стаб** `stubSimilarVendorCodes` из `domains/recommendations/stub.go` (он остаётся как fallback; можно оставить, но почистить 24 хардкод-кода → вернуть к минимальному стабу или удалить вовсе, если fallback не нужен).
- `domain.SimilarOpts` сейчас только `Limit`. Если фронту понадобится `section`/`exclude` — расширить порт и проброс (клиент уже поддерживает).
- Env-имя `RECOMMENDATION_ENGINE_SERVICE_HOST` согласовать с devops (k8s service discovery; см. deploy-задание `docs/deploy/2026-06-09-recommendationengine-deploy-task.md`).

## Definition of Done
- [ ] Модуль `clients/recommendation-engine` собирается, `Similar` покрыт тестом (httptest), в go.work.
- [ ] `EngineSource` адаптер реализует `domain.RecommendationSource`, тесты (маппинг + проброс ошибки) зелёные.
- [ ] `config.RecommendationEngine.BaseURL` из env; wire берёт реальный источник при заданном URL, иначе стаб.
- [ ] `go build/vet/test ./...` в intgateway и клиенте — зелёные.
- [ ] e2e: gateway с `RECOMMENDATION_ENGINE_SERVICE_HOST` отдаёт похожие из реального движка.
