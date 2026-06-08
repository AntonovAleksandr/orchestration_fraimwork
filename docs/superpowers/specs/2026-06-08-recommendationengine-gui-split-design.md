# RecommendationEngine → движок + админка: дизайн разделения

**Дата:** 2026-06-08
**Статус:** утверждён к планированию
**Scope:** разделение моно-репо `recomendationengine` на два независимо разворачиваемых сервиса. Интеграция с IntGateway — отдельный цикл.

## Контекст

Михаил вынес сервис «Похожие товары» (`gj-similar`) из монолита `automerch` в репозиторий
`gitlab.gloria.aaanet.ru/greensight/gj/go/recomendationengine`. Сейчас это **моно-репо с двумя половинами**:

- **Backend** — Go 1.24 + Fiber (`cmd/similar`, `internal/`), своя Postgres, фид по расписанию,
  публичный API похожих + admin-API стратегии.
- **Frontend** — React 18 + TypeScript + CRA + Tailwind в `frontend/` (админка стратегии/фида/витрина).

Devops подсветил, что движок и его админку нужно развернуть как **два отдельных проекта** в k8s.
Создан пустой репозиторий `gitlab.gloria.aaanet.ru/greensight/gj/go/recomendationenginegui`.
Оба репо склонированы локально в `platform-new/`.

Развёртывание — по аналогии с `checkout` / `intgateway`: репо отдаёт `Dockerfile` + одноимённый
include shared-пайплайна, дальше devops собирает образ (Kaniko → registry) и катит helm-upgrade
per-env (`gs-test` / `stage` / `prod`). Helm-чарты живут на стороне devops.

### Что упрощает задачу (текущее состояние связности)

- Фронт читает **конфигурируемый** API-base: `frontend/src/services/api.ts` →
  `REACT_APP_API_URL || REACT_APP_API_BASE_URL || ''`; пустая строка = относительные пути (CRA proxy).
- Go-бинарь **не** эмбедит фронт-билд (единственный `go:embed` — `strategy/fixtures/document_0206.json`).
- Контракт между половинами — чистый HTTP под `/api/*`; здоровье — `/health`.
- CORS на движке сейчас `AllowOrigins: "*"` (`internal/middleware/middleware.go`).

Вывод: это в основном **хирургия репозиториев + упаковка деплоя**, а не переписывание кода.

## Цель и не-цели

**Цель:** два независимо разворачиваемых сервиса, готовых под k8s-деплой devops'ом по схеме checkout/intgateway.

**Не-цели (этот цикл):**
- Интеграция реального `RecommendationSource` в IntGateway — отдельный план; `stubSource` в
  `intgateway/internal/domains/recommendations/stub.go` пока остаётся. (Хидратор `CatalogCacheHydrator`
  уже реальный — на него это не влияет.)
- Переписывание алгоритма похожих / фида.
- Добавление аутентификации к admin-API (вынесено в follow-up, см. Риски).

## Подход

Devops продиктовал **два отдельных репозитория**. Рассмотренные и отклонённые альтернативы:
моно-репо с двумя деплоями (отклонено — devops хочет раздельные проекты), `go:embed` фронта в бинарь
(отклонено — противоречит раздельному деплою). Выбран **split на два репо**.

### Ключевое решение: как GUI ходит в API движка

CRA вшивает `REACT_APP_*` на **этапе билда**, а Kaniko собирает **один образ** на все стенды.
Чтобы статика была идентична на всех стендах и не требовала per-env конфига, выбран
**nginx reverse-proxy внутри пода админки**:

- GUI-образ = `nginx` + собранная статика + наш `nginx.conf` (один контейнер, не отдельная сущность куба).
- Фронт зовёт **относительные** `/api/...` (ровно как CRA `proxy` в dev).
- `nginx.conf` проксирует `location /api/ → http://recommendationengine:8080` — k8s-Service движка
  в том же namespace. Имя namespace-локальное, **одинаковое на всех стендах** → образ идентичен везде,
  per-env переменных у фронта ноль, CORS в браузере не нужен.

Отклонено: build-time bake (нужен отдельный образ на стенд — не ложится на «один образ → много env»);
runtime `env.js` (рабочий, но тянет CORS-allowlist на движке + правку `api.ts` — лишняя сложность здесь).

## Целевое состояние

### Репо `recomendationengine` (остаётся — чистый Go-сервис)

| Изменение | Детали |
|---|---|
| Удалить `frontend/` | Целиком, включая `package-lock.json`, `.playwright-cli`. |
| `.gitlab-ci.yml` | Заменить самописные backend/frontend стадии на include `greensight/gj/devops/gitlab-ci → golang-backend-pipeline.yml` (как у `intgateway`), `variables: DOMAIN_SERVICE: "go"`. |
| `Dockerfile` | Оставить как есть (CGO+`debian-bookworm-slim`). CGO требуется, потому что **sqlite — действующий драйвер тестов и локалки**, не мёртвый код: `internal/testutil/db.go` гоняет юнит-тесты на SQLite в temp-каталоге, есть ветка `initSQLite`, слой трансляции диалекта `rewriteSQLiteJSON`, отдельные SQLite-миграции и parity-тесты SQLite↔Postgres. Прод — только Postgres. Удаление sqlite ⇒ `CGO_ENABLED=0`/distroless — **отдельный follow-up** (см. ниже), не часть сплита. |
| `Makefile` | Убрать цели `frontend-install` / `frontend-dev` / `frontend-build`; почистить `.PHONY`. |
| `docker-compose.yml` | Проверить — фронт-сервиса там нет, правок по сути не требуется. |
| `README.md` / `AGENTS.md` | Выкинуть раздел фронта; добавить ссылку на репо GUI; чеклист агента — убрать шаги 3/5 про frontend. |
| CORS | Оставить `AllowOrigins: "*"` (не регресс; публичный API зовёт IntGateway server-to-server, CORS не применяется). Сужение — follow-up. |

После правок должны быть зелёными: `go build ./... && go vet ./... && go test ./...`.

### Репо `recomendationenginegui` (наполняем с нуля)

| Артефакт | Детали |
|---|---|
| Содержимое `frontend/` | Скопировать **в корень** GUI-репо (package.json в корне). Без git-истории: первый коммит «initial: admin GUI extracted from recomendationengine». |
| `Dockerfile` | Multi-stage: `node:20-alpine` (`npm ci && npm run build`) → `nginx:alpine` (статика в `/usr/share/nginx/html` + наш `nginx.conf`). |
| `nginx.conf` | SPA-fallback `try_files $uri $uri/ /index.html`; `location /api/ { proxy_pass http://recommendationengine:8080; }`. |
| `.gitlab-ci.yml` | Include `greensight/gj/devops/gitlab-ci → frontend-pipeline.yml`. |
| `api.ts` | **Без изменений** — пустой base уже даёт относительные пути в nginx. |
| `package.json` `"proxy"` | Оставить (dev-only, безвредно для prod-сборки). |
| `README.md` | Dev: `npm start` + proxy на локальный движок. Prod: nginx-proxy в namespace. |

После: `npm ci && npm run build && npx tsc --noEmit` зелёные; `docker build` ок.

### CI / Deploy (обе репы)

- Shared-пайплайн строит `Dockerfile` через Kaniko → registry, деплой = helm-upgrade per-env.
- Ветки по конвенции шаблона: `task-*` / `release-*` / `uat` / `master`.
- **На стороне devops:** helm-чарты, `Service` / `Ingress` / `Deployment`, имя upstream-Service движка.
- **На нашей стороне:** рабочий `Dockerfile` + include шаблона.

## Риски и follow-ups (вне scope этого цикла)

1. **Admin API без auth.** `/api/admin/*` ничем не защищён; при отдельном ingress GUI становится
   открытым наружу. Решить до prod (ingress basic-auth или auth в движке). — *follow-up*
2. **Имя k8s-Service движка** должно совпасть с `proxy_pass` (дефолт `recommendationengine`).
   Согласовать с devops; если имя иное — либо devops правят Service, либо делаем upstream
   параметром через `envsubst` в entrypoint. — *согласование с devops*
3. **npm-registry внутри Kaniko-сборки GUI.** По аналогии с `GOPROXY`-nexus у go-сборок, возможно
   понадобится `.npmrc` на nexus-прокси, чтобы `npm ci` достучался до реестра в CI. — *уточнить у devops*
4. **Удаление sqlite + CGO-free сборка.** Перевести тест-харнесс на Postgres (testcontainers /
   `INTEGRATION_DATABASE_URL`), снести диалект-слой `rewriteSQLiteJSON`, SQLite-миграции и parity-тесты,
   убрать `mattn/go-sqlite3` → `CGO_ENABLED=0` + distroless как у флота (checkout/intgateway). Заметный
   рефактор кода Михаила, ортогонален сплиту. — *отдельный follow-up*
5. **Переименование Go-модуля** `gj-similar` → `gitlab.gloria.aaanet.ru/greensight/gj/go/recomendationengine`
   для единообразия с флотом. Не требуется для интеграции (общение по HTTP), косметика. — *опционально*

## Верификация

**Движок (после удаления `frontend/`):**
- `go build ./... && go vet ./... && go test ./...` — зелёные.
- `docker build .` — успешно.
- `make run` → `curl localhost:8080/health` → `curl localhost:8080/api/v1/client/products/<id>/similar`.

**GUI:**
- `npm ci && npm run build && npx tsc --noEmit` — зелёные.
- `docker build .` — успешно.
- `docker run` локально → статика отдаётся, `/api/*` проксируется на локальный движок
  (проверить открытие админки + сохранение стратегии).
