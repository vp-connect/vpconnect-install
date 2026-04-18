"""
Build raw.githubusercontent.com URLs for vpconnect-configure scripts 00-03.

Depends on ``shared.defaults`` and ``core.github_repo.parse_github_repo_url``.
"""

from __future__ import annotations

from core.github_repo import parse_github_repo_url
from shared import defaults as d


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
