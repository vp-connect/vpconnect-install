"""
Графический интерфейс (Tkinter) для :func:`vpconnect_install.runner.run`.

Два режима: упрощённый (``auto_setup``) и расширенный с отдельными блоками (SSH, домен, WG, MTProxy, VPManage).
Лог выводится в фоне; по успеху открывается каталог артефактов в файловом менеджере ОС.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from vpconnect_install import defaults as d
from vpconnect_install import gui_captions_ru as gc
from vpconnect_install import gui_hints_ru as gh
from vpconnect_install.config import ProvisionConfig
from vpconnect_install.gui_clipboard import (
    install_text_clipboard_and_context_menu,
    install_ttk_entry_clipboard_and_context_menu,
)
from vpconnect_install.gui_extended_hint import bind_extended_hint
from vpconnect_install.outputs import open_directory_in_file_manager
from vpconnect_install.runner import run

# Высота лога в строках в расширенном режиме; в упрощённом лог растягивается по вертикали.
_LOG_LINES_COMPACT = 6
# Минимум строк лога в упрощённом режиме при растягивании окна
_LOG_LINES_MIN_STRETCH = 4
# Стартовая ширина колонки с логом (px), плюс ширина левой панели и отступы
_LOG_COLUMN_STARTUP_PX = 200


def _parse_int(entry: ttk.Entry, default: int) -> int:
    """Целое из поля; пустая строка — ``default``."""
    t = entry.get().strip()
    return int(t) if t else default


def _parse_required_ssh_port(entry: ttk.Entry) -> int:
    """Обязательный SSH-порт: непустое поле, диапазон 1–65535."""
    t = entry.get().strip()
    if not t:
        raise ValueError("Укажите SSH port")
    try:
        p = int(t)
    except ValueError as e:
        raise ValueError("SSH port должен быть числом") from e
    if not (1 <= p <= 65535):
        raise ValueError(f"Некорректный SSH port: {p}")
    return p


def _wire_mask_secret_on_blur(entry: ttk.Entry) -> None:
    """Пока фокус в поле — видимые символы; без фокуса — звёздочки."""

    def on_focus_in(_event: tk.Event | None = None) -> None:
        entry.configure(show="")

    def on_focus_out(_event: tk.Event | None = None) -> None:
        entry.configure(show="*")

    entry.bind("<FocusIn>", on_focus_in, add=True)
    entry.bind("<FocusOut>", on_focus_out, add=True)
    entry.configure(show="*")


def _parse_optional_port(entry: ttk.Entry) -> int | None:
    t = entry.get().strip()
    return int(t) if t else None


def _build_config(
    *,
    auto_setup: bool,
    host: str,
    port: int,
    root_pw: str,
    root_key: str,
    root_key_pp: str,
    set_new_connect: bool,
    new_root: str,
    new_ssh: int | None,
    extra_pub: str,
    enable_firewall: bool,
    set_domain: bool,
    domain: str,
    vpconfigure_repo_url: str,
    set_wg: bool,
    wg_port: int,
    wg_cert: str,
    wg_conf: str,
    wg_server_private_key: str,
    set_mt: bool,
    mt_port: int,
    mtproxy_secret: str,
    set_vpm: bool,
    vpm_http: int,
    vpm_pw: str,
) -> ProvisionConfig:
    """Собрать конфигурацию из значений виджетов (учёт ``auto_setup`` и чекбоксов расширенного режима)."""
    dom = domain.strip() or None
    if not set_domain:
        dom = None

    cfg = ProvisionConfig(
        host=host.strip(),
        port=port,
        root_password=root_pw,
        root_private_key=root_key.strip(),
        root_private_key_passphrase=root_key_pp,
        auto_setup=auto_setup,
        set_new_connect=set_new_connect,
        new_root_password=new_root if set_new_connect else "",
        new_ssh_port=new_ssh if set_new_connect else None,
        new_ssh_public_key=extra_pub.strip() if set_new_connect else "",
        enable_firewall=bool(enable_firewall) if set_new_connect else False,
        set_domain=set_domain,
        domain=dom,
        vpconfigure_repo_url=vpconfigure_repo_url.strip() or d.VPCONFIGURE_REPO_URL_DEFAULT,
        set_wireguard=set_wg if not auto_setup else True,
        wg_port=wg_port,
        wg_client_cert_path=wg_cert.strip() or d.WG_CLIENT_CERT_PATH_DEFAULT,
        wg_client_config_path=wg_conf.strip() or d.WG_CLIENT_CONFIG_PATH_DEFAULT,
        wg_server_private_key=wg_server_private_key.strip(),
        set_mtproxy=set_mt if not auto_setup else True,
        mtproxy_port=mt_port,
        mtproxy_secret=mtproxy_secret.strip(),
        set_vpmanage=set_vpm if not auto_setup else True,
        vpm_http_port=vpm_http,
        vpm_password=vpm_pw if set_vpm or auto_setup else "",
    )
    return cfg


class ProvisionerGUI:
    """
    Главное окно: форма слева, лог справа, кнопки Start/Exit.

    Запуск установки не блокирует UI (поток + очередь сообщений в лог).
    """

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("vpconnect-install 1.0.2")

        self._log_q: queue.Queue[str] = queue.Queue()
        self._running = False

        self.auto_setup_var = tk.BooleanVar(value=True)

        frm = ttk.Frame(self.root, padding=8)
        self.frm = frm
        frm.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        # col0: форма фиксированной ширины по содержимому; col1: только лог тянется при ресайзе окна
        frm.columnconfigure(0, weight=0)
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(0, weight=1)

        left_panel = ttk.Frame(frm)
        self._left_panel = left_panel
        left_panel.grid(row=0, column=0, sticky="nw", padx=(0, 8))
        left_panel.columnconfigure(1, weight=1)

        r = 0
        banner_lbl = ttk.Label(
            left_panel,
            text=gc.CAP_BANNER,
        )
        banner_lbl.grid(row=r, column=0, columnspan=2, sticky="w")
        bind_extended_hint(self.root, [banner_lbl], gh.BANNER)
        r += 1
        mode_fr = ttk.Frame(left_panel)
        mode_fr.grid(row=r, column=0, columnspan=2, sticky="w", pady=4)
        mode_lbl = ttk.Label(mode_fr, text=gc.CAP_MODE_LABEL)
        mode_lbl.pack(side="left", padx=(0, 8))
        rb_simple = ttk.Radiobutton(
            mode_fr,
            text=gc.CAP_MODE_SIMPLE,
            variable=self.auto_setup_var,
            value=True,
            command=self._on_mode_change,
        )
        rb_simple.pack(side="left", padx=4)
        rb_adv = ttk.Radiobutton(
            mode_fr,
            text=gc.CAP_MODE_ADVANCED,
            variable=self.auto_setup_var,
            value=False,
            command=self._on_mode_change,
        )
        rb_adv.pack(side="left", padx=4)
        bind_extended_hint(self.root, [mode_lbl, rb_simple, rb_adv], gh.MODE)
        r += 1

        conn = ttk.LabelFrame(left_panel, text=gc.CAP_SECTION_CONNECTION, padding=6)
        conn.grid(row=r, column=0, columnspan=2, sticky="ew", pady=4)
        conn.columnconfigure(1, weight=1)
        r += 1
        cr = 0
        host_lbl = ttk.Label(conn, text=gc.CAP_HOST)
        host_lbl.grid(row=cr, column=0, sticky="e")
        self.host = ttk.Entry(conn, width=42)
        self.host.grid(row=cr, column=1, sticky="ew", padx=4)
        bind_extended_hint(self.root, [host_lbl, self.host], gh.HOST)
        cr += 1
        port_lbl = ttk.Label(conn, text=gc.CAP_SSH_PORT)
        port_lbl.grid(row=cr, column=0, sticky="e")
        self.port = ttk.Entry(conn, width=8)
        self.port.insert(0, "22")
        self.port.grid(row=cr, column=1, sticky="w", padx=4)
        bind_extended_hint(self.root, [port_lbl, self.port], gh.SSH_PORT)
        cr += 1
        root_pw_lbl = ttk.Label(conn, text=gc.CAP_ROOT_PASSWORD)
        root_pw_lbl.grid(row=cr, column=0, sticky="e")
        self.root_pw = ttk.Entry(conn, width=42)
        self.root_pw.grid(row=cr, column=1, sticky="ew", padx=4)
        _wire_mask_secret_on_blur(self.root_pw)
        bind_extended_hint(self.root, [root_pw_lbl, self.root_pw], gh.ROOT_PASSWORD)
        cr += 1
        key_lbl = ttk.Label(conn, text=gc.CAP_SSH_PRIVATE_KEY)
        key_lbl.grid(row=cr, column=0, sticky="e")
        key_row = ttk.Frame(conn)
        key_row.grid(row=cr, column=1, sticky="ew", padx=4)
        key_row.columnconfigure(0, weight=1)
        self.root_key = ttk.Entry(key_row, width=36)
        self.root_key.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        key_browse_btn = ttk.Button(key_row, text=gc.CAP_BROWSE_FILE, command=self._browse_private_key, width=8)
        key_browse_btn.grid(row=0, column=1, sticky="e")
        bind_extended_hint(self.root, [key_lbl, self.root_key, key_browse_btn], gh.SSH_PRIVATE_KEY)
        cr += 1
        key_pp_lbl = ttk.Label(conn, text=gc.CAP_SSH_KEY_PASSPHRASE)
        key_pp_lbl.grid(row=cr, column=0, sticky="e")
        self.root_key_pp = ttk.Entry(conn, width=42)
        self.root_key_pp.grid(row=cr, column=1, sticky="ew", padx=4)
        _wire_mask_secret_on_blur(self.root_key_pp)
        bind_extended_hint(self.root, [key_pp_lbl, self.root_key_pp], gh.SSH_KEY_PASSPHRASE)
        cr += 1
        repo_lbl = ttk.Label(conn, text=gc.CAP_VPCONFIGURE_REPO)
        repo_lbl.grid(row=cr, column=0, sticky="ne")
        self.vpconfigure_repo_ent = ttk.Entry(conn, width=42)
        self.vpconfigure_repo_ent.insert(0, d.VPCONFIGURE_REPO_URL_DEFAULT)
        self.vpconfigure_repo_ent.grid(row=cr, column=1, sticky="ew", padx=4)
        bind_extended_hint(self.root, [repo_lbl, self.vpconfigure_repo_ent], gh.VPCONFIGURE_REPO)

        self.advanced_frame = ttk.Frame(left_panel)
        self.advanced_frame.grid(row=r, column=0, columnspan=2, sticky="ew", pady=4)
        r += 1
        af = self.advanced_frame
        af.columnconfigure(1, weight=1)

        ar = 0
        self.set_nc_var = tk.BooleanVar(value=False)
        self.enable_fw_var = tk.BooleanVar(value=True)
        nc = ttk.LabelFrame(af, text=gc.CAP_SECTION_NEW_CONNECT, padding=6)
        nc.grid(row=ar, column=0, columnspan=2, sticky="ew", pady=4)
        nc.columnconfigure(1, weight=1)
        nc_on = ttk.Checkbutton(nc, text=gc.CAP_ENABLE, variable=self.set_nc_var, command=self._toggle_nc)
        nc_on.grid(row=0, column=0, columnspan=2, sticky="w")
        bind_extended_hint(self.root, [nc_on], gh.NEW_CONNECT_ENABLE)
        nr_lbl = ttk.Label(nc, text=gc.CAP_NEW_ROOT_PASSWORD)
        nr_lbl.grid(row=1, column=0, sticky="e")
        self.new_root = ttk.Entry(nc, width=40, show="*")
        self.new_root.grid(row=1, column=1, sticky="ew", padx=4)
        bind_extended_hint(self.root, [nr_lbl, self.new_root], gh.NEW_ROOT_PASSWORD)
        ns_lbl = ttk.Label(nc, text=gc.CAP_NEW_SSH_PORT)
        ns_lbl.grid(row=2, column=0, sticky="e")
        self.new_ssh = ttk.Entry(nc, width=8)
        self.new_ssh.grid(row=2, column=1, sticky="w", padx=4)
        bind_extended_hint(self.root, [ns_lbl, self.new_ssh], gh.NEW_SSH_PORT)
        epk_lbl = ttk.Label(nc, text=gc.CAP_NEW_SSH_PUBLIC_KEY)
        epk_lbl.grid(row=3, column=0, sticky="e")
        self.extra_pub = ttk.Entry(nc, width=40)
        self.extra_pub.grid(row=3, column=1, sticky="ew", padx=4)
        bind_extended_hint(self.root, [epk_lbl, self.extra_pub], gh.NEW_SSH_PUBLIC_KEY)
        fw_lbl = ttk.Label(nc, text=gc.CAP_ENABLE_FIREWALL)
        fw_lbl.grid(row=4, column=0, sticky="e")
        self.enable_fw_cb = ttk.Checkbutton(nc, text=gc.CAP_ENABLE_FIREWALL_CHECKBOX, variable=self.enable_fw_var)
        self.enable_fw_cb.grid(row=4, column=1, sticky="w", padx=4, pady=(2, 0))
        bind_extended_hint(self.root, [fw_lbl, self.enable_fw_cb], gh.ENABLE_FIREWALL)
        self._nc_widgets = [self.new_root, self.new_ssh, self.extra_pub]
        ar += 1

        self.set_dom_var = tk.BooleanVar(value=False)
        domf = ttk.LabelFrame(af, text=gc.CAP_SECTION_DOMAIN, padding=6)
        domf.grid(row=ar, column=0, columnspan=2, sticky="ew", pady=4)
        domf.columnconfigure(1, weight=1)
        dom_on = ttk.Checkbutton(domf, text=gc.CAP_SET_DOMAIN, variable=self.set_dom_var, command=self._toggle_dom)
        dom_on.grid(row=0, column=0, columnspan=2, sticky="w")
        bind_extended_hint(self.root, [dom_on], gh.DOMAIN_ENABLE)
        dom_lbl = ttk.Label(domf, text=gc.CAP_DOMAIN_FQDN)
        dom_lbl.grid(row=1, column=0, sticky="e")
        self.domain_ent = ttk.Entry(domf, width=40)
        self.domain_ent.grid(row=1, column=1, sticky="ew", padx=4)
        bind_extended_hint(self.root, [dom_lbl, self.domain_ent], gh.DOMAIN_FQDN)
        self._dom_widgets = [self.domain_ent]
        ar += 1

        self.set_wg_var = tk.BooleanVar(value=True)
        wgf = ttk.LabelFrame(af, text=gc.CAP_SECTION_WIREGUARD, padding=6)
        wgf.grid(row=ar, column=0, columnspan=2, sticky="ew", pady=4)
        wgf.columnconfigure(1, weight=1)
        wg_on = ttk.Checkbutton(wgf, text=gc.CAP_INSTALL, variable=self.set_wg_var, command=self._toggle_wg)
        wg_on.grid(row=0, column=0, sticky="w")
        bind_extended_hint(self.root, [wg_on], gh.WIREGUARD_ENABLE)
        wgp_lbl = ttk.Label(wgf, text=gc.CAP_WG_UDP_PORT)
        wgp_lbl.grid(row=1, column=0, sticky="e")
        self.wg_port = ttk.Entry(wgf, width=8)
        self.wg_port.insert(0, str(d.WG_PORT_DEFAULT))
        self.wg_port.grid(row=1, column=1, sticky="w", padx=4)
        bind_extended_hint(self.root, [wgp_lbl, self.wg_port], gh.WIREGUARD_UDP_PORT)
        wgc_lbl = ttk.Label(wgf, text=gc.CAP_WG_CLIENT_CERT)
        wgc_lbl.grid(row=2, column=0, sticky="e")
        self.wg_cert = ttk.Entry(wgf, width=40)
        self.wg_cert.insert(0, d.WG_CLIENT_CERT_PATH_DEFAULT)
        self.wg_cert.grid(row=2, column=1, sticky="ew", padx=4)
        bind_extended_hint(self.root, [wgc_lbl, self.wg_cert], gh.WIREGUARD_CLIENT_CERT_PATH)
        wgf_lbl = ttk.Label(wgf, text=gc.CAP_WG_CLIENT_CONFIG)
        wgf_lbl.grid(row=3, column=0, sticky="e")
        self.wg_conf = ttk.Entry(wgf, width=40)
        self.wg_conf.insert(0, d.WG_CLIENT_CONFIG_PATH_DEFAULT)
        self.wg_conf.grid(row=3, column=1, sticky="ew", padx=4)
        bind_extended_hint(self.root, [wgf_lbl, self.wg_conf], gh.WIREGUARD_CLIENT_CONFIG_PATH)
        wgs_lbl = ttk.Label(wgf, text=gc.CAP_WG_SERVER_PRIVATE_KEY)
        wgs_lbl.grid(row=4, column=0, sticky="ne")
        self.wg_server_priv = ttk.Entry(wgf, width=40)
        self.wg_server_priv.grid(row=4, column=1, sticky="ew", padx=4)
        bind_extended_hint(self.root, [wgs_lbl, self.wg_server_priv], gh.WIREGUARD_SERVER_PRIVATE_KEY_REUSE)
        self._wg_widgets = [self.wg_port, self.wg_cert, self.wg_conf, self.wg_server_priv]
        ar += 1

        self.set_mt_var = tk.BooleanVar(value=True)
        mtf = ttk.LabelFrame(af, text=gc.CAP_SECTION_MTPROXY, padding=6)
        mtf.grid(row=ar, column=0, columnspan=2, sticky="ew", pady=4)
        mtf.columnconfigure(1, weight=1)
        mt_on = ttk.Checkbutton(mtf, text=gc.CAP_INSTALL, variable=self.set_mt_var, command=self._toggle_mt)
        mt_on.grid(row=0, column=0, sticky="w")
        bind_extended_hint(self.root, [mt_on], gh.MTPROXY_ENABLE)
        mtp_lbl = ttk.Label(mtf, text=gc.CAP_MTPROXY_TCP_PORT)
        mtp_lbl.grid(row=1, column=0, sticky="e")
        self.mt_port = ttk.Entry(mtf, width=8)
        self.mt_port.insert(0, str(d.MTPROXY_PORT_DEFAULT))
        self.mt_port.grid(row=1, column=1, sticky="w", padx=4)
        bind_extended_hint(self.root, [mtp_lbl, self.mt_port], gh.MTPROXY_TCP_PORT)
        mts_lbl = ttk.Label(mtf, text=gc.CAP_MTPROXY_SECRET)
        mts_lbl.grid(row=2, column=0, sticky="e")
        self.mtproxy_secret_ent = ttk.Entry(mtf, width=40)
        self.mtproxy_secret_ent.grid(row=2, column=1, sticky="ew", padx=4)
        bind_extended_hint(self.root, [mts_lbl, self.mtproxy_secret_ent], gh.MTPROXY_SECRET_REUSE)
        self._mt_widgets = [self.mt_port, self.mtproxy_secret_ent]
        ar += 1

        self.set_vpm_var = tk.BooleanVar(value=True)
        vpmf = ttk.LabelFrame(af, text=gc.CAP_SECTION_VPMANAGE, padding=6)
        vpmf.grid(row=ar, column=0, columnspan=2, sticky="ew", pady=4)
        vpm_on = ttk.Checkbutton(vpmf, text=gc.CAP_INSTALL, variable=self.set_vpm_var, command=self._toggle_vpm)
        vpm_on.grid(row=0, column=0, sticky="w")
        bind_extended_hint(self.root, [vpm_on], gh.VPMANAGE_ENABLE)
        vpmh_lbl = ttk.Label(vpmf, text=gc.CAP_VPM_HTTP_PORT)
        vpmh_lbl.grid(row=1, column=0, sticky="e")
        self.vpm_http = ttk.Entry(vpmf, width=8)
        self.vpm_http.insert(0, str(d.VPM_HTTP_PORT_DEFAULT))
        self.vpm_http.grid(row=1, column=1, sticky="w", padx=4)
        bind_extended_hint(self.root, [vpmh_lbl, self.vpm_http], gh.VPMANAGE_HTTP_PORT)
        vpmp_lbl = ttk.Label(vpmf, text=gc.CAP_VPM_PASSWORD)
        vpmp_lbl.grid(row=2, column=0, sticky="e")
        self.vpm_pw = ttk.Entry(vpmf, width=40, show="*")
        self.vpm_pw.grid(row=2, column=1, sticky="ew", padx=4)
        bind_extended_hint(self.root, [vpmp_lbl, self.vpm_pw], gh.VPMANAGE_PASSWORD)
        self._vpm_widgets = [self.vpm_http, self.vpm_pw]

        bf = ttk.Frame(left_panel)
        bf.grid(row=r, column=0, columnspan=2, pady=8)
        self.btn_start = ttk.Button(bf, text=gc.CAP_START, command=self._on_start)
        self.btn_start.pack(side="left", padx=4)
        ttk.Button(bf, text=gc.CAP_EXIT, command=self.root.destroy).pack(side="left", padx=4)

        self.log_outer = ttk.Frame(frm)
        self.log_outer.grid(row=0, column=1, sticky="nsew")
        self.log_outer.columnconfigure(0, weight=1)
        self.log_outer.rowconfigure(1, weight=1)
        log_lbl = ttk.Label(self.log_outer, text=gc.CAP_LOG)
        log_lbl.grid(row=0, column=0, sticky="nw")
        self.log_widget = scrolledtext.ScrolledText(
            self.log_outer, height=_LOG_LINES_MIN_STRETCH, state="disabled", wrap="word"
        )
        self.log_widget.grid(row=1, column=0, sticky="nsew", pady=(0, 4))
        bind_extended_hint(self.root, [log_lbl, self.log_widget], gh.LOG_PANEL)

        self.root.after(200, self._drain_log)
        install_ttk_entry_clipboard_and_context_menu(self.root)
        install_text_clipboard_and_context_menu(self.root)
        self._on_mode_change()
        self._capture_and_apply_startup_geometry()

    def _capture_and_apply_startup_geometry(self) -> None:
        """Узкая колонка лога при первом показе; размер авто-режима для возврата с «Расширенный»."""
        self.root.update_idletasks()
        left_w = self._left_panel.winfo_reqwidth()
        # padding frm (~16) + зазор между колонками (8)
        extra = 24
        min_w, min_h = self.root.minsize()
        init_w = max(left_w + _LOG_COLUMN_STARTUP_PX + extra, min_w)
        init_h = max(self.root.winfo_reqheight(), min_h)
        self._initial_auto_size = (init_w, init_h)
        self.root.geometry(f"{init_w}x{init_h}")

    def _browse_private_key(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="SSH private key",
            filetypes=[
                ("PEM / OpenSSH", "*.pem"),
                ("Все файлы", "*.*"),
            ],
        )
        if path:
            self.root_key.delete(0, "end")
            self.root_key.insert(0, path)

    def _state_widgets(self, widgets: list[ttk.Entry | ttk.Entry], st: str) -> None:
        for w in widgets:
            w.state([st] if st else ["!disabled"])

    def _toggle_nc(self) -> None:
        st = "disabled" if not self.set_nc_var.get() else "!disabled"
        self._state_widgets(self._nc_widgets, st)
        if not self.set_nc_var.get():
            self.enable_fw_cb.state(["disabled"])
        else:
            self.enable_fw_cb.state(["!disabled"])

    def _toggle_dom(self) -> None:
        on = self.set_dom_var.get()
        st = "!disabled" if on else "disabled"
        self._state_widgets(self._dom_widgets, st)

    def _toggle_wg(self) -> None:
        st = "disabled" if not self.set_wg_var.get() else "!disabled"
        self._state_widgets(self._wg_widgets, st)

    def _toggle_mt(self) -> None:
        st = "disabled" if not self.set_mt_var.get() else "!disabled"
        self._state_widgets(self._mt_widgets, st)

    def _toggle_vpm(self) -> None:
        st = "disabled" if not self.set_vpm_var.get() else "!disabled"
        self._state_widgets(self._vpm_widgets, st)

    def _apply_log_layout_mode(self) -> None:
        """Вертикальное растяжение окна — только колонка с логом (правая).

        В упрощённом и расширенном режиме отличается только минимальная высота лога в строках.
        """
        self.log_outer.rowconfigure(1, weight=1)
        self.log_widget.grid_configure(sticky="nsew", pady=(0, 4))
        if self.auto_setup_var.get():
            self.log_widget.configure(height=_LOG_LINES_MIN_STRETCH)
        else:
            self.log_widget.configure(height=_LOG_LINES_COMPACT)

    def _on_mode_change(self) -> None:
        auto = self.auto_setup_var.get()
        if auto:
            self.advanced_frame.grid_remove()
            self.root.minsize(620, 420)
            self.root.update_idletasks()
            if hasattr(self, "_initial_auto_size"):
                init_w, init_h = self._initial_auto_size
                cur_w = self.root.winfo_width()
                if cur_w <= 1:
                    cur_w = init_w
                self.root.geometry(f"{cur_w}x{init_h}")
        else:
            self.advanced_frame.grid()
            self._toggle_nc()
            self._toggle_dom()
            self._toggle_wg()
            self._toggle_mt()
            self._toggle_vpm()
            self.root.minsize(620, 640)
        self._apply_log_layout_mode()
        if not auto:
            self.root.after_idle(self._shrink_wrap_height)

    def _shrink_wrap_height(self) -> None:
        """При смене режима подогнать только высоту окна; ширину не меняем."""
        self.root.update_idletasks()
        req_h = self.root.winfo_reqheight()
        cur_w = self.root.winfo_width()
        if cur_w <= 1:
            cur_w = max(self.root.winfo_reqwidth(), 620)
        self.root.geometry(f"{cur_w}x{req_h}")

    def _append_log(self, line: str) -> None:
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", line + "\n")
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")

    def _clear_log(self) -> None:
        try:
            while True:
                self._log_q.get_nowait()
        except queue.Empty:
            pass
        self.log_widget.configure(state="normal")
        self.log_widget.delete("1.0", tk.END)
        self.log_widget.configure(state="disabled")

    def _drain_log(self) -> None:
        try:
            while True:
                msg = self._log_q.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass
        self.root.after(200, self._drain_log)

    def _on_start(self) -> None:
        if self._running:
            messagebox.showinfo("Busy", "Already running.")
            return
        auto = self.auto_setup_var.get()
        try:
            cfg = _build_config(
                auto_setup=auto,
                host=self.host.get(),
                port=_parse_required_ssh_port(self.port),
                root_pw=self.root_pw.get(),
                root_key=self.root_key.get(),
                root_key_pp=self.root_key_pp.get(),
                set_new_connect=self.set_nc_var.get() if not auto else True,
                new_root=self.new_root.get(),
                new_ssh=_parse_optional_port(self.new_ssh) if not auto else None,
                extra_pub=self.extra_pub.get(),
                enable_firewall=self.enable_fw_var.get() if not auto else True,
                set_domain=self.set_dom_var.get() if not auto else False,
                domain=self.domain_ent.get(),
                vpconfigure_repo_url=self.vpconfigure_repo_ent.get(),
                set_wg=self.set_wg_var.get(),
                wg_port=_parse_int(self.wg_port, d.WG_PORT_DEFAULT),
                wg_cert=self.wg_cert.get(),
                wg_conf=self.wg_conf.get(),
                wg_server_private_key=self.wg_server_priv.get(),
                set_mt=self.set_mt_var.get(),
                mt_port=_parse_int(self.mt_port, d.MTPROXY_PORT_DEFAULT),
                mtproxy_secret=self.mtproxy_secret_ent.get(),
                set_vpm=self.set_vpm_var.get(),
                vpm_http=_parse_int(self.vpm_http, d.VPM_HTTP_PORT_DEFAULT),
                vpm_pw=self.vpm_pw.get(),
            )
            cfg.apply_auto_setup()
            cfg.validate()
        except Exception as e:
            messagebox.showerror("Validation", str(e))
            return

        self._clear_log()
        self._running = True
        self.btn_start.state(["disabled"])

        def work() -> None:
            try:
                artifact_root = run(cfg, log=self._log_q.put)
                self.root.after(0, lambda r=artifact_root: self._done_ok(r))
            except Exception as ex:
                err_msg = str(ex)
                self.root.after(0, lambda m=err_msg: self._done_err(m))

        threading.Thread(target=work, daemon=True).start()

    def _done_ok(self, artifact_root: Path) -> None:
        self._running = False
        self.btn_start.state(["!disabled"])
        sep = "=" * 62
        for _ in range(3):
            self._log_q.put("")
        self._log_q.put(sep)
        self._log_q.put("Установка завершена.")
        self._log_q.put("")
        self._log_q.put("Новые доступы, ключи и пароли сохранены в каталоге:")
        self._log_q.put(f"  {artifact_root.resolve()}")
        self._log_q.put("")
        self._log_q.put(sep)
        open_directory_in_file_manager(artifact_root)

    def _done_err(self, msg: str) -> None:
        self._running = False
        self.btn_start.state(["!disabled"])
        messagebox.showerror("Error", msg)

    def run_ui(self) -> None:
        """Запустить главный цикл Tk (блокирует до закрытия окна)."""
        self.root.mainloop()


def main() -> None:
    """Точка входа GUI: создать :class:`ProvisionerGUI` и показать окно."""
    ProvisionerGUI().run_ui()


if __name__ == "__main__":  # pragma: no cover
    main()
