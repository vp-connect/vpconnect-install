"""
Локальные артефакты прогона: каталог ``provision-artifacts``, RSA-ключ оператора, ACCESS.txt.

Проверка прав на запись до SSH и открытие каталога в файловом менеджере после GUI.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from vpconnect_install import defaults as d
from vpconnect_install.config import ProvisionConfig


@dataclass
class ArtifactBundle:
    """Paths and material for one provisioning run."""

    root: Path
    private_key_path: Path
    public_key_path: Path
    public_key_openssh: str


@dataclass
class AccessFileState:
    """Накопление полей для ACCESS.txt между шагами (WireGuard / MTProxy заполняются по мере готовности)."""

    mtproxy_secret: str | None = None
    wireguard_public_key: str | None = None
    last_saved_after: str = ""


def default_artifacts_base(cwd: Path | None = None) -> Path:
    base = cwd or Path.cwd()
    return base / "provision-artifacts"


def check_artifacts_base_writable(base: Path, log: Callable[[str], None]) -> None:
    """
    Проверка до SSH: в каталог provision-artifacts (или переданный base) можно писать файлы результатов.
    Иначе в лог — пояснение про потерю доступа к серверу и паролям.
    """
    resolved = base.resolve()
    try:
        resolved.mkdir(parents=True, exist_ok=True)
        probe = resolved / ".vpconnect-install-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as e:
        log(
            "Ошибка! Нет прав на запись в каталог результатов:\n"
            f"{resolved}\n\n"
            "Если установка сменит пароль root или параметры SSH, без сохранённых в этом каталоге "
            "ключей и паролей вы можете потерять доступ к серверу. Новые пароли не будут записаны на диск.\n\n"
            f"Укажите каталог с правом записи или смените рабочую папку.\nТехническая причина: {e}"
        )
        raise RuntimeError("Нет доступа на запись в каталог provision-artifacts. См. сообщение в логе.") from e


def open_directory_in_file_manager(path: Path) -> None:
    """Открыть каталог в проводнике / Finder / файловом менеджере (без ошибок в UI при сбое)."""
    p = path.resolve()
    if not p.is_dir():
        return
    try:
        if sys.platform == "win32":
            os.startfile(str(p))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)], start_new_session=True)  # noqa: S603
        else:
            subprocess.Popen(["xdg-open", str(p)], start_new_session=True)  # noqa: S603
    except OSError:
        pass


def prepare_artifact_dir(config: ProvisionConfig, base: Path | None = None) -> ArtifactBundle:
    """Создать provision-artifacts/<host>-<timestamp>/ и пару OpenSSH RSA (размер — ``OPERATOR_SSH_RSA_KEY_BITS``)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_host = config.host.replace(":", "_").replace("/", "_")
    root = (base or default_artifacts_base()) / f"{safe_host}-{ts}"
    root.mkdir(parents=True, exist_ok=True)

    priv = rsa.generate_private_key(public_exponent=65537, key_size=d.OPERATOR_SSH_RSA_KEY_BITS)
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub = priv.public_key()
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )
    pub_str = pub_bytes.decode("ascii")

    pk = root / "id_rsa"
    pubp = root / "id_rsa.pub"
    pk.write_bytes(priv_pem)
    pubp.write_bytes(pub_bytes + b"\n")
    try:
        pk.chmod(0o600)
    except NotImplementedError:
        pass

    return ArtifactBundle(
        root=root,
        private_key_path=pk,
        public_key_path=pubp,
        public_key_openssh=pub_str,
    )


def write_secret_file(bundle: ArtifactBundle, filename: str, content: str) -> Path:
    p = bundle.root / filename
    p.write_text(content.strip() + "\n", encoding="utf-8")
    try:
        p.chmod(0o600)
    except NotImplementedError:
        pass
    return p


def write_access_file(
    bundle: ArtifactBundle,
    config: ProvisionConfig,
    state: AccessFileState,
) -> Path:
    """Записать ACCESS.txt из конфигурации и накопленного ``state`` (можно вызывать многократно)."""
    target = config.effective_domain_or_ip or config.host
    ssh_port = config.new_ssh_port if config.new_ssh_port is not None else config.port
    ssh_cmd = f"ssh -i {shlex.quote(str(bundle.private_key_path))} -p {ssh_port} root@{shlex.quote(target)}"
    lines = [
        f"Host: {config.host}",
        f"SSH effective target: {target}",
        f"SSH port: {ssh_port}",
        f"Operator private key (generated): {bundle.private_key_path}",
        f"SSH command: {ssh_cmd}",
        "",
    ]
    if config.set_wireguard:
        lines.append(f"WireGuard UDP port: {config.wg_port}")
    if config.set_mtproxy:
        lines.append(f"MTProxy TCP port: {config.mtproxy_port}")
    if state.mtproxy_secret:
        lines.append(f"MTProxy secret (hex): {state.mtproxy_secret}")
    if state.wireguard_public_key:
        lines.extend(["", "WireGuard server public key:", state.wireguard_public_key.strip(), ""])
    if config.set_vpmanage:
        lines.extend(
            [
                f"VPManage HTTP port: {config.vpm_http_port}",
                f"VPManage URL: http://{target}:{config.vpm_http_port}/",
            ]
        )
        if config.vpm_password.strip():
            lines.append(f"VPManage admin password: {config.vpm_password.strip()}")
    lines.extend(
        [
            "",
            f"use_public_ip: {config.use_public_ip}",
        ]
    )
    if config.domain:
        lines.append(f"Domain (FQDN): {config.domain}")
    if config.domain_client_key.strip():
        lines.append("Domain client key: (set)")
    if state.last_saved_after:
        lines.extend(["", f"Last artifact save: {state.last_saved_after}"])
    path = bundle.root / "ACCESS.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
