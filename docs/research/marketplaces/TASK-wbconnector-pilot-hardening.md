# ТЗ: доработка wbconnector до pilot-ready (по итогам ревью 2026-08-18)

Документ для новой сессии. Контекст: внешнее ревью wbconnector
(`platform-new/wbconnector`, HEAD `3c796e2`) выставило NO-GO для пилота.
Каждое утверждение ревью **проверено по коду и подтверждено** — список ниже
уже верифицирован, перепроверять не нужно, только чинить.

Состояние на 2026-08-19: контур на стейдже работает end-to-end (остатки,
заказ → резерв → поставка → WMS → КИЗ в ВБ, Kafka-статусы). Это не отменяет
дефекты ниже: они детерминированные и не зависят от нагрузки.

## Блокеры пилота (чинить первыми)

### Б1. pack-scan всегда отвечает no_supply

- `internal/adapters/pgstore/pack.go:158-173` — `packContext` джойнит
  `supplies s ON s.wb_supply_id = o.wb_supply_id`; `orders.wb_supply_id`
  **никогда не пишется** (принадлежность к поставке теперь —
  `orders.supply_id`, ставится в `takeOrdersIntoSupplyTx`, supply_form.go).
- Фикс: джойн по `s.supply_id = o.supply_id`. Проверить остальных читателей
  `orders.wb_supply_id` (grep) — все перевести на `supply_id`.
- `pack_test.go` заполнял старое поле руками — после фикса тест должен
  идти через реальное формирование поставки, без ручной подстановки.
- Приёмка: цепочка ingest → формирование → add_orders → `pack-scan` на
  свежем заказе отвечает печатью, а не `no_supply`.

### Б2. Outbox теряет команды при рестарте/деплое

- `internal/adapters/pgstore/store.go:417-430` (`ClaimDue`) ставит до 50 команд
  `state='sent'` до выполнения; `internal/worker/outbox.go:36-63` исполняет
  последовательно; при SIGTERM оставшиеся остаются `sent` навсегда.
  Комментарий в outbox.go:52-54 ссылается на «stuck-command sweep» — его не
  существует (комментарий врёт).
- Фикс: `claimed_at`, `claim_owner`, TTL; цикл возврата просроченных
  `sent` → `pending`. ВАЖНО: не все внешние вызовы безопасны к повтору —
  `create_supply` (POST /supplies неидемпотентен) при потерянном ответе
  требует сверки (см. Р5) прежде чем повторять. Остальные команды
  идемпотентны по dedup_key/поведению OTS/WB.
- Приёмка: процесс убивается посреди батча → после рестарта команды
  доезжают; повторный create_supply не плодит поставку-дубль.

### Б3. Голодание статусного опроса после 1000 заказов

- `internal/adapters/pgstore/store.go` `TrackedOrderIDs`:
  `ORDER BY updated_at ASC LIMIT 1000`; `ApplyStatuses` обновляет
  `updated_at` только при СМЕНЕ статуса → неподвижные заказы вечно в голове
  очереди, остальные не опрашиваются никогда. Индекс
  `orders_status_idx (supplier_status, gj_status)` запросу не помогает.
- Фикс: колонка `status_checked_at` (миграция), обновлять при КАЖДОМ опросе
  (в т.ч. при неизменном статусе), выбирать `ORDER BY status_checked_at`,
  индекс под фактический предикат. Индекс не должен исключать
  `supplier_status='complete'` — такие заказы опрашиваются до `sold`.
- Приёмка: 1001+ долгоживущих заказа → опрос обходит всех по кругу;
  `sold`/отмена доезжают и к хвосту очереди.

### Б4. Недобор при резерве застревает молча

- `internal/worker/commands/ots.go` reserve → `classifyOTS(ErrShortage)` →
  permanent → park. Заказ при этом остаётся `imported`/`new`,
  `supply_id IS NULL` → формирование заберёт его в поставку БЕЗ резерва.
  Отмены задания в WB и перевода в shortage нет (тот путь есть только для
  асинхронного `SUSPENDED` — pgstore/otsstatus.go).
- Фикс: при `ErrShortage` — `gj_status=shortage`, outbox `cancel_order` в WB,
  заказ исключается из пула формирования (учесть в `SupplyCandidateOrders`:
  `supplier_status='new' AND supply_id IS NULL AND gj_status NOT IN
  ('shortage', 'canceled')` — либо отдельное условие; shortage может прийти и
  позже по `SUSPENDED`, проверить обе ветки).
- Приёмка: резерв с недобором → задание в WB отменено, заказ не формируется
  в поставку, запись в реестре отклонений.

## Lifecycle-риски (вторая очередь)

### Р1. Двойной deliver при Ship
`internal/shipping/service.go:371-386`: outbox-намерение `deliver` +
синхронный `DeliverSupply` — outbox-цикл может забрать команду параллельно
(поставка в `draining` → хендлер реально звонит в WB). Развести: либо
outbox, либо синхронно, не оба.

### Р2. Ship без батчей по 100
`service.go:~276` — `ReadMetaBatch` без разбиения (лимит WB 100,
`wbapi/orders.go:246`); `service.go:~341` — `AddOrdersToSupply(leftovers)`
одним вызовом (лимит 100, `wbapi/client.go:62`). Поставка >100 заданий
ломает Ship.

### Р3. Заказ с supply_id без supply_orders при закрытой поставке
Формирование ставит `supply_id`; если Ship закрыл поставку до выполнения
`add_orders`, команда паркуется (`commands/supply.go` addOrders: state≠open
→ permanent), заказ не в пуле и нигде не виден. Нужен детект «supply_id
есть, активной строки supply_orders нет» → возврат в пул (supply_id=NULL)
или перевод в преемник.

### Р4. Kafka: коммит N+1 после ошибки на N
`internal/platform/kafka/consumer.go:~150`: ошибка обработчика не коммитит
offset, но следующий успешный коммит (N+1) сносит и N. Нужно не коммитить
дальше failed offset в пределах партиции (очередь pending-commit по
партициям) или останавливать чтение партиции до разрешения.

### Р5. Потерянный ответ create_supply → дубль поставки
`commands/supply.go` createSupply: идемпотентность только по state=open +
wb_supply_id; при потерянном ответе повторный POST создаёт вторую поставку.
Перед повтором — сверка с WB (поиск открытой поставки по имени/составу) или
переиспользование.

### Р6. Гонка отмена × упаковка
`packContext` читает без FOR UPDATE; отмена между проверкой и insert
pack_scan проскакивает, pull-задача не появляется (requestPullTx — UPDATE
по существующей строке). Сериализовать: блокировка строки заказа на время
pack-scan, либо pull-задача при отмене должна смотреть и на «скан идёт
прямо сейчас».

## Производительность и хозяйство (третья очередь, до прода)

- **П1.** UpsertOrders / ApplyStatuses: 3–6 round trips на заказ в одной
  транзакции → при массовом heal тысячи round trips. Чанки + set-based
  (unnest) операции.
- **П2.** Пул формирования: добавить индекс под
  `supplier_status='new' AND supply_id IS NULL ORDER BY created_at`
  (существующий `orders_status_idx` ему не соответствует).
- **П3.** N+1: `AddSupplyOrders` (supply.go:138-157), `InsertMetaChecks`
  (supply.go:338-354), перенос остатков при Ship (по транзакции на заказ).
  Свести к set-based.
- **П4.** `nextPackSeq` (pack.go:240) max(seq)+1 без блокировки → гонка
  двух упаковщиков одной поставки; UNIQUE спасает данные, но второй
  упаковщик получает 500. Сериализовать на поставку (advisory lock по
  supply_id).
- **П5.** Retention только у wh_events/order_events/outbox. `stickers.payload`
  (~10 KiB × 20 тыс./сутки ≈ 73 ГБ/год), `meta_checks`, `pack_scans`,
  `supply_orders`, `orders` растут безгранично. Партиционировать и/или
  retention по тем же рельсам (maintenance-цикл уже есть).
- **П6.** Пул pgx голый (`platform/storage/postgres.go`): задать MaxConns,
  таймауты acquire/statement, application_name; учесть, что writer lease
  держит одно соединение постоянно.
- **П7.** Maintenance дропает outbox-партиции независимо от состояния строк:
  перед дропом проверять отсутствие не-terminal строк (pending/sent/failed),
  иначе пропускать партицию.

## Порядок работ и приёмка

1. Б1–Б4 (блокеры), каждый со своим тестом по приёмке выше.
2. Р1–Р6.
3. П1–П7.
4. После каждой группы: `go build/vet/test` зелёные + pgstore-сьют с
  `WBCONNECTOR_TEST_DSN`; `make e2e-sandbox` обязателен после Б1–Б4
  (он ловит порядок intake→формирование→Ship).
5. Обновить `docs/research/marketplaces/HANDOFF-*.md` по завершении.

## Ссылки

- Ревью-источник: сессия 2026-08-18, HEAD `3c796e2`.
- Контурные факты: `docs/research/marketplaces/HANDOFF-2026-08-17.md`.
- Стейдж: сервис + wbstatus + cron wbgoods раскатаны; свежие тестовые заказы
  идут из блока 32 (после миграции `20260818120000_order_block_32.sql`).
