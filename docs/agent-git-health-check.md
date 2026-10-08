# Agent Git Health Check Integration

Скрипт `scripts/gj/git-health-check.sh` проверяет и исправляет состояние git-репозитория в начале работы агента. Это критично, потому что:

- **Platform-клоны shallow** (depth 1) → merge-base/ahead-behind/cherry-pick дают неверные результаты до `git fetch --unshallow`
- **Refs могут быть устаревшими** → лучше проверить перед операциями над ветками
- **Origin может быть не настроен** → fail fast вместо молчаливых ошибок

## Использование

### 1. Прямой вызов в Bash-команде агента

Самый надёжный способ — добавить проверку в начало скрипта, который агент выполняет:

```bash
#!/bin/bash
# Начало скрипта агента
"$CLAUDE_PROJECT_DIR/scripts/gj/git-health-check.sh" --unshallow --verbose
# … дальше логика агента
```

### 2. Вызов из агентского frontmatter (для агентов в `.claude/agents/`)

В файле агента `.claude/agents/my-agent.md` добавить блок инициализации:

```markdown
---
name: my-agent
description: Агент для работы с X
instructions: |
  Перед любой работой выполни проверку git:
  
  ```bash
  "$CLAUDE_PROJECT_DIR/scripts/gj/git-health-check.sh" --unshallow --verbose
  ```
  
  Если скрипт завершился с ошибкой, не продолжай.
---
```

### 3. Hook-based автоматизация в .claude/settings.json

Для автоматического запуска перед каждым агентским промптом:

```bash
scripts/gj/install-hooks.sh
```

Это добавит в `.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "[ -f \"$CLAUDE_PROJECT_DIR/scripts/gj/git-health-check.sh\" ] && bash \"$CLAUDE_PROJECT_DIR/scripts/gj/git-health-check.sh\" --unshallow --verbose || true",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

## Флаги

| Флаг | Описание |
|------|---------|
| `--unshallow` / `--fix` | Выполнить `git fetch --unshallow` если репо shallow |
| `--verbose` | Выводить отчёт о всех проверках (не только ошибки) |
| `--help` | Показать справку (не реализовано, просмотреть исходник) |

## Коды выхода

| Код | Значение |
|-----|----------|
| `0` | Репозиторий здоров (или успешно исправлен) |
| `1` | Ошибка: нет .git, нет origin, или unshallow не удалась |
| `2` | Ошибка парсинга аргументов |

## Примеры интеграции

### Пример 1: Агент, который работает с git-history

```bash
#!/bin/bash
set -euo pipefail
PROJ_DIR="${CLAUDE_PROJECT_DIR:-.}"

# Здоровье репо — критично для merge-base
"$PROJ_DIR/scripts/gj/git-health-check.sh" --unshallow || exit 1

# Теперь можно безопасно использовать git
git merge-base --is-ancestor main HEAD && echo "main в истории" || echo "new branch"
```

### Пример 2: Агент в подкаталоге (platform/ensi/)

```bash
#!/bin/bash
set -euo pipefail
PROJ_DIR="${CLAUDE_PROJECT_DIR:-.}"

# Перейти в ENSI, проверить git
cd "$PROJ_DIR/platform/ensi" || exit 1
"$PROJ_DIR/scripts/gj/git-health-check.sh" --unshallow --verbose

# Дальше работа с ENSI-репо
git log --oneline -5
```

### Пример 3: Проверка без unshallow (только диагностика)

```bash
# Просто проверить, есть ли проблемы, без исправления
if ! "$PROJ_DIR/scripts/gj/git-health-check.sh" --verbose; then
  echo "репо нездоров, требует ручного вмешательства" >&2
  exit 1
fi
```

## Когда использовать

### Используй `--unshallow`

- Агент работает с `git merge-base`, `git cherry-pick`, `git rebase`
- Агент определяет ahead/behind относительно main
- Агент строит граф веток или проверяет историю
- Агент в `platform/*/` (shallow по умолчанию)

### Используй `--verbose`

- Дебаг git-проблем
- Первый запуск агента (убедиться, что setup корректен)
- Агент работает в незнакомом окружении

### Используй обычный вызов (без флагов)

- Просто убедиться, что это git-репо и origin есть
- Быстрая проверка перед критичной операцией
- В очень чувствительных к времени скриптах (но лучше unshallow один раз)

## Часто встречающиеся ошибки

### "нет токена ~/.config/gj/gitlab_pat"

Это не ошибка этого скрипта — это от других утилит (например, `branch-registry.sh`).

### ".git directory: FAIL"

Репозиторий не инициализирован или вы находитесь вне git-дерева. Проверьте `pwd` и `git status`.

### "origin remote: FAIL"

Удалённый сервер не настроен. Проверьте `git remote -v` и добавьте `origin`:

```bash
git remote add origin <url>
git fetch origin
```

### "unshallow: FAIL"

Возможные причины:
1. **Сеть** — проверьте VPN и интернет
2. **Shallow информация нарушена** — try `git remote add-url origin <url>` и повторить
3. **Диск переполнен** — проверьте свободное место

## Интеграция в агентов Orca

Если Orca orchestrate.sh запускает агентов, добавить в начало каждого агента:

```bash
# ~/.claude/agents/my-agent.md
---
name: my-agent
description: ...
---

Перед началом выполни:
\`\`\`bash
"$CLAUDE_PROJECT_DIR/scripts/gj/git-health-check.sh" --unshallow --verbose
\`\`\`
```

Или если агент вызывает Bash-скрипты, положить проверку туда:

```bash
# scripts/my-agent/main.sh
#!/bin/bash
set -euo pipefail
PROJ_DIR="${CLAUDE_PROJECT_DIR:-.}"

# Инициализация
"$PROJ_DIR/scripts/gj/git-health-check.sh" --unshallow || exit $?

# Дальше всё остальное
```

## Проверка, что работает

```bash
# Проверить скрипт локально
cd /Users/user/orca/workspaces/development-platform/betta

# Обычная проверка (молчит если OK)
scripts/gj/git-health-check.sh

# С отчётом
scripts/gj/git-health-check.sh --verbose

# С unshallow (может быть медленно на первый раз)
scripts/gj/git-health-check.sh --unshallow --verbose

# В подкаталоге (например, в submodule или added repo)
scripts/gj/git-health-check.sh platform/ensi
scripts/gj/git-health-check.sh --unshallow platform/starfish24/core/go/logistics
```

## Переменные окружения

Скрипт не требует переменных, но опирается на:

- `CLAUDE_PROJECT_DIR` — корень workspace (если не указан, используется текущая директория)
- `PWD` — текущая директория для cd

Переопредели `CLAUDE_PROJECT_DIR`, если скрипт запускается из другого контекста:

```bash
CLAUDE_PROJECT_DIR=/path/to/gj-ecommerce scripts/gj/git-health-check.sh --verbose
```
