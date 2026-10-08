---
name: develop-gloriaots-testing
version: 1.0.0
layer: stack
platform: Gloria OTS
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# Develop Gloria OTS Testing

Тестирование Gloria OTS с использованием xUnit + Moq + InMemory EF Core.

## Test Project Structure

```
GloriaOTS.Tests/
├── Unit/
│   ├── Services/
│   │   ├── ShipmentServiceTests.cs
│   │   ├── OrderServiceTests.cs
│   │   └── ShipmentServiceFacadeTests.cs
│   ├── Repositories/
│   │   └── OrderRepositoryTests.cs
│   └── Handlers/
│       └── OrderShippedEventHandlerTests.cs
├── Integration/
│   ├── OrderApiTests.cs
│   ├── ShipmentsApiTests.cs
│   └── Database/
│       └── MigrationTests.cs
├── Fixtures/
│   ├── OrdersDbContextFixture.cs
│   ├── MigrationFixture.cs
│   └── TestDataBuilder.cs
└── GloriaOTS.Tests.csproj
```

## Unit Tests - Moq Pattern

### Service Unit Tests

```csharp
using Xunit;
using Moq;
using GloriaOTS.ApplicationCore.Interfaces.TKManager;
using GloriaOTS.ApplicationCore.DTOs;
using GloriaOTS.Infrastructure.Services.ShipmentServices;

namespace GloriaOTS.Tests.Unit.Services
{
  public class DpdShipmentServiceTests
  {
    private readonly Mock<HttpClient> _mockHttpClient;
    private readonly Mock<IOptions<DpdApiSettings>> _mockSettings;
    private readonly Mock<ILogger<DpdShipmentService>> _mockLogger;
    private readonly DpdShipmentService _service;
    
    public DpdShipmentServiceTests()
    {
      _mockHttpClient = new Mock<HttpClient>();
      _mockSettings = new Mock<IOptions<DpdApiSettings>>();
      _mockLogger = new Mock<ILogger<DpdShipmentService>>();
      
      _mockSettings.Setup(s => s.Value).Returns(new DpdApiSettings
      {
        ApiUrl = "https://api.dpd.test",
        ApiKey = "test-key",
        TimeoutSeconds = 30
      });
      
      _service = new DpdShipmentService(
        _mockHttpClient.Object,
        _mockSettings.Object,
        _mockLogger.Object);
    }
    
    [Fact]
    public async Task CreateShipmentAsync_WithValidRequest_ReturnsSuccessResult()
    {
      // Arrange
      var request = new ShipmentRequest
      {
        OrderId = 123,
        SenderCity = "Moscow",
        RecipientCity = "SPB",
        Weight = 5.5m
      };
      
      var dpdResponse = new { TrackingNumber = "DPD123456", EstimatedDelivery = "2026-09-05" };
      
      _mockHttpClient
        .Setup(h => h.PostAsJsonAsync(
          It.IsAny<string>(),
          It.IsAny<object>(),
          It.IsAny<CancellationToken>()))
        .ReturnsAsync(new HttpResponseMessage
        {
          StatusCode = HttpStatusCode.OK,
          Content = new StringContent(JsonSerializer.Serialize(dpdResponse))
        });
      
      // Act
      var result = await _service.CreateShipmentAsync(request);
      
      // Assert
      Assert.True(result.IsSuccess);
      Assert.Equal("DPD123456", result.TrackingNumber);
      Assert.Equal(ShipmentService.DPD, result.Carrier);
      
      _mockHttpClient.Verify(
        h => h.PostAsJsonAsync(
          It.IsAny<string>(),
          It.IsAny<object>(),
          It.IsAny<CancellationToken>()),
        Times.Once);
    }
    
    [Fact]
    public async Task CreateShipmentAsync_WhenApiReturns500_ReturnsFailureResult()
    {
      // Arrange
      var request = new ShipmentRequest { OrderId = 123, SenderCity = "Moscow" };
      
      _mockHttpClient
        .Setup(h => h.PostAsJsonAsync(It.IsAny<string>(), It.IsAny<object>(), It.IsAny<CancellationToken>()))
        .ReturnsAsync(new HttpResponseMessage
        {
          StatusCode = HttpStatusCode.InternalServerError,
          Content = new StringContent("API Error")
        });
      
      // Act
      var result = await _service.CreateShipmentAsync(request);
      
      // Assert
      Assert.False(result.IsSuccess);
      Assert.Contains("DPD API error", result.ErrorMessage);
    }
    
    [Fact]
    public async Task CreateShipmentAsync_WhenTimeoutOccurs_ReturnsFailureResult()
    {
      // Arrange
      var request = new ShipmentRequest { OrderId = 123, SenderCity = "Moscow" };
      
      _mockHttpClient
        .Setup(h => h.PostAsJsonAsync(It.IsAny<string>(), It.IsAny<object>(), It.IsAny<CancellationToken>()))
        .ThrowsAsync(new OperationCanceledException("Timeout"));
      
      // Act
      var result = await _service.CreateShipmentAsync(request);
      
      // Assert
      Assert.False(result.IsSuccess);
      Assert.Contains("timeout", result.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }
    
    [Theory]
    [InlineData(null)]
    [InlineData("")]
    public async Task GetTrackingStatusAsync_WithInvalidTrackingNumber_ThrowsArgumentException(string invalidNumber)
    {
      // Act & Assert
      await Assert.ThrowsAsync<ArgumentException>(
        () => _service.GetTrackingStatusAsync(invalidNumber));
    }
  }
}
```

## Integration Tests - InMemory Database

### Database Integration Tests

```csharp
public class OrderRepositoryIntegrationTests : IAsyncLifetime
{
  private readonly OrdersDbContext _dbContext;
  private readonly OrderRepository _repository;
  
  public OrderRepositoryIntegrationTests()
  {
    var options = new DbContextOptionsBuilder<OrdersDbContext>()
      .UseInMemoryDatabase($"test-{Guid.NewGuid()}")
      .Options;
    
    _dbContext = new OrdersDbContext(options);
    _repository = new OrderRepository(_dbContext);
  }
  
  public async Task InitializeAsync()
  {
    await _dbContext.Database.EnsureCreatedAsync();
    await SeedTestDataAsync();
  }
  
  public async Task DisposeAsync()
  {
    await _dbContext.Database.EnsureDeletedAsync();
    await _dbContext.DisposeAsync();
  }
  
  private async Task SeedTestDataAsync()
  {
    var orders = new[]
    {
      new Order { OrderId = 1, OrderNumber = "ORD-001", Status = OrderStatus.PENDING, CreatedAt = DateTime.UtcNow },
      new Order { OrderId = 2, OrderNumber = "ORD-002", Status = OrderStatus.SHIPPED, CreatedAt = DateTime.UtcNow.AddDays(-1) },
      new Order { OrderId = 3, OrderNumber = "ORD-003", Status = OrderStatus.DELIVERED, CreatedAt = DateTime.UtcNow.AddDays(-2) }
    };
    
    await _dbContext.Orders.AddRangeAsync(orders);
    await _dbContext.SaveChangesAsync();
  }
  
  [Fact]
  public async Task GetOrderByIdAsync_WithValidId_ReturnsOrder()
  {
    // Act
    var order = await _repository.GetByIdAsync(1);
    
    // Assert
    Assert.NotNull(order);
    Assert.Equal("ORD-001", order.OrderNumber);
  }
  
  [Fact]
  public async Task GetOrdersByStatusAsync_WithPendingStatus_ReturnsMatchingOrders()
  {
    // Act
    var orders = await _repository.GetOrdersByStatusAsync(OrderStatus.PENDING);
    
    // Assert
    Assert.Single(orders);
    Assert.Equal(OrderStatus.PENDING, orders[0].Status);
  }
  
  [Fact]
  public async Task GetOrderWithShipmentsAsync_WithValidId_IncludesShipments()
  {
    // Arrange
    var order = await _dbContext.Orders.FindAsync(1);
    var shipment = new Shipment { OrderId = 1, TrackingNumber = "DPD123" };
    _dbContext.Shipments.Add(shipment);
    await _dbContext.SaveChangesAsync();
    
    // Act
    var result = await _repository.GetOrderWithShipmentsAsync(1);
    
    // Assert
    Assert.NotNull(result);
    Assert.NotEmpty(result.Shipments);
    Assert.Equal("DPD123", result.Shipments.First().TrackingNumber);
  }
}
```

## API Endpoint Tests

```csharp
public class OrdersApiTests : IAsyncLifetime
{
  private readonly WebApplicationFactory<Program> _factory;
  private readonly HttpClient _client;
  private OrdersDbContext _dbContext;
  
  public OrdersApiTests()
  {
    _factory = new WebApplicationFactory<Program>();
    _client = _factory.CreateClient();
  }
  
  public async Task InitializeAsync()
  {
    // Setup test database
    using var scope = _factory.Services.CreateScope();
    _dbContext = scope.ServiceProvider.GetRequiredService<OrdersDbContext>();
    await _dbContext.Database.EnsureCreatedAsync();
    await SeedTestData();
  }
  
  public async Task DisposeAsync()
  {
    await _dbContext.Database.EnsureDeletedAsync();
    _dbContext.Dispose();
  }
  
  private async Task SeedTestData()
  {
    var order = new Order { OrderNumber = "ORD-001", Status = OrderStatus.PENDING };
    _dbContext.Orders.Add(order);
    await _dbContext.SaveChangesAsync();
  }
  
  [Fact]
  public async Task GetOrder_WithValidId_Returns200()
  {
    // Act
    var response = await _client.GetAsync("/api/orders/1");
    
    // Assert
    response.EnsureSuccessStatusCode();
    var content = await response.Content.ReadAsAsync<OrderDto>();
    Assert.NotNull(content);
    Assert.Equal("ORD-001", content.OrderNumber);
  }
  
  [Fact]
  public async Task GetOrder_WithInvalidId_Returns404()
  {
    // Act
    var response = await _client.GetAsync("/api/orders/9999");
    
    // Assert
    Assert.Equal(System.Net.HttpStatusCode.NotFound, response.StatusCode);
  }
  
  [Fact]
  public async Task CreateShipment_WithValidRequest_Returns200()
  {
    // Arrange
    var createRequest = new CreateShipmentRequest
    {
      CarrierCode = "DPD",
      SenderCity = "Moscow",
      RecipientCity = "SPB"
    };
    
    // Act
    var response = await _client.PostAsJsonAsync("/api/orders/1/shipment", createRequest);
    
    // Assert
    response.EnsureSuccessStatusCode();
    var content = await response.Content.ReadAsAsync<ShipmentDto>();
    Assert.NotNull(content.TrackingNumber);
  }
}
```

## Event Handler Tests

```csharp
public class OrderShippedEventHandlerTests
{
  private readonly Mock<IOrderRepository> _mockOrderRepository;
  private readonly Mock<IEventBus> _mockEventBus;
  private readonly Mock<ILogger<OrderShippedEventHandler>> _mockLogger;
  private readonly OrderShippedEventHandler _handler;
  
  public OrderShippedEventHandlerTests()
  {
    _mockOrderRepository = new Mock<IOrderRepository>();
    _mockEventBus = new Mock<IEventBus>();
    _mockLogger = new Mock<ILogger<OrderShippedEventHandler>>();
    
    _handler = new OrderShippedEventHandler(
      _mockOrderRepository.Object,
      _mockEventBus.Object,
      _mockLogger.Object);
  }
  
  [Fact]
  public async Task HandleAsync_WithValidEvent_UpdatesOrderStatus()
  {
    // Arrange
    var @event = new OrderShippedEvent
    {
      OrderId = 1,
      TrackingNumber = "DPD123456"
    };
    
    var order = new Order { OrderId = 1, Status = OrderStatus.PENDING };
    
    _mockOrderRepository
      .Setup(r => r.GetByIdAsync(1))
      .ReturnsAsync(order);
    
    // Act
    await _handler.HandleAsync(@event);
    
    // Assert
    _mockOrderRepository.Verify(
      r => r.UpdateAsync(It.Is<Order>(o => o.Status == OrderStatus.SHIPPED)),
      Times.Once);
    
    Assert.Equal(OrderStatus.SHIPPED, order.Status);
    Assert.Equal("DPD123456", order.TrackingNumber);
  }
  
  [Fact]
  public async Task HandleAsync_WithNonexistentOrder_DoesNotThrow()
  {
    // Arrange
    var @event = new OrderShippedEvent { OrderId = 9999 };
    
    _mockOrderRepository
      .Setup(r => r.GetByIdAsync(9999))
      .ReturnsAsync((Order)null);
    
    // Act & Assert
    await _handler.HandleAsync(@event);  // Should not throw
    
    _mockOrderRepository.Verify(r => r.UpdateAsync(It.IsAny<Order>()), Times.Never);
  }
}
```

## Test Fixtures & Data Builders

### OrdersDbContextFixture

```csharp
public class OrdersDbContextFixture : IAsyncLifetime
{
  private readonly DbContextOptions<OrdersDbContext> _options;
  public OrdersDbContext DbContext { get; private set; }
  
  public OrdersDbContextFixture()
  {
    _options = new DbContextOptionsBuilder<OrdersDbContext>()
      .UseInMemoryDatabase($"test-{Guid.NewGuid()}")
      .EnableSensitiveDataLogging()
      .Options;
  }
  
  public async Task InitializeAsync()
  {
    DbContext = new OrdersDbContext(_options);
    await DbContext.Database.EnsureCreatedAsync();
  }
  
  public async Task DisposeAsync()
  {
    await DbContext.Database.EnsureDeletedAsync();
    await DbContext.DisposeAsync();
  }
}

// Usage in test class
public class OrderServiceTests : IClassFixture<OrdersDbContextFixture>
{
  private readonly OrdersDbContextFixture _fixture;
  
  public OrderServiceTests(OrdersDbContextFixture fixture)
  {
    _fixture = fixture;
  }
  
  [Fact]
  public async Task SomeTest()
  {
    var order = new Order { /* ... */ };
    _fixture.DbContext.Orders.Add(order);
    await _fixture.DbContext.SaveChangesAsync();
    
    // Test logic
  }
}
```

### TestDataBuilder

```csharp
public class OrderBuilder
{
  private int _orderId = 1;
  private string _orderNumber = "ORD-001";
  private OrderStatus _status = OrderStatus.PENDING;
  private string? _trackingNumber = null;
  
  public OrderBuilder WithOrderNumber(string number)
  {
    _orderNumber = number;
    return this;
  }
  
  public OrderBuilder WithStatus(OrderStatus status)
  {
    _status = status;
    return this;
  }
  
  public OrderBuilder WithTrackingNumber(string trackingNumber)
  {
    _trackingNumber = trackingNumber;
    return this;
  }
  
  public Order Build()
  {
    return new Order
    {
      OrderId = _orderId++,
      OrderNumber = _orderNumber,
      Status = _status,
      TrackingNumber = _trackingNumber,
      CreatedAt = DateTime.UtcNow
    };
  }
}

// Usage
[Fact]
public async Task CreateShipment_WithMultipleOrders_ProcessesAll()
{
  var orders = new[]
  {
    new OrderBuilder().WithOrderNumber("ORD-001").WithStatus(OrderStatus.PENDING).Build(),
    new OrderBuilder().WithOrderNumber("ORD-002").WithStatus(OrderStatus.SHIPPED).Build(),
    new OrderBuilder().WithOrderNumber("ORD-003").WithStatus(OrderStatus.DELIVERED).Build()
  };
  
  // Test logic
}
```

## Coverage & CI/CD

### Local Coverage Check

```bash
# Run tests with coverage
dotnet test /p:CollectCoverage=true /p:CoverageThreshold=80

# Generate coverage report
dotnet test /p:CollectCoverage=true \
  /p:CoverageFormat=opencover \
  /p:CoverageFilename=coverage.xml
```

### Coverage Validation

```xml
<!-- .csproj -->
<Target Name="ValidateCoverage" AfterTargets="Test" Condition="'$(CollectCoverage)' == 'true'">
  <Message Text="Coverage validation would go here" />
</Target>
```

### CI Pipeline (GitLab)

```yaml
test:
  stage: test
  script:
    - dotnet test /p:CollectCoverage=true /p:CoverageThreshold=80
    - dotnet test --no-build --logger "junit:test-results.xml"
  artifacts:
    reports:
      junit: test-results.xml
    expire_in: 30 days
  coverage: '/Coverage: \d+\.\d+%/'
```

## Test Organization

### Theory vs Fact

```csharp
// ✅ Use [Theory] for parameterized tests
[Theory]
[InlineData(OrderStatus.PENDING, true)]
[InlineData(OrderStatus.CANCELLED, false)]
public void CanShip_BasedOnStatus(OrderStatus status, bool expected)
{
  var order = new Order { Status = status };
  Assert.Equal(expected, order.CanShip());
}

// ✅ Use [Fact] for single scenario
[Fact]
public void OrderDefaults_AreInitializedCorrectly()
{
  var order = new Order();
  Assert.NotNull(order.CreatedAt);
}

// ❌ Don't create multiple [Fact] methods for variations
[Fact]
public void Test_WithStatusPending() { }
[Fact]
public void Test_WithStatusShipped() { }
[Fact]
public void Test_WithStatusDelivered() { }
// Use [Theory] instead!
```

## Related Skills

- **pattern-development-gloriaots** — full 7-step workflow
- **gloriaots-stack-anatomy** — architecture overview
- **gloriaots-dotnet-conventions** — C# naming and patterns
- **develop-gloriaots-infrastructure** — Infrastructure patterns
- **gloriaots-gitlab-mr-review** — review checklist

---

**Version:** 1.0  
**Platform:** Gloria OTS (.NET 10, xUnit)  
**Last Updated:** 2026-10-06
