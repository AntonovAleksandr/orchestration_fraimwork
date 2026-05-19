# Platform: OMS (Starfish)

Order Management System на базе **Starfish OMS** — исполнение заказов, доставка, оркестрация через Camunda BPM.

## Что здесь должно лежать

```
starfish24/
├── awg/                       # GJ-specific overlay (4 репо)
│   ├── integration-gj/        # placeholder
│   ├── bpmn-process/          # BPMN XML процессы
│   ├── cloud-configs/         # per-env YAML
│   └── gloria_ci/             # Jenkinsfile pipelines
└── core/                      # Starfish core (27 репо)
    ├── go/logistics/          # единственный Go-сервис (имеет свой .claude/)
    ├── Order, Stock, Delivery, Dictionary, Camunda, BPM, camunda-worker
    ├── Settings, SSO, API-Gateway, Cloud-config-server
    ├── Parsers, Adapter, Cloud-Message-Gateway, Websocket, OMS-UI, oms-alerts
    ├── product, pay-service, reports, 5post-connector
    └── oms-objects, oms-json, telemetry-starter, cdek-api-sdk, russian-post-api-sdk, local-discovery-client
```

## GitLab

- Группа: https://gitlab.gloria.aaanet.ru/starfish-oms/cloud
- Подгруппы: `awg/` (GJ-specific) + `core/` (Starfish ядро) + `core/go/` (Go-сервисы)

## Setup

См. `<workspace>/README.md` → раздел **Bootstrap → OMS (Starfish)** — там готовый bash-цикл для всех 32 репо.

Полный реестр сервисов: `<workspace>/docs/service-index.md` → раздел "Платформа Starfish / OMS".

## Стек

- **Java** Spring Boot + Maven + Lombok, JKS truststore (mTLS), Spring Cloud Config
- **Go** (logistics) — Gin + Kafka + Redis + Clean Architecture
- **Camunda BPM** — engine + external task workers + BPMN-процессы

## ⚠️ Default branches

Многие репо НЕ на `master`/`main`:
- `Delivery` → `19783+19795`
- `pay-service` → `CLD-1840`
- `cdek-api-sdk` → `CLD-4877`
- `cloud-configs` → `CLD-17047`
- `integration-gj` → `develop`

## Агенты

- `oms-navigator` — навигация по 32 репо
- `oms-java-engineer` — Spring Boot / Maven / Lombok код
- `camunda-bpm-engineer` — BPMN, external task workers, миграции инстансов
- `oms-go-*` (7 агентов) — Go-специфика (импортированы из `logistics/.claude/`, с logistics-контекстом)
