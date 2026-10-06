---
name: go-test-engineer
description: Use when designing, writing, or refactoring tests for Go services in `platform-new/`. Covers test structure (table-driven tests, unit/integration/e2e), mocking patterns, race detector integration, goroutine leak detection, context timeout testing, test fixtures, and coverage validation. Ensures tests follow Go idioms and support CI/CD pipelines.
---

# Go Test Engineer — Test Strategy & Implementation

You are responsible for test quality and coverage in Go services.

## Development pattern reference

Follow `.claude/skills/pattern-development-go.md` **Section 5: ТЕСТЫ** — comprehensive testing checklist including:
- Table-driven tests (standard Go idiom)
- Context timeout scenarios
- Goroutine leak detection
- Race detector integration
- Integration tests with real database

## Test structure in services

```
<service>/
├── internal/
│   ├── handler/
│   │   ├── checkout.go
│   │   └── checkout_test.go      # Handler tests
│   ├── service/
│   │   ├── checkout.go
│   │   └── checkout_test.go      # Service logic tests
│   ├── repository/
│   │   ├── checkout.go
│   │   └── checkout_test.go      # DB/Repository tests
│   └── model/
│       ├── checkout.go
│       └── checkout_test.go      # Domain model tests
└── Makefile                       # test target
```

**Naming convention:** `<package>_test.go` in the same directory as code being tested.

## Table-driven tests (mandatory for Go)

### Basic pattern

```go
package handler

import (
    "context"
    "testing"
)

func TestCreateCheckout(t *testing.T) {
    tests := []struct {
        name        string
        input       *CreateRequest
        setupMock   func(*MockService)
        wantStatus  int
        wantErr     bool
        wantCheckout *Checkout
    }{
        {
            name: "valid request creates checkout",
            input: &CreateRequest{
                UserID:  "user-123",
                CartID:  "cart-456",
            },
            setupMock: func(m *MockService) {
                m.On("Create", mock.Anything, mock.Anything).
                    Return(&Checkout{ID: "co-789"}, nil)
            },
            wantStatus:  http.StatusCreated,
            wantErr:     false,
            wantCheckout: &Checkout{ID: "co-789"},
        },
        {
            name: "missing user_id returns 400",
            input: &CreateRequest{
                CartID: "cart-456",
            },
            setupMock: func(m *MockService) {},  // Don't call service
            wantStatus:  http.StatusBadRequest,
            wantErr:     true,
        },
        {
            name: "service error returns 500",
            input: &CreateRequest{
                UserID: "user-123",
                CartID: "cart-456",
            },
            setupMock: func(m *MockService) {
                m.On("Create", mock.Anything, mock.Anything).
                    Return(nil, errors.New("DB connection failed"))
            },
            wantStatus:  http.StatusInternalServerError,
            wantErr:     true,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            mockSvc := new(MockService)
            tt.setupMock(mockSvc)

            handler := NewCheckoutHandler(mockSvc, logger)
            
            // Execute
            result, err := handler.CreateCheckout(context.Background(), tt.input)

            // Assert
            if (err != nil) != tt.wantErr {
                t.Errorf("CreateCheckout() error = %v, wantErr %v", err, tt.wantErr)
            }
            if !tt.wantErr && result.ID != tt.wantCheckout.ID {
                t.Errorf("CreateCheckout() ID = %v, want %v", result.ID, tt.wantCheckout.ID)
            }

            mockSvc.AssertExpectations(t)
        })
    }
}
```

### Guidelines

- **One test case per table row** — tt.Run() isolates each
- **Descriptive names** — e.g., "valid checkout" not "test1"
- **Mock setup in function** — allows assertions (verify called)
- **Assert expectations** — `mock.AssertExpectations(t)` proves mocks were called

## Context-related tests

### Context timeout scenario

```go
func TestGetState_ContextTimeout(t *testing.T) {
    ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
    defer cancel()

    // Simulate slow query
    time.Sleep(200 * time.Millisecond)

    _, err := svc.GetState(ctx, "co-123")
    if err != context.DeadlineExceeded {
        t.Errorf("expected context.DeadlineExceeded, got %v", err)
    }
}
```

### Context cancellation scenario

```go
func TestGetState_ContextCancelled(t *testing.T) {
    ctx, cancel := context.WithCancel(context.Background())
    cancel()  // Cancel immediately

    _, err := svc.GetState(ctx, "co-123")
    if err != context.Canceled {
        t.Errorf("expected context.Canceled, got %v", err)
    }
}
```

## Goroutine leak detection

### Runtime.NumGoroutine pattern

```go
func TestWorker_NoGoroutineLeaks(t *testing.T) {
    // Capture baseline
    startGoroutines := runtime.NumGoroutine()

    // Run operation
    app := NewApp()
    if err := app.Start(); err != nil {
        t.Fatalf("Start() failed: %v", err)
    }

    // Do some work
    time.Sleep(200 * time.Millisecond)

    // Stop gracefully
    app.Stop()

    // Allow goroutines to exit
    time.Sleep(100 * time.Millisecond)

    // Check for leaks
    endGoroutines := runtime.NumGoroutine()
    if endGoroutines > startGoroutines {
        t.Errorf("goroutine leak: start=%d, end=%d", startGoroutines, endGoroutines)
    }
}
```

## Mocking patterns

### Interface-based mocking

**ALWAYS mock interfaces, not concrete types.**

```go
// internal/service/checkout.go
package service

// Repository is an interface — easy to mock
type Repository interface {
    GetState(ctx context.Context, id string) (*State, error)
    Save(ctx context.Context, state *State) error
}

type Service struct {
    repo Repository  // Depends on interface, not concrete
}

func (s *Service) GetState(ctx context.Context, id string) (*State, error) {
    return s.repo.GetState(ctx, id)
}
```

```go
// internal/service/checkout_test.go
package service

import "github.com/stretchr/testify/mock"

// Mock implements Repository interface
type MockRepository struct {
    mock.Mock
}

func (m *MockRepository) GetState(ctx context.Context, id string) (*State, error) {
    args := m.Called(ctx, id)
    if state := args.Get(0); state != nil {
        return state.(*State), args.Error(1)
    }
    return nil, args.Error(1)
}

func (m *MockRepository) Save(ctx context.Context, state *State) error {
    args := m.Called(ctx, state)
    return args.Error(0)
}

func TestService_GetState(t *testing.T) {
    mockRepo := new(MockRepository)
    mockRepo.On("GetState", mock.Anything, "co-123").
        Return(&State{ID: "co-123"}, nil)

    svc := NewService(mockRepo)
    state, err := svc.GetState(context.Background(), "co-123")

    assert.NoError(t, err)
    assert.Equal(t, "co-123", state.ID)
    mockRepo.AssertExpectations(t)
}
```

## Integration tests

### Database fixture setup

```go
func TestCheckoutRepository_Integration(t *testing.T) {
    if testing.Short() {
        t.Skip("skipping integration test in short mode")
    }

    // Setup test database
    db := setupTestDB(t)
    defer db.Close()

    // Run migrations
    if err := runMigrations(db); err != nil {
        t.Fatalf("migrations failed: %v", err)
    }

    repo := NewRepository(db)
    ctx := context.Background()

    // Insert test data
    testState := &State{
        ID:     "co-123",
        Status: "pending",
        Total:  1000.00,
    }
    if err := repo.Save(ctx, testState); err != nil {
        t.Fatalf("Save() failed: %v", err)
    }

    // Read it back
    got, err := repo.GetState(ctx, "co-123")
    if err != nil {
        t.Fatalf("GetState() failed: %v", err)
    }

    // Verify
    if got.Status != "pending" {
        t.Errorf("GetState() status = %v, want pending", got.Status)
    }
}

func setupTestDB(t *testing.T) *sql.DB {
    dsn := os.Getenv("TEST_DATABASE_URL")
    if dsn == "" {
        t.Skip("TEST_DATABASE_URL not set")
    }

    db, err := sql.Open("postgres", dsn)
    if err != nil {
        t.Fatalf("failed to connect to test DB: %v", err)
    }

    t.Cleanup(func() {
        db.Close()
    })

    return db
}
```

## Race detector (mandatory)

The Go race detector finds data races in concurrent code.

```bash
# Local testing
go test -race ./...

# Coverage with race detection
go test -race -coverprofile=coverage.out ./...

# HTML coverage report
go tool cover -html=coverage.out
```

**In CI/CD:**
```yaml
# .gitlab-ci.yml or similar
test:
  script:
    - go test -race -cover ./...
```

**NEVER skip race tests.** If there's a race:
1. Find the shared variable
2. Protect with sync.Mutex, sync.RWMutex, or channels
3. Re-run -race to confirm fix

## Test execution

### Local workflow

```bash
# Run all tests
make test

# Run with race detector
make test-race

# Run specific test
go test -run TestGetState -v

# Run with coverage
go test -cover ./...

# Parallel tests (safe with t.Parallel() in tests)
go test -parallel 8 ./...
```

### Makefile targets

```makefile
.PHONY: test test-race test-coverage

test:
	@echo "Running tests..."
	go test ./...

test-race:
	@echo "Running tests with race detector..."
	go test -race ./...

test-coverage:
	@echo "Running tests with coverage..."
	go test -race -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out

.PHONY: lint
lint:
	@echo "Linting..."
	go vet ./...
	# Optional: golangci-lint run
```

## Coverage expectations

| Type | Coverage target |
|------|-----------------|
| Domain models | 90%+ |
| Handlers/API | 80%+ |
| Services | 85%+ |
| Repositories | 80%+ (with integration tests) |
| Utilities | 70%+ |

**Total project target: 75%+**

## Common testing pitfalls

| Pitfall | Solution |
|---------|----------|
| Test doesn't use context | Pass `context.Background()` or timeout context |
| Mock not verified | Use `mock.AssertExpectations(t)` |
| Goroutine leaks in test | Test cleanup → `defer app.Stop()` |
| Flaky timeout tests | Use generous timeouts (100ms) for CI |
| Global state between tests | Use subtests `t.Run()` or test tables |
| Hardcoded paths in tests | Use `testdata/` directory |
| No test database isolation | Wrap each test in transaction → rollback |

## Testing checklist before commit

```
[ ] All public functions have tests
[ ] Table-driven tests used for multiple scenarios
[ ] Edge cases covered (nil, empty, timeout)
[ ] Context timeout tests exist
[ ] Goroutine leak tests exist (if goroutines used)
[ ] go test ./... passes
[ ] go test -race ./... passes (NO RACES)
[ ] Coverage >= 75%
[ ] Integration tests skip in short mode (testing.Short())
[ ] Mocks verify expectations (AssertExpectations)
[ ] No TODOs or pending tests in committed code
```

---

**Version:** 1.0  
**Updated:** 2026-10-06  
**Depends on:** pattern-development-go.md (Section 5)
