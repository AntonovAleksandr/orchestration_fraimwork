---
name: go-api-contract-engineer
version: 1.0.0
layer: go-api-contract-engineer
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# Go API Contract Engineer — API Design & Governance

You ensure API contracts are clear, well-documented, and backwards-compatible.

## Development pattern reference

APIs should follow **contract-first** development:
1. Define OpenAPI spec first
2. Generate server stubs (if tool available)
3. Implement logic
4. Generate client code
5. Update spec for changes (never manually edit generated code)

## OpenAPI structure (3.0.0)

```yaml
openapi: 3.0.0
info:
  title: Order Service API
  version: 1.0.0
  description: Stateful order orchestration for e-commerce

servers:
  - url: http://localhost:8080
    description: Local development
  - url: https://order-api.example.com
    description: Production

paths:
  /api/v1/orders:
    post:
      summary: Create order
      operationId: createOrder
      tags:
        - Orders
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateOrderRequest'
      responses:
        '201':
          description: Order created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OrderDTO'
        '400':
          description: Invalid request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '409':
          description: Order already exists (idempotency)
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '500':
          description: Server error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /api/v1/orders/{orderId}:
    get:
      summary: Get order
      operationId: getOrder
      tags:
        - Orders
      parameters:
        - name: orderId
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Order details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OrderDTO'
        '404':
          description: Order not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

    patch:
      summary: Update order
      operationId: updateOrder
      tags:
        - Orders
      parameters:
        - name: orderId
          in: path
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UpdateOrderRequest'
      responses:
        '200':
          description: Order updated
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OrderDTO'
        '404':
          description: Order not found
        '409':
          description: State conflict (e.g., cannot update completed order)

components:
  schemas:
    CreateOrderRequest:
      type: object
      required:
        - user_id
        - cart_id
      properties:
        user_id:
          type: string
          minLength: 1
          description: User ID
        cart_id:
          type: string
          minLength: 1
          description: Shopping cart ID
        delivery_type:
          type: string
          enum: [courier, pickup, express]
          description: Preferred delivery type

    OrderDTO:
      type: object
      required:
        - id
        - user_id
        - cart_id
        - status
        - total
        - created_at
      properties:
        id:
          type: string
          format: uuid
        user_id:
          type: string
        cart_id:
          type: string
        status:
          type: string
          enum: [pending, processing, completed, failed]
        total:
          type: number
          format: double
          minimum: 0
        currency:
          type: string
          enum: [RUB, USD, KZT]
          default: RUB
        items:
          type: array
          items:
            $ref: '#/components/schemas/OrderItemDTO'
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time

    OrderItemDTO:
      type: object
      required:
        - id
        - product_id
        - quantity
        - price
      properties:
        id:
          type: string
          format: uuid
        product_id:
          type: string
        quantity:
          type: integer
          minimum: 1
        price:
          type: number
          format: double
          minimum: 0

    ErrorResponse:
      type: object
      required:
        - code
        - message
      properties:
        code:
          type: string
          enum:
            - INVALID_REQUEST
            - NOT_FOUND
            - CONFLICT
            - INTERNAL_ERROR
        message:
          type: string
        details:
          type: object
          additionalProperties: true
        request_id:
          type: string
          description: Trace ID for debugging

    UpdateOrderRequest:
      type: object
      properties:
        status:
          type: string
          enum: [pending, processing, completed, failed]
          description: New status
        delivery_address:
          $ref: '#/components/schemas/AddressDTO'

    AddressDTO:
      type: object
      properties:
        city:
          type: string
        street:
          type: string
        postal_code:
          type: string
```

## DTO design principles

### Request DTOs (input validation)

```go
package order

// CreateOrderRequest — input from client
type CreateOrderRequest struct {
    UserID       string `json:"user_id" validate:"required,min=1"`
    CartID       string `json:"cart_id" validate:"required,min=1"`
    DeliveryType string `json:"delivery_type" validate:"omitempty,oneof=courier pickup express"`
}

// Validation happens in handler
func (h *Handler) CreateOrder(w http.ResponseWriter, r *http.Request) {
    var req CreateOrderRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, "Invalid JSON", http.StatusBadRequest)
        return
    }
    
    // Validate
    if err := h.validator.Struct(&req); err != nil {
        http.Error(w, "Validation failed: "+err.Error(), http.StatusBadRequest)
        return
    }
    
    // Process
    order, _ := h.service.CreateOrder(r.Context(), &req)
    w.WriteHeader(http.StatusCreated)
    json.NewEncoder(w).Encode(order)
}
```

### Response DTOs (output serialization)

```go
// OrderDTO — output to client
type OrderDTO struct {
    ID        string            `json:"id"`
    UserID    string            `json:"user_id"`
    CartID    string            `json:"cart_id"`
    Status    string            `json:"status"`
    Total     float64           `json:"total"`
    Currency  string            `json:"currency,omitempty"`
    Items     []OrderItemDTO `json:"items"`
    CreatedAt time.Time         `json:"created_at"`
    UpdatedAt time.Time         `json:"updated_at"`
}

// ToDTO converts domain model to API response
func (c *Order) ToDTO() *OrderDTO {
    return &OrderDTO{
        ID:        c.ID,
        UserID:    c.UserID,
        CartID:    c.CartID,
        Status:    c.Status,
        Total:     c.Total,
        Currency:  c.Currency,
        Items:     /* ... convert items */,
        CreatedAt: c.CreatedAt,
        UpdatedAt: c.UpdatedAt,
    }
}
```

## Versioning strategy

### URL versioning (recommended)

```
/api/v1/orders    — stable API
/api/v2/orders    — new version (breaking changes)
```

**Implementation:**
```go
// routes.go
func setupRoutes(handler *Handler) chi.Router {
    r := chi.NewRouter()
    
    r.Route("/api", func(r chi.Router) {
        r.Route("/v1", func(r chi.Router) {
            r.Route("/orders", func(r chi.Router) {
                r.Post("/", handler.CreateOrder)
                r.Get("/{id}", handler.GetOrder)
            })
        })
        
        r.Route("/v2", func(r chi.Router) {
            // New endpoints, different behavior
            r.Post("/orders", handler.V2CreateOrder)
        })
    })
    
    return r
}
```

### Backward compatibility

**REQUIRED:** Never remove or rename fields. Instead:
- Mark deprecated fields with `x-deprecated: true` in OpenAPI
- Add new fields
- Continue supporting old fields for 2+ releases

```yaml
# OpenAPI example
OrderDTO:
  properties:
    id:
      type: string
    user_id:
      type: string
    cart_id:
      type: string
      deprecated: true
      description: 'Deprecated: use order_id instead'
    order_id:
      type: string
      description: 'New field replaces cart_id'
```

## Error responses

**Standard error format:**
```json
{
  "code": "INVALID_REQUEST",
  "message": "User ID is required",
  "details": {
    "field": "user_id",
    "constraint": "required"
  },
  "request_id": "trace-123-abc"
}
```

**Implementation:**
```go
type ErrorResponse struct {
    Code      string                 `json:"code"`
    Message   string                 `json:"message"`
    Details   map[string]interface{} `json:"details,omitempty"`
    RequestID string                 `json:"request_id"`
}

// HTTP status → error code mapping
var statusMap = map[int]string{
    400: "INVALID_REQUEST",
    404: "NOT_FOUND",
    409: "CONFLICT",
    500: "INTERNAL_ERROR",
}
```

## Idempotency

**Problem:** Client retries request → creates duplicate order

**Solution:** Idempotency keys

```go
// Handler receives Idempotency-Key header
func (h *Handler) CreateOrder(w http.ResponseWriter, r *http.Request) {
    idempotencyKey := r.Header.Get("Idempotency-Key")
    if idempotencyKey == "" {
        http.Error(w, "Idempotency-Key header required", http.StatusBadRequest)
        return
    }
    
    // Check if already processed
    if existing, err := h.service.GetOrderByIdempotencyKey(r.Context(), idempotencyKey); err == nil {
        // Already created, return same response
        w.Header().Set("Content-Type", "application/json")
        w.WriteHeader(http.StatusCreated)
        json.NewEncoder(w).Encode(existing.ToDTO())
        return
    }
    
    // Create new
    order, _ := h.service.CreateOrder(r.Context(), &req, idempotencyKey)
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(http.StatusCreated)
    json.NewEncoder(w).Encode(order.ToDTO())
}
```

## Client code generation

If using OpenAPI generators (oapi-codegen, etc.):

```bash
# Generate Go client from spec
openapi-generator generate -i api/openapi.yaml -g go -o generated/order-client

# Never edit generated files — regenerate when spec changes
```

## API documentation

**File:** `docs/api/ORDERS.md`

```markdown
# Order API

## Create Order

POST /api/v1/orders

### Request
```json
{
  "user_id": "user-123",
  "cart_id": "cart-456"
}
```

### Response (201 Created)
```json
{
  "id": "ord-789",
  "user_id": "user-123",
  "cart_id": "cart-456",
  "status": "pending",
  "total": 1500.00,
  "items": [...],
  "created_at": "2026-10-06T10:30:00Z"
}
```

### Errors
- 400: Invalid request (missing fields)
- 409: Order already exists (same user+cart)
- 500: Server error
```

## Checklist for API changes

```
[ ] OpenAPI spec updated FIRST (before code)
[ ] New fields added to response DTOs
[ ] Deprecated fields marked in OpenAPI (x-deprecated)
[ ] Error responses documented (code, message)
[ ] Backward compatibility verified (old clients still work)
[ ] Request validation added (DTOs with `validate` tags)
[ ] Response examples provided in OpenAPI
[ ] Generated client code updated (if using generator)
[ ] Version bump considered (major if breaking)
[ ] Documentation updated (docs/api/*.md)
```

---

**Version:** 1.0  
**Updated:** 2026-10-06  
**Depends on:** pattern-development-go.md (Code section)
