# ТЗ: проброс атрибутов валидации марки `inst` / `version` (ТС ПИОТ, аварийный режим) — ОТС + Integration

> **Дата:** 2026-06-19 · **Тип:** ТЗ на доработку · **Эпик:** OPSOMN‑10783 (Разрешительный режим маркировки для Еком)
> **Системы в скоупе:** **ОТС (= `gloriaots`, `platform/gloriaots`)**, **Integration Service** (`platform/integration`). ⚠️ Исправлено 2026-07-01: ОТС — это gloriaots, не Starfish (см. §4).
> **Связанный research:** `docs/research/2026-06-19-rr-tspot-inst-ver-dorabotki.md`.

---

## 1. Контекст и предпосылки

С 01.03.2026 проверка марки в разрешительном режиме (РР) переводится на **ТС ПИОТ**. В **аварийном/офлайн‑режиме** (ТС ПИОТ недоступен онлайн) проверка идёт через **ЛМ ЧЗ `/api/Mark/OfflineCheck`**, и ответ дополнительно содержит два новых параметра:

| Параметр | Смысл |
|---|---|
| `inst` | идентификатор экземпляра ПО «Локальный модуль Честный ЗНАК» |
| `version` (в очереди — `Ver`) | версия базы «чёрного списка», на которой проверялся КИ |

Эти два параметра должны быть доставлены до закрывающего чека `full_payment` (тег **1265**) для **предоплаченных** еком‑заказов.

Текущее сообщение РР (`measuring: permission`), которое WebGJISMP (WEBJSMP) шлёт в `permission-queue`:

```json
{
  "measuring": "permission",
  "timestamp": "2023-01-21T02:05:55.000Z",
  "order_idd": "Z0003522004863104",
  "UIDD": "a0aaa00a-0000-4444-00a0-000a444a0aaa",
  "permission_timestamp": 1689255764761
}
```

После внедрения ТС ПИОТ в аварийном режиме добавляются `inst` и `Ver`:

```json
{
  "measuring": "permission",
  "timestamp": "2023-01-21T02:05:55.000Z",
  "order_idd": "Z0003522004863104",
  "UIDD": "a0aaa00a-0000-4444-00a0-000a444a0aaa",
  "permission_timestamp": 1689255764761,
  "inst": "4c182ce0-a325-42a9-ab9eb5e562cc8721",
  "Ver": "52cadcfe-a28f-4877-8b2f-da0481ddf1fa"
}
```

Итоговый формат тега **1265**: `UUID={uuid}&Time={timestamp}&Inst={inst}&Ver={version}` (было `UUID&Time`).

### 1.1 Варианты сообщения `permission-queue` (⚠️ часть на уточнении у аналитика)

Дополнительно вводится **необязательное** boolean‑поле **`is_emergency_mode`** (по умолчанию `false`; `true` — когда ТС ПИОТ по этой интеграции вернул код **`204`** и вышел в аварийный режим).

| # | Ситуация | Поля сообщения | Тег 1265 в чеке |
|---|---|---|---|
| **A** | онлайн‑проверка ОК | `order_idd`, `UIDD`, `permission_timestamp` (+ `is_emergency_mode=false`) | `UUID&Time` |
| **B** | офлайн ЛМ ЧЗ (есть результат) | + `inst`, `Ver` (+ `is_emergency_mode=false`) | `UUID&Time&Inst&Ver` |
| **C** | **204 — аварийный режим** | только `order_idd` + `is_emergency_mode=true` (атрибутов валидации нет) | **1260 не заполняется** |

Вариант C — еком‑аналог розничного сценария «ТС ПИОТ вернул 203 → аварийный режим, теги 1260 (1262‑1265) не заполняются» (Confluence `165388354`).

```json
// Вариант C (204, аварийный режим)
{
  "measuring": "permission",
  "timestamp": "2023-01-21T02:05:55.000Z",
  "order_idd": "Z0003522004863104",
  "is_emergency_mode": true
}
```

> **Открытые вопросы (см. §10):** соотношение B и C; значение `is_emergency_mode` в варианте B; нужно ли поле в OMS.

## 2. Цель

Обеспечить сквозной проброс `inst`/`version` для обоих типов отгрузки заказа (FF и SFS) от источника проверки до OMS, не ломая текущий поток (поля **необязательные**, обратная совместимость обязательна).

## 3. Скоуп

**В скоупе:**
- **ОТС (`gloriaots`):** приём 2 новых полей из `permission-queue`, хранение, проброс далее (FF).
- **Integration:** проброс 2 новых полей в OMS в обеих ветках (FF — демон `transferOtsOrderStatus`; SFS — `updateStatusByArmV2`).

**Вне скоупа:**
- **OMS** — приём/хранение/проброс `inst`/`version` уже доработан (CLD‑27103: поля `inst`/`version`/`rawValue` в DTO `DatamatrixCodeValidation`, сущности `Item`, конвертере, миграции БД). Кейс «нет атрибутов → чек `full_payment` без тега 1260» — **уже работает** (фикс OPSOMN‑11617, 05.03.2025), то есть вариант C (204) OMS отрабатывает без доработок. Команде OMS остаётся **верифицировать** формирование значения тега 1265 (`&Inst&Ver`) для варианта B.
  - ⚠️ **Развилка (на уточнении):** поля `is_emergency_mode` в контракте OMS **нет**. Если бизнесу нужно, чтобы OMS его явно хранил/различал/репортил — это **новая доработка OMS** (выйдет из «вне скоупа»). Если OMS достаточно реагировать на отсутствие атрибутов (текущее поведение) — OMS остаётся вне скоупа.
- **WebGJISMP / Сервис Марок** (DEVLBL001) — добавление `inst`/`Ver` в сообщение `permission-queue` (источник, отдельное ТЗ).
- **Касса / АРМ розницы** (OPSRTL) — получение `inst`/`version` из ЛМ ЧЗ и передача в контракт АРМ→OMS.
- **COD** (оплата при получении) — отдельный кейс, тег 1265 в скоуп не входит.

## 4. Глоссарий

- **ОТС = `gloriaots`** (.NET Order Transport System, `platform/gloriaots/gloriaots`, **в клонах**) — приёмник `permission-queue` (RabbitMQ `MarkPermissionRequestedEvent`), ведёт статусы заказа и марки. ⚠️ **Исправлено 2026-07-01:** прежняя формулировка «ОТС = Starfish, НЕ gloriaots» была неверна (ошибка из-за gitignore-ловушки при grep). Доработку `inst`/`version` делать **в gloriaots** — якоря: `OTSOrderResultV2.cs`, `Infrastructure/OrderStatusNotifiers/Services/ResultConversionService.cs`, `Constants/OrderTrackingParams.cs`, `OTSModels/Results/OrderIntegrationResult.cs`, Kafka `OrderStatusNotifiers/Starfish/Sender.cs`, `Events/MarkPermissionRequestedEvent.cs`.
- **FF** — отгрузка с регионального склада; проверка марки серверно в WebGJISMP.
- **SFS** — отгрузка из магазина; проверка марки на кассе/АРМ через ТС ПИОТ.
- **Тег 1265** — реквизит в составе отраслевого реквизита 1260 фискального чека.

---

## 5. ТЗ для ОТС (= `gloriaots`, .NET, в клонах)

### 5.1 Приём из `permission-queue`

Интеграция: **INT 97.65.5** (Confluence `130133580`), RabbitMQ vhost `remarkhost`, exchange `remark-exch`, queue `permission-queue`.

Расширить разбор JSON‑сообщения двумя **необязательными** полями:

| Поле в сообщении | Поле в ОТС | Обязательность |
|---|---|---|
| `order_idd` | `order_id` | да (как сейчас) |
| `UIDD` | `good_mark_validation_uuid` | да (как сейчас) |
| `permission_timestamp` | `good_mark_validation_timestamp` | да (как сейчас) |
| **`inst`** | **`good_mark_validation_instance`** | **нет (новое)** |
| **`Ver`** | **`good_mark_validation_version`** | **нет (новое)** |
| **`is_emergency_mode`** | **`is_emergency_mode`** (order‑level, boolean) | **нет (новое, default `false`)** |

Если `inst`/`Ver` отсутствуют (обычный онлайн‑режим) — поведение прежнее, поля пустые/null. Вариант **C (204)**: приходит только `order_idd` + `is_emergency_mode=true`, атрибутов валидации нет — разбор не должен падать на их отсутствии.

### 5.2 Хранение

Завести в модели заказа два новых атрибута — `good_mark_validation_instance`, `good_mark_validation_version`. Как и для `uuid`/`timestamp`, **продублировать значения в каждый товар заказа** (требование `130133580`: GJISMP передаёт общую по заказу информацию, ОТС сохраняет в разрезе каждого товара).

### 5.3 Передача далее (в Integration → OMS)

ОТС передаёт параметры валидации в статус‑сообщении заказа **не ранее статуса `DELIVERING`** (правило из OPSOMN‑11421). В per-item структуру статус‑сообщения добавить новые поля с теми же именами, что читает Integration:

- `good_mark_validation_instance`
- `good_mark_validation_version`

(рядом с существующими `good_mark_validation_uuid` / `good_mark_validation_timestamp`).

### 5.4 Требования к совместимости

- Новые поля **необязательные** на всех этапах.
- Отсутствие полей не должно приводить к ошибке разбора/обработки сообщения.
- Гейт `≥ DELIVERING` сохраняется без изменений.

---

## 6. ТЗ для Integration Service

Обе ветки сходятся в Integration и используют один контракт к OMS: `OmsClient::updateOrderItemStatusByOrderId()` → `POST /item/status/{orderId}/update`, тело уходит без трансформации (`->body($items)`). **Сам OmsClient менять не нужно** — новые ключи проходят автоматически.

⚠️ **Имена ключей в payload к OMS — строго как в OMS DTO `DatamatrixCodeValidation`:** `inst`, `version` (не `instance`).

### 6.1 FF‑ветка — демон `TransferService::transferOtsOrderStatus()`

Источник — статус‑сообщение от ОТС. Сейчас (стр. ~2151‑2199):

```2194:2199:platform/integration/integration/www/app/Service/Exchange/Services/V1/Common/TransferService.php
                    if (!empty($markValidationUuid)) {
                        $newItem['datamatrixCodeValidation']['uuid'] = $markValidationUuid;
                    }
                    if (!empty($markValidationTimestamp)) {
                        $newItem['datamatrixCodeValidation']['dateTime'] = $markValidationTimestamp;
                    }
```

**Доработать:** читать из `$item` поля `good_mark_validation_instance` / `good_mark_validation_version` и дописывать в `$newItem`:

```php
$markValidationInstance = $item['good_mark_validation_instance'] ?? null;
$markValidationVersion  = $item['good_mark_validation_version']  ?? null;
// ...
if (!empty($markValidationInstance)) {
    $newItem['datamatrixCodeValidation']['inst'] = $markValidationInstance;
}
if (!empty($markValidationVersion)) {
    $newItem['datamatrixCodeValidation']['version'] = $markValidationVersion;
}
```

### 6.2 SFS‑ветка — приём от АРМ

Эндпоинт: `POST /integration/v2/orders/status/1c` (`routes/api.php:64`), тело — XML, параметры на уровне `<order>`.

> ⚠️ **Исправлено 2026-09-22 по факту реализации OPSOMN002-395.** Имена входящих элементов
> ниже (`good_mark_validation_instance` / `good_mark_validation_version`) — **ошибка этого ТЗ**.
> Контракт [INT 24.132.1 v.2, стр. 130132966](https://confluence.gloria-jeans.ru/pages/viewpage.action?pageId=130132966)
> (версия 11 от 15.09.2026) объявляет на уровне `<order>` элементы **`<inst>`** и **`<version>`**
> без префикса — они пришли из задачи 1С `DEVRTL001-8188`, тогда как `good_mark_validation_uuid` /
> `_timestamp` пришли из `OPSOMN-10909` и префикс имеют. Постановка OPSOMN002-395 называет
> те же короткие имена. Реализовано и смержено по контракту: читать `order.inst` / `order.version`.
> Исходящие ключи в OMS (`datamatrixCodeValidation.inst` / `.version`) в §6.2.3 указаны верно.

**6.2.1 Контракт запроса** `UpdateOrderStatusRequest.php`. Сейчас:

```33:63:platform/integration/integration/www/app/Service/UserApi/Http/Requests/V2/Order/Arm/UpdateOrderStatusRequest.php
        $parsed['order']['good_mark_validation_uuid'] = $this->convertEmptyToNull($parsed['order']['good_mark_validation_uuid'] ?? '');
        $parsed['order']['good_mark_validation_timestamp'] = $this->convertEmptyToNull($parsed['order']['good_mark_validation_timestamp'] ?? '');
        ...
            'order.good_mark_validation_uuid' => ['nullable','string'],
            'order.good_mark_validation_timestamp' => ['nullable','string'],
```

**Доработать** `afterConvert()` и `rules()`:

```php
// afterConvert()
$parsed['order']['good_mark_validation_instance'] = $this->convertEmptyToNull($parsed['order']['good_mark_validation_instance'] ?? '');
$parsed['order']['good_mark_validation_version']  = $this->convertEmptyToNull($parsed['order']['good_mark_validation_version']  ?? '');

// rules()
'order.good_mark_validation_instance' => ['nullable', 'string'],
'order.good_mark_validation_version'  => ['nullable', 'string'],
```

**6.2.2 Сборка `markValidationData`** в `OrderService::updateStatusByArmV2()`. Сейчас:

```609:620:platform/integration/integration/www/app/Service/UserApi/Services/V2/Order/OrderService.php
        $markValidationData = [
            'uuid' => array_key_exists('good_mark_validation_uuid', $orderData) ? $orderData['good_mark_validation_uuid'] : null,
            'timestamp' => array_key_exists('good_mark_validation_timestamp', $orderData) ? $orderData['good_mark_validation_timestamp'] : null,
        ];
        $markValidationData['has_data'] = !(is_null($markValidationData['uuid']) && is_null($markValidationData['timestamp']));
```

**Доработать:**

```php
$markValidationData = [
    'uuid'      => $orderData['good_mark_validation_uuid']      ?? null,
    'timestamp' => $orderData['good_mark_validation_timestamp'] ?? null,
    'instance'  => $orderData['good_mark_validation_instance']  ?? null,
    'version'   => $orderData['good_mark_validation_version']   ?? null,
];
$markValidationData['has_data'] = !(
    is_null($markValidationData['uuid'])
    && is_null($markValidationData['timestamp'])
    && is_null($markValidationData['instance'])
    && is_null($markValidationData['version'])
);
```

**6.2.3 Проброс в payload OMS** в `collectArmOrderItemUpdateData()`. Сейчас:

```1131:1136:platform/integration/integration/www/app/Service/UserApi/Services/V2/Order/OrderService.php
            if (!is_null($markValidationData['uuid'])) {
                $itemForUpdate['datamatrixCodeValidation']['uuid'] = $markValidationData['uuid'];
            }
            if (!is_null($markValidationData['timestamp'])) {
                $itemForUpdate['datamatrixCodeValidation']['dateTime'] = $markValidationData['timestamp'];
            }
```

**Доработать (добавить):**

```php
if (!is_null($markValidationData['instance'])) {
    $itemForUpdate['datamatrixCodeValidation']['inst'] = $markValidationData['instance'];
}
if (!is_null($markValidationData['version'])) {
    $itemForUpdate['datamatrixCodeValidation']['version'] = $markValidationData['version'];
}
```

### 6.3 Версия контракта

Поля `nullable` → обратно совместимо. Достаточно расширить V2 (`/v2/orders/status/1c`); при необходимости оформить как «v3» — продолжение OPSOMN‑10929. V1 (`/integration/orders/status/1c`) марки не обрабатывает — не трогаем.

### 6.4 Тесты (Integration)

- Юнит/функциональные тесты на `updateStatusByArmV2`: кейс с `instance`+`version`, кейс без них (обратная совместимость), кейс частичного набора.
- Тест демона `transferOtsOrderStatus` с новыми per-item полями.
- Обновить XML/JSON фикстуры в `platform/integration/.../tests/mocks/...`.
- Проверить, что итоговый payload к OMS содержит `datamatrixCodeValidation.inst` / `.version` с правильными именами ключей.

---

## 7. Аварийный режим (поведение)

| Вариант | `is_emergency_mode` | `uuid`/`timestamp` | `inst`/`version` | Поведение Integration | Тег 1260/1265 |
|---|---|---|---|---|---|
| A — онлайн ОК | `false` | есть | нет | прокидываем `uuid`+`timestamp` | `UUID&Time` |
| B — офлайн ЛМ ЧЗ | `false` | есть | **есть** | прокидываем `uuid`+`timestamp`+`inst`+`version` | `UUID&Time&Inst&Ver` |
| C — 204 аварийный | **`true`** | нет | нет | `has_data=false`, `datamatrixCodeValidation` не добавляется; передаём флаг (если решено — см. §10) | 1260 **не заполняется** |

Integration корректно обрабатывает отсутствие полей (`convertEmptyToNull` / `?? null`). Для варианта C оформление чека без 1260 — **уже на стороне OMS** (фикс OPSOMN‑11617), доп. доработка OMS не требуется (кроме развилки по хранению флага — §10).

## 8. Критерии приёмки

1. **ОТС:** сообщение `permission-queue` с `inst`/`Ver` корректно разобрано, поля сохранены в заказ и **во все товары**; при отсутствии полей — поведение без изменений.
2. **ОТС:** в статус‑сообщении к Integration на статусе `≥ DELIVERING` присутствуют per-item `good_mark_validation_instance`/`version`.
3. **Integration (FF):** демон `transferOtsOrderStatus` прокидывает `datamatrixCodeValidation.inst`/`.version` в OMS.
4. **Integration (SFS):** запрос АРМ с `good_mark_validation_instance`/`version` приводит к `datamatrixCodeValidation.inst`/`.version` в payload к OMS по каждой позиции.
5. **Сквозной тест (оба пути):** для предоплаченного заказа в офлайн‑режиме ЛМ ЧЗ значение тега 1265 в чеке YooKassa = `UUID=…&Time=…&Inst=…&Ver=…`.
6. **Регресс:** заказы без ТС ПИОТ/аварийного режима оформляются как раньше (тег 1265 = `UUID&Time`).

## 9. Ссылки

- **Confluence:** `130133580` (INT 97.65.5 GJISMP→ОТС) · `165388354` (РР с ТС ПИОТ) · `130145593` (использование марок в заказах) · `130127785` (AR. РР в Еком)
- **Jira:** эпик `OPSOMN-10783` · `OPSOMN-11421` (OTS ≥DELIVERING) · `OPSOMN-10929` (контракт АРМ→OMS) · `OPSOMN-11617` (баг пустых полей) · `OPSRTL-4848` (SFS endpoint) · `OPSRTL-5747`/`6223` (ТС ПИОТ розница) · `CLD-27103` (OMS — готово)
- **Research:** `docs/research/2026-06-19-rr-tspot-inst-ver-dorabotki.md`
- **Карта процессов маркировки:** `docs/architecture/2026-06-03-marking-process-map.md`

## 10. Открытые вопросы (на уточнении у аналитика)

> Блокируют финализацию контракта `is_emergency_mode` и варианта C.

1. **Соотношение вариантов B и C.** Кейс B (`inst`/`Ver`, есть результат офлайн ЛМ ЧЗ) и кейс C (`204`, без атрибутов) — оба существуют на одной очереди? Или `is_emergency_mode` **заменяет** механизм `inst`/`Ver` (тогда B не нужен)?
2. **Значение `is_emergency_mode` в варианте B** — `false` или `true`?
3. **Нужен ли `is_emergency_mode` в OMS?** Поля нет в контракте OMS. Достаточно ли текущего поведения «нет атрибутов → чек без 1260» (OPSOMN‑11617), или OMS должен явно принимать/хранить/репортить флаг? От ответа зависит, **переоткрывается ли скоуп OMS**.
4. **Код ответа ТС ПИОТ.** В этой интеграции (GJISMP→ОТС) — именно HTTP `204`? (в рознице фигурирует `203`). Зафиксировать семантику.
5. **Уровень поля.** `is_emergency_mode` — order‑level (как permission «общий по заказу»)? Нужно ли дублировать в позиции, как `good_mark_validation_*`?
6. **Имя поля.** В очереди `is_emergency_mode`; имя в ОТС / в контракте к OMS (если потребуется) — согласовать.

> До ответов: §1.1, §5.1, §7 и развилка в §3 помечены как **проект**. После — обновить контракт и критерии приёмки (добавить кейс C: `is_emergency_mode=true` → чек оформляется без 1260, регресс не ломается).
