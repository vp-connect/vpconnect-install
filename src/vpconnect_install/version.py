"""
Версия дистрибутива пакета и утилита для имени ветки Git (тесты, сборки).
"""

from __future__ import annotations

__version__ = "0.1.0"


def scripts_git_branch(dist_version: str) -> str:
    """
    Сопоставить строку версии пакета с типичным именем ветки на GitHub (``v0.1.0`` или ``main`` для dev).
    """
    v = dist_version.strip().lower()
    if "dev" in v or v in ("0", "0.0.0"):
        return "main"
    if v.startswith("v"):
        return dist_version.strip()
    return f"v{dist_version.strip()}"
