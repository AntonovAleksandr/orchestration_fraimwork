# ТЗ B, редакция 3: intgateway — приём Excel для импорта позиций категорий PIM

> **Согласованная редакция от 2026-09-16.** PIM не меняем, intgateway остаётся без БД. После проверки Excel gateway запрашивает активные импорты PIM. При 0–2 допускает загрузку и регистрацию; при 3 и более возвращает 409. Это проверка текущей нагрузки, не дедупликация и не распределённая блокировка.

> Для исполнителя: используй `superpowers:executing-plans`, выполняй шаги последовательно. Это самостоятельное ТЗ и план реализации; история обсуждения не требуется. Реализация разрешена в указанном репозитории после выполнения входного условия по pimclient. Не перепроектировать согласованный MVP и не просить повторно подтвердить его границы.

**Цель:** дать интеграционный HTTP-метод, который принимает секретный токен и XLSX, проверяет файл, передаёт его в PIM и подтверждает регистрацию фонового импорта.

**Архитектура:** intgateway выполняет три последовательные HTTP-операции PIM: поиск активных импортов, загрузку файла и регистрацию в рамках входящего запроса. Асинхронная обработка Excel, изменения связей и аудит остаются в PIM. Собственных очереди, БД и фонового worker в intgateway нет.

**Стек:** Go 1.26.2, net/http + chi, OpenAPI-first/types-only oapi-codegen, pimclient, gj-go-httpclient, Excelize v2.

**Spec:** этот документ содержит полный нормативный контракт, интерфейсы зависимостей и план. Читать историю другой сессии не нужно.

## 1. Область работ и явные решения владельца

- `$WORKSPACE` — корень GJ-Ecommerce. Репозиторий задачи: `$WORKSPACE/platform-new/intgateway`.
- Remote: `git@gitlab.gloria.aaanet.ru:greensight/gj/go/intgateway.git`.
- Module: `gitlab.gloria.aaanet.ru/greensight/gj/go/intgateway`.
- Работать только в intgateway. **Не менять AutoMerch, PIM PHP, pimclient, audit, CMS, общую HTTP-библиотеку или инфраструктурные репозитории.**
- AutoMerch — другая команда. Расчёт, расписание, публикации, интерфейс, подтверждения и дальнейшие действия отправителя не входят в задачу.
- Владелец явно выбрал **intgateway → PIM**. Предлагать AutoMerch → PIM напрямую запрещено: это отменённый вариант.
- Старый ADR-0008 ограничивает intgateway ролью BFF. В этом задании разрешено узкое исключение: интеграционный endpoint импорта. Оформить новый ADR с пометкой, что он частично supersedes ограничение ADR-0008 только для этого endpoint. Не превращать gateway в универсальный proxy.
- На MVP общий секретный токен, без пользователей, ролей, customer JWT и login-flow.
- Автор аудита **«Система»** принят владельцем. Отдельного автора «Automerch» и передачу пользовательского initial-event через очередь сейчас не реализовывать.
- Ответ `202 Accepted` означает: PIM подтвердил регистрацию импорта. Это не подтверждение обновления каталога и не завершение автомерча.
- Не добавлять status endpoint, polling, callback, идемпотентность/кеш отпечатков, persistent journal, retry, очередь, БД/Redis, mutex или блокировки категорий. Единственный новый предохранитель — проверка числа активных импортов по разделу 6.

### Правила рабочей сессии

Прочитать AGENTS.md/CLAUDE.md, `README.md`, `docs/configuration.md`, `docs/architecture/code-organization-contract.md` и относящиеся ADR. Выполнить status/HEAD/branch до изменений. В исходном checkout были посторонние изменения `go.mod`/`go.sum`: не присваивать и не перезаписывать их. Предпочесть отдельный worktree от согласованной базы и ветку `codex/category-position-imports`.

Не запускать массовый sync. Для нужного fetch использовать `git -c core.hooksPath=/dev/null fetch origin`: ранее git hooks запускали контейнеры. Не запускать реальные импорты и не менять окружение самостоятельно.

Не делать commit/push/MR/tag/deploy без отдельного поручения. Завершить проверяемым diff и отчётом для ревью основной сессией. Если актуальная структура изменилась, адаптировать пути к ней без рефакторинга несвязанных функций.

## 2. Входное условие: готовый pimclient

До реализации PIM-адаптера должен быть **отревьюен и опубликован** клиент из отдельного задания A. Владелец передаёт одобренную версию/тег; проверить, что эта версия содержит приведённые ниже сигнатуры. Не выбирать произвольный latest и не придумывать номер релиза.

Если одобренной версии нет, завершить сообщение конкретным blocker: «нужна опубликованная одобренная версия pimclient с SearchProductImports, PreloadProductImportFile и CreateProductImport». Не встраивать HTTP-копию клиента в gateway и не делать постоянный local replace. Отсутствие тега не означает разрешения дорабатывать другой репозиторий.

Dependency module: `gitlab.gloria.aaanet.ru/greensight/gj/go/clients/pimclient`, package alias `pim`:

```go
func New(baseURL string, opts ...httpclient.Option) *Client

func (c *Client) PreloadProductImportFile(
    ctx context.Context, filename string, content []byte,
) (PreloadProductImportFileResponse, error)

func (c *Client) CreateProductImport(
    ctx context.Context, req CreateProductImportRequest,
) (CreateProductImportResponse, error)

func (c *Client) SearchProductImports(
    ctx context.Context, req SearchProductImportsRequest,
) (SearchProductImportsResponse, error)

const ImportTypeCategoryPosition = 1

// Generated DTO fields, не объявлять копии этих типов в gateway:
// CreateProductImportRequest.PreloadFileId int64
// CreateProductImportRequest.Type int
// PreloadProductImportFileResponse.Data.PreloadFileId int64
// CreateProductImportResponse.Data.Id int64
// SearchProductImportsRequest.Filter ProductImportsFilter
// ProductImportsFilter.Status []int
// SearchProductImportsRequest.Pagination ProductImportsPagination
// ProductImportsPagination.Type string, Offset int, Limit int
// SearchProductImportsResponse.Data []ProductImportSummary
// ProductImportSummary.Id int64, Status int
```

Три метода возвращают ошибки, совместимые с `errors.Is`/`errors.As` из gj-go-httpclient: ErrBadRequest, ErrUnauthorized, ErrNotFound, ErrUpstream, ErrTimeout, ErrCanceled, ErrNetwork, ErrDecode. Требуется gj-go-httpclient **не ниже v0.1.2**: v0.1.1 портит multipart Content-Type.

## 3. Публичный HTTP-контракт gateway

```http
POST /api/v1/catalog/category-position-imports
X-Integration-Token: <секрет из конфигурации>
Content-Type: multipart/form-data; boundary=...

file: category.xlsx
```

- Ровно одна файловая part с именем `file` и непустым filename.
- Других файлов и текстовых полей нет. `type`, URL файла, user_id и токен в body/query не принимаются.
- Токен принимается только в заголовке `X-Integration-Token`.
- Клиентский MIME самой part не является доказательством формата файла и не должен быть единственной проверкой. Допустим, например, `application/octet-stream` для корректного XLSX.
- Имя файла должно иметь расширение `.xlsx` без учёта регистра; не содержать CR, LF, NUL, `/`, `\`. Имя не используется как локальный путь.
- Для проверки исходного filename читать параметр `filename` из Content-Disposition part через mime.ParseMediaType: Go может уже удалить путь в FileHeader.Filename. Не считать нормализованный basename доказательством корректности исходного имени.
- Общий HTTP body ограничен **11 MiB** с учётом multipart overhead. Сам файл — **10 MiB**, то есть 10 485 760 байт, включительно.

Успех — только после получения положительного ID зарегистрированного импорта от PIM:

```http
HTTP/1.1 202 Accepted
Content-Type: application/json
X-Request-ID: <request-id>

{"import_id":501,"status":"accepted","message":"Файл принят в асинхронную обработку"}
```

Без `data` envelope: сохранить ровно эту структуру. `import_id` — integer/int64, >0. `status` — единственное значение `accepted`. Не возвращать статус PIM как признак завершения. Не добавлять Location на несуществующий endpoint статуса.

OpenAPI tag: `catalog-imports`; operationId: `createCategoryPositionImport`. Success schema: `CategoryPositionImportAccepted`. Security scheme: `IntegrationToken`, `type: apiKey`, `in: header`, `name: X-Integration-Token`. Endpoint не наследует customer Bearer security.

## 4. Контракт XLSX v1 и валидация

Это **структурная проверка до отправки**. Проверка существования товара/категории, изменений состава категории и конфликтов позиций остаётся в PIM.

### 4.1. Книга

- Только читаемый, незашифрованный XLSX. CSV, старый XLS, произвольный ZIP, повреждённый архив и файл с паролем отклоняются.
- Ровно один worksheet, имя произвольное. Дополнительные, в том числе скрытые, листы отклоняются: gateway не должен проверить один лист, а передать PIM другие непроверенные данные.
- Строка 1 — заголовки. Данные начинаются со строки 2. Минимум одна строка данных.
- A1:D1 должны **точно**, без trim/case-fold, равняться:

```text
Артикул СС | Код категории | Позиция товара | Исключен
```

`СС` — кириллические буквы. Заголовки — строковые ячейки, не формулы.

- Данные занимают A:D. Непустые значения или формулы правее D запрещены, пустое форматирование не считается данными.
- Формулы, Excel error cells и merged cells в используемой таблице запрещены. Не вычислять формулы и не доверять их cached values.
- Полностью пустые хвостовые строки игнорируются. Пустая строка между строками данных отклоняется; частично пустая строка отклоняется.
- Максимум **100 000 строк данных**. Это технический лимит нового endpoint, его явно включить в API-документацию. Нельзя обойти лимит огромным sparse row index.
- Не требовать единственной категории в файле, сортировки строк, уникальности позиций/товаров или шага 10. Не добавлять бизнес-ограничений сверх перечисленных.

### 4.2. Ячейки

| Колонка | Допускается | Отклоняется |
|---|---|---|
| A: Артикул СС | Непустая строковая ячейка с `products.vendor_code` PIM; leading zeros сохраняются | Numeric/bool/error/formula; пустая/пробельная строка; пробелы по краям |
| B: Код категории | Положительное целое 1..2147483647; числовая ячейка с целым значением либо строка десятичных цифр без пробелов | 0, отрицательное, дробь, дата, bool, формула, научная запись в строковой ячейке |
| C: Позиция товара | Те же правила положительного целого 1..2147483647 | Те же нарушения; не ограничивать значением 999999 |
| D: Исключен | Настоящее Excel boolean true/false; либо точная строка `да`, `нет`, `ЛОЖЬ` | Пустое, numeric 0/1, строки `true`, `false`, `ИСТИНА`, `ДА`, формулы и остальные значения |

Правило D намеренно следует реальному PIM: он считает true только boolean true или точную строку `да`. Строка `ЛОЖЬ` из существующего формата корректно даёт false. Нельзя «улучшить» проверку до case-insensitive true и затем передать исходный файл, который PIM истолкует иначе.

Для B/C числовые ячейки проверять по raw значению и отсутствию дробной части, finite и диапазону; не через округление. Для строк — `^[0-9]+$` и ParseInt с проверкой диапазона. Чтобы не трактовать дату как serial number, числовые B/C принимаются только с number format General (NumFmt=0) либо целочисленным `0` (NumFmt=1), без CustomNumFmt; font/fill/border не ограничиваются. Excel date cells и остальные number formats отклоняются. Так исполнитель не должен писать собственный распознаватель произвольных Excel date formats.

Пример допустимых строк (A обязательно text, B/C integer, D text):

```text
GAS011429-1 | 123 | 1000 | ЛОЖЬ
GAS011430-1 | 123 | 1010 | ЛОЖЬ
000123     | 456 | 1000000 | нет
```

### 4.3. Безопасное чтение и неизменность

- Использовать `github.com/xuri/excelize/v2`; базовая согласованная версия **v2.9.1**, уже применённая в генераторе совместимого формата. Если в gateway уже есть более новая версия, не понижать её. Не писать собственный XLSX parser.
- Ограничить распакованный размер через `excelize.Options{UnzipSizeLimit: 64 << 20, UnzipXMLSizeLimit: 8 << 20}`. `UnzipXMLSizeLimit` — порог перехода на temp storage, а не общий лимит памяти. Официальная документация: [Excelize Options](https://xuri.me/excelize/en/workbook.html).
- Перед парсингом multipart поставить `http.MaxBytesReader` на 11 MiB. Читать файл ограниченным reader до 10 MiB + 1, а не доверять только FileHeader.Size/Content-Length.
- Multipart допускается разбирать с memory budget 1 MiB. Удалять временные файлы `MultipartForm.RemoveAll`, закрывать файлы, workbook и row iterator на всех путях.
- Проверять фактический тип ячейки, raw value и формулы. Одного GetRows с отформатированными строками недостаточно для различения boolean/string/numeric.
- Проверять отмену ctx при обходе строк. Избегать обхода миллионов пустых ячеек по непроверенному dimension.
- Остановиться на первой ошибке и вернуть её координату, без содержимого ячейки. Пример: `Строка 3, колонка C: ожидается положительное целое число`.
- После валидации отправить в PIM **те же байты**, а не заново сохранённую книгу. Тест должен сравнить SHA256/bytes входа и multipart PIM.

## 5. Секретный токен и конфигурация

Добавить конфигурацию:

| Env | Значение по умолчанию | Правило |
|---|---|---|
| `CATEGORY_POSITION_IMPORT_ENABLED` | `false` | При false endpoint отвечает 404 и не выполняет работу |
| `CATEGORY_POSITION_IMPORT_TOKEN` | пусто | При enabled обязателен, 32..256 ASCII-символов без whitespace; только env/secret injection |
| `CATALOG_PIM_SERVICE_HOST` | пусто | При enabled обязателен: http(s) scheme + host, без credentials/query/fragment и path кроме `/` |
| `PIM_IMPORT_TIMEOUT_MS` | `30000` | Общий бюджет трёх последовательных вызовов PIM; 1..45000, некорректная настройка — startup error |
| `HTTP_READ_TIMEOUT_SECONDS` | `15` | Существующий server timeout сделать конфигурируемым; при enabled минимум 60 |
| `HTTP_WRITE_TIMEOUT_SECONDS` | `15` | Существующий server timeout сделать конфигурируемым; при enabled минимум 90 |

При enabled=false прежние deployments сохраняют defaults и не требуют PIM/token. При enabled=true ошибочная/пустая конфигурация останавливает запуск; **никакого auth passthrough**. Не брать существующий `UPSTREAM_TIMEOUT_MS=800` для импорта.

Проверка запроса: feature enabled → токен → разбор body → XLSX → PIM. Неверный/отсутствующий/повторяющийся token header — 401 до чтения файла и без обращения в PIM. Сравнивать секрет constant-time; пример:

```go
expectedHash := sha256.Sum256([]byte(configuredToken))
actualHash := sha256.Sum256([]byte(requestToken))
valid := subtle.ConstantTimeCompare(expectedHash[:], actualHash[:]) == 1
```

Дополнительно отклонить несколько значений header и длину >256. Не принимать токен из Authorization/query/body. Не логировать token, его хеш, body или содержимое Excel.

Не менять существующую customer auth. Даже если CUSTOMER_AUTH_PUBLIC_KEY не настроен и старые guards passthrough, новый endpoint всё равно требует правильный IntegrationToken.

Настройка PIM-клиента при wiring:

```go
httpclient.WithHTTPClient(&http.Client{
    CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
        return http.ErrUseLastResponse
    },
})
```

Не пересылать incoming IntegrationToken, Authorization, cookies, X-Customer-Id и X-Initial-Event в PIM. Передавать только штатные transport headers и X-Request-ID из gateway context. Токен защищает внешний метод и не является учётной записью администратора PIM.

## 6. Последовательность и ошибки

Handler использует request ctx с общим deadline **60 секунд** на локальную обработку и downstream. PIM-адаптер создаёт от него один дочерний ctx с PIM_IMPORT_TIMEOUT_MS на **три** вызова суммарно. Не выдавать каждому вызову полный новый бюджет.

```text
validate upload + workbook
    → SearchProductImports(ctx, filter.status=[1,2], pagination=offset/0/3)
    → если len(data)>2: 409 pim_imports_busy, без preload/create
    → иначе PreloadProductImportFile(ctx, filename, originalBytes)
    → проверить preload_file_id > 0
    → CreateProductImport(ctx, {PreloadFileId: id, Type: ImportTypeCategoryPosition})
    → проверить import_id > 0
    → 202
```

Ни одного PIM-вызова до полной проверки файла. Search выполняется ровно один раз после валидации и перед preload. При неуспешном search не вызывать preload/create. Не вызывать create, если preload вернул ошибку. Не ждать очереди PIM, не спрашивать отдельный статус/предупреждения и не проверять каталог после create.

### Проверка нагрузки: точная семантика

```json
{"filter":{"status":[1,2]},"pagination":{"type":"offset","offset":0,"limit":3}}
```

- Endpoint PIM: `POST /api/v1/imports/products:search`.
- Активными для этого правила считаются записи product_excel_imports со status=1 (NEW, ожидает) или status=2 (IN_PROCESS).
- Учитывать все типы и всех инициаторов, включая CMS: без filter.type/user_id. Отдельная таблица импорта изображений не входит в этот API.
- Достаточно получить первые три записи. Не запрашивать весь журнал, total/count или следующие страницы.
- 0, 1 или **2** результата → продолжить. **3 и больше** → HTTP 409, `error=pim_imports_busy`, `message=В PIM уже больше двух активных импортов. Повторите запрос позже.`
- В библиотечном поиске data missing/null — ошибка, а не пустой список. На стороне адаптера дополнительно проверить, что возвращённые status только 1/2 и ID не повторяются; неожиданный ответ — 502 pim_unavailable без записи в PIM.
- Таймаут search → 504 pim_timeout; любая другая ошибка search → 502 pim_unavailable. Не подменять отказ чтения нулём активных импортов.
- Не менять условие на >=2: при двух активных новый запрос разрешён и может стать третьим.
- Это **проверка по наблюдаемому списку**, а не строгий максимум «три одновременно». Между search и create другие запросы/реплики/CMS могут добавить импорты; проверка неатомарна. Сами статусы PIM также не являются доказательством числа реально работающих workers: FAILED может выставляться до фактической остановки.
- Не заявлять защиту от дублей: повтор одного Excel после завершения первого импорта создаст новый импорт. Это принятое ограничение MVP. Не компенсировать его скрытым хранилищем, изменением PIM или расширением контракта AutoMerch.


Ошибки сохраняют существующий gateway envelope:

```json
{"error":"invalid_excel","message":"Строка 3, колонка C: ожидается положительное целое число"}
```

| Ситуация | HTTP | error |
|---|---|---|
| Feature disabled | 404 | `not_found` |
| Token missing/invalid/duplicate | 401 | `invalid_integration_token` |
| Не multipart/form-data | 415 | `unsupported_media_type` |
| Malformed multipart, file missing/duplicate, лишние parts, пустой файл, небезопасное filename | 400 | `invalid_upload` |
| Расширение не .xlsx | 415 | `unsupported_file_type` |
| Body >11 MiB или file >10 MiB | 413 | `file_too_large` |
| Корруптная/зашифрованная книга, структура/ячейки не по контракту, превышение rows/unzip limit | 422 | `invalid_excel` |
| Активных импортов по search больше 2 | 409 | `pim_imports_busy` |
| Search timeout | 504 | `pim_timeout` |
| Search network/5xx/3xx/decode/4xx, неожиданные status/duplicate IDs | 502 | `pim_unavailable` |
| Preload timeout | 504 | `pim_timeout` |
| Preload network/5xx/3xx/decode/4xx, включая upstream 401 | 502 | `pim_unavailable` |
| Create получил явный 4xx | 502 | `pim_rejected` |
| Create timeout | 504 | `pim_registration_unknown` |
| Create network/5xx/3xx/decode либо невалидный ID | 502 | `pim_registration_unknown` |
| Локальная неожиданная ошибка | 500 | `internal` |

При create timeout/network/5xx/decode импорт **мог быть зарегистрирован**. Сообщение пользователю: `Не удалось подтвердить регистрацию импорта. Проверьте историю импортов PIM перед повторной отправкой.` Не выдавать 202, не повторять автоматически, не писать «импорт не создан».

При отмене входящего ctx прекратить работу, не начинать следующий вызов PIM (search/preload/create). Если клиент уже отключился, не пытаться выдать ему успешный ответ; записать cancel с текущим stage. Если отмена/ошибка случилась во время create, результат регистрации считать неизвестным.

Не включать raw PIM error body/адреса/stack trace в HTTP message. X-Request-ID остаётся в заголовке ответа через существующий middleware.

## 7. Внутренняя структура

Новый domain: `internal/domains/catalogimports`, generated DTO: `catalogimports/apiv1`.

Определить consumer-owned порт и независимые от pimclient типы:

```go
type ImportFile struct {
    Filename string
    Content  []byte
}
type ImportRegistration struct {
    ImportID      int64
    PreloadFileID int64 // внутреннее поле для логов, не в HTTP response
}
type ImportRegistrar interface {
    Register(ctx context.Context, file ImportFile) (ImportRegistration, error)
}
```

Домен содержит handler/token middleware/Excel validator/service и domain marker errors. Он не импортирует опубликованный pimclient и `internal/app`, `internal/adapters`, `platform/config`, соседние домены. Excelize допустим непосредственно в validator как библиотека формата.

Адаптер `internal/adapters/catalogimports/pim.go` вызывает **три метода** pimclient в порядке search → preload → create, знает общий downstream budget, переводит typed upstream errors в domain errors, сохраняет stage и preload ID для логов. Domain service не оперирует PIM DTO.

Предлагаемые domain errors: `ErrInvalidExcel`, `ErrPIMImportsBusy`, `ErrPIMUnavailable`, `ErrPIMRejected`, `ErrPIMTimeout`, `ErrRegistrationUnknown`, `ErrCanceled`. Для ErrRegistrationUnknown сохранить признак timeout, чтобы handler различал 502/504; не угадывать это по тексту ошибки. ValidationError хранит безопасную координату/причину. Ошибка адаптера может содержать stage/preload ID/cause; не выводить её целиком в HTTP.

Composition root: `internal/app/wire/catalogimports.go` создаёт клиент с metrics/decorator/no-redirect, адаптер, service, handler. Роут монтировать **отдельно от OptionalAuth-группы basket/recommendations** с собственной token-проверкой.

### Файлы

Создать:

- `api/v1/paths/catalog_imports.yaml`.
- `api/v1/components/schemas/catalog_imports.yaml`.
- `api/v1/oapi-codegen-catalogimports.yaml`.
- `internal/domains/catalogimports/{doc.go,types.go,service.go,handler.go,routes.go,middleware.go,validator.go}`.
- `internal/domains/catalogimports/{service_test.go,handler_test.go,middleware_test.go,validator_test.go,boundary_test.go}`.
- Generated `internal/domains/catalogimports/apiv1/openapi.gen.go`.
- `internal/adapters/catalogimports/pim.go`, `pim_test.go`.
- `internal/app/wire/catalogimports.go`.
- `docs/architecture/adr/0015-category-position-import-ingress.md` — если номер занят, следующий свободный, указать в отчёте.
- `docs/category-position-import-api.md` — самостоятельная документация контракта для команды-потребителя, включая полный Excel-контракт.

Изменить:

- `api/v1/openapi.yaml` — tag, path ref, apiKey security scheme, краткое расширение описания сервиса; bundle только генерацией.
- `internal/platform/config/config.go`, `config_test.go`.
- `internal/platform/transport/routes.go`, `routes_test.go`, `server.go` и узкий тест его timeout-конфигурации.
- `internal/app/container.go`, `app.go`.
- `go.mod`, `go.sum`, `README.md`, `CLAUDE.md`, `docs/configuration.md`, `docs/runbook.md`.

CLAUDE.md/README обновить точечно: отметить разрешённый интеграционный endpoint и новый ADR. Не переписывать всю архитектуру и не редактировать `.agents/`/`.codex/`.

## 8. Логи, CMS и audit

Записывать результат запроса структурированно: `request_id`, operation=`category_position_import`, stage=`validation|active_check|preload|create|accepted`, `file_size`, `row_count`, `active_imports_observed` (0..3, значение 3 означает «не меньше трёх»), `preload_file_id` после preload, `import_id` после create, outcome. ID и filename не использовать как labels Prometheus; filename в логах не нужен.

Использовать gj-go-logger и существующий способ request-scoped logging. Для связи ошибок adapter→handler передавать структурированные поля, не разбирать error string.

CMS читает запись импорта PIM; пользовательский `user_id` будет null. Аудит CategoryProductLink поддерживает автора `system` и отображает «Система». Это не нужно реализовывать заново. Путь audit.log→ES зависит от окружения; unit tests gateway не доказывают доставку в audit.

Техническая приёмка «виден в CMS и автор Система» проводится отдельно на стенде после ревью. Исполнитель не должен сам запускать этот реальный импорт.

## 9. Тесты и критерии приёмки

Fixtures генерировать Excelize в тестах из синтетических данных. Не вызывать сервис AutoMerch и не брать реальные товарные выгрузки. Отдельный внешний пример файла потребителю можно добавить только как синтетическую fixture с описанными колонками.

### 9.1. Validator

- Валидная книга: text артикулы, integer category/sort, `ЛОЖЬ`; принят файл с несколькими категориями.
- Артикул `000123` остаётся строкой; numeric артикул отвергается.
- Все допустимые формы D из таблицы принимаются; `ДА`, `ИСТИНА`, string `true` и numeric 1 отвергаются.
- Missing/wrong headers, пустая книга, extra sheet, extra nonempty column, merged cells, formulas (включая cached value), corrupted/encrypted input отклоняются.
- Numeric integral B/C и digit strings принимаются; дроби, ноль, отрицательное, overflow, bool/date отклоняются. Значение sort=1000000 принимается.
- Interior blank row и partially blank row отклоняются; trailing formatting-only rows не считаются данными.
- Oversized row count и unzip size дают контролируемую ошибку; для быстрых tests helper может принимать меньший лимит, production defaults остаются фиксированными.
- Проверка не меняет input bytes. Закрываются workbook/iterator/temp files.

### 9.2. HTTP и service

- Без токена, с неправильным токеном, двумя значениями header: 401, тело не читается, validator/PIM не вызваны. Использовать reader-spy, который сигнализирует о Read.
- Customer JWT не заменяет integration token; пустая конфигурация старого customer auth не открывает новый метод.
- Feature disabled: 404. Enabled с пустым token/PIM URL — config validation error.
- Bad multipart, missing/duplicate/extra parts, empty file, неподдерживаемое расширение, wrong request MIME дают точные статусы из таблицы.
- Пределы 10 MiB файла и 11 MiB body проверяются и при отсутствующем Content-Length. Не доверять FileHeader.Size.
- Invalid XLSX: 422 и **ноль** upstream calls.
- Happy path: ровно search, затем preload, затем create(type=1), response 202 с правильным import_id и без утверждения о завершении.
- Search с 0/1/2 записями разрешает работу; с 3 записями даёт 409/pim_imports_busy и ноль preload/create. Порог >2, не >=2.
- Search failure: preload/create не вызываются; empty data=[] разрешено, missing/null/неожиданные статусы не разрешены.
- Preload failure: create не вызывается. Create failure: 202 не возвращается.
- Token и входящий X-Initial-Event/X-Customer-Id/Authorization не дошли до upstream.
- Существующие basket/recommendations route/auth tests остаются зелёными.

Основа fake для domain service tests:

```go
type registrarFunc func(context.Context, ImportFile) (ImportRegistration, error)
func (f registrarFunc) Register(ctx context.Context, in ImportFile) (ImportRegistration, error) {
    return f(ctx, in)
}
```

### 9.3. Адаптер + реальный pimclient + httptest PIM

Это обязательные интеграционные тесты без настоящего PIM:

1. Сначала upstream получает POST search со status=[1,2], offset=0, limit=3, без type/user_id; при 0/1/2 ответах получает оригинальные XLSX bytes в multipart и затем JSON `{"preload_file_id":2032,"type":1}`. Headers имеют правильный Content-Type на всех трёх шагах.
2. X-Request-ID одинаков для всех трёх запросов. Metadata IntegrationToken не передаётся.
3. Preload ID и import ID положительные; повреждённый/пустой response не даёт accepted.
4. Таймаут preload даёт 504/pim_timeout; таймаут create — 504/pim_registration_unknown.
5. Create 500, broken JSON и обрыв соединения дают 502/pim_registration_unknown. Число create requests = 1.
6. Create 4xx даёт 502/pim_rejected, upstream 401 не превращается в клиентский 401.
7. 307/308 не вызывают redirect target.
8. Search и preload расходуют общий PIM budget, последующие вызовы получают только остаток; отменённый ctx не запускает следующий вызов.
9. Registration ID в JSON ответа совпадает с ID upstream и логируется вместе с request_id.
10. При трёх найденных импортах только один search, ноль preload/create, HTTP 409. Не обходить следующий page.
11. Search timeout/500/invalid JSON/missing data дают отказ без preload/create; считать ошибки поиска нулевой загрузкой запрещено.

Для искусственных задержек применять короткие явно переданные timeout в tests, не ждать production 30/60 секунд. Race tests не должны зависеть от случайного sleep порядка goroutine; использовать channels/controlled server.

### 9.4. Контрактные проверки

- Root OpenAPI содержит path, tag и IntegrationToken scheme; операция требует security, ровно file, описывает лимиты, 409/pim_imports_busy и неатомарный порог >2.
- Generated DTO строятся из spec; повторная генерация даёт те же хеши generated-файлов.
- Boundary test нового домена повторяет запреты существующего `internal/domains/basket/boundary_test.go` с self-prefix catalogimports.
- Config tests подтверждают defaults 15/15 при disabled и требование 60/90 при enabled; timeout-значения реально применены к http.Server.

## 10. Порядок выполнения

- [ ] Проверить входное условие по версии pimclient и чистую изолированную рабочую область.
- [ ] Прочитать существующие domain/wire/router/config patterns. Добавить ADR с узким исключением для integration endpoint.
- [ ] Описать API/DTO/security/errors/Excel contract; `make generate`.
- [ ] Реализовать validator через RED→GREEN по таблице, без upstream.
- [ ] Реализовать token middleware и HTTP parsing через RED→GREEN; проверить fail-closed и размер.
- [ ] Реализовать порт/service/PIM adapter через RED→GREEN, используя опубликованный pimclient.
- [ ] Подключить wire/router/config, проверить остальные endpoints и server timeouts.
- [ ] Добавить документацию потребителю и runbook с настройками/ограничениями/неизвестным результатом при timeout.
- [ ] Выполнить полные проверки; подготовить отчёт. Не публиковать и не деплоить до ревью.

Команды из корня intgateway:

```sh
make generate
make lint
go test ./... -count=1
go test -race ./...
go vet ./...
go build ./...
git diff --check
```

Сравнить SHA256 generated-файлов до и после повторного `make generate`: должны совпасть. Проверки новой функциональности должны быть выполнены, старые failures не скрывать. Если build/test останавливается из-за зависимостей/окружения, точно записать команду и ошибку, не объявлять GREEN.

## 11. Документация запуска и ограничения

В `docs/runbook.md` включить конфигурацию для включения endpoint: enabled=true, секрет через штатное secret injection, CATALOG_PIM_SERVICE_HOST, PIM_IMPORT_TIMEOUT_MS=30000, HTTP_READ_TIMEOUT_SECONDS=60, HTTP_WRITE_TIMEOUT_SECONDS=90. Не коммитить реальный секрет.

Инфраструктурные prerequisites описать, но не менять самостоятельно: gateway имеет сетевой доступ к PIM; ingress принимает body >=11 MiB и допускает ответ >=90 секунд; доступен writable temp directory для multipart/Excelize. Не объявлять окружение готовым без проверки владельцем.

Документация потребителю должна объяснять:

- 202 подтверждает регистрацию, а не завершение/успех всех строк;
- результат обработки можно смотреть в существующей CMS;
- при 3 и более активных product imports запрос отклоняется с 409; при 0–2 разрешён; учитываются все типы/инициаторы;
- проверка неатомарна и не гарантирует строгого предела параллелизма;
- повторная отправка при прохождении проверки создаёт новый импорт; идемпотентности нет;
- при неопределённом результате create сначала проверить историю импортов PIM;
- импорт использует стандартную семантику PIM: создаёт недостающие связи, не удаляет отсутствующие в Excel, может сбрасывать чужую занятую позицию на 1000000, exclude работает при default sort. Gateway этого поведения не меняет;
- весь контракт файла из раздела 4 является обязанностью отправителя; payload не пересохраняется.

## 12. Условия остановки и отчёт

Остановиться, если нет одобренного опубликованного pimclient, требуемые методы/DTO отличаются, нужен PHP patch PIM, нет способа выполнить генерацию/получить dependencies или обнаружен конфликт с чужими изменениями. Не расширять scope в обход blocker.

Финальный отчёт для ревью:

1. Repository path, branch, base commit, HEAD и состояние working tree.
2. Изменённые файлы, принятый ADR, точный HTTP-контракт.
3. Реальная версия pimclient/gj-go-httpclient/Excelize; никаких выдуманных опубликованных тегов.
4. Краткая матрица tests: validator, auth, multipart, порядок search→preload→create и граница 2/3, timeout/unknown, no retry, byte preservation, regressions.
5. Все проверочные команды и результаты; не выполненные проверки/причины.
6. Подтверждение: PIM/AutoMerch/CMS/audit не менялись; live import/deploy не выполнялись; очередь/БД/status API не добавлены; новый search используется только внутри проверки нагрузки.
7. Осталось для владельца после ревью: настройки окружения и контрольный стендовый импорт с проверкой CMS/audit. Не выдавать это за уже выполненную приёмку.

## 13. Первоисточники для точечной сверки

Пути от `$WORKSPACE`:

- `platform-new/intgateway/internal/domains/basket/` — domain layout и boundary test.
- `platform-new/intgateway/internal/app/wire/basket.go` — пример wiring/adapters/headers.
- `platform-new/intgateway/internal/platform/transport/{routes.go,server.go}` — auth groups и реальные server timeouts.
- `platform-new/intgateway/internal/platform/config/config.go` — upstream timeout=800ms и существующие env patterns.
- `platform/ensi/apps/catalog/pim/app/Domain/Imports/ExcelReaders/CategoryPositionReader.php` — колонки, точное сравнение exclude и семантика позиций.
- `platform/ensi/apps/catalog/pim/app/Domain/Support/Casts/SortValue.php` — default sort и positive integer.
- `platform/ensi/apps/catalog/pim/app/Domain/Audit/Resolvers/CurrentUserResolver.php` — system/null actor.
- `platform/ensi/apps/admin-gui/admin-gui-backend/app/Http/ApiV1/Modules/Catalog/Controllers/ProductsImportsController.php` — видимость импорта в CMS.

Только читать первоисточники. Не подключать анализ или изменение AutoMerch: согласованный контракт полностью приведён в этом ТЗ.
