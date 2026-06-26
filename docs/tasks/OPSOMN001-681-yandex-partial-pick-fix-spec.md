# ТЗ: Yandex partial-pick / cancel — `parameters`-enrichment + `item_barcode` через `request/info`

> Документ для отдельной агентской сессии (другой агент). Самодостаточный: всё необходимое — ниже.
> Тикеты: **OPSOMN001-681** (items/remove), **OPSOMN001-693** (NRE на отмене). Смежный: **OPSOMN001-683** (трекинг статусов — уже исправлен, не трогать).

---

## 0. Постановка (TL;DR)

В интеграции OTS ↔ Яндекс.Доставка при частичной сборке (partial pick) и при отмене заказа есть две связанные проблемы:

1. **`OTSOrderParams.parameters` приходит `null`** (из входящего Starfish-сообщения и из restored-JSON), а Yandex-пути читают/пишут `parameters[EXTERNAL_TK_ID]` → `NullReferenceException` (в update и в cancel). DPD-пути этого избегают, т.к. идут через общий enrichment, а Yandex — нет.
2. **`item_barcode` для `items/remove` — это внутренний штрихкод Яндекса**, который надо предварительно получить методом `request/info` (поле `items[].barcode`) и сматчить с нашей позицией по `article`. Сейчас OTS шлёт в `item_barcode` артикул (SKU) → Яндекс отвечает `400 bad_request: "Item with barcode ... does not exist in the order"`.

Нужно: (A) системно гарантировать заполнение `parameters` из БД-tracking перед Yandex-вызовами + сделать поле never-null; (B) добавить вызов `request/info` и брать `item_barcode` оттуда по джойну на `article`.

**Часть A — предусловие для части B** (без `EXTERNAL_TK_ID` нечем звать `request/info`).

---

## 1. Рамки проекта (scope / boundaries)

- **Репозиторий:** `gloriaots/gloriaots` (GitLab: `git@gitlab.gloria.aaanet.ru:gloriaots/gloriaots.git`).
- **Локальный клон (рабочая директория):** `$WORKSPACE/platform/gloriaots/gloriaots`
- **Ветка:** `yandex-fix` (уже создана от `staging`). В ней уже закоммичены фиксы 681 (`3c7e86e7`) и 683 (`8811dbb7`).
- **Стек:** .NET 10, ASP.NET Core, EF Core (SQL Server), Refit (Yandex API client), System.Text.Json.
- **Только этот репозиторий.** Не трогать другие платформы в `$WORKSPACE/platform/*`.
- **Не трогать:** метод трекинга статусов `MapToOrderIntegrationResult(GetRequestHistoryResponse ...)` (683, уже исправлен); другие ТК (FIVEPOST/RUSSIANPOST/CDEK/DPD/OWN) — они берут `tkInvoiceId` из tracking напрямую и от `parameters` не зависят; контракт с Яндексом и create-payload менять не нужно.
- **Не коммитить и не пушить** без явной команды пользователя. Работать в `yandex-fix`.

---

## 2. Контекст и подтверждённые факты

### 2.1 Как устроен поток
- Partial pick: Starfish → OTS присылает `ORDER_TO_EDIT` со статусом `ORDER_REGISTER_TRANSPORT`. Хендлер `OrderRegisterTransport` → `IShipmentServiceFacade.UpdateOrder` → (Yandex) `YandexShipmentService.UpdateOrderAsync` → `OtsYandexResultAdapter.MapToUpdateOrderRequest` → `IYandexApiClient.RemoveOrderItemsAsync` (`POST /api/b2b/platform/request/items/remove`).
- Cancel: хендлер `CancellingTransport` → `IShipmentServiceFacade.CancelOrder` → `CancelYandexOrder` → `YandexShipmentService.CancelOrderAsync` → `MapToCancelOrderRequest` → `IYandexApiClient.CancelRequestAsync`.

### 2.2 Подтверждённый контракт Яндекса (проверено живым вызовом на тест-стенде)
`GET /api/b2b/platform/request/info?request_id=<EXTERNAL_TK_ID>` возвращает (фрагмент, заказ `2000467752`):

```json
{
  "request_id": "e573faa4e2314e609a914804678f8177-udp",
  "request": {
    "items": [
      { "count": 1, "name": "Платье ... L/170", "article": "GDR026602F0009",
        "barcode": "6447b138bd4c2738abde94a30579a9ec", "place_barcode": "GJ2000467752", "refused_count": 0 },
      { "count": 1, "name": "Платье ... M/164", "article": "GDR026602F0008",
        "barcode": "b12dec05139e3a98fe13adf2249785e5", "place_barcode": "GJ2000467752", "refused_count": 0 }
    ],
    "places": [ { "barcode": "GJ2000467752" } ]
  },
  "state": { "status": "SORTING_CENTER_LOADED" }
}
```

Выводы (подтверждено):
- `item_barcode` для `items/remove` = **`request.items[].barcode`** (внутренний хэш Яндекса), НЕ `article` и НЕ EAN.
- Джойн нашей позиции с ответом — **по `article`** (мы передаём его в create; Яндекс его возвращает).
- `place_barcode` (= `GJ<order_id>`) — штрихкод коробки, один на все позиции, для джойна НЕ годится.
- В **опубликованной доке** Яндекса поля `items[].barcode` НЕТ (дока неполная) — ориентироваться на фактический ответ выше.

### 2.3 Где именно `parameters == null`
- Во входящем `ORDER_TO_EDIT` сообщении Starfish: `"parameters": null`.
- В restored из persisted-JSON (`OTSOrderDocuments`) `OTSOrderParams`: `parameters == null`.
- При этом данные есть в БД: `OrderTrackingParams` содержит `EXTERNAL_TK_ID` (пишется при create в `OrderRegisterTransport.CreateTracking`).

### 2.4 Текущее состояние кода (важно)
- Уже закоммичено в `yandex-fix`:
  - 681: `MapToUpdateOrderRequest` шлёт полный набор позиций с `RemainingCount = total − cancelled` (0 = удалить), `RequestId = parameters[EXTERNAL_TK_ID]`. **`ItemBarcode` сейчас = `article_id` — это и есть оставшийся баг (часть B).**
  - 683: трекинг статусов через `NextForwardStatus` — НЕ трогать.
- В рабочем дереве (НЕ закоммичено): временная гидрация `parameters` в `OrderRegisterTransport` (см. часть A3 — её надо перенести в фасад).

---

## 3. Известные заблуждения (guardrails — НЕ повторять)
- ❌ `item_barcode = article` (SKU `GDR...`) — Яндекс отвергает (`does not exist in the order`).
- ❌ `item_barcode = EAN` (`good_id`, `4660207...`) — Яндекс этих штрихкодов не знает (мы их не передаём).
- ❌ `place_barcode` — это коробка (`GJ<order_id>`), не товар.
- ✅ `item_barcode = request/info → items[].barcode`, джойн по `article`.
- В комментариях QA (Игорь) встречаются неточности: «роутинг в full update вместо items/remove» (это один и тот же путь) и «ожидаемый payload с EAN/remaining_count:1» — НЕ брать как истину; ориентир — факты из раздела 2.

---

## 4. Задача A — системный `parameters`-enrichment

**Цель:** `OTSOrderParams.parameters` всегда заполнен из БД-tracking перед Yandex-вызовами; поле never-null на уровне модели.

### A1. Модель never-null
- **Файл:** `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.ApplicationCore/OTSModels/Params/OTSRequestParams.cs`
- **Что:** свойство `public Dictionary<string, string> parameters { get; set; }` (≈ строка 40) переделать на бэкинг-поле с коалесингом в сеттере: при `null` присваивать пустой словарь. Гарантия: даже `"parameters": null` в JSON → не-null.
- **На что смотреть:** это `record`; убедиться, что System.Text.Json при десериализации вызывает сеттер (вызывает) и что never-null не ломает существующую сериализацию. Прогнать `dotnet build`; десериализацию `OTSOrderParams` с `"parameters": null` проверить вручную/в рантайме.

### A2. Прогнать Yandex через обогащение (как DPD)
- **Файл:** `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.Infrastructure/Services/ShipmentServiceFacade.cs`
- **A2.1 — `CancelYandexOrder`** (метод ≈ строки 268–277): сейчас делает ручной `Deserialize` + `restoredOtsOrderParams.parameters[EXTERNAL_TK_ID] = ...` → NRE. Переписать на использование уже существующего `GetOrderParams(OrderTracking)` (≈ строка 428) — он восстанавливает из persisted-JSON **и** гидрирует `parameters` из `OrderTracking.OrderTrackingParams`. После этого `EXTERNAL_TK_ID` уже будет в `parameters` (из tracking). Если по бизнесу нужно гарантированно использовать `cancelParams.RegisteredInTKOrderOrInvoiceId` — допустимо перезаписать им ключ ПОСЛЕ гидрации (но проверить, что значения совпадают с tracking).
- **A2.2 — `UpdateOrder`, ветка `ShipmentService.YANDEX`** (≈ строки 201–203): `ordTracking` уже загружен выше (≈ строка 183). Заполнить `orderParams.parameters` из `ordTracking` перед `_yandexShipmentService.UpdateOrderAsync(orderParams)`. Использовать общий хелпер (см. A4) либо существующий `EnrichOrderTrackingParams`/паттерн из `GetOrderParams(OrderTracking)`.
- **На что смотреть:** не затереть осознанно выставленные значения; enrichment делает доп. запрос(ы) в БД — это уже норма для DPD, приемлемо; адаптеры остаются чистыми мапперами (БД-доступ только в фасаде).

### A3. Убрать ставшую лишней заплатку
- **Файл:** `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.Infrastructure/Handlers/Handlers/ORDER_TO_CHECK/OrderRegisterTransport.cs`
- В блоке `if (action_type == ORDER_TO_EDIT && tracking != null)` есть незакоммиченная гидрация `otsOrderParams.parameters ??= tracking.OrderTrackingParams.ToDictionary(...)`. После A2.2 она дублируется фасадом — **откатить** (вернуть метод к исходному виду), чтобы логика жила в одном месте (фасад).

### A4. (Опционально) Консолидация конвертации
- Конвертация `List<OrderTrackingParam> → Dictionary<string,string>` (`p.StringValue ?? p.IntValue?.ToString() ?? p.DateTimeValue?.ToString()`) дублируется в ≥4 местах: `OrderMappers` (`/src/GloriaOTS.ApplicationCore/Mapping/Order/OrderMappers.cs`), `ShipmentServiceFacade.EnrichOrderTrackingParams` (≈ 383) и `GetOrderParams(OrderTracking)` (≈ 428), а также в нашей заплатке.
- Вынести в один метод, напр. `OrderTracking.ToParamsDictionary()` в `/src/GloriaOTS.ApplicationCore/Entities/OrderTracking.cs`, и заменить вызовы. Чистый рефактор без смены поведения; можно отдельным коммитом/PR.

---

## 5. Задача B — `item_barcode` через `request/info`

**Цель:** в `items/remove` слать `item_barcode = request/info.items[].barcode`, сматченный по `article`.

### B1. Эндпоинт в клиенте
- **Файлы:**
  - `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.Infrastructure/ApiClients/Yandex/IYandexApiClient.cs`
  - `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.Infrastructure/ApiClients/Yandex/YandexApiService.cs`
- Добавить Refit-метод (по образцу `GetRequestHistoryAsync`, который тоже `[Get]` с `request_id`):
  - `[Get("/api/b2b/platform/request/info")] Task<GetRequestInfoResponse> GetRequestInfoAsync([Query("request_id")] string requestId, CancellationToken ct = default);`
  - В `YandexApiService` — обёртка с логированием (как у остальных методов).

### B2. DTO ответа
- **Папка:** `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.ApplicationCore/DTO/Yandex/` (рядом с `RemoveOrderItem`, `RequestHistory`, `CreateOrder`, `EditStatus`, `CancelRequest` — создать подпапку `RequestInfo`).
- Минимальный набор полей (имена JSON — snake_case, маппинг как в других DTO Яндекса):
  - корень: `request` (объект), `state { status }` (опц., для будущего трекинга).
  - `request.items[]`: `article` (string), `barcode` (string), `refused_count` (int), `count` (int), `name` (string).
- Достаточно десериализовать только нужное; лишние поля игнорировать.

### B3. Поток вызова (в сервисе, не в адаптере)
- **Файл:** `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.Infrastructure/Services/ShipmentServices/Yandex/YandexShipmentService.cs`, метод `UpdateOrderAsync`.
- Перед маппингом `items/remove`:
  1. `requestId = orderParams.parameters[OrderTrackingParams.EXTERNAL_TK_ID]` (заполнен в части A; ключ-константа в `/src/GloriaOTS.ApplicationCore/Constants/OrderTrackingParams.cs`).
  2. `var info = await _yandexApiService.GetRequestInfoAsync(requestId)`.
  3. `var articleToBarcode = info.Request.Items.ToDictionary(i => i.Article, i => i.Barcode)`.
  4. Передать `articleToBarcode` в маппинг.
- Причина расположения: вызов API доступен в сервисе (`_yandexApiService`), а `OtsYandexResultAdapter` обязан остаться чистым маппером без сетевых/БД-зависимостей.

### B4. Маппинг
- **Файл:** `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.Infrastructure/Services/ShipmentServices/Yandex/OtsYandexResultAdapter.cs`, метод `MapToUpdateOrderRequest` (≈ строки 102–125).
- Изменить сигнатуру: добавить параметр `IReadOnlyDictionary<string,string> articleToBarcode`.
- Внутри: `ItemBarcode = articleToBarcode[good.article_id]` (хэш Яндекса) вместо текущего `group.Key`.
- Группировку оставить по `article_id` (как сейчас), `RemainingCount = total − cancelled` (0 = удалить) — **не менять** (это корректно по 681).
- Кейс «`article` отсутствует в `articleToBarcode`»: не падать NRE/KeyNotFound — залогировать предупреждение и принять решение (пропустить позицию либо вернуть управляемую ошибку без перевода заказа в `CHECKED_INVALID` до попытки). Согласовать поведение (см. раздел 9).

### B5. Обработка ошибок
- `request/info` вернул ошибку/пусто, либо нужного `article` нет в ответе → НЕ уводить заказ в `CHECKED_INVALID` преждевременно; логировать; рассмотреть ретрай (в потоке уже есть ретраи на сетевые вызовы Яндекса — свериться с `YandexApiClientExtensions`).

---

## 6. Порядок выполнения
1. **A1 + A2** (+ A3) — `parameters` всегда заполнен, NRE 681/693 закрыты. Промежуточно проверяемо: отмена и update больше не падают с NRE (но `items/remove` ещё вернёт 400 по `item_barcode` — это норм до части B).
2. **B1 → B2 → B3 → B4 → B5** — `item_barcode` из `request/info`.
3. **A4** — консолидация (опц., отдельным коммитом).

---

## 7. Проверка на тест-стенде

- **Индекс логов OTS (stage):** `gloria_ots_test-*` (через Buddy data-target `gloria_ots_test`, либо Kibana).
- **Токен/URL Яндекс тест-стенда** (в конфиге): `$WORKSPACE/platform/gloriaots/gloriaots/src/Workers/GloriaOTS.OrderTracking/appsettings.json` → секция `YandexApi`:
  - `BaseUrl = https://b2b.taxi.tst.yandex.net`
  - `ApiKey = <Bearer-токен тест-стенда>` (он же в `GloriaOTS.Web/appsettings.json`).
- **Ручная проверка `request/info`** (read-only GET):
  - `GET {BaseUrl}/api/b2b/platform/request/info?request_id=<EXTERNAL_TK_ID>` с заголовками `Authorization: Bearer <ApiKey>`, `Accept-Language: ru`.
- **Сценарии E2E:** заказ Яндекс ПВЗ (`transport_id=9`), 2 SKU, partial pick (одна позиция → `CANCELLED`). Проверить: `items/remove` → `202 Accepted` + `editing_task_id`; затем `GET request/edit/status` → `success`; заказ НЕ уходит в `CHECKED_INVALID`. Отдельно — отмену заказа на `CANCELLING_TRANSPORT` (нет NRE, заказ → `CANCELLED`).

---

## 8. Критерии приёмки
- [ ] Partial pick: OTS вызывает `items/remove` с `item_barcode = <хэш из request/info>`, `request_id = …-udp`, корректными `remaining_count` (0 для удаляемой, остаток для уменьшения) → Яндекс `202` + `editing_task_id`, далее `edit/status` → `success`.
- [ ] Нет `NullReferenceException` в `MapToUpdateOrderRequest` и в `CancelYandexOrder`.
- [ ] Отмена заказа в Яндекс на `CANCELLING_TRANSPORT` проходит, заказ → `CANCELLED`.
- [ ] Заказ не уходит в `CHECKED_INVALID` по этим сценариям.
- [ ] `dotnet build` чистый.
- [ ] Логика трекинга статусов (683) не затронута; другие ТК не затронуты.

---

## 9. Конвенции и ограничения
- **Workspace-правила** (`$WORKSPACE/CLAUDE.md`): git-операции только внутри клона `platform/gloriaots/gloriaots`; домен-скилл — `gloriaots-stack-anatomy`.
- **Комментарии в коде:** не добавлять поясняющие/нарративные комментарии (по требованию владельца). Только если есть нетривиальное намерение/ограничение — кратко.
- **Чистота слоёв:** БД/HTTP — в фасаде/сервисе; `OtsYandexResultAdapter` — чистый маппер.
- **Сборка:** `dotnet build` из `$WORKSPACE/platform/gloriaots/gloriaots` (см. `GloriaOTS.sln`). Локальный запуск — по `CLAUDE.md` раздел Gloria OTS.
- **Минимальные диффы**, без переформатирования чужого кода.

---

## 10. Git
- Ветка `yandex-fix` (уже есть, от `staging`). Все правки — в неё.
- **Не коммитить и не пушить** без явной команды пользователя (он коммитит сам). После готовности — показать сводный `git diff`.
- Целевой MR: `yandex-fix → staging` (модель веток: feature → staging → master → release).

---

## 11. Справочные данные (тест-стенд, для воспроизведения)

| Заказ | EXTERNAL_TK_ID (request_id) | Позиции (article → EAN good_id) | Yandex item barcode (из request/info) | Trace OTS |
|---|---|---|---|---|
| 2000467752 | `e573faa4e2314e609a914804678f8177-udp` | `GDR026602F0009`→`4660207511981` (L); `GDR026602F0008`→`4660207511974` (M) | `GDR026602F0009`→`6447b138bd4c2738abde94a30579a9ec`; `GDR026602F0008`→`b12dec05139e3a98fe13adf2249785e5` | — |
| 2000467723 | `feec196007f84f65a3ebb186b46686c7-udp` | те же SKU | (получить из request/info) | `936729df31f24f6e468cc4142b7cd2d3` |
| 2000467714 (cancel/693) | `bafba46c5b0045a6ab4bc8dfc78bbbfc-udp` | — | — | `59bc271d26b79357447d29c2449819be` |
| 2000467709 (исходный 681) | `0049233955504e70a9b5ee34846083e1-udp` | те же SKU | — | `e2d83da0f5c1e64f774a4862487405cb` |

Контракты Confluence: INT236.65.3 (items/remove) `pageId=149774961`; быстрая инструкция Яндекс-OTS `pageId=165408329`.

---

## Приложение. Ключевые файлы (абсолютные пути)
- Модель: `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.ApplicationCore/OTSModels/Params/OTSRequestParams.cs`
- Фасад: `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.Infrastructure/Services/ShipmentServiceFacade.cs`
- Адаптер: `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.Infrastructure/Services/ShipmentServices/Yandex/OtsYandexResultAdapter.cs`
- Сервис: `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.Infrastructure/Services/ShipmentServices/Yandex/YandexShipmentService.cs`
- Клиент: `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.Infrastructure/ApiClients/Yandex/IYandexApiClient.cs` и `YandexApiService.cs`
- Хендлер: `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.Infrastructure/Handlers/Handlers/ORDER_TO_CHECK/OrderRegisterTransport.cs`
- Сущность tracking: `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.ApplicationCore/Entities/OrderTracking.cs`
- Константы: `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.ApplicationCore/Constants/OrderTrackingParams.cs`, `OrderStatus.cs`
- DTO Яндекса: `$WORKSPACE/platform/gloriaots/gloriaots/src/GloriaOTS.ApplicationCore/DTO/Yandex/`
- Конфиг (токен): `$WORKSPACE/platform/gloriaots/gloriaots/src/Workers/GloriaOTS.OrderTracking/appsettings.json`
