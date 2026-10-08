# WorkerMessage Protocol — примеры и тестовые сценарии

---

## Пример 1: Простая задача с автоматическими переходами

### Задача
OPSOMN002-300: "Добавить поле last_updated в таблицу orders"

### Сценарий: всё прошло идеально

**Шаг 1. Координатор запускает lead**

```bash
scripts/gj/orchestrate.sh lead OPSOMN002-300 "Добавить last_updated в orders"
# Выдаст: координатор запущен в вкладке "OPSOMN002-300 · координатор"
```

**Шаг 2. Координатор запускает монитор в фоне**

```bash
scripts/gj/orchestrate.sh monitor-auto-phase OPSOMN002-300 &
# Выдаст: "мониторим фазы для opsomn002-300 (dispatch: abc123xyz-def456)"
```

**Шаг 3. Worker в своей сессии работает по фазам**

```bash
# === PHASE 1: Understanding ===
# Worker читает инструкцию, находит файлы, трассирует код
# ... [работа по пониманию] ...
# Готово! Отправляет сообщение:

scripts/gj/orchestrate.sh send-phase-complete abc123xyz-def456 "understanding" "success"
# Выдаст: "фаза understanding отправлена (→ planning)"
```

**Результат в координаторе:**
```
[фаза understanding завершена: success] переход в planning
→ запуск следующей фазы: planning
фаза understanding отправлена (→ planning)
```

**Шаг 4. Worker автоматически получает указание**

Координатор отправляет worker'у через Orca:
```
Координатор: переходи в фазу planning. Предыдущая фаза (understanding) завершена.
```

Worker видит это в своей сессии и переходит к phase 2.

```bash
# === PHASE 2: Planning ===
# Worker разбирает задачу, составляет план
# ... [работа по планированию] ...
# Готово!

scripts/gj/orchestrate.sh send-phase-complete abc123xyz-def456 "planning" "success"
# Выдаст: "фаза planning отправлена (→ implementation)"
```

**Результат:**
```
[фаза planning завершена: success] переход в implementation
→ запуск следующей фазы: implementation
```

**Шаг 5. Phase 3: Implementation**

```bash
# ... [кодирование] ...
scripts/gj/orchestrate.sh send-phase-complete abc123xyz-def456 "implementation" "success"
# Выдаст: "фаза implementation отправлена (→ testing)"
```

**Шаг 6. Phase 4: Testing**

```bash
# ... [тесты] ...
scripts/gj/orchestrate.sh send-phase-complete abc123xyz-def456 "testing" "success"
# Выдаст: "фаза testing отправлена (→ verification)"
```

**Шаг 7. Phase 5: Verification**

```bash
# ... [финальная проверка] ...
# expect.sh есть и прошла:
scripts/gj/orchestrate.sh send-phase-complete abc123xyz-def456 "verification" "success"
# Выдаст: "фаза verification отправлена (→ done)"
```

### Логирование в .tasks/opsomn002-300/phase-transitions.log

```
2024-10-08 14:00:00	START	auto-monitor started
2024-10-08 14:15:32	understanding	success → planning	Требования разобраны, точки входа найдены
2024-10-08 14:28:15	planning	success → implementation	План согласован, таблица шагов готова
2024-10-08 15:45:22	implementation	success → testing	Код готов, 3 коммита
2024-10-08 17:30:11	testing	success → verification	Все тесты пройдены
2024-10-08 17:35:44	verification	success → done	expect.sh прошла, готово к сдаче
2024-10-08 17:35:45	END	auto-monitor finished
```

### Вся задача заняла 3.5 часа, координатор не вмешивался

---

## Пример 2: Задача с блокером

### Задача
OPSOMN002-301: "Интегрировать YooKassa в мобильное приложение"

### Сценарий: блокер в understanding фазе

**Шаг 1-2. Обычный запуск**

```bash
# Координатор:
scripts/gj/orchestrate.sh lead OPSOMN002-301 "Интегрировать YooKassa"
scripts/gj/orchestrate.sh monitor-auto-phase OPSOMN002-301 &
```

**Шаг 3. Worker начинает understanding**

```bash
# ... [анализ кода] ...
# Worker находит контракт API:
grep -r "yookassa" platform/mobile-app/ | head -5
# Результат: нет актуальной документации, только старая версия SDK

# Worker отправляет partial:
scripts/gj/orchestrate.sh send-phase-complete abc123xyz-def456 "understanding" "partial"
# Выдаст: "фаза understanding отправлена (→ understanding)"
```

**Результат в координаторе:**
```
[фаза understanding завершена: partial] переход в understanding
  ⚠ статус partial — требуется вмешательство, не переходим автоматически
```

**Шаг 4. Координатор видит проблему**

Координатор проверяет лог:
```bash
tail .tasks/opsomn002-301/phase-transitions.log
# 2024-10-08 14:20:00	understanding	partial → understanding	(нет резюме)
```

Координатор спрашивает worker'а:
```bash
scripts/gj/orchestrate.sh answer abc123xyz-def456 "Какой блокер? Нужна документация API?"
```

**Шаг 5. Worker отвечает**

Worker получает вопрос и отвечает:
```bash
scripts/gj/orchestrate.sh say abc123xyz-def456 "Да, документация по YooKassa устаревшая. Нужен доступ к актуальному SDK"
```

**Шаг 6. Координатор решает проблему**

Координатор запрашивает доступ у владельца YooKassa SDK или документации. После получения доступа:

```bash
scripts/gj/orchestrate.sh say abc123xyz-def456 "Доступ получен, вот ссылка на актуальный SDK: https://..."
```

**Шаг 7. Worker продолжает, отправляет success**

Worker изучает актуальную документацию:
```bash
# ... [теперь всё ясно] ...
scripts/gj/orchestrate.sh send-phase-complete abc123xyz-def456 "understanding" "success"
# Выдаст: "фаза understanding отправлена (→ planning)"
```

**Результат:**
```
[фаза understanding завершена: success] переход в planning
→ запуск следующей фазы: planning
```

### Лог взаимодействия

```
2024-10-08 14:20:00	understanding	partial → understanding	Документация устаревшая
2024-10-08 14:25:15	[вопрос от coordinator]	"Какой блокер?"
2024-10-08 14:26:33	[ответ от worker]	"Нужен доступ к SDK"
2024-10-08 14:35:22	[указание от coordinator]	"Доступ получен, вот ссылка"
2024-10-08 14:40:11	understanding	success → planning	(повторно)
```

---

## Пример 3: Критический отказ

### Задача
OPSOMN002-302: "Миграция базы данных на PostgreSQL 15"

### Сценарий: ошибка в implementation фазе

**Шаг 1-3. Обычный запуск**

```bash
scripts/gj/orchestrate.sh lead OPSOMN002-302 "Миграция на PG 15"
scripts/gj/orchestrate.sh monitor-auto-phase OPSOMN002-302 &
```

**Шаг 4. Worker проходит understanding и planning успешно**

```bash
scripts/gj/orchestrate.sh send-phase-complete abc123xyz-def456 "understanding" "success"
scripts/gj/orchestrate.sh send-phase-complete abc123xyz-def456 "planning" "success"
```

**Шаг 5. Worker начинает implementation**

```bash
# ... [написание миграции] ...
# Worker пишет SQL, коммитит

# Локальное тестирование:
psql -U test db < migration.sql
# ERROR: syntax error in line 27

# Worker находит ошибку и пытается исправить
# ... [ещё попытки] ...
# Так и не разобрался! Миграция некорректна или несовместима

# Worker отправляет failed:
scripts/gj/orchestrate.sh send-phase-complete abc123xyz-def456 "implementation" "failed"
# Выдаст: "фаза implementation отправлена (→ implementation)"
```

**Результат в координаторе:**
```
[фаза implementation завершена: failed] переход в implementation
  ⚠ статус failed — требуется вмешательство, не переходим автоматически
```

**Шаг 6. Координатор видит отказ**

```bash
# Лог показывает:
tail .tasks/opsomn002-302/phase-transitions.log
# 2024-10-08 15:30:22	implementation	failed → implementation	SQL syntax error

# Координатор читает последний вывод worker'а:
scripts/gj/orchestrate.sh read abc123xyz-def456 | tail -50
# ... выводится ошибка SQL

# Координатор видит проблему: непорядок в миграции
# Может либо:
# 1) Отправить worker'у исправленный код
# 2) Назначить себе эту часть
# 3) Запросить помощь у DBA-архитектора

# Координатор вызывает help:
scripts/gj/orchestrate.sh say abc123xyz-def456 "Нужна помощь: ошибка в миграции, вызываю ДБА-архитектора"
```

**Шаг 7. Архитектор смотрит и помогает**

ДБА-архитектор получает вопрос через escalation и предлагает решение. Координатор передаёт worker'у:

```bash
scripts/gj/orchestrate.sh say abc123xyz-def456 "Ошибка была в типе данных (должен быть TEXT вместо VARCHAR). Исправьте и переделайте миграцию"
```

**Шаг 8. Worker исправляет и отправляет success**

```bash
# ... [исправление миграции] ...
# Локальное тестирование: ✓
scripts/gj/orchestrate.sh send-phase-complete abc123xyz-def456 "implementation" "success"
# Автоматический переход в testing
```

### Лог

```
2024-10-08 15:30:22	implementation	failed → implementation	SQL syntax error in line 27
2024-10-08 15:32:11	[escalation]	"Нужна помощь: ошибка в миграции"
2024-10-08 15:45:33	[указание от coordinator]	"Ошибка в типе данных, исправьте"
2024-10-08 16:20:11	implementation	success → testing	(повторно)
```

---

## Пример 4: Множественные worker'ы (параллельная разработка)

### Сценарий

Две независимые задачи OPSOMN002-310 и OPSOMN002-311 работают параллельно.

**Координатор**

```bash
# Задача 1
scripts/gj/orchestrate.sh lead OPSOMN002-310 "Фича A"
scripts/gj/orchestrate.sh monitor-auto-phase OPSOMN002-310 &

# Задача 2
scripts/gj/orchestrate.sh lead OPSOMN002-311 "Фича B"
scripts/gj/orchestrate.sh monitor-auto-phase OPSOMN002-311 &

# Координатор может смотреть оба логи:
scripts/gj/orchestrate.sh list
# Выдаст: две вкладки worker'ов и два монитора
```

**Worker 1** (работает быстро)

```bash
# 14:00 - understanding success
scripts/gj/orchestrate.sh send-phase-complete dispatch1 "understanding" "success"
# 14:20 - planning success
scripts/gj/orchestrate.sh send-phase-complete dispatch1 "planning" "success"
# 15:30 - implementation success
scripts/gj/orchestrate.sh send-phase-complete dispatch1 "implementation" "success"
# 17:00 - testing success
scripts/gj/orchestrate.sh send-phase-complete dispatch1 "testing" "success"
# 17:15 - verification success
scripts/gj/orchestrate.sh send-phase-complete dispatch1 "verification" "success"
# Готово: 3 часа
```

**Worker 2** (проблемы)

```bash
# 14:10 - understanding success
scripts/gj/orchestrate.sh send-phase-complete dispatch2 "understanding" "success"
# 14:45 - planning partial (нужны уточнения)
scripts/gj/orchestrate.sh send-phase-complete dispatch2 "planning" "partial"
# [координатор вмешивается, отправляет ответ]
# 16:00 - planning success (повторно)
scripts/gj/orchestrate.sh send-phase-complete dispatch2 "planning" "success"
# 18:00 - testing failed (критический баг)
scripts/gj/orchestrate.sh send-phase-complete dispatch2 "testing" "failed"
# [координатор помогает]
# 19:30 - testing success (повторно)
# Готово: 5+ часов
```

**Координатор видит в list**

```bash
scripts/gj/orchestrate.sh list
# opsomn002-310: verification ✓ [готов к done]
# opsomn002-311: testing (retry) [всё ещё работает]
```

---

## Пример 5: Timeout и потеря соединения

### Сценарий

Worker завис или потерял соединение, не отправил сообщение о фазе.

**Что происходит:**

```bash
# Монитор ждёт с timeout 30 минут (по умолчанию)
scripts/gj/orchestrate.sh monitor-auto-phase OPSOMN002-320 1800000

# ... [работник ничего не отправляет 30 минут] ...
# Монитор истекает:
# за 1800 с смыслового события нет (таймаут — точка проверки, а не сбой)
```

**Координатор получает сигнал о таймауте**

```bash
tail .tasks/opsomn002-320/phase-transitions.log
# 2024-10-08 14:00:00	START	auto-monitor started
# [30 минут молчания]
# 2024-10-08 14:30:01	END	auto-monitor finished
```

**Координатор вмешивается**

```bash
# Проверить, что делает worker
scripts/gj/orchestrate.sh read dispatch123 | tail -50
# [смотрит последние логи работника]

# Если worker жив, но не отвечает:
scripts/gj/orchestrate.sh say dispatch123 "Где ты? Какая фаза? Отправь сообщение о фазе"

# Если worker упал:
scripts/gj/orchestrate.sh release dispatch123
# и запустить его заново
```

---

## Тестовые сценарии для разработчиков

### Test 1: Базовый переход успешный

```bash
# Setup
KEY="test-phase-001"
dispatch=$(cat .tasks/test-phase-001/.dispatch)

# Test: отправить success → должен перейти в next
scripts/gj/orchestrate.sh send-phase-complete "$dispatch" "understanding" "success"

# Verify
grep "understanding.*success" .tasks/test-phase-001/phase-transitions.log
# Expected: "2024-10-08 XX:XX:XX	understanding	success → planning"
```

### Test 2: Partial status → не переходит

```bash
# Test: отправить partial → не должно быть автоматического перехода
scripts/gj/orchestrate.sh send-phase-complete "$dispatch" "planning" "partial"

# Verify
tail -1 .tasks/test-phase-002/phase-transitions.log | grep "planning.*partial"
# Expected: "2024-10-08 XX:XX:XX	planning	partial → planning"
# (то есть остаётся на той же фазе)
```

### Test 3: Failed status → не переходит

```bash
# Test: отправить failed
scripts/gj/orchestrate.sh send-phase-complete "$dispatch" "implementation" "failed"

# Verify: статус должен остаться на implementation
grep "implementation.*failed" .tasks/test-phase-003/phase-transitions.log
```

### Test 4: Monitor timeout

```bash
# Test: запустить монитор с малым таймаутом
GJ_PHASE_TIMEOUT=5000 scripts/gj/orchestrate.sh monitor-auto-phase test-phase-004 &
sleep 6

# Verify: монитор должен был выйти
jobs -p | grep -q "monitor-auto-phase" && echo "FAIL: monitor should have exited" || echo "PASS"
```

### Test 5: Multiple phases in sequence

```bash
# Test: отправить все фазы подряд success
for phase in understanding planning implementation testing verification; do
  scripts/gj/orchestrate.sh send-phase-complete "$dispatch" "$phase" "success"
  sleep 1
done

# Verify: лог должен показать все переходы
wc -l .tasks/test-phase-005/phase-transitions.log
# Expected: 6 строк (START + 5 фаз)
```

---

## Загрузка тестирования

Для проверки performance под нагрузкой:

```bash
# Запустить 10 параллельных monitor'ов
for i in {1..10}; do
  scripts/gj/orchestrate.sh monitor-auto-phase "test-load-$i" 600000 &
done

# Отправить события от всех 10
for i in {1..10}; do
  dispatch=$(cat .tasks/test-load-$i/.dispatch)
  scripts/gj/orchestrate.sh send-phase-complete "$dispatch" "understanding" "success" &
done

# Подождать
wait

# Проверить, что все справились
for i in {1..10}; do
  grep -q "understanding.*success" .tasks/test-load-$i/phase-transitions.log && echo "test-load-$i: PASS" || echo "test-load-$i: FAIL"
done
```
