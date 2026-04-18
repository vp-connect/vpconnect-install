"""Нормализация поля «Сеть WG подключений»."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from vpconnect_install.wg_client_network import (
    normalize_wg_client_network,
    parse_optional_wg_client_network,
)


@pytest.mark.parametrize(
    ("raw", "expected_addr", "expected_net"),
    [
        ("10.0.0.0/24", "10.0.0.1/24", "10.0.0.0/24"),
        ("10.0.0.1/24", "10.0.0.1/24", "10.0.0.0/24"),
        ("10.0.0.0", "10.0.0.1/24", "10.0.0.0/24"),
        ("10.0.0.1", "10.0.0.1/24", "10.0.0.0/24"),
        ("10.0", "10.0.0.1/24", "10.0.0.0/24"),
        ("10.0.", "10.0.0.1/24", "10.0.0.0/24"),
        ("10.0.5", "10.0.5.1/24", "10.0.5.0/24"),
        ("10.0.0.0/16", "10.0.0.1/24", "10.0.0.0/24"),
    ],
)
def test_normalize_wg_client_network_ok(raw: str, expected_addr: str, expected_net: str) -> None:
    addr, net = normalize_wg_client_network(raw)
    assert addr == expected_addr
    assert net == expected_net


def test_parse_optional_empty() -> None:
    assert parse_optional_wg_client_network("") is None
    assert parse_optional_wg_client_network("  \t  ") is None
    assert parse_optional_wg_client_network(None) is None


@pytest.mark.parametrize("bad", ["10", "10.", ".1", "999.0.0.0", "10.0.0.1/99", "not-an-ip"])
def test_normalize_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        normalize_wg_client_network(bad)


@pytest.mark.parametrize(
    ("raw", "msg"),
    [
        ("10.0.0.0/xx", "Некорректная маска"),
        ("10.0.0.0/33", "Некорректная маска"),
        ("1.2.3.4.5", "Слишком много"),
        ("10.xx.0.0", "Некорректный октет"),
    ],
)
def test_normalize_rejects_specific_messages(raw: str, msg: str) -> None:
    with pytest.raises(ValueError, match=msg):
        normalize_wg_client_network(raw)


def test_normalize_wraps_ipaddress_interface_errors() -> None:
    with patch("vpconnect_install.wg_client_network.ipaddress.IPv4Interface", side_effect=ValueError("bad")):
        with pytest.raises(ValueError, match="Не удалось сформировать корректный адрес WireGuard"):
            normalize_wg_client_network("10.0.0.0")
