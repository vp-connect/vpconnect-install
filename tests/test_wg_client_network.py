"""Нормализация поля «Сеть WG подключений»."""

from __future__ import annotations

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
