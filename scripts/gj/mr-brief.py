#!/usr/bin/env python3
"""Сжатая выжимка запроса на слияние для агентского ревью.

Задача — не показать агенту весь дифф, а показать каждое РАЗНОЕ изменение по
одному разу. В наборе клиентов OPSOMN002-232 было 1 748 изменённых файлов и
всего 6 различных правок: остальное — та же правка, размноженная генератором.
Выжимка из таких запросов весит 3–5 тыс. токенов вместо 400–600 тыс.

    mr-brief.py <адрес запроса> [--out файл] [--max-samples N]
    mr-brief.py <проект> <iid>

Дифф считается локальным git в кеш-клоне: интерфейс GitLab при большом наборе
молча отдаёт пустые диффы (на cms!7 — у 566 файлов из 587), и ревью по нему
получается слепым. Из интерфейса берутся только описание и вершины.

Токен берётся из ~/.config/gj/gitlab_pat (как и у остальных скриптов GJ).
Кеш клонов — ~/.cache/gj-mr-brief, переопределяется GJ_MR_CACHE.
"""
import os, re, sys, json, argparse, hashlib, subprocess, collections
from urllib.parse import quote

HOST = "gitlab.gloria.aaanet.ru"
IP = os.environ.get("GJ_GITLAB_IP", "10.61.64.83")
PAT_FILE = os.path.expanduser("~/.config/gj/gitlab_pat")
CACHE = os.environ.get("GJ_MR_CACHE", os.path.expanduser("~/.cache/gj-mr-brief"))


def api(path, token):
    """Запрос к GitLab. Прокси обходим: в окружении стоит HTTPS_PROXY для Claude."""
    url = f"https://{HOST}/api/v4/{path}"
    r = subprocess.run(
        ["curl", "-4", "-s", "--noproxy", "*", "--resolve", f"{HOST}:443:{IP}",
         "--connect-timeout", "15", "--max-time", "120",
         "-H", f"PRIVATE-TOKEN: {token}", url],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl вернул {r.returncode}: {r.stderr[:200]}")
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"не JSON от {path}: {r.stdout[:200]}")


def parse_url(u):
    m = re.search(r"https?://[^/]+/(.+?)/-/merge_requests/(\d+)", u)
    if not m:
        return None
    return m.group(1), int(m.group(2))


def git(args, cwd=None, check=True):
    r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])}: {r.stderr.strip()[:200]}")
    return r.stdout


def local_diff(proj, dr, token):
    """Полный дифф из кеш-клона. Возвращает список изменений в форме интерфейса."""
    os.makedirs(CACHE, exist_ok=True)
    repo = os.path.join(CACHE, proj.replace("/", "_"))
    url = f"https://oauth2:{token}@{HOST}/{proj}.git"
    if not os.path.isdir(os.path.join(repo, ".git")):
        git(["clone", "--quiet", "--filter=blob:none", "--no-checkout", url, repo])
    base, head = dr.get("base_sha"), dr.get("head_sha")
    if not base or not head:
        raise RuntimeError("в запросе нет base_sha/head_sha")
    # тянем ровно две вершины — веток может уже не быть
    git(["fetch", "--quiet", url, base, head], cwd=repo)
    raw = git(["diff", "--no-color", "--no-ext-diff", f"{base}..{head}"], cwd=repo)

    changes, cur = [], None
    for line in raw.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if cur: changes.append(cur)
            m = re.match(r"diff --git a/(.+?) b/(.+)", line.rstrip())
            cur = {"old_path": m.group(1) if m else "?", "new_path": m.group(2) if m else "?",
                   "new_file": False, "deleted_file": False, "renamed_file": False, "_d": []}
        elif cur is not None:
            if line.startswith("new file"): cur["new_file"] = True
            elif line.startswith("deleted file"): cur["deleted_file"] = True
            elif line.startswith("rename "): cur["renamed_file"] = True
            elif line.startswith(("@@", "+", "-", " ", "\\")): cur["_d"].append(line)
    if cur: changes.append(cur)
    for c in changes:
        c["diff"] = "".join(c.pop("_d"))
    return changes


def normalize(diff):
    """Свёртка дифа к «форме правки»: имена и числа стираются, остаётся структура.

    Благодаря этому 553 одинаковых правки в DTO схлопываются в одну строку.
    """
    out = []
    for line in diff.splitlines():
        if not line or line[0] not in "+-":
            continue
        if line.startswith(("+++", "---")):
            continue
        s = line[1:].strip()
        s = re.sub(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", "N", s)   # имена
        s = re.sub(r"\d+", "9", s)                              # числа
        s = re.sub(r"\s+", " ", s)
        out.append(line[0] + s)
    return hashlib.sha1("\n".join(out).encode()).hexdigest()[:12], len(out)


def trim(diff, keep=26):
    """Обрезает дифф до первых значимых строк — для образца этого достаточно."""
    lines = [l for l in diff.splitlines() if l[:1] in "+- @"]
    if len(lines) <= keep:
        return "\n".join(lines)
    return "\n".join(lines[:keep] + [f"… ещё {len(lines)-keep} строк"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target"); ap.add_argument("iid", nargs="?")
    ap.add_argument("--out"); ap.add_argument("--max-samples", type=int, default=12)
    a = ap.parse_args()

    if not os.path.exists(PAT_FILE):
        print(f"нет токена: {PAT_FILE}", file=sys.stderr); return 2
    token = open(PAT_FILE).read().strip()

    if a.iid:
        proj, iid = a.target, int(a.iid)
    else:
        p = parse_url(a.target)
        if not p:
            print("не разобрал адрес запроса", file=sys.stderr); return 2
        proj, iid = p
    pid = quote(proj, safe="")

    mr = api(f"projects/{pid}/merge_requests/{iid}", token)
    if "iid" not in mr:
        print(f"запрос не найден: {mr}", file=sys.stderr); return 2
    source = "локальный git"
    try:
        changes = local_diff(proj, mr.get("diff_refs") or {}, token)
    except Exception as e:
        print(f"локальный дифф не получился ({e}); беру из интерфейса — "
              f"он может быть неполным", file=sys.stderr)
        ch = api(f"projects/{pid}/merge_requests/{iid}/changes", token)
        changes = ch.get("changes", [])
        source = "интерфейс GitLab (возможны пропуски)"
    changes = [c for c in changes if c.get("diff")]

    groups = collections.defaultdict(list)
    sizes = {}
    for c in changes:
        d = c.get("diff", "")
        sig, n = normalize(d)
        groups[sig].append(c)
        sizes[sig] = max(sizes.get(sig, 0), n)

    order = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    total_lines = sum(sizes[s] * len(g) for s, g in order)

    L = []
    W = L.append
    W(f"# {mr.get('title','')}")
    W("")
    W(f"- запрос: {mr.get('web_url')}")
    W(f"- состояние: {mr.get('state')}" + ("  ЧЕРНОВИК" if mr.get("draft") else ""))
    W(f"- ветки: `{mr.get('source_branch')}` → `{mr.get('target_branch')}`")
    dr = mr.get("diff_refs") or {}
    W(f"- вершина: `{(dr.get('head_sha') or '')[:12]}`  база: `{(dr.get('base_sha') or '')[:12]}`")
    W(f"- автор: {(mr.get('author') or {}).get('name','')}")
    W("")
    W(f"**{len(changes)} изменённых файлов · {len(order)} различных правок · ~{total_lines} изменённых строк**")
    W(f"<sub>источник диффа: {source}</sub>")
    W("")
    if len(changes) > len(order) * 3:
        W(f"> Дифф размножен: {len(changes)} файлов несут всего {len(order)} разных правок. "
          f"Ниже каждая правка показана один раз с числом повторов.")
        W("")

    for i, (sig, files) in enumerate(order[:a.max_samples], 1):
        paths = [f.get("new_path") or f.get("old_path") for f in files]
        W(f"## Правка {i} — повторов: {len(files)}")
        flags = []
        if any(f.get("new_file") for f in files): flags.append("новые файлы")
        if any(f.get("deleted_file") for f in files): flags.append("удаления")
        if any(f.get("renamed_file") for f in files): flags.append("переименования")
        if flags: W(f"*{', '.join(flags)}*")
        show = paths[:4]
        W("Файлы: " + ", ".join(f"`{p}`" for p in show) +
          (f" … и ещё {len(paths)-len(show)}" if len(paths) > len(show) else ""))
        W("")
        W("```diff")
        W(trim(files[0].get("diff", "")))
        W("```")
        W("")
    if len(order) > a.max_samples:
        rest = sum(len(g) for _, g in order[a.max_samples:])
        W(f"*(ещё {len(order)-a.max_samples} редких правок в {rest} файлах — запрашивать точечно)*")

    text = "\n".join(L)
    if a.out:
        open(a.out, "w").write(text)
        kb = len(text.encode()) / 1000
        print(f"{a.out}  ({kb:.1f} КБ ≈ {kb*1000/4000:.0f} тыс. токенов, "
              f"вместо {len(changes)} диффов)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
