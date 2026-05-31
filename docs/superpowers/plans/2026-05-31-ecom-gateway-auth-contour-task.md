# Задача: Auth-контур (сессия покупателя) для ecom-gateway

**Дата:** 2026-05-31 · **Кому:** разработчик ecom-gateway · **Тип:** реализация (с ADR по развилке)

## 0. Репозиторий и окружение (читать первым — чтобы не плутать по путям)
- **Где код:** ecom-gateway = отдельный gitlab-репо **`e-commerce/platform/ecom-gateway`** (branch `main`). Для задачи достаточно склонировать ТОЛЬКО его. Коммитить — в нём.
- **Про `platform-new/`:** это локальная папка-агрегатор new-платформы GJ (gateway + `checkout` + `clients/*` + go-pkg libs), у каждого подкаталога — **свой** gitlab-репо. Она **gitignored** в workspace-репо `GJ-Ecommerce` (development-platform) и не обязательна: если работаешь только над gateway — клонируй его репо отдельно, `platform-new` не нужен.
- **Окружение Go (Buddy-стиль, обязательно — иначе приватные модули не резолвятся):**
  `go env -w GOPRIVATE='gitlab.gloria.aaanet.ru/*'` + глобальный git `insteadOf` (`git config --global url."ssh://git@gitlab.gloria.aaanet.ru/".insteadOf "https://gitlab.gloria.aaanet.ru/"`) + (в сети GJ) Nexus `GOPROXY`. **Без `replace`/`go.work`** — чистый `require vX`.
- **Эталоны:** сервис/резолв — **`gj-buddy-server`**; клиент (если понадобится `clients/customer-auth`) — **`e-commerce/platform/clients/catalog-cache`**; ADR ecom-gateway — в `<ecom-gateway>/docs/architecture/adr/`.
- **Самодостаточность:** ссылки на `docs/...` (в meta-репо GJ-Ecommerce) и `platform-new/checkout/docs/...` (в репо `checkout`) — **дополнительные**; всё нужное для этой задачи инлайнено ниже, доку можно выполнять без доступа к ним.

## Контекст
`ecom-gateway` — новый публичный **BFF** (Go, net/http + chi) для site/mobile; постепенно заменяет/дублирует ENSI `customers-api-web` как **edge**. За ним — внутренний контур: `checkout` и др. домены.

Сегодня авторизацию покупателя проверяет **`customers-api-web`** через ENSI **`customer-auth`** (`laravel/passport`, OAuth2 — токен это **подписанный JWT**, + `corbosman/laravel-passport-claims` с кастом-клеймами, в т.ч. идентификатор покупателя). Внутренние ENSI-сервисы (baskets/customers/offers/bu/catalog-cache) auth **не требуют** (east-west, доверие по сети); проверка — на edge.

**Цель:** edge-авторизация переезжает в ecom-gateway — он валидирует customer-Bearer, ставит guard'ы на эндпоинты, резолвит личность покупателя и прокидывает её доверенным каналом во внутренние сервисы.

## Три токен-контекста (не путать)
| Канал | Токен | Кто проверяет |
|---|---|---|
| фронт → **ecom-gateway** | **customer-Bearer** (Passport OAuth2 JWT) | **ecom-gateway** (эта задача) |
| checkout/домены → **OMS** | **сервисный** Bearer (`OMS_SERVICE_CLIENT_ACCESS_TOKEN`) | OMS api-gateway |
| checkout/домены → **ENSI** | — нет | — |
| checkout → **discount** | rotating-word + md5 | сам discount-клиент |

## Требования (scope)
1. **Валидация customer-Bearer** (Passport JWT): подпись, `exp`, issuer/audience, scope; извлечь `customer_id` из claim. Реализация — см. «Развилка» ниже.
2. **Identity propagation:** gateway резолвит `customer_id` (+ нужные claims) и прокидывает downstream **доверенным каналом** — заголовок `X-Customer-Id` (или typed reqctx → исходящий заголовок). Внутренние сервисы ему доверяют. Положить identity в `internal/platform/reqctx` + логи/трейс.
3. **Guards per-endpoint — ТРИ тира** (декларативно на роут):
   - **public** — отвечает всем (suggest города и т.п.);
   - **auth-optional / anonymous-ok** — отвечает анониму **degraded** (без customer-данных), обогащает если авторизован (get-checkout, delivery-options, delivery-cost, ПВЗ/карта);
   - **auth-required** — без валидного auth → **401** (commit/create-order, recipient из customers, бонусы, сохранённые адреса).
   **🔴 «нет токена» ≠ «битый токен»:**
   - нет заголовка `Authorization` → аноним: optional → degraded, required → **401**;
   - `Authorization` есть, но протух/невалиден → **401 ВСЕГДА** (в т.ч. на optional!) — чтобы фронт пошёл в refresh (legacy BFF) и получил обогащённый ответ. **Молчаливый downgrade залогиненного до анонима запрещён.**
   - нет прав/scope → **403**.
4. **🔴 Anti-IDOR:** downstream НЕ принимает `customer_id`/идентичность из **клиентского тела** — только gateway-inject из токена. (Следствие: `checkout` уберёт `customer_id` из публичного `CreateCheckoutRequest` и возьмёт из `X-Customer-Id` — фаза 2 checkout.)
5. **Guest-flow + корзина:** гость идентифицируется **`deviceId`** (генерит фронт); авторизован — `customerId` из токена. На optional-ручки gateway прокидывает корзинный ключ: гость → `deviceId` (из запроса), authed → `customerId` (из токена). Превью доставки/ПВЗ — гостю да; commit — требует авторизации.
   - **Мерж корзин (гость→юзер) — НЕ наша зона:** алгоритм в ENSI `baskets` (`MergeBasketsAction`, эндпоинт `baskets customer:merge`), триггер на логине оркеструет **legacy BFF** (в текущей фазе login там). Gateway/checkout мерж НЕ реализуют — потребляют уже смерженную корзину. Integration к мержу отношения НЕ имеет.
   - **⚠️ checkout-дизайн:** логин ПОСРЕДИ чекаута (аноним→юзер) → корзина меняется (мерж) → снапшот корзины в сессии пере-снять (дополнение к «snapshot при входе + ре-валидация на commit»: ре-резолв при смене identity).
6. **Ошибки:** единый envelope; 401/403 семантика; не протекают внутренние детали.
7. **🔴 Сетевая изоляция (инфра-требование):** checkout и внутренние сервисы доступны **только через gateway**; прямой внешний доступ закрыт — иначе `X-Customer-Id` спуфится. Зафиксировать в деплое/неймспейсе/네тполиси.

## Развилка (нужно ADR) — как валидировать + нужен ли auth-client
- **A. Локальная JWT-проверка (рекомендуется для BFF):** gateway верифицирует подпись Passport-JWT публичным ключом customer-auth (`oauth-public.key`/JWKS, в конфиге), читает claims. **Без сети на запрос, auth-client НЕ нужен.** Минус: не ловит отзыв токена в середине жизни → компенсируется коротким TTL.
- **B. Удалённая валидация/интроспекция:** gateway зовёт customer-auth (нужен **Go `clients/customer-auth`** — часть флота `clients/*`, на substrate `gj-go-httpclient`, faithful по OpenAPI customer-auth). Ловит revocation; цена — сетевой вызов на запрос (кэшируемый).
- **Когда auth-client ОБЯЗАТЕЛЕН:** если gateway сам берёт на себя **auth-флоу** (login/refresh/logout/регистрация), а не только валидацию. Тогда `clients/customer-auth` нужен независимо от A/B.
- **Решение зафиксировать ADR** (local vs remote; владеет ли gateway login-флоу).

### Фаза постепенной миграции (текущая) — выбор A, auth-client НЕ нужен
Фронт сначала ходит в gateway лишь за частью методов (get-checkout, create-order и т.п.); **refresh/login остаются в legacy BFF**. Логика фронта: на **401** идёт в legacy refresh → новый токен → ретрай. Значит gateway **только валидирует** (вариант **A**, local JWT verify публичным ключом Passport) → **`clients/customer-auth` в этой фазе НЕ нужен**. Он понадобится позже, только если login/refresh переедут в gateway.

## Стек / конвенции
- ecom-gateway: Go, net/http + chi; ADR-0002 (chi), 0003 (layout platform/domains), 0004 (OpenAPI), 0008/0009 (client fleet). Auth = middleware в `internal/platform/` (cross-cutting) либо отдельный auth-пакет.
- Источник истины по токену: ENSI `customer-auth` (laravel/passport) — его OpenAPI `public/api-docs/v1` + публичный ключ.
- Эталон клиента (если нужен B): `clients/catalog-cache` + `gj-buddy-server`. Резолв приватных модулей — GOPRIVATE + git insteadOf (Buddy-стиль), без replace.

## DoD
- Protected-эндпоинт: без токена → 401; невалидный/просроченный → 401; валидный → проходит, `customer_id` в reqctx и в `X-Customer-Id` downstream.
- `customer_id` downstream берётся ТОЛЬКО из токена (клиентское тело игнорируется) — тест на IDOR.
- Guards конфигурируемы per-route; гостевые ручки (если есть) работают без токена.
- Тесты: valid / invalid / expired / missing / guest / scope-fail; boundary-test пакета.
- ADR: local-JWT vs remote-introspection + владение login-флоу + нужен ли `clients/customer-auth`.
- Зафиксировано инфра-требование сетевой изоляции внутренних сервисов.

## Ссылки (опциональны — всё нужное инлайнено выше; репо указан у каждой)
- _[репо `checkout`]_ Auth-модель по зависимостям: `docs/dev/stage-access.md` (§Авторизация).
- _[репо `checkout`]_ Карта доменов: `docs/architecture/domain-map.md`.
- _[meta-репо GJ-Ecommerce]_ Backlog gateway↔checkout (B4): `docs/superpowers/plans/2026-05-30-starfish-client-and-gateway-prep-backlog.md`.
- _[meta-репо GJ-Ecommerce]_ Дизайн checkout §2 (auth_context зарезервирован): `docs/superpowers/specs/2026-05-29-checkout-service-design.md`.
- _[ENSI]_ Источник истины по токену: сервис `customer-auth` (`apps/customers/customer-auth`) — OpenAPI + публичный ключ Passport.
