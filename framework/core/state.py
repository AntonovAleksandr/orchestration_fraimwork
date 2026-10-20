"""Состояние задачи: один файл state.json в каталоге задачи, переходы по разрешённой таблице.

Состояние — единственный источник правды о том, на каком этапе задача и почему она стоит. Журнал событий — история
переходов; вопросы, требования, лог гейта и вердикт приёмки — доказательства, по ним сверка проверяет state.json. Каждый переход
пишется в историю и в журнал событий. Недопустимый переход отклоняется.

Этапы:
  new            — задача заведена
  analysis       — проход требований, сбор вопросов
  waiting_input  — ждём ответа человека или аналитика; задача стоит, причина в поле reason
  implementation — доработка
  review         — ревью (свой или чужого кода)
  fixing         — исправление находок
  acceptance     — приёмка по критериям
  ready          — готово к передаче человеку (MR оформлен, стенд не трогаем)
  done           — закрыто
"""
import datetime
import json
import os
import re
import sys
import tempfile

from . import config, events, questions, releases, requirements

STATES = ("new", "analysis", "waiting_input", "implementation", "review", "fixing", "acceptance", "ready", "done")

ALLOWED = {
    "new": {"analysis", "implementation"},
    "analysis": {"waiting_input", "implementation"},
    "waiting_input": {"analysis", "implementation"},
    "implementation": {"review", "waiting_input"},
    "review": {"fixing", "acceptance", "waiting_input"},
    "fixing": {"review", "waiting_input"},
    "acceptance": {"ready", "fixing", "waiting_input"},
    "ready": {"done", "fixing"},
    "done": set(),
}


class TransitionError(ValueError):
    pass


def path(key):
    return os.path.join(config.task_dir(key), "state.json")


def load(key):
    p = path(key)
    if not os.path.isfile(p):
        return {"key": key, "state": "new", "reason": "", "history": []}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _save(key, data):
    d = config.task_dir(key)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".state-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path(key))


def transition(key, to, reason=""):
    if to not in STATES:
        raise TransitionError(f"неизвестный этап: {to}")
    data = load(key)
    current = data["state"]
    if to == current:
        return data
    if to not in ALLOWED.get(current, set()):
        raise TransitionError(f"переход {current} → {to} не разрешён")
    if to == "waiting_input" and not reason.strip():
        raise TransitionError("в ожидание ввода нужна причина: кого ждём и что")
    if to == "ready":
        f = gather_facts(key)
        blockers = []
        if f["blocking_requirements"]:
            blockers.append(f"блокирующих требований: {f['blocking_requirements']}")
        if f["open_questions"]:
            blockers.append(f"открытых вопросов: {f['open_questions']}")
        if f["last_gate"] != "ПРОЙДЕНО":
            blockers.append(f"последний гейт: {f['last_gate'] or 'не запускался'}")
        if f["acceptance"] not in ("APPROVE", "ПРИНЯТО"):
            blockers.append(f"приёмка: {f['acceptance'] or 'не проводилась'}")
        if blockers:
            raise TransitionError("в ready нельзя: " + "; ".join(blockers))
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    data["history"].append({"ts": ts, "from": current, "to": to, "reason": reason})
    data["state"] = to
    data["reason"] = reason if to == "waiting_input" else ""
    _save(key, data)
    events.emit(key, "state_changed", frm=current, to=to, reason=reason)
    return data


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("show", "set", "check"):
        print("usage: state.py show <КЛЮЧ> | set <КЛЮЧ> <этап> [--reason «…»] | check <КЛЮЧ>", file=sys.stderr)
        return 2
    if argv[0] == "check":
        div = reconcile(argv[1])
        print(f"{argv[1]}: {load(argv[1])['state']}")
        for d in div:
            print("РАСХОЖДЕНИЕ:", d)
        if not div:
            print("согласовано")
        return 1 if div else 0
    if argv[0] == "show":
        print(json.dumps(load(argv[1]), ensure_ascii=False, indent=2))
        return 0
    if len(argv) < 3:
        print("set: нужны ключ и этап", file=sys.stderr)
        return 2
    reason = ""
    if "--reason" in argv:
        i = argv.index("--reason")
        reason = argv[i + 1] if i + 1 < len(argv) else ""
    try:
        data = transition(argv[1], argv[2], reason)
    except TransitionError as e:
        print(str(e), file=sys.stderr)
        return 2
    print(f"{argv[1]}: {data['state']}")
    if data["state"] == "ready" and not releases.releases_for_task(argv[1]):
        print(f"ПРЕДУПРЕЖДЕНИЕ: задача {argv[1]} готова, но не записана ни в одну релизную карту "
              f"(scripts/orch/releases.py add …). Репозиторий может быть забыт.", file=sys.stderr)
    return 0


BLOCKING_REQ = ("конфликт", "открыто")


def _legacy_open(d):
    qp = os.path.join(d, "open-questions.md")
    if not os.path.isfile(qp):
        return []
    return re.findall(r"^- Q\d+ \[открыт\]", open(qp, encoding="utf-8").read(), re.M)


def gather_facts(key):
    """Доказательства из файлов задачи. Ничего не меняет."""
    d = config.task_dir(key)
    facts = {"open_questions": 0, "blocking_requirements": 0, "last_gate": None, "acceptance": None}
    # Вопросы живут в реестре questions.py; open-questions.md — старый файл, учитываем, пока в нём что-то открыто.
    mine = [q for q in questions.load()["questions"] if q["task"] == key and q["state"] == "открыт"]
    facts["open_questions"] = len(mine) + len(_legacy_open(d))
    facts["blocking_questions"] = sum(1 for q in mine if q["status"] == "блокер")
    facts["blocking_requirements"] = sum(1 for r in requirements.rows(key) if r[4] in BLOCKING_REQ)
    gl = os.path.join(d, "gate.log")
    if os.path.isfile(gl):
        lines = [l for l in open(gl, encoding="utf-8").read().splitlines() if l.strip()]
        if lines:
            parts = lines[-1].split("\t")
            facts["last_gate"] = parts[2] if len(parts) > 2 else None
    ap = os.path.join(d, "acceptance.md")
    if os.path.isfile(ap):
        m = re.search(r"^## вердикт:\s*(.+)$", open(ap, encoding="utf-8").read(), re.M)
        facts["acceptance"] = m.group(1).strip() if m else "без вердикта"
    return facts


def reconcile(key):
    """Расхождения state.json с доказательствами и журналом. Пустой список — согласовано."""
    data = load(key)
    st = data["state"]
    f = gather_facts(key)
    out = []
    if st == "waiting_input" and f["open_questions"] == 0 and f["blocking_requirements"] == 0:
        out.append("ожидание ввода, но открытых вопросов и блокирующих требований нет")
    if st in ("ready", "done") and f["blocking_requirements"]:
        out.append(f"{st}, но блокирующих требований: {f['blocking_requirements']}")
    if st in ("ready", "done") and f["open_questions"]:
        out.append(f"{st}, но открытых вопросов: {f['open_questions']}")
    if st in ("ready", "done") and f["last_gate"] not in (None, "ПРОЙДЕНО"):
        out.append(f"{st}, но последний гейт: {f['last_gate']}")
    if st in ("ready", "done") and f["acceptance"] not in (None, "APPROVE", "ПРИНЯТО"):
        out.append(f"{st}, но вердикт приёмки: {f['acceptance']}")
    if st == "acceptance" and f["acceptance"] == "APPROVE":
        out.append("приёмка прошла (APPROVE), но состояние не переведено в ready")
    last = None
    for row in events.read(key):
        if row.get("type") == "state_changed":
            last = row.get("to")
    if data["history"] and last is not None and last != st:
        out.append(f"журнал событий говорит «{last}», state.json — «{st}»: файл правили вручную?")
    if not data["history"] and st != "new":
        out.append(f"state.json в «{st}», но истории переходов нет")
    return out
