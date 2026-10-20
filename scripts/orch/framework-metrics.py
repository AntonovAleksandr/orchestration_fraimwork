#!/usr/bin/env python3
"""Метрики работы фреймворка по файлам задач. Только чтение.

  framework-metrics.py [--tasks DIR] [--json]

Что считает:
- гейт: прогоны, пройдено / не пройдено (gate.log), последний вердикт по задаче;
- реестр требований и вопросы по фазам (requirements.py stats);
- статусы находок в отчётах ревью: открытые блокеры и важное, исправлено, принято;
- приёмка: вердикты acceptance.md, автозапуски (.acceptance-<sha>);
- отказы хуков (hooks.log), подтверждения в ожидании, выданные;
- журнал решений задач (decisions.md).

Чего не считает: ложные срабатывания хуков — их нет в данных, их размечают вручную
в docs/architecture/hooks-review.md (см. framework-effectiveness).
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "hooks"))


def tasks_default():
    root = os.path.abspath(os.path.join(HERE, "..", ".."))
    return os.environ.get("ORCH_TASKS_DIR") or os.path.join(root, ".tasks")


def gate_metrics(tasks):
    runs, passed, last = 0, 0, {}
    for d in sorted(os.listdir(tasks)) if os.path.isdir(tasks) else []:
        log = os.path.join(tasks, d, "gate.log")
        if not os.path.isfile(log):
            continue
        for line in open(log, encoding="utf-8"):
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            runs += 1
            ok = parts[2] == "ПРОЙДЕНО"
            passed += ok
            last[d] = parts[2]
    return {"прогонов": runs, "пройдено": passed, "не_пройдено": runs - passed,
            "последний_вердикт_по_задаче": last}


def questions_metrics(tasks):
    import requirements
    old = os.environ.get("ORCH_TASKS_DIR")
    os.environ["ORCH_TASKS_DIR"] = tasks
    total = Counter()
    per_task = {}
    for d in sorted(os.listdir(tasks)) if os.path.isdir(tasks) else []:
        if not os.path.isfile(os.path.join(tasks, d, "open-questions.md")):
            continue
        c = Counter(ph for _, ph in requirements.question_lines(d))
        if c:
            per_task[d] = dict(c)
            total.update(c)
    if old is None:
        os.environ.pop("ORCH_TASKS_DIR", None)
    else:
        os.environ["ORCH_TASKS_DIR"] = old
    return {"по_фазам": dict(total), "по_задачам": per_task}


def findings_metrics(tasks):
    import findings
    out = Counter()
    for d in sorted(os.listdir(tasks)) if os.path.isdir(tasks) else []:
        if not d.startswith("review-"):
            continue
        rep = os.path.join(tasks, d, "report.md")
        if not os.path.isfile(rep):
            out["отчёт_не_найден"] += 1
            continue
        for it in findings.parse(open(rep, encoding="utf-8").read().splitlines()):
            sev = findings.severity(it["title"])
            st = (it["status"] or "открыто")
            kind = ("принято" if st.startswith("принято:") else
                    "снято" if st.startswith("снято:") else
                    "исправлено" if st.startswith("исправлено") else "открыто")
            out[f"{sev}:{kind}"] += 1
    return dict(out)


def acceptance_metrics(tasks):
    verdicts, autostart = Counter(), 0
    for d in sorted(os.listdir(tasks)) if os.path.isdir(tasks) else []:
        ap = os.path.join(tasks, d, "acceptance.md")
        if os.path.isfile(ap):
            m = re.search(r"^## вердикт:\s*(.+)$", open(ap, encoding="utf-8").read(), re.M)
            verdicts[m.group(1).strip() if m else "без вердикта"] += 1
        autostart += sum(1 for f in os.listdir(os.path.join(tasks, d)) if f.startswith(".acceptance-")) \
            if os.path.isdir(os.path.join(tasks, d)) else 0
    return {"вердикты": dict(verdicts), "автозапусков": autostart}


def hooks_metrics(tasks):
    log = os.path.join(tasks, "hooks.log")
    if not os.path.isfile(log):
        return {"отказов": 0, "замечание": "журнала hooks.log нет — отказы не измерены"}
    rows = [l.rstrip("\n").split("\t") for l in open(log, encoding="utf-8") if l.strip()]
    return {"отказов": len(rows), "по_дням": dict(Counter(r[0][:10] for r in rows)),
            "коды_в_ожидании": len(os.listdir(os.path.join(tasks, "approvals", "pending")))
            if os.path.isdir(os.path.join(tasks, "approvals", "pending")) else 0}


def decisions_metrics(root):
    p = os.path.join(root, "docs", "architecture", "decisions.md")
    if not os.path.isfile(p):
        return {"записей": 0, "замечание": "docs/architecture/decisions.md не создан"}
    n = len(re.findall(r"^## D-\d+", open(p, encoding="utf-8").read(), re.M))
    return {"записей": n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default=tasks_default())
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    tasks = os.path.abspath(a.tasks)
    root = os.path.abspath(os.path.join(HERE, "..", ".."))
    data = {
        "гейт": gate_metrics(tasks),
        "вопросы": questions_metrics(tasks),
        "находки": findings_metrics(tasks),
        "приёмка": acceptance_metrics(tasks),
        "хуки": hooks_metrics(tasks),
        "решения": decisions_metrics(root),
    }
    if a.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        for k, v in data.items():
            print(f"== {k}")
            print(json.dumps(v, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
