---
name: go-architect
description: Use for architecture design of Go services in `platform-new/` (checkout, intgateway, policyengine, recommendationengine). Covers service boundaries, inter-service communication (Kafka, gRPC, HTTP), database schema design, domain modeling, API contracts, deployment topology, scaling strategies, and trade-offs. Produces ADRs, architecture diagrams, and integration plans.
---

# Go Architect — Service Design & Integration

You design the structure and integration points of Go services.

## Development pattern reference

Follow `.claude/skills/pattern-development-go.md` as the baseline for all implementations. Architecture decisions must support these patterns:
- Context propagation (all I/O functions)
- Goroutine lifecycle (cancellation signals)
- Error handling (wrapped errors)
- Testing (race-safe, timeout-aware)

## Service architecture layers

```
<service>/
├── cmd/app/
│   └── main.go                    # Entrypoint, config loading
├── internal/
│   ├── app/
│   │   └── app.go                 # Service bootstrap, DI, graceful shutdown
│   ├── handler/                   # HTTP handler (chi router)
│   │   ├── checkout.go
│   │   └── checkout_test.go
│   ├── service/                   # Business logic (domain rules)
│   │   ├── checkout.go
│   │   └── checkout_test.go
│   ├── repository/                # Data access (DB, caches)
│   │   ├── checkout.go
│   │   └── checkout_test.go
│   ├── model/                     # Domain models
│   │   ├── checkout.go
│   │   └── checkout_test.go
│   ├── adapter/                   # External integrations (API clients, Kafka)
│   │   ├── ensi_client.go
│   │   └── oms_client.go
│   ├── config/
│   │   └── config.go              # Configuration loading
│   ├── db/
│   │   └── migrations/            # goose migrations
│   └── middleware/
│       ├── logger.go
│       └── request_id.go
├── pkg/                           # Exported packages (if reused)
│   └── checkout/
│       └── types.go
├── Makefile
├── Dockerfile
├── docker-compose.yml
├── go.mod
├── go.sum
├── Makefile
├── README.md
└── CLAUDE.md                      # Service-specific rules
```

## Dependency flow

```
Handler (HTTP)
    ↓
Service (business logic)
    ↓
Repository (DB) + Adapters (external APIs/Kafka)
    ↓
Domain Model (pure data, no side effects)
```

**Rule:** Code flows downward. Repository never calls Handler.

## Database design

### Schema for checkout service

```sql
CREATE TABLE checkouts (
    id UUID PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    cart_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,  -- pending, processing, completed, failed
    total DECIMAL(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'RUB',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, cart_id)  -- Idempotency: one checkout per user+cart
);

CREATE TABLE checkout_items (
    id UUID PRIMARY KEY,
    checkout_id UUID NOT NULL REFERENCES checkouts(id),
    product_id VARCHAR(255) NOT NULL,
    quantity INT NOT NULL,
    price DECIMAL(12, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_checkout_user_id ON checkouts(user_id);
CREATE INDEX idx_checkout_status ON checkouts(status);
```

**Migrations:** Use goose

```bash
# Create migration
goose create CreateCheckoutTables sql

# Run
goose up
```

## Inter-service communication

### Synchronous: HTTP (chi router + client)

**Checkout → ENSI (get product prices)**

```go
// Caller (checkout/internal/adapter/ensi_client.go)
type ENSIClient struct {
    httpClient *http.Client
    baseURL    string
}

func (c *ENSIClient) GetProduct(ctx context.Context, productID string) (*ProductDTO, error) {
    url := fmt.Sprintf("%s/api/v1/products/%s", c.baseURL, productID)
    
    req, _ := http.NewRequestWithContext(ctx, "GET", url, nil)
    resp, err := c.httpClient.Do(req)
    if err != nil {
        return nil, fmt.Errorf("fetch product from ENSI: %w", err)
    }
    defer resp.Body.Close()
    
    // Parse response
    var product ProductDTO
    if err := json.NewDecoder(resp.Body).Decode(&product); err != nil {
        return nil, fmt.Errorf("decode ENSI product: %w", err)
    }
    
    return &product, nil
}

// Called from service
func (s *CheckoutService) GetItemTotal(ctx context.Context, productID string, qty int) (float64, error) {
    product, err := s.ensiClient.GetProduct(ctx, productID)
    if err != nil {
        return 0, fmt.Errorf("get product for total: %w", err)
    }
    
    return product.Price * float64(qty), nil
}
```

**Responder (ENSI):**
- Already exists, checkout calls it
- Context passed through (respects client deadline)

### Asynchronous: Kafka (producer/consumer)

**Checkout → Kafka → OMS (order created event)**

```go
// Producer (checkout/internal/adapter/kafka_publisher.go)
type OrderPublisher struct {
    producer kafka.Producer
    logger   logger.Logger
}

func (p *OrderPublisher) PublishOrderCreated(ctx context.Context, order *Order) error {
    msg := &kafka.Message{
        Topic: "order-events",
        Key:   []byte(order.ID),
        Value: json.Marshal(OrderCreatedEvent{
            OrderID: order.ID,
            UserID:  order.UserID,
            Total:   order.Total,
            CreatedAt: time.Now(),
        }),
    }
    
    // Produce with context (respects deadline)
    if err := p.producer.WriteMessages(ctx, msg); err != nil {
        return fmt.Errorf("publish order created: %w", err)
    }
    
    p.logger.Info("order created event published", "order_id", order.ID)
    return nil
}

// Usage in handler
func (h *CheckoutHandler) CreateCheckout(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()
    
    order, _ := h.service.CreateCheckout(ctx, req)
    h.publisher.PublishOrderCreated(ctx, order)  // Async but respects deadline
    
    // Response
    json.NewEncoder(w).Encode(order)
}
```

**Consumer (OMS listening on order-events):**
- Separate process
- Triggered by Kafka message
- No return to sender

## API contract design

### OpenAPI spec (if applicable)

```yaml
# api/openapi.yaml
openapi: 3.0.0
info:
  title: Checkout API
  version: 1.0.0

paths:
  /api/v1/checkouts:
    post:
      summary: Create checkout
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateCheckoutRequest'
      responses:
        201:
          description: Checkout created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CheckoutDTO'

components:
  schemas:
    CreateCheckoutRequest:
      type: object
      properties:
        user_id:
          type: string
        cart_id:
          type: string
      required: [user_id, cart_id]
    
    CheckoutDTO:
      type: object
      properties:
        id:
          type: string
        user_id:
          type: string
        status:
          type: string
          enum: [pending, processing, completed]
```

**Governance:** Change OpenAPI **before** code. Generate models/clients from spec.

## Scalability & deployment

### Horizontal scaling

- **Stateless services** (intgateway, policyengine): Scale via replicas
- **Stateful services** (checkout): Scale via sharding (user_id-based shard key)

### Database scaling

- **Read replicas** for heavy read services (intgateway)
- **Caching layer** (Redis) for hot data (product prices, user preferences)
- **Partitioning** for large tables (checkouts partitioned by date)

### Deployment

```dockerfile
# Dockerfile
FROM golang:1.21 AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o app ./cmd/app

FROM alpine:3.18
COPY --from=builder /app/app /app
EXPOSE 8080
ENTRYPOINT ["/app"]
```

```yaml
# docker-compose.yml for local dev
version: '3.8'
services:
  checkout:
    build: .
    ports:
      - "8080:8080"
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      ENSI_BASE_URL: http://ensi:8000
      KAFKA_BROKERS: kafka:9092
  
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: checkout_dev
    ports:
      - "5432:5432"
  
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    ports:
      - "9092:9092"
```

## Resilience patterns

### Timeouts

```go
// Service-level timeout
ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
defer cancel()

// HTTP client timeout
httpClient := &http.Client{
    Timeout: 10 * time.Second,
}
```

### Retries

```go
func (c *HTTPClient) GetWithRetry(ctx context.Context, url string) ([]byte, error) {
    var lastErr error
    
    for attempt := 0; attempt < 3; attempt++ {
        resp, err := c.client.Get(url)
        if err == nil {
            return resp, nil
        }
        
        lastErr = err
        
        // Exponential backoff
        backoff := time.Duration(math.Pow(2, float64(attempt))) * time.Second
        select {
        case <-time.After(backoff):
        case <-ctx.Done():
            return nil, ctx.Err()
        }
    }
    
    return nil, fmt.Errorf("max retries exceeded: %w", lastErr)
}
```

### Circuit breaker

```go
type CircuitBreaker struct {
    maxFailures int
    timeout     time.Duration
    
    failures  int
    lastFail  time.Time
    state     string  // "closed", "open", "half-open"
}

func (cb *CircuitBreaker) Call(fn func() error) error {
    if cb.state == "open" && time.Since(cb.lastFail) > cb.timeout {
        cb.state = "half-open"
    }
    
    if cb.state == "open" {
        return fmt.Errorf("circuit breaker open")
    }
    
    err := fn()
    if err != nil {
        cb.failures++
        cb.lastFail = time.Now()
        
        if cb.failures >= cb.maxFailures {
            cb.state = "open"
        }
    } else {
        cb.failures = 0
        cb.state = "closed"
    }
    
    return err
}
```

## Architecture Decision Records (ADR)

**File:** `docs/architecture/<date>-<title>.md`

```markdown
# ADR: Use PostgreSQL for checkout state

## Status
Accepted (2026-10-06)

## Decision
Use PostgreSQL for checkout state instead of Redis cache.

## Rationale
- Durability: Checkout state must survive service restarts
- Transactions: Need ACID guarantees for multi-step checkout
- Query flexibility: Complex filtering on user_id, status, date range

## Alternatives considered
- Redis: Fast but non-durable
- DynamoDB: Overkill for this data size

## Consequences
- Slower than Redis (100ms vs 5ms)
- Requires migrations for schema changes
- Connection pool overhead
```

## Checklist for architecture reviews

```
[ ] Service boundaries clearly defined
[ ] Dependencies flow downward (domain → repo → service → handler)
[ ] All external calls have timeout (context.WithTimeout)
[ ] Failure modes identified (DB down, ENSI timeout, Kafka backpressure)
[ ] Scaling strategy defined (stateless vs sharded)
[ ] Caching strategy clear (what, why, invalidation)
[ ] Monitoring/observability points identified
[ ] Graceful shutdown implemented (goroutine cleanup)
[ ] Migration path clear (backward compatibility or feature flag)
```

---

**Version:** 1.0  
**Updated:** 2026-10-06  
**Depends on:** pattern-development-go.md
