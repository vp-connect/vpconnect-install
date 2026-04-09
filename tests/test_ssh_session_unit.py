"""Юнит-тесты SSHSession без живого sshd."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import paramiko
import pytest

from vpconnect_install import ssh_session as ss
from vpconnect_install.ssh_session import SSHSession


def test_load_private_key_invalid_path() -> None:
    with pytest.raises(ValueError, match="Could not load private key"):
        ss._load_private_key(str(Path("/nonexistent/key")), None)


def test_load_private_key_rsa_minimal(tmp_path: Path) -> None:
    key = paramiko.RSAKey.generate(1024)
    p = tmp_path / "id_rsa"
    key.write_private_key_file(str(p))
    loaded = ss._load_private_key(str(p), None)
    assert isinstance(loaded, paramiko.RSAKey)


def test_connect_raises_when_all_auth_fail() -> None:
    logs: list[str] = []
    s = SSHSession("127.0.0.1", 22, "root", password="", private_key_path="", log=logs.append)
    with patch.object(s, "_attempt_private_key", return_value=False), patch.object(s, "_attempt_password", return_value=False):
        with pytest.raises(RuntimeError, match="не удалось подключиться"):
            s.connect()
    assert any("Не удалось" in m for m in logs)


def test_test_connect_refused_fast() -> None:
    s = SSHSession("127.0.0.1", 1, "root", connect_timeout=1)
    assert s.test_connect() is False


def test_client_property_not_connected() -> None:
    s = SSHSession("h", 22, "root")
    with pytest.raises(RuntimeError, match="not connected"):
        _ = s.client


def test_close_idempotent() -> None:
    s = SSHSession("h", 22, "root")
    s.close()
    s.close()


def test_attempt_private_key_skips_missing_file() -> None:
    s = SSHSession("h", 22, "root", private_key_path="/no/such/file")
    assert s._attempt_private_key() is False


def test_attempt_password_skips_empty() -> None:
    s = SSHSession("h", 22, "root", password="")
    assert s._attempt_password() is False
