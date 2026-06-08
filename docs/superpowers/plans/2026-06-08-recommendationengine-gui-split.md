# RecommendationEngine → движок + админка: план разделения

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Разнести моно-репо `recomendationengine` (Go-движок + React-админка в `frontend/`) на два независимо разворачиваемых сервиса: чистый Go-движок и отдельный репозиторий админки (`recomendationenginegui`), готовые под k8s-деплой devops'ом по схеме checkout/intgateway.

**Architecture:** Админка — статический CRA-бандл, который раздаёт nginx **внутри пода админки**; тот же nginx проксирует `location /api/ → http://recommendationengine:8080` (k8s-Service движка в том же namespace, имя namespace-локальное → образ идентичен на всех стендах, без per-env конфига и без CORS). Движок остаётся Go 1.24 + Fiber, из него удаляется `frontend/`. Оба репо подключают shared GitLab-CI шаблон (Kaniko собирает `Dockerfile` → registry → helm-upgrade per-env; helm-чарты на стороне devops).

**Tech Stack:** Go 1.24 + Fiber (движок); React 18 + TypeScript + CRA (react-scripts 5) + Tailwind, nginx:alpine, node:20-alpine (админка); GitLab CI shared templates (`greensight/gj/devops/gitlab-ci`).

**Спека:** `docs/superpowers/specs/2026-06-08-recommendationengine-gui-split-design.md`

---

## Pre-flight: контекст для исполнителя (прочитать целиком до начала)

**Рабочее окружение.** Все пути ниже — относительно корня workspace `/Users/zak/Projects/GJ-Ecommerce`. Два целевых репозитория — это **отдельные git-клоны** внутри `platform-new/`:

- Движок: `platform-new/recomendationengine` — модуль `gj-similar`, default-ветка `master`.
- Админка: `platform-new/recomendationenginegui` — сейчас **пустой** (только `.git`), default-ветка `master`.

Это НЕ один git-репозиторий. Коммить **внутри каждого репо отдельно** (`cd` в репо перед `git`). Никаких git-операций в корне workspace по этим изменениям.

**⚠️ Критический гейт для Go-команд в движке.** В `platform-new/` есть родительский `go.work`, который **не** перечисляет `recomendationengine`. Поэтому `go build/vet/test` внутри движка падают с `directory prefix . does not contain modules listed in go.work`. **Всегда** запускай Go-команды в движке с префиксом `GOWORK=off`:
```bash
cd platform-new/recomendationengine && GOWORK=off go build ./...
```
(В CI этой проблемы нет — Docker-сборка копирует только репо, без родительского go.work.)

**Базовое состояние тестов движка (зафиксировано 2026-06-08, до изменений).**
- `GOWORK=off go build ./...` — OK.
- `GOWORK=off go vet ./...` — OK.
- `GOWORK=off go test ./...` — все пакеты PASS, **КРОМЕ одного пред-существующего фейла**: `TestAdminStrategy_GetStrategy_returnsDefaults` в `internal/handlers` (`admin_strategy_test.go:57`, дрейф дефолтов `category_leaf: 90`). Этот фейл **не относится к сплиту** и существует до любых правок. Критерий приёмки движка ниже — «**нет НОВЫХ фейлов** относительно этого базлайна», а не «всё зелёное».

**Конвенция веток (важно для CI).** Shared-пайплайн триггерится на ветках `task-*` / `release-*` / `uat` / `master` (`master` — обычно manual). Для исполнения создаём `task-*` ветки в каждом репо. Финальный merge в `master` — решение владельца, **не** часть этого плана (план доводит до запушенных task-веток + локальной верификации).

**Порядок фаз — строго:** сначала Фаза 1 (наполнить и проверить админку), и только потом Фаза 2 (удалить `frontend/` из движка). Так админка гарантированно сохранена до удаления источника.

---

## Файловая карта изменений

**Создаются в `recomendationenginegui`:**
- `Dockerfile` — multi-stage: node-build CRA → nginx раздаёт статику.
- `nginx.conf` — SPA-fallback + reverse-proxy `/api/` на движок.
- `.gitlab-ci.yml` — include shared `frontend-pipeline.yml`.
- `.gitignore`, `.dockerignore`.
- `README.md` — dev/prod инструкции (перезаписывает скопированный фронт-README).
- (копируются как есть) `package.json`, `package-lock.json`, `postcss.config.js`, `tailwind.config.js`, `tsconfig.json`, `public/`, `src/`.

**Модифицируются в `recomendationengine`:**
- Удаляется каталог `frontend/` целиком.
- `.gitlab-ci.yml` — заменяется на include shared `golang-backend-pipeline.yml`.
- `Makefile` — убираются `frontend-*` цели.
- `.gitignore` — убирается секция Frontend.
- `README.md`, `AGENTS.md` — убираются разделы про фронт, добавляется ссылка на GUI-репо.
- `Dockerfile` — **без изменений** (CGO+debian остаются: sqlite — драйвер тестов/локалки).

---

## ФАЗА 1 — Наполнить репозиторий админки (`recomendationenginegui`)

### Task 1: Ветка + перенос содержимого `frontend/` в корень GUI-репо

**Files:**
- Source: `platform-new/recomendationengine/frontend/` (копируется)
- Dest: `platform-new/recomendationenginegui/` (корень)

- [ ] **Step 1: Создать рабочую ветку в GUI-репо**

```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/recomendationenginegui
git checkout -b task-gui-split
```
Expected: `Switched to a new branch 'task-gui-split'` (репо пустой — это первая ветка поверх дефолтной `master`; если `master` ещё не существует как локальная ветка, команда всё равно создаст `task-gui-split`).

- [ ] **Step 2: Скопировать фронт в корень, исключив скрэтч-каталог `.playwright-cli`**

```bash
cd /Users/zak/Projects/GJ-Ecommerce
cp -R platform-new/recomendationengine/frontend/. platform-new/recomendationenginegui/
rm -rf platform-new/recomendationenginegui/.playwright-cli
```

- [ ] **Step 3: Проверить, что перенеслось ожидаемое (и НЕ перенеслось лишнее)**

```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/recomendationenginegui
ls -A
```
Expected: присутствуют `package.json`, `package-lock.json`, `postcss.config.js`, `tailwind.config.js`, `tsconfig.json`, `public/`, `src/`, `README.md`, `.git/`. **Отсутствуют** `.playwright-cli/`, `node_modules/`, `build/`.

### Task 2: Добавить `.gitignore` и `.dockerignore`

**Files:**
- Create: `platform-new/recomendationenginegui/.gitignore`
- Create: `platform-new/recomendationenginegui/.dockerignore`

- [ ] **Step 1: Записать `.gitignore`**

`platform-new/recomendationenginegui/.gitignore`:
```gitignore
node_modules/
build/
.env
.env.local
.env.production
*.log
.DS_Store
.idea/
.vscode/
.playwright-cli/
```

- [ ] **Step 2: Записать `.dockerignore`** (чтобы Kaniko не тащил мусор в build-контекст)

`platform-new/recomendationenginegui/.dockerignore`:
```dockerignore
node_modules
build
.git
.gitlab-ci.yml
.playwright-cli
README.md
```

### Task 3: Добавить `nginx.conf`

**Files:**
- Create: `platform-new/recomendationenginegui/nginx.conf`

- [ ] **Step 1: Записать `nginx.conf`**

> Замечание про `proxy_pass`: адрес указан **без** завершающего пути (`http://recommendationengine:8080;`), поэтому nginx сохраняет префикс `/api/` при проксировании — движок ожидает запросы именно под `/api/...`. НЕ добавляй слэш/путь после порта, иначе префикс будет срезан.

`platform-new/recomendationenginegui/nginx.conf`:
```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # SPA: любой путь, не являющийся файлом, отдаёт index.html (react-router)
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API движка «Похожие» — k8s-Service в том же namespace.
    # Имя namespace-локальное и одинаковое на всех стендах → образ идентичен везде.
    location /api/ {
        proxy_pass http://recommendationengine:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health самого nginx-пода (не движка)
    location = /healthz {
        access_log off;
        return 200 "ok\n";
        add_header Content-Type text/plain;
    }
}
```

### Task 4: Добавить `Dockerfile` (multi-stage)

**Files:**
- Create: `platform-new/recomendationenginegui/Dockerfile`

- [ ] **Step 1: Записать `Dockerfile`**

> `ENV CI=false` обязателен: CRA (`react-scripts build`) трактует ESLint-warnings как ошибки, когда `CI=true`, а GitLab выставляет `CI=true`. Без этого сборка падает на любом warning.

`platform-new/recomendationenginegui/Dockerfile`:
```dockerfile
# syntax=docker/dockerfile:1

# --- stage 1: собрать статический бандл CRA ---
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# CRA трактует warnings как ошибки при CI=true (GitLab его выставляет) — отключаем.
ENV CI=false
RUN npm run build

# --- stage 2: nginx раздаёт статику + проксирует /api на движок ---
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### Task 5: Добавить `.gitlab-ci.yml` (shared frontend-pipeline)

**Files:**
- Create: `platform-new/recomendationenginegui/.gitlab-ci.yml`

> **Координация с devops (зафиксировать, не блокер для написания файла):** `frontend-pipeline.yml` на стадии deploy через `.helm-upgrade` собирает путь values как `ms-helm-values/<env>/${DOMAIN_SERVICE}/${DEPLOY_SERVICE}/...`, где `DEPLOY_SERVICE = ${CI_PROJECT_NAME}` (= `recomendationenginegui`). Значение `DOMAIN_SERVICE` ниже выставлено в `"go"` — по группе репозитория `greensight/gj/go` и по аналогии с `intgateway`/движком. Это первый фронт-сервис в группе, поэтому **до первого деплоя** нужно подтвердить с devops, что helm-values по пути `go/recomendationenginegui/` заведены; если devops используют иной домен-каталог — поменять только это значение.

- [ ] **Step 1: Записать `.gitlab-ci.yml`**

`platform-new/recomendationenginegui/.gitlab-ci.yml`:
```yaml
variables:
  DOMAIN_SERVICE: "go"

include:
- project: 'greensight/gj/devops/gitlab-ci'
  ref: master
  file:
  - frontend-pipeline.yml
```

### Task 6: Перезаписать `README.md` GUI-репо

**Files:**
- Modify (overwrite): `platform-new/recomendationenginegui/README.md`

- [ ] **Step 1: Перезаписать `README.md`**

`platform-new/recomendationenginegui/README.md`:
```markdown
# RecommendationEngine GUI — админка сервиса «Похожие товары»

Админка (React 18 + TypeScript + CRA + Tailwind) для сервиса рекомендаций
[`recomendationengine`](https://gitlab.gloria.aaanet.ru/greensight/gj/go/recomendationengine):
настройка стратегии похожих (веса, пороги, правила атрибутов, цветовые семейства, preview),
управление фидом, витрина.

Выделена из моно-репо `recomendationengine` (каталог `frontend/`).

## Как админка ходит в API движка

- **Prod (k8s):** образ = `nginx` + статический бандл. nginx раздаёт SPA и проксирует
  `/api/*` на k8s-Service движка `recommendationengine:8080` в том же namespace
  (см. `nginx.conf`). Фронт зовёт относительные пути `/api/...`, никакого CORS и per-env
  конфига не требуется.
- **Dev:** CRA dev-server проксирует `/api` на локальный движок через поле `"proxy"` в
  `package.json` (по умолчанию `http://localhost:8081` — поправь под порт своего локального
  движка, движок по умолчанию слушает `:8080`).

API-base во фронте конфигурируется через `REACT_APP_API_URL` (см. `src/services/api.ts`);
по умолчанию пусто → относительные пути, что и нужно для nginx-proxy. Менять не требуется.

## Локальная разработка

```bash
npm ci
npm start            # CRA dev-server на :3000, проксирует /api на движок
npx tsc --noEmit     # typecheck
npm run build        # production-бандл в build/
```

Нужен запущенный движок (`recomendationengine`) — см. его README (`make run`, по умолчанию `:8080`).

## Docker

```bash
docker build -t recomendationenginegui .
docker run --rm -p 8088:80 recomendationenginegui
# http://localhost:8088 — статика; /api/* проксируется на хост recommendationengine:8080
```

## Деплой

GitLab CI (`.gitlab-ci.yml`) подключает shared-шаблон `frontend-pipeline.yml`
(`greensight/gj/devops/gitlab-ci`): Kaniko собирает `Dockerfile` → registry → helm-upgrade
per-env. Helm-чарты, Service/Ingress и имя upstream-Service движка — на стороне devops.
Имя upstream в `nginx.conf` (`recommendationengine`) должно совпадать с именем k8s-Service
движка в том же namespace.
```

### Task 7: Верификация сборки фронта

**Files:** —

- [ ] **Step 1: Установить зависимости**

```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/recomendationenginegui
npm ci
```
Expected: установка без ошибок (нужен Node 20; `npm ci` использует `package-lock.json`).

- [ ] **Step 2: Typecheck**

```bash
npx tsc --noEmit
```
Expected: завершается без ошибок (нет вывода).

- [ ] **Step 3: Production-сборка**

```bash
CI=false npm run build
```
Expected: `Compiled successfully` (или с warnings, но без падения); создаётся каталог `build/` с `index.html` и `static/`.

- [ ] **Step 4: Проверить артефакт сборки**

```bash
ls build && test -f build/index.html && echo "build OK"
```
Expected: `build OK`.

### Task 8: Верификация Docker-образа и проксирования

**Files:** —

- [ ] **Step 1: Собрать образ**

```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/recomendationenginegui
docker build -t recomendationenginegui:test .
```
Expected: образ собирается, оба стейджа проходят.

- [ ] **Step 2: Запустить и проверить раздачу статики**

```bash
docker run -d --name regui-test -p 8088:80 recomendationenginegui:test
sleep 2
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8088/
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8088/healthz
```
Expected: `200` на `/` (отдаётся `index.html`) и `200` на `/healthz`.

- [ ] **Step 3: Проверить, что reverse-proxy `/api` активен**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8088/api/health
```
Expected: `502` (или `504`) — апстрим `recommendationengine` не резолвится в standalone-`docker run`, что и **доказывает, что блок `location /api/` активен и пытается проксировать** (а не отдаёт SPA-fallback `200`). Если вернулось `200` — proxy НЕ сработал, проверь `nginx.conf`.

- [ ] **Step 4: Остановить контейнер**

```bash
docker rm -f regui-test
```

### Task 9: Коммит и пуш GUI-репо

**Files:** все созданные/скопированные в `recomendationenginegui`.

- [ ] **Step 1: Закоммитить**

```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/recomendationenginegui
git add -A
git status
```
Expected в `git status`: добавлены `Dockerfile`, `nginx.conf`, `.gitlab-ci.yml`, `.gitignore`, `.dockerignore`, `README.md`, `package.json`, `package-lock.json`, `postcss.config.js`, `tailwind.config.js`, `tsconfig.json`, `public/`, `src/`. **Нет** `node_modules/`, `build/`, `.playwright-cli/`.

```bash
git commit -m "initial: admin GUI extracted from recomendationengine

Static CRA bundle served by nginx; nginx reverse-proxies /api to the
recommendationengine k8s service in the same namespace. CI via shared
frontend-pipeline.yml."
```

- [ ] **Step 2: Запушить ветку**

```bash
git push -u origin task-gui-split
```
Expected: ветка создана в origin; в GitLab стартует пайплайн `frontend-pipeline` (task-ветка → build всегда, deploy — manual).

---

## ФАЗА 2 — Очистить движок (`recomendationengine`)

> Выполнять ТОЛЬКО после успешной Фазы 1 (админка скопирована, собирается, запушена).

### Task 10: Ветка + удаление каталога `frontend/`

**Files:**
- Delete: `platform-new/recomendationengine/frontend/` (весь каталог)

- [ ] **Step 1: Создать ветку**

```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/recomendationengine
git checkout -b task-drop-frontend
```
Expected: `Switched to a new branch 'task-drop-frontend'`.

- [ ] **Step 2: Удалить `frontend/`**

```bash
git rm -r frontend
```
Expected: список удалённых файлов (`frontend/package.json`, `frontend/src/...` и т.д.).

### Task 11: Почистить `.gitignore` движка

**Files:**
- Modify: `platform-new/recomendationengine/.gitignore`

- [ ] **Step 1: Удалить секцию Frontend**

Найти и удалить целиком этот блок в конце файла:
```gitignore
# Frontend
node_modules/
frontend/build/
```
Expected после правки: в `.gitignore` больше нет упоминаний `frontend/` и `node_modules/`.

### Task 12: Убрать `frontend-*` цели из `Makefile`

**Files:**
- Modify: `platform-new/recomendationengine/Makefile`

- [ ] **Step 1: Убрать frontend-цели из `.PHONY`**

Заменить строку:
```makefile
.PHONY: help build run dev test test-coverage clean deps-tidy pg-up pg-down docker-build docker-run frontend-install frontend-dev frontend-build
```
на:
```makefile
.PHONY: help build run dev test test-coverage clean deps-tidy pg-up pg-down docker-build docker-run
```

- [ ] **Step 2: Удалить три target-блока в конце файла**

Удалить целиком:
```makefile
frontend-install: ## Установить зависимости админки
	cd frontend && npm install

frontend-dev: ## Запустить админку (CRA dev server :3000)
	cd frontend && npm start

frontend-build: ## Собрать production-бандл админки
	cd frontend && npm run build
```

- [ ] **Step 3: Проверить, что в Makefile не осталось frontend**

```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/recomendationengine
grep -n frontend Makefile; echo "exit=$?"
```
Expected: нет совпадений (`exit=1`).

### Task 13: Заменить `.gitlab-ci.yml` на shared golang-backend-pipeline

**Files:**
- Modify (overwrite): `platform-new/recomendationengine/.gitlab-ci.yml`

- [ ] **Step 1: Перезаписать `.gitlab-ci.yml`**

> Заменяет текущие самописные стадии (backend-test/frontend-test/backend-build/frontend-build) на тот же shared-шаблон, что использует `intgateway`. Frontend-стадии больше не нужны — фронт уехал в отдельный репо.

`platform-new/recomendationengine/.gitlab-ci.yml`:
```yaml
variables:
  DOMAIN_SERVICE: "go"

include:
- project: 'greensight/gj/devops/gitlab-ci'
  ref: master
  file:
  - golang-backend-pipeline.yml
```

### Task 14: Обновить `README.md` движка

**Files:**
- Modify: `platform-new/recomendationengine/README.md`

- [ ] **Step 1: Изменить строку про стек фронта**

Заменить строку в разделе «## Стек»:
```markdown
- **Frontend (админка):** React 18 + TypeScript + CRA + Tailwind.
```
на:
```markdown
- **Админка** вынесена в отдельный репозиторий [`recomendationenginegui`](https://gitlab.gloria.aaanet.ru/greensight/gj/go/recomendationenginegui) (React 18 + TS + CRA, nginx-proxy на этот сервис).
```

- [ ] **Step 2: Убрать `frontend/` из дерева структуры**

В блоке «## Структура» удалить строку:
```
├── frontend/               # React-админка: SimilarStrategy + витрина + фид
```

- [ ] **Step 3: Удалить раздел быстрого старта фронта**

Удалить целиком блок:
```markdown
### 2. Frontend (админка)

​```bash
make frontend-install
make frontend-dev          # http://localhost:3000 (proxy → :8080)
​```
```
(и поправить нумерацию: «### 3. Docker» → «### 2. Docker», «### 1. Backend + БД» остаётся).

- [ ] **Step 4: Убрать typecheck фронта из раздела тестов**

В разделе «## Тесты» удалить строку:
```
cd frontend && npx tsc --noEmit
```

- [ ] **Step 5: Проверить README**

```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/recomendationengine
grep -n "frontend\|make frontend\|:3000" README.md; echo "exit=$?"
```
Expected: единственное допустимое совпадение — ссылка на репозиторий `recomendationenginegui`. Никаких `make frontend-*`, `cd frontend`, `:3000`.

### Task 15: Обновить `AGENTS.md` движка

**Files:**
- Modify: `platform-new/recomendationengine/AGENTS.md`

- [ ] **Step 1: Убрать frontend-строки из чеклиста**

В таблице «Обязательный чеклист» удалить строки шагов 3 и 5:
```
| 3 | Typecheck frontend | Правки `frontend/src/**` | `cd frontend && npx tsc --noEmit` |
```
```
| 5 | **Перезапуск frontend** | Правки `frontend/src/**`, `package.json` | `make frontend-dev` (или restart-dev.sh frontend) |
```
Перенумеровать оставшиеся шаги (1,2,4,6 → 1,2,3,4) и в строке отчёта убрать упоминание frontend `:3000`:
заменить
```
| 6 | Отчёт | Всегда | Явно: build/vet/test OK, backend `:8080` и frontend `:3000` перезапущены (или что не трогалось) |
```
на
```
| 4 | Отчёт | Всегда | Явно: build/vet/test OK, backend `:8080` перезапущен (или что не трогалось) |
```

- [ ] **Step 2: Убрать строку перезапуска фронта из блока restart**

Удалить строку:
```
./scripts/restart-dev.sh frontend    # kill :3000 + npm start
```

- [ ] **Step 3: Убрать frontend-строки из таблицы «Где что»**

Удалить строки:
```
| Админка (React) | `frontend/src/pages/SimilarStrategy*.tsx` |
```
```
| Витрина (React) | `frontend/src/pages/SimilarShowcase.tsx` |
```

- [ ] **Step 4: Добавить пометку про вынесенную админку**

В раздел «## Границы сервиса (важно)» добавить пункт:
```
- **Админка вынесена** в репозиторий `recomendationenginegui` (nginx-proxy `/api/` на этот сервис). Здесь — только Go-движок; фронт не трогаем отсюда.
```

- [ ] **Step 5: Проверить AGENTS.md**

```bash
grep -n "frontend\|:3000\|restart-dev.sh frontend" AGENTS.md; echo "exit=$?"
```
Expected: упоминаний `frontend/`-путей и `:3000` не осталось (допустимо только имя репо `recomendationenginegui`).

### Task 16: Верификация движка после удаления фронта

**Files:** —

> Напоминание: **всегда** `GOWORK=off` (см. Pre-flight).

- [ ] **Step 1: Build**

```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/recomendationengine
GOWORK=off go build ./...
```
Expected: без ошибок (удаление `frontend/` не влияет на Go — фронт не эмбедился).

- [ ] **Step 2: Vet**

```bash
GOWORK=off go vet ./...
```
Expected: без ошибок.

- [ ] **Step 3: Тесты — сверка с базлайном**

```bash
GOWORK=off go test ./... 2>&1 | grep -E "^(ok|FAIL|---)" 
```
Expected: тот же набор, что в базлайне — все пакеты `ok`, **кроме** одного пред-существующего фейла `internal/handlers` (`TestAdminStrategy_GetStrategy_returnsDefaults`). **Критерий приёмки: НЕТ НОВЫХ упавших пакетов/тестов** относительно Pre-flight базлайна. Если упал кто-то ещё — это регресс от правок, разбираться (хотя правки не трогали Go-код, кроме удаления каталога фронта).

- [ ] **Step 4: Подтвердить, что `docker-compose.yml` не ссылается на фронт**

```bash
grep -n "frontend\|:3000" docker-compose.yml; echo "exit=$?"
```
Expected: нет совпадений (`exit=1`) — в compose только `postgres` + `app`, правок не требуется.

- [ ] **Step 5: Docker-сборка движка**

```bash
docker build -t recomendationengine:test .
```
Expected: образ собирается (Dockerfile не менялся; `CGO_ENABLED=1`, debian-slim).

- [ ] **Step 6: Smoke публичного API (опционально, требует БД)**

```bash
make pg-up
make run &   # поднимется на :8080, прогонит миграции, подтянет фид
sleep 8
curl -s -o /dev/null -w "health=%{http_code}\n" http://localhost:8080/health
# найдите любой артикул из загруженного фида в логах/БД и подставьте <id>:
# curl -s "http://localhost:8080/api/v1/client/products/<id>/similar" | head
kill %1 2>/dev/null; make pg-down
```
Expected: `health=200`. (Шаг можно пропустить, если нет Docker/БД — он не меняет код.)

### Task 17: Коммит и пуш движка

**Files:** изменённые в `recomendationengine`.

- [ ] **Step 1: Закоммитить**

```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/recomendationengine
git add -A
git status
```
Expected: удалён `frontend/` (много `deleted:`), изменены `.gitlab-ci.yml`, `Makefile`, `.gitignore`, `README.md`, `AGENTS.md`. `Dockerfile` НЕ изменён.

```bash
git commit -m "chore: extract admin GUI to separate repo (recomendationenginegui)

Remove frontend/ (moved to recomendationenginegui), drop frontend Make
targets and gitignore section, switch CI to shared golang-backend-pipeline,
update README/AGENTS. Dockerfile unchanged (sqlite still drives tests/local)."
```

- [ ] **Step 2: Запушить ветку**

```bash
git push -u origin task-drop-frontend
```
Expected: ветка в origin; стартует пайплайн `golang-backend-pipeline` (build; deploy — manual).

---

## ФАЗА 3 — Хендофф devops / координация (НЕ код, зафиксировать в MR/тикете)

Это не задачи на правку кода, а пункты, которые исполнитель должен явно вынести в описание MR / тикет, чтобы devops смогли развернуть оба сервиса:

- [ ] **Helm-values для GUI.** Подтвердить с devops, что заведён путь values `go/recomendationenginegui/` (или поправить `DOMAIN_SERVICE` в `recomendationenginegui/.gitlab-ci.yml` под их домен-каталог). `DEPLOY_SERVICE = recomendationenginegui` (имя проекта).
- [ ] **Имя k8s-Service движка.** `nginx.conf` админки проксирует на `http://recommendationengine:8080`. Убедиться с devops, что k8s-Service движка в том же namespace называется `recommendationengine` и слушает `8080`. Если имя иное — либо devops приводят Service к этому имени, либо параметризуем upstream через `envsubst` в entrypoint (отдельная мелкая правка).
- [ ] **npm-registry в CI.** Сборка GUI делает `npm ci` внутри Kaniko. Если в CI нет доступа к публичному npm-registry (по аналогии с `GOPROXY`-nexus у go-сборок) — согласовать с devops nexus-проксю и при необходимости добавить `.npmrc` в репо GUI.
- [ ] **Раздельные ingress'ы.** Публичный `/api/v1/client/*` движка нужен IntGateway (server-to-server, внутри кластера) — отдельно от ingress админки. Не публиковать админский `/api/admin/*` наружу без защиты (см. follow-up auth).

---

## Follow-ups (вне scope этого плана — НЕ выполнять здесь)

1. **Auth на `/api/admin/*`** движка (сейчас открыт) — до prod-публикации админки.
2. **Удаление sqlite + CGO-free/distroless** сборка движка (тесты → Postgres/testcontainers, снос `rewriteSQLiteJSON`/SQLite-миграций/parity-тестов) — приведение к канону флота.
3. **Починка пред-существующего `TestAdminStrategy_GetStrategy_returnsDefaults`** (дрейф дефолтов `category_leaf`).
4. **Интеграция реального `RecommendationSource` в IntGateway** (замена `stubSource` на HTTP-клиент к публичному API движка) — отдельный цикл; хидратор `CatalogCacheHydrator` уже реальный.
5. **Опционально:** переименование Go-модуля `gj-similar` → канонический путь группы.

---

## Definition of Done

- [ ] `recomendationenginegui` содержит фронт в корне + `Dockerfile`/`nginx.conf`/`.gitlab-ci.yml`/`.gitignore`/`.dockerignore`/`README.md`; `npm ci && CI=false npm run build && npx tsc --noEmit` зелёные; `docker build` ок; контейнер отдаёт статику (`200` на `/`) и проксирует `/api` (`502` без апстрима standalone); ветка `task-gui-split` запушена, пайплайн `frontend-pipeline` стартовал.
- [ ] `recomendationengine` без `frontend/`; `GOWORK=off go build/vet` зелёные; `go test` без НОВЫХ фейлов относительно базлайна; `docker build` ок; CI переключён на `golang-backend-pipeline`; README/AGENTS/Makefile/.gitignore почищены; ветка `task-drop-frontend` запушена.
- [ ] Пункты Фазы 3 вынесены в MR/тикет для devops.
