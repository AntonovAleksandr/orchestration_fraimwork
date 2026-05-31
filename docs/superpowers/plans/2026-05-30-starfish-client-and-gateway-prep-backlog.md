# Backlog для другой сессии: `starfish-oms` client + ecom-gateway → checkout

**Дата:** 2026-05-30
**Назначение:** набор работ, который Zak отдаёт агентам в отдельной сессии. НЕ для исполнения здесь.
**Связанное:** дизайн checkout — `docs/superpowers/specs/2026-05-29-checkout-service-design.md`; контракт OMS — `docs/research/2026-05-29-order-create-contract.md`; dev-доступ + фикстуры — `platform-new/checkout/docs/dev/stage-access.md`.

---

## 0. Допущение и развилка (подтвердить перед стартом)

**Рамка (дизайн-консистентная):**
- `site/mobile → ecom-gateway (тонкий BFF) → checkout → OMS`. **OMS зовёт `checkout`, не gateway.**
- **`starfish-oms` client** → потребитель **`checkout`** (переиспользуемый пакет группы `clients`).
- **ecom-gateway** в OMS не ходит. Его prep к checkout = новый bounded-домен `checkout` (прокси/BFF) + `clients/checkout` (east-west к сервису checkout) + auth-контур. **`starfish-oms` ему не нужен.**

**Если иное** (gateway сам ходит в OMS) — Track B меняется; сообщить до старта.

**Топология (как у catalog-cache / ADR-0008/0009):**
```
go-pkg/gj-go-httpclient                      — generic substrate (есть)
e-commerce/platform/clients/catalog-cache    — образец (v0.1.0)
e-commerce/platform/clients/starfish-oms     — НОВЫЙ (Track A)
e-commerce/platform/clients/checkout         — НОВЫЙ, позже (Track B), east-west gateway→checkout
```
Локально: `platform-new/clients/<name>` (независимые git-репо; Buddy-стиль — чистый `require vX` без replace, резолв по GOPRIVATE+SSH/Nexus).

### Полный флот клиентов checkout + ИСТОЧНИК вывода («база» — существующие PHP-клиенты)

Принцип: сервисы общаются в контуре **напрямую** (east-west), BFF (ecom-gateway) — только для фронта. Go-клиенты **выводим из существующих контрактов**, не изобретаем:

| Go-клиент `clients/*` | Потребитель | Источник вывода | Тип |
|---|---|---|---|
| `catalog-cache` ✅ | gateway, checkout | (есть) ENSI catalog-cache OpenAPI / Integration `CatalogClient` | generated REST |
| **`starfish-oms`** | checkout | Integration **`OmsClient`+`OmsClientV2`** + `apidoc.starfish24.com` + фикстуры `oms/*.json` | generated REST (нет OpenAPI в репо → faithful по клиенту) |
| **`checkout`** | gateway | OpenAPI самого checkout (§3 дизайна) | generated REST |
| `baskets` | checkout | **ENSI baskets OpenAPI** `apps/orders/baskets/public/api-docs/v1` + `packages/baskets-client-php` | generated REST (ENSI OpenAPI-first) |
| `customers` | checkout | **ENSI customers OpenAPI** `apps/customers/customers/public/api-docs/v1` + `packages/customers-client-php` | generated REST |
| `offers` | checkout | ENSI offers OpenAPI + `packages/offers-client-php` | generated REST |
| `bu` (business-units) | checkout | ENSI bu OpenAPI + `packages/bu-client-php` (магазины/регионы/город) | generated REST |
| `discount` (discount service / сервер скидок) | checkout | Integration **`DiscountClient`** + WWWDKMVC `Models/4.x` (XML-схемы) | **ОСОБЫЙ: legacy XML** `/api/Query` (RequestType), rotating-`word` auth, quote/spend двухфазно — НЕ oapi-codegen |

**Стратегия вывода:**
- **ENSI-клиенты** (`baskets`/`customers`/`offers`/`bu`): ENSI **OpenAPI-first** → генерим Go-клиент из `public/api-docs/v1` сервиса (faithful subset нужных эндпоинтов), `*-client-php` — как cross-check семантики.
- **`starfish-oms`**: OpenAPI в репо нет → faithful по рукописным `OmsClient`/`OmsClientV2` (эндпоинты/тела/auth) + `apidoc.starfish24.com` + реальные фикстуры.
- **`discount`** (discount service): legacy XML — отдельный клиент по образцу `DiscountClient` (XmlHelper, RequestType 1/17/21/30), НЕ generated; quote (`GetDiscount`) + spend (`BonusSpend(Ext)`, idemp по `DOC`), rotating-`word` auth.

Прочие клиенты Integration (`OtsClient`, `PriceClient`, `Ecom1CClient`, `DwhClient`, `AsmClient`, `CB1CRetailClient`, `WebGjISmpClient`) — для checkout **не нужны** (1C/DWH/ОTS/ASM вне его контура).

**Очередь сборки клиентов:** `starfish-oms` (сейчас, Track A) → по мере фазы 2 checkout: `baskets`, `customers`, `offers`, `bu`, `discount`. `checkout`-client (Track B) — после контракта checkout.

---

## TRACK A — `starfish-oms` client (можно стартовать сейчас, независимо от checkout)

Образец паттерна — `catalog-cache` client: тонкий клиент + split OpenAPI (consumer-defined, faithful subset) → generated **types-only** oapi-codegen → ошибки через substrate `gj-go-httpclient`. **DTO заземляем на реальные фикстуры stage** (`platform-new/checkout/fixtures/oms/*.json`).

| ID | Работа | Вход / референс | DoD | Агент |
|----|--------|-----------------|-----|-------|
| **A0** | Repo + skeleton пакета `clients/starfish-oms` (go.mod, layout как catalog-cache, dep на gj-go-httpclient, replace для dev) | catalog-cache client; ADR-0008/0009 | `go build` зелёный, пустой клиент компилится | go-expert-coder |
| **A1** | Split OpenAPI (faithful subset) под нужные эндпоинты, **с квирками** | фикстуры `oms/*.json`; `apidoc.starfish24.com`; Integration `OmsClient`/`OmsClientV2` | `redocly lint` clean; bundle собирается | go-expert-coder |
| **A2** | Generated DTO (types-only) из bundle + тонкие методы клиента | A1 | типы сгенерены, drift-gate `go generate` | go-expert-coder |
| **A3** | Транспорт/конфиг: **два base URL** (`api-gateway/v1` + `api-gateway-v2/v2`), Bearer-токен, заголовок `X-Target-Endpoint`, trace-id, таймауты | stage-access.md; substrate opts | методы бьют в правильный gateway+префикс | go-expert-coder |
| **A4** | Маппинг ошибок: OMS Spring-envelope (`{timestamp,status,error,path}`) → substrate sentinels (`ErrUpstream/ErrBadRequest/…`) | substrate Error model | табличные тесты статус→sentinel | go-expert-coder |
| **A5** | Фикстурные тесты декодирования (golden) — верность форм + квирки | `oms/*.json` → `testdata/` | decode без потерь; квирки покрыты | go-test-strategist |
| **A6** | README + версия `v0.1.0` (tag), publish | catalog-cache README | тег запушен, `go get` работает | go-expert-coder |

### Эндпоинты в скоупе A (приоритет — то, что нужно checkout-resolver’у фазы 2)
**Сначала read/logistics+city (для delivery resolver):**
- v2 `/logistics/delivery-preliminary` (POST; body `{addressTo.city, cart.items[], systemSettings.returnStock}`)
- v2 `/logistics/pickup-stores/v1` (POST; **ответ — голый массив**)
- v2 `/logistics/pickup-points` (POST; **+ `areaViewPort` bbox** — для карты; `/v1` без bbox НЕ использовать на карте)
- v2 `/logistics/delivery-intervals` (POST; курьер; `intervals.list[].id` — **хэш**, слоты `from/to`)
- v1 `/city/goldenrecord` (GET `?name=|goldenRecordId=|fiasId=`), `/suggestion/city`
**Потом write (для commit):**
- v1 `/order/create` (POST; см. контракт-док), `/onlinepay/{clientOrderId}/getlink`

### Квирки, которые DTO/клиент ОБЯЗАН учесть (из реальных ответов)
- **base path с префиксом** `/v1` и `/v2` (без него gateway → 404).
- `pickup-stores/v1` отдаёт **голый массив**, `delivery-preliminary`/`delivery-intervals` — `{data:[…]}`.
- поле-опечатка **`cartAvailabillity`** (две `l`) в delivery-intervals — оставить как есть.
- interval/ПВЗ **`id` = 8-симв. хэш** (детерминирован, но плывёт на границе picking-волны/суток).
- `instock` (магазины/ПВЗ) vs `inventory.availableQuantity` (курьер) vs `cart.items[].stock[]` (preliminary) — **3 разные формы coverage** «X из N».
- ПВЗ-флаги `orderDimensions/Weight/PackageWeightExceeded`; перевозчики ПВЗ: 5post/russianpost/cdek/dpd/yandex.
- масштаб: один `pickup-points` Москвы = **3963 точки / 3.5 МБ** → bbox обязателен.
- auth: статичный Bearer (`OMS_SERVICE_CLIENT_ACCESS_TOKEN`), без OAuth-флоу.

> **NB:** клиент = faithful-обёртка OMS. **Нормализация 3 форм в одну `Komplektaciya`** — это НЕ задача клиента, а resolver’а внутри `checkout` (§2c дизайна). Клиент отдаёт сырые пер-эндпоинтные DTO.

---

## TRACK B — ecom-gateway → checkout onboarding (ПОЗЖЕ; зависит от контракта checkout v1)

ecom-gateway сейчас = 1 домен (`recommendations`). Подготовить к добавлению checkout. **Блокер:** нужен стабильный API-контракт `checkout` (§3 дизайна) — поэтому Track B стартует после фиксации контракта (можно по OpenAPI checkout, не дожидаясь полной реализации).

| ID | Работа | Вход / референс | DoD | Агент |
|----|--------|-----------------|-----|-------|
| **B1** | Новый bounded-context `checkout` в ecom-gateway (handler/service/routes/types по code-organization-contract) | ecom-gateway code-organization-contract; §3 дизайна | boundary_test зелёный, домен изолирован | go-expert-coder |
| **B2** | `clients/checkout` — generated client (gateway→checkout, east-west) на substrate | OpenAPI checkout (§3); catalog-cache паттерн | клиент компилится, методы под §3 | go-expert-coder |
| **B3** | Проводка `wire_checkout.go` + config (`CHECKOUT_BASE_URL`) + `/ready` чекает checkout | ecom-gateway wire_recommendations | switch real/stub, ready-проба | go-expert-coder |
| **B4** | **Auth-контур gateway (edge) — переезд auth из customers-api-web сюда.** (1) валидация **customer-Bearer** (через ENSI `customer-auth`); (2) **guard’ы per-endpoint** (что требует логина, что можно гостю); (3) gateway САМ резолвит `customer_id` из токена и **прокидывает доверенную identity** (`X-Customer-Id`/inject), checkout ей доверяет; (4) **anti-IDOR**: НЕ доверять `customer_id` из клиентского тела. | дизайн §2 (auth_context); ENSI customer-auth; стек ecom-gateway | без токена 401; с токеном identity доходит до checkout; чужой customer_id невозможен | go-expert-coder + architect |
| **B5** | Решить стиль прокси: тонкий pass-through vs BFF-агрегация (checkout уже отдаёт фронт-готовые формы → вероятно тонкий) | §3 (контракт фронт-готовый) | ADR/решение зафиксировано | architect |
| **B6** | Тесты сквозные gateway→checkout на стабе + boundary | B1-B3 | сквозной 200 на стабе | go-test-strategist |

> **Auth-контур (важно, проверено 2026-05-31 на stage).** Edge-авторизация переезжает из `customers-api-web` в **ecom-gateway** (новый публичный вход фронта). Три токен-контекста, не путать: фронт→gateway = **customer-Bearer** (валидирует gateway через customer-auth); checkout→**OMS** = **сервисный** Bearer (`OMS_SERVICE_CLIENT_ACCESS_TOKEN`, не customer); checkout→**ENSI** = **без auth** (east-west, доверие по сети); checkout→**discount** = rotating-word+md5 (в клиенте). checkout сам customer-auth НЕ проверяет — доверяет identity от gateway. Требования: (а) checkout берёт `customer_id` ТОЛЬКО из доверенного источника (gateway-inject), НЕ из клиентского тела — иначе IDOR (правка контракта checkout фазы 2: убрать `customer_id` из публичного `CreateCheckoutRequest`, брать из `X-Customer-Id`); (б) **сетевая изоляция** — checkout доступен только через gateway (иначе доверенный заголовок спуфится) — инфра-требование.

---

## Последовательность / зависимости

```
A (starfish-oms client)  ──── независим, СТАРТ СЕЙЧАС ──── publish v0.1.0
                                                              │
checkout v1 (writing-plans, отдельно) ── контракт §3 ─┐       │ (фаза 2 checkout импортит A)
                                                       ▼
                                          B (gateway→checkout)  ── после контракта checkout
```
- **A** ни от чего не зависит (фикстуры есть) → отдать агентам сразу.
- **checkout v1** (walking skeleton) — отдельный план (`/writing-plans`), стабы вместо A.
- **A интегрируется в checkout** в фазе 2 (замена стаб-`DeliverySource`/`OrderSink` на реальные адаптеры поверх `starfish-oms`).
- **B** — после стабилизации контракта checkout (§3 / его OpenAPI).

## Общие правила для агентов
- Стандарт: `go-service-guideline` + ADR ecom-gateway (0002 chi, 0008/0009 client fleet). Эталон — `catalog-cache` client + `gj-buddy-server`.
- Каждый клиент: тонкий, faithful, types-only oapi-codegen, ошибки через substrate, фикстурные тесты, README, semver-tag.
- Dev-доступ к OMS (port-forward на stage) — `platform-new/checkout/docs/dev/stage-access.md`. Курированные фикстуры → `testdata/` соответствующего клиента.
- Секреты (токен) — только из k8s-секрета/`.env` (gitignored), не в код/тесты.
