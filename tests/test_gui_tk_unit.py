"""Парсеры и сборка конфига GUI; дымовой тест ProvisionerGUI (Tk)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

tkinter = pytest.importorskip("tkinter")

from vpconnect_install import defaults as d
from vpconnect_install.gui_tk import (
    ProvisionerGUI,
    _build_config,
    _parse_int,
    _parse_optional_port,
    _parse_required_ssh_port,
    _wire_mask_secret_on_blur,
)


def _tk_skip_if_broken() -> None:
    try:
        r = tkinter.Tk()
        r.withdraw()
        r.destroy()
    except tkinter.TclError as e:
        pytest.skip(f"Tk/Tcl unavailable: {e}")


def test_parse_int_empty_uses_default() -> None:
    e = MagicMock()
    e.get.side_effect = ["", "8080"]
    assert _parse_int(e, 99) == 99
    assert _parse_int(e, 99) == 8080


def test_parse_required_ssh_port_errors() -> None:
    e = MagicMock()
    e.get.side_effect = ["", "abc", "99999"]
    with pytest.raises(ValueError, match="Укажите SSH port"):
        _parse_required_ssh_port(e)
    with pytest.raises(ValueError, match="числом"):
        _parse_required_ssh_port(e)
    with pytest.raises(ValueError, match="Некорректный"):
        _parse_required_ssh_port(e)


def test_parse_optional_port() -> None:
    e = MagicMock()
    e.get.side_effect = ["", "2222"]
    assert _parse_optional_port(e) is None
    assert _parse_optional_port(e) == 2222


def test_build_config_auto_vs_extended() -> None:
    cfg_a = _build_config(
        auto_setup=True,
        host="  h  ",
        port=22,
        root_pw="p",
        root_key="",
        root_key_pp="",
        set_new_connect=True,
        new_root="",
        new_ssh=None,
        extra_pub="",
        enable_firewall=True,
        set_domain=False,
        domain="",
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
        set_wg=False,
        wg_port=1,
        wg_cert="",
        wg_conf="",
        set_mt=False,
        mt_port=1,
        set_vpm=False,
        vpm_http=1,
        vpm_pw="",
    )
    assert cfg_a.set_wireguard is True
    cfg_m = _build_config(
        auto_setup=False,
        host="h",
        port=22,
        root_pw="p",
        root_key="",
        root_key_pp="",
        set_new_connect=False,
        new_root="",
        new_ssh=None,
        extra_pub="",
        enable_firewall=False,
        set_domain=False,
        domain="",
        vpconfigure_repo_url="",
        set_wg=True,
        wg_port=443,
        wg_cert="",
        wg_conf="",
        set_mt=False,
        mt_port=25,
        set_vpm=False,
        vpm_http=80,
        vpm_pw="",
    )
    assert cfg_m.set_wireguard is True
    assert cfg_m.set_mtproxy is False


def test_wire_mask_secret_on_blur_registers_handlers() -> None:
    entry = MagicMock()
    _wire_mask_secret_on_blur(entry)
    assert entry.bind.call_count == 2
    entry.configure.assert_called_with(show="*")


class _InstantThread:
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None) -> None:
        self._target = target
        self._args = args or ()
        self._kwargs = kwargs if kwargs is not None else {}

    def start(self) -> None:
        assert self._target is not None
        self._target(*self._args, **self._kwargs)


def test_provisioner_gui_flows_single_window() -> None:
    """Один Tk на тест — избегаем проблем второго корня в одном процессе."""
    _tk_skip_if_broken()
    with (
        patch("vpconnect_install.gui_tk.open_directory_in_file_manager") as mock_open,
        patch("vpconnect_install.gui_tk.threading.Thread", _InstantThread),
        patch("vpconnect_install.gui_tk.run") as mock_run,
        patch("vpconnect_install.gui_tk.messagebox.showerror") as mock_err,
        patch("vpconnect_install.gui_tk.messagebox.showinfo") as mock_info,
        patch("vpconnect_install.gui_tk.filedialog.askopenfilename", return_value="/k.pem"),
    ):
        g = ProvisionerGUI()
        g.root.withdraw()

        def immediate_after(ms, fn=None, *extra):
            if callable(fn):
                fn()
            return "id"

        g.root.after = immediate_after  # type: ignore[method-assign]

        mock_run.return_value = Path("/tmp/artifacts-test")
        g.host.insert(0, "127.0.0.1")
        g.root_pw.insert(0, "secret")
        g._on_start()
        mock_run.assert_called_once()
        mock_open.assert_called_once()

        g._running = False
        mock_run.reset_mock()
        mock_open.reset_mock()
        g._running = True
        g._on_start()
        mock_info.assert_called()

        g._running = False
        g.host.delete(0, "end")
        g._on_start()
        mock_err.assert_called()

        g._running = True
        g._done_err("e")
        assert not g._running

        g.auto_setup_var.set(False)
        g._on_mode_change()
        g.auto_setup_var.set(True)
        g._on_mode_change()
        g._append_log("x")
        g._clear_log()

        g._browse_private_key()
        assert g.root_key.get() == "/k.pem"

        with patch.object(g.root, "mainloop"):
            g.run_ui()

        mock_run.side_effect = RuntimeError("install failed")
        g._running = False
        g.host.delete(0, "end")
        g.host.insert(0, "127.0.0.1")
        g.root_pw.delete(0, "end")
        g.root_pw.insert(0, "secret")
        g._on_start()
        assert mock_err.call_count >= 2

        g.root.destroy()


def test_gui_tk_main_calls_run_ui() -> None:
    with patch("vpconnect_install.gui_tk.ProvisionerGUI") as pc:
        inst = MagicMock()
        pc.return_value = inst
        import vpconnect_install.gui_tk as gt

        gt.main()
        inst.run_ui.assert_called_once()
