# ТЗ: ecom-gateway — починить JWT-verifier под РЕАЛЬНЫЕ claims Laravel Passport

**Статус:** готово к исполнению. Самодостаточно — весь нужный контекст ниже.
**Репозиторий:** `platform-new/ecom-gateway` (module `gj-ecom-gateway`).
**Причина:** auth-контур реализован под *выдуманные* claims (`iss`, `customer_id`, `aud=ecom-gateway`).
Реальные токены `customer-auth` (Laravel Passport / league/oauth2-server) их **не содержат** —
сейчас verifier зарубит в 401 **любой** боевой токен. Проверено на живом stage-токене и реальном ключе.

---

## 1. Доказательство (живые данные)

`customer-auth` = Laravel Passport + `CorBosman\Passport` (один кастомный claim `login_asm` = email).
league/oauth2-server **не вызывает `issuedBy()`** → `iss` отсутствует; идентификатор пользователя — `sub`.

Декодированный payload реального access-токена со stage:
```json
{
  "aud": "9881b222-0ef0-49bb-a3a8-5573e6ccde16",   // client UUID OAuth-клиента сайта (НЕ "ecom-gateway")
  "jti": "84b766ac22ef527897b0bad77378...",
  "iat": 1778670969.182551,                         // ⚠️ float (микросекунды) — golang-jwt v5 это переваривает
  "nbf": 1778670969.182554,
  "exp": 1781262969.176365,
  "sub": "4455421",                                 // ← ЭТО и есть customer_id
  "scopes": []
}
```
**Нет `iss`. Нет `customer_id`.** Заголовок: `{"typ":"JWT","alg":"RS256"}`.

---

## 2. Что менять

### 2.1 `internal/platform/authn/jwt.go` — `Verify()` и `NewVerifier()`
- **Идентификатор покупателя ← `sub`** (`claims.RegisteredClaims.Subject`), а не кастомное поле `customer_id`.
  В `passportClaims` поле `CustomerID string json:"customer_id"` **убрать** (оставить `Scopes []string json:"scopes"`).
- **Issuer:** `jwt.WithIssuer(...)` добавлять в опции, **только если `v.issuer != ""`**. У реальных токенов `iss` нет —
  жёсткая проверка всегда падает.
- **Audience:** убрать безусловный `jwt.WithAudience("ecom-gateway")`. Реальный `aud` = client-UUID.
  Добавлять `jwt.WithAudience(v.audience)`, **только если `v.audience != ""`** (по умолчанию — не enforce'ить).
  *(Опциональный hardening на будущее, НЕ в этой задаче: allowlist разрешённых client-UUID сайта/мобилки.)*
- **Обязательное оставить:** RS256 (reject не-RSA `alg`), `jwt.WithExpirationRequired()`, **непустой `sub`**
  (сейчас проверка `claims.CustomerID == ""` → заменить на проверку `claims.Subject == ""`).
- Возврат: `reqctx.CustomerIdentity{CustomerID: claims.Subject, Scopes: claims.Scopes}`.

`middleware.go` и `reqctx` **НЕ трогать** — они уже работают через `CustomerIdentity.CustomerID`,
маппинг `no-token→аноним / bad-token→401` корректен и должен сохраниться.

### 2.2 `internal/platform/config/config.go` — ослабить валидацию auth
- Сейчас all-or-nothing: «issuer требует key+audience». Поменять на: **auth включается одним наличием публичного ключа**
  (`CUSTOMER_AUTH_PUBLIC_KEY` или `CUSTOMER_AUTH_PUBLIC_KEY_FILE`). `CUSTOMER_AUTH_ISSUER` и
  `CUSTOMER_AUTH_AUDIENCE` — **опциональны** (пустые = не enforce'ить).
- Ключ не задан → `NewPassthroughGuards()` (как сейчас, для локалки без ключа). Это поведение сохранить.

### 2.3 Тесты `internal/platform/authn/*_test.go`
- Перевести фикстуры на реальную модель: токены без `iss`, identity по `sub`, `aud` не обязателен.
- Кейсы (сохранить намерение существующих + добавить):
  - валидный токен (RS256, есть `sub`, `exp` в будущем, **без `iss`/`customer_id`**) → identity с `CustomerID = sub`;
  - просрочен (`exp` в прошлом) → `ErrTokenExpired` → 401 `token_expired`;
  - битая подпись / `alg != RS*` (e.g. HS256/none) → `ErrTokenInvalid` → 401 `invalid_token`;
  - пустой `sub` → `ErrTokenInvalid`;
  - **float-таймстампы** `iat/exp` (как у Passport) → парсятся без ошибок;
  - issuer задан в конфиге, а в токене его нет → 401 (проверка работает, когда сконфигурена);
  - issuer/audience пусты в конфиге → не enforce'ятся (валидный токен проходит);
  - OptionalAuth: нет токена → проходит аноним (200); битый токен → 401 (не downgrade);
  - анти-IDOR: `CustomerID` берётся из токена (`sub`), а не из тела/заголовка запроса.

---

## 3. Реальный публичный ключ Passport (stage) — для wiring и фикстур

Источник: pod `customer-auth-master-ms-...`, ns `stage`, контейнер `php`, файл `/var/run/secrets/oauth-public.key`
(`PASSPORT_KEYS_PATH=/var/run/secrets`). Достаётся:
```bash
KUBECONFIG=<...> kubectl -n stage exec <customer-auth-master-ms-pod> -c php -- cat /var/run/secrets/oauth-public.key
```
Формат — PKIX/SPKI `PUBLIC KEY` PEM (то, что `NewVerifier`/`ParsePKIXPublicKey` уже умеет):
```
-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAyH85tESMD9JjT/TeMkeE
y0/qNWp2MCatWOD1puY1MqDBX6UP9Mg7chblr1LTEKcgr1h8lWM/9VekiOiE564p
qgiG+cNtaRi0AOd1KArnW8q/m/1nLEhM3+hmyYwwdXNceopSWaznuUoMHfPqBYeA
NsXCkcuDis+LSHK9SCu0bwxlt5kVTxBk64uUNjfYL3fBamsVaVZD6OHXBwCgRE+t
JSp0yxAjk93l3pG87cE/VtO00jraDyLJrLUAnIUkwgZHD2sCESLesPs1Bmwo8zuv
c8CKmHLHZ9KVgoicqBpIqzWYTCI4EN8bsHR9C6PaZYYH6mWCxjFdnfQXzMu7N8BT
N5uEGS0bD4ftKQx89a6dTgouxN4b+rOIaom3k6I3TtRDvXzFh/mGPP1zhtoNAGEy
Vd+BBMl81oJP6PosZRof/r0k8UjdrMOHTngOI6Tg41rjBjlER3xNKwKM5APCoy5B
x9/cDim1+WVyL4XojgMFXMMUERVfyVtcGHUiIid/NuJNz+J9+yojBKj2X0cdzE+2
Rvin0JeC5rzQEbC541wto96XWEff3vTeyBA712FduRrvb960GbM06VE5gaOX8ZgI
5lWzL8/CSqOH1IgvaHto/KwywOB4bpsCB7mhuWYWYv4KBJBi6Quh2P/4dQjZ1qx9
0g+H9vnKHNgvZF+JdWaCgP0CAwEAAQ==
-----END PUBLIC KEY-----
```
> Это публичный ключ — не секрет, можно класть в тест-фикстуры. **Приватный** ключ Passport не нужен и не выносить.
> Для unit-тестов лучше генерить собственную RSA-пару (не зависеть от stage-ключа); stage-ключ — для ручной/интеграционной проверки.

---

## 4. Критерий приёмки (ручная проверка на реальном токене)

`.env.local` (gitignored): `CUSTOMER_AUTH_PUBLIC_KEY_FILE=<путь к ключу выше>`,
`CUSTOMER_AUTH_ISSUER=` (пусто), `CUSTOMER_AUTH_AUDIENCE=` (пусто). Запуск gateway, эндпоинт OptionalAuth
(`/api/v1/recommendations/similar`):
- без `Authorization` → **200** (аноним);
- `Authorization: Bearer <мусор>` → **401** `invalid_token` (не молчаливый downgrade);
- `Authorization: Bearer <реальный stage-токен>` → **200**, вниз в catalog-cache уходит `X-Customer-Id: 4455421` (= `sub`).

Реальный stage access-token для проверки (просрочится/перевыпущен — взять свежий из localStorage фронта stage):
```
eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiI5ODgxYjIyMi0wZWYwLTQ5YmItYTNhOC01NTczZTZjY2RlMTYiLCJqdGkiOiI4NGI3NjZhYzIyZWY1Mjc4OTdiMGJhZDc3Mzc4ODFiODg0NzJiMjFmMGM3NGM3ZWJiMTljZGFiNDJmMDI5ZGM1NTE5OGUxMDRmZmM1MzM3NiIsImlhdCI6MTc3ODY3MDk2OS4xODI1NTEsIm5iZiI6MTc3ODY3MDk2OS4xODI1NTQsImV4cCI6MTc4MTI2Mjk2OS4xNzYzNjUsInN1YiI6IjQ0NTU0MjEiLCJzY29wZXMiOltdfQ.LvXXeo4-...(подпись)
```
Подпись этого токена уже проверена реальным ключом из §3 (signature + exp — OK).

---

## 5. Границы задачи
- НЕ менять `middleware.go`/`reqctx` (поведение тиров корректно).
- НЕ вводить JWKS-загрузку — статический PEM достаточен (Passport ротирует ключ редко; путь к файлу/значение в конфиге).
- Allowlist `aud` (client-UUID) — отдельный hardening-тикет, не здесь.
- Секреты (приватные ключи, токены) — не коммитить; публичный ключ — допустимо в фикстурах.
