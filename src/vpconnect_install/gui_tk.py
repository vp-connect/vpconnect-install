"""
Графический интерфейс (Tkinter) для удалённой настройки сервера через vpconnect-install.

Целевая ОС на сервере — одно из семейств vpconnect-configure (debian / centos / freebsd);
см. README проекта. Собирает поля в :class:`ProvisionConfig`, запускает
:func:`vpconnect_install.runner.run` в фоновом потоке; по успеху открывает каталог артефактов.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from vpconnect_install import defaults as d
from vpconnect_install.config import ProvisionConfig
from vpconnect_install.gui_clipboard import (
    install_text_clipboard_and_context_menu,
    install_ttk_entry_clipboard_and_context_menu,
)
from vpconnect_install.outputs import open_directory_in_file_manager
from vpconnect_install.runner import run

# Высота лога в строках в расширенном режиме; в упрощённом лог растягивается по вертикали.
_LOG_LINES_COMPACT = 6
# Минимум строк лога в упрощённом режиме при растягивании окна
_LOG_LINES_MIN_STRETCH = 4


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
    domain_client_key: str,
    vpconfigure_repo_url: str,
    set_wg: bool,
    wg_port: int,
    wg_cert: str,
    wg_conf: str,
    set_mt: bool,
    mt_port: int,
    set_vpm: bool,
    vpm_http: int,
    vpm_pw: str,
) -> ProvisionConfig:
    """Собрать :class:`ProvisionConfig` из значений полей формы (режимы упрощённый/расширенный)."""
    dom = domain.strip() or None
    dkey = domain_client_key.strip()
    if not set_domain:
        dom = None
        dkey = ""

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
        domain_client_key=dkey,
        vpconfigure_repo_url=vpconfigure_repo_url.strip() or d.VPCONFIGURE_REPO_URL_DEFAULT,
        set_wireguard=set_wg if not auto_setup else True,
        wg_port=wg_port,
        wg_client_cert_path=wg_cert.strip() or d.WG_CLIENT_CERT_PATH_DEFAULT,
        wg_client_config_path=wg_conf.strip() or d.WG_CLIENT_CONFIG_PATH_DEFAULT,
        set_mtproxy=set_mt if not auto_setup else True,
        mtproxy_port=mt_port,
        set_vpmanage=set_vpm if not auto_setup else True,
        vpm_http_port=vpm_http,
        vpm_password=vpm_pw if set_vpm or auto_setup else "",
    )
    if auto_setup:
        cfg.set_wireguard = True
        cfg.set_mtproxy = True
        cfg.set_vpmanage = True
        cfg.set_new_connect = True
    return cfg


class ProvisionerGUI:
    """Окно Tk: ввод параметров, фоновый :func:`~vpconnect_install.runner.run`, лог, открытие каталога артефактов."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("vpconnect-install")

        self._log_q: queue.Queue[str] = queue.Queue()
        self._running = False

        self.auto_setup_var = tk.BooleanVar(value=True)
        # Общая переменная для "Ключ сервиса домена" (дублированный ввод в упрощённом и расширенном режимах).
        self.domain_key_var = tk.StringVar(value="")

        frm = ttk.Frame(self.root, padding=8)
        self.frm = frm
        frm.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        frm.columnconfigure(1, weight=1)

        r = 0
        ttk.Label(
            frm,
            text="SSH: сервер — debian / centos / freebsd (vpconnect-configure; подробности в README)",
        ).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        mode_fr = ttk.Frame(frm)
        mode_fr.grid(row=r, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Label(mode_fr, text="Режим:").pack(side="left", padx=(0, 8))
        ttk.Radiobutton(
            mode_fr,
            text="Упрощённый (auto_setup)",
            variable=self.auto_setup_var,
            value=True,
            command=self._on_mode_change,
        ).pack(side="left", padx=4)
        ttk.Radiobutton(
            mode_fr,
            text="Расширенный",
            variable=self.auto_setup_var,
            value=False,
            command=self._on_mode_change,
        ).pack(side="left", padx=4)
        r += 1

        conn = ttk.LabelFrame(frm, text="Подключение", padding=6)
        conn.grid(row=r, column=0, columnspan=2, sticky="ew", pady=4)
        conn.columnconfigure(1, weight=1)
        r += 1
        cr = 0
        ttk.Label(conn, text="Host").grid(row=cr, column=0, sticky="e")
        self.host = ttk.Entry(conn, width=42)
        self.host.grid(row=cr, column=1, sticky="ew", padx=4)
        cr += 1
        ttk.Label(conn, text="SSH port").grid(row=cr, column=0, sticky="e")
        self.port = ttk.Entry(conn, width=8)
        self.port.insert(0, "22")
        self.port.grid(row=cr, column=1, sticky="w", padx=4)
        cr += 1
        ttk.Label(conn, text="Root password").grid(row=cr, column=0, sticky="e")
        self.root_pw = ttk.Entry(conn, width=42)
        self.root_pw.grid(row=cr, column=1, sticky="ew", padx=4)
        _wire_mask_secret_on_blur(self.root_pw)
        cr += 1
        ttk.Label(conn, text="SSH Private key").grid(row=cr, column=0, sticky="e")
        key_row = ttk.Frame(conn)
        key_row.grid(row=cr, column=1, sticky="ew", padx=4)
        key_row.columnconfigure(0, weight=1)
        self.root_key = ttk.Entry(key_row, width=36)
        self.root_key.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(key_row, text="Файл…", command=self._browse_private_key, width=8).grid(row=0, column=1, sticky="e")
        cr += 1
        ttk.Label(conn, text="SSH Key passphrase").grid(row=cr, column=0, sticky="e")
        self.root_key_pp = ttk.Entry(conn, width=42)
        self.root_key_pp.grid(row=cr, column=1, sticky="ew", padx=4)
        _wire_mask_secret_on_blur(self.root_key_pp)
        cr += 1
        ttk.Label(conn, text="Репозиторий vpconnect-configure").grid(row=cr, column=0, sticky="ne")
        self.vpconfigure_repo_ent = ttk.Entry(conn, width=42)
        self.vpconfigure_repo_ent.insert(0, d.VPCONFIGURE_REPO_URL_DEFAULT)
        self.vpconfigure_repo_ent.grid(row=cr, column=1, sticky="ew", padx=4)
        cr += 1
        ttk.Label(conn, text="Ключ сервиса домена").grid(row=cr, column=0, sticky="e")
        self.domain_key_top_ent = ttk.Entry(conn, width=42, textvariable=self.domain_key_var)
        self.domain_key_top_ent.grid(row=cr, column=1, sticky="ew", padx=4)

        self.advanced_frame = ttk.Frame(frm)
        self.advanced_frame.grid(row=r, column=0, columnspan=2, sticky="ew", pady=4)
        r += 1
        af = self.advanced_frame
        af.columnconfigure(1, weight=1)

        ar = 0
        self.set_nc_var = tk.BooleanVar(value=False)
        self.enable_fw_var = tk.BooleanVar(value=True)
        nc = ttk.LabelFrame(af, text="Настройка подключения (на сервере)", padding=6)
        nc.grid(row=ar, column=0, columnspan=2, sticky="ew", pady=4)
        nc.columnconfigure(1, weight=1)
        ttk.Checkbutton(nc, text="Включить", variable=self.set_nc_var, command=self._toggle_nc).grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(nc, text="Новый пароль root").grid(row=1, column=0, sticky="e")
        self.new_root = ttk.Entry(nc, width=40, show="*")
        self.new_root.grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Label(nc, text="Новый SSH port (пусто = не менять)").grid(row=2, column=0, sticky="e")
        self.new_ssh = ttk.Entry(nc, width=8)
        self.new_ssh.grid(row=2, column=1, sticky="w", padx=4)
        ttk.Label(nc, text="Новый SSH Public key").grid(row=3, column=0, sticky="e")
        self.extra_pub = ttk.Entry(nc, width=40)
        self.extra_pub.grid(row=3, column=1, sticky="ew", padx=4)
        ttk.Label(nc, text="Включить файервол (ufw)").grid(row=4, column=0, sticky="e")
        self.enable_fw_cb = ttk.Checkbutton(nc, text="", variable=self.enable_fw_var)
        self.enable_fw_cb.grid(row=4, column=1, sticky="w", padx=4, pady=(2, 0))
        self._nc_widgets = [self.new_root, self.new_ssh, self.extra_pub]
        ar += 1

        self.set_dom_var = tk.BooleanVar(value=False)
        domf = ttk.LabelFrame(af, text="Домен", padding=6)
        domf.grid(row=ar, column=0, columnspan=2, sticky="ew", pady=4)
        domf.columnconfigure(1, weight=1)
        ttk.Checkbutton(domf, text="Настроить домен", variable=self.set_dom_var, command=self._toggle_dom).grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(domf, text="Домен (FQDN)").grid(row=1, column=0, sticky="e")
        self.domain_ent = ttk.Entry(domf, width=40)
        self.domain_ent.grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Label(domf, text="Ключ сервиса домена").grid(row=2, column=0, sticky="e")
        self.domain_key_ent = ttk.Entry(domf, width=40, textvariable=self.domain_key_var)
        self.domain_key_ent.grid(row=2, column=1, sticky="ew", padx=4)
        self._dom_widgets = [self.domain_ent, self.domain_key_ent]
        ar += 1

        self.set_wg_var = tk.BooleanVar(value=True)
        wgf = ttk.LabelFrame(af, text="WireGuard", padding=6)
        wgf.grid(row=ar, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Checkbutton(wgf, text="Установить", variable=self.set_wg_var, command=self._toggle_wg).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(wgf, text="Порт UDP").grid(row=1, column=0, sticky="e")
        self.wg_port = ttk.Entry(wgf, width=8)
        self.wg_port.insert(0, str(d.WG_PORT_DEFAULT))
        self.wg_port.grid(row=1, column=1, sticky="w", padx=4)
        ttk.Label(wgf, text="client_cert (сервер)").grid(row=2, column=0, sticky="e")
        self.wg_cert = ttk.Entry(wgf, width=40)
        self.wg_cert.insert(0, d.WG_CLIENT_CERT_PATH_DEFAULT)
        self.wg_cert.grid(row=2, column=1, sticky="ew", padx=4)
        ttk.Label(wgf, text="client_config (сервер)").grid(row=3, column=0, sticky="e")
        self.wg_conf = ttk.Entry(wgf, width=40)
        self.wg_conf.insert(0, d.WG_CLIENT_CONFIG_PATH_DEFAULT)
        self.wg_conf.grid(row=3, column=1, sticky="ew", padx=4)
        self._wg_widgets = [self.wg_port, self.wg_cert, self.wg_conf]
        ar += 1

        self.set_mt_var = tk.BooleanVar(value=True)
        mtf = ttk.LabelFrame(af, text="MTProxy", padding=6)
        mtf.grid(row=ar, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Checkbutton(mtf, text="Установить", variable=self.set_mt_var, command=self._toggle_mt).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(mtf, text="UDP порт").grid(row=1, column=0, sticky="e")
        self.mt_port = ttk.Entry(mtf, width=8)
        self.mt_port.insert(0, str(d.MTPROXY_PORT_DEFAULT))
        self.mt_port.grid(row=1, column=1, sticky="w", padx=4)
        self._mt_widgets = [self.mt_port]
        ar += 1

        self.set_vpm_var = tk.BooleanVar(value=True)
        vpmf = ttk.LabelFrame(af, text="VPManage", padding=6)
        vpmf.grid(row=ar, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Checkbutton(vpmf, text="Установить", variable=self.set_vpm_var, command=self._toggle_vpm).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(vpmf, text="HTTP порт").grid(row=1, column=0, sticky="e")
        self.vpm_http = ttk.Entry(vpmf, width=8)
        self.vpm_http.insert(0, str(d.VPM_HTTP_PORT_DEFAULT))
        self.vpm_http.grid(row=1, column=1, sticky="w", padx=4)
        ttk.Label(vpmf, text="Пароль (пусто = сгенерировать)").grid(row=2, column=0, sticky="e")
        self.vpm_pw = ttk.Entry(vpmf, width=40, show="*")
        self.vpm_pw.grid(row=2, column=1, sticky="ew", padx=4)
        self._vpm_widgets = [self.vpm_http, self.vpm_pw]

        bf = ttk.Frame(frm)
        bf.grid(row=r, column=0, columnspan=2, pady=8)
        r += 1
        self.btn_start = ttk.Button(bf, text="Start", command=self._on_start)
        self.btn_start.pack(side="left", padx=4)
        ttk.Button(bf, text="Exit", command=self.root.destroy).pack(side="left", padx=4)

        self._log_frm_row = r
        ttk.Label(frm, text="Log").grid(row=r, column=0, sticky="nw")
        self.log_widget = scrolledtext.ScrolledText(frm, height=_LOG_LINES_MIN_STRETCH, state="disabled", wrap="word")
        self.log_widget.grid(row=r, column=1, sticky="nsew", padx=4, pady=4)

        self.root.after(200, self._drain_log)
        install_ttk_entry_clipboard_and_context_menu(self.root)
        install_text_clipboard_and_context_menu(self.root)
        self._on_mode_change()

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
        """Лишняя высота окна — в области лога (форма сверху не «плавает»).

        В упрощённом и расширенном режиме отличается только минимальная высота лога в строках.
        """
        log_row = self._log_frm_row
        self.frm.rowconfigure(log_row, weight=1)
        self.log_widget.grid_configure(sticky="nsew", padx=4, pady=4)
        if self.auto_setup_var.get():
            self.log_widget.configure(height=_LOG_LINES_MIN_STRETCH)
        else:
            self.log_widget.configure(height=_LOG_LINES_COMPACT)

    def _on_mode_change(self) -> None:
        auto = self.auto_setup_var.get()
        if auto:
            self.advanced_frame.grid_remove()
            self.root.minsize(620, 420)
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
        """Убирает лишнюю пустоту под логом: высота окна по содержимому."""
        self.root.update_idletasks()
        req_h = self.root.winfo_reqheight()
        cur_w = max(self.root.winfo_width(), self.root.winfo_reqwidth())
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
                domain_client_key=self.domain_key_var.get(),
                vpconfigure_repo_url=self.vpconfigure_repo_ent.get(),
                set_wg=self.set_wg_var.get(),
                wg_port=_parse_int(self.wg_port, d.WG_PORT_DEFAULT),
                wg_cert=self.wg_cert.get(),
                wg_conf=self.wg_conf.get(),
                set_mt=self.set_mt_var.get(),
                mt_port=_parse_int(self.mt_port, d.MTPROXY_PORT_DEFAULT),
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


if __name__ == "__main__":
    main()
