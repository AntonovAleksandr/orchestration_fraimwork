---
name: SKILL
version: 1.0.0
layer: go-library-engineer
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# Go Library Engineer — Shared Code & Dependencies

You build and maintain Go libraries that multiple services depend on.

## Development pattern reference

Libraries must support pattern-development-go principles:
- **Context propagation:** All I/O functions accept `context.Context` as first param
- **Error handling:** Errors wrapped with `fmt.Errorf("%w", err)`
- **Concurrency-safe:** No unprotected shared state
- **Well-tested:** 80%+ coverage, -race detector passing

## Library structure

```
gj-go-logger/
├── logger.go              # Main interface & implementation
├── logger_test.go         # Unit tests
├── examples/
│   └── usage.go           # Example usage
├── go.mod                 # Module definition
├── go.sum                 # Dependency lock
├── README.md              # Documentation
├── LICENSE                # (usually MIT)
└── CHANGELOG.md           # Version history
```

## Core library: gj-go-logger

```go
// logger.go
package logger

import (
    "context"
    "log/slog"
)

// Logger is the interface all services depend on
type Logger interface {
    // Structured logging with context propagation
    InfoContext(ctx context.Context, msg string, args ...interface{})
    ErrorContext(ctx context.Context, msg string, args ...interface{})
    DebugContext(ctx context.Context, msg string, args ...interface{})
    
    // Legacy (deprecated)
    Info(msg string, args ...interface{})
    Error(msg string, args ...interface{})
}

// Implementation using slog
type slogLogger struct {
    logger *slog.Logger
}

func (l *slogLogger) InfoContext(ctx context.Context, msg string, args ...interface{}) {
    l.logger.LogContext(ctx, slog.LevelInfo, msg, args...)
}

func (l *slogLogger) ErrorContext(ctx context.Context, msg string, args ...interface{}) {
    l.logger.LogContext(ctx, slog.LevelError, msg, args...)
}

// Create logger (uses JSON handler for ELK)
func New() Logger {
    return &slogLogger{
        logger: slog.New(slog.NewJSONHandler(os.Stdout, nil)),
    }
}
```

**Usage in services:**
```go
import "github.com/gloriajeansdev/gj-go-logger"

type CheckoutService struct {
    logger logger.Logger  // Inject interface, not concrete type
}

func (s *CheckoutService) GetCheckout(ctx context.Context, id string) (*Checkout, error) {
    s.logger.InfoContext(ctx, "fetching checkout", "checkout_id", id)
    
    checkout, err := s.repo.Get(ctx, id)
    if err != nil {
        s.logger.ErrorContext(ctx, "checkout fetch failed", "error", err)
        return nil, fmt.Errorf("get checkout: %w", err)
    }
    
    return checkout, nil
}
```

## Core library: gj-go-httpclient

```go
// httpclient.go
package httpclient

import (
    "context"
    "io"
    "net/http"
    "time"
)

// Client wraps http.Client with sensible defaults
type Client struct {
    httpClient *http.Client
    baseURL    string
}

// New creates a client with default timeouts
func New(baseURL string) *Client {
    return &Client{
        httpClient: &http.Client{
            Timeout: 30 * time.Second,  // Global timeout
            Transport: &http.Transport{
                MaxIdleConns:       100,
                MaxIdleConnsPerHost: 10,
                MaxConnsPerHost:     100,
            },
        },
        baseURL: baseURL,
    }
}

// ✅ MANDATORY: context as first parameter
func (c *Client) Get(ctx context.Context, path string) ([]byte, error) {
    url := c.baseURL + path
    
    req, _ := http.NewRequestWithContext(ctx, "GET", url, nil)
    resp, err := c.httpClient.Do(req)
    if err != nil {
        return nil, fmt.Errorf("http get %s: %w", path, err)
    }
    defer resp.Body.Close()
    
    // Check status
    if resp.StatusCode >= 400 {
        body, _ := io.ReadAll(resp.Body)
        return nil, fmt.Errorf("http %d: %s", resp.StatusCode, string(body))
    }
    
    body, err := io.ReadAll(resp.Body)
    if err != nil {
        return nil, fmt.Errorf("read response: %w", err)
    }
    
    return body, nil
}

// Post with request/response types
func (c *Client) Post(ctx context.Context, path string, req interface{}, resp interface{}) error {
    // Implementation
    return nil
}
```

**Usage:**
```go
import "github.com/gloriajeansdev/gj-go-httpclient"

type ENSIClient struct {
    http *httpclient.Client
}

func (c *ENSIClient) GetProduct(ctx context.Context, id string) (*Product, error) {
    // Context passed through — respects deadline
    body, err := c.http.Get(ctx, "/api/v1/products/"+id)
    if err != nil {
        return nil, fmt.Errorf("fetch product: %w", err)
    }
    
    var p Product
    json.Unmarshal(body, &p)
    return &p, nil
}
```

## Core library: gj-go-money

```go
// money.go
package money

import "fmt"

// Money is a safe representation of currency (kopecks as integer)
type Money struct {
    Amount   int64  // Amount in kopecks (never float!)
    Currency string // RUB, USD, KZT
}

// FromRubles creates Money from rubles (float → int conversion)
func FromRubles(rubles float64, currency string) Money {
    kopecks := int64(rubles * 100)  // 1500.99 RUB → 150099 kopecks
    return Money{
        Amount:   kopecks,
        Currency: currency,
    }
}

// ToRubles returns money as float rubles
func (m Money) ToRubles() float64 {
    return float64(m.Amount) / 100  // 150099 kopecks → 1500.99
}

// Add safely adds two money amounts (must be same currency)
func (m Money) Add(other Money) (Money, error) {
    if m.Currency != other.Currency {
        return Money{}, fmt.Errorf("cannot add %s to %s", other.Currency, m.Currency)
    }
    return Money{
        Amount:   m.Amount + other.Amount,
        Currency: m.Currency,
    }, nil
}

// String implements Stringer
func (m Money) String() string {
    return fmt.Sprintf("%.2f %s", m.ToRubles(), m.Currency)
}
```

**Usage:**
```go
import "github.com/gloriajeansdev/gj-go-money"

type CheckoutDTO struct {
    Total money.Money `json:"total"`
}

// In handler
checkout := &Checkout{}
// ...
price := money.FromRubles(1500.99, "RUB")
checkout.Total = price
```

## Versioning

### Semantic versioning (semver)

```
v1.0.0
↑ ↑ ↑
│ │ └─ Patch: bug fixes (1.0.1)
│ └─── Minor: new features, backward compatible (1.1.0)
└───── Major: breaking changes (2.0.0)
```

### go.mod

```go
module github.com/gloriajeansdev/gj-go-logger

go 1.21

require (
    golang.org/x/exp v0.0.0-20231006140011-7918f672742d
)
```

### Tags for releases

```bash
# Create tagged release
git tag v1.2.0
git push origin v1.2.0

# Services can depend on specific version
require github.com/gloriajeansdev/gj-go-logger v1.2.0
```

## Backward compatibility

### Adding a new method (non-breaking)

```go
// ✅ OK: Add method to interface
type Logger interface {
    Info(msg string, args ...interface{})
    Error(msg string, args ...interface{})
    + InfoContext(ctx context.Context, msg string, args ...interface{})  // NEW
}

// Bump minor version: v1.1.0 → v1.2.0
```

### Changing method signature (breaking)

```go
// ❌ BREAKING: Change parameter type
type Logger interface {
    // OLD: Info(msg string, args ...interface{})
    // NEW: Info(ctx context.Context, msg string, args ...interface{})
}

// Bump major version: v1.x.x → v2.0.0
// Old code won't compile
```

**Alternative:** Add new method, deprecate old one

```go
type Logger interface {
    // Deprecated: use InfoContext instead
    Info(msg string, args ...interface{})
    
    // New method
    InfoContext(ctx context.Context, msg string, args ...interface{})
}
```

## Testing libraries

```go
// logger_test.go
package logger

import "testing"

func TestLogger_InfoContext(t *testing.T) {
    tests := []struct {
        name   string
        msg    string
        args   []interface{}
    }{
        {
            name: "valid message",
            msg:  "test message",
            args: []interface{}{"key", "value"},
        },
    }
    
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            logger := New()
            ctx := context.Background()
            
            // Just verify no panic
            logger.InfoContext(ctx, tt.msg, tt.args...)
        })
    }
}

// Mock for testing
type MockLogger struct {
    InfoCalls []string
}

func (m *MockLogger) InfoContext(ctx context.Context, msg string, args ...interface{}) {
    m.InfoCalls = append(m.InfoCalls, msg)
}
```

## Documentation

**File:** `README.md`

```markdown
# gj-go-logger

Structured logging library for Gloria Jeans Go services.

## Installation

```bash
go get github.com/gloriajeansdev/gj-go-logger
```

## Usage

```go
import "github.com/gloriajeansdev/gj-go-logger"

logger := logger.New()

ctx := context.Background()
logger.InfoContext(ctx, "checkout created", "checkout_id", "co-123")
// Output: {"level":"info","msg":"checkout created","checkout_id":"co-123"}
```

## API

### Logger interface

```go
type Logger interface {
    InfoContext(ctx context.Context, msg string, args ...interface{})
    ErrorContext(ctx context.Context, msg string, args ...interface{})
    DebugContext(ctx context.Context, msg string, args ...interface{})
}
```

## Versioning

This library uses [Semantic Versioning](https://semver.org/).

- v1.x.x: Stable API
- v2.0.0 (future): Breaking changes
```

## Distribution & registration

For libraries to be discoverable:

1. **github.com:** Push to company GitHub
2. **go.mod:** Declare in go.mod of services using it
3. **Makefile:** Add test/lint targets
4. **CI/CD:** Ensure tests pass before release

```go
// In service's go.mod
require github.com/gloriajeansdev/gj-go-logger v1.2.0
```

## Checklist for library releases

```
[ ] Unit tests pass (go test -race ./...)
[ ] Coverage > 80%
[ ] README.md updated with examples
[ ] CHANGELOG.md entry added
[ ] Backward compatibility verified (or major version bump)
[ ] API documentation complete (godoc)
[ ] Examples in docs/examples/ or README
[ ] Go.mod and go.sum committed
[ ] Tags created (v1.x.x format)
[ ] All services updated to new version (coordinated)
```

## Common pitfalls

| Pitfall | Fix |
|---------|-----|
| Context not propagated | Accept `context.Context` as first param in all I/O functions |
| Panic instead of error | Return error, let caller decide response |
| Mutable global state | No package-level variables; use dependency injection |
| No versioning | Use semver tags (v1.0.0, v1.0.1, v1.1.0, v2.0.0) |
| Breaking changes without major bump | Always bump major version if API changes |
| Unused library | Archive or remove; don't let it rot |

---

**Version:** 1.0  
**Updated:** 2026-10-06  
**Depends on:** pattern-development-go.md (Code & Testing sections)
