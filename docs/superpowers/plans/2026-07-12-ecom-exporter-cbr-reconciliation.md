# Ecom Exporter CBR Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Создать конечное Go-приложение `ecom-exporter`, которое по `--type=export-cbr-recon` формирует эквивалентную текущей Integration CSV-выгрузку из read-only OMS PostgreSQL replica и отправляет её в 1С ЦБР, а по `--dry-run` формирует файл без отправки.

**Architecture:** Kubernetes CronJob запускает один процесс и владеет расписанием. Приложение следует шаблону `platform-new`: `cmd → app/wire → domain ports → adapters/platform`. Домен пакетно получает базовые заказы и связанные данные, повторяет PHP-маппинг 20 полей и последовательно пишет временный CSV.

**Tech Stack:** Go 1.26.2, `pgx/v5`, `gj-go-logger` v1.0.5, standard `flag`, `net/http`, `encoding/csv`, `httptest`, PostgreSQL integration tests, Alpine multi-stage Docker image.

## Global Constraints

- Новый независимый репозиторий: `$WORKSPACE/platform-new/ecom-exporter`; module `gitlab.gloria.aaanet.ru/greensight/gj/go/ecom-exporter`.
- OMS внешняя: не менять OMS-код, схему, view, индексы или API.
- Читать только настроенную через env read-only OMS replica.
- CLI: `ecom-exporter --type=export-cbr-recon [--dry-run]`.
- MVP повторяет PHP-выгрузку 1:1: 60 дней, три группы, дедупликация, 20 колонок и текущая семантика.
- CronJob владеет расписанием и использует `concurrencyPolicy: Forbid`.
- CSV только во временном локальном файле; без S3/MinIO и журнала запусков.
- Отправка: не более 3 попыток с backoff и structured logs.
- `--dry-run` выполняет всю сборку, но не обращается к ЦБР.
- Конфигурация только через env/Secret; `.env` не коммитить.
- Домен не импортирует `app`, `platform`, `adapters`, `pgx` или `net/http`.
- Не исправлять бизнес-семантику до доказанного parity и успешного end-to-end запуска.

---

## File Map

```text
platform-new/ecom-exporter/
├── cmd/ecom-exporter/main.go
├── internal/app/{app.go,options.go,container.go}
├── internal/app/wire/export_cbr_recon.go
├── internal/domains/cbrreconciliation/
│   ├── {types.go,ports.go,service.go,mapper.go,csv.go,boundary_test.go}
│   └── *_test.go
├── internal/adapters/cbrreconciliation/
│   ├── {oms_repository.go,queries.go,cbr_client.go,temp_file.go}
│   └── *_test.go
├── internal/platform/{config,logger,storage,retry}/
├── scripts/compare-cbr/{main.go,compare.go,compare_test.go}
├── deploy/cronjob.yaml
├── docs/{configuration.md,runbook.md,parity-runbook.md}
└── {go.mod,go.sum,Makefile,Dockerfile,.gitlab-ci.yml,.gitignore,README.md}
```

### Task 1: Bootstrap repository and strict CLI

**Files:** Create `go.mod`, `cmd/ecom-exporter/main.go`, `internal/app/options.go`, `internal/app/options_test.go`, `.gitignore`, `Makefile`.

**Interfaces:** Produces `ParseOptions(args []string) (Options, error)`, `ExportTypeCBRRecon = "export-cbr-recon"`, `Options{Type ExportType, DryRun bool}`.

- [ ] Write table tests for valid normal/dry-run calls, missing `--type`, unknown `export-cbr`, and positional arguments.
- [ ] Run `go test ./internal/app -run TestParseOptions -v`; expect FAIL because parser does not exist.
- [ ] Implement with private `flag.FlagSet`, `flag.ContinueOnError`, rejected positional args, and no env/external access.
- [ ] Add thin `main`: parse → `app.New` → `Run`; only `main` may terminate the process.
- [ ] Add `make build`, `make test`, `make run` (`--type=export-cbr-recon`).
- [ ] Run `go test ./... && make build && ./bin/ecom-exporter --type=bad`; expect tests/build success and non-zero invalid-type exit.
- [ ] Commit: `git commit -m "chore: bootstrap ecom exporter CLI"`.

Required `go.mod` direct dependencies:

```go
require (
	github.com/google/uuid v1.6.0
	github.com/jackc/pgx/v5 v5.7.4
	gitlab.gloria.aaanet.ru/go-pkg/gj-go-logger v1.0.5
)
```

### Task 2: Runtime configuration and infrastructure

**Files:** Create `internal/platform/config/{config.go,config_test.go}`, `logger/logger.go`, `storage/postgres.go`, `retry/{policy.go,policy_test.go}`.

**Interfaces:** Produces `config.Load() Config`, `Config.Validate(dryRun bool) error`, `storage.NewPool(ctx, dsn)`, `retry.Policy{MaxAttempts, Delays}`.

- [ ] Write failing tests for exact env contract and defaults: `OMS_QUERY_TIMEOUT=30s`, `OMS_BATCH_SIZE=500`, `CBR_REQUEST_TIMEOUT=60s`, `CBR_RETRY_DELAYS=1s,3s`, `TEMP_DIR=/tmp`.
- [ ] Require `OMS_DB_DSN`; require CBR URL/auth/credentials only when `dryRun=false`; restrict batch to `50..2000`; require exactly two positive retry delays.
- [ ] Run `go test ./internal/platform/config ./internal/platform/retry -v`; expect FAIL, then implement typed config and make it PASS.
- [ ] Implement `pgxpool` with 5-second ping and `AfterConnect` setting `default_transaction_read_only=on`; never log DSN/credentials.
- [ ] Follow `policyengine` logger setup with `gj-go-logger`.
- [ ] Commit: `git commit -m "feat: add exporter runtime configuration"`.

Exact config shapes:

```go
type OMSConfig struct { DSN string; QueryTimeout time.Duration; BatchSize int }
type CBRConfig struct {
	BaseURL, AuthURL, Username, Password string
	RequestTimeout time.Duration
	Retry retry.Policy
}
type Config struct { AppName, Env, TempDir string; OMS OMSConfig; CBR CBRConfig }
```

### Task 3: CBR reconciliation domain boundary

**Files:** Create `internal/domains/cbrreconciliation/{types.go,ports.go,service.go,service_test.go,boundary_test.go}`.

**Interfaces:** Produces `Order`, `Item`, `Payment`, `StatusDates`, `ExportRow`, `ExportResult`, and `Service.Run(ctx, Request)`.

- [ ] First write boundary test rejecting imports from `internal/app`, `internal/platform`, `internal/adapters`, `pgx`, and `net/http`.
- [ ] Define consumer ports exactly:

```go
type OrderSource interface {
	ForEachBatch(context.Context, time.Time, int, func([]Order) error) error
}
type Artifact interface {
	io.Writer
	Path() string
	Close() error
	Remove() error
	Open() (io.ReadCloser, error)
}
type ArtifactFactory interface { Create(context.Context, string) (Artifact, error) }
type OpenBody func() (io.ReadCloser, error)
type Destination interface { Send(context.Context, string, OpenBody, int64) error }
type Mapper interface { Map(Order) (ExportRow, error) }
```

- [ ] Write service tests: fixed cutoff propagated; one row per unique OMS id; close before send; dry-run makes zero destination calls; success removes artifact; failure returns categorized error; result has rows/bytes/SHA-256.
- [ ] Run focused tests and expect FAIL; implement streaming orchestration with `sha256.New()` and `io.MultiWriter`; do not hold all rows in memory.
- [ ] Run `go test ./internal/domains/cbrreconciliation -v`; expect PASS including boundary test.
- [ ] Commit: `git commit -m "feat: define CBR reconciliation domain"`.

### Task 4: Exact 20-column mapper and CSV

**Files:** Create `internal/domains/cbrreconciliation/{mapper.go,mapper_test.go,csv.go,csv_test.go}`. Reference current PHP `CbrReconOrderMutator.php` and `CbrReconCsvConverter.php`.

**Interfaces:** Produces `NewMapper() Mapper`, `CSVHeader() []string`, `ExportRow.Values() []string`.

- [ ] Freeze anonymized golden cases: prepaid completed, COD completed, returned cancelled payment, SFS, reserve, pickup, paid delivery, cancelled item, missing dates.
- [ ] Assert all 20 columns in exact order:

```text
code,totalPrice,deliveryPrice,totalProduct,products,redeemedProduct,
checked_valid,datePayment,datePicked,dateCreateDelivered,dateCancelled,
orderDateDelivered,dateLost,datePaymentReturn,paymentType,deliveryTypeId,
orderStatus,createDatePayment,dateDelivering,sfs
```

- [ ] Run mapper/CSV tests; expect FAIL.
- [ ] Port rules without cleanup: `createDatePayment=datePayment`, `orderDateDelivered=dateCreateDelivered`, returned online payment uses cancellation date, redeemed products only for `COMPLETED`, paid delivery adds one product.
- [ ] Copy delivery mappings `76,100,111,112,113,114` exactly from Confluence page `74155886` and current Integration configuration.
- [ ] Match header, delimiter, escaping, dates and line endings byte-for-byte with PHP golden CSV; do not add BOM.
- [ ] Run domain tests; expect PASS. Commit: `git commit -m "feat: port CBR CSV mapping contract"`.

### Task 5: Batch OMS replica repository

**Files:** Create `internal/adapters/cbrreconciliation/{queries.go,oms_repository.go,oms_repository_test.go}`, `testdata/{schema.sql,orders.sql}`.

**Interfaces:** Produces `NewOMSRepository(pool *pgxpool.Pool, queryTimeout time.Duration) *OMSRepository`, implementing `OrderSource`.

- [ ] Verify physical column names from live read-only catalog and Java mappings; encode the used subset of `order_t`, `shipping`, `item`, `payment`, `order_custom_attribute`, `custom_attribute`, `status_history` in `schema.sql` so drift is visible.
- [ ] Seed and test: SFS included; reserve included; fulfillment+pickup with `DELIVERING` included; without it excluded; old/deleted/foreign-tenant excluded exactly as PHP API; overlaps emitted once; cutoff boundaries deterministic.
- [ ] Run repository tests; expect FAIL.
- [ ] Implement stable keyset pagination by `(date_time_created,id)`, one fixed cutoff, exact tenant/deleted filters and three groups. Use `EXISTS status_history` for third group.
- [ ] For each base batch, fetch shipping, items, payments, order attributes, item attributes and required histories using array predicates; never query once per order.
- [ ] Assert constant upper bound of seven SQL operations per batch and context deadline propagation as `oms_query_error`.
- [ ] On safe replica run `SHOW transaction_read_only` (expect `on`) and `EXPLAIN (ANALYZE, BUFFERS)` for representative cutoff; record sanitized plan in parity runbook, never run against primary.
- [ ] Run adapter tests; expect PASS. Commit: `git commit -m "feat: read CBR export data from OMS replica"`.

### Task 6: Temporary artifact and CBR client

**Files:** Create `internal/adapters/cbrreconciliation/{temp_file.go,temp_file_test.go,cbr_client.go,cbr_client_test.go}`.

**Interfaces:** Produces `NewTempFileFactory(dir)`, `NewCBRClient(httpClient, cfg, retryPolicy)`.

- [ ] Test temp files use `os.CreateTemp`, prefix `cbr-recon-<runID>-`, mode `0600`, reopen after close, and removal only on explicit `Remove`.
- [ ] With `httptest`, test auth, Bearer use, `POST /api/Starfish/1CCBROrdersList`, `Content-Type: csv/text`, and one `OpenBody` call with a freshly closed reader for each attempt.
- [ ] Assert `202` succeeds; sequence `500,502,202` uses three attempts; `400` is terminal; transport/timeout, `408`, `429`, and `5xx` retry at most three times.
- [ ] Cap response text included in safe errors; never log request body, credentials or token.
- [ ] Implement backoff from configured two delays and context cancellation.
- [ ] Run focused tests; expect PASS. Commit: `git commit -m "feat: send CBR export with bounded retries"`.

### Task 7: Composition root and executable lifecycle

**Files:** Create `internal/app/{container.go,app.go,app_test.go}`, `internal/app/wire/export_cbr_recon.go`; modify `main.go`.

**Interfaces:** Produces `app.New(options) (*App,error)` and `App.Run(ctx) error`.

- [ ] Write tests proving config validates before DB access; run id is UUID; cutoff calculated once; SIGTERM cancels work; pool closes on all paths; dry-run accepts absent CBR secrets; normal mode rejects them.
- [ ] Implement wiring only in `app`/`wire`; `wire.ExportCBRRecon` returns the configured service without global mutation.
- [ ] Emit final success log with `run_id,export_type,dry_run,cutoff_time,rows,bytes,sha256,duration`; failure adds safe stage/category.
- [ ] Run `go test ./...`, invalid-type smoke test, and dry-run missing-DSN smoke test. Expect invalid type before env access and no CBR validation in dry-run.
- [ ] Commit: `git commit -m "feat: wire CBR reconciliation export job"`.

### Task 8: Standalone parity comparator

**Files:** Create `scripts/compare-cbr/{main.go,compare.go,compare_test.go}`, `testdata/{equal-old.csv,equal-new.csv,different.csv}`; modify `Makefile`.

**Interfaces:** Command `go run ./scripts/compare-cbr --old old.csv --new new.csv`; exit `0` equal, `1` differences, `2` invalid input.

- [ ] Write tests that normalize order by `code`, validate exact 20 headers, reject duplicate codes, preserve empties, and emit `{code,column,old,new}` differences.
- [ ] Summary must include counts for old/new, missing, extra, duplicates and per-column differences.
- [ ] Run tests; expect FAIL; implement with default maximum 100 details and `--max-details` override. Never print full rows.
- [ ] Run equal fixture (expect `0`, `equal=true`) and different fixture (expect `1`, non-zero counts).
- [ ] Commit: `git commit -m "test: add CBR export parity comparator"`.

### Task 9: Image, CronJob, CI and runbooks

**Files:** Create `Dockerfile`, `.gitlab-ci.yml`, `deploy/cronjob.yaml`, `docs/{configuration.md,runbook.md,parity-runbook.md}`, `README.md`.

**Interfaces:** Image entrypoint `/app/bin/ecom-exporter`; CronJob args `--type=export-cbr-recon`.

- [ ] Follow `policyengine` Go 1.26 Alpine builder/Nexus setup and non-root Alpine runtime; copy only exporter binary.
- [ ] Add CronJob essentials:

```yaml
concurrencyPolicy: Forbid
successfulJobsHistoryLimit: 3
failedJobsHistoryLimit: 5
jobTemplate:
  spec:
    backoffLimit: 0
    template:
      spec:
        restartPolicy: Never
        containers:
          - name: ecom-exporter
            args: ["--type=export-cbr-recon"]
```

- [ ] Reference credentials only via `secretKeyRef`; leave schedule as environment deployment value, not application config.
- [ ] Document every env/default/secret, exit codes, dry-run, failure categories, parity procedure, controlled send, and rollback.
- [ ] Include existing `golang-backend-pipeline.yml`; run `go test ./...`, `make build`, Docker build and invalid-type container smoke test.
- [ ] Commit: `git commit -m "chore: package CBR exporter job"`.

### Task 10: Parity evidence and controlled rollout

**Files:** Modify `docs/parity-runbook.md`; create `docs/evidence/cbr-recon-parity-summary.md` (no CSV/PII).

**Interfaces:** Produces go/no-go evidence; does not alter mapping or disable legacy cron by itself.

- [ ] Capture legacy reference and new dry-run with one shared cutoff. If legacy cannot accept cutoff, record exact extraction interval and classify later mutations separately.
- [ ] Run comparator; acceptance is zero missing, extra, duplicates and field differences across all 20 columns.
- [ ] Repeat multiple production-like runs; record only run ids, cutoff, counts, hashes, duration, replica lag observation and summaries.
- [ ] Suppress legacy send for one controlled window, run new normal export, confirm HTTP success and downstream CBR reconciliation completion.
- [ ] Only after CBR confirmation enable new CronJob and disable old Integration schedule; keep legacy code during stabilization.
- [ ] Document rollback: disable new CronJob and restore old schedule.
- [ ] Commit sanitized evidence: `git commit -m "docs: record CBR exporter parity evidence"`.

## Final Verification Gate

Run from `platform-new/ecom-exporter`:

```bash
go test ./...
go vet ./...
make build
docker build -t ecom-exporter:verify .
git status --short
```

Completion requires: all commands exit `0`; boundary test passes; dry-run proves zero destination calls; retry tests prove at most three attempts; repository tests prove bounded queries; approved comparator runs are exact; CBR confirms end-to-end; no credentials, CSV, order data, `.env`, or developer-specific absolute paths are committed.
