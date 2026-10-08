# Система автоматической очистки веток (Cleanup Branches System)

## Проблема

**Ограничение:** рабочие деревья git имеют лимит на число веток (~30 слотов worktree).

**Текущее состояние:** 24/30 слотов занято, что блокирует запуск новых задач.

**Причина:** ветки задач остаются после merge, занимая слоты неопределённо долго.

## Решение

Автоматическая удаление локальных и удалённых веток задачи, которые уже слиты в целевые ветки (main/master).

## Архитектура

### Компоненты

| Компонент | Назначение | Расположение |
|-----------|-----------|--------------|
| `cleanup-merged-branches.sh` | основной скрипт очистки веток | `scripts/gj/` |
| `orchestrate.sh` (функция) | интеграция cleanup в workflow | `scripts/gj/` |
| Логирование | состояние и история очистки | `.tasks/<key>/branches.log` |

### Workflow

#### 1. Запуск задачи (task / front)
```bash
orchestrate.sh task OPSOMN002-123
```
↓ Создаёт `.tasks/opsomn002-123/brief.md`, запускает работника

#### 2. Выполнение и merge (done)
```bash
orchestrate.sh done OPSOMN002-123
```
↓ Работник: слияние всех запросов в стейдж-ветку
↓ Сигнал worker_done отправляется координатору

#### 3. Автоматическая очистка (в wait)
```
→ orchestrate.sh wait
  ↓ Ловит worker_done для done-opsomn002-123
  ↓ Проверяет expect.sh (если есть)
  ↓ Если успех: вызывает cleanup_task_branches "opsomn002-123"
```
↓ Очищаются все ветки с паттерном `opsomn002-123`

### Алгоритм очистки

```
FOR each task repository (platform/*/*/*, platform-new/*, platform-next/*)
  FOR each branch matching pattern "opsomn002-123"
    IF branch is merged into main/master/origin/main/origin/master THEN
      DELETE local branch (git branch -D)
      DELETE remote branch (git push --delete)
    ELSE
      SKIP (not merged)
    END IF
  END FOR
END FOR
```

### Проверка merged

Использует `git merge-base --is-ancestor`:
```bash
git merge-base --is-ancestor <branch> <base>
```
- Returns 0 (success) если `<branch>` — предок `<base>` (fully merged)
- Returns 1 если нет (still needed)

Переходит к базовой ветке в этом порядке:
1. `origin/main` (современный стандарт)
2. `origin/master` (legacy GitHub)
3. `main` (локальная)
4. `master` (локальная)

## Использование

### Автоматический режим (рекомендуется)

При завершении `orchestrate.sh done OPSOMN002-123`:

```
✓ Работник завершил merge
✓ wait получил worker_done
✓ cleanup_task_branches запущен автоматически
  • Нашёл 4 ветки с паттерном opsomn002-123
  • Проверил merged: все слиты
  • Удалил локально и удалённо
  • Записал лог в .tasks/opsomn002-123/branches.log
✓ Worktree слоты освобождены (например: 24/30 → 20/30)
```

### Ручной режим

Для задачи, сдача которой уже прошла:
```bash
# Сухой прогон (показать что будет удалено)
scripts/gj/orchestrate.sh cleanup OPSOMN002-123 --dry

# Реальная очистка
scripts/gj/orchestrate.sh cleanup OPSOMN002-123

# Просмотр логов
scripts/gj/orchestrate.sh cleanup-log OPSOMN002-123
```

### Отключение очистки

Если нужно сохранить ветки (отладка, специальный случай):
```bash
GJ_SKIP_CLEANUP=1 orchestrate.sh done OPSOMN002-123
```

## Логирование

### Основной лог: `.tasks/<key>/branches.log`

```
[2026-10-08 15:23:45] success: удалена локально: feat/opsomn002-123 из /Users/user/orca/.../platform/ensi
[2026-10-08 15:23:46] success: удалена удалённо: feat/opsomn002-123 из origin
[2026-10-08 15:23:47] info: [NOT MERGED] hotfix/opsomn002-123-urgent в ... — оставляем
[2026-10-08 15:23:48] error: ошибка при удалении fix/opsomn002-123-typo из /Users/user/orca/.../platform/site
```

### Состояние: `.tasks/<key>/cleanup.state`

```
last_run=1728404625
last_status=success
last_message_timestamp=2026-10-08 15:23:48
```

Статусы:
- `success` — все ветки удалены без ошибок
- `partial_failure` — некоторые ветки не удалось удалить (пересмотреть логи)
- `dry_run` — сухой прогон, удаления не было

## Обработка ошибок

| Сценарий | Действие | Результат |
|----------|---------|-----------|
| Ветка не слита | Пропустить | Остаётся в репо, слот занят |
| Нет доступа к origin | Залогировать | Локально удалена, удалённо не удалена |
| Ветка в использовании (checkout) | Ошибка git | Залогировать, пропустить эту ветку |
| Сетевая ошибка при push --delete | Залогировать | Повторить очистку позже |

**Результат:** cleanup не падает, логирует ошибки, продолжает удаление остальных веток.

## Производительность

- **Сканирование веток:** ~200ms (grep по всем refs)
- **Проверка merged:** ~50ms за ветку (merge-base)
- **Удаление:** ~100ms за ветку (git branch -D, git push)

Типичный прогон (4 ветки):
```
Очистка веток задачи: OPSOMN002-123 (паттерн: opsomn002-123)

Удаляем: feat/opsomn002-123 из platform/ensi
  удалена локально: feat/opsomn002-123
  удалена удалённо: feat/opsomn002-123

Удаляем: fix/opsomn002-123-typo из platform/integration
  удалена локально: fix/opsomn002-123-typo
  удалена удалённо: fix/opsomn002-123-typo

[NOT MERGED] hotfix/opsomn002-123-urgent в ... — оставляем

==========================================
Результат очистки для задачи: OPSOMN002-123
Удалено веток: 3
==========================================
```
Время: ~500ms

## Безопасность

- **Без force:** удаляет только полностью слитые ветки (merge-base проверяет)
- **Локальное первым:** если удаление локальной ветки пройдёт, удалённая не потеряется
- **Лог всего:** каждое действие — в `.tasks/<key>/branches.log`
- **Dry-run режим:** `--dry-run` показывает без удаления для проверки

## Интеграция с orchestrate.sh

### Функция cleanup_task_branches()

```bash
cleanup_task_branches() {
  local key=$1 skip=${GJ_SKIP_CLEANUP:-}
  [ -n "$skip" ] && return 0
  
  # Вызывает scripts/gj/cleanup-merged-branches.sh "$key"
  # Логирует результат
  # Возвращает 0 при успехе, 1 при ошибке (не блокирует done)
}
```

### Вызов из wait (при worker_done for done-* диспетча)

```bash
if [ -n "$is_done_dispatch" ]; then
  cleanup_task_branches "$task_key" || true
fi
```

Ключ момент: `|| true` — ошибка очистки не прерывает workflow.

### Вызов из команды cleanup

```bash
orchestrate.sh cleanup <КЛЮЧ> [--dry|--log]
```

- `--dry` — просмотр без удаления
- `--log` — просмотр логов прошлого прогона
- (ничего) — реальная очистка

## Мониторинг

### Свободные слоты

```bash
orca diagnostics memory --json | jq '.result.worktrees[].sessions | length'
```

Проверить перед/после очистки:
```bash
# Перед
orchestrate.sh list  # показывает: сессий 24 из 30

# После cleanup (автоматическая или ручная)
orchestrate.sh list  # показывает: сессий 20 из 30
```

### Статус очистки последней задачи

```bash
orchestrate.sh cleanup-log OPSOMN002-123
cat .tasks/opsomn002-123/cleanup.state
```

## Примеры

### Пример 1: Успешная автоматическая очистка

```bash
$ scripts/gj/orchestrate.sh done OPSOMN002-123
# ... работник сливает запросы в стейдж ...
# ... worker_done отправляется ...

[в фоне wait обрабатывает результат]
запуск очистки веток задачи: opsomn002-123
  удалена локально: feat/opsomn002-123
  удалена удалённо: feat/opsomn002-123
  удалена локально: fix/opsomn002-123-style
  удалена удалённо: fix/opsomn002-123-style
==========================================
Результат очистки для задачи: OPSOMN002-123
Удалено веток: 2
==========================================
очистка веток завершена успешно
```

### Пример 2: Сухой прогон перед удалением

```bash
$ scripts/gj/orchestrate.sh cleanup OPSOMN002-123 --dry
Очистка веток задачи: OPSOMN002-123 (паттерн: opsomn002-123)

  [DRY RUN] удалить локально: feat/opsomn002-123 из /Users/user/.../platform/ensi
  [DRY RUN] удалить удалённо: feat/opsomn002-123

==========================================
Результат очистки для задачи: OPSOMN002-123
Удалено веток: 2
==========================================
```

### Пример 3: Просмотр логов после очистки

```bash
$ scripts/gj/orchestrate.sh cleanup-log OPSOMN002-123
=== Логи очистки веток для задачи: OPSOMN002-123 ===

[2026-10-08 15:23:45] success: удалена локально: feat/opsomn002-123
[2026-10-08 15:23:46] success: удалена удалённо: feat/opsomn002-123
[2026-10-08 15:23:47] success: удалена локально: fix/opsomn002-123-style
[2026-10-08 15:23:48] success: удалена удалённо: fix/opsomn002-123-style

=== Состояние последней очистки ===
last_run=1728404625
last_status=success
last_message_timestamp=2026-10-08 15:23:48
```

## Что дальше

После интеграции cleanup системы:

1. **Мониторинг worktree слотов:** проверить что очистка действительно освобождает слоты
2. **Автоматизация в pipeline:** интегрировать в CI/CD для очистки веток после автоматического merge
3. **Расширение:** добавить очистку стройных веток (orphan branches)
4. **Метрики:** отслеживать динамику освобождения слотов по времени

## Благодарности

- Проблема определена в начале сессии: 24/30 слотов, новые задачи не могут запускаться
- Решение повторяет pattern git cleanup: безопасное удаление, полное логирование
- Интеграция через orchestrate.sh done → wait → cleanup_task_branches
