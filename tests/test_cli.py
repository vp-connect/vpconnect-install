from __future__ import annotations

from vpconnect_install.cli import build_arg_parser, config_from_args


def test_config_auto_setup_defaults() -> None:
    p = build_arg_parser()
    ns = p.parse_args(
        [
            "--host",
            "10.0.0.1",
            "--root-password",
            "secret",
        ]
    )
    cfg = config_from_args(ns)
    assert cfg.auto_setup is True
    assert cfg.set_wireguard is True
    assert cfg.set_mtproxy is True
    assert cfg.set_vpmanage is True


def test_config_no_auto_flags_off() -> None:
    p = build_arg_parser()
    ns = p.parse_args(
        [
            "--host",
            "10.0.0.1",
            "--root-password",
            "x",
            "--no-auto-setup",
            "--no-set-wireguard",
            "--no-set-mtproxy",
            "--no-set-vpmanage",
        ]
    )
    cfg = config_from_args(ns)
    assert cfg.auto_setup is False
    assert cfg.set_wireguard is False
    assert cfg.set_mtproxy is False
    assert cfg.set_vpmanage is False


def test_new_ssh_port_optional() -> None:
    p = build_arg_parser()
    ns = p.parse_args(
        [
            "--host",
            "10.0.0.1",
            "--root-password",
            "x",
            "--no-auto-setup",
            "--no-set-wireguard",
            "--no-set-mtproxy",
            "--no-set-vpmanage",
        ]
    )
    cfg = config_from_args(ns)
    assert cfg.new_ssh_port is None


def test_apply_auto_vpm_password_optional_until_08() -> None:
    p = build_arg_parser()
    ns = p.parse_args(["--host", "10.0.0.1", "--root-password", "x"])
    cfg = config_from_args(ns)
    cfg.apply_auto_setup()
    cfg.validate()
    assert cfg.new_root_password
    assert cfg.vpm_password == ""
