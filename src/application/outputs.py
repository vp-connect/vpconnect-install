"""
Локальные артефакты прогона: каталог ``provision-artifacts``, при auto_setup — RSA-ключ оператора, ACCESS.txt.

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

from shared import defaults as d
from config import ProvisionConfig


@dataclass
class ArtifactBundle:
    """
    Каталог одного прогона и опциональная пара RSA «оператора».

    Ключи создаются только в режиме ``auto_setup`` и передаются в ``04_setsystemaccess.sh``.
    """

    root: Path
    private_key_path: Path | None = None
    public_key_path: Path | None = None
    public_key_openssh: str = ""


@dataclass
class AccessFileState:
    """
    Данные для повторной записи ``ACCESS.txt`` между шагами 06–07 (ключи и секреты по мере появления).
    """

    mtproxy_secret: str | None = None
    vpserver_public_key: str | None = None
    last_saved_after: str = ""


def default_artifacts_base(cwd: Path | None = None) -> Path:
    """Базовый каталог ``provision-artifacts`` относительно ``cwd`` (по умолчанию текущая директория)."""
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


def _write_operator_rsa_keypair(root: Path) -> ArtifactBundle:
    """Сгенерировать ``id_rsa`` / ``id_rsa.pub`` в ``root``; вернуть заполненный :class:`ArtifactBundle`."""
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
    return ArtifactBundle(root=root, private_key_path=pk, public_key_path=pubp, public_key_openssh=pub_str)


def _access_ssh_command(
    bundle: ArtifactBundle,
    config: ProvisionConfig,
    target: str,
    ssh_port: int,
) -> str:
    """Строка ``ssh …`` для ``ACCESS.txt`` (сгенерированный ключ, путь root-ключа или без ``-i``)."""
    key_for_ssh: Path | None = bundle.private_key_path
    if key_for_ssh is None:
        rk = config.root_private_key.strip()
        if rk and Path(rk).is_file():
            key_for_ssh = Path(rk)
    if key_for_ssh is not None:
        return f"ssh -i {shlex.quote(str(key_for_ssh))} -p {ssh_port} root@{shlex.quote(target)}"
    return f"ssh -p {ssh_port} root@{shlex.quote(target)}"


def prepare_artifact_dir(config: ProvisionConfig, base: Path | None = None) -> ArtifactBundle:
    """Создать ``provision-artifacts/<host>-<timestamp>/``; RSA оператора — только при ``config.auto_setup``."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_host = config.host.replace(":", "_").replace("/", "_")
    root = (base or default_artifacts_base()) / f"{safe_host}-{ts}"
    root.mkdir(parents=True, exist_ok=True)
    if not config.auto_setup:
        return ArtifactBundle(root=root)
    return _write_operator_rsa_keypair(root)


def write_secret_file(bundle: ArtifactBundle, filename: str, content: str) -> Path:
    """Записать текстовый секрет в каталог артефактов с правами ``0600`` (где поддерживается ОС)."""
    p = bundle.root / filename
    p.write_text(content.strip() + "\n", encoding="utf-8")
    try:
        p.chmod(0o600)
    except NotImplementedError:
        pass
    return p


def _access_header_lines(bundle: ArtifactBundle, config: ProvisionConfig, target: str, ssh_port: int) -> list[str]:
    ssh_cmd = _access_ssh_command(bundle, config, target, ssh_port)
    lines = [
        f"Host: {config.host}",
        f"SSH effective target: {target}",
        f"SSH port: {ssh_port}",
    ]
    if bundle.private_key_path is not None:
        lines.append(f"Operator private key (generated): {bundle.private_key_path}")
    lines.extend([f"SSH command: {ssh_cmd}", ""])
    return lines


def _access_vpserver_lines(config: ProvisionConfig) -> list[str]:
    if not config.set_vpserver:
        return []
    lines = [f"VP server UDP port: {config.vp_port}"]
    wgn = (config.vp_client_network or "").strip()
    if wgn:
        lines.append(f"VP server address (normalized): {wgn}")
    return lines


def _access_mtproxy_lines(config: ProvisionConfig, state: AccessFileState) -> list[str]:
    lines: list[str] = []
    if config.set_mtproxy:
        lines.append(f"MTProxy TCP port: {config.mtproxy_port}")
    if state.mtproxy_secret:
        lines.append(f"MTProxy secret (hex): {state.mtproxy_secret}")
    return lines


def _access_vp_public_key_lines(state: AccessFileState) -> list[str]:
    if not state.vpserver_public_key:
        return []
    return ["", "VP server public key:", state.vpserver_public_key.strip(), ""]


def _access_vpmanage_lines(config: ProvisionConfig, target: str) -> list[str]:
    if not config.set_vpmanage:
        return []
    lines = [
        f"VPManage HTTP port: {config.vpm_http_port}",
        f"VPManage URL: http://{target}:{config.vpm_http_port}/",
    ]
    if config.vpm_password.strip():
        lines.append(f"VPManage admin password: {config.vpm_password.strip()}")
    return lines


def _access_footer_lines(config: ProvisionConfig, state: AccessFileState) -> list[str]:
    lines = ["", f"use_public_ip: {config.use_public_ip}"]
    if config.domain:
        lines.append(f"Domain (FQDN): {config.domain}")
    if state.last_saved_after:
        lines.extend(["", f"Last artifact save: {state.last_saved_after}"])
    return lines


def write_access_file(
    bundle: ArtifactBundle,
    config: ProvisionConfig,
    state: AccessFileState,
) -> Path:
    """Записать ``ACCESS.txt`` из конфигурации и накопленного ``state`` (идемпотентно по содержимому файла)."""
    target = config.effective_domain_or_ip or config.host
    ssh_port = config.new_ssh_port if config.new_ssh_port is not None else config.port
    lines: list[str] = []
    lines.extend(_access_header_lines(bundle, config, target, ssh_port))
    lines.extend(_access_vpserver_lines(config))
    lines.extend(_access_mtproxy_lines(config, state))
    lines.extend(_access_vp_public_key_lines(state))
    lines.extend(_access_vpmanage_lines(config, target))
    lines.extend(_access_footer_lines(config, state))
    path = bundle.root / "ACCESS.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
