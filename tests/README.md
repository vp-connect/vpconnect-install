# Тесты по слоям `src/`

Структура каталогов повторяет пакеты: тест лежит рядом с тем слоем, который он проверяет.

| Каталог | Модули `src` |
|---------|----------------|
| [`application/`](application/) | `application.outputs`, `application.runner` |
| [`commands/`](commands/) | `commands.configure_bootstrap`, `commands.vpconfigure_provision` |
| [`config/`](config/) | `config.provision` (`ProvisionConfig`) |
| [`core/`](core/) | `core.vp_client_network` |
| [`server/`](server/) | `server.ssh_session`, `server.remote_port_precheck`, `server.remote_scripts_fetch`, `core.github_repo` (часть тестов URL) |
| [`cli/`](cli/) | `cli.main` |
| [`gui/`](gui/) | `gui.gui_*` |
| [`vpconnect_install/`](vpconnect_install/) | точка входа `__main__`, `runpy` по скриптам |

`PYTHONPATH=src` задаётся в [`pyproject.toml`](../pyproject.toml) для pytest.
