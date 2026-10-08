---
name: develop-gloriaots-applications
version: 1.0.0
layer: stack
platform: Gloria OTS
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# Develop Gloria OTS Web/Applications Layer

Разработка HTTP API слоя Gloria OTS (GloriaOTS.Web).

## Layer Responsibilities

**Web слой** — **ТОЛЬКО** HTTP handling:
- Controllers for HTTP endpoints
- OpenAPI/Swagger definitions
- DI configuration (register all services)
- appsettings.json (configuration from Environment)
- Hangfire dashboard (if job management)
- SignalR hubs (if real-time needed)

**Запрещено в Web слое:**
- Business logic (belongs in Infrastructure services)
- Database queries directly (use repositories/services)
- Event publishing (use Application-layer events)

## Controller Development

### Structure

```csharp
namespace GloriaOTS.Web.Controllers
{
  [ApiController]
  [Route("api/[controller]")]
  public class OrdersController : ControllerBase
  {
    private readonly IOrderService _orderService;
    private readonly ILogger<OrdersController> _logger;
    
    public OrdersController(
      IOrderService orderService,
      ILogger<OrdersController> logger)
    {
      _orderService = orderService;
      _logger = logger;
    }
    
    /// <summary>Get order details by ID</summary>
    /// <remarks>
    /// Sample request:
    ///
    ///     GET /api/orders/123
    ///
    /// </remarks>
    /// <param name="orderId">Order ID</param>
    /// <returns>Order details</returns>
    /// <response code="200">Order found</response>
    /// <response code="404">Order not found</response>
    [HttpGet("{orderId:int}")]
    [ProduceResponseType(typeof(OrderDto), StatusCodes.Status200OK)]
    [ProduceResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<OrderDto>> GetOrderAsync(int orderId)
    {
      _logger.LogInformation("Fetching order {OrderId}", orderId);
      
      var order = await _orderService.GetOrderByIdAsync(orderId);
      if (order is null)
      {
        _logger.LogWarning("Order {OrderId} not found", orderId);
        return NotFound();
      }
      
      return Ok(order);
    }
    
    /// <summary>Create new shipment for order</summary>
    /// <param name="orderId">Order ID</param>
    /// <param name="request">Shipment request</param>
    [HttpPost("{orderId:int}/shipment")]
    [ProduceResponseType(typeof(ShipmentDto), StatusCodes.Status200OK)]
    [ProduceResponseType(StatusCodes.Status400BadRequest)]
    public async Task<ActionResult<ShipmentDto>> CreateShipmentAsync(
      int orderId,
      [FromBody] CreateShipmentRequest request)
    {
      if (!ModelState.IsValid)
        return BadRequest(ModelState);
      
      _logger.LogInformation("Creating shipment for order {OrderId}", orderId);
      
      var result = await _orderService.CreateShipmentAsync(orderId, request);
      if (!result.IsSuccess)
      {
        _logger.LogWarning("Shipment creation failed: {Error}", result.Error);
        return BadRequest(new { error = result.Error });
      }
      
      return Ok(result.Data);
    }
  }
}
```

### Key Patterns

✅ **ПРАВИЛЬНО:**
- Controllers are thin (only HTTP concerns)
- Inject ILogger<T> for request/response logging
- Use async/await
- Return typed ActionResult<T> (not object)
- Add XML documentation (///) for Swagger
- Log important operations (don't log PII)

❌ **ПЛОХО:**
- Business logic in controllers
- Injecting DbContext directly
- Sync method wrappers (.Result, .Wait)
- Generic "success" responses
- No logging or error handling

## DI Registration

### Startup Configuration

```csharp
// Program.cs
var builder = WebApplication.CreateBuilder(args);

// Add services
builder.Services
  .AddControllers()
  .AddJsonOptions(options =>
  {
    options.JsonSerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
  });

// Add OpenAPI/Swagger
builder.Services.AddOpenApi();

// Add Infrastructure services
builder.Services.AddInfrastructureServices(builder.Configuration);

// Add Logging
builder.Services.AddLogging(config =>
{
  config.ClearProviders();
  config.AddConsole();
  config.AddDebug();
});

// Add Health checks
builder.Services
  .AddHealthChecks()
  .AddDbContextCheck<OrdersDbContext>()
  .AddRabbitMQ(builder.Configuration.GetConnectionString("RabbitMQ") ?? "");

// Build and run
var app = builder.Build();

if (app.Environment.IsDevelopment())
{
  app.MapOpenApi();
  app.UseSwagger();
  app.UseSwaggerUI();
}

app.MapControllers();
app.MapHealthChecks("/health");

app.Run();
```

### Register Infrastructure Services

```csharp
// Extension in Infrastructure project
namespace GloriaOTS.Infrastructure.Extensions
{
  public static class ServiceCollectionExtensions
  {
    public static IServiceCollection AddInfrastructureServices(
      this IServiceCollection services,
      IConfiguration configuration)
    {
      // Database
      services.AddDbContext<OrdersDbContext>(options =>
        options.UseSqlServer(configuration.GetConnectionString("Ordering")));
      
      // Repositories
      services.AddScoped<IOrderRepository, OrderRepository>();
      services.AddScoped<IShipmentRepository, ShipmentRepository>();
      
      // Services
      services.AddScoped<IOrderService, OrderService>();
      services.AddScoped<IShipmentServiceFacade, ShipmentServiceFacade>();
      
      // Shipment service implementations (keyed)
      services.AddKeyedScoped<IShipmentService, DpdShipmentService>("dpd");
      services.AddKeyedScoped<IShipmentService, CdekShipmentService>("cdek");
      services.AddKeyedScoped<IShipmentService, RussianPostShipmentService>("rpost");
      
      // Configuration options
      services.Configure<DpdApiSettings>(configuration.GetSection("Carriers:DPD"));
      services.Configure<CdekApiSettings>(configuration.GetSection("Carriers:CDEK"));
      
      // Event Bus (RabbitMQ)
      services.AddRabbitMQ(configuration);
      
      return services;
    }
  }
}
```

## Configuration Management

### appsettings.json

```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft": "Warning"
    }
  },
  "ConnectionStrings": {
    "Ordering": "Server=localhost;Database=gloriaots_orders;Trusted_Connection=true;",
    "Hangfire": "Server=localhost;Database=gloriaots_hangfire;Trusted_Connection=true;",
    "RabbitMQ": "amqp://guest:guest@localhost:5672/"
  },
  "Carriers": {
    "DPD": {
      "ApiUrl": "https://api.dpd.ru/v1",
      "ApiKey": "${DPD_API_KEY}",
      "TimeoutSeconds": 30
    },
    "CDEK": {
      "ApiUrl": "https://api.cdek.ru/v2",
      "ApiKey": "${CDEK_API_KEY}",
      "TimeoutSeconds": 30
    }
  },
  "RabbitMQ": {
    "HostName": "localhost",
    "Port": 5672,
    "UserName": "guest",
    "Password": "guest"
  }
}
```

### Environment Variables Override

```bash
# .env file or CI/CD
export ConnectionStrings__Ordering="Server=prod-db;Database=gj_orders;..."
export Carriers__DPD__ApiKey="sk_live_dpd_key"
export RabbitMQ__HostName="rabbitmq.prod.internal"
```

## OpenAPI/Swagger

### Documentation

```csharp
public class Program
{
  public static void Main(string[] args)
  {
    var builder = WebApplication.CreateBuilder(args);
    
    builder.Services.AddOpenApi(config =>
    {
      config.AddOperationTransformer((operation, context, cancellation) =>
      {
        operation.Description = operation.Description ?? "Add summary";
        return Task.CompletedTask;
      });
    });
    
    builder.Services.AddSwaggerGen(options =>
    {
      options.SwaggerDoc("v1", new OpenApiInfo
      {
        Title = "Gloria OTS API",
        Version = "v1",
        Description = "Order Transport System API for Gloria Jeans"
      });
      
      // Add security scheme for Bearer tokens
      options.AddSecurityDefinition("Bearer", new OpenApiSecurityScheme
      {
        Type = SecuritySchemeType.Http,
        Scheme = "bearer",
        BearerFormat = "JWT",
        Description = "JWT Authorization"
      });
      
      // Include XML comments
      var xmlFile = $"{Assembly.GetExecutingAssembly().GetName().Name}.xml";
      var xmlPath = Path.Combine(AppContext.BaseDirectory, xmlFile);
      if (File.Exists(xmlPath))
        options.IncludeXmlComments(xmlPath);
    });
  }
}
```

## Error Handling Middleware

```csharp
public class ErrorHandlingMiddleware
{
  private readonly RequestDelegate _next;
  private readonly ILogger<ErrorHandlingMiddleware> _logger;
  
  public ErrorHandlingMiddleware(RequestDelegate next, ILogger<ErrorHandlingMiddleware> logger)
  {
    _next = next;
    _logger = logger;
  }
  
  public async Task InvokeAsync(HttpContext context)
  {
    try
    {
      await _next(context);
    }
    catch (Exception ex)
    {
      _logger.LogError(ex, "Unhandled exception in pipeline");
      
      context.Response.ContentType = "application/json";
      
      if (ex is ValidationException validationEx)
      {
        context.Response.StatusCode = StatusCodes.Status400BadRequest;
        await context.Response.WriteAsJsonAsync(new { error = validationEx.Message });
      }
      else if (ex is NotFoundException notFoundEx)
      {
        context.Response.StatusCode = StatusCodes.Status404NotFound;
        await context.Response.WriteAsJsonAsync(new { error = notFoundEx.Message });
      }
      else
      {
        context.Response.StatusCode = StatusCodes.Status500InternalServerError;
        await context.Response.WriteAsJsonAsync(new { error = "Internal server error" });
      }
    }
  }
}

// Register in Program.cs
app.UseMiddleware<ErrorHandlingMiddleware>();
```

## Health Checks

```csharp
builder.Services
  .AddHealthChecks()
  .AddDbContextCheck<OrdersDbContext>(
    name: "database",
    failureStatus: HealthStatus.Unhealthy,
    tags: new[] { "db" })
  .AddRabbitMQ(
    new Uri(configuration.GetConnectionString("RabbitMQ") ?? "amqp://guest:guest@localhost"),
    name: "rabbitmq",
    tags: new[] { "messaging" });

// Endpoint
app.MapHealthChecks("/health", new HealthCheckOptions
{
  ResponseWriter = WriteHealthCheckResponse
});

app.MapHealthChecks("/health/ready", new HealthCheckOptions
{
  Predicate = healthCheck => healthCheck.Tags.Contains("ready"),
  ResponseWriter = WriteHealthCheckResponse
});
```

## Related Skills

- **pattern-development-gloriaots** — full 7-step workflow
- **gloriaots-stack-anatomy** — architecture overview
- **gloriaots-dotnet-conventions** — C# naming and patterns
- **develop-gloriaots-infrastructure** — Infrastructure layer
- **gloriaots-gitlab-mr-review** — review checklist

---

**Version:** 1.0  
**Platform:** Gloria OTS (.NET 10, ASP.NET Core)  
**Last Updated:** 2026-10-06
