from __future__ import annotations

import pytest

from vpconnect_install.remote_scripts_fetch import parse_github_repo_url, script_raw_url
from vpconnect_install.version import scripts_git_branch


def test_parse_github_repo_url() -> None:
    assert parse_github_repo_url("https://github.com/foo/bar") == ("foo", "bar")
    assert parse_github_repo_url("https://github.com/foo/bar.git") == ("foo", "bar")


def test_parse_github_repo_url_invalid() -> None:
    with pytest.raises(ValueError):
        parse_github_repo_url("https://gitlab.com/foo/bar")


def test_script_raw_url() -> None:
    u = script_raw_url("https://github.com/acme/scripts", "v1.0.0", "base_ufw_prepare.sh")
    assert u == "https://raw.githubusercontent.com/acme/scripts/v1.0.0/remote/base_ufw_prepare.sh"


def test_scripts_git_branch() -> None:
    assert scripts_git_branch("0.1.0") == "v0.1.0"
    assert scripts_git_branch("v0.1.0") == "v0.1.0"
    assert scripts_git_branch("0.1.0dev") == "main"
