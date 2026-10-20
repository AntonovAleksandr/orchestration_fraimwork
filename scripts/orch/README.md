# Набор скриптов оркестрации

Запуск задач, формы контроля и хуки. Каждый скрипт закрывает конкретную статью расхода
или повторяющуюся ошибку работы агентов.

| Скрипт | Что делает |
|---|---|
| `orchestrate.sh` | работники Orca: `task`, `front`, `review`, `respond`, `done`, `analyze`, `accept`; скиллы вписаны в постановку, сдача без «Самопроверки» не идёт |
| `task.sh` | заводит вводную `.tasks/<ключ>/brief.md` и печатает команду запуска отдельной сессии |
| `fleet.sh` | пачка задач одной командой, вкладка на каждую |
| `cleanup-merged-branches.sh` | удаляет локальные и удалённые ветки задачи, которые уже слиты |
| `create-mr-with-base-branch.sh` | открывает запрос на слияние в зарегистрированную целевую ветку |
| `install-hooks.sh` | подключает хуки из `hooks/` в `.claude/settings.json` дерева |
| `state.py`, `events.py`, `findings.py`, `requirements.py`, `questions.py`, `releases.py` | обёртки над ядром `framework/core` с настройками проекта |
| `gate.py`, `selfcheck.py` | гейт сдачи и проверка раздела «Самопроверка» во вводной |
| `approve.sh`, `decide.sh` | разовое подтверждение внешней записи человеком; журнал решений задачи |
| `stats.py`, `framework-metrics.py` | аналитика по журналам сессий и метрики фреймворка |

## Запуск задачи

```bash
scripts/orch/task.sh back  PROJ-123 "краткий заголовок"
scripts/orch/task.sh front PROJ-124 "краткий заголовок"
scripts/orch/task.sh review https://git.example.com/group/project/-/merge_requests/7
```

Каждая команда кладёт вводную в `.tasks/<ключ>/brief.md` и печатает команду запуска.
Запускать отдельной сессией: сессии живут долго, и к концу каждый ход стоит в разы дороже первого.
Ссылка на задачу в вводной строится из `ORCH_TRACKER_URL` (например `https://tracker.example.com/browse`).

## Скиллы классов дефектов и ревью

Перечень — `defect-skills.txt` (единый для скриптов и хуков): `retry-safe-writes`,
`fail-loud-boundaries`, `value-precision`, `change-hygiene`. Чек-листы, каталог дефектов,
формат комментариев и ответ на ревью — `review-checklists`.

## Хуки: чтобы скиллы применялись

```bash
scripts/orch/install-hooks.sh          # один раз в каждом рабочем дереве (.claude/settings.json не в git)
```

- `skill-router.py` (UserPromptSubmit) — на ссылку на запрос, задачу, слова о ревью или сдаче
  дописывает в контекст одну строку: какие скиллы загрузить и какой командой оркестратора запускать.
  Причина: скиллы по описанию грузятся редко, текст в реплике срабатывает всегда.
- `mr-gate.py` (PreToolUse, Bash) — отказывает в создании запроса на слияние (`-o merge_request.create`,
  `glab mr create`, POST `/merge_requests`), если в `.tasks/<ключ>/brief.md` не заполнена «Самопроверка».
  Обход — `ORCH_SKIP_SELFCHECK=1` в самой команде.
- `approval-guard.py`, `git-guard.py`, `merge-guard.py` — внешние записи и слияния только по подтверждению человека.

Ключ задачи в хуках — «слово-число» (кроме `release-N`, `hotfix-N`); свой шаблон — `ORCH_TASK_KEY_RE`.

Проверить, что скиллы реально грузятся: `scripts/orch/stats.py --skills --days 7`.

## Вложенные клоны

Рабочее дерево git не содержит вложенных клонов. Если задачи идут по набору отдельных репозиториев
внутри корня, их маски (через пробел, от корня) задаются в `ORCH_REPO_GLOBS`, например `"repos/* repos/*/*"`:
по ним `orchestrate.sh` останавливает запуск в дереве без клонов, `fleet.sh` предупреждает, а
`cleanup-merged-branches.sh` ищет ветки. Без масок проверка дерева отключена, очистка работает в самом корне.

## Аналитика

```bash
scripts/orch/stats.py                       # свод: расход, на ход, на задачу
scripts/orch/stats.py --phases              # структура расхода по фазам работы
scripts/orch/stats.py --sinks               # куда уходит объём
scripts/orch/stats.py --waste               # отказы, повторные чтения
scripts/orch/stats.py --skills              # скиллы, делегирования, цена ревью
scripts/orch/stats.py --compare 14          # период против предыдущего
scripts/orch/stats.py --snapshot base.json  # зафиксировать замер
scripts/orch/stats.py --baseline base.json  # сравнить с ним позже
```

Смотреть на расход на задачу, не на общий: общий растёт вместе с объёмом работы.

Две ловушки, обе учтены в скрипте: один ответ модели пишется несколькими записями с общим usage
(сырой подсчёт завышает вдвое, склейка идёт по `requestId`), а ходы подагентов не логируются вовсе —
все числа относятся только к родительским сессиям. Подробности — `.claude/skills/session-analytics`.

## Автоматическая очистка веток после слияния

Ветки задач занимают слоты рабочих деревьев. После успешной сдачи `orchestrate.sh done` удаляет
локальные и удалённые ветки задачи, которые уже слиты в целевые ветки.

```bash
scripts/orch/orchestrate.sh done PROJ-123
scripts/orch/orchestrate.sh cleanup PROJ-123       # запустить очистку
scripts/orch/orchestrate.sh cleanup PROJ-123 --dry # показать, что будет удалено
scripts/orch/orchestrate.sh cleanup-log PROJ-123   # показать лог очистки
scripts/orch/cleanup-merged-branches.sh <КЛЮЧ>     # то же напрямую (--dry-run, --log)
```

Как это работает:
1. Поиск репозиториев: по `ORCH_REPO_GLOBS`, без масок — сам корень.
2. Поиск веток по шаблону задачи: `slug(PROJ-123)` = `proj-123` в `refs/heads/*` и `refs/remotes/*`.
3. Проверка, что ветка слита в main/master (локальные и `origin/*`).
4. Удаление только слитых: `git branch -D <ветка>`, `git push <remote> --delete <ветка>`.
5. Лог: `.tasks/<ключ>/branches.log`, состояние: `.tasks/<ключ>/cleanup.state`.

Ветка остаётся, если она не слита (ревью или конфликт), не найдена или нет доступа к удалённому
хранилищу; тогда в лог пишется ошибка, удалить можно вручную.

Переменные: `ORCH_SKIP_CLEANUP=1` — пропустить очистку, `ORCH_DRY_RUN=1` — сухой прогон,
`ORCH_TASKS_DIR` — каталог задач (по умолчанию `.tasks`).
