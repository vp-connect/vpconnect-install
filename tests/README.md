# Тесты после разбиения на пакеты

- **Unit (без сети/SSH):** `core`, `config`, разбор stdout в `commands.configure_bootstrap`, часть `application.outputs`.
- **С моками Paramiko / requests:** `server.ssh_session`, `commands.configure_bootstrap` (HTTP), `server.remote_port_precheck`.
- **Сценарий прогона:** `application.runner` с патчами на `SSHSession`, bootstrap и фазы.
- **CLI:** `cli.main` — парсер, секреты, `main` с патчем на `run`.
- **GUI:** `gui.gui_tk` — только там, где доступен Tcl/Tk; часть тестов помечена skip в headless.

Импорты в тестах идут из пакетов верхнего уровня (`application`, `commands`, `config`, …); `PYTHONPATH=src` задаётся в `pyproject.toml` для pytest.
