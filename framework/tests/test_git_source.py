"""Тесты проверки строки по версии файла в git: настоящий временный репозиторий.

Запуск из корня воркспейса: python3 framework/tests/test_git_source.py
"""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from core import git_source as gs  # noqa: E402


def git(d, *args):
    return subprocess.run(["git", "-C", d, *args], capture_output=True, text=True, check=True).stdout.strip()


class GitSourceTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="fw-git-")
        subprocess.run(["git", "init", "-q", self.d], check=True)
        with open(os.path.join(self.d, "a.py"), "w", encoding="utf-8") as f:
            f.write("one\ntwo\nthree\n")
        git(self.d, "add", "a.py")
        git(self.d, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c1")
        self.sha1 = git(self.d, "rev-parse", "HEAD")
        with open(os.path.join(self.d, "a.py"), "w", encoding="utf-8") as f:
            f.write("one\ntwo\n")
        git(self.d, "add", "a.py")
        git(self.d, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c2")
        self.sha2 = git(self.d, "rev-parse", "HEAD")

    def test_line_present_in_old_version(self):
        self.assertTrue(gs.line_exists(self.d, self.sha1, "a.py", 3))
        self.assertEqual(gs.line_text(self.d, self.sha1, "a.py", 3), "three")

    def test_line_removed_in_new_version(self):
        self.assertFalse(gs.line_exists(self.d, self.sha2, "a.py", 3))
        self.assertIsNone(gs.line_text(self.d, self.sha2, "a.py", 3))

    def test_missing_file_and_bad_numbers(self):
        self.assertFalse(gs.line_exists(self.d, self.sha2, "nope.py", 1))
        self.assertFalse(gs.line_exists(self.d, self.sha2, "a.py", 0))
        self.assertFalse(gs.line_exists(self.d, self.sha2, "a.py", -2))


if __name__ == "__main__":
    unittest.main()
