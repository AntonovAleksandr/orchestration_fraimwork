---
name: SKILL
version: 1.0.0
layer: camunda-bpm
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# Camunda BPM in OMS

## Development pattern reference

For Camunda/BPMN development in OMS, follow `.claude/skills/pattern-development-oms.md` step 7 (Camunda BPMN Process Validation) — topic matching, compensating transactions, running instance safety, and process variables documentation.

The OMS orchestrates business processes via Camunda BPM. Three pieces are involved:

| Piece | Path |
|-------|------|
| Engine (Spring Boot wrapping Camunda) | `platform/starfish24/core/Camunda/` |
| External task workers | `platform/starfish24/core/camunda-worker/` |
| BPMN/DMN process definitions | `platform/starfish24/awg/bpmn-process/process/` |
| Per-env engine config | `platform/starfish24/awg/cloud-configs/camunda-gj-*.{yml,yaml}` |

Plus a service named `core/BPM/` (verify role — may be related management/UI).

## BPMN basics (mental model)

A BPMN process is an XML file describing a workflow:
- **Start event** → **Tasks** → **Gateways** (decisions) → **End event**
- **Service Task** with `camunda:type="external"` and a `camunda:topic="<name>"` — this is the integration point with your Java code

Example excerpt:
```xml
<bpmn:serviceTask id="ValidateOrder"
                  name="Validate order"
                  camunda:type="external"
                  camunda:topic="validateOrder" />
```

## External task pattern — preferred integration

External tasks decouple BPMN from Java code: the BPMN says "this task needs `validateOrder` work"; your worker subscribes to that topic and does the work.

### Why preferred (vs embedded `JavaDelegate` or `camunda:expression`)
- BPMN doesn't import Java classes → cleaner
- Worker can run in a separate JVM / pod → independent scaling
- Failure isolation: if your worker crashes, the BPMN engine stays healthy

### Implementation skeleton (in `core/camunda-worker/`)
```java
@Component
@ExternalTaskSubscription(
    topicName = "validateOrder",
    lockDuration = 30000          // ms — how long this worker holds the task
)
@RequiredArgsConstructor
@Slf4j
public class ValidateOrderHandler implements ExternalTaskHandler {

    private final OrderService orderService;

    @Override
    public void execute(ExternalTask task, ExternalTaskService svc) {
        String orderId = (String) task.getVariable("orderId");
        log.info("Validating order {}", orderId);

        try {
            var result = orderService.validate(orderId);
            svc.complete(task, Map.of(
                "validationResult", result.isValid(),
                "validationErrors", result.errors()
            ));
        } catch (OrderNotValidException e) {
            // BUSINESS error — handled in BPMN by an error boundary event
            svc.handleBpmnError(task, "ORDER_INVALID", e.getMessage());
        } catch (Exception e) {
            // TECHNICAL error — retry with backoff; eventually becomes incident
            int retries = task.getRetries() != null ? task.getRetries() - 1 : 3;
            svc.handleFailure(task, e.getMessage(), stack(e), retries, 60000);
        }
    }
}
```

### Three completion paths

| Path | When | Effect |
|------|------|--------|
| `complete(...)` | Work succeeded | Process moves forward |
| `handleBpmnError(...)` | Designed business error path | Triggers BPMN error boundary event |
| `handleFailure(...)` | Technical/unexpected error | Decrements retries; when 0, creates incident (requires Cockpit intervention) |

## Process variables

- Variables passed at process start, mutated by tasks, read by gateways
- Stored as JSON (typed) in `act_ru_variable` (runtime) and `act_hi_varinst` (history)
- **Keep them small** — every transaction persists them. Store IDs, fetch detail from service DB.

```java
// Get
String orderId = (String) task.getVariable("orderId");
Boolean valid = (Boolean) task.getVariable("validationResult");

// Set on complete
svc.complete(task, Map.of(
    "newOrderId", "12345",
    "newStatus", "VALIDATED"
));
```

## Deployment

Camunda Spring Boot can auto-deploy BPMN files placed in `classpath:processes/` or a configured directory. Verify in `core/Camunda/src/main/resources/application.yml` (or its variant):

```yaml
camunda:
  bpm:
    deployment-resource-pattern: "classpath*:**/*.bpmn,classpath*:**/*.dmn"
    auto-deployment-enabled: true
```

BPMN files from `awg/bpmn-process/process/` are typically packaged into Camunda's image at build time (check the service's CI to confirm how).

## Versioning & migration

- Camunda deploys BPMN by **version**. Each deployment = new version.
- **Running instances continue with their original definition** unless you migrate them.
- New instances always use the latest deployed version.

### Safe BPMN changes (no migration needed)
- Adding entirely new processes
- Changing visual labels (no semantic change)
- Adding new versions while old runs to completion

### Unsafe (running instances would break)
- Renaming a step that running instances haven't yet reached
- Removing a step
- Changing topic name (running instances stuck waiting for old topic)

For **unsafe changes**, build a **migration plan**:
```java
MigrationPlan plan = processEngine.getRuntimeService()
    .createMigrationPlan(sourceProcDefId, targetProcDefId)
    .mapEqualActivities()                  // automatic for matching IDs
    .mapActivities("oldId", "newId")       // explicit
    .build();
processEngine.getRuntimeService().newMigration(plan)
    .processInstanceIds(instanceIds)
    .execute();
```

Test the migration on staging before prod.

## Decisions (DMN)

DMN tables for business rules:
```xml
<dmn:decisionTable hitPolicy="UNIQUE">
    <dmn:input id="orderAmount" label="Order amount" />
    <dmn:output id="discount" label="Discount %" />
    <dmn:rule>...</dmn:rule>
</dmn:decisionTable>
```

Used from BPMN via `businessRuleTask` with `camunda:decisionRef="decisionKey"`.

## Troubleshooting

### Stuck process
1. Open Camunda Cockpit (web UI) — find the instance by process key or business key
2. See the current "token position" (which step is the process at)
3. Look at recent activity log (`act_hi_actinst`) and variables (`act_hi_varinst`)
4. Incidents in `act_ru_incident` — failed tasks needing manual intervention

### Worker not picking up tasks
Possible causes:
- Worker not started (check logs)
- Topic name mismatch (BPMN says `validateOrder`, handler subscribes to `validate_order`)
- Lock duration too short — task gets re-fetched but worker dies before completion
- Network/connectivity to engine

### Engine connection issues
Check `awg/cloud-configs/camunda-gj-<env>.{yml,yaml}` for endpoint config. Check k8s service DNS resolves for cross-service calls.

## Querying engine state

Useful tables (PostgreSQL/Oracle/etc. depending on Camunda DB):
- `act_re_procdef` — deployed process definitions
- `act_ru_execution` — runtime execution tree
- `act_ru_task` — user tasks (if any)
- `act_ru_variable` — runtime variables
- `act_ru_external_task` — pending external tasks
- `act_ru_incident` — failed tasks needing attention
- `act_hi_*` — history (longer retention; helpful for postmortem)

## Anti-patterns

- **Embedded service task with Java expression** — couples BPMN to Java, hard to test, hard to scale workers independently
- **Long-running synchronous handler** — external task `lockDuration` is fixed; if work takes longer, the task is re-fetched and you'll have duplicate work
- **Big objects in process variables** — every transaction re-serializes. Store IDs.
- **Hardcoded topic names** — use shared constants (or at least co-located config) between BPMN and Java
- **Ignoring retries** — `handleFailure(task, msg, details, 0, 0)` discards retries; incident created immediately
- **Modifying BPMN without thinking about versioning** — running instances may break
- **Skipping the migration plan when changing a step** — you'll have inconsistent process instances

## Verification before declaring done

- BPMN opens in Camunda Modeler (or at least XML-valid)
- Worker compiles + tests pass
- Topic name in BPMN == topic name in handler subscription (case-sensitive!)
- New config keys in `awg/cloud-configs/camunda-gj-<env>.*`
- If you changed an existing process, you have a migration plan (or confirmed no running instances will reach the changed area)

## When to escalate

- Java implementation help → `oms-java-engineer`
- "Where does this BPMN run?" / "Where is this worker?" → `oms-navigator`
- Cross-system orchestration design → `architect`
- Live incident → `logs-detective` + Camunda Cockpit
