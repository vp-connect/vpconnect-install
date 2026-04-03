"""
Обёртка над Paramiko: подключение по ключу или паролю, exec, SFTP, потоковый вывод в лог.
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Callable
from pathlib import Path
from typing import IO, TYPE_CHECKING

import paramiko

if TYPE_CHECKING:
    from paramiko import PKey, SFTPClient, SSHClient

LogFn = Callable[[str], None]


def _load_private_key(path: str, passphrase: str | None) -> PKey:
    pp = passphrase if passphrase else None
    last_err: Exception | None = None
    for loader in (
        paramiko.Ed25519Key,
        paramiko.RSAKey,
        paramiko.ECDSAKey,
    ):
        try:
            return loader.from_private_key_file(path, password=pp)
        except Exception as e:
            last_err = e
            continue
    raise ValueError(f"Could not load private key from {path}: {last_err}")


def _new_ssh_client() -> SSHClient:
    """Новый SSHClient с политикой AutoAddPolicy."""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    return c


class SSHSession:
    """Paramiko: try private key first, then password; SFTP; streaming exec."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str = "",
        *,
        private_key_path: str = "",
        private_key_passphrase: str = "",
        connect_timeout: int = 30,
        log: LogFn | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key_path = private_key_path.strip()
        self.private_key_passphrase = private_key_passphrase
        self.connect_timeout = connect_timeout
        self._log = log or (lambda _m: None)
        self._client: SSHClient | None = None
        self._auth_method: str = ""

    def _connect_common_kwargs(self) -> dict:
        return {
            "hostname": self.host,
            "port": self.port,
            "username": self.username,
            "timeout": self.connect_timeout,
            "banner_timeout": self.connect_timeout,
            "auth_timeout": self.connect_timeout,
            "allow_agent": False,
            "look_for_keys": False,
        }

    def _attempt_private_key(self) -> bool:
        key_path = self.private_key_path.strip()
        if not key_path or not Path(key_path).is_file():
            return False
        c = _new_ssh_client()
        try:
            pkey = _load_private_key(key_path, self.private_key_passphrase or None)
            c.connect(pkey=pkey, **self._connect_common_kwargs())
            self._client = c
            self._auth_method = "private_key"
            return True
        except Exception:
            try:
                c.close()
            except Exception:
                pass
            return False

    def _attempt_password(self) -> bool:
        if not self.password:
            return False
        c = _new_ssh_client()
        try:
            c.connect(password=self.password, **self._connect_common_kwargs())
            self._client = c
            self._auth_method = "password"
            return True
        except Exception:
            try:
                c.close()
            except Exception:
                pass
            return False

    def connect(self) -> None:
        self.close()
        self._log(f"[Подключение] Подключаюсь к {self.host}:{self.port}")

        key_path = self.private_key_path.strip()
        use_key = bool(key_path and Path(key_path).is_file())

        if use_key:
            self._log("[Подключение] Использую SSH Key")
            if self._attempt_private_key():
                self._log("[Подключение] Соединение успешно")
                return
            self._log("[Подключение] Ошибка подключения с SSH Key")

        if self.password:
            if self._attempt_password():
                self._log("[Подключение] Соединение успешно")
                return
            self._log("[Подключение] Ошибка подключения с паролем")

        self._log("[Подключение] Не удалось установить соединение с сервером")
        raise RuntimeError("SSH: не удалось подключиться к серверу")

    @property
    def auth_method(self) -> str:
        return self._auth_method

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    @property
    def client(self) -> SSHClient:
        if self._client is None:
            raise RuntimeError("SSH not connected")
        return self._client

    def upload_bytes(self, remote_path: str, data: bytes) -> None:
        sftp: SFTPClient = self.client.open_sftp()
        try:
            dirname = remote_path.rsplit("/", 1)[0]
            if dirname:
                self._mkdir_p_sftp(sftp, dirname)
            with sftp.open(remote_path, "wb") as f:
                f.write(data)
        finally:
            sftp.close()
        self._log(f"Uploaded {len(data)} bytes to {remote_path}")

    def download_bytes(self, remote_path: str) -> bytes:
        sftp: SFTPClient = self.client.open_sftp()
        try:
            with sftp.open(remote_path, "rb") as f:
                return f.read()
        finally:
            sftp.close()

    def _mkdir_p_sftp(self, sftp: SFTPClient, remote_dir: str) -> None:
        parts = remote_dir.strip("/").split("/")
        cur = ""
        for p in parts:
            if not p:
                continue
            cur = f"{cur}/{p}" if cur else f"/{p}"
            try:
                sftp.stat(cur)
            except OSError:
                try:
                    sftp.mkdir(cur)
                except OSError:
                    pass

    def run_remote_shell(
        self,
        command: str,
        *,
        timeout: int | None = None,
        get_pty: bool = True,
    ) -> int:
        transport = self.client.get_transport()
        if transport is None:
            raise RuntimeError("SSH transport not available")
        chan = transport.open_session()
        if get_pty:
            chan.get_pty()
        chan.exec_command(command)

        out = chan.makefile("r", -1)
        err = chan.makefile_stderr("r", -1)

        def pump(name: str, stream: IO[str]) -> None:
            for line in iter(stream.readline, ""):
                if line:
                    self._log(f"[{name}] {line.rstrip()}")

        t1 = threading.Thread(target=pump, args=("stdout", out), daemon=True)
        t2 = threading.Thread(target=pump, args=("stderr", err), daemon=True)
        t1.start()
        t2.start()

        status_holder: list[int] = []

        def wait_exit() -> None:
            status_holder.append(chan.recv_exit_status())

        t3 = threading.Thread(target=wait_exit, daemon=True)
        t3.start()
        t3.join(timeout=timeout)
        if t3.is_alive():
            try:
                chan.close()
            except Exception:
                pass
            raise TimeoutError(f"command exceeded {timeout}s")

        exit_status = status_holder[0] if status_holder else chan.recv_exit_status()
        t1.join(timeout=5)
        t2.join(timeout=5)
        chan.close()
        return exit_status

    def exec_command(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> tuple[int, str, str]:
        stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
        try:
            out_b = stdout.read()
            err_b = stderr.read()
            code = stdout.channel.recv_exit_status()
            return code, out_b.decode("utf-8", errors="replace"), err_b.decode("utf-8", errors="replace")
        finally:
            stdin.close()

    def test_connect(self) -> bool:
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
            sock.close()
            return True
        except OSError:
            return False
