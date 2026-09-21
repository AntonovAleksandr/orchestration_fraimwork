# ТЗ C: pimclient — чтение импорта по ID

> **Для исполнителя:** использовать `superpowers:executing-plans`, выполнить задачи последовательно. Документ самодостаточный; предыдущие сессии читать не требуется. Реализация разрешена только в pimclient. Commit/push/tag/release выполняются владельцем после отдельного ревью и поручения.

**Цель:** добавить опубликованному Go-клиенту PIM метод чтения записи импорта по ID для будущего GET статуса в intgateway.

**Архитектура:** один HTTP GET существующего PIM API, generated DTO и ручной метод поверх gj-go-httpclient. Клиент не знает правил AutoMerch, не ограничивает тип импорта и не хранит состояние.

**Стек:** Go 1.26.0, oapi-codegen v2.8.0 для ЭТОГО репозитория, gj-go-httpclient v0.1.2, oapi-codegen/runtime v1.4.1.

**Спецификация:** нормативный контракт полностью приведён ниже. Следующий этап — [ТЗ D: intgateway](2026-09-16-intgateway-import-status-spec.md).

## 1. Рабочая область и границы

- `$WORKSPACE` — корень GJ-Ecommerce.
- Репозиторий: `$WORKSPACE/platform-new/clients/pim`.
- Module/remote: `gitlab.gloria.aaanet.ru/greensight/gj/go/clients/pimclient`, `git@gitlab.gloria.aaanet.ru:greensight/gj/go/clients/pimclient.git`.
- Проверенная база: опубликованная v0.2.0, SHA `932c0e1a1086f4e1637100217b2f67ac59a87bab`. Если HEAD продвинулся, проверить наличие этих изменений, не откатывать их.
- Прочитать применимые AGENTS/CLAUDE, README, status/branch/HEAD и diff до изменений. Ветка новой работы: `codex/pimclient-import-status`; если уже создана — продолжить её после проверки состояния.
- Не менять intgateway, PIM PHP, AutoMerch, shared HTTP library, CMS/audit и deployment.
- Существующие SearchSkuProducts, SearchProductImports, PreloadProductImportFile, CreateProductImport сохранить совместимыми.
- Не добавлять retry, polling, cache, БД, бизнес-фильтр type=1, новый status endpoint PIM или произвольные query-параметры.
- Не запускать массовый sync. При необходимом fetch отключать repo hooks для этой команды: `git -c core.hooksPath=/dev/null fetch origin`.
- Никаких реальных HTTP-запросов PIM/импортов. Проверки через httptest.

## 2. Подтверждённый PIM API

```http
GET /api/v1/imports/products/501
```

```json
{"data":{"id":501,"type":1,"status":2,"created_at":"2026-09-16T10:00:00Z","updated_at":"2026-09-16T10:01:00Z","user_id":null,"file":null,"chunks_count":1,"chunks_finished":0}}
```

HTTP 200; отсутствующая запись — 404. Потребителю нужны только id/type/status, остальные поля игнорировать. Не считать наличие timestamps/file/chunks обязательным для нового DTO.

Локальные первоисточники от `$WORKSPACE`:

- `platform/ensi/apps/catalog/pim/app/Http/ApiV1/Modules/Imports/Controllers/ProductImportsController.php` — getProductImport/findOrFail.
- `platform/ensi/apps/catalog/pim/app/Http/ApiV1/Modules/Imports/Resources/ProductImportsResource.php` — реальные поля.
- `platform/ensi/apps/catalog/pim/app/Domain/Imports/Models/ProductExcelImportStatus.php` — 1 NEW, 2 IN_PROCESS, 3 DONE, 4 FAILED, 5 CANCELLED.

Клиент принимает любые положительные `type`/`status` для совместимости с будущими перечислениями. Известные бизнес-статусы фильтрует gateway. Нельзя превращать 404/timeout в фиктивную запись FAILED.

## 3. Точный публичный интерфейс

```go
func (c *Client) GetProductImport(ctx context.Context, id int64) (GetProductImportResponse, error)

// Generated из OpenAPI, не объявлять вручную:
// type ProductImportDetails struct {
//     Id int64 `json:"id"`
//     Type int `json:"type"`
//     Status int `json:"status"`
// }
// type GetProductImportResponse struct {
//     Data ProductImportDetails `json:"data"`
// }
```

В OpenAPI добавить отдельный ProductImportDetails; существующие ProductImport (create) и ProductImportSummary (search) не расширять обязательными полями. Все три поля details и data обязательны, integer, minimum=1; id имеет format=int64, type/status должны генерироваться как int.

Операция OpenAPI: `getProductImport`, tag `imports`, path parameter `id` required positive int64. Path `/api/v1/imports/products/{id}`. Успех 200 GetProductImportResponse; описать 404 и ошибки стандартным способом этого репозитория.

## 4. Выполнение запроса и ошибки

1. `id <= 0`: вернуть typed KindBadRequest, op=`product_import_get`, service=`pim`, HTTP не вызывать.
2. Построить URL из c.baseURL + `/api/v1/imports/products/` + strconv.FormatInt(id,10). Никаких query/body и Content-Type для несуществующего JSON body.
3. Использовать c.hc.Do с http.NewRequestWithContext; это сохраняет текущие decorator/metrics/options. Не создавать независимый http.Client и не менять переданные caller options.
4. Для GET нужна обработка ошибок чтения тела: существующий DoJSON v0.1.2 теряет их. Поэтому новый метод должен читать resp.Body сам; не исправлять shared library и не переписывать другие методы клиента в этом задании.
5. Любой полученный body закрыть на всех путях.
6. Успех только при HTTP 200, читаемом полном JSON и валидном ответе. Читать максимум 64 KiB + 1; тело >64 KiB — KindDecode. Ошибку чтения не игнорировать, даже если прочитанный префикс выглядит как валидный JSON.
7. JSON decode через json.Unmarshal; пустое/повреждённое тело, несколько JSON-документов, data missing/null, id/type/status missing/null/<=0, id != запрошенному → KindDecode. Unknown JSON fields допустимы. HTTP 204 и прочие неожиданные 2xx → KindDecode.
8. Non-2xx: захватить максимум 4 KiB в Error.Body; не читать без лимита и не ждать EOF для полного дренирования error body. Статусы: 401/403 KindUnauthorized, 404 KindNotFound, 5xx KindUpstream, остальные non-2xx KindBadRequest. Сохранить фактический StatusCode. На ошибке чтения самого error body сохранить context/transport cause и bounded prefix; валидным ответ не становится.
9. context.DeadlineExceeded → KindTimeout; context.Canceled → KindCanceled; сохранить причину в Error.Err, чтобы errors.Is работал. Проверять как до headers, так и во время чтения body; transport errors из c.hc.Do сохранить. Прочие повреждения/обрывы успешного body → KindDecode.
10. Не логировать body. Не ставить таймаут через context.Background: deadline приходит от caller. Ошибка содержит Service/Op/StatusCode по канону httpclient.
11. Retry отсутствует. Политику redirect задаёт caller через WithHTTPClient; в тестах и gateway использовать CheckRedirect → http.ErrUseLastResponse. Метод не должен обходить этот запрет.

Переиспользовать readError/decodeError/badRequest из imports.go, если семантика совпадает. Не менять их глобальное поведение без необходимости; изменения не должны влиять на POST.

## 5. Файлы

Создать:

- `import_status.go` — GetProductImport и его узкие константы/проверки.
- `import_status_test.go` — tests нового метода.

Изменить:

- `api/v1/openapi.yaml` — path ref.
- `api/v1/paths/imports.yaml` — GET path item.
- `api/v1/components/schemas/imports.yaml` — ProductImportDetails/GetProductImportResponse.
- `api/v1/bundle/openapi.yaml`, `openapi.gen.go` — только генерацией.
- `README.md` — GET example и typed errors; не писать несуществующий release tag.

go.mod/go.sum менять только при реальной необходимости: нужные библиотеки уже есть. Не обновлять их массово.

## 6. Задача C1: контракт, метод и тесты

- [ ] Зафиксировать исходное состояние и прочитать существующий imports.go.
- [ ] Описать OpenAPI и сгенерировать DTO с **v2.8.0**, совпадающей с текущим generated клиента. Не менять глобальную установленную версию инструмента ради этого репозитория; использовать отдельный tool directory/PATH или версионный запуск.
- [ ] Добавить failing happy-path test и тест id<=0 без upstream.
- [ ] Реализовать метод в import_status.go по разделу 4.
- [ ] Добавить и выполнить матрицу ниже.

Минимальный тест (package pim; импорты context/io/net/http/net/http/httptest/testing):

```go
func TestGetProductImport_HappyPath(t *testing.T) {
    calls := 0
    srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        calls++
        if r.Method != http.MethodGet || r.URL.Path != "/api/v1/imports/products/501" || r.URL.RawQuery != "" {
            t.Errorf("unexpected request: %s %s", r.Method, r.URL)
        }
        body, err := io.ReadAll(r.Body)
        if err != nil || len(body) != 0 { t.Errorf("unexpected body: %q err=%v", body, err) }
        w.Header().Set("Content-Type", "application/json")
        _, _ = io.WriteString(w, `{"data":{"id":501,"type":1,"status":2,"user_id":null}}`)
    }))
    defer srv.Close()
    out, err := New(srv.URL).GetProductImport(context.Background(), 501)
    if err != nil || out.Data.Id != 501 || out.Data.Type != 1 || out.Data.Status != 2 || calls != 1 {
        t.Fatalf("out=%+v err=%v calls=%d", out, err, calls)
    }
}
```

Матрица обязательна:

| Случай | Ожидание |
|---|---|
| id 0, -1 | KindBadRequest, 0 HTTP calls |
| id 501, URL с завершающим / | Правильный один GET, без двойного / и body |
| id MaxInt64 | Точный десятичный ID, без потери разрядов |
| Ответ с type=2/status=99 | Клиент принимает положительные значения; бизнес-фильтра нет |
| id ответа другой; missing/null/zero/negative data fields | KindDecode |
| Пустой/сломанный JSON, trailing JSON, body >64 KiB, 204 | KindDecode |
| 401/403/404/422/500/503 | Правильный Kind и фактический StatusCode |
| Error body больше 4 KiB | Body ограничен, не ждёт чтения неограниченного хвоста |
| Timeout/cancel до headers | Правильный Kind и errors.Is(ctx error) |
| 200 + flush headers + timeout/cancel при body | Правильный Kind; не KindDecode |
| 200 + полный JSON-префикс + оборванный Content-Length | Не успех; ошибка чтения сохранена |
| 307/308 и клиент с запретом redirects | Redirect target не вызван, нет повтора |
| Network/500/decode | Ровно одна попытка |
| Request decorator | X-Request-ID доходит |

Синхронизация cancellation tests — channels/controlled reader, а не гонка случайных sleep. Если deadline test использует короткое время, сервер должен сигнализировать, что нужная фаза действительно достигнута.

## 7. Задача C2: завершение и handoff

- [ ] Повторить генерацию и сравнить generated hashes: дрейфа нет, существующая сериализация не меняется.
- [ ] Выполнить команды ниже, каждую проверять по exit code.
- [ ] Подготовить отчёт: branch/HEAD/diff, методы/DTO, результаты тестов, точная версия генератора. Не коммитить/публиковать автоматически.

```bash
GOWORK=off go test ./... -count=1
GOWORK=off go test -race ./... -count=1
GOWORK=off go vet ./...
GOWORK=off go build ./...
make lint
git diff --check
```

GOWORK=off обязателен: общий workspace ранее скрывал отсутствующую зависимость. При sandbox-ошибке открытия httptest-порта или доступа к cache обозначить причину, а не объявлять тест зелёным.

Владелец проводит ревью, публикует клиент и передаёт **реальный одобренный тег** исполнителю ТЗ D. Не придумывать версию и не утверждать, что v0.2.0 уже имеет GET.
