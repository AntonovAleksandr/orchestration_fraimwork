---
name: develop-gloriaots-workers
description: Develop background workers for Gloria OTS (OrderTracking, WmsSync). Covers HostedServices, Hangfire jobs, RabbitMQ consumers, polling logic, status updates, cancellation flows, warehouse synchronization, and configuration mirroring between Web and Workers.
---

# Develop Gloria OTS Background Workers

Разработка фоновых воркеров Gloria OTS (GloriaOTS.OrderTracking, GloriaOTS.WmsSync).

## Worker Architecture

```
GloriaOTS.Web (HTTP API)
├── Receives order export from OMS
├── Persists to DB
└── Publishes OrderCreatedEvent

GloriaOTS.OrderTracking (Worker)
├── Subscribes OrderCreatedEvent
├── Polls carrier (DPD, CDEK, etc) for status updates
├── Updates Order.Status in DB
└── Publishes OrderStatusChangedEvent

GloriaOTS.WmsSync (Worker)
├── Subscribes to Tgw* events (warehouse/TGW)
├── Syncs inventory to WMS DB
├── Sends to 1C registry
└── One instance per warehouse (NSK, MSK, etc)
```

## OrderTracking Worker

### Program.cs Setup

```csharp
var builder = Host.CreateDefaultBuilder(args);

builder.ConfigureServices((context, services) =>
{
  // Configuration
  var configuration = context.Configuration;
  
  // DbContext (same as Web)
  services.AddDbContext<OrdersDbContext>(options =>
    options.UseSqlServer(configuration.GetConnectionString("Ordering")));
  
  // Infrastructure services
  services.AddInfrastructureServices(configuration);
  
  // RabbitMQ event bus
  services.AddRabbitMQ(configuration);
  
  // HostedServices
  services.AddHostedService<OrderStatusPollingService>();
  services.AddHostedService<OrderCancellationService>();
  
  // Logging
  services.AddLogging(config =>
  {
    config.AddConsole();
    config.AddDebug();
  });
});

var host = builder.Build();
await host.RunAsync();
```

### OrderStatusPollingService

```csharp
namespace GloriaOTS.OrderTracking.Services
{
  public class OrderStatusPollingService : BackgroundService
  {
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<OrderStatusPollingService> _logger;
    private readonly IOptions<OrderTrackingSettings> _settings;
    
    public OrderStatusPollingService(
      IServiceProvider serviceProvider,
      ILogger<OrderStatusPollingService> logger,
      IOptions<OrderTrackingSettings> settings)
    {
      _serviceProvider = serviceProvider;
      _logger = logger;
      _settings = settings;
    }
    
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
      _logger.LogInformation("OrderStatusPollingService starting");
      
      // Initial delay - let OTS stabilize
      await Task.Delay(TimeSpan.FromSeconds(5), stoppingToken);
      
      while (!stoppingToken.IsCancellationRequested)
      {
        try
        {
          await PollOrderStatusesAsync(stoppingToken);
          
          // Poll interval from config (e.g., 5 minutes)
          await Task.Delay(_settings.Value.PollingIntervalMs, stoppingToken);
        }
        catch (OperationCanceledException)
        {
          _logger.LogInformation("OrderStatusPollingService stopping");
          break;
        }
        catch (Exception ex)
        {
          _logger.LogError(ex, "Unexpected error in OrderStatusPollingService");
          // Continue polling despite errors
          await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken);
        }
      }
    }
    
    private async Task PollOrderStatusesAsync(CancellationToken cancellationToken)
    {
      using var scope = _serviceProvider.CreateScope();
      var orderRepository = scope.ServiceProvider.GetRequiredService<IOrderRepository>();
      var shipmentServiceFacade = scope.ServiceProvider.GetRequiredService<IShipmentServiceFacade>();
      var eventBus = scope.ServiceProvider.GetRequiredService<IEventBus>();
      
      // Get all orders waiting for shipment status
      var pendingOrders = await orderRepository.GetAsync(
        o => o.Status == OrderStatus.PENDING_CARRIER_RESPONSE && 
             o.TrackingNumber != null);
      
      _logger.LogInformation("Polling status for {Count} orders", pendingOrders.Count);
      
      foreach (var order in pendingOrders)
      {
        try
        {
          // Get status from carrier
          var status = await shipmentServiceFacade.GetTrackingStatusAsync(order.TrackingNumber!);
          
          // If status changed, update order and publish event
          if (status.Status != order.CurrentStatus)
          {
            order.CurrentStatus = status.Status;
            order.LastStatusUpdate = DateTime.UtcNow;
            
            await orderRepository.UpdateAsync(order);
            
            // Publish event for subscribers (e.g., to notify OMS)
            var @event = new OrderStatusChangedEvent
            {
              OrderId = order.OrderId,
              TrackingNumber = order.TrackingNumber,
              NewStatus = status.Status,
              Location = status.Location,
              UpdatedAt = DateTime.UtcNow
            };
            
            await eventBus.PublishAsync(@event);
            
            _logger.LogInformation(
              "Order {OrderId} status changed to {Status}",
              order.OrderId,
              status.Status);
          }
        }
        catch (Exception ex)
        {
          _logger.LogError(
            ex,
            "Error polling status for order {OrderId}, tracking {TrackingNumber}",
            order.OrderId,
            order.TrackingNumber);
          // Continue with next order
        }
      }
    }
  }
}
```

### Cancellation Service

```csharp
public class OrderCancellationService : BackgroundService
{
  private readonly IServiceProvider _serviceProvider;
  private readonly ILogger<OrderCancellationService> _logger;
  private readonly IOptions<OrderTrackingSettings> _settings;
  
  protected override async Task ExecuteAsync(CancellationToken stoppingToken)
  {
    _logger.LogInformation("OrderCancellationService starting");
    
    await Task.Delay(TimeSpan.FromSeconds(10), stoppingToken);
    
    while (!stoppingToken.IsCancellationRequested)
    {
      try
      {
        await ProcessCancellationsAsync(stoppingToken);
        
        await Task.Delay(
          TimeSpan.FromMinutes(_settings.Value.CancellationCheckIntervalMinutes),
          stoppingToken);
      }
      catch (OperationCanceledException)
      {
        _logger.LogInformation("OrderCancellationService stopping");
        break;
      }
      catch (Exception ex)
      {
        _logger.LogError(ex, "Error in OrderCancellationService");
        await Task.Delay(TimeSpan.FromMinutes(1), stoppingToken);
      }
    }
  }
  
  private async Task ProcessCancellationsAsync(CancellationToken cancellationToken)
  {
    using var scope = _serviceProvider.CreateScope();
    var orderRepository = scope.ServiceProvider.GetRequiredService<IOrderRepository>();
    var shipmentServiceFacade = scope.ServiceProvider.GetRequiredService<IShipmentServiceFacade>();
    
    // Get orders marked for cancellation
    var ordersToCancel = await orderRepository.GetAsync(
      o => o.Status == OrderStatus.CANCELLATION_REQUESTED &&
           o.TrackingNumber != null);
    
    _logger.LogInformation("Processing {Count} cancellation requests", ordersToCancel.Count);
    
    foreach (var order in ordersToCancel)
    {
      try
      {
        var cancelResult = await shipmentServiceFacade.CancelShipmentAsync(order.TrackingNumber!);
        
        if (cancelResult.IsSuccess)
        {
          order.Status = OrderStatus.CANCELLED;
          order.CancelledAt = DateTime.UtcNow;
          
          await orderRepository.UpdateAsync(order);
          
          _logger.LogInformation("Order {OrderId} cancelled successfully", order.OrderId);
        }
        else
        {
          _logger.LogWarning(
            "Failed to cancel order {OrderId}: {Error}",
            order.OrderId,
            cancelResult.Error);
        }
      }
      catch (Exception ex)
      {
        _logger.LogError(ex, "Error cancelling order {OrderId}", order.OrderId);
      }
    }
  }
}
```

## WmsSync Worker

### Warehouse-Specific Instances

```bash
# docker-compose.yml - one instance per warehouse
order-tracking:
  image: gloriaots/order-tracking:latest
  environment:
    - ConnectionStrings__Ordering=...
    - RabbitMQ__HostName=...

wms-sync-nsk:
  image: gloriaots/wms-sync:latest
  environment:
    - Warehouse=NSK
    - ConnectionStrings__Ordering=...
    - RabbitMQ__HostName=...

wms-sync-msk:
  image: gloriaots/wms-sync:latest
  environment:
    - Warehouse=MSK
    - ConnectionStrings__Ordering=...
    - RabbitMQ__HostName=...
```

### WmsSync Service

```csharp
namespace GloriaOTS.WmsSync.Services
{
  public class WmsSyncService : BackgroundService
  {
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<WmsSyncService> _logger;
    private readonly IOptions<WmsSyncSettings> _settings;
    
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
      var warehouse = Environment.GetEnvironmentVariable("Warehouse")
        ?? throw new InvalidOperationException("Warehouse environment variable not set");
      
      _logger.LogInformation("WmsSyncService starting for warehouse {Warehouse}", warehouse);
      
      using var scope = _serviceProvider.CreateScope();
      var eventBus = scope.ServiceProvider.GetRequiredService<IEventBus>();
      var wmsService = scope.ServiceProvider.GetRequiredService<IWmsService>();
      
      // Subscribe to TGW events (warehouse-specific)
      await eventBus.SubscribeAsync<TgwInventoryUpdatedEvent>(
        async @event => await HandleInventoryUpdateAsync(@event, wmsService, stoppingToken),
        stoppingToken);
      
      // Keep running
      while (!stoppingToken.IsCancellationRequested)
      {
        await Task.Delay(1000, stoppingToken);
      }
    }
    
    private async Task HandleInventoryUpdateAsync(
      TgwInventoryUpdatedEvent @event,
      IWmsService wmsService,
      CancellationToken cancellationToken)
    {
      _logger.LogInformation(
        "Processing TGW inventory update for SKU {Sku}",
        @event.Sku);
      
      try
      {
        // Update local DB
        await wmsService.UpdateInventoryAsync(@event, cancellationToken);
        
        // Push to 1C registry
        await wmsService.Sync1CAsync(@event.Sku, cancellationToken);
      }
      catch (Exception ex)
      {
        _logger.LogError(
          ex,
          "Error syncing inventory for SKU {Sku}",
          @event.Sku);
      }
    }
  }
}
```

## Hangfire Jobs (Optional)

```csharp
public class HangfireJobsStartup
{
  public static void Configure(IApplicationBuilder app)
  {
    RecurringJob.AddOrUpdate<OrderSyncJob>(
      job => job.SyncOrdersAsync(),
      Cron.Hourly);
    
    RecurringJob.AddOrUpdate<ReportGenerationJob>(
      job => job.GenerateDailyReportAsync(),
      "0 2 * * *");  // 2 AM daily
  }
}

public class OrderSyncJob
{
  private readonly IOrderRepository _orderRepository;
  private readonly ILogger<OrderSyncJob> _logger;
  
  public OrderSyncJob(IOrderRepository orderRepository, ILogger<OrderSyncJob> logger)
  {
    _orderRepository = orderRepository;
    _logger = logger;
  }
  
  public async Task SyncOrdersAsync()
  {
    _logger.LogInformation("Starting hourly order sync job");
    
    try
    {
      var recentOrders = await _orderRepository.GetAsync(
        o => o.UpdatedAt > DateTime.UtcNow.AddHours(-1));
      
      _logger.LogInformation("Synced {Count} orders", recentOrders.Count);
    }
    catch (Exception ex)
    {
      _logger.LogError(ex, "Order sync job failed");
    }
  }
}
```

## Configuration (appsettings.json)

```json
{
  "OrderTracking": {
    "PollingIntervalMs": 300000,
    "CancellationCheckIntervalMinutes": 30,
    "MaxRetries": 3
  },
  "WmsSync": {
    "BatchSize": 100,
    "SyncInterval": 600000
  },
  "ConnectionStrings": {
    "Ordering": "Server=localhost;Database=gloriaots_orders;",
    "Hangfire": "Server=localhost;Database=gloriaots_hangfire;"
  },
  "RabbitMQ": {
    "HostName": "localhost",
    "Port": 5672,
    "UserName": "guest",
    "Password": "guest"
  }
}
```

**ВАЖНО:** Web и Workers ДОЛЖНЫ иметь ОДИНАКОВЫЕ appsettings.json/env vars для:
- `ConnectionStrings`
- `RabbitMQ`
- `Carriers.*`
- Domain-specific settings

## Error Handling & Resilience

### Retry Logic

```csharp
// ✅ ПРАВИЛЬНО: exponential backoff with max retries
private async Task<T> ExecuteWithRetryAsync<T>(
  Func<Task<T>> operation,
  int maxRetries = 3)
{
  for (int attempt = 1; attempt <= maxRetries; attempt++)
  {
    try
    {
      return await operation();
    }
    catch (Exception ex) when (attempt < maxRetries)
    {
      var delay = TimeSpan.FromSeconds(Math.Pow(2, attempt));
      _logger.LogWarning(
        ex,
        "Attempt {Attempt} failed, retrying in {DelaySeconds}s",
        attempt,
        delay.TotalSeconds);
      
      await Task.Delay(delay);
    }
  }
  
  throw new OperationFailedException("Max retries exceeded");
}
```

### Graceful Shutdown

```csharp
// ✅ ПРАВИЛЬНО: respond to cancellation token
protected override async Task ExecuteAsync(CancellationToken stoppingToken)
{
  while (!stoppingToken.IsCancellationRequested)
  {
    try
    {
      await DoWorkAsync(stoppingToken);
      
      await Task.Delay(TimeSpan.FromMinutes(5), stoppingToken);
    }
    catch (OperationCanceledException)
    {
      _logger.LogInformation("Service gracefully stopping");
      break;
    }
  }
  
  // Cleanup if needed
  await CleanupAsync();
}
```

## Testing Workers

```csharp
[UnitTest]
public class OrderStatusPollingServiceTests
{
  [Fact]
  public async Task PollOrderStatuses_WhenOrderStatusChanged_UpdatesOrderAndPublishesEvent()
  {
    // Arrange
    var mockOrderRepository = new Mock<IOrderRepository>();
    var mockShipmentFacade = new Mock<IShipmentServiceFacade>();
    var mockEventBus = new Mock<IEventBus>();
    var logger = new Mock<ILogger<OrderStatusPollingService>>();
    
    var order = new Order { OrderId = 1, Status = OrderStatus.PENDING_CARRIER_RESPONSE };
    var newStatus = new TrackingStatus { Status = "DELIVERED" };
    
    mockOrderRepository
      .Setup(r => r.GetAsync(It.IsAny<Expression<Func<Order, bool>>>()))
      .ReturnsAsync(new List<Order> { order });
    
    mockShipmentFacade
      .Setup(s => s.GetTrackingStatusAsync(It.IsAny<string>()))
      .ReturnsAsync(newStatus);
    
    var service = new OrderStatusPollingService(mockOrderRepository.Object, ...);
    
    // Act
    await service.PollOrderStatusesAsync(CancellationToken.None);
    
    // Assert
    mockOrderRepository.Verify(r => r.UpdateAsync(It.IsAny<Order>()), Times.Once);
    mockEventBus.Verify(b => b.PublishAsync(It.IsAny<OrderStatusChangedEvent>()), Times.Once);
  }
}
```

## Related Skills

- **pattern-development-gloriaots** — full 7-step workflow
- **gloriaots-stack-anatomy** — architecture overview
- **gloriaots-dotnet-conventions** — C# naming and patterns
- **develop-gloriaots-applications** — Web/API layer
- **develop-gloriaots-infrastructure** — Infrastructure layer
- **gloriaots-gitlab-mr-review** — review checklist

---

**Version:** 1.0  
**Platform:** Gloria OTS (.NET 10, Background Services)  
**Last Updated:** 2026-10-06
