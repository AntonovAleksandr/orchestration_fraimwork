#!/usr/bin/env python3
"""Публикация подтверждённых замечаний ревью в обсуждения MR с проверкой строк по версии ревью.

  publish_review.py --project <проект GitLab> --mr <номер> --review-dir <каталог ревью в .tasks> \
      --repo-dir <локальный клон> --verdicts <json> [--sha <коммит ревью>] [--publish]

--verdicts: {"F1": {"verdict": "confirmed", "ref": "…"}, "F2": {"verdict": "rejected", "reason": "…"}, …}
Без --publish только план: в GitLab ничего не пишется. С --publish пишет — это внешняя запись, вызывать по
решению пользователя.
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "framework"))

from core import config, review_publish as rp  # noqa: E402
from adapters.gitlab_vcs import GitLabVcs  # noqa: E402

config.configure(prefix="ORCH_", state_dir=".tasks", root=ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--mr", required=True, type=int)
    ap.add_argument("--review-dir", required=True)
    ap.add_argument("--repo-dir", required=True)
    ap.add_argument("--verdicts", required=True)
    ap.add_argument("--sha", default="")
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()

    report = os.path.join(config.state_root(), a.review_dir, "report.md")
    if not os.path.isfile(report):
        print(f"нет отчёта: {report}", file=sys.stderr)
        return 2
    text = open(report, encoding="utf-8").read()
    sha = a.sha
    if not sha:
        m = re.search(r"^- Вершина на ревью:\s*`([0-9a-f]{7,40})`", text, re.M)
        sha = m.group(1) if m else ""
    if not sha:
        print("коммит ревью не найден: укажите --sha", file=sys.stderr)
        return 2
    findings = rp.parse(text.splitlines())
    try:
        verdicts = json.load(open(a.verdicts, encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"вердикты не прочитаны: {e}", file=sys.stderr)
        return 2

    problems = rp.check_verdicts(findings, verdicts)
    if problems:
        for p in problems:
            print("СТОП:", p, file=sys.stderr)
        return 1

    result = rp.publish_from_repo(GitLabVcs(), a.project, a.mr, findings, verdicts,
                                  a.repo_dir, sha, dry_run=not a.publish)
    for k in ("planned", "published", "skipped_existing", "fallback_note", "rejected", "questions", "errors"):
        if result.get(k):
            print(f"{k}: {result[k]}")
    if not a.publish:
        print("dry-run: в GitLab ничего не записано (нужен --publish)")
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
