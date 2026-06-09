# DevOps: разворачивание recomendationengine + recomendationenginegui (k8s) — задание

**Дата:** 2026-06-09
**Репозитории:**
- движок — `gitlab.gloria.aaanet.ru/greensight/gj/go/recomendationengine` (ветка `master`)
- админка — `gitlab.gloria.aaanet.ru/greensight/gj/go/recomendationenginegui` (ветка `master`)

Оба репо уже подключают shared GitLab-CI (`greensight/gj/devops/gitlab-ci`): движок — `golang-backend-pipeline.yml`,
админка — `frontend-pipeline.yml`. Kaniko собирает `Dockerfile` → registry → helm-upgrade per-env.
**От нас (кода) всё готово; нужны helm-values и Postgres.**

---

## 1. Два деплоя

| Сервис (`CI_PROJECT_NAME` = `DEPLOY_SERVICE`) | Что это | Порт контейнера | Образ |
|---|---|---|---|
| `recomendationengine` | Go-сервис «Похожие» (API), distroless, статический бинарь | **8080** | golang-backend-pipeline |
| `recomendationenginegui` | nginx: статика админки + reverse-proxy `/api` на движок | **80** | frontend-pipeline |

`DOMAIN_SERVICE: "go"` (задан в `.gitlab-ci.yml` обоих репо) → путь values:
`ms-helm-values/<env>/go/<DEPLOY_SERVICE>/<DEPLOY_SERVICE>.yaml` (+ `.sops.yaml` для секретов).
Развернуть на **всех стендах**: `gs-test`, `stage`, `prod`.

---

## 2. ⚠️ Критично: имя k8s-Service движка

Админка (nginx) жёстко проксирует `/api/*` на **`http://recommendationengine:8080`** (см. `nginx.conf`).
Значит k8s-**Service движка в том же namespace ДОЛЖЕН называться `recommendationengine`** и слушать порт **8080**.
(Имя сервиса в чарте задаётся через `web.service.name`/values — привести к `recommendationengine`.
Если по конвенции чарта имя получается иным — нужно либо алиас-Service `recommendationengine`,
либо мы параметризуем upstream в nginx через env; сообщите, что удобнее.)

**Порядок релизов:** Service движка должен существовать в namespace до/вместе со стартом пода админки —
иначе nginx админки падает с `host not found in upstream` и крутится в CrashLoop, пока Service не появится.

---

## 3. Postgres (нужно провижнить)

Движку нужна **выделенная БД PostgreSQL** на каждом стенде (SQLite удалён, фолбэка нет — без `DATABASE_URL`
сервис не поднимется осмысленно). Схема накатывается **автоматически при старте** (миграции в коде),
ручных миграций не нужно. Достаточно пустой БД + доступ.

---

## 4. ENV-переменные движка `recomendationengine` (главное)

| Переменная | Обяз. | Значение | Где (секрет?) |
|---|---|---|---|
| `DATABASE_URL` | **ДА** | строка подключения к провижненному PG, напр. `postgres://<user>:<pwd>@<host>:5432/<db>?sslmode=require` | **СЕКРЕТ → `*.sops.yaml`** (содержит пароль) |
| `GOMEMLIMIT` | **рекомендуется** | мягкий потолок кучи Go ≈ **0.7× memory limit пода** (напр. `1400MiB` при limit `2Gi`). Страховка GC во время фонового прогрева кэша. | values (не секрет) |
| `FEED_URL` | желательно явно | URL XML-фида товаров (источник данных). Дефолт в коде — GJ auto-merch CDN; задать явно/при необходимости per-env | values |
| `FEED_SYNC_INTERVAL` | опц. | период автозагрузки фида, напр. `1h`; `0` — выключить планировщик | values |
| `PORT` | нет | `8080` (дефолт; контейнер `EXPOSE 8080`) | — |

**Не задавать** (наследие, в коде не используются): `TEMPLATE_PATH`, `STATIC_PATH`, `DATABASE_PATH` (SQLite удалён).
`PROMETHEUS_APP_NAME` чарт проставляет сам (`<service>-master`).

### ENV админки `recomendationenginegui`
**Не требуются.** Образ = nginx + статика; всё проксирование зашито в `nginx.conf` (upstream `recommendationengine:8080`).
Per-env конфига у фронта нет (один образ на все стенды). Возможный открытый вопрос — доступен ли npm-registry
в Kaniko-сборке фронта (по аналогии с `GOPROXY`-nexus у go); если `npm ci` в сборке не достучится — нужен nexus-`.npmrc`.

---

## 5. Probes / ресурсы движка

- **Health:** `GET /health` → `200`. Образ distroless (нет shell) → пробы только `httpGet` (не `exec`):
  - readiness: `GET /health` :8080
  - liveness: `GET /health` :8080
- **Ресурсы (ориентир):** request `cpu: 500m, memory: 512Mi`; limit `cpu: 2, memory: 2Gi` + `GOMEMLIMIT=1400MiB`.
  Прогрев кэша считает ранжирование для всего каталога в фоне (2 воркера, ограниченная конкуренция);
  пиковая память на текущем каталоге ~единицы-сотни МБ, лимит 2Gi с запасом.
- **GUI:** статика, лёгкая; request `cpu: 50m, memory: 64Mi`, limit `cpu: 250m, memory: 256Mi`. Health: `GET /healthz` :80.

---

## 6. Ingress / доступ

- **Движок, публичный API** `/api/v1/client/products/.../similar` — потребитель IntGateway (вызов **внутри кластера** по Service,
  внешний ingress не обязателен; завести только если нужен прямой внешний доступ).
- **Админка** (GUI) — ingress для команды мерча. ⚠️ **Админ-API движка `/api/admin/*` сейчас без аутентификации** —
  не публиковать наружу без защиты (ingress basic-auth / ограничение по сети). Это известный gap, его закрытие — отдельной задачей.

---

## 7. Резюме «что сделать девопсу»

1. Провижнить Postgres-БД движку на `gs-test`/`stage`/`prod`.
2. Завести helm-values `ms-helm-values/<env>/go/recomendationengine/` с `DATABASE_URL` (в `.sops.yaml`), `GOMEMLIMIT`, `FEED_URL`, `FEED_SYNC_INTERVAL`; `recomendationenginegui` — без env.
3. Назвать k8s-Service движка **`recommendationengine`** (порт 8080) — обязательно для проксирования из админки.
4. httpGet-пробы (`/health` движок, `/healthz` GUI), ресурсы по п.5.
5. Обеспечить порядок: Service движка до пода админки.
6. Ingress: GUI — для мерча (с защитой админ-путей); публичный API движка — внутрикластерно для IntGateway.

**Вопросы к нам:** имя Service (`recommendationengine` или нужен алиас?), npm-registry в Kaniko для фронта.
