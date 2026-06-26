# RecommendationEngine: полное удаление sqlite (Postgres-only) — план

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Убрать из движка `recomendationengine` всё, что связано с sqlite (драйвер, инициализация, sqlite-миграции, SQLite→PG шим-переписыватель), перевести весь runtime-SQL на нативный Postgres (литеральные `$n`), и привести тесты к юнитам без БД.

**Architecture:** Вариант B — полный native-PG rewrite, шим удалён, ноль placeholder-хелперов. `Init` всегда Postgres. Все DB-зависимые тесты удаляются (строго без БД); переписанный SQL верифицируется только manual staging smoke. Нативные PG-миграции (`migrations_postgres.go`) уже существуют и становятся единственным путём.

**Tech Stack:** Go 1.24, `database/sql` + `github.com/jackc/pgx/v5/stdlib`, Postgres. Fiber (HTTP). Удаляется `github.com/mattn/go-sqlite3` (последняя CGO-зависимость → `CGO_ENABLED=0`).

**Спека:** `docs/superpowers/specs/2026-06-08-recommendationengine-drop-sqlite-design.md`

---

## Pre-flight: контекст для исполнителя (прочитать целиком)

**Репозиторий:** `platform-new/recomendationengine` (модуль `gj-similar`, default-ветка `master`) внутри workspace `$WORKSPACE`. Это отдельный git-клон — `cd` в него, коммить локально.

**⚠️ Гейт Go-команд:** родительский `platform-new/go.work` НЕ содержит `recomendationengine` → все Go-команды запускать с префиксом `GOWORK=off`, иначе ошибка `directory prefix . does not contain modules listed in go.work`:
```bash
cd $WORKSPACE/platform-new/recomendationengine && GOWORK=off go build ./...
```

**Базлайн (до изменений):** `GOWORK=off go build/vet` зелёные; `go test ./...` все пакеты `ok`, КРОМЕ пред-существующего `TestAdminStrategy_GetStrategy_returnsDefaults` в `internal/handlers` — этот файл удаляется в Task 2, фейл уедет вместе с ним.

**Ветка:** этот план — на ветке `task-drop-sqlite` от `master` (независимо от сплита `task-drop-frontend`).

**Принцип порядка:** SQL переписываем на `$n` ДО удаления шима (Task 3 перед Task 6). Пока шим есть, он переписывает только `?`/sqlite-паттерны → на уже-нативном `$n`-SQL он no-op, build остаётся зелёным между коммитами. `go build` зелёный — единственный автоматический гейт (DB-тестов нет); корректность SQL подтверждается staging-smoke в конце.

**Риск (осознанный, см. спеку):** боевой SQL переписывается без автотестов. Самое опасное — порядок `$n` там, где один логический аргумент биндился несколькими `?` (в плане такие места отмечены явно).

---

## Файловая карта

**Удаляются целиком:**
- Тесты (10): `internal/database/migrations_test.go`, `internal/database/schema_consistency_test.go`, `internal/database/connection_rewrite_test.go`, `internal/handlers/admin_strategy_test.go`, `internal/handlers/data_upload_feed_file_test.go`, `internal/repository/postgres_integration_test.go`, `internal/repository/runtime_settings_test.go`, `internal/routes/admin_routes_test.go`, `internal/services/feed_import_flow_test.go`, `internal/services/strategy_service_test.go`.
- `internal/testutil/` (db.go + postgres.go).
- Dead code: `internal/queries/builder.go` + `internal/queries/builder_test.go`; `internal/repository/category_path_filter.go`.
- `internal/database/migrations_runner.go` (sqlite-миграционная машинерия).

**Модифицируются:**
- `internal/database/connection.go` — выкинуть sqlite/шим, `Init` → один аргумент.
- `internal/database/migrations.go` — `RunMigrations` → one-liner; удалить sqlite-DDL консты + `needsStockColumns`.
- `internal/database/migrations_catalog.go` — удалить sqlite-registry-only консты, оставить `createSimilarStrategyPresetsTable`.
- `internal/config/config.go` — убрать `DatabasePath`/`DATABASE_PATH`.
- `cmd/similar/main.go` — обновить вызов `database.Init`.
- SQL `?`→`$n`: `internal/queries/products.go`, `internal/repository/{product,sync,runtime_settings,similar,similar_repository_pool,similar_repository_merge,strategy_preset}_repository.go`.
- `go.mod` / `go.sum` — `go mod tidy`.
- `Dockerfile` — `CGO_ENABLED=0` + distroless.

---

## Task 1: Ветка

- [ ] **Step 1: Создать ветку от master**

```bash
cd $WORKSPACE/platform-new/recomendationengine
git checkout master && git pull --ff-only 2>/dev/null; git checkout -b task-drop-sqlite
```
Expected: `Switched to a new branch 'task-drop-sqlite'`.

---

## Task 2: Удалить все DB-зависимые тесты + testutil

**Files:** удаление 10 тест-файлов + `internal/testutil/`.

- [ ] **Step 1: Удалить тесты и testutil**

```bash
cd $WORKSPACE/platform-new/recomendationengine
git rm internal/database/migrations_test.go \
       internal/database/schema_consistency_test.go \
       internal/database/connection_rewrite_test.go \
       internal/handlers/admin_strategy_test.go \
       internal/handlers/data_upload_feed_file_test.go \
       internal/repository/postgres_integration_test.go \
       internal/repository/runtime_settings_test.go \
       internal/routes/admin_routes_test.go \
       internal/services/feed_import_flow_test.go \
       internal/services/strategy_service_test.go
git rm -r internal/testutil
```

- [ ] **Step 2: Убедиться, что оставшиеся тесты не импортируют testutil**

```bash
grep -rn "internal/testutil\|testutil\." --include="*.go" internal cmd; echo "exit=$?"
```
Expected: нет совпадений (`exit=1`). Если что-то найдено — значит тест, который мы не удалили, зависит от testutil; такой тест тоже DB-зависимый → удалить его и повторить.

- [ ] **Step 3: Build + тесты зелёные и без БД**

```bash
GOWORK=off go build ./... && echo BUILD_OK
GOWORK=off go test ./... 2>&1 | grep -E "^(ok|FAIL|---|\?)|migration|Импорт"
```
Expected: build OK; все пакеты `ok`/`?`, ни одного `FAIL`, и в выводе НЕТ строк `Running migration…` / `Импорт товаров в БД` (значит тесты больше не открывают БД). Пред-существующий `TestAdminStrategy_GetStrategy_returnsDefaults` исчез вместе с файлом.

- [ ] **Step 4: Commit**

```bash
git commit -m "test: drop all DB-dependent tests and testutil (unit-only, no DB)"
```

---

## Task 3: Переписать runtime-SQL на нативный Postgres (`?`→`$n`, `available=1`→TRUE)

> Шим ещё на месте — на уже-нативном `$n`-SQL он no-op, build остаётся зелёным. Делаем ДО удаления шима.
> **Каждый `?` → позиционный `$n` по порядку появления в строке запроса; порядок аргументов в Go-вызове НЕ меняется.**

**Files:** `internal/queries/products.go`, `internal/repository/*.go` (см. ниже).

- [ ] **Step 1: `queries/products.go` — UpsertProduct VALUES (27 плейсхолдеров)**

Заменить блок VALUES:
```go
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
			?, ?, ?, ?, ?, ?, ?, ?, ?)
```
на:
```go
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18,
			$19, $20, $21, $22, $23, $24, $25, $26, $27)
```
(Часть `ON CONFLICT (sku) DO UPDATE SET … excluded.* … WHERE … IS DISTINCT FROM …` НЕ трогать — там нет плейсхолдеров и она уже нативная.)

- [ ] **Step 2: `repository/product_repository.go` — 3 места**

`deleteProductsMissingFromFeed` (строка ~80):
```go
	stmt, err := tx.Prepare("INSERT INTO current_feed_skus (sku) VALUES (?) ON CONFLICT (sku) DO NOTHING")
```
→
```go
	stmt, err := tx.Prepare("INSERT INTO current_feed_skus (sku) VALUES ($1) ON CONFLICT (sku) DO NOTHING")
```

`BackfillSaleStartDatesFromAttributes` prepared UPDATE:
```go
	stmt, err := tx.Prepare(`
		UPDATE products
		SET sale_start_date = ?
		WHERE sku = ?
			AND NULLIF(NULLIF(TRIM(sale_start_date), ''), '01.01.2000') IS NULL
	`)
```
→ (вызывается `stmt.Exec(item.date, item.sku)` → `$1=date, $2=sku`):
```go
	stmt, err := tx.Prepare(`
		UPDATE products
		SET sale_start_date = $1
		WHERE sku = $2
			AND NULLIF(NULLIF(TRIM(sale_start_date), ''), '01.01.2000') IS NULL
	`)
```

`CollectAttributeKeyCounts` (строка ~219):
```go
		rows, err = r.db.Query(baseQuery+" LIMIT ?", sampleLimit)
```
→
```go
		rows, err = r.db.Query(baseQuery+" LIMIT $1", sampleLimit)
```

- [ ] **Step 3: `repository/sync_repository.go` — 2 места**

`GetLastSync`:
```go
	err := r.db.QueryRow(`SELECT last_synced_at FROM sync_status WHERE name = ?`, name).Scan(&ts)
```
→
```go
	err := r.db.QueryRow(`SELECT last_synced_at FROM sync_status WHERE name = $1`, name).Scan(&ts)
```

`Upsert` (вызывается `Exec(…, name, syncedAt)` → `$1=name, $2=syncedAt`):
```go
		VALUES (?, ?, CURRENT_TIMESTAMP)
```
→
```go
		VALUES ($1, $2, CURRENT_TIMESTAMP)
```

- [ ] **Step 4: `repository/runtime_settings_repository.go` — 2 места**

`Get`:
```go
	err := r.db.QueryRow(`SELECT value_json FROM runtime_settings WHERE key = ?`, key).Scan(&raw)
```
→
```go
	err := r.db.QueryRow(`SELECT value_json FROM runtime_settings WHERE key = $1`, key).Scan(&raw)
```

`Set` (вызывается `Exec(…, key, valueJSON)` → `$1=key, $2=valueJSON`):
```go
		VALUES (?, ?, CURRENT_TIMESTAMP)
```
→
```go
		VALUES ($1, $2, CURRENT_TIMESTAMP)
```

- [ ] **Step 5: `repository/similar_repository.go` — LoadProductBySKU (5 плейсхолдеров)**

Вызов: `r.db.QueryRowContext(ctx, query, sku, sku, sku, legacyPrefix, legacyPrefix)` → `$1=sku, $2=sku, $3=sku, $4=legacyPrefix, $5=legacyPrefix`.
```go
		WHERE p.sku = ? OR p.group_id = ? OR p.sales_sku = ? OR p.group_id LIKE ? OR p.sales_sku LIKE ?
```
→
```go
		WHERE p.sku = $1 OR p.group_id = $2 OR p.sales_sku = $3 OR p.group_id LIKE $4 OR p.sales_sku LIKE $5
```

- [ ] **Step 6: `repository/similar_repository_pool.go` — boolean + динамический LIMIT + section-фрагменты**

> ⚠️ Самое аккуратное место. В `LoadSimilarPool` аргументы: сначала section-args (0/1/2 шт.), потом `limit` добавляется ПОСЛЕДНИМ (`args = append(args, limit)`). Значит section-плейсхолдеры — `$1`(/`$2`), а `LIMIT` — `$(len(args)+1)`, что зависит от числа section-args. Поэтому `LIMIT ?` делаем динамическим, а section-фрагменты — литеральными `$1`/`$2` (они всегда идут первыми).

6a. boolean (строка ~41):
```go
			  AND p.available = 1
```
→
```go
			  AND p.available = TRUE
```

6b. Динамический LIMIT. Заменить хвост запроса и добавление аргумента:
```go
		ORDER BY sku ASC
		LIMIT ?
	`
	args = append(args, limit)
```
→
```go
		ORDER BY sku ASC
		LIMIT $` + fmt.Sprintf("%d", len(args)+1) + `
	`
	args = append(args, limit)
```
Добавить импорт `"fmt"` в `similar_repository_pool.go` (сейчас его там нет — импорты `context`, `strings`, и два discovery/similar). Новый блок импорта:
```go
import (
	"context"
	"fmt"
	"strings"

	"gj-similar/internal/discovery"
	"gj-similar/internal/discovery/similar"
)
```

6c. `similarPoolSectionSQL` — три фрагмента, section-args всегда первые:
```go
		return ` AND (p.root_section = ? OR (p.root_section = 'unknown' AND p.gender = ?))`, []interface{}{section, gender}
```
→
```go
		return ` AND (p.root_section = $1 OR (p.root_section = 'unknown' AND p.gender = $2))`, []interface{}{section, gender}
```
```go
		return ` AND (p.root_section = ? OR (p.root_section = 'unknown' AND p.gender IN ('Девочки', 'Мальчики')))`, []interface{}{section}
```
→
```go
		return ` AND (p.root_section = $1 OR (p.root_section = 'unknown' AND p.gender IN ('Девочки', 'Мальчики')))`, []interface{}{section}
```
```go
	return ` AND p.root_section = ?`, []interface{}{section}
```
→
```go
	return ` AND p.root_section = $1`, []interface{}{section}
```

- [ ] **Step 7: `repository/similar_repository_merge.go` — динамический IN-список**

`loadMergedGroupAttributes`: заменить генерацию плейсхолдеров.
```go
	placeholders := strings.Repeat("?,", len(unique))
	placeholders = placeholders[:len(placeholders)-1]
	args := make([]interface{}, len(unique))
	for i, key := range unique {
		args[i] = key
	}
```
→
```go
	parts := make([]string, len(unique))
	args := make([]interface{}, len(unique))
	for i, key := range unique {
		parts[i] = fmt.Sprintf("$%d", i+1)
		args[i] = key
	}
	placeholders := strings.Join(parts, ",")
```
Добавить `"fmt"` в импорты `similar_repository_merge.go` (сейчас: `context`, `encoding/json`, `strings`, два внутренних). Новый блок:
```go
import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"gj-similar/internal/catalog"
	"gj-similar/internal/discovery/similar"
)
```

- [ ] **Step 8: `repository/strategy_preset_repository.go` — 6 мест**

`GetByID`:
```go
		FROM similar_strategy_presets WHERE id = ?
```
→
```go
		FROM similar_strategy_presets WHERE id = $1
```

`Create` (вызов `Exec(…, id, name, documentJSON, isProduction)` → `$1..$4`):
```go
		VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
```
→
```go
		VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
```

`Update` (вызов `Exec(…, name, documentJSON, id)` → `$1=name, $2=documentJSON, $3=id`):
```go
		SET name = ?, document_json = ?, updated_at = CURRENT_TIMESTAMP
		WHERE id = ?
```
→
```go
		SET name = $1, document_json = $2, updated_at = CURRENT_TIMESTAMP
		WHERE id = $3
```

`Delete`:
```go
	_, err = r.db.Exec(`DELETE FROM similar_strategy_presets WHERE id = ?`, id)
```
→
```go
	_, err = r.db.Exec(`DELETE FROM similar_strategy_presets WHERE id = $1`, id)
```

`SetProduction` (последний UPDATE, вызов `tx.Exec(…, id)` → `$1=id`):
```go
		SET is_production = TRUE, updated_at = CURRENT_TIMESTAMP
		WHERE id = ?
```
→
```go
		SET is_production = TRUE, updated_at = CURRENT_TIMESTAMP
		WHERE id = $1
```
(`UPDATE … SET is_production = FALSE` и `WHERE is_production = TRUE` в этом файле НЕ трогать — без плейсхолдеров, уже нативные.)

- [ ] **Step 9: Build + проверить, что `?`-плейсхолдеров в SQL не осталось**

```bash
GOWORK=off go build ./... && echo BUILD_OK
grep -rnF "?" internal/queries internal/repository --include="*.go" | grep -v _test | grep -vE "builder.go|category_path_filter.go"
echo "exit=$?"
```
Expected: BUILD_OK; второй grep — пусто (`exit=1`). (`builder.go`/`category_path_filter.go` ещё содержат `?`, но они удаляются в Task 4 — поэтому исключены из проверки.)

- [ ] **Step 10: Commit**

```bash
git add -A && git commit -m "refactor(db): rewrite all runtime SQL to native Postgres placeholders (\$n)"
```

---

## Task 4: Удалить dead code (QueryBuilder + category_path_filter)

> Подтверждено: `QueryBuilder` (`queries/builder.go`) и `appendCategoryPathPrefixFilter` (`repository/category_path_filter.go`) не имеют вызовов в runtime-коде. Это устраняет последний `json_extract` и динамические `?`-билдеры.

**Files:** удаление 3 файлов.

- [ ] **Step 1: Удалить**

```bash
cd $WORKSPACE/platform-new/recomendationengine
git rm internal/queries/builder.go internal/queries/builder_test.go internal/repository/category_path_filter.go
```

- [ ] **Step 2: Build + vet**

```bash
GOWORK=off go build ./... && GOWORK=off go vet ./... && echo OK
```
Expected: `OK`. (Если build падает `undefined: appendCategoryPathPrefixFilter` или `NewQueryBuilder` — значит код всё-таки используется; в таком случае НЕ удалять этот файл, а перевести его SQL на `$n` по правилам Task 3 и сообщить.)

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove dead query builder and category_path_filter (unused)"
```

---

## Task 5: Вырезать sqlite из миграций

**Files:** `internal/database/migrations.go`, `internal/database/migrations_runner.go` (удалить), `internal/database/migrations_catalog.go`.

- [ ] **Step 1: Удалить sqlite-миграционную машинерию**

```bash
cd $WORKSPACE/platform-new/recomendationengine
git rm internal/database/migrations_runner.go
```

- [ ] **Step 2: `migrations.go` — `RunMigrations` → one-liner, удалить sqlite-DDL**

Заменить ВЕСЬ файл `internal/database/migrations.go` на:
```go
package database

// RunMigrations накатывает схему. Движок работает только на Postgres,
// нативные PG-миграции — в migrations_postgres.go.
func RunMigrations(db *DB) error {
	return RunPostgresMigrations(db)
}
```
(Это удаляет: старый `RunMigrations` с sqlite-веткой, `needsStockColumns`, и sqlite-DDL консты `createProductsTable`, `createSyncStatusTable`, `removeCategoryIDsColumn`, `addGroupIDColumnToProducts`, `addStockColumnsToProducts`. Импорты `fmt`/`log` больше не нужны.)

- [ ] **Step 3: `migrations_catalog.go` — оставить только PG-используемый конст**

В `internal/database/migrations_catalog.go` оставить ТОЛЬКО `const createSimilarStrategyPresetsTable = …` (его использует `RunPostgresMigrations`). Удалить остальные консты этого файла: `addCatalogDiscoveryColumns`, `createRuntimeSettingsTable`, `createCatalogDiscoveryIndexes`, `createCatalogPerformanceIndexes`, `createProductLookupIndexes`, `backfillCatalogDiscoveryDefaults` — они использовались только sqlite-реестром (PG-схема создаёт эти таблицы/индексы в `createPostgresSchema`/`createPostgresIndexes`).

Если в этом файле есть guard-функции (`needsCatalogDiscoveryColumns` и т.п.) — удалить и их (использовались только реестром; PRAGMA-логика = sqlite).

- [ ] **Step 4: Build — компилятор как страховка от лишнего/недостающего**

```bash
GOWORK=off go build ./...
```
Expected: BUILD_OK. **Если `undefined: createSimilarStrategyPresetsTable`** (или иной конст) — значит этот конст ещё нужен Postgres-миграциям → восстановить его в `migrations_catalog.go`. Go разрешает неиспользуемые package-level консты, поэтому «лишние» не сломают build — их выявит финальный grep (Task 8).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(db): drop sqlite migration registry, Postgres-only migrations"
```

---

## Task 6: Вырезать sqlite-драйвер и шим из connection.go + Init

**Files:** `internal/database/connection.go`, `internal/config/config.go`, `cmd/similar/main.go`.

- [ ] **Step 1: Заменить `internal/database/connection.go` целиком**

Новый полный файл `internal/database/connection.go`:
```go
package database

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
)

type DB struct {
	*sql.DB
}

type Product struct {
	SKU                   string  `json:"sku"`
	SalesSKU              string  `json:"sales_sku"`
	GroupID               string  `json:"group_id"`
	Name                  string  `json:"name"`
	Price                 float64 `json:"price"`
	OldPrice              float64 `json:"oldprice"`
	Discount              float64 `json:"discount"`
	Gender                string  `json:"gender"`
	ImageURL              string  `json:"image_url"`
	SaleStartDate         string  `json:"sale_start_date"`
	Available             bool    `json:"available"`
	Categories            string  `json:"categories"`
	URL                   string  `json:"url"`
	SizeName              string  `json:"size_name"`
	SizeCompleteness      string  `json:"size_completeness"`
	SizeOutOfStockPercent float64 `json:"size_out_of_stock_percent"`
	StoreStock            int     `json:"store_stock"`
	WarehouseStock        int     `json:"warehouse_stock"`
	// Discovery / client catalog (Phase 1)
	CategoryPathJSON  string `json:"category_path,omitempty"`
	LeafCategory      string `json:"leaf_category,omitempty"`
	RootSection       string `json:"root_section,omitempty"`
	Subsection        string `json:"subsection,omitempty"`
	AttributesJSON    string `json:"attributes,omitempty"`
	NormalizedColor   string `json:"normalized_color,omitempty"`
	ProductType       string `json:"product_type,omitempty"`
	PublicationStatus string `json:"publication_status,omitempty"`
	FeedVersion       string `json:"feed_version,omitempty"`
}

// Init открывает подключение к Postgres.
func Init(databaseURL string) (*DB, error) {
	db, err := sql.Open("pgx", databaseURL)
	if err != nil {
		return nil, fmt.Errorf("failed to open postgres database: %w", err)
	}
	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping postgres database: %w", err)
	}
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(time.Hour)

	log.Printf("PostgreSQL database connected")
	return &DB{DB: db}, nil
}

func (db *DB) Begin() (*Tx, error) {
	tx, err := db.DB.Begin()
	if err != nil {
		return nil, err
	}
	return &Tx{Tx: tx}, nil
}

type Tx struct {
	*sql.Tx
}

// QueryContext оставлен для совместимости вызовов с context.
func (db *DB) QueryContext(ctx context.Context, query string, args ...interface{}) (*sql.Rows, error) {
	return db.DB.QueryContext(ctx, query, args...)
}

func (db *DB) QueryRowContext(ctx context.Context, query string, args ...interface{}) *sql.Row {
	return db.DB.QueryRowContext(ctx, query, args...)
}

func (db *DB) Close() error {
	return db.DB.Close()
}
```

> Примечание: `DB` встраивает `*sql.DB`, а `Tx` — `*sql.Tx`, поэтому методы `Exec/Query/QueryRow/Prepare` и т.п. наследуются напрямую (раньше они оборачивали `rewriteSQL`; теперь обёртка не нужна — SQL уже нативный). Удалены: `initSQLite`, `initPostgres` (слит в `Init`), поле `Driver`, `IsPostgres()`, и весь шим (`rewriteSQL`, `rewritePostgresSQL`, `rewriteSQLiteJSON`, `rewritePlaceholders`, `rewriteInsertOrReplace`, `rewriteBooleanSQL`, `conflictColumns`, `splitSQLList`, `booleanColumns`/`boolEqRe`/`boolCoalesceRe`), импорты `regexp`/`strconv`/`strings`, и импорт `mattn/go-sqlite3`.

- [ ] **Step 2: `internal/config/config.go` — убрать DatabasePath**

Удалить поле из структуры:
```go
	DatabasePath     string
```
Удалить чтение env:
```go
	databasePath := os.Getenv("DATABASE_PATH")
	if databasePath == "" {
		databasePath = "./data.db"
	}
```
Удалить из возвращаемого литерала `Load()`:
```go
		DatabasePath:     databasePath,
```
(Оставить `DatabaseURL`/`DATABASE_URL` с дефолтом `postgresql://similar:similar@localhost:5434/similar?sslmode=disable`.)

- [ ] **Step 3: `cmd/similar/main.go` — обновить вызов Init**

```go
	db, err := database.Init(cfg.DatabasePath, cfg.DatabaseURL)
```
→
```go
	db, err := database.Init(cfg.DatabaseURL)
```

- [ ] **Step 4: Build + vet**

```bash
GOWORK=off go build ./... && GOWORK=off go vet ./... && echo OK
```
Expected: `OK`. Если build ругается на `IsPostgres`/`.Driver`/`rewrite*`/`DatabasePath` в других местах — это оставшиеся call-site'ы тех же сущностей; поправить их (по текущему коду таких нет) и повторить.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(db): remove sqlite driver and SQLite->PG rewrite shim; Init is Postgres-only"
```

---

## Task 7: `go mod tidy` (убрать go-sqlite3)

**Files:** `go.mod`, `go.sum`.

- [ ] **Step 1: tidy**

```bash
cd $WORKSPACE/platform-new/recomendationengine
GOWORK=off go mod tidy
```

- [ ] **Step 2: Проверить, что go-sqlite3 ушёл**

```bash
grep -n "go-sqlite3" go.mod go.sum; echo "exit=$?"
GOWORK=off go build ./... && echo BUILD_OK
```
Expected: нет `go-sqlite3` в `go.mod` (`go.sum` может временно хранить хеши — допустимо, но в `go.mod` его быть не должно); BUILD_OK.

- [ ] **Step 3: Commit**

```bash
git add go.mod go.sum && git commit -m "build: go mod tidy — drop mattn/go-sqlite3"
```

---

## Task 8: Dockerfile → CGO_ENABLED=0 + distroless

**Files:** `Dockerfile`.

> CGO был нужен только для sqlite. Теперь движок собирается статически, как checkout/intgateway.

- [ ] **Step 1: Заменить `Dockerfile` целиком**

`platform-new/recomendationengine/Dockerfile`:
```dockerfile
# syntax=docker/dockerfile:1
FROM golang:1.24-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/gj-similar ./cmd/similar

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/gj-similar /gj-similar
EXPOSE 8080
USER nonroot:nonroot
ENTRYPOINT ["/gj-similar"]
```

- [ ] **Step 2: Собрать образ**

```bash
cd $WORKSPACE/platform-new/recomendationengine
docker build -t recomendationengine:test .
```
Expected: оба стейджа проходят, статический бинарь собирается без CGO.

- [ ] **Step 3: Commit**

```bash
git add Dockerfile && git commit -m "build: CGO_ENABLED=0 + distroless (sqlite was the only CGO dep)"
```

---

## Task 9: Финальная верификация

**Files:** —

- [ ] **Step 1: Build + vet**

```bash
cd $WORKSPACE/platform-new/recomendationengine
GOWORK=off go build ./... && GOWORK=off go vet ./... && echo OK
```
Expected: `OK`.

- [ ] **Step 2: Тесты — зелёные и БЕЗ обращений к БД**

```bash
GOWORK=off go test ./... 2>&1 | tee /tmp/sqlite_drop_test.log | grep -E "^(ok|FAIL|\?)"
grep -iE "Running migration|Импорт товаров|sqlite|data.db|Database connected" /tmp/sqlite_drop_test.log; echo "db_noise_exit=$?"
```
Expected: ни одного `FAIL`; `db_noise_exit=1` (никаких миграций/импорта/sqlite-логов в выводе тестов — тесты чисто-юнитовые).

- [ ] **Step 3: Ноль остатков sqlite в коде**

```bash
grep -rniE "sqlite|go-sqlite3|DATABASE_PATH|rewriteSQLite|rewritePostgresSQL|datetime\('now'\)|INSERT OR (IGNORE|REPLACE)|json_extract|INDEXED BY|PRAGMA|sqlite_master" --include="*.go" internal cmd; echo "exit=$?"
```
Expected: пусто (`exit=1`). Любое совпадение — недоудалённый sqlite-артефакт, дочистить.

- [ ] **Step 4: Ноль `?`-плейсхолдеров в SQL**

```bash
grep -rnF "?" internal --include="*.go" | grep -v _test | grep -E "Query|Exec|Prepare|VALUES|WHERE|LIMIT|= \?|IN \(" ; echo "exit=$?"
```
Expected: пусто (`exit=1`).

- [ ] **Step 5: Docker build**

```bash
docker build -t recomendationengine:verify .
```
Expected: успешно.

- [ ] **Step 6: Push ветки**

```bash
git push -u origin task-drop-sqlite
```
Expected: ветка в origin; стартует `golang-backend-pipeline`.

---

## Task 10: Manual staging smoke (ЕДИНСТВЕННЫЙ гейт корректности SQL)

> DB-тестов нет — это осознанный выбор. Переписанный SQL обязательно прогнать на staging-Postgres перед merge.

- [ ] **Step 1: Поднять движок против staging/локального Postgres**

```bash
cd $WORKSPACE/platform-new/recomendationengine
make pg-up                 # локальный PG на :5434 (или укажи DATABASE_URL на staging)
DATABASE_URL=postgresql://similar:similar@localhost:5434/similar?sslmode=disable PORT=8080 go run ./cmd/similar &
sleep 8
```

- [ ] **Step 2: Прогнать ключевые ручки и проверить переписанный SQL**

```bash
curl -s -o /dev/null -w "health=%{http_code}\n" http://localhost:8080/health
curl -s -X POST -o /dev/null -w "feed_refresh=%{http_code}\n" http://localhost:8080/api/feed/refresh
sleep 5
curl -s -o /dev/null -w "data_status=%{http_code}\n" http://localhost:8080/api/data-status
curl -s -o /dev/null -w "strategy_get=%{http_code}\n" http://localhost:8080/api/admin/similar-strategy
# похожие по любому артикулу из загруженного фида (взять из логов импорта):
# curl -s "http://localhost:8080/api/v1/client/products/<SKU>/similar" | head
# создать/прочитать пресет (проверяет INSERT ... ON CONFLICT и SELECT по $1):
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"name":"smoke","document":{}}' \
  -o /dev/null -w "preset_create=%{http_code}\n" http://localhost:8080/api/admin/similar-strategy/presets
curl -s -o /dev/null -w "preset_list=%{http_code}\n" http://localhost:8080/api/admin/similar-strategy/presets
kill %1 2>/dev/null; make pg-down
```
Expected: `health=200`, `feed_refresh=200` (фид грузится — проверяет `UpsertProduct` `$1..$27`, `sync_status` upsert, `current_feed_skus`), `data_status=200`, `strategy_get=200`, `preset_create`=200/201, `preset_list=200`, и похожие возвращают непустой список. Любая 500 → смотреть лог: вероятна ошибка в переписанном SQL (порядок `$n`, `ON CONFLICT`, `LIMIT $n`).

---

## Follow-ups / координация (в описание MR)

- **DATABASE_URL обязателен в k8s.** `Init` больше не имеет sqlite-fallback — helm-values должны задавать `DATABASE_URL` на всех стендах (dev/stage/prod). Согласовать с devops.
- **Merge-порядок со сплитом.** Эта ветка от `master`, ветка сплита `task-drop-frontend` тоже. Конфликтов быть не должно (сплит трогает frontend/docs/CI, эта — internal Go + Dockerfile). Если сплит мержится первым — перебазировать `task-drop-sqlite` на обновлённый `master`; единственный возможный конфликт — `Dockerfile`/CI (сплит Dockerfile не менял, так что чисто).

## Definition of Done

- [ ] Удалены 10 DB-тестов + `internal/testutil/` + dead code (builder, category_path_filter) + sqlite-миграции.
- [ ] Весь runtime-SQL — нативный PG (`$n`, `TRUE/FALSE`); ноль `?`-плейсхолдеров в SQL.
- [ ] `connection.go` без sqlite/шима, `Init(databaseURL string)`; `config.go` без `DatabasePath`.
- [ ] `go.mod` без `mattn/go-sqlite3`; Dockerfile `CGO_ENABLED=0` + distroless.
- [ ] `GOWORK=off go build/vet` зелёные; `go test ./...` зелёный и без обращений к БД; grep по sqlite-артефактам пустой; `docker build` ок.
- [ ] Ветка `task-drop-sqlite` запушена; staging-smoke пройден (Task 10).
