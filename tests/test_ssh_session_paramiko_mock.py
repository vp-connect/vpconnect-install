"""SSHSession с подменой Paramiko (успешные пути exec/SFTP/run_remote_shell)."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from vpconnect_install.ssh_session import SSHSession


@pytest.fixture
def mock_new_client() -> MagicMock:
    with patch("vpconnect_install.ssh_session._new_ssh_client") as m:
        yield m


def test_connect_with_password_uses_paramiko(mock_new_client: MagicMock) -> None:
    mock_c = MagicMock()
    mock_new_client.return_value = mock_c
    s = SSHSession("h", 22, "root", password="pw", private_key_path="", log=lambda _m: None)
    s.connect()
    assert s.auth_method == "password"
    mock_c.connect.assert_called()


def test_connect_with_key_file_success(mock_new_client: MagicMock, tmp_path) -> None:
    key_path = tmp_path / "id_rsa"
    key_path.write_text("dummy-key", encoding="utf-8")
    mock_c = MagicMock()
    mock_new_client.return_value = mock_c
    with patch("vpconnect_install.ssh_session._load_private_key", return_value=MagicMock(name="pkey")):
        s = SSHSession("h", 22, "root", password="", private_key_path=str(key_path), log=lambda _m: None)
        s.connect()
    assert s.auth_method == "private_key"


def test_exec_command_decodes_utf8(mock_new_client: MagicMock) -> None:
    mock_c = MagicMock()
    mock_new_client.return_value = mock_c
    stdin, stdout, stderr = MagicMock(), MagicMock(), MagicMock()
    stdout.read.return_value = b"out\xc3\xa9"
    stderr.read.return_value = b"err"
    stdout.channel.recv_exit_status.return_value = 42
    mock_c.exec_command.return_value = (stdin, stdout, stderr)

    s = SSHSession("h", 22, "root", password="x", log=lambda _m: None)
    s.connect()
    code, o, e = s.exec_command("true", timeout=10)
    assert code == 42
    assert "out" in o
    stdin.close.assert_called_once()


def test_upload_bytes_creates_remote_dirs(mock_new_client: MagicMock) -> None:
    mock_c = MagicMock()
    mock_new_client.return_value = mock_c
    sftp = MagicMock()
    mock_c.open_sftp.return_value = sftp
    sftp.stat.side_effect = OSError("no")
    fh = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = fh
    cm.__exit__.return_value = None
    sftp.open.return_value = cm

    s = SSHSession("h", 22, "root", password="x", log=lambda _m: None)
    s.connect()
    s.upload_bytes("/tmp/a/b/c.txt", b"data")

    sftp.mkdir.assert_called()
    fh.write.assert_called_once_with(b"data")
    sftp.close.assert_called_once()


def test_download_bytes(mock_new_client: MagicMock) -> None:
    mock_c = MagicMock()
    mock_new_client.return_value = mock_c
    sftp = MagicMock()
    mock_c.open_sftp.return_value = sftp
    fh = MagicMock()
    fh.read.return_value = b"xyz"
    cm = MagicMock()
    cm.__enter__.return_value = fh
    cm.__exit__.return_value = None
    sftp.open.return_value = cm

    s = SSHSession("h", 22, "root", password="x", log=lambda _m: None)
    s.connect()
    assert s.download_bytes("/r/f") == b"xyz"


def test_run_remote_shell_exit_status(mock_new_client: MagicMock) -> None:
    mock_c = MagicMock()
    mock_new_client.return_value = mock_c
    transport = MagicMock()
    mock_c.get_transport.return_value = transport
    chan = MagicMock()
    transport.open_session.return_value = chan
    chan.makefile.return_value = BytesIO(b"")
    chan.makefile_stderr.return_value = BytesIO(b"")
    chan.recv_exit_status.return_value = 7

    s = SSHSession("h", 22, "root", password="x", log=lambda _m: None)
    s.connect()
    assert s.run_remote_shell("echo hi", timeout=5, get_pty=True) == 7
    chan.get_pty.assert_called_once()
    chan.exec_command.assert_called_once_with("echo hi")


def test_run_remote_shell_no_transport_raises(mock_new_client: MagicMock) -> None:
    mock_c = MagicMock()
    mock_new_client.return_value = mock_c
    mock_c.get_transport.return_value = None
    s = SSHSession("h", 22, "root", password="x", log=lambda _m: None)
    s.connect()
    with pytest.raises(RuntimeError, match="transport"):
        s.run_remote_shell("x")


def test_close_clears_client(mock_new_client: MagicMock) -> None:
    mock_c = MagicMock()
    mock_new_client.return_value = mock_c
    s = SSHSession("h", 22, "root", password="x", log=lambda _m: None)
    s.connect()
    s.close()
    mock_c.close.assert_called()
    with pytest.raises(RuntimeError):
        _ = s.client


def test_attempt_private_key_connect_fails_closes_client(mock_new_client: MagicMock, tmp_path) -> None:
    key_path = tmp_path / "k"
    key_path.write_text("x", encoding="utf-8")
    mock_c = MagicMock()
    mock_new_client.return_value = mock_c
    mock_c.connect.side_effect = OSError("refused")
    with patch("vpconnect_install.ssh_session._load_private_key", return_value=MagicMock(name="pkey")):
        s = SSHSession("h", 22, "root", private_key_path=str(key_path), log=lambda _m: None)
        assert s._attempt_private_key() is False
    mock_c.close.assert_called()


def test_mkdir_p_sftp_ignores_existing(mock_new_client: MagicMock) -> None:
    mock_c = MagicMock()
    mock_new_client.return_value = mock_c
    sftp = MagicMock()
    mock_c.open_sftp.return_value = sftp
    sftp.stat.return_value = MagicMock()
    fh = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = fh
    cm.__exit__.return_value = None
    sftp.open.return_value = cm

    s = SSHSession("h", 22, "root", password="x", log=lambda _m: None)
    s.connect()
    s.upload_bytes("/x/y.txt", b"1")
    sftp.mkdir.assert_not_called()
