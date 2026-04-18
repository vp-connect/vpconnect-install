"""
Пакет ``server`` — транспорт и удалённая сторона (SSH, предпроверки, URL к скриптам).

**Назначение:** сессия Paramiko, проверка занятых портов на сервере, построение raw URL GitHub.

**Разрешённые зависимости:** ``shared``, ``core``, ``config`` (только тип параметров, без сценариев).

**Запрещено:** ``cli``, ``gui``, ``application`` (оркестрация — в ``application``).

**Публичный API:** :mod:`server.ssh_session`, :mod:`server.remote_port_precheck`, :mod:`server.remote_scripts_fetch`.
"""
