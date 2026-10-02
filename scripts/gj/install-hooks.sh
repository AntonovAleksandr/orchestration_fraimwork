#!/usr/bin/env bash
# Подключить хуки воркспейса GJ в .claude/settings.json текущего дерева (файл не в git,
# поэтому ставится в каждое дерево отдельно). Повторный запуск ничего не дублирует.
#   scripts/gj/install-hooks.sh [корень дерева]
set -euo pipefail
ROOT=${1:-"$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"}
python3 - "$ROOT" <<'PY'
import json, os, sys
root = sys.argv[1]; p = os.path.join(root, ".claude", "settings.json")
d = json.load(open(p)) if os.path.exists(p) else {}
hooks = d.setdefault("hooks", {})
# Команда молчит, если в дереве ещё нет скрипта (ветка без хуков): python3 на отсутствующий
# файл выходит с кодом 2, а для UserPromptSubmit код 2 блокирует реплику.
def guarded(name):
    f = '"$CLAUDE_PROJECT_DIR/scripts/gj/hooks/%s"' % name
    return '[ -f %s ] && python3 %s || true' % (f, f)
want = {
  "UserPromptSubmit": (None, guarded("skill-router.py")),
  "PreToolUse": ("Bash", guarded("mr-gate.py")),
}
for ev, (matcher, cmd) in want.items():
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
