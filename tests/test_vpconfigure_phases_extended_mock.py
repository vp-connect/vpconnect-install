"""run_04_connect_steps и run_vpconfigure_phases_05_to_08 — все ветки с моками."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vpconnect_install import defaults as d
from vpconnect_install.config import ProvisionConfig
from vpconnect_install.outputs import AccessFileState, ArtifactBundle
from vpconnect_install.vpconfigure_provision import (
    _chmod_remote,
    run_04_connect_steps,
    run_vpconfigure_phases_05_to_08,
)


def _cfg(**kw: object) -> ProvisionConfig:
    base = dict(
        host="h",
        port=22,
        root_password="p",
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    base.update(kw)
    return ProvisionConfig(**base)  # type: ignore[arg-type]


@patch("vpconnect_install.vpconfigure_provision._run_configure_script")
def test_run_04_auto_setup_with_firewall_flag(mock_run: MagicMock) -> None:
    session = MagicMock()
    session.exec_command.return_value = (0, "", "")
    cfg = _cfg(auto_setup=True, enable_firewall=True)
    cfg.apply_auto_setup()
    bundle = ArtifactBundle(root=MagicMock(), public_key_openssh="ssh-rsa X")
    run_04_connect_steps(
        session,
        "/root",
        "/cfg",
        "debian",
        cfg,
        bundle,
        lambda _m: None,
        60,
        artifact_persist=lambda _x: None,
    )
    extra = mock_run.call_args[0][5]
    assert "--enable-firewall" in extra


@patch("vpconnect_install.vpconfigure_provision._run_configure_script")
def test_run_04_auto_setup_uploads_operator_key(mock_run: MagicMock) -> None:
    session = MagicMock()
    session.exec_command.return_value = (0, "", "")
    cfg = _cfg(auto_setup=True)
    cfg.apply_auto_setup()
    bundle = ArtifactBundle(
        root=MagicMock(),
        public_key_openssh="ssh-rsa AAA",
    )
    persist: list[str] = []
    run_04_connect_steps(
        session,
        "/root",
        "/cfg",
        "debian",
        cfg,
        bundle,
        lambda _m: None,
        60,
        artifact_persist=persist.append,
    )
    assert session.upload_bytes.call_count >= 2
    mock_run.assert_called_once()
    session.exec_command.assert_called()
    assert persist == ["после 04_setsystemaccess.sh"]


@patch("vpconnect_install.vpconfigure_provision._run_configure_script")
def test_run_04_manual_extended_options(mock_run: MagicMock) -> None:
    session = MagicMock()
    session.exec_command.return_value = (0, "", "")
    cfg = _cfg(
        auto_setup=False,
        new_root_password="npw",
        new_ssh_port=2222,
        new_ssh_public_key="ssh-ed25519 X",
        enable_firewall=True,
    )
    bundle = ArtifactBundle(root=MagicMock())
    run_04_connect_steps(
        session,
        "/home",
        "/c",
        "centos",
        cfg,
        bundle,
        lambda _m: None,
        120,
        artifact_persist=lambda _x: None,
    )
    mock_run.assert_called_once()
    assert session.upload_bytes.call_count == 2


def test_chmod_remote_failure() -> None:
    session = MagicMock()
    session.exec_command.return_value = (1, "o", "e")
    logs: list[str] = []
    with pytest.raises(RuntimeError, match="Установка прекращена"):
        _chmod_remote(logs.append, session, "/tmp/f", 10)


@patch("vpconnect_install.vpconfigure_provision._run_configure_script")
def test_phases_05_only_domain(mock_run: MagicMock) -> None:
    session = MagicMock()
    cfg = _cfg(auto_setup=False, set_domain=True, domain="a.example")
    st = AccessFileState()
    run_vpconfigure_phases_05_to_08(
        session,
        "/cfg",
        "debian",
        cfg,
        lambda _m: None,
        60,
        access_state=st,
        artifact_persist=lambda _x: None,
    )
    mock_run.assert_called_once()
    call = mock_run.call_args[0]
    assert call[3] == "05_setdomain.sh"
    assert "--domain" in call[5]


@patch("vpconnect_install.vpconfigure_provision._run_configure_script")
def test_phases_06_wireguard_downloads_key(mock_run: MagicMock) -> None:
    session = MagicMock()
    session.download_bytes.return_value = b"wg-pub-key\n"
    cfg = _cfg(auto_setup=False, set_wireguard=True, set_domain=False, domain=None)
    cfg.set_mtproxy = False
    cfg.set_vpmanage = False
    mock_run.return_value = "result:success; message:ok\n"
    run_vpconfigure_phases_05_to_08(
        session,
        "/cfg",
        "debian",
        cfg,
        lambda _m: None,
        60,
        access_state=AccessFileState(),
        artifact_persist=lambda _x: None,
    )
    assert session.download_bytes.called
    scripts = [c[0][3] for c in mock_run.call_args_list]
    assert "06_setwireguard.sh" in scripts


@patch("vpconnect_install.vpconfigure_provision._run_configure_script")
def test_phases_07_mtproxy_uses_default_secret_path(mock_run: MagicMock) -> None:
    session = MagicMock()
    session.download_bytes.return_value = b"deadbeef"
    cfg = _cfg(auto_setup=False, set_wireguard=False, set_mtproxy=True, set_domain=False, domain=None)
    mock_run.return_value = "result:success; message:ok\n"
    st = AccessFileState()
    run_vpconfigure_phases_05_to_08(
        session,
        "/cfg",
        "freebsd",
        cfg,
        lambda _m: None,
        60,
        access_state=st,
        artifact_persist=lambda _x: None,
    )
    assert st.mtproxy_secret == "deadbeef"


@patch("vpconnect_install.vpconfigure_provision._run_configure_script")
def test_phases_08_with_explicit_vpm_password(mock_run: MagicMock) -> None:
    session = MagicMock()
    cfg = _cfg(
        auto_setup=False,
        set_wireguard=False,
        set_mtproxy=False,
        set_vpmanage=True,
        vpm_password="preset",
        set_domain=False,
        domain=None,
    )
    mock_run.return_value = "result:success; message:ok\n"
    run_vpconfigure_phases_05_to_08(
        session,
        "/cfg",
        "debian",
        cfg,
        lambda _m: None,
        60,
        access_state=AccessFileState(),
        artifact_persist=lambda _x: None,
    )
    extra = [c[0][5] for c in mock_run.call_args_list if c[0][3] == "08_setvpmanage.sh"][0]
    assert "--vpm-password" in extra


@patch("vpconnect_install.vpconfigure_provision._run_configure_script")
def test_phases_08_parses_password(mock_run: MagicMock) -> None:
    session = MagicMock()
    cfg = _cfg(
        auto_setup=False,
        set_wireguard=False,
        set_mtproxy=False,
        set_vpmanage=True,
        vpm_password="",
        set_domain=False,
        domain=None,
    )
    mock_run.return_value = "result:success; message:ok; password:Secret99\n"
    run_vpconfigure_phases_05_to_08(
        session,
        "/cfg",
        "debian",
        cfg,
        lambda _m: None,
        60,
        access_state=AccessFileState(),
        artifact_persist=lambda _x: None,
    )
    assert cfg.vpm_password == "Secret99"


@patch("vpconnect_install.vpconfigure_provision._run_configure_script")
def test_phases_none_enabled_persist_message(mock_run: MagicMock) -> None:
    session = MagicMock()
    cfg = _cfg(auto_setup=False, set_wireguard=False, set_mtproxy=False, set_vpmanage=False)
    cfg.set_domain = False
    cfg.domain = None
    cfg.use_public_ip = False
    persisted: list[str] = []
    run_vpconfigure_phases_05_to_08(
        session,
        "/cfg",
        "debian",
        cfg,
        lambda _m: None,
        60,
        access_state=AccessFileState(),
        artifact_persist=persisted.append,
    )
    mock_run.assert_not_called()
    assert any("не запускались" in p for p in persisted)


@patch("vpconnect_install.vpconfigure_provision._run_configure_script")
def test_phases_07_download_failure_logged(mock_run: MagicMock) -> None:
    session = MagicMock()
    session.download_bytes.side_effect = OSError("read fail")
    cfg = _cfg(auto_setup=False, set_wireguard=False, set_mtproxy=True, set_domain=False, domain=None)
    mock_run.return_value = "result:success; message:ok\n"
    logs: list[str] = []
    run_vpconfigure_phases_05_to_08(
        session,
        "/cfg",
        "debian",
        cfg,
        logs.append,
        60,
        access_state=AccessFileState(),
        artifact_persist=lambda _x: None,
    )
    assert any("Не прочитан MTProxy secret" in m for m in logs)


@patch("vpconnect_install.vpconfigure_provision._run_configure_script")
def test_phases_06_download_failure_logged(mock_run: MagicMock) -> None:
    session = MagicMock()
    session.download_bytes.side_effect = OSError("nope")
    cfg = _cfg(auto_setup=False, set_wireguard=True, set_domain=False, domain=None)
    cfg.set_mtproxy = False
    cfg.set_vpmanage = False
    mock_run.return_value = "result:success; message:ok\n"
    logs: list[str] = []
    run_vpconfigure_phases_05_to_08(
        session,
        "/cfg",
        "debian",
        cfg,
        logs.append,
        60,
        access_state=AccessFileState(),
        artifact_persist=lambda _x: None,
    )
    assert any("Не прочитан публичный ключ WG" in m for m in logs)
