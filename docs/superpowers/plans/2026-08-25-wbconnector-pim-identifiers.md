# WB Connector ↔ PIM Identifiers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Научить `wbconnector` получать наш SKU-артикул по баркоду из ENSI PIM и отправлять в OTS/WMS его, а не `vendorCode` от WB, который на проде выглядит как `GAS011429/коричневый` и артикулом не является.

**Architecture:** PIM остаётся мастером `баркод ↔ vendor_code ↔ IDD`, запись в него не делается. Коннектор держит локальный кеш `product_identifiers` — по тому же принципу, что уже работающая карта `goods` для стороны WB. Наполнение гибридное: ночной cron `cmd/pimsync` обходит `sku_products` курсором целиком, а при приёме заказа с неизвестным баркодом делается адресный батч-дозапрос. Соединение двух сторон — только по баркоду: это единственный идентификатор, который есть одновременно у WB, у PIM и у OTS.

**Tech Stack:** Go 1.26.2, `pgx/v5`, `gj-go-httpclient` v0.1.1, `gj-go-logger`, goose-миграции, `oapi-codegen` + Redocly (как в `platform-new/clients/offers`), PostgreSQL-тесты по `WBCONNECTOR_TEST_DSN`.

## Global Constraints

- PIM внешний: не менять код, схему и API PIM. Только чтение `POST /products/sku-products:search`.
- Авторизация PIM не нужна: в спеке нет `security`, у группы `ApiV1` в `routes.php` только `->middleware('api')`. Проверено по коду 2026-08-25.
- Ключ соединения — баркод. `nmID`/`chrtID` в PIM отсутствуют, `vendorCode` карточки WB — код уровня модели плюс цвет, ключом быть не может.
- Инкремента по времени в PIM нет: в `SkuProductsQuery` фильтры — `id` (range), `vendor_code`, `barcode`, `product_status`, `type_of_good` (плюс scope `filled_replacement`), сорт только по `id`; фильтра по времени нет. Полный проход — курсорной пагинацией, которую надо явно запросить (`pagination.type: "cursor"`, дефолт в PIM — offset).
- Имена фильтров генерируются как `baseName + suffixes[type]`, а карта суффиксов ставит `'equal' => ''` — это дефолтный конфиг пакета `platform/ensi/packages/query-builder-extension/config/query-builder-extensions.php:5-15`, подмешиваемый через `hasConfigFile()`; PIM его не переопределяет. Поэтому равенство — это `barcode` и `vendor_code` без суффикса, а варианты диапазона и подстроки — с **двойным** подчёркиванием: `id__gt`, `id__gte`, `barcode__like`, `barcode__empty`. Сверено 2026-08-25 по `Filters/NameGenerator.php:15-19` и конфигу пакета.
- Заказ, баркод которого PIM не знает, **не экспортируется** в OTS: отклонение `unknown_sku` + retry в рамках бюджета, затем парковка. Пустой артикул в OTS недопустим — по контракту это «безымянная строка» в WMS.
- Существующее поле `orders.article` (vendorCode от WB) сохраняется как факт от WB; оно перестаёт быть источником для OTS, но не удаляется.
- Клиент PIM — **готовая внешняя зависимость** `…/clients/pimclient@v0.1.3`, не часть этой работы. Здесь его только подключают и оборачивают.
- Все SQL — только в `internal/adapters/pgstore`.
- Каждая задача заканчивается зелёным `go test -race ./...` на реальном PostgreSQL.

## File Map

**Готовый клиент `platform-new/clients/pim`** (module `…/clients/pimclient`, тег `v0.1.3`) — реализован отдельной сессией, живая проверка на stage пройдена. В рамках этого плана **не меняется**, только подключается в `go.mod` (Task 1). Даёт `pim.New`, `SearchSkuProducts`, `pim.PaginationTypeCursor` и типы `SkuProduct` / `CursorPagination`.

**`platform-new/wbconnector`**
- `migrations/20260825120000_product_identifiers.sql` — кеш, реестр конфликтов, вид отклонения.
- `internal/core/sku.go` — `SkuIdentity`, `SkuConflict`, `DeviationUnknownSKU`.
- `internal/adapters/pgstore/skus.go` — `UpsertSkus`, `SkuByBarcode`, `SkusByBarcodes`, `UnknownBarcodes`.
- `internal/adapters/pim/client.go` — адаптер над `pimclient`: доменные типы, режимы обхода и батча.
- `internal/skus/importer.go` — курсорный обход PIM в кеш (по образцу `internal/goods`).
- `cmd/pimsync/main.go` — бинарь полного прохода.
- `internal/worker/commands/ots.go:232` — источник артикула.
- `internal/platform/config/config.go` — `PIM_BASE_URL`, `PIM_TIMEOUT_MS`.
- `internal/app/container.go` — сборка адаптера и резолвера.
- `internal/testharness/ports.go` — реальный `VendorCodeResolver` вместо заглушки.
- `Makefile`, `Dockerfile` — новый бинарь.
- `README.md`, `.env.example`.

**`platform/ensi/devops/ms-helm-values`**
- `stage/go/wbconnector/wbconnector.yaml` — `PIM_BASE_URL`, cron `pimsync`, и правка `WB_STICKER_FORMAT` на `png`.

---

### Task 0: Разблокировать стенд

Без этого ни один следующий шаг нельзя проверить на стенде: `stage:deploy` падает, потому что новый бинарь отвергает конфиг.

**Files:**
- Modify: `platform/ensi/devops/ms-helm-values/stage/go/wbconnector/wbconnector.yaml:113-118`

**Interfaces:**
- Consumes: ничего.
- Produces: рабочий деплой стенда на актуальном master.

- [ ] **Step 1: Заменить формат стикера**

```yaml
    WB_STICKER_FORMAT:
      value: "png"
    WB_STICKER_WIDTH:
      value: "58"
    WB_STICKER_HEIGHT:
      value: "40"
```

- [ ] **Step 2: Проверить, что бинарь принимает конфиг**

```bash
cd $WORKSPACE/platform-new/wbconnector
env -i PATH="$PATH" HOME="$HOME" APP_ENV=stage \
  WBCONNECTOR_DB_DSN='postgres://wb:wb@localhost:55432/wbconnector?sslmode=disable' \
  WB_STICKER_FORMAT=png WB_STICKER_WIDTH=58 WB_STICKER_HEIGHT=40 \
  WB_STATION_TOKEN=dummy WB_PRINTER_ALLOWLIST=10.0.0.1 \
  KAFKA_SECURITY_PROTOCOL=PLAINTEXT KAFKA_SASL_MECHANISMS=PLAIN \
  timeout 15 go run ./cmd/wbconnector 2>&1 | head -3
```

Expected: строка `wbconnector listening on :8080`, никакого `bootstrap failed`.

- [ ] **Step 3: Закоммитить в ms-helm-values и перезапустить `stage:deploy`**

```bash
cd $WORKSPACE/platform/ensi/devops/ms-helm-values
git add stage/go/wbconnector/wbconnector.yaml
git commit -m "fix(wbconnector): stage prints WB PNG stickers, not raw ZPL"
```

Expected: после ретрая job'а Deployment `wbconnector` и `wbconnector-bkg-wbstatus` на одном образе с CronJob.

---

### Task 1: Клиент PIM — ✅ сделано вне этого плана

Клиент **написан, опубликован и проверен на stage** отдельной сессией по ТЗ
`docs/superpowers/plans/2026-08-26-pimclient-go.md`:
`gitlab.gloria.aaanet.ru/greensight/gj/go/clients/pimclient@v0.1.3`, локальная
рабочая копия — `platform-new/clients/pim`, уже прописана в `go.work`.

**Отдельного шага «зафиксировать версию» здесь нет, и это осознанно.** Пин через
`go get` до появления импорта укладывает строку как `// indirect`, а
документированный `make tidy` такую строку удаляет — проверено 2026-08-26.
Поэтому `go get …@v0.1.3` делается в Task 4 Step 3, там же, где пишется импорт:
тогда зависимость становится прямой и tidy её сохраняет. В `go.mod` эта работа
попадает один раз, вместе с кодом, который ею пользуется.

**Interfaces:**
- Provides (фактический контракт `v0.1.3`, сверено по коду 2026-08-26):
  - `pim.New(baseURL string, opts ...httpclient.Option) *Client` — `baseURL` без `/api/v1`, авторизация не нужна
  - `(*Client).SearchSkuProducts(ctx, SearchSkuProductsRequest) (SearchSkuProductsResponse, error)`
  - `pim.PaginationTypeCursor` — стабильная константа для `pagination.type`; предпочитать её сгенерированному `Cursor`
  - `SkuProduct{Id int64, Barcode, VendorCode, ProductVendorCode, ExternalId string, ProductId, MarkType, TypeOfGood *…}`
  - `SearchSkuProductsResponse.Meta.Pagination` — **указатель** на анонимную структуру с полями
    `Cursor`, `Limit`, **`NextCursor`**

Важно про `go.work`: локально он подставляет рабочую копию `./clients/pim`, и
сборка идёт по ней, а не по тегу. В CI никакого `go.work` нет — там модуль
тянется из GitLab по версии из `go.mod`. Значит расхождение «локально собралось,
в CI нет» возможно ровно тогда, когда правки в рабочую копию не выпущены тегом.
Если по ходу работы понадобится менять клиент — выпускать новый патч-тег и
поднимать версию в `go.mod`, а не жить на незакоммиченной рабочей копии.

---

## Курсор обхода: читать `next_cursor`, не `cursor`

Вопрос закрыт живой проверкой на stage 2026-08-26 и зафиксирован в самом клиенте.
В ответе PIM заполняет **`next_cursor`**, а поле `cursor` приходит `null` — в
фикстуре клиента (`testdata/sku_products_search.json`) это специально видно:

```json
"meta": {"pagination": {"cursor": null, "limit": 2, "next_cursor": "eyJpZCI6NDA3NzkyfQ", "type": "cursor"}}
```

Запрос при этом отправляет курсор в поле `pagination.cursor` — то есть поля
запроса и ответа называются по-разному, и это единственная асимметрия контракта.

Почему это важнее, чем выглядит: если читать `cursor`, обход остановится после
первой страницы **молча**. Карта наполнится частично, ошибки не будет, и
расхождение обнаружится только когда заказ упрётся в `unknown_sku`. Поэтому в
Task 4 продолжение обхода обязано быть покрыто тестом на двух страницах.

### Task 2: Кеш идентификаторов в схеме

**Files:**
- Create: `platform-new/wbconnector/migrations/20260825120000_product_identifiers.sql`
- Create: `platform-new/wbconnector/internal/core/sku.go`

**Interfaces:**
- Produces: таблицы `product_identifiers`, `sku_conflicts`; вид отклонения `unknown_sku`; типы `core.SkuIdentity`, `core.SkuConflict`, константа `core.DeviationUnknownSKU`.

- [ ] **Step 1: Написать миграцию**

```sql
-- +goose Up
-- +goose StatementBegin

-- Наша сторона карты идентификаторов. Мастер — ENSI PIM (MP-WB-FBS-077);
-- здесь только кеш нужного подмножества полей, чтобы приём заказа не зависел
-- от доступности PIM. Вторая половина карты — goods (сторона WB).
--
-- Баркод первичным ключом потому, что это единственный идентификатор,
-- присутствующий одновременно в карточке WB (sizes[].skus), в PIM
-- (sku_products.barcode) и в контракте OTS (good_id).
CREATE TABLE product_identifiers (
    barcode             text        PRIMARY KEY,
    sku_id              bigint      NOT NULL,
    -- Наш SKU-артикул: то, что должно уезжать в OTS как article_id и дальше
    -- в WMS как ItemNr. vendorCode карточки WB для этого не годится — на проде
    -- это «модель/цвет» вида GAS011429/коричневый.
    vendor_code         text        NOT NULL,
    -- Артикул модели (СС) — для сверки с vendorCode карточки WB.
    product_vendor_code text        NOT NULL DEFAULT '',
    -- IDD: пригодится маркировке и 1С.
    external_id         text        NOT NULL DEFAULT '',
    mark_type           int,
    type_of_good        int,
    synced_at           timestamptz NOT NULL DEFAULT now(),
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- Полный проход обновляет synced_at; по нему видно SKU, пропавшие из PIM.
CREATE INDEX product_identifiers_synced_idx ON product_identifiers (synced_at);

-- Один баркод у двух SKU — не повод молча перезаписать карту: артикул уехал бы
-- на чужой товар. В карте остаётся последнее значение, факт — здесь.
CREATE TABLE sku_conflicts (
    id          bigserial   PRIMARY KEY,
    barcode     text        NOT NULL,
    known_sku   bigint      NOT NULL,
    seen_sku    bigint      NOT NULL,
    seen_at     timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX sku_conflicts_pair_idx
    ON sku_conflicts (barcode, known_sku, seen_sku);

-- Новый вид отклонения: PIM не знает баркод сборочного задания, поэтому наш
-- артикул неизвестен и заказ нельзя отдать в OTS.
-- В списке обязаны остаться все живые виды: supply_order_rejected добавлен
-- миграцией 20260820130000_supply_order_remote_outcome.sql, без него этот
-- ALTER запретит запись чужого отклонения.
ALTER TABLE deviations DROP CONSTRAINT deviations_kind_check;
ALTER TABLE deviations ADD CONSTRAINT deviations_kind_check
    CHECK (kind IN ('unmapped_barcode', 'stock_mismatch', 'stock_sync_error',
                    'kafka_status_rejected', 'reserve_shortage',
                    'supply_order_rejected', 'unknown_sku'));

-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
ALTER TABLE deviations DROP CONSTRAINT deviations_kind_check;
ALTER TABLE deviations ADD CONSTRAINT deviations_kind_check
    CHECK (kind IN ('unmapped_barcode', 'stock_mismatch', 'stock_sync_error',
                    'kafka_status_rejected', 'reserve_shortage',
                    'supply_order_rejected'));
DROP TABLE IF EXISTS sku_conflicts;
DROP TABLE IF EXISTS product_identifiers;
-- +goose StatementEnd
```

- [ ] **Step 2: Добавить доменные типы**

`internal/core/sku.go`:

```go
package core

import "time"

// SkuIdentity is our side of the identifier map: what PIM masters for one
// barcode. WB gives no SKU-level article of ours — only the barcode — so this
// is the only source for the OTS/WMS item number.
type SkuIdentity struct {
	Barcode           string
	SkuID             int64
	VendorCode        string
	ProductVendorCode string
	ExternalID        string
	MarkType          *int
	TypeOfGood        *int
	SyncedAt          time.Time
}

// SkuConflict — один баркод под разными SKU в PIM.
type SkuConflict struct {
	Barcode  string
	KnownSKU int64
	SeenSKU  int64
}

// DeviationUnknownSKU — PIM не знает баркод задания: наш артикул неизвестен,
// и в OTS заказ отдавать нельзя (пустой article_id оставляет в WMS безымянную
// строку).
const DeviationUnknownSKU = "unknown_sku"

// SkuImportResult — итог одного прохода pimsync. Форма повторяет
// GoodsImportResult (internal/core/goods.go), чтобы обе половины карты
// отчитывались одинаково.
type SkuImportResult struct {
	// Pages — сколько страниц PIM прочитано.
	Pages int
	// Skus — сколько строк принесла выгрузка.
	Skus int
	// Upserted — сколько строк кеша создано или обновлено.
	Upserted int
	// Conflicts — сколько баркодов переехало на другой SKU.
	Conflicts int
}
```

- [ ] **Step 3: Накатить и откатить миграцию**

```bash
cd $WORKSPACE/platform-new/wbconnector
export DSN='postgres://wb:wb@localhost:55432/wbconnector?sslmode=disable'
WBCONNECTOR_DB_DSN=$DSN go run ./cmd/migrate --cmd=up   --dir=migrations
WBCONNECTOR_DB_DSN=$DSN go run ./cmd/migrate --cmd=down --dir=migrations
WBCONNECTOR_DB_DSN=$DSN go run ./cmd/migrate --cmd=up   --dir=migrations
```

Expected: три раза `OK 20260825120000_product_identifiers.sql`, без ошибок.

- [ ] **Step 4: Коммит**

```bash
git add migrations/20260825120000_product_identifiers.sql internal/core/sku.go
git commit -m "feat: schema for the PIM-mastered SKU identifier cache"
```

---

### Task 3: Хранилище кеша

**Files:**
- Create: `platform-new/wbconnector/internal/adapters/pgstore/skus.go`
- Create: `platform-new/wbconnector/internal/adapters/pgstore/skus_test.go`

**Interfaces:**
- Consumes: `core.SkuIdentity`, `core.SkuConflict` (Task 2).
- Produces:
  - `(*Store).UpsertSkus(ctx, []core.SkuIdentity) (int, []core.SkuConflict, error)`
  - `(*Store).SkuByBarcode(ctx, barcode string) (*core.SkuIdentity, error)` — `(nil, nil)` если баркод неизвестен
  - `(*Store).SkusByBarcodes(ctx, []string) (map[string]core.SkuIdentity, error)`

- [ ] **Step 1: Написать падающие тесты**

`skus_test.go`:

```go
package pgstore

import (
	"context"
	"testing"

	"gitlab.gloria.aaanet.ru/greensight/gj/go/marketplaces/wbconnector/internal/core"
)

func TestUpsertSkusIsIdempotentAndReadable(t *testing.T) {
	store, _ := newTestStore(t)
	ctx := context.Background()

	rows := []core.SkuIdentity{{
		Barcode: "4660207658280", SkuID: 15324,
		VendorCode: "GAS011429-105", ProductVendorCode: "GAS011429",
		ExternalID: "00000000123",
	}}
	n, conflicts, err := store.UpsertSkus(ctx, rows)
	if err != nil || n != 1 || len(conflicts) != 0 {
		t.Fatalf("first upsert = %d/%v/%v, want 1/nil/nil", n, conflicts, err)
	}
	if _, _, err := store.UpsertSkus(ctx, rows); err != nil {
		t.Fatalf("repeat upsert: %v", err)
	}

	got, err := store.SkuByBarcode(ctx, "4660207658280")
	if err != nil {
		t.Fatalf("SkuByBarcode: %v", err)
	}
	if got == nil || got.VendorCode != "GAS011429-105" {
		t.Fatalf("sku = %+v, want the SKU vendor code from PIM", got)
	}

	missing, err := store.SkuByBarcode(ctx, "0000000000000")
	if err != nil {
		t.Fatalf("SkuByBarcode of unknown barcode: %v", err)
	}
	if missing != nil {
		t.Fatalf("unknown barcode = %+v, want nil", missing)
	}
}

// Баркод, переехавший на другой SKU, обязан остаться видимым: артикул иначе
// уедет на чужой товар, а карта об этом промолчит.
func TestUpsertSkusRecordsBarcodeMovedToAnotherSku(t *testing.T) {
	store, _ := newTestStore(t)
	ctx := context.Background()

	if _, _, err := store.UpsertSkus(ctx, []core.SkuIdentity{{
		Barcode: "4660207658280", SkuID: 1, VendorCode: "A-1",
	}}); err != nil {
		t.Fatalf("seed: %v", err)
	}

	_, conflicts, err := store.UpsertSkus(ctx, []core.SkuIdentity{{
		Barcode: "4660207658280", SkuID: 2, VendorCode: "B-1",
	}})
	if err != nil {
		t.Fatalf("conflicting upsert: %v", err)
	}
	if len(conflicts) != 1 || conflicts[0].KnownSKU != 1 || conflicts[0].SeenSKU != 2 {
		t.Fatalf("conflicts = %+v, want one 1→2 conflict", conflicts)
	}
	got, err := store.SkuByBarcode(ctx, "4660207658280")
	if err != nil || got == nil || got.SkuID != 2 {
		t.Fatalf("sku after conflict = %+v (%v), want the latest SKU 2", got, err)
	}
}

func TestSkusByBarcodesReturnsOnlyKnown(t *testing.T) {
	store, _ := newTestStore(t)
	ctx := context.Background()

	if _, _, err := store.UpsertSkus(ctx, []core.SkuIdentity{
		{Barcode: "1111111111111", SkuID: 1, VendorCode: "A-1"},
		{Barcode: "2222222222222", SkuID: 2, VendorCode: "A-2"},
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}

	got, err := store.SkusByBarcodes(ctx, []string{"1111111111111", "9999999999999"})
	if err != nil {
		t.Fatalf("SkusByBarcodes: %v", err)
	}
	if len(got) != 1 || got["1111111111111"].VendorCode != "A-1" {
		t.Fatalf("map = %+v, want only the known barcode", got)
	}
}
```

- [ ] **Step 2: Прогнать — должны упасть**

Run: `WBCONNECTOR_TEST_DSN=$DSN go test ./internal/adapters/pgstore/ -run 'TestUpsertSkus|TestSkusByBarcodes' -v`
Expected: FAIL — методов ещё нет.

- [ ] **Step 3: Реализовать `skus.go`**

Структуру взять с `internal/adapters/pgstore/goods.go`: `UpsertGoods` — **set-based**, он раскладывает батч в параллельные массивы и делает один запрос через `unnest` внутри транзакции. Повторить ту же форму, читать её перед написанием:

```bash
rg -n -A80 "func \(s \*Store\) UpsertGoods" internal/adapters/pgstore/goods.go
```

Конфликт нельзя получить из `RETURNING`: после `DO UPDATE` там уже новое значение. Прежний `sku_id` читается **до** записи, в той же транзакции:

```go
	const knownQ = `
		SELECT barcode, sku_id
		FROM product_identifiers
		WHERE barcode = ANY($1)`
	// известные sku_id до записи; расхождение с входящим набором и есть конфликт
```

Затем один set-based upsert:

```go
	const upsertQ = `
		INSERT INTO product_identifiers (barcode, sku_id, vendor_code,
		                                 product_vendor_code, external_id,
		                                 mark_type, type_of_good, synced_at)
		SELECT * FROM unnest($1::text[], $2::bigint[], $3::text[], $4::text[],
		                     $5::text[], $6::int[], $7::int[]) AS t(
		       barcode, sku_id, vendor_code, product_vendor_code,
		       external_id, mark_type, type_of_good),
		       LATERAL (SELECT now()) AS s(synced_at)
		ON CONFLICT (barcode) DO UPDATE SET
			sku_id              = EXCLUDED.sku_id,
			vendor_code         = EXCLUDED.vendor_code,
			product_vendor_code = EXCLUDED.product_vendor_code,
			external_id         = EXCLUDED.external_id,
			mark_type           = EXCLUDED.mark_type,
			type_of_good        = EXCLUDED.type_of_good,
			synced_at           = now()`
```

и запись конфликтов тем же приёмом, что `goods_conflicts` (`ON CONFLICT DO NOTHING` по уникальной тройке). Если форма `unnest` с `LATERAL` окажется неудобной, допустимо повторить ровно тот вариант, который использует `goods.go` — важно только, чтобы запрос был один на батч, а не по строке.

- [ ] **Step 4: Прогнать — должны пройти**

Run: `WBCONNECTOR_TEST_DSN=$DSN go test -race ./internal/adapters/pgstore/ -count=1`
Expected: ok.

- [ ] **Step 5: Коммит**

```bash
git add internal/adapters/pgstore/skus.go internal/adapters/pgstore/skus_test.go
git commit -m "feat: store for the PIM SKU identifier cache"
```

---

### Task 4: Адаптер PIM и импортёр

**Files:**
- Create: `platform-new/wbconnector/internal/adapters/pim/client.go`
- Create: `platform-new/wbconnector/internal/adapters/pim/client_test.go`
- Create: `platform-new/wbconnector/internal/skus/importer.go`
- Create: `platform-new/wbconnector/internal/skus/importer_test.go`
- Create: `platform-new/wbconnector/cmd/pimsync/main.go`
- Modify: `platform-new/wbconnector/Makefile`, `platform-new/wbconnector/Dockerfile`

**Interfaces:**
- Consumes: `pimclient` (Task 1), `(*Store).UpsertSkus` (Task 3).
- Produces:
  - `pim.New(baseURL string, timeout time.Duration) *Client`
  - `(*pim.Client).Page(ctx, cursor string, limit int) ([]core.SkuIdentity, string, error)` — вторым значением следующий курсор, пустая строка = конец
  - `(*pim.Client).ByBarcodes(ctx, []string) ([]core.SkuIdentity, error)`
  - `skus.NewImporter(api PIMAPI, store Store, maxPages int) *Importer` и `(*Importer).Run(ctx) (core.SkuImportResult, error)`

- [ ] **Step 1: Написать падающий тест импортёра на фейках**

`internal/skus/importer_test.go`:

```go
package skus

import (
	"context"
	"testing"

	"gitlab.gloria.aaanet.ru/greensight/gj/go/marketplaces/wbconnector/internal/core"
)

type fakeAPI struct {
	pages [][]core.SkuIdentity
	calls []string
}

func (f *fakeAPI) Page(_ context.Context, cursor string, _ int) ([]core.SkuIdentity, string, error) {
	f.calls = append(f.calls, cursor)
	if len(f.pages) == 0 {
		return nil, "", nil
	}
	page := f.pages[0]
	f.pages = f.pages[1:]
	next := ""
	if len(f.pages) > 0 {
		next = "cursor-next"
	}
	return page, next, nil
}

type fakeStore struct{ rows []core.SkuIdentity }

func (f *fakeStore) UpsertSkus(_ context.Context, rows []core.SkuIdentity) (int, []core.SkuConflict, error) {
	f.rows = append(f.rows, rows...)
	return len(rows), nil, nil
}

// Обход обязан идти до конца: PIM не поддерживает фильтр по времени, поэтому
// проход всегда полный, и остановка на первой странице оставила бы карту
// частичной без всякого признака.
func TestImporterWalksEveryPage(t *testing.T) {
	api := &fakeAPI{pages: [][]core.SkuIdentity{
		{{Barcode: "1", SkuID: 1, VendorCode: "A-1"}},
		{{Barcode: "2", SkuID: 2, VendorCode: "A-2"}},
	}}
	store := &fakeStore{}

	res, err := NewImporter(api, store, 0).Run(context.Background())
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	if res.Pages != 2 || res.Skus != 2 {
		t.Fatalf("result = %+v, want 2 pages and 2 SKUs", res)
	}
	if len(store.rows) != 2 {
		t.Fatalf("stored = %d, want both pages persisted", len(store.rows))
	}
	if len(api.calls) != 2 || api.calls[0] != "" || api.calls[1] != "cursor-next" {
		t.Fatalf("cursors = %v, want an empty start and one follow-up for two pages", api.calls)
	}
}
```

- [ ] **Step 1b: Написать падающий тест адаптера на httptest**

Тест импортёра выше подменяет весь адаптер, поэтому он **не проверяет** ни чтение
курсора, ни имя ключа фильтра — а это ровно те два места, где догадки уже
оказывались неверными. Нужен отдельный тест, который ходит по HTTP.

Create: `platform-new/wbconnector/internal/adapters/pim/client_test.go`

```go
// Продолжение обхода читается из meta.pagination.next_cursor: PIM присылает
// cursor как null. Тест держит эту асимметрию — с чтением `cursor` он упадёт.
func TestPageFollowsNextCursor(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var got struct {
			Filter     map[string]any `json:"filter"`
			Pagination struct{ Type, Cursor string } `json:"pagination"`
		}
		_ = json.NewDecoder(r.Body).Decode(&got)
		if got.Pagination.Type != "cursor" {
			t.Errorf("pagination.type = %q, want cursor — PIM defaults to offset", got.Pagination.Type)
		}
		w.Header().Set("Content-Type", "application/json")
		io.WriteString(w, `{"data":[{"id":407792,"barcode":"4660207658280",`+
			`"vendor_code":"GAS011429F0002","product_vendor_code":"GAS011429",`+
			`"external_id":"00055550005552694"}],`+
			`"meta":{"pagination":{"cursor":null,"next_cursor":"CUR2"}}}`)
	}))
	defer srv.Close()

	rows, next, err := New(pim.New(srv.URL)).Page(context.Background(), "", 100)
	if err != nil {
		t.Fatalf("Page: %v", err)
	}
	if next != "CUR2" {
		t.Fatalf("next = %q, want CUR2 — обход остановился бы после первой страницы", next)
	}
	if len(rows) != 1 || rows[0].VendorCode != "GAS011429F0002" {
		t.Fatalf("rows = %+v, want the SKU-level vendor_code", rows)
	}
}

// Равенство в PIM это ключ БЕЗ суффикса: карта суффиксов ставит 'equal' в
// пустую строку. С `barcode_equal` PIM вернул бы 400 или проигнорировал фильтр.
func TestByBarcodesSendsBareFilterKey(t *testing.T) {
	// тот же httptest; проверить, что в теле пришёл ключ "barcode"
	// со значением-массивом, и что ключа "barcode_equal" нет.
}
```

Обе проверки — про контракт, а не про нашу логику, поэтому они обязаны идти по
HTTP: только так видно фактическое тело запроса и разбор фактического ответа.

- [ ] **Step 2: Прогнать — должен упасть**

Run: `go test ./internal/skus/ ./internal/adapters/pim/ -v`
Expected: FAIL — пакетов ещё нет.

- [ ] **Step 3: Реализовать адаптер PIM**

Сначала — зависимость, вместе с импортом (см. Task 1, почему не раньше):

```bash
cd $WORKSPACE/platform-new/wbconnector
GOPRIVATE=gitlab.gloria.aaanet.ru go get gitlab.gloria.aaanet.ru/greensight/gj/go/clients/pimclient@v0.1.3
```

Expected: после написания адаптера строка `…/pimclient v0.1.3` стоит в `go.mod` **без** пометки `// indirect`, и `go mod tidy` её не убирает.


`internal/adapters/pim/client.go` переводит `pim.SkuProduct` в `core.SkuIdentity` и задаёт два режима запроса. Модуль называется `pimclient`, а пакет внутри — `pim`, поэтому импорт выглядит как `pim "gitlab.gloria.aaanet.ru/greensight/gj/go/clients/pimclient"`. Почти все поля запроса — указатели, отсюда локальные переменные и хелпер `ptr`:

```go
func ptr[T any](v T) *T { return &v }

// Page reads one page of the full walk. An empty next cursor means the end.
func (c *Client) Page(ctx context.Context, cursor string, limit int) ([]core.SkuIdentity, string, error) {
	req := pimclient.SearchSkuProductsRequest{
		Sort: &[]string{"id"},
		Pagination: &pim.CursorPagination{
			Type: ptr(pim.PaginationTypeCursor), Limit: &limit, Cursor: &cursor,
		},
	}
	resp, err := c.api.SearchSkuProducts(ctx, req)
	if err != nil {
		return nil, "", fmt.Errorf("pim: search sku products: %w", err)
	}
	// Запрос отправляет курсор в pagination.cursor, а ответ приносит его в
	// next_cursor — единственная асимметрия контракта. Чтение `cursor` здесь
	// остановило бы обход после первой страницы молча.
	next := ""
	if p := resp.Meta.Pagination; p != nil && p.NextCursor != nil {
		next = *p.NextCursor
	}
	return identities(resp.Data), next, nil
}

// ByBarcodes is the targeted lookup. The filter key is plain "barcode":
// SkuProductsQuery declares it via BundleFilter::input, and the generated name
// is baseName + suffixes[type], and the query-builder-extension package ships
// a config mapping 'equal' => '' which PIM does not override — so the
// EQUAL variant keeps the bare name, and only the other variants get a suffix
// (__like, __empty, __gt, …). An array value becomes whereIn, so a list is
// accepted. Batched because the body and PIM page size are finite.
func (c *Client) ByBarcodes(ctx context.Context, barcodes []string) ([]core.SkuIdentity, error) {
	const batch = 500
	var out []core.SkuIdentity
	for start := 0; start < len(barcodes); start += batch {
		end := min(start+batch, len(barcodes))
		filter := map[string]any{"barcode": barcodes[start:end]}
		limit := batch
		resp, err := c.api.SearchSkuProducts(ctx, pim.SearchSkuProductsRequest{
			Filter: &filter,
			Pagination: &pim.CursorPagination{
				Type: ptr(pim.PaginationTypeCursor), Limit: &limit,
			},
		})
		if err != nil {
			return nil, fmt.Errorf("pim: lookup %d barcodes: %w", end-start, err)
		}
		out = append(out, identities(resp.Data)...)
	}
	return out, nil
}
```

- [ ] **Step 4: Реализовать импортёр**

`internal/skus/importer.go` — цикл по страницам с курсором в `sync_state` под именем `pim_skus`:

```go
func (i *Importer) Run(ctx context.Context) (core.SkuImportResult, error) {
	var res core.SkuImportResult

	cursor, err := i.startCursor(ctx)
	if err != nil {
		return res, err
	}

	for {
		rows, next, err := i.api.Page(ctx, cursor, pageLimit)
		if err != nil {
			return res, fmt.Errorf("skus: read PIM page %d: %w", res.Pages+1, err)
		}
		res.Pages++
		res.Skus += len(rows)

		if len(rows) > 0 {
			n, conflicts, err := i.store.UpsertSkus(ctx, rows)
			if err != nil {
				return res, err
			}
			res.Upserted += n
			res.Conflicts += len(conflicts)
		}

		if next == "" || (i.maxPages > 0 && res.Pages >= i.maxPages) {
			break
		}
		cursor = next
		if err := i.saveCursor(ctx, cursor); err != nil {
			return res, err
		}
	}
	return res, nil
}
```

`startCursor`/`saveCursor` — как в `internal/goods/importer.go`, только имя записи `sync_state` другое; при `--full` стартовый курсор игнорируется.

- [ ] **Step 5: Реализовать резолвер (кеш → PIM → кеш)**

`internal/skus/resolver.go` — то, чем пользуется обработчик OTS:

```go
// Resolver answers "what is our SKU for this barcode". The cache is checked
// first so the order intake does not depend on PIM being up; a miss is looked
// up in PIM once and written back, because a card created today is not in the
// nightly sweep yet.
type Resolver struct {
	store Store
	api   PIMAPI
}

// Resolve returns (nil, nil) when neither the cache nor PIM knows the barcode.
func (r *Resolver) Resolve(ctx context.Context, barcode string) (*core.SkuIdentity, error) {
	cached, err := r.store.SkuByBarcode(ctx, barcode)
	if err != nil {
		return nil, err
	}
	if cached != nil {
		return cached, nil
	}

	fresh, err := r.api.ByBarcodes(ctx, []string{barcode})
	if err != nil {
		return nil, err
	}
	if len(fresh) == 0 {
		return nil, nil
	}
	if _, _, err := r.store.UpsertSkus(ctx, fresh); err != nil {
		return nil, err
	}
	return &fresh[0], nil
}
```

Тест перед реализацией:

```go
func TestResolverPrefersCacheAndBackfillsOnMiss(t *testing.T) {
	store := &fakeStore{known: map[string]core.SkuIdentity{
		"1111111111111": {Barcode: "1111111111111", VendorCode: "A-1"},
	}}
	api := &fakeAPI{byBarcode: map[string]core.SkuIdentity{
		"2222222222222": {Barcode: "2222222222222", VendorCode: "A-2"},
	}}
	r := NewResolver(store, api)

	if got, _ := r.Resolve(context.Background(), "1111111111111"); got.VendorCode != "A-1" {
		t.Fatalf("cached hit = %+v", got)
	}
	if api.lookups != 0 {
		t.Fatalf("PIM called %d times for a cached barcode, want 0", api.lookups)
	}

	got, err := r.Resolve(context.Background(), "2222222222222")
	if err != nil || got == nil || got.VendorCode != "A-2" {
		t.Fatalf("miss = %+v (%v), want the PIM answer", got, err)
	}
	if len(store.rows) != 1 {
		t.Fatalf("stored = %d, want the miss written back to the cache", len(store.rows))
	}

	unknown, err := r.Resolve(context.Background(), "9999999999999")
	if err != nil || unknown != nil {
		t.Fatalf("unknown = %+v (%v), want (nil, nil)", unknown, err)
	}
}
```

- [ ] **Step 6: Реализовать бинарь**

`cmd/pimsync/main.go` повторяет `cmd/wbgoods/main.go`: флаги `--max-pages` (0 — до конца) и `--full`, логирование итога одной строкой. В `Makefile` и `Dockerfile` добавить `pimsync` рядом с `wbstatus` и `wbgoods`.

- [ ] **Step 7: Прогнать тесты и сборку**

```bash
go build ./... && go test -race ./internal/skus/ ./internal/adapters/pim/ -count=1
```

Expected: ok.

- [ ] **Step 8: Коммит**

```bash
git add internal/adapters/pim internal/skus cmd/pimsync Makefile Dockerfile go.mod go.sum
git commit -m "feat: PIM SKU importer, resolver and pimsync binary"
```

---

### Task 5: Артикул в контракте OTS

Ядро задачи: именно здесь `GAS011429/коричневый` перестаёт уезжать в WMS.

**Files:**
- Modify: `platform-new/wbconnector/internal/worker/commands/ots.go:47-60` (поле и конструктор), `:225-233` (состав заказа)
- Modify: `platform-new/wbconnector/internal/worker/commands/ots.go:25-37` (расширение `OrderStore` — интерфейс лежит в `ots.go`, не в `commands.go`)
- Modify: `platform-new/wbconnector/internal/worker/commands/ots_test.go`
- Modify: `platform-new/wbconnector/internal/worker/commands/fakes_test.go`
- Modify: `platform-new/wbconnector/internal/app/container.go` (пятый аргумент `NewOTS`)

Правка сигнатуры `NewOTS` ломает сборку, поэтому проводка в контейнере входит в эту же задачу: каждая задача обязана заканчиваться зелёной сборкой. Пока `PIM_BASE_URL` не задан (это Task 6), в контейнер передаётся резолвер, который всегда возвращает `(nil, nil)` — экспорт в OTS честно отказывает с `unknown_sku` вместо того, чтобы молча отправить неверный артикул.

**Interfaces:**
- Consumes: `skus.Resolver` (Task 4), `core.DeviationUnknownSKU` и `core.SkuIdentity` (Task 2).
- Produces: у `OTSHandlers` появляется пятое поле `skus SkuResolver`; `NewOTS` получает пятый аргумент. Интерфейс:

```go
// SkuResolver answers what our SKU is for a WB barcode. *skus.Resolver
// implements it.
type SkuResolver interface {
	Resolve(ctx context.Context, barcode string) (*core.SkuIdentity, error)
}
```

**Важно:** в пакете `internal/worker/commands` **нет** ни `mustJSON`, ни записи отклонений — это проверено. `OTSHandlers` держит `store OrderStore`, поэтому отклонение пишется через расширение этого интерфейса, а не через новую зависимость: `*pgstore.Store` уже реализует `RecordDeviation` (`internal/adapters/pgstore/deviations.go:14`). Добавить в `OrderStore`:

```go
	// RecordDeviation фиксирует случай, требующий разбора человеком.
	RecordDeviation(ctx context.Context, d core.Deviation) error
```

- [ ] **Step 1: Написать падающие тесты**

```go
func TestOTSOrderCarriesOurSkuVendorCode(t *testing.T) {
	// WB отдаёт «модель/цвет», в OTS обязан уехать наш SKU-артикул.
	store := newFakeStore()
	store.orders[5] = core.Order{
		WBOrderID: 5, GJOrderID: "3200000011", Barcode: "4660207658280",
		Article: "GAS011429/коричневый", WarehouseID: "9148", PriceKopecks: 100000,
	}
	skus := fakeSkuResolver{"4660207658280": {VendorCode: "GAS011429-105"}}

	req := buildOTSOrder(t, store, skus, 5)
	if got := req.Goods[0].Article; got != "GAS011429-105" {
		t.Fatalf("OTS article = %q, want our SKU vendor code, not the WB vendorCode", got)
	}
}

func TestOrderWithUnknownBarcodeIsNotExportedAndIsRecorded(t *testing.T) {
	store := newFakeStore()
	store.orders[6] = core.Order{
		WBOrderID: 6, GJOrderID: "3200000012", Barcode: "9999999999999",
		Article: "GAS011429/коричневый", WarehouseID: "9148",
	}
	skus := fakeSkuResolver{} // PIM не знает баркод

	err := exportOrder(t, store, skus, 6)
	if err == nil {
		t.Fatal("export succeeded with an unknown SKU — WMS would get a nameless line")
	}
	if len(store.deviations) != 1 || store.deviations[0].Kind != core.DeviationUnknownSKU {
		t.Fatalf("deviations = %+v, want one unknown_sku", store.deviations)
	}
	if store.otsCalls != 0 {
		t.Fatalf("OTS calls = %d, want none", store.otsCalls)
	}
}
```

Имена `buildOTSOrder`/`exportOrder`/`fakeSkuResolver` — тестовые хелперы этого пакета; их формы взять с существующих тестов `internal/worker/commands/ots_test.go`, чтобы не заводить второй стиль.

- [ ] **Step 2: Прогнать — должны упасть**

Run: `go test ./internal/worker/commands/ -run 'TestOTSOrderCarries|TestOrderWithUnknownBarcode' -v`
Expected: FAIL.

- [ ] **Step 3: Реализовать**

В построителе заказа после проверки баркода:

```go
	sku, err := h.skus.Resolve(ctx, barcode)
	if err != nil {
		return ots.OrderRequest{}, nil, err
	}
	if sku == nil {
		// Пустой article_id оставляет в WMS безымянную строку (ItemNr), а
		// vendorCode от WB артикулом не является: на проде это «модель/цвет».
		// Экспорт не делаем.
		payload, err := json.Marshal(map[string]any{
			"wb_order_id":    order.WBOrderID,
			"gj_order_id":    strings.TrimSpace(order.GJOrderID),
			"wb_vendor_code": order.Article,
		})
		if err != nil {
			return ots.OrderRequest{}, nil, fmt.Errorf("build unknown_sku payload: %w", err)
		}
		if err := h.store.RecordDeviation(ctx, core.Deviation{
			Kind:    core.DeviationUnknownSKU,
			Ref:     barcode,
			Payload: payload,
		}); err != nil {
			return ots.OrderRequest{}, nil, err
		}
		return ots.OrderRequest{}, nil, fmt.Errorf(
			"order %d: PIM does not know barcode %s, our article is unknown",
			order.WBOrderID, barcode)
	}
```

Тип поля `Payload` сверен 2026-08-25: `core.Deviation.Payload` — `[]byte` (`internal/core/deviation.go:37-47`), результат `json.Marshal` подходит без обёрток.

И в составе заказа `Article: sku.VendorCode`.

Ошибка **retryable**, не `permanentf`: адресный дозапрос в PIM внутри резолвера может наполнить кеш к следующей попытке; если PIM его правда не знает, команда паркуется по обычному бюджету, а отклонение уже видно.

- [ ] **Step 4: Прогнать — должны пройти**

Run: `WBCONNECTOR_TEST_DSN=$DSN go test -race ./internal/worker/commands/ -count=1`
Expected: ok.

- [ ] **Step 5: Мутационная проверка**

Временно вернуть `Article: order.Article` и убедиться, что `TestOTSOrderCarriesOurSkuVendorCode` падает с сообщением про `GAS011429/коричневый`. Вернуть код.

- [ ] **Step 6: Провести зависимость через контейнер**

В `internal/app/container.go` передать резолвер пятым аргументом `commands.NewOTS`. Пока `PIM_BASE_URL` не настроен, подставляется заглушка, отвечающая «не знаю»:

```go
// unknownSKUs stands in until PIM is configured. Answering "unknown" is the
// safe default: the export refuses loudly instead of sending WB's
// «модель/цвет» into the WMS item number.
type unknownSKUs struct{}

func (unknownSKUs) Resolve(context.Context, string) (*core.SkuIdentity, error) {
	return nil, nil
}
```

С заглушкой экспорт в OTS встаёт с `unknown_sku` для **всех** заказов, поэтому Task 5 и Task 6 выкатываются на стенд одним релизом, без промежуточного деплоя Task 5.

- [ ] **Step 7: Полная проверка и коммит**

```bash
go build ./... && WBCONNECTOR_TEST_DSN=$DSN go test -race -p 1 ./... -count=1
git add internal/worker/commands/ internal/app/container.go
git commit -m "fix: send our SKU article to OTS instead of the WB vendorCode"
```

Expected: сборка и весь набор зелёные.

---

### Task 6: Конфигурация, сборка, стенд

**Files:**
- Modify: `platform-new/wbconnector/internal/platform/config/config.go`
- Modify: `platform-new/wbconnector/internal/platform/config/config_test.go`
- Modify: `platform-new/wbconnector/internal/app/container.go`
- Modify: `platform-new/wbconnector/internal/testharness/ports.go`
- Modify: `platform-new/wbconnector/.env.example`, `README.md`
- Modify: `platform/ensi/devops/ms-helm-values/stage/go/wbconnector/wbconnector.yaml`

**Interfaces:**
- Consumes: всё из задач 1–5.
- Produces: `cfg.PIM.BaseURL`, `cfg.PIM.Timeout`; собранный резолвер в контейнере; cron `pimsync` на стенде.

- [ ] **Step 1: Тест на конфиг**

```go
func TestLoadReadsPIMSettings(t *testing.T) {
	t.Setenv("PIM_BASE_URL", "http://pim-master.stage.svc.cluster.local")
	t.Setenv("PIM_TIMEOUT_MS", "15000")

	cfg := Load()
	if cfg.PIM.BaseURL != "http://pim-master.stage.svc.cluster.local" {
		t.Fatalf("base url = %q", cfg.PIM.BaseURL)
	}
	if cfg.PIM.Timeout != 15*time.Second {
		t.Fatalf("timeout = %v, want 15s", cfg.PIM.Timeout)
	}
}
```

- [ ] **Step 2: Реализовать конфиг и сборку в контейнере**

`PIMConfig{BaseURL string; Timeout time.Duration}`; по образцу `OTS_BASE_URL`. Резолвер собирается только при непустом `PIM_BASE_URL`; без него сервис поднимается, а экспорт в OTS отказывает с понятным сообщением — так же, как циклы без БД пишут предупреждение и не запускаются.

Заменить `StubVendorCodeResolver` в стенде на резолвер поверх кеша.

- [ ] **Step 3: Values стенда**

```yaml
    PIM_BASE_URL:
      value: "http://pim-master.stage.svc.cluster.local"
    PIM_TIMEOUT_MS:
      value: "15000"
```

и cron рядом с `wbgoods`:

```yaml
  pimsync:
    enabled: true
    container: go
    schedule: "0 20 * * *"
    command: ["/app/bin/pimsync"]
```

Расписание раньше `wbgoods` (21:00): сначала наша сторона карты, потом сторона WB.

Адрес PIM на stage сверен 2026-08-25: `stage/common-env.yaml:21` уже задаёт `CATALOG_PIM_SERVICE_HOST = http://pim-master.stage.svc.cluster.local` (service `pim-master`, port 80 → targetPort 8080, `stage/catalog/pim/pim.yaml:166-170`; values PIM лежат в `stage/catalog/pim/`, не в `stage/php/`). Используем то же имя хоста, без `:8080`.

- [ ] **Step 4: Полная проверка**

```bash
cd $WORKSPACE/platform-new/wbconnector
go build ./... && go vet ./... && gofmt -l internal/ cmd/
WBCONNECTOR_TEST_DSN=$DSN go test -race -p 1 ./... -count=1
```

Expected: пусто у `gofmt`, всё `ok`.

- [ ] **Step 5: Коммит**

```bash
git add internal/platform/config internal/app/container.go internal/testharness .env.example README.md
git commit -m "feat: wire the PIM identifier resolver into the service"
```

---

## Final Verification Gate

- [ ] `go build ./...`, `go vet ./...`, `gofmt -l` — чисто в обоих репозиториях.
- [ ] `WBCONNECTOR_TEST_DSN=… go test -race -p 1 ./... -count=1` — зелёно.
- [ ] Миграция `20260825120000` накатывается и откатывается.
- [ ] `stage:deploy` проходит, Deployment и CronJob на одном образе.
- [ ] На стенде `pimsync` отработал: в логе одна строка с числом страниц и SKU, в `product_identifiers` непустая карта.
- [ ] Заказ из песочницы уезжает в OTS с `article_id`, равным `vendor_code` из PIM, а не `TEST-*`/`модель/цвет`.
- [ ] Заказ с намеренно неизвестным баркодом не уезжает и даёт отклонение `unknown_sku`.

## Вне объёма

- Запись чего-либо в PIM или в 1С-справочник идентификаторов МП. Мастер не меняется.
- Сверка ошибок заведения карточек (`goods × product_identifiers`): отдельная задача после релиза.
- Prod-values для `wbconnector` — их не существует вообще, это отдельная работа перед прод-релизом.
- Периодический полный проход `wbgoods` и чистка карты WB по `synced_at`.

## Пересечение баркодов PIM × WB — измерено 2026-08-25

Вопрос закрыт фактом, до реализации. Источники: прод-снимок каталога
`platform-new/wbconnector/dev/catalog/wb-catalog-2026-07-27.jsonl.gz` и прод-БД
PIM (`ensi-gs-pim-prod`, только чтение).

| Величина | Значение |
|---|---|
| Уникальных баркодов в каталоге WB | 359 892 |
| Из них корректной длины 13 | 359 881 |
| Битой длины (12 / 5 / 3 символа) | 8 / 1 / 2 — итого **11** |
| SKU в PIM | 626 044 |
| Уникальных баркодов в PIM | 626 039 (то есть **5 дублей**) |
| Длина баркода в PIM | ровно 13 у всех, пустых нет |
| Сопоставлено | **весь каталог, не выборка** |
| Есть в WB, нет в PIM | **3 883 → 1,08 %** |

Расхождение не случайное: это один опознаваемый класс плюс мусор.

| Класс отсутствующих | Сколько |
|---|---:|
| Внутренние баркоды «2…», 13 символов | 3 862 |
| Битой длины (`123`, `124`, `56-58`, `460123456789`…`460123456799`) | 11 |
| Корректные GS1 «4…», 13 символов | **10** |

**Покрытие настоящих GS1-баркодов — 356 009 из 356 019, то есть 99,997 %.**

Следствия для реализации:

1. **Для обычного товара связка по баркоду работает практически всегда** —
   не сопоставились 10 баркодов из 356 019. Soft-delete в `sku_products`
   отсутствует (колонок `deleted_at`/статуса в таблице нет), так что это
   настоящее отсутствие, а не скрытые фильтром строки.
2. **Весь промах в 1,08 % — это баркоды с первой цифрой «2».** В PIM таких нет
   ни одного (все 626 039 начинаются с «4»), а в каталоге WB их 3 862, и
   отсутствуют они все до единого. Префикс «2» в EAN-13 зарезервирован под
   внутреннее обращение, то есть это не товарные GS1-коды, а внутренние.

   И это **не легаси**. Разбор по карточкам:

   | Где лежат внутренние баркоды | Баркодов | Карточек | Обновлялись в 2026 |
   |---|---:|---:|---:|
   | Смешанные карточки: часть размеров на GS1, часть на внутреннем | **2 431** | 2 035 | 1 573 |
   | Карточки, где внутренние все баркоды | 1 431 | 991 | 528 |

   У смешанных нормальный `vendorCode` (`GSH010649/лайт`, `GSK016941/белый`), и
   распределение — почти всегда **один внутренний размер из N**: 1/6 — 603
   карточки, 1/4 — 408, 1/5 — 340, 1/7 — 107. То есть это живой товар, у
   которого одному размеру завели внутренний баркод вместо товарного EAN.
   У полностью внутренних `vendorCode` битый (`Леггинсы/size44/23/12/new1`,
   `BSH006032/size`) — вот это похоже на тестовые дубли.

   Практический вывод: политика «не экспортировать» **будет** останавливать
   заказы на реальные продаваемые размеры, а не только на мусор. Корневая
   причина — данные карточки, а не наш код: физически склад и OTS работают по
   баркоду, поэтому правильное исправление — привести баркод размера в ЛК ВБ к
   товарному EAN. Реестр `unknown_sku` для этого и нужен, а список затронутых
   карточек можно выдать контент-менеджерам уже сейчас, из снимка каталога, до
   всякой реализации.

   Автоматический обходной путь дорог: связка «карточка → товар» есть только
   через `vendorCode` уровня модели с цветом, а размер пришлось бы сопоставлять
   по `techSize`, причём `SkuProductsQuery` фильтра по `product_vendor_code`
   не разрешает вовсе (только по `vendor_code` уровня SKU). Это отдельный
   проект, не часть этого плана.
3. **11 битых баркодов — очевидные тестовые карточки в боевом кабинете**
   (`123`, `124`, `56-58`, серия `46012345678x`). В PIM все баркоды ровно
   13-символьные, так что эти не сопоставятся никогда и попадут в `unknown_sku`
   заслуженно. Стоит сообщить контент-менеджерам.
4. **5 дублей баркода в PIM** — ровно тот случай, под который в Task 2 заведён
   `sku_conflicts`: один баркод у двух SKU. Реестр не теоретический.

## Открытые вопросы

- **Не блокирует реализацию, блокирует включение на пилоте:** 2 431 размер в
  2 035 живых карточках заведён на внутренний баркод. Нужно решение владельца —
  чинить баркоды в ЛК ВБ (правильный путь, потому что склад и OTS физически
  работают по баркоду) или сознательно принять, что часть заказов будет
  останавливаться в реестре `unknown_sku`. Список затронутых карточек и размеров
  выдаётся из снимка каталога без всякого кода.
- 11 тестовых карточек в боевом кабинете (`123`, `124`, `56-58`, серия
  `46012345678x`) чинить в ЛК ВБ или терпеть в реестре. Вопрос к
  контент-менеджерам.
- Что делать с SKU, пропавшими из PIM (`synced_at` отстал). Пока только наблюдаем.

## Источники

- `docs/research/marketplaces/EVIDENCE-LEDGER.md` — `MP-WB-FBS-077` (цепочка идентификаторов), `MP-WB-FBS-040` (остатки только по `chrtId`).
- `docs/research/marketplaces/stages/stage-18-wb-identifiers-stocks-sandbox.md` — вариант B, карта на стороне коннектора.
- `platform/ensi/apps/catalog/pim/public/api-docs/v1/sku_products/` — контракт `sku-products:search`.
- `platform/ensi/apps/catalog/pim/app/Http/ApiV1/Modules/Products/Queries/SkuProductsQuery.php` — разрешённые фильтры и сорт.
- `platform-new/wbconnector/internal/adapters/ots/types.go:77-80` — почему пустой артикул недопустим.
- Прод-снимок каталога WB 2026-07-27: `vendorCode` вида `AAA######/цвет` у 81 860 из 82 228 карточек (99,55 %); у остальных 368 — произвольные значения (вплоть до самого баркода или свободного текста, напр. `4650215494826/new`), что лишь усиливает вывод: ключом связки vendorCode быть не может.
