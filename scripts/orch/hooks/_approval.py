"""Общая логика подтверждений внешних действий для PreToolUse-хуков.

Действие с кодом sha256(текст) блокируется, пока человек не выполнил
`scripts/orch/approve.sh <код>`. Разрешение однократное: файл удаляется при первом
совпадении. Подтверждение привязано к точному тексту действия, поэтому
изменённая команда требует нового подтверждения.
"""
import hashlib
import json
import os


def tasks_dir(cwd):
    root = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    return os.environ.get("ORCH_TASKS_DIR") or os.path.join(root, ".tasks")


def code_for(action):
    return hashlib.sha256(action.encode("utf-8")).hexdigest()[:12]


def consume_or_request(action, cwd):
    """None — действие разрешено (подтверждение израсходовано); строка — причина запрета."""
    base = os.path.join(tasks_dir(cwd), "approvals")
    code = code_for(action)
    granted = os.path.join(base, code)
    if os.path.isfile(granted):
        os.remove(granted)
        return None
    pending = os.path.join(base, "pending")
    os.makedirs(pending, exist_ok=True)
    with open(os.path.join(pending, code), "w", encoding="utf-8") as f:
        f.write(action)
    import datetime
    os.makedirs(os.path.dirname(os.path.join(tasks_dir(cwd), "hooks.log")), exist_ok=True)
    with open(os.path.join(tasks_dir(cwd), "hooks.log"), "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}\tdeny\t{code}\t{action[:120]}\n")
    return (f"Действие требует подтверждения пользователя: {action[:300]}. "
            f"Код: {code}. Пользователь подтверждает командой "
            f"scripts/orch/approve.sh {code}. Повтори действие после подтверждения. "
            "Сам подтверждение не создавай.")


def deny(reason):
    import sys
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
          "permissionDecision": "deny", "permissionDecisionReason": reason}}, ensure_ascii=False))
    sys.exit(0)
