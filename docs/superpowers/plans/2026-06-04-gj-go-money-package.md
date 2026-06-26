# ТЗ: пакет `gj-go-money` — единый money-тип для Go-флота GJ

**Тип:** создание нового shared-модуля. **Исполнитель:** отдельная сессия агента-кодера (без памяти — всё нужное ниже). **Ревьюер:** автор ТЗ в отдельной сессии.

---

## 0. Контекст (зачем) — читать первым

В новом Go-флоте GJ (BFF `intgateway`, сервис `checkout`, клиенты `clients/*`) деньги приходят из разных апстримов в **разных единицах**, и конверсия ×100 / ÷100 начала размазываться по сервисам (адаптеры, хендлеры, границы с OMS) с риском расходящегося округления и перепутанных единиц (`int64` рубли там, где ждут копейки).

**Факты по единицам (источник истины):**
| Источник/потребитель | Единица |
|---|---|
| ENSI `catalog-cache` | **рубли** (число с плавающей точкой, напр. `599.0`) |
| ENSI `baskets` | **копейки** (`int`, напр. `59900`) |
| OMS (приём заказа) | **рубли** |
| Фронт (web/mobile) | **рубли** (фронт — только представление, **не конвертирует**) |
| Внутренний канон Go-флота | **копейки** (`int64`) |

**Решение:** единый value-тип `Money` (канонически — int64 копейки), который «впитывает» единицу источника на конструкторе и отдаёт единицу потребителя на аксессоре. Вся арифметика и правило округления — **в одном месте**. Этот пакет — фундамент; потребителей (`intgateway`, `checkout`) мигрируют отдельными задачами, **в этой задаче их НЕ трогаем**.

Пакет **consumer-agnostic**: не знает ни про какой апстрим/домен, чистый stdlib.

---

## 1. Репозиторий, модуль, окружение

- **Новый отдельный git-репозиторий**, группа go-pkg (как `gj-go-logger`, `gj-go-httpclient`).
- **Module path:** `gitlab.gloria.aaanet.ru/go-pkg/gj-go-money`
- **Package name:** `money` (короткое; потребитель пишет `money.Money`, `money.FromKopecks(...)`).
  - *(Пакетное имя намеренно ≠ последний сегмент пути — так же как у `gj-go-logger`, где package `gjlogger`. Это валидный Go; потребитель ссылается по имени пакета `money`.)*
- **go.mod:** `go 1.22` (низкий floor намеренно — пакет на чистом stdlib, потребители на 1.26.2 совместимы).
- **Зависимости:** только stdlib (`math`, `strconv`/`fmt` для String). Никаких внешних модулей.
- **Локальная разработка:** репозиторий клонируется в `platform-new/gj-go-money/`; добавить его в `platform-new/go.work` в блок `use (...)` (рядом с `./gj-go-logger`). Резолв приватных модулей — как в остальном флоте (`GOPRIVATE=gitlab.gloria.aaanet.ru/*` + git `insteadOf`); но т.к. зависимостей нет, для самого пакета это не критично.
- **Версионирование:** semver-тег. Первый релиз — `v0.1.0` (тег после мёржа).

### Структура (flat-модуль, как `gj-go-logger`)
```
gj-go-money/
├── go.mod
├── money.go        // тип + конструкторы + аксессоры + арифметика
├── money_test.go   // table-driven тесты
├── doc.go          // package doc (можно объединить с money.go, тогда doc.go не нужен)
└── README.md
```

---

## 2. API (точные сигнатуры)

```go
package money

// Money is an amount of money. The canonical internal unit is KOPECKS (int64).
// Construct via FromKopecks/FromRubles/FromRublesString/FromRublesFloat; render
// via Kopecks/Rubles/RublesDecimal. Zero value is a valid zero amount. Money is a
// defined int64, so ==, <, > work directly between Money values.
//
// GJ money canon (OPSOMN-12987): contract money is RUBLES with 2 decimals,
// rounding UP (ceil). Frontend displays WHOLE rubles ("1999"). Internal/east-west
// is kopecks. This type serves all three via the accessors below.
type Money int64

// --- constructors (absorb the source unit) ---

// FromKopecks builds Money from an integer kopeck amount (e.g. ENSI baskets).
func FromKopecks(k int64) Money

// FromRubles builds Money from a whole-ruble integer amount (exact ×100).
func FromRubles(r int64) Money

// FromRublesString parses a decimal-ruble string into exact kopecks, e.g.
// "1299.00"→129900, "599"→59900, "50.5"→5050. Used for upstreams that send money
// as decimal strings (discount server, OMS rubles-decimal). Returns an error on
// malformed input or more than 2 fractional digits. (Exact parse — no rounding.)
func FromRublesString(s string) (Money, error)

// FromRublesFloat builds Money from a fractional-ruble float (e.g. ENSI
// catalog-cache returns float rubles). This is an INGRESS parse: it must faithfully
// represent the upstream value, so it rounds rubles×100 to the NEAREST kopeck
// (math.Round). NOTE: this is round-to-nearest, NOT the canon ceil — ceil is an
// egress/compute policy, never applied when reading an upstream value.
func FromRublesFloat(r float64) Money

// --- accessors (render the consumer unit) ---

// Kopecks returns the exact kopeck amount (internal / east-west).
func (m Money) Kopecks() int64

// Rubles returns WHOLE rubles, rounding UP (ceil) per canon OPSOMN-12987
// ("округление в большую сторону"). Use for the FRONTEND (BFF responses display
// whole rubles, e.g. 1999) and for the commit orderSum ("в рублях без копеек").
// For whole-ruble amounts (the real GJ case) this is exact; ceil only affects
// sub-ruble amounts.
func (m Money) Rubles() int64

// RublesDecimal returns rubles with exactly 2 decimal places as a string, e.g.
// 129900→"1299.00", 59999→"599.99". EXACT (kopecks already carry 2-decimal
// precision — no rounding). Use for ENSI↔IS↔OMS and discount-server contracts
// (feed into json.Number on the wire; never float).
func (m Money) RublesDecimal() string

// --- arithmetic (stay in canonical kopecks) ---

// Add returns m + o.
func (m Money) Add(o Money) Money

// Sub returns m - o.
func (m Money) Sub(o Money) Money

// MulQty returns m repeated qty times (line total = unit price × qty).
func (m Money) MulQty(qty int) Money

// --- debug ---

// String renders a human-readable "<rubles>.<kk> ₽" form for logs/tests.
// NOT for API output — API conversion goes through the accessors at the DTO
// boundary. Example: Money(59900).String() == "599.00 ₽".
func (m Money) String() string
```

### Точные формулы (зафиксировать в коде и тестах)
- `Rubles()` — **целые рубли, округление ВВЕРХ (ceil)** по канону OPSOMN-12987:
  - `k := int64(m)`
  - ceil-деление на 100: `k >= 0` → `(k + 99) / 100`; `k < 0` → `k / 100` (целочисленное деление в Go усекает к нулю → для отрицательных это и есть ceil).
  - Проверка: `59900→599`, `59901→600`, `59900` ровно→`599`, `-59901→-599`.
- `RublesDecimal()` — **точное** 2-знаковое представление, без округления:
  - знак, `abs/100` (целая часть), `.`, `abs%100` с ведущим нулём (`%02d`).
  - `129900→"1299.00"`, `59999→"599.99"`, `5→"0.05"`, `-1234→"-12.34"`.
- `FromRublesString(s)` — точный парс decimal-рублей в копейки:
  - принять опциональный знак, целую часть, опц. `.` + 1–2 знака; `>2` дробных → ошибка; нечисловое → ошибка.
  - `"1299.00"→129900`, `"599"→59900`, `"50.5"→5050`, `"0.05"→5`. (Реализуй парсом строки, НЕ через float — иначе теряешь точность.)
- `FromRublesFloat(r)` — ingress, round-to-nearest: `Money(int64(math.Round(r * 100)))`. (Намеренно НЕ ceil — верно представляем апстрим.)
- `FromRubles(r)` → `Money(r * 100)` (точно).
- `FromKopecks(k)` → `Money(k)`.
- `MulQty(qty)` → `Money(int64(m) * int64(qty))`.

---

## 3. Жёсткие требования / что НЕ делать

1. **НЕ реализовывать `MarshalJSON` / `UnmarshalJSON`** у `Money`. Это сознательно: один и тот же money-value на разных границах рендерится в разных единицах (фронт — рубли, OMS — рубли, внутренний east-west — копейки). Авто-маршалинг зашил бы одну единицу. Конверсия в DTO — **явная**, на границе, через `Kopecks()`/`Rubles()`. Generated DTO у потребителей остаются обычными `int` — этот пакет их не касается.
2. **Никакой бизнес-логики/знаний об апстримах** (catalog-cache, baskets, OMS) в пакете. Чистая арифметика единиц.
3. **Только stdlib.** Ни `gj-go-logger`, ни чего-либо ещё.
4. **Не плодить дублирующее API.** Свободные функции `KopecksToRubles`/`RublesToKopecks` НЕ нужны — их роль закрывает `money.FromKopecks(k).Rubles()` / `money.FromRubles(r).Kopecks()`.
5. **Не паниковать.** `MulQty` с отрицательным qty — просто умножение (поведение определено арифметикой). Переполнение int64 не обрабатываем (суммы заказов далеки от 9.2e16 копеек).

---

## 4. Тесты (`money_test.go`, table-driven)

Покрыть:
- **Конструкторы:**
  - `FromKopecks(59900).Kopecks() == 59900`
  - `FromRubles(599).Kopecks() == 59900`
  - `FromRublesFloat(599.0).Kopecks() == 59900`
  - `FromRublesFloat(2499.5).Kopecks() == 249950`  (2499.5 точно представимо → 249950)
  - `FromRublesFloat(599.49).Kopecks() == 59949`  (округление вниз, без `.5`-границы)
  - `FromRublesFloat(599.51).Kopecks() == 59951`  (округление вверх, без `.5`-границы)
  - ⚠️ **НЕ** писать тест-кейсы на точную десятичную `.5`-границу для `FromRublesFloat`
    (напр. `599.005`): такие значения **не представимы точно** в float64 (`599.005*100 ≈ 59900.4999…`),
    результат `math.Round` непредсказуем по последней цифре → тест будет хрупким. Семантику
    «ties away from zero» проверяем на целочисленном пути `Rubles()` (см. ниже — там точно).
- **`FromRublesString` (точный парс, без float):**
  - `"1299.00"→129900`, `"599"→59900`, `"50.5"→5050`, `"0.05"→5`, `"-12.34"→-1234`
  - ошибки: `"1.234"` (>2 дробных), `"abc"`, `""` → возвращают error
- **`Rubles()` — целые рубли, ceil (вверх):**
  - `FromKopecks(59900).Rubles() == 599` (ровно)
  - `FromKopecks(59901).Rubles() == 600` (ceil вверх)
  - `FromKopecks(59999).Rubles() == 600`
  - `FromKopecks(0).Rubles() == 0`
  - `FromKopecks(-59901).Rubles() == -599` (ceil к +∞ для отрицательных)
  - `FromKopecks(-59900).Rubles() == -599`
- **`RublesDecimal()` — точно, 2 знака:**
  - `FromKopecks(129900).RublesDecimal() == "1299.00"`
  - `FromKopecks(59999).RublesDecimal() == "599.99"`
  - `FromKopecks(5).RublesDecimal() == "0.05"`
  - `FromKopecks(-1234).RublesDecimal() == "-12.34"`
- **Арифметика:**
  - `FromRubles(599).MulQty(3).Rubles() == 1797`
  - `FromKopecks(59900).Add(FromKopecks(249900)).Kopecks() == 309800`
  - `Sub` симметрично.
  - `MulQty(0).Kopecks() == 0`
- **Round-trip:** `FromRubles(r).Rubles() == r` для набора целых рублей; `FromRublesString(s).RublesDecimal() == s` для набора `"NNN.NN"`.
- **Zero value:** `var m Money; m.Kopecks()==0; m.Rubles()==0; m.RublesDecimal()=="0.00"`.
- **String:** `FromKopecks(59900).String() == "599.00 ₽"`, `FromKopecks(5).String() == "0.05 ₽"`, отрицательное — `"-12.34 ₽"`.

`go test ./...` зелёный. `go vet ./...` чисто. Без внешних зависимостей в `go.sum` (кроме отсутствия таковых).

---

## 5. README.md (кратко)

- Что это: единый money-тип флота, канон — копейки int64. Канон представления денег — **OPSOMN-12987** (Confluence 165380364): контракты ENSI↔ИС↔OMS — рубли, 2 знака, округление ВВЕРХ; фронт — целые рубли.
- Таблица: какой конструктор/аксессор на какой границе:
  | Граница | Вход/выход | Метод |
  |---|---|---|
  | catalog-cache (рубли-float) | ingress | `FromRublesFloat` |
  | baskets (копейки) | ingress | `FromKopecks` |
  | discount / OMS (рубли decimal-строки) | ingress | `FromRublesString` |
  | **фронт** (BFF: целые рубли `1999`) | egress | `Rubles()` |
  | **OMS/ENSI контракты** (рубли.2знака `"1999.00"`) | egress | `RublesDecimal()` |
  | commit `orderSum` (целые рубли) | egress | `Rubles()` |
  | внутренний / east-west | both | `Kopecks()` |
- Примеры:
  ```go
  m := money.FromRublesFloat(card.Price)      // ingress: catalog-cache рубли-float
  m := money.FromKopecks(item.Price)          // ingress: baskets копейки
  m, _ := money.FromRublesString(d.Price)     // ingress: discount/OMS "1299.00"

  dto.Price = m.Rubles()                       // egress фронт: 1999 (целые рубли, ceil)
  omsReq.Price = json.Number(m.RublesDecimal())// egress OMS/ENSI: "1999.00"
  internal.PriceKopecks = m.Kopecks()          // east-west: копейки

  lineTotal := unit.MulQty(qty)                // суммы — в копейках
  ```
- Жирным: **API-маршалинга нет — конверсия явная на границе** (почему — см. §3.1).

---

## 6. Determination of Done (критерий приёмки)

- [ ] Новый репо `gj-go-money`, module `gitlab.gloria.aaanet.ru/go-pkg/gj-go-money`, `go 1.22`, без внешних зависимостей.
- [ ] `money.go` с типом и всем API из §2; формулы округления точно по §2.
- [ ] `money_test.go` со всеми кейсами §4; `go test ./...` + `go vet ./...` зелёные.
- [ ] README по §5.
- [ ] Нет `MarshalJSON`/`UnmarshalJSON`, нет внешних импортов, нет знаний об апстримах.
- [ ] Добавлен в `platform-new/go.work` (`use ./gj-go-money`) для локальной разработки.
- [ ] Тег `v0.1.0` (после ревью/мёржа — может проставить ревьюер).
- [ ] Потребители (`intgateway`, `checkout`, `clients/*`) в этой задаче **не меняются** — отдельные задачи.

---

## 7. Граница задачи (scope)

**В этой задаче:** только пакет `gj-go-money` + его тесты + README + запись в go.work.
**НЕ в этой задаче:** миграция `intgateway`/`checkout` на тип, решение про published-клиенты (faithful vs нормализующие), правки DTO/адаптеров. Это последующие задачи поверх готового пакета.
