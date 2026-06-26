# Разрешительный режим + ТС ПИОТ: доработки под `inst`/`Ver` (2 пути)

> **Дата:** 2026-06-19 · **Тип:** research / план доработок · **Скоуп:** проброс новых атрибутов валидации марки (`inst`, `Ver`) из аварийного/офлайн‑режима ТС ПИОТ через еком‑контур до чека `full_payment`.
> **Контекст:** с 01.03.2026 проверка марки в разрешительном режиме (РР) переводится на **ТС ПИОТ**. В аварийном (офлайн) режиме проверка идёт через **ЛМ ЧЗ `/api/Mark/OfflineCheck`**, и ответ дополнительно содержит `inst` (экземпляр ПО ЛМ ЧЗ) и `version` (версия базы «чёрного списка»). Эти два поля должны дойти до тега **1265** закрывающего чека.

## TL;DR

- Новые поля в сообщении РР (аварийный режим): `inst` (instance) и `Ver`/`version`.
- Тег **1265**: было `UUID={reqId}&Time={reqTimestamp}` → стало `UUID=…&Time=…&Inst={inst}&Ver={version}`.
- Путей **два, по источнику отгрузки**: **FF** (с регионального склада) и **SFS** (из магазина). Они отличаются **где проверяется марка** и **каким транспортом** атрибуты доходят до OMS.
- **OMS дорабатывать не нужно** (приём/хранение/проброс `inst`/`Ver` уже сделаны, см. блок «OMS») — кроме одной проверки по чеку.

## Две независимые оси (не путать)

| Ось | Значения | На что влияет |
|---|---|---|
| **Оплата** | предоплата (онлайн) / оплата при получении (COD) | Закрывающий чек `full_payment` с тегом 1265 нужен для **предоплаченных** заказов — это и есть скоуп РР‑в‑екоме. |
| **Отгрузка** | **FF** (склад) / **SFS** (магазин) | **Где** проверяется марка и **каким транспортом** атрибуты валидации доходят до OMS. |

Оси **ортогональны**: предоплаченный заказ бывает и FF, и SFS. «Онлайн‑оплата» — **общий знаменатель обоих путей**, а не признак SFS. COD — отдельный кейс (реальный криптохвост из WebGJISMP, риск `CHECKED_INVALID`), вне данного скоупа тега 1265.

## Терминология (важно — снять коллизию)

- **«ОТС»** в маркировочных доках = **Starfish** (`ots.gloria-jeans.ru`, элемент `OTS-Starfish` на схемах). Это система, принимающая `permission-queue` и ведущая статусы заказа (`ORDER_PICKUP`/`PICKING`/`DELIVERING`).
- **.NET `gloriaots`** (Order Transport System) в этом контуре **НЕ участвует** — проверено по коду: ноль упоминаний `permission`/`Mark`/`Validation`/`1265` во всём репозитории.
- **OMS** — система формирования чека `full_payment` и выгрузки в 1С.

---

## Путь 1 — FF (отгрузка с регионального склада)

Предоплаченный заказ, отгрузка со склада. Проверку марки делает **WebGJISMP** серверно (`GetCheckOrder`), результат идёт по очереди.

```mermaid
flowchart LR
    CHZ["ГИС МТ / ЛМ ЧЗ\n(офлайн → inst, version)"]
    WEB["WebGJISMP (WEBJSMP)\nСервис Марок"]
    OTS["ОТС (Starfish)\nприёмник permission-queue"]
    OMS["OMS\n(чек full_payment)"]
    YOO["YooKassa → ATOL → ОФД"]
    CHZ --> WEB
    WEB -->|RabbitMQ permission-queue\n+inst,+Ver| OTS
    OTS -->|datamatrixCodeValidation\n(≥ DELIVERING)| OMS
    OMS -->|тег 1265| YOO
```

**Цепочка доработок (без OMS):**

| # | Система | Что доработать | Где / ссылка |
|---|---|---|---|
| 1 | **WebGJISMP** (Сервис Марок, DEVLBL001) | Добавить `inst` и `Ver` в JSON сообщения `permission-queue` (только в аварийном/офлайн режиме). Обновить контракт интеграции. | INT 97.65.5 — Confluence `130133580` |
| 2 | **ОТС** (Starfish, приёмник очереди) | Распарсить 2 новых необязательных поля; завести `good_mark_validation_instance` / `good_mark_validation_version`; **продублировать в каждый товар** заказа; на `≥ DELIVERING` добавить их per-item в статус‑сообщение к Integration. | Расширение OPSOMN‑11421. ⚠️ репозиторий ОТС **не в клонах**. |
| 3 | **Integration** (FF‑хоп) | Демон `TransferService::transferOtsOrderStatus()` читает per-item `good_mark_validation_*` из сообщения ОТС и шлёт в OMS — дописать `datamatrixCodeValidation.inst/version`. **У нас в клонах.** | `…/Exchange/Services/V1/Common/TransferService.php` (~стр. 2194) |

---

## Путь 2 — SFS (отгрузка из магазина)

Предоплаченный заказ, отгрузка из магазина. Марку сканируют на **кассе/АРМ магазина через ТС ПИОТ**. `permission-queue` от GJISMP **не участвует**. Атрибуты валидации идут из АРМ в OMS, чек `full_payment` пробивает OMS (предоплата — как и в FF).

```mermaid
flowchart LR
    TSPOT["Касса/АРМ магазина\n+ ТС ПИОТ / ЛМ ЧЗ\n(офлайн → inst, version)"]
    INT["Integration (АРМ→OMS)\nplatform/integration (Lumen)"]
    OMS["OMS\n(чек full_payment)"]
    YOO["YooKassa → ATOL → ОФД"]
    TSPOT -->|XML order status\n+good_mark_validation_*| INT
    INT -->|datamatrixCodeValidation\n(≥ DELIVERING)| OMS
    OMS -->|тег 1265| YOO
```

**Цепочка доработок (без OMS):**

| # | Система | Что доработать | Где / ссылка |
|---|---|---|---|
| 1 | **Касса / АРМ розницы** (ТС ПИОТ) | Получать `inst`/`version` из офлайн‑ответа ЛМ ЧЗ и класть в контракт АРМ→OMS. | Розничный контур — Confluence `165388354` (OPSRTL‑5747/6223) |
| 2a | **Integration** — приём от АРМ | Добавить поля `good_mark_validation_instance` / `good_mark_validation_version` в правила и `afterConvert`. | `…/Http/Requests/V2/Order/Arm/UpdateOrderStatusRequest.php` (стр. 33‑34, 56‑63) |
| 2b | **Integration** — сбор `markValidationData` | Расширить массив (`instance`/`version`) и `has_data`. | `…/Services/V2/Order/OrderService.php::updateStatusByArmV2()` (стр. 609‑620) |
| 2c | **Integration** — проброс в OMS | Дописать `datamatrixCodeValidation.instance/version` в payload. | `…/Services/V2/Order/OrderService.php` (стр. 1131‑1135) |
| 2d | **Integration** — демон ОТС↔ОМС статус‑синк (проверить) | Чтение `good_mark_validation_*` по позиции — добавить новые поля, если SFS‑марки идут и через него. | `…/Service/Exchange/Services/V1/Common/TransferService.php` (~стр. 2151) |

> Это по сути «v3 контракта АРМ→OMS» — продолжение **OPSOMN‑10929**. Эндпоинт розницы — `int-oms.gloria-jeans.ru` (OPSRTL‑4848).

---

## Обе ветки сходятся в OMS

| Часть OMS | Статус |
|---|---|
| Контракт приёма `datamatrixCodeValidation` (ОТС/Integration → OMS) | ✅ готово |
| Хранение `inst`/`version`/`rawValue` на позиции + миграция БД | ✅ готово |
| Проброс наружу (`ItemConverter`) | ✅ готово |
| **Чек YooKassa: значение тега 1265 `&Inst&Ver` + аварийный режим (пустой 1260)** | ⚠️ **верифицировать** |

**Готово коммитом `CLD-27103` «add new fields to datamatrixCodeValidation»** (24.09.2025, `platform/starfish24/core/Order`): DTO `DatamatrixCodeValidation`, сущность `Item`, `ItemConverter`, `ItemServiceImpl`, `OrderCalculationServiceImpl` + миграция БД. Модель — **общая для FF и SFS**.

**Единственная оговорка по OMS:** `inst`/`Ver` сейчас читаются только в `ItemConverter` (уходят в DTO наружу); отдельной правки сборки тега 1265 в истории `Order`/`pay-service` не видно (код обфусцирован). Нужно подтвердить в коде фискализации, что:
1. значение тега 1265 формируется как `UUID&Time&Inst&Ver`;
2. в аварийном режиме чек оформляется без тегов 1260 (иначе риск повтора **OPSOMN‑11617** «full_payment с незаполненными полями валидации»).

---

## Открытые вопросы

1. **Репозиторий ОТС‑Starfish** — не в локальных клонах; подтвердить парсинг `permission-queue` и формирование статус‑сообщения к Integration (путь 1, звено 2). Хоп Integration (`transferOtsOrderStatus`) — в клонах.
2. **Имена полей** в очереди (`inst`/`Ver`) vs розница (`inst`/`version`) — выровнять в контракте INT 97.65.5.
3. **Код фискализации OMS** (тег 1265) — обфусцирован/вне читаемых клонов; нужна верификация по чеку (оговорка выше).
4. **Демон `TransferService`** (2d) — уточнить, проходят ли SFS‑марки через него, или только через `updateStatusByArmV2`.

## Ссылки

- **Confluence:** `130133580` (INT 97.65.5 GJISMP→ОТС) · `165388354` (РР с ТС ПИОТ) · `130145593` (использование марок в заказах) · `130127785` (AR. РР в Еком) · карта процессов: `docs/architecture/2026-06-03-marking-process-map.md`
- **Jira:** эпик `OPSOMN-10783` · `OPSOMN-11421` (OTS ≥DELIVERING) · `OPSOMN-10929` (контракт АРМ→OMS) · `OPSOMN-11617` (баг пустых полей) · `OPSOMN-11663` (ручное добавление) · `OPSRTL-4848` (SFS endpoint) · `OPSRTL-5747`/`6223` (ТС ПИОТ розница) · `CLD-27103` (OMS — готово)
