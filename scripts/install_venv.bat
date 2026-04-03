@echo off
setlocal
cd /d "%~dp0\.."
py -3 -m venv .venv
if errorlevel 1 python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -e .
echo.
echo CLI:  python -m vpconnect_install --help
echo GUI:  python -m vpconnect_install gui
