# Windows PowerShell: venv + requirements.txt + editable install.
# If args include "build" (after any --system-python), delegates to bootstrap-dist.ps1.
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
Set-Location $RepoRoot

$i = 0
while ($i -lt $args.Count -and $args[$i] -eq "--system-python") { $i++ }
if ($i -lt $args.Count -and $args[$i] -eq "build") {
    $dist = Join-Path $PSScriptRoot "bootstrap-dist.ps1"
    & $dist @args
    exit $LASTEXITCODE
}

$SystemPython = $false
$extra = [System.Collections.ArrayList]@()
foreach ($a in $args) {
    if ($a -eq "--system-python") { $SystemPython = $true }
    else { [void]$extra.Add($a) }
}
if ($extra.Count -gt 0) {
    Write-Error "Unknown arguments: $($extra -join ' '). Only --system-python is supported, or use .\scripts\windows\ps\bootstrap-dist.ps1 build"
}

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { throw "python not found in PATH" }
& python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"

if ($SystemPython) {
    python -m pip install --user -U pip
    python -m pip install --user -r requirements.txt
    Write-Host "Run from repo root with PYTHONPATH=src, e.g.:"
    Write-Host "  `$env:PYTHONPATH='src'; python -m vpconnect_install --help"
    exit 0
}

if (-not (Test-Path .venv)) { python -m venv .venv }
$venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
& $venvPy -m pip install -U pip
& $venvPy -m pip install -r requirements.txt
& $venvPy -m pip install -e .
Write-Host "Done. Use: .\.venv\Scripts\python.exe -m vpconnect_install --help"
Write-Host "Or activate: .\.venv\Scripts\Activate.ps1"
