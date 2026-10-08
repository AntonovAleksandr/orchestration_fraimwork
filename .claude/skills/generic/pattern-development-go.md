---
name: pattern-development-go
version: 1.0.0
layer: generic
platform: Go
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---

# 🐹 pattern-development-go.md

**Категория:** [PATTERNS] Go-специфичная разработка  
**Используется:** разработчиками Go сервисов в `platform-new/`  
**Версия:** 1.0  
**Статус:** Production-ready  
**Основа:** pattern-development-flow.md (7 шагов) + Go-специфичные расширения

---

## 📋 Описание

**Явный паттерн разработки на Go** — как разработчик пишет Go-код в `platform-new/` по постановке.

Разработчик **ДОЛЖЕН ВСЕГДА** следовать этим **7 обязательным шагам** (из базового паттерна) **+ 6 GO-специфичных проверок**.

Нет импровизации. Go требует внимания к goroutines, channels, error handling, и Context — этот паттерн покрывает всё.

---

## 🎯 7 обязательных шагов (базовые из pattern-development-flow.md)

### 1️⃣ ПОНИМАНИЕ (Understanding)

**Что делать:**
- Прочитать ПОЛНУЮ постановку (ЧТО, ГДЕ, КАК, РИСКИ)
- Понять требование (ЧТО нужно делать?)
- Понять сервисы (ГДЕ писать код? какой модуль?)
- Понять верификацию (КАК проверяем? unit? integration? e2e?)
- Понять риски (Какие [BLOCKER]? Есть ли конкурентность?)

**Go-специфичные вопросы на этом шаге:**

```
❓ ПАРАЛЛЕЛИЗМ: нужны ли goroutines?
   Если ДА → нужны ли channels? мьютексы?
   
❓ CONTEXT: нужна ли отмена операций (ctx.Done())?
   Если ДА → передавать context через всю цепь

❓ ERROR HANDLING: какие ошибки ожидаемы?
   SQL? Network? Timeout? Parsing?
   
❓ DEFER: нужна ли очистка ресурсов?
   Connexion pools? File handles? Goroutine cleanup?
```

**Процесс:**

```
ЧТО? "Добавить метод GetCheckoutState для checkout сервиса"
      ✅ Понял: HTTP handler + SQL query + response

ГДЕ? "platform-new/checkout/internal/handler/checkout.go"
      ✅ Понял: внутри checkout service

КАК? "Unit тесты на handler, integration с mock DB"
      ✅ Понял: Table-driven tests + TestDB

РИСКИ? "Нет конкурентности, query простой"
      ✅ Понял: без goroutines, простой error handling

✅ ПОНИМАНИЕ ЗАВЕРШЕНО → шаг 2
```

---

### 2️⃣ ПЛАН (Planning)

**Что делать:**
- Какие файлы трогаем? (какие пакеты?)
- Какой порядок имплементации? (domain → repo → service → handler)
- Какие есть зависимости? (DB, logger, external APIs?)
- Есть ли [NB] вопросы? (миграции? protobuf? код-генерация?)
- GO-СПЕЦИФИЧНО: нужны ли новые goroutines? channels? sync primitives?

**Процесс:**

```
Файлы:
✅ platform-new/checkout/internal/model/checkout.go (domain)
✅ platform-new/checkout/internal/repository/checkout.go (DB)
✅ platform-new/checkout/internal/service/checkout.go (бизнес-логика)
✅ platform-new/checkout/internal/handler/checkout.go (HTTP)

Порядок:
1. Model (структура данных первой)
2. Repository (SQL запросы, от модели зависит)
3. Service (бизнес-логика, зависит от repo)
4. Handler (HTTP, зависит от service)

GO-специфичное:
✅ Использовать context.Context везде
✅ DB query имеет timeout (ctx.WithTimeout)
✅ Нет goroutines (sync операция)
✅ Error wrapping (fmt.Errorf("%w", err))

[NB] вопросы:
- Нужна ли миграция БД? → да, в migrations/
- Нужно ли регенерировать proto? → нет для этого PR
- Есть ли конкурентные тесты? → нет, но запланировать
```

---

### 3️⃣ КОД (Implementation)

**Что делать:**
- Писать код по плану
- Следовать **Go Code Style Conventions** (из projet-next code base)
- Комментарии только "ПОЧЕМУ", не "ЧТО"
- Функции ясные, ≤50 строк для handler, ≤30 строк для helpers
- **GO-специфично: всегда принимать first argument = context.Context**

**Процесс:**

```go
// ✅ ХОРОШО: функция явно принимает context
func (h *Handler) GetCheckoutState(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()  // HTTP request context
    
    // SQL query с timeout (если нужен)
    queryCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()
    
    state, err := h.service.GetState(queryCtx, checkoutID)
    if err != nil {
        // Error wrapping с контекстом
        h.logger.Error("failed to get checkout state", 
            "checkout_id", checkoutID, 
            "error", err)
        http.Error(w, "Internal Server Error", http.StatusInternalServerError)
        return
    }
    
    // Успешный ответ
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(state)
}

// ✅ ХОРОШО: вспомогательная функция с timeout
func (r *Repository) GetStateByID(ctx context.Context, id string) (*State, error) {
    // Context может быть отменён (покупатель закрыл браузер)
    row := r.db.QueryRowContext(ctx, `SELECT id, status, total FROM checkouts WHERE id = $1`, id)
    
    var s State
    if err := row.Scan(&s.ID, &s.Status, &s.Total); err != nil {
        return nil, fmt.Errorf("scan checkout state: %w", err)  // wrapping
    }
    return &s, nil
}

// ❌ ПЛОХО: нет context
func GetCheckout(id string) *State { ... }

// ❌ ПЛОХО: context не передаётся
func (r *Repository) GetState(id string) (*State, error) {
    // Может "зависнуть" если DB упадёт
    row := r.db.QueryRow(`SELECT ...`, id)
    ...
}

// ❌ ПЛОХО: error не wrapped
if err != nil {
    return nil, err  // потеря информации о пути error'а
}

// ❌ ПЛОХО: не очищена goroutine
go func() {
    time.Sleep(10 * time.Second)
    doSomething()  // может выполниться после shutdown!
}()
```

**Правила:**

1. **Context ВСЕГДА первый аргумент** (после receiver если метод)
   ```go
   func (s *Service) Checkout(ctx context.Context, order *Order) error
   func GetPrice(ctx context.Context, productID string) (float64, error)
   ```

2. **Error wrapping обязателен**
   ```go
   // ✅ Правильно: контекст сохранён
   if err != nil {
       return nil, fmt.Errorf("fetch product %s: %w", productID, err)
   }
   
   // ❌ Неправильно: контекст потерян
   if err != nil {
       return nil, errors.New("error fetching product")
   }
   ```

3. **Goroutine cleanup обязателен**
   ```go
   // ✅ Правильно: goroutine отменяется
   ctx, cancel := context.WithCancel(context.Background())
   defer cancel()
   
   go func() {
       select {
       case <-ctx.Done():
           return  // graceful shutdown
       case result := <-resultChan:
           handleResult(result)
       }
   }()
   
   // ❌ Неправильно: "orphan goroutine"
   go func() {
       time.Sleep(1 * time.Minute)
       doSomething()  // может выполниться после shutdown!
   }()
   ```

4. **Defer для очистки**
   ```go
   // ✅ Правильно
   conn, err := pool.Acquire(ctx)
   if err != nil {
       return fmt.Errorf("acquire connection: %w", err)
   }
   defer conn.Release()
   
   // ✅ Правильно: cancel timeout
   ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
   defer cancel()
   ```

5. **Нет package-level goroutines в init()**
   ```go
   // ❌ ПЛОХО: нет способа остановить
   func init() {
       go pollService()  // запустится при import
   }
   
   // ✅ ХОРОШО: явно запускается
   func (app *App) Start() error {
       app.ctx, app.cancel = context.WithCancel(context.Background())
       go app.pollService(app.ctx)
       return nil
   }
   ```

---

### 4️⃣ SECURITY (Security Checks)

**Базовые checks (из pattern-development-flow.md):**
- ✅ Нет SQL injection? (параметризованные запросы)
- ✅ Нет secrets in code? (no hardcoded passwords/tokens)
- ✅ Нет PII in logs?

**GO-СПЕЦИФИЧНЫЕ security checks:**

#### 🔒 Check 1: SQL Injection Prevention

```go
// ✅ ПРАВИЛЬНО: placeholders $1, $2
query := "SELECT * FROM orders WHERE id = $1 AND status = $2"
row := db.QueryRowContext(ctx, query, orderID, status)

// ❌ НЕПРАВИЛЬНО: string concatenation
query := fmt.Sprintf("SELECT * FROM orders WHERE id = '%s'", orderID)
row := db.QueryRowContext(ctx, query)
```

#### 🔒 Check 2: Goroutine Leaks (утечки goroutines)

Утечка = goroutine, которая продолжает работать после shutdown.

```go
// ❌ УТЕЧКА: нет способа остановить loop
go func() {
    for {
        time.Sleep(1 * time.Second)
        fetchData()
    }
}()

// ✅ ПРАВИЛЬНО: listening на context cancellation
go func() {
    ticker := time.NewTicker(1 * time.Second)
    defer ticker.Stop()
    
    for {
        select {
        case <-ctx.Done():
            return  // graceful exit
        case <-ticker.C:
            fetchData()
        }
    }
}(ctx)
```

#### 🔒 Check 3: Deadlock Prevention

```go
// ❌ DEADLOCK: оба goroutine ждут друг друга
ch := make(chan string)

go func() {
    ch <- "data"  // sender
}()

go func() {
    msg := <-ch  // receiver
    ch <- msg    // пытается писать в buffered channel = deadlock
}()

// ✅ ПРАВИЛЬНО: buffered channel или правильная синхронизация
ch := make(chan string, 1)  // buffered
// или использовать sync.WaitGroup/sync.Mutex
```

#### 🔒 Check 4: Resource Exhaustion Prevention

```go
// ❌ ОПАСНО: может создать тысячи goroutine
func (s *Service) ProcessItems(ctx context.Context, items []Item) error {
    for _, item := range items {
        go func(i Item) {
            s.process(ctx, i)
        }(item)  // 10000 goroutine = OOM!
    }
}

// ✅ ПРАВИЛЬНО: ограниченный worker pool
func (s *Service) ProcessItems(ctx context.Context, items []Item) error {
    workers := 10
    semaphore := make(chan struct{}, workers)
    
    for _, item := range items {
        select {
        case <-ctx.Done():
            return ctx.Err()
        case semaphore <- struct{}{}:
            go func(i Item) {
                defer func() { <-semaphore }()
                s.process(ctx, i)
            }(item)
        }
    }
}
```

#### 🔒 Check 5: Nil Pointer Prevention

```go
// ❌ ПАНИКА: panic если m == nil
func (m *Model) GetID() string {
    return m.ID  // nil pointer dereference
}

// ✅ ПРАВИЛЬНО: проверить nil
func (m *Model) GetID() string {
    if m == nil {
        return ""  // или return error
    }
    return m.ID
}
```

#### 🔒 Check 6: Token/Secret Management

```go
// ❌ ПЛОХО: hardcoded secret в коде
apiKey := "sk-12345abcdef"

// ❌ ПЛОХО: secret в логах
logger.Info("calling API with key", "key", apiKey)

// ✅ ПРАВИЛЬНО: из env/config
apiKey := os.Getenv("API_KEY")
if apiKey == "" {
    return errors.New("API_KEY not set")
}

// ✅ ПРАВИЛЬНО: не логируем секреты
logger.Info("calling external API", "endpoint", endpoint)
```

**Security Checklist (перед commit):**

```
[ ] Нет SQL string concatenation? (только placeholders)
[ ] Все goroutines имеют способ остановиться (ctx.Done)?
[ ] Нет deadlock-потенциальных паттернов (2+ channel writes)?
[ ] Resource pools имеют лимиты (worker pool, connection pool)?
[ ] Нет hardcoded secrets (API keys, passwords)?
[ ] Secrets не логируются?
[ ] Nil pointer checks где нужны?
```

---

### 5️⃣ ТЕСТЫ (Testing)

**Что писать:**

#### Table-Driven Tests (стандарт в Go)

```go
func TestGetCheckoutState(t *testing.T) {
    tests := []struct {
        name       string
        checkoutID string
        mockSetup  func(*mocks.MockRepository)
        wantErr    bool
        wantStatus string
    }{
        {
            name:       "valid checkout returns state",
            checkoutID: "checkout-123",
            mockSetup: func(m *mocks.MockRepository) {
                m.On("GetState", mock.Anything, "checkout-123").
                    Return(&State{ID: "checkout-123", Status: "pending"}, nil)
            },
            wantErr:    false,
            wantStatus: "pending",
        },
        {
            name:       "not found returns error",
            checkoutID: "invalid-id",
            mockSetup: func(m *mocks.MockRepository) {
                m.On("GetState", mock.Anything, "invalid-id").
                    Return(nil, sql.ErrNoRows)
            },
            wantErr: true,
        },
        {
            name:       "context timeout returns error",
            checkoutID: "slow-checkout",
            mockSetup: func(m *mocks.MockRepository) {
                m.On("GetState", mock.Anything, "slow-checkout").
                    Return(nil, context.DeadlineExceeded)
            },
            wantErr: true,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            repo := &mocks.MockRepository{}
            tt.mockSetup(repo)
            service := NewService(repo)

            state, err := service.GetState(context.Background(), tt.checkoutID)

            if (err != nil) != tt.wantErr {
                t.Fatalf("GetState() error = %v, wantErr %v", err, tt.wantErr)
            }
            if !tt.wantErr && state.Status != tt.wantStatus {
                t.Errorf("GetState() status = %v, want %v", state.Status, tt.wantStatus)
            }
        })
    }
}
```

#### Context Timeout Tests

```go
func TestCheckoutService_ContextCancellation(t *testing.T) {
    // Test что сервис корректно обработает отменённый context
    ctx, cancel := context.WithCancel(context.Background())
    cancel()  // отмена прямо сейчас

    repo := &mocks.MockRepository{}
    service := NewService(repo)

    _, err := service.GetState(ctx, "checkout-123")

    if err != context.Canceled {
        t.Errorf("expected context.Canceled, got %v", err)
    }
}
```

#### Goroutine Leak Detection

```go
func TestGoroutineLeaks(t *testing.T) {
    // Считаем goroutines в начале
    startGoroutines := runtime.NumGoroutine()

    // Запустим операцию
    app := NewApp()
    app.Start()
    
    // Какая-то работа
    time.Sleep(100 * time.Millisecond)
    
    // Остановим приложение
    app.Stop()
    
    // Дожидаемся goroutine cleanup
    time.Sleep(100 * time.Millisecond)
    
    // Проверяем что goroutines очищены
    endGoroutines := runtime.NumGoroutine()
    
    if endGoroutines > startGoroutines {
        t.Errorf("goroutine leak detected: start=%d, end=%d", 
            startGoroutines, endGoroutines)
    }
}
```

#### Integration Tests

```go
func TestCheckoutRepository_Integration(t *testing.T) {
    if testing.Short() {
        t.Skip("skipping integration test in short mode")
    }

    db := setupTestDB(t)
    defer db.Close()

    repo := NewRepository(db)
    ctx := context.Background()

    // Вставляем тестовые данные
    state := &State{ID: "checkout-123", Status: "pending", Total: 1000}
    err := repo.Create(ctx, state)
    if err != nil {
        t.Fatalf("Create() failed: %v", err)
    }

    // Проверяем что можем прочитать
    got, err := repo.GetState(ctx, "checkout-123")
    if err != nil {
        t.Fatalf("GetState() failed: %v", err)
    }

    if got.Status != "pending" {
        t.Errorf("GetState() status = %v, want pending", got.Status)
    }
}
```

**Testing Checklist:**

```
[ ] Table-driven tests для основных cases?
[ ] Edge-cases покрыты (nil, empty, timeout)?
[ ] Context-related tests (cancellation, timeout)?
[ ] Goroutine leak tests (runtime.NumGoroutine)?
[ ] Mock всех dependencies (repo, logger, external APIs)?
[ ] Coverage >80%?
[ ] Integration tests для DB/API calls?
[ ] Тесты могут запуститься параллельно (t.Parallel())?
```

---

### 6️⃣ КОММИТ (Commit)

**Что делать:**
- Правильная ветка: `feature/`, `fix/`, `refactor/`, `perf/`
- Сообщение ясное и структурированное
- Co-Authored-By добавлен
- Все тесты зелёные (`go test ./...`)
- Никаких горячих goroutine утечек
- `go vet` и `go fmt` passed

**Процесс:**

```bash
# Проверка перед коммитом
go fmt ./...              # форматирование
go vet ./...              # статический анализ
go test -race ./...       # race detector (ОБЯЗАТЕЛЕН для Go!)
go test -cover ./...      # coverage

# Проверка что нет TODO без контекста
grep -r "TODO\|FIXME" --include="*.go" .

# Если всё ОК → коммит
git commit -m "feat(checkout): добавить GetCheckoutState handler

- добавить SQL query для получения состояния
- создать handler с context timeouts
- добавить unit тесты (table-driven)
- добавить integration тесты с mock DB

Improvements:
- используется context.WithTimeout (5s) для DB queries
- все goroutines gracefully shutdown через context
- error wrapping for debugging (fmt.Errorf)
- проверены nil pointers и edge cases

Testing:
- Unit: 8 cases (valid, not found, timeout, malformed)
- Integration: Create + Get flow
- Race detector: passed
- Coverage: 88%

Co-Authored-By: Claude Haiku <noreply@anthropic.com>"
```

**Важно:** `-race` флаг ОБЯЗАТЕЛЕН для Go проектов!

---

### 7️⃣ MR (Merge Request)

**Что делать:**
- Правильный target branch (обычно `main` или `develop`)
- Описание: краткое резюме, links на tickets
- GO-специфично: отметить если есть goroutines/channels
- Все тесты зелёные в CI, включая race detector

**Процесс:**

```bash
git push origin feature/OPSOMN002-XXX

# Создать MR через GitLab
Title: "feat(checkout): добавить GetCheckoutState handler"

Description:
"## Summary
Добавляем HTTP handler для получения состояния чекаута.

## Changes
- SQL model для checkout state
- Repository layer с context timeout (5s)
- Service layer с error handling
- HTTP handler с structured logging
- Unit тесты (8 cases table-driven)
- Integration тесты

## Go-специфичные улучшения
- Используется context.Context для всех операций
- context.WithTimeout для DB queries
- Error wrapping (fmt.Errorf with %w)
- Graceful goroutine shutdown (нет goroutines в этом PR)

## Test plan
✅ Unit tests: 8 cases (go test -run TestGetCheckoutState)
✅ Integration: real DB (go test -run Integration)
✅ Race detector: passed (go test -race ./...)
✅ Coverage: 88% (go test -cover ./...)

## Performance notes
- Single DB query per request
- No blocking goroutines
- 5s timeout prevents hanging requests

/cc @go-team

Closes OPSOMN002-XXX"

✅ MR ГОТОВ → передаём Ревьюерам
```

---

## 🔧 GO-СПЕЦИФИЧНЫЕ РАСШИРЕНИЯ (6 дополнительных проверок)

Эти 6 проверок ДОБАВЛЯЮТСЯ к базовым 7 шагам из pattern-development-flow.md.

### ✅ Check 1: Context Propagation

**Перед коммитом убедись что:**

```
[ ] Все функции, которые делают I/O, принимают context.Context первым аргументом?
[ ] Context передаётся в DB queries (QueryRowContext, ExecContext)?
[ ] Context передаётся в HTTP calls (req.WithContext)?
[ ] Context передаётся в goroutines (channel или arg)?
[ ] Есть context.WithTimeout для операций которые могут висеть?
```

### ✅ Check 2: Goroutine Lifecycle

**Перед коммитом убедись что:**

```
[ ] Каждая запущенная goroutine имеет способ остановиться (ctx.Done или явный сигнал)?
[ ] Используется sync.WaitGroup для ожидания completion?
[ ] Нет "orphan goroutines" которые могут выполниться после shutdown?
[ ] Тесты проверяют что goroutines корректно завершаются?
[ ] Используется -race флаг в CI?
```

### ✅ Check 3: Error Handling & Logging

**Перед коммитом убедись что:**

```
[ ] Все errors wrapped с fmt.Errorf("%w", err)?
[ ] Логируются структурированные поля (не одна большая строка)?
[ ] PII не логируется (passwords, tokens, emails)?
[ ] Используется logger.WithContext для trace propagation?
[ ] Систематизирован log level (Info, Error, Debug)?
```

### ✅ Check 4: Resource Management

**Перед коммитом убедись что:**

```
[ ] DB connections возвращаются в пул (defer)?
[ ] File handles закрываются (defer file.Close())?
[ ] Goroutine pools имеют лимиты (semaphore pattern)?
[ ] Нет утечек памяти (особенно maps/slices, которые растут бесконечно)?
[ ] Тесты проверяют resource cleanup?
```

### ✅ Check 5: Concurrency Safety

**Перед коммитом убедись что:**

```
[ ] Shared data защищено (sync.Mutex, sync.RWMutex, или atomic)?
[ ] Нет data races (проверено go test -race)?
[ ] Нет race conditions (особенно в initialization)?
[ ] Если используются channels, то без потенциальных deadlocks?
[ ] Тесты включают race detector (-race флаг)?
```

### ✅ Check 6: Dependencies & Interfaces

**Перед коммитом убедись что:**

```
[ ] Используются interfaces для mock-ирования в тестах?
[ ] Dependency injection (передаются как аргументы, не глобалы)?
[ ] Нет circular dependencies между пакетами?
[ ] External dependencies явно в go.mod?
[ ] Версии зафиксированы (go mod tidy)?
```

---

## 📚 Полный пример: HTTP Handler с DB Query

```go
// checkout/internal/model/checkout.go
package model

type State struct {
    ID     string
    Status string  // pending, processing, completed
    Total  float64
}

// checkout/internal/repository/checkout.go
package repository

import (
    "context"
    "database/sql"
    "fmt"
    "time"

    "myproject/checkout/internal/model"
)

type CheckoutRepository interface {
    GetState(ctx context.Context, id string) (*model.State, error)
}

type repository struct {
    db *sql.DB
}

func (r *repository) GetState(ctx context.Context, id string) (*model.State, error) {
    // Context с таймаутом
    queryCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()

    var state model.State
    
    // Параметризованный query (безопасно от injection)
    err := r.db.QueryRowContext(queryCtx,
        `SELECT id, status, total FROM checkouts WHERE id = $1`,
        id,
    ).Scan(&state.ID, &state.Status, &state.Total)

    if err != nil {
        if err == sql.ErrNoRows {
            // Не найдено - это нормально (не ошибка приложения)
            return nil, fmt.Errorf("checkout not found: %w", err)
        }
        // Другие ошибки DB (connection, parsing, etc)
        return nil, fmt.Errorf("query checkout state: %w", err)
    }

    return &state, nil
}

// checkout/internal/service/checkout.go
package service

import (
    "context"
    "fmt"

    "myproject/checkout/internal/model"
    "myproject/checkout/internal/repository"
    "myproject/pkg/logger"
)

type CheckoutService struct {
    repo   repository.CheckoutRepository
    logger logger.Logger
}

func (s *CheckoutService) GetState(ctx context.Context, id string) (*model.State, error) {
    // Логируем начало операции
    s.logger.Info("fetching checkout state", "checkout_id", id)

    // Вызываем репозиторий (context пробрасывается)
    state, err := s.repo.GetState(ctx, id)
    if err != nil {
        s.logger.Error("failed to get checkout state",
            "checkout_id", id,
            "error", err)
        return nil, fmt.Errorf("get checkout state: %w", err)
    }

    s.logger.Info("checkout state retrieved",
        "checkout_id", id,
        "status", state.Status)
    
    return state, nil
}

// checkout/internal/handler/checkout.go
package handler

import (
    "encoding/json"
    "net/http"

    "myproject/checkout/internal/service"
    "myproject/pkg/logger"
)

type CheckoutHandler struct {
    service service.CheckoutService
    logger  logger.Logger
}

func (h *CheckoutHandler) GetState(w http.ResponseWriter, r *http.Request) {
    // Context от HTTP request уже включает deadline от client
    ctx := r.Context()

    // Извлекаем parameter из URL (обычно из gorilla/mux или другого router)
    checkoutID := r.URL.Query().Get("id")
    if checkoutID == "" {
        http.Error(w, "missing checkout id", http.StatusBadRequest)
        return
    }

    // Вызываем сервис
    state, err := h.service.GetState(ctx, checkoutID)
    if err != nil {
        // Логируем ошибку но не выдаём детали клиенту
        h.logger.Error("handler get state failed", "error", err)
        http.Error(w, "Internal Server Error", http.StatusInternalServerError)
        return
    }

    // Успешный ответ
    w.Header().Set("Content-Type", "application/json")
    if err := json.NewEncoder(w).Encode(state); err != nil {
        h.logger.Error("failed to encode response", "error", err)
    }
}

// checkout/internal/handler/checkout_test.go
package handler

import (
    "context"
    "encoding/json"
    "net/http"
    "net/http/httptest"
    "testing"

    "myproject/checkout/internal/model"
    "myproject/mocks"
)

func TestGetState(t *testing.T) {
    tests := []struct {
        name        string
        checkoutID  string
        mockResult  *model.State
        mockErr     error
        wantStatus  int
        wantBody    *model.State
    }{
        {
            name:       "valid checkout",
            checkoutID: "co-123",
            mockResult: &model.State{ID: "co-123", Status: "pending", Total: 1000},
            mockErr:    nil,
            wantStatus: http.StatusOK,
            wantBody:   &model.State{ID: "co-123", Status: "pending", Total: 1000},
        },
        {
            name:       "checkout not found",
            checkoutID: "invalid",
            mockResult: nil,
            mockErr:    fmt.Errorf("not found"),
            wantStatus: http.StatusInternalServerError,
        },
        {
            name:       "missing id parameter",
            checkoutID: "",
            wantStatus: http.StatusBadRequest,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            // Prepare mock service
            mockService := &mocks.MockCheckoutService{}
            if tt.checkoutID != "" {
                mockService.On("GetState", mock.Anything, tt.checkoutID).
                    Return(tt.mockResult, tt.mockErr)
            }

            handler := &CheckoutHandler{
                service: mockService,
                logger:  mocks.NewMockLogger(),
            }

            // Create request
            url := "http://localhost:8080/checkout/state"
            if tt.checkoutID != "" {
                url += "?id=" + tt.checkoutID
            }
            req, _ := http.NewRequest("GET", url, nil)

            // Record response
            rec := httptest.NewRecorder()
            handler.GetState(rec, req)

            // Check status
            if rec.Code != tt.wantStatus {
                t.Errorf("status = %d, want %d", rec.Code, tt.wantStatus)
            }

            // Check body if success
            if tt.wantStatus == http.StatusOK {
                var got model.State
                if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
                    t.Fatalf("failed to parse response: %v", err)
                }
                if got.ID != tt.wantBody.ID {
                    t.Errorf("response id = %s, want %s", got.ID, tt.wantBody.ID)
                }
            }
        })
    }
}

// Тест с context cancellation
func TestGetState_ContextCancellation(t *testing.T) {
    mockService := &mocks.MockCheckoutService{}
    mockService.On("GetState", mock.MatchedBy(func(ctx context.Context) bool {
        // Mock должен получить отменённый context
        select {
        case <-ctx.Done():
            return true
        default:
            return false
        }
    }), "co-123").Return(nil, context.Canceled)

    handler := &CheckoutHandler{
        service: mockService,
        logger:  mocks.NewMockLogger(),
    }

    // Create request с отменённым context
    req := httptest.NewRequest("GET", "http://localhost:8080/checkout/state?id=co-123", nil)
    ctx, cancel := context.WithCancel(req.Context())
    cancel()  // Отмена прямо сейчас
    req = req.WithContext(ctx)

    rec := httptest.NewRecorder()
    handler.GetState(rec, req)

    if rec.Code != http.StatusInternalServerError {
        t.Errorf("expected 500 on context cancellation, got %d", rec.Code)
    }
}
```

---

## ✨ Важные правила для GO разработчиков

### Правило 1: Context ВСЕГДА первый аргумент

```go
// ✅ ПРАВИЛЬНО
func (s *Service) Process(ctx context.Context, data string) error

// ❌ НЕПРАВИЛЬНО
func (s *Service) Process(data string) error
func (s *Service) Process(data string, ctx context.Context) error
```

### Правило 2: Error wrapping обязателен

```go
// ✅ ПРАВИЛЬНО
return fmt.Errorf("parse order %s: %w", orderID, err)

// ❌ НЕПРАВИЛЬНО
return err
return errors.New("parse error")
return fmt.Errorf("parse order: error")
```

### Правило 3: Goroutine cleanup обязателен

Каждая запущенная goroutine ДОЛЖНА иметь graceful shutdown!

```go
// ✅ ПРАВИЛЬНО
for {
    select {
    case <-ctx.Done():
        return
    case work := <-workChan:
        process(work)
    }
}

// ❌ НЕПРАВИЛЬНО
for {
    work := <-workChan  // зависнет если channel закрыт
    process(work)
}
```

### Правило 4: -race флаг ОБЯЗАТЕЛЕН в CI

```bash
# Local development
go test -race ./...

# CI/CD pipeline
go test -race -coverprofile=coverage.out ./...
```

### Правило 5: No package-level state в goroutines

```go
// ❌ ПЛОХО: package-level goroutine
var done = make(chan bool)

func init() {
    go func() {
        pollService()
    }()
}

// ✅ ПРАВИЛЬНО: explicit lifecycle
type App struct {
    ctx context.Context
    cancel context.CancelFunc
}

func (a *App) Start() {
    a.ctx, a.cancel = context.WithCancel(context.Background())
    go a.pollService()
}

func (a *App) Stop() {
    a.cancel()
}
```

---

## 🚀 Как использовать

1. **Получил постановку?** → Загрузить этот файл
2. **Начинаешь писать код?** → Следовать 7 основных шагов + 6 Go-проверок
3. **Перед коммитом?** → Пройти все 6 Go-специфичных чеклистов
4. **Перед MR?** → Убедиться что `-race` passed в CI

---

## 📋 Чеклист готовности

```
ШАГ 1: ПОНИМАНИЕ
[ ] Прочитал полную постановку
[ ] Определил file structure (domain → repo → service → handler)
[ ] Определил нужны ли goroutines/channels
[ ] Нет [BLOCKER] вопросов

ШАГ 2: ПЛАН
[ ] Определены все файлы
[ ] Определён порядок реализации
[ ] GO: определены context timeout точки
[ ] GO: определены goroutine lifecycle

ШАГ 3: КОД
[ ] Код написан и форматирован (go fmt)
[ ] Все функции I/O принимают context первым
[ ] Error wrapping везде (fmt.Errorf)
[ ] Nill pointers проверены
[ ] Resource cleanup (defer)

ШАГ 4: SECURITY
[ ] SQL injection prevented (placeholders)
[ ] Goroutine leaks prevented (lifecycle)
[ ] Deadlock prevention (channel usage)
[ ] Resource exhaustion prevented (pool limits)
[ ] Secrets not in code/logs

ШАГ 5: ТЕСТЫ
[ ] Table-driven tests написаны
[ ] Edge cases покрыты
[ ] Context timeout tests есть
[ ] Goroutine leak tests есть
[ ] Coverage >80%
[ ] go test -race passed

ШАГ 6: КОММИТ
[ ] go fmt пройден
[ ] go vet пройден
[ ] go test -race пройден
[ ] Сообщение коммита ясное
[ ] Co-Authored-By добавлен

ШАГ 7: MR
[ ] Target branch правильный (main/develop)
[ ] Описание полное и структурировано
[ ] Отмечены GO-специфичные улучшения
[ ] Все CI checks зелёные (включая -race)
```

---

## 🎓 Полный пример workflow

```
ЗАДАЧА: Добавить endpoint GET /checkout/{id}/state

ШАГ 1: ПОНИМАНИЕ ✅
- Требуется SQL query к checkout state
- Синхронная операция (без goroutines)
- Может быть timeout если DB медленный
- Нужна ошибка обработка (not found, timeout)

ШАГ 2: ПЛАН ✅
- Model (State struct)
- Repository (GetState query + context timeout)
- Service (GetState with logging)
- Handler (HTTP GET /checkout/{id}/state)
- Tests (8 cases table-driven + timeout)

ШАГ 3: КОД ✅
- Написано 4 файла
- Context.WithTimeout(5s) для DB query
- Error wrapping везде
- Nil checks для ID

ШАГ 4: SECURITY ✅
- SQL query с placeholders ($1)
- Нет hardcoded values
- PII (id) не логируется
- Secrets not in code
- Context timeout prevents hanging

ШАГ 5: ТЕСТЫ ✅
- 8 unit tests (table-driven)
- 1 context timeout test
- 1 context cancellation test
- Coverage: 88%
- go test -race: PASSED

ШАГ 6: КОММИТ ✅
$ go fmt ./...
$ go vet ./...
$ go test -race ./...
$ git commit -m "feat(checkout): добавить GetState endpoint..."

ШАГ 7: MR ✅
- Target: main
- Описание полное
- CI: все зелёные
- -race: PASSED
```

---

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Статус:** Production-ready  
**Автор:** Claude Haiku 4.5 + Antonov Aleksandr (Outsource)

---

## 📚 Ссылки

- **Базовый паттерн:** pattern-development-flow.md
- **Go best practices:** https://golang.org/doc/effective_go
- **Context guide:** https://go.dev/blog/context
- **Race detector:** https://golang.org/doc/articles/race_detector
