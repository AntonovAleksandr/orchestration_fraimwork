# Инвентаризация: что в ядро, что в адаптер проекта

Классы:
- **ядро** — готов к переносу, проектных токенов нет (проверяет тест);
- **параметризовать** — логика общая, но держит проектные имена; переносится после выноса в профиль;
- **адаптер** — конкретная интеграция (GitLab, трекер задач, Orca, Kubernetes), остаётся отдельным модулем;
- **проект** — только для воркспейса проекта.

| Файл | Класс | Проектных токенов | Что нужно |
|---|---|---|---|
| `framework/core/vcs.py` | ядро | 0 | интерфейс VCS: адаптеры реализуют |
| `framework/core/responses.py` | ядро | 0 | ответы на замечания: исправлено / согласие / отклонено / не исправлено / задача по согласованию; без ответа слияния нет |
| `framework/core/git_source.py` | ядро | 0 | проверка строки по версии файла в git |
| `.claude/skills/framework-review-validate/` | ядро | 0 | проверка замечаний перед публикацией |
| `framework/core/review_publish.py` | ядро | 0 | публикация находок только после проверки: подтверждено / отклонено / вопрос |
| `framework/adapters/gitlab_vcs.py` | адаптер (GitLab, общие знания) | 0 | обсуждения MR по строкам диффа через `glab api`; записи — только по решению вызывающего |
| `framework/core/releases.py` | ядро | 0 | релизная карта: ветки задач по релизам, порядок слияния, сверка с этапами задач (забытые репозитории) |
| `framework/core/questions.py` | ядро | 0 | единый реестр вопросов аналитике по задачам: проверка источника, дедупликация, экспорт |
| `framework/core/state.py` | ядро | 0 | состояние задачи: переходы, причина ожидания, история |
| `framework/core/findings.py` | ядро | 0 | перенесён; `scripts/orch/findings.py` — обёртка проекта |
| `framework/core/requirements.py` | ядро | 0 | перенесён; `scripts/orch/requirements.py` — обёртка проекта |
| `framework/core/config.py` | ядро | 0 | настройки: префикс, каталог состояния, корень |
| `framework/core/events.py` | ядро | 0 | события задач; обёртка `scripts/orch/events.py` |
| `scripts/orch/hooks/git-guard.py` | ядро | 0 | — |
| `scripts/orch/selfcheck.py` | ядро | 0 | — |
| `scripts/orch/gate.py` | параметризовать | 5 | ключи, защищённые ветки, команда `glab` → адаптер |
| `scripts/orch/framework-metrics.py` | параметризовать | 7 | список метрик → профиль |
| `scripts/orch/approve.sh` | параметризовать | 1 | каталог состояния |
| `scripts/orch/decide.sh` | параметризовать | 2 | каталог состояния |
| `scripts/orch/hooks/_approval.py` | параметризовать | 1 | каталог состояния |
| `scripts/orch/hooks/approval-guard.py` | адаптер (MCP и glab) | 7 | список внешних записей → профиль |
| `scripts/orch/hooks/merge-guard.py` | адаптер (GitLab) | 4 | формат имени каталога ревью → профиль |
| `scripts/orch/hooks/mr-gate.py` | адаптер (GitLab) | 9 | ключ задачи и MR → профиль |
| `scripts/orch/hooks/skill-router.py` | проект | — | подсказки — только в профиле проекта |
| `scripts/orch/install-hooks.sh` | параметризовать | 2 | список хуков из профиля |
| `scripts/orch/orchestrate.sh` | проект + ядро | — | разделить: ядро команд, спецификации — в профиль |
| `.claude/orchestration/review_results.py` | адаптер (GitLab) | 7 | публикация — адаптер |
| `.claude/skills/framework-retro/` | ядро | 0 | — |
| `.claude/skills/framework-effectiveness/` | ядро | 0 | — |
| `.claude/agents/qa-acceptance.md` | проект | — | в профиль проекта |
| `docs/architecture/metrics.md`, `hooks-review.md`, `decisions.md` | проект | — | остаются в воркспейсе проекта |
