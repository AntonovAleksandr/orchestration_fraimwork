#!/usr/bin/env bash
# Подключить хуки воркспейса в .claude/settings.json текущего дерева (файл не в git,
# поэтому ставится в каждое дерево отдельно). Повторный запуск ничего не дублирует.
#   scripts/orch/install-hooks.sh [корень дерева]
set -euo pipefail
ROOT=${1:-"$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"}
python3 - "$ROOT" <<'PY'
import json, os, sys
root = sys.argv[1]; p = os.path.join(root, ".claude", "settings.json")
d = json.load(open(p)) if os.path.exists(p) else {}
hooks = d.setdefault("hooks", {})
# Команда молчит, если в дереве ещё нет скрипта (ветка без хуков): python3 на несуществующий
# файл выходит с кодом 2, а для UserPromptSubmit код 2 блокирует реплику.
def guarded(name):
    f = '"$CLAUDE_PROJECT_DIR/scripts/orch/hooks/%s"' % name
    return '[ -f %s ] && python3 %s || true' % (f, f)
MCP_WRITE = ("mcp__[A-Za-z0-9_-]+__[A-Za-z0-9_]*(add_comment|create_issue|transition_issue|update_issue|link_issues"
             "|add_merge_request_note|approve_merge_request|unapprove_merge_request"
             "|create_merge_request_thread|reply_merge_request_thread|resolve_merge_request_thread"
             "|create_merge_request_draft_note|publish_merge_request_draft_notes)")
want = [
  ("UserPromptSubmit", None, guarded("skill-router.py")),
  ("PreToolUse", "Bash", guarded("mr-gate.py")),
  ("PreToolUse", "Bash", guarded("git-guard.py")),
  ("PreToolUse", "Bash", guarded("merge-guard.py")),
  ("PreToolUse", "Bash|" + MCP_WRITE, guarded("approval-guard.py")),
]
for ev, matcher, cmd in want:
    lst = hooks.setdefault(ev, [])
    name = cmd.split("/hooks/")[1].split('"')[0]
    # старую незащищённую запись того же хука заменить
    for g in lst:
        g["hooks"] = [h for h in g.get("hooks", []) if not (name in h.get("command", "") and h.get("command") != cmd)]
    lst[:] = [g for g in lst if g.get("hooks")]
    if any(h.get("command") == cmd for g in lst for h in g.get("hooks", [])):
        continue
    g = {"hooks": [{"type": "command", "command": cmd, "timeout": 5}]}
    if matcher: g["matcher"] = matcher
    lst.append(g)
os.makedirs(os.path.dirname(p), exist_ok=True)
json.dump(d, open(p, "w"), ensure_ascii=False, indent=2)
print("хуки подключены:", p)
PY
