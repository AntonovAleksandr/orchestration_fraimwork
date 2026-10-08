---
name: develop-gloriaots-infrastructure
description: Develop Infrastructure layer for Gloria OTS. Covers service implementations, EF Core repositories, event handlers, RabbitMQ consumers, DI keyed registration, and integration with ApplicationCore contracts. Follows layered architecture with proper dependency direction.
---

# Develop Gloria OTS Infrastructure Layer

Разработка Infrastructure слоя Gloria OTS (GloriaOTS.Infrastructure).

## Layer Responsibilities

**Infrastructure слой** — реализация контрактов из ApplicationCore:
- Service implementations (IShipmentService, IWmsService, …)
- EF Core DbContext, repositories, migrations
- Event handlers, RabbitMQ consumers
- DI registration (DependencyInjectionExtensions.cs)
- External API integrations

**Зависимости:**
- ✅ Может зависеть: ApplicationCore
- ❌ Не может зависеть: Web, Workers

## Service Implementation Pattern

### IShipmentService Example

**Interface in ApplicationCore:**

```csharp
namespace GloriaOTS.ApplicationCore.Interfaces.TKManager
{
  public interface IShipmentService
  {
    Task<ShipmentResult> CreateShipmentAsync(ShipmentRequest request);
    Task<TrackingStatus> GetTrackingStatusAsync(string trackingNumber);
    Task<CancelResult> CancelShipmentAsync(string trackingNumber);
  }
}
```

**Implementation in Infrastructure:**

```csharp
namespace GloriaOTS.Infrastructure.Services.ShipmentServices
{
  public class DpdShipmentService : IShipmentService
  {
    private readonly HttpClient _httpClient;
    private readonly IOptions<DpdApiSettings> _settings;
    private readonly ILogger<DpdShipmentService> _logger;
    
    public DpdShipmentService(
      HttpClient httpClient,
      IOptions<DpdApiSettings> settings,
      ILogger<DpdShipmentService> logger)
    {
      _httpClient = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
      _settings = settings ?? throw new ArgumentNullException(nameof(settings));
      _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }
    
    public async Task<ShipmentResult> CreateShipmentAsync(ShipmentRequest request)
    {
      if (request is null)
        throw new ArgumentNullException(nameof(request));
      
      _logger.LogInformation(
        "Creating DPD shipment for order {OrderId}",
        request.OrderId);
      
      try
      {
        // Transform ApplicationCore DTO to DPD API format
        var dpdRequest = MapToDpdRequest(request);
        
        // Call external API
        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(30));
        var response = await _httpClient.PostAsJsonAsync(
          $"{_settings.Value.ApiUrl}/shipments",
          dpdRequest,
          cancellationToken: cts.Token);
        
        // Handle HTTP errors gracefully
        if (!response.IsSuccessStatusCode)
        {
          var errorContent = await response.Content.ReadAsStringAsync(cts.Token);
          _logger.LogWarning(
            "DPD API returned {StatusCode}: {Error}",
            response.StatusCode,
            errorContent);
          
          return ShipmentResult.Failure($"DPD API error: {response.StatusCode}");
        }
        
        // Parse response
        var dpdResponse = await response.Content
          .ReadAsAsync<DpdCreateResponse>(cancellationToken: cts.Token);
        
        // Transform back to ApplicationCore DTO
        var result = MapToShipmentResult(dpdResponse);
        
        _logger.LogInformation(
          "DPD shipment created: {TrackingNumber}",
          result.TrackingNumber);
        
        return result;
      }
      catch (OperationCanceledException ex)
      {
        _logger.LogError(ex, "DPD API timeout for order {OrderId}", request.OrderId);
        return ShipmentResult.Failure("API timeout");
      }
      catch (HttpRequestException ex)
      {
        _logger.LogError(ex, "HTTP error calling DPD API for order {OrderId}", request.OrderId);
        return ShipmentResult.Failure("Network error");
      }
      catch (Exception ex)
      {
        _logger.LogError(ex, "Unexpected error creating DPD shipment for order {OrderId}", request.OrderId);
        return ShipmentResult.Failure("Internal error");
      }
    }
    
    public async Task<TrackingStatus> GetTrackingStatusAsync(string trackingNumber)
    {
      if (string.IsNullOrWhiteSpace(trackingNumber))
        throw new ArgumentException("Tracking number required", nameof(trackingNumber));
      
      try
      {
        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(30));
        var response = await _httpClient.GetAsync(
          $"{_settings.Value.ApiUrl}/shipments/{trackingNumber}",
          cancellationToken: cts.Token);
        
        if (!response.IsSuccessStatusCode)
          return TrackingStatus.Unknown();
        
        var dpdStatus = await response.Content
          .ReadAsAsync<DpdStatusResponse>(cancellationToken: cts.Token);
        
        return MapToTrackingStatus(dpdStatus);
      }
      catch (Exception ex)
      {
        _logger.LogError(ex, "Error getting DPD status for {TrackingNumber}", trackingNumber);
        return TrackingStatus.Unknown();
      }
    }
    
    public async Task<CancelResult> CancelShipmentAsync(string trackingNumber)
    {
      if (string.IsNullOrWhiteSpace(trackingNumber))
        throw new ArgumentException("Tracking number required", nameof(trackingNumber));
      
      try
      {
        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(30));
        var response = await _httpClient.DeleteAsync(
          $"{_settings.Value.ApiUrl}/shipments/{trackingNumber}",
          cancellationToken: cts.Token);
        
        if (!response.IsSuccessStatusCode)
          return CancelResult.Failure("DPD API error");
        
        _logger.LogInformation("DPD shipment cancelled: {TrackingNumber}", trackingNumber);
        return CancelResult.Success();
      }
      catch (Exception ex)
      {
        _logger.LogError(ex, "Error cancelling DPD shipment {TrackingNumber}", trackingNumber);
        return CancelResult.Failure("Cancellation failed");
      }
    }
    
    // Private mappers - transform between external API and ApplicationCore
    private DpdCreateRequestDto MapToDpdRequest(ShipmentRequest request)
    {
      return new DpdCreateRequestDto
      {
        SenderCity = request.SenderCity,
        RecipientCity = request.RecipientCity,
        Weight = request.Weight,
        // ... map all fields
      };
    }
    
    private ShipmentResult MapToShipmentResult(DpdCreateResponse response)
    {
      return ShipmentResult.Success(
        trackingNumber: response.TrackingNumber,
        carrier: ShipmentService.DPD,
        estimatedDelivery: response.EstimatedDelivery);
    }
    
    private TrackingStatus MapToTrackingStatus(DpdStatusResponse response)
    {
      return new TrackingStatus
      {
        TrackingNumber = response.TrackingNumber,
        Status = response.Status,
        UpdatedAt = response.UpdatedAt,
        Location = response.CurrentLocation
      };
    }
  }
}
```

## Repository Pattern

### Generic Repository Base

```csharp
namespace GloriaOTS.Infrastructure.Repositories
{
  public interface IRepository<T> where T : class
  {
    Task<T?> GetByIdAsync(int id);
    Task<List<T>> GetAllAsync();
    Task<List<T>> GetAsync(Expression<Func<T, bool>> predicate);
    Task AddAsync(T entity);
    Task UpdateAsync(T entity);
    Task DeleteAsync(int id);
    Task SaveChangesAsync();
  }
  
  public class Repository<T> : IRepository<T> where T : class
  {
    private readonly OrdersDbContext _dbContext;
    protected DbSet<T> DbSet => _dbContext.Set<T>();
    
    public Repository(OrdersDbContext dbContext)
    {
      _dbContext = dbContext ?? throw new ArgumentNullException(nameof(dbContext));
    }
    
    public async Task<T?> GetByIdAsync(int id)
    {
      return await DbSet.FindAsync(id);
    }
    
    public async Task<List<T>> GetAllAsync()
    {
      return await DbSet.AsNoTracking().ToListAsync();
    }
    
    public async Task<List<T>> GetAsync(Expression<Func<T, bool>> predicate)
    {
      return await DbSet.Where(predicate).AsNoTracking().ToListAsync();
    }
    
    public async Task AddAsync(T entity)
    {
      await DbSet.AddAsync(entity);
      await SaveChangesAsync();
    }
    
    public async Task UpdateAsync(T entity)
    {
      DbSet.Update(entity);
      await SaveChangesAsync();
    }
    
    public async Task DeleteAsync(int id)
    {
      var entity = await GetByIdAsync(id);
      if (entity is not null)
      {
        DbSet.Remove(entity);
        await SaveChangesAsync();
      }
    }
    
    public async Task SaveChangesAsync()
    {
      await _dbContext.SaveChangesAsync();
    }
  }
}
```

### Specialized Repository

```csharp
public interface IOrderRepository : IRepository<Order>
{
  Task<Order?> GetOrderWithShipmentsAsync(int orderId);
  Task<List<Order>> GetOrdersByStatusAsync(OrderStatus status);
}

public class OrderRepository : Repository<Order>, IOrderRepository
{
  private readonly OrdersDbContext _dbContext;
  
  public OrderRepository(OrdersDbContext dbContext) : base(dbContext)
  {
    _dbContext = dbContext;
  }
  
  public async Task<Order?> GetOrderWithShipmentsAsync(int orderId)
  {
    return await _dbContext.Orders
      .AsNoTracking()
      .Include(o => o.Shipments)
      .FirstOrDefaultAsync(o => o.OrderId == orderId);
  }
  
  public async Task<List<Order>> GetOrdersByStatusAsync(OrderStatus status)
  {
    return await _dbContext.Orders
      .AsNoTracking()
      .Where(o => o.Status == status)
      .OrderByDescending(o => o.CreatedAt)
      .ToListAsync();
  }
}
```

## Event Handlers

```csharp
namespace GloriaOTS.Infrastructure.EventHandlers
{
  public class OrderShippedEventHandler : IEventHandler<OrderShippedEvent>
  {
    private readonly IOrderRepository _orderRepository;
    private readonly IEventBus _eventBus;
    private readonly ILogger<OrderShippedEventHandler> _logger;
    
    public OrderShippedEventHandler(
      IOrderRepository orderRepository,
      IEventBus eventBus,
      ILogger<OrderShippedEventHandler> logger)
    {
      _orderRepository = orderRepository ?? throw new ArgumentNullException(nameof(orderRepository));
      _eventBus = eventBus ?? throw new ArgumentNullException(nameof(eventBus));
      _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }
    
    public async Task HandleAsync(OrderShippedEvent @event)
    {
      _logger.LogInformation(
        "Handling OrderShipped event for order {OrderId}",
        @event.OrderId);
      
      try
      {
        // Update order status
        var order = await _orderRepository.GetByIdAsync(@event.OrderId);
        if (order is null)
        {
          _logger.LogWarning("Order {OrderId} not found", @event.OrderId);
          return;
        }
        
        order.Status = OrderStatus.SHIPPED;
        order.TrackingNumber = @event.TrackingNumber;
        order.ShippedAt = DateTime.UtcNow;
        
        await _orderRepository.UpdateAsync(order);
        
        _logger.LogInformation(
          "Order {OrderId} marked as shipped with tracking {TrackingNumber}",
          @event.OrderId,
          @event.TrackingNumber);
      }
      catch (Exception ex)
      {
        _logger.LogError(ex, "Error handling OrderShipped event for order {OrderId}", @event.OrderId);
        throw;  // let event bus handle retry
      }
    }
  }
}
```

## RabbitMQ Consumers

```csharp
namespace GloriaOTS.Infrastructure.EventBus.Consumers
{
  public class OrderShippedEventConsumer : BackgroundService
  {
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<OrderShippedEventConsumer> _logger;
    
    public OrderShippedEventConsumer(
      IServiceProvider serviceProvider,
      ILogger<OrderShippedEventConsumer> logger)
    {
      _serviceProvider = serviceProvider;
      _logger = logger;
    }
    
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
      _logger.LogInformation("OrderShipped consumer started");
      
      using var scope = _serviceProvider.CreateScope();
      var eventBus = scope.ServiceProvider.GetRequiredService<IEventBus>();
      var handler = scope.ServiceProvider.GetRequiredService<IEventHandler<OrderShippedEvent>>();
      
      await eventBus.SubscribeAsync<OrderShippedEvent>(
        async @event => await handler.HandleAsync(@event),
        stoppingToken);
    }
  }
}
```

## DI Registration

```csharp
namespace GloriaOTS.Infrastructure.Extensions
{
  public static class DependencyInjectionExtensions
  {
    public static IServiceCollection AddInfrastructureServices(
      this IServiceCollection services,
      IConfiguration configuration)
    {
      // DbContext
      services.AddDbContext<OrdersDbContext>(options =>
      {
        var connectionString = configuration.GetConnectionString("Ordering")
          ?? throw new InvalidOperationException("Connection string 'Ordering' not found");
        
        options.UseSqlServer(connectionString, sqlOptions =>
        {
          sqlOptions.CommandTimeout(30);
          sqlOptions.EnableRetryOnFailure();
        });
      });
      
      // Repositories
      services.AddScoped(typeof(IRepository<>), typeof(Repository<>));
      services.AddScoped<IOrderRepository, OrderRepository>();
      services.AddScoped<IShipmentRepository, ShipmentRepository>();
      
      // Services
      services.AddScoped<IOrderService, OrderService>();
      services.AddScoped<IShipmentServiceFacade, ShipmentServiceFacade>();
      
      // Shipment services - keyed registration
      services.AddKeyedScoped<IShipmentService, DpdShipmentService>("dpd");
      services.AddKeyedScoped<IShipmentService, CdekShipmentService>("cdek");
      services.AddKeyedScoped<IShipmentService, RussianPostShipmentService>("rpost");
      
      // Configure HTTP clients for shipment services
      services.AddHttpClient<DpdShipmentService>()
        .ConfigureHttpClient((serviceProvider, client) =>
        {
          var settings = serviceProvider.GetRequiredService<IOptions<DpdApiSettings>>();
          client.BaseAddress = new Uri(settings.Value.ApiUrl);
          client.DefaultRequestHeaders.Authorization = 
            new AuthenticationHeaderValue("Bearer", settings.Value.ApiKey);
          client.Timeout = TimeSpan.FromSeconds(30);
        });
      
      // Event bus and handlers
      services.AddScoped<IEventBus, RabbitMqEventBus>();
      services.AddScoped(typeof(IEventHandler<>), typeof(EventHandler<>));
      services.AddScoped<IEventHandler<OrderShippedEvent>, OrderShippedEventHandler>();
      
      // Configuration options
      services.Configure<DpdApiSettings>(configuration.GetSection("Carriers:DPD"));
      services.Configure<CdekApiSettings>(configuration.GetSection("Carriers:CDEK"));
      
      return services;
    }
  }
}
```

## Data Seeding

```csharp
public static class DataSeeder
{
  public static async Task SeedAsync(OrdersDbContext dbContext)
  {
    if (await dbContext.ShipmentServices.AnyAsync())
      return;  // Already seeded
    
    var services = new[]
    {
      new ShipmentServiceEntity { Id = 1, Code = "DPD", Name = "DPD Express" },
      new ShipmentServiceEntity { Id = 2, Code = "CDEK", Name = "CDEK" },
      new ShipmentServiceEntity { Id = 3, Code = "RPOST", Name = "Russian Post" }
    };
    
    await dbContext.ShipmentServices.AddRangeAsync(services);
    await dbContext.SaveChangesAsync();
  }
}
```

## Related Skills

- **pattern-development-gloriaots** — full 7-step workflow
- **gloriaots-stack-anatomy** — architecture overview
- **gloriaots-dotnet-conventions** — C# naming and patterns
- **develop-gloriaots-applications** — Web/API layer
- **develop-gloriaots-database** — SQL migrations
- **gloriaots-gitlab-mr-review** — review checklist

---

**Version:** 1.0  
**Platform:** Gloria OTS (.NET 10, EF Core)  
**Last Updated:** 2026-10-06
