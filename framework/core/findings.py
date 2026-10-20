#!/usr/bin/env python3
"""Статусы находок в отчёте ревью и проверка перед приёмкой и слиянием.

  findings.py check <report.md> [--repo PATH]   — код 1, если есть открытые блокеры или важное
  findings.py set   <report.md> F<n> "<статус>"  — записать статус находки

Находка: заголовок «### F<n>. <приоритет> — …», под ним строка «- Статус: …».
Статусы: открыто | исправлено в <sha> | принято: <владелец> | снято: <причина>.
Блокер — P0/P1 или [блокер]; важно — P2 или [важно]. Без статуса считается открытой.
"""
import argparse
import os
import re
import subprocess
import sys

from . import events

HEADER = re.compile(r"^### (F\d+)\.\s*(.*)$")
STATUS = re.compile(r"^- Статус:\s*(.*\S)\s*$")
BLOCKER = re.compile(r"\[блокер|\bP[01]\b")
IMPORTANT = re.compile(r"\[важно|\bP2\b")
SHA = re.compile(r"исправлено в\s+`?([0-9a-f]{7,40})`?")


def parse(lines):
    items, cur = [], None
    for i, line in enumerate(lines):
        m = HEADER.match(line)
        if m:
            cur = {"id": m.group(1), "title": m.group(2), "line": i, "status": None, "status_line": None}
            items.append(cur)
            continue
        if cur is None:
            continue
        if line.startswith("## ") or line.startswith("### "):
            cur = None
            continue
        s = STATUS.match(line)
        if s and cur["status"] is None:
            cur["status"] = s.group(1)
            cur["status_line"] = i
    return items


def severity(title):
    if BLOCKER.search(title):
        return "блокер"
    if IMPORTANT.search(title):
        return "важно"
    return "замечание"


def sha_exists(repo, sha):
    if not repo:
        return True
    r = subprocess.run(["git", "-C", repo, "cat-file", "-e", sha + "^{commit}"],
                       capture_output=True, text=True)
    return r.returncode == 0


def judge(item, repo):
    sev = severity(item["title"])
    st = item["status"] or "открыто"
    if sev == "замечание":
        return True, f"{item['id']} [{sev}] {st}"
    if st.startswith("принято:") and st[len("принято:"):].strip():
        return True, f"{item['id']} [{sev}] принято ({st[len('принято:'):].strip()})"
    if st.startswith("снято:") and st[len("снято:"):].strip():
        return True, f"{item['id']} [{sev}] снято"
    m = SHA.match(st)
    if m:
        if sha_exists(repo, m.group(1)):
            return True, f"{item['id']} [{sev}] исправлено в {m.group(1)}"
        return False, f"{item['id']} [{sev}] исправлено в {m.group(1)}, но коммит не найден в репозитории"
    return False, f"{item['id']} [{sev}] открыто: {item['title'][:80]}"


def cmd_check(a):
    with open(a.report, encoding="utf-8") as f:
        items = parse(f.read().splitlines())
    if not items:
        print("находок нет")
        return 0
    bad = []
    for it in items:
        ok, msg = judge(it, a.repo)
        print(("PASS " if ok else "FAIL ") + msg)
        if not ok and severity(it["title"]) in ("блокер", "важно"):
            bad.append(it["id"])
    print(f"блокирующих открыто: {len(bad)}")
    return 1 if bad else 0


def cmd_set(a):
    with open(a.report, encoding="utf-8") as f:
        lines = f.read().splitlines()
    items = parse(lines)
    it = next((x for x in items if x["id"] == a.fid), None)
    if it is None:
        print(f"находки {a.fid} нет в {a.report}", file=sys.stderr)
        return 2
    new = f"- Статус: {a.status}"
    if it["status_line"] is not None:
        lines[it["status_line"]] = new
    else:
        h = it["line"]
        if h + 1 >= len(lines) or lines[h + 1].strip():
            lines.insert(h + 1, "")
        lines.insert(h + 2, new)
        if h + 3 >= len(lines) or lines[h + 3].strip():
            lines.insert(h + 3, "")
    with open(a.report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    events.emit(os.path.basename(os.path.dirname(os.path.abspath(a.report))), "finding_status",
                review=os.path.basename(os.path.dirname(os.path.abspath(a.report))), fid=a.fid, status=a.status)
    print(f"{a.fid}: {new}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("report"); c.add_argument("--repo"); c.set_defaults(f=cmd_check)
    s = sub.add_parser("set"); s.add_argument("report"); s.add_argument("fid"); s.add_argument("status")
    s.set_defaults(f=cmd_set)
    a = ap.parse_args()
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
