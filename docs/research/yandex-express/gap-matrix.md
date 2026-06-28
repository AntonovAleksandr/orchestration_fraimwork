# Gap matrix: SFS Yandex

Дата: 2026-06-28

Цель: зафиксировать разрывы между текущим SFS CDEK as-is и целевым SFS Yandex flow. Confidence указан по текущему локальному коду и исследовательским заметкам; перед разработкой часть пунктов нужно подтвердить у владельцев OMS/retail.

| ID | Область | As-is | Target | Gap | Confidence | Владелец |
|---|---|---|---|---|---|---|
| G-01 | Справочник delivery type | Есть `SFS_CDEK`, `SFS_PICKPOINT`, `SFS_RUSSIANPOST`, `SFS_GLORIAJEANS_EXPRESS`; есть `YANDEX = 10`. | Новый SFS Yandex delivery type. | Нет кода/названия `SFS_YANDEX`. | high | 1C/retail + Integration |
| G-02 | Integration mapping | Нет правила `DELIVERY + SFS + YANDEX`. | `delivery + sfs + yandexNextDayDelivery -> SFS_YANDEX`. | Добавить enum/name/rules/export mapping. | confirmed | Integration |
| G-03 | CBR export | SFS CDEK/GJ Express ветки есть. | CBR получает новый SFS Yandex type. | Нет ветки Yandex в CBR mutator/rules. | high | Integration |
| G-04 | Старый V1 order resolver | SFS resolver знает CDEK и `gjexpress`. | Resolver возвращает `SFS_YANDEX` для Yandex SFS. | Нет Yandex SFS ветки. | confirmed | Integration |
| G-05 | customer-api-web express grouping | Express определяется только как `carrierId == gjexpress`. | Yandex SFS должен отображаться в нужном UI-блоке. | Нужно решить: express-блок или обычная courier delivery. | confirmed | customer-api-web/site/mobile |
| G-06 | OMS release process | Gateway "SFS и CDEK?" проверяет `fulfillmentType == 'sfs' && carrierId == 'cdek'`. | Yandex SFS должен идти по корректному SFS courier route. | Условие может не покрыть Yandex. | confirmed | OMS |
| G-07 | OMS dispatch process | Есть SFS route и special cases для `gjexpress`. | Yandex SFS route запускает правильный registry/call flow. | Нужно добавить/подтвердить `yandexNextDayDelivery` route. | high | OMS |
| G-08 | carrierRegistryProcess | CDEK-specific условия и courier-call flow. | Yandex-specific registry/call/order flow. | Не ясно, расширять процесс или заводить отдельный. | confirmed | OMS/Camunda |
| G-09 | OMS Delivery courier call | Для CDEK есть `CdekCourierRequestServiceImpl` и status service. | Yandex SFS умеет вызвать/зарегистрировать курьера/заказ. | Не найден `CourierRequestService`/`CallCourierStatusService` для `yandexNextDayDelivery`. | high | OMS Delivery |
| G-10 | OMS Delivery Yandex flow | Есть calculation/order registration/cancellation/tracking под Yandex Next Day. | Поддержан именно SFS pickup from store. | Не подтверждено, что текущий Yandex Next Day flow подходит магазинам. | medium | OMS Delivery/logistics |
| G-11 | Carrier enable/disable | CDEK SFS уже работает. | CDEK/Yandex включаются независимо по магазинам/городам/тарифам. | Нужно найти и подтвердить точку управления availability. | medium | OMS Delivery/logistics |
| G-12 | ARM import | Найденный main-код создает SFS документ с `Tk.CDEK`. | ARM принимает SFS Yandex. | Нужна retail-ветка/релиз с Yandex SFS. | high | Retail/ARM |
| G-13 | ARM выдача курьеру | UI/действие выдачи найдено для CDEK. | UI/статусы работают для Yandex. | Нужна проверка retail доработок. | high | Retail/ARM |
| G-14 | 1C dictionaries | Есть действующие CDEK/SFS справочники. | Добавлены Yandex SFS code/name/barcode. | Нужна справочная заявка/подтверждение. | medium | 1C/retail |
| G-15 | Status lifecycle | ARM отправляет статусы через Integration, OMS обновляет order/items. | ARM + Yandex statuses не конфликтуют, финализация корректна. | Нужно описать ownership статусов ARM vs Yandex tracking. | medium | OMS + Retail + Integration |
| G-16 | OTS boundary | OTS не участвует в SFS CDEK. | OTS не участвует в SFS Yandex. | Нужно не добавлять OTS задачи по ошибке. | high | All |

## Блокеры до оценки разработки

1. Код и название нового `SFS_YANDEX`.
2. Подтверждение retail-готовности: ветка, релиз, справочник, import, выдача курьеру.
3. Решение OMS Delivery: Yandex SFS это courier-call, order registration или отдельная claim flow.
4. Решение UI: `yandexNextDayDelivery` попадает в express grouping или остается обычной courier delivery.
5. Механизм включения/отключения carrier по магазинам.

## Риски

- Если переиспользовать `YANDEX = 10`, можно смешать складской/next-day сценарий с SFS.
- Если считать `yandexNextDayDelivery` express всегда, можно сломать не-SFS Yandex отображение.
- Если добавить только Integration mapping, заказ может создаться, но зависнуть в Camunda/retail на выдаче.
- Если retail не готов, магазин не сможет принять или выдать заказ курьеру.
- Если OMS Delivery не поддерживает магазинный pickup, вызов Яндекса будет технически успешен не в том сценарии или неуспешен на данных магазина.

