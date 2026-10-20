"""Тесты ответов на замечания: валидность по исходам, необработанные, блокировка слияния.

Запуск из корня воркспейса: python3 framework/tests/test_responses.py
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from core import responses as rs  # noqa: E402


class ResponsesTest(unittest.TestCase):
    def test_each_outcome_valid_with_required_fields(self):
        cases = [
            {"outcome": "fixed", "sha": "abc1234"},
            {"outcome": "agreed", "comment": "согласен, исправлю"},
            {"outcome": "rejected", "reason": "поведение описано в постановке §4"},
            {"outcome": "not_fixed", "reason": "вынесено в задачу, см. ниже"},
            {"outcome": "task_link", "url": "https://tracker.example/T-1", "agreed_with": "аналитик"},
        ]
        for c in cases:
            self.assertEqual(rs.problems(c), [], c)

    def test_missing_fields_are_reported(self):
        self.assertTrue(rs.problems({"outcome": "fixed"}))
        self.assertTrue(rs.problems({"outcome": "rejected", "reason": " "}))
        self.assertTrue(rs.problems({"outcome": "task_link", "url": "https://x"}))

    def test_unknown_outcome_is_refused(self):
        self.assertTrue(rs.problems({"outcome": "игнор"}))

    def test_unanswered_threads_are_listed(self):
        resp = {"T1": {"outcome": "fixed", "sha": "abc"}, "T2": {"outcome": "rejected"}}
        self.assertEqual(rs.unanswered(["T1", "T2", "T3"], resp), ["T2", "T3"])

    def test_merge_blocked_until_all_answered(self):
        self.assertFalse(rs.can_merge(["T1"], {}))
        self.assertTrue(rs.can_merge(["T1"], {"T1": {"outcome": "agreed", "comment": "ok"}}))

    def test_no_threads_means_mergeable(self):
        self.assertTrue(rs.can_merge([], {}))


if __name__ == "__main__":
    unittest.main()
