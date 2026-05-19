---
name: oms-java-conventions
description: Use when writing or reviewing Java code for OMS services in platform/starfish24/core/. Covers Spring Boot patterns, Maven (single-module + multi-module), Lombok usage, JKS truststore handling, Spring Cloud Config integration, shared libs (oms-objects/oms-json/telemetry-starter), error handling, Kafka, testing conventions, and CI quirks (Jenkins + bitbucket-pipelines + gitlab-ci coexistence).
---

# OMS Java Conventions

All Java OMS services live in `platform/starfish24/core/<Service>/`. They share a common stack and patterns.

## Before you write code — verify the service's specifics

1. Read `pom.xml` for:
   - Spring Boot version (parent POM)
   - Java version (`<java.version>` property)
   - Whether it's multi-module (`<modules>...</modules>`)
2. Read `lombok.config` to see which features are enabled
3. Look at `src/main/java/<package>/` for existing patterns
4. Look at `src/main/resources/application.yml` for default config
5. Look at `awg/cloud-configs/<service>-gj-<env>.yml` for env-specific overrides

## Maven layout

### Single-module (most services)
```
<service>/
├── pom.xml
└── src/
    ├── main/java/<package>/
    ├── main/resources/
    └── test/java/<package>/
```

### Multi-module (some services)
```
<service>/
├── pom.xml                      # parent
├── <service>-api/               # interfaces, DTOs
│   └── pom.xml
├── <service>-core/              # business logic
│   └── pom.xml
└── <service>-app/               # Spring Boot bootstrap
    └── pom.xml
```

Check `<modules>` in root `pom.xml` to detect this.

## Lombok

`lombok.config` at repo root sets project-wide Lombok behavior. Common features enabled in this codebase:

- `@Data` / `@Value` / `@Builder` — DTOs
- `@Slf4j` — logger field
- `@RequiredArgsConstructor` — Spring DI by final fields
- `@Getter` / `@Setter` — explicit accessors

```java
@Service
@RequiredArgsConstructor
@Slf4j
public class OrderService {
    private final OrderRepository orderRepository;
    private final EventPublisher eventPublisher;

    public Order createOrder(CreateOrderRequest request) {
        log.info("Creating order for tenant {}", request.getTenantId());
        // ...
    }
}
```

**Don't** mix Lombok and manually written getters/setters/constructors in the same class — pick one style.

## Spring Boot patterns

### REST Controller
```java
@RestController
@RequestMapping("/api/v1/orders")
@RequiredArgsConstructor
public class OrderController {
    private final OrderService orderService;

    @PostMapping
    public ResponseEntity<OrderDto> create(@RequestBody @Valid CreateOrderRequest req) {
        return ResponseEntity.status(HttpStatus.CREATED)
            .body(orderService.create(req));
    }
}
```

### Service
```java
@Service
@RequiredArgsConstructor
@Slf4j
public class OrderService { ... }
```

### Repository (Spring Data JPA)
```java
public interface OrderRepository extends JpaRepository<OrderEntity, Long> {
    Optional<OrderEntity> findByExternalId(String externalId);
}
```

## Configuration

### `application.yml` — defaults only
```yaml
spring:
  application:
    name: order-service
  cloud:
    config:
      uri: ${CONFIG_SERVER_URI:http://localhost:8888}

# Domain config — overridden by Spring Cloud Config in deployed envs
order:
  max-items: 100
```

### `bootstrap.yml` (Spring Cloud)
Sometimes there's a `bootstrap.yml` with Spring Cloud Config wiring — loads BEFORE `application.yml`.

### Per-env values come from `awg/cloud-configs/`
```
awg/cloud-configs/
├── order-service-gj-staging.yml
├── order-service-gj-preprod.yml
└── order-service-gj-prod.yaml      # note: yaml vs yml inconsistency!
```

⚠️ The extension varies (`.yml` vs `.yaml`). Spring treats them equivalently, but `git mv` / file-search must match exactly.

## Shared libs

Imported via Maven:

```xml
<dependency>
    <groupId>com.starfish.oms</groupId>
    <artifactId>oms-objects</artifactId>
    <version>${oms-objects.version}</version>
</dependency>
```

| Lib | Use when |
|-----|----------|
| `oms-objects` | Need a DTO that's shared with other services — find it here first |
| `oms-json` | JSON serialization/deserialization with project conventions |
| `telemetry-starter` | Add metrics/tracing — auto-configures via Spring Boot starter |
| `cdek-api-sdk` | СДЭК API calls |
| `russian-post-api-sdk` | Russian Post API calls |
| `local-discovery-client` | Service discovery client (if not using Spring Cloud LoadBalancer directly) |

**Before reinventing:** grep `oms-objects/src/main/java/` for related class.

## JKS truststore (mTLS)

`client.truststore.jks` is committed in many service repos. It's the truststore for outbound mTLS:

```yaml
javax:
  net:
    ssl:
      trustStore: classpath:client.truststore.jks
      trustStorePassword: ${TRUSTSTORE_PASSWORD}
```

Or in Java code via system properties (set in `Dockerfile` ENTRYPOINT).

⚠️ **Before adding/changing certs in JKS** — verify it's not a secret leakage path. Public CA certs are fine; private keys would not be (look for `.p12` or PEM in same directory as clues).

To inspect:
```bash
keytool -list -keystore client.truststore.jks
```

## Logging

Use SLF4J via Lombok's `@Slf4j`:
```java
log.info("...");                 // structured
log.error("Failed: {}", id, ex); // pass exception as LAST arg
```

Don't:
- `System.out.println` (won't go through logging pipeline)
- `Throwable.printStackTrace()` (same)
- String concatenation in log args (`log.info("X: " + foo)`) — use `{}` placeholders

## Testing

- **Unit tests** in `src/test/java/`
- Mockito + AssertJ + JUnit 5 (typical Spring Boot 2.x+/3.x)
- For Spring context tests: `@SpringBootTest` or sliced (`@WebMvcTest`, `@DataJpaTest`)
- For Kafka: Spring Kafka Test, embedded Kafka or Testcontainers
- For Camunda: `@SpringBootTest` with `@MockBean` for external services, or `ProcessEngineRule` for engine tests

Maven commands:
```bash
mvn clean test                    # unit only
mvn clean verify                  # unit + integration
mvn -pl <module> test             # multi-module: one module
mvn -pl <module> -am test         # also build deps
```

## Error handling

```java
@ControllerAdvice
@Slf4j
public class GlobalExceptionHandler {
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ErrorResponse> handleBusiness(BusinessException ex) {
        log.warn("Business error: {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
            .body(new ErrorResponse(ex.getCode(), ex.getMessage()));
    }
}
```

Use:
- Custom `BusinessException` (or whatever exists in the codebase) for expected business errors
- Let `RuntimeException` propagate to `@ControllerAdvice` for unexpected
- Don't catch `Exception` and rethrow as `RuntimeException` without preserving cause

## Camunda integration

For Camunda-specific patterns see `.claude/skills/camunda-bpm/SKILL.md`. Key points:
- External task pattern is preferred over embedded `JavaDelegate`
- Workers in `core/camunda-worker/` subscribe by topic name
- Process variables are typed but stored as JSON

## CI quirks

Many repos have:
- `bitbucket-pipelines.yml` — legacy (Bitbucket migration leftover)
- `.gitlab-ci.yml` — possibly current
- Jenkins references via `awg/gloria_ci/Jenkinsfile*` — for actual deploys

**Don't assume which is canonical.** Check recent pipeline activity:
```
mcp__gj-buddy__gitlab_list_pipelines(projectId="starfish-oms/cloud/core/<Service>", per_page=5)
```

## Anti-patterns

- Hardcoded URLs/credentials in code or `application.yml` — they belong in `awg/cloud-configs/<svc>-gj-<env>.{yml,yaml}`
- New config key without updating all 3 env files
- Logging at INFO level inside hot loops (volume → ELK cost)
- Catching `Exception` broadly (mask real causes)
- Adding a dep to parent `pom.xml` without checking children
- Mixing Lombok-generated and manual accessors
- Editing `client.truststore.jks` directly — use `keytool`
- Adding new shared types to a single service instead of `oms-objects`

## Verification

Before declaring done:
- `mvn clean verify` passes (locally or via CI)
- If touched a property — verify it exists in `awg/cloud-configs/<svc>-gj-{staging,preprod,prod}.{yml,yaml}`
- If touched Camunda — verify BPMN-side too (BPMN topic must match handler subscription)
- If touched a shared lib — verify dependent services still compile (could be many)
