#!/usr/bin/env python3
"""PreToolUse(Bash): не сливать MR, пока в отчёте его ревью открыт блокер или важное.

Ловит `glab mr merge <номер> [--repo <проект>]`. Отчёт ищется в
.tasks/review-<последний сегмент проекта>-<номер>/report.md. Если отчёта нет —
слияние не блокируется: проверяются только MR, для которых ревью вёлся через оркестратор.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import findings  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _approval  # noqa: E402

MERGE = re.compile(r"(?:^|[;&(]\s*)glab\s+mr\s+merge\s+!?(\d+)")
REPO = re.compile(r"--repo[=\s]+(\S+)")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if data.get("tool_name") != "Bash":
        return
    cmd = (data.get("tool_input") or {}).get("command") or ""
    m = MERGE.search(cmd)
    if not m:
        return
    cwd = data.get("cwd") or os.getcwd()
    number = m.group(1)
    r = REPO.search(cmd)
    project = r.group(1).rstrip("/").split("/")[-1] if r else None
    if project is None:
        return
    root = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    tasks = os.environ.get("ORCH_TASKS_DIR") or os.path.join(root, ".tasks")
    report = os.path.join(tasks, f"review-{slug(project)}-{number}", "report.md")
    if not os.path.isfile(report):
        return
    with open(report, encoding="utf-8") as f:
        items = findings.parse(f.read().splitlines())
    blockers = []
    for it in items:
        ok, msg = findings.judge(it, cwd)
        if not ok and findings.severity(it["title"]) in ("блокер", "важно"):
            blockers.append(msg)
    if not blockers:
        return
    left = _approval.consume_or_request(f"bash: {cmd}", cwd)
    if left is None:
        return
    _approval.deny(f"Слияние !{number} заблокировано: в ревью открыто {len(blockers)} блокирующих пунктов "
                   f"({'; '.join(blockers)[:300]}). Закрой их статусом в {report} "
                   f"(findings.py set) или прими риск владельца. {left}")


if __name__ == "__main__":
    main()
