"""Связки «спецификация → скилл»: каждый скилл, названный в спецификациях оркестратора, существует.

Скилл, на который ссылается роль, но которого нет в .claude/skills, молча пропадает: работник получает инструкцию
без скилла. Тест ловит такие ссылки до запуска работника.

Запуск из корня воркспейса: python3 tests/orch/test_skill_links.py
"""
import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SKILLS = os.path.join(ROOT, ".claude", "skills")
SPEC_FILES = [os.path.join(ROOT, "scripts", "orch", "orchestrate.sh")]
LOAD = re.compile(r"Загрузи скилл(?:ы)?\s+((?:[a-z][a-z0-9-]*)(?:,\s*[a-z][a-z0-9-]*)*)")
ECHO = re.compile(r'\)\s+echo "([^"$]*)')
FRAMEWORK = re.compile(r"\b(framework-[a-z0-9-]+[a-z0-9])\b")
DEFECTS = os.path.join(ROOT, "scripts", "orch", "defect-skills.txt")


def split(s):
    return [x.strip() for x in s.split(",") if re.fullmatch(r"[a-z][a-z0-9-]*", x.strip())]


def referenced(path):
    out = {}
    in_skills_for = False
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if line.startswith("skills_for()"):
                in_skills_for = True
            elif line.startswith("}"):
                in_skills_for = False
            for m in LOAD.finditer(line):
                for name in split(m.group(1)):
                    out.setdefault(name, n)
            for m in (ECHO.finditer(line) if in_skills_for else ()):
                for name in split(m.group(1)):
                    out.setdefault(name, n)
            for m in FRAMEWORK.finditer(line):
                out.setdefault(m.group(1), n)
    if os.path.exists(DEFECTS):
        with open(DEFECTS, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if line.strip() and not line.startswith("#"):
                    out.setdefault(line.split()[0], n)
    return out


class SkillLinksTest(unittest.TestCase):
    def test_every_skill_named_in_specs_exists(self):
        missing = []
        for spec in SPEC_FILES:
            for name, line in referenced(spec).items():
                if not os.path.isfile(os.path.join(SKILLS, name, "SKILL.md")):
                    missing.append(f"{name} (строка {line})")
        self.assertEqual(missing, [], "в спецификациях названы несуществующие скиллы: " + ", ".join(missing))


if __name__ == "__main__":
    unittest.main()
