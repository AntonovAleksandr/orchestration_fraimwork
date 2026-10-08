# WorkerMessage Protocol — автоматизация фаз между worker'ом и координатором

## Обзор

**WorkerMessage Protocol** — это система обмена сообщениями между worker'ом Orca и координатором, которая автоматизирует переходы между фазами задачи без необходимости ручного вмешательства координатора.

**Цель:** worker завершает фазу → отправляет сообщение → координатор автоматически запускает следующую фазу.

---

## Фазы задачи (Phase Model)

Каждая задача проходит линейно через фазы:

1. **understanding** — анализ и понимание требований
2. **planning** — планирование подхода и разделение на подзадачи
3. **implementation** — написание кода, правки, коммиты
4. **testing** — локальные прогоны, проверка крайних случаев
5. **verification** — финальная проверка всей системы, expect.sh если задана
6. **done** — задача завершена

### Переходы между фазами

| Фаза → Фаза | Условие | Пример |
|---|---|---|
| understanding → planning | status=success | требования понятны, задача разбита |
| understanding → understanding | status=partial\|failed | нужны уточнения |
| planning → implementation | status=success | планирование завершено |
| planning → planning | status=partial\|failed | план нуждается в доработке |
| implementation → testing | status=success | код готов |
| implementation → implementation | status=partial\|failed | правки или баги |
| testing → verification | status=success | тесты проходят |
| testing → testing | status=partial\|failed | найдены ошибки |
| verification → done | status=success | всё проверено |
| verification → verification | status=partial\|failed | проверка не прошла |

---

## Структура WorkerMessage (JSON)

Worker отправляет структурированное JSON-сообщение при завершении фазы:

```json
{
  "type": "phase_complete",
  "phase": "understanding",
  "status": "success",
  "next_phase": "planning",
  "summary": "Задача OPSOMN002-123: найлили где живёт код корзины, определили точки входа, задокументировали workflow",
  "blockers": [],
  "timestamp": "2024-10-08T15:30:45Z"
}
```

### Поля

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `type` | string | ✓ | Всегда `"phase_complete"` |
| `phase` | string | ✓ | Текущая завершённая фаза: `understanding\|planning\|implementation\|testing\|verification` |
| `status` | string | ✓ | Статус завершения: `success\|partial\|failed` |
| `next_phase` | string | — | Рекомендуемая следующая фаза (опционально; координатор вычислит сам) |
| `summary` | string | — | Краткое описание что сделано (до 200 символов) |
| `blockers` | array | — | Список блокеров (если status≠success): `["нет доступа к prod", "API недокументирован"]` |
| `timestamp` | string | — | ISO 8601 момент отправки (заполняется автоматически) |

### Примеры

#### Успешное завершение фазы planning
```json
{
  "type": "phase_complete",
  "phase": "planning",
  "status": "success",
  "summary": "Разобран workflow, идентифицированы 4 файла для правки, составлен план",
  "blockers": []
}
```

#### Частичное завершение с блокерами
```json
{
  "type": "phase_complete",
  "phase": "understanding",
  "status": "partial",
  "summary": "Найдены точки входа, но контракт API не совпадает с документацией",
  "blockers": [
    "docs/api.md не обновлена с 2023-05",
    "мобильный клиент использует field_old, сайт ждёт field_new"
  ]
}
```

#### Критический отказ
```json
{
  "type": "phase_complete",
  "phase": "implementation",
  "status": "failed",
  "summary": "Тесты базы данных не проходят: миграция ломается",
  "blockers": [
    "SQL syntax error в миграции #127",
    "Нужен код для отката"
  ]
}
```

---

## Как Worker отправляет сообщение

### Через API Orca (SendMessage)

Worker вызывает команду SendMessage для отправки сообщения координатору:

```python
# Пример из контекста worker'а
import json
import subprocess

message = {
    "type": "phase_complete",
    "phase": "understanding",
    "status": "success",
    "summary": "Требования разобраны, начинаем planning",
    "blockers": []
}

# Отправить через orchestration send (работает из любого контекста)
subprocess.run([
    "orca", "orchestration", "send",
    "--to", f"dispatch:{dispatch_id}",
    "--subject", "phase_complete: understanding → planning",
    "--body", json.dumps(message),
    "--json"
], capture_output=True)
```

### Через bash скрипт (в дереве воркера)

```bash
#!/bin/bash
dispatch_id="abc123xyz"

# Отправить завершение understanding фазы
scripts/gj/orchestrate.sh send-phase-complete "$dispatch_id" "understanding" "success" "planning"
```

---

## Как Координатор обрабатывает сообщения

### Команда monitor-auto-phase

Координатор запускает монитор в фоне сразу после запуска worker'а:

```bash
# В инструкции lead_spec
scripts/gj/orchestrate.sh monitor-auto-phase OPSOMN002-123 &
```

**Что она делает:**

1. **Ждёт сообщения** от worker'а типа `phase_complete`
2. **Парсит JSON** сообщение
3. **Логирует переход** в `.tasks/opsomn002-123/phase-transitions.log`
4. **Вычисляет next_phase** на основе phase + status (если не задана)
5. **Проверяет статус:**
   - ✓ **success** → автоматически запуск следующей фазы
   - ⚠ **partial/failed** → логирует, **НЕ переходит** (требуется вмешательство)
6. **Отправляет worker'у указание** о переходе в следующую фазу
7. **Продолжает ждать** следующего сообщения

### Логирование

Каждый переход записывается в `.tasks/opsomn002-123/phase-transitions.log`:

```
2024-10-08 15:30:45	understanding	success → planning	Требования разобраны
2024-10-08 15:45:22	planning	success → implementation	План согласован
2024-10-08 18:12:11	implementation	partial → implementation	Баг в миграции, перепроверяем
2024-10-08 18:25:33	implementation	success → testing	Код готов
```

---

## Интеграция со скиллами worker'а

### Когда Worker завершает фазу

В конце каждой фазы скилл (например, `gj-task-orchestration`) может предложить worker'у отправить сообщение:

```markdown
# Фаза: Understanding

[... работа по пониманию требований ...]

## Завершение фазы

Отправьте сообщение о завершении:
```bash
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "understanding" "success"
```

Это уведомит координатора, что понимание завершено, и тот автоматически запустит planning.
```

---

## Примеры использования

### Сценарий 1: Автоматический workflow без вмешательства

```bash
# Координатор
scripts/gj/orchestrate.sh lead OPSOMN002-123 "Добавить поле в корзину"

# ... в фоне
scripts/gj/orchestrate.sh monitor-auto-phase OPSOMN002-123 &

# Worker (в его сессии) при завершении каждой фазы:
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "understanding" "success"
# → автоматически переходит в planning

scripts/gj/orchestrate.sh send-phase-complete <dispatch> "planning" "success"
# → автоматически переходит в implementation
```

**Результат:** работа идёт без остановок, координатор видит лог переходов.

### Сценарий 2: Блокер требует участия

```bash
# Worker отправляет partial status
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "understanding" "partial"

# Блокер: API не документирована

# Координатор видит в логе и отправляет worker'у вопрос
scripts/gj/orchestrate.sh answer <dispatch> "Запросил доступ у владельца API, он ответит завтра"

# Worker получает ответ и может продолжить (если научился работать обходным путём)
# или ждать (если критично)
```

### Сценарий 3: Критический отказ

```bash
# Worker находит неразрешимую проблему
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "implementation" "failed"

# Блокер: миграция БД ломается

# Coordinator видит в логе, проверяет ошибку
scripts/gj/orchestrate.sh read <dispatch> | tail -20

# Принимает решение: отправить worker'у новую инструкцию
scripts/gj/orchestrate.sh say <dispatch> "Откати миграцию #127, используй колонку с суффиксом _new"

# Worker видит указание и исправляет, затем отправляет success
```

---

## Обработка ошибок

### Что если worker отправит некорректный JSON?

```bash
# Worker отправит неправильное сообщение
# → Monitor парсит, не может десериализовать
# → Логирует ошибку, ждёт исправления
# → Координатор видит в логе: "ошибка парсинга JSON"
```

**Решение:** worker отправляет исправленное сообщение.

### Что если worker завис и не отправляет сообщение?

```bash
# Монитор работает с timeout (по умолчанию 30 минут)
# По истечении — выходит из монитора
# → Координатор видит: "таймаут, смыслового события нет"
# → Проверяет worker'а через `read` и `questions`
```

**Решение:** координатор вмешивается, проверяет лог worker'а.

---

## Конфигурация

### Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `GJ_PHASE_TIMEOUT` | 1800000 (30 мин) | Таймаут монитора в мс |
| `GJ_PHASE_LOG_DIR` | `.tasks/<ключ>` | Где логировать переходы |
| `GJ_AUTO_PHASE` | 1 | Включить автоматический переход (0 = отключить) |

```bash
# Запустить монитор с кастомным таймаутом (1 час)
GJ_PHASE_TIMEOUT=3600000 scripts/gj/orchestrate.sh monitor-auto-phase OPSOMN002-123
```

---

## Архитектура

```
Worker (фаза заканчивается)
    ↓
  send-phase-complete или SendMessage
    ↓
Orca orchestration send (JSON payload)
    ↓
Coordinator (monitor-auto-phase в фоне)
    ↓
  Парсить, логировать, проверить статус
    ↓
[success] → вычислить next_phase → отправить worker'у → ждать дальше
[partial/failed] → логировать, НЕ переходить → требуется вмешательство
[done] → завершить монитор, отпустить worker
    ↓
.tasks/<key>/phase-transitions.log (аудит)
```

---

## Лучшие практики

1. **Отправляй сообщение сразу после завершения фазы**, а не потом
2. **Указывай realistic summary**, а не пусто — помогает координатору понять прогресс
3. **Логируй блокеры для partial/failed** — это единственный способ координатору узнать чего не хватает
4. **Не жди слишком долго перед отправкой** — если фаза заняла 2 часа, worker может отправить сообщение сразу по завершении
5. **Используй next_phase только если уверен**, иначе дай координатору вычислить автоматически

---

## FAQ

### Может ли worker пропустить фазу?

Нет, фазы идут линейно. Если нужно пропустить, это должно быть явной командой координатора через `say`.

### Может ли worker откатиться на одну фазу назад?

Нет, механизм поддерживает только движение вперёд. Откат — явное указание координатора.

### Что если координатор не запустил монитор?

Worker может отправлять сообщения, но они просто будут в очереди. Координатор позже сможет посмотреть их через `questions`.

### Может ли быть несколько monitor'ов для одной задачи?

Да, но они будут дублировать работу. Лучше запустить один раз в фоне.

### Как узнать, в какой фазе сейчас worker?

Прочитай `.tasks/<key>/.phase` или логи:
```bash
tail -5 .tasks/opsomn002-123/phase-transitions.log
```
