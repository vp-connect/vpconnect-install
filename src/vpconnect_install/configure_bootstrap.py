"""Скачивание скриптов 00–03 с GitHub (raw), загрузка в $HOME и поочерёдный запуск; 04–08 — из каталога после 03."""

from __future__ import annotations

import shlex
from collections.abc import Callable

import requests

from vpconnect_install import defaults as d
from vpconnect_install.config import ProvisionConfig
from vpconnect_install.remote_scripts_fetch import github_raw_file_url
from vpconnect_install.ssh_session import SSHSession

LogFn = Callable[[str], None]

INSTALL_ABORTED_MSG = "Установка прекращена, обратитесь к администратору"

# Только загрузка и запуск из $HOME; репозиторий с 04–08 клонирует 03_getconfigure.sh.
CONFIGURE_SCRIPT_NAMES = (
    "00_bashinstall.sh",
    "01_getosversion.sh",
    "02_gitinstall.sh",
    "03_getconfigure.sh",
)


def parse_configure_result_line(stdout: str) -> tuple[str, str, str | None, str]:
    """Строка result:… в stdout (apt/dnf и т.д. могут писать в stdout до неё — берём последнюю строку result:)."""
    text = (stdout or "").lstrip("\ufeff").strip()
    if not text:
        return "unknown", "", None, ""
    stripped_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    line1 = ""
    for ln in reversed(stripped_lines):
        if ln.lower().startswith("result:"):
            line1 = ln
            break
    if not line1:
        line1 = stripped_lines[0] if stripped_lines else ""
    if not line1.lower().startswith("result:"):
        return "unknown", line1, None, line1
    status = ""
    message = ""
    branch: str | None = None
    for seg in line1.split(";"):
        seg = seg.strip()
        if not seg:
            continue
        low = seg.lower()
        if low.startswith("result:"):
            status = seg.split(":", 1)[1].strip()
        elif low.startswith("message:"):
            message = seg.split(":", 1)[1].strip()
        elif low.startswith("branch:"):
            branch = seg.split(":", 1)[1].strip()
    return status, message, branch, line1


def parse_configure_install_path(stdout: str) -> str | None:
    """Поле path:… в строке result: (stdout 03_getconfigure.sh после успешного клона)."""
    _st, _msg, _br, line1 = parse_configure_result_line(stdout)
    if not line1:
        return None
    for seg in line1.split(";"):
        seg = seg.strip()
        if seg.lower().startswith("path:"):
            val = seg.split(":", 1)[1].strip()
            return val or None
    return None


def resolve_configure_install_dir(
    session: SSHSession,
    home: str,
    log: LogFn,
    stdout_from_03: str,
    timeout: int,
) -> str:
    """
    Каталог с 04–08: path: из вывода 03, иначе VPCONFIGURE_INSTALL_DIR на сервере (относительные пути — от $HOME),
    иначе $HOME/vpconnect-configure (аналог умолчания ./vpconnect-configure при запуске 03 из $HOME).
    """
    p = parse_configure_install_path(stdout_from_03)
    if p:
        log(f"[vpconnect-configure] Каталог установки (path из вывода 03): {p}")
        return p
    inner = (
        'cd "$HOME" && '
        'if [[ -n "${VPCONFIGURE_INSTALL_DIR-}" ]]; then '
        'd="$VPCONFIGURE_INSTALL_DIR"; '
        'if [[ "$d" != /* ]]; then d="$HOME/${d#./}"; fi; '
        'printf "%s" "$d"; '
        "else "
        'printf "%s" "$HOME/vpconnect-configure"; '
        "fi"
    )
    code, out, _err = session.exec_command(f"bash -lc {shlex.quote(inner)}", timeout=min(timeout, 60))
    resolved = (out or "").strip()
    if code == 0 and resolved:
        log(f"[vpconnect-configure] Каталог установки (окружение или умолчание): {resolved}")
        return resolved
    fallback = f"{home}/vpconnect-configure"
    log(f"[vpconnect-configure] Не удалось определить каталог, использую {fallback}")
    return fallback


def verify_configure_scripts_dir(session: SSHSession, configure_dir: str, log: LogFn, timeout: int) -> None:
    """Проверка, что каталог есть и в нём лежит 04_setsystemaccess.sh."""
    inner = f"test -d {shlex.quote(configure_dir)} && test -f {shlex.quote(configure_dir + '/04_setsystemaccess.sh')}"
    code, _o, e = session.exec_command(f"bash -lc {shlex.quote(inner)}", timeout=timeout)
    if code != 0:
        log(f"Ошибка! Каталог скриптов не найден или нет 04_setsystemaccess.sh: {configure_dir}")
        log(f"[vpconnect-configure] {e.strip() or 'test не выполнен'}")
        log(INSTALL_ABORTED_MSG)
        raise RuntimeError(INSTALL_ABORTED_MSG)


def _fetch_configure_script(repo_url: str, branch: str, name: str, timeout: int) -> bytes:
    url = github_raw_file_url(repo_url, branch, name)
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content


def _remote_home(session: SSHSession, log: LogFn, timeout: int) -> str:
    code, out, err = session.exec_command("bash -lc 'printf %s \"$HOME\"'", timeout=timeout)
    if code != 0:
        log(f"[vpconnect-configure] Не удалось получить $HOME: {err.strip() or out}")
        raise RuntimeError(INSTALL_ABORTED_MSG)
    h = (out or "").strip()
    if not h:
        raise RuntimeError(INSTALL_ABORTED_MSG)
    return h


def _stdout_lines_before_marked_line(full: str, marker_line: str) -> str:
    """Строки stdout до последнего вхождения marker_line (для лога при ошибке, если result: не в начале)."""
    text = (full or "").strip()
    marker = (marker_line or "").strip()
    if not text or not marker:
        return ""
    lines = text.splitlines()
    last_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == marker:
            last_idx = i
            break
    if last_idx <= 0:
        return ""
    return "\n".join(lines[:last_idx]).strip()


def _configure_step_failed(status: str, exit_code: int) -> bool:
    if status == "error":
        return True
    if status == "unknown":
        return True
    if exit_code != 0:
        return True
    return False


def abort_configure_on_failure(
    log: LogFn,
    script_name: str,
    message: str,
    out: str,
    err: str,
    line1: str,
) -> None:
    log(f"Ошибка! {message or 'см. строку результата и stderr выше'}")
    tail_out = (out or "").strip()
    if tail_out and tail_out != line1:
        if line1.lower().startswith("result:"):
            prefix_out = _stdout_lines_before_marked_line(tail_out, line1)
            if prefix_out:
                log(f"[vpconnect-configure] доп. вывод stdout:\n{prefix_out}")
        else:
            rest = tail_out.split("\n", 1)[1] if "\n" in tail_out else ""
            if rest.strip():
                log(f"[vpconnect-configure] доп. вывод stdout:\n{rest.strip()}")
    if err.strip():
        log(f"[vpconnect-configure] доп. вывод stderr (повтор):\n{err.rstrip()}")
    log(INSTALL_ABORTED_MSG)
    raise RuntimeError(INSTALL_ABORTED_MSG)


def exec_vpconfigure_script(
    session: SSHSession,
    work_dir: str,
    script_name: str,
    export_branch: str | None,
    extra_cli: str,
    timeout: int,
    *,
    extra_env_lines: tuple[str, ...] = (),
) -> tuple[int, str, str]:
    """work_dir — каталог, где лежит script_name (cd туда перед запуском)."""
    script_path = f"{work_dir}/{script_name}"
    inner_parts = [f"cd {shlex.quote(work_dir)}", "set -e"]
    for el in extra_env_lines:
        inner_parts.append(el)
    if export_branch:
        inner_parts.append(
            f"export VPCONFIGURE_GIT_BRANCH={shlex.quote(export_branch)}",
        )
    inner_parts.append(f"bash {shlex.quote(script_path)}{extra_cli}")
    inner = " && ".join(inner_parts)
    return session.exec_command(f"bash -lc {shlex.quote(inner)}", timeout=timeout)


def run_vpconnect_configure_bootstrap(
    session: SSHSession,
    config: ProvisionConfig,
    log: LogFn,
) -> tuple[str, str, str]:
    """Скачать 00–03 в $HOME, выполнить 00–03. Возвращает (home, os_branch, configure_dir). При error — стоп."""
    repo = config.vpconfigure_repo_url.strip()
    branch = d.VPCONFIGURE_RAW_GIT_BRANCH
    timeout = min(config.command_timeout, 3600)
    fetch_to = min(120, timeout)

    log("[vpconnect-configure] Загрузка скриптов с GitHub (raw)…")
    home = _remote_home(session, log, min(30, timeout))
    log(f"[vpconnect-configure] Каталог на сервере: {home}")

    for name in CONFIGURE_SCRIPT_NAMES:
        try:
            body = _fetch_configure_script(repo, branch, name, fetch_to)
        except requests.RequestException as e:
            log(f"Ошибка! Не удалось скачать {name}: {e}")
            log(INSTALL_ABORTED_MSG)
            raise RuntimeError(INSTALL_ABORTED_MSG) from e

        remote_path = f"{home}/{name}"
        session.upload_bytes(remote_path, body)
        try:
            c_ch, o_ch, e_ch = session.exec_command(f"chmod +x {shlex.quote(remote_path)}", timeout=30)
            if c_ch != 0:
                log(f"Ошибка! chmod {name}: {e_ch.strip() or o_ch}")
                log(INSTALL_ABORTED_MSG)
                raise RuntimeError(INSTALL_ABORTED_MSG)
        except RuntimeError:
            raise
        except Exception as ex:
            log(f"Ошибка! chmod {name}: {ex}")
            log(INSTALL_ABORTED_MSG)
            raise RuntimeError(INSTALL_ABORTED_MSG) from ex

    os_branch: str | None = None
    stdout_03 = ""

    for idx, name in enumerate(CONFIGURE_SCRIPT_NAMES):
        if idx > 0:
            log("")
        extra_cli = ""
        export_b: str | None = None
        if idx >= 2:
            if not os_branch:
                log("Ошибка! Не определена VPCONFIGURE_GIT_BRANCH после 01_getosversion.sh")
                log(INSTALL_ABORTED_MSG)
                raise RuntimeError(INSTALL_ABORTED_MSG)
            export_b = os_branch
        if name == "03_getconfigure.sh":
            dest = f"{home}/vpconnect-configure"
            extra_cli = f" --repo {shlex.quote(repo)} -d {shlex.quote(dest)}"

        code, out, err = exec_vpconfigure_script(session, home, name, export_b, extra_cli, timeout)

        status, message, br, line1 = parse_configure_result_line(out)
        log(f"[vpconnect-configure] {name}: {line1 or '(пустой stdout)'}")

        if err.strip():
            log(f"[vpconnect-configure] {name} stderr:\n{err.rstrip()}")

        if name == "01_getosversion.sh" and br:
            os_branch = br

        if name == "03_getconfigure.sh":
            stdout_03 = out or ""

        if status == "warning":
            log(f"[vpconnect-configure] {name}: предупреждение — {message}")

        if _configure_step_failed(status, code):
            abort_configure_on_failure(log, name, message, out, err, line1)

    log("[vpconnect-configure] Шаги 00–03 завершены успешно.")
    assert os_branch is not None
    configure_dir = resolve_configure_install_dir(session, home, log, stdout_03, min(60, timeout))
    verify_configure_scripts_dir(session, configure_dir, log, min(30, timeout))
    return home, os_branch, configure_dir
