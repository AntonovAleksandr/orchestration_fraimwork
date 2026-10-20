"""Единый реестр вопросов аналитике и заказчику по задачам.

Один файл на все задачи: <состояние>/questions-register.json. Разработчик в начале дня выгружает реестр (export) и
отправляет аналитику. Вопросы добавляются по мере появления в задачах.

Вопрос добавляется только с доказательством, что его нет в ответах: ссылка на Confluence (confluence:<id>@v<версия>),
постановку (постановка §<раздел>), трекер (tracker:<КЛЮЧ>) или код (код:<путь>). Вопрос, похожий на уже записанный
(≥ 0.5 по словам), отклоняется. Импорт из внешних реестров — отдельно, с пометкой источника.
"""
import datetime
import html
import json
import os
import re
import sys

from . import config, requirements

STATUSES = ("блокер", "важно", "уточнение")
PRIORITIES = ("срочно", "позже")
EVIDENCE = re.compile(r"confluence:\d+|постановка §\S+|tracker:[A-Z][A-Z0-9]+-\d+|код:\S+", re.I)


def path():
    return os.path.join(config.state_root(), "questions-register.json")


def load():
    p = path()
    if not os.path.isfile(p):
        return {"questions": []}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _save(data):
    os.makedirs(os.path.dirname(path()), exist_ok=True)
    with open(path(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _known_texts(data):
    return [q["text"] for q in data["questions"]]


INTERNAL = re.compile(
    r"агент|скилл|оркестр|работник|гейт|фикстур|state\.json|\.tasks|requirements\.py|questions\.py|"
    r"orca|orchestrat|claude|промпт|prompt|конфлюенс-?скил|реестр вопросов|мок-данн|тест-?раннер",
    re.I)
IDENT = re.compile(r"\b(?:[a-z]+[A-Z][A-Za-z0-9]*|[a-z]+(?:_[a-z0-9]+)+)\b")
FILE_NAME = re.compile(r"\b[\w/.-]+\.(py|php|ts|tsx|js|go|sh|md|json|yaml|yml|kt|swift|dart)\b", re.I)


def check_human(text):
    """Вопрос должен читаться без доступа к нашим инструментам. Пустой список — вопрос проходит."""
    problems = []
    t = text.strip()
    if not 15 <= len(t) <= 400:
        problems.append("длина вопроса от 15 до 400 символов")
    if "?" not in t:
        problems.append("сформулировать как вопрос (с «?»)")
    m = INTERNAL.search(t)
    if m:
        problems.append(f"убрать внутренний термин «{m.group(0)}»: аналитику он не нужен")
    f = FILE_NAME.search(t)
    if f:
        problems.append(f"убрать имя файла «{f.group(0)}»: описать поведение словами")
    ident = IDENT.search(t)
    if ident:
        problems.append(f"убрать идентификатор кода «{ident.group(0)}»: описать словами, что происходит")
    return problems


def add(task, text, checked, status="уточнение", priority="позже", addressee="аналитик", thread="",
        options=None, deadline="", imported=False):
    if status not in STATUSES:
        raise ValueError(f"статус: {', '.join(STATUSES)}")
    if priority not in PRIORITIES:
        raise ValueError(f"приоритет: {', '.join(PRIORITIES)}")
    if not text.strip():
        raise ValueError("пустой вопрос")
    if not imported:
        problems = check_human(text)
        if problems:
            raise ValueError("вопрос не принят: " + "; ".join(problems))
    if not imported and not EVIDENCE.search(checked or ""):
        raise ValueError("нужна ссылка на проверенный источник: confluence:<id>@v<версия>, "
                         "постановка §<раздел>, tracker:<КЛЮЧ>, код:<путь>")
    data = load()
    for known in _known_texts(data) + [t for t in requirements_texts(task)]:
        sim = requirements.similarity(text, known)
        if sim >= 0.5:
            raise ValueError(f"похоже на уже записанный вопрос (сходство {sim:.2f}): {known[:120]}")
    n = 1 + sum(1 for q in data["questions"] if q["task"] == task)
    item = {
        "id": f"{task}-Q{n}", "task": task, "thread": thread, "addressee": addressee,
        "status": status, "priority": priority, "text": text.strip(), "options": options or [],
        "deadline": deadline, "checked": (checked or "").strip(), "imported": imported,
        "state": "открыт", "answer": "", "added": datetime.date.today().isoformat(),
    }
    data["questions"].append(item)
    _save(data)
    return item


def requirements_texts(task):
    try:
        return [r[1] for r in requirements.rows(task)]
    except Exception:
        return []


def close(qid, answer, source):
    data = load()
    hit = [q for q in data["questions"] if q["id"] == qid]
    if not hit:
        raise ValueError(f"нет вопроса {qid}")
    if not answer.strip() or not source.strip():
        raise ValueError("закрытие нужно с ответом и источником")
    hit[0]["state"] = "закрыт"
    hit[0]["answer"] = f"{answer.strip()} (источник: {source.strip()})"
    _save(data)
    return hit[0]


def export_markdown(open_only=True):
    data = load()
    tasks = {}
    for q in data["questions"]:
        if open_only and q["state"] != "открыт":
            continue
        tasks.setdefault(q["task"], []).append(q)
    out = ["# Вопросы аналитике", ""]
    for task, qs in tasks.items():
        out.append(f"## {task}")
        out.append("")
        for q in qs:
            out.append(f"- **{q['id']}** [{q['status']}, {q['priority']}] {q['text']}")
            if q["thread"]:
                out.append(f"  - тред: {q['thread']}")
            if q["options"]:
                out.append("  - варианты: " + " / ".join(q["options"]))
            if q["deadline"]:
                out.append(f"  - срок: {q['deadline']}")
            out.append(f"  - проверено: {q['checked']}")
        out.append("")
    return "\n".join(out)


def export_html(open_only=True):
    md = export_markdown(open_only)
    body = []
    for line in md.splitlines():
        if line.startswith("## "):
            body.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("- "):
            body.append(f"<p class='q'>{html.escape(line[2:])}</p>")
        elif line.startswith("  - "):
            body.append(f"<p class='d'>{html.escape(line[4:])}</p>")
        elif line.startswith("# "):
            body.append(f"<h1>{html.escape(line[2:])}</h1>")
    return ("<!doctype html><html lang='ru'><head><meta charset='utf-8'><title>Вопросы аналитике</title>"
            "<style>body{font:15px -apple-system,sans-serif;max-width:820px;margin:24px auto;padding:0 16px}"
            "h2{margin-top:28px;border-bottom:1px solid #ddd}.q{margin:14px 0 2px;font-weight:600}"
            ".d{margin:2px 0 2px 16px;color:#555}</style></head><body>"
            + "".join(body) + "</body></html>")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="questions", description="Единый реестр вопросов аналитике")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("task"); a.add_argument("text")
    a.add_argument("--checked", required=True, help="источник проверки: confluence:<id>@v<n> | постановка §… | tracker:KEY | код:путь")
    a.add_argument("--status", default="уточнение", choices=STATUSES)
    a.add_argument("--priority", default="позже", choices=PRIORITIES)
    a.add_argument("--addressee", default="аналитик")
    a.add_argument("--thread", default=""); a.add_argument("--option", action="append", default=[])
    a.add_argument("--deadline", default="")
    c = sub.add_parser("close"); c.add_argument("qid"); c.add_argument("answer"); c.add_argument("--source", required=True)
    e = sub.add_parser("export"); e.add_argument("--format", choices=("md", "html"), default="md")
    e.add_argument("--all", action="store_true", help="включая закрытые")
    sub.add_parser("list")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "add":
            it = add(args.task, args.text, args.checked, args.status, args.priority, args.addressee,
                     args.thread, args.option, args.deadline)
            print(f"добавлено: {it['id']}")
        elif args.cmd == "close":
            it = close(args.qid, args.answer, args.source)
            print(f"закрыто: {it['id']}")
        elif args.cmd == "export":
            out = export_html(not args.all) if args.format == "html" else export_markdown(not args.all)
            print(out)
        elif args.cmd == "list":
            for q in load()["questions"]:
                print(f"{q['id']:<22} {q['state']:<8} {q['status']:<9} {q['priority']:<7} {q['text'][:70]}")
    except ValueError as err:
        print(str(err), file=sys.stderr)
        return 2
    return 0
