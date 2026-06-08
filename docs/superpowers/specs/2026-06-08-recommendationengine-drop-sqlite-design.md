# RecommendationEngine: полное удаление sqlite, Postgres-only — дизайн

**Дата:** 2026-06-08
**Статус:** утверждён к планированию
**Scope:** движок `recomendationengine` (`platform-new/recomendationengine`, модуль `gj-similar`). Follow-up #2 из спеки сплита (`2026-06-08-recommendationengine-gui-split-design.md`).

## Контекст

Слой БД движка написан **sqlite-first**: runtime-SQL в sqlite-диалекте (`?`-плейсхолдеры,
`INSERT OR REPLACE`, `json_extract`, `datetime('now')`, `INDEXED BY`, boolean как `0/1`),
а на Postgres работает только через runtime-шим `rewritePostgresSQL` в `connection.go`,
переписывающий SQLite→PG. В прод всегда Postgres → всегда через шим. sqlite остаётся как
драйвер тестов (`internal/testutil/db.go` — SQLite в temp dir) и локалки, плюс отдельные
sqlite-миграции с PRAGMA/`sqlite_master`-гардами. Нативные PG-миграции **уже существуют**
(`internal/database/migrations_postgres.go`).

## Цель

Движок использует **только Postgres**. Убрать всё, что связано с sqlite (вариант **B** —
полный нативный PG-rewrite, шим удалён), и привести тесты к **юнитам без БД**.

## Решения (зафиксированы при brainstorming)

1. **Глубина = B (полный native-PG rewrite).** Не просто выкинуть драйвер: переписать весь
   boevoy SQL на нативный Postgres и **удалить шим** `rewritePostgresSQL` целиком.
2. **Тесты — строго без БД.** Удалить ВСЕ тесты, которым нужна БД (9 файлов), плюс тест шима
   (`connection_rewrite_test.go`). Хендлеры/сервисы остаются без юнит-покрытия (фейки НЕ вводим —
   осознанное решение пользователя). Дефолтный `go test ./...` не трогает БД.
3. **SQL-страховка = только manual staging smoke.** Автотестов на переписанный SQL нет
   (осознанный риск, см. ниже).
4. **Ветка** `task-drop-sqlite` от `master` (изменение независимо от сплита `task-drop-frontend`).

## Изменения: runtime / слой БД

- **`internal/database/connection.go`:** удалить `initSQLite`, импорт `github.com/mattn/go-sqlite3`,
  поле `Driver` и `IsPostgres()`, и **весь шим**: `rewritePostgresSQL`, `rewriteSQLiteJSON`,
  `rewritePlaceholders`, `rewriteInsertOrReplace`, `rewriteBooleanSQL`, `conflictColumns`,
  `splitSQLList`, `booleanColumns`/`boolEqRe`/`boolCoalesceRe`. `DB` → тонкая обёртка над `*sql.DB`;
  методы `Exec/Query/QueryContext/QueryRow/QueryRowContext/Begin` + `Tx.*` — прямой passthrough
  без `rewriteSQL`.
- **`Init`:** сигнатуру `Init(dbPath string, databaseURL ...string)` → `Init(databaseURL string)`
  (только Postgres). Правка вызова в `cmd/similar/main.go` и `internal/container/container.go`.
- **`internal/config/config.go`:** удалить `DatabasePath`, чтение `DATABASE_PATH`, дефолт `./data.db`.
  Остаётся `DatabaseURL` (`DATABASE_URL`, дефолт локального PG).
- **Миграции:** `RunMigrations` — убрать sqlite-ветку, оставить только `RunPostgresMigrations`
  (`migrations_postgres.go`). Удалить sqlite-реестр и PRAGMA/`sqlite_master`-гарды
  (`migrations.go` sqlite-часть + `migrations_runner.go` целиком, если он только sqlite).
- **Боевой SQL → нативный PG** (21 место в 10 файлах `internal/queries/` + `internal/repository/`):
  `?`→`$1..$n`; `INSERT OR REPLACE`→`INSERT … ON CONFLICT (<keys>) DO UPDATE SET …`;
  `INSERT OR IGNORE`→`… ON CONFLICT DO NOTHING`; `json_extract(x,'$."k"')`→`(x::jsonb ->> 'k')`,
  `json_extract(x,'$[i]')`→`(x::jsonb ->> i)`, `json_array_length(x)`→`jsonb_array_length(x::jsonb)`;
  `datetime('now')`→`CURRENT_TIMESTAMP`; убрать `INDEXED BY …`; boolean-сравнения
  `col = 0/1`→`col = FALSE/TRUE` (колонки `available|is_active|enabled`).
  ON CONFLICT-ключи (из удаляемого `conflictColumns`): `sync_status`→`name`,
  `runtime_settings`→`key`, `similar_strategy_presets`→`id`, `products`→первичный ключ продукта.
- **`go.mod`:** `go mod tidy` уберёт `mattn/go-sqlite3`.
- **`Dockerfile`:** `CGO_ENABLED=1`+debian → **`CGO_ENABLED=0` + distroless** (как checkout/intgateway):
  CGO был нужен только для sqlite. Закрывает follow-up «CGO-free» из спеки сплита.

## Изменения: тесты

**Удалить (10 файлов):**
`internal/database/migrations_test.go`, `internal/database/schema_consistency_test.go`,
`internal/database/connection_rewrite_test.go`, `internal/handlers/admin_strategy_test.go`,
`internal/handlers/data_upload_feed_file_test.go`, `internal/repository/postgres_integration_test.go`,
`internal/repository/runtime_settings_test.go`, `internal/routes/admin_routes_test.go`,
`internal/services/feed_import_flow_test.go`, `internal/services/strategy_service_test.go`.

**Удалить `internal/testutil/`** целиком (`db.go` + `postgres.go` — только для DB-тестов) → пакет исчезает.

**Оставить (~28 чисто-логических юнитов):** `internal/catalog/*`, `internal/clientcatalog/id_codec_test.go`,
`internal/config/feed_test.go`, `internal/discovery/*` (section, similar/*, strategy/defaults+feature_catalog+migrate),
`internal/queries/builder_test.go`, `internal/repository/similar_repository_merge_test.go`, `internal/utils/*`.

Пред-существующий фейл `TestAdminStrategy_GetStrategy_returnsDefaults` исчезает вместе с
`admin_strategy_test.go`.

## Верификация

- `GOWORK=off go build ./... && GOWORK=off go vet ./...` — зелёные.
- `GOWORK=off go test ./...` — **все зелёные и НОЛЬ обращений к БД**: в выводе не должно быть
  `Running migration…` / `Импорт товаров в БД` / открытий sqlite/pg.
- `grep -rn "sqlite\|SQLite\|DATABASE_PATH\|go-sqlite3\|rewriteSQLite\|datetime('now')\|INSERT OR\|json_extract\|INDEXED BY\| ? " internal cmd` — пусто (кроме легитимных `?` вне SQL, если такие есть — проверить глазами).
- `docker build` (CGO=0/distroless) — ок.
- **Manual staging smoke** (единственный гейт SQL): движок на staging-PG → `/health`,
  `/api/feed/refresh` (фид грузится), `/api/v1/client/products/:id/similar` (похожие считаются),
  `/api/admin/similar-strategy` GET+PUT (стратегия читается/пишется), пресеты, `/api/data-status`.

## Риски

1. **Боевой SQL переписывается без автотестов.** Единственный гейт — staging smoke (осознанный
   выбор). Узкие места: upsert'ы (`ON CONFLICT` для `runtime_settings.key`, `sync_status.name`,
   `similar_strategy_presets.id`, `products`), JSON-доступ, порядок `$n`-плейсхолдеров (особенно
   там, где один аргумент использовался дважды через `?` — в PG это разные `$n`!).
2. **Хендлеры/сервисы без юнит-покрытия** после удаления их DB-тестов.
3. **Плейсхолдеры — главная ловушка миграции:** sqlite `?` позиционны по вхождению; если запрос
   биндил один и тот же логический параметр несколькими `?`, при наивном `$1,$2,…` порядок
   аргументов в Go-вызове должен совпасть. Проверять каждый запрос вместе с его `Exec/Query` call-site.
