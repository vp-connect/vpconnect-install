# Handoff Report: VP Service Migration

## Цель изменений
- Уйти от фиксированной установки WireGuard к выбору VPN-сервиса: `wireguard` или `amneziawg`.
- Полностью обобщить параметры и названия: заменить WG-специфику на `vp` / `vpserver`.
- Синхронизировать изменения между двумя репозиториями:
  - `vpconnect-configure` (ветки `debian`, `centos`, `freebsd`)
  - `vpconnect-install` (CLI, GUI, конфиг, раннер, тесты)
- Обновить дефолтные серверные пути:
  - `/usr/vpserver/client_cert`
  - `/usr/vpserver/client_config`

## Обязательные результаты
- Новый шаг `06_setvpservice.sh` вместо `06_setwireguard.sh`.
- Выбор сервиса через параметр шага 06: `wireguard|amneziawg` (default: `wireguard`).
- WireGuard-ветка в 06 сохраняет текущую рабочую логику.
- AmneziaWG-ветка в 06 доведена до рабочего состояния.
- Шаги 07/08 продолжают работать с новым обобщенным env-контрактом.
- В `vpconnect-install` добавлен новый параметр выбора сервиса и UI-радио-кнопки.

## Репозиторий: vpconnect-configure

## Ветки, которые нужно обновить
- `debian`
- `centos`
- `freebsd`

Изменения в каждой ветке должны быть эквивалентны по контракту (с учетом OS-специфики).

## Основной шаг 06
- Старый файл: `06_setwireguard.sh`
- Новый файл: `06_setvpservice.sh`

Что сделать в новом 06:
- Добавить аргумент выбора сервиса (например `--vp-service wireguard|amneziawg`).
- Сохранить существующую логику WireGuard как подрежим.
- Добавить/доработать установку AmneziaWG как второй подрежим.
- Унифицировать названия env/параметров с `wg*` на `vp*`/`vpserver*`.
- Обновить дефолтные пути client artifacts на:
  - `/usr/vpserver/client_cert`
  - `/usr/vpserver/client_config`
- Сохранить формат `result:...` и `--export/--persist` контракт.

## Файлы-потребители, которые нужно синхронизировать в vpconnect-configure
- `07_setmtproxy.sh`
- `08_setvpmanage.sh`
- `10_uninstall.sh`
- `wg/*.sh` и `wg/README.md` (или соответствующий переезд/переименование, если запланирован)
- `README.md`

## Что проверить после правок 06/07/08
- Персист env-файла после 06 корректен для последующих шагов 07/08.
- 07 корректно читает новые `vp*` переменные и пути.
- 08 корректно читает новые `vp*` переменные и пути.
- `10_uninstall.sh` удаляет ресурсы, созданные обоими вариантами VPN-сервиса.

## Репозиторий: vpconnect-install

## Модель конфигурации и валидация
- `src/config/provision.py`
- Ввести обобщенные поля для VPN-сервиса:
  - флаг установки VPN-сервиса (вместо `set_wireguard`)
  - выбор сервиса (`wireguard|amneziawg`)
  - переименованные поля `wg_*` -> `vp*`
- Обновить валидацию и нормализацию, которые завязаны на старый `set_wireguard`.

## Defaults
- `src/shared/defaults.py`
- Поменять дефолтные пути:
  - `/usr/wireguard/client_cert` -> `/usr/vpserver/client_cert`
  - `/usr/wireguard/client_config` -> `/usr/vpserver/client_config`
- Привести комментарии/доки к новому нейтральному смыслу (`VP service` вместо только `WireGuard`).

## CLI
- `src/cli/main.py`
- Заменить `--set-wireguard` на обобщенный флаг установки VPN.
- Добавить параметр выбора сервиса (`wireguard|amneziawg`).
- Переименовать WG-аргументы в обобщенные `vp*`.
- Сохранить корректное поведение `--auto-setup`.

## Оркестрация запуска скриптов
- `src/commands/vpconfigure_provision.py`
- Вместо `06_setwireguard.sh` вызывать `06_setvpservice.sh`.
- Прокидывать выбор сервиса и новые `vp*` параметры.
- Обновить места, где в логах/артефактах явно упоминается WireGuard, на нейтральные формулировки (кроме поля выбора сервиса).

## Порт-чекер и ACCESS
- `src/server/remote_port_precheck.py`
- `src/application/outputs.py`
- Перевести поля и вывод на `vp*`/`vpserver*`, сохранив полезную диагностику.
- Отражать выбранный тип VPN-сервиса в результирующих данных.

## GUI
- `src/gui/gui_tk.py`
- `src/gui/gui_captions_ru.py`
- `src/gui/gui_hints_ru.py`
- В секции установки VPN:
  - оставить переключатель установки;
  - добавить радио-кнопки выбора: `WireGuard` и `AmneziaWG`.
- Обновить подписи/подсказки с общими терминами `VPN server`/`vpserver`, не теряя конкретику выбора типа.

## Набор тестов, которые точно затронутся
- `tests/config/test_config_validation.py`
- `tests/cli/test_cli.py`
- `tests/cli/test_cli_main_and_secrets.py`
- `tests/commands/test_vpconfigure_phases_extended_mock.py`
- `tests/commands/test_vpconfigure_provision.py`
- `tests/gui/test_gui_tk_unit.py`
- `tests/application/test_outputs.py`
- `tests/server/test_remote_port_precheck.py`

## Карта обязательных переименований (концептуально)
- `set_wireguard` -> `set_vpserver` (или эквивалентное обобщенное имя)
- `--set-wireguard` -> `--set-vpserver` (или эквивалент)
- `06_setwireguard.sh` -> `06_setvpservice.sh`
- `wg_*` поля конфигурации -> `vp*` поля
- WireGuard-only тексты -> нейтральные VP-service тексты

Важно:
- Названия `WireGuard` и `AmneziaWG` остаются только там, где пользователь выбирает тип сервиса.
- Все остальные параметры должны быть обобщенными.

## Порядок реализации (рекомендуемый)
- Сначала ветка `debian` в `vpconnect-configure` как эталон (новый 06 + новый env-контракт).
- Затем перенести в `centos` и `freebsd`.
- После стабилизации `vpconnect-configure` обновить `vpconnect-install`.
- В конце обновить тесты, README и проверить end-to-end.

## Риски и контрольные точки
- Риск: рассинхрон env-переменных между 06 и 07/08.
  - Контроль: явно прогнать сценарии с `--persist` и новой сессией shell.
- Риск: частичный рефактор имен (где-то остались `wg*`).
  - Контроль: глобальный grep по `set_wireguard`, `--set-wireguard`, `06_setwireguard`, `VPCONFIGURE_WG_`, `wg_`.
- Риск: UI/CLI используют разные имена параметров.
  - Контроль: сверить `ProvisionConfig`, `CLI parser`, `_build_config` GUI, и раннер.
- Риск: сломать обратный сценарий WireGuard.
  - Контроль: отдельная проверка режима `wireguard` после миграции.
- Риск: нерабочая ветка `amneziawg`.
  - Контроль: хотя бы smoke-проверка установки и запуска сервиса в каждой OS-ветке.

## Критерии готовности
- В обоих репозиториях нет рабочих путей, требующих старый `06_setwireguard.sh`.
- Внешний контракт установки VPN полностью обобщен в `vp/vpserver`.
- Выбор `WireGuard/AmneziaWG` работает через CLI и GUI.
- Дефолтные пути применяются как:
  - `/usr/vpserver/client_cert`
  - `/usr/vpserver/client_config`
- Тесты из затронутых модулей обновлены и проходят.
