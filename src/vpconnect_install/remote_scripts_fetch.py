"""GitHub raw URL helpers for vpconnect-configure (и др.)."""

from __future__ import annotations

import re

import requests

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
    prefix = d.REMOTE_SCRIPTS_REPO_PATH.strip("/")
    path = f"{prefix}/{script_name}" if prefix else script_name
    return github_raw_file_url(repo_url, branch, path)


def probe_scripts_available(repo_url: str, branch: str, script_name: str, timeout: int = 15) -> bool:
    """Return True if raw URL responds with HTTP 200."""
    if not repo_url.strip():
        return False
    try:
        url = script_raw_url(repo_url, branch, script_name)
        r = requests.head(url, allow_redirects=True, timeout=timeout)
        return r.status_code == 200
    except requests.RequestException:
        return False
