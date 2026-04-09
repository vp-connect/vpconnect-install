# vpconnect-install

Инструмент на **Python 3.10+** для настройки сервера по **SSH**: скачивает и выполняет скрипты **[vpconnect-configure](https://github.com/vp-connect/vpconnect-configure)** (этапы **00–03** в `$HOME` на сервере, **03** клонирует репозиторий), затем по пути из вывода **03** запускает **04–08** (доступ, домен, WireGuard, MTProxy, VPManage). После успешного завершения шагов запрашивается **перезагрузка** сервера (ожидание SSH — best-effort). Точки входа: **CLI** (`python -m vpconnect_install`), **GUI** (`python -m vpconnect_install gui`, Tkinter), опционально **сборка PyInstaller** (см. раздел про `dist/`).

> **Риск.** Смена SSH-порта, firewall или паролей может отрезать доступ. Держите **консоль** провайдера и тестируйте на одноразовой VM. Режима «только посмотреть» нет: выполняются реальные команды на сервере.

## Поддерживаемые версии и платформы

### Машина оператора (CLI и GUI из исходников)

- **Python** ≥ **3.10** (см. `requires-python` в `pyproject.toml`).
- **ОС:** **Windows** 10/11, **Linux**, **macOS** — везде, где доступны зависимости (`paramiko`, `cryptography`, `requests`) и стандартный **Tkinter** (для GUI; на минимальных установках Linux может понадобиться пакет `python3-tk`).
- Сеть: SSH до сервера, **GitHub** `raw.githubusercontent.com` (скрипты **00–03**), клонирование репозитория по `--vpconfigure-repo-url`.

Корневые **`./bootstrap.sh`** и **`./bootstrap-dist.sh`** определяют ОС и вызывают скрипт из [`scripts/`](scripts/README.md) (Linux / macOS / Windows **CMD**). На Windows из **PowerShell** удобнее сразу `scripts\windows\ps\*.ps1`. Ручная установка Python и venv тоже возможна.

### Сборка GUI (дистрибутив)

- **Готовый `.exe` для операторов без Python** получается при запуске `packaging/build_distribution.py` (или `bootstrap-dist … build`) на **64-bit Windows 10+**; отдельный Python для запуска exe не нужен.
- На **Linux/macOS** тот же скрипт может собрать замороженный бинарник **`vpconnect-install-gui`** (без расширения `.exe`) и всё равно положить в **`dist/`** portable zip и **`readme.txt`** — смысл zip тот же; **Windows exe** для раздачи коллегам на Windows собирайте на Windows.
- Артефакты прогона установщика пишутся в **`provision-artifacts/…`** относительно **текущего рабочего каталога** (откуда запущены CLI/GUI/exe).

### Целевой сервер (скрипты vpconnect-configure)

На стороне сервера поддержка версий ОС задаётся скриптами **vpconnect-configure** (после `01_getosversion.sh` используется одно из **трёх семейств** — имя ветки `VPCONFIGURE_GIT_BRANCH`):

| Семейство | Суть | Примеры |
|-----------|------|---------|
| **debian** | `apt` | Debian 12–13, Ubuntu 22.04 / 24.04 / 26.04 и производные (Linux Mint, Raspberry Pi OS и т.д.) |
| **centos** | `dnf` / `yum` | RHEL 8–10, AlmaLinux, Rocky Linux, Oracle Linux, Fedora 39+, Amazon Linux 2023+ и аналоги |
| **freebsd** | пакеты FreeBSD | FreeBSD 13–14 |

Точный список релизов, производных и явных исключений — в [README vpconnect-configure](https://github.com/vp-connect/vpconnect-configure/blob/main/README.md) (в репозитории рядом: `vpconnect-configure/README.md`).

## Как устроен прогон

1. **Локально** (до SSH): создаётся каталог артефактов `provision-artifacts/<host>-<timestamp>/`, проверяется право записи; при **`--auto-setup`** дополнительно генерируется пара RSA-ключей оператора (для шага **04**).
2. **SSH** как root (ключ или пароль).
3. **Bootstrap** (`configure_bootstrap.py`): для каждого из `00_bashinstall.sh` … `03_getconfigure.sh` — загрузка с GitHub (raw), запуск в домашнем каталоге на сервере.
4. **03** клонирует **vpconnect-configure**; из stdout извлекается `path:` — каталог установки скриптов **04–08**.
5. **Провижининг** (`vpconfigure_provision.py`): при необходимости **04** (настройка доступа), затем **05–08** (WireGuard, MTProxy, VPManage — по флагам конфигурации).
6. **Локально**: `ACCESS.txt`, файлы с паролями при необходимости; при **`auto_setup`** — также сгенерированные **`id_rsa`** / **`id_rsa.pub`** в каталоге артефактов.
7. **Перезагрузка** сервера по SSH (после успеха), затем краткое ожидание доступности SSH.

Версия пакета и ветка raw для **00–03** задаются в `vpconnect_install/defaults.py` (`VPCONFIGURE_RAW_GIT_BRANCH` и URL репозитория).

## Быстрый старт

**Linux / macOS / Git Bash (Windows):**

```sh
./bootstrap.sh
. .venv/bin/activate   # macOS: source .venv/bin/activate
python -m vpconnect_install --help
```

**Windows CMD** (из корня репозитория):

```bat
scripts\windows\cmd\bootstrap.bat
.venv\Scripts\activate.bat
python -m vpconnect_install --help
```

**Windows PowerShell:**

```powershell
.\scripts\windows\ps\bootstrap.ps1
.\.venv\Scripts\python.exe -m vpconnect_install --help
```

Подробнее о каталогах `scripts/` — [scripts/README.md](scripts/README.md).

## CLI

Кратко о платформах см. в конце вывода **`python -m vpconnect_install --help`** (epilog: Python 3.10+ и три семейства целевой ОС).

**Аутентификация:** сначала `--root-private-key`, иначе пароль (`--root-password` / `ROOT_PASSWORD`).

**`--auto-setup` (по умолчанию):** WireGuard + MTProxy + VPManage, новый пароль root, SSH-порт **2222** (если не задан), публичный IP на сервере для URL при отсутствии явного домена, генерация `VPM_PASSWORD` при пустом значении.

**`--no-auto-setup`:** явно `--set-wireguard` / `--set-mtproxy` / `--set-vpmanage`. Без `--new-ssh-port` порт SSH не меняется.  
Файервол на сервере (ufw) включается опционально флагом **`--enable-firewall`** (шаг `04_setsystemaccess.sh`).

**Эффективный хост для URL (домен / IP):**

1. `--domain` (FQDN), если задан  
2. иначе **`--use-public-ip`** или **`--auto-setup`** — опрос публичного IP на сервере  
3. иначе SSH **host**

**Репозиторий vpconnect-configure:** `--vpconfigure-repo-url` (по умолчанию в `defaults.py`).

Флаги отдельных сценариев на сервере (например, **`07_setmtproxy.sh`**: опциональный **`--mtproxy-secret`** для hex-секрета MTProxy) описаны в [README vpconnect-configure](https://github.com/vp-connect/vpconnect-configure/blob/main/README.md).

Пример (расширенный режим, опционально новый SSH-порт):

```sh
python -m vpconnect_install --host 203.0.113.10 --no-auto-setup \
  --root-password-file /secure/root.txt \
  --set-wireguard --set-mtproxy --set-vpmanage \
  --new-ssh-port 2222 --new-root-password-file /secure/new.txt \
  --domain example.com
```

Переменные окружения (опционально): `ROOT_PASSWORD`, `NEW_ROOT_PASSWORD`, `VPM_PASSWORD`, `ROOT_KEY_PASSPHRASE`.

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
- при **упрощённом режиме** (`auto_setup`): `id_rsa` / `id_rsa.pub` — RSA-ключ оператора, **2048** бит (публичный добавляется на сервер в **04**)

## Сборки для распространения

В каталоге **`dist/`** после полного прогона **`packaging/build_distribution.py`** обычно появляются:

| Артефакт | Описание |
|----------|----------|
| **`vpconnect-install-gui.exe`** | Только при сборке на **Windows** (PyInstaller). |
| **`vpconnect-install-gui`** | При сборке PyInstaller на **Linux/macOS** (имя без `.exe`). |
| **`vpconnect-install-portable.zip`** | Исходники, `scripts/`, корневые `bootstrap*.sh`, `packaging/` — для запуска из исходников на любой поддерживаемой ОС. |
| **`readme.txt`** | Краткая справка **на английском**; **текст зависит от ОС, на которой запускали `build_distribution.py`** (Windows / macOS / Linux), и от флага **`--skip-pyinstaller`**. |

**Подготовка и полная сборка** (аналог **Build full distribution** в IDE — `.run/Build full distribution.run.xml`):

- Linux / macOS / Git Bash: `./bootstrap-dist.sh build`
- Windows CMD: `scripts\windows\cmd\bootstrap-dist.bat build`
- Windows PowerShell: `.\scripts\windows\ps\bootstrap-dist.ps1 build`

После слова **`build`** можно передать аргументы **`packaging/build_distribution.py`** (например `build --skip-pyinstaller`).

Только подготовить окружение для сборки (без PyInstaller): те же команды **без** аргумента `build`.

Пересобрать **только** `readme.txt` и zip **без** PyInstaller:

```sh
python packaging/build_distribution.py --skip-pyinstaller
```

Флаг **`--system-python`** в sh/bat/ps1: ставить зависимости в user site-packages без venv.

**Вручную** (полный цикл в уже активированном venv):

```sh
pip install -r requirements-dev.txt
pip install -e .
python packaging/build_distribution.py
```

Только PyInstaller (если dev-зависимости уже стоят):

```text
python -m PyInstaller --noconfirm --distpath dist --workpath build packaging/vpconnect-install-gui.spec
```

**Portable zip:** распаковать, выполнить **bootstrap** для своей ОС (`scripts/linux`, `scripts/macos`, `scripts/windows/cmd` или `ps`, либо корневой `./bootstrap.sh` на Unix/Git Bash), затем `python -m vpconnect_install gui` или CLI. Подробнее — [scripts/README.md](scripts/README.md).

## Качество кода

```sh
pip install -r requirements-dev.txt
ruff check src tests
ruff format src tests
flake8 src tests
pytest
```

## Настройки по умолчанию

Файл [`src/vpconnect_install/defaults.py`](src/vpconnect_install/defaults.py): таймауты SSH и ожидания после перезагрузки, порты WireGuard / MTProxy / VPManage, пути к артефактам WG на сервере, размер RSA-ключа оператора (бит), длина генерируемых секретов, URL репозитория **vpconnect-configure** и ветка **`VPCONFIGURE_RAW_GIT_BRANCH`** для raw **00–03**.

## Тесты

```sh
pip install -r requirements-test.txt
pip install -e .
pytest
```
