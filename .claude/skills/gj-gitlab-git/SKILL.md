---
name: gj-gitlab-git
description: Use for git write-ops against Gloria Jeans GitLab (gitlab.gloria.aaanet.ru) — fetch/push, creating branches, opening MRs, and managing the PAT. Covers the file-based credential helper, safe token handling (never echo it), token validity checks, the "invalid token → open the file myself + ask user to replace" flow, and clean branch+MR creation via API. Triggers on "запушь", "открой MR", "git push не проходит", "авторизуйся в gitlab", "поменяй токен", auth 401 from gitlab.gloria.aaanet.ru.
---

# GJ GitLab — git auth & write-ops

Локальный `git fetch/push` к `gitlab.gloria.aaanet.ru` требует PAT: в osxkeychain gitlab-кред НЕ хранится, поэтому без настройки git падает с `could not read Username ... terminal prompts disabled`. Buddy MCP (`mcp__buddy-mcp__gitlab_*`) — **read-only** (MR/commits/файлы читать), для записи (push, создание MR) — этот механизм. См. также [[gitlab-api-write-access]].

## Токен — правила безопасности (ВАЖНО)

- Токен живёт **только** в `~/.config/gj/gitlab_pat` (chmod 600, вне репо, не трекается).
- **Никогда** не выводить токен: не `cat` в видимую команду, не `echo`, не в git-конфиг, не в транскрипт. Подставлять **только** через `$(cat ~/.config/gj/gitlab_pat)` внутри команды.
- Helper `~/.config/gj/gitlab-cred.sh` токена не содержит — читает файл в момент запроса git.
- Диагностику файла делать **без вывода содержимого** (`wc -c`, `file`, `grep -q`), не `head`/`cat` самого токена.

## Сеть (проверено 2026-07-21)

- Хост резолвится сам: `gitlab.gloria.aaanet.ru → 10.61.64.83` (`dscacheutil -q host -a name ...`). `/etc/hosts` не нужен.
- И прямой путь, и через `HTTPS_PROXY=http://127.0.0.1:10810` достижимы (без токена → 401). 502 сейчас не воспроизводится.
- Если curl вдруг даёт 502/висит: `curl -4 --noproxy '*' --resolve gitlab.gloria.aaanet.ru:443:10.61.64.83 ...`. macOS: нет `timeout`, `-4` против IPv6-зависания.
- Если git-push начнёт 502-ить через прокси: `git config --global "http.https://gitlab.gloria.aaanet.ru/.proxy" ""`.

## Одноразовая настройка helper (если ещё нет)

Проверить: `git config --global --get-all "credential.https://gitlab.gloria.aaanet.ru.helper"`. Если пусто — создать:

```bash
DIR="$HOME/.config/gj"; mkdir -p "$DIR"; chmod 700 "$DIR"
[ -f "$DIR/gitlab_pat" ] || : > "$DIR/gitlab_pat"; chmod 600 "$DIR/gitlab_pat"
cat > "$DIR/gitlab-cred.sh" <<'EOF'
#!/bin/sh
# GJ GitLab credential helper — reads PAT from a 600 file. No secret stored here.
[ "$1" = "get" ] || exit 0
TOKEN_FILE="${GJ_GITLAB_PAT_FILE:-$HOME/.config/gj/gitlab_pat}"
[ -s "$TOKEN_FILE" ] || exit 0
printf 'username=oauth2\n'
printf 'password=%s\n' "$(cat "$TOKEN_FILE")"
EOF
chmod 700 "$DIR/gitlab-cred.sh"
# для хоста использовать ТОЛЬКО наш helper (сброс унаследованного osxkeychain + добавление)
git config --global "credential.https://gitlab.gloria.aaanet.ru.helper" ""
git config --global --add "credential.https://gitlab.gloria.aaanet.ru.helper" "$DIR/gitlab-cred.sh"
```

`username=oauth2` + PAT как password — GitLab это принимает.

## Проверка токена (перед push/MR)

```bash
F="$HOME/.config/gj/gitlab_pat"
curl -sS -o /tmp/u.json -w "%{http_code}\n" --header "PRIVATE-TOKEN: $(cat "$F")" \
  https://gitlab.gloria.aaanet.ru/api/v4/user --max-time 15
# 200 → токен валиден; 401 → невалиден/просрочен/пустой файл
# scopes/срок:
curl -sS --header "PRIVATE-TOKEN: $(cat "$F")" \
  https://gitlab.gloria.aaanet.ru/api/v4/personal_access_tokens/self --max-time 15
```

Нужны scopes `api` (или `read_repository`+`write_repository`), `active: true`, не просрочен. Git-уровень: `GIT_TERMINAL_PROMPT=0 git ls-remote --heads origin` → refs (exit 0).

## Flow «токена нет / невалиден» — САМ открываю файл и прошу заменить

Если `/api/v4/user` вернул **401** (или файл пустой / git даёт `HTTP Basic: Access denied`):

1. **Сам** открыть файл пользователю: `open -e "$HOME/.config/gj/gitlab_pat"` (TextEdit; для пустого файла — plain text).
2. Попросить пользователя **вставить новый PAT** и сохранить (Cmd+S): с этого инстанса `gitlab.gloria.aaanet.ru`, scope `api`, не просрочен, целиком (обычно `glpat-…`), без пробелов/лишних строк; если TextEdit в rich-режиме — Shift+Cmd+T (Make Plain Text).
3. Дождаться подтверждения «сохранил», затем **перепроверить** (`/api/v4/user` → 200).
4. Диагностика при повторном 401 без вывода токена: `file "$F"` (ASCII text?), `wc -c` (длина; glpat = 26), `grep -qi 'rtf' "$F"` (не RTF ли), whitespace-check. Если формат ок, а токен всё равно 401 → просрочен/мало scope → просить выпустить новый.

Токен пользователь вставляет сам (клавиатура → файл). Я его не читаю.

## Чистый MR (не тащить лишние коммиты)

Feature-ветку резать от целевой релизной, а не от текущей (иначе в MR попадут чужие коммиты):

```bash
git fetch origin <release>
git checkout -B <feature> origin/<release>
git cherry-pick <sha>        # наш коммит(ы); или git am <patch>
git diff --stat origin/<release>..HEAD   # проверить: только нужные файлы
GIT_TERMINAL_PROMPT=0 git push -u origin <feature>
```

MR через API (push-опции многострочное описание НЕ принимают — только API). Тело — JSON-файлом (`ensure_ascii=False`), токен из файла:

```bash
python3 - <<'PY'
import json
json.dump({
  "source_branch":"<feature>","target_branch":"<release>",
  "title":"...","description":"...\n🤖 Generated with [Claude Code](https://claude.com/claude-code)",
  "remove_source_branch":True,
}, open("/tmp/mr.json","w"), ensure_ascii=False)
PY
curl -sS -o /tmp/mr.out -w "%{http_code}\n" \
  --header "PRIVATE-TOKEN: $(cat "$HOME/.config/gj/gitlab_pat")" \
  --header "Content-Type: application/json" --data @/tmp/mr.json \
  https://gitlab.gloria.aaanet.ru/api/v4/projects/<projectId>/merge_requests --max-time 20
# 201 → создан; в ответе iid, web_url
```

Commit-месседж заканчивать `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. PR/MR-описание — строкой `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

## Project IDs (кэш; иначе `gitlab_search_projects`)

| repo | id | path |
|------|----|------|
| customers-api-web | 456 | greensight/gj/customer-gui/customers-api-web |
| pim | 449 | greensight/gj/catalog/pim |

Ветки beauty-релиза: `release-26.09`, интеграционные `release-26.08-release-26.09` (customers-api-web), `release-26.08.1-release-26.09` (pim).

## Anti-patterns

- `cat`/`head`/`echo` токена в видимую команду — утечка в транскрипт.
- Хранить токен в репо, в git-конфиге или в scratchpad (session-cleaned) — только `~/.config/gj/gitlab_pat`.
- Резать MR-ветку от текущей feature-ветки (тащит чужие коммиты) — резать от `origin/<release>`.
- Многострочное описание MR через push-options — падает; использовать API.
- Заключать «сеть закрыта» при 401 — 401 = достижимо, нет/битый токен; сверить `git ls-remote`.
