# 🎯 pattern-development-oms.md

**Категория:** [PATTERNS] OMS-specific  
**Используется:** разработчики Starfish/OMS платформы  
**Версия:** 1.0  
**Статус:** Production-ready  
**Platform:** Java Spring Boot + Camunda BPM + Spring Cloud Config

---

## 📋 Описание

**Явный паттерн разработки для OMS (Starfish)** - специализированная версия pattern-development-flow.md с Java/Spring-специфичными правилами.

OMS разработчик **ДОЛЖЕН ВСЕГДА** следовать этим 8 шагам. Нет импровизации. Отличие от generic-паттерна: добавлены Camunda BPMN, Spring Cloud Config, Maven, Java-специфичные security checks.

---

## 🎯 8 обязательных шагов для OMS

### 1️⃣ ПОНИМАНИЕ (Understanding) — OMS edition

**Что делать:**
- Прочитать ПОЛНУЮ постановку (ЧТО, ГДЕ, КАК, РИСКИ)
- Понять требование: новый сервис / изменение Order / Delivery / Payment?
- Понять сервисы: какой core-репо? (Order, Stock, Delivery, Dictionary, Camunda, etc.)
- Понять BPMN: затронут ли какой-то процесс в `platform/starfish24/awg/bpmn-process/`?
- Понять Spring Cloud Config: нужны ли env-specific values в `platform/starfish24/awg/cloud-configs/`?
- Понять верификацию: Unit tests? Integration tests? BPMN-worker tests?
- Понять риски: какие [BLOCKER] есть?

**Процесс:**

```
ЧТО?  "Добавить новый статус order PARTIALLY_SHIPPED"
      ✅ Понял: новый OrderStatus enum + database migration

ГДЕ?  "core/Order (Java) + awg/bpmn-process (BPMN XML) + Integration (PHP)"
      ✅ Понял: 2 Java-репо + BPMN + Integration

BPMN? "У процесса orderProcessing есть шаг ShippingDecision"
      ✅ Понял: нужно добавить новую branch в BPMN
      
CONFIG? "Разные пороги PARTIALLY_SHIPPED per env (prod/staging/dev)"
        ✅ Понял: cloud-config entries для каждого окружения

КАК?  "Unit (OrderStatus test) + Integration (BPMN worker test) + E2E (на staging)"
      ✅ Понял: как проверяем

РИСКИ? "[BLOCKER] нет; есть зависимость от Dictionary, но он уже обновлён"
      ✅ Понял: могу начинать писать

✅ ПОНИМАНИЕ ЗАВЕРШЕНО → переход на шаг 2
```

**Если не понял:**
- Спросить аналитика про бизнес-логику
- Спросить OMS-архитектора про BPMN-процесс
- Спросить DevOps про cloud-config strategy
- Не начинать писать "наугад"

---

### 2️⃣ ПЛАН (Planning) — OMS edition

**Что делать:**
- Какие файлы трогаем? (Java, BPMN XML, YAML config, Tests)
- Какой порядок имплементации?
- Какие Java-репо затронуты?
- Есть ли BPMN-процессы которые нужно обновить?
- Есть ли миграции БД?
- Есть ли cloud-config изменения?
- Есть ли [NB] нерешённые вопросы?

**Процесс:**

```
Java-репо:
✅ platform/starfish24/core/Order                    (OrderStatus.java)
✅ platform/starfish24/core/camunda-worker          (ShippingDecisionWorker.java)
✅ platform/starfish24/awg/cloud-configs             (yml per env)

BPMN-процессы:
✅ platform/starfish24/awg/bpmn-process/orderProcessing.bpmn20.xml

Database:
✅ Order service миграция: add column partially_shipped_count

Cloud-Config:
✅ awg/cloud-configs/order-service-{dev,staging,prod}.yml
   + new property: order.partial-ship-threshold = <per-env>

Тесты:
✅ Unit: OrderStatus enum test
✅ Integration: BPMN worker test с embedded Camunda
✅ E2E: staging сценарий частичной отправки

[NB] вопросы:
- нужна ли миграция для существующих заказов? (ответ: нет, только новые)
- нужно ли уведомлять customer про partial ship? (ответ: да, через Event Dispatcher)
- нужны ли изменения в Integration? (ответ: потом, отдельный task)

Зависимости:
- OrderStatus (первое, от этого зависит BPMN worker)
- BPMN-процесс (зависит от OrderStatus)
- Worker (зависит от BPMN)
- Cloud-config (независимо, можно параллельно)
- DB миграция (зависит от OrderStatus, выкатываем с кодом)
```

---

### 3️⃣ КОД (Implementation) — OMS edition

**Что делать:**
- Писать Java код по плану, следовать oms-java-conventions skill
- Обновить BPMN XML процессы по плану
- Обновить cloud-config YAML
- Создать/обновить миграции БД (если нужны)
- Следовать shared-code-style (naming, javadoc, comments)
- Комментарии только "ПОЧЕМУ", не "ЧТО"
- Функции/методы <50 строк
- Lombok для @Data, @AllArgsConstructor, @Builder

**Процесс:**

```java
// ✅ ХОРОШО: новый OrderStatus для частичной отправки
// (используется когда товар отправлен по частям на разные адреса)
@Getter
@RequiredArgsConstructor
public enum OrderStatus {
  PENDING("PENDING"),
  PARTIALLY_SHIPPED("PARTIALLY_SHIPPED"),  // ← новый
  FULLY_SHIPPED("FULLY_SHIPPED"),
  DELIVERED("DELIVERED");
  
  private final String value;
}

// ❌ ПЛОХО:
public enum OrderStatus {
  PENDING, PS, FS, DLV  // невразумительные сокращения
}
```

**BPMN обновление:**

```xml
<!-- ✅ ХОРОШО: новая branch в BPMN процессе для partial shipping -->
<bpmn:serviceTask id="ShippingDecisionTask" 
                   name="Decide Shipping Method"
                   camunda:type="external"
                   camunda:topic="shipping-decision">
  <bpmn:outgoing>toPartialShip</bpmn:outgoing>
  <bpmn:outgoing>toFullShip</bpmn:outgoing>
</bpmn:serviceTask>

<!-- Branch для частичной отправки -->
<bpmn:sequenceFlow id="toPartialShip" name="Partial Shipment" 
                   sourceRef="ShippingDecisionTask"
                   targetRef="PartialShipmentHandler">
  <bpmn:conditionExpression>
    ${orderPartiallyShipmentEligible == true}
  </bpmn:conditionExpression>
</bpmn:sequenceFlow>

<!-- Handler для частичной отправки -->
<bpmn:serviceTask id="PartialShipmentHandler"
                   name="Handle Partial Shipment"
                   camunda:type="external"
                   camunda:topic="partial-shipment-handler" />
```

**Cloud-Config обновление:**

```yaml
# cloud-configs/order-service-prod.yml
order:
  # Порог количества товара для partial shipment
  # (если наличие < порога, отправляем частичный заказ)
  partial-ship-threshold: 5
  partial-ship-max-attempts: 3
  partial-ship-notification-enabled: true

# cloud-configs/order-service-staging.yml
order:
  partial-ship-threshold: 1  # ниже для быстрого тестирования
  partial-ship-max-attempts: 5
  partial-ship-notification-enabled: true

# cloud-configs/order-service-dev.yml
order:
  partial-ship-threshold: 0  # всегда парциальный в dev
  partial-ship-max-attempts: 10
  partial-ship-notification-enabled: false  # не спамим events в dev
```

**Java Worker для Camunda:**

```java
// ✅ ХОРОШО: External task worker для partial shipment
@Service
@Slf4j
public class PartialShipmentHandler {
  
  private final OrderRepository orderRepository;
  private final EventDispatcher eventDispatcher;
  
  @Autowired
  public PartialShipmentHandler(OrderRepository orderRepository,
                                EventDispatcher eventDispatcher) {
    this.orderRepository = orderRepository;
    this.eventDispatcher = eventDispatcher;
  }
  
  // Слушаем Camunda topic: partial-shipment-handler
  // (остальной код регистрации через ExternalTaskClient в конфиге)
  
  public void handlePartialShipment(ExternalTask task) {
    String orderId = task.getVariable("orderId");
    Long shipmentId = task.getVariable("shipmentId");
    
    try {
      Order order = orderRepository.findById(orderId)
        .orElseThrow(() -> new OrderNotFoundException(orderId));
      
      // Обновляем статус (важно: меняем статус на PARTIALLY_SHIPPED)
      order.setStatus(OrderStatus.PARTIALLY_SHIPPED);
      orderRepository.save(order);
      
      // Отправляем событие (notify customer)
      eventDispatcher.publish(new PartialShipmentEvent(
        orderId,
        shipmentId,
        order.getCustomerId()
      ));
      
      // Сообщаем Camunda что завершили
      task.getClient().complete(task);
      
      log.info("Partial shipment handled: orderId={}, shipmentId={}", 
               orderId, shipmentId);
               
    } catch (Exception e) {
      log.error("Failed to handle partial shipment: orderId={}", orderId, e);
      // Camunda retry механика (зависит от конфига)
      task.getClient().handleBpmnError(task, "PARTIAL_SHIPMENT_FAILED");
    }
  }
}
```

---

### 4️⃣ DATABASE (Миграции) — OMS edition

**Что делать:**
- Создать миграцию для новых колонок / таблиц
- Использовать Liquibase XML (OMS стандарт)
- Версия миграции: timestamp (2026-10-06-HHMMSS)
- Обратимая миграция (rollback возможен)

**Процесс:**

```xml
<!-- ✅ ХОРОШО: Liquibase миграция для partial shipment tracking -->
<!-- File: src/main/resources/db/changelog/2026-10-06-100000-add-partial-shipment.xml -->

<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                   xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
                   http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.10.xsd">

  <changeSet id="add-partial-shipment-tracking" author="OMS-Team">
    
    <!-- Новая колонка для tracking partial shipments -->
    <addColumn tableName="orders">
      <column name="partially_shipped_count" type="INT" defaultValue="0">
        <constraints nullable="false"/>
      </column>
    </addColumn>
    
    <!-- Новая колонка для статуса -->
    <addColumn tableName="orders">
      <column name="shipment_status" type="VARCHAR(50)" defaultValue="PENDING">
        <constraints nullable="false"/>
      </column>
    </addColumn>
    
    <!-- Index для быстрого поиска */
    <createIndex indexName="idx_orders_shipment_status" tableName="orders">
      <column name="shipment_status"/>
    </createIndex>
    
    <!-- Rollback plan -->
    <rollback>
      <dropIndex tableName="orders" indexName="idx_orders_shipment_status"/>
      <dropColumn tableName="orders" columnName="partially_shipped_count"/>
      <dropColumn tableName="orders" columnName="shipment_status"/>
    </rollback>
    
  </changeSet>

</databaseChangeLog>
```

---

### 5️⃣ SECURITY (Security Checks) — OMS edition

**Что проверять:**
- Нет SQL injection? (QueryDSL, parameterized queries, Spring Data)
- Нет secrets in code? (no hardcoded DB passwords, API keys)
- Нет PII in logs? (не логируем customer_id, email, personal info)
- Нет XXE в XML парсинге? (отключить DTD processing)
- BPMN process security: variables не содержат secrets
- Spring Security: авторизация проверена на endpoints

**Процесс:**

```java
// ✅ ХОРОШО: параметризованный запрос через Spring Data
@Repository
public interface OrderRepository extends JpaRepository<Order, String> {
  List<Order> findByStatusAndShipmentStatus(
    OrderStatus status,
    String shipmentStatus
  );
  // Spring автоматически параметризует запрос
}

// ❌ ПЛОХО: SQL injection risk
@Query("SELECT * FROM orders WHERE status = '" + status + "'")
List<Order> findByStatus(String status);

// ✅ ХОРОШО: security на BPMN переменных
// (никогда не сохраняем secrets в BPMN process variables)
Map<String, Object> variables = new HashMap<>();
variables.put("orderId", orderId);  // OK - public data
variables.put("customerId", customerId);  // OK - internal only
// variables.put("apiKey", apiKey);  // ❌ НИКОГДА!

// ✅ ХОРОШО: логирование без PII
log.info("Partial shipment event: orderId={}", orderId);
// log.info("Partial shipment event: customer={}, email={}", customerId, email); // ❌ NO!

// ✅ ХОРОШО: XXE protection в XML парсинге
XMLInputFactory xmlFactory = XMLInputFactory.newInstance();
xmlFactory.setProperty(XMLInputFactory.SUPPORT_DTD, false);
xmlFactory.setProperty("javax.xml.stream.isSupportingExternalEntities", false);
```

---

### 6️⃣ ТЕСТЫ (Testing) — OMS edition

**Что писать:**
- Unit tests: для каждого метода (OrderStatus enum, status transitions)
- Integration tests: с embedded Camunda, Spring Test, TestContainers
- BPMN tests:验证процессы через camunda-bpm-assert
- E2E тесты: на staging окружении (отдельно)

**Процесс:**

```java
// Unit test для OrderStatus enum
@Test
public void testPartiallyShippedStatusExists() {
  assertTrue(
    Arrays.stream(OrderStatus.values())
      .anyMatch(s -> s.value.equals("PARTIALLY_SHIPPED")),
    "OrderStatus должен содержать PARTIALLY_SHIPPED"
  );
}

// Integration test с embedded Camunda
@SpringBootTest
@ExtendWith(SpringExtension.class)
public class PartialShipmentWorkerTest {

  @Autowired
  private OrderRepository orderRepository;
  
  @Autowired
  private EventDispatcher eventDispatcher;
  
  private ExternalTaskClient client;
  private PartialShipmentHandler handler;

  @BeforeEach
  public void setUp() {
    // Embedded Camunda engine (из spring-boot-starter-camunda)
    handler = new PartialShipmentHandler(orderRepository, eventDispatcher);
    client = ExternalTaskClient.create();
  }

  @Test
  public void testPartialShipmentHandlerUpdatesOrderStatus() {
    // Given: есть заказ в статусе PENDING
    Order order = createTestOrder(OrderStatus.PENDING);
    orderRepository.save(order);
    
    // When: выполняем partial shipment
    handler.handlePartialShipment(createMockExternalTask(order.getId()));
    
    // Then: статус должен измениться на PARTIALLY_SHIPPED
    Order updated = orderRepository.findById(order.getId()).orElseThrow();
    assertEquals(OrderStatus.PARTIALLY_SHIPPED, updated.getStatus());
  }

  @Test
  public void testPartialShipmentPublishesEvent() {
    // Given: есть заказ
    Order order = createTestOrder(OrderStatus.PENDING);
    orderRepository.save(order);
    
    // When: выполняем partial shipment
    handler.handlePartialShipment(createMockExternalTask(order.getId()));
    
    // Then: событие должно быть published
    verify(eventDispatcher, times(1))
      .publish(any(PartialShipmentEvent.class));
  }
}

// BPMN процесс тест
@SpringBootTest
public class OrderProcessingBpmnTest {

  @Autowired
  private ProcessEngine processEngine;

  @Test
  public void testPartialShipmentBranchExecutes() {
    // Given: BPMN процесс orderProcessing
    ProcessDefinition processDefinition = processEngine.getRepositoryService()
      .createProcessDefinitionQuery()
      .processDefinitionKey("orderProcessing")
      .singleResult();
    
    // When: стартуем процесс с partial shipment
    ProcessInstance instance = processEngine.getRuntimeService()
      .startProcessInstanceByKey("orderProcessing", 
        Map.of("orderId", "test-123", 
               "orderPartiallyShipmentEligible", true));
    
    // Then: должны быть в процессе PartialShipmentHandler
    assertTrue(processEngine.getRuntimeService()
      .createExecutionQuery()
      .processInstanceId(instance.getId())
      .activityId("PartialShipmentHandler")
      .list()
      .size() > 0);
  }
}

// Edge-case: быстрые повторы partial shipment
@Test
public void testConcurrentPartialShipments() {
  Order order = createTestOrder(OrderStatus.PENDING);
  orderRepository.save(order);
  
  // Запускаем несколько потоков которые одновременно
  // пытаются сделать partial shipment
  ExecutorService executor = Executors.newFixedThreadPool(3);
  
  for (int i = 0; i < 3; i++) {
    executor.submit(() -> {
      handler.handlePartialShipment(createMockExternalTask(order.getId()));
    });
  }
  
  executor.shutdown();
  executor.awaitTermination(5, TimeUnit.SECONDS);
  
  // Проверяем что состояние консистентно (не совпадают счётчики)
  Order final = orderRepository.findById(order.getId()).orElseThrow();
  assertEquals(OrderStatus.PARTIALLY_SHIPPED, final.getStatus());
  assertTrue(final.getPartiallyShippedCount() >= 1);
}
```

**Coverage требование:** >85% для critical paths (Order, Payment, Delivery)

---

### 7️⃣ CAMUNDA BPMN (Process Validation) — OMS edition

**Что проверять:**
- Все новые service tasks имеют camunda:topic
- Все topics определены в Java workers
- Нет циклических зависимостей между процессами
- Все переменные процесса задокументированы
- Процесс может откатиться (compensating transactions для важных операций)

**Процесс:**

```xml
<!-- ✅ ХОРОШО: service task с правильным topic -->
<bpmn:serviceTask id="PartialShipmentHandler"
                   name="Handle Partial Shipment"
                   camunda:type="external"
                   camunda:topic="partial-shipment-handler"
                   camunda:retries="3">  <!-- retry механика -->
  <bpmn:incoming>toPartialShip</bpmn:incoming>
  <bpmn:outgoing>toCheckNextShipment</bpmn:outgoing>
</bpmn:serviceTask>

<!-- Compensating transaction для отката -->
<bpmn:boundaryEvent id="PartialShipmentFailed" 
                     attachedToRef="PartialShipmentHandler">
  <bpmn:errorEventDefinition errorRef="PartialShipmentError"/>
  <bpmn:outgoing>toCompensation</bpmn:outgoing>
</bpmn:boundaryEvent>

<!-- Compensation: откатить что сделали -->
<bpmn:serviceTask id="RollbackPartialShipment"
                   name="Rollback Partial Shipment"
                   camunda:type="external"
                   camunda:topic="rollback-partial-shipment">
  <bpmn:incoming>toCompensation</bpmn:incoming>
  <bpmn:outgoing>toErrorHandling</bpmn:outgoing>
</bpmn:serviceTask>
```

---

### 8️⃣ КОММИТ И MR (Commit & PR) — OMS edition

**Что делать:**
- Правильная ветка: feature/*, fix/*, refactor/* (НЕ feature/my-thing)
- Сообщение ясное: `feat(order): добавить статус PARTIALLY_SHIPPED`
- Co-Authored-By добавить
- Все тесты зелёные (должны пройти в CI)
- Обновить `docs/` если есть архитектурные изменения

**Процесс:**

```bash
# Перед коммитом: проверка
mvn clean verify                      # Unit + Integration тесты
mvn -P checkstyle verify              # Style checks (OMS uses checkstyle)
mvn -P spotbugs verify                # Static analysis

# Коммит
git commit -m "feat(order): добавить статус PARTIALLY_SHIPPED

- добавить OrderStatus enum value
- создать PartialShipmentHandler worker
- обновить orderProcessing BPMN процесс
- миграция БД: добавить partially_shipped_count column
- cloud-config: per-env threshold values
- unit/integration/BPMN tests с >85% coverage

Changes:
- core/Order/OrderStatus.java
- core/camunda-worker/PartialShipmentHandler.java
- awg/bpmn-process/orderProcessing.bpmn20.xml
- awg/cloud-configs/order-service-{dev,staging,prod}.yml
- core/Order/migrations/2026-10-06-XXXXX.xml

AC выполнены:
- Unit тесты: ✅ OrderStatus + Handler
- Integration: ✅ Camunda embedded engine
- BPMN: ✅ процесс работает, compensations OK
- Security: ✅ нет SQL injection, XXE, PII in logs
- Coverage: ✅ 87% на critical paths

Closes OPSOMN002-XXX

Co-Authored-By: Claude Haiku <noreply@anthropic.com>"
```

**MR описание (GitLab):**

```markdown
## Summary
Добавляем поддержку частичной отправки заказов (PARTIALLY_SHIPPED).

Это позволяет обрабатывать случаи когда товар отправляется несколько раз
до полной доставки (например, 1С отправляет по частям, или по разным складам).

## Changes

### Java changes
- **OrderStatus.java**: добавлен enum value PARTIALLY_SHIPPED
- **PartialShipmentHandler.java**: новый external task worker для Camunda
- **OrderRepository**: новые методы for querying partial shipments

### BPMN changes
- **orderProcessing.bpmn20.xml**: новая branch для partial shipment decision

### Database
- **Migration 2026-10-06**: добавлены колонки для tracking

### Configuration
- **cloud-configs/**: per-env threshold values (prod=5, staging=1, dev=0)

### Tests
- **OrderStatusTest**: enum validation
- **PartialShipmentHandlerTest**: unit + integration
- **OrderProcessingBpmnTest**: BPMN flow validation

## Test plan

### Unit tests
```bash
mvn test -Dtest=OrderStatusTest
mvn test -Dtest=PartialShipmentHandlerTest
```

### Integration tests
```bash
mvn -Dgroups=integration test -Dtest=*BpmnTest
```

### Manual E2E (staging)
1. Create order in staging
2. Mark as eligible for partial shipment
3. Verify BPMN process transitions correctly
4. Check database columns updated
5. Verify event dispatched

## Deployment notes
- Cloud config changes: apply to all envs (dev/staging/prod)
- Database migration: auto-run on Order service startup
- No breaking changes, backward compatible
- Feature can be toggled off via cloud-config

## Risk assessment
- **LOW** - no breaking changes
- Partial shipments are new flow, existing orders unaffected
- BPMN compensations in place for rollback

Closes OPSOMN002-XXX

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

---

## ✨ Важные правила для OMS разработчика

### Правило 1: ВСЕГДА 8 шагов (не 7)
- Unit + Integration = шаг 5
- **BPMN validation = отдельный шаг 7**
- Config management = встроен в шаг 3

### Правило 2: Camunda - это контракт
- Имя topic (service-task @camunda:topic) - это контракт между BPMN XML и Java worker
- Case-sensitive
- При смене имени → обновить BPMN И Java одновременно
- Думать о running instances перед изменением

### Правило 3: Spring Cloud Config - обязателен
- Per-env values в `awg/cloud-configs/`
- Никогда application.yml в core/
- Все env-specific values: dev/staging/prod
- Обновлять ВСЕ 3 файла если меняется структура

### Правило 4: Database миграции
- Использовать Liquibase XML (не SQL)
- Версионируй: timestamp_description.xml
- Всегда включай rollback блок
- Миграции должны быть idempotent

### Правило 5: Security обязателен
- Spring Data для SQL (параметризованные запросы)
- XXE protection в XML
- Нет secrets in BPMN variables
- Нет PII in logs
- Даже если "потом фиксим" - не пушить

### Правило 6: Тесты для BPMN
- Embedded Camunda в tests
- camunda-bpm-assert для assertions
- Validate все task topics
- Edge-cases: retry механика, compensations

### Правило 7: Default branches нестандартные
- Много feature-веток (CLD-XXXX)
- `Delivery` (19783+19795), `pay-service` (CLD-1840), `cloud-configs` (CLD-17047)
- Перед push проверять куда идём
- GitLab MR interface показывает правильный default

### Правило 8: OMS-Java-конвенции
- Lombok @Data, @RequiredArgsConstructor, @Builder обязательны
- Методы методы <50 строк (Java больше verbosity чем PHP)
- Javadoc на public classes и методы
- Комментарии только "ПОЧЕМУ", не "ЧТО"

---

## 🎓 Полный пример: PARTIALLY_SHIPPED

```
ШАГ 1: ПОНИМАНИЕ ✅
"Требуется поддержать частичную отправку заказов"
→ Новый enum, BPMN branch, worker, config, миграция

ШАГ 2: ПЛАН ✅
Файлы:
  - core/Order/OrderStatus.java
  - core/camunda-worker/PartialShipmentHandler.java
  - awg/bpmn-process/orderProcessing.bpmn20.xml
  - awg/cloud-configs/order-service-*.yml
  - core/Order/migrations/2026-10-06-XXXXX.xml
Порядок: Enum → Worker → BPMN → Config → Migration

ШАГ 3: КОД ✅
✅ Enum с javadoc
✅ Worker с logging, error handling, Lombok
✅ BPMN с compensating transactions
✅ Cloud-config YAML для каждого окружения
✅ Liquibase миграция с rollback

ШАГ 4: DATABASE ✅
✅ Миграция Liquibase XML
✅ Обратимая (rollback план)
✅ Индексы для performance

ШАГ 5: SECURITY ✅
✅ Spring Data (параметризованные запросы)
✅ XXE protection
✅ Нет secrets in BPMN/logs
✅ Нет PII в логах

ШАГ 6: ТЕСТЫ ✅
✅ Unit: OrderStatus enum
✅ Integration: Handler + embedded Camunda
✅ BPMN: процесс flow + compensations
✅ Coverage: 87% on critical paths

ШАГ 7: CAMUNDA VALIDATION ✅
✅ Topic names match Java workers
✅ Compensating transactions в place
✅ No cyclic dependencies
✅ All variables documented

ШАГ 8: КОММИТ & MR ✅
✅ Ветка: feature/OPSOMN002-XXX
✅ Сообщение: feat(order): добавить статус PARTIALLY_SHIPPED
✅ Co-Authored-By добавлен
✅ Все тесты зелёные
✅ MR description полное

→ ГОТОВО! Передаём ревьюерам
```

---

## 📚 Обязательные документы для OMS разработчика

### Skills (в `.claude/skills/`)
- `oms-java-conventions` — Java code style, Lombok, Spring Boot
- `oms-stack-anatomy` — structure of OMS, репо, сервисы
- `camunda-bpm` — BPMN design patterns, external tasks

### CLAUDE.md sections
- `## Платформа Starfish / OMS` — overview
- `## Платформа Starfish / OMS → Особенности` — default branches, quirks

### External
- `docs/service-index.md` — полный реестр OMS сервисов
- `.claude/skills/oms-java-conventions/SKILL.md` — в деталях
- `.claude/skills/camunda-bpm/SKILL.md` — BPMN patterns

---

## 🔗 Pattern Reference

Этот паттерн **расширяет** `pattern-development-flow.md`:
- Шаги 1-6: идентичны (ПОНИМАНИЕ → КОД → SECURITY → ТЕСТЫ → КОММИТ → MR)
- Шаги 7-8: OMS-специфичные (DATABASE миграции, CAMUNDA BPMN validation)
- Примеры: Java/Spring/Liquibase/BPMN вместо generic

**Использовать как:**
```
Для OMS-разработки:
1. Загрузить pattern-development-oms.md
2. Следовать 8 шагам ВСЕГДА
3. Обращаться к oms-java-conventions для деталей

Для других платформ:
1. Загрузить pattern-development-flow.md
2. Следовать 7 шагам
3. Обращаться к platform-specific skills
```

---

## ✅ Чеклист готовности разработчика перед кодом

- ☐ Прочитал pattern-development-oms.md полностью
- ☐ Понял какие Java-репо трогаю
- ☐ Понял какие BPMN процессы обновляю
- ☐ Знаю какие cloud-config значения менять
- ☐ Знаю как писать Liquibase миграции
- ☐ Знаю как тестировать BPMN embedded в Spring
- ☐ Знаю какой default branch у моего репо
- ☐ Знаю как запустить mvn verify локально
- ☐ Знаю как гайдить MR на правильный репо

---

**Версия:** 1.0  
**Дата:** 2026-10-06  
**Статус:** ✅ Production-ready  
**Платформа:** OMS / Starfish Java Spring Boot + Camunda BPM  
**Автор:** Claude Haiku 4.5 + Antonov Aleksandr (Outsource)

---

## 📍 Файлы

```
.claude/skills/
├── pattern-development-flow.md          (generic - 7 шагов)
├── pattern-development-oms.md          ✅ (OMS - 8 шагов, Java/BPMN)
└── pattern-development-*.md             (future: mobile, site, etc)
```

🚀 **ГОТОВО К ИСПОЛЬЗОВАНИЮ!**
