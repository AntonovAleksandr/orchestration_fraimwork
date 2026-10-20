"""Тесты состояния задачи: переходы, причины ожидания, история, журнал событий.

Запуск из корня воркспейса: python3 framework/tests/test_state.py
"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from core import config, state  # noqa: E402


class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fw-state-")
        config.configure(prefix="FWT_", state_dir=".state", root=self.tmp)
        os.environ.pop("FWT_TASKS_DIR", None)

    def test_new_task_starts_in_new(self):
        self.assertEqual(state.load("TASK-1")["state"], "new")

    def test_valid_path_is_recorded(self):
        state.transition("TASK-1", "analysis")
        state.transition("TASK-1", "waiting_input", reason="ждём аналитика по лимиту корзины")
        d = state.load("TASK-1")
        self.assertEqual(d["state"], "waiting_input")
        self.assertEqual(d["reason"], "ждём аналитика по лимиту корзины")
        self.assertEqual([h["to"] for h in d["history"]], ["analysis", "waiting_input"])

    def test_invalid_transition_is_refused(self):
        with self.assertRaises(state.TransitionError):
            state.transition("TASK-2", "done")

    def test_waiting_requires_reason(self):
        state.transition("TASK-3", "analysis")
        with self.assertRaises(state.TransitionError):
            state.transition("TASK-3", "waiting_input", reason="  ")

    def test_reason_cleared_on_leaving_wait(self):
        state.transition("TASK-4", "analysis")
        state.transition("TASK-4", "waiting_input", reason="ответ аналитика")
        state.transition("TASK-4", "analysis")
        self.assertEqual(state.load("TASK-4")["reason"], "")

    def evidence(self, key, gate="ПРОЙДЕНО", verdict="APPROVE"):
        d = config.task_dir(key)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "gate.log"), "w", encoding="utf-8") as f:
            f.write(f"2026-10-17 10:00:00\tdone\t{gate}\t0 провалов\tsha=x:abc\n")
        with open(os.path.join(d, "acceptance.md"), "w", encoding="utf-8") as f:
            f.write(f"# Приёмка\n## вердикт: {verdict}\n")

    def test_done_is_terminal(self):
        self.evidence("TASK-5")
        for to in ("analysis", "implementation", "review", "acceptance", "ready", "done"):
            state.transition("TASK-5", to, reason="x" if to == "waiting_input" else "")
        with self.assertRaises(state.TransitionError):
            state.transition("TASK-5", "implementation")

    def test_transition_emits_event(self):
        state.transition("TASK-6", "analysis")
        p = os.path.join(config.task_dir("TASK-6"), "events.jsonl")
        rows = [json.loads(l) for l in open(p, encoding="utf-8")]
        self.assertEqual(rows[-1]["type"], "state_changed")
        self.assertEqual(rows[-1]["to"], "analysis")


    def test_ready_refused_without_gate(self):
        for to in ("analysis", "implementation", "review", "acceptance"):
            state.transition("TASK-7", to)
        with self.assertRaises(state.TransitionError):
            state.transition("TASK-7", "ready")

    def test_ready_refused_when_acceptance_not_approved(self):
        self.evidence("TASK-8", verdict="CHANGES REQUIRED")
        for to in ("analysis", "implementation", "review", "acceptance"):
            state.transition("TASK-8", to)
        with self.assertRaises(state.TransitionError):
            state.transition("TASK-8", "ready")

    def test_reconcile_clean_after_consistent_ready(self):
        self.evidence("TASK-9")
        for to in ("analysis", "implementation", "review", "acceptance", "ready"):
            state.transition("TASK-9", to)
        self.assertEqual(state.reconcile("TASK-9"), [])

    def test_reconcile_detects_manual_edit(self):
        state.transition("TASK-10", "analysis")
        d = state.load("TASK-10")
        d["state"] = "implementation"
        state._save("TASK-10", d)
        div = state.reconcile("TASK-10")
        self.assertTrue(any("журнал событий" in x for x in div))

    def test_reconcile_detects_open_blockers_for_ready(self):
        self.evidence("TASK-11")
        for to in ("analysis", "implementation", "review", "acceptance", "ready"):
            state.transition("TASK-11", to)
        with open(os.path.join(config.task_dir("TASK-11"), "open-questions.md"), "w", encoding="utf-8") as f:
            f.write("- Q1 [открыт] вопрос | проверено: ФТ | фаза: analysis\n")
        self.assertTrue(any("открытых вопросов" in x for x in state.reconcile("TASK-11")))

    def test_waiting_without_questions_is_divergence(self):
        state.transition("TASK-12", "analysis")
        state.transition("TASK-12", "waiting_input", reason="ждём аналитика")
        self.assertTrue(any("ожидание ввода" in x for x in state.reconcile("TASK-12")))

    def test_open_question_in_register_blocks_ready(self):
        from core import questions
        self.evidence("TASK-13")
        for to in ("analysis", "implementation", "review", "acceptance"):
            state.transition("TASK-13", to)
        questions.add("TASK-13", "Округлять бонусы вниз или до ближайшего целого?", "confluence:4411@v2")
        with self.assertRaises(state.TransitionError):
            state.transition("TASK-13", "ready")


if __name__ == "__main__":
    unittest.main()
