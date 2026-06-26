# Инкремент: реальный `DeliverySource` (частичный) — живые данные доставки из OMS

**Дата:** 2026-05-31 · **Тип:** инкремент checkout (вставляется ПЕРЕД Plan 4) · **Зачем:** раннее тестирование на реальных данных кусочками.

**Идея (цель Zak):** дать живой `GET /checkout/{id}/delivery-options` на **реальном OMS**, **анонимно** (без кастомера), **частично** — сначала **курьер + магазин**, ПВЗ отложить. Ловить расхождения рано, оптимизировать. Сейчас `DeliverySource` = stub из фикстур; меняем на реальный адаптер.

## 0. Репозиторий и окружение (читать первым)
- **Код:** репо `e-commerce/platform/checkout` (branch `main`, локально `platform-new/checkout`, свой git). Коммитить там. Plan 1–3 готовы (тег `v0.0.3-resolver`).
- **Окружение Go (Buddy-стиль, иначе приватные модули не резолвятся):** `go env -w GOPRIVATE='gitlab.gloria.aaanet.ru/*'` + git `insteadOf` (https→ssh). **Без replace/go.work.** Эталон — `gj-buddy-server`.
- **Локальный контур:** Postgres `docker compose -f dev/docker-compose.yml up -d` (:5544); OMS на stage — `KUBECONFIG=~/.kube/ecom.yaml make port-forward` (api-gateway v1 :18080, v2 :18081); токен + base URL’ы v1/v2 — в `.env` (см. `docs/dev/stage-access.md`). OMS требует **Bearer**.
- **Самодостаточно:** ссылки на доки опциональны, ключевое инлайнено.

## Что НЕ трогаем (важно)
- **§2c resolver** (`internal/adapters/delivery/resolver.go`) — нормализация 4 форм OMS → `Komplektaciya/Digest`, rubles→int64 копейки — **общий и уже доказан на реальных фикстурах**. Реальный адаптер: «дёрнул OMS → скормил СЫРОЙ ответ в ТЕ ЖЕ resolver-функции». НЕ переписывать resolver.
- **stub `DeliverySource`** остаётся (на нём unit-тесты домена). Переключение stub↔real — через конфиг.

## Шов
`internal/app/wire/delivery.go`: сейчас `src := adapter.NewStubDeliverySource()`. Здесь же выбираем real vs stub по конфигу и инжектим starfish-oms клиент.

## Порт (что реализует реальный адаптер)
```go
Digest(ctx, cart []CartLine) (DeliveryDigest, error)
Options(ctx, cart []CartLine, t DeliveryType) ([]Komplektaciya, error)
```
**Customer-agnostic** — берёт только корзину (+ город, см. ниже).

## Scope (частично — курьер+магазин сейчас, ПВЗ отложить)
1. **`OMSDeliverySource`** в `internal/adapters/delivery/` (рядом со stub) на опубликованном клиенте **`clients/starfish-oms` v0.1.1** (добавить в go.mod, Buddy-стиль `require`, без replace):
   - `Digest(cart)` → OMS v2 `delivery-preliminary` → `resolver.normalizeDigest` (тот же).
   - `Options(cart, COURIER)` → OMS v2 `delivery-intervals` → resolver.
   - `Options(cart, STORE_*)` → OMS v2 `pickup-stores` → resolver.
   - `Options(cart, PVZ)` → **вернуть пусто + в Digest пометить pvz `Available:false`** (pickup-points/кластеры — отложено). Курьер+магазин работают на реальных данных.
2. **Маппинг входа:** `delivery.CartLine` → тело запроса starfish-oms (`cart.items[]` + город). **Город:** на раннем этапе — из конфига/сида (полный city/region join — фаза 2). Ошибки OMS → через `starfish-oms` `AsSpringError` → доменные ошибки.
3. **Конфиг-переключатель:** `OMS_DELIVERY_SOURCE=stub|real` (default `stub` — unit-тесты не лезут в сеть). При `real`: `wire.Delivery` строит `starfish-oms` клиент (base URL v1/v2 + Bearer из env) и `OMSDeliverySource`.
4. **Сид реальной корзины в сессию** (для e2e): минимальный путь наполнить `cart_snapshot` реальными offerId+город (extend session-create опциональным inline-cart для dev, ЛИБО dev-seed). Полная интеграция baskets — фаза 2. Цель: у сессии есть реальная корзина → digest её использует.

## Constraints
- Деньги — `int64` копейки (resolver уже так; адаптер не вводит float).
- Не ломать stub/unit-тесты; real — за конфигом.
- starfish-oms READ-методы (preliminary/intervals/pickup-stores) faithful по фикстурам → низкий риск; order/create-ответы НЕ нужны здесь.
- Buddy-стиль; коммит в репо checkout.

## DoD
- `OMS_DELIVERY_SOURCE=real` + `make port-forward` + реальная корзина в сессии → `GET /checkout/{id}/delivery-options` отдаёт **живой digest** (курьер+магазин Available, pvz `Available:false`), **анонимно**.
- Live-e2e против stage OMS: digest-методы + courier-интервалы + магазины — реальные; ПВЗ помечен недоступным.
- Unit-тесты домена (на stub) зелёные; добавить guarded integration-тест реального адаптера (skip без OMS-env).
- `go build/vet/test`, `make generate` без drift, redocly clean.
- Сид-корзина воспроизводима (документировать в `docs/dev/`).

## Отложено (фаза 2 / Plan 4)
ПВЗ (pickup-points + кластеры на реальных данных), полный city/region join, интеграция baskets (наполнение корзины), commit-сага.

## Ссылки (опционально)
- _[repo checkout]_ карта доменов `docs/architecture/domain-map.md`; dev-доступ `docs/dev/stage-access.md`; resolver/стаб `internal/adapters/delivery/`.
- _[repo checkout]_ Plan 3 (контекст) `docs/superpowers/plans/2026-05-30-checkout-v1-plan3-resolver.md` (или в meta-репо).
- _[clients]_ `e-commerce/platform/clients/starfish-oms` v0.1.1 — методы GetDeliveryPreliminary / GetCourierDeliveryIntervals / GetPickupStores (+ GetPickupPoints — отложено).
