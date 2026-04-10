# Скрипты окружения и сборки

Все пути ниже — от **корня репозитория** `vpconnect-install`.

## Корневые диспетчеры

| Файл | Назначение |
|------|------------|
| `bootstrap.sh` | Определяет ОС (`uname`) и запускает Linux / macOS / Windows (CMD) скрипт подготовки venv. |
| `bootstrap-dist.sh` | То же для сборки дистрибутива (dev-зависимости и опционально `packaging/build_distribution.py`). |

На **Windows** из **Git Bash** / **MSYS** корневые `*.sh` вызывают `scripts/windows/cmd/*.bat`.

## Каталоги по ОС

### `linux/`

| Скрипт | Действие |
|--------|----------|
| `bootstrap.sh` | `.venv`, `requirements.txt`, `pip install -e .`. Если среди аргументов есть `build`, вызывается `bootstrap-dist.sh` (сборка `dist/`). |
| `bootstrap-dist.sh` | `requirements-dev.txt`, опционально аргумент `build` и далее аргументы для `build_distribution.py` |

Флаг `--system-python` — установка в user site-packages без venv.

### `macos/`

Те же сценарии, что в `linux/` (активация: `source .venv/bin/activate`).

### `windows/cmd/`

Запуск из **cmd.exe**:

```bat
scripts\windows\cmd\bootstrap.bat
scripts\windows\cmd\bootstrap-dist.bat build
rem Эквивалентно полной сборке:
scripts\windows\cmd\bootstrap.bat build
```

В **CMD** после `shift` переменная `%*` по-прежнему содержит исходные аргументы, поэтому `bootstrap-dist.bat` собирает хвост после `build` отдельно (в отличие от `sh`/`PowerShell`).

### `windows/ps/`

Запуск из **PowerShell**:

```powershell
.\scripts\windows\ps\bootstrap.ps1
.\scripts\windows\ps\bootstrap-dist.ps1 build
# То же, что dist-сборка:
.\scripts\windows\ps\bootstrap.ps1 build
```

## Portable zip

В архив попадают каталоги `scripts/linux`, `scripts/macos`, `scripts/windows`, корневые `bootstrap.sh` / `bootstrap-dist.sh` и исходники. После распаковки используйте bootstrap для своей ОС, затем `python -m vpconnect_install …`.
