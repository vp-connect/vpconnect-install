"""Resolve FQDN using domain_client_key via HTTP service."""

from __future__ import annotations

import json

import requests

from vpconnect_install import defaults as d


def resolve_domain_fqdn(client_key: str, *, timeout: int | None = None) -> str:
    """
    GET service URL with query param key=...; body is plain FQDN or JSON with domain/fqdn field.
    """
    t = timeout if timeout is not None else d.DOMAIN_CLIENT_SERVICE_TIMEOUT
    key = client_key.strip()
    if not key:
        raise ValueError("empty domain_client_key")
    r = requests.get(
        d.DOMAIN_CLIENT_SERVICE_URL,
        params={"key": key},
        timeout=t,
    )
    r.raise_for_status()
    text = (r.text or "").strip()
    if not text:
        raise ValueError("empty response from domain service")
    if text.startswith("{"):
        data = json.loads(text)
        fqdn = (data.get("domain") or data.get("fqdn") or "").strip()
        if not fqdn:
            raise ValueError("domain service JSON missing domain/fqdn")
        return fqdn
    line = text.splitlines()[0].strip()
    if not line:
        raise ValueError("domain service returned no FQDN")
    return line
