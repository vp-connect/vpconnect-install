"""
Пакет ``config`` — модель параметров одного прогона и валидация.

**Назначение:** датакласс :class:`~config.provision.ProvisionConfig`, методы ``validate()`` и ``apply_auto_setup()``.

**Разрешённые зависимости:** ``shared``, ``core``.

**Запрещено:** ``server``, ``commands``, ``application``, ``cli``, ``gui``.

**Публичный API:** :class:`config.provision.ProvisionConfig` (реэкспорт ниже).
"""
from .provision import ProvisionConfig

__all__ = ["ProvisionConfig"]
