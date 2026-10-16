#!/usr/bin/env python3
"""Реестр требований задачи и вопросы аналитику без повторов.

  requirements init  <КЛЮЧ>
  framework-requirements add   <КЛЮЧ> --text "…" --source "…" --version "…" --status согласовано|конфликт|открыто|допущение [--note "…"]
  framework-requirements check <КЛЮЧ>                       — код 1, если есть конфликт или открытое требование
  framework-requirements ask   <КЛЮЧ> "<вопрос>" --checked "<где проверено>" [--blocks R3] [--phase analysis|architecture|review|dev]
  framework-requirements stats [КЛЮЧ]                       — сколько вопросов по фазам (метрика: до архитектуры и после ревью)
  framework-requirements answer <КЛЮЧ> Q<n> "<ответ>" --source "…"

Файлы: <каталог состояния>/<ключ>/requirements.md, open-questions.md, answers.md.
Вопрос отклоняется, если пустой раздел «проверено», либо он похож (≥ 0.5 по словам) на
требование, ответ или вопрос, уже записанный по задаче.
"""
import argparse
import os
import re
import sys

from . import config, events

STATUSES = ("согласовано", "конфликт", "открыто", "допущение")
PHASES = ("analysis", "architecture", "review", "dev")
BLOCKING = ("конфликт", "открыто")
STOP = {"и", "в", "во", "на", "по", "из", "для", "не", "что", "как", "это", "или", "а", "но", "с", "к", "у",
        "the", "of", "to", "is", "a"}
HEADER = ("| id | требование | источник | версия | статус | примечание |\n"
          "|---|---|---|---|---|---|\n")


def tasks_dir():
    return config.state_root()


def task_dir(key):
    return config.task_dir(key)


def path(key, name):
    return os.path.join(task_dir(key), name)


def read(key, name):
    p = path(key, name)
    return open(p, encoding="utf-8").read() if os.path.isfile(p) else ""


def append(key, name, text):
    os.makedirs(task_dir(key), exist_ok=True)
    with open(path(key, name), "a", encoding="utf-8") as f:
        f.write(text)


def rows(key):
    out = []
    for line in read(key, "requirements.md").splitlines():
        if not line.startswith("| R") :
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5:
            out.append(cells)
    return out


def words(text):
    toks = re.findall(r"[a-zа-яё0-9\-_.]+", text.lower())
    return {t for t in toks if len(t) > 2 and t not in STOP}


def similarity(a, b):
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def known_texts(key):
    texts = []
    for r in rows(key):
        texts.append(("требование " + r[0], r[1]))
    for name in ("answers.md", "open-questions.md"):
        for line in read(key, name).splitlines():
            if line.startswith("- "):
                texts.append((name, line[2:]))
    return texts


def cmd_init(a):
    if not os.path.isfile(path(a.key, "requirements.md")):
        append(a.key, "requirements.md", f"# Требования {a.key}\n\n" + HEADER)
    print(f"реестр: {path(a.key, 'requirements.md')}")
    return 0


def cmd_add(a):
    if a.status not in STATUSES:
        print(f"статус должен быть одним из: {', '.join(STATUSES)}", file=sys.stderr)
        return 2
    if a.status == "согласовано" and not (a.source and a.version):
        print("согласованное требование без источника и версии не принимается", file=sys.stderr)
        return 2
    if not os.path.isfile(path(a.key, "requirements.md")):
        cmd_init(a)
    n = len(rows(a.key)) + 1
    cells = [f"R{n}", a.text.replace("|", "/"), a.source or "", a.version or "", a.status, a.note or ""]
    append(a.key, "requirements.md", "| " + " | ".join(cells) + " |\n")
    print(f"R{n} добавлено")
    return 0


def cmd_check(a):
    rs = rows(a.key)
    if not rs:
        print("реестр пуст или не создан: requirements init")
        return 1
    blocking = [r for r in rs if r[4] in BLOCKING]
    unsourced = [r for r in rs if r[4] == "согласовано" and not (r[2] and r[3])]
    for r in blocking:
        print(f"БЛОК {r[0]} [{r[4]}] {r[1][:90]}")
    for r in unsourced:
        print(f"НЕТ ИСТОЧНИКА {r[0]} {r[1][:90]}")
    print(f"требований: {len(rs)}, блокирующих: {len(blocking)}")
    return 1 if blocking or unsourced else 0


def cmd_ask(a):
    if not a.checked.strip():
        print("вопрос без указания, где проверено, не принимается (внешние источники, answers.md, код)", file=sys.stderr)
        return 2
    for where, text in known_texts(a.key):
        sim = similarity(a.question, text)
        if sim >= 0.5:
            print(f"ПОВТОР ({where}, сходство {sim:.2f}): {text[:160]}", file=sys.stderr)
            return 3
    n = len(re.findall(r"^- Q\d+", read(a.key, "open-questions.md"), re.M)) + 1
    blocks = f" | блокирует: {a.blocks}" if a.blocks else ""
    append(a.key, "open-questions.md",
           f"- Q{n} [открыт] {a.question.strip()} | проверено: {a.checked.strip()}{blocks} | фаза: {a.phase}\n")
    events.emit(a.key, "question_asked", qid=f"Q{n}", phase=a.phase)
    print(f"Q{n} записан")
    return 0


def question_lines(key):
    for line in read(key, "open-questions.md").splitlines():
        m = re.match(r"^- Q\d+ \[(открыт|закрыт)\]", line)
        if m:
            ph = re.search(r"\| фаза: (\w+)\s*$", line)
            yield m.group(1), (ph.group(1) if ph else "analysis")


def cmd_stats(a):
    keys = [a.key] if a.key else sorted(
        d for d in os.listdir(tasks_dir()) if os.path.isfile(os.path.join(tasks_dir(), d, "open-questions.md"))
    ) if os.path.isdir(tasks_dir()) else []
    if not keys:
        print("задач с вопросами нет")
        return 0
    total = {p: 0 for p in PHASES}
    print(f"{'задача':<28}" + "".join(f"{p:>14}" for p in PHASES))
    for k in keys:
        cnt = {p: 0 for p in PHASES}
        for _, ph in question_lines(k):
            cnt[ph] = cnt.get(ph, 0) + 1
        for p in PHASES:
            total[p] += cnt.get(p, 0)
        print(f"{k:<28}" + "".join(f"{cnt.get(p, 0):>14}" for p in PHASES))
    print(f"{'ИТОГО':<28}" + "".join(f"{total[p]:>14}" for p in PHASES))
    return 0


def cmd_answer(a):
    p = path(a.key, "open-questions.md")
    text = read(a.key, "open-questions.md")
    pat = re.compile(rf"^- {re.escape(a.qid)} \[открыт\] (.*)$", re.M)
    m = pat.search(text)
    if not m:
        print(f"открытого вопроса {a.qid} нет", file=sys.stderr)
        return 1
    new = pat.sub(lambda mm: f"- {a.qid} [закрыт] {mm.group(1)}", text, count=1)
    with open(p, "w", encoding="utf-8") as f:
        f.write(new)
    append(a.key, "answers.md", f"- {a.qid}: {a.answer.strip()} (источник: {a.source or 'не указан'})\n")
    events.emit(a.key, "question_answered", qid=a.qid)
    print(f"{a.qid} закрыт")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("key"); p.set_defaults(f=cmd_init)
    p = sub.add_parser("add"); p.add_argument("key"); p.add_argument("--text", required=True)
    p.add_argument("--source"); p.add_argument("--version"); p.add_argument("--status", required=True)
    p.add_argument("--note"); p.set_defaults(f=cmd_add)
    p = sub.add_parser("check"); p.add_argument("key"); p.set_defaults(f=cmd_check)
    p = sub.add_parser("ask"); p.add_argument("key"); p.add_argument("question")
    p.add_argument("--checked", required=True); p.add_argument("--blocks")
    p.add_argument("--phase", default="analysis", choices=PHASES); p.set_defaults(f=cmd_ask)
    p = sub.add_parser("stats"); p.add_argument("key", nargs="?"); p.set_defaults(f=cmd_stats)
    p = sub.add_parser("answer"); p.add_argument("key"); p.add_argument("qid"); p.add_argument("answer")
    p.add_argument("--source"); p.set_defaults(f=cmd_answer)
    a = ap.parse_args()
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
