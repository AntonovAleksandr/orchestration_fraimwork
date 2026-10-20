#!/usr/bin/env python3
"""Заполнена ли «Самопроверка» во вводной задачи.

  selfcheck.py <brief.md>          код 0 — заполнена, 1 — нет (причина в stderr)
  selfcheck.py --skills back|front список скиллов через запятую

Заполнена = раздел есть, заготовка удалена и в нём упомянут каждый обязательный скилл
для вида задачи (строка «- вид:» вводной). Либо во вводной строка
«Самопроверка не нужна: <причина>» — для запросов без кода (документация, конфиг).
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))

def skills(kind):
    out = []
    for line in open(os.path.join(HERE, "defect-skills.txt"), encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, kinds = line.split("\t", 1)
        if kind in kinds.split():
            out.append(name)
    return out

def kind_of(text):
    return "front" if re.search(r"^- вид:\s*вёрстка", text, re.M) else "back"

def check(path):
    if not os.path.exists(path):
        return "вводной нет"
    text = open(path, encoding="utf-8").read()
    if re.search(r"^Самопроверка не нужна:\s*\S", text, re.M):
        return None
    m = re.search(r"^## Самопроверка\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return "раздела «Самопроверка» нет"
    body = m.group(1)
    if "заполняется перед сдачей" in body:
        return "в разделе «Самопроверка» осталась заготовка"
    missing = [s for s in skills(kind_of(text)) if s not in body]
    if missing:
        return "в «Самопроверке» нет ответов по: " + ", ".join(missing)
    return None

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--skills":
        print(", ".join(skills(sys.argv[2]))); sys.exit(0)
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr); sys.exit(2)
    err = check(sys.argv[1])
    if err:
        print(err, file=sys.stderr); sys.exit(1)
