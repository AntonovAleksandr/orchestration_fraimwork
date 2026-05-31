# checkout — design (TO-BE чекаут, v1: walking skeleton)

**Дата:** 2026-05-29
**Статус:** на ревью
**Автор:** Zak + Claude (brainstorming)
**Репозиторий:** `https://gitlab.gloria.aaanet.ru/e-commerce/platform/checkout` (заведён, пустой)
**Грунт (обязательно к прочтению):** [`../../research/2026-05-29-checkout-as-is-archaeology.md`](../../research/2026-05-29-checkout-as-is-archaeology.md), [`../../research/2026-05-29-order-create-contract.md`](../../research/2026-05-29-order-create-contract.md)

---

## 1. Контекст и цель

Текущий чекаут (PHP Integration + ENSI `customers-api-web` + жирная `general-data`) болен структурно: декартова матрица «способ × склад × поштучная доступность», перерисовка фронта по любому чиху, interval-drift → `400`, маскировка провала под `200 success:false`. Прод: ~4,5k созданий/сутки, **~77 срывов/сутки на interval-drift**, маскируемых под успех (web).

Строим **новый сервис `checkout`** на новой платформе e-commerce — **stateful Go-домен по стандарту `ecom-gateway`** — который владеет персистентной **сессией выбора**, отдаёт **гранулярный** пред-чекаут (не матрицу), делает **честный идемпотентный commit** и **устраняет drift** пиннингом даты + серверным примирением. Стратегия — **strangler**: живёт параллельно legacy, забирает новый поток, со временем замещает Integration-чекаут + ENSI commit.

**Замковый камень дизайна** (из контракт-дока): OMS пермиссивен и доверяет — реально нужен `{stable client_order_id, customer(id/phone), recipient, items(productId,qty,price,discount), delivery selection, totals-checksum, paymentType, ≥1 package}`. Всё остальное OMS пере-выводит или делает сам в Camunda. Значит пред-чекаут — это машина для сборки **одного валидного выбора + устойчивого id + checksum**, радикально тоньше general-data.

### Архитектурные решения (зафиксированы на брайнсторме)

- **Отдельный stateful сервис `checkout`** (не внутри ecom-gateway — тот остаётся чистым BFF; не в OMS — не тащим тяжёлую работу в Java).
- **Стек = как у `ecom-gateway`:** Go 1.26.x + `net/http` + `chi/v5` (ADR-0002), spec-first `oapi-codegen` types-only, `gj-go-logger`, Prometheus, структура по `go-service-guideline.md v1.0`. В отличие от gateway — **stateful**, поэтому §4 guideline применяется: **pgx + репозитории** (Postgres), миграции — через **`go-pkg/gj-go-migrate`** (канон флота, не самопал).
- **Тракт фронта:** `site/mobile → ecom-gateway (тонкий BFF, north-south) → checkout`. `checkout` — внутренний, наружу не торчит.
- **East-west зависимости (по API, не через PHP Integration):**
  - **OMS api-gateway (Starfish API, `apidoc.starfish24.com`)** — logistics (гранулярная доставка + пиннинг даты) и order/create. **Новый Go-клиент** `clients/starfish-oms` на substrate `gj-go-httpclient` (как `clients/catalog-cache`). Чтим контракт OMS, убираем из тракта PHP-обёртку.
  - **ENSI** — `baskets` (корзина), `catalog-cache` (товары; клиент уже есть), `customers` (профиль/адреса), `offers`/promo (цены/скидки). Эти не болят — переиспользуем.
  - Своя **Postgres** — сессия выбора.
- **Корзина:** **snapshot при входе** в сессию + **ре-валидация на commit** (сверка с живой корзиной/стоком).
- **Идемпотентность:** `client_order_id` = **номер корзины** (минтит ENSI baskets, не checkout; `basket# = order#`), стабилен на ретраи (закрывает дыру OMS, где `null` → дубли). На create корзина потребляется, остаток → новая корзина (§2b).

---

## 2. Доменная модель — Checkout Session

Серверный объект в БД `checkout`. Создаётся при входе в чекаут, живёт до commit или TTL (~30–60 мин). Одна активная сессия на (customer + basket).

```
CheckoutSession  — подготовка ОДНОГО заказа (текущая логика; остаток → новая корзина)
  checkout_id        UUID (PK)
  customer_id        string
  basket_id          string
  client_order_id    = НОМЕР КОРЗИНЫ (basket#)  ← минтит baskets (ENSI), НЕ checkout.
                       basket# = order# = DOC скидок = idemp-ключ OMS.
  status             draft | selecting | revalidating | ready | committing | committed | conflict | failed | expired
  cart_snapshot      []CartLine        — снимок НАМЕРЕНИЯ (productId, qty, price@snapshot); НЕ truth
  fulfillment        FulfillmentChoice — выбранный способ + точка
  selected_komplektaciya  Komplektaciya — комплектация (подмножество корзины), из которой создаётся ЭТОТ заказ
  identity           {phone, sms_verified}  — аноним: phone + СМС-код («Мои данные»)
  recipient          Recipient         — {first_name, last_name, phone}; authed → из customers ensi
  address            Address           — курьер: fias + кв/подъезд/этаж/домофон/комментарий + координаты
  promo_intent       PromoIntent       — промокод/бонусы (намерение; бонусы только для authed)
  payment_method     SBP | CARD_ONLINE | ON_RECEIPT   (SBP/CARD = prepay через YooKassa/ЮMoney-виджет; ON_RECEIPT = POST)
  auth_context       anon | authed     — authed разблокирует копить/списывать бонусы + предзаполнение
  totals_checksum    money             — последняя показанная сумма
  created_at / updated_at / expires_at
```

```
Komplektaciya  — = inventory одного интервала OMS logistics (подмножество корзины)
  items              []{productId, qty}   — «X из N товаров»
  delivery_type      C&R (самовывоз) | C&C (склад→магазин) | PVZ (склад→ПВЗ) | COURIER (источник — серверный)
  point              store_id | pickup_point_id(+carrier: Почта/5Post) | courier_address | warehouse_id
  interval_id        string
  dispatch_date      date     ← ПИНИТСЯ (anti-drift)
  promissed_date     date
  time_window        {from,to}  — только курьер (9-12…18-21); ПВЗ/магазин — без слота
  carrier_id / carrier_tariff_id / logistic_group_id / delivery_rule_id
  delivery_cost      money     — 0 (магазин/курьер) | 299 (ПВЗ) и т.п.
  features           {try_on: bool, passport_required: bool (ПВЗ), storage_deadline: date,
                      timing_label: "соберём за 30 мин" | "завтра и позже" | "дата-диапазон",
                      oversize/overweight: bool (ПВЗ-перевозчик отказал по габаритам/весу:
                      orderDimensions/Weight/PackageWeightExceeded)}
  carrier            ПВЗ: 5post | russianpost | cdek | dpd | yandex; курьер: dpd/…; магазин: gloriajeans
```

**Жизненный цикл:** `draft` → `selecting` (точечные мутации) → `revalidating` (ре-резолв волатильного) → `ready` → `committing` → `committed` (заказ создан, остаток → новая корзина) | `conflict` (409) | `failed` | `expired`.

### 2b. Split корзины — текущая механика и ОТКРЫТЫЙ таргет

**Сейчас (воспроизводим в новом checkout):** на commit создаётся **ОДИН заказ** из выбранной комплектации; товары, не попавшие в неё, **переезжают в новую корзину** (старая удаляется, т.к. `basket# = order#`). Split решается последовательно: оформил что можешь → остаток в свежей корзине → чекаут заново.

**Таргет — НЕ выбран** (решаем отдельно; бизнес очень хочет закрыть боль сплита). Кандидаты: (1) пачка заказов сразу + сущность **мастер-заказ**; (2) **один заказ — несколько отправлений (shipments)**. Сейчас склоняемся к более простому — **несколько заказов, каждый со своим жизненным циклом**.

**Шов:** комплектация — first-class в отображении/выборе; модель сессии и контракт держим расширяемыми (сессия может стать оркестратором пачки), но в этом дизайне commit = один заказ + spill остатка, как сейчас.

### 2c. Delivery/Komplektaciya resolver — ЯДРО СЛОЖНОСТИ (главный риск)

Вся боль чекаута — инварианты **точка × комплектация × интервал**. В legacy они размазаны по слоям (отсюда болезнь). **Решение: запереть их в ОДНОМ ограниченном компоненте** `delivery` за чистым портом, как чистую трансформацию выдачи OMS logistics → доменные комплектации/точки/дайджест. Остальной checkout (сессия, commit, оплата) зависит ТОЛЬКО от его выхода (выбранная комплектация), не от внутренностей.

**Инварианты, которые resolver обязан держать (и покрыть тестами на фикстурах):**
1. **Coverage:** каждая точка/комплектация покрывает подмножество строк корзины («X из N»); сумма выбранных может не покрыть всю корзину → остаток в spill.
2. **Типы точек/источники:** магазин (C&R сток-в-магазине / C&C со склада), ПВЗ (Почта/5Post, со склада), курьер (из магазина/со склада — выбирает сервер). У каждого свои coverage/тайминг/цена/features.
3. **Интервалы:** на (точку, комплектацию) — один/несколько интервалов; дата (+тайм-слот у курьера). Несколько интервалов = разные наборы/тайминг («15 за 30мин» vs «12 на 28авг»).
4. **Атрибуты опции:** цена (0 / 299), try_on, passport_required (ПВЗ), storage_deadline, timing_label, часы работы.
5. **Стабильность id:** interval id = хэш с `dispatch_date` (из now) → **пин даты** + примирение на commit (§6).
6. **Политика «лучшего»:** дефолтный выбор комплектации/интервала на способ (макс. coverage / раньше / дешевле) — заменяемая стратегия.
7. **Волатильность:** сдвиг стока меняет coverage/split/интервалы → ре-резолв на `revalidating`, diff → 409.
8. **Гео/город:** logisticGroup по городу/полигонам; смена города → ре-резолв всего.
9. **Два уровня:** per-method дайджест (вход) vs per-point детали (drill-in).

**Стратегия снижения риска:** resolver — чистые функции над DTO logistics → **табличные/фикстурные тесты** (мульти-точка, частичное покрытие, мульти-интервал, drift, смена города). Это самый тестируемый юнит. В **v1 walking skeleton** стаб `DeliverySource` отдаёт канонические фикстуры, прогоняющие ровно эти инварианты, — чтобы контракт resolver’а и поведение сессии/commit были выверены ДО реального OMS. Реальный адаптер (фаза 2) подменяется без изменения домена.

---

## 2a. Персистентное состояние и волатильность (store intent, not truth)

**Главный принцип:** сессия персистит **РЕШЕНИЯ пользователя (intent)**, а НЕ **ИСТИНУ**. Всё волатильное (сток, цена, скидка, интервалы, состав корзины) живёт у источника, **пере-выводится при чтении** и **ре-валидируется на commit**. «Последнее показанное» (цена/итоги) хранится только как *advisory* для diff и checksum — не как claim доступности. Это снимает риск «разлёта» при долгом dwell.

### Карта истины

| Данные | Источник истины | Волатильность | Что хранит checkout |
|--------|-----------------|---------------|---------------------|
| Сток/доступность | OMS stock / ENSI catalog-cache | высокая | ничего (всегда live) |
| Цена | ENSI offers | средняя | last-shown (advisory, checksum) |
| Скидка/купон/бонус | сервер скидок (`WWWDK_API`, вне екома) | высокая, **без hold** | intent (какой купон/бонус) + advisory quote |
| Интервалы/комплектация | OMS logistics | высокая (время!) | выбор + **pinned `dispatch_date`** |
| Состав корзины | ENSI baskets | средняя (др. вкладка) | snapshot **намерения** (productId+qty), не truth |
| Профиль/адрес | ENSI customers | низкая | выбор |

### Состояние `revalidating`

На возврате в чекаут И в начале commit — пере-резолв всего волатильного и **diff** против intent/last-shown. Материальный diff → `conflict` (HTTP 409, явное «подтвердите изменения»), не тихий пропуск и не 400.

### Резерв / оверселл — РЕШЕНИЕ: принять окно

Сток **не резервируется** в пред-чекауте (принцип fashion-екома + текущий GJ: конверсия важнее). Резерв — за OMS `confirmationProcess` **после** create (`createReservation` по `dispatchWarehouseId`/`pickupStoreId`). Значит **окно оверселла открыто весь чекаут** — это осознанно принято. Митигация: `checkout` делает **строгую ре-валидацию стока непосредственно перед** OMS create (два чтения: OMS stock + ENSI catalog-cache, как сейчас). Если резерв всё же сорвётся downstream — заказ уходит в отмену/частичный с уведомлением (поведение OMS). Soft-reserve/hold НЕ вводим (нет stock-hold API; overkill для fashion).

### Скидки — РЕШЕНИЕ: spend на create в durable-саге (не ломаем legacy)

Подтверждено по коду сервера скидок (`WWWDK_API/Models/4.1/BonusSpend.cs`, `4.4/BonusSpendExt.cs`):
- **Spend идемпотентен по `DOC` (= SaleId + `client_order_id`)** — повтор с тем же DOC = no-op (нет двойного списания). Откат — тоже по DOC.
- **Hold/TTL нет.** Купон = одноразовая карта (`crd.Block`); quote (`GetDiscount`) ничего не держит.
- Текущее поведение = **spend на создании заказа (до оплаты) + Rollback при отмене**.

TO-BE сохраняет это поведение, но делает надёжным: **re-quote** перед create (advisory, сверка checksum) → OMS create → **spend как шаг durable-саги** с `DOC=client_order_id` → payment link. Любой сбой шага → компенсация (`Rollback` по тому же DOC). Идемпотентность ретраев дана нативно (сервер дедупит по DOC + наш стабильный `client_order_id`). Отмена/неоплата 24ч → `Rollback` как компенсация (по событию OMS). **COD не ломается** (нет отдельного пути).

### Корнер-кейсы (учтены в дизайне)

1. Долгий dwell + возврат → `revalidating`, показать diff.
2. Сток упал/исчез → строка недоступна/qty не хватает → 409 (политика частичной доступности — §ниже).
3. Гонка за последней единицей → оверселл, ловится резервом OMS post-create.
4. Цена изменилась → checksum mismatch → 409.
5. Купон протух/использован → re-quote перед create ловит; spend в саге с компенсацией.
6. Интервал уплыл → pinned date + серверное примирение → 409 если материально.
7. Частичная доступность (1 из N OOS) → **дефолт: all-or-nothing** (409 «уберите недоступное, чтобы продолжить»); split — на будущее.
8. Оплата в полёте (PREPAID 24ч) → заказ создан, резерв держит OMS, скидка списана (legacy), откат при таймауте.
9. Ретрай commit при OMS-локе (30с) → 409 pending; идемпотентность по `client_order_id`.
10. Сирота (create прошёл, шаг после упал) → durable-сага компенсирует, не fire-and-forget.

---

## 3. API-поверхность (гранулярный пред-чекаут + commit)

Контракт `checkout` (внутренний; ecom-gateway проксирует north-south). **Гранулярность — лекарство от «моргания» (рычаг №1):** каждая мутация трогает только свою часть и возвращает только затронутый фрагмент + пересчитанные итоги, не декартову матрицу.

| Метод | Назначение | Шаг |
|-------|-----------|-----|
| `POST /checkout` | создать сессию из basket (snapshot) → `checkout_id` + контекст с **per-method дайджестом** | — |
| `GET /checkout/{id}` | текущее состояние сессии (итоги, выбор, получатель) | — |
| `GET /checkout/{id}/points?type=store\|pvz` | **drill-in** карта/список точек способа: на точку coverage «X из N» + тайминг/цена/features (метод-специфично) | Доставка |
| `GET /checkout/{id}/delivery-options?type=courier&address=` | **drill-in** курьер: резолв интервалов/тайм-слотов для адреса | Доставка |
| `PATCH /checkout/{id}/delivery-method` | выбрать способ → авто-резолв «лучшей» комплектации + **пин `dispatch_date`** → фрагмент + итоги | Доставка |
| `PATCH /checkout/{id}/komplektaciya` | сменить точку/интервал/слот (выбор из списка комплектаций способа) | Доставка |
| `PATCH /checkout/{id}/identity` | телефон + запрос/проверка СМС-кода (аноним) | Получатель |
| `PATCH /checkout/{id}/recipient` | получатель {имя, фамилия, телефон}; authed → префилл из customers ensi | Получатель |
| `PATCH /checkout/{id}/payment-method` | `SBP \| CARD_ONLINE \| ON_RECEIPT` | Оплата |
| `PATCH /checkout/{id}/promo` | промокод/бонус (намерение) | Оплата |
| `POST /checkout/{id}/commit` | идемпотентное создание заказа + spill остатка (см. §4); для онлайн-оплаты вернуть токен виджета | Оформление |

**Два уровня доставки (дизайн «Способ получения»):**
- **На входе** (`POST /checkout`, `GET /checkout/{id}`) — **компактный per-method дайджест**: на каждый способ (ПВЗ / курьер / магазин) → `{coverage "X из N товаров", лучший интервал (даты/цена/features), предзаполненная точка из customers ensi}`. Это НЕ декартова матрица general-data — это дайджест на способ.
- **На «Изменить»** (`delivery-options?type=`) — детальные интервалы/точки/комплектации этого способа.
- **«Лучший интервал/комплектация» — серверная политика** (как у IS), вынесена в заменяемый резолвер (дефолтный выбор).

**Шаги визарда (степпер UI):** `Доставка → Получатель → Способ оплаты → Оформление`. Гранулярные эндпоинты = шаги; сессия прогрессирует по ним. `selected_komplektaciya` — **ВЫБОР пользователя из списка комплектаций способа** (radio «Состав заказа»: напр. «15 из 19 соберём за 30 мин» vs «12 из 19 доставим 28 авг»), дефолт = серверная «лучшая».

**Примерка ⟂ оплата:** `features.try_on` (примерка перед выкупом) — атрибут комплектации/способа (только отображение). `payment_type` — **ОТДЕЛЬНЫЙ** выбор на шаге «Способ оплаты»: `PREPAID` (онлайн сейчас) | `POST` (оплата при получении/выкуп). Ортогональны: бывает «примерка + онлайн-оплата» и «примерка + выкуп на месте». Сага spend-на-create + Rollback (§2a) покрывает оба.

**Сводка заказа (правая панель, отдаём как summary):** items+сумма, стоимость доставки, **начисление бонусов** (earned, напр. +25), **разбивка скидки** (промокод / Скидка GJ / списанные бонусы — из сервера скидок), адрес/дата, **срок хранения** (для самовывоза/ПВЗ), Итого. Бонусы (копить/списать) — только для залогиненных → сессия знает **auth-контур** (anon vs authed).

### ПВЗ-карта: viewport + кластеризация (масштаб — отдельная боль)

ПВЗ в крупном городе — **тысячи точек**. Замер на stage (Москва, корзина из 4): один `pickup-points/v1` = **3963 точки / 3.5 МБ** (5post 1766, russianpost 999, cdek 841, dpd 180, yandex 177). Грузить все — медленно (вызов подвисает) и нечем рисовать карту. Сейчас фронт **костылит кластеризацию у себя**. Переносим в checkout:
- **Всегда bbox-bound:** `GET /checkout/{id}/points?type=pvz&bbox=<sw,ne>&zoom=<z>`. OMS умеет фильтр по прямоугольнику — `areaViewPort{latitude,longitude}` (есть в `pickup-points` v2). Полную выборку города НЕ запрашиваем никогда.
- **Серверная кластеризация по zoom:** низкий зум (город) → отдаём **кластеры** `{lat,lng,count}` (грид/geohash-агрегация в checkout), без поштучного coverage; высокий зум (улица) → реальные точки с coverage «X из N» + детали. Порог по count/zoom.
- **Разделяем гео и coverage:** *гео ПВЗ* (где точки, перевозчик, часы) — cart-независимое, медленно меняется → кэшируемо/пре-кластеризуемо; *coverage «X из N»* — cart-зависимое, тяжёлое → считаем только для точек в текущем viewport (или лениво при фокусе на точке). Кластерам coverage не нужен (только count).
- Это убирает фронтовый костыль в одно тестируемое место и держит ответ маленьким.

**Контракт карточек/товаров** — полный `ProductInterface` фронта (как в catalog-cache-client), без поштучного взрыва.

---

## 4. Data flow

### Пред-чекаут (без матрицы, без «моргания»)
```
POST /checkout
  ← ENSI baskets (snapshot + client_order_id = basket#) + catalog-cache (карточки) + customers (профиль/адреса/прошлые точки)
  → status=draft, вернуть контекст: per-method ДАЙДЖЕСТ (coverage "X из N" + лучший интервал + предзаполненная точка)

PATCH /delivery-method {type}
  ← OMS logistics: авто-резолв лучшей комплектации способа (granular), с ПИНОМ dispatch_date
  → записать selected_komplektaciya (+ pinned date), вернуть ТОЛЬКО фрагмент delivery + новые итоги
  (смена города/способа/qty НЕ перезапрашивает весь контекст — точечно)

GET /delivery-options?type=  (drill-in «Изменить»)
  ← OMS logistics: детальные интервалы/точки/комплектации этого способа (по требованию)
```

### Commit (честный, идемпотентный, two-phase truth, сага)
```
POST /checkout/{id}/commit   (идемпотентен по checkout_id/client_order_id)
  1. Ре-валидация стока: cart_snapshot ↔ живая корзина + сток (OMS stock + ENSI catalog-cache).
     Расхождение → 409 "корзина изменилась". (резерва нет — окно оверселла принято, §2a)
  2. Примирение доставки: пере-резолв interval c ПИНЕНОЙ датой (OMS logistics).
     Изменился → 409 "выбор обновился, подтвердите".  (drift больше НЕ 400 в лицо)
  3. Two-phase truth: пере-вывести цену (ENSI offers) + RE-QUOTE скидок (сервер скидок GetDiscount, advisory),
     сверить с totals_checksum. Расхождение → 409 "сумма изменилась".
  4. Собрать ЧИСТЫЙ payload OMS (см. §5): без qty-explosion, типизированные поля, stable client_order_id.
  5. durable-сага (шаги записаны в БД checkout, идемпотентны, с компенсациями):
     a. POST OMS order/create (идемпотентно по client_order_id). Честный статус: 201+ref | реальный 4xx.
     b. discount spend (DOC=client_order_id, идемпотентно сервером; компенсация Rollback по DOC).
     c. онлайн-оплата (SBP/CARD_ONLINE): payment token/link (getlink) для ЮMoney/YooKassa-виджета. ON_RECEIPT — шаг пропускается.
     Сбой шага → компенсация предыдущих. Отмена/неоплата 24ч → Rollback скидок по событию OMS.
  6. SPILL остатка: товары не из выбранной комплектации → новая корзина (старая = client_order_id удаляется).
     Новый basket# станет client_order_id для следующего чекаута остатка.
  7. status=committed, вернуть order ref (+ payment token для онлайн-оплаты).
```
> Текущая механика split: один заказ + spill. Под целевой мульти-заказ шаг 5 станет циклом по комплектациям (§2b), шаг 6 уйдёт.

---

## 5. Целевой контракт payload в OMS (чистый)

Собираем минимум из §0 контракт-дока, **выкидывая наведённые костыли**:

| Сохраняем (типизированно) | Выкидываем (костыль AS-IS) |
|---------------------------|----------------------------|
| `client_order_id` (стабильный) | qty-explosion (N позиций по 1шт + `position` attr) → шлём `{productId, quantity, unitPrice, lineDiscount}` |
| customer (id/phone) + recipient | хардкод-габариты package 0.1³/900г → package = выбранная комплектация с реальными вес/габаритами |
| items `{productId, quantity, price, discount}` | custom-attr side-channel (`totalBaseAmount`, `deliveryDaysCount`, `discountIntegrationCallbackData`, …) → first-class поля |
| shipping selection (type, interval_id, **pinned date**, warehouse/pvz, carrier+tariff, logistic_group/rule, address) | `payableCost`-дубль |
| totals (checksum) + paymentType | рудимент `payment[].cardNumber` |

**two-phase truth сохраняем как зерно:** клиент/сессия дают выбор + checksum, `checkout` пере-выводит деньги/сток/скидки на сервере. OMS дальше доверяет и сам делает резерв/фрод/маршрут/экспорт в Camunda (создание НЕ стартует процесс — это Kafka `ORDER_CREATED` downstream).

### Деньги: копейки vs рубли (КРИТИЧНО — см. `../../research/2026-05-30-money-kopecks-rubles.md`)

Известная мина GJ (Jira OPSOMN-12987/11196/14721): ENSI offers хранит цену в **копейках (int 59900)**, а контракт ENSI↔ИС↔OMS по канону — **рубли с 2 знаками, округление вверх**; конверсия местами теряется/смешивается → «лишние нули» и `InvalidateTotalCost` 400 (смешанные единицы: `items.price` в копейках + `totalCost` в рублях).

**Политика нового checkout:**
- Внутри — деньги **`int64` копейки + тип `Money`**, НИКОГДА `float64` (все `money`/`number,double` поля в этом доке — это `Money`-копейки).
- Единица известна на КАЖДОЙ границе клиента; адаптер нормализует вход → копейки: `offers`=копейки 1:1; `starfish-oms` logistics/order = **рубли-decimal** (вход ÷, выход × по канону 2 знака округл.вверх; в фикстурах `deliveryCost:299`/`actualDeliveryCost:317.2` = рубли); `discount` = подтвердить единицу.
- **Checksum/two-phase-truth — сравнение `int64` копеек** (без float-эпсилон) → убивает `InvalidateTotalCost`-by-rounding.
- **Один payload OMS — одна единица** (рубли-decimal по канону): `items.price`/`discount`/`totalCost`/`deliveryCost` согласованы. Скидку всегда re-quote перед сверкой.

---

## 6. Ошибки и честность

- **Честный HTTP-статус:** код ответа commit = реально ли создан заказ. OMS 4xx → 4xx наружу; никакого `200 {success:false}`. (Единый error-envelope `{error, message}` как в ecom-gateway, `internal/httpx`.)
- **`409 Conflict` вместо тихого провала:** изменение корзины/выбора/суммы → явный «подтвердите обновление», не `400` и не маскировка.
- **Drift закрыт на корню:** пин `dispatch_date` (хэш id OMS перестаёт плыть) + серверное примирение если всё же протухло (ёмкость/сток). **Уточнение по реальным ответам OMS:** хэшируемый interval-`id` (плывёт) — у **курьера** (`/logistics/delivery-intervals`) И у **ПВЗ** (`/logistics/pickup-points`, поле `id`+`originalId`); **магазины** (`pickup-stores`) — без хэша, ключ = `store.code`/`warehouseId` + `dispatchDate`. Пин даты критичен для курьера и ПВЗ. **Drift — ступенчатый, не непрерывный:** id = детерминированный хэш входов, стабилен в пределах picking-волны; «прыгает» лишь на границе (cut-off волны / смена суток) или при сдвиге стока/ёмкости. Проверено вживую: 2 снимка курьера через минуту → все 15 id совпали. Пин `dispatch_date` фиксирует переменную, прыгающую на границе → id стабилен и после пересечения cut-off на commit. **НО пин даты — не вся история:** в хэш id входит и `deliveryCost`, который зависит от суммы корзины через порог бесплатной доставки (реальный пример: та же корзина — сырой OMS `id=QOOcGGOK, cost=299` vs general-data после free-threshold `id=vn14dWsQ, cost=0`). → **примирение на commit не должно матчить интервал по полному хэшу id**: матчить по `(dispatch_date, warehouse, time_window, carrier, tariff)` и принимать пересчитанную стоимость, либо пиннить и стоимость. Иначе пересечение порога бесплатной доставки = `SelectedIntervalNotFound`.
- **Идемпотентность:** сессия — единица идемпотентности; повтор commit безопасен; OMS дедупит по `client_order_id`.
- **Сага/компенсация** для купона/бонуса/оплаты (AS-IS делает fire-and-forget без отката).

---

## 7. Наблюдаемость, телеметрия

По стандарту ecom-gateway: Prometheus (3 обязательных HTTP-метрики через middleware; `path` = шаблон маршрута), `gj-go-logger` через `ctx` с `request_id`, `/health/live` + `/health/ready` (ready чекает БД + критичные порты). Доменные метрики: `checkout_commit_total{outcome}` (created/conflict/upstream_error), `checkout_delivery_reconcile_total{result}` (stable/repinned/failed) — чтобы измерять, что drift реально закрыт.

---

## 8. Тестирование

- `boundary_test.go` (границы пакета домена).
- Сквозные тесты сессии + commit на **стаб-портах** (детерминированные OMS/ENSI) — форма ответа = DTO из openapi.gen.go; идемпотентность commit; `409` на расхождениях; пустой/невалидный выбор.
- Табличные тесты маппинга доменных ошибок → HTTP.
- Тесты репозитория сессии на реальной БД (§10.3 guideline — БД есть).
- Контракт-линт в CI: `redocly lint` + diff-gate `go generate`.

---

## 9. Объём v1 — walking skeleton (DoD)

Как стартовал ecom-gateway: production-grade каркас по стандарту + сессия в БД + гранулярный контракт и commit на **STUB-портах** (без реальных OMS/ENSI).

**В v1 входит:**
- Скаффолд по `go-service-guideline` (thin main, `internal/{app,config,http,httpx,observability,health}`, домен `checkout`).
- **Postgres + pgx + repo** для `CheckoutSession` (это отличие от stateless gateway); миграции через **`gj-go-migrate`**.
- Гранулярная API-поверхность (§3) с реальной логикой сессии, но **стаб-адаптерами** портов (`DeliverySource`, `CartSource`, `OrderSink`, `PricingSource`, `DiscountSource`, `CustomerSource`) — детерминированные заглушки.
- **Komplektaciya-resolver (§2c)** — реальная доменная логика (чистые функции) + фикстуры стаб-`DeliverySource`, прогоняющие инварианты точка×комплектация×интервал. Это самый тестируемый юнит v1.
- Идемпотентный `commit` с честным статусом и `409`-семантикой на стаб-данных.
- Пиннинг даты и примирение — реализованы против стаб-DeliverySource (проверяемо детерминированно).
- Observability/health/metrics; Dockerfile; OpenAPI + генерация.

**DoD:** `make generate` + `redocly lint` зелёные; `go build/vet/test` зелёные; миграции применяются; сервис стартует; `/health/*`, `/metrics` отвечают; сквозной сценарий create→select→commit на стабах проходит; Docker собирается.

---

## 10. Явно вне v1 (следующие фазы)

- **Фаза 2 — реальные клиенты:** `clients/starfish-oms` (logistics + order/create, реальный пиннинг даты), ENSI baskets/catalog-cache/customers/offers; реальный commit + сага; решение auth/connectivity к OMS api-gateway (креды/JKS-эквивалент Integration).
- **Фаза 3 — фронт:** роутинг через ecom-gateway; интеграция site за GrowthBook-флагом (как `NEW_CHECKOUT`); переписать потребление на гранулярный контракт (убрать decart-матрицу из NgRx SignalStore); mobile — позже.
- **Не делаем сейчас:** корзина/оплата как домен (остаются ENSI/YooKassa-контур); **split-таргет** (мастер-заказ / мульти-отправление / мульти-заказ — §2b, бизнес-решение) — пока текущая механика «один заказ + spill»; edge-роутинг трафика; distributed tracing.

---

## 11. Открытые вопросы (грунт перед фазой 2)

1. **Живая JSON-схема `order_create`** OMS (`api.validation.json_schema.external.service.name` в `awg/cloud-configs/<env>` → `GET /validation/schema/order_create`) — авторитетный список обязательных полей. → `oms-java-engineer`.
2. ~~**Где минтится `client_order_id`**~~ — **ЗАКРЫТО**: это **номер корзины** (ENSI baskets); `basket# = order#`. На create корзина потребляется, остаток → новая корзина с новым номером. (Деталь к подтверждению: точный механизм spill/пересоздания корзины в baskets — для воспроизведения в новом checkout.)
2a. **Split-таргет — ОТКРЫТО (бизнес-driven):** мастер-заказ + пачка vs один заказ — несколько отправлений vs несколько заказов со своим ЖЦ (текущий фаворит). Влияет на payment-cardinality и аллокацию скидки по сплиту. Решаем отдельно; в этом дизайне сохраняем текущую механику (один заказ + spill), §2b.
3. **OMS api-gateway:** какие именно роуты Starfish API соответствуют logistics/order/create и какая авторизация для внешнего вызова (свериться с `apidoc.starfish24.com` + конфиг Integration OmsClient).
4. **`ORDER_CREATED` → `confirmationProcess` binding** (`core/Camunda`) — для понимания, что происходит после нашего create. → `camunda-bpm-engineer`.
5. Стандарт нового Go-сервиса (рычаг «канон»): свериться с актуальным `go-service-guideline` + ADR ecom-gateway (0002 chi, 0008/0009 client fleet) — `checkout` должен быть эталонно-конформен.
7. **ПВЗ-масштаб/кластеризация:** точная форма `areaViewPort` (apidoc OMS); считает ли OMS coverage (inventory) для ВСЕХ точек в bbox (если да — bbox должен быть мал) или есть лёгкий «гео-only» вызов; кластеризует ли OMS сам или это работа checkout (по факту — checkout). `pickup-points/v1` без bbox грузит весь город и подвисает — не использовать на карте.
