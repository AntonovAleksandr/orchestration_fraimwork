"""Адаптер GitLab для интерфейса Vcs (framework/core/vcs.py). Работает через `glab api`.

Хост и проект задаются вызывающим; в адаптере нет адресов конкретных проектов. Записи (комментарии, обсуждения,
слияние) вызываются только по решению вызывающего кода: адаптер сам ничего не публикует.
"""
import json
import re
import subprocess
import urllib.parse

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def parse_new_lines(diff_text, new_path):
    """Номера строк новой стороны, попавших в диф (добавленные и контекстные)."""
    out = set()
    line_no = None
    for raw in diff_text.splitlines():
        m = HUNK.match(raw)
        if m:
            line_no = int(m.group(1))
            continue
        if line_no is None:
            continue
        if raw.startswith("+"):
            out.add((new_path, line_no))
            line_no += 1
        elif raw.startswith(" "):
            out.add((new_path, line_no))
            line_no += 1
        elif raw.startswith("-"):
            continue
    return out


class GitLabVcs:
    def __init__(self, glab="glab", timeout=60):
        self.glab = glab
        self.timeout = timeout

    def _api(self, endpoint, fields=None, method=None):
        args = [self.glab, "api", endpoint]
        if method:
            args += ["-X", method]
        for k, v in (fields or {}).items():
            args += ["-f", f"{k}={v}"]
        r = subprocess.run(args, capture_output=True, text=True, timeout=self.timeout)
        if r.returncode != 0:
            return None
        try:
            return json.loads(r.stdout) if r.stdout.strip() else {}
        except ValueError:
            return None

    @staticmethod
    def _proj(repo):
        return urllib.parse.quote(repo, safe="")

    def _mr(self, repo, number):
        return f"projects/{self._proj(repo)}/merge_requests/{number}"

    def head_sha(self, repo, branch):
        d = self._api(f"projects/{self._proj(repo)}/repository/branches/{urllib.parse.quote(branch, safe='')}")
        return (d or {}).get("commit", {}).get("id")

    def pipeline_status(self, repo, sha):
        d = self._api(f"projects/{self._proj(repo)}/pipelines?sha={sha}&per_page=1")
        if d is None:
            return None
        return d[0].get("status") if d else "none"

    def change_description(self, repo, number):
        d = self._api(self._mr(repo, number))
        return None if d is None else d.get("description") or ""

    def comment(self, repo, number, text):
        return self._api(f"{self._mr(repo, number)}/notes", {"body": text}, method="POST") is not None

    def merge(self, repo, number):
        return self._api(f"{self._mr(repo, number)}/merge", method="PUT") is not None

    def diff_refs(self, repo, number):
        d = self._api(self._mr(repo, number))
        if d is None or "diff_refs" not in d:
            return None
        r = d["diff_refs"]
        return {"base_sha": r["base_sha"], "start_sha": r["start_sha"], "head_sha": r["head_sha"]}

    def diff_lines(self, repo, number):
        d = self._api(f"{self._mr(repo, number)}/changes")
        if d is None or "changes" not in d:
            return None
        lines = set()
        for ch in d["changes"]:
            lines |= parse_new_lines(ch.get("diff", ""), ch.get("new_path") or ch.get("old_path"))
        return lines

    def discussions(self, repo, number):
        d = self._api(f"{self._mr(repo, number)}/discussions?per_page=100")
        if d is None:
            return None
        return [n.get("body", "") for disc in d for n in disc.get("notes", [])]

    def line_discussion(self, repo, number, path, line, body, refs):
        fields = {
            "body": body,
            "position[position_type]": "text",
            "position[base_sha]": refs["base_sha"],
            "position[start_sha]": refs["start_sha"],
            "position[head_sha]": refs["head_sha"],
            "position[old_path]": path,
            "position[new_path]": path,
            "position[new_line]": str(line),
        }
        return self._api(f"{self._mr(repo, number)}/discussions", fields, method="POST") is not None
