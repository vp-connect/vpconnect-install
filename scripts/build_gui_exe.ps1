# Build windowed GUI exe with PyInstaller. Run from repository root in PowerShell.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $Root

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    & $venvPython -m pip install -q -r requirements-dev.txt
    & $venvPython -m pip install -q -e .
    & $venvPython -m PyInstaller --noconfirm packaging\vpconnect-install-gui.spec
}
else {
    python -m pip install -q -r requirements-dev.txt
    python -m pip install -q -e .
    python -m PyInstaller --noconfirm packaging\vpconnect-install-gui.spec
}

Write-Host "Output: $Root\dist\vpconnect-install-gui.exe"
