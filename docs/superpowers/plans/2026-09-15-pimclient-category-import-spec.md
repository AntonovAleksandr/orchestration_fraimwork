# ТЗ A, редакция 3: Go pimclient — поиск импортов, загрузка Excel и регистрация

> **Согласованная редакция от 2026-09-16.** PIM не меняем, intgateway остаётся без БД. Gateway допускает запрос, если найдено не больше двух активных импортов PIM; при трёх и более отклоняет. Это проверка нагрузки по текущему списку, не дедупликация и не атомарный лимит параллелизма.

> Для исполнителя: используй `superpowers:executing-plans`, выполняй шаги последовательно. Это самостоятельное ТЗ и план реализации; контекст других сессий не требуется. Реализация разрешена в указанном репозитории. Новое проектирование задачи и повторное согласование уже зафиксированных решений не нужны.

**Цель:** расширить существующий Go-клиент PIM тремя методами: загрузка файла, регистрация асинхронного импорта и поиск импортов для проверки текущей нагрузки gateway.

**Редакция 3:** Итоговый объём — ровно три новых метода: SearchProductImports, PreloadProductImportFile, CreateProductImport. Библиотека не хранит состояние и не реализует порог «больше двух»: это политика gateway.

**Архитектура:** библиотека моделирует HTTP-контракт PIM. Excel проверяет вызывающий сервис intgateway; обработку строк выполняет PIM. Клиент ничего не знает о токене intgateway, команде AutoMerch или её процессах.

**Стек:** Go 1.26, types-only oapi-codegen, `gj-go-httpclient`.

**Spec:** этот документ содержит полный нормативный контракт и план. Зависимость от ТЗ intgateway отсутствует.

## 1. Границы и правила выполнения

- `$WORKSPACE` — корень GJ-Ecommerce. Рабочий репозиторий: `$WORKSPACE/platform-new/clients/pim`.
- Git remote: `git@gitlab.gloria.aaanet.ru:greensight/gj/go/clients/pimclient.git`.
- Go module: `gitlab.gloria.aaanet.ru/greensight/gj/go/clients/pimclient`; Go package: `pim`.
- Работать только в этом репозитории. Не менять PIM PHP, intgateway, AutoMerch, общую HTTP-библиотеку и workspace adapters `.agents/`/`.codex/`.
- Сначала прочитать применимые AGENTS.md/CLAUDE.md и README клиента. Это ТЗ уточняет задачу и имеет приоритет над устаревшими описаниями области клиента.
- Не начинать с массового sync workspace. Git hooks уже запускали контейнеры при fetch: при необходимости чтения remote использовать `git -c core.hooksPath=/dev/null fetch origin`. Не запускать контейнеры.
- Проверить branch/HEAD/status. Не перезаписывать чужие изменения. Если рабочие файлы задачи уже изменены и их назначение неизвестно — остановиться и сообщить.
- Использовать отдельную ветку `codex/pimclient-product-imports` либо worktree по правилам окружения. Не переключать checkout другой активной сессии.
- Не делать commit/push/MR/tag/release/deploy без отдельного прямого поручения. Нужен проверяемый diff для ревью основной сессией.
- Не вызывать реальный импорт PIM. Все тесты — локальный `httptest.Server`.

## 2. Проверенный исходный уровень

На 2026-09-15 проверен `origin/main`, commit `0ec657f`, последний обнаруженный тег `v0.1.3`. Текущее API клиента содержит только `SearchSkuProducts`.

Важные файлы:

- `client.go` — Client, New и SearchSkuProducts.
- `client_test.go`, `testdata/sku_products_search.json` — существующие контрактные тесты.
- `api/v1/openapi.yaml` — корневая спецификация.
- `api/v1/paths/sku_products.yaml`, `api/v1/components/schemas/sku_products.yaml` — образец split-структуры.
- `api/v1/oapi-codegen.yaml` — генерация DTO; методы клиента пишутся вручную.
- `api/v1/bundle/openapi.yaml`, `openapi.gen.go` — generated, руками не менять.
- `doc.go`, `Makefile`, `.redocly.yaml`, `go.mod`, `README.md`.

Если HEAD продвинулся, сравнить изменения именно этих контрактов. Не откатывать новые версии до исходного уровня этого ТЗ.

## 3. Нормативный внешний API Go-библиотеки

Добавить следующие имена и сигнатуры. Они являются договором с отдельной сессией intgateway:

```go
func (c *Client) PreloadProductImportFile(
    ctx context.Context,
    filename string,
    content []byte,
) (PreloadProductImportFileResponse, error)

func (c *Client) CreateProductImport(
    ctx context.Context,
    req CreateProductImportRequest,
) (CreateProductImportResponse, error)

func (c *Client) SearchProductImports(
    ctx context.Context, req SearchProductImportsRequest,
) (SearchProductImportsResponse, error)

const ImportTypeCategoryPosition = 1
```

Публичные DTO генерируются из OpenAPI. Обеспечить следующий Go-интерфейс полей:

```go
// Иллюстрация обязательного результата генерации, не писать эти типы вручную.
type CreateProductImportRequest struct {
    PreloadFileId int64 `json:"preload_file_id"`
    Type          int   `json:"type"`
}
type PreloadProductImportFileData struct {
    PreloadFileId int64 `json:"preload_file_id"`
}
type PreloadProductImportFileResponse struct {
    Data PreloadProductImportFileData `json:"data"`
}
type ProductImport struct {
    Id int64 `json:"id"`
}
type CreateProductImportResponse struct {
    Data ProductImport `json:"data"`
}
type ProductImportsFilter struct {
    Status []int `json:"status"`
}
type ProductImportsPagination struct {
    Type   string `json:"type"`
    Offset int    `json:"offset"`
    Limit  int    `json:"limit"`
}
type SearchProductImportsRequest struct {
    Filter     ProductImportsFilter     `json:"filter"`
    Pagination ProductImportsPagination `json:"pagination"`
}
type ProductImportSummary struct {
    Id     int64 `json:"id"`
    Status int   `json:"status"`
}
type SearchProductImportsResponse struct {
    Data []ProductImportSummary `json:"data"`
}
```

Схема — сознательный минимальный subset PIM: дополнительные поля ответов (`file`, даты, счётчики, nullable `user_id`, `meta`) разрешены и игнорируются. В create-response достаточно ID; summary для поиска выделен отдельно. Поля в показанных DTO обязательные, без omitempty. ID — integer/int64, остальные числовые поля — integer без format; Pagination.Type — string без enum (входная проверка требует offset). Не добавлять GET по ID, warnings или cancel API. Если генератор меняет spelling, использовать штатную настройку имени в исходной спецификации; не менять публичный договор молча.

## 4. Реальный HTTP-контракт PIM

### 4.1. Загрузка файла

```http
POST /api/v1/imports/products:preload-file
Content-Type: multipart/form-data; boundary=...

file: исходные байты с filename
```

Штатный ответ PIM — `201`:

```json
{"data":{"preload_file_id":2032,"file":{"url":"https://example.invalid/file.xlsx"}}}
```

Клиент извлекает только `data.preload_file_id`. Успех: 2xx + валидный JSON + ID > 0. Не принимать пустой ответ, отсутствующий `data`, null, нулевой или отрицательный ID как успех.

### 4.2. Регистрация

```http
POST /api/v1/imports/products
Content-Type: application/json

{"preload_file_id":2032,"type":1}
```

Штатный ответ PIM — `201`, минимально значимая часть:

```json
{"data":{"id":501}}
```

Успех: 2xx + валидный JSON + `data.id > 0`. Дополнительные реальные поля не мешают чтению. `id` означает регистрацию импорта, а не завершение фоновой работы.

### 4.3. Поиск импортов

```http
POST /api/v1/imports/products:search
Content-Type: application/json

{"filter":{"status":[1,2]},"pagination":{"type":"offset","offset":0,"limit":3}}
```

Штатный ответ — 200, примеры значимой части ответа:

```json
{"data":[]}
```

```json
{"data":[{"id":501,"status":1},{"id":502,"status":2},{"id":503,"status":2}]}
```

Значения статусов: NEW=1 (ожидает), IN_PROCESS=2 (обрабатывается), DONE=3, FAILED=4, CANCELLED=5. Search выполняется через DoJSON, operation `product_import_search`. Метод не создаёт и не изменяет импорт, хотя HTTP-метод POST.

Проверка аргументов: непустой Status с положительными значениями, Pagination.Type строго offset, Offset>=0, Limit>0; нарушение — KindBadRequest без HTTP-вызова. Не зашивать значения [1,2] или limit=3 в сам библиотечный метод — их задаёт gateway.

Успех: 2xx, валидный JSON, data — именно массив (пустой [] допустим; missing/null недопустимы); каждый элемент имеет положительные id/status. Ошибка структуры — KindDecode. Для отличия missing/null от [] проверить Data != nil после декодирования. Не вызывать следующие страницы и не вычислять total. Не добавлять retry/polling.

Gateway запрашивает максимум три записи и проверяет len(Data)>2. Это достаточно для порога независимо от наличия 3, 10 или 100 активных импортов. Фильтры type/user_id не передаются: учитываются все записи product_excel_imports с указанными статусами, в том числе зарегистрированные через CMS. Отдельные импорты изображений этот API не охватывает.

### 4.4. Общие правила

- `baseURL` — scheme + host, без `/api/v1`; prefix уже включён в пути. Не удваивать `/api/v1`.
- Имя файла использовать только как multipart metadata, не как путь на диске/часть URL. Пустое имя, CR/LF/NUL и пути с `/` или `\` отклонять локально.
- Клиент не валидирует XLSX и не ограничивает файл бизнес-лимитом 10 MiB: это ответственность intgateway. Передаёт байты без преобразований.
- Для пустого `content`, некорректного filename, `PreloadFileId <= 0`, `Type <= 0` возвращать typed `KindBadRequest`, без HTTP-вызова.
- Не фиксировать `type=1` внутри CreateProductImport: метод библиотечный; intgateway выбирает экспортированную константу.
- Не добавлять auth токен в PIM. Существующие options/decorators должны работать, включая X-Request-ID.
- Не добавлять retry, background goroutine, polling или очистку временного файла PIM.
- `preload_file_id` одноразовый: регистрация потребляет TempFile. Таймаут регистрации не доказывает, что импорт не создан. Клиент возвращает ошибку, не повторяет POST.
- Контекст вызывающего кода использовать во всех HTTP-запросах. Не подменять на `context.Background()`.

## 5. Multipart и общая HTTP-библиотека

Обновить зависимость `gitlab.gloria.aaanet.ru/go-pkg/gj-go-httpclient` минимум до **v0.1.2**. Проверено: v0.1.1 принудительно заменяет Content-Type на JSON; v0.1.2 сохраняет явно заданный multipart Content-Type. Если уже используется более новая совместимая версия, не понижать её.

В существующей библиотеке есть:

```go
func (c *Client) Do(ctx context.Context, op string, req *http.Request) (*http.Response, error)
```

Она применяет headers/decorators, транспортные метрики и typed transport errors. Она **не** превращает non-2xx в ошибку: это обязанность pimclient для upload.

Реализация upload:

1. `bytes.Buffer` + `multipart.NewWriter` + `CreateFormFile("file", filename)`.
2. Записать content и закрыть multipart writer до отправки. Не использовать `io.Pipe` и отдельные goroutine для файла размером порядка 10 MiB.
3. Сформировать request с `ctx`, абсолютным URL и `writer.FormDataContentType()`.
4. Выполнить через `c.hc.Do(ctx, "product_import_preload", req)`.
5. Закрыть response body на любом пути. Для успеха читать не более 64 KiB + 1, превышение — `KindDecode`; для non-2xx сохранить максимум 4 KiB в typed error.
6. Декодировать единственный JSON-документ и проверить положительный ID.

Если низкоуровневый Do не достраивает URL, добавить в `Client` нормализованный `baseURL`, не менять New signature и SearchSkuProducts.

CreateProductImport использует имеющийся `DoJSON`, operation `product_import_create`, затем проверяет `data.id > 0`. Сохранить `errors.Is` и `errors.As` совместимость.

Для non-2xx upload создать `*httpclient.Error` с Service=`pim`, Op=`product_import_preload`, StatusCode и Kind:

| HTTP | Kind |
|---|---|
| 401, 403 | KindUnauthorized |
| 404 | KindNotFound |
| 5xx | KindUpstream |
| остальные non-2xx, включая 3xx | KindBadRequest |

Для некорректного/пустого 2xx JSON или отсутствующего ID — `KindDecode`. Transport error от Do возвращать с сохранением chain.

Не дублировать реализацию транспортных метрик и не менять их общий смысл. В README отметить, что низкоуровневый Do в v0.1.2 не классифицирует HTTP status в outcome метрики; фактический результат операции получает вызывающий код.

Клиент поддерживает `WithHTTPClient`. В README и контрактных тестах показать HTTP-клиент с `CheckRedirect`, возвращающим `http.ErrUseLastResponse`: импорт нельзя автоматически пересылать по 307/308. Это обязательная настройка потребителя intgateway, не глобальное изменение поведения существующего SearchSkuProducts.

## 6. Изменяемые файлы

Создать:

- `api/v1/paths/imports.yaml` — три path item.
- `api/v1/components/schemas/imports.yaml` — DTO из раздела 3.
- `imports.go` — методы, константа, приватные upload helpers.
- `imports_test.go` — контрактные тесты.
- При необходимости `testdata/product_import_*.json` — небольшие тестовые ответы без реальных данных.

Изменить:

- `api/v1/openapi.yaml` — tag `imports` и три `$ref`.
- `client.go` — только минимальное расширение Client/New для baseURL, если необходимо.
- `go.mod`, `go.sum`, `README.md`.
- Перегенерировать `api/v1/bundle/openapi.yaml`, `openapi.gen.go`.

Не менять существующие SKU DTO и семантику SearchSkuProducts.

## 7. Обязательные тесты

Тесты проверяют wire behavior через `httptest.Server`, не только вызов mock.

| Тест | Проверка |
|---|---|
| Upload success | POST и точный path; ParseMultipartForm успешен; ровно file; имя и байты равны входу; ID=2032 |
| Header regression | Content-Type содержит multipart boundary, не application/json |
| Upload decorator | X-Request-ID из WithRequestDecorator дошёл до upstream |
| Base URL | baseURL с завершающим `/` не даёт `//api` |
| Create success | JSON строго содержит preload_file_id и type; ID=501 |
| Extra fields | реальные дополнительные поля и null user_id не мешают чтению |
| Bad success | invalid JSON, пустой body, missing/null data, missing/zero/negative ID дают ErrDecode; upload и create |
| HTTP errors | 400/422, 401/403, 404, 500 классифицируются; upload body в error <=4 KiB |
| Oversized success | upload response >64 KiB даёт ErrDecode |
| Context | отменённый/истёкший ctx возвращает ErrCanceled/ErrTimeout, причина сохранена |
| No retry | счётчик POST равен 1 при 500 и при обрыве ответа |
| Redirect | с указанным CheckRedirect target не вызван, 307/308 не дают success |
| Local input | неправильные аргументы не выполняют HTTP |
| Regression | существующие SKU tests продолжают проходить |
| Search success | точный POST path, JSON filter.status=[1,2], pagination offset/0/3; пустой массив и три результата декодируются |
| Search edge cases | data missing/null, invalid JSON, missing/nonpositive id/status дают ErrDecode; лишние поля/meta игнорируются |
| Search errors | 404/500/cancel/timeout сохраняют typed error; нет встроенного paging/polling; invalid request не вызывает HTTP |

Образец основы upload-теста:

```go
payload := []byte("test-xlsx-bytes") // клиент не проверяет содержимое XLSX
srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodPost || r.URL.Path != "/api/v1/imports/products:preload-file" {
        t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
    }
    file, header, err := r.FormFile("file")
    if err != nil { t.Errorf("multipart: %v", err); w.WriteHeader(400); return }
    defer file.Close()
    if r.MultipartForm != nil { defer r.MultipartForm.RemoveAll() }
    got, err := io.ReadAll(file)
    if err != nil || !bytes.Equal(got, payload) || header.Filename != "category.xlsx" {
        t.Errorf("payload/filename mismatch: %v", err)
    }
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(http.StatusCreated)
    _, _ = w.Write([]byte(`{"data":{"preload_file_id":2032}}`))
}))
defer srv.Close()
out, err := New(srv.URL).PreloadProductImportFile(context.Background(), "category.xlsx", payload)
if err != nil || out.Data.PreloadFileId != 2032 { t.Fatalf("out=%+v err=%v", out, err) }
```

## 8. Порядок реализации

- [ ] Зафиксировать исходный HEAD/status и прочитать перечисленные файлы.
- [ ] Обновить OpenAPI с точными именами; `make generate`; убедиться в совпадении DTO с разделом 3.
- [ ] Написать upload/create/search тесты; запустить целевые тесты и зафиксировать RED, отсутствие метода — допустимый первый RED.
- [ ] Обновить HTTP dependency и реализовать три метода с typed errors.
- [ ] Добиться GREEN обязательных тестов, затем проверить существующий API.
- [ ] Обновить README: три вызова, контекст, redirects, нет retries, registration != completion; search нужен для проверки текущей нагрузки gateway, не гарантирует атомарность search→create.
- [ ] Выполнить проверки ниже и подготовить отчёт. Не публиковать библиотеку до ревью.

Команды из корня pimclient:

```sh
make generate
make lint
go test ./... -count=1
go test -race ./...
go vet ./...
go build ./...
git diff --check
```

Для воспроизводимости генерации сравнить SHA256 generated-файлов до и после повторного `make generate`; хеши должны совпасть. Не требовать пустой diff относительно исходного HEAD: generated-файлы закономерно изменены этой задачей.

## 9. Условия остановки

Остановиться с точным описанием причины, если нельзя получить приватную зависимость, генератор несовместим с требуемыми DTO, текущий upstream-контракт отличается по смыслу или нужно менять другой репозиторий. Не обходить проблему копированием кода зависимостей, постоянным local replace или собственным альтернативным клиентом в intgateway.

Невыполненные тесты указывать как невыполненные, не как пройденные. В конце не объявлять библиотеку опубликованной: задача завершается diff и отчётом.

## 10. Отчёт для ревью и следующей сессии

Выдать в финале:

1. Repository path, branch, base commit, HEAD; есть ли незафиксированные изменения.
2. Изменённые файлы и публичные сигнатуры, включая точные Go-имена DTO/полей.
3. Версия gj-go-httpclient, подтверждение multipart Content-Type и отсутствия retry.
4. Команды проверок, результаты, не выполненные проверки и причины.
5. Что не входит в изменение: PIM, intgateway, реальные импорты, публикация тега.
6. Состояние handoff: «готово к ревью» либо конкретный blocker. Подтвердить наличие всех трёх методов редакции 3. Отдельная сессия intgateway должна получить одобренную и опубликованную версию клиента после ревью.

## 11. Локальные первоисточники

Пути от `$WORKSPACE`:

- `platform/ensi/apps/catalog/pim/public/api-docs/v1/imports/paths.yaml` — ProductsImportPreloadFile, ProductsImportsCreate, ProductsImportsSearch.
- `platform/ensi/apps/catalog/pim/public/api-docs/v1/imports/schemas/products.yaml` — create request/response.
- `platform/ensi/apps/catalog/pim/public/api-docs/v1/common_schemas.yaml` — PreloadFile.
- `platform/ensi/apps/catalog/pim/app/Http/ApiV1/Modules/Imports/Requests/CreateProductImportRequest.php` — обязательные поля.
- `platform/ensi/apps/catalog/pim/app/Http/ApiV1/Support/Requests/PreloadFileRequest.php` — 10 MiB upstream limit.
- `platform-new/gj-go-httpclient/httpclient.go`, `errors.go` — низкоуровневый Do и классификация ошибок.
