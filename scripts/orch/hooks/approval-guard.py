#!/usr/bin/env python3
"""PreToolUse: внешние записи требуют подтверждения пользователя.

Покрывает: записи в GitLab через `glab` (mr/issue create|note|approve|update|merge|close|
reopen|delete, `glab api` с не-GET методом или полями) и через MCP-инструменты
трекера и VCS-хостинга, которые меняют данные. Черновик (draft) подтверждением не считается.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _approval  # noqa: E402

APPROVE_SELF = re.compile(r"(?:^|[;&(]\s*)(?:bash\s+|\./)?(?:\S*/)?approve\.sh\b")
GLAB_WRITE = re.compile(r"(?:^|[;&(]\s*)glab\s+(?:mr|issue)\s+(?:create|note|approve|update|merge|close|reopen|delete)\b")
GLAB_API = re.compile(r"(?:^|[;&(]\s*)glab\s+api\b")
API_WRITE = re.compile(r"(?:-X|--method)[\s=]*(?:POST|PUT|PATCH|DELETE)\b|(?:^|\s)(?:-f|-F|--field|--raw-field)[\s=]")
MCP_WRITE = re.compile(r"^mcp__[\w-]+__\w*(?:add_comment|create_issue|transition_issue|update_issue|link_issues"
                       r"|add_merge_request_note|approve_merge_request|unapprove_merge_request"
                       r"|create_merge_request_thread|reply_merge_request_thread|resolve_merge_request_thread"
                       r"|create_merge_request_draft_note|publish_merge_request_draft_notes)$")


# Комментарии в запрос на слияние из ветки задачи агент пишет сам (D-016); слияние, approve, создание — нет.
MR_NOTE = re.compile(r"(?:^|[;&(]\s*)glab\s+mr\s+note\s+!?(\d+)\b")
MR_API_NOTE = re.compile(r"(?:^|[;&(]\s*)glab\s+api\s+\S*merge_requests/(\d+)/(?:notes|discussions)\b")
# Ключ задачи: ORCH_TASK_KEY_RE либо «слово-число», кроме релизных веток (release-26, hotfix-3).
_KEY_RE = os.environ.get("ORCH_TASK_KEY_RE") or r"(?<![A-Za-z0-9])(?!(?:release|hotfix|rc|v)-)[A-Za-z][A-Za-z0-9]*-\d+"
TASK_BRANCH = re.compile(_KEY_RE, re.I)


def _current_branch(cwd):
    try:
        return subprocess.run(["git", "-C", cwd, "branch", "--show-current"], capture_output=True,
                              text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


def _mr_source_branch(number, cwd):
    try:
        out = subprocess.run(["glab", "mr", "view", str(number), "--output", "json"], cwd=cwd,
                             capture_output=True, text=True, timeout=15).stdout
        return json.loads(out).get("source_branch") or ""
    except Exception:
        return ""


def own_mr_note(cmd, cwd):
    """Комментарий в запрос на слияние из ветки текущей задачи — без подтверждения (D-016)."""
    m = MR_NOTE.search(cmd)
    if not m and API_WRITE.search(cmd):
        m = MR_API_NOTE.search(cmd)
    if not m:
        return False
    branch = _current_branch(cwd)
    if not branch or not TASK_BRANCH.search(branch):
        return False
    return _mr_source_branch(int(m.group(1)), cwd) == branch


def external(data):
    name = data.get("tool_name") or ""
    if name == "Bash":
        cmd = (data.get("tool_input") or {}).get("command") or ""
        if APPROVE_SELF.search(cmd):
            return "SELF_APPROVE"
        if (GLAB_WRITE.search(cmd) or GLAB_API.search(cmd)) and own_mr_note(cmd, data.get("cwd") or os.getcwd()):
            return None
        if GLAB_WRITE.search(cmd):
            return f"bash: {cmd}"
        if GLAB_API.search(cmd) and API_WRITE.search(cmd):
            return f"bash: {cmd}"
        return None
    if MCP_WRITE.match(name):
        return f"{name} {json.dumps(data.get('tool_input') or {}, sort_keys=True, ensure_ascii=False)}"
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    action = external(data)
    if action is None:
        return
    if action == "SELF_APPROVE":
        _approval.deny("approve.sh запускает только человек: команда `!scripts/orch/approve.sh <код>` в сессии. "
                       "Работнику подтверждать действия нельзя.")
    left = _approval.consume_or_request(action, data.get("cwd") or os.getcwd())
    if left is None:
        return
    _approval.deny(left)


if __name__ == "__main__":
    main()
