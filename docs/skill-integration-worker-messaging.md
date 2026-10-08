# Интеграция WorkerMessage Protocol со скиллами

Этот документ описывает, как скиллы (например, `gj-task-orchestration`, `gj-task-execution`) должны инструктировать worker'а отправлять сообщения о завершении фаз.

---

## Общее правило

После того, как worker завершил работу по фазе и пройдёл все критерии готовности фазы, скилл должен вставить инструкцию:

```markdown
## Завершение фазы

Отправьте координатору сообщение о завершении фазы:

```bash
# Если все критерии пройдены:
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "<phase>" "success"

# Если есть блокеры или неполнота:
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "<phase>" "partial"
```

**Координатор получит сообщение и автоматически запустит следующую фазу.**
```

---

## Интеграция по фазам

### Understanding (Анализ)

**Когда вставлять инструкцию:** после того, как worker понял требования, нашёл ключевые файлы кода, задокументировал точки входа.

```markdown
## Завершение фазы understanding

Если требования полностью разобраны и задача начинается в planning:
```bash
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "understanding" "success"
```

Если остались вопросы:
```bash
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "understanding" "partial"
```
```

**Критерии ready:**
- ✓ Найдены все затронутые файлы (`grep` или `codegraph`)
- ✓ Понятен workflow (трассировка вызовов)
- ✓ Известны edge cases или ограничения
- ✓ Написана вводная (раздел 1 с целью)

---

### Planning (Планирование)

**Когда вставлять инструкцию:** после составления плана, определения точек входа для правок, создания таблицы шагов.

```markdown
## Завершение фазы planning

Если план согласован и implementation может начаться:
```bash
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "planning" "success"
```

Если нужны уточнения:
```bash
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "planning" "partial"
```
```

**Критерии ready:**
- ✓ Таблица шагов заполнена (file:line, что менять)
- ✓ Определены dependencies между шагами (если есть)
- ✓ Вычислена таблица retry-safe-writes (если задача пишет в БД)
- ✓ Вводная обновлена (раздел 2 с плаом)

---

### Implementation (Кодирование)

**Когда вставлять инструкцию:** после завершения всех правок по плану, commit'ов, прохождения локального phpstan/tests.

```markdown
## Завершение фазы implementation

Если все правки внесены и коммиты готовы:
```bash
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "implementation" "success"
```

Если обнаружены баги, требующие переделки:
```bash
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "implementation" "failed"
```
```

**Критерии ready:**
- ✓ Все файлы из плана изменены
- ✓ Коммиты логичны и описаны
- ✓ phpstan/cs-fixer прошли (если PHP)
- ✓ Локальные unit-тесты прошли
- ✓ Вводная обновлена (раздел 3 с что сделано)

---

### Testing (Тестирование)

**Когда вставлять инструкцию:** после полных прогонов всех затронутых путей, проверки edge cases.

```markdown
## Завершение фазы testing

Если все тесты прошли и баги не найдены:
```bash
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "testing" "success"
```

Если найдены баги:
```bash
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "testing" "failed"
```
```

**Критерии ready:**
- ✓ Полный прогон всех затронутых путей (не только один)
- ✓ Проверены edge cases (null, пусто, граница)
- ✓ Нет новых warning'ов в логах
- ✓ Баги задокументированы (если есть)

---

### Verification (Финальная проверка)

**Когда вставлять инструкцию:** после проверки expect.sh и финальной ревизии по чек-листам скилла.

```markdown
## Завершение фазы verification

Если все критерии готовности пройдены и ревизия завершена:
```bash
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "verification" "success"
```

Если найдены нарушения критериев:
```bash
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "verification" "failed"
```
```

**Критерии ready:**
- ✓ expect.sh прошла (если задана)
- ✓ Все пункты чек-листа скилла пройдены
- ✓ Вводная обновлена (раздел 4 с что сделано, что осталось, выкатка)

---

## Пример: скилл gj-task-orchestration

В разделе каждой фазы скилл должен содержать:

```markdown
# Phase 1: Understanding

[... инструкции по анализу ...]

## Завершение

Когда требования разобраны:

```bash
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "understanding" "success"
```

Координатор автоматически уведомит тебя о переходе в Planning.
```

---

## Обработка dispatch ID

Worker должен знать свой `<dispatch>`. Он приходит в начальных инструкциях координатора:

```markdown
ЦЕЛЬ: задача OPSOMN002-123. Вводная: ...

Dispatch: abc123xyz-def456  ← ВОТ ЭТОТ ID
```

Или можно прочитать из файла `.dispatch` в дереве задачи:

```bash
DISPATCH=$(cat .tasks/opsomn002-123/.dispatch)
scripts/gj/orchestrate.sh send-phase-complete "$DISPATCH" "understanding" "success"
```

---

## Интеграция с SendMessage

Если worker предпочитает использовать встроенную функцию `SendMessage` вместо bash:

```python
# Worker может отправить сообщение напрямую
from worker_messaging import send_phase_complete

send_phase_complete(
    phase="understanding",
    status="success",
    summary="Требования разобраны, точки входа найдены"
)
```

**Это должно быть реализовано в runtime helper'е worker'а** (например, в `client/worker_messaging.py`).

---

## Обработка ошибок в скилле

Если worker отправляет сообщение, но координатор не получает:

```markdown
## Отправка не прошла?

Если координатор не ответил в течение 30 секунд:

1. Проверьте dispatch ID: `cat .tasks/<key>/.dispatch`
2. Повторите команду:
   ```bash
   scripts/gj/orchestrate.sh send-phase-complete <dispatch> "understanding" "success"
   ```
3. Если повторилось, напишите координатору: `scripts/gj/orchestrate.sh say <dispatch> "Не могу отправить сообщение, помогите"`
```

---

## Потоки контроля

### Automatic Flow (идеальный case)

```
Worker (Understanding)
  ↓ send-phase-complete "understanding" "success"
Coordinator (получил сообщение)
  ↓ автоматически отправляет next-phase: planning
Worker (Planning)
  ↓ send-phase-complete "planning" "success"
Coordinator (автоматически → Implementation)
...
```

**Результат:** work идёт без остановок, оба занимаются своим.

---

### Blocked Flow (с блокерами)

```
Worker (Understanding)
  ↓ send-phase-complete "understanding" "partial"
  ↓ blockers: ["API не документирована"]
Coordinator (получил partial)
  ↓ логирует, НЕ переходит
  ↓ может отправить: "Запросил доступ, жди 2 часа"
Worker (ждёт ответа)
  ↓ получает ответ, ждёт или работает вокруг
  ↓ после разрешения: send-phase-complete "understanding" "success"
Coordinator (теперь success → автоматический переход)
```

---

## Чек-лист для скилла

При написании новой фазы в скилле, убедитесь:

- [ ] Описаны критерии готовности фазы
- [ ] Указана команда для завершения: `send-phase-complete <dispatch> "<phase>" "success"`
- [ ] Указана команда для partial: `send-phase-complete <dispatch> "<phase>" "partial"`
- [ ] Объяснено, когда использовать каждую
- [ ] Добавлена ссылка на `docs/worker-messaging-protocol.md`
- [ ] Примеры include dispatch ID или `$(cat .dispatch)`

---

## Связь с CLAUDE.md

В CLAUDE.md уже описано, что worker должен:

```markdown
ОГРАНИЧЕНИЯ: работать по фазам скилла gj-task-orchestration с потолками контекста.
```

WorkerMessage Protocol **расширяет** это правило, добавляя автоматизацию переходов между фазами.

---

## FAQ

### Могу ли я отправить сообщение несколько раз за фазу?

Да, каждый раз перезаписывается статус. Последнее сообщение — то, что считается финальным.

### Что если я забыл отправить сообщение?

Координатор ждёт `worker_done`. Если используется монитор фаз, он будет ждать `phase_complete`. Можете отправить сообщение позже или координатор скажет вам.

### Может ли скилл автоматически отправлять сообщения от worker'а?

Нет, worker должен явно вызвать команду. Это гарантирует, что он действительно завершил фазу.

### Как я узнаю, что монитор запущен?

Координатор скажет: "монитор запущен, вкладка ХХХ".
Дополнительно смотрите `scripts/gj/orchestrate.sh list` — там видны активные фазы.
