"""Тесты локальных артефактов (provision-artifacts, ACCESS.txt, RSA оператора)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpconnect_install import defaults as d
from vpconnect_install.config import ProvisionConfig
from vpconnect_install.outputs import (
    AccessFileState,
    ArtifactBundle,
    check_artifacts_base_writable,
    default_artifacts_base,
    open_directory_in_file_manager,
    prepare_artifact_dir,
    write_access_file,
    write_secret_file,
)


def _minimal_config(**overrides: object) -> ProvisionConfig:
    base = dict(
        host="srv.example",
        port=22,
        root_password="pw",
        auto_setup=False,
        set_wireguard=True,
        set_mtproxy=True,
        set_vpmanage=True,
        wg_port=d.WG_PORT_DEFAULT,
        mtproxy_port=d.MTPROXY_PORT_DEFAULT,
        vpm_http_port=d.VPM_HTTP_PORT_DEFAULT,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    base.update(overrides)
    return ProvisionConfig(**base)  # type: ignore[arg-type]


def test_default_artifacts_base_relative_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert default_artifacts_base() == tmp_path / "provision-artifacts"
    assert default_artifacts_base(tmp_path / "sub") == tmp_path / "sub" / "provision-artifacts"


def test_check_artifacts_base_writable_ok(tmp_path: Path) -> None:
    logs: list[str] = []
    base = tmp_path / "provision-artifacts"
    check_artifacts_base_writable(base, logs.append)
    assert base.is_dir()
    assert logs == []


def test_check_artifacts_base_writable_raises_on_probe_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "provision-artifacts"
    base.mkdir(parents=True)
    real_write = Path.write_text

    def selective_write(self: Path, *args: object, **kwargs: object) -> object:
        if self.name == ".vpconnect-install-write-probe":
            raise OSError("simulated write failure")
        return real_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", selective_write)
    logs: list[str] = []

    with pytest.raises(RuntimeError, match="provision-artifacts"):
        check_artifacts_base_writable(base, logs.append)
    assert logs and "Ошибка" in logs[0]


def test_open_directory_skips_missing(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    open_directory_in_file_manager(missing)  # no exception


@patch("vpconnect_install.outputs.subprocess.Popen")
@patch("vpconnect_install.outputs.sys.platform", "darwin")
def test_open_directory_macos_open(mock_popen: MagicMock, tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    open_directory_in_file_manager(tmp_path)
    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    assert args[0][:2] == ["open", str(tmp_path.resolve())]
    assert kwargs.get("start_new_session") is True


@patch("vpconnect_install.outputs.subprocess.Popen")
@patch("vpconnect_install.outputs.sys.platform", "linux")
def test_open_directory_linux_xdg(mock_popen: MagicMock, tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    open_directory_in_file_manager(tmp_path)
    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    assert args[0][:2] == ["xdg-open", str(tmp_path.resolve())]
    assert kwargs.get("start_new_session") is True


@patch("vpconnect_install.outputs.os.startfile")
@patch("vpconnect_install.outputs.sys.platform", "win32")
def test_open_directory_win32(mock_startfile: MagicMock, tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    open_directory_in_file_manager(tmp_path)
    mock_startfile.assert_called_once_with(str(tmp_path.resolve()))


def test_prepare_artifact_dir_no_auto_setup(tmp_path: Path) -> None:
    cfg = _minimal_config(auto_setup=False)
    bundle = prepare_artifact_dir(cfg, base=tmp_path)
    assert bundle.root.is_dir()
    assert bundle.private_key_path is None
    assert bundle.public_key_path is None


def test_prepare_artifact_dir_auto_setup_creates_keys(tmp_path: Path) -> None:
    cfg = _minimal_config(auto_setup=True)
    bundle = prepare_artifact_dir(cfg, base=tmp_path)
    assert bundle.private_key_path and bundle.private_key_path.is_file()
    assert bundle.public_key_path and bundle.public_key_path.is_file()
    assert bundle.public_key_openssh.startswith("ssh-rsa ") or bundle.public_key_openssh.startswith("ssh-ed25519 ")


def test_prepare_artifact_dir_sanitizes_host_in_path(tmp_path: Path) -> None:
    cfg = _minimal_config(host="bad:host/name", auto_setup=False)
    bundle = prepare_artifact_dir(cfg, base=tmp_path)
    assert "bad_host_name" in bundle.root.name or "bad" in bundle.root.name


def test_write_secret_file(tmp_path: Path) -> None:
    bundle = ArtifactBundle(root=tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = write_secret_file(bundle, "sec.txt", "  hello  \n")
    assert p.read_text(encoding="utf-8") == "hello\n"


def test_write_access_file_generated_key_and_ports(tmp_path: Path) -> None:
    cfg = _minimal_config(
        host="10.0.0.1",
        effective_domain_or_ip="10.0.0.1",
        new_ssh_port=2222,
        vpm_password="admin",
    )
    bundle = ArtifactBundle(
        root=tmp_path,
        private_key_path=tmp_path / "id_rsa",
        public_key_path=tmp_path / "id_rsa.pub",
        public_key_openssh="ssh-rsa AAA",
    )
    tmp_path.mkdir(parents=True, exist_ok=True)
    state = AccessFileState(mtproxy_secret="deadbeef", wireguard_public_key="wgpub\n", last_saved_after="t0")
    path = write_access_file(bundle, cfg, state)
    text = path.read_text(encoding="utf-8")
    assert "Host: 10.0.0.1" in text
    assert "SSH port: 2222" in text
    assert "-i " in text and "id_rsa" in text
    assert "MTProxy secret (hex): deadbeef" in text
    assert "WireGuard server public key:" in text
    assert "wgpub" in text
    assert "VPManage admin password: admin" in text
    assert "Last artifact save: t0" in text


def test_write_access_file_ssh_uses_root_key_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key_file = tmp_path / "root_key"
    key_file.write_text("dummy", encoding="utf-8")
    cfg = _minimal_config(
        root_private_key=str(key_file),
        new_ssh_port=None,
        effective_domain_or_ip=None,
    )
    bundle = ArtifactBundle(root=tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    text = write_access_file(bundle, cfg, AccessFileState()).read_text(encoding="utf-8")
    assert "-i " in text and "root_key" in text
    assert "SSH port: 22" in text


def test_write_access_file_plain_ssh_no_key(tmp_path: Path) -> None:
    cfg = _minimal_config(host="h", root_private_key="")
    bundle = ArtifactBundle(root=tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    text = write_access_file(bundle, cfg, AccessFileState()).read_text(encoding="utf-8")
    assert "SSH command: ssh -p 22 root@h" in text
    assert "-i " not in text.split("SSH command:")[1].split("\n")[0]


def test_write_access_file_optional_sections_off(tmp_path: Path) -> None:
    cfg = _minimal_config(
        set_wireguard=False,
        set_mtproxy=False,
        set_vpmanage=False,
        domain="ex.com",
    )
    bundle = ArtifactBundle(root=tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    text = write_access_file(bundle, cfg, AccessFileState()).read_text(encoding="utf-8")
    assert "WireGuard UDP port" not in text
    assert "MTProxy TCP port" not in text
    assert "VPManage" not in text
    assert "Domain (FQDN): ex.com" in text
