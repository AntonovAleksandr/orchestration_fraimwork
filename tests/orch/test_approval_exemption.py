"""Комментарии в свой запрос на слияние — без подтверждения; слияние и чужие запросы — с подтверждением (D-016).

Запуск из корня воркспейса: python3 tests/orch/test_approval_exemption.py
"""
import importlib.util
import os
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
spec = importlib.util.spec_from_file_location("ag", os.path.join(ROOT, "scripts/orch/hooks/approval-guard.py"))
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)


class Exemption(unittest.TestCase):
    def setUp(self):
        self._branch, self._source = ag._current_branch, ag._mr_source_branch
        ag._current_branch = lambda cwd: "task/PROJ-534-review"
        ag._mr_source_branch = lambda n, cwd: {12: "task/PROJ-534-review", 13: "feature/other"}.get(n, "")

    def tearDown(self):
        ag._current_branch, ag._mr_source_branch = self._branch, self._source

    def bash(self, cmd):
        return ag.external({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": ROOT})

    def test_note_on_own_mr_is_allowed(self):
        self.assertIsNone(self.bash('glab mr note 12 -m "проверено"'))

    def test_discussion_post_on_own_mr_is_allowed(self):
        self.assertIsNone(self.bash("glab api projects/1/merge_requests/12/discussions -f body=ok"))

    def test_note_on_foreign_mr_needs_approval(self):
        self.assertIsNotNone(self.bash('glab mr note 13 -m "чужой"'))

    def test_merge_on_own_mr_still_needs_approval(self):
        self.assertIsNotNone(self.bash("glab mr merge 12"))

    def test_note_outside_task_branch_needs_approval(self):
        ag._current_branch = lambda cwd: "main"
        self.assertIsNotNone(self.bash('glab mr note 12 -m "x"'))


if __name__ == "__main__":
    unittest.main()
