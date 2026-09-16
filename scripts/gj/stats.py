#!/usr/bin/env python3
"""Аналитика по журналам сессий: куда уходит расход и меняется ли он со временем.

Цель — не урезать глубину, а видеть, за что платим, и сравнивать периоды между собой.

    stats.py                     сводка за всё время
    stats.py --days 14           только последние 14 дней
    stats.py --compare 14        последние 14 дней против предыдущих 14
    stats.py --phases            структура расхода по фазам работы
    stats.py --sinks             куда уходит объём: инструменты и отдельные вызовы
    stats.py --waste             потери: ошибки, отказы, повторные чтения
    stats.py --skills            использование скиллов и подагентов, цена эпизодов
    stats.py --skill-effect      эффективность: сессии со скиллом против сессий без
    stats.py --workers           сессии-работники orca (их расход виден, в отличие от подагентов)
    stats.py --snapshot ФАЙЛ     записать замер в JSON (для сравнения потом)
    stats.py --baseline ФАЙЛ     сравнить текущее состояние с записанным замером

Фазы определяются по составу инструментов в ходе — отдельной разметки не требуется.

Один ответ модели пишется в журнал несколькими записями с общим usage — они
склеиваются по requestId, иначе контекст считается по нескольку раз (в сыром виде
завышение примерно вдвое).

СЛЕПОЕ ПЯТНО. Ходы подагентов в журналах не сохраняются вообще: их расход не виден
ни здесь, ни где-либо ещё на диске. Все числа ниже — только родительские сессии,
то есть нижняя граница. Экономию от делегирования этот инструмент показать не может,
он показывает лишь то, что делегирование убрало из родителя.
"""
import os, sys, json, glob, argparse, collections, datetime, statistics as st

ROOT = os.path.expanduser("~/.claude/projects")

# Инструмент → фаза работы. Ход относится к фазе по первому совпавшему инструменту.
PHASE_BY_TOOL = {
    "jira": "1 постановка", "confluence": "1 постановка", "documents_": "1 постановка",
    "Agent": "2 разведка", "Explore": "2 разведка", "codegraph": "2 разведка",
    "Grep": "2 разведка", "Glob": "2 разведка", "Read": "2 разведка",
    "Edit": "3 правка", "Write": "3 правка", "NotebookEdit": "3 правка",
    "gitlab_": "5 ревью",
    "data_logs": "6 разбор данных", "data_pg": "6 разбор данных", "data_k8s": "6 разбор данных",
    "Artifact": "7 отчёт",
}
# Команды Bash, по которым ход относится к контролю
CONTROL_HINTS = ("pest", "phpunit", "jest", "phpstan", "cs-fixer", "tsc", "golden.sh",
                 "visual-check", "yarn test", "npm test", "detox")


def phase_of(tools, bash_cmds):
    for c in bash_cmds:
        if any(h in c for h in CONTROL_HINTS):
            return "4 контроль"
    for t in tools:
        for key, ph in PHASE_BY_TOOL.items():
            if key in t:
                return ph
    if tools:
        return "0 оболочка"
    return "8 рассуждение"


def load(days=None, until=None):
    """Проходит журналы и возвращает поход`овые записи."""
    cutoff = None
    if days:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    upper = until

    turns = []      # {ts, ctx, out, phase, sid, tools, errs}
    files = collections.Counter()
    reread = collections.Counter()
    sinks = collections.Counter()
    sink_n = collections.Counter()
    errs = collections.Counter()
    skills = collections.Counter()
    sess_skills = collections.defaultdict(set)
    workers = {}
    delegs = collections.Counter()
    sess_review = set()
    sess_ctx = collections.Counter()
    sess_turns = collections.Counter()
    humans = 0

    for path in glob.glob(f"{ROOT}/*/*.jsonl"):
        sid = os.path.basename(path)[:8]
        idmap, inmap = {}, {}
        seen_req = {}          # requestId → индекс хода: один вызов API = один ход
        for line in open(path, errors="replace"):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = r.get("timestamp")
            dt = None
            if ts:
                try:
                    dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    dt = None
            if dt and cutoff and dt < cutoff:
                continue
            if dt and upper and dt >= upper:
                continue
            if "orca-workspaces" in path or "orca/workspaces" in path:
                w = workers.setdefault(sid, {"ctx": 0, "n": 0,
                                             "proj": os.path.basename(os.path.dirname(path)).split("-platform-")[-1]})
                if r.get("type") == "assistant":
                    _u = r.get("message", {}).get("usage", {})
                    _c = (_u.get("input_tokens", 0) + _u.get("cache_read_input_tokens", 0)
                          + _u.get("cache_creation_input_tokens", 0))
                    if _c > 1000 and (r.get("requestId") or "") not in seen_req:
                        w["ctx"] += _c; w["n"] += 1

            t = r.get("type")
            if t == "assistant":
                m = r.get("message", {})
                u = m.get("usage", {})
                ctx = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                       + u.get("cache_creation_input_tokens", 0))
                if ctx <= 1000:
                    continue
                # Один ответ пишется несколькими записями (thinking / text / tool_use)
                # с ОДНИМ usage. Без этой склейки контекст считается по нескольку раз.
                req = r.get("requestId") or m.get("id") or r.get("uuid")
                first = req not in seen_req
                tools, cmds = [], []
                for c in m.get("content", []) or []:
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        n = c.get("name", "?")
                        tools.append(n)
                        idmap[c.get("id")] = n
                        inmap[c.get("id")] = c.get("input", {}) or {}
                        if n == "Bash":
                            cmds.append((c.get("input", {}) or {}).get("command", "")[:300])
                        if n == "Read":
                            fp = (c.get("input", {}) or {}).get("file_path", "")
                            if fp:
                                files[fp] += 1
                        if n == "Skill":
                            _sk = (c.get("input", {}) or {}).get("skill", "?")
                            skills[_sk] += 1
                            sess_skills[_sk].add(sid)
                        if n == "Agent":
                            delegs[(c.get("input", {}) or {}).get("subagent_type", "(по умолчанию)")] += 1
                        if "gitlab" in n or n == "Skill" and "review" in str(c.get("input", {})):
                            sess_review.add(sid)
                if first:
                    seen_req[req] = len(turns)
                    turns.append({"ts": dt, "ctx": ctx, "out": u.get("output_tokens", 0),
                                  "phase": phase_of(tools, cmds), "sid": sid,
                                  "ntools": len(tools), "tools": list(tools), "cmds": list(cmds)})
                    sess_ctx[sid] += ctx
                    sess_turns[sid] += 1
                else:
                    # добор инструментов из остальных записей того же вызова
                    x = turns[seen_req[req]]
                    x["tools"] += tools
                    x["cmds"] += cmds
                    x["ntools"] += len(tools)
                    x["phase"] = phase_of(x["tools"], x["cmds"])
            elif t == "user":
                cont = r.get("message", {}).get("content")
                if isinstance(cont, str):
                    if not cont.startswith("<") and (r.get("origin", {}).get("kind") == "human"
                                                     or r.get("promptSource") == "typed"):
                        humans += 1
                elif isinstance(cont, list):
                    for c in cont:
                        if isinstance(c, dict) and c.get("type") == "tool_result":
                            n = idmap.get(c.get("tool_use_id"), "?")
                            b = len(json.dumps(c.get("content"), ensure_ascii=False))
                            sinks[n] += b
                            sink_n[n] += 1
                            if c.get("is_error"):
                                errs[n] += 1
    for f, n in files.items():
        if n > 1:
            reread[f] = n
    return {"turns": turns, "sinks": sinks, "sink_n": sink_n, "errs": errs,
            "humans": humans, "reread": reread, "skills": skills, "delegs": delegs,
            "sess_review": sess_review, "sess_ctx": sess_ctx, "sess_turns": sess_turns,
            "sess_skills": {k: v for k, v in sess_skills.items()}, "workers": workers}


def totals(d):
    T = d["turns"]
    ctx = sum(x["ctx"] for x in T)
    out = sum(x["out"] for x in T)
    return {"ctx": ctx, "out": out, "turns": len(T), "humans": d["humans"],
            "per_turn": ctx / max(len(T), 1), "per_task": ctx / max(d["humans"], 1),
            "turns_per_task": len(T) / max(d["humans"], 1),
            "useful": 100 * out / max(ctx, 1)}


def fmt(n):
    if n >= 1e9: return f"{n/1e9:.2f} млрд"
    if n >= 1e6: return f"{n/1e6:.1f} млн"
    if n >= 1e3: return f"{n/1e3:.0f} тыс."
    return str(int(n))


def bar(frac, width=28):
    filled = int(round(frac * width))
    return "█" * filled + "·" * (width - filled)


def report_summary(d, title="СВОД"):
    t = totals(d)
    print(f"=== {title} ===")
    print(f"  расход контекста   {fmt(t['ctx']):>12}")
    print(f"  вывод модели       {fmt(t['out']):>12}   ({t['useful']:.2f}% от расхода)")
    print(f"  ходов              {t['turns']:>12,}".replace(",", " "))
    print(f"  задач              {t['humans']:>12,}".replace(",", " "))
    print(f"  на ход             {fmt(t['per_turn']):>12}")
    print(f"  на задачу          {fmt(t['per_task']):>12}   ({t['turns_per_task']:.1f} ходов)")
    if d["turns"]:
        q = sorted(x["ctx"] for x in d["turns"])
        print(f"  контекст: медиана {fmt(q[len(q)//2])}, дециль {fmt(q[int(len(q)*.9)])}, "
              f"макс {fmt(q[-1])}")


def report_phases(d):
    T = d["turns"]
    if not T:
        print("нет данных"); return
    by = collections.defaultdict(lambda: {"ctx": 0, "n": 0})
    for x in T:
        by[x["phase"]]["ctx"] += x["ctx"]
        by[x["phase"]]["n"] += 1
    tot = sum(v["ctx"] for v in by.values())
    print("=== СТРУКТУРА РАСХОДА ПО ФАЗАМ ===")
    print(f"  {'фаза':<18} {'расход':>10} {'доля':>7} {'ходов':>7} {'на ход':>9}")
    for ph, v in sorted(by.items(), key=lambda kv: -kv[1]["ctx"]):
        share = v["ctx"] / tot
        print(f"  {ph:<18} {fmt(v['ctx']):>10} {100*share:>6.1f}% {v['n']:>7} "
              f"{fmt(v['ctx']/v['n']):>9}  {bar(share)}")
    print("\n  Фазы определены по составу инструментов в ходе; «оболочка» — ходы только с Bash,")
    print("  «рассуждение» — ходы без инструментов вообще.")


def report_sinks(d):
    s, n = d["sinks"], d["sink_n"]
    tot = sum(s.values())
    if not tot:
        print("нет данных"); return
    print(f"=== КУДА УХОДИТ ОБЪЁМ (всего {tot/1e6:.0f} МБ ≈ {fmt(tot/4)} токенов) ===")
    print(f"  {'инструмент':<40} {'объём':>9} {'вызовов':>8} {'на вызов':>10} {'доля':>6}")
    for k, v in sorted(s.items(), key=lambda x: -x[1])[:14]:
        print(f"  {k[:40]:<40} {v/1e6:>7.1f}МБ {n[k]:>8} {v/max(n[k],1):>9.0f}Б "
              f"{100*v/tot:>5.1f}%")


def report_waste(d):
    print("=== ПОТЕРИ ===")
    e = d["errs"]
    print(f"  отказов инструментов: {sum(e.values())}")
    for k, v in sorted(e.items(), key=lambda x: -x[1])[:6]:
        print(f"      {k[:40]:<40} {v}")
    rr = d["reread"]
    extra = sum(n - 1 for n in rr.values())
    print(f"\n  повторные чтения одного файла: {len(rr)} файлов, {extra} лишних чтений")
    for f, n in sorted(rr.items(), key=lambda x: -x[1])[:6]:
        print(f"      {n}× {os.path.basename(f)[:56]}")
    T = d["turns"]
    if T:
        idle = sum(1 for x in T if x["ntools"] == 0)
        print(f"\n  ходов без инструментов (только текст/рассуждение): {idle} "
              f"({100*idle/len(T):.0f}%) — {fmt(sum(x['ctx'] for x in T if x['ntools']==0))}")
        print("      это ответы пользователю и рассуждение; каждый перечитывает весь контекст")


def report_skills(d):
    sk, dg = d["skills"], d["delegs"]
    T = d["turns"]
    print("=== СКИЛЛЫ И ДЕЛЕГИРОВАНИЕ ===")
    print(f"  загрузок скиллов: {sum(sk.values())} на {len(T)} ходов "
          f"({100*sum(sk.values())/max(len(T),1):.2f}% ходов)")
    for k, v in sk.most_common(16):
        print(f"      {k[:40]:<40} {v:>4}")
    print(f"\n  делегирований подагентам: {sum(dg.values())} "
          f"({100*sum(dg.values())/max(len(T),1):.2f}% ходов)")
    for k, v in dg.most_common(10):
        print(f"      {k[:40]:<40} {v:>4}")

    rev = d["sess_review"]
    sc, stn = d["sess_ctx"], d["sess_turns"]
    if rev:
        rc = sum(sc[s] for s in rev if s in sc)
        rt = sum(stn[s] for s in rev if s in stn)
        oc = sum(v for k, v in sc.items() if k not in rev)
        ot = sum(v for k, v in stn.items() if k not in rev)
        print(f"\n  сессии, где велось ревью: {len(rev)}")
        print(f"      расход {fmt(rc)} за {rt} ходов — {fmt(rc/max(rt,1))} на ход")
        print(f"      прочие сессии: {fmt(oc/max(ot,1))} на ход")
    print("\n  ВНИМАНИЕ: расход подагентов в журналы не попадает. Делегирование убирает")
    print("  разбор из родителя, но его собственная цена отсюда не видна — она есть только")
    print("  в биллинге. Вывод «делегировать дешевле» этими данными НЕ доказывается.")


def report_skill_effect(d):
    """Сравнивает сессии, где скилл грузился, с сессиями без него.

    Это не доказательство причинности: скиллы грузятся на более сложных задачах.
    Но систематический перекос виден, и его стоит объяснять."""
    T = d["turns"]
    by = collections.defaultdict(lambda: {"ctx": 0, "n": 0, "err": 0})
    for x in T:
        b = by[x["sid"]]
        b["ctx"] += x["ctx"]; b["n"] += 1
    sk = d["sess_skills"]
    print("=== ЭФФЕКТИВНОСТЬ СКИЛЛОВ ===")
    print("  сессия, где скилл грузился хотя бы раз, против остальных\n")
    print(f"  {'скилл':<30} {'сессий':>7} {'на ход':>10} {'без него':>10} {'разница':>9}")
    allsid = set(by)
    for name, sids in sorted(sk.items(), key=lambda kv: -len(kv[1])):
        w = [by[s] for s in sids if s in by]
        o = [by[s] for s in allsid - set(sids) if s in by]
        if not w or not o:
            continue
        wp = sum(x["ctx"] for x in w) / max(sum(x["n"] for x in w), 1)
        op = sum(x["ctx"] for x in o) / max(sum(x["n"] for x in o), 1)
        d_ = 100 * (wp - op) / op if op else 0
        print(f"  {name[:30]:<30} {len(w):>7} {fmt(wp):>10} {fmt(op):>10} {d_:>+8.0f}%")
    print("\n  Отрицательная разница — сессии со скиллом дешевле на ход. Причинности тут нет:")
    print("  скиллы грузят на сложных задачах, и это тянет цифру вверх. Смотреть на тренд")
    print("  одного скилла между периодами (--compare), а не на сравнение скиллов между собой.")


def report_workers(d):
    """Сессии-работники orca. Их расход виден; внутренние подагенты — нет."""
    w = d["workers"]
    print("=== РАБОТНИКИ ORCA ===")
    if not w:
        print("  не найдено")
    else:
        tot = sum(v["ctx"] for v in w.values())
        print(f"  сессий-работников: {len(w)}, расход {fmt(tot)}")
        print(f"  {'сессия':<12} {'рабочее дерево':<26} {'расход':>10} {'ходов':>7}")
        for sid, v in sorted(w.items(), key=lambda kv: -kv[1]["ctx"])[:12]:
            print(f"  {sid:<12} {v['proj'][:26]:<26} {fmt(v['ctx']):>10} {v['n']:>7}")
    print("\n  Работники orca — обычные сессии, поэтому их расход виден здесь полностью.")
    print("  Внутренние подагенты (инструмент Agent) не логируются вовсе: переводя")
    print("  делегирование на orca, вы делаете цену делегирования измеримой.")


def snapshot(d):
    t = totals(d)
    t["ts"] = datetime.datetime.now().isoformat(timespec="seconds")
    by = collections.defaultdict(int)
    for x in d["turns"]:
        by[x["phase"]] += x["ctx"]
    t["phases"] = dict(by)
    return t


def compare(a, b, la, lb):
    print(f"=== {la}  ПРОТИВ  {lb} ===")
    rows = [("расход", "ctx", fmt), ("ходов", "turns", lambda x: f"{x:,}".replace(",", " ")),
            ("задач", "humans", lambda x: str(x)),
            ("на ход", "per_turn", fmt), ("на задачу", "per_task", fmt),
            ("ходов на задачу", "turns_per_task", lambda x: f"{x:.1f}"),
            ("полезная доля,%", "useful", lambda x: f"{x:.2f}")]
    print(f"  {'показатель':<18} {la:>14} {lb:>14} {'изменение':>12}")
    for name, key, f in rows:
        va, vb = a.get(key, 0), b.get(key, 0)
        if vb:
            delta = 100 * (va - vb) / vb
            if abs(delta) < 0.5:
                ch = "без изменений"
            else:
                mark = "лучше" if (delta < 0) != (key == "useful") else "хуже"
                ch = f"{delta:+.0f}% {mark}"
        else:
            ch = "—"
        print(f"  {name:<18} {f(va):>14} {f(vb):>14} {ch:>12}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int)
    ap.add_argument("--compare", type=int, metavar="N",
                    help="последние N дней против предыдущих N")
    ap.add_argument("--phases", action="store_true")
    ap.add_argument("--sinks", action="store_true")
    ap.add_argument("--waste", action="store_true")
    ap.add_argument("--skills", action="store_true")
    ap.add_argument("--skill-effect", action="store_true", dest="skill_effect")
    ap.add_argument("--workers", action="store_true")
    ap.add_argument("--snapshot", metavar="ФАЙЛ")
    ap.add_argument("--baseline", metavar="ФАЙЛ")
    a = ap.parse_args()

    if a.compare:
        now = datetime.datetime.now(datetime.timezone.utc)
        mid = now - datetime.timedelta(days=a.compare)
        cur = totals(load(days=a.compare))
        prev = totals(load(days=a.compare * 2, until=mid))
        compare(cur, prev, f"{a.compare} дн.", f"пред. {a.compare}")
        return 0

    d = load(days=a.days)
    label = f"СВОД за {a.days} дн." if a.days else "СВОД за всё время"

    if a.baseline:
        base = json.load(open(a.baseline))
        compare(totals(d), base, "сейчас", base.get("ts", "замер")[:10])
        return 0

    any_report = a.phases or a.sinks or a.waste or a.skills or a.skill_effect or a.workers
    if not any_report:
        report_summary(d, label)
    if a.phases: report_phases(d)
    if a.sinks:
        if any_report: print()
        report_sinks(d)
    if a.waste:
        if any_report: print()
        report_waste(d)
    if a.skills:
        if any_report: print()
        report_skills(d)
    if a.skill_effect:
        if any_report: print()
        report_skill_effect(d)
    if a.workers:
        if any_report: print()
        report_workers(d)

    if a.snapshot:
        json.dump(snapshot(d), open(a.snapshot, "w"), ensure_ascii=False, indent=1)
        print(f"\nзамер записан: {a.snapshot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
