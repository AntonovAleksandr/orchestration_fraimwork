"""Тесты релизной карты: добавление, порядок, статусы, сверка с состоянием задач.

Запуск из корня воркспейса: python3 framework/tests/test_releases.py
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from core import config, releases as rl  # noqa: E402


class ReleasesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fw-rel-")
        config.configure(prefix="FWR_", state_dir=".state", root=self.tmp)
        os.environ.pop("FWR_TASKS_DIR", None)

    def add(self, task="PROJ-1", repo="svc/a", branch="task-1", target="rel-1", order=1, **kw):
        return rl.add("26.10.03", task=task, repo=repo, branch=branch, target=target, order=order, **kw)

    def test_entry_is_stored_and_listed(self):
        self.add()
        self.assertEqual(len(rl.load("26.10.03")["entries"]), 1)

    def test_required_fields_are_enforced(self):
        with self.assertRaises(ValueError):
            rl.add("26.10.03", task="", repo="r", branch="b", target="t", order=1)

    def test_duplicate_refused(self):
        self.add()
        with self.assertRaises(ValueError):
            self.add()

    def test_order_is_applied(self):
        self.add(task="PROJ-2", repo="svc/b", branch="b2", order=2)
        self.add(task="PROJ-1", repo="svc/a", branch="b1", order=1)
        self.assertEqual([e["task"] for e in rl.ordered("26.10.03")], ["PROJ-1", "PROJ-2"])

    def test_dependency_order_violation_is_reported(self):
        self.add(task="PROJ-1", repo="svc/a", branch="b1", order=1, after=["PROJ-2"])
        self.add(task="PROJ-2", repo="svc/b", branch="b2", order=2)
        probs = rl.order_problems("26.10.03")
        self.assertEqual(len(probs), 1)
        self.assertIn("PROJ-2", probs[0])

    def test_forgotten_repo_is_detected(self):
        self.add(task="PROJ-1")
        r = rl.reconcile("26.10.03", {"PROJ-1": "done", "PROJ-9": "ready"})
        self.assertTrue(any("PROJ-9" in f for f in r["forgotten"]))

    def test_done_task_with_unmerged_branch_is_reported(self):
        self.add(task="PROJ-1")
        r = rl.reconcile("26.10.03", {"PROJ-1": "done"})
        self.assertEqual(len(r["not_merged"]), 1)

    def test_status_update_clears_not_merged(self):
        self.add(task="PROJ-1")
        rl.set_status("26.10.03", "PROJ-1", "svc/a", "task-1", "merged")
        r = rl.reconcile("26.10.03", {"PROJ-1": "done"})
        self.assertEqual(r["not_merged"], [])

    def test_task_keys_compared_by_slug(self):
        self.add(task="PROJ-1")
        r = rl.reconcile("26.10.03", {"proj-1": "done"})
        self.assertEqual(r["not_merged"][0].split(" ")[0], "PROJ-1")

    def test_unknown_status_refused(self):
        self.add()
        with self.assertRaises(ValueError):
            rl.set_status("26.10.03", "PROJ-1", "svc/a", "task-1", "готово")


if __name__ == "__main__":
    unittest.main()
