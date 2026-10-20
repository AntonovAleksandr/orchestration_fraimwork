"""Тесты единого реестра вопросов: проверка источника, дедупликация, закрытие, экспорт.

Запуск из корня воркспейса: python3 framework/tests/test_questions.py
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from core import config, questions as qs  # noqa: E402


class QuestionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fw-q-")
        config.configure(prefix="FWQ_", state_dir=".state", root=self.tmp)
        os.environ.pop("FWQ_TASKS_DIR", None)

    def test_question_without_source_is_refused(self):
        with self.assertRaises(ValueError):
            qs.add("T-1", "Какой лимит корзины?", checked="посмотрел")

    def test_question_with_source_is_added(self):
        it = qs.add("T-1", "Какой лимит корзины для гостя?", checked="confluence:190974786@v14")
        self.assertEqual(it["id"], "T-1-Q1")
        self.assertEqual(it["state"], "открыт")

    def test_similar_question_is_refused(self):
        qs.add("T-1", "Какой лимит корзины для гостя по позициям?", checked="постановка §3.2")
        with self.assertRaises(ValueError):
            qs.add("T-2", "Какой лимит корзины для гостя по позициям ?", checked="код:basket.py")

    def test_status_and_priority_are_checked(self):
        with self.assertRaises(ValueError):
            qs.add("T-1", "Вопрос один", checked="tracker:OPS-1", status="страшно")
        with self.assertRaises(ValueError):
            qs.add("T-1", "Вопрос два", checked="tracker:OPS-1", priority="никогда")

    def test_close_needs_answer_and_source(self):
        it = qs.add("T-1", "Нужна ли проверка прав на шаге оплаты?", checked="tracker:OPS-7")
        with self.assertRaises(ValueError):
            qs.close(it["id"], "да", "")
        closed = qs.close(it["id"], "да, на каждом шаге", "аналитик, письмо")
        self.assertEqual(closed["state"], "закрыт")

    def test_imported_question_needs_no_evidence_but_keeps_source(self):
        it = qs.add("MR-1", "Округлять бонусы вниз?", checked="импорт: реестр artifact X", imported=True,
                    options=["floor", "round"])
        self.assertTrue(it["imported"])

    def test_export_contains_open_only_by_default(self):
        it = qs.add("T-3", "Один открытый вопрос про выкатку?", checked="confluence:1@v2")
        other = qs.add("T-3", "Второй вопрос про округление?", checked="confluence:1@v2")
        qs.close(other["id"], "округлять вниз", "аналитик")
        md = qs.export_markdown()
        self.assertIn(it["id"], md)
        self.assertNotIn(other["id"], md)
        self.assertIn("проверено: confluence:1@v2", md)

    def test_html_export_escapes_text(self):
        qs.add("T-4", "Что <script>alert(1)</script> делает?", checked="tracker:OPS-9")
        h = qs.export_html()
        self.assertNotIn("<script>alert", h)
        self.assertIn("&lt;script&gt;", h)


class HumanTextTest(unittest.TestCase):
    def test_internal_terms_are_refused(self):
        self.assertTrue(qs.check_human("Агент проверил state.json: пуст ли он?"))
        self.assertTrue(qs.check_human("Запустить gate.py на фикстуре: проходит ли?"))

    def test_code_identifiers_and_file_names_are_refused(self):
        self.assertTrue(qs.check_human("Из какого состава складывается sumPaid при возврате?"))
        self.assertTrue(qs.check_human("Нужно ли проверять revision_id в контроллере OrdersApi?"))
        self.assertTrue(qs.check_human("Что делает обработчик в handler.php при повторе?"))

    def test_plain_business_question_passes(self):
        self.assertEqual(qs.check_human("Округлять бонусы вниз, вверх или до ближайшего целого?"), [])

    def test_no_question_mark_refused(self):
        self.assertTrue(qs.check_human("Нужно уточнить округление бонусов при списании"))

    def test_add_refuses_non_human_text(self):
        with self.assertRaises(ValueError):
            qs.add("T-9", "Почему orchestrate.sh падает на sumPaid?", checked="tracker:OPS-2")


if __name__ == "__main__":
    unittest.main()
