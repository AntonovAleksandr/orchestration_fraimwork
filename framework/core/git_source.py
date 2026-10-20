"""Проверка по версии файла в git: есть ли строка в указанном коммите.

Нужна перед публикацией замечания: строка из отчёта должна существовать в той версии файла, по которой ревью. Если её
нет — замечание устарело или ссылается не туда.
"""
import subprocess


def read_file(repo_dir, sha, path):
    """Текст файла в коммите или None, если его там нет."""
    r = subprocess.run(["git", "-C", repo_dir, "show", f"{sha}:{path}"],
                       capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        return None
    return r.stdout


def line_exists(repo_dir, sha, path, line):
    """True, если в файле path в коммите sha есть строка с номером line (нумерация с 1)."""
    text = read_file(repo_dir, sha, path)
    if text is None or line < 1:
        return False
    return line <= len(text.splitlines())


def line_text(repo_dir, sha, path, line):
    """Текст строки или None — для вывода в доказательство проверки."""
    text = read_file(repo_dir, sha, path)
    if text is None or line < 1:
        return None
    lines = text.splitlines()
    return lines[line - 1] if line <= len(lines) else None
