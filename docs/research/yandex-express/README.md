# Yandex Express SFS research pack

Дата: 2026-06-28

Цель пакета: дать аналитикам и разработчикам компактный вход в задачу интеграции Яндекс-доставки для SFS, где текущая рабочая гипотеза такая:

- OMS carrier остается существующим `yandexNextDayDelivery`;
- для SFS нужен новый справочный delivery type, условно `SFS_YANDEX`;
- OTS в SFS-поток не добавляем;
- включение CDEK/Yandex для SFS должно жить в OMS Delivery/logistics rules, а не в Integration.

## Как читать

1. `sfs-cdek-as-is.md` - текущий рабочий SFS CDEK lifecycle: кто создает заказ, кто вызывает курьера, кто обновляет статусы.
2. `sfs-yandex-target-process.md` - целевой SFS Yandex process и ключевые гипотезы.
3. `code-space-mapping.md` - разные кодовые пространства и где может сломаться маппинг.
4. `gap-matrix.md` - список разрывов между as-is и target process.
5. `implementation-slices.md` - как раскладывать задачу по командам и подсистемам.
6. `acceptance-and-test-plan.md` - приемочные сценарии и тестовые проверки.

## Текущие выводы

Подтверждено кодом:

- Integration знает carrier `yandexNextDayDelivery`, но не имеет SFS-маппинга `DELIVERY + SFS + YANDEX`.
- Integration уже имеет SFS-типы для CDEK/PickPoint/RussianPost/GJ Express.
- OMS BPMN SFS-поток идет в `1c-cbr`, а не в OTS.
- OMS carrier registry process сейчас содержит CDEK-specific условия.
- OMS Delivery содержит часть Yandex Next Day поддержки, но не найден courier-call сервис, аналогичный CDEK.
- customer-api-web считает express только carrier `gjexpress`.
- main-код ARM/Gloria Retail, который был просмотрен, выглядит SFS CDEK-only.

Открыто:

- точный код и название нового `SFS_YANDEX` в 1C/retail справочнике;
- фактическая retail-ветка/релиз с Yandex SFS;
- нужен ли отдельный Yandex courier-call или достаточно order registration/confirmation;
- где именно операционно включается carrier по магазинам;
- должен ли `yandexNextDayDelivery` попадать в express UI только для SFS или всегда.

## Граница ответственности

Ecom/Integration:

- корректно принять selected interval;
- передать `delivery + sfs + yandexNextDayDelivery` в OMS;
- замапить комбинацию в новый справочный тип;
- не выбирать carrier вместо OMS Delivery/logistics.

OMS/Camunda/Delivery:

- вернуть доступные SFS Yandex интервалы;
- вести SFS-заказ по правильному BPMN route;
- зарегистрировать/вызвать Yandex courier/order;
- обработать статусы/трекинг.

Retail/ARM/1C:

- принять заказ с новым типом/ТК;
- показать магазинный процесс выдачи курьеру;
- отправить статусы обратно через Integration;
- подтвердить справочные коды.

## Следующий практический шаг

Перед разработкой собрать короткий sync с владельцами OMS и retail:

- OMS: подтвердить Yandex flow в Delivery service и механизм включения carrier.
- Retail/1C: подтвердить `SFS_YANDEX` code/name/barcode и ветку готовности ARM.
- Ecom: решить UI-классификацию express для `yandexNextDayDelivery`.

