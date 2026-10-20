"""События задачи: одна строка JSON на событие в <каталог задачи>/events.jsonl.

Назначение: из событий строятся отчёты эффективности (время, круги ревью, вопросы по фазам, падения гейта, вызовы
скиллов). Событие пишет инструмент в момент действия; текст переписки и содержимое документов в события не попадает.

Типы событий (поле `type`):
  task_started       — старт задачи (поля: kind)
  gate_run           — прогон гейта (verdict: ПРОЙДЕНО | НЕ ПРОЙДЕНО; failed: число провалов; sha)
  question_asked     — вопрос аналитику (qid, phase)
  question_answered  — ответ на вопрос (qid)
  finding_status     — статус находки (review, fid, status)
  review_round       — новая вершина в отчёте ревью (review, sha, verdict)
  decision_recorded  — решение записано (source)
  hook_denied        — отказ хука (hook, code)
  approval_granted   — человек подтвердил действие (code)
  acceptance_verdict — вердикт приёмки (verdict, sha)
  merged             — слияние (review)
  state_changed      — переход состояния задачи (frm, to, reason)

CLI (через обёртку проекта, которая задаёт каталог состояния):
  events.py emit <КЛЮЧ> <тип> [поле=значение ...]
  events.py show <КЛЮЧ>
"""
import datetime
import json
import os
import sys

from . import config

EVENT_TYPES = {
    "task_started", "gate_run", "question_asked", "question_answered", "finding_status",
    "review_round", "decision_recorded", "hook_denied", "approval_granted", "acceptance_verdict", "merged",
    "state_changed",
}


def path(key):
    return os.path.join(config.task_dir(key), "events.jsonl")


def emit(key, etype, **data):
    if etype not in EVENT_TYPES:
        raise ValueError(f"неизвестный тип события: {etype}")
    os.makedirs(config.task_dir(key), exist_ok=True)
    row = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "type": etype, **data}
    with open(path(key), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def read(key):
    p = path(key)
    if not os.path.isfile(p):
        return []
    out = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _parse_kv(items):
    data = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"ожидалось поле=значение, получено: {item}")
        k, v = item.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("emit", "show"):
        print("usage: events.py emit <КЛЮЧ> <тип> [поле=значение ...] | show <КЛЮЧ>", file=sys.stderr)
        return 2
    if argv[0] == "emit":
        if len(argv) < 3:
            print("emit: нужны ключ и тип", file=sys.stderr)
            return 2
        try:
            emit(argv[1], argv[2], **_parse_kv(argv[3:]))
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        return 0
    rows = read(argv[1])
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    if not rows:
        print("событий нет")
    return 0
