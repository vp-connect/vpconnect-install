"""
Пакет ``application`` — сценарий полного прогона установки (оркестрация).

**Назначение:** артефакты → SSH → bootstrap → фазы → перезагрузка;
функция :func:`~application.runner.run`.

**Разрешённые зависимости:** ``shared``, ``config``, ``server``, ``commands``,
модуль ``application.outputs``.

**Запрещено:** ``cli``, ``gui``.

**Публичный API:** :func:`application.runner.run`.
"""
from .runner import run

__all__ = ["run"]
