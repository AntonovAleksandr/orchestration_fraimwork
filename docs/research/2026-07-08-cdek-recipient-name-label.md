# CDEK Recipient Name (ФИО) on Shipping Labels — OTS Investigation

**Date:** 2026-07-08  
**Symptom:** некоторые CDEK-этикетки имеют имя получателя в секции «КОМУ», на других — только телефон и адрес, без имени.

---

## Summary

ФИО получателя проходит по цепочке **OMS → Integration → OTS → CDEK API**. В OTS поле `recipient.name` формируется прямой конкатенацией `clnt_surname + " " + clnt_name`. Если любое из этих полей равно `null`, в CDEK уходит строка вида `" Иван"`, `"Иванов "` или `" "` (одиночный пробел). CDEK API принимает запрос без ошибки, но рендерит пустой раздел «КОМУ» на этикетке. Отчество (`clnt_patronym`) в CDEK-запрос **не передаётся вообще**.

---

## 1. Где происходит регистрация заказа в CDEK

**Точка входа:**  
`GloriaOTS.Web` → `OrderController` (POST `/` или POST `/v2`) → `IOrderRequestsProcessor.HandleRequest`  
→ хэндлер `OrderRegisterTransport` (`ORDER_REGISTER_TRANSPORT`) → `IShipmentServiceFacade.CreateOrder` / `UpdateOrder`  
→ `CdekShipmentService.CreateOrderAsync` / `UpdateOrderAsync`

**Файлы:**
```
src/GloriaOTS.Infrastructure/Handlers/Handlers/ORDER_TO_CHECK/OrderRegisterTransport.cs
src/GloriaOTS.Infrastructure/Services/ShipmentServices/CDEK/CDEKShipmentService.cs
src/GloriaOTS.Infrastructure/Services/ShipmentServices/CDEK/CdekShipmentServiceAdapter.cs
```

---

## 2. Поле, которое отображается в секции «КОМУ»

CDEK API-параметр: **`recipient.name`** в теле `RegisterOrderParams` / `UpdateOrderParams`.

Структура:
```csharp
// InternalParamsTypes.cs
public class RecipientContact : Contact   // для RegisterOrder
{
    public string name { get; set; }  // ← идёт на этикетку в "КОМУ"
    public string passport_series { get; set; }
    public string passport_number { get; set; }
    ...
}

public class Recipient   // для UpdateOrder
{
    public string name { get; set; }  // ← то же самое
    ...
}
```

---

## 3. Как формируется `recipient.name` в OTS

**`CdekShipmentServiceAdapter.ToCdekRegisterOrderParams`** (строки 85–90):
```csharp
recipient = new RecipientContact
{
    name = orderInfo?.order.clnt_surname + " " + orderInfo?.order.clnt_name,
    phones = [new Phone { number = orderInfo?.order.clnt_phone }],
    email = orderInfo?.order.clnt_email,
},
```

**`CdekShipmentServiceAdapter.ToCdekOrderUpdateParams`** (строки 190–195):
```csharp
recipient = new Recipient()
{
    name = orderInfo.order.clnt_surname + " " + orderInfo.order.clnt_name,
    phones = new[] { new Phone() { number = orderInfo.order.clnt_phone } },
    email = orderInfo.order.clnt_email,
},
```

> **Важно:** метод `Order.GetClientFullName()` (возвращает `"{clnt_name} {clnt_surname} {clnt_patronym}"`) существует, но **не используется** в CDEK-интеграции.

---

## 4. Источник данных: откуда OTS берёт clnt_name / clnt_surname

### Путь через Integration Service (Hybris / основной путь)

**`OrderExportOtsMutator.FIELD_MAP`** (`platform/integration/.../OrderExportOtsMutator.php`):
```php
'order.clnt_surname' => 'shipping.recipientLastName',
'order.clnt_name'    => 'shipping.recipientFirstName',
'order.clnt_patronym' => 'shipping.recipientMiddleName',
```

`DEFAULT_VALUES` для этих трёх полей **не заданы**. `GLOBAL_DEFAULT_VALUE = null`.  
→ Если OMS не передал `recipientLastName` или `recipientFirstName`, в OTS придёт `null`.

**Валидация в Integration** (`ExportOrderRequest.php`, строки 138–140):
```php
'shipping.recipientFirstName' => 'required|string',  // maps to: OTS
'shipping.recipientMiddleName' => 'string|nullable',  // maps to: OTS
'shipping.recipientLastName'  => 'required|string',   // maps to: OTS
```
Формально поля `required`, но эта валидация применяется только к входящим HTTP-запросам. Внутренние cron-пути и message-queue консьюмеры могут её обходить.

### Путь через OMS Starfish напрямую (POST /v2)

Данные приходят прямо из OMS `StarFishOrderParams`. Источник — JPA-сущность `Shipping`:
```java
// Shipping.java — нет @Column(nullable = false), нет @NotNull
private String recipientFirstName;
private String recipientMiddleName;
private String recipientLastName;
```
Поля nullable в БД OMS. Если при создании заказа имя не было заполнено (например, гость-заказ без полного профиля), OMS передаёт `null`.

---

## 5. Условия, при которых имя будет пустым на этикетке

### H1 — null от OMS (основная гипотеза, HIGH CONFIDENCE)

| Сценарий | Результат |
|----------|-----------|
| `clnt_surname = null`, `clnt_name = "Иван"` | `name = " Иван"` (ведущий пробел) |
| `clnt_surname = "Иванов"`, `clnt_name = null` | `name = "Иванов "` (хвостовой пробел) |
| `clnt_surname = null`, `clnt_name = null` | `name = " "` (только пробел) |

В C# `null + " " + null = " "`. CDEK API принимает запрос без ошибки валидации, но рендерит пустое поле «КОМУ» на этикетке. Этикетки с только телефоном/адресом — именно этот случай.

### H2 — Пустая строка (`""`) вместо null (MEDIUM CONFIDENCE)

Если OMS или Integration передают пустую строку:
- `"" + " " + ""` = `" "` — тот же результат.
- Проверить в логах: `order.clnt_surname == ""` или `order.clnt_name == ""`.

### H3 — Гостевые заказы / анонимные пользователи (MEDIUM CONFIDENCE)

Некоторые заказы могут создаваться без обязательного фулл-профиля покупателя (guest checkout). В этом случае `recipientFirstName` / `recipientLastName` в OMS могут быть `null` изначально.

### H4 — Заказы из определённого источника (OrderSource) (LOW CONFIDENCE)

OTS поддерживает `OrderSource` (Hybris, Starfish, RSG). Разные источники могут иметь разные правила заполнения shipping. Стоит проверить корреляцию: заказы с пустым именем — это только RSG или только Starfish?

### H5 — Отсутствие patronym (SECONDARY BUG, CONFIRMED)

`clnt_patronym` **не передаётся** в CDEK. Метод `GetClientFullName()` возвращает `{name} {surname} {patronym}`, но в адаптере используется только `surname + " " + name`. Это отдельный баг — отчество никогда не попадает на CDEK-этикетку.

---

## 6. Схема потока данных

```
OMS (Shipping.recipientLastName / recipientFirstName)
        │
        │  [OMS → Integration HTTP export  ИЛИ  OMS → OTS /v2 напрямую]
        ▼
Integration: OrderExportOtsMutator.FIELD_MAP
  shipping.recipientLastName  → order.clnt_surname
  shipping.recipientFirstName → order.clnt_name
  shipping.recipientMiddleName → order.clnt_patronym
        │
        │  [HTTP POST / или /v2 в OTS]
        ▼
OTS: OTSOrderParams.order.clnt_surname / clnt_name / clnt_patronym
        │
        │  OrderRegisterTransport → CdekShipmentService.CreateOrderAsync
        ▼
CdekShipmentServiceAdapter.ToCdekRegisterOrderParams:
  recipient.name = clnt_surname + " " + clnt_name   ← БАГ: нет null-guard, нет patronym
        │
        │  CDEK REST API POST /v2/orders
        ▼
CDEK: если recipient.name == " " → поле "КОМУ" пустое на этикетке
```

---

## 7. Рекомендуемые фиксы

### Fix 1 — OTS: null-safe конкатенация (владелец: OTS team)

```csharp
// CdekShipmentServiceAdapter.cs
private static string BuildRecipientName(Order order)
{
    var parts = new[] { order.clnt_surname, order.clnt_name, order.clnt_patronym }
        .Where(p => !string.IsNullOrWhiteSpace(p));
    return string.Join(" ", parts);
}
```

Использовать вместо `clnt_surname + " " + clnt_name` в обоих методах (`ToCdekRegisterOrderParams` и `ToCdekOrderUpdateParams`).

### Fix 2 — OTS: добавить отчество (владелец: OTS team)

Тот же хелпер `BuildRecipientName` включает `clnt_patronym` — патроним появится на этикетке.

### Fix 3 — Integration: дефолт при null (владелец: Integration team)

В `OrderExportOtsMutator.DEFAULT_VALUES` добавить:
```php
'order.clnt_surname' => self::UNSET_ATTRIBUTE_KEY,
'order.clnt_name'    => self::UNSET_ATTRIBUTE_KEY,
```
Либо добавить явный `mutateOrderClntSurnameAttribute` / `mutateOrderClntNameAttribute`, который возвращает пустую строку вместо `null`.

### Fix 4 — OMS: не допускать null recipient name в заказе (владелец: OMS team)

Добавить `@NotNull` или `@Column(nullable = false)` на `recipientFirstName` / `recipientLastName` в `Shipping.java`, или проверять на уровне бизнес-логики создания заказа.

---

## 8. Файлы и строки

| Файл | Строки | Значимость |
|------|--------|------------|
| `src/.../ShipmentServices/CDEK/CdekShipmentServiceAdapter.cs` | 85–90, 190–195 | 🔴 Основной баг |
| `src/.../ApiClients/CDEKApiClient/InternalParamsTypes.cs` | 17–23, 121–128 | Модели recipient |
| `src/.../ApiClients/CDEKApiClient/ApiRequestParams.cs` | 51–80 | RegisterOrderParams |
| `src/.../OTSModels/Params/InternalTypes/Order.cs` | 11–23 | clnt_name/surname/patronym + GetClientFullName |
| `platform/integration/.../OrderExportOtsMutator.php` | 46–48 | FIELD_MAP (маппинг ФИО) |
| `platform/integration/.../ExportOrderRequest.php` | 138–140 | Валидация (required) |
| `platform/starfish24/core/Order/.../Shipping.java` | 44–46 | JPA entity (nullable) |

---

## Следующие шаги

1. **Проверить конкретные заказы** с пустым именем в логах OTS: искать `clnt_surname=null` или `clnt_name=null` в `LogInformation("Input request: {@request}", orderParams)` (Web/OrderController.cs строка 176).
2. **Проверить источник** (`orderParams.source`): коррелируют ли пустые имена с Hybris / Starfish / RSG.
3. **Применить Fix 1** в OTS — минимальный риск, не меняет контракт, устраняет симптом.
4. **Проверить OMS** — есть ли реальные строки в БД с `recipient_first_name IS NULL` в таблице `shipping`.
