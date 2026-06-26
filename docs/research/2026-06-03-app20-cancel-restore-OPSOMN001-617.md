# OPSOMN001-617 — APP20 не восстанавливается после отмены заказа (root-cause)

**Дата:** 2026-06-03 · **Статус тикета:** Новая, Критический · **Тэгнут:** zakomirnyy (FYI), svyatoslav.meyer
**Тип:** read-only расследование (Integration ↔ OMS/Camunda ↔ Discount Server)

> **РЕВИЗИЯ 2026-06-03 (после челленджа):** тестеры подтверждали, что отмена откатывала промо →
> рабочим механизмом был **Path 2** (фикс OPSOMN-12554). Значит это **регресс Path 2**, а не «Path 1
> всегда сломан». Гипотеза «payload status-update тонкий» **опровергнута**: OMS шлёт полный заказ
> (`OrderExportWithFeedbackHandler.getFullOrder`), Path 2 получает couponId+promocodeName+customer.emails.
> Код Path 2 и BPMN с момента фикса не менялись → поломка рантайм/по данным. Ведущие версии:
> (1) у части заказов нет `promocodeName` (2005146914) → тихий skip; (2) multi-email
> (2007168946) → откат на customer.emails[0] не совпадает с email трансляции → СС не снимает отметку;
> (3) ghost-usage = смежный create-side баг. **Точную ветку покажет только трейс ИС** (INFO vs WARNING vs
> ответ СС); `logs-is-awg-prod` сейчас пуст — нужно репро + логи. Раздел «Главное: добавить couponTranslate
> в Path 1» ниже — НЕ подтверждённый фикс, а одна из гипотез; не действовать без трейса.

## TL;DR

APP20 («скидка за установку приложения», DS22) — одноразовый промокод. Его «израсходованность»
на Сервере Скидок (СС, `WWWDK_API`) определяется записью **трансляции** (`CouponTranslate`),
ключ — **`email` + `promocode`**. Освободить промокод повторно можно **только** обратной
трансляцией `CouponTranslate` с атрибутом `Rollback=1`. Возврат уникального купона
(`returnCoupon` = `BonusSpend Rollback=1`) этого **не делает** — он откатывает списание купона на
заказе, но не снимает отметку «APP20 использован».

**Корневая причина — асимметрия двух путей отмены:**

1. **Путь, который реально дёргает Camunda при отмене** (`paymentFinalizationProcess` →
   `gjOrderLoyaltyReturn` → `POST /integration/internal/loyalty/return`, BP-INT-16) вызывает
   **только `returnCoupon`** и **никогда** `couponTranslate(Rollback=1)`. → трансляция APP20 не
   откатывается → промокод остаётся «использованным».
2. **Откат трансляции** (`couponTranslate(rollback=true)`) добавлен фиксом OPSOMN-12554/12764 **только**
   в (а) путь создания заказа и (б) хендлер экспорта `status-update` (Path 2). В endpoint
   `loyalty/return` (Path 1) его **не добавили никогда** (подтверждено git-историей метода).
3. Path 2 (экспорт `status-update`, BPMN `dwhStatusUpdate`, шлётся на каждый апдейт статуса,
   включая `ORDER_CANCELED`) **молча пропускает** откат (Severity::WARNING), если в payload нет
   `promocodeName` / `couponId` / `customer.emails[0]`. Коммит `157aa783` понизил жёсткий
   `ERROR + return` до тихого `WARNING + no-op` — провалы перестали быть заметными.

Итого: на отмене заказа гарантированно срабатывает `returnCoupon` (Path 1), но обратная
трансляция APP20 либо не вызывается вообще (Path 1), либо тихо пропускается (Path 2 без данных).

## Подтверждено на prod (oms-awg-order-prod)

Все 4 заказа из тикета — `status_id = CANCELLED`, `couponId` в `order_custom_attribute` есть:

| client_order_id | order_id | status | couponId | promocodeName | contact_email | customer_emails |
|---|---|---|---|---|---|---|
| 2005146914 | gloriajeans-2005146914-9986 | CANCELLED | 5000049453282 | **отсутствует ❌** | genrihovna.inessa@yandex.ru | есть |
| 2005250104 | gloriajeans-2005250104-959 | CANCELLED | 5000108670223 | APP20 | genrihovna.inessa@yandex.ru | есть |
| 2007168946 | gloriajeans-2007168946-3488 | CANCELLED | 5000102534071 | APP20 | slavna555@icloud.com | **2 шт** ⚠ |
| 2009533041 | gloriajeans-2009533041-2098 | CANCELLED | 5000109525638 | APP20 | alina26_987@bk.ru | есть |

- `order_marketing` для этих заказов **пусто** → APP20 это coupon-translate-промо, не бонусы;
  бонусная ветка Path 1 (`returnLoyaltyPoints`) тут вообще не при делах.
- **2005146914**: нет `promocodeName` → даже Path 2 уйдёт в тихий WARNING-skip (гарантированно).
- **2007168946** (customer 3646341): в `customer_emails` **два** адреса
  (`slavna555@icloud.com`, `olya21cherkasova@yandex.ru`) → `customer.emails[0]` может выбрать не тот
  email, которым делалась трансляция → Rollback на СС не найдёт запись.

### Ghost usage («заказов не было»)

- `79176114654`, `79292966359` — **0 заказов** в OMS, но APP20 «использован».
- `79016855712` — 1 заказ от 2026-06-02 в статусе PICKING (свежий).

→ Трансляция APP20 произошла на этапе корзины/чекаута (ключ — email), но **заказ в OMS не создан**
(failed checkout / abandon после трансляции). Откатывать нечего — нет orderId. Это смежный баг
**OPSOMN-14839 → OPSOMN001-439** (rollback при ошибке create) + несработавший in-basket rollback
(OPSOMN-12764).

## Код (ветка production)

### Path 1 — то, что дёргает Camunda на отмене (НЕ откатывает трансляцию)
- BPMN `platform/starfish24/awg/bpmn-process/process/gloriajeans/paymentFinalizationProcess.bpmn`:
  gateway «Статус заказа», ветка **Other** (любой не-COMPLETED, т.е. CANCELLED/LOST) →
  serviceTask «Возврат списанных бонусов» `${gjOrderLoyaltyReturn}` (есть в обеих ветках: оплачен/нет).
- `platform/starfish24/core/Camunda/.../activity/GjOrderLoyaltyReturn.java` → `POST {gj.integrationUrl}{gj.orderLoyalityReturnEndpoint}` = `/integration/internal/loyalty/return`, тело `{orderId}`.
- Конфиг: `platform/starfish24/awg/cloud-configs/camunda-gj-prod.yaml:130`.
- IS: `OrderService::returnLoyalty()` (`app/Service/UserApi/Services/V1/Order/OrderService.php:4786`):
  `getOrderFull` → `couponId` → **только** `returnCoupon(clientOrderId, couponId, baseStore)` (стр. 4903).
  `couponTranslate` тут **отсутствует** (git -L по методу: всегда был только `returnCoupon`).

### Path 2 — единственное место с откатом трансляции на отмене (тихо пропускает без данных)
- BPMN `dwhStatusUpdate.bpmn` (стартует по `STATUS_UPDATED`, корреляции включают `ORDER_CANCELED`),
  external topic `orderExportWithFeedbackActivity`, `destination=status-update`.
- IS: `OrderService::export()` → `case ExportDestinationEnum::STATUS_UPDATE`
  (`OrderService.php:1147-1188`, метка `// OPSOMN-12554`):
  - читает `couponId/baseStoreCode/promocodeName` из `$data['customAttributes']`, email из `$data['customer']['emails'][0]`;
  - `if (!empty($couponId))` → если `couponId && email && promoCode` → `returnCoupon()` **+** `couponTranslate(..., rollback=true)`;
  - иначе (email/promoCode пусты) → `trace(... Severity::WARNING)` и **ничего не делает**.
- Коммит `157aa783` (OPSOMN-12554): раньше было `ERROR + return` при нехватке любого из полей
  (включая `customerId`), стало `WARNING + no-op` → провал перестал быть видимым.
- Контракт отката: `XmlHelper::couponTranslate()` (`app/Service/DiscountClient/Parsers/XmlHelper.php:310`)
  — `Rollback=(int)$rollback`, дети `<promocode>`, `<email>`, `<cartcode>`. Ключ отмены — email+promocode.

## Почему Path 2 не спасает (ведущая гипотеза, требует подтверждения логами IS)

`dwhStatusUpdate` = «Выгрузка факта апдейта статуса в DWH». Высокая вероятность, что payload экспорта
`status-update` — это «тонкая» проекция статуса/дат и **не несёт** `customAttributes` и/или
`customer.emails`. Тогда:
- `couponId` из payload → null → весь блок (`if !empty($couponId)`) пропускается, `couponTranslate(rollback)` не вызывается;
- либо `couponId` есть, но `email`/`promocodeName` нет → тихий WARNING-skip.

В обоих случаях трансляция не откатывается. А `returnCoupon` всё равно отрабатывает в Path 1
(он делает `getOrderFull`, поэтому couponId у него всегда есть) — отсюда иллюзия, что «откат вызван».
Это ровно исторический корень **OPSOMN-11011**: «rollback в ИС вызывается, СС не отдаёт промо повторно».

## Что проверить для финального подтверждения

1. **IS prod логи** (`logs-is-awg-prod` сейчас пуст — нет шиппинга/ретеншена; нужен доступ/восстановление)
   по traceId/orderId: какой trace на отмене —
   `'Заказ содержит данные купона для отката...'` (INFO, Path 2 сработал) vs
   `'...некорректные данные заказа для обработки отката промокода'` (WARNING, тихий skip) vs
   только Path 1 (`'возвращаю купон'` без `couponTranslate`).
2. **Payload экспорта `status-update`** из OMS (мутаторы `OrderExportEcomMutator`/`AbstractOrderExport1CMutator`
   и проекция `orderExportWithFeedbackActivity`): несёт ли `customAttributes` + `customer.emails`.
3. **Сырой ответ СС** на `CouponTranslate Rollback=1` (ok vs «трансляция не найдена») — для multi-email
   кейса (2007168946) проверить, каким email делалась исходная трансляция.

## Рекомендация по фиксу (на согласование)

- **Главное:** добавить `couponTranslate(Rollback=1)` в `OrderService::returnLoyalty()` (Path 1) —
  чтобы реальный путь отмены (Camunda → loyalty/return) откатывал трансляцию, а не только `returnCoupon`.
  Это закрывает все CANCELLED/LOST-кейсы из таблицы.
- Брать email/promocode из надёжного источника (атрибуты заказа / тот email, которым делалась
  трансляция), не из `customer.emails[0]`; обработать multi-email и phone-only.
- Вернуть видимость провалов: при наличии `couponId`, но отсутствии данных для отката — НЕ молча
  WARNING, а ERROR + алерт/ретрай (откатить дух коммита `157aa783`).
- Идемпотентный авто-ретрай отката (СС идемпотентен по DOC) вместо ручного восстановления КЦ/IT.
- **Ghost usage:** закрыть OPSOMN-14839/OPSOMN001-439 — rollback трансляции при ошибке создания
  заказа / по таймауту незавершённой корзины (трансляция была, заказа нет).

## Связанные

OPSOMN-12310/12764 (in-basket + on-create rollback), OPSOMN-12551/12554 (Path 2 на cancel/lost),
OPSOMN-12799 (ручной откат 20.05.2025), OPSOMN-11011 (исторический корень), OPSOMN-14839/OPSOMN001-439
(rollback при ошибке create). Confluence: pageId=130154031, 60692929, 146506730, 147030206.
