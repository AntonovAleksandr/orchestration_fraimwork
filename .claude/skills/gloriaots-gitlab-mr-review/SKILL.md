---
name: SKILL
version: 1.0.0
layer: gloriaots-gitlab-mr-review
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# Gloria OTS GitLab MR Review Checklist

Используйте этот скилл для review всех MR в `gloriaots/gloriaots` репозитории.

## Core Review Points

### 1. Layering Architecture

**MUST CHECK:** Правильное распределение кода по слоям.

```
✅ ApplicationCore
   - Interfaces (IShipmentService, IWmsService, …)
   - DTOs / Models (ShipmentRequest, TrackingStatus, …)
   - Enums (ShipmentService, WarehouseType, …)
   - Events (OrderShippedEvent, OrderCancelledEvent, …)
   - ❌ НЕ ДОЛЖНО: зависимости на Infrastructure / Web / Workers

✅ Infrastructure
   - Service implementations (DpdShipmentService, CdekShipmentService, …)
   - EF Core DbContext, migrations, repositories
   - Event handlers (Handlers/ папка)
   - DI registration (DependencyInjectionExtensions.cs)
   - RabbitMQ integration (consumers, publishers)
   - ❌ НЕ ДОЛЖНО: зависимости на Web / Workers

✅ Web
   - HTTP API endpoints (Controllers/, ActionResults)
   - Configuration (Startup.cs, DI setup)
   - appsettings.json
   - Swagger/OpenAPI definitions
   - ❌ НЕ ДОЛЖНО: business logic (только HTTP handling)

✅ Workers (OrderTracking, WmsSync)
   - Background jobs (HostedServices, quartz jobs)
   - Event subscribers
   - Configuration
   - appsettings.json mirror
```

**При нарушении layering → REJECT MR.**

### 2. DI and Keyed Registration

**CHECK:** Если несколько реализаций одного интерфейса → обязательно keyed.

```csharp
// ❌ ПЛОХО: no keying
services.AddScoped<IShipmentService, DpdShipmentService>();
services.AddScoped<IShipmentService, CdekShipmentService>();  // конфликт!

// ✅ ПРАВИЛЬНО: keyed
services.AddKeyedScoped<IShipmentService, DpdShipmentService>("dpd");
services.AddKeyedScoped<IShipmentService, CdekShipmentService>("cdek");
```

**Получение в коде:**
```csharp
var service = serviceProvider.GetRequiredKeyedService<IShipmentService>(key);
```

### 3. Database Migrations

**MUST CHECK:**
- Все schema changes → новый `vXXX_*.sql` в `Database/SqlDeploy/`
- Миграции **idempotent** (safe to re-run)
- ❌ No auto-migrations on startup (GloriaOTS uses manual SqlDeploy)
- ❌ No hardcoded table/column names в коде (использовать enums/constants)

```sql
-- ✅ ПРАВИЛЬНО: idempotent
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
   WHERE TABLE_NAME = 'Orders' AND COLUMN_NAME = 'DpdTrackingNumber')
BEGIN
  ALTER TABLE Orders ADD DpdTrackingNumber NVARCHAR(255) NULL;
END
GO

-- ❌ ПЛОХО: не idempotent (fall при повторе)
ALTER TABLE Orders ADD DpdTrackingNumber NVARCHAR(255);
```

### 4. Configuration Management

**MUST CHECK:**
- ❌ Нет hardcoded values (особенно API keys, URLs, credentials)
- ✅ Все в `appsettings.json` (dev) или env vars (prod)
- ✅ Используется `IOptions<T>` pattern
- ✅ **Web и Workers имеют mirror конфиги** (оба нужны одни и те же settings)

```csharp
// ❌ ПЛОХО
private const string DPD_API_KEY = "sk_live_XXX";

// ✅ ПРАВИЛЬНО
public class DpdApiSettings
{
  public string ApiUrl { get; set; }
  public string ApiKey { get; set; }  // из env / config
  public int Timeout { get; set; }
}

// Использование
public class DpdShipmentService
{
  private readonly IOptions<DpdApiSettings> _settings;
  
  public DpdShipmentService(IOptions<DpdApiSettings> settings)
  {
    _settings = settings;
  }
  
  public async Task<ShipmentResult> CreateShipment(ShipmentRequest request)
  {
    var client = new HttpClient { Timeout = TimeSpan.FromSeconds(_settings.Value.Timeout) };
    // используем _settings.Value.ApiKey, _settings.Value.ApiUrl
  }
}
```

### 5. Security Checks

**MUST VERIFY:**

- ✅ **Нет SQL injection** — все DB запросы через EF Core (no FromSqlRaw с string interpolation)
- ✅ **Нет secrets в коде** — конфиг/env vars
- ✅ **Нет PII в логах** — не логируем Customer ID, адреса, tracking info
- ✅ **Нет hardcoded API keys/tokens**
- ✅ **XXE safe** — если парсим XML, используем XmlReader с DisableEntityExpansion
- ✅ **Async/await patterns** — нет .Result, .Wait (deadlock risk)
- ✅ **Path operations safe** — Path.Combine, Path.GetFileName validation

```csharp
// ❌ ПЛОХО: SQL injection
var orders = context.Orders
  .FromSqlRaw($"SELECT * FROM Orders WHERE Number = '{number}'")
  .ToList();

// ✅ ПРАВИЛЬНО: parameterized (EF Core автоматически)
var orders = context.Orders
  .Where(o => o.Number == number)
  .ToList();

// ❌ ПЛОХО: PII в логе
_logger.LogInformation($"Tracking {order.CustomerEmail} for {order.Address}");

// ✅ ПРАВИЛЬНО: no sensitive data
_logger.LogInformation($"Tracking order {order.Id} status {status}");

// ❌ ПЛОХО: async deadlock
var result = service.GetStatusAsync().Result;

// ✅ ПРАВИЛЬНО: async all the way
var result = await service.GetStatusAsync();
```

### 6. Testing Coverage

**MUST VERIFY:**

- ✅ Unit tests: >80% coverage для критичных путей (services, handlers)
- ✅ Integration tests: для API вызовов, DB операций
- ✅ Handler tests: для event processing
- ✅ Mock external deps: HTTP, SQL, RabbitMQ
- ✅ xUnit + Moq (стандарт для GloriaOTS)
- ✅ InMemory EF Core для DB тестов
- ✅ No skipped tests (SkipReason → разрешить только с JIRA ticket)

```csharp
// ✅ ПРАВИЛЬНО: xUnit + Moq
[Fact]
public async Task DpdShipmentService_CreateShipment_ReturnsTrackingNumber()
{
  // Arrange
  var mockHttp = new Mock<HttpClient>();
  var settings = Options.Create(new DpdApiSettings { ApiUrl = "http://test" });
  var service = new DpdShipmentService(mockHttp.Object, settings);
  
  // Act
  var result = await service.CreateShipment(new ShipmentRequest { /* ... */ });
  
  // Assert
  Assert.NotNull(result.TrackingNumber);
  mockHttp.Verify(h => h.PostAsync(It.IsAny<string>(), It.IsAny<HttpContent>()), Times.Once);
}

// ❌ ПЛОХО: skipped test без причины
[Fact(Skip = "TODO")]
public void SomeTest() { }

// ✅ ПРАВИЛЬНО: skipped с ticket
[Fact(Skip = "GLORIA-123: waiting for API docs")]
public void SomeTest() { }
```

### 7. Code Style & Conventions

**CHECK:**
- ✅ Naming: PascalCase для classes, camelCase для locals/fields
- ✅ No magic strings (use const/enum)
- ✅ Comments only "ПОЧЕМУ", не "ЧТО"
- ✅ Methods <50 lines (if longer → break into helpers)
- ✅ No commented-out code
- ✅ Exception handling: catch specific, not generic Exception
- ✅ Null-safe operators: ?. and ?? (not null checks everywhere)

```csharp
// ❌ ПЛОХО
private const string SHIPMENT_SERVICE = "DPD";  // magic string
var orders = db.Orders.Where(o => o.Service == "DPD").ToList();

// ✅ ПРАВИЛЬНО: enum + const
public enum ShipmentService { DPD = 1, CDEK = 2, RussianPost = 3 }
var orders = db.Orders.Where(o => o.Service == ShipmentService.DPD).ToList();

// ❌ ПЛОХО: дублирующий комментарий
// Increase counter
counter++;

// ✅ ПРАВИЛЬНО: only necessary explanation
// Retry count must not exceed API limit (see GLORIA-456)
if (retryCount > MAX_RETRY) { /* ... */ }

// ❌ ПЛОХО: null checks everywhere
if (order != null && order.Customer != null && order.Customer.Email != null)
{
  SendEmail(order.Customer.Email);
}

// ✅ ПРАВИЛЬНО: null-safe
SendEmail(order?.Customer?.Email);
```

### 8. RabbitMQ Events

**CHECK:**
- ✅ Events defined in ApplicationCore (no Infrastructure/Web classes)
- ✅ Published through IEventBus
- ✅ Subscribed in correct layer (OrderTracking for background work)
- ✅ Event names: PascalCase, suffix "Event" (OrderShippedEvent, …)
- ✅ No side effects in event publishing (transactional)

```csharp
// ✅ ПРАВИЛЬНО: event in ApplicationCore
namespace GloriaOTS.ApplicationCore.Events
{
  public class OrderShippedEvent
  {
    public int OrderId { get; set; }
    public string TrackingNumber { get; set; }
  }
}

// Subscribe в Worker
public class OrderShippedEventConsumer : IEventConsumer<OrderShippedEvent>
{
  public async Task ConsumeAsync(OrderShippedEvent @event)
  {
    // уведомить OMS, отправить email, etc
  }
}
```

### 9. Version Control & MR Quality

**CHECK:**
- ✅ Branch name matches ticket (e.g., `feature/gloria-123-add-dpd-carrier`)
- ✅ Target branch correct (usually `master` for GloriaOTS)
- ✅ Commit messages clear (e.g., `feat(dpd): add DPD shipment service`)
- ✅ No merge commits (rebase before merge)
- ✅ All CI checks pass (.gitlab-ci.yml)
- ✅ Code coverage maintained (>80% for critical paths)

**Commit message format:**
```
feat(domain): brief description

Detailed explanation if needed. Reference ticket: GLORIA-XXX

Changes by layer:
- ApplicationCore: added DpdShipmentService interface
- Infrastructure: implemented DpdShipmentService
- Web: added DPD API settings in appsettings.json
- Tests: added unit tests for DpdShipmentService
```

## Checklist Template

```
LAYERING
- [ ] ApplicationCore: no Infrastructure/Web dependencies
- [ ] Infrastructure: depends only on ApplicationCore
- [ ] Web/Workers: depends on Infrastructure + ApplicationCore
- [ ] No circular dependencies

DI & REGISTRATION
- [ ] Keyed services for multiple implementations
- [ ] All services registered in DependencyInjectionExtensions.cs
- [ ] No service locator pattern (inject via constructor)

DATABASE
- [ ] Schema changes in Database/SqlDeploy/vXXX_*.sql
- [ ] Migrations are idempotent
- [ ] No auto-migrations (manual SqlDeploy)
- [ ] Reference data updated if needed

CONFIGURATION
- [ ] No hardcoded values (API keys, URLs, etc)
- [ ] IOptions<T> pattern used
- [ ] Web and Workers have mirror configs
- [ ] Secrets in config, not code

SECURITY
- [ ] No SQL injection (EF Core parameterized)
- [ ] No secrets in source code
- [ ] No PII in logs
- [ ] Async/await patterns correct (no deadlocks)
- [ ] Path operations safe

TESTING
- [ ] >80% code coverage for critical paths
- [ ] Unit tests present (>5 test cases)
- [ ] Integration tests for external APIs
- [ ] Handler tests for event processing
- [ ] No skipped tests (or justified with ticket)
- [ ] xUnit + Moq used

CODE STYLE
- [ ] PascalCase/camelCase conventions
- [ ] No magic strings (use enums/const)
- [ ] Comments only explain "why"
- [ ] Methods <50 lines
- [ ] No commented-out code
- [ ] Exception handling: specific, not generic

RABBITMQ EVENTS
- [ ] Events in ApplicationCore
- [ ] Published via IEventBus
- [ ] Subscribed in correct layer
- [ ] Event naming convention (PascalCase + Event suffix)
- [ ] No side effects in publishing

VERSION CONTROL
- [ ] Branch name matches ticket
- [ ] Target branch is master
- [ ] Commit messages clear
- [ ] No merge commits (rebase)
- [ ] All CI checks pass
- [ ] Code coverage maintained
```

## Related Skills

- **pattern-development-gloriaots** — 7-step development workflow
- **gloriaots-stack-anatomy** — system layout and architecture
- **gloriaots-dotnet-conventions** — C# naming and code style
- **develop-gloriaots-infrastructure** — Infrastructure layer patterns

---

**Version:** 1.0  
**Platform:** Gloria OTS (.NET 10)  
**Last Updated:** 2026-10-06
