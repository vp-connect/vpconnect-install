# vpconnect-install

Инструмент на **Python 3.10+** для настройки сервера по **SSH**: скачивает и выполняет скрипты **[vpconnect-configure](https://github.com/vp-connect/vpconnect-configure)** (этапы **00–03** в `$HOME` на сервере, **03** клонирует репозиторий), затем по пути из вывода **03** запускает **04–08** (подключение/домен, WireGuard, MTProxy, VPManage / selfvpn и финализация). Точки входа: **CLI**, **GUI (Tkinter)**, сборка **PyInstaller** `.exe`.

> **Риск.** Смена SSH-порта, firewall или паролей может отрезать доступ. Держите **консоль** провайдера и тестируйте на одноразовой VM. Режима «только посмотреть» нет: выполняются реальные команды на сервере.

## Поддерживаемые версии и платформы

### Машина оператора (CLI и GUI из исходников)

- **Python** ≥ **3.10** (см. `requires-python` в `pyproject.toml`).
- **ОС:** **Windows** 10/11, **Linux**, **macOS** — везде, где доступны зависимости (`paramiko`, `cryptography`, `requests`) и стандартный **Tkinter** (для GUI; на минимальных установках Linux может понадобиться пакет `python3-tk`).
- Сеть: SSH до сервера, **GitHub** `raw.githubusercontent.com` (скрипты **00–03**), клонирование репозитория по `--vpconfigure-repo-url`.

Для `./bootstrap.sh` на Windows удобны **Git Bash** или **WSL**; можно обойтись без них, установив Python и venv вручную.

### Сборка GUI `.exe` (дистрибутив)

- **Только 64-bit Windows** 10 или новее; отдельный Python для запуска `.exe` не нужен.
- Артефакты по умолчанию пишутся в **текущий рабочий каталог** (`provision-artifacts/…`). Краткая справка — в `dist/readme.txt` рядом с exe.

### Целевой сервер (скрипты vpconnect-configure)

На стороне сервера поддержка версий ОС задаётся скриптами **vpconnect-configure** (после `01_getosversion.sh` используется одно из **трёх семейств** — имя ветки `VPCONFIGURE_GIT_BRANCH`):

| Семейство | Суть | Примеры |
|-----------|------|---------|
| **debian** | `apt` | Debian 12–13, Ubuntu 22.04 / 24.04 / 26.04 и производные (Linux Mint, Raspberry Pi OS и т.д.) |
| **centos** | `dnf` / `yum` | RHEL 8–10, AlmaLinux, Rocky Linux, Oracle Linux, Fedora 39+, Amazon Linux 2023+ и аналоги |
| **freebsd** | пакеты FreeBSD | FreeBSD 13–14 |

Точный список релизов, производных и явных исключений — в [README vpconnect-configure](https://github.com/vp-connect/vpconnect-configure/blob/main/README.md) (в репозитории рядом: `vpconnect-configure/README.md`).

## Как устроен прогон

1. **Локально** (до SSH): создаётся каталог артефактов `provision-artifacts/<host>-<timestamp>/`, проверяется право записи; генерируется пара ключей оператора.
2. **SSH** как root (ключ или пароль).
3. **Bootstrap** (`configure_bootstrap.py`): для каждого из `00_bashinstall.sh` … `03_getconfigure.sh` — загрузка с GitHub (raw), запуск в домашнем каталоге на сервере.
4. **03** клонирует **vpconnect-configure**; из stdout извлекается `path:` — каталог установки скриптов **04–08**.
5. **Провижининг** (`vpconfigure_provision.py`): при необходимости **04** (настройка доступа), затем **05–08** (WireGuard, MTProxy, VPManage и т.д. — в соответствии с флагами конфигурации).
6. **Локально**: `ACCESS.txt`, файлы с паролями при необходимости, публичный ключ в артефактах.

Версия пакета и ветка raw для **00–03** задаются в `vpconnect_install/defaults.py` (`VPCONFIGURE_RAW_GIT_BRANCH` и URL репозитория).

## Быстрый старт

```sh
./bootstrap.sh
. .venv/bin/activate
python -m vpconnect_install --help
```

## CLI

Кратко о платформах см. в конце вывода **`python -m vpconnect_install --help`** (epilog: Python 3.10+ и три семейства целевой ОС).

**Аутентификация:** сначала `--root-private-key`, иначе пароль (`--root-password` / `ROOT_PASSWORD`).

**`--auto-setup` (по умолчанию):** WireGuard + MTProxy + VPManage, новый пароль root, SSH-порт **2222** (если не задан), публичный IP на сервере для URL при отсутствии домена/ключа домена, генерация `VPM_PASSWORD` при пустом значении.

**`--no-auto-setup`:** явно `--set-wireguard` / `--set-mtproxy` / `--set-vpmanage`. Без `--new-ssh-port` порт SSH не меняется.

**Эффективный хост для URL (домен / IP):**

1. `--domain` (FQDN), если задан  
2. иначе `--domain-client-key` / `DOMAIN_CLIENT_KEY` — HTTP к `DOMAIN_CLIENT_SERVICE_URL` (см. `defaults.py`)  
3. иначе **`--use-public-ip`** или **`--auto-setup`** — опрос публичного IP на сервере  
4. иначе SSH **host**

**Репозиторий vpconnect-configure:** `--vpconfigure-repo-url` (по умолчанию в `defaults.py`).

Пример (расширенный режим, опционально новый SSH-порт):

```sh
python -m vpconnect_install --host 203.0.113.10 --no-auto-setup \
  --root-password-file /secure/root.txt \
  --set-wireguard --set-mtproxy --set-vpmanage \
  --new-ssh-port 2222 --new-root-password-file /secure/new.txt \
  --domain example.com
```

Переменные окружения (опционально): `ROOT_PASSWORD`, `NEW_ROOT_PASSWORD`, `VPM_PASSWORD`, `ROOT_KEY_PASSPHRASE`, `DOMAIN_CLIENT_KEY`.

## GUI

```sh
python -m vpconnect_install gui
```

Строка под заголовком окна напоминает три семейства целевой ОС; подробности — в разделе **«Поддерживаемые версии и платформы»**.

- **Упрощённый** режим: только подключение и URL репозитория; соответствует `auto_setup`.
- **Расширенный:** блоки (подключение на сервере, домен, WireGuard, MTProxy, VPManage) с чекбоксами.

По успеху в лог выводится путь к артефактам и открывается каталог в файловом менеджере.

## Локальные артефакты

`provision-artifacts/<host>-<timestamp>/`:

- `ACCESS.txt` — сводка, SSH, порты, URL  
- `credentials_new_root_password.txt` / `credentials_vpm_password.txt` — при необходимости  
- `id_rsa` / `id_rsa.pub` — RSA-ключ оператора, **2048** бит (публичный добавляется на сервер)

## Сборки для распространения

После сборки рядом с **`vpconnect-install-gui.exe`** создаётся **`dist/readme.txt`** — краткая справка для пользователя exe (Windows x64, три семейства целевой ОС, артефакты, сеть).

**Windows: GUI exe, readme, portable zip** в `dist/`:

```sh
pip install -r requirements-dev.txt
pip install -e .
python packaging/build_distribution.py
```

Только PyInstaller:

```powershell
pip install -r requirements-dev.txt
.\scripts\build_gui_exe.ps1
```

Portable zip: распаковать, выполнить `scripts/install_venv.sh` или `install_venv.bat`, затем `python -m vpconnect_install gui` или CLI.

## Качество кода

```sh
pip install -r requirements-dev.txt
ruff check src tests
ruff format src tests
flake8 src tests
pytest
```

## Настройки по умолчанию

Файл [`src/vpconnect_install/defaults.py`](src/vpconnect_install/defaults.py): URL git VPManage, репозиторий vpconnect-configure, сервис домена, пути на сервере, порты, таймауты, поведение `auto_setup`.

## Тесты

```sh
pip install -r requirements-test.txt
pip install -e .
pytest
```
