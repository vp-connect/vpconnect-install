"""
Метапакет **vpconnect-install**: публичный API версии и ветки Git для релизов.

Рабочий код расположен в пакетах ``application``, ``commands``, ``config``, ``core``,
``gui``, ``server``, ``shared``, ``cli``.
"""

from shared.version import __version__, scripts_git_branch

__all__ = ["__version__", "scripts_git_branch"]
