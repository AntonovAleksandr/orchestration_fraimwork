#!/usr/bin/env python3
"""UserPromptSubmit: подсказать нужные скиллы прямо в реплике.

Замер по 66 журналам: скиллы грузятся в 0,17% ходов, подбор по описанию не срабатывает,
а текст в самой реплике срабатывает всегда. Хук дописывает одну строку с именами скиллов
и командой оркестратора — только когда реплика на это похожа. Системные уведомления
(завершение подагента и т. п.) пропускаются: в них чужой текст.
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import selfcheck  # noqa: E402

BACK = selfcheck.skills("back")
DEFECT = ", ".join(BACK)

def rules(p, mr):
    hints = []
    ci = re.search(r"пайплайн|джоб|pipeline|сборк[аи] упал", p)
    respond = re.search(r"замечани|тред|комментари", p) and (mr or re.search(r"![0-9]+|ревьюер", p))
    if respond:
        hints.append("Ответ на ревью нашего запроса: загрузи gj-review-checklists (references/comments.md, "
                     "«Ответ автора на ревью»); из скиллов " + DEFECT + " — те, к классам которых относятся треды. "
                     "Несколько запросов — scripts/gj/orchestrate.sh respond <адреса>.")
    elif mr and not ci or re.search(r"\bревью\b|апрув|посмотри (mr|мр|мерж)|проверь (mr|мр|мерж)", p):
        hints.append("Ревью запроса: загрузи gj-review-delegation (scripts/gj/orchestrate.sh review <адрес>), чек-листы — gj-review-checklists.")
    if ci:
        hints.append("Сбой сборки или деплоя: загрузи gj-ci-deploy-map.")
    if re.search(r"jira\.gloria-jeans\.ru/browse/|\bприступ(и|ай)\b|возьми задач|начни работ|\bopsomn\d*-\d+\b.*\b(сделай|начни|возьми|правь)", p):
        hints.append("Задача: загрузи gj-task-orchestration и gj-task-execution, затем " + DEFECT +
                     " (работник: scripts/gj/orchestrate.sh task <КЛЮЧ>). Таблица повторов до правки, «Самопроверка» во вводной до сдачи.")
    if re.search(r"оформи (mr|мр|запрос)|открой (mr|мр|запрос)|подготовь (mr|мр)|\bсдай\b|\bсдача\b|готово к (mr|мр)", p):
        hints.append("Перед запросом на слияние: «Самопроверка» во вводной (scripts/gj/selfcheck.py), описание — "
                     "gj-commit-and-mr-writing, сдача — scripts/gj/orchestrate.sh done <КЛЮЧ>.")
    if re.search(r"выкат|депло|\bhelm\b|ms-helm|маппинг|переиндекс|cronjob", p):
        hints.append("Выкатка: загрузи gj-rollout-safety и gj-ci-deploy-map.")
    return hints

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    raw = data.get("prompt") or ""
    if not raw or re.search(r"<task-notification>|\[SYSTEM NOTIFICATION", raw):
        return
    p = raw.lower()
    hints = rules(p, bool(re.search(r"/-/merge_requests/\d+", p)))
    if hints:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
              "additionalContext": "Скиллы воркспейса GJ: " + " | ".join(hints)}}, ensure_ascii=False))

if __name__ == "__main__":
    main()
