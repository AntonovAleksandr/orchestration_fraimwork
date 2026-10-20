#!/usr/bin/env python3
"""UserPromptSubmit: подсказать нужные скиллы прямо в реплике.

Скиллы по описанию грузятся редко, а текст в самой реплике срабатывает всегда. Хук дописывает одну строку с именами скиллов
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
        hints.append("Ответ на ревью нашего запроса: загрузи review-checklists (references/comments.md, "
                     "«Ответ автора на ревью»); из скиллов " + DEFECT + " — те, к классам которых относятся треды. "
                     "Несколько запросов — scripts/orch/orchestrate.sh respond <адреса>.")
    elif mr and not ci or re.search(r"\bревью\b|апрув|посмотри (mr|мр|мерж)|проверь (mr|мр|мерж)", p):
        hints.append("Ревью запроса: загрузи review-delegation (scripts/orch/orchestrate.sh review <адрес>), чек-листы — review-checklists.")
    if re.search(r"/browse/|\bприступ(и|ай)\b|возьми задач|начни работ|\b[a-z][a-z0-9]*-\d+\b.*\b(сделай|начни|возьми|правь)", p):
        hints.append("Задача: загрузи task-orchestration и task-execution, затем " + DEFECT +
                     " (работник: scripts/orch/orchestrate.sh task <КЛЮЧ>). Таблица повторов до правки, «Самопроверка» во вводной до сдачи.")
    if re.search(r"оформи (mr|мр|запрос)|открой (mr|мр|запрос)|подготовь (mr|мр)|\bсдай\b|\bсдача\b|готово к (mr|мр)", p):
        hints.append("Перед запросом на слияние: «Самопроверка» во вводной (scripts/orch/selfcheck.py), описание — "
                     "commit-and-mr-writing, сдача — scripts/orch/orchestrate.sh done <КЛЮЧ>.")
    if re.search(r"архитектур|спроектир|постановк|\bфт\b|критери[йя] приёмки|проектиров", p):
        hints.append("Архитектура: сначала выпиши из ФТ и критериев приёмки всё, что относится к решению "
                     "(task-orchestration); если ФТ молчит — вопрос аналитику, а не выбор по аналогии. "
                     "Решения фиксируй: scripts/orch/decide.sh <КЛЮЧ> \"…\" --from \"…\".")
    if re.search(r"самоанализ|ретро фреймворк|эффективност[ьи] фреймворк|доработк[аи] фреймворк|фреймворк.{0,40}(эффект|ретро|метрик)", p):
        hints.append("Фреймворк: после доработки — framework-retro (факт, проверка, решение в docs/architecture/decisions.md, "
                     "предложения с фактом); вопрос об эффекте — framework-effectiveness; метрики — docs/architecture/metrics.md, "
                     "снимок: scripts/orch/framework-metrics.py.")
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
              "additionalContext": "Скиллы воркспейса: " + " | ".join(hints)}}, ensure_ascii=False))

if __name__ == "__main__":
    main()
