# ТЗ: миграция `checkout` на пакет `gj-go-money`

**Тип:** рефакторинг (унификация денег + устранение float на границах). **Исполнитель:** отдельная сессия агента-кодера (без памяти). **Ревьюер:** автор ТЗ. **Чувствительная задача** — есть digest-стабильность и OMS-контракт, см. §5.

---

## 1. Якоря: репозитории и пути (читать перед любым действием)

Проект большой, рядом много репозиториев. Работаешь ТОЛЬКО в `checkout`.

| Что | Абсолютный путь (локально) | Go-модуль | Git remote |
|---|---|---|---|
| **checkout** (правим ЗДЕСЬ) | `/Users/zak/Projects/GJ-Ecommerce/platform-new/checkout/` | `gitlab.gloria.aaanet.ru/greensight/gj/go/checkout` | `git@gitlab.gloria.aaanet.ru:greensight/gj/go/checkout.git` |
| **gj-go-money** (зависимость, ОПУБЛИКОВАН, НЕ менять) | `/Users/zak/Projects/GJ-Ecommerce/platform-new/gj-go-money/` | `gitlab.gloria.aaanet.ru/go-pkg/gj-go-money` (тег `v0.1.0`) | `git@gitlab.gloria.aaanet.ru:go-pkg/gj-go-money.git` |
| go.work (workspace) | `/Users/zak/Projects/GJ-Ecommerce/platform-new/go.work` (уже `use ./gj-go-money`) | — | — |

> **`ROOT` = `/Users/zak/Projects/GJ-Ecommerce/platform-new/checkout`.** Все пути ниже — абсолютные или от `ROOT`. Все `git`/`go` — из `ROOT`. НЕ трогать другие репозитории, НЕ трогать `/Users/zak/Projects/GJ-Ecommerce/platform-new/gj-go-money/`, НЕ коммитить в workspace-репо `/Users/zak/Projects/GJ-Ecommerce`.

- **Ветка:** в `ROOT` создать `feat/money-migration`, коммитить туда.
- **Зависимость:** в `$ROOT/go.mod` — `require gitlab.gloria.aaanet.ru/go-pkg/gj-go-money v0.1.0`. Тег `v0.1.0` **опубликован** в GitLab → `go get gitlab.gloria.aaanet.ru/go-pkg/gj-go-money@v0.1.0` резолвится без `replace`. **НЕ добавляй `replace`.** Выполни `go get …@v0.1.0` (или `go mod tidy`), убедись что go.sum получил хэш.
- **Импорт:** `money "gitlab.gloria.aaanet.ru/go-pkg/gj-go-money"`.
- **Конвенции:** `$ROOT/CLAUDE.md`. Generated `*/apiv1/openapi.gen.go` **НЕ редактировать** (рендерим в них).

### API `gj-go-money` (готов)
```go
money.FromKopecks(int64) Money
money.FromRubles(int64) Money
money.FromRublesString(string) (Money, error)   // СТРОГО ≤2 знаков, иначе error
money.FromRublesFloat(float64) Money             // ingress, round-nearest
func (Money) Kopecks() int64
func (Money) Rubles() int64                       // целые рубли, CEIL (фронт / orderSum)
func (Money) RublesDecimal() string               // "1299.00" (контракты OMS/ENSI)
func (Money) Add(Money) Money; Sub; MulQty(int)
```

### Канон денег (OPSOMN-12987, не обсуждается)
- Внутри — `money.Money` (int64 копейки).
- **Публичные ответы checkout** (фронт через gateway) — **целые рубли**, ceil → `m.Rubles()`.
- **OMS** (order create / logistics) — **рубли.2знака**, ceil → `m.RublesDecimal()` (в `json.Number`), НЕ truncate/float.
- ingress: offers/baskets — копейки (`FromKopecks`); catalog-cache — рубли-float (`FromRublesFloat`); OMS rubles-decimal — через существующий толерантный парсер (см. §4.OMS-ingress).

---

## 2. Принцип миграции (важно для чувствительной задачи)

- **Имена полей НЕ меняем** (минимальный дифф, ниже риск пропустить место, легче ревью). Меняем только **тип** money-полей `int64` → `money.Money`. Поле вида `PriceKopecks money.Money` читается как «каноничные деньги» (суффикс `Kopecks` оставляем — это и есть внутренний юнит). Косметический ренейм — отдельная задача, НЕ сейчас.
- **Wire-поля в `apiv1` (`*_kopecks int64`, `*float32`) НЕ меняем** — это контракт. На границе рендерим из `Money`: `m.Kopecks()` для `*_kopecks int64`-полей, `float32(m.Rubles())` для `float32`-рублёвых полей.
- **Никакого float для денег внутри** и никакого ручного `/100`, `*100`, `float32(k)/100` после миграции (grep чист).

---

## 3. Внутренние типы → `money.Money`

Файлы (абсолютные):
- `/Users/zak/Projects/GJ-Ecommerce/platform-new/checkout/internal/domains/session/types.go`
  поля: `CartItem.PriceKopecks`, `Selection.DeliveryCostKopecks`, `Totals.{ItemsKopecks,DiscountKopecks,DeliveryKopecks,GrandTotalKopecks}`, `DeliveryView.{MinCostKopecks,FreeThresholdKopecks}`, `TotalsView.{TotalKopecks,DeliveryCostKopecks,DiscountKopecks}` (и любые другие `*Kopecks int64` в файле) → `money.Money`.
- `/Users/zak/Projects/GJ-Ecommerce/platform-new/checkout/internal/domains/pricing/types.go`
  `Totals.{TotalKopecks,DeliveryCostKopecks,DiscountKopecks}` → `money.Money`; интерфейс `Quoter.Quote(ctx, deliveryCostKopecks int64, …)` → `deliveryCostKopecks money.Money` (и реализации/стаб).
- `/Users/zak/Projects/GJ-Ecommerce/platform-new/checkout/internal/domains/delivery/types.go`
  `*.DeliveryCostKopecks`, `MinCostKopecks`, `FreeThresholdKopecks`, `Komplektaciya.PriceKopecks` (и пр. `*Kopecks int64`) → `money.Money`.
- Сопутствующее использование в `internal/domains/delivery/service.go`, `cluster.go`, `internal/domains/pricing/service.go`: арифметику над деньгами вести через `money.Money` (`Add`/`Sub`/`MulQty`), сравнения — `a.Kopecks() < b.Kopecks()` или напрямую (`Money` — int64, операторы сравнения работают).

> `Count`, `Qty`, `RegionId`, координаты (lat/lng `float64`), `zoom`, метрики, доли (`ratio`) — **НЕ деньги, не трогать.**

---

## 4. Границы (ingress / egress)

### ingress — cart (offers/baskets копейки)
`/Users/zak/Projects/GJ-Ecommerce/platform-new/checkout/internal/adapters/cart/resolver.go`
- цены позиций из offers/baskets (копейки) → `money.FromKopecks(int64(...))` в `CartItem.PriceKopecks`.

### ingress — OMS rubles-decimal (СОХРАНИТЬ толерантный парсер)
`/Users/zak/Projects/GJ-Ecommerce/platform-new/checkout/internal/adapters/delivery/kopecks.go`
- Функция `rublesToKopecks(json.Number) int64` — **оставить как есть** (round half-up на 2-м знаке, без float; gj-go-money.FromRublesString строгий и для OMS-quirk'ов не годится).
- На местах вызова (в `internal/adapters/delivery/oms.go`, `raw.go`, `resolver.go`) оборачивать результат: `money.FromKopecks(rublesToKopecks(n))`. То есть `rublesToKopecks` остаётся приватным OMS-парсером, а наружу из адаптера отдаём уже `money.Money`.

### egress — публичные totals/delivery (УБРАТЬ float)
`/Users/zak/Projects/GJ-Ecommerce/platform-new/checkout/internal/domains/session/assembler.go`
- Удалить `kopecksToRubles(k int64) float32 { return float32(k)/100 }` (float-деньги — нарушение политики).
- DTO `apiv1`-поля рублёвые `float32` (`CheckoutTotals.{Items,Discount,Delivery,GrandTotal}`, `DeliveryView.{MinCost,FreeThreshold}`, item `Price`) заполнять `float32(m.Rubles())` (целые рубли, ceil, канон-фронт). Хелпер: `func rublesF32(m money.Money) float32 { return float32(m.Rubles()) }`.
- DTO `apiv1`-поля `*_kopecks int64` (`delivery_cost_kopecks`, `min_cost_kopecks`, `free_threshold_kopecks`) заполнять `m.Kopecks()`.
- ⚠️ Поведение для дробных рублей меняется (`float32(k)/100` отдавал дробь → теперь целые рубли ceil). Для целочисленных рублёвых сумм (реальный GJ) — идентично. Это канон-выравнивание, см. §5.

### egress — OMS (order create / logistics req) (truncate → canon 2dp)
`/Users/zak/Projects/GJ-Ecommerce/platform-new/checkout/internal/adapters/delivery/oms.go`
- Заменить `rub := int(l.PriceKopecks / 100); item.Price = &rub` (целочисленный truncate) на канон: рубли.2знака через `m.RublesDecimal()` в `json.Number` — **если** поле в OMS-DTO `json.Number`. Если текущее поле `*int` (целые рубли) — привести к канону контракта OMS: деньги в OMS идут `json.Number` рубли.2знака (OPSOMN-12987). Проверь тип поля в starfish-OMS request DTO (`gitlab.gloria.aaanet.ru/greensight/gj/go/clients/starfishclient`); money-поля там должны быть `json.Number`. Если в текущем коде стоит `*int` — это баг truncate, заменить на `json.Number(m.RublesDecimal())`.
  - На каждый money-вызов: `m := money.FromKopecks(l.PriceKopecks-как-Money)` → уже `money.Money` после §3; `omsItem.Price = jsonNumberPtr(m.RublesDecimal())`.
- Если в этом файле есть обратный разбор money из OMS-ответа — через `money.FromKopecks(rublesToKopecks(n))` (§4 ingress).

---

## 5. Чувствительные точки (ОБЯЗАТЕЛЬНО с тестами)

### 5.1 digest стабильность — `internal/domains/session/digest.go`
- `CartHash` хэширует `sku:qty:price` через `strconv.FormatInt(it.PriceKopecks, 10)`. После смены типа на `money.Money` — хэшить **тот же int64**: `strconv.FormatInt(it.PriceKopecks.Kopecks(), 10)`.
- **Хэш обязан остаться байт-идентичным** (иначе инвалидируются живые session-дайджесты). Добавь тест: для фиксированного `[]CartItem` (известные sku/qty/цена) `CartHash` равен **зашитой строке-эталону** (вычисли её на текущем коде ДО миграции и впиши в тест как константу). Любой дрейф хэша — фейл.

### 5.2 OMS-контракт
- После правки §4-egress: тест, что money в OMS-request — `json.Number` рубли.2знака (`"599.00"`, не `599` и не `59900`), для набора сумм (целые и, если поддерживается, дробные).
- Сверка two-phase-truth/checksum (если есть в `session`): сравнение сумм вести в **копейках** (`m.Kopecks()`), целочисленно, без float — найти места сверки и убедиться, что они на `Kopecks()`.

---

## 6. Стабы и тесты
- `internal/adapters/commit/commit_stubs.go` (`StubPricer`, константы `stubItemsSubtotalKopecks=539600` и т.п.), `internal/domains/pricing/stub.go` (`StubQuoter`): money-значения строить через `money.FromKopecks(...)`; сигнатуры под новые типы.
- Все `*_test.go` с money — на `money.*` (`FromKopecks`/`FromRubles`), ассерты через `.Kopecks()`/`.Rubles()`/`.RublesDecimal()`. Сохранить смысл существующих кейсов.
- Новые тесты: §5.1 (digest-эталон), §5.2 (OMS json.Number 2 знака).

---

## 7. Проверка
```bash
cd /Users/zak/Projects/GJ-Ecommerce/platform-new/checkout
go get gitlab.gloria.aaanet.ru/go-pkg/gj-go-money@v0.1.0   # резолв тега
go build ./... && go test ./... -count=1 && go vet ./...
# нет ручной money-арифметики / float-денег (non-test):
grep -rnE "\* 100|/ 100|\+ 50|float32\([^)]*\) ?/ ?100|math\.Round" internal --include='*.go' | grep -v _test   # пусто по деньгам
# нет float-денег в доменных типах:
grep -rnE "Kopecks +float|Cost +\*?float|Total +\*?float|Price +\*?float|Discount +\*?float" internal/domains --include='*.go' | grep -v apiv1   # пусто
```

## 8. Determination of Done
- [ ] `go.mod` requires `gj-go-money v0.1.0`, резолв без `replace`, go.sum обновлён.
- [ ] Все внутренние money-поля доменов = `money.Money` (имена сохранены), арифметика через `Add/Sub/MulQty`.
- [ ] ingress: cart→`FromKopecks`; OMS→`FromKopecks(rublesToKopecks(...))` (парсер сохранён).
- [ ] egress публичный: `float32(m.Rubles())` / `m.Kopecks()` (убран `float32(k)/100`).
- [ ] egress OMS: `json.Number(m.RublesDecimal())` (убран `int(k/100)` truncate).
- [ ] §5.1 digest байт-стабилен + тест-эталон; §5.2 OMS 2-знака + тест.
- [ ] `build`+`test`+`vet` зелёные; grep'ы (§7) чистые.
- [ ] apiv1 generated НЕ изменён; публичные контракты (типы полей) не сломаны.
- [ ] Коммит(ы) в `feat/money-migration` репо checkout. Мёрж/публикация — ревьюер.

## 9. Границы задачи
**В задаче:** `checkout` на `money` (внутренние типы + ingress/egress + digest + OMS). **НЕ в задаче:** косметический ренейм `*Kopecks`→без суффикса; смена контрактных типов в `apiv1` (float32/`*_kopecks`) — это отдельные решения; правки `gj-go-money`, `clients/*`, `intgateway`.
