#!/usr/bin/env python3
"""Обёртка над ядром фреймворка: framework/core/requirements.py с настройками."""
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "framework"))

from core import config  # noqa: E402

config.configure(prefix="ORCH_", state_dir=".tasks", root=_ROOT)

from core.requirements import *  # noqa: E402,F401,F403
from core.requirements import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
