"""
Пакет **vpconnect-install**: провижининг по SSH через **vpconnect-configure**
(WireGuard, MTProxy, VPManage).

Публичный API: версия и вспомогательная функция ветки Git для релизов.
"""

from vpconnect_install.version import __version__, scripts_git_branch

__all__ = ["__version__", "scripts_git_branch"]
