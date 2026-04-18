"""
Предпроверка на сервере: выбранные для прогона порты не должны уже прослушиваться (до 01–03).

Выполняется после успешного ``00_bashinstall.sh`` (на Linux гарантирован ``ss`` из iproute2/iproute).
На FreeBSD допускается ``sockstat`` из базовой системы, если ``ss`` недоступен.
"""

from __future__ import annotations

import shlex
from collections.abc import Callable
import re
from dataclasses import dataclass

from vpconnect_install.config import ProvisionConfig
from vpconnect_install.ssh_session import SSHSession

LogFn = Callable[[str], None]

# Сообщение совпадает с configure_bootstrap.INSTALL_ABORTED_MSG (импорт оттуда даёт цикл).
INSTALL_ABORTED_MSG = "Установка прекращена, обратитесь к администратору"

# Совпадает с MTPROXY_INTERNAL_PORT в vpconnect-configure/07_setmtproxy.sh
MTPROXY_INTERNAL_TCP_PORT = 8888


def _need_run_04_connect(config: ProvisionConfig) -> bool:
    """Копия логики vpconfigure_provision.need_run_04_connect (избегаем циклического импорта)."""
    if config.auto_setup:
        return True
    return bool(
        config.new_root_password.strip()
        or config.new_ssh_port is not None
        or config.new_ssh_public_key.strip()
        or config.enable_firewall
    )


@dataclass(frozen=True)
class PortCheck:
    """Один порт для проверки: протокол ``tcp``/``udp``, номер, подпись для лога."""

    proto: str
    port: int
    purpose: str
    service: str


def required_listen_port_checks(config: ProvisionConfig) -> list[PortCheck]:
    """Собрать порты, которые реально понадобятся в этом прогоне (после apply_auto_setup)."""
    checks: list[PortCheck] = []
    seen: set[tuple[str, int]] = set()

    def add(proto: str, port: int, purpose: str, service: str) -> None:
        key = (proto.lower(), int(port))
        if key in seen:
            return
        seen.add(key)
        checks.append(PortCheck(proto=proto.lower(), port=int(port), purpose=purpose, service=service))

    if _need_run_04_connect(config) and config.new_ssh_port is not None:
        if config.new_ssh_port != config.port:
            add("tcp", config.new_ssh_port, "новый SSH (sshd после шага 04)", "ssh")

    if config.set_wireguard:
        add("udp", config.wg_port, "WireGuard (UDP ListenPort)", "wireguard")

    if config.set_mtproxy:
        add("tcp", config.mtproxy_port, "MTProxy для клиентов (-H)", "mtproxy")
        if config.mtproxy_port != MTPROXY_INTERNAL_TCP_PORT:
            add("tcp", MTPROXY_INTERNAL_TCP_PORT, "MTProxy внутренний (-p, см. 07_setmtproxy.sh)", "mtproxy")

    if config.set_vpmanage:
        add("tcp", config.vpm_http_port, "VPManage HTTP (gunicorn)", "vpmanage")

    return checks


# Запуск: bash -lc SCRIPT _ spec1 spec2 …  (позиционные параметры для «for spec do»)
_REMOTE_PORT_CHECK_SCRIPT = r"""
set -euo pipefail
is_ssh_port() {
  local p="$1"
  if command -v sshd >/dev/null 2>&1; then
    sshd -T 2>/dev/null | awk '/^port[[:space:]]+/ {print $2}' | grep -Fxq "$p" && return 0
  fi
  if [ -r /etc/ssh/sshd_config ] \
    && grep -Eiq "^[[:space:]]*Port[[:space:]]+$p([[:space:]]|$)" \
      /etc/ssh/sshd_config; then
    return 0
  fi
  return 1
}
is_wireguard_port() {
  local p="$1"
  if command -v wg >/dev/null 2>&1; then
    wg show all listen-port 2>/dev/null | awk '{print $2}' | grep -Fxq "$p" && return 0
  fi
  if ls /etc/wireguard/*.conf >/dev/null 2>&1; then
    grep -hE '^[[:space:]]*ListenPort[[:space:]]*=' /etc/wireguard/*.conf 2>/dev/null \
      | sed -E 's/.*=[[:space:]]*([0-9]+).*/\1/' \
      | grep -Fxq "$p" && return 0
  fi
  return 1
}
is_mtproxy_port() {
  local p="$1"
  if [ -r /etc/systemd/system/mtproxy.service ] \
    && grep -Eq \
      "(^|[[:space:]])-H[[:space:]]+$p([[:space:]]|$)|(^|[[:space:]])-p[[:space:]]+$p([[:space:]]|$)" \
      /etc/systemd/system/mtproxy.service; then
    return 0
  fi
  if command -v systemctl >/dev/null 2>&1; then
    systemctl cat mtproxy 2>/dev/null \
      | grep -Eq "(^|[[:space:]])-H[[:space:]]+$p([[:space:]]|$)|(^|[[:space:]])-p[[:space:]]+$p([[:space:]]|$)" \
      && return 0
  fi
  return 1
}
is_vpmanage_port() {
  local p="$1"
  if [ -r /etc/systemd/system/vpconnect-manage.service ] \
    && grep -Eq "(--bind|--bind=)[^ ]*:$p([[:space:]]|$)" /etc/systemd/system/vpconnect-manage.service; then
    return 0
  fi
  if command -v systemctl >/dev/null 2>&1; then
    systemctl cat vpconnect-manage 2>/dev/null \
      | grep -Eq "(--bind|--bind=)[^ ]*:$p([[:space:]]|$)" \
      && return 0
  fi
  if [ -r /root/.vpconnect-configure.env ] \
    && grep -Eq "^[[:space:]]*export[[:space:]]+VPCONFIGURE_VPM_HTTP_PORT=$p([[:space:]]|$)" \
      /root/.vpconnect-configure.env; then
    return 0
  fi
  return 1
}
details_for_ss() {
  local proto="$1"
  local p="$2"
  if [ "$proto" = tcp ]; then
    ss -Hlnpt "sport = :$p" 2>/dev/null || true
  elif [ "$proto" = udp ]; then
    ss -Hlunp "sport = :$p" 2>/dev/null || true
  else
    printf '%s\n' "Неизвестный протокол: $proto" >&2
    exit 2
  fi
}
details_for_sockstat() {
  local proto="$1"
  local p="$2"
  if [ "$proto" = tcp ]; then
    sockstat -l -P tcp -p "$p" 2>/dev/null || true
  elif [ "$proto" = udp ]; then
    sockstat -l -P udp -p "$p" 2>/dev/null || true
  else
    printf '%s\n' "Неизвестный протокол: $proto" >&2
    exit 2
  fi
}
if command -v ss >/dev/null 2>&1; then
  TOOL=ss
elif [ "$(uname -s)" = FreeBSD ] && command -v sockstat >/dev/null 2>&1; then
  TOOL=sockstat
else
  printf '%s\n' "Не найдены команды ss или sockstat (FreeBSD) для проверки портов." >&2
  exit 2
fi
busy_count=0
for spec do
  proto=${spec%%:*}
  rest=${spec#*:}
  port=${rest%%:*}
  expected=${rest#*:}
  if [ "$expected" = "$rest" ]; then
    expected=""
  fi
  if ! [[ "$port" =~ ^[0-9]+$ ]] || [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
    printf '%s\n' "Некорректная спецификация порта: $spec" >&2
    exit 2
  fi
  details=""
  if [ "$TOOL" = ss ]; then
    details="$(details_for_ss "$proto" "$port")"
  else
    details="$(details_for_sockstat "$proto" "$port")"
  fi
  if [ -n "${details//[[:space:]]/}" ]; then
    details=$(printf '%s' "$details" | tr '\n' ';' | tr -s ' ' | tr '|' '/')
    owner=""
    if [ "$expected" = ssh ] && is_ssh_port "$port"; then
      owner="ssh"
    elif [ "$expected" = wireguard ] && [ "$proto" = udp ] && is_wireguard_port "$port"; then
      owner="wireguard"
    elif [ "$expected" = mtproxy ] && is_mtproxy_port "$port"; then
      owner="mtproxy"
    elif [ "$expected" = vpmanage ] && is_vpmanage_port "$port"; then
      owner="vpmanage"
    fi
    if [ -n "$owner" ]; then
      printf '%s\n' "BUSY:${proto}:${port}|OWNER:${owner}|${details}"
    else
      printf '%s\n' "BUSY:${proto}:${port}|${details}"
    fi
    busy_count=$((busy_count + 1))
  fi
done
if [ "$busy_count" -gt 0 ]; then
  exit 1
fi
exit 0
"""

_PROCESS_MATCHERS: dict[str, tuple[re.Pattern[str], ...]] = {
    "ssh": (re.compile(r"\bsshd\b", re.IGNORECASE),),
    "wireguard": (
        re.compile(r"\bwg-quick\b", re.IGNORECASE),
        re.compile(r"\bwireguard\b", re.IGNORECASE),
        re.compile(r"\bwg\b", re.IGNORECASE),
    ),
    "mtproxy": (
        re.compile(r"\bmtproto-proxy\b", re.IGNORECASE),
        re.compile(r"\bmtproxy\b", re.IGNORECASE),
    ),
    "vpmanage": (
        re.compile(r"\bgunicorn\b", re.IGNORECASE),
        re.compile(r"\bvpconnect-manage\b", re.IGNORECASE),
        re.compile(r"\bmanage_site\b", re.IGNORECASE),
    ),
}


def _is_expected_reinstall_owner(check: PortCheck, details: str) -> bool:
    if f"OWNER:{check.service}" in details:
        return True
    if not details.strip():
        return False
    for rx in _PROCESS_MATCHERS.get(check.service, ()):
        if rx.search(details):
            return True
    return False


def _raise_missing_port_check_tool(log: LogFn, out_s: str, err_s: str) -> None:
    log(f"[Порты] {err_s or out_s or 'Нет утилиты проверки портов'}")
    log("[Порты] На Linux после 00_bashinstall.sh должен быть установлен пакет с ss (iproute2/iproute).")
    log(INSTALL_ABORTED_MSG)
    raise RuntimeError(INSTALL_ABORTED_MSG)


def _partition_busy_lines(
    busy_lines: list[str],
    checks_by_spec: dict[str, PortCheck],
) -> tuple[list[str], list[str]]:
    allowed_reinstall: list[str] = []
    blocked_unknown: list[str] = []
    for ln in busy_lines:
        payload = ln.split("BUSY:", 1)[1]
        spec, _, details = payload.partition("|")
        spec = spec.strip()
        details = details.strip()
        check = checks_by_spec.get(spec)
        if check and _is_expected_reinstall_owner(check, details):
            allowed_reinstall.append(
                f"{spec} — {check.purpose}; обнаружен процесс: {details or 'неизвестно'}",
            )
            continue
        purpose = check.purpose if check else "неизвестное назначение"
        blocked_unknown.append(
            f"{spec} — {purpose}; обнаружен процесс: {details or 'не удалось определить'}",
        )
    return allowed_reinstall, blocked_unknown


def _log_busy_rows(log: LogFn, header: str, rows: list[str]) -> None:
    log(header)
    for row in rows:
        log(f"[Порты]   {row}")


def _raise_blocked_ports(log: LogFn, blocked_unknown: list[str]) -> None:
    _log_busy_rows(log, "[Порты] Найдены занятые порты неизвестными/чужими приложениями:", blocked_unknown)
    log(
        "[Порты] Освободите эти порты на сервере или измените порты в настройках установки "
        "(CLI / GUI) и повторите прогон."
    )
    log(INSTALL_ABORTED_MSG)
    raise RuntimeError(INSTALL_ABORTED_MSG)


def _raise_generic_port_check_failure(log: LogFn, code: int, err_s: str, out_s: str) -> None:
    log(f"[Порты] Проверка завершилась с кодом {code}.")
    if err_s:
        log(f"[Порты] stderr:\n{err_s}")
    if out_s:
        log(f"[Порты] stdout:\n{out_s}")
    log(
        "[Порты] Освободите указанные порты на сервере или измените порты в настройках установки "
        "(CLI / GUI) и повторите прогон."
    )
    log(INSTALL_ABORTED_MSG)
    raise RuntimeError(INSTALL_ABORTED_MSG)


def assert_remote_listen_ports_free(
    session: SSHSession,
    config: ProvisionConfig,
    log: LogFn,
    timeout: int,
) -> None:
    """Проверить на сервере, что нужные порты свободны; иначе лог и :exc:`RuntimeError`."""
    checks = required_listen_port_checks(config)
    if not checks:
        return

    specs = [f"{c.proto}:{c.port}:{c.service}" for c in checks]
    checks_by_spec = {f"{c.proto}:{c.port}": c for c in checks}

    log("[Порты] Проверка занятости перед установкой (после 00_bashinstall.sh)…")
    for c in checks:
        log(f"[Порты]   {c.proto.upper()} {c.port} — {c.purpose}")

    script = _REMOTE_PORT_CHECK_SCRIPT.strip()
    argv = ["bash", "-lc", script, "_", *specs]
    remote_cmd = shlex.join(argv)

    code, out, err = session.exec_command(remote_cmd, timeout=min(timeout, 120))

    out_s = (out or "").strip()
    err_s = (err or "").strip()

    if code == 2 or ("Не найдены" in err_s and code != 0):
        _raise_missing_port_check_tool(log, out_s, err_s)

    busy_lines = [ln.strip() for ln in (out or "").splitlines() if ln.strip().startswith("BUSY:")]
    if busy_lines:
        allowed_reinstall, blocked_unknown = _partition_busy_lines(busy_lines, checks_by_spec)
        if allowed_reinstall:
            _log_busy_rows(
                log,
                "[Порты] Обнаружены порты, занятые уже установленными компонентами vpconnect (повторная установка):",
                allowed_reinstall,
            )
        if blocked_unknown:
            _raise_blocked_ports(log, blocked_unknown)
        if allowed_reinstall and code != 0:
            log("[Порты] Конфликты распознаны как повторная установка наших сервисов — продолжаю.")
            return

    if code != 0:
        _raise_generic_port_check_failure(log, code, err_s, out_s)

    log("[Порты] Все проверяемые порты свободны.")
