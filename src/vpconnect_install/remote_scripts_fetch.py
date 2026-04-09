"""
Построение URL для сырого содержимого файлов на GitHub (``raw.githubusercontent.com``).

Используется при загрузке скриптов **00–03** и в тестах; путь к скрипту внутри репозитория задаётся
через :data:`vpconnect_install.defaults.REMOTE_SCRIPTS_REPO_PATH`.
"""

from __future__ import annotations

import re

from vpconnect_install import defaults as d

_GITHUB_REPO_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


def parse_github_repo_url(url: str) -> tuple[str, str]:
    """Return (owner, repo) for https://github.com/owner/repo."""
    u = url.strip().rstrip("/")
    m = _GITHUB_REPO_RE.match(u)
    if not m:
        raise ValueError(f"Not a github.com repository URL: {url!r}")
    return m.group("owner"), m.group("repo")


def github_raw_file_url(repo_url: str, branch: str, relative_path: str) -> str:
    """Произвольный файл в репозитории на raw.githubusercontent.com."""
    owner, repo = parse_github_repo_url(repo_url)
    rel = relative_path.strip().lstrip("/")
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{rel}"


def script_raw_url(repo_url: str, branch: str, script_name: str) -> str:
    """URL файла ``script_name`` под префиксом ``REMOTE_SCRIPTS_REPO_PATH`` (например ``remote/00_…sh``)."""
    prefix = d.REMOTE_SCRIPTS_REPO_PATH.strip("/")
    path = f"{prefix}/{script_name}" if prefix else script_name
    return github_raw_file_url(repo_url, branch, path)
