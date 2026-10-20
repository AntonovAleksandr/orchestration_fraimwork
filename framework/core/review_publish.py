"""Публикация находок ревью как обсуждений запроса на слияние, привязанных к строкам диффа.

Находка в отчёте ревью: заголовок «### F<n>. <приоритет> — …», строка «- Место: `путь:строка`», остальное до
следующей находки — тело. Публикация идёт через адаптер VCS (см. vcs.py). Повтор не создаётся: в тело записывается
маркер находки, и если обсуждение с таким маркером уже есть, находка пропускается.

Если строка не входит в диф, GitLab не привяжет обсуждение: тогда публикуется общий комментарий со ссылкой на
место, и это отмечается в результате.
"""
import re

from . import git_source

HEADER = re.compile(r"^### (F\d+)\.\s*(.*)$")
PLACE = re.compile(r"^- Место:\s*`?([^`:\s]+):(\d+)`?")
MARK = "<!-- finding:{fid} -->"


def parse(lines):
    items, cur = [], None
    for line in lines:
        m = HEADER.match(line)
        if m:
            cur = {"fid": m.group(1), "title": m.group(2).strip(), "path": None, "line": None, "body": []}
            items.append(cur)
            continue
        if cur is None:
            continue
        if line.startswith("## ") or line.startswith("### "):
            cur = None
            continue
        p = PLACE.match(line)
        if p and cur["path"] is None:
            cur["path"], cur["line"] = p.group(1), int(p.group(2))
        cur["body"].append(line)
    return items


def compose(item):
    text = "\n".join(l for l in item["body"] if l.strip())
    return f"{MARK.format(fid=item['fid'])}\n**{item['fid']}. {item['title']}**\n\n{text}".rstrip()


VERDICTS = ("confirmed", "rejected", "question")


def check_verdicts(findings, verdicts):
    """Ошибки проверки перед публикацией. Публикация без полной проверки запрещена."""
    problems = []
    for it in findings:
        v = verdicts.get(it["fid"])
        if v is None:
            problems.append(f"{it['fid']}: нет проверки — находку нельзя публиковать без неё")
            continue
        kind = v.get("verdict")
        if kind not in VERDICTS:
            problems.append(f"{it['fid']}: неизвестный вердикт «{kind}»")
        elif kind == "confirmed" and not str(v.get("ref", "")).strip():
            problems.append(f"{it['fid']}: подтверждено без ссылки на критерий или раздел постановки")
        elif kind in ("rejected", "question") and not str(v.get("reason", "")).strip():
            problems.append(f"{it['fid']}: «{kind}» без причины")
    return problems


def publish(vcs, repo, number, findings, verdicts, dry_run=True, line_exists=None):
    """Публикует только подтверждённые находки.

    verdicts: {fid: {"verdict": confirmed|rejected|question, "ref": "…", "reason": "…"}} — результат проверки.
    line_exists(path, line) -> bool: проверка, что строка есть в актуальной версии файла; None — не проверять.
    Возвращает план и результат; вопросы человеку — в поле questions.
    """
    result = {"planned": [], "published": [], "skipped_existing": [], "fallback_note": [],
              "rejected": [], "questions": [], "errors": []}
    problems = check_verdicts(findings, verdicts)
    if problems:
        result["errors"] = problems
        return result
    existing = vcs.discussions(repo, number)
    if existing is None:
        result["errors"].append("список обсуждений не получен — публикация остановлена")
        return result
    existing_text = "\n".join(existing)
    diff = vcs.diff_lines(repo, number)
    refs = vcs.diff_refs(repo, number)
    if diff is None or refs is None:
        result["errors"].append("диф или refs запроса не получены — публикация остановлена")
        return result
    for it in findings:
        v = verdicts[it["fid"]]
        if v["verdict"] == "rejected":
            result["rejected"].append((it["fid"], v["reason"]))
            continue
        if v["verdict"] == "question":
            result["questions"].append((it["fid"], v["reason"]))
            continue
        if MARK.format(fid=it["fid"]) in existing_text:
            result["skipped_existing"].append(it["fid"])
            continue
        if not it["path"] or not it["line"]:
            result["errors"].append(f"{it['fid']}: нет места «путь:строка» — пропущено")
            continue
        if line_exists is not None and not line_exists(it["path"], it["line"]):
            result["errors"].append(f"{it['fid']}: строки {it['path']}:{it['line']} нет в актуальной версии файла")
            continue
        body = compose(it) + f"\n\n_Проверено: {v['ref']}_"
        in_diff = (it["path"], it["line"]) in diff
        result["planned"].append((it["fid"], it["path"], it["line"], in_diff))
        if dry_run:
            continue
        if in_diff:
            ok = vcs.line_discussion(repo, number, it["path"], it["line"], body, refs)
            (result["published"] if ok else result["errors"]).append(
                it["fid"] if ok else f"{it['fid']}: обсуждение не создано")
        else:
            ok = vcs.comment(repo, number, f"{body}\n\nМесто: `{it['path']}:{it['line']}` (строка вне диффа запроса)")
            if ok:
                result["fallback_note"].append(it["fid"])
            else:
                result["errors"].append(f"{it['fid']}: общий комментарий не создан")
    return result


def publish_from_repo(vcs, repo, number, findings, verdicts, repo_dir, sha, dry_run=True):
    """Публикация с проверкой строк по версии файла в локальном репозитории (коммит ревью)."""
    def exists(path, line):
        return git_source.line_exists(repo_dir, sha, path, line)
    return publish(vcs, repo, number, findings, verdicts, dry_run=dry_run, line_exists=exists)
