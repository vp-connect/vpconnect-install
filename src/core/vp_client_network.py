"""
Совместимый API нормализации сети VPN-клиентов.

Исторически реализация находилась в ``core.wg_client_network``; здесь даются
переименованные функции/константы для нового нейтрального контракта ``vp*``.
"""

from __future__ import annotations

from core.wg_client_network import (
    DEFAULT_WG_ADDRESS_CIDR,
    normalize_wg_client_network,
    parse_optional_wg_client_network,
)

DEFAULT_VP_ADDRESS_CIDR = DEFAULT_WG_ADDRESS_CIDR


def normalize_vp_client_network(raw: str) -> tuple[str, str]:
    return normalize_wg_client_network(raw)


def parse_optional_vp_client_network(raw: str | None) -> tuple[str, str] | None:
    return parse_optional_wg_client_network(raw)

