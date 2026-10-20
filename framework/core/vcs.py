"""Интерфейс системы контроля версий и запросов на слияние.

Ядро обращается к VCS только через этот интерфейс. Адаптеры для конкретных хостингов реализуют его.
Все методы не должны менять состояние, кроме merge, который вызывается только после подтверждения человека.
"""
from typing import Optional, Protocol


class Vcs(Protocol):
    def head_sha(self, repo: str, branch: str) -> Optional[str]:
        """Полный SHA головы ветки или None, если ветки нет или запрос не удался."""

    def pipeline_status(self, repo: str, sha: str) -> Optional[str]:
        """Статус последнего пайплайна на коммите: success, failed, running, manual, none; None — не получено."""

    def change_description(self, repo: str, number: int) -> Optional[str]:
        """Описание запроса на слияние или None."""

    def comment(self, repo: str, number: int, text: str) -> bool:
        """Оставить комментарий. True — успешно."""

    def merge(self, repo: str, number: int) -> bool:
        """Слить запрос. Вызывать только после подтверждения человека. True — успешно."""

    def diff_refs(self, repo: str, number: int) -> Optional[dict]:
        """base_sha, start_sha, head_sha запроса для привязки к строкам или None."""

    def diff_lines(self, repo: str, number: int) -> Optional[set]:
        """Множество (путь, номер строки) новой стороны диффа или None."""

    def discussions(self, repo: str, number: int) -> Optional[list]:
        """Тексты существующих обсуждений запроса или None."""

    def line_discussion(self, repo: str, number: int, path: str, line: int, body: str, refs: dict) -> bool:
        """Создать обсуждение, привязанное к строке диффа. True — успешно."""
