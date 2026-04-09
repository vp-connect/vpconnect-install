@echo off
setlocal EnableExtensions
rem Windows CMD: venv + requirements.txt + editable install (repo root = 3 levels up from this file).
cd /d "%~dp0..\..\.."

set "USE_SYS=0"
if /i "%~1"=="--system-python" set "USE_SYS=1"

where python >nul 2>&1 || (echo python not found >&2 & exit /b 1)
python -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" || exit /b 1

if "%USE_SYS%"=="1" (
  python -m pip install --user -U pip
  python -m pip install --user -r requirements.txt
  echo Run from repo root with PYTHONPATH=src, e.g.:
  echo   set PYTHONPATH=src
  echo   python -m vpconnect_install --help
  exit /b 0
)

if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -e .
echo Done. Activate:  .venv\Scripts\activate.bat
echo Then: python -m vpconnect_install --help
exit /b 0
