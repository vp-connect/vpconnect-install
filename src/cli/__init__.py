"""
Пакет ``cli`` — интерфейс командной строки (argparse).

**Назначение:** разбор аргументов, сборка :class:`config.ProvisionConfig`, вызов :func:`application.runner.run`.

**Разрешённые зависимости:** ``application``, ``config``, ``shared``.

**Запрещено:** ``gui``, прямой импорт ``server`` / ``commands`` (только через ``application``).

**Публичный API:** :func:`cli.main.main`, :func:`cli.main.build_arg_parser`, :func:`cli.main.config_from_args`.
"""
from .main import build_arg_parser, config_from_args, main

__all__ = ["main", "build_arg_parser", "config_from_args"]
