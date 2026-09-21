# ТЗ D: intgateway — получение статуса импорта позиций категорий

> **Для исполнителя:** использовать `superpowers:executing-plans`. Документ самодостаточный. Разрешена реализация только в intgateway поверх существующего POST. Commit/push/deploy и реальные импорты не выполнять: сначала отчёт и ревью владельцем.

**Цель:** backend AutoMerch получает по выданному при загрузке `import_id` фактический статус PIM и показывает его в своём UI.

**Архитектура:** AutoMerch → intgateway → существующий GET PIM. Gateway без БД: один входящий GET вызывает максимум один GET PIM. Отдельные read port, handler и adapter, общий с POST интеграционный токен.

**Стек:** Go 1.26.2, chi v5, существующий gj-go-httpclient, одобренный опубликованный pimclient с GetProductImport. **oapi-codegen v2.4.1** — версия именно gateway.

**Зависимость:** сначала [ТЗ C: pimclient](2026-09-16-pimclient-import-status-spec.md), ревью и выпуск клиента. В v0.2.0 нужного метода нет. Номер новой версии сообщает владелец после публикации; не придумывать тег.

## 1. Рабочая область и исходное состояние

- `$WORKSPACE` — корень GJ-Ecommerce; репозиторий `$WORKSPACE/platform-new/intgateway`.
- Проверенная ветка: `codex/category-position-imports`, HEAD `aa8053eed1f04f34aa3cd156f10ae9e7f7a77a6a`.
- **Реализация POST, исправления по ревью и её документация находятся в текущем working tree, включая untracked файлы. В HEAD их нет.** Начать с проверки branch/status/diff и продолжить этот checkout. Не создавать чистую копию от HEAD: она потеряет базу данной задачи. Если изменения уже закоммичены владельцем, использовать их актуальное состояние.
- Прочитать применимые AGENTS/CLAUDE, README и `docs/category-position-import-api.md`.
- Не откатывать чужие изменения и не переписывать уже проверенную реализацию POST/Excel validator.
- Не менять PIM, AutoMerch, CMS/audit, pimclient, shared libraries, deployment. Клиент дорабатывается отдельной сессией по ТЗ C.
- Запрещены БД/Redis, локальный реестр ID, сохранение статусов, фоновые jobs/polling, retry, дедупликация, новый импорт и поиск списка импортов из GET.
- Не добавлять warnings endpoint, процент прогресса, причины ошибок PIM, отмену импорта или управление очередью.

### Входной контроль зависимости

Проверить реально опубликованный одобренный тег pimclient и наличие интерфейса:

```go
GetProductImport(ctx context.Context, id int64) (GetProductImportResponse, error)
// response.Data: Id int64, Type int, Status int
```

Подключить этот тег в go.mod/go.sum. Не использовать local replace, workspace-подмену, выдуманный тег или собственный HTTP-клиент PIM в gateway. Если тег ещё не опубликован, можно подготовить OpenAPI/domain/handler с fake port; интеграцию и сдачу завершить после получения зависимости. Не объявлять задачу готовой без standalone сборки.

## 2. Публичный HTTP-контракт

```http
GET /api/v1/catalog/category-position-imports/501
X-Integration-Token: <тот же секрет, что у POST>
```

Без request body и обязательных query-параметров. `import_id` — именно ID из ответа POST, не preload_file_id. Customer JWT не нужен.

```http
HTTP/1.1 200 OK
Content-Type: application/json
Cache-Control: no-store
```

```json
{"import_id":501,"status":"in_process"}
```

Оба поля обязательны. Ответ без `data` envelope. Не возвращать `accepted`, type/user/file/chunks, токен, upstream body, счётчики строк или is_terminal. X-Request-ID обрабатывается существующим middleware сервиса.

Path ID: каноническая десятичная запись положительного int64, шаблон `^[1-9][0-9]*$`, затем `strconv.ParseInt(...,10,64)`. Ноль, минус, плюс, ведущие нули, пробелы, дроби, буквы и переполнение → 400. Отсутствующий сегмент пути обрабатывает router (404); не переопределять глобальный 404.

### Статусы

| PIM | HTTP status field | Смысл для потребителя |
|---|---|---|
| 1 | `new` | Запись создана, обработка ожидается |
| 2 | `in_process` | Обработка выполняется |
| 3 | `done` | PIM отметил обработку завершённой; это не гарантия применения каждой строки |
| 4 | `failed` | PIM зафиксировал ошибку; в текущей реализации возможно последующее `done` |
| 5 | `cancelled` | PIM отметил импорт отменённым |

GET отражает текущую запись PIM. Он не подтверждает обновление витрины, не вычисляет успешность всех строк и не устанавливает строго терминальные состояния. Временная ошибка GET не должна превращаться в `status=failed`.

### Ошибки

Формат через существующий httpx.Helper: `{"error":"код","message":"безопасное описание"}`. Клиент ветвится по HTTP/error, текст message не является контрактом.

| Условие | HTTP | error |
|---|---:|---|
| Feature flag выключен | 404 | `not_found` |
| Токен отсутствует/неверен/дублирован | 401 | `invalid_integration_token` |
| Некорректный path ID | 400 | `invalid_import_id` |
| PIM 404 или существующий импорт другого положительного type | 404 | `import_not_found` |
| PIM timeout, в том числе чтение body после headers | 504 | `pim_timeout` |
| PIM 3xx, остальные 4xx, 5xx, network/decode/неизвестный status | 502 | `pim_unavailable` |
| Неожиданная внутренняя ошибка gateway | 500 | `internal` |

На всех ответах обработанного GET-маршрута, включая guard/error paths, `Cache-Control: no-store`. Не менять cache headers других API. При отмене входящего ctx прекратить upstream, не повторять запрос и не пытаться выдавать успешный статус: как существующая ветка ErrCanceled в handler.go, завершить handler без записи ответа. Клиентский disconnect не является ошибкой самого импорта; тест проверяет отсутствие записи тела, а не требует отдельного HTTP-кода на закрытом соединении.

Порядок проверок: no-store → существующий TokenMiddleware.Guard (disabled, затем token) → ID → PIM. Для disabled/token/ID ошибок PIM не вызывается. PIM 401/403 не превращать в ошибку integration token: это 502.

## 3. Чтение PIM и границы доступа

PIM уже предоставляет `GET /api/v1/imports/products/{id}` с ответом `{"data":{"id":501,"type":1,"status":2}}` и дополнительными полями. Для чтения использовать только pimclient.GetProductImport.

1. Ровно один вызов клиента в контексте входящего запроса с deadline по разделу 5.
2. Клиент по ТЗ C проверяет положительные id/type/status, совпадение ID и целостность ответа. Такие нарушения → typed decode → 502.
3. Валидный `type != 1` → 404/import_not_found. Не раскрывать тип или статус такого импорта.
4. Для `type == 1` преобразовать status по таблице. Неизвестный положительный status → 502, без подстановки failed/new.
5. Переносить в HTTP только import_id/status. Не возвращать необработанный объект клиента.

Любой обладатель общего токена с известным ID сможет прочитать минимальное состояние любого импорта позиций категорий, включая созданный через CMS. Проверка происхождения «создано именно AutoMerch» в этом MVP отсутствует: у gateway нет хранилища и признака источника. Не имитировать такую проверку по user_id/file name.

GET не вызывает search/preload/create и не проверяет число активных импортов. Сохранить POST-правило **active > 2 → busy**: при 0/1/2 создание допускается. Занятость очереди не блокирует чтение.

## 4. Структура реализации

### Domain

Создать `internal/domains/catalogimports/status.go`:

```go
type ImportStatus string

const (
    ImportStatusNew       ImportStatus = "new"
    ImportStatusInProcess ImportStatus = "in_process"
    ImportStatusDone      ImportStatus = "done"
    ImportStatusFailed    ImportStatus = "failed"
    ImportStatusCancelled ImportStatus = "cancelled"
)

type ImportStatusSnapshot struct {
    ImportID int64
    Status   ImportStatus
}

type ImportStatusReader interface {
    GetStatus(context.Context, int64) (ImportStatusSnapshot, error)
}
```

В существующий доменный errors.go добавить ErrImportNotFound; переиспользовать ErrPIMUnavailable/ErrPIMTimeout/ErrCanceled. Domain не импортирует pimclient и adapter.

Создать `status_handler.go`, `status_handler_test.go`. Интерфейс:

```go
func NewStatusHandler(enabled bool, reader ImportStatusReader, errs *httpx.Helper) *StatusHandler
func (h *StatusHandler) Get(w http.ResponseWriter, r *http.Request)
```

Успех писать generated DTO CategoryPositionImportStatusResponse. Допустим json.Encoder с Content-Type application/json; не вводить глобальный response helper ради одного метода. Проверка enabled до обращения к reader обязательна, чтобы disabled wiring с nil reader безопасно работал.

В routes.go добавить `StatusHandler *StatusHandler` в Deps и GET с тем же Token.Guard. Узкий no-store middleware для GET поставить перед guard. Маршрут остаётся внутри `/api/v1`, отдельно от customer auth. POST mount/signature NewHandler не менять.

### Adapter и wiring

Создать `internal/adapters/catalogimports/status.go`, `status_test.go`:

```go
func NewPIMStatusReader(client *pimclient.Client, budget time.Duration) *PIMStatusReader
func (r *PIMStatusReader) GetStatus(ctx context.Context, id int64) (catalogimports.ImportStatusSnapshot, error)
```

Adapter владеет преобразованием type/status и typed errors клиента; ошибки сохраняют cause для errors.Is. Не копировать алгоритм регистрации из pim.go и не переписывать существующие error mappers POST.

В `internal/app/wire/catalogimports.go` добавить CatalogImportsStatus(cfg, errs, hcm) → *StatusHandler. Можно вынести существующее создание PIM-клиента в узкий общий helper, сохранив настройки POST:

- WithMetrics(hcm);
- HTTP client с CheckRedirect → http.ErrUseLastResponse;
- decorator передаёт только доверенный X-Request-ID из reqctx;
- не переносить X-Integration-Token, Authorization, customer headers, initial-event и произвольные входящие headers в PIM.

Добавить CatalogImportsStatusHandler в container.go, app.go и transport dependencies. При disabled не создавать используемую upstream-зависимость, не требовать PIM URL/token. Оставить поведение остальных доменов прежним.

ID можно писать как поле структурированного лога; не использовать ID/сырой URL с ID как metric label. Использовать существующие route templates и операции клиента, не добавлять отдельную telemetry-систему.

## 5. Ограничение времени

Новая настройка `PIM_IMPORT_STATUS_TIMEOUT_MS`: default **5000**, допустимо **1..10000** включительно. Поле `StatusTimeout time.Duration` в CategoryPositionImportConfig. POST остаётся на прежнем PIM_IMPORT_TIMEOUT_MS с прежней семантикой.

Load сейчас возвращает Config без error. Для нового параметра использовать os.LookupEnv: отсутствующая переменная → default; заданное значение строго разобрать через strconv.ParseInt, проверить диапазон до умножения на time.Millisecond. Пустое/нечисловое/вне диапазона/overflow → нулевой sentinel, который config.Validate отвергает при enabled. Не использовать молчаливый clamp или fallback для ошибочного значения. Не менять сигнатуру Load и общие env helpers.

При disabled валидация не требует новой настройки или интеграционных секретов. Ошибка enabled-конфига называет PIM_IMPORT_STATUS_TIMEOUT_MS и диапазон; не печатает token.

Adapter создаёт один context.WithTimeout(parent, StatusTimeout) с defer cancel; более ранний deadline parent сохраняется. Не использовать Background. Глобальные HTTP read/write timeouts не менять. В конфиг-тестах существующие валидные enabled fixtures дополнить новым полем — не ослаблять Validate.

## 6. OpenAPI и документация

Изменить split-спеку до реализации, затем генерировать:

- `api/v1/openapi.yaml` — новый path ref;
- `api/v1/paths/catalog_imports.yaml` — GET, operationId `getCategoryPositionImport`, tag `catalog-imports`, security `IntegrationToken`, required path import_id integer/int64 minimum=1 с описанием строгого формата;
- `api/v1/components/schemas/catalog_imports.yaml` — CategoryPositionImportStatus (string enum из пяти значений), CategoryPositionImportStatusResponse (required import_id/status), ошибки и no-store header по разделу 2;
- `api/v1/bundle/openapi.yaml` и generated domain DTO — только генерацией **v2.4.1**. У клиента генератор v2.8.0, это не основание обновлять gateway.

Не допускать изменений сериализации basket/recommendations: ранее другой генератор добавлял omitempty в nullable поля. Сравнить generated других доменов с исходным состоянием этой сессии.

Обновить README, `docs/configuration.md`, `docs/category-position-import-api.md`, `docs/category-position-import-status-proposal.md`: GET реализован локально после тестов; deployment не подтверждён. Добавить новую env-настройку, curl и строгий формат ID. Не создавать .env-файлы и не менять POST/Excel контракт.

```bash
curl --request GET \
  --url "${INTGATEWAY_BASE_URL}/api/v1/catalog/category-position-imports/501" \
  --header "X-Integration-Token: ${CATEGORY_IMPORT_TOKEN}"
```

Потребительская документация сохраняет рекомендации: backend хранит токен; UI опрашивает примерно раз в 5 секунд без одновременных запросов на один ID; при временных ошибках backoff до 30 секунд. Gateway сам опрос не выполняет. Истечение локального времени наблюдения не доказывает сбой PIM; никакого автоматического повторного POST.

## 7. Последовательность и обязательные тесты

### D1. Контракт и handler

- [ ] Зафиксировать исходные branch/HEAD/status, сохранность POST и опубликованный тег клиента.
- [ ] Описать OpenAPI, сгенерировать DTO закреплённой версией.
- [ ] Добавить failing handler tests с fake ImportStatusReader, затем реализовать domain/handler/route.
- [ ] Проверить таблицу HTTP ниже через реальный route и middleware, а не только прямой вызов handler.

### D2. Adapter, конфигурация и wiring

- [ ] Добавить failing adapter tests с httptest PIM, затем реализовать adapter/error mapping.
- [ ] Добавить StatusTimeout, parsing/Validate и wiring.
- [ ] Добавить сквозной httptest для gateway router → реальный pimclient → fake PIM: POST вернул ID, GET читает этот ID. Учитывать отдельные upstream-вызовы POST; на фазе GET разрешён только один GET.

| Проверка | Ожидаемый результат |
|---|---|
| Все 5 известных statuses, type=1 | 200, точные import_id/status, без лишних полей |
| Disabled; missing/wrong/duplicate token | 404/401 как у POST, 0 PIM calls; no-store |
| Valid token, без customer JWT | Успешное чтение |
| IDs 0, -1, +1, 01, abc, 1.5, encoded spaces, >MaxInt64 | 400 invalid_import_id, 0 PIM calls |
| ID MaxInt64 | Передан без потери точности |
| PIM 404; type=2 с валидными полями | 404 import_not_found |
| Missing/null/zero/negative fields, другой id, malformed JSON, 204 | 502 pim_unavailable |
| type=1, status=99 | 502 pim_unavailable |
| PIM 401/403/422/500/503/network | 502, тело/URL/token upstream не раскрыты |
| Timeout до headers и после 200 headers | 504 pim_timeout; один вызов |
| Parent cancel/ранний deadline | Upstream прерван в parent budget, retry отсутствует |
| Redirect 307/308 | Target не вызван, 502 |
| Валидный GET при занятости импорта | Search/busy/preload/create не вызваны |
| Передача заголовков | Только доверенный X-Request-ID из входящих context headers |
| Два GET: сначала PIM failed, потом done | Два свежих чтения; нет cache/фиксации failed |
| Новая env отсутствует/1/10000 | Default 5s или точное заданное значение |
| Новая env пустая/abc/0/-1/10001/overflow, enabled | Validate возвращает ошибку |
| Disabled без token/PIM URL | Конфигурация валидна; GET 404 |
| Полная регрессия POST | Excel validation, unknown outcome и порог >2 сохранены |

Для всех обработанных GET success/error проверить JSON и no-store. Для upstream error/cancel проверить число попыток. Синхронизировать cancel/after-headers tests каналами или controlled reader, не случайными sleep. Ни одного live PIM запроса.

### D3. Завершение и отчёт

- [ ] Повторить генерацию; generated hash не меняется. Existing DTO других доменов без дрейфа.
- [ ] Выполнить из intgateway все команды ниже, проверяя exit codes.
- [ ] Обновить consumer docs; провести self-review diff и подготовить отчёт. Не коммитить и не деплоить.

```bash
GOWORK=off go test -race ./... -count=1
GOWORK=off go vet ./...
GOWORK=off go build ./...
make lint
git diff --check
```

На исходной базе aa8053e ранее подтверждены две существующие ошибки lint: nullable-type-sibling в basket и security-defined у BasketCurrent. Новые ошибки GET недопустимы; старые перечислить отдельно, не исправлять посторонние схемы. Если результат отличается, исследовать diff, не объявлять любое падение «старым».

Итоговый отчёт владельцу: branch/HEAD; реально подключённая версия pimclient; список файлов; endpoint/example/status/error mapping; результаты каждой проверки; подтверждение неизменности POST и отсутствия новых зависимостей/хранилища; оставшиеся ограничения. Ссылаться на реальные результаты, не только на ожидаемые.

## 8. Приёмка владельцем

Работа готова к ревью, когда GET полностью проходит матрицу и standalone сборку, PIM/POST не изменены, generated других доменов стабильны, документация совпадает с кодом. Опубликованный клиент — обязательная зависимость сдачи. Проверка deployment, реального импорта и UI AutoMerch выполняется отдельным поручением после ревью.
