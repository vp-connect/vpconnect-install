@echo off
setlocal EnableExtensions
rem Windows CMD: requirements-dev + editable; optional "build" then args for build_distribution.py
cd /d "%~dp0..\..\.."

set "USE_SYS=0"
:parseopt
if /i "%~1"=="--system-python" (
  set "USE_SYS=1"
  shift
  goto parseopt
)

where python >nul 2>&1 || (echo python not found >&2 & exit /b 1)
python -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" || exit /b 1

if "%USE_SYS%"=="1" goto usersite
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -U pip
python -m pip install -r requirements-dev.txt
python -m pip install -e .
goto afterinstall
:usersite
python -m pip install --user -U pip
python -m pip install --user -r requirements-dev.txt
python -m pip install --user -e .
:afterinstall

if /i "%~1"=="build" (
  shift
  python packaging\build_distribution.py %*
  exit /b %ERRORLEVEL%
)

echo Build environment ready. Full distribution:
echo   scripts\windows\cmd\bootstrap-dist.bat build
exit /b 0
