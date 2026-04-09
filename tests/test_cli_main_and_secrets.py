"""CLI: секреты из файлов/env и код возврата main()."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from vpconnect_install.cli import build_arg_parser, config_from_args, main


def test_config_from_args_reads_root_password_file(tmp_path: Path) -> None:
    f = tmp_path / "pw.txt"
    f.write_text("  from-file  \n", encoding="utf-8")
    p = build_arg_parser()
    ns = p.parse_args(["--host", "h", "--root-password-file", str(f)])
    cfg = config_from_args(ns)
    assert cfg.root_password == "from-file"


def test_config_from_args_new_ssh_public_key_file(tmp_path: Path) -> None:
    f = tmp_path / "k.pub"
    f.write_text("ssh-ed25519 AAAcomment\n", encoding="utf-8")
    p = build_arg_parser()
    ns = p.parse_args(
        [
            "--host",
            "h",
            "--root-password",
            "x",
            "--no-auto-setup",
            "--no-set-wireguard",
            "--no-set-mtproxy",
            "--no-set-vpmanage",
            "--new-ssh-public-key-file",
            str(f),
        ]
    )
    cfg = config_from_args(ns)
    assert "ssh-ed25519" in cfg.new_ssh_public_key


def test_config_from_args_enable_firewall_explicit_off_with_auto_setup() -> None:
    p = build_arg_parser()
    ns = p.parse_args(["--host", "h", "--root-password", "x", "--no-enable-firewall"])
    cfg = config_from_args(ns)
    assert cfg.enable_firewall is False


def test_config_from_args_feature_flags_no_auto_explicit_wireguard_only() -> None:
    p = build_arg_parser()
    ns = p.parse_args(
        [
            "--host",
            "h",
            "--root-password",
            "x",
            "--no-auto-setup",
            "--set-wireguard",
            "--no-set-mtproxy",
            "--no-set-vpmanage",
        ]
    )
    cfg = config_from_args(ns)
    assert cfg.set_wireguard is True
    assert cfg.set_mtproxy is False
    assert cfg.set_vpmanage is False


def test_main_returns_0_on_success() -> None:
    argv = [
        "--host",
        "127.0.0.1",
        "--root-password",
        "x",
        "--no-auto-setup",
        "--no-set-wireguard",
        "--no-set-mtproxy",
        "--no-set-vpmanage",
    ]
    with patch("vpconnect_install.cli.run") as run_mock:
        code = main(argv)
    assert code == 0
    run_mock.assert_called_once()


def test_main_returns_1_on_run_error(tmp_path: Path) -> None:
    argv = [
        "--host",
        "127.0.0.1",
        "--root-password",
        "x",
        "--no-auto-setup",
        "--no-set-wireguard",
        "--no-set-mtproxy",
        "--no-set-vpmanage",
        "--artifacts-dir",
        str(tmp_path / "art"),
    ]
    (tmp_path / "art").mkdir()

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("planned")

    with patch("vpconnect_install.cli.run", side_effect=boom):
        code = main(argv)
    assert code == 1


def test_config_artifacts_dir_passed_via_main_mock(tmp_path: Path) -> None:
    """main передаёт artifacts_base только когда задан --artifacts-dir."""
    base = tmp_path / "custom"
    base.mkdir()
    argv = [
        "--host",
        "127.0.0.1",
        "--root-password",
        "x",
        "--no-auto-setup",
        "--no-set-wireguard",
        "--no-set-mtproxy",
        "--no-set-vpmanage",
        "--artifacts-dir",
        str(base),
    ]
    with patch("vpconnect_install.cli.run") as run_mock:
        main(argv)
    assert run_mock.call_args.kwargs.get("artifacts_base") == base.resolve()
