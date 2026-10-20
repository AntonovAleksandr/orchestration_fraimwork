"""Настройки ядра: префикс переменных окружения, каталог состояния задач и корень проекта.

Ядро не знает, какой проект его использует. Адаптер (например, обёртка проекта) вызывает configure() до работы
модулей. Значения по умолчанию нейтральны.
"""
import os
import re

_settings = {"prefix": "FW_", "state_dir": ".framework", "root": None}


def configure(prefix=None, state_dir=None, root=None):
    if prefix is not None:
        _settings["prefix"] = prefix
    if state_dir is not None:
        _settings["state_dir"] = state_dir
    if root is not None:
        _settings["root"] = os.path.abspath(root)


def prefix():
    return _settings["prefix"]


def root():
    return _settings["root"] or os.getcwd()


def state_root():
    """Каталог состояния задач: переменная <префикс>TASKS_DIR, иначе <корень>/<state_dir>."""
    env = os.environ.get(f"{_settings['prefix']}TASKS_DIR")
    if env:
        return env
    return os.path.join(root(), _settings["state_dir"])


def slug(key):
    return re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")


def task_dir(key):
    return os.path.join(state_root(), slug(key))
