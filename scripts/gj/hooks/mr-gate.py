#!/usr/bin/env python3
"""PreToolUse(Bash): не открывать запрос на слияние без «Самопроверки» во вводной задачи.

Ловит только создание запроса: `git … push -o merge_request.create`, `glab mr create` в начале
команды, POST на `…/merge_requests` (ровно на коллекцию, не на notes/merge/rebase/approve).
Ключ задачи — только из полей запроса: title и source_branch (в heredoc или JSON после
`--data @файл`), --title/--source-branch у glab, ветка у git push; затем из ветки каталога,
куда команда делает cd / -C (от cwd сессии). Во всём тексте команды ключ не ищется:
описание запроса может упоминать чужие задачи.
Нет ключа — не задача (слияние релизных веток), пропускаем.
Обход — только переменной среды GJ_SKIP_SELFCHECK=1 у сессии либо строкой
«Самопроверка не нужна: <причина>» во вводной.
"""
import json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import selfcheck  # noqa: E402

KEY = re.compile(r"\b(OPSOMN\d*-\d+|GJISOMS-\d+)\b", re.I)
SEP = r"[^|;&\n]*"
PUSH = re.compile(r"\bgit\b" + SEP + r"\bpush\b" + SEP + r"merge_request\.create")
GLAB = re.compile(r"(^|[;&|\n]\s*)glab\s+mr\s+create\b")
COLLECTION = re.compile(r"/merge_requests(?=[\"'\s?]|$)", re.M)
BODY = re.compile(r"(-X\s*POST|--request\s+POST|(^|\s)-d\s*\S|--data(-raw|-binary)?[\s=]|--json[\s=])")
GET = re.compile(r"(^|\s)-G(\s|$)|--get\b")

def creates_mr(cmd):
    if PUSH.search(cmd) or GLAB.search(cmd):
        return True
    return bool(COLLECTION.search(cmd) and BODY.search(cmd) and not GET.search(cmd)
                and re.search(r"\bcurl\b", cmd))

FIELD = re.compile(r"""["']?(?:source_branch|title)["']?\s*[:=]\s*["']([^"'\n]+)""")
GLAB_ARG = re.compile(r"""(?:--title|-t|--source-branch|-s)[\s=]+("[^"]*"|'[^']*'|\S+)""")

def key_from_cmd(cmd):
    vals = FIELD.findall(cmd)
    if GLAB.search(cmd):
        vals += GLAB_ARG.findall(cmd)
    for m in re.finditer(r"\bgit\b" + SEP + r"\bpush\b(" + SEP + ")", cmd):
        vals += [t for t in m.group(1).split() if not t.startswith("-") and "=" not in t]
    for v in vals:
        k = KEY.search(v)
        if k:
            return k
    return None

def key_from_file(cmd, cwd):
    for m in re.finditer(r"(?:--data(?:-binary)?|--json|-d)[\s=]*@(\S+)", cmd):
        p = m.group(1).strip("\"'")
        p = p if os.path.isabs(p) else os.path.join(cwd, p)
        try:
            d = json.load(open(p, encoding="utf-8"))
            k = KEY.search(f"{d.get('source_branch','')} {d.get('title','')}")
            if k:
                return k
        except Exception:
            continue
    return None

def branch_of(cmd, cwd):
    m = re.search(r"(?:\bcd\s+|\bgit\s+-C\s+)(\"[^\"]+\"|'[^']+'|[^\s;&|]+)", cmd)
    d = cwd
    if m:
        d = m.group(1).strip("\"'")
        d = os.path.expanduser(d) if d.startswith("~") else d
        d = d if os.path.isabs(d) else os.path.join(cwd, d)
    try:
        return subprocess.run(["git", "-C", d, "branch", "--show-current"],
                              capture_output=True, text=True, timeout=3).stdout.strip()
    except Exception:
        return ""

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if os.environ.get("GJ_SKIP_SELFCHECK") == "1" or not creates_mr(cmd):
        return
    cwd = data.get("cwd") or os.getcwd()
    m = key_from_cmd(cmd) or key_from_file(cmd, cwd) or KEY.search(branch_of(cmd, cwd))
    if not m:
        return
    key = m.group(1).upper()
    root = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    tasks = os.environ.get("GJ_TASKS_DIR") or os.path.join(root, ".tasks")
    brief = os.path.join(tasks, re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-"), "brief.md")
    err = selfcheck.check(brief)
    if err:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": f"Запрос на слияние по {key} не открыт: {err} ({brief}). Пройди раздел "
            "«Самопроверка» каждого обязательного скилла по своему диффу и запиши во вводную ответы с "
            "доказательствами, по скиллу на пункт. Если запрос не относится к задаче — сообщи пользователю, "
            "решение об обходе за ним."}}, ensure_ascii=False))

if __name__ == "__main__":
    main()
