#!/usr/bin/env python3
"""Детерминированный гейт перед сдачей задачи.

  gate.py <КЛЮЧ> [--stage done] [--repo PATH]... [--base ВЕТКА] [--no-fetch]

Источники, всё в .tasks/<ключ>/:
  repos        — пути репозиториев задачи, по одному в строке (или --repo)
  .base-branch — целевая ветка (или --base)
  gate.cmds    — проверки: «<путь репо> :: <команда>» — код выхода должен быть 0;
                 «<путь репо> :: !red[имя теста] <команда>» — на базовом коде с тестами
                 из вершины команда обязана упасть, и имя теста должно быть в выводе;
                 «<путь репо> :: !base-ok <команда>» — проверка окружения на базе,
                 обязательна для каждого !red в этом репо: если она падает, !red не
                 засчитывается.
                 Команды задаёт постановка; гейт не угадывает стек.

Проверки по репо: ветка не прод-ветка, дерево чистое, коммиты запушены, есть
изменения относительно базы, пайплайн на вершине успешен, тесты не удалены и
ассерты не ослаблены. Затем команды из gate.cmds. Результат — в gate.log.
Код 0 — пройдено, 1 — есть провалы, 2 — гейт не смог проверить.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

PROTECTED = {"master", "main", "production", "release/production"}
CMD_TIMEOUT = 1800
TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|spec)/"
    r"|(_test\.go|Tests?\.php|\.spec\.[jt]sx?|\.test\.[jt]sx?|Tests?\.cs|Tests?\.java|test_[^/]*\.py)$"
)
ASSERT_LINE = re.compile(r"assert|expect\(|should|toBe|toEqual|toHave|->see|Assert\.", re.I)


def sh(args, cwd, timeout=120):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def slug(key):
    return re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")


def is_test(path):
    return bool(TEST_PATH.search(path))


def project_path(repo):
    code, url, _ = sh(["git", "remote", "get-url", "origin"], repo)
    if code != 0 or not url:
        return None
    m = re.search(r"[:/]([^:]+?)(?:\.git)?$", url)
    return m.group(1) if m else None


def changed_files(repo, base_ref):
    code, diff, err = sh(["git", "diff", "--name-only", f"{base_ref}...HEAD"], repo)
    if code != 0:
        return None, err
    return [f for f in diff.splitlines() if f], ""


def check_tamper(repo, base_ref, files, rec):
    test_files = [f for f in files if is_test(f)]
    _, deleted, _ = sh(["git", "diff", "--diff-filter=D", "--name-only",
                        f"{base_ref}...HEAD"], repo)
    gone = [f for f in deleted.splitlines() if is_test(f)]
    rec(not gone, "тесты не удалены",
        f"удалено: {', '.join(gone)[:200]}" if gone else "")
    if not test_files:
        rec(True, "ассерты не ослаблены", "тестовых файлов в диффе нет")
        return
    _, udiff, _ = sh(["git", "diff", "--unified=0", f"{base_ref}...HEAD", "--", *test_files], repo)
    added = removed = 0
    for line in udiff.splitlines():
        if line.startswith("+") and not line.startswith("+++") and ASSERT_LINE.search(line):
            added += 1
        elif line.startswith("-") and not line.startswith("---") and ASSERT_LINE.search(line):
            removed += 1
    rec(removed <= added, "ассерты не ослаблены",
        f"строк с ассертами: удалено {removed}, добавлено {added}")


def check_repo(repo, base, fetch, results):
    name = os.path.basename(repo.rstrip("/"))

    def rec(ok, check, detail=""):
        results.append((ok, f"{name}: {check}", detail))

    if not os.path.exists(os.path.join(repo, ".git")):
        rec(False, "репозиторий", f"нет git-репозитория по пути {repo}")
        return

    code, branch, _ = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo)
    if code != 0 or branch == "HEAD":
        rec(False, "ветка", "detached HEAD — работать надо на ветке задачи")
        return
    rec(branch not in PROTECTED, "не прод-ветка", f"ветка {branch}")

    code, status, _ = sh(["git", "status", "--porcelain"], repo)
    rec(code == 0 and status == "", "рабочее дерево чистое", status[:200])

    code, _, _ = sh(["git", "rev-parse", "--abbrev-ref", "@{u}"], repo)
    if code != 0:
        rec(False, "ветка запушена", "нет upstream")
    else:
        _, ahead, _ = sh(["git", "rev-list", "--count", "@{u}..HEAD"], repo)
        rec(ahead == "0", "все коммиты запушены", f"не запушено: {ahead}")

    base_ref = f"origin/{base}"
    if fetch:
        sh(["git", "fetch", "--quiet", "origin", base], repo, timeout=300)
    files, err = changed_files(repo, base_ref)
    if files is None:
        rec(False, f"diff относительно {base_ref}", err[:200])
        return
    rec(bool(files), f"есть изменения относительно {base}", f"файлов: {len(files)}")
    code, behind, err = sh(["git", "rev-list", "--count", f"HEAD..{base_ref}"], repo)
    if code != 0:
        rec(False, f"ветка содержит актуальную {base}", err[:200])
    else:
        rec(behind == "0", f"ветка содержит актуальную {base}",
            f"позади на {behind} коммитов: влей {base_ref} в ветку задачи")
    if files:
        check_tamper(repo, base_ref, files, rec)

    proj = project_path(repo)
    sha = sh(["git", "rev-parse", "HEAD"], repo)[1]
    if not proj:
        rec(False, "пайплайн", "не определён проект из origin")
        return
    enc = urllib.parse.quote(proj, safe="")
    code, out, err = sh(["glab", "api",
                         f"projects/{enc}/pipelines?sha={sha}&per_page=1&order_by=id&sort=desc"], repo)
    if code != 0:
        rec(False, "пайплайн", f"glab: {err[:200] or 'ошибка запроса'}")
        return
    try:
        pipes = json.loads(out)
    except json.JSONDecodeError:
        rec(False, "пайплайн", "ответ GitLab не разобран")
        return
    if not pipes:
        rec(False, "пайплайн на вершине", f"для {sha[:8]} пайплайнов нет")
    else:
        st = pipes[0].get("status")
        rec(st == "success", "пайплайн на вершине успешен", f"{pipes[0].get('id')}: {st}")


def run_on_base(tmp, cmd):
    try:
        r = subprocess.run(cmd, shell=True, cwd=tmp, capture_output=True, text=True,
                           timeout=CMD_TIMEOUT)
        return r.returncode, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired:
        return 124, f"таймаут {CMD_TIMEOUT} с"


def red_check(repo, base, test_name, cmd, base_cmds, results):
    """Тест из вершины на базовом коде: окружение должно работать, тест — упасть по имени."""
    name = os.path.basename(repo.rstrip("/"))
    label = f"{name}: красно на базе: {test_name}"
    base_ref = f"origin/{base}"
    code, mb, err = sh(["git", "merge-base", "HEAD", base_ref], repo)
    if code != 0:
        results.append((False, label, f"merge-base не найден: {err[:150]}"))
        return
    files, err = changed_files(repo, base_ref)
    if files is None:
        results.append((False, label, err[:150]))
        return
    tmp = tempfile.mkdtemp(prefix="gate-red-")
    try:
        code, _, err = sh(["git", "worktree", "add", "--detach", tmp, "HEAD"], repo)
        if code != 0:
            results.append((False, label, f"worktree: {err[:150]}"))
            return
        for f in files:
            if is_test(f):
                continue
            if sh(["git", "cat-file", "-e", f"{mb}:{f}"], tmp)[0] == 0:
                sh(["git", "restore", f"--source={mb}", "--staged", "--worktree", "--", f], tmp)
            else:
                target = os.path.join(tmp, f)
                if os.path.exists(target):
                    os.remove(target)
        for bc in base_cmds:
            rc, out = run_on_base(tmp, bc)
            if rc != 0:
                results.append((False, label,
                                f"окружение на базе сломано: «{bc[:60]}» код {rc}: "
                                + " | ".join(out.strip().splitlines()[-2:])[:200]))
                return
        rc, out = run_on_base(tmp, cmd)
        tail = " | ".join(out.strip().splitlines()[-2:])[:200]
        if rc == 0:
            results.append((False, label, "на базе прошла — тест не ловит пропажу изменения"))
        elif test_name not in out:
            results.append((False, label, f"упала без имени «{test_name}» — возможно, не тест: {tail}"))
        else:
            results.append((True, label, "на базе упала по имени теста"))
    finally:
        sh(["git", "worktree", "remove", "--force", tmp], repo)
        shutil.rmtree(tmp, ignore_errors=True)


RED_LINE = re.compile(r"^!red\[([^\]]+)\]\s+(.+)$")
BASE_LINE = re.compile(r"^!base-ok\s+(.+)$")


def run_cmds(task_dir, repos, base, results):
    path = os.path.join(task_dir, "gate.cmds")
    if not os.path.isfile(path):
        results.append((False, "проверки задачи (gate.cmds)", "файл не задан — постановка без проверок"))
        return
    with open(path, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.lstrip().startswith("#")]
    if not lines:
        results.append((False, "проверки задачи (gate.cmds)", "файл пуст"))
        return

    entries = []
    for line in lines:
        if " :: " not in line:
            results.append((False, f"проверка «{line[:60]}»", "формат: <путь репо> :: <команда>"))
            continue
        repo, body = (p.strip() for p in line.split(" :: ", 1))
        entries.append((os.path.abspath(repo), body))

    base_cmds = {}
    for repo, body in entries:
        m = BASE_LINE.match(body)
        if m:
            base_cmds.setdefault(repo, []).append(m.group(1).strip())
    red_repos = {repo for repo, body in entries if body.startswith("!red")}

    for repo, body in entries:
        if body.startswith("!base-ok"):
            if repo not in red_repos:
                results.append((False, f"{os.path.basename(repo)}: {body[:60]}",
                                "!base-ok без !red в этом репо — лишняя строка"))
            continue
        if body.startswith("!red"):
            m = RED_LINE.match(body)
            if not m:
                results.append((False, f"красно на базе: {body[:60]}",
                                "формат: <репо> :: !red[имя теста] <команда>"))
                continue
            if not base:
                results.append((False, f"красно на базе: {m.group(1)}", "нужна целевая ветка"))
                continue
            if not base_cmds.get(repo):
                results.append((False, f"красно на базе: {m.group(1)}",
                                "нет строки «<репо> :: !base-ok <команда>» для проверки окружения"))
                continue
            red_check(repo, base, m.group(1), m.group(2).strip(), base_cmds[repo], results)
            continue
        try:
            r = subprocess.run(body, shell=True, cwd=repo, capture_output=True, text=True,
                               timeout=CMD_TIMEOUT)
            tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
            results.append((r.returncode == 0, f"{os.path.basename(repo)}: {body[:70]}",
                            f"код {r.returncode}; " + " | ".join(tail)[:300]))
        except subprocess.TimeoutExpired:
            results.append((False, f"{os.path.basename(repo)}: {body[:70]}",
                            f"таймаут {CMD_TIMEOUT} с"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("--stage", default="done", choices=["done"])
    ap.add_argument("--repo", action="append", default=[])
    ap.add_argument("--base")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--tasks", default=os.environ.get("ORCH_TASKS_DIR", ""))
    a = ap.parse_args()

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    tasks = a.tasks or os.path.join(root, ".tasks")
    task_dir = os.path.join(tasks, slug(a.key))
    if not os.path.isdir(task_dir):
        print(f"гейт: нет каталога задачи {task_dir}", file=sys.stderr)
        return 2

    repos = list(a.repo)
    rf = os.path.join(task_dir, "repos")
    if not repos and os.path.isfile(rf):
        with open(rf, encoding="utf-8") as f:
            repos = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    base = a.base
    if not base:
        bf = os.path.join(task_dir, ".base-branch")
        base = open(bf, encoding="utf-8").read().strip() if os.path.isfile(bf) else ""

    results = []
    if not repos:
        results.append((False, "репозитории задачи", "не заданы: файл repos или --repo"))
    if not base:
        results.append((False, "целевая ветка", "не зарегистрирована: .base-branch или --base"))
    for repo in repos:
        if base:
            check_repo(os.path.abspath(repo), base, not a.no_fetch, results)
    run_cmds(task_dir, repos, base, results)

    failed = [r for r in results if not r[0]]
    for ok, check, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {check}" + (f" — {detail}" if detail and not ok else ""))
    verdict = "ПРОЙДЕНО" if not failed else "НЕ ПРОЙДЕНО"
    print(f"\nгейт {a.key}: {verdict} ({len(results) - len(failed)}/{len(results)})")

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    shas = []
    for repo in repos:
        rp = os.path.abspath(repo)
        code, sha, _ = sh(["git", "rev-parse", "HEAD"], rp)
        if code == 0:
            shas.append(f"{os.path.basename(rp.rstrip('/'))}:{sha[:12]}")
    sys.path.insert(0, os.path.join(root, "framework"))
    from core import config as _config, events as _events
    _config.configure(prefix="ORCH_", state_dir=".tasks", root=root)
    _events.emit(a.key, "gate_run", verdict=verdict, failed=len(failed), sha=",".join(shas))
    with open(os.path.join(task_dir, "gate.log"), "a", encoding="utf-8") as f:
        f.write(f"{stamp}\t{a.stage}\t{verdict}\t{len(failed)} провалов\tsha={','.join(shas)}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
