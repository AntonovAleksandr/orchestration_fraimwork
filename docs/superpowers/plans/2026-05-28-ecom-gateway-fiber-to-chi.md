# ecom-gateway: Fiber → `net/http` + chi migration

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Migrate the existing `ecom-gateway` walking-skeleton from Fiber v2 to `net/http` + `go-chi/chi/v5`. Behaviour and contract unchanged; all tests + smoke test still green.

**Decision record:** [ADR-0002](../../../platform-new/ecom-gateway/docs/architecture/adr/0002-net-http-chi-over-fiber.md).

**Architecture:** 1:1 idiomatic translation. Handlers `func(http.ResponseWriter, *http.Request)`. Middleware `func(http.Handler) http.Handler`. Request-scoped data via `r.Context()` + the existing `reqctx` package (re-implemented over `context.WithValue`). chi router under `internal/http/server.go`. `promhttp.Handler()` mounted directly — no `gofiber/adaptor`.

**Out of scope:**
- Behaviour changes (response shape, status codes, query param semantics — all preserved exactly).
- ADR-0001 reversal (still types-only DTO codegen; handlers still hand-written).
- Docker / Makefile / OpenAPI spec (`openapi.yaml`, `openapi.gen.go`) — unchanged.
- README / runbook text — `make run` stays the same.

**Repo:** `platform-new/ecom-gateway/` (independent git, branch `main`). Workspace-root is **not** touched.

---

## Pre-migration state (commit `1c25fb7`)

The pre-migration tree uses these Fiber-specific things to replace:

| Where | Fiber idiom | net/http+chi replacement |
|---|---|---|
| Handlers | `func(c *fiber.Ctx) error` | `func(w http.ResponseWriter, r *http.Request)` |
| Query param | `c.Query("k")` | `r.URL.Query().Get("k")` |
| Request context | `c.UserContext()` | `r.Context()` |
| Per-request locals | `c.Locals(k, v)` / `c.Locals(k).(string)` | `context.WithValue(r.Context(), k, v)` carried via `*http.Request` mutation (`r = r.WithContext(...)`) |
| Status + JSON | `c.Status(s).JSON(v)` | `w.Header().Set("Content-Type","application/json"); w.WriteHeader(s); json.NewEncoder(w).Encode(v)` (helper) |
| Route mounting | `router.Group("/api/v1"); g.Get("/foo", h)` | `r.Route("/api/v1", func(r chi.Router) { r.Get("/foo", h) })` |
| Metrics middleware | Fiber middleware reading `ctx.Route().Path` | net/http middleware reading `chi.RouteContext(r.Context()).RoutePattern()` |
| `/metrics` | `adaptor.HTTPHandler(promhttp.HandlerFor(...))` | `promhttp.HandlerFor(...)` directly |
| Server | `fiber.New(); app.Listen(); app.ShutdownWithContext(ctx)` | `&http.Server{Handler: r}; srv.ListenAndServe(); srv.Shutdown(ctx)` |
| Test app | `app.Test(httptest.NewRequest(...))` returns `*http.Response` | Use `httptest.NewRecorder()` against `chi.Router.ServeHTTP`, or `httptest.NewServer(r)` + `http.Get` |
| Recovery middleware | Fiber-specific | chi has `middleware.Recoverer`; we still need our own to format the envelope and log via gj-logger |

`go.mod` cleanup:
- Remove: `github.com/gofiber/fiber/v2`, `github.com/gofiber/adaptor/v2`.
- Add: `github.com/go-chi/chi/v5@v5.1.0` (or latest 5.x).
- Keep: `github.com/google/uuid`, `github.com/prometheus/client_golang`, `gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger`, `github.com/oapi-codegen/runtime`.

`internal/recommendations/openapi.gen.go` — generated DTOs, package-internal struct types. **Not touched** — verified by `git diff --exit-code` after migration.

---

## Task M2 — Foundational layers (leaf packages, no transitive Fiber deps after)

**Files:**
- `internal/reqctx/reqctx.go`, `internal/reqctx/reqctx_test.go`, `internal/reqctx/helpers_test.go`
- `internal/httpx/error.go`, `internal/httpx/error_test.go`
- `internal/observability/{metrics,middleware,handler,routes,metrics_test}.go`

### Step 1 — Rewrite `internal/reqctx/reqctx.go`

```go
// Package reqctx is the dedicated place for per-request data carried via the
// request context (guideline §6.2). Today it holds only the request ID; user
// identity will be added here when the personal-recommendations contour lands.
package reqctx

import (
	"context"
	"net/http"
)

// Unexported key type prevents collisions with other packages.
type ctxKey int

const requestIDKey ctxKey = iota

// WithRequestID returns a new context carrying the request ID.
func WithRequestID(ctx context.Context, id string) context.Context {
	return context.WithValue(ctx, requestIDKey, id)
}

// SetRequestID is a convenience that mutates the request's context in place
// (returns the updated request). Useful inside middleware.
func SetRequestID(r *http.Request, id string) *http.Request {
	return r.WithContext(WithRequestID(r.Context(), id))
}

// RequestIDFromContext returns the request ID stored in ctx, or "" if none.
func RequestIDFromContext(ctx context.Context) string {
	if v, ok := ctx.Value(requestIDKey).(string); ok {
		return v
	}
	return ""
}

// RequestID extracts the request ID from r.Context(), or "" if none.
func RequestID(r *http.Request) string {
	return RequestIDFromContext(r.Context())
}
```

### Step 2 — Rewrite `internal/reqctx/reqctx_test.go`

```go
package reqctx

import (
	"net/http/httptest"
	"testing"
)

func TestSetAndGetRequestID(t *testing.T) {
	r := httptest.NewRequest("GET", "/x", nil)
	r = SetRequestID(r, "abc-123")
	if got := RequestID(r); got != "abc-123" {
		t.Fatalf("RequestID: want abc-123, got %q", got)
	}
}

func TestRequestIDEmptyWhenUnset(t *testing.T) {
	r := httptest.NewRequest("GET", "/x", nil)
	if got := RequestID(r); got != "" {
		t.Fatalf("RequestID: want empty, got %q", got)
	}
}
```

Delete `internal/reqctx/helpers_test.go` — no longer needed (we use `httptest.NewRequest` directly).

### Step 3 — Rewrite `internal/httpx/error.go`

```go
package httpx

import (
	"encoding/json"
	"net/http"
)

// ErrorEnvelope is the canonical JSON error shape for all REST endpoints.
type ErrorEnvelope struct {
	Error   string `json:"error"`
	Message string `json:"message"`
}

// Helper writes canonical error envelopes. Construct one and inject it into
// each handler. It holds no state today but is a struct so future cross-cutting
// concerns attach without changing call sites.
type Helper struct{}

// NewHelper constructs a Helper.
func NewHelper() *Helper { return &Helper{} }

// JSON writes a canonical error envelope with the given status.
func (h *Helper) JSON(w http.ResponseWriter, status int, code, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(ErrorEnvelope{Error: code, Message: msg})
}

// BadRequest writes a 400 response.
func (h *Helper) BadRequest(w http.ResponseWriter, code, msg string) {
	h.JSON(w, http.StatusBadRequest, code, msg)
}

// Internal writes a 500 response.
func (h *Helper) Internal(w http.ResponseWriter, code, msg string) {
	h.JSON(w, http.StatusInternalServerError, code, msg)
}
```

Note: methods now return `void` (we write directly to `w`). Callers no longer `return h.errs.BadRequest(...)`; they call it then `return`.

### Step 4 — Rewrite `internal/httpx/error_test.go`

```go
package httpx

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestBadRequestWritesEnvelope(t *testing.T) {
	h := NewHelper()
	rec := httptest.NewRecorder()
	h.BadRequest(rec, "invalid_argument", "product_id is required")

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status: want 400, got %d", rec.Code)
	}
	var env ErrorEnvelope
	if err := json.Unmarshal(rec.Body.Bytes(), &env); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if env.Error != "invalid_argument" || env.Message != "product_id is required" {
		t.Fatalf("envelope: %+v", env)
	}
}

func TestJSONStatusPassthrough(t *testing.T) {
	h := NewHelper()
	rec := httptest.NewRecorder()
	h.JSON(rec, http.StatusBadGateway, "source_unavailable", "upstream down")
	if rec.Code != http.StatusBadGateway {
		t.Fatalf("status: want 502, got %d", rec.Code)
	}
}
```

### Step 5 — Rewrite `internal/observability/middleware.go`

```go
package observability

import (
	"net/http"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"
)

// Middleware records per-request HTTP metrics. Wrap with NewMiddleware(m).Wrap.
type Middleware struct{ m *Metrics }

// NewMiddleware creates a Middleware backed by the given Metrics.
func NewMiddleware(m *Metrics) *Middleware { return &Middleware{m: m} }

// statusRecorder captures the status code written by the downstream handler.
// Defaults to 200 (the implicit status if the handler never calls WriteHeader).
type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (sr *statusRecorder) WriteHeader(code int) {
	sr.status = code
	sr.ResponseWriter.WriteHeader(code)
}

// Wrap returns a middleware that records request count + latency. Uses chi's
// RoutePattern() to keep label cardinality bounded.
// Nil Metrics is a no-op pass-through.
func (mw *Middleware) Wrap(next http.Handler) http.Handler {
	if mw.m == nil {
		return next
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mw.m.HTTPRequestsInFlight.Inc()
		defer mw.m.HTTPRequestsInFlight.Dec()

		sr := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		start := time.Now()
		next.ServeHTTP(sr, r)
		duration := time.Since(start).Seconds()

		route := chi.RouteContext(r.Context()).RoutePattern()
		if route == "" {
			route = "unmatched"
		}
		method := r.Method
		status := strconv.Itoa(sr.status)

		mw.m.HTTPRequestsTotal.WithLabelValues(method, route, status).Inc()
		mw.m.HTTPRequestDuration.WithLabelValues(method, route).Observe(duration)
	})
}
```

### Step 6 — Rewrite `internal/observability/handler.go`

```go
package observability

import (
	"net/http"

	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// Handler serves the Prometheus scrape endpoint.
type Handler struct{ m *Metrics }

// NewHandler creates a Handler backed by the given Metrics.
func NewHandler(m *Metrics) *Handler { return &Handler{m: m} }

// ServeHTTP is the http.Handler for GET /metrics.
// Nil Metrics returns 503.
func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if h.m == nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		return
	}
	promhttp.HandlerFor(h.m.Registry(), promhttp.HandlerOpts{}).ServeHTTP(w, r)
}
```

### Step 7 — Rewrite `internal/observability/routes.go`

```go
package observability

import "github.com/go-chi/chi/v5"

// Deps carries dependencies required to mount observability routes.
type Deps struct{ Metrics *Metrics }

// Mount registers /metrics first (so it stays scrapable even if downstream
// middleware errors), then applies the instrumentation middleware so every
// subsequent handler in the router is measured.
//
// Call this on the root router BEFORE mounting any other routes.
func Mount(r chi.Router, deps Deps) {
	h := NewHandler(deps.Metrics)
	r.Method(http.MethodGet, "/metrics", h)
	r.Use(NewMiddleware(deps.Metrics).Wrap)
}
```

Note: `Mount` requires an `import "net/http"` for `http.MethodGet`. Add it.

### Step 8 — `internal/observability/metrics.go` is unchanged

This file uses only `prometheus/client_golang`. Leave it as-is.

### Step 9 — `internal/observability/metrics_test.go` is unchanged

Same reason. Leave as-is.

### Step 10 — Build + test the foundational layers

```bash
go build ./internal/reqctx/ ./internal/httpx/ ./internal/observability/
go test ./internal/reqctx/ ./internal/httpx/ ./internal/observability/
```
Both should pass. Note: `go build ./...` will still FAIL until M3 and M4 because `recommendations` and `internal/http` still reference Fiber. That's expected at this point.

### Step 11 — Commit M2

```bash
git -C /Users/zak/Projects/GJ-Ecommerce/platform-new/ecom-gateway add internal/reqctx/ internal/httpx/ internal/observability/
git -C /Users/zak/Projects/GJ-Ecommerce/platform-new/ecom-gateway commit -m "refactor(chi): migrate foundational layers (reqctx, httpx, observability) to net/http"
```

---

## Task M3 — Domain + health

### Step 1 — Rewrite `internal/health/handler.go`

```go
package health

import (
	"encoding/json"
	"net/http"
)

// Handler exposes health endpoints over net/http.
type Handler struct{ service *Service }

// NewHandler constructs a Handler.
func NewHandler(service *Service) *Handler { return &Handler{service: service} }

// Live handles GET /health/live.
func (h *Handler) Live(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, h.service.Live())
}

// Ready handles GET /health/ready.
func (h *Handler) Ready(w http.ResponseWriter, r *http.Request) {
	resp := h.service.Ready()
	status := http.StatusOK
	if resp.Status != "ready" {
		status = http.StatusServiceUnavailable
	}
	writeJSON(w, status, resp)
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
```

### Step 2 — Rewrite `internal/health/routes.go`

```go
package health

import "github.com/go-chi/chi/v5"

// Deps carries dependencies required to mount health routes.
type Deps struct{ Handler *Handler }

// Mount registers the health routes.
func Mount(r chi.Router, deps Deps) {
	r.Get("/health/live", deps.Handler.Live)
	r.Get("/health/ready", deps.Handler.Ready)
}
```

### Step 3 — Rewrite `internal/health/health_test.go`

```go
package health

import (
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"
)

func mount(t *testing.T, ready func() error) http.Handler {
	t.Helper()
	r := chi.NewRouter()
	svc := NewService("ecom-gateway", "test", ready)
	Mount(r, Deps{Handler: NewHandler(svc)})
	return r
}

func TestLiveOK(t *testing.T) {
	r := mount(t, nil)
	rec := httptest.NewRecorder()
	r.ServeHTTP(rec, httptest.NewRequest("GET", "/health/live", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("live: want 200, got %d", rec.Code)
	}
}

func TestReadyOKWhenNoChecks(t *testing.T) {
	r := mount(t, nil)
	rec := httptest.NewRecorder()
	r.ServeHTTP(rec, httptest.NewRequest("GET", "/health/ready", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("ready: want 200, got %d", rec.Code)
	}
}

func TestReadyUnavailableWhenCheckFails(t *testing.T) {
	r := mount(t, func() error { return errors.New("down") })
	rec := httptest.NewRecorder()
	r.ServeHTTP(rec, httptest.NewRequest("GET", "/health/ready", nil))
	if rec.Code != http.StatusServiceUnavailable {
		t.Fatalf("ready: want 503, got %d", rec.Code)
	}
}
```

`internal/health/{service,types}.go` — unchanged.

### Step 4 — Rewrite `internal/recommendations/handler.go`

```go
package recommendations

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"

	"gj-ecom-gateway/internal/httpx"
)

const (
	defaultLimit = 10
	maxLimit     = 50
)

// Handler is the HTTP edge for the recommendations bounded context.
type Handler struct {
	service *Service
	errs    *httpx.Helper
}

// NewHandler constructs a Handler.
func NewHandler(service *Service, errs *httpx.Helper) *Handler {
	return &Handler{service: service, errs: errs}
}

// Similar handles GET /api/v1/recommendations/similar.
func (h *Handler) Similar(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	productID := strings.TrimSpace(q.Get("product_id"))
	if productID == "" {
		h.errs.BadRequest(w, "invalid_argument", "product_id is required")
		return
	}

	limit, err := parseLimit(q.Get("limit"))
	if err != nil {
		h.errs.BadRequest(w, "invalid_argument", err.Error())
		return
	}

	cards, err := h.service.Similar(r.Context(), ProductID(productID), SimilarOpts{Limit: limit})
	if err != nil {
		switch {
		case errors.Is(err, ErrInvalidArgument):
			h.errs.BadRequest(w, "invalid_argument", err.Error())
		case errors.Is(err, ErrSourceUnavailable):
			h.errs.JSON(w, http.StatusBadGateway, "source_unavailable", "recommendation source unavailable")
		default:
			h.errs.Internal(w, "internal", "internal error")
		}
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(toSimilarResponse(cards))
}

// parseLimit resolves the limit query param: empty → default; otherwise must be
// an integer within [1, maxLimit].
func parseLimit(raw string) (int, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return defaultLimit, nil
	}
	v, err := strconv.Atoi(raw)
	if err != nil {
		return 0, errors.New("limit must be an integer")
	}
	if v < 1 || v > maxLimit {
		return 0, errors.New("limit must be between 1 and 50")
	}
	return v, nil
}

// toSimilarResponse maps domain cards to the generated API DTO.
func toSimilarResponse(cards []ProductCard) SimilarResponse {
	items := make([]SimilarItem, 0, len(cards))
	for _, c := range cards {
		items = append(items, SimilarItem{
			Id:       string(c.ID),
			Name:     c.Name,
			Price:    c.Price,
			ImageUrl: c.ImageURL,
		})
	}
	return SimilarResponse{Items: items}
}
```

### Step 5 — Rewrite `internal/recommendations/routes.go`

```go
package recommendations

import "github.com/go-chi/chi/v5"

// Deps carries dependencies required to mount recommendation routes.
type Deps struct{ Handler *Handler }

// Mount registers the recommendations routes under the given router.
// Caller is expected to scope them under /api/v1 with r.Route(...) or similar.
func Mount(r chi.Router, deps Deps) {
	r.Route("/recommendations", func(rr chi.Router) {
		rr.Get("/similar", deps.Handler.Similar)
	})
}
```

### Step 6 — Rewrite `internal/recommendations/handler_test.go`

```go
package recommendations

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"gj-ecom-gateway/internal/httpx"

	"github.com/go-chi/chi/v5"
)

func newTestRouter() http.Handler {
	r := chi.NewRouter()
	svc := NewService(NewStubSource(), NewStubHydrator())
	h := NewHandler(svc, httpx.NewHelper())
	r.Route("/api/v1", func(rr chi.Router) {
		Mount(rr, Deps{Handler: h})
	})
	return r
}

func TestSimilarEndpoint_OK(t *testing.T) {
	router := newTestRouter()
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, httptest.NewRequest("GET", "/api/v1/recommendations/similar?product_id=119871&limit=2", nil))

	if rec.Code != http.StatusOK {
		t.Fatalf("status: want 200, got %d", rec.Code)
	}
	var out SimilarResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatalf("unmarshal into generated DTO: %v", err)
	}
	if len(out.Items) != 2 {
		t.Fatalf("items: want 2 (limit honored), got %d", len(out.Items))
	}
	if out.Items[0].Id != "101" {
		t.Fatalf("order: want first id 101, got %q", out.Items[0].Id)
	}
}

func TestSimilarEndpoint_MissingProductID(t *testing.T) {
	router := newTestRouter()
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, httptest.NewRequest("GET", "/api/v1/recommendations/similar", nil))

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status: want 400, got %d", rec.Code)
	}
	var env httpx.ErrorEnvelope
	_ = json.Unmarshal(rec.Body.Bytes(), &env)
	if env.Error != "invalid_argument" {
		t.Fatalf("error code: want invalid_argument, got %q", env.Error)
	}
}

func TestSimilarEndpoint_LimitOutOfRange(t *testing.T) {
	router := newTestRouter()
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, httptest.NewRequest("GET", "/api/v1/recommendations/similar?product_id=1&limit=999", nil))
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status: want 400, got %d", rec.Code)
	}
}
```

`internal/recommendations/{types,service,stub,doc,openapi.gen,boundary_test,service_test}.go` — unchanged. Verify `openapi.gen.go` is byte-identical to before with `git diff --exit-code`.

### Step 7 — Build + test domain + health

```bash
go build ./internal/health/ ./internal/recommendations/
go test ./internal/health/ ./internal/recommendations/
```

Note: still expect `go build ./...` to fail because `internal/http` and `internal/app` not yet migrated.

### Step 8 — Commit M3

```bash
git -C /Users/zak/Projects/GJ-Ecommerce/platform-new/ecom-gateway add internal/health/ internal/recommendations/
git -C /Users/zak/Projects/GJ-Ecommerce/platform-new/ecom-gateway commit -m "refactor(chi): migrate recommendations + health to net/http"
```

---

## Task M4 — Transport + wiring + go.mod

### Step 1 — Rewrite `internal/http/middleware.go`

```go
package http

import (
	"encoding/json"
	"net/http"
	"runtime/debug"
	"strings"
	"time"

	"gj-ecom-gateway/internal/reqctx"

	"github.com/google/uuid"
	gjlogger "gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger"
)

const requestIDHeader = "X-Request-ID"

// requestIDMiddleware ensures every request has a correlation ID, echoed back
// on the response and stored in reqctx for downstream logging.
func requestIDMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := strings.TrimSpace(r.Header.Get(requestIDHeader))
		if _, err := uuid.Parse(id); err != nil {
			id = uuid.NewString()
		}
		r = reqctx.SetRequestID(r, id)
		w.Header().Set(requestIDHeader, id)
		next.ServeHTTP(w, r)
	})
}

// statusRecorder captures the status code for the access log.
type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (sr *statusRecorder) WriteHeader(code int) {
	sr.status = code
	sr.ResponseWriter.WriteHeader(code)
}

// accessLogMiddleware logs one structured line per request after the chain runs.
func accessLogMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		sr := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		start := time.Now()
		next.ServeHTTP(sr, r)
		log := gjlogger.WithContext(map[string]interface{}{
			"method":      r.Method,
			"path":        r.URL.Path,
			"status":      sr.status,
			"duration_ms": time.Since(start).Milliseconds(),
			"request_id":  reqctx.RequestID(r),
			"ip":          clientIP(r),
		})
		log.Info().Msg("access_request")
	})
}

// recoveryMiddleware converts panics into a 500 envelope and logs diagnostics.
func recoveryMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rec := recover(); rec != nil {
				log := gjlogger.WithContext(map[string]interface{}{
					"request_id": reqctx.RequestID(r),
					"method":     r.Method,
					"path":       r.URL.Path,
					"error":      rec,
					"stack":      string(debug.Stack()),
				})
				log.Error().Msg("request_recover")
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusInternalServerError)
				_ = json.NewEncoder(w).Encode(map[string]string{
					"error":   "internal",
					"message": "internal server error",
				})
			}
		}()
		next.ServeHTTP(w, r)
	})
}

func clientIP(r *http.Request) string {
	// Honour X-Forwarded-For if set by a trusted upstream (k8s ingress); fall back to RemoteAddr.
	if xff := r.Header.Get("X-Forwarded-For"); xff != "" {
		if i := strings.IndexByte(xff, ','); i >= 0 {
			return strings.TrimSpace(xff[:i])
		}
		return strings.TrimSpace(xff)
	}
	if i := strings.LastIndexByte(r.RemoteAddr, ':'); i >= 0 {
		return r.RemoteAddr[:i]
	}
	return r.RemoteAddr
}
```

### Step 2 — Rewrite `internal/http/routes.go`

```go
package http

import (
	"gj-ecom-gateway/internal/health"
	"gj-ecom-gateway/internal/observability"
	"gj-ecom-gateway/internal/recommendations"

	"github.com/go-chi/chi/v5"
)

// Dependencies holds per-domain Deps consumed by registerRoutes.
type Dependencies struct {
	Health          health.Deps
	Observability   observability.Deps
	Recommendations recommendations.Deps
}

// registerRoutes mounts observability first (so /metrics is always reachable
// and the instrumentation middleware wraps everything after), then health, then
// the versioned API group.
func registerRoutes(r chi.Router, deps Dependencies) {
	observability.Mount(r, deps.Observability)
	health.Mount(r, deps.Health)

	r.Route("/api/v1", func(rr chi.Router) {
		recommendations.Mount(rr, deps.Recommendations)
	})
}
```

### Step 3 — Rewrite `internal/http/server.go`

```go
package http

import (
	"context"
	stdhttp "net/http"
	"time"

	"gj-ecom-gateway/internal/config"

	"github.com/go-chi/chi/v5"
	gjlogger "gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger"
)

// Server wraps the http.Server and its lifecycle.
type Server struct {
	srv    *stdhttp.Server
	config config.Config
}

// NewServer builds the chi router, installs base middleware, registers routes,
// and constructs an http.Server with conservative timeouts.
func NewServer(cfg config.Config, deps Dependencies) *Server {
	r := chi.NewRouter()
	// Base middleware: request-id → access log → recovery → routes.
	// Access log runs outside recovery so panic outcomes are still logged.
	r.Use(requestIDMiddleware)
	r.Use(accessLogMiddleware)
	r.Use(recoveryMiddleware)

	registerRoutes(r, deps)

	srv := &stdhttp.Server{
		Addr:              cfg.ListenAddr(),
		Handler:           r,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      15 * time.Second,
		IdleTimeout:       60 * time.Second,
	}
	return &Server{srv: srv, config: cfg}
}

// Run starts listening (blocking). Returns nil on graceful shutdown.
func (s *Server) Run() error {
	log := gjlogger.Logger()
	log.Info().Msgf("%s listening on %s", s.config.AppName, s.srv.Addr)
	if err := s.srv.ListenAndServe(); err != nil && err != stdhttp.ErrServerClosed {
		return err
	}
	return nil
}

// Shutdown gracefully stops the server.
func (s *Server) Shutdown(ctx context.Context) error {
	return s.srv.Shutdown(ctx)
}
```

### Step 4 — `internal/app/app.go`, `internal/app/container.go`, `internal/app/wire_recommendations.go`

`container.go` and `wire_recommendations.go` — **unchanged** (they don't import Fiber).

`app.go` — only the imports change (Fiber types no longer referenced). The structure stays the same: load config → setup logger → build container → build server → handle signals. The graceful-shutdown channel pattern is preserved verbatim.

Verify `app.go` compiles after M2/M3 are in. If any leftover Fiber import remains in app.go, remove it.

### Step 5 — `cmd/ecom-gateway/main.go`

Unchanged. It only imports `internal/app` and `gj-go-logger`.

### Step 6 — `go.mod` cleanup

```bash
go mod edit -droprequire github.com/gofiber/fiber/v2
go mod edit -droprequire github.com/gofiber/adaptor/v2
go get github.com/go-chi/chi/v5@v5.1.0
go mod tidy
```

If `go mod edit -droprequire` complains the require is missing (because tidy already removed it after deleting all imports), that's fine — proceed.

### Step 7 — Full build + vet + test

```bash
go build ./...
go vet ./...
go test ./... -count=1
```
All must pass.

### Step 8 — Smoke test

```bash
go run ./cmd/ecom-gateway & SERVER_PID=$!
sleep 2
curl -s -o /dev/null -w "live=%{http_code}\n"  localhost:8080/health/live
curl -s -o /dev/null -w "ready=%{http_code}\n" localhost:8080/health/ready
curl -s -o /dev/null -w "metrics=%{http_code}\n" localhost:8080/metrics
curl -s "localhost:8080/api/v1/recommendations/similar?product_id=119871&limit=2"
echo
curl -s -o /dev/null -w "no_pid=%{http_code}\n" "localhost:8080/api/v1/recommendations/similar"
kill $SERVER_PID
```
Expected (must match pre-migration behaviour): `live=200`, `ready=200`, `metrics=200`, similar returns 2 items (ids 101, 102), `no_pid=400`. The JSON body for similar must be **byte-identical** in shape to pre-migration (same field names: `id`, `name`, `price`, `image_url`, wrapped in `items`).

### Step 9 — Verify generated DTOs unchanged

```bash
git diff HEAD~10 -- internal/recommendations/openapi.gen.go | head
# Expected: empty output (file untouched)
```

### Step 10 — Commit M4

```bash
git -C /Users/zak/Projects/GJ-Ecommerce/platform-new/ecom-gateway add internal/http/ internal/app/ cmd/ go.mod go.sum
git -C /Users/zak/Projects/GJ-Ecommerce/platform-new/ecom-gateway commit -m "refactor(chi): migrate transport + wiring; drop Fiber from go.mod"
```

---

## Task M5 — Final verification + docs

### Step 1 — Re-run DoD

```bash
PATH="$(go env GOPATH)/bin:$PATH" make generate
git diff --exit-code internal/recommendations/openapi.gen.go && echo "GEN-CLEAN"
make lint
make build
go vet ./...
make test
```
All green.

### Step 2 — Update `Dockerfile` (no changes expected — verify)

The Dockerfile copies source and runs `go build`. Framework-agnostic. Confirm `make docker` still works.

### Step 3 — Update `CLAUDE.md` if any stale Fiber references remain

The file was already updated to mention `net/http`+chi in this PR. Grep:
```bash
grep -nE "fiber|Fiber" CLAUDE.md docs/ README.md
```
Anything remaining that refers to Fiber as the *current* framework (not history) — rephrase. Historical mentions (ADR-0002 context) stay.

### Step 4 — Commit doc fixes if any

```bash
git -C /Users/zak/Projects/GJ-Ecommerce/platform-new/ecom-gateway add -A
git -C /Users/zak/Projects/GJ-Ecommerce/platform-new/ecom-gateway commit -m "docs: scrub stale Fiber references post-migration"
```

### Step 5 — Final code-quality review

Dispatch a go-quality-analyzer subagent over the migration diff range (M2..M5 commits). Scope: correctness of net/http migration, idiomaticity, no leftover Fiber leakage, middleware ordering, graceful shutdown soundness, statusRecorder correctness.

Address findings inline; commit fixes if needed.

---

## Definition of Done

- `go build ./...`, `go vet ./...`, `go test ./...` green (same set of test packages PASS).
- `make lint` green; `openapi.gen.go` unchanged.
- Smoke test endpoints behave identically to pre-migration.
- `go.mod` no longer requires `github.com/gofiber/...`.
- No reference to `fiber.Ctx` or `gofiber/*` in non-historical source (ADRs / planning docs may reference Fiber as context).
- ADR-0002 committed; CLAUDE.md reflects chi.
