"""Ответы на замечания (обсуждения запроса на слияние).

Каждое замечание обрабатывается одним из исходов:
  fixed        — исправлено коммитом: нужен sha
  agreed       — согласие с замечанием: нужен комментарий
  rejected     — отклонено: нужна причина
  not_fixed    — не исправлено: нужно объяснение, почему
  task_link    — вынесено в задачу, согласованную с человеком: нужны ссылка на задачу и имя человека, который согласовал

Замечание без валидного ответа считается необработанным. Запрос на слияние с необработанными замечаниями не сливается.
Агент не заводит задачи сам и не выносит доработку из фичи без согласия человека.
"""

OUTCOMES = {
    "fixed": ("sha",),
    "agreed": ("comment",),
    "rejected": ("reason",),
    "not_fixed": ("reason",),
    "task_link": ("url", "agreed_with"),
}


def problems(response):
    """Что не так с ответом; пустой список — ответ валиден."""
    kind = response.get("outcome")
    if kind not in OUTCOMES:
        return [f"неизвестный исход «{kind}»"]
    missing = [f for f in OUTCOMES[kind] if not str(response.get(f, "")).strip()]
    return [f"исход «{kind}»: не заполнено «{f}»" for f in missing]


def unanswered(thread_ids, responses):
    """Замечания без валидного ответа."""
    out = []
    for tid in thread_ids:
        r = responses.get(tid)
        if r is None or problems(r):
            out.append(tid)
    return out


def can_merge(thread_ids, responses):
    """Слияние разрешено только когда все замечания обработаны."""
    return not unanswered(thread_ids, responses)
