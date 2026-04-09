"""Тесты валидации и apply_auto_setup для ProvisionConfig."""

from __future__ import annotations

import pytest

from vpconnect_install import defaults as d
from vpconnect_install.config import ProvisionConfig


def _valid_extended(**kw: object) -> ProvisionConfig:
    defaults: dict = dict(
        host="10.0.0.1",
        port=22,
        root_password="secret",
        auto_setup=False,
        set_wireguard=False,
        set_mtproxy=False,
        set_vpmanage=False,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    defaults.update(kw)
    return ProvisionConfig(**defaults)  # type: ignore[arg-type]


def test_validate_empty_host() -> None:
    cfg = _valid_extended(host="  ")
    with pytest.raises(ValueError, match="host is required"):
        cfg.validate()


def test_validate_bad_ssh_port() -> None:
    cfg = _valid_extended(port=0)
    with pytest.raises(ValueError, match="SSH port"):
        cfg.validate()


def test_validate_bad_new_ssh_port() -> None:
    cfg = _valid_extended(new_ssh_port=70000)
    with pytest.raises(ValueError, match="new_ssh_port"):
        cfg.validate()


def test_validate_bad_service_ports() -> None:
    for field in ("wg_port", "mtproxy_port", "vpm_http_port"):
        cfg = _valid_extended(**{field: 0})
        with pytest.raises(ValueError, match=field):
            cfg.validate()


def test_validate_no_credentials() -> None:
    cfg = _valid_extended(root_password="", root_private_key="")
    with pytest.raises(ValueError, match="root_password"):
        cfg.validate()


def test_validate_empty_repo_url() -> None:
    cfg = _valid_extended(vpconfigure_repo_url="  ")
    with pytest.raises(ValueError, match="vpconfigure_repo_url is required"):
        cfg.validate()


def test_validate_invalid_repo_url() -> None:
    cfg = _valid_extended(vpconfigure_repo_url="https://example.com/not-github")
    with pytest.raises(ValueError, match="vpconfigure_repo_url"):
        cfg.validate()


def test_validate_domain_empty_string_when_manual() -> None:
    cfg = _valid_extended(auto_setup=False, domain="")
    with pytest.raises(ValueError, match="domain must be non-empty"):
        cfg.validate()


def test_validate_domain_none_ok_in_manual_mode() -> None:
    cfg = _valid_extended(auto_setup=False, domain=None)
    cfg.validate()


def test_apply_auto_setup_skipped_when_false() -> None:
    cfg = _valid_extended(auto_setup=False, domain="keep.me", new_ssh_port=3333, new_ssh_public_key="ssh-rsa X")
    cfg.apply_auto_setup()
    assert cfg.domain == "keep.me"
    assert cfg.new_ssh_port == 3333
    assert cfg.new_ssh_public_key == "ssh-rsa X"


def test_apply_auto_setup_clears_domain_and_sets_defaults() -> None:
    cfg = ProvisionConfig(
        host="h",
        root_password="p",
        auto_setup=True,
        domain="old.example",
        new_ssh_port=None,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    cfg.apply_auto_setup()
    assert cfg.domain is None
    assert cfg.new_ssh_port == 2222
    assert cfg.new_ssh_public_key == ""
    assert cfg.new_root_password


def test_apply_auto_setup_preserves_explicit_new_root_password() -> None:
    cfg = ProvisionConfig(
        host="h",
        root_password="p",
        auto_setup=True,
        new_root_password="fixed-pass",
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    cfg.apply_auto_setup()
    assert cfg.new_root_password == "fixed-pass"
