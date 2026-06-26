# ТЗ: миграция `intgateway` на пакет `gj-go-money`

**Тип:** рефакторинг (де-размазывание money-конверсии). **Исполнитель:** отдельная сессия агента-кодера (без памяти — всё нужное ниже). **Ревьюер:** автор ТЗ.

---

## 0. Контекст (зачем) — читать первым

`intgateway` — Go BFF (модуль `gitlab.gloria.aaanet.ru/greensight/gj/go/intgateway`). Сейчас работа с деньгами **размазана и местами на float**:

- **basket-домен:** внутри копейки (`int`), адаптер делает `rubles→kopecks` руками (`×100`), handler делает `kopecks→rubles` руками (`÷100`, half-away). Конверсия дублируется в двух местах с риском разного округления.
- **recommendations-домен:** деньги — **`float64` рубли** end-to-end (нарушение money-policy «никогда float для денег»), просто проброс catalog-cache float наружу.

Готов общий типизированный пакет **`gj-go-money`** (`gitlab.gloria.aaanet.ru/go-pkg/gj-go-money`, канон — `int64` копейки). Эта задача — перевести `intgateway` на него: вся конверсия — через тип, ни одного ручного `×100`/`÷100`/`float`-денежного поля.

### Канон денег (зафиксировано, не обсуждается — OPSOMN-12987)
- Внутри — `money.Money` (int64 копейки).
- **Фронт** (ответы BFF) — **целые рубли** (число `1999`), округление **вверх (ceil)** → `m.Rubles() int64`.
- catalog-cache отдаёт **рубли (float)** → ingress `money.FromRublesFloat(...)`.
- baskets отдаёт **копейки (int)** → ingress `money.FromKopecks(...)`.

### API пакета `gj-go-money` (уже готов, используй как есть)
```go
money.FromKopecks(k int64) Money
money.FromRubles(r int64) Money
money.FromRublesString(s string) (Money, error)
money.FromRublesFloat(r float64) Money   // ingress, round-to-nearest
func (Money) Kopecks() int64
func (Money) Rubles() int64              // целые рубли, CEIL (для фронта)
func (Money) RublesDecimal() string      // "1999.00" (в этой задаче НЕ нужно — контрактов 2-знака тут нет)
func (Money) Add(Money) Money
func (Money) Sub(Money) Money
func (Money) MulQty(qty int) Money
```

---

## 1. Якоря: репозитории и пути (читать перед любым действием)

Проект большой, рядом много других репозиториев — **не перепутай**. Работаешь ТОЛЬКО в репо `intgateway`.

| Что | Абсолютный путь (локально) | Go-модуль | Git remote |
|---|---|---|---|
| **intgateway** (правим ЗДЕСЬ) | `$WORKSPACE/platform-new/intgateway/` | `gitlab.gloria.aaanet.ru/greensight/gj/go/intgateway` | `git@gitlab.gloria.aaanet.ru:greensight/gj/go/intgateway.git` |
| **gj-go-money** (зависимость, НЕ менять) | `$WORKSPACE/platform-new/gj-go-money/` | `gitlab.gloria.aaanet.ru/go-pkg/gj-go-money` | `git@gitlab.gloria.aaanet.ru:go-pkg/gj-go-money.git` |
| go.work (workspace) | `$WORKSPACE/platform-new/go.work` | — | — |

> **`ROOT` = `$WORKSPACE/platform-new/intgateway`.** Все пути файлов ниже даны абсолютно от `ROOT`. Все `git`/`go` команды — из `ROOT` (`cd "$ROOT"` первым делом). НЕ коммить в другие репозитории, НЕ редактировать `$WORKSPACE/platform-new/gj-go-money/`, НЕ трогать workspace-репо `$WORKSPACE` (это набор клонов, не один git).

- **Ветка:** в `ROOT` создать `feat/money-migration`, коммитить туда.
- **Зависимость:** в `$ROOT/go.mod` добавить `require gitlab.gloria.aaanet.ru/go-pkg/gj-go-money v0.1.0`. Локально резолвится через `go.work` (там уже `use ./gj-go-money`). Если `go mod tidy` ругается на отсутствие тега в remote — ожидаемо (тег ставит ревьюер); сборка/тесты в workspace проходят. **НЕ** добавляй `replace`.
- **Импорт в коде:** `money "gitlab.gloria.aaanet.ru/go-pkg/gj-go-money"`.
- **go version / стиль:** 1.26.2. Конвенции — `$ROOT/CLAUDE.md` (handler делает DTO-маппинг; адаптеры в `$ROOT/internal/adapters/<domain>`; generated `apiv1/*.gen.go` НЕ редактировать).

---

## 2. Часть A — basket (главное)

Файлы (абсолютные пути):
- `$WORKSPACE/platform-new/intgateway/internal/domains/basket/types.go`
- `$WORKSPACE/platform-new/intgateway/internal/adapters/basket/manager.go`
- `$WORKSPACE/platform-new/intgateway/internal/adapters/basket/mapping.go`
- `$WORKSPACE/platform-new/intgateway/internal/domains/basket/handler.go`
- тесты: `…/internal/adapters/basket/mapping_test.go`, `…/internal/adapters/basket/manager_test.go`, `…/internal/domains/basket/handler_test.go` (под тем же `ROOT`)

## 2. Часть A — basket (главное)

Файлы:
- `internal/domains/basket/types.go`
- `internal/adapters/basket/manager.go`
- `internal/adapters/basket/mapping.go`
- `internal/domains/basket/handler.go`
- тесты: `internal/adapters/basket/mapping_test.go`, `manager_test.go`, `internal/domains/basket/handler_test.go`

### A1. `types.go` — money-поля → `money.Money`
Заменить тип money-полей с `int`/`*int` на `money.Money`/`*money.Money`. Поля (по комментариям «kopecks»):
- `Cart`: `Price`, `OldPrice *…`, `BonusSum`
- `CartSize`: `Price`, `PriceSum *…`, `OldPrice *…`, `OldPriceSum *…`

`Count`, `CountSelected`, `Number`, `Qty`, `OfferID` и т.п. — **НЕ деньги, не трогать** (остаются `int`). `DiscountRate` — НЕ деньги.
Импорт: `money "gitlab.gloria.aaanet.ru/go-pkg/gj-go-money"`. Обнови комментарии: канон — `money.Money` (копейки внутри).

### A2. `manager.go` — убрать `rublesToKopecks`, использовать ingress-конструкторы
- Удалить функцию `rublesToKopecks(p *float32) int` (и импорт `math`, если больше не нужен).
- Везде, где catalog-cache `*float32` цена клалась в доменное поле — теперь:
  - значение есть → `money.FromRublesFloat(float64(*p))`
  - `nil` → `money.Money(0)` для не-указателей, или `nil` для `*money.Money`.
- baskets-копейки (если где-то берутся напрямую) → `money.FromKopecks(int64(...))`.

### A3. `mapping.go` — собрать суммы через тип
- `priceSum` (= цена × qty для current-размера): `unitPrice.MulQty(qty)` вместо ручного умножения копеек.
- `computeParams`: суммирование `price += *s.PriceSum` → через `money.Money.Add` (аккумулятор `money.Money`, `.Add(*s.PriceSum)`).
- `oldPrice` логика (nil-фильтр «>0») сохраняется, но на `money.Money` (сравнение `> money.Money(0)` или `.Kopecks() > 0`).
- Никаких `×100` в этом файле не остаётся.

### A4. `handler.go` — egress через `money.Rubles()`, удалить `kopToRub`
- Удалить `kopToRub` и `kopToRubPtr`.
- В `toParams`/`toSize` money-поля DTO (они `*int`/`int`, целые рубли — НЕ менять типы DTO) заполнять:
  - `m.Rubles()` для не-указателей,
  - для `*int`-полей: хелпер `rublesPtr(m *money.Money) *int { if m==nil {return nil}; v:=m.Rubles(); return &v }` (один маленький хелпер в handler.go вместо kopToRubPtr).
- Семантика: было half-away `(k+50)/100`, стало ceil (`money.Rubles()`). Для целочисленных рублёвых корзин результат идентичный; ceil — канон.

### A5. Тесты basket
- `mapping_test.go` / `manager_test.go`: фикстуры money — строить через `money.FromRublesFloat(...)`/`money.FromKopecks(...)`; ассерты — через `.Kopecks()`/`.Rubles()`. Сохранить смысл существующих кейсов (priceSum для current, oldPrice nil-фильтр, суммирование).
- `handler_test.go`: уже есть `TestHandler_Current_MoneyConvertedToRubles` (вход копейки → выход рубли). Переписать вход на `money.Money` (`money.FromKopecks(539600)` и т.д.), ожидания в рублях те же (`5396`, `599`).

---

## 3. Часть B — recommendations (убрать float-деньги)

Файлы (абсолютные пути, тот же `ROOT`):
- `$WORKSPACE/platform-new/intgateway/internal/domains/recommendations/types.go`
- `$WORKSPACE/platform-new/intgateway/internal/adapters/recommendations/mapping.go`
- `$WORKSPACE/platform-new/intgateway/internal/domains/recommendations/handler.go`
- тесты: `…/internal/domains/recommendations/*_test.go`, `…/internal/app/wire/recommendations_test.go`

**Цель:** внутри домена/адаптера денег-`float64` больше нет — только `money.Money`. **DTO-контракт НЕ меняем** (остаётся `apiv1` `Price float32` / `OldPrice *float32`) — рендерим из `Money`. Поведение для целочисленных рублёвых цен (реальный случай GJ) не меняется.

### B1. `types.go`
- `ProductCard.Price float64` → `money.Money`; `ProductCard.OldPrice *float64` → `*money.Money`.
- `Size.Price float64` → `money.Money`; `Size.OldPrice *float64` → `*money.Money`.

### B2. `adapters/recommendations/mapping.go`
- Удалить money-хелперы `f32`/`f32ToF64Ptr` **в части денег** (если они используются и для не-денежных полей — оставить для них; для money перейти на `money.FromRublesFloat`).
- catalog-cache `*float32` цена → `money.FromRublesFloat(float64(*p))`; `nil` → `money.Money(0)` / `nil`.

### B3. `handler.go`
- Удалить `f64ToF32Ptr` (money-часть).
- DTO money рендерить из `Money`, **сохраняя тип float32**:
  - `Price: float32(c.Price.Rubles())`
  - `OldPrice:` хелпер `rublesF32Ptr(m *money.Money) *float32 { if m==nil {return nil}; v:=float32(m.Rubles()); return &v }`
- (Да, на проводе остаётся float32 целых рублей `599` — контракт каруселей не меняем. Цель части B — убрать float ИЗ домена, не сменить контракт.)

### B4. Тесты recommendations
- Фикстуры/ассерты money — через `money.*`. Существующий end-to-end тест в `internal/app/wire/recommendations_test.go` (catalog-cache httptest → similar) — проверить, что `out.Items[...].Price` всё ещё ожидаемые целые рубли (цены в фикстуре теста — целые).

> **Если ревьюер решит**, что float-контракт каруселей надо ломать на integer — это отдельная задача (правка OpenAPI `recommendations` + фронт). В ЭТОЙ задаче DTO float32 сохраняем.

---

## 4. Boundary-test и чистота

- `boundary_test.go` доменов: домен теперь импортирует `gitlab.gloria.aaanet.ru/go-pkg/gj-go-money` — это **разрешённый** внешний пакет (money — value-тип, не клиент/инфра). Если boundary-тест белым списком запрещает «всё кроме X» — добавь money в разрешённые (как `reqctx`/`httpx`). НЕ добавляй money в forbidden.
- Никаких ручных `* 100` / `/ 100` / `+ 50` / `math.Round` для денег в `intgateway` после миграции (grep чистый).
- Никаких `float32`/`float64` денежных полей в **доменных** типах (в DTO `apiv1` float остаётся — это контракт).

---

## 5. Проверка

```bash
cd $WORKSPACE/platform-new/intgateway
go build ./... && go test ./... -count=1     # всё зелёное
go vet ./...
# нет ручной money-арифметики:
grep -rnE "\* 100|/ 100|\+ 50|math\.Round" internal --include=*.go | grep -v _test   # ожидается пусто (по деньгам)
```

Ручной прогон (опц., нужен реальный stage-токен) — формат ответа `/api/v1/basket/current` не изменился (целые рубли: `price:5396`, size `price:599`).

---

## 6. Determination of Done

- [ ] `go.mod` requires `gj-go-money v0.1.0`; импорт резолвится (go.work).
- [ ] basket: `types.go` money-поля = `money.Money`; адаптер — `FromRublesFloat`/`FromKopecks` + `MulQty`/`Add`; handler — `Rubles()`; `rublesToKopecks`/`kopToRub`/`kopToRubPtr` удалены.
- [ ] recommendations: доменные money-поля = `money.Money`; адаптер — `FromRublesFloat`; handler рендерит `float32(m.Rubles())`; float-деньги ушли из домена; **DTO `apiv1` не изменён**.
- [ ] Нет ручной money-арифметики и float-денег в доменных типах (grep чист).
- [ ] `go build`+`go test`+`go vet` зелёные; boundary-тесты проходят (money в allow-list).
- [ ] Формат публичных ответов не изменился (целые рубли).
- [ ] Коммит(ы) в ветке `feat/money-migration` в репо intgateway. Мёрж/тег — ревьюер.

## 7. Границы задачи
**В задаче:** только `intgateway` (basket + recommendations) на `money`. **НЕ в задаче:** `checkout` (отдельное ТЗ, там осторожно с `session/digest` и OMS-границей), смена контракта каруселей float→int, правки `clients/*` и `gj-go-money`.
