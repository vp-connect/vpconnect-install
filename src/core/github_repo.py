"""
Parse GitHub repository URLs (owner, repo) without network I/O.

Used by ``config`` validation and ``server.remote_scripts_fetch`` for raw URLs.
"""
from __future__ import annotations

import re

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
