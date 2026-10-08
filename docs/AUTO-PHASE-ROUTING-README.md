# Auto-Phase Routing System — начало работы

Это документация для **WorkerMessage Protocol** — системы автоматического перехода worker'а между фазами без ожидания координатора.

## Что это такое?

**Раньше:**
```
Worker завершил фазу
  ↓ ждёт координатора вручную
Coordinator получает worker_done (30 мин могут пройти)
  ↓ читает результат, проверяет
Coordinator вручную запускает worker'а в следующую фазу
```

**Теперь:**
```
Worker завершил фазу
  ↓ send-phase-complete (1 команда)
Coordinator автоматически получает сообщение
  ↓ парсит JSON, проверяет статус
[success] → автоматически запускает next phase
[partial/failed] → требуется вмешательство
```

## Быстрый старт

### Для координатора

```bash
# 1. Запустить задачу
scripts/gj/orchestrate.sh lead OPSOMN002-123 "Описание задачи"

# 2. Запустить монитор фаз (в фоне!)
scripts/gj/orchestrate.sh monitor-auto-phase OPSOMN002-123 &

# 3. Ждать — worker теперь сам будет запускать фазы
# Координатор видит логирование в .tasks/opsomn002-123/phase-transitions.log
```

### Для worker'а

```bash
# После завершения каждой фазы:
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "<phase>" "<status>"

# Примеры:
scripts/gj/orchestrate.sh send-phase-complete abc123 "understanding" "success"
scripts/gj/orchestrate.sh send-phase-complete abc123 "planning" "success"
scripts/gj/orchestrate.sh send-phase-complete abc123 "implementation" "success"
```

## Структура фаз

```
understanding (анализ требований)
    ↓ [success]
planning (планирование подхода)
    ↓ [success]
implementation (кодирование)
    ↓ [success]
testing (тестирование)
    ↓ [success]
verification (финальная проверка)
    ↓ [success]
done (готово)
```

**Замечание:** если status ≠ success, фаза повторяется (на той же или с коррекцией).

## Основные команды

### Для worker'а (отправка сообщений о завершении фаз)

```bash
# Отправить успешное завершение
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "understanding" "success"

# Отправить partial (требует вмешательства)
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "planning" "partial"

# Отправить failed (критическая проблема)
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "implementation" "failed"
```

### Для координатора (мониторинг и управление)

```bash
# Запустить монитор с автоматическими переходами (30 мин по умолчанию)
scripts/gj/orchestrate.sh monitor-auto-phase OPSOMN002-123

# Запустить с кастомным таймаутом (1 час)
scripts/gj/orchestrate.sh monitor-auto-phase OPSOMN002-123 3600000

# Посмотреть все переходы фаз
cat .tasks/opsomn002-123/phase-transitions.log

# Если нужно вмешаться
scripts/gj/orchestrate.sh say <dispatch> "Переходи к implementation, problems решены"

# Стандартные команды всё ещё работают
scripts/gj/orchestrate.sh wait
scripts/gj/orchestrate.sh questions
scripts/gj/orchestrate.sh answer <dispatch> "ответ на вопрос"
```

## JSON Schema

Worker отправляет структурированное JSON-сообщение:

```json
{
  "type": "phase_complete",
  "phase": "understanding",
  "status": "success",
  "summary": "Требования разобраны, найдены 4 файла для правки",
  "blockers": [],
  "timestamp": "2024-10-08T15:30:45Z"
}
```

## Состояния фаз

| Status | Действие | Пример |
|---|---|---|
| **success** | Перейти в next_phase автоматически | `understanding → planning` |
| **partial** | Остаться на той же фазе, требует ввода | `planning → planning` (нужны уточнения) |
| **failed** | Остаться на фазе, требует помощи | `implementation → implementation` (баг) |

## Логирование

Все переходы логируются в `.tasks/<ключ>/phase-transitions.log`:

```
2024-10-08 14:15:32	understanding	success → planning
2024-10-08 14:28:15	planning	success → implementation
2024-10-08 15:45:22	implementation	success → testing
2024-10-08 17:30:11	testing	success → verification
2024-10-08 17:35:44	verification	success → done
```

Это позволяет координатору видеть весь путь задачи без вмешательства.

## Сценарии использования

### Сценарий 1: Плавная работа без блокеров

```bash
# Координатор
scripts/gj/orchestrate.sh lead OPSOMN002-100 "Задача"
scripts/gj/orchestrate.sh monitor-auto-phase OPSOMN002-100 &

# Worker (в своей сессии, без координатора)
send-phase-complete ... "understanding" "success"  # 14:00
send-phase-complete ... "planning" "success"       # 14:30
send-phase-complete ... "implementation" "success" # 16:00
send-phase-complete ... "testing" "success"        # 17:30
send-phase-complete ... "verification" "success"   # 18:00

# Результат: 4 часа работы, координатор не вмешивался
```

### Сценарий 2: Блокер требует помощи

```bash
# Worker отправляет partial
send-phase-complete ... "understanding" "partial"
# blockers: ["API не документирована"]

# Координатор получает сигнал (можно посмотреть через `wait`)
# Вмешивается:
scripts/gj/orchestrate.sh say dispatch "Запросил доступ к документации, жди 30 мин"

# Worker после получения доступа:
send-phase-complete ... "understanding" "success"
# → автоматический переход в planning
```

### Сценарий 3: Критический отказ

```bash
# Worker находит critical bug
send-phase-complete ... "testing" "failed"
# blockers: ["SQL ошибка в миграции"]

# Координатор видит failed и не переходит автоматически
# Проверяет логи:
scripts/gj/orchestrate.sh read dispatch | tail -20

# Помогает:
scripts/gj/orchestrate.sh say dispatch "SQL syntax on line 42: должен быть TEXT не VARCHAR"

# Worker исправляет и отправляет:
send-phase-complete ... "testing" "success"
# → автоматический переход в verification
```

## Интеграция со скиллами

Скиллы (например, `gj-task-orchestration`) должны инструктировать worker'а:

```markdown
## Завершение фазы understanding

Когда требования полностью разобраны:

```bash
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "understanding" "success"
```

Координатор автоматически уведомит тебя о переходе в Planning.
```

Подробнее в [`skill-integration-worker-messaging.md`](skill-integration-worker-messaging.md).

## Часто задаваемые вопросы

### Что если я забыл отправить сообщение?

Worker может отправить его позже. Координатор будет ждать до таймаута (30 мин по умолчанию).

### Может ли быть несколько сообщений за одну фазу?

Да, каждое новое сообщение перезаписывает статус. Последнее сообщение — финальное.

### Что если я отправлю сообщение вручную через Orca?

Если JSON-структура правильная, система обработает его так же, как и через `send-phase-complete`.

### Может ли worker пропустить фазу?

Нет, фазы идут линейно. Пропуск — только по явному указанию координатора через `say`.

### Как откатиться на фазу назад?

Откат — явное указание координатора через `say`. Система не поддерживает автоматический откат.

### Где найти мой dispatch ID?

- В инструкции координатора (`Dispatch: abc123xyz`)
- Файл `.tasks/<ключ>/.dispatch`
- Вывод `orchestrate.sh list`

## Дополнительные ресурсы

- 📖 [`worker-messaging-protocol.md`](worker-messaging-protocol.md) — полная спецификация протокола
- 🎯 [`skill-integration-worker-messaging.md`](skill-integration-worker-messaging.md) — как интегрировать со скиллами
- 📋 [`worker-messaging-examples.md`](worker-messaging-examples.md) — примеры и тестовые сценарии
- 🔧 `scripts/gj/orchestrate.sh` — исходный код (функции `send-phase-complete`, `monitor-auto-phase`, и т.д.)

## Устранение проблем

### Монитор не получает сообщения

```bash
# Проверить, запущен ли монитор
jobs -p | grep monitor-auto-phase

# Если нет, перезапустить
scripts/gj/orchestrate.sh monitor-auto-phase OPSOMN002-123 &

# Проверить dispatch ID
cat .tasks/opsomn002-123/.dispatch
```

### Worker не может отправить сообщение

```bash
# Проверить dispatch ID
echo $DISPATCH  # если не установлена

# Проверить права на scripts/
ls -la scripts/gj/orchestrate.sh

# Попробовать отправить вручную
$ORCA orchestration send --to "dispatch:abc123" --subject "test" --body "test message"
```

### Монитор упал или зависла

```bash
# Убить зависший процесс
pkill -f "monitor-auto-phase OPSOMN002-123"

# Перезапустить
scripts/gj/orchestrate.sh monitor-auto-phase OPSOMN002-123 &
```

## Итого

**WorkerMessage Protocol** — это система для автоматизации переходов между фазами. Worker отправляет одну команду (`send-phase-complete`), координатор видит логирование, и если всё успешно — next фаза запускается автоматически.

**Когда использовать:**
- ✓ Задачи с несколькими фазами (understanding → planning → implementation → ...)
- ✓ Когда coordinator может работать асинхронно (не вмешиваться между фазами)
- ✓ Когда worker может быть автономным и работать по скиллам

**Когда не использовать:**
- ✗ Простые одно-фазовые задачи (просто worker_done)
- ✗ Когда координатор должен проверить каждый шаг (используй `wait` и `answer`)
- ✗ Когда фазы не линейны (используй `say` и явное управление)

---

**Версия:** 1.0 (2024-10-08)  
**Автор:** Orca Automation System  
**Статус:** Production-ready
