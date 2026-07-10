# Gap matrix: Yandex Express SFS

Дата актуализации: 2026-07-10

Confidence: `confirmed` — подтверждено локальным кодом/Jira; `team-input` — заявление команды; `open` — нужен межкомандный контракт.

| ID | Область | As-is | Target | Gap / действие | Confidence | Владелец |
|---|---|---|---|---|---|---|
| G-01 | Product identity | `yandexNextDayDelivery` — существующий складской Яндекс. | Отдельный Яндекс Экспресс из магазина. | Запретить переиспользование NDD; получить carrier id Starfish24. | confirmed/open | Starfish24 + Integration |
| G-02 | Starfish24 capability | Локальный OMS-клон показывает старую carrier/BPMN-модель. | В новой OMS-версии заявлена готовая интеграция, настройка 1–2 недели. | Получить version/config scope и payload contract; локальный AS-IS не считать target. | team-input | Starfish24 |
| G-03 | OMS availability | SFS и generic express механики существуют раздельно. | Express offer только для eligible SFS store. | Подтвердить pilot config, ranking, coexistence с warehouse/CDEK. | open | Starfish24 |
| G-04 | Store ranking | OMS postfilter умеет полноту и дистанцию. | Полнота ↓, дистанция ↑ именно для Express. | Настроить/доказать профиль на test stand. | confirmed/open | Starfish24 |
| G-05 | Store hours | Есть warehouse timezone/working hours, но нет подтвержденного end-to-end Express rule. | Offer только пока магазин открыт и успевает собрать/передать заказ. | Настроить source-store timezone, schedule, cutoff и fail-closed при неполных данных. | confirmed/open | Starfish24 |
| G-06 | Dynamic quote | Стандартный SFS CDEK использует фиксированную/пороговую цену. | Цена Яндекса из interval, без free threshold. | Подтвердить поле/TTL; не применять локальную подмену цены. | open | Starfish24 + BFF + Fronts |
| G-07 | Payment | Обычная доставка может допускать COD. | Только `prepaid`. | Вернуть restriction из backend и сбрасывать несовместимый выбор на клиентах. | confirmed | BFF + Site + Mobile |
| G-08 | Integration enum | Есть `YANDEX = yandexNextDayDelivery`. | Отдельный Express carrier enum. | Добавить после получения точной строки. | confirmed/open | Integration |
| G-09 | Integration V4 create | Selected interval generic переносится в OMS order. | Сохранить carrier/tariff/fulfillment/cost нового interval. | Contract/regression tests; special branch не требуется без доказательства. | confirmed | Integration |
| G-10 | CBR/ARM mapping | SFS mappings hardcoded для известных carriers; Яндекс Express отсутствует. | Существующий SFS retail flow принимает новый carrier/тип. | Решить code/name/barcode/good id; обновить rules и legacy mutators. | confirmed/open | Integration + Retail/1C |
| G-11 | BFF old checkout | Express = только `carrierId == gjexpress`. | Новый carrier попадает в `deliveryExpress`. | Расширить классификацию без влияния на NDD. | confirmed | customer-api-web |
| G-12 | BFF general data | `method=express` предусмотрен; форматирование покрыто не полностью. | Стабильный Express method contract. | Исправить response formatting, selection и tests. | confirmed | customer-api-web |
| G-13 | Site | Есть поле `deliveryExpress`, но нет `EXPRESS` в активном method/state/UI flow. | Отдельная карточка и полный selection/commit flow. | Реализовать frontend slice, цену, payment, analytics, stale offer. | confirmed | Site |
| G-14 | Mobile | Есть текст «Экспресс», но нет method/route/state flow. | Функционально равный Site checkout. | Реализовать полноценный mobile slice и version rollout. | confirmed | Mobile |
| G-15 | Retail readiness | По бизнес-вводной магазинный процесс не меняется; локальный main ранее выглядел CDEK-specific. | Новый carrier проходит текущий SFS flow. | Получить релизное подтверждение и UAT import/issue/status. | open | Retail/ARM/1C |
| G-16 | Commit drift | Offer может исчезнуть между preview и commit. | Server-side revalidation. | Определить ошибку/fallback UX без автоматической замены на CDEK. | confirmed design gap | Integration + BFF + Fronts |
| G-17 | OTS boundary | OTS участвует в других carrier flows. | OTS не участвует в SFS Express. | Подтвердить маршрут Starfish24; не создавать OTS scope без evidence. | high/open | Starfish24 + Integration |
| G-18 | Rollout | Нет пилотного профиля и совместного протокола. | СЗ+Сибирь, независимый switch и CDEK regression. | Feature/config rollout, dashboards, order/trace evidence. | open | All |

## Блокеры до финальной оценки

1. Payload contract и точный carrier/tariff id от Starfish24.
2. Подтвержденный механизм store hours/cutoff и ranking для Express.
3. Решение Retail/1C по учетному типу и delivery good/barcode.
4. Волна запуска Site/Mobile и поддерживаемые версии приложения.
5. Тестовые магазины, адреса и товары для СЗ/Сибири.

## Главные риски

- Подмена нового carrier на `yandexNextDayDelivery` смешает складской и SFS-продукты.
- «Настройка 1–2 недели» без payload contract не гарантирует совместимость e-commerce clients.
- Фильтрация только по времени города клиента может оставить закрытый магазин источником.
- Отображение цены через общую free-delivery механику занулит динамический тариф Яндекса.
- Добавление только BFF grouping не создаст рабочего Site/Mobile selection flow.
- Автоматический fallback на CDEK при stale offer может изменить согласованный способ/цену без клиента.
