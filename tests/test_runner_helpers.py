"""Юнит-тесты вспомогательных функций runner (без реального SSH)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vpconnect_install import runner
from vpconnect_install.config import ProvisionConfig


def _cfg(**kw: object) -> ProvisionConfig:
    base = dict(
        host="10.0.0.1",
        port=22,
        root_password="old",
        new_root_password="",
        new_ssh_port=None,
        root_private_key="",
        root_private_key_passphrase="",
        auto_setup=False,
        use_public_ip=False,
        set_domain=False,
        domain=None,
        ssh_connect_timeout=1,
        reboot_wait_timeout=2,
        ssh_poll_interval=1,
    )
    base.update(kw)
    return ProvisionConfig(**base)  # type: ignore[arg-type]


def test_log_default_noop() -> None:
    runner._log_default("anything")


def test_close_session_quietly_swallows_close_error() -> None:
    s = MagicMock()
    s.close.side_effect = RuntimeError("boom")
    runner._close_session_quietly(s)  # no exception


def test_post_connect_params() -> None:
    port, pw, key = runner._post_connect_params(
        _cfg(new_ssh_port=2222, new_root_password="n", root_password="old", root_private_key="")
    )
    assert port == 2222
    assert pw == "n"
    assert key == ""

    port2, pw2, key2 = runner._post_connect_params(_cfg(new_ssh_port=None, new_root_password="", root_private_key=""))
    assert port2 == 22
    assert pw2 == "old"


def test_want_public_ip() -> None:
    assert runner._want_public_ip(_cfg(domain="x.com")) is False
    assert runner._want_public_ip(_cfg(domain=None, auto_setup=True)) is True
    assert runner._want_public_ip(_cfg(domain=None, use_public_ip=True)) is True
    assert runner._want_public_ip(_cfg(domain=None, set_domain=True)) is True
    assert runner._want_public_ip(_cfg(domain=None, auto_setup=False, use_public_ip=False)) is False


def test_resolve_public_target_good_ip() -> None:
    session = MagicMock()
    session.exec_command.return_value = (0, "203.0.113.5\n", "")
    log: list[str] = []
    ip = runner._resolve_public_target(session, _cfg(host="10.0.0.1"), log.append)
    assert ip == "203.0.113.5"
    assert any("Публичный IPv4" in m for m in log)


def test_resolve_public_target_fallback_on_bad_stdout() -> None:
    session = MagicMock()
    session.exec_command.return_value = (0, "not an ip", "")
    log: list[str] = []
    cfg = _cfg(host="myhost")
    assert runner._resolve_public_target(session, cfg, log.append) == "myhost"


def test_apply_effective_host_uses_domain() -> None:
    session = MagicMock()
    log: list[str] = []
    cfg = _cfg(domain="d.example", auto_setup=False)
    runner._apply_effective_host(session, cfg, log.append)
    assert cfg.effective_domain_or_ip == "d.example"


def test_apply_effective_host_uses_host_when_no_public_wanted() -> None:
    session = MagicMock()
    log: list[str] = []
    cfg = _cfg(domain=None, auto_setup=False, use_public_ip=False)
    runner._apply_effective_host(session, cfg, log.append)
    assert cfg.effective_domain_or_ip == cfg.host


def test_apply_effective_host_resolves_public() -> None:
    session = MagicMock()
    session.exec_command.return_value = (0, "1.1.1.1", "")
    log: list[str] = []
    cfg = _cfg(domain=None, auto_setup=True)
    runner._apply_effective_host(session, cfg, log.append)
    assert cfg.effective_domain_or_ip == "1.1.1.1"


def test_maybe_reconnect_returns_same_session_when_not_needed() -> None:
    sess = MagicMock()
    out = runner._maybe_reconnect_session(sess, _cfg(port=22, new_ssh_port=None, new_root_password=""), lambda _m: None)
    assert out is sess


def test_request_reboot_logs_warning_on_failure() -> None:
    session = MagicMock()
    session.exec_command.return_value = (1, "", "nope")
    logs: list[str] = []
    runner._request_reboot(session, logs.append)
    assert any("Предупреждение" in m for m in logs)


def test_request_reboot_success_log() -> None:
    session = MagicMock()
    session.exec_command.return_value = (0, "", "")
    logs: list[str] = []
    runner._request_reboot(session, logs.append)
    assert any("Перезагрузка запрошена" in m for m in logs)


def test_poll_ssh_after_finalize_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """Короткие таймауты + сессия никогда не подключается — выходим по дедлайну."""
    cfg = _cfg(reboot_wait_timeout=1, ssh_poll_interval=1)

    class FakeSession:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def test_connect(self) -> bool:
            return False

        def connect(self) -> None:
            raise RuntimeError("still down")

    monkeypatch.setattr(runner, "SSHSession", FakeSession)
    logs: list[str] = []
    s = runner._poll_ssh_after_finalize(cfg, 2222, "pw", "", logs.append)
    assert any("Таймаут" in m for m in logs)
    assert isinstance(s, FakeSession)


def test_write_credential_artifacts_quiet(tmp_path: Path) -> None:
    from vpconnect_install.outputs import ArtifactBundle

    bundle = ArtifactBundle(root=tmp_path)
    cfg = _cfg()
    cfg.new_root_password = "nr"
    cfg.set_vpmanage = True
    cfg.vpm_password = "vp"
    runner._write_credential_artifacts(bundle, cfg, lambda _m: None, quiet=True)
    assert (tmp_path / "credentials_new_root_password.txt").is_file()
    assert (tmp_path / "credentials_vpm_password.txt").is_file()


def test_poll_ssh_after_finalize_connects_successfully(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(reboot_wait_timeout=30, ssh_poll_interval=1)
    call = {"n": 0}

    class FakeSession:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def test_connect(self) -> bool:
            call["n"] += 1
            return call["n"] >= 2

        def connect(self) -> None:
            pass

    monkeypatch.setattr(runner, "SSHSession", FakeSession)
    logs: list[str] = []
    s = runner._poll_ssh_after_finalize(cfg, 22, "pw", "", logs.append, prefer_auth="password")
    assert isinstance(s, FakeSession)
    assert any("Снова доступен" in m for m in logs)


def test_poll_ssh_after_reboot_swallows_inner_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "_poll_ssh_after_finalize", MagicMock(side_effect=RuntimeError("x")))
    logs: list[str] = []
    runner._poll_ssh_after_reboot(_cfg(), logs.append, prior_auth="")
    assert any("Предупреждение" in m for m in logs)
