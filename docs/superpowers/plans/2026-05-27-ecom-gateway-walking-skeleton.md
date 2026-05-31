# ecom-gateway Walking Skeleton — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up `ecom-gateway` — a stateless Go/Fiber BFF — as a production-grade walking skeleton with all cross-cutting wiring and one end-to-end stub endpoint (`GET /api/v1/recommendations/similar`).

**Architecture:** Pure BFF, no business logic. One bounded context (`recommendations`) consuming two outbound ports (`RecommendationSource`, `ProductHydrator`) as interfaces, backed by deterministic stub adapters in v1. Cross-cutting layers (config, observability, httpx error envelope, health, request context, transport) are lifted from the proven `gj-buddy-server` pattern and trimmed to BFF needs. Spec-first OpenAPI via `oapi-codegen` in types-only mode (generate DTOs only; Fiber routes/handlers hand-written).

**Tech Stack:** Go 1.26.2 · Fiber v2 · oapi-codegen (types-only) · Prometheus (`client_golang`) · `gofiber/adaptor` · `gj-go-logger` (zerolog) · `google/uuid`. No DB, no auth, no external calls in v1.

**Spec:** `docs/superpowers/specs/2026-05-27-ecom-gateway-design.md`
**Precedent reference (read-only):** `~/Projects/Buddy/gj-buddy-server` + `~/Projects/Buddy/go-service-guideline.md`

**Module path:** `gj-ecom-gateway` · **Service dir:** `platform-new/ecom-gateway/`

> NOTE: `platform/non-platform/` clones are independent git repos. Run `git init` inside `ecom-gateway/` and commit there — do NOT commit the service into the workspace-root repo.

---

## File Structure

```
platform-new/ecom-gateway/
├── go.mod                                  # module gj-ecom-gateway, go 1.26.2, replace gj-go-logger → ../gj-go-logger
├── cmd/ecom-gateway/main.go                # ≤30 lines: app.New().Run()
├── api/v1/
│   ├── openapi.yaml                        # contract (source of truth)
│   └── oapi-codegen.yaml                   # types-only config
├── internal/
│   ├── config/config.go                    # env config (+ config_test.go)
│   ├── observability/
│   │   ├── metrics.go                      # 3 metrics in private registry
│   │   ├── middleware.go                   # per-request counter+histogram
│   │   ├── handler.go                      # /metrics via adaptor+promhttp
│   │   └── routes.go                       # Mount(): /metrics + middleware
│   ├── httpx/error.go                      # canonical {"error","message"} envelope (+ error_test.go)
│   ├── reqctx/reqctx.go                     # request-id set/get on fiber locals
│   ├── platform/logging.go                 # gj-go-logger Setup
│   ├── health/
│   │   ├── service.go, handler.go, routes.go, types.go   # /health/live, /health/ready
│   ├── recommendations/
│   │   ├── doc.go                          # //go:generate directive
│   │   ├── openapi.gen.go                  # GENERATED DTOs (do not edit)
│   │   ├── types.go                        # domain model + marker errors
│   │   ├── service.go                      # orchestration + consumed ports
│   │   ├── stub.go                         # v1 stub adapters
│   │   ├── handler.go                      # HTTP I/O + DTO mapping
│   │   ├── routes.go                       # Mount() ≤80 lines
│   │   ├── service_test.go
│   │   ├── handler_test.go
│   │   └── boundary_test.go
│   ├── http/
│   │   ├── server.go                       # fiber.App build + graceful shutdown
│   │   ├── middleware.go                   # request-id + recovery + access log
│   │   └── routes.go                       # registerRoutes (thin coordinator)
│   └── app/
│       ├── app.go                          # New()/Run(): config→logger→container→server→signals
│       ├── container.go                    # dependency assembly ≤200 lines
│       └── wire_recommendations.go         # wires recommendations bounded context
├── Dockerfile
├── Makefile                                # generate, lint, build, test, run
└── README.md
```

---

## Task 1: Module bootstrap + config

**Files:**
- Create: `platform-new/ecom-gateway/go.mod` (via commands)
- Create: `platform-new/ecom-gateway/internal/config/config.go`
- Test: `platform-new/ecom-gateway/internal/config/config_test.go`

- [ ] **Step 1: Initialize the module**

Run from repo root:
```bash
cd platform-new/ecom-gateway
git init
go mod init gj-ecom-gateway
go mod edit -go=1.26.2
go mod edit -require=gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger@v1.0.5
go mod edit -replace=gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger=../gj-go-logger
```

- [ ] **Step 2: Write the failing config test**

Create `internal/config/config_test.go`:
```go
package config

import "testing"

func TestLoadDefaults(t *testing.T) {
	t.Setenv("APP_NAME", "")
	t.Setenv("HTTP_PORT", "")
	cfg := Load()
	if cfg.AppName != "ecom-gateway" {
		t.Fatalf("AppName: want ecom-gateway, got %q", cfg.AppName)
	}
	if cfg.Env != "local" {
		t.Fatalf("Env: want local, got %q", cfg.Env)
	}
	if got := cfg.ListenAddr(); got != ":8080" {
		t.Fatalf("ListenAddr: want :8080, got %q", got)
	}
	if cfg.UpstreamTimeout.Milliseconds() != 800 {
		t.Fatalf("UpstreamTimeout: want 800ms, got %v", cfg.UpstreamTimeout)
	}
}

func TestLoadOverrides(t *testing.T) {
	t.Setenv("APP_NAME", "ecom-gateway-test")
	t.Setenv("APP_ENV", "staging")
	t.Setenv("HTTP_HOST", "127.0.0.1")
	t.Setenv("HTTP_PORT", "9090")
	t.Setenv("UPSTREAM_TIMEOUT_MS", "1500")
	cfg := Load()
	if cfg.AppName != "ecom-gateway-test" {
		t.Fatalf("AppName override failed: %q", cfg.AppName)
	}
	if cfg.ListenAddr() != "127.0.0.1:9090" {
		t.Fatalf("ListenAddr override failed: %q", cfg.ListenAddr())
	}
	if cfg.UpstreamTimeout.Milliseconds() != 1500 {
		t.Fatalf("UpstreamTimeout override failed: %v", cfg.UpstreamTimeout)
	}
}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `go test ./internal/config/`
Expected: FAIL — `undefined: Load` (config.go not written yet).

- [ ] **Step 4: Write the config implementation**

Create `internal/config/config.go`:
```go
package config

import (
	"net"
	"os"
	"strconv"
	"time"
)

// Config is the resolved runtime configuration for ecom-gateway.
type Config struct {
	AppName string
	Env     string
	HTTP    HTTPConfig
	// UpstreamTimeout bounds every outbound port call (rec-source, hydrator).
	UpstreamTimeout time.Duration
}

type HTTPConfig struct {
	Host string
	Port string
}

// Load reads configuration from the environment, applying defaults.
func Load() Config {
	return Config{
		AppName: getEnv("APP_NAME", "ecom-gateway"),
		Env:     getEnv("APP_ENV", "local"),
		HTTP: HTTPConfig{
			Host: getEnv("HTTP_HOST", ""),
			Port: getEnv("HTTP_PORT", "8080"),
		},
		UpstreamTimeout: time.Duration(clampInt(getEnvInt("UPSTREAM_TIMEOUT_MS", 800), 50, 10000)) * time.Millisecond,
	}
}

// ListenAddr returns the host:port the HTTP server should bind.
func (c Config) ListenAddr() string {
	if c.HTTP.Host == "" {
		return ":" + c.HTTP.Port
	}
	return net.JoinHostPort(c.HTTP.Host, c.HTTP.Port)
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getEnvInt(key string, fallback int) int {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(v)
	if err != nil {
		return fallback
	}
	return parsed
}

func clampInt(v, min, max int) int {
	if v < min {
		return min
	}
	if v > max {
		return max
	}
	return v
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `go test ./internal/config/`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add go.mod internal/config/
git commit -m "feat: module bootstrap + env config"
```

---

## Task 2: Observability (Prometheus)

**Files:**
- Create: `internal/observability/metrics.go`
- Create: `internal/observability/middleware.go`
- Create: `internal/observability/handler.go`
- Create: `internal/observability/routes.go`
- Test: `internal/observability/metrics_test.go`

- [ ] **Step 1: Add dependencies**

```bash
go get github.com/gofiber/fiber/v2@v2.52.12
go get github.com/gofiber/adaptor/v2@v2.2.1
go get github.com/prometheus/client_golang@v1.23.2
```

- [ ] **Step 2: Write the failing metrics test**

Create `internal/observability/metrics_test.go`:
```go
package observability

import "testing"

func TestNewMetricsRegistersAll(t *testing.T) {
	m := NewMetrics()
	if m == nil || m.Registry() == nil {
		t.Fatal("expected non-nil Metrics and Registry")
	}
	// Exercising the vectors must not panic (confirms registration succeeded).
	m.HTTPRequestsTotal.WithLabelValues("GET", "/x", "200").Inc()
	m.HTTPRequestDuration.WithLabelValues("GET", "/x").Observe(0.1)

	got, err := m.Registry().Gather()
	if err != nil {
		t.Fatalf("gather: %v", err)
	}
	if len(got) == 0 {
		t.Fatal("expected at least one metric family registered")
	}
}

func TestNewMetricsIsolatedRegistries(t *testing.T) {
	// Two independent instances must not collide (private registry per instance).
	_ = NewMetrics()
	_ = NewMetrics()
}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `go test ./internal/observability/`
Expected: FAIL — `undefined: NewMetrics`.

- [ ] **Step 4: Write metrics.go**

Create `internal/observability/metrics.go`:
```go
package observability

import "github.com/prometheus/client_golang/prometheus"

// Metrics holds instrumentation in a private registry so multiple instances
// (e.g. in tests) never collide on metric names. The three mandatory metrics
// (guideline §7.2): requests counter, latency histogram, in-flight gauge.
type Metrics struct {
	HTTPRequestsTotal    *prometheus.CounterVec
	HTTPRequestDuration  *prometheus.HistogramVec
	HTTPRequestsInFlight prometheus.Gauge
	registry             *prometheus.Registry
}

var durationBuckets = []float64{0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10}

// NewMetrics constructs and registers all metrics in a fresh private registry.
func NewMetrics() *Metrics {
	reg := prometheus.NewRegistry()

	requestsTotal := prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "ecom_gateway_http_requests_total",
			Help: "Total HTTP requests processed, partitioned by method, route, and status.",
		},
		[]string{"method", "route", "status"},
	)
	requestDuration := prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "ecom_gateway_http_request_duration_seconds",
			Help:    "HTTP request latency in seconds, partitioned by method and route.",
			Buckets: durationBuckets,
		},
		[]string{"method", "route"},
	)
	requestsInFlight := prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "ecom_gateway_http_requests_in_flight",
			Help: "Number of HTTP requests currently being served.",
		},
	)

	reg.MustRegister(requestsTotal, requestDuration, requestsInFlight)

	return &Metrics{
		HTTPRequestsTotal:    requestsTotal,
		HTTPRequestDuration:  requestDuration,
		HTTPRequestsInFlight: requestsInFlight,
		registry:             reg,
	}
}

// Registry returns the private Prometheus registry.
func (m *Metrics) Registry() *prometheus.Registry { return m.registry }
```

- [ ] **Step 5: Write middleware.go**

Create `internal/observability/middleware.go`:
```go
package observability

import (
	"strconv"
	"time"

	"github.com/gofiber/fiber/v2"
)

// FiberMiddleware records per-request HTTP metrics.
type FiberMiddleware struct{ m *Metrics }

// NewFiberMiddleware creates a FiberMiddleware backed by the given Metrics.
func NewFiberMiddleware(m *Metrics) *FiberMiddleware { return &FiberMiddleware{m: m} }

// Handle wraps ctx.Next() and records request count + latency after the chain
// completes. It uses the route pattern (not the raw URL) to bound cardinality.
// Nil Metrics is a no-op pass-through.
func (mw *FiberMiddleware) Handle(ctx *fiber.Ctx) error {
	if mw.m == nil {
		return ctx.Next()
	}
	mw.m.HTTPRequestsInFlight.Inc()
	defer mw.m.HTTPRequestsInFlight.Dec()

	start := time.Now()
	err := ctx.Next()
	duration := time.Since(start).Seconds()

	method := ctx.Method()
	route := ctx.Route().Path
	status := strconv.Itoa(ctx.Response().StatusCode())

	mw.m.HTTPRequestsTotal.WithLabelValues(method, route, status).Inc()
	mw.m.HTTPRequestDuration.WithLabelValues(method, route).Observe(duration)
	return err
}
```

- [ ] **Step 6: Write handler.go**

Create `internal/observability/handler.go`:
```go
package observability

import (
	"github.com/gofiber/adaptor/v2"
	"github.com/gofiber/fiber/v2"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// Handler serves the Prometheus scrape endpoint.
type Handler struct{ m *Metrics }

// NewHandler creates a Handler backed by the given Metrics.
func NewHandler(m *Metrics) *Handler { return &Handler{m: m} }

// ServeHTTP bridges promhttp (net/http) into Fiber via gofiber/adaptor.
// Nil Metrics returns 503.
func (h *Handler) ServeHTTP(ctx *fiber.Ctx) error {
	if h.m == nil {
		return ctx.SendStatus(fiber.StatusServiceUnavailable)
	}
	httpHandler := promhttp.HandlerFor(h.m.Registry(), promhttp.HandlerOpts{})
	return adaptor.HTTPHandler(httpHandler)(ctx)
}
```

- [ ] **Step 7: Write routes.go**

Create `internal/observability/routes.go`:
```go
package observability

import "github.com/gofiber/fiber/v2"

// Deps carries dependencies required to mount observability routes.
type Deps struct{ Metrics *Metrics }

// Mount registers /metrics first (always reachable), then applies the
// instrumentation middleware so every subsequent handler is measured.
func Mount(router fiber.Router, deps Deps) {
	h := NewHandler(deps.Metrics)
	router.Get("/metrics", h.ServeHTTP)
	router.Use(NewFiberMiddleware(deps.Metrics).Handle)
}
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `go test ./internal/observability/`
Expected: PASS (2 tests).

- [ ] **Step 9: Commit**

```bash
git add internal/observability/ go.mod go.sum
git commit -m "feat: prometheus observability (metrics, middleware, /metrics)"
```

---

## Task 3: httpx error envelope

**Files:**
- Create: `internal/httpx/error.go`
- Test: `internal/httpx/error_test.go`

- [ ] **Step 1: Write the failing test**

Create `internal/httpx/error_test.go`:
```go
package httpx

import (
	"encoding/json"
	"io"
	"net/http/httptest"
	"testing"

	"github.com/gofiber/fiber/v2"
)

func TestBadRequestWritesEnvelope(t *testing.T) {
	app := fiber.New()
	h := NewHelper()
	app.Get("/x", func(c *fiber.Ctx) error {
		return h.BadRequest(c, "invalid_argument", "product_id is required")
	})

	resp, err := app.Test(httptest.NewRequest("GET", "/x", nil))
	if err != nil {
		t.Fatalf("request: %v", err)
	}
	if resp.StatusCode != fiber.StatusBadRequest {
		t.Fatalf("status: want 400, got %d", resp.StatusCode)
	}
	body, _ := io.ReadAll(resp.Body)
	var env ErrorEnvelope
	if err := json.Unmarshal(body, &env); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if env.Error != "invalid_argument" || env.Message != "product_id is required" {
		t.Fatalf("unexpected envelope: %+v", env)
	}
}

func TestJSONStatusPassthrough(t *testing.T) {
	app := fiber.New()
	h := NewHelper()
	app.Get("/x", func(c *fiber.Ctx) error {
		return h.JSON(c, fiber.StatusBadGateway, "source_unavailable", "upstream down")
	})
	resp, _ := app.Test(httptest.NewRequest("GET", "/x", nil))
	if resp.StatusCode != fiber.StatusBadGateway {
		t.Fatalf("status: want 502, got %d", resp.StatusCode)
	}
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `go test ./internal/httpx/`
Expected: FAIL — `undefined: NewHelper`.

- [ ] **Step 3: Write error.go**

Create `internal/httpx/error.go`:
```go
package httpx

import "github.com/gofiber/fiber/v2"

// ErrorEnvelope is the canonical JSON error shape for all REST endpoints.
type ErrorEnvelope struct {
	Error   string `json:"error"`
	Message string `json:"message"`
}

// Helper writes canonical error envelopes. Construct one and inject it into
// each handler. It holds no state today but is a struct so future cross-cutting
// concerns (e.g. error metrics) attach without changing call sites.
type Helper struct{}

// NewHelper constructs a Helper.
func NewHelper() *Helper { return &Helper{} }

// JSON sends a canonical error envelope with the given status.
func (h *Helper) JSON(c *fiber.Ctx, status int, code, msg string) error {
	return c.Status(status).JSON(ErrorEnvelope{Error: code, Message: msg})
}

// BadRequest sends a 400 response.
func (h *Helper) BadRequest(c *fiber.Ctx, code, msg string) error {
	return h.JSON(c, fiber.StatusBadRequest, code, msg)
}

// Internal sends a 500 response.
func (h *Helper) Internal(c *fiber.Ctx, code, msg string) error {
	return h.JSON(c, fiber.StatusInternalServerError, code, msg)
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `go test ./internal/httpx/`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add internal/httpx/
git commit -m "feat: canonical httpx error envelope"
```

---

## Task 4: Health endpoints

**Files:**
- Create: `internal/health/types.go`
- Create: `internal/health/service.go`
- Create: `internal/health/handler.go`
- Create: `internal/health/routes.go`
- Test: `internal/health/health_test.go`

- [ ] **Step 1: Write the failing test**

Create `internal/health/health_test.go`:
```go
package health

import (
	"errors"
	"net/http/httptest"
	"testing"

	"github.com/gofiber/fiber/v2"
)

func mount(t *testing.T, ready func() error) *fiber.App {
	t.Helper()
	app := fiber.New()
	svc := NewService("ecom-gateway", "test", ready)
	Mount(app, Deps{Handler: NewHandler(svc)})
	return app
}

func TestLiveOK(t *testing.T) {
	app := mount(t, nil)
	resp, _ := app.Test(httptest.NewRequest("GET", "/health/live", nil))
	if resp.StatusCode != fiber.StatusOK {
		t.Fatalf("live: want 200, got %d", resp.StatusCode)
	}
}

func TestReadyOKWhenNoChecks(t *testing.T) {
	app := mount(t, nil)
	resp, _ := app.Test(httptest.NewRequest("GET", "/health/ready", nil))
	if resp.StatusCode != fiber.StatusOK {
		t.Fatalf("ready: want 200, got %d", resp.StatusCode)
	}
}

func TestReadyUnavailableWhenCheckFails(t *testing.T) {
	app := mount(t, func() error { return errors.New("down") })
	resp, _ := app.Test(httptest.NewRequest("GET", "/health/ready", nil))
	if resp.StatusCode != fiber.StatusServiceUnavailable {
		t.Fatalf("ready: want 503, got %d", resp.StatusCode)
	}
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `go test ./internal/health/`
Expected: FAIL — `undefined: NewService`.

- [ ] **Step 3: Write types.go**

Create `internal/health/types.go`:
```go
package health

// StatusResponse is the JSON body for health endpoints.
type StatusResponse struct {
	Status  string `json:"status"`
	Service string `json:"service"`
	Env     string `json:"env"`
}
```

- [ ] **Step 4: Write service.go**

Create `internal/health/service.go`:
```go
package health

// Service answers liveness and readiness queries. readyChecks are optional
// functions probed on /health/ready; v1 passes none (stateless BFF).
type Service struct {
	appName string
	env     string
	ready   func() error
}

// NewService builds a Service. The first readyCheck (if any) gates readiness.
func NewService(appName, env string, readyChecks ...func() error) *Service {
	var rc func() error
	if len(readyChecks) > 0 {
		rc = readyChecks[0]
	}
	return &Service{appName: appName, env: env, ready: rc}
}

// Live reports process liveness.
func (s *Service) Live() StatusResponse {
	return StatusResponse{Status: "ok", Service: s.appName, Env: s.env}
}

// Ready reports readiness, running the optional check.
func (s *Service) Ready() StatusResponse {
	if s.ready != nil {
		if err := s.ready(); err != nil {
			return StatusResponse{Status: "not_ready", Service: s.appName, Env: s.env}
		}
	}
	return StatusResponse{Status: "ready", Service: s.appName, Env: s.env}
}
```

- [ ] **Step 5: Write handler.go**

Create `internal/health/handler.go`:
```go
package health

import "github.com/gofiber/fiber/v2"

// Handler exposes health endpoints over Fiber.
type Handler struct{ service *Service }

// NewHandler constructs a Handler.
func NewHandler(service *Service) *Handler { return &Handler{service: service} }

// Live handles GET /health/live.
func (h *Handler) Live(ctx *fiber.Ctx) error {
	return ctx.Status(fiber.StatusOK).JSON(h.service.Live())
}

// Ready handles GET /health/ready.
func (h *Handler) Ready(ctx *fiber.Ctx) error {
	resp := h.service.Ready()
	if resp.Status == "ready" {
		return ctx.Status(fiber.StatusOK).JSON(resp)
	}
	return ctx.Status(fiber.StatusServiceUnavailable).JSON(resp)
}
```

- [ ] **Step 6: Write routes.go**

Create `internal/health/routes.go`:
```go
package health

import "github.com/gofiber/fiber/v2"

// Deps carries dependencies required to mount health routes.
type Deps struct{ Handler *Handler }

// Mount registers the health routes.
func Mount(router fiber.Router, deps Deps) {
	router.Get("/health/live", deps.Handler.Live)
	router.Get("/health/ready", deps.Handler.Ready)
}
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `go test ./internal/health/`
Expected: PASS (3 tests).

- [ ] **Step 8: Commit**

```bash
git add internal/health/
git commit -m "feat: health live/ready endpoints"
```

---

## Task 5: Request context + logger setup

**Files:**
- Create: `internal/reqctx/reqctx.go`
- Create: `internal/platform/logging.go`
- Test: `internal/reqctx/reqctx_test.go`

- [ ] **Step 1: Add the uuid dependency**

```bash
go get github.com/google/uuid@v1.6.0
```

- [ ] **Step 2: Write the failing reqctx test**

Create `internal/reqctx/reqctx_test.go`:
```go
package reqctx

import (
	"testing"

	"github.com/gofiber/fiber/v2"
)

func TestSetAndGetRequestID(t *testing.T) {
	app := fiber.New()
	var got string
	app.Get("/x", func(c *fiber.Ctx) error {
		SetRequestID(c, "abc-123")
		got = RequestID(c)
		return c.SendStatus(200)
	})
	if _, err := app.Test(testRequest("/x")); err != nil {
		t.Fatalf("request: %v", err)
	}
	if got != "abc-123" {
		t.Fatalf("RequestID: want abc-123, got %q", got)
	}
}

func TestRequestIDEmptyWhenUnset(t *testing.T) {
	app := fiber.New()
	var got = "sentinel"
	app.Get("/x", func(c *fiber.Ctx) error {
		got = RequestID(c)
		return c.SendStatus(200)
	})
	_, _ = app.Test(testRequest("/x"))
	if got != "" {
		t.Fatalf("RequestID: want empty, got %q", got)
	}
}
```

Create `internal/reqctx/helpers_test.go`:
```go
package reqctx

import "net/http"
import "net/http/httptest"

func testRequest(path string) *http.Request {
	return httptest.NewRequest("GET", path, nil)
}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `go test ./internal/reqctx/`
Expected: FAIL — `undefined: SetRequestID`.

- [ ] **Step 4: Write reqctx.go**

Create `internal/reqctx/reqctx.go`:
```go
// Package reqctx is the dedicated place for per-request data carried via the
// Fiber context (guideline §6.2). Today it holds only the request ID; user
// identity will be added here when the personal-recommendations contour lands.
package reqctx

import "github.com/gofiber/fiber/v2"

const requestIDKey = "request_id"

// SetRequestID stores the request ID on the Fiber context locals.
func SetRequestID(c *fiber.Ctx, id string) {
	c.Locals(requestIDKey, id)
}

// RequestID returns the request ID, or "" if none was set.
func RequestID(c *fiber.Ctx) string {
	if v, ok := c.Locals(requestIDKey).(string); ok {
		return v
	}
	return ""
}
```

- [ ] **Step 5: Write platform/logging.go**

Create `internal/platform/logging.go`:
```go
// Package platform reserves the place for infrastructure adapters (logging,
// and later: HTTP clients to rec-service and ENSI).
package platform

import (
	"gj-ecom-gateway/internal/config"

	gjlogger "gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger"
)

// SetupLogger initialises the global gj-go-logger with service-wide fields.
func SetupLogger(cfg config.Config) error {
	_, err := gjlogger.Setup(gjlogger.Options{
		ServiceName: cfg.AppName,
		DefaultFields: map[string]interface{}{
			"app": cfg.AppName,
			"env": cfg.Env,
		},
	})
	return err
}
```

- [ ] **Step 6: Run the test + tidy**

Run: `go mod tidy && go test ./internal/reqctx/`
Expected: PASS (2 tests). `go mod tidy` resolves `gj-go-logger` via the local replace.

- [ ] **Step 7: Commit**

```bash
git add internal/reqctx/ internal/platform/ go.mod go.sum
git commit -m "feat: request-context package + gj-go-logger setup"
```

---

## Task 6: recommendations — OpenAPI contract, codegen, domain, service

**Files:**
- Create: `api/v1/openapi.yaml`
- Create: `api/v1/oapi-codegen.yaml`
- Create: `internal/recommendations/doc.go`
- Generated: `internal/recommendations/openapi.gen.go`
- Create: `internal/recommendations/types.go`
- Create: `internal/recommendations/service.go`
- Create: `internal/recommendations/stub.go`
- Test: `internal/recommendations/service_test.go`

- [ ] **Step 1: Write the OpenAPI contract**

Create `api/v1/openapi.yaml`:
```yaml
openapi: 3.0.3
info:
  title: ecom-gateway API
  description: BFF for personalization / similar products.
  version: 1.0.0
servers:
  - url: /api/v1
tags:
  - name: recommendations
    description: Product recommendation surfaces.
paths:
  /recommendations/similar:
    get:
      tags: [recommendations]
      summary: Similar products for a given product.
      operationId: getSimilar
      parameters:
        - name: product_id
          in: query
          required: true
          schema: { type: string, minLength: 1 }
        - name: limit
          in: query
          required: false
          schema: { type: integer, default: 10, minimum: 1, maximum: 50 }
      responses:
        "200":
          description: Recommended products (possibly empty).
          content:
            application/json:
              schema: { $ref: "#/components/schemas/SimilarResponse" }
        "400":
          description: Invalid request.
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ErrorResponse" }
components:
  schemas:
    SimilarItem:
      type: object
      required: [id, name, price, image_url]
      properties:
        id: { type: string }
        name: { type: string }
        price: { type: integer, format: int64, description: "Price in minor units (kopecks)." }
        image_url: { type: string }
    SimilarResponse:
      type: object
      required: [items]
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/SimilarItem" }
    ErrorResponse:
      type: object
      required: [error, message]
      properties:
        error: { type: string }
        message: { type: string }
```

- [ ] **Step 2: Write the codegen config**

Create `api/v1/oapi-codegen.yaml`:
```yaml
# Generates Go types only (types-only mode). Routing and handler shapes stay in
# Fiber; generated types are imported for request/response serialisation.
package: recommendations
generate:
  models: true
output: ../../internal/recommendations/openapi.gen.go
output-options:
  skip-prune: false
```

- [ ] **Step 3: Write the go:generate directive**

Create `internal/recommendations/doc.go`:
```go
// Package recommendations is the BFF bounded context for product
// recommendations. It orchestrates outbound ports (RecommendationSource,
// ProductHydrator) and maps domain results to generated API DTOs.
package recommendations

//go:generate oapi-codegen --config ../../api/v1/oapi-codegen.yaml ../../api/v1/openapi.yaml
```

- [ ] **Step 4: Install oapi-codegen and generate the DTOs**

```bash
go install github.com/oapi-codegen/oapi-codegen/v2/cmd/oapi-codegen@v2.4.1
go get github.com/oapi-codegen/runtime@v1.4.0
PATH="$(go env GOPATH)/bin:$PATH" go generate ./internal/recommendations/...
```
Expected: creates `internal/recommendations/openapi.gen.go` defining `SimilarItem`, `SimilarResponse`, `ErrorResponse` with fields `Id`, `Name`, `Price int64`, `ImageUrl string`, `Items []SimilarItem`, `Error`, `Message`.

- [ ] **Step 5: Write the failing service test**

Create `internal/recommendations/service_test.go`:
```go
package recommendations

import (
	"context"
	"errors"
	"testing"
)

type fakeSource struct {
	ids []ProductID
	err error
}

func (f fakeSource) Similar(_ context.Context, _ ProductID, _ SimilarOpts) ([]ProductID, error) {
	return f.ids, f.err
}

type fakeHydrator struct {
	err error
}

func (f fakeHydrator) Hydrate(_ context.Context, ids []ProductID) ([]ProductCard, error) {
	if f.err != nil {
		return nil, f.err
	}
	cards := make([]ProductCard, 0, len(ids))
	for _, id := range ids {
		cards = append(cards, ProductCard{ID: id, Name: "p", Price: 1, ImageURL: "u"})
	}
	return cards, nil
}

func TestSimilar(t *testing.T) {
	tests := []struct {
		name      string
		productID ProductID
		limit     int
		source    fakeSource
		hydrator  fakeHydrator
		wantCount int
		wantErr   error
	}{
		{
			name:      "happy path returns hydrated cards",
			productID: "119871",
			limit:     10,
			source:    fakeSource{ids: []ProductID{"1", "2", "3"}},
			wantCount: 3,
		},
		{
			name:      "limit trims results",
			productID: "119871",
			limit:     2,
			source:    fakeSource{ids: []ProductID{"1", "2", "3"}},
			wantCount: 2,
		},
		{
			name:      "empty source yields empty slice, no error",
			productID: "119871",
			limit:     10,
			source:    fakeSource{ids: nil},
			wantCount: 0,
		},
		{
			name:      "missing product id is invalid argument",
			productID: "",
			limit:     10,
			wantErr:   ErrInvalidArgument,
		},
		{
			name:      "source failure surfaces as source unavailable",
			productID: "119871",
			limit:     10,
			source:    fakeSource{err: errors.New("boom")},
			wantErr:   ErrSourceUnavailable,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			svc := NewService(tt.source, tt.hydrator)
			cards, err := svc.Similar(context.Background(), tt.productID, SimilarOpts{Limit: tt.limit})
			if tt.wantErr != nil {
				if !errors.Is(err, tt.wantErr) {
					t.Fatalf("err: want %v, got %v", tt.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected err: %v", err)
			}
			if len(cards) != tt.wantCount {
				t.Fatalf("count: want %d, got %d", tt.wantCount, len(cards))
			}
		})
	}
}
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `go test ./internal/recommendations/`
Expected: FAIL — `undefined: NewService`, `undefined: ProductID`, etc.

- [ ] **Step 7: Write types.go**

Create `internal/recommendations/types.go`:
```go
package recommendations

import "errors"

// ProductID identifies a product in the catalog.
type ProductID string

// ProductCard is the domain representation of a hydrated product, independent
// of the generated API DTOs. The handler maps this to SimilarItem.
type ProductCard struct {
	ID       ProductID
	Name     string
	Price    int64 // minor units (kopecks)
	ImageURL string
}

// SimilarOpts carries query options for a similar-products request.
type SimilarOpts struct {
	Limit int
}

// Marker errors classify failures for the HTTP layer (wrapped with %w).
var (
	ErrInvalidArgument   = errors.New("invalid argument")
	ErrSourceUnavailable = errors.New("recommendation source unavailable")
)
```

- [ ] **Step 8: Write service.go**

Create `internal/recommendations/service.go`:
```go
package recommendations

import (
	"context"
	"fmt"
)

// RecommendationSource returns ranked candidate product IDs. The concrete
// implementation will be an HTTP client to the recommendation service; v1 uses
// a deterministic stub. (Interface defined by the consumer — guideline §3.1.)
type RecommendationSource interface {
	Similar(ctx context.Context, productID ProductID, opts SimilarOpts) ([]ProductID, error)
}

// ProductHydrator turns product IDs into full cards. The concrete implementation
// will call ENSI (catalog-cache/offers); v1 uses a stub.
type ProductHydrator interface {
	Hydrate(ctx context.Context, ids []ProductID) ([]ProductCard, error)
}

// Service orchestrates a similar-products lookup: source → trim → hydrate.
type Service struct {
	source   RecommendationSource
	hydrator ProductHydrator
}

// NewService builds a Service from its ports.
func NewService(source RecommendationSource, hydrator ProductHydrator) *Service {
	return &Service{source: source, hydrator: hydrator}
}

// Similar returns hydrated product cards similar to productID, honoring limit.
func (s *Service) Similar(ctx context.Context, productID ProductID, opts SimilarOpts) ([]ProductCard, error) {
	if productID == "" {
		return nil, fmt.Errorf("%w: product_id is required", ErrInvalidArgument)
	}

	ids, err := s.source.Similar(ctx, productID, opts)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrSourceUnavailable, err)
	}
	if opts.Limit > 0 && len(ids) > opts.Limit {
		ids = ids[:opts.Limit]
	}
	if len(ids) == 0 {
		return []ProductCard{}, nil
	}

	cards, err := s.hydrator.Hydrate(ctx, ids)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrSourceUnavailable, err)
	}
	return cards, nil
}
```

- [ ] **Step 9: Write stub.go (v1 adapters)**

Create `internal/recommendations/stub.go`:
```go
package recommendations

import (
	"context"
	"fmt"
)

// stubSource returns a fixed, deterministic candidate list. Replaced by the
// real recommendation-service HTTP client in a later cycle.
type stubSource struct{}

// NewStubSource constructs the v1 stub RecommendationSource.
func NewStubSource() RecommendationSource { return stubSource{} }

func (stubSource) Similar(_ context.Context, _ ProductID, _ SimilarOpts) ([]ProductID, error) {
	return []ProductID{"101", "102", "103"}, nil
}

// stubHydrator fabricates deterministic cards. Replaced by ENSI clients later.
type stubHydrator struct{}

// NewStubHydrator constructs the v1 stub ProductHydrator.
func NewStubHydrator() ProductHydrator { return stubHydrator{} }

func (stubHydrator) Hydrate(_ context.Context, ids []ProductID) ([]ProductCard, error) {
	cards := make([]ProductCard, 0, len(ids))
	for i, id := range ids {
		cards = append(cards, ProductCard{
			ID:       id,
			Name:     fmt.Sprintf("Stub product %s", id),
			Price:    int64(100000 * (i + 1)),
			ImageURL: fmt.Sprintf("https://stub.local/products/%s.jpg", id),
		})
	}
	return cards, nil
}
```

- [ ] **Step 10: Run the test to verify it passes**

Run: `go test ./internal/recommendations/`
Expected: PASS (1 test, 5 subtests).

- [ ] **Step 11: Commit**

```bash
git add api/ internal/recommendations/ go.mod go.sum
git commit -m "feat: recommendations contract, codegen, domain service + stubs"
```

---

## Task 7: recommendations — handler, routes, DTO mapping

**Files:**
- Create: `internal/recommendations/handler.go`
- Create: `internal/recommendations/routes.go`
- Test: `internal/recommendations/handler_test.go`

- [ ] **Step 1: Write the failing handler test**

Create `internal/recommendations/handler_test.go`:
```go
package recommendations

import (
	"encoding/json"
	"io"
	"net/http/httptest"
	"testing"

	"gj-ecom-gateway/internal/httpx"

	"github.com/gofiber/fiber/v2"
)

func newTestApp() *fiber.App {
	app := fiber.New()
	svc := NewService(NewStubSource(), NewStubHydrator())
	h := NewHandler(svc, httpx.NewHelper())
	Mount(app.Group("/api/v1"), Deps{Handler: h})
	return app
}

func TestSimilarEndpoint_OK(t *testing.T) {
	app := newTestApp()
	resp, err := app.Test(httptest.NewRequest("GET", "/api/v1/recommendations/similar?product_id=119871&limit=2", nil))
	if err != nil {
		t.Fatalf("request: %v", err)
	}
	if resp.StatusCode != fiber.StatusOK {
		t.Fatalf("status: want 200, got %d", resp.StatusCode)
	}
	body, _ := io.ReadAll(resp.Body)
	var out SimilarResponse
	if err := json.Unmarshal(body, &out); err != nil {
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
	app := newTestApp()
	resp, _ := app.Test(httptest.NewRequest("GET", "/api/v1/recommendations/similar", nil))
	if resp.StatusCode != fiber.StatusBadRequest {
		t.Fatalf("status: want 400, got %d", resp.StatusCode)
	}
	body, _ := io.ReadAll(resp.Body)
	var env httpx.ErrorEnvelope
	_ = json.Unmarshal(body, &env)
	if env.Error != "invalid_argument" {
		t.Fatalf("error code: want invalid_argument, got %q", env.Error)
	}
}

func TestSimilarEndpoint_LimitOutOfRange(t *testing.T) {
	app := newTestApp()
	resp, _ := app.Test(httptest.NewRequest("GET", "/api/v1/recommendations/similar?product_id=1&limit=999", nil))
	if resp.StatusCode != fiber.StatusBadRequest {
		t.Fatalf("status: want 400, got %d", resp.StatusCode)
	}
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `go test ./internal/recommendations/ -run TestSimilarEndpoint`
Expected: FAIL — `undefined: NewHandler`, `undefined: Mount`.

- [ ] **Step 3: Write handler.go**

Create `internal/recommendations/handler.go`:
```go
package recommendations

import (
	"errors"
	"strconv"
	"strings"

	"gj-ecom-gateway/internal/httpx"

	"github.com/gofiber/fiber/v2"
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
func (h *Handler) Similar(c *fiber.Ctx) error {
	productID := strings.TrimSpace(c.Query("product_id"))
	if productID == "" {
		return h.errs.BadRequest(c, "invalid_argument", "product_id is required")
	}

	limit, err := parseLimit(c.Query("limit"))
	if err != nil {
		return h.errs.BadRequest(c, "invalid_argument", err.Error())
	}

	cards, err := h.service.Similar(c.UserContext(), ProductID(productID), SimilarOpts{Limit: limit})
	if err != nil {
		switch {
		case errors.Is(err, ErrInvalidArgument):
			return h.errs.BadRequest(c, "invalid_argument", err.Error())
		case errors.Is(err, ErrSourceUnavailable):
			return h.errs.JSON(c, fiber.StatusBadGateway, "source_unavailable", "recommendation source unavailable")
		default:
			return h.errs.Internal(c, "internal", "internal error")
		}
	}

	return c.Status(fiber.StatusOK).JSON(toSimilarResponse(cards))
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

> If `go generate` produced different field names (e.g. `ImageUrl` vs `ImageURL`), align `toSimilarResponse` to the actual generated identifiers in `openapi.gen.go`. The mapping function is the ONLY place that touches generated field names.

- [ ] **Step 4: Write routes.go**

Create `internal/recommendations/routes.go`:
```go
package recommendations

import "github.com/gofiber/fiber/v2"

// Deps carries dependencies required to mount recommendation routes.
type Deps struct{ Handler *Handler }

// Mount registers the recommendations routes under the given router group.
func Mount(router fiber.Router, deps Deps) {
	g := router.Group("/recommendations")
	g.Get("/similar", deps.Handler.Similar)
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `go test ./internal/recommendations/`
Expected: PASS (all service + handler tests).

- [ ] **Step 6: Commit**

```bash
git add internal/recommendations/handler.go internal/recommendations/routes.go internal/recommendations/handler_test.go
git commit -m "feat: recommendations handler + routes + DTO mapping"
```

---

## Task 8: recommendations — boundary test

**Files:**
- Test: `internal/recommendations/boundary_test.go`

- [ ] **Step 1: Write the boundary test**

Create `internal/recommendations/boundary_test.go`:
```go
package recommendations

import (
	"go/parser"
	"go/token"
	"os"
	"strings"
	"testing"
)

// TestBoundary_NoUpwardOrCrossDomainImports enforces guideline §1.2/§3.1:
// the recommendations bounded context must not import the assembly/transport
// layers or any other bounded context. It may import shared utilities (httpx).
func TestBoundary_NoUpwardOrCrossDomainImports(t *testing.T) {
	forbiddenPrefixes := []string{
		"gj-ecom-gateway/internal/app",
		"gj-ecom-gateway/internal/http",
		"gj-ecom-gateway/internal/health",
		"gj-ecom-gateway/internal/observability",
	}

	fset := token.NewFileSet()
	pkgs, err := parser.ParseDir(fset, ".", func(fi os.FileInfo) bool {
		return !strings.HasSuffix(fi.Name(), "_test.go")
	}, parser.ImportsOnly)
	if err != nil {
		t.Fatalf("parse dir: %v", err)
	}

	for _, pkg := range pkgs {
		for fileName, file := range pkg.Files {
			for _, imp := range file.Imports {
				path := strings.Trim(imp.Path.Value, `"`)
				for _, bad := range forbiddenPrefixes {
					if path == bad || strings.HasPrefix(path, bad+"/") {
						t.Errorf("%s imports forbidden package %q (boundary violation)", fileName, path)
					}
				}
			}
		}
	}
}
```

- [ ] **Step 2: Run the boundary test to verify it passes**

Run: `go test ./internal/recommendations/ -run TestBoundary`
Expected: PASS (domain imports only `httpx` + stdlib + generated runtime).

- [ ] **Step 3: Commit**

```bash
git add internal/recommendations/boundary_test.go
git commit -m "test: recommendations package boundary guard"
```

---

## Task 9: Transport + container + app + main (end-to-end wiring)

**Files:**
- Create: `internal/http/middleware.go`
- Create: `internal/http/routes.go`
- Create: `internal/http/server.go`
- Create: `internal/app/container.go`
- Create: `internal/app/wire_recommendations.go`
- Create: `internal/app/app.go`
- Create: `cmd/ecom-gateway/main.go`

- [ ] **Step 1: Write transport middleware**

Create `internal/http/middleware.go`:
```go
package http

import (
	"runtime/debug"
	"strings"
	"time"

	"gj-ecom-gateway/internal/reqctx"

	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
	gjlogger "gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger"
)

const requestIDHeader = "X-Request-ID"

// requestIDMiddleware ensures every request has a correlation ID, echoed back
// on the response and stored in reqctx for downstream logging.
func requestIDMiddleware() fiber.Handler {
	return func(c *fiber.Ctx) error {
		id := strings.TrimSpace(c.Get(requestIDHeader))
		if _, err := uuid.Parse(id); err != nil {
			id = uuid.NewString()
		}
		reqctx.SetRequestID(c, id)
		c.Set(requestIDHeader, id)
		return c.Next()
	}
}

// accessLogMiddleware logs one structured line per request after the chain runs.
func accessLogMiddleware() fiber.Handler {
	return func(c *fiber.Ctx) error {
		start := time.Now()
		err := c.Next()
		gjlogger.WithContext(map[string]interface{}{
			"method":      c.Method(),
			"path":        c.Path(),
			"status":      c.Response().StatusCode(),
			"duration_ms": time.Since(start).Milliseconds(),
			"request_id":  reqctx.RequestID(c),
			"ip":          c.IP(),
		}).Info().Msg("access_request")
		return err
	}
}

// recoveryMiddleware converts panics into a 500 envelope and logs diagnostics.
func recoveryMiddleware() fiber.Handler {
	return func(c *fiber.Ctx) (err error) {
		defer func() {
			if rec := recover(); rec != nil {
				gjlogger.WithContext(map[string]interface{}{
					"request_id": reqctx.RequestID(c),
					"method":     c.Method(),
					"path":       c.Path(),
					"error":      rec,
					"stack":      string(debug.Stack()),
				}).Error().Msg("request_recover")
				err = c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
					"error":   "internal",
					"message": "internal server error",
				})
			}
		}()
		return c.Next()
	}
}

// registerBaseMiddleware installs request-id, access logging, and recovery in
// order. Access logging runs outside recovery so panic outcomes are still logged.
func registerBaseMiddleware(app *fiber.App) {
	app.Use(requestIDMiddleware())
	app.Use(accessLogMiddleware())
	app.Use(recoveryMiddleware())
}
```

- [ ] **Step 2: Write transport routes (thin coordinator)**

Create `internal/http/routes.go`:
```go
package http

import (
	"gj-ecom-gateway/internal/health"
	"gj-ecom-gateway/internal/observability"
	"gj-ecom-gateway/internal/recommendations"

	"github.com/gofiber/fiber/v2"
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
func registerRoutes(app *fiber.App, deps Dependencies) {
	observability.Mount(app, deps.Observability)
	health.Mount(app, deps.Health)

	v1 := app.Group("/api/v1")
	recommendations.Mount(v1, deps.Recommendations)
}
```

- [ ] **Step 3: Write the server**

Create `internal/http/server.go`:
```go
package http

import (
	"context"

	"gj-ecom-gateway/internal/config"

	"github.com/gofiber/fiber/v2"
	gjlogger "gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger"
)

// Server wraps the Fiber app and its lifecycle.
type Server struct {
	app    *fiber.App
	config config.Config
}

// NewServer builds the Fiber app, installs base middleware, and registers routes.
func NewServer(cfg config.Config, deps Dependencies) *Server {
	app := fiber.New(fiber.Config{AppName: cfg.AppName})
	registerBaseMiddleware(app)
	registerRoutes(app, deps)
	return &Server{app: app, config: cfg}
}

// Run starts listening (blocking).
func (s *Server) Run() error {
	addr := s.config.ListenAddr()
	gjlogger.Logger().Info().Msgf("%s listening on %s", s.config.AppName, addr)
	return s.app.Listen(addr)
}

// Shutdown gracefully stops the server.
func (s *Server) Shutdown(ctx context.Context) error {
	return s.app.ShutdownWithContext(ctx)
}
```

- [ ] **Step 4: Write the container**

Create `internal/app/container.go`:
```go
package app

import (
	"gj-ecom-gateway/internal/config"
	"gj-ecom-gateway/internal/health"
	"gj-ecom-gateway/internal/httpx"
	"gj-ecom-gateway/internal/observability"
	"gj-ecom-gateway/internal/recommendations"
)

// Container holds constructed dependencies, assembled once at startup.
type Container struct {
	Config config.Config

	Metrics       *observability.Metrics
	HealthHandler *health.Handler
	ErrorsHelper  *httpx.Helper

	RecommendationsHandler *recommendations.Handler
}

// NewContainer assembles all dependencies. Wiring per bounded context lives in
// wire_<context>.go files (guideline §12.2).
func NewContainer(cfg config.Config) *Container {
	c := &Container{Config: cfg}

	c.Metrics = observability.NewMetrics()
	c.ErrorsHelper = httpx.NewHelper()
	c.HealthHandler = health.NewHandler(health.NewService(cfg.AppName, cfg.Env))

	wireRecommendations(c)
	return c
}
```

- [ ] **Step 5: Write the recommendations wiring**

Create `internal/app/wire_recommendations.go`:
```go
package app

import "gj-ecom-gateway/internal/recommendations"

// wireRecommendations builds the recommendations bounded context with v1 stub
// ports. Real adapters (rec-service HTTP client, ENSI hydrator) replace the
// stubs here without touching the domain service.
func wireRecommendations(c *Container) {
	svc := recommendations.NewService(
		recommendations.NewStubSource(),
		recommendations.NewStubHydrator(),
	)
	c.RecommendationsHandler = recommendations.NewHandler(svc, c.ErrorsHelper)
}
```

- [ ] **Step 6: Write the app bootstrap**

Create `internal/app/app.go`:
```go
package app

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"gj-ecom-gateway/internal/config"
	"gj-ecom-gateway/internal/health"
	transport "gj-ecom-gateway/internal/http"
	"gj-ecom-gateway/internal/observability"
	"gj-ecom-gateway/internal/platform"
	"gj-ecom-gateway/internal/recommendations"

	gjlogger "gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger"
)

// App is the composed application.
type App struct {
	config     config.Config
	container  *Container
	httpServer *transport.Server
}

// New loads config, sets up logging, assembles the container, and builds the server.
func New() (*App, error) {
	cfg := config.Load()

	if err := platform.SetupLogger(cfg); err != nil {
		return nil, fmt.Errorf("setup logger: %w", err)
	}

	container := NewContainer(cfg)

	server := transport.NewServer(cfg, transport.Dependencies{
		Health:        health.Deps{Handler: container.HealthHandler},
		Observability: observability.Deps{Metrics: container.Metrics},
		Recommendations: recommendations.Deps{
			Handler: container.RecommendationsHandler,
		},
	})

	return &App{config: cfg, container: container, httpServer: server}, nil
}

// Run starts the server and blocks until a shutdown signal, then stops gracefully.
func (a *App) Run() error {
	const shutdownTimeout = 10 * time.Second

	interrupt := make(chan os.Signal, 1)
	signal.Notify(interrupt, os.Interrupt, syscall.SIGTERM)
	defer signal.Stop(interrupt)

	serverErr := make(chan error, 1)
	go func() { serverErr <- a.httpServer.Run() }()

	select {
	case err := <-serverErr:
		return err
	case sig := <-interrupt:
		gjlogger.Logger().Info().Str("signal", sig.String()).Msg("shutdown signal received")
		ctx, cancel := context.WithTimeout(context.Background(), shutdownTimeout)
		defer cancel()
		if err := a.httpServer.Shutdown(ctx); err != nil {
			return fmt.Errorf("server shutdown failed: %w", err)
		}
		return <-serverErr
	}
}
```

- [ ] **Step 7: Write main.go**

Create `cmd/ecom-gateway/main.go`:
```go
package main

import (
	"gj-ecom-gateway/internal/app"

	gjlogger "gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger"
)

func main() {
	application, err := app.New()
	if err != nil {
		gjlogger.Logger().Fatal().Err(err).Msg("bootstrap failed")
	}
	if err := application.Run(); err != nil {
		gjlogger.Logger().Fatal().Err(err).Msg("server failed")
	}
}
```

- [ ] **Step 8: Build + vet + full test run**

Run:
```bash
go mod tidy
go build ./...
go vet ./...
go test ./...
```
Expected: build succeeds, vet clean, all tests PASS.

- [ ] **Step 9: Smoke-test the running service**

Run:
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
Expected: `live=200`, `ready=200`, `metrics=200`, similar returns JSON with 2 items (ids 101,102), `no_pid=400`.

- [ ] **Step 10: Commit**

```bash
git add cmd/ internal/http/ internal/app/ go.mod go.sum
git commit -m "feat: transport, container, app bootstrap, main (end-to-end skeleton)"
```

---

## Task 10: Dockerfile, Makefile, README + final verification

**Files:**
- Create: `Dockerfile`
- Create: `Makefile`
- Create: `README.md`
- Create: `.dockerignore`

- [ ] **Step 1: Write the Makefile**

Create `Makefile`:
```makefile
.PHONY: generate lint build test run tidy

# Regenerate DTOs from the OpenAPI contract (types-only).
# Install once: go install github.com/oapi-codegen/oapi-codegen/v2/cmd/oapi-codegen@v2.4.1
generate:
	go generate ./internal/recommendations/...

# Validate the OpenAPI contract.
lint:
	npx --yes @redocly/cli lint api/v1/openapi.yaml

tidy:
	go mod tidy

build:
	go build ./...

test:
	go test ./...

run:
	go run ./cmd/ecom-gateway
```

- [ ] **Step 2: Write the Dockerfile**

Create `Dockerfile`:
```dockerfile
# syntax=docker/dockerfile:1
FROM golang:1.26.2 AS build
WORKDIR /src
# gj-go-logger is a sibling module resolved via a local replace directive.
COPY gj-go-logger/ /gj-go-logger/
COPY ecom-gateway/go.mod ecom-gateway/go.sum /src/
RUN go mod download
COPY ecom-gateway/ /src/
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/ecom-gateway ./cmd/ecom-gateway

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/ecom-gateway /ecom-gateway
EXPOSE 8080
USER nonroot:nonroot
ENTRYPOINT ["/ecom-gateway"]
```

> NOTE: the `replace … => ../gj-go-logger` directive means the Docker build context must be `platform/non-platform/` (the parent dir), so both `ecom-gateway/` and `gj-go-logger/` are visible. Build with:
> `docker build -f ecom-gateway/Dockerfile -t ecom-gateway .` run from `platform/non-platform/`.

- [ ] **Step 3: Write .dockerignore**

Create `.dockerignore`:
```
**/*_test.go
.git
```

- [ ] **Step 4: Write the README**

Create `README.md`:
```markdown
# ecom-gateway

Stateless Go/Fiber **BFF** for e-commerce personalization (similar products).
Pure BFF: no business logic. The recommendation engine and ENSI hydration are
separate services consumed via the `RecommendationSource` / `ProductHydrator`
ports — v1 uses deterministic stubs.

## Layout
- `cmd/ecom-gateway` — entrypoint (thin)
- `api/v1` — OpenAPI contract (source of truth) + oapi-codegen config (types-only)
- `internal/recommendations` — the one bounded context
- `internal/{config,observability,httpx,health,reqctx,platform,http,app}` — cross-cutting

## Develop
```bash
make tidy        # resolve deps (gj-go-logger via local ../gj-go-logger replace)
make generate    # regenerate DTOs from api/v1/openapi.yaml
make lint        # redocly lint of the contract
make test
make run         # serves on :8080
```

## Endpoints
- `GET /health/live`, `GET /health/ready`, `GET /metrics`
- `GET /api/v1/recommendations/similar?product_id={id}&limit={1..50}`

## Status
v1 = walking skeleton. Out of scope: real rec-service/ENSI clients, auth,
persistence, tracing, CI/deploy. See
`docs/superpowers/specs/2026-05-27-ecom-gateway-design.md`.
```

- [ ] **Step 5: Final verification (Definition of Done)**

Run:
```bash
PATH="$(go env GOPATH)/bin:$PATH" make generate
git diff --exit-code internal/recommendations/openapi.gen.go && echo "GEN-CLEAN" || echo "GEN-DRIFT"
make lint
make build
go vet ./...
make test
```
Expected: `GEN-CLEAN` (generated file matches committed), redocly lint passes, build clean, vet clean, all tests PASS.

- [ ] **Step 6: Verify Docker build**

Run from `platform/non-platform/`:
```bash
docker build -f ecom-gateway/Dockerfile -t ecom-gateway:dev .
```
Expected: image builds successfully.

- [ ] **Step 7: Commit**

```bash
git add Dockerfile .dockerignore Makefile README.md
git commit -m "chore: Dockerfile, Makefile, README for ecom-gateway skeleton"
```

---

## Definition of Done (recap from spec §7)

- `make generate` + `make lint` green; generated file has no drift.
- `go build ./...`, `go vet ./...`, `go test ./...` green.
- Service starts; `/health/live`, `/health/ready`, `/metrics` return 200; `GET /api/v1/recommendations/similar?product_id=…` returns stub cards; missing `product_id` → 400.
- Dockerfile builds locally (CI pipeline deferred to deploy phase).

## Explicitly out of scope (do NOT build)

Recommendation logic, real ENSI clients/hydration, personal recommendations + auth (`sessionctx`/customer token), Postgres/migrations, distributed tracing, dashboards/alerts, `.gitlab-ci.yml` and deploy configs.
