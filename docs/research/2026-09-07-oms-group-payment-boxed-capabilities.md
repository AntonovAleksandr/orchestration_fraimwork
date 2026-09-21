# Общая оплата split-заказов: признаки в коробке OMS

Дата проверки: 2026-09-07. Исследование без изменения прикладного кода и production-данных.

## Вывод

В исходниках коробки Starfish есть parent/child связи, клонирование заказа с переносом платежных записей, batch-обновление split-заказов с переданными платежами и корректировка стоимости родителя по изменению стоимости ребенка. Это реальные механизмы, которые можно рассматривать для повторного использования.

Проверенные пути не подтверждают готовый сценарий единого платежа YooKassa с автоматическим распределением суммы, согласованием статусов дочерних заказов и независимыми корректными возвратами. Копирование платежной записи не является распределением денег. Наличие singleton order_id в pay-service само по себе не исключает оплату родителя с отдельной оркестрацией детей.

## Проверенные версии

| Компонент | Проверенный код | Актуальность |
|---|---|---|
| Order | `480aa16413802f167c2cc0ff6a8dddba2514740f` | master от 2026-09-03; подтвержден GitLab и получен git fetch |
| camunda-worker | `71e359b7303cf927ea14297cbdc6adf40ce49041` | master от 2026-09-03; подтвержден GitLab и получен git fetch |
| pay-service | `9851339144312557c703ef12de82bc59129374dc` | master от 2026-06-11; локальный ref совпал с актуальным GitLab |
| GJ BPMN | `711510c` | локальный main от 2026-07-02; deployed BPMN не выгружались |

Рабочие ветки не переключались. Первые попытки sync завершились fetch failed; targeted fetch Order и worker с сетевым разрешением прошли успешно. Рабочий checkout pay-service остается на старой default-ветке CLD-1840 (2022), поэтому выводы о YooKassa сделаны по origin/master, а не по ней.

## Положительные признаки

1. `OrderCloneServiceImpl.java:54-90` создает дочерний заказ, передает `.payment(fullOrderById.getPayments())` и создает связи parent/child.
2. `OrderServiceImpl` сохраняет переданные платежи ребенка через `updatePaymentByOrderId`; `PaymentServiceImpl.java:654-686` назначает записи orderId ребенка, сохраняет переданные sumPaid и acquierTransactionId. Идентификатор эквайринга может быть перенесен без новой оплаты, но сумма автоматически не делится.
3. `POST /split/orders/update` принимает `List<SplitOrderDto>`. `SplitOrderServiceImpl.java:45-77` в транзакции обновляет существующие заказы, включая переданные payments. Доли должен рассчитать вызывающий сценарий; метод не создает provider payment и не создает дочерние заказы.
4. `OrderServiceImpl.java:1045-1059` корректирует totalCost родителя на дельту стоимости ребенка. Это агрегация стоимости, а не распределение платежа.

Исходники:

- [Клонирование и перенос платежей](https://gitlab.gloria.aaanet.ru/starfish-oms/cloud/core/Order/-/blob/480aa16413802f167c2cc0ff6a8dddba2514740f/src/main/java/com/starfish24/services/orderService/OrderCloneServiceImpl.java#L54)
- [Обновление split-заказов](https://gitlab.gloria.aaanet.ru/starfish-oms/cloud/core/Order/-/blob/480aa16413802f167c2cc0ff6a8dddba2514740f/src/main/java/com/starfish24/services/split/SplitOrderServiceImpl.java#L45)
- [Сохранение платёжных полей](https://gitlab.gloria.aaanet.ru/starfish-oms/cloud/core/Order/-/blob/480aa16413802f167c2cc0ff6a8dddba2514740f/src/main/java/com/starfish24/services/PaymentServiceImpl.java#L654)
- [Изменение стоимости родителя](https://gitlab.gloria.aaanet.ru/starfish-oms/cloud/core/Order/-/blob/480aa16413802f167c2cc0ff6a8dddba2514740f/src/main/java/com/starfish24/services/orderService/OrderServiceImpl.java#L1045)

## Где не подтвержден готовый общий процесс

- `OnlinePaymentController` создает ссылку по одному clientOrderId; `YookassaServiceImpl.java:68-95` загружает один заказ и сохраняет OnlinePayment с его идентификаторами.
- `YookassaCallbackServiceImpl.java:40-62` определяет один orderId из metadata либо платежной записи и обновляет платеж этого заказа.
- `Order/PaymentServiceImpl.java:414-475` обновляет записи заданного orderId и публикует PAYMENT_UPDATED для него. Обхода дочерних заказов в этом пути нет. Отдельную внешнюю оркестрацию по событию нельзя исключить без проверки deployed процессов/настроек.
- `AcquierChargeRequestHandler.java:53-144` рассчитывает списание по платежу, позициям и доставке одного заказа процесса. Координатора сумм нескольких заказов в этом обработчике нет.
- `DependentPayment` относится к истории зачета предоплаты одного clientOrderId, а не к распределению общего платежа между заказами.

Исходники:

- [Callback YooKassa](https://gitlab.gloria.aaanet.ru/starfish-oms/cloud/core/pay-service/-/blob/9851339144312557c703ef12de82bc59129374dc/src/main/java/com/starfish24/service/yooKassa/YookassaCallbackServiceImpl.java#L40)
- [Обновление платежа Order](https://gitlab.gloria.aaanet.ru/starfish-oms/cloud/core/Order/-/blob/480aa16413802f167c2cc0ff6a8dddba2514740f/src/main/java/com/starfish24/services/PaymentServiceImpl.java#L414)
- [Worker списания](https://gitlab.gloria.aaanet.ru/starfish-oms/cloud/core/camunda-worker/-/blob/71e359b7303cf927ea14297cbdc6adf40ce49041/src/main/java/com/starfish24/handlers/sber/AcquierChargeRequestHandler.java#L53)

## Production: что проверено

Через Buddy read-only Kubernetes в namespace prod:

- pay-service: `gj-prod-46`, 2/2 ready;
- order: `gj-prod-82`, 6/6 ready;
- camunda-worker: `gj-prod-33`, 1/1 ready.

Тег Jenkins-сборки не сопоставлен с SHA исходников. Актуальный master нельзя автоматически считать содержимым этих образов.

Схема `oms-awg-pay-prod.public`: online_payment содержит одиночные order_id/client_order_id; cart связан с online_payment, отдельного распределения по дочерним заказам в просмотренных таблицах нет. Схема `oms-awg-order-prod.public` содержит link, payment, item_payment_state и историю предоплат.

Ограниченная выборка последних 20 000 записей public.payment по id: не найден непустой acquier_transaction_id одного acquier_id, связанный с более чем одним различным order_id внутри выборки. Персональные данные и идентификаторы платежей не выгружались. Это не проверка всей истории, не проверка только успешных оплат и не доказательство невозможности такого сценария.

## Исторические требования

- [CR37, старая версия](https://confluence.gloria-jeans.ru/pages/viewpage.action?pageId=73794036), v22, 2024-04-16: прямо описан уже реализованный простой parent/child подход и проблемы с оплатами, частичными отменами и частичными оплатами. Единая оплата родителя описана как требование.
- [R-20 Сплиты заказов](https://confluence.gloria-jeans.ru/pages/viewpage.action?pageId=108057394), v22, 2024-04-27: п.20 — единый платеж родителя; п.25 — списания по отдельным отправлениям. Раздел демонстрации Starfish 22.02.2023 относится к логистическому расчету; он не доказывает готовый платежный цикл.
- [Текущее архитектурное решение OPSOMN-234](https://confluence.gloria-jeans.ru/pages/viewpage.action?pageId=165412816), v21: группа отдельных заказов, требования к совместимости оплаты, без подтвержденного описания общего платежного координатора.

## Практическое решение

Начинать оценку с существующего родительского заказа и split API, а не предполагать обязательное создание всей модели с нуля. До признания решения готовой коробочной возможностью нужен воспроизводимый сценарий на нашей версии: один платеж за два заказа, отмена одного, возврат одной позиции второго, повторный callback и проверка сумм, статусов и чеков. Владение общей суммой и распределение операций должны быть явными.
