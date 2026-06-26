# Engine-side colour dedupe + self-exclude (shrink gateway overscan) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move colour-model dedupe and "never recommend the requested model back" from the gateway into the recommendation engine, then shrink the gateway's overscan — cutting the dominant hydration hop by ~40–70 ms.

**Architecture:** Today `intgateway`'s `EngineSource` requests 2×limit (cap 40) ids from the engine and dedupes colour variants client-side, so the hydrator fetches up to 40 catalog-cache cards to fill a 20-card carousel. The engine's per-article topK (idCache) is the right place for this: at build time (`computeTopKIDs`) full `ProductRow`s are available, so we dedupe by **model key** (group key sans `-N` colour suffix) and exclude the base article's whole model while building the cached top-100. The gateway then needs only a small availability margin (`limit`+25%) for the hydrator's `view_target=carousel` filtering.

**Tech Stack:** Engine: `platform-new/recomendationengine` (Go 1.26 + Fiber, module `gj-similar`, **NOT in go.work → prefix all Go commands with `GOWORK=off`**). Gateway: `platform-new/intgateway` (in go.work, plain `go` commands). Both deploy via golang-backend-pipeline; gateway: master push auto-deploys **test**; prod = two manual clicks (trigger → `gitlab-ci-prod-deploy` job). Engine deploys are manual.

**Measured baseline (prod, engine path):** bu ≈0 (cached) · engine ~10–20 ms · hydration ~130–175 ms for up to 40 cards (dominant). Target: hydrate ~25 cards for limit=20.

---

## Context an implementer must know (read first)

- Engine candidate ids ARE `productGroupKey(row)` values (`rank.go:74`: GroupKey → GroupID → SalesSKU → SKU). For the GJ auto-merch feed these are **CC colour-model codes** (`BWT001950-1`) — the feed groups per colour, so both colours of one model appear as independent candidates. That's the duplicate pair seen live on prod.
- `articlePrefix` (`rank.go:139`) is NOT a model key — it's the 3-letter category prefix ("BWT") used by blocking weights. Don't reuse it.
- Serve-time exclude (`service.go` `FindSimilar`) already drops the exact requested sku and `productGroupKey(base)`, but NOT the sibling colour (`-2` of the requested `-1`) and does NOT dedupe candidates between themselves.
- `computeTopKIDs` (`service.go:482`) builds the per-article cached top-100: `blockCandidates → RankSimilarCandidates → PickSimilarFromRanked(ranked, exclude, idCacheTopK=100, cfg)`. Rows are available here — this is where dedupe belongs (zero serve-time cost, cached result already clean).
- `PickSimilarFromRanked` (`rank.go:420`) is also used by `PickSimilar` (`rank.go:344`) and mirrored by `PickSimilarExplain` — admin GUI preview must show the same deduped picture, so the dedupe goes into the shared path, not just the cache build.
- No strategy-config flag for this (YAGNI): the product decision is firm — a "similar products" carousel must not show two colours of one model. If merchandising ever wants colours back, add a `StrategyConfig` toggle then (pattern exists — see `Blocking`).
- Gateway keeps a **belt-and-suspenders self-model guard** (3 lines) but drops cross-candidate dedupe: protects against engine/gateway version skew during rollouts, costs nothing.
- Rollout is backward-compatible in both directions: old gateway (2×limit + own dedupe) against new engine → double dedupe, harmless; new gateway against old engine → only risk is under-dedupe, which the order of deployment (engine first) avoids.

---

## File Structure

| Repo | File | Change |
|---|---|---|
| engine | `internal/discovery/similar/rank.go` | + `modelKey()`, + `dedupeByModel()`; `PickSimilarFromRanked` gains `baseModelKey` param and dedupes; `PickSimilar` / `PickSimilarExplain` thread the param |
| engine | `internal/discovery/similar/service.go` | `computeTopKIDs` passes `modelKey(*base)`; godoc |
| engine | `internal/discovery/similar/rank_test.go` (or nearest existing test file) | unit tests for modelKey/dedupe/self-exclude |
| gateway | `internal/adapters/recommendations/source.go` | overscan 2×→`limit+ceil(limit/4)` (cap 40); drop cross-candidate dedupe; keep self-model guard |
| gateway | `internal/adapters/recommendations/source_test.go` | update overscan asserts; replace dedupe test with self-guard test |

---

## Task 1 (engine): `modelKey` helper

**Files:** Modify `internal/discovery/similar/rank.go`; Test: same package.

- [ ] **Step 1: Write the failing test** (add to the existing rank/service test file in `internal/discovery/similar/`):

```go
func TestModelKey(t *testing.T) {
	cases := []struct{ in ProductRow; want string }{
		{ProductRow{GroupKey: "BWT001950-1"}, "BWT001950"},
		{ProductRow{SKU: "GKT028479-2"}, "GKT028479"},
		{ProductRow{SKU: "NOSUFFIX"}, "NOSUFFIX"},
		{ProductRow{SKU: "-1"}, "-1"}, // защитный кейс: суффикс без тела не режем
	}
	for _, c := range cases {
		if got := modelKey(c.in); got != c.want {
			t.Fatalf("modelKey(%+v): want %q, got %q", c.in, c.want, got)
		}
	}
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd platform-new/recomendationengine && GOWORK=off go test ./internal/discovery/similar/ -run TestModelKey`
Expected: FAIL (`undefined: modelKey`).

- [ ] **Step 3: Implement** — in `rank.go`, right below `productGroupKey`:

```go
// modelKey коллапсирует цветомодификации одной модели: групповой ключ без
// хвоста "-N" ("BWT001950-1" → "BWT001950"). Ключи без дефиса (или с дефисом
// в нулевой позиции) возвращаются как есть.
func modelKey(row ProductRow) string {
	id := productGroupKey(row)
	if i := strings.LastIndexByte(id, '-'); i > 0 {
		return id[:i]
	}
	return id
}
```

- [ ] **Step 4: Run to verify it passes** — same command, expected PASS.
- [ ] **Step 5: Commit**

```bash
cd platform-new/recomendationengine
git add internal/discovery/similar/
git commit -m "feat(similar): modelKey — групповой ключ без цвет-суффикса

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 (engine): dedupe by model inside the shared pick path

**Files:** Modify `internal/discovery/similar/rank.go` (PickSimilarFromRanked + PickSimilar + PickSimilarExplain), `internal/discovery/similar/service.go` (computeTopKIDs call site). Tests: same package.

- [ ] **Step 1: Write the failing test**

```go
func TestPickSimilarFromRanked_DedupesColourModelsAndBaseModel(t *testing.T) {
	rows := []ProductRow{
		{SKU: "BWT001950-1"}, // цвет 1 модели 1950 — keep (лучший ранг)
		{SKU: "BWT001950-2"}, // цвет 2 той же модели — drop
		{SKU: "GKT028479-1"}, // сиблинг ЗАПРОШЕННОЙ модели — drop (baseModelKey)
		{SKU: "BWT001840-1"}, // keep
	}
	ranked := make([]scoredPair, len(rows))
	for i := range rows {
		ranked[i] = scoredPair{row: &rows[i], score: float32(100 - i)} // убывающий ранг
	}
	items, _, _ := PickSimilarFromRanked(ranked, map[string]struct{}{}, "GKT028479", 10, DefaultConfig())
	if len(items) != 2 || items[0].ID != "BWT001950-1" || items[1].ID != "BWT001840-1" {
		t.Fatalf("want [BWT001950-1 BWT001840-1], got %+v", items)
	}
}
```

> Подгони конструирование `scoredPair`/`DefaultConfig()` под фактические приватные типы (`scoredPair{row,score}` — проверь поля по `rank.go`; тест в том же пакете, доступ есть). Если каскад порогов в `pickFromScored` режет низкие скоры — задай скоры заведомо выше порогов из `DefaultConfig()`.

- [ ] **Step 2: Run to verify it fails**

Run: `GOWORK=off go test ./internal/discovery/similar/ -run TestPickSimilarFromRanked_Dedupes`
Expected: FAIL (signature mismatch — у `PickSimilarFromRanked` нет параметра baseModelKey).

- [ ] **Step 3: Implement** — в `rank.go`:

```go
// dedupeByModel оставляет лучший по рангу цвет каждой модели и выкидывает
// цветомодификации базовой (запрошенной) модели. scored отсортирован по рангу
// убыванию, поэтому «первый встреченный» = лучший.
func dedupeByModel(scored []scoredPair, baseModelKey string) []scoredPair {
	seen := make(map[string]struct{}, len(scored))
	out := scored[:0:0]
	for _, p := range scored {
		mk := modelKey(*p.row)
		if mk == baseModelKey {
			continue
		}
		if _, dup := seen[mk]; dup {
			continue
		}
		seen[mk] = struct{}{}
		out = append(out, p)
	}
	return out
}
```

Сигнатура `PickSimilarFromRanked` получает параметр и применяет дедуп ДО каскада лимитов:

```go
func PickSimilarFromRanked(
	ranked []scoredPair,
	exclude map[string]struct{},
	baseModelKey string,
	limit int,
	cfg StrategyConfig,
) (items []Item, strategy string, fallbackUsed bool) {
	scored := dedupeByModel(filterRankedByExclude(ranked, exclude), baseModelKey)
	pick, strategy, fallbackUsed := pickFromScored(scored, limit, cfg)
	// ... остальное без изменений
```

Call sites (компилятор найдёт все):
- `rank.go:344` (`PickSimilar`): передать `modelKey(base)` (у функции есть `base ProductRow`).
- `service.go:487` (`computeTopKIDs`): `PickSimilarFromRanked(ranked, exclude, modelKey(*base), idCacheTopK, cfg)`.
- `PickSimilarExplain` (rank.go ~447): применить тот же `dedupeByModel(scored, modelKey(base))` перед `pickFromScored`, чтобы admin-превью совпадало с продом (в `topRankedExplain` сырой ранг можно оставить недедупленным — это диагностика).

- [ ] **Step 4: Run the full engine suite**

Run: `GOWORK=off go build ./... && GOWORK=off go vet ./... && GOWORK=off go test ./...`
Expected: PASS. Если существующие тесты пикера фиксировали выдачу с дублями моделей — обнови фикстуры осознанно (это и есть новое поведение), НЕ ослабляй ассерты.

- [ ] **Step 5: Commit**

```bash
git add internal/discovery/similar/
git commit -m "feat(similar): дедуп цветомоделей + исключение модели запроса в общем pick-пути

Кандидаты — групповые ключи уровня цветомодели (фид группирует по цвету), из-за
чего в топ попадали оба цвета одной модели, а сиблинг запрошенного артикула не
исключался. Дедупим по modelKey до каскада лимитов: в кэшированном топ-100 теперь
100 РАЗНЫХ моделей; admin-превью (Explain) показывает ту же картину.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 (engine): deploy + live verify

- [ ] **Step 1:** `git push origin master`; собрать и выкатить движок на **test**, затем **prod** (manual jobs; прод — двухступенчатый: trigger → `gitlab-ci-prod-deploy` → `deploy:recomendationengine`; **IMAGE_TAG фиксируется при создании downstream-пайплайна** — жми джобу из СВЕЖЕГО пайплайна).
- [ ] **Step 2:** после прогрева (`Similar idCache warmed (N cards)` в логах) дёрнуть движок напрямую (изнутри/port-forward): `GET /api/v1/similar/BWT002353-1?limit=40` → в ответе **нет двух id с общим префиксом до последнего дефиса** и нет `BWT002353-*`.

---

## Task 4 (gateway): shrink overscan, drop client-side dedupe, keep self-guard

**Files:** Modify `internal/adapters/recommendations/source.go`; Test `internal/adapters/recommendations/source_test.go`.

- [ ] **Step 1: Update tests first** (они зафиксируют новый контракт):

В `source_test.go`:
- `TestEngineSource_MapsIDsAndOverscans`: ожидание `gotL` для `Limit: 20` → **25** (`20 + ceil(20/4)`).
- `TestEngineSource_OverscanCappedAtEngineMax`: `Limit: 36` → 40 (кап), `Limit: 0` → 0.
- `TestEngineSource_DedupesColourVariantsAndSelf` ЗАМЕНИТЬ на:

```go
func TestEngineSource_SelfModelGuard(t *testing.T) {
	// движок дедупит сам; гейтвей держит только страховку от version skew:
	// цветомодификация ЗАПРОШЕННОЙ модели никогда не возвращается,
	// остальные id передаются как есть (включая возможные дубли — ответственность движка)
	fe := &fakeEngine{ids: []string{"GKT028479-1", "BWT001950-1", "BWT001950-2"}}
	s := NewEngineSource(fe)
	out, err := s.Similar(context.Background(), domain.ProductID("GKT028479-2"), domain.SimilarOpts{Limit: 10})
	if err != nil {
		t.Fatalf("similar: %v", err)
	}
	want := []domain.ProductID{"BWT001950-1", "BWT001950-2"}
	if len(out) != 2 || out[0] != want[0] || out[1] != want[1] {
		t.Fatalf("want %v (self-model dropped, rest passthrough), got %v", want, out)
	}
}
```

- [ ] **Step 2: Run to verify failures**: `cd platform-new/intgateway && go test ./internal/adapters/recommendations/ -run TestEngineSource` → FAIL.

- [ ] **Step 3: Implement** — в `source.go` заменить тело `Similar` (helper `baseModel` остаётся):

```go
// Over-scan: гидратор отфильтрует не-showable карточки (view_target=carousel),
// поэтому просим limit + 25% (движок уже дедупит цвета и исключает запрошенную
// модель — см. план 2026-06-11-engine-colour-dedupe). Кап — лимит движка 40.
func (s *EngineSource) Similar(ctx context.Context, productID domain.ProductID, opts domain.SimilarOpts) ([]domain.ProductID, error) {
	reqLimit := opts.Limit
	if reqLimit > 0 {
		reqLimit += (reqLimit + 3) / 4 // +25%, округление вверх
		if reqLimit > engineMaxLimit {
			reqLimit = engineMaxLimit
		}
	}

	ids, err := s.client.Similar(ctx, string(productID), recengine.SimilarOpts{Limit: reqLimit})
	if err != nil {
		return nil, err
	}

	// Страховка от version skew движка: цветомодификацию запрошенной модели не
	// возвращаем никогда. Кросс-кандидатный дедуп НЕ делаем — это контракт движка.
	ownModel := baseModel(string(productID))
	out := make([]domain.ProductID, 0, len(ids))
	for _, id := range ids {
		if baseModel(id) == ownModel {
			continue
		}
		out = append(out, domain.ProductID(id))
	}
	return out, nil
}
```

- [ ] **Step 4: Full gateway suite**: `go build ./... && go vet ./... && go test ./...` → PASS.
- [ ] **Step 5: Commit + push** (auto test deploy):

```bash
git add internal/adapters/recommendations/source.go internal/adapters/recommendations/source_test.go
git commit -m "perf(recommendations): overscan 2×→+25% — дедуп цветов переехал в движок

Гидратор теперь тянет ~25 карточек вместо 40 на limit=20 (−40..70мс с
доминирующего хопа). Кросс-кандидатный дедуп удалён (контракт движка),
оставлена страховка self-model на случай version skew.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
git push origin master
```

> **Порядок выката обязателен: движок (Task 3) раньше гейтвея.** Новый гейтвей против старого движка вернёт недодедупленную карусель.

---

## Task 5: prod rollout + verification

- [ ] **Step 1:** прод-деплой гейтвея (два клика, свежий пайплайн).
- [ ] **Step 2:** проверить из браузера `https://api-int.gloria-jeans.ru/api/v1/recommendations/similar?product_id=BWT002353-1&region_id=0c5b2444-70a0-4932-980c-b4dc0d3f02b5&limit=20`: нет пар одной модели; время заметно меньше прежнего.
- [ ] **Step 3:** `/metrics` гейтвея: средняя латентность `httpclient_request_duration_seconds{service="catalog-cache",op="search"}` на запрос должна упасть (меньше карточек за вызов); `recommendations_hydration_ratio` должен подняться ближе к 1 (просим 25, отдаём 20).

---

## Risks

- **Эвристика modelKey (обрезка `-N`)**: если в каталоге есть модели, где разные товары делят «базу» артикула, они схлопнутся. Смягчение: то же правило уже месяц работает в гейтвее на проде без жалоб; admin-превью (Explain) покажет эффект мерчандайзингу; при необходимости — флаг в StrategyConfig (паттерн Blocking) отдельной задачей.
- **Каскад порогов после дедупа**: кандидатов до лимита станет меньше; topK=100 различных моделей даёт запас в 2.5× над максимальным limit=40 — недобор маловероятен.
- **Version skew при выкате**: закрыт порядком деплоя + self-guard в гейтвее.

## Self-review checklist
1. Все call sites `PickSimilarFromRanked` обновлены (компилятор-driven), включая Explain.
2. `idCache` инвалидации не требуется отдельно: деплой = рестарт пода = пустой кэш + прогрев.
3. Гейтвей: тест `SelfModelGuard` фиксирует passthrough дублей (контракт движка) — это сознательно.
4. Никаких изменений публичного API/OpenAPI ни у движка, ни у гейтвея.
