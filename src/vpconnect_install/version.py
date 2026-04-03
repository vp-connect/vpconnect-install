"""Single source for release version."""

from __future__ import annotations

__version__ = "0.1.0"


def scripts_git_branch(dist_version: str) -> str:
    """Совместимость: сопоставление версии пакета с именем ветки Git (тесты, внешние вызовы)."""
    v = dist_version.strip().lower()
    if "dev" in v or v in ("0", "0.0.0"):
        return "main"
    if v.startswith("v"):
        return dist_version.strip()
    return f"v{dist_version.strip()}"
