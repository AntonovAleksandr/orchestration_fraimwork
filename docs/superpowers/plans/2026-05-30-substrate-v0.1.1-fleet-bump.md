# Runbook: gj-go-httpclient v0.1.1 + fleet bump

**Дата:** 2026-05-30
**Зачем:** опубликовать критичный фикс substrate + привести флот клиентов к реальному pin версии.

> **✅ ВЫПОЛНЕНО 2026-05-30.** substrate v0.1.1 + 7 клиентов (catalog-cache/baskets/customers/offers/bu/starfish-oms/discount) запушены, теги v0.1.1 на remote (verified). discount по ходу починен (был не склонирован → subtree split в свой репо). **Остаётся:** Step 3 (ecom-gateway — consumer, пушит Zak при деплое) + default branch master→main у starfish-oms/discount в GitLab UI.

## Контекст — два бага, которые это закрывает
1. **Truncation (критичный, fleet-wide):** `gj-go-httpclient` обрезал любой 2xx-ответ >4 КБ (`io.LimitReader` на каждом теле) → `KindDecode`. Фикс — коммит `0aa590b` на `main` (полное чтение на 2xx). Бьёт catalog-cache/starfish-oms/baskets/customers/offers/bu на реальных данных.
2. **Плейсхолдер-require (консьюмабельность):** все 6 клиентов имеют `require gj-go-httpclient v0.0.0-00010101000000-000000000000` + держатся на `replace ../../gj-go-httpclient`. Опубликованные v0.1.0 **не резолвятся внешним потребителем** (нет такой версии substrate). Эталон — ecom-gateway: `require ... v0.1.0` + replace.

**Итог:** pin до реального `v0.1.1` чинит оба. `replace` оставляем (dev-only, downstream его игнорирует).

## Порядок (строго bottom-up — иначе downstream не зарезолвит)
substrate → клиенты (6) → ecom-gateway.

> Локальные `go build/test` зелёные на каждом шаге благодаря `replace` (тянет локальный fixed substrate независимо от того, опубликован ли v0.1.1). Реальный pin v0.1.1 — метаданные для downstream; станут резолвиться после Step 1 push.

---

## Step 1 — substrate v0.1.1
```bash
cd ~/Projects/GJ-Ecommerce/platform-new/gj-go-httpclient
go build ./... && go test ./...                 # фикс + регресс-тест зелёные
git tag -a v0.1.1 -m "fix: read full 2xx body (4 KiB cap truncated large responses)"
git push origin main --tags
```

## Step 2 — клиенты (повторить для каждого из 6)
Список: `catalog-cache  starfish-oms  baskets  customers  offers  bu  discount`
> `discount` добавлен 2026-05-30 (вернулся позже; truncation ему не страшен — свой read через escape-hatch Do, но placeholder-require тот же → bump для консьюмабельности). Его go.mod require уже бампнут локально.
Для каждого `clients/<NAME>`:
```bash
cd ~/Projects/GJ-Ecommerce/platform-new/clients/<NAME>
# 1. pin реальную версию substrate (заменить плейсхолдер; replace оставить как есть)
sed -i '' 's#gj-go-httpclient v0.0.0-00010101000000-000000000000#gj-go-httpclient v0.1.1#' go.mod
# 2. проверка (replace → локальный fixed substrate)
go build ./... && go test ./...
# 3. коммит + тег + пуш
git add go.mod
git commit -m "chore: pin gj-go-httpclient v0.1.1 (truncation fix; was placeholder pseudo-version)"
git tag -a v0.1.1 -m "pin substrate v0.1.1 (truncation fix)"
git push origin main --tags
```
> Если `go build` после sed жалуется на go.sum — `go mod tidy` (с активным replace он не качает v0.1.1, берёт локальный путь). Если tidy всё же лезет в сеть за v0.1.1 — значит Step 1 не запушен; сделай Step 1 сначала.
> v0.1.0 НЕ двигаем (тег остаётся); v0.1.1 — новый patch-тег.

## Step 3 — ecom-gateway
```bash
cd ~/Projects/GJ-Ecommerce/platform-new/ecom-gateway
sed -i '' 's#gj-go-httpclient v0.1.0#gj-go-httpclient v0.1.1#; s#clients/catalog-cache v0.1.0#clients/catalog-cache v0.1.1#' go.mod
go build ./... && go test ./...                 # replace’ы оба локальные → зелёное
git add go.mod
git commit -m "chore: bump gj-go-httpclient v0.1.1 + catalog-cache v0.1.1 (truncation fix)"
git push origin main          # тег ecom-gateway по желанию (сервис, не публикуемая либа)
```

## Проверка консьюмабельности (опц., после всех push)
Во временной директории вне workspace (без replace):
```bash
GOFLAGS=-mod=mod go mod download gitlab.gloria.aaanet.ru/e-commerce/platform/clients/starfish-oms@v0.1.1
# должно зарезолвить и v0.1.1 substrate без ошибок «unknown revision v0.0.0-0001...»
```

---

## Про `replace` при публикации (УТОЧНЕНО 2026-05-30)
`replace gj-go-httpclient => ../../gj-go-httpclient` в go.mod клиента — **НЕ-main модуль → Go его ИГНОРИРУЕТ у downstream** (применяются только replace главного модуля). Значит:
- **Публикацию НЕ блокирует:** потребитель (checkout/ecom-gateway) резолвит `require gj-go-httpclient v0.1.1` штатно, replace клиента игнорит. **Ship now с replace — корректно.**
- Дропать replace стоит только ради гигиены + standalone-CI клиента — это **fast-follow**, не блокер.
- **substrate v0.1.1 уже затеган локально** (агентом starfish-oms) — на Step 1 просто `git push origin main --tags` (повторный `git tag` пропустить).

## Fast-follow: ВЫПОЛНЕНО иначе — Buddy-стиль (2026-05-31, заменяет go.work-идею)
Изначально планировался gitignored `go.work`. По итогу принят **Buddy-эталон** (gj-buddy-server): **чистые go.mod без replace + без go.work**, приватные модули резолвятся `GOPRIVATE=gitlab.gloria.aaanet.ru/*` + git `insteadOf` (SSH) + Nexus go-proxy. Флот переехал в `platform-new/`, все relative-`replace` убраны, go.sum дозаполнен (standalone-репо, как Buddy). go.work НЕ используется. Детали — память `project_checkout.md` + `reference_buddy_go_precedent.md`.

## Политика (ADR-кандидат, рядом с ecom-gateway ADR-0008/0009)
- **Клиенты `clients/*` ОБЯЗАНЫ пинить реальную версию substrate** (`require gj-go-httpclient vX.Y.Z`), НЕ плейсхолдер `v0.0.0-0001...`. `replace ../../gj-go-httpclient` — только для локальной разработки (downstream его игнорирует).
- **Фикс substrate = скоординированный patch-bump флота:** tag substrate → во всех клиентах bump require + ре-тег → bump в ecom-gateway. Чек-лист — этот файл.
- Дубль того же gap для catalog-cache был известен; теперь закрывается.

## Чего НЕ делаем здесь
- order/create + getlink response-DTO у starfish-oms остаются best-effort (README-flagged) до захвата фикстур на stage (фикстуры Tier-1 A+C) — отдельный шаг фазы 2.
