"""
Пакет ``commands`` — выполнение удалённых шагов vpconnect-configure (bootstrap 00–03, фазы 04–08).

**Назначение:** загрузка и запуск скриптов на сервере, разбор ``result:`` строк, вызов ``04–08``.

**Разрешённые зависимости:** ``shared``, ``config``, ``server``, ``application.outputs`` (локальные артефакты).

**Запрещено:** ``cli``, ``gui``.

**Публичный API:** :mod:`commands.configure_bootstrap`, :mod:`commands.vpconfigure_provision`.
"""
