# ecom-gateway — design (v1: walking skeleton)

**Дата:** 2026-05-27
**Статус:** на ревью
**Автор:** Zak + Claude (brainstorming)

## 1. Контекст и цель

Запускаем новый **BFF-слой** на Go для e-commerce GJ — второй BFF поверх существующего PHP/Lumen `platform/integration/`. Стратегия — **strangler**: на старте `ecom-gateway` живёт параллельно PHP-integration и берёт только **новые** домены, со временем постепенно замещая legacy. Большой миграции «взрывом» нет.

Первый домен — **персонализация / похожие товары** (запрос продуктовой команды). Это новый домен, которого нет в PHP-integration, поэтому стартуем с чистого листа без миграции legacy.

**Скоуп v1 — walking skeleton (без внешних вызовов):** production-grade каркас по стандартам со всеми сквозными механизмами и одним сквозным стаб-эндпоинтом. Реальные интеграции (rec-движок, ENSI-клиенты) — следующие циклы.

### Архитектурные решения, зафиксированные на брайнсторме

- **`ecom-gateway` — чистый BFF.** Без доменной/бизнес-логики рекомендаций. Движок рекомендаций — отдельный сервис (пишется отдельно, вне этого спека).
- **Стек определён прецедентом** (сервис `gj-buddy-server` в `~/Projects/Buddy`): Go + **Fiber v2** + **spec-first OpenAPI** через `oapi-codegen` в **types-only** режиме (`generate: models: true`, ADR-0015 §D1) — генерим только DTO, роуты/хендлеры на Fiber пишем руками. Это снимает проблему «oapi-codegen таргетит net/http, не Fiber».
- **Стандарт структуры** — `go-service-guideline.md v1.0` (из Buddy): тонкий `main` (≤30 строк), один bounded context = один пакет в `internal/`, канонические 4 файла на пакет.
- **Телеметрия = Prometheus** (гайдлайн §7), не OTel. `gj-go-logger v1.0.5` для структурного лога.
- **v1 stateless** — у чистого BFF нет своего хранилища (состояние в rec-сервисе), поэтому §4 гайдлайна (pgx/миграции/репозитории) в v1 не применяется.
- **Имя сервиса:** `ecom-gateway` (снимает конфликт с деплоем `integration-api` у PHP-сервиса).
- **Размещение:** `platform-new/ecom-gateway/` — попадание в существующий Go-флот (`ecom-stat-service`, `stock-inventory-service`, `feed-generator`, … + shared `gj-go-logger`/`gj-go-migrate`).
- **Версия Go:** `1.26.2` (последняя стабильная; совпадает с Buddy и локальным toolchain).
- **CI (`.gitlab-ci.yml`):** отложено до этапа деплоя — не входит в v1. Шаблон сверим с соседними Go-сервисами non-platform, когда дойдём до деплоя.

### Подход к скаффолдингу: Hybrid

Структура и границы — строго по `go-service-guideline.md`. Из Buddy переносим только generic-обвязку (`cmd/server` thin main, `internal/config`, `internal/health`, `internal/observability`, `internal/httpx` error-envelope, `oapi-codegen.yaml` + Makefile-таргет, graceful shutdown). Домен `recommendations` и роутинг пишем заново.

## 2. Структура проекта

```
platform-new/ecom-gateway/
├── cmd/ecom-gateway/main.go        # ≤30 строк: config → container → transport → wait signal
├── api/v1/
│   ├── openapi.yaml                # источник истины (Redocly lint)
│   └── oapi-codegen.yaml           # types-only (models: true)
├── internal/
│   ├── app/container.go            # сборка зависимостей, ≤200 строк
│   ├── app/wire_recommendations.go # проводка одного bounded context
│   ├── config/                     # env-конфиг
│   ├── http/                       # корневой роутер, монтаж доменов, middleware
│   ├── httpx/                      # единый error-envelope {"error","message"}
│   ├── observability/              # Prometheus: 3 метрики, /metrics, middleware
│   ├── health/                     # /health, /ready
│   └── recommendations/            # единственный домен v1
│       ├── types.go                # domain-модель + (импорт DTO из openapi.gen.go)
│       ├── service.go              # оркестрация + потребляемые интерфейсы (порты)
│       ├── handler.go              # HTTP I/O, вызывает service
│       ├── routes.go               # тонкий, ≤80 строк
│       └── boundary_test.go        # проверка границ пакета
├── Dockerfile, Makefile           # .gitlab-ci.yml — на этапе деплоя, вне v1
```

Go pinned: `go 1.26.2`.

`openapi.gen.go` генерится в `internal/recommendations/` (по аналогии с Buddy `internal/admin/openapi.gen.go`).

### Порты домена (SOLID — интерфейс определяет потребитель, пакет `recommendations`)

```go
// service.go
type RecommendationSource interface {
    Similar(ctx context.Context, productID ProductID, opts SimilarOpts) ([]ProductID, error)
}
type ProductHydrator interface {
    Hydrate(ctx context.Context, ids []ProductID) ([]ProductCard, error)
}
```

- `RecommendationSource` → будущий rec-сервис. v1: `stubSource` (детерминированный список).
- `ProductHydrator` → будущий ENSI (`catalog-cache`/`offers`). v1: `stubHydrator` (каноничные карточки).
- `service.go` зависит **только** от этих интерфейсов; стаб-адаптеры подставляются в `wire_recommendations.go`. Реальные адаптеры добавятся позже без изменения домена.

## 3. Data flow сквозного эндпоинта

Эндпоинт v1: `GET /api/v1/recommendations/similar?product_id={id}&limit={n}`

```
client
  │  GET /api/v1/recommendations/similar?product_id=119871&limit=10
  ▼
http.Router ──> observability.Middleware (метрики на весь трафик)
  │             requestID + gj-go-logger в context (§6: никакого context.Background())
  ▼
recommendations.handler
  │  1. парсит+валидирует query (product_id обязателен; limit: default 10, max 50)
  │  2. service.Similar(ctx, productID, opts)
  ▼
recommendations.service
  │  3. ids   := RecommendationSource.Similar(ctx, productID, opts)   // v1 stub → [101,102,103]
  │  4. cards := ProductHydrator.Hydrate(ctx, ids)                    // v1 stub → карточки
  │  5. SimilarResponse{items: cards} (порядок сохраняем по ids)
  ▼
handler ──> httpx: 200 + JSON (DTO из openapi.gen.go)
            ошибки ──> единый envelope {"error","message"}
```

- service не знает про HTTP и про конкретные источники — только порты.
- Стабы детерминированы → сквозной тест воспроизводим.
- `limit` валидируется на BFF; пустая выдача = `200 {items: []}`, не ошибка.

## 4. Ошибки и контекст запроса

**Единый envelope (§5.2):** `{"error":"<code>","message":"<human>"}`, без утечки внутренних деталей. Живёт в `internal/httpx`.

**Маркер-ошибки + `%w` (§5.1):** домен возвращает типизированные ошибки; `handler` мапит в статус+код в одном месте.

| Маркер (domain) | HTTP | `error` code | Когда |
|---|---|---|---|
| `ErrInvalidArgument` | 400 | `invalid_argument` | нет `product_id`, `limit` вне диапазона |
| `ErrSourceUnavailable` | 502 | `source_unavailable` | rec-source/hydrator недоступны (с реальными адаптерами; v1 стаб не падает) |
| (fallthrough) | 500 | `internal` | необёрнутая ошибка |

**Контекст (§6):**
- В хендлерах — только `c.UserContext()` (Fiber); `context.Background()` запрещён. `ctx` пробрасывается во все порты (отмена/таймаут).
- В `ctx` через middleware кладём `request_id` и преднастроенный `gj-go-logger` → корреляция на всех слоях.
- Идентичность пользователя (персональный контур) — через будущий пакет `sessionctx`, не голым ключом. В v1 не нужен (similar анонимен), место зарезервировано.

**Таймауты:** per-request deadline на исходящие вызовы (конфиг, дефолт ~800ms) — заложено в порты сразу, чтобы реальные адаптеры были обязаны его уважать.

## 5. Наблюдаемость

Prometheus из коробки (гайдлайн §7), без OTel в v1.

**Три обязательные метрики (§7.2), на весь трафик через middleware (§7.4):**
- `http_requests_total{method,path,status}` — counter
- `http_request_duration_seconds{method,path}` — histogram
- `http_requests_in_flight` — gauge

`path` = **шаблон маршрута** (`/api/v1/recommendations/similar`), не сырой URL (контроль кардинальности).

**Эндпоинты:**
- `/metrics` — через `gofiber/adaptor` поверх `promhttp` (как в Buddy).
- `/health` — liveness.
- `/ready` — readiness; v1 stateless → 200 безусловно. Зарезервировано под чек реальных портов.

**Логирование:** `gj-go-logger v1.0.5`, structured, через `ctx`, каждая запись с `request_id`.

**Доменная метрика (опц. в v1, дёшево):** `recommendations_similar_results{outcome}` (hit/empty/error) — доля пустых выдач для продуктовой команды.

**НЕ делаем в v1 (YAGNI):** distributed tracing (OTel), бизнес-дашборды, алерты.

## 6. Тестирование

**1. `boundary_test.go` (§10.1, обязателен):** компайл-тайм проверка, что `recommendations` не импортирует чужие bounded-context'ы напрямую, зависит только от своих портов.

**2. Сквозной тест эндпоинта** со стаб-портами:
- `200` + форма ответа совпадает с DTO из `openapi.gen.go`;
- порядок `items` соответствует порядку id от source;
- нет `product_id` → `400 {"error":"invalid_argument"}`;
- `limit` вне диапазона → `400`; пустая выдача стаба → `200 {items:[]}`.

**3. Табличные тесты (§10.2)** для валидации query и маппинга маркер-ошибок → HTTP-статус.

**4. Контракт-линт в CI:** `redocly lint api/v1/openapi.yaml` + diff-gate `go generate` (сгенерить и убедиться, что `openapi.gen.go` не отстал от спеки).

**НЕ делаем в v1:** тесты с реальной БД (§10.3 — БД нет); интеграционные с живыми rec/ENSI (их нет). Стаб-порты = вся внешка в тестах.

## 7. Definition of Done (каркас v1)

- `make generate` + `redocly lint` зелёные;
- `go build ./...`, `go vet`, `go test ./...` зелёные;
- сервис стартует; `/health`, `/ready`, `/metrics` отвечают; `GET /api/v1/recommendations/similar` отдаёт стаб-карточки;
- Dockerfile собирается локально (CI-пайплайн — отдельно, на этапе деплоя).

## 8. Явно вне скоупа v1

- Логика рекомендаций (отдельный rec-сервис, пишется отдельно).
- Реальные ENSI-клиенты и реальная гидрация карточек.
- Персональные рекомендации и auth-контур (`sessionctx`, валидация токена покупателя).
- Хранилище/Postgres/миграции.
- Distributed tracing, дашборды, алерты.
- Edge-роутинг/сплит трафика сайта-моб на gateway (отдельное инфра-решение).
- `.gitlab-ci.yml` и деплой-конфиги (на этапе деплоя).
