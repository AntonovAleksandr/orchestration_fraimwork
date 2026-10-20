"""Граница ядра: модули класса «ядро» из INVENTORY.md не содержат проектных токенов.

Запуск из корня воркспейса: python3 framework/tests/test_boundary.py
"""
import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# Токены проекта — через ORCH_PROJECT_TOKENS (регулярное выражение); «ORCH_» зашит всегда:
# префикс переменных ядру задаёт профиль, в модулях он не пишется.
_extra = os.environ.get("ORCH_PROJECT_TOKENS", "")
PROJECT_TOKENS = re.compile("ORCH_" + (f"|{_extra}" if _extra else ""), re.I)


def core_paths():
    inv = os.path.join(ROOT, "framework", "INVENTORY.md")
    out = []
    with open(inv, encoding="utf-8") as f:
        for line in f:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and cells[1] == "ядро":
                out.append(cells[0].strip("`"))
    return out


class BoundaryTest(unittest.TestCase):
    def test_core_modules_have_no_project_tokens(self):
        paths = core_paths()
        self.assertTrue(paths, "в INVENTORY.md нет ни одного модуля класса «ядро»")
        bad = []
        for rel in paths:
            full = os.path.join(ROOT, rel)
            self.assertTrue(os.path.exists(full), f"нет файла: {rel}")
            targets = [full] if os.path.isfile(full) else [
                os.path.join(dp, fn) for dp, _, fns in os.walk(full) for fn in fns]
            for t in targets:
                with open(t, encoding="utf-8", errors="ignore") as f:
                    for n, line in enumerate(f, 1):
                        if PROJECT_TOKENS.search(line):
                            bad.append(f"{os.path.relpath(t, ROOT)}:{n}")
        self.assertEqual(bad, [], "проектные токены в модулях ядра: " + ", ".join(bad[:10]))


if __name__ == "__main__":
    unittest.main()
