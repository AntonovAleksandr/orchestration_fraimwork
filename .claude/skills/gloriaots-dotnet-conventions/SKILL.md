---
name: gloriaots-dotnet-conventions
description: C# and .NET coding conventions for Gloria OTS. Covers naming (PascalCase, camelCase), async/await patterns, EF Core best practices, null-safety, exception handling, DI patterns, and Xunit testing. Use when writing or reviewing C# code in platform/gloriaots/.
---

# Gloria OTS .NET / C# Conventions

Стандарты кодирования для Gloria OTS (.NET 10, ASP.NET Core, EF Core, xUnit).

## Naming Conventions

### Types (Classes, Interfaces, Enums, Records)

```csharp
// ✅ ПРАВИЛЬНО: PascalCase для public типов
public class OrderTrackingService { }
public interface IShipmentService { }
public enum ShipmentService { DPD, CDEK, RussianPost }
public record ShipmentRequest(string TrackingNumber, string CarrierCode);

// ❌ ПЛОХО
public class order_tracking_service { }
public interface shipment_service { }
public enum shipment_service { dpd, cdek }
```

### Properties and Methods

```csharp
public class Order
{
  // ✅ ПРАВИЛЬНО: PascalCase для public properties
  public int OrderId { get; set; }
  public string TrackingNumber { get; set; }
  
  // ✅ ПРАВИЛЬНО: PascalCase для methods
  public async Task<ShipmentResult> CreateShipment(ShipmentRequest request)
  {
    // ✅ camelCase для local variables
    var trackingNumber = ExtractTrackingNumber(request);
    var result = await SendToCarrier(request);
    return result;
  }
  
  // ✅ ПРАВИЛЬНО: private/protected methods also PascalCase
  private string ExtractTrackingNumber(ShipmentRequest request)
  {
    return request.TrackingNumber?.Trim() ?? string.Empty;
  }
}

// ❌ ПЛОХО
public class Order
{
  public int orderId { get; set; }  // should be PascalCase
  
  public async Task<ShipmentResult> createShipment(ShipmentRequest request)  // should be PascalCase
  {
    var TrackingNumber = ExtractTrackingNumber(request);  // should be camelCase
  }
}
```

### Fields and Constants

```csharp
public class OrderService
{
  // ✅ ПРАВИЛЬНО: private fields with underscore prefix
  private readonly IShipmentService _shipmentService;
  private readonly ILogger<OrderService> _logger;
  
  // ✅ ПРАВИЛЬНО: constants UPPER_SNAKE_CASE или PascalCase
  private const int MAX_RETRY_COUNT = 3;
  private const string ORDER_STATUS_PENDING = "PENDING";
  
  // ✅ ПРАВИЛЬНО: static readonly
  private static readonly TimeSpan SHIPMENT_TIMEOUT = TimeSpan.FromSeconds(30);
  
  public OrderService(IShipmentService shipmentService, ILogger<OrderService> logger)
  {
    _shipmentService = shipmentService;
    _logger = logger;
  }
}

// ❌ ПЛОХО
public class OrderService
{
  public IShipmentService ShipmentService;  // should be private with _
  private int maxRetryCount = 3;  // should be const
}
```

### Parameter Names

```csharp
// ✅ ПРАВИЛЬНО: camelCase для параметров
public async Task<ShipmentResult> CreateShipment(
  ShipmentRequest shipmentRequest,
  CancellationToken cancellationToken = default)
{
  // используем shipmentRequest, cancellationToken
}

// ❌ ПЛОХО
public async Task<ShipmentResult> CreateShipment(
  ShipmentRequest ShipmentRequest,  // should be camelCase
  CancellationToken CancellationToken = default)  // should be camelCase
{
}
```

## Async/Await Patterns

### Basic Rules

```csharp
// ✅ ПРАВИЛЬНО: async all the way
public async Task ProcessOrderAsync(int orderId)
{
  var order = await _db.Orders.FindAsync(orderId);
  var result = await _shipmentService.CreateShipmentAsync(order);
  await _logger.LogAsync($"Order {orderId} shipped");
}

// ❌ ПЛОХО: .Result causes deadlock
public void ProcessOrder(int orderId)
{
  var order = _db.Orders.FindAsync(orderId).Result;  // DEADLOCK RISK!
  var result = _shipmentService.CreateShipmentAsync(order).Result;  // DEADLOCK!
}

// ❌ ПЛОХО: fire-and-forget without await
public async Task ProcessOrderAsync(int orderId)
{
  var order = await _db.Orders.FindAsync(orderId);
  _shipmentService.CreateShipmentAsync(order);  // WRONG: fire-and-forget
  // continues without waiting
}

// ✅ ПРАВИЛЬНО: if intentional fire-and-forget, use _ discard + warning
public async Task ProcessOrderAsync(int orderId)
{
  var order = await _db.Orders.FindAsync(orderId);
  _ = _shipmentService.CreateShipmentAsync(order);  // intentional fire-and-forget
  // но ЛУЧШЕ: избегать fire-and-forget в production коде
}
```

### ConfigureAwait Usage

```csharp
// ✅ ПРАВИЛЬНО: use ConfigureAwait(false) in library code
public async Task<ShipmentResult> GetStatusAsync(string trackingNumber)
{
  var response = await _httpClient
    .GetAsync($"/api/status/{trackingNumber}")
    .ConfigureAwait(false);
  
  var content = await response.Content
    .ReadAsStringAsync()
    .ConfigureAwait(false);
  
  return JsonSerializer.Deserialize<ShipmentResult>(content);
}

// ℹ️ NOTE: Web/Worker код может пропустить ConfigureAwait(false),
// но рекомендуется использовать везде для consistency
```

### Method Naming with Async

```csharp
// ✅ ПРАВИЛЬНО: Async suffix для async методов
public async Task<ShipmentResult> CreateShipmentAsync(ShipmentRequest request)
{
  return await _httpClient.PostAsync(...);
}

public async Task<List<Order>> GetOrdersAsync(int customerId)
{
  return await _db.Orders
    .Where(o => o.CustomerId == customerId)
    .ToListAsync();
}

// ❌ ПЛОХО: нет Async суффикса
public async Task<ShipmentResult> CreateShipment(ShipmentRequest request) { }

// ℹ️ ИСКЛЮЧЕНИЕ: событийные методы (event handlers) не используют Async suffix
public async void OnOrderCreated(OrderCreatedEvent @event)  // OK: event handler
{
  // но ЛУЧШЕ: используй Task, не void
  public async Task OnOrderCreatedAsync(OrderCreatedEvent @event)
}
```

## Null-Safety & Optional Values

### Nullable Reference Types (C# 8+)

```csharp
// ✅ ПРАВИЛЬНО: enable nullable reference types
#nullable enable

public class Order
{
  // ✅ Non-nullable (required)
  public int OrderId { get; set; }
  public string TrackingNumber { get; set; } = string.Empty;  // default value
  
  // ✅ Nullable (optional)
  public string? CustomerNotes { get; set; }  // can be null
  
  public async Task<string?> GetTrackingUrlAsync()  // returns nullable
  {
    return await _service.GetUrlAsync(...);
  }
}

#nullable restore  // return to project default
```

### Null-Coalescing & Null-Conditional Operators

```csharp
// ✅ ПРАВИЛЬНО: null-conditional operator
var email = order?.Customer?.Email;  // returns null if any step is null

// ✅ null-coalescing for defaults
var status = order?.Status ?? OrderStatus.PENDING;
var name = shipment?.CarrierName ?? "Unknown";

// ✅ ПРАВИЛЬНО: null-coalescing assignment (C# 8+)
order.TrackingNumber ??= GenerateTrackingNumber();

// ❌ ПЛОХО: excessive null checks
if (order != null && order.Customer != null && order.Customer.Email != null)
{
  SendEmail(order.Customer.Email);
}

// ✅ ПРАВИЛЬНО: equivalent using null-conditional
if (order?.Customer?.Email is not null)
{
  SendEmail(order.Customer.Email);
}
```

## Exception Handling

### Catch Specific Exceptions

```csharp
// ✅ ПРАВИЛЬНО: catch specific exceptions
public async Task<ShipmentResult> CreateShipmentAsync(ShipmentRequest request)
{
  try
  {
    var response = await _httpClient.PostAsync(...);
    return MapResponse(response);
  }
  catch (HttpRequestException ex)  // network/HTTP error
  {
    _logger.LogError(ex, "HTTP request failed");
    return ShipmentResult.Failure("API unavailable");
  }
  catch (JsonException ex)  // JSON parsing error
  {
    _logger.LogError(ex, "Invalid response format");
    return ShipmentResult.Failure("Invalid response");
  }
  catch (OperationCanceledException ex)  // timeout
  {
    _logger.LogError(ex, "Request timeout");
    return ShipmentResult.Failure("Timeout");
  }
  // NOT: catch (Exception ex) - too broad!
}

// ❌ ПЛОХО: generic exception catch
try
{
  var result = await _service.DoSomethingAsync();
}
catch (Exception ex)  // catches EVERYTHING
{
  // can't distinguish between expected and unexpected errors
  _logger.LogError(ex, "Something failed");
}
```

### Throw or Log, Not Both (Usually)

```csharp
// ✅ ПРАВИЛЬНО: log and transform to ApplicationCore result
public async Task<ShipmentResult> CreateShipmentAsync(ShipmentRequest request)
{
  try
  {
    var response = await _httpClient.PostAsync(...);
    return MapResponse(response);
  }
  catch (HttpRequestException ex)
  {
    _logger.LogError(ex, "Shipment API failed for order {OrderId}", request.OrderId);
    return ShipmentResult.Failure("API unavailable");  // return error result
    // DON'T also throw - caller decides what to do with Failure
  }
}

// ✅ ПРАВИЛЬНО: throw for unrecoverable errors
public class OrderService
{
  private readonly IOptions<OrderServiceSettings> _settings;
  
  public OrderService(IOptions<OrderServiceSettings>? settings)
  {
    _settings = settings ?? throw new ArgumentNullException(nameof(settings));
  }
}

// ❌ ПЛОХО: log and throw (redundant)
catch (HttpRequestException ex)
{
  _logger.LogError(ex, "API failed");
  throw;  // don't throw if you already logged
}
```

## EF Core Patterns

### DbContext Usage

```csharp
// ✅ ПРАВИЛЬНО: async all the way with EF Core
public async Task<Order?> GetOrderByIdAsync(int orderId)
{
  return await _dbContext.Orders
    .AsNoTracking()
    .FirstOrDefaultAsync(o => o.OrderId == orderId);
}

public async Task<List<Order>> GetOrdersByStatusAsync(OrderStatus status)
{
  return await _dbContext.Orders
    .Where(o => o.Status == status)
    .OrderByDescending(o => o.CreatedAt)
    .ToListAsync();  // materialize server-side
}

// ✅ ПРАВИЛЬНО: use AsNoTracking for read-only queries
public async Task<decimal> GetTotalShippingCostAsync(int orderId)
{
  return await _dbContext.Orders
    .AsNoTracking()
    .Where(o => o.OrderId == orderId)
    .Select(o => o.ShippingCost)
    .FirstOrDefaultAsync();
}

// ❌ ПЛОХО: .ToList() before .Where (materializes unnecessarily)
var orders = await _dbContext.Orders.ToListAsync();  // loads ALL orders!
var expensive = orders.Where(o => o.Total > 1000).ToList();  // filters in memory
```

### Migrations & Schema

```csharp
// ✅ ПРАВИЛЬНО: use Database/SqlDeploy for migrations (not auto-migrate)
// SQL файл: Database/SqlDeploy/v202610_add_dpd_tracking.sql

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
  WHERE TABLE_NAME = 'Orders' AND COLUMN_NAME = 'DpdTrackingNumber')
BEGIN
  ALTER TABLE Orders ADD DpdTrackingNumber NVARCHAR(255) NULL;
END
GO

// Код остаётся в sync с DB schema через EF Core domain model
public class Order
{
  public int OrderId { get; set; }
  public string? DpdTrackingNumber { get; set; }  // mirror DB column
}
```

## Dependency Injection

### Constructor Injection

```csharp
// ✅ ПРАВИЛЬНО: inject via constructor
public class OrderService
{
  private readonly IShipmentService _shipmentService;
  private readonly ILogger<OrderService> _logger;
  private readonly IOptions<OrderServiceSettings> _settings;
  
  public OrderService(
    IShipmentService shipmentService,
    ILogger<OrderService> logger,
    IOptions<OrderServiceSettings> settings)
  {
    _shipmentService = shipmentService ?? throw new ArgumentNullException(nameof(shipmentService));
    _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    _settings = settings ?? throw new ArgumentNullException(nameof(settings));
  }
}

// ❌ ПЛОХО: service locator antipattern
public class OrderService
{
  private IShipmentService _shipmentService;
  
  public void SetShipmentService(IShipmentService service)
  {
    _shipmentService = service;  // setter injection - fragile!
  }
}
```

### Keyed Services

```csharp
// ✅ ПРАВИЛЬНО: register multiple implementations with keys
services.AddKeyedScoped<IShipmentService, DpdShipmentService>("dpd");
services.AddKeyedScoped<IShipmentService, CdekShipmentService>("cdek");
services.AddKeyedScoped<IShipmentService, RussianPostShipmentService>("rpost");

// Retrieve by key
public class ShipmentServiceFacade
{
  private readonly IServiceProvider _serviceProvider;
  
  public async Task<ShipmentResult> CreateShipment(Order order)
  {
    var key = ShipmentServiceHelper.GetServiceKey(order.ShipmentService);
    var service = _serviceProvider.GetRequiredKeyedService<IShipmentService>(key);
    
    return await service.CreateShipment(MapToRequest(order));
  }
}

// ❌ ПЛОХО: no keying - conflict
services.AddScoped<IShipmentService, DpdShipmentService>();
services.AddScoped<IShipmentService, CdekShipmentService>();  // overwrites previous!
```

## Logging

### What to Log

```csharp
// ✅ ПРАВИЛЬНО: log important business events and errors
public async Task<ShipmentResult> CreateShipmentAsync(ShipmentRequest request)
{
  _logger.LogInformation(
    "Creating shipment for order {OrderId} via {Carrier}",
    request.OrderId,
    request.CarrierCode);
  
  try
  {
    var result = await _shipmentService.CreateShipmentAsync(request);
    
    if (result.IsSuccess)
    {
      _logger.LogInformation(
        "Shipment created: {TrackingNumber}",
        result.TrackingNumber);
    }
    else
    {
      _logger.LogWarning(
        "Shipment creation failed for order {OrderId}: {Reason}",
        request.OrderId,
        result.ErrorMessage);
    }
    
    return result;
  }
  catch (Exception ex)
  {
    _logger.LogError(
      ex,
      "Unexpected error creating shipment for order {OrderId}",
      request.OrderId);
    throw;
  }
}

// ❌ ПЛОХО: no PII in logs
_logger.LogInformation($"Order for {customer.Email} to {customer.Address}");  // PII!

// ✅ ПРАВИЛЬНО: log only non-sensitive info
_logger.LogInformation(
  "Order {OrderId} processed for customer {CustomerId}",
  order.OrderId,
  order.CustomerId);  // no email/address/phone
```

## Comments & Documentation

### When to Comment

```csharp
// ✅ ПРАВИЛЬНО: explain WHY, not WHAT
public async Task<ShipmentResult> CreateShipmentAsync(ShipmentRequest request)
{
  // DPD API rate limit: max 100 requests per minute.
  // We implement exponential backoff to avoid throttling.
  var result = await _dpdService.CreateShipmentWithRetryAsync(request);
  
  return result;
}

// ✅ ПРАВИЛЬНО: document assumptions
public decimal CalculateDeliveryFee(Order order)
{
  // Note: Fee calculation assumes all shipments use standard 3-5 day delivery.
  // Express delivery rates must be handled separately (see GLORIA-456).
  var baseRate = order.Distance * RATE_PER_KM;
  return baseRate * order.Weight;
}

// ❌ ПЛОХО: comments that duplicate code
var total = order.Items.Sum(i => i.Price);  // sum item prices
var tax = total * TAX_RATE;  // multiply by tax rate

// ❌ ПЛОХО: commented-out code (use git history instead)
// var oldMethod = CalculateDeliveryFeeOld();
// var result = await _service.ProcessAsync();
```

## Code Organization

### Method Length

```csharp
// ✅ ПРАВИЛЬНО: small, focused methods (<30 lines typical)
public async Task<OrderProcessingResult> ProcessOrderAsync(Order order)
{
  var validation = ValidateOrder(order);
  if (!validation.IsValid) return OrderProcessingResult.Failure(validation.Error);
  
  var shipment = await CreateShipmentAsync(order);
  if (!shipment.IsSuccess) return OrderProcessingResult.Failure(shipment.Error);
  
  await NotifyCustomerAsync(order);
  
  return OrderProcessingResult.Success();
}

// Helper methods kept small and focused
private OrderValidationResult ValidateOrder(Order order)
{
  if (order.Items.Count == 0)
    return OrderValidationResult.Failure("Order must contain items");
  
  return OrderValidationResult.Success();
}

// ❌ ПЛОХО: god methods (100+ lines)
public async Task<OrderProcessingResult> ProcessOrderAsync(Order order)
{
  // validation logic
  // shipment creation
  // notification
  // email sending
  // analytics tracking
  // ... 100 more lines ...
}
```

### Constants vs Magic Values

```csharp
// ✅ ПРАВИЛЬНО: use constants for magic values
private const int MAX_RETRY_COUNT = 3;
private const int TIMEOUT_SECONDS = 30;
private static readonly TimeSpan CACHE_DURATION = TimeSpan.FromHours(1);

public async Task<ShipmentResult> CreateWithRetryAsync(ShipmentRequest request)
{
  for (int attempt = 1; attempt <= MAX_RETRY_COUNT; attempt++)
  {
    try
    {
      return await CreateShipmentAsync(request);
    }
    catch (HttpRequestException) when (attempt < MAX_RETRY_COUNT)
    {
      await Task.Delay(TimeSpan.FromSeconds(Math.Pow(2, attempt)));  // exponential backoff
    }
  }
}

// ❌ ПЛОХО: magic numbers scattered everywhere
for (int i = 1; i <= 3; i++)  // what does 3 mean?
{
  await Task.Delay(1000);  // what's 1000?
}
```

---

## Testing Conventions

See **develop-gloriaots-testing** for xUnit test patterns.

## Related Skills

- **pattern-development-gloriaots** — 7-step development workflow
- **gloriaots-stack-anatomy** — system architecture
- **gloriaots-gitlab-mr-review** — MR review checklist
- **develop-gloriaots-testing** — xUnit test patterns

---

**Version:** 1.0  
**Platform:** Gloria OTS (.NET 10)  
**Last Updated:** 2026-10-06
