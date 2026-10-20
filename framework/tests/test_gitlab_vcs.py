"""Тесты разбора диффа адаптера GitLab (без сети).

Запуск из корня воркспейса: python3 framework/tests/test_gitlab_vcs.py
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from adapters.gitlab_vcs import parse_new_lines  # noqa: E402

DIFF = """@@ -10,4 +10,5 @@ def f():
 keep
-old line
+new line
+another
 tail
@@ -40,2 +41,2 @@
 x
-y
+z
"""


class ParseNewLinesTest(unittest.TestCase):
    def test_added_and_context_lines_are_positioned(self):
        got = parse_new_lines(DIFF, "a.py")
        self.assertIn(("a.py", 10), got)
        self.assertIn(("a.py", 11), got)
        self.assertIn(("a.py", 12), got)
        self.assertIn(("a.py", 13), got)
        self.assertIn(("a.py", 41), got)
        self.assertIn(("a.py", 42), got)

    def test_removed_lines_are_not_positioned(self):
        got = parse_new_lines(DIFF, "a.py")
        self.assertEqual(len(got), 6)

    def test_line_outside_hunks_is_absent(self):
        self.assertNotIn(("a.py", 99), parse_new_lines(DIFF, "a.py"))


if __name__ == "__main__":
    unittest.main()
