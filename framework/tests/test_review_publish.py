"""Тесты публикации находок ревью: проверка перед публикацией, привязка к строке, общий комментарий, повтор.

Запуск из корня воркспейса: python3 framework/tests/test_review_publish.py
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from core import review_publish as rp  # noqa: E402

REPORT = [
    "# Ревью",
    "",
    "## вердикт: CHANGES REQUIRED",
    "",
    "## Находки",
    "",
    "### F1. P1 — порча данных при повторе",
    "- Место: `src/a.py:12`",
    "- Проблема: повтор запроса дублирует запись",
    "",
    "### F2. P2 — тихий отказ",
    "- Место: `src/b.py:40`",
    "",
    "### F3. P2 — строка вне диффа",
    "- Место: `src/c.py:7`",
    "",
    "## Что проверено",
    "- ok",
]

CONFIRMED = {"verdict": "confirmed", "ref": "постановка §2.3, критерий AC-2"}


class FakeVcs:
    def __init__(self, discussions=(), diff=(("src/a.py", 12), ("src/b.py", 40)), ok=True):
        self._disc = list(discussions) if discussions is not None else None
        self._diff = set(diff)
        self.ok = ok
        self.inline, self.notes = [], []

    def discussions(self, repo, number):
        return self._disc

    def diff_lines(self, repo, number):
        return self._diff

    def diff_refs(self, repo, number):
        return {"base_sha": "b", "start_sha": "s", "head_sha": "h"}

    def line_discussion(self, repo, number, path, line, body, refs):
        self.inline.append((path, line))
        return self.ok

    def comment(self, repo, number, text):
        self.notes.append(text)
        return self.ok


def all_confirmed():
    return {"F1": CONFIRMED, "F2": CONFIRMED, "F3": CONFIRMED}


class ReviewPublishTest(unittest.TestCase):
    def setUp(self):
        self.items = rp.parse(REPORT)

    def test_parse_finds_places_and_bodies(self):
        self.assertEqual([i["fid"] for i in self.items], ["F1", "F2", "F3"])
        self.assertEqual((self.items[0]["path"], self.items[0]["line"]), ("src/a.py", 12))
        self.assertIn("повтор запроса дублирует запись", rp.compose(self.items[0]))

    def test_no_publication_without_verdicts(self):
        v = FakeVcs()
        r = rp.publish(v, "p", 1, self.items, {}, dry_run=False)
        self.assertTrue(r["errors"])
        self.assertEqual(v.inline, [])
        self.assertEqual(v.notes, [])

    def test_confirmed_without_reference_is_refused(self):
        v = FakeVcs()
        bad = all_confirmed()
        bad["F1"] = {"verdict": "confirmed", "ref": " "}
        r = rp.publish(v, "p", 1, self.items, bad, dry_run=False)
        self.assertTrue(any("без ссылки" in e for e in r["errors"]))
        self.assertEqual(v.inline, [])

    def test_rejected_and_question_are_not_published(self):
        v = FakeVcs()
        verdicts = all_confirmed()
        verdicts["F2"] = {"verdict": "rejected", "reason": "поведение описано в постановке §4"}
        verdicts["F3"] = {"verdict": "question", "reason": "не ясно, допустим ли отказ в этом сценарии"}
        r = rp.publish(v, "p", 1, self.items, verdicts, dry_run=False)
        self.assertEqual(v.inline, [("src/a.py", 12)])
        self.assertEqual(r["rejected"], [("F2", "поведение описано в постановке §4")])
        self.assertEqual(r["questions"], [("F3", "не ясно, допустим ли отказ в этом сценарии")])

    def test_dry_run_writes_nothing(self):
        v = FakeVcs()
        r = rp.publish(v, "p", 1, self.items, all_confirmed(), dry_run=True)
        self.assertEqual(v.inline, [])
        self.assertEqual(v.notes, [])
        self.assertEqual(len(r["planned"]), 3)

    def test_inline_when_line_in_diff_and_note_otherwise(self):
        v = FakeVcs()
        r = rp.publish(v, "p", 1, self.items, all_confirmed(), dry_run=False)
        self.assertEqual(v.inline, [("src/a.py", 12), ("src/b.py", 40)])
        self.assertEqual(r["fallback_note"], ["F3"])
        self.assertIn("строка вне диффа", v.notes[0])

    def test_line_must_exist_in_current_file(self):
        v = FakeVcs()
        r = rp.publish(v, "p", 1, self.items, all_confirmed(), dry_run=False,
                       line_exists=lambda path, line: path != "src/a.py")
        self.assertTrue(any("нет в актуальной версии" in e for e in r["errors"]))
        self.assertNotIn(("src/a.py", 12), v.inline)

    def test_existing_marker_is_not_duplicated(self):
        v = FakeVcs(discussions=["…", "<!-- finding:F1 -->\n**F1. …**"])
        r = rp.publish(v, "p", 1, self.items, all_confirmed(), dry_run=False)
        self.assertEqual(r["skipped_existing"], ["F1"])
        self.assertNotIn(("src/a.py", 12), v.inline)

    def test_missing_discussions_stops_publishing(self):
        v = FakeVcs(discussions=None)
        r = rp.publish(v, "p", 1, self.items, all_confirmed(), dry_run=False)
        self.assertTrue(r["errors"])
        self.assertEqual(v.inline, [])

    def test_failed_write_is_reported(self):
        v = FakeVcs(ok=False)
        r = rp.publish(v, "p", 1, self.items, all_confirmed(), dry_run=False)
        self.assertTrue(any("не создано" in e for e in r["errors"]))


class PublishFromRepoTest(unittest.TestCase):
    def test_lines_checked_against_review_commit(self):
        import subprocess, tempfile
        d = tempfile.mkdtemp(prefix="fw-pub-")
        subprocess.run(["git", "init", "-q", d], check=True)
        with open(os.path.join(d, "src_a.py"), "w", encoding="utf-8") as f:
            f.write("x\n")
        subprocess.run(["git", "-C", d, "add", "src_a.py"], check=True)
        subprocess.run(["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c"], check=True)
        sha = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        items = [{"fid": "F1", "title": "t", "path": "src_a.py", "line": 1, "body": ["- Проблема: y"]},
                 {"fid": "F2", "title": "t", "path": "src_a.py", "line": 9, "body": ["- Проблема: z"]}]
        verdicts = {"F1": CONFIRMED, "F2": CONFIRMED}
        v = FakeVcs(diff=(("src_a.py", 1),))
        r = rp.publish_from_repo(v, "p", 1, items, verdicts, d, sha, dry_run=False)
        self.assertEqual(v.inline, [("src_a.py", 1)])
        self.assertTrue(any("нет в актуальной версии" in e for e in r["errors"]))


if __name__ == "__main__":
    unittest.main()
