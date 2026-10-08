# Руководство Worker'а по WorkerMessage Protocol

Это руководство для worker'а, который получил инструкции от координатора запускать фазы и отправлять сообщения о их завершении.

## Как это работает

1. **Координатор** запускает тебя с инструкциями по фазам
2. **Ты** работаешь по каждой фазе (understanding → planning → implementation → ...)
3. **Ты** отправляешь сообщение о завершении фазы (`send-phase-complete`)
4. **Координатор** автоматически получает сообщение и запускает next фазу

## Где брать dispatch ID

В инструкции координатора будет написано:

```
Dispatch: abc123xyz-def456
```

Или прочитать из файла:

```bash
DISPATCH=$(cat .tasks/<ключ>/.dispatch)
echo "Мой dispatch: $DISPATCH"
```

## Команда для отправки сообщения

После завершения каждой фазы **отправляй сообщение**:

```bash
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "<phase>" "<status>"
```

### Параметры

- `<dispatch>` — твой dispatch ID (например, `abc123xyz-def456`)
- `<phase>` — название текущей фазы:
  - `understanding` (анализ)
  - `planning` (планирование)
  - `implementation` (кодирование)
  - `testing` (тестирование)
  - `verification` (финальная проверка)
- `<status>` — как прошла фаза:
  - `success` (всё прошло успешно → переходим в next phase)
  - `partial` (прошло частично → требуется вмешательство)
  - `failed` (критический отказ → требуется помощь)

## Примеры

### ✓ Успешное завершение фазы

```bash
# После анализа требований (phase 1)
scripts/gj/orchestrate.sh send-phase-complete abc123xyz-def456 "understanding" "success"

# Output:
# фаза understanding отправлена (→ planning)
```

**Результат:** координатор получает сообщение и отправляет тебе указание начать Planning.

### ⚠ Частичное завершение (требует помощи)

```bash
# Если в фазе осталось что-то не ясно
scripts/gj/orchestrate.sh send-phase-complete abc123xyz-def456 "understanding" "partial"

# Output:
# фаза understanding отправлена (→ understanding)
```

**Результат:** координатор видит, что не всё готово. Он может:
- Отправить тебе вопрос: `answer <dispatch> "какой конкретно блокер?"`
- Помочь: `say <dispatch> "Вот ссылка на документацию..."`
- Вмешаться сам

После разрешения блокера ты отправляешь `success`:

```bash
scripts/gj/orchestrate.sh send-phase-complete abc123xyz-def456 "understanding" "success"
# Теперь → автоматический переход в planning
```

### ✗ Критический отказ

```bash
# Если нашёл неразрешимую проблему
scripts/gj/orchestrate.sh send-phase-complete abc123xyz-def456 "implementation" "failed"

# Output:
# фаза implementation отправлена (→ implementation)
```

**Результат:** координатор видит отказ и не переходит на next фазу. Он вмешивается:

```bash
# Координатор:
scripts/gj/orchestrate.sh say <dispatch> "Какая ошибка? Могу помочь"

# Или:
scripts/gj/orchestrate.sh answer <dispatch> "SQL синтаксис: замени VARCHAR на TEXT в line 42"
```

Ты исправляешь и отправляешь success.

## Пошаговый workflow

### Phase 1: Understanding (анализ)

1. Прочитай задачу и цель в вводной
2. Найди все затронутые файлы через `grep` или `codegraph`
3. Трассируй вызовы, поймай workflow
4. Найди edge cases и ограничения
5. **Отправь сообщение:**
   ```bash
   scripts/gj/orchestrate.sh send-phase-complete <dispatch> "understanding" "success"
   ```

### Phase 2: Planning (планирование)

1. Получи инструкцию от координатора о next phase
2. Разбери задачу на шаги
3. Определи какие файлы менять и где
4. Составь таблицу retry-safe-writes если нужно (для BDD-изменений)
5. **Отправь сообщение:**
   ```bash
   scripts/gj/orchestrate.sh send-phase-complete <dispatch> "planning" "success"
   ```

### Phase 3: Implementation (кодирование)

1. Пройди по плану
2. Делай правки файл за файлом
3. Коммитай после каждого логичного блока
4. Запусти phpstan/tests локально
5. **Отправь сообщение:**
   ```bash
   scripts/gj/orchestrate.sh send-phase-complete <dispatch> "implementation" "success"
   ```

### Phase 4: Testing (тестирование)

1. Запусти полные тесты всех затронутых путей
2. Проверь edge cases (null, пусто, граница)
3. Посмотри логи на наличие новых warning'ов
4. Если баги → отправь `failed` и исправь
5. **Отправь сообщение:**
   ```bash
   scripts/gj/orchestrate.sh send-phase-complete <dispatch> "testing" "success"
   ```

### Phase 5: Verification (финальная проверка)

1. Прочитай чек-листы в скилле
2. Убедись что все пункты пройдены
3. Если есть expect.sh → проверь что она проходит
4. Обнови вводную (что сделано, что осталось)
5. **Отправь сообщение:**
   ```bash
   scripts/gj/orchestrate.sh send-phase-complete <dispatch> "verification" "success"
   ```

**Результат:** координатор видит `verification success` и может начинать сдачу!

## Если что-то не так

### Координатор не отвечает

Если больше 15 минут нет ответа → координатор может быть занят.

Попробуй:
```bash
# Отправить вопрос
scripts/gj/orchestrate.sh say <dispatch> "Жду ответа, в чём причина partial status?"

# Или просто жди — координатор обязательно ответит
```

### Не знаешь что делать

Задай вопрос через `ask`:
```bash
# В своём терминале (из дерева задачи)
ask --timeout-ms 110000 "Какой статус отправить: success или partial? В понимании разобрались, но API не документирована"

# Координатор получит вопрос и ответит
```

### Не помнишь dispatch ID

```bash
DISPATCH=$(cat .tasks/<ключ>/.dispatch)
echo "dispatch=$DISPATCH"
```

Или посмотри в логах текущей session'и в вкладке terminal.

## Команды которые тебе нужны

| Команда | Что делает | Когда |
|---|---|---|
| `send-phase-complete <d> <p> success` | Завершить фазу, переходим в next | Когда всё готово |
| `send-phase-complete <d> <p> partial` | Частичное завершение, требуется ввод | Есть вопросы или блокеры |
| `send-phase-complete <d> <p> failed` | Критический отказ, нужна помощь | Баг или невозможно продолжить |
| `scripts/gj/orchestrate.sh say <d> "…"` | Отправить сообщение координатору | Нужно сообщить что-то срочное |
| `ask --timeout-ms 110000 "вопрос"` | Задать вопрос и ждать ответа | Когда не знаешь что делать |

## Советы

1. **Отправляй сообщение сразу** после завершения фазы, не ждите
2. **Будь честен со статусом**: если partial — пиши partial, не success
3. **Логируй блокеры** в сообщении, иначе координатор не поймёт что не так
4. **Читай инструкции скилла** перед каждой фазой — там все критерии
5. **Не жди координатора** — работай следующей фазе, если уже знаешь что делать

## Часто задаваемые вопросы

### Что если я отправлю success, но потом найду ошибку?

Отправь `failed`:
```bash
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "implementation" "failed"
```

Координатор не будет переходить дальше. Ты исправляешь ошибку и отправляешь success.

### Можно ли пропустить фазу?

Нет, фазы идут линейно. Пропуск только по явному указанию координатора.

### Как узнать, что координатор получил сообщение?

Координатор отправляет тебе указание о next phase. Если молчит → возможно не получил.

Повтори команду:
```bash
scripts/gj/orchestrate.sh send-phase-complete <dispatch> "understanding" "success"
```

### Что если я запутаюсь в фазах?

Посмотри текущее состояние:
```bash
cat .tasks/<ключ>/.phase
```

Или спроси у координатора:
```bash
scripts/gj/orchestrate.sh say <dispatch> "Какая фаза сейчас? Запутался"
```

---

**Главное:** отправляй сообщение о завершении фазы → координатор автоматически запускает next → работа идёт без остановок.

**Успехов!** 🚀
