#!/usr/bin/env python3
"""PreToolUse(Bash): запрет разрушающих git-операций без подтверждения.

Блокирует: `git add -A|--all|.` (захватывает чужие файлы), `commit --amend` для уже
опубликованного коммита, `push` с --force / -f / --force-with-lease / +refspec.
Разрешить — только через scripts/orch/approve.sh (см. _approval.py).
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _approval  # noqa: E402

ADD_ALL = re.compile(r"(?:^|[;&(]\s*)git\s+add\s+(?:-A\b|--all\b|\.(?=\s|$|;|&|\|))")
AMEND = re.compile(r"(?:^|[;&(]\s*)git\s+commit\b[^|;&\n]*--amend\b")
FORCE = re.compile(r"(?:^|[;&(]\s*)git\s+push\b[^|;&\n]*(?:--force\b|--force-with-lease\b|\s-f(?=\s|$)|\s\+\S)")


def published_head(cwd):
    try:
        out = subprocess.run(["git", "branch", "-r", "--contains", "HEAD"], cwd=cwd,
                             capture_output=True, text=True, timeout=5).stdout
        return bool(out.strip())
    except Exception:
        return False


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if data.get("tool_name") != "Bash":
        return
    cmd = (data.get("tool_input") or {}).get("command") or ""
    cwd = data.get("cwd") or os.getcwd()

    reason = None
    if ADD_ALL.search(cmd):
        reason = "git add -A/--all/. захватывает чужие файлы рабочего дерева: добавляй явные пути"
    elif AMEND.search(cmd) and published_head(cwd):
        reason = "commit --amend опубликованного коммита переписывает историю общей ветки: делай новый коммит"
    elif FORCE.search(cmd):
        reason = "force-push переписывает удалённую ветку"
    if reason is None:
        return
    left = _approval.consume_or_request(f"bash: {cmd}", cwd)
    if left is None:
        return
    _approval.deny(f"{reason}. {left}")


if __name__ == "__main__":
    main()
