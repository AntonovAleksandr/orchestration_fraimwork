---
name: oms-stack-anatomy
description: Use when working with the Gloria Jeans OMS (starfish24). Explains the multi-repo layout — awg/ (GJ overlays) vs core/ (Starfish core), Java services vs the single Go service (logistics), Camunda BPM at the center, Spring Cloud Config for env-specific values. Trigger on anything related to platform/starfish24/.
---

# OMS Stack Anatomy

`platform/starfish24/` mirrors `starfish-oms/cloud/` in GitLab — two top-level groups:

```
platform/starfish24/
├── awg/                              # GJ-specific overlay (4 repos)
│   ├── integration-gj/               # almost empty (README only); placeholder
│   ├── bpmn-process/process/         # BPMN XML process definitions (Camunda)
│   ├── cloud-configs/                # per-service per-env YAML configs
│   │   └── <service>-gj-{preprod,prod,staging}.{yml,yaml}
│   └── gloria_ci/                    # Jenkinsfile pipelines
│       ├── Jenkinsfile
│       ├── Jenkinsfile_go_services
│       ├── Jenkinsfile_oms_deploy_preprod_prod
│       └── Jenkinsfile_oms_deploy_staging
└── core/                             # 27 main repos (Starfish OMS core)
    ├── go/
    │   └── logistics/                # Go service (with own .claude/ + CLAUDE.md)
    └── (Java services + libs)
```

## Java services in `core/` — what each does

### Core orchestration
| Service | Role |
|---------|------|
| `Order` | Order CRUD, lifecycle, state |
| `Camunda` | Camunda BPM engine (Spring Boot wrapper) |
| `camunda-worker` | External task workers (subscribe to BPMN topics) |
| `BPM` | BPM-related service (verify role from README) |
| `Delivery` | Доставка — courier scheduling, shipping (branch `19783+19795`) |

### Domain services
| Service | Role |
|---------|------|
| `Stock` | Склад / inventory |
| `Dictionary` | Reference data |
| `Settings` | Service settings |
| `SSO` | Single Sign-On |
| `API-Gateway` | API routing/aggregation |
| `Cloud-config-server` | Spring Cloud Config server (serves `awg/cloud-configs/`) |
| `Parsers` | External format parsers |
| `Adapter` | Generic adapter service |
| `Cloud-Message-Gateway` | Messaging gateway |
| `Websocket` | WS for real-time UI |
| `OMS-UI` | Admin UI |
| `oms-alerts` | Alerting |
| `product` | OMS-side product info |
| `pay-service` | Payments (branch `CLD-1840`) |
| `reports` | Reports |
| `5post-connector` | 5post (СДЭК) carrier integration |

### Shared Java libs (consumed via Maven)
| Lib | Provides |
|-----|----------|
| `oms-objects` | Shared DTOs / model objects |
| `oms-json` | JSON utilities |
| `telemetry-starter` | Spring Boot starter for telemetry (metrics, tracing) |
| `cdek-api-sdk` | СДЭК API client (branch `CLD-4877`) |
| `russian-post-api-sdk` | Russian Post API client |
| `local-discovery-client` | Service discovery client |

## Go service in `core/go/`

| Service | Role |
|---------|------|
| `logistics` | Delivery pricing/availability rule engine. Has its own ready-to-use `.claude/` with 7 agents + extensive `CLAUDE.md`. |

The logistics repo keeps its own Go agents under `platform/starfish24/core/go/logistics/.claude/agents/`. Root Go agents are generic `platform-new` agents and intentionally do not duplicate logistics-specific OMS context.

## GJ-specific overlay (`awg/`)

| Repo | Role |
|------|------|
| `integration-gj` | (almost empty; integration namespace) |
| `bpmn-process` | BPMN XML definitions for Camunda — these are the actual workflows |
| `cloud-configs` | Per-service per-env config values fetched by Spring Cloud Config |
| `gloria_ci` | Jenkins pipelines (`Jenkinsfile*`) for build/deploy |

## How the pieces connect

```
        ┌───────────────┐
        │   Camunda     │  ◀── BPMN deployed from awg/bpmn-process/
        │  (BPM engine) │
        └───────┬───────┘
                │  external tasks
                ▼
        ┌───────────────┐
        │ camunda-worker│  ◀── Java handlers subscribing to topics
        └───────┬───────┘
                │  calls
                ▼
  ┌────────┬──────┬────────┬─────────┬─────────┐
  │ Order  │Stock │Delivery│logistics│pay-svc  │ ... domain services
  └────────┴──────┴────────┴─────────┴─────────┘
                │   │
                │   └──→ Kafka (events between services)
                ▼
        ┌───────────────┐
        │ Cloud-config- │  ◀── awg/cloud-configs/ (per env values)
        │   server      │
        └───────────────┘
```

## Standard Java service layout (e.g. Order)

```
core/Order/
├── pom.xml                            # Maven (root — may declare modules)
├── lombok.config                      # Lombok config
├── client.truststore.jks              # mTLS truststore (committed; check if real secrets)
├── Dockerfile
├── docker-compose.yml                 # local dev infra
├── bitbucket-pipelines.yml            # legacy CI (probably unused)
├── .gitlab-ci.yml                     # current CI (verify)
├── ci/                                # CI scripts/configs
├── deploy/                            # deployment manifests
└── src/
    ├── main/
    │   ├── java/<package>/            # business code
    │   └── resources/
    │       ├── application.yml        # default config (env values via Cloud Config)
    │       └── ...
    └── test/
```

## Per-env configuration

Each service has YAML in `awg/cloud-configs/<service>-gj-<env>.{yml,yaml}` — fetched at runtime via Spring Cloud Config server. Local `application.yml` only has defaults; **real values come from this directory** for deployed envs (preprod/staging/prod).

**When adding a new config key:** also add it to `awg/cloud-configs/<svc>-gj-prod.yaml` (and staging/preprod) — otherwise prod will start without it.

## Deploy / CI

- **Jenkins** is the actual CI/CD orchestrator (see `awg/gloria_ci/Jenkinsfile*`)
- Many repos still have `bitbucket-pipelines.yml` (legacy) AND `.gitlab-ci.yml` AND Jenkins references — verify which one is canonical by looking at recent pipelines via `gitlab-investigator` agent or Jenkins UI
- Deploy targets are typically Kubernetes (helm charts in `deploy/` of each repo)

## Where OMS sits in the bigger architecture

- **Upstream**: Integration service (`platform/integration/`) sends order requests via REST/Kafka
- **Downstream**: 
  - Carriers (СДЭК, Почта России, 5post, etc.) — via their SDK libs and connector services
  - Payment processors — via `pay-service`
- **Notification**: WS to `Websocket` service → admin UI / connected clients

## Anti-patterns

- Mixing app code into `awg/cloud-configs/` (it's purely config)
- Editing `awg/bpmn-process/*.bpmn` without considering running process instances
- Treating `awg/gloria_ci/Jenkinsfile*` and `.gitlab-ci.yml` as equivalent — they may diverge
- Forgetting to update env configs across all 3 envs when adding a key
- Cloning into `core/` something that should be in `awg/` (GJ-specific should live in awg)
