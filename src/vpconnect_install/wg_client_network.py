"""
Нормализация поля «Сеть WG подключений» к виду ``x.y.z.1/24`` и сети ``x.y.z.0/24``.

Пустое значение означает умолчание установщика (как в ``06_setwireguard.sh`` без ``--wg-address``).
"""

from __future__ import annotations

import ipaddress
import re

# Совпадает с умолчанием в vpconnect-configure/06_setwireguard.sh
DEFAULT_WG_ADDRESS_CIDR = "10.8.0.1/24"


def _wg_strip_trailing_dots(s: str) -> str:
    s = s.rstrip()
    return re.sub(r"\.+$", "", s)


def _wg_ipv4_before_slash(s: str, raw: str) -> str:
    if "/" not in s:
        return s.strip()
    addr_part, _, suffix = s.partition("/")
    suffix = suffix.strip()
    if not suffix.isdigit() or not (0 <= int(suffix) <= 32):
        raise ValueError(f"Некорректная маска в CIDR: {raw!r}")
    return addr_part.strip()


def _wg_octets_from_ip_part(ip_before_slash: str) -> list[str]:
    parts = [p for p in ip_before_slash.split(".") if p != ""]
    if len(parts) < 2:
        raise ValueError(
            "Укажите не менее двух октетов сети (например 10.8 или 10.8.0.1), "
            "либо оставьте поле пустым для значения по умолчанию."
        )
    if len(parts) > 4:
        raise ValueError("Слишком много компонентов в адресе.")
    while len(parts) < 3:
        parts.append("0")
    if len(parts) == 3:
        parts.append("1")
    else:
        parts[3] = "1"
    return parts


def _wg_validate_octets(parts: list[str]) -> tuple[int, int, int, int]:
    a, b, c, d = parts[0], parts[1], parts[2], parts[3]
    for label, octet in (("первый", a), ("второй", b), ("третий", c), ("четвёртый", d)):
        if not octet.isdigit():
            raise ValueError(f"Некорректный октет ({label}): {octet!r}")
        v = int(octet)
        if v < 0 or v > 255:
            raise ValueError(f"Октет вне диапазона 0–255: {octet}")
    return int(a), int(b), int(c), int(d)


def normalize_wg_client_network(raw: str) -> tuple[str, str]:
    """
    Разобрать ввод и вернуть ``(address_cidr, network_cidr)`` в форме ``a.b.c.1/24`` и ``a.b.c.0/24``.

    Допустимо:
    - пустая строка → :exc:`ValueError` не вызывается из этой функции: вызывайте
      :func:`parse_optional_wg_client_network`.

    - ``10.0.0.0/24``, ``10.0.0.1/24``, ``10.0.0.0``, ``10.0.0.1``
    - не менее двух октетов: ``10.0``, ``10.0.`` (хвостовая точка допускается)
    """
    s = (raw or "").strip()
    if not s:
        raise ValueError("Пустая строка: используйте parse_optional_wg_client_network")
    s = _wg_strip_trailing_dots(s)
    ip_before_slash = _wg_ipv4_before_slash(s, raw)
    parts = _wg_octets_from_ip_part(ip_before_slash)
    ia, ib, ic, _ = _wg_validate_octets(parts)
    address_cidr = f"{ia}.{ib}.{ic}.1/24"
    try:
        iface = ipaddress.IPv4Interface(address_cidr)
    except ValueError as e:
        raise ValueError(f"Не удалось сформировать корректный адрес WireGuard: {address_cidr}") from e
    return address_cidr, str(iface.network)


def parse_optional_wg_client_network(raw: str | None) -> tuple[str, str] | None:
    """
    Если ``raw`` пустой — ``None`` (скрипт 06 оставит адрес по умолчанию).

    Иначе — пара ``(address_cidr, network_cidr)``.
    """
    if raw is None or not str(raw).strip():
        return None
    return normalize_wg_client_network(str(raw))
