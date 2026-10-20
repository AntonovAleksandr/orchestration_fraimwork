"""Релизная карта: какие задачи, из каких репозиториев и веток, в какой релиз и в каком порядке.

Цель — не потерять репозиторий, который должен попасть в релиз. Карта хранится в файлах каталога состояния:
<состояние>/releases/<релиз>.json. Каждая запись — одна ветка одного репозитория для одной задачи.

Запись:
  task      — ключ задачи
  repo      — репозиторий (путь проекта)
  branch    — ветка с изменениями
  target    — ветка релиза, куда должна попасть
  order     — порядок слияния внутри релиза (целое, меньше — раньше)
  status    — planned | merged | verified | dropped
  after     — необязательно: задачи, которые должны быть влиты раньше этой записи

Сверка с состоянием задач (state.py): задача в ready или done без записи в карте — «забыт репозиторий»; запись
в статусе planned у задачи в done — «не влито»; запись merged без задачи в done — предупреждение.
"""
import json
import os
import re

from . import config

STATUSES = ("planned", "merged", "verified", "dropped")
REQUIRED = ("task", "repo", "branch", "target", "order")


def releases_dir():
    return os.path.join(config.state_root(), "releases")


def _path(release):
    return os.path.join(releases_dir(), f"{re.sub(r'[^A-Za-z0-9._-]+', '-', release)}.json")


def load(release):
    p = _path(release)
    if not os.path.isfile(p):
        return {"release": release, "entries": []}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _save(release, data):
    os.makedirs(releases_dir(), exist_ok=True)
    with open(_path(release), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def add(release, **entry):
    missing = [k for k in REQUIRED if entry.get(k) in (None, "")]
    if missing:
        raise ValueError("не заполнено: " + ", ".join(missing))
    entry.setdefault("status", "planned")
    if entry["status"] not in STATUSES:
        raise ValueError(f"неизвестный статус: {entry['status']}")
    entry["order"] = int(entry["order"])
    data = load(release)
    for e in data["entries"]:
        if e["task"] == entry["task"] and e["repo"] == entry["repo"] and e["branch"] == entry["branch"]:
            raise ValueError("такая запись уже есть")
    data["entries"].append(entry)
    _save(release, data)
    return entry


def set_status(release, task, repo, branch, status):
    if status not in STATUSES:
        raise ValueError(f"неизвестный статус: {status}")
    data = load(release)
    hit = [e for e in data["entries"] if e["task"] == task and e["repo"] == repo and e["branch"] == branch]
    if not hit:
        raise ValueError("записи нет")
    hit[0]["status"] = status
    _save(release, data)
    return hit[0]


def ordered(release):
    """Записи в порядке слияния; при равном order — по задаче, стабильно."""
    return sorted(load(release)["entries"], key=lambda e: (e["order"], e["task"], e["repo"]))


def order_problems(release):
    """Нарушения порядка: задача в after стоит позже своей зависимой записи."""
    entries = ordered(release)
    pos = {}
    for i, e in enumerate(entries):
        pos.setdefault(e["task"], i)
    problems = []
    for i, e in enumerate(entries):
        for dep in e.get("after", []) or []:
            if dep in pos and pos[dep] > i:
                problems.append(f"{e['task']} ({e['repo']}) должен идти после {dep}")
    return problems


def reconcile(release, task_states):
    """Расхождения карты и состояния задач. task_states: {задача: этап}; ключи сравниваются по slug."""
    entries = load(release)["entries"]
    states = {config.slug(k): v for k, v in task_states.items()}
    in_map = {config.slug(e["task"]) for e in entries}
    report = {"forgotten": [], "not_merged": [], "merged_not_done": [], "order": order_problems(release)}
    for task, st in task_states.items():
        if st in ("ready", "done") and config.slug(task) not in in_map:
            report["forgotten"].append(f"{task}: в статусе {st}, но в карте релиза нет ни одной ветки")
    for e in entries:
        st = states.get(config.slug(e["task"]))
        if st == "done" and e["status"] == "planned":
            report["not_merged"].append(f"{e['task']} ({e['repo']}:{e['branch']}): задача done, ветка не влита")
        if e["status"] == "merged" and st not in ("done", "ready"):
            report["merged_not_done"].append(f"{e['task']} ({e['repo']}): влито, но задача в статусе {st or 'неизвестно'}")
    return report


def task_states_from_disk():
    """Этапы задач из state.json каталога состояния."""
    root = config.state_root()
    out = {}
    if not os.path.isdir(root):
        return out
    for d in os.listdir(root):
        p = os.path.join(root, d, "state.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                out[d] = json.load(f).get("state", "new")
    return out


def main(argv=None):
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="releases", description="Релизная карта: ветки задач по релизам")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("release"); a.add_argument("task"); a.add_argument("repo")
    a.add_argument("branch"); a.add_argument("target"); a.add_argument("order", type=int)
    a.add_argument("--after", default="", help="задачи через запятую, которые должны быть влиты раньше")
    l = sub.add_parser("list"); l.add_argument("release")
    s = sub.add_parser("status"); s.add_argument("release"); s.add_argument("task"); s.add_argument("repo")
    s.add_argument("branch"); s.add_argument("state", choices=STATUSES)
    c = sub.add_parser("check"); c.add_argument("release")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "add":
            after = [x.strip() for x in args.after.split(",") if x.strip()]
            add(args.release, task=args.task, repo=args.repo, branch=args.branch,
                target=args.target, order=args.order, after=after)
            print("добавлено")
        elif args.cmd == "list":
            for e in ordered(args.release):
                print(f"{e['order']:>3}  {e['status']:<9} {e['task']:<14} {e['repo']:<28} {e['branch']} -> {e['target']}")
        elif args.cmd == "status":
            set_status(args.release, args.task, args.repo, args.branch, args.state)
            print("обновлено")
        elif args.cmd == "check":
            rep = reconcile(args.release, task_states_from_disk())
            total = sum(len(v) for v in rep.values())
            for k, v in rep.items():
                for line in v:
                    print(f"{k}: {line}")
            print(f"расхождений: {total}")
            return 1 if total else 0
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0


def releases_for_task(task):
    """Релизы, в которых есть хотя бы одна запись этой задачи."""
    d = releases_dir()
    if not os.path.isdir(d):
        return []
    out = []
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".json"):
            rel = fn[:-5]
            if any(config.slug(e["task"]) == config.slug(task) for e in load(rel)["entries"]):
                out.append(rel)
    return out
