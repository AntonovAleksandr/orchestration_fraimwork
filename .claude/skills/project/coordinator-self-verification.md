# Coordinator Self-Verification Skill

**Purpose:** Методы для координирующего агента и других агентов при делегировании задач: проверка целостности ссылок, определение принадлежности пути репозиторию, разрешение веток в коммиты.

**Когда:** Перед отправкой задачи субагенту, при сборке контекста из нескольких файлов, при проверке, что путь указан правильно.

---

## Методы

### `verify_url(url, timeout=10)`

Проверить, что URL доступен без ошибок 403/404/500.

**Параметры:**
- `url` (str) — полная ссылка: claude.ai artifact, GitLab MR, файл на GitHub, SSH:
  - `https://claude.ai/artifacts/UUID` → статус 200, заголовок `X-Robots-Tag: index`
  - `https://gitlab.gj.corp/project/-/merge_requests/123` → статус 200
  - `https://github.com/anthropic-ai/anthropic-sdk-python` → статус 200
- `timeout` (int) — сек перед отказом

**Возвращает:**
```json
{
  "ok": true|false,
  "status": 200|403|404|500|"timeout"|"dns_error",
  "url": "исходная ссылка",
  "error": "если ok=false: текст ошибки",
  "redirected_to": "если было перенаправление",
  "headers": {
    "content-type": "...",
    "x-frame-options": "..."
  }
}
```

**Примеры:**

```python
# Artifact в claude.ai
verify_url("https://claude.ai/artifacts/abc123")
# ➜ {"ok": true, "status": 200, "url": "..."}

# GitLab MR — 403 из-за приватного проекта
verify_url("https://gitlab.gj.corp/ensi/private/-/merge_requests/5000")
# ➜ {"ok": false, "status": 403, "error": "Forbidden"}

# Гео-блок на 10.810 прокси
verify_url("https://vpn.gj.corp/internal/docs")
# ➜ {"ok": false, "status": "timeout", "error": "VPN proxy timeout"}

# Перенаправление
verify_url("https://bit.ly/gj-docs")
# ➜ {"ok": true, "status": 200, "redirected_to": "https://confluence.gj.corp/...", "url": "..."}
```

---

### `identify_repo(path)`

Определить, какому Git-репозиторию принадлежит файл или папка в `$WORKSPACE`.

**Параметры:**
- `path` (str) — абсолютный путь в рабочей директории:
  - `/Users/user/orca/workspaces/development-platform/betta/platform/ensi/apps/catalog/pim/src/...`
  - `/Users/user/orca/workspaces/development-platform/betta/platform/starfish24/core/Order/...`
  - `./relative/path` → преобразуется в абсолют

**Возвращает:**
```json
{
  "found": true|false,
  "repo": {
    "name": "ensi",
    "remote_url": "git@gitlab.gj.corp:ensi/ensi.git",
    "local_path": "/Users/user/orca/workspaces/development-platform/betta/platform/ensi",
    "default_branch": "master",
    "shallow": true|false
  },
  "relative_path_in_repo": "apps/catalog/pim/src/...",
  "git_root": "/Users/user/orca/workspaces/development-platform/betta/platform/ensi",
  "error": "если found=false"
}
```

**Примеры:**

```python
# Файл в ENSI репо
identify_repo("/Users/user/orca/workspaces/development-platform/betta/platform/ensi/apps/catalog/pim/src/Domain/Product.php")
# ➜ {
#   "found": true,
#   "repo": {
#     "name": "ensi",
#     "remote_url": "git@gitlab.gj.corp:ensi/ensi.git",
#     "default_branch": "master",
#     "shallow": true
#   },
#   "relative_path_in_repo": "apps/catalog/pim/src/Domain/Product.php",
#   "git_root": "/Users/user/orca/workspaces/development-platform/betta/platform/ensi"
# }

# Файл в OMS logistics Go-репо
identify_repo("/Users/user/orca/workspaces/development-platform/betta/platform/starfish24/core/go/logistics/internal/app/app.go")
# ➜ {
#   "found": true,
#   "repo": {
#     "name": "logistics",
#     "remote_url": "git@gitlab.gj.corp:oms/logistics.git",
#     "default_branch": "main",
#     "shallow": true
#   },
#   "relative_path_in_repo": "internal/app/app.go",
#   "git_root": "/Users/user/orca/workspaces/development-platform/betta/platform/starfish24/core/go/logistics"
# }

# Путь вне репо (например, в платформе-новой, которая ignored)
identify_repo("/Users/user/orca/workspaces/development-platform/betta/platform-new/checkout/main.go")
# ➜ {
#   "found": false,
#   "error": "path is in ignored directory platform-new; not a tracked git repo"
# }

# Путь не существует
identify_repo("/Users/user/orca/nonexistent/path")
# ➜ {
#   "found": false,
#   "error": "path does not exist"
# }
```

---

### `resolve_ref(ref, repo_name=None)`

Разрешить ветку, тег или шорт-SHA в полный коммит-хеш и метаданные.

**Параметры:**
- `ref` (str) — ветка, тег или коммит:
  - `main`, `master`, `develop`, `release/production`
  - `v1.2.3` (тег)
  - `abc123` или `abc123def456...` (SHA)
- `repo_name` (str, опц.) — конкретный репо (если не указан, определяется от cwd)

**Возвращает:**
```json
{
  "resolved": true|false,
  "input": "исходная ref",
  "repo": "имя репо",
  "type": "branch"|"tag"|"commit",
  "commit_hash": "полный SHA",
  "commit_short": "7 символов",
  "commit_message": "первая строка сообщения коммита",
  "committer": "Иван Петров",
  "date": "2026-10-08T14:23:01Z",
  "remote_tracking": "origin/main",  # если это отслеживаемая ветка
  "error": "если resolved=false"
}
```

**Примеры:**

```python
# Ветка
resolve_ref("feat/review-defect-skills", repo_name="workspace")
# ➜ {
#   "resolved": true,
#   "input": "feat/review-defect-skills",
#   "repo": "workspace",
#   "type": "branch",
#   "commit_hash": "306e8d2f7a9b1c4e5d6f7g8h9i0j1k2l",
#   "commit_short": "306e8d2",
#   "commit_message": "feat(gloriaots): create 8 skills for Gloria OTS platform development",
#   "committer": "Antonov Aleksandr (Антонов Александр)",
#   "date": "2026-10-07T18:45:00Z",
#   "remote_tracking": "origin/feat/review-defect-skills"
# }

# Тег
resolve_ref("pim-client-v1.2.3", repo_name="ensi")
# ➜ {
#   "resolved": true,
#   "input": "pim-client-v1.2.3",
#   "repo": "ensi",
#   "type": "tag",
#   "commit_hash": "f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4",
#   "commit_short": "f9e8d7c",
#   "commit_message": "release: pim-client v1.2.3",
#   "committer": "CI/CD Pipeline",
#   "date": "2026-09-15T10:00:00Z"
# }

# Короткий SHA
resolve_ref("abc123", repo_name="integration")
# ➜ {
#   "resolved": true,
#   "input": "abc123",
#   "repo": "integration",
#   "type": "commit",
#   "commit_hash": "abc123def456abc123def456abc123def456abc1",
#   "commit_short": "abc123d",
#   "commit_message": "fix(baskets): correct init_qty calculation",
#   "committer": "Maria Sokolov",
#   "date": "2026-10-05T09:32:00Z"
# }

# Ветка, которой нет (может быть удалена или никогда не существовала)
resolve_ref("develop", repo_name="integration")
# ➜ {
#   "resolved": false,
#   "input": "develop",
#   "repo": "integration",
#   "error": "ref not found in repository"
# }

# Shallow clone — коммит может быть вне графа
resolve_ref("abc123", repo_name="ensi")
# ➜ {
#   "resolved": false,
#   "input": "abc123",
#   "repo": "ensi",
#   "error": "commit not found (repo is shallow; run 'git fetch --unshallow' if needed)"
# }
```

---

## Использование в Coordinator Prompts

### Пример 1: Перед делегированием задачи субагенту

**Coordinator prompt:**
```
Перед отправкой задачи subagent-1, проверить целостность контекста:

1. verify_url("https://gitlab.gj.corp/ensi/ensi/-/merge_requests/5432")
2. identify_repo("/Users/user/orca/workspaces/development-platform/betta/platform/ensi/apps/catalog/pim/src/Domain")
3. resolve_ref("master", repo_name="ensi")

Если какой-то метод вернёт ошибку, сообщить пользователю и не запускать задачу.
Иначе отправить subagent-1 с контекстом выше.
```

### Пример 2: Сборка контекста из нескольких репо

**Coordinator prompt:**
```
Собрать контекст для кроссплатформной задачи (site + integration + ensi):

1. resolve_ref("release/production", repo_name="site")
2. resolve_ref("dev", repo_name="integration")
3. resolve_ref("master", repo_name="ensi")

Проверить, что все три коммита доступны (не shallow). Если ensi shallow:
- Предложить разработчику: git fetch --unshallow platform/ensi
- Не продолжать.

Иначе отправить site-engineer и integration-engineer одновременно 
с явными commit_hash для каждого.
```

### Пример 3: Проверка консистентности путей в artifact

**Coordinator prompt:**
```
Artifact содержит пути в 5 файлов:
- /Users/user/.../platform/ensi/apps/catalog/pim/src/X.php
- /Users/user/.../platform/starfish24/core/Order/Y.java
- /Users/user/.../platform/integration/www/Z.php
- /Users/user/.../CLAUDE.md
- /Users/user/.../platform/nonexistent/W.txt

Для каждого пути вызвать identify_repo():
- Если found=false, добавить в ошибки
- Если found=true, собрать список репо: [ensi, Order, integration]

Отправить субагентам только пути из найденных репо.
```

### Пример 4: Миграция на unshallow

**Coordinator prompt:**
```
Задача требует cherry-pick между ветками в ENSI.
Но clone shallow (глубина 1).

Действия:
1. resolve_ref("CLD-1234", repo_name="ensi")
   - Если error содержит "shallow", то:
   2. Вызвать bash: cd $ENSI_ROOT && git fetch --unshallow
   3. Повторить resolve_ref()

Только после успеха запустить cherry-pick-handler.
```

### Пример 5: Валидация artifact-ссылок в промпте

**Coordinator prompt:**
```
User передал artifact URL: https://claude.ai/artifacts/abc-123-def

Перед добавлением в контекст:
1. verify_url("https://claude.ai/artifacts/abc-123-def")

Если ok=false:
- Log: "Artifact недоступен (статус {status})"
- Попросить user проверить ссылку или повторить позже

Если ok=true:
- Добавить artifact в контекст
- Продолжить
```

---

## Интеграция с Bash / Git

Методы опираются на локальные команды:

```bash
# verify_url() использует:
curl -sI --connect-timeout 10 "$url"

# identify_repo() использует:
git -C "$path" rev-parse --show-toplevel
git -C "$path" config --get remote.origin.url
git -C "$path" rev-parse --abbrev-ref HEAD
git rev-parse --is-shallow-repository

# resolve_ref() использует:
git -C "$repo_root" rev-parse "$ref"
git -C "$repo_root" rev-parse --short "$ref"
git -C "$repo_root" log -1 --format='%B' "$ref"
git -C "$repo_root" log -1 --format='%an' "$ref"
git -C "$repo_root" log -1 --format='%aI' "$ref"
git -C "$repo_root" symbolic-ref -q --short HEAD
```

Все команды запускаются локально; никаких API-запросов к GitLab/GitHub (кроме `verify_url` для проверки доступности).

---

## Обработка ошибок

### Shallow clone — распространённая ошибка

**Сценарий:**
```
resolve_ref("abc123", repo_name="ensi")
# ➜ {"resolved": false, "error": "commit not found (repo is shallow...)"}
```

**Действие в Coordinator:**
```python
if "shallow" in result["error"]:
    print("⚠️  Репо shallow; предложить разработчику:")
    print(f"  cd {git_root}")
    print("  git fetch --unshallow")
    print("Затем повторить запрос.")
    skip_task = True
```

### URL недоступна из-за VPN

**Сценарий:**
```
verify_url("https://gitlab.gj.corp/private/repo")
# ➜ {"ok": false, "status": "timeout", "error": "VPN proxy timeout"}
```

**Действие в Coordinator:**
```python
if result["status"] == "timeout" and "gj.corp" in result["url"]:
    print("❌ GitLab недоступен: проверить VPN подключение")
    skip_task = True
```

### Путь не в отслеживаемом репо

**Сценарий:**
```
identify_repo("/Users/user/orca/workspaces/development-platform/betta/platform-new/checkout/main.go")
# ➜ {"found": false, "error": "path is in ignored directory platform-new..."}
```

**Действие в Coordinator:**
```python
if "ignored" in result["error"]:
    print("⚠️  Путь находится в ignored directory")
    print("Локального клона нет. Использовать GitLab MCP для чтения?")
    use_mcp = True
```

---

## Примеры в контексте Coordinator

### Полный цикл: Проверка → Делегирование

```python
# Задача: изменить контракт API в ENSI и обновить клиента в Integration

paths = [
    "/Users/user/.../platform/ensi/apps/connectors/webapi-connector/spec.yaml",
    "/Users/user/.../platform/integration/www/app/Clients/EnsiClient.php"
]

repos = {}
for path in paths:
    result = identify_repo(path)
    if not result["found"]:
        print(f"❌ {path} не в репо: {result['error']}")
        exit(1)
    repos[result["repo"]["name"]] = result

# Все пути в порядке, теперь разрешить ветки
branches = {}
for repo_name in repos.keys():
    default_branch = repos[repo_name]["repo"]["default_branch"]
    result = resolve_ref(default_branch, repo_name=repo_name)
    if not result["resolved"]:
        print(f"❌ Не могу разрешить {default_branch} в {repo_name}: {result['error']}")
        exit(1)
    branches[repo_name] = result["commit_hash"]

# Всё хорошо — отправить субагентам с явными коммитами
print(f"✓ ENSI на {branches['ensi'][:7]} ({default_branch})")
print(f"✓ Integration на {branches['integration'][:7]} ({default_branch})")

# Delegated task context
subagent_context = {
    "ensi_commit": branches["ensi"],
    "integration_commit": branches["integration"],
    "files": paths
}
```

---

## Заметки для использования

1. **Абсолютные пути:** методы всегда возвращают абсолютные пути. Если передан относительный путь, его преобразуют во время выполнения.

2. **Кэширование:** Coordinator может кэшировать результаты `resolve_ref()` в пределах сессии, если не ожидается изменение веток между вызовами.

3. **GitLab MCP vs локальный git:** `verify_url()` проверяет доступность (для artifact/публичных URL), а `resolve_ref()` работает только с локально клонированными репо.

4. **Нестандартные default-branches:** Site (`release/production`), OMS (много фич-веток). Координатор должен явно передавать нужную ветку в `resolve_ref()`.

5. **Ошибка статуса vs ошибка безопасности:** `verify_url()` на 403/404 вернёт `ok=false`, но это не всегда ошибка (репо может быть приватное). Координатор должен различать по `status` коду.
