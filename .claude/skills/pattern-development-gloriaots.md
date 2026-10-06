# 💻 pattern-development-gloriaots.md

**Категория:** [PATTERNS]  
**Используется:** gloriaots-engineer  
**Версия:** 1.0  
**Статус:** Production-ready  
**Платформа:** Gloria OTS (.NET 10, ASP.NET Core, EF Core, RabbitMQ)

---

## 📋 Описание

**Явный паттерн разработки для Gloria OTS** - как разработчик пишет .NET/C# код по постановке в логистической системе Gloria Jeans.

Разработчик **ДОЛЖЕН ВСЕГДА** следовать этим 7 шагам. Нет импровизации. Специфика: **layered architecture**, EF Core миграции, RabbitMQ события, DI registration.

---

## 🎯 7 обязательных шагов для GloriaOTS

### 1️⃣ ПОНИМАНИЕ (Understanding)

**Что делать:**
- Прочитать ПОЛНУЮ постановку (ЧТО, ГДЕ, КАК, РИСКИ)
- Понять требование (какая бизнес-логика?)
- Понять в каком слое (ApplicationCore / Infrastructure / Web / Worker?)
- Понять зависимости от OMS/Integration
- Понять если нужны миграции БД
- Понять если нужны RabbitMQ события

**Процесс для GloriaOTS:**
```
ЧТО? "Добавить поддержку нового перевозчика — DPD"
      ✅ Понял: новая реализация IShipmentService

ГДЕ? "ApplicationCore (интерфейс + enum + helper)"
      "Infrastructure (сервис реализация)"
      "Web (DI регистрация)"
      "OrderTracking (конфиг + статусы)"
      ✅ Понял: 4 места в разных слоях

КАК? "Unit: трансформация статусов"
      "Integration: заказ через DPD"
      "Manual: проверка на тестовом стенде"
      ✅ Понял: как проверяем

РИСКИ? "[BLOCKER] нужна координация с Integration (mutators)"
        "[NB] DPD API может быть недоступна - mock?"
      ✅ Понял: есть зависимость от другой команды

✅ ПОНИМАНИЕ ЗАВЕРШЕНО → переход на шаг 2
```

**Если не понял:**
- Спросить gloriaots-researcher (потому что нужны интеграционные детали)
- Не начинать писать "наугад"

---

### 2️⃣ ПЛАН (Planning)

**Что делать:**
- Какие файлы трогаем и в каких слоях?
- Какой порядок: сначала контракты (ApplicationCore), потом реализация (Infrastructure), потом регистрация (DI)?
- Есть ли DB миграции?
- Есть ли RabbitMQ события?
- Есть ли зависимости между слоями?

**Процесс для GloriaOTS:**
```
Слой 1 - ApplicationCore (контракты):
✅ src/GloriaOTS.ApplicationCore/Constants/ShipmentService.cs
   → Добавить enum: DPD = 5
   
✅ src/GloriaOTS.ApplicationCore/Constants/ShipmentServiceHelper.cs
   → Добавить маппинг: "DPD" → ShipmentService.DPD
   
✅ src/GloriaOTS.ApplicationCore/Interfaces/TKManager/IShipmentService.cs
   → Интерфейс уже есть, зависит от реализации

Слой 2 - Infrastructure (реализация + DI):
✅ src/GloriaOTS.Infrastructure/Services/ShipmentServices/DpdShipmentService.cs
   → НОВЫЙ ФАЙЛ: реализация IShipmentService для DPD
   
✅ src/GloriaOTS.Infrastructure/Services/DependencyInjectionExtensions.cs
   → Добавить: services.AddKeyedScoped<IShipmentService, DpdShipmentService>("dpd")
   
✅ src/GloriaOTS.Infrastructure/Services/ShipmentServices/ShipmentServiceFacade.cs
   → Добавить маршрут: case ShipmentService.DPD → _dpd

Слой 3 - Web (конфиг):
✅ src/GloriaOTS.Web/appsettings.json
   → Добавить: "DpdApi": { "Url": "...", "Token": "..." }

Слой 4 - OrderTracking (конфиг + статусы):
✅ src/Workers/GloriaOTS.OrderTracking/appsettings.json
   → Добавить те же настройки DPD

✅ src/Workers/GloriaOTS.OrderTracking/Program.cs
   → Убедиться что ConsumeStatusUpdatesJob знает про DPD статусы

DB Миграции:
✅ Database/SqlDeploy/vXXX_add_dpd.sql
   → Если нужно: добавить enum value в reference data

RabbitMQ События:
⏳ Проверить нужны ли: OrderShippedViaDpdEvent или достаточно существующих

[NB] Вопросы:
- нужно ли возвращать TrackingUrl от DPD? → проверить DTO
- какие статусы DPD есть? → смотреть документацию DPD API
- кто обновляет в OMS? → Integration мутатор уже есть?

Порядок имплементации:
1. Enum + Helper (ApplicationCore) - базовое определение
2. IShipmentService реализация (Infrastructure) - логика
3. DI регистрация + Facade (Infrastructure) - проводка
4. Web конфиг (Web) - настройки API
5. OrderTracking конфиг (Worker) - настройки для воркера
6. DB миграция если нужна (Database) - reference data
7. Тесты (всё) - покрытие
```

---

### 3️⃣ КОД (Implementation)

**Что делать:**
- Писать код по плану, соблюдая layered архитектуру
- ApplicationCore: **нет** зависимостей на Infrastructure/Web
- Infrastructure: может зависеть на ApplicationCore, но **не** на Web/Workers
- Следовать shared-code-style для C# (naming, форматирование)
- Комментарии только "ПОЧЕМУ", не "ЧТО"
- Переменные ясные, методы <50 строк
- Использовать existing patterns из кода

**Процесс для GloriaOTS:**
```csharp
// ❌ ПЛОХО: ApplicationCore не должна знать про Infrastructure
namespace GloriaOTS.ApplicationCore.Interfaces
{
  public interface IShipmentService
  {
    // ❌ Зависит от Web-specific класса
    async Task<WebResponse> SendOrder(Order order);
  }
}

// ✅ ХОРОШО: ApplicationCore - только интерфейсы и DTOs
namespace GloriaOTS.ApplicationCore.Interfaces.TKManager
{
  public interface IShipmentService
  {
    // ✅ Зависит только от ApplicationCore-типов
    Task<ShipmentResult> CreateShipment(ShipmentRequest request);
    Task<TrackingStatus> GetTrackingStatus(string trackingNumber);
  }
}

// Реализация в Infrastructure
namespace GloriaOTS.Infrastructure.Services.ShipmentServices
{
  public class DpdShipmentService : IShipmentService
  {
    private readonly HttpClient _httpClient;
    private readonly IOptions<DpdApiSettings> _settings;
    
    public DpdShipmentService(HttpClient httpClient, IOptions<DpdApiSettings> settings)
    {
      _httpClient = httpClient;
      _settings = settings;
    }
    
    // Трансформируем DPD API response в ApplicationCore DTO
    public async Task<ShipmentResult> CreateShipment(ShipmentRequest request)
    {
      // Правилом: перевозчик API может быть down, мы должны graceful handle
      var dpdRequest = MapToCreateRequestDto(request);
      var response = await _httpClient.PostAsync(_settings.Value.Url, ...);
      
      if (!response.IsSuccessStatusCode)
      {
        // Контракт: IShipmentService вернёт ApplicationCore-Result, не HTTP-ошибку
        return ShipmentResult.Failure("DPD API unavailable");
      }
      
      var dpdResponse = await response.Content.ReadAsAsync<DpdCreateResponse>();
      return MapToShipmentResult(dpdResponse);
    }
    
    // ✅ Private helper - логика трансформации
    private DpdCreateRequestDto MapToCreateRequestDto(ShipmentRequest request)
    {
      return new DpdCreateRequestDto
      {
        SenderCity = request.SenderCity,
        RecipientCity = request.RecipientCity,
        // ... маппинг полей
      };
    }
  }
}

// DI регистрация (важно: keyed для нескольких IShipmentService)
namespace GloriaOTS.Infrastructure.Services
{
  public static class DependencyInjectionExtensions
  {
    public static IServiceCollection AddShipmentServices(
      this IServiceCollection services, IConfiguration configuration)
    {
      // ✅ Keyed registration - несколько IShipmentService
      services.AddKeyedScoped<IShipmentService, CdekShipmentService>("cdek");
      services.AddKeyedScoped<IShipmentService, DpdShipmentService>("dpd");
      services.AddKeyedScoped<IShipmentService, RussianPostShipmentService>("rpost");
      
      return services;
    }
  }
}

// ShipmentServiceFacade - главный dispatchen
public class ShipmentServiceFacade
{
  private readonly IServiceProvider _serviceProvider;
  
  public async Task<ShipmentResult> CreateShipment(Order order)
  {
    // Определяем какого перевозчика использовать
    var key = ShipmentServiceHelper.GetServiceKey(order.ShipmentService);
    
    // Получаем правильную реализацию через DI
    var service = _serviceProvider.GetRequiredKeyedService<IShipmentService>(key);
    
    return await service.CreateShipment(MapToRequest(order));
  }
}
```

**Правила для GloriaOTS C# код:**
- ✅ Layered: ApplicationCore → Infrastructure → Web/Workers
- ✅ Interfaces in ApplicationCore (IShipmentService, IWmsService)
- ✅ Implementation in Infrastructure (DpdShipmentService, ...)
- ✅ DI Keyed registration для нескольких реализаций
- ✅ Config в appsettings (Url, Token, Timeout)
- ✅ Null-safe: ?.  и ?? operators
- ✅ async/await для IO операций
- ✅ Нет magic strings (использовать const/enum)
- ✅ Нет exception swallowing (re-throw или логировать)

---

### 4️⃣ SECURITY (Security Checks)

**Что проверять для .NET/GloriaOTS:**
- Нет SQL injection? (всегда параметризованные запросы в EF Core)
- Нет secrets in code? (ConfigurationBuilder + User Secrets или env vars)
- Нет PII in logs? (не логируем customer ID, tracking info, адреса)
- Нет XXE в XML parsing? (XmlReader settings)
- Нет hardcoded API keys/tokens? (config, not code)
- Нет directory traversal? (Path.Combine validation)
- Нет race conditions? (async/await pattern)

**Процесс для GloriaOTS:**
```csharp
// ❌ ПЛОХО: SQL injection
var query = $"SELECT * FROM Orders WHERE OrderNumber = '{orderNumber}'";
var orders = context.Orders.FromSqlInterpolated(query);

// ✅ ХОРОШО: EF Core параметризация (автоматическая)
var orders = context.Orders
  .Where(o => o.OrderNumber == orderNumber)
  .ToList();

// ❌ ПЛОХО: API key в коде
private const string DPD_API_KEY = "sk_live_XXX";

// ✅ ХОРОШО: конфиг + User Secrets (dev) или env vars (prod)
public class DpdApiSettings
{
  public string ApiKey { get; set; }  // из appsettings.json или env
  public string ApiUrl { get; set; }
}

// ❌ ПЛОХО: логируем sensitive data
_logger.LogInformation($"Order {order.CustomerEmail} shipped via {carrier}");

// ✅ ХОРОШО: логируем только non-sensitive
_logger.LogInformation($"Order {order.Id} shipped via {carrier}");

// ❌ ПЛОХО: path traversal
var filePath = $"/uploads/{userInput}";

// ✅ ХОРОШО: validate + combine
var basePath = Path.Combine("/uploads", "orders");
var safePath = Path.Combine(basePath, Path.GetFileName(fileName));
if (!Path.GetFullPath(safePath).StartsWith(Path.GetFullPath(basePath)))
  throw new SecurityException("Invalid path");
```

✅ **SECURITY CHECKLIST:**
- [ ] Все DB запросы через EF Core (нет SQL strings)
- [ ] Нет secrets in source code (все в config/env)
- [ ] Нет PII в логах
- [ ] API tokens используют configuration
- [ ] Нет XXE уязвимостей (если парсим XML)
- [ ] Path operations используют Path.Combine + validation
- [ ] Async patterns используются правильно (нет deadlocks)

---

### 5️⃣ ТЕСТЫ (Testing)

**Что писать для GloriaOTS:**
- Unit tests: для каждого public метода
- Integration tests: для OrderTracking/WmsSync логики
- Handler tests: для status transition handlers
- Mock tests: для внешних API (DPD, WMS)

**Процесс для GloriaOTS:**
```csharp
// Unit test - ShipmentServiceFacade
[Fact]
public async Task CreateShipment_WithDpdCarrier_UsesDpdService()
{
  // Arrange
  var order = new Order { ShipmentService = ShipmentService.DPD };
  var mockDpdService = new Mock<IShipmentService>();
  mockDpdService
    .Setup(s => s.CreateShipment(It.IsAny<ShipmentRequest>()))
    .ReturnsAsync(new ShipmentResult { Success = true });
  
  var facade = new ShipmentServiceFacade(mockDpdService.Object);
  
  // Act
  var result = await facade.CreateShipment(order);
  
  // Assert
  Assert.True(result.Success);
  mockDpdService.Verify(s => s.CreateShipment(It.IsAny<ShipmentRequest>()), Times.Once);
}

// Integration test - DPD API
[IntegrationTest]
public async Task DpdShipmentService_SendsCorrectRequest_ToApiEndpoint()
{
  // Arrange
  var httpClient = new HttpClient();
  var settings = Options.Create(new DpdApiSettings 
  { 
    ApiUrl = "http://dpd.test/api",
    ApiKey = "test-key"
  });
  
  var service = new DpdShipmentService(httpClient, settings);
  var request = new ShipmentRequest 
  { 
    SenderCity = "Moscow",
    RecipientCity = "SPB"
  };
  
  // Act
  var result = await service.CreateShipment(request);
  
  // Assert (используем HttpClient mock или WireMock)
  Assert.NotEmpty(result.TrackingNumber);
}

// Handler test - OrderTracking
[Fact]
public async Task OrderTrackingHandler_ReceivesDpdStatus_UpdatesOrderStatus()
{
  // Arrange
  var dbContext = CreateTestDbContext();
  var order = new Order { Id = 1, Status = OrderStatus.PENDING };
  dbContext.Orders.Add(order);
  await dbContext.SaveChangesAsync();
  
  var handler = new OrderTrackingHandler(dbContext);
  var dpdEvent = new DpdStatusUpdatedEvent 
  { 
    OrderId = 1,
    DpdStatus = "DELIVERED"
  };
  
  // Act
  await handler.Handle(dpdEvent);
  
  // Assert
  var updatedOrder = await dbContext.Orders.FindAsync(1);
  Assert.Equal(OrderStatus.DELIVERED, updatedOrder.Status);
}

// RabbitMQ event test
[IntegrationTest]
public async Task DpdShipmentCreated_PublishesEvent_ToRabbitMq()
{
  // Arrange
  var mockEventBus = new Mock<IEventBus>();
  var service = new DpdShipmentService(httpClient, settings, mockEventBus.Object);
  
  // Act
  var result = await service.CreateShipment(request);
  
  // Assert
  mockEventBus.Verify(
    eb => eb.PublishAsync(It.IsAny<ShipmentCreatedEvent>()),
    Times.Once
  );
}

✅ ТЕСТЫ ДОЛЖНЫ:
- Использовать xUnit + Moq (как в коде GloriaOTS)
- Тестировать ApplicationCore контракты
- Мокировать внешние зависимости (API, БД)
- Покрывать happy path + error cases
- Использовать InMemory EF Core для DB тестов
- Использовать TestFixture для setup
- >80% coverage для критических path

Coverage check:
dotnet test /p:CollectCoverage=true /p:CoverageThreshold=80
```

---

### 6️⃣ КОММИТ (Commit)

**Что делать:**
- Правильная ветка: feature/*, fix/*, refactor/*
- Сообщение: feat(dpd): добавить поддержку перевозчика DPD
- Описывать что добавили/изменили в каких слоях
- Co-Authored-By добавить
- Все тесты зелёные
- Build успешный

**Процесс для GloriaOTS:**
```bash
# Проверка перед коммитом
git status           # только нужные файлы?
dotnet build         # build успешный?
dotnet test          # все тесты зелёные? (xUnit)

# (Optional) dotnet test /p:CollectCoverage=true если критично

# Коммит
git commit -m "feat(dpd): добавить поддержку перевозчика DPD

Изменения по слоям:
- ApplicationCore: добавлен enum ShipmentService.DPD
- ApplicationCore: добавлен маппинг в ShipmentServiceHelper
- Infrastructure: добавлен DpdShipmentService (реализация IShipmentService)
- Infrastructure: keyed DI регистрация в DependencyInjectionExtensions
- Infrastructure: маршрут в ShipmentServiceFacade
- Web: appsettings.json с DPD API URL и токеном
- OrderTracking: appsettings.json с DPD конфигом
- Database: миграция для reference data (если нужна)

AC выполнены:
- ✅ Enum + Helper в ApplicationCore
- ✅ Реализация IShipmentService в Infrastructure
- ✅ DI регистрация Keyed
- ✅ Конфиг в Web + OrderTracking
- ✅ Unit тесты для ShipmentService (4 test cases)
- ✅ Integration тесты для API вызовов (2 test cases)
- ✅ Handler тесты для status updates (2 test cases)
- ✅ Code coverage: 82%
- ✅ Build: успешный

[NB] Заметки:
- Integration мутаторы (Integration Service) обновляются отдельно (координация)
- DPD API timeout установлен на 30 сек (как в других перевозчиков)

Co-Authored-By: Claude Haiku <noreply@anthropic.com>"
```

---

### 7️⃣ MR (Merge Request)

**Что делать:**
- Правильный target branch (обычно `master` для GloriaOTS)
- Описание: ссылка на ticket, краткое описание
- Все тесты зелёные в CI (.gitlab-ci.yml)
- Проверить что все слои покрыты

**Процесс для GloriaOTS:**
```bash
git push origin feature/add-dpd-carrier

# Создать MR через GitLab
Title: "feat(dpd): добавить поддержку перевозчика DPD"

Description:
"## Summary
Добавляем полную поддержку перевозчика DPD в Gloria OTS.

## Changes

### ApplicationCore
- Enum value `ShipmentService.DPD = 5`
- Маппинг в `ShipmentServiceHelper`

### Infrastructure
- Новый сервис `DpdShipmentService` (реализация `IShipmentService`)
- Keyed DI регистрация в `DependencyInjectionExtensions`
- Маршрут в `ShipmentServiceFacade`

### Configuration
- Web/appsettings.json: DPD API URL + токен
- OrderTracking/appsettings.json: то же самое

### Database (если нужна)
- Миграция vXXX_add_dpd.sql для reference data

## Test plan

### Unit tests
- ✅ ShipmentServiceFacade выбирает DpdShipmentService
- ✅ DpdShipmentService правильно трансформирует request
- ✅ Ошибка API обрабатывается gracefully
- ✅ TrackingNumber извлекается из response

### Integration tests
- ✅ DPD API вызов отправляет правильный payload (mock)
- ✅ OrderTracking получает DPD event

### Manual testing
- ✅ На стенде: заказ через DPD до статуса DELIVERED

## Security
- ✅ Нет hardcoded API keys (config-based)
- ✅ Параметризованные DB запросы (EF Core)
- ✅ Нет PII в логах

## Layering
- ✅ ApplicationCore: контракты и enum
- ✅ Infrastructure: реализация + DI
- ✅ Web/OrderTracking: конфиг

## Fixes
Closes GLORIA-XXX (новая поддержка перевозчика DPD)

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

MR будет автоматически:
✅ Запустит dotnet build
✅ Запустит dotnet test
✅ Проверит code coverage
✅ Пройдёт lint (если есть)

После одобрения двумя ревьюерами → merge в master
```

---

## ✨ Важные правила для GloriaOTS

### Правило 1: Layering
- **ApplicationCore** → только интерфейсы, DTOs, enum, events (нет зависимостей)
- **Infrastructure** → реализация, EF Core, services (зависит на ApplicationCore)
- **Web/Workers** → endpoints, DI, конфиг (зависит на Infrastructure/ApplicationCore)
- **Нарушение layering** → ВСЕГДА отказ ревьюера

### Правило 2: DI Keyed Registration
- Если несколько реализаций одного интерфейса → **обязательно** keyed
- Пример: `services.AddKeyedScoped<IShipmentService, DpdShipmentService>("dpd")`
- Получение: `serviceProvider.GetRequiredKeyedService<IShipmentService>(key)`

### Правило 3: DB Миграции
- Используем `Database/SqlDeploy` (no auto-migrate)
- Любые изменения schema → новый vXXX_*.sql файл
- Миграции должны быть **idempotent** (safe to re-run)

### Правило 4: Config Management
- **Никогда** hardcoded values (особенно API keys)
- Использовать `IOptions<T>` для config классов
- Mirror changes в Web **и** OrderTracking (оба нужны конфиг)

### Правило 5: RabbitMQ Events
- Публиковать события через `IEventBus` когда статус меняется
- Subscribe в правильном слое (OrderTracking для фоновых работ)
- Events = ApplicationCore DTOs (не Infrastructure/Web классы)

### Правило 6: Async/Await
- **Обязателен** для HTTP/DB операций (не .Result, не .Wait)
- Возвращать `Task<T>`, не `void` (кроме event handlers)
- Не создавать deadlocks (используй ConfigureAwait(false) если нужно)

### Правило 7: Exception Handling
- Ловить специфичные exception, не generic Exception
- Логировать перед throw (не swallow)
- Трансформировать внешние exception в ApplicationCore Result/Exception

### Правило 8: Testing
- xUnit + Moq (как в коде)
- Mock внешние зависимости (HTTP, SQL, Queue)
- >80% coverage для путей критичных (handlers, services)
- InMemory EF Core для DB тестов

---

## 🎓 Полный пример: Добавить перевозчика DPD

```
ШАГ 1: ПОНИМАНИЕ
✅ Добавить DPD в качестве перевозчика (IShipmentService реализация)
✅ Слои: ApplicationCore (enum/helper) → Infrastructure (сервис) → Web (конфиг)
✅ Нужны DB миграции (reference data для DPD)
✅ Нужны RabbitMQ события для OrderTracking
✅ [BLOCKER] Координация с Integration для мутаторов (ОК параллельно)

ШАГ 2: ПЛАН
✅ ApplicationCore: ShipmentService enum + ShipmentServiceHelper
✅ Infrastructure: DpdShipmentService + DI keyed + Facade маршрут
✅ Web/OrderTracking: appsettings.json
✅ Database: миграция для reference data
✅ Порядок: enum → реализация → DI → конфиг → тесты

ШАГ 3: КОД
✅ Написал ApplicationCore enum и helper
✅ Написал DpdShipmentService (IShipmentService)
✅ Добавил DI keyed регистрацию
✅ Обновил ShipmentServiceFacade
✅ Добавил конфиг в appsettings
✅ Следовал layering правилам

ШАГ 4: SECURITY
✅ Нет hardcoded API key (используется IOptions<DpdApiSettings>)
✅ Параметризованные DB запросы (EF Core)
✅ Нет PII в логах (логируем только OrderId)
✅ Path operations безопасны
✅ Async/await использованы правильно

ШАГ 5: ТЕСТЫ
✅ Unit: ShipmentServiceFacade использует DpdService
✅ Unit: DpdShipmentService трансформирует запрос
✅ Unit: Обработка DPD API ошибок
✅ Integration: Mock DPD API + проверка request
✅ Handler: OrderTracking получает DPD event
✅ Coverage: 84%

ШАГ 6: КОММИТ
✅ Ветка feature/add-dpd-carrier
✅ Сообщение описывает изменения по слоям
✅ Все AC выполнены
✅ dotnet build успешный
✅ dotnet test успешный (4 test cases)
✅ Co-Authored-By добавлен

ШАГ 7: MR
✅ Target: master (GloriaOTS стандартная ветка)
✅ Описание полное (Summary, Changes, Tests)
✅ CI успешный (.gitlab-ci.yml)
✅ Code coverage >80%

→ ГОТОВО! MR передан ревьюерам (gloriaots-researcher + gloriaots-engineer)
```

---

## 🔗 Связь с другими системами

### OMS Integration
- OMS BPMN экспортирует заказ через `orderExportWithFeedbackActivity`
- OTS получает через `Adapter`
- Обновления статуса отправляются обратно в OMS

### Integration Service
- Integration читает статусы из OTS через `OtsClient`
- Синк остатков через Kafka (BP-INT-30)
- Экспорт заказов через OTS mutators

### Reference
- `gloriaots-stack-anatomy` — полная архитектура
- `docs/bp/08-master-data-sync.md` — синхронизация
- `README.md` в repo — development guides

---

## ✅ Чеклист перед MR

```
ПОНИМАНИЕ
- [ ] Прочитана вся постановка
- [ ] Ясны ВСЕ ЧТО/ГДЕ/КАК/РИСКИ
- [ ] [BLOCKER] вопросы разрешены

ПЛАН
- [ ] Определены файлы в КАЖДОМ слое
- [ ] Определён порядок (ApplicationCore → Infrastructure → Web)
- [ ] Понято про DB миграции
- [ ] Понято про RabbitMQ события

КОД
- [ ] Layering соблюдён (ApplicationCore не зависит)
- [ ] Интерфейсы в ApplicationCore
- [ ] Реализация в Infrastructure
- [ ] DI Keyed регистрация если нужна
- [ ] Config в appsettings
- [ ] Комментарии только "ПОЧЕМУ"

SECURITY
- [ ] Нет hardcoded secrets
- [ ] EF Core параметризация
- [ ] Нет PII в логах
- [ ] Path operations безопасны
- [ ] Async/await правильно

ТЕСТЫ
- [ ] Unit: happy path
- [ ] Unit: error cases
- [ ] Integration: API вызовы
- [ ] Handlers: event processing
- [ ] Coverage >80%

КОММИТ
- [ ] Правильная ветка
- [ ] Сообщение ясное (по слоям)
- [ ] Все AC в сообщении
- [ ] Co-Authored-By добавлен
- [ ] dotnet build ✅
- [ ] dotnet test ✅

MR
- [ ] Target branch правильный (master)
- [ ] Описание полное
- [ ] CI успешный
- [ ] Coverage >80%
- [ ] Готово к merge
```

---

## 📚 Файлы для чтения

### Обязательно
- `gloriaots-stack-anatomy` — архитектура и файлоструктура
- `gloriaots-engineer` — agent для реализации
- Existing код в `platform/starfish24/core/*/ShipmentServices/` — примеры

### Дополнительно
- `README.md` в `platform/gloriaots/gloriaots/`
- `src/GloriaOTS.Infrastructure/Services/ShipmentServices/` — примеры реализации
- `.gitlab-ci.yml` — CI pipeline
- `Docs/` в repo — документация интеграций

---

## 🚀 Как использовать этот паттерн

### Для разработчика (gloriaots-engineer)

```
1. Загрузить: pattern-development-gloriaots.md
2. Загрузить: gloriaots-stack-anatomy.md
3. Загрузить: shared-code-style.md (C# section)
4. Следовать 7 шагам ВСЕГДА
5. Проверить чеклист перед коммитом
6. Создать MR с полным описанием
```

### Для ревьювера

```
1. Загрузить: pattern-review-standard.md
2. Проверить: layering (ApplicationCore → Infrastructure → Web)
3. Проверить: DI keyed registration если несколько реализаций
4. Проверить: конфиг в appsettings + mirror в Web/OrderTracking
5. Проверить: tests >80% coverage
6. Проверить: security (no hardcoded secrets, parameterized queries)
7. Проверить: CI успешный
```

---

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Платформа:** Gloria OTS (.NET 10)  
**Статус:** ✅ Production-ready  
**Автор:** Claude Haiku 4.5 + Antonov Aleksandr (Outsource)

🚀 **ГОТОВО К ИСПОЛЬЗОВАНИЮ!**
