# Windows PowerShell: requirements-dev + editable; optional: build [args for build_distribution.py]
# Syntax: [--system-python] [build [args passed to build_distribution.py...]]
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
Set-Location $RepoRoot

$SystemPython = $false
$i = 0
while ($i -lt $args.Count -and $args[$i] -eq "--system-python") {
    $SystemPython = $true
    $i++
}

$wantBuild = $false
$buildArgs = @()
if ($i -lt $args.Count) {
    if ($args[$i] -ne "build") {
        throw "Unexpected argument '$($args[$i])'. Use: [--system-python] [build [args...]]"
    }
    $wantBuild = $true
    $i++
    if ($i -lt $args.Count) {
        $buildArgs = @($args[$i..($args.Count - 1)])
    }
}

$null = Get-Command python -ErrorAction Stop
& python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"

if ($SystemPython) {
    python -m pip install --user -U pip
    python -m pip install --user -r requirements-dev.txt
    python -m pip install --user -e .
    $runPy = "python"
}
else {
    if (-not (Test-Path .venv)) { python -m venv .venv }
    $venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    & $venvPy -m pip install -U pip
    & $venvPy -m pip install -r requirements-dev.txt
    & $venvPy -m pip install -e .
    $runPy = $venvPy
}

if ($wantBuild) {
    if ($buildArgs.Count -eq 0) {
        & $runPy packaging\build_distribution.py
    }
    else {
        & $runPy packaging\build_distribution.py @buildArgs
    }
    exit $LASTEXITCODE
}

Write-Host "Build environment ready. Full distribution:"
Write-Host "  .\scripts\windows\ps\bootstrap-dist.ps1 build"
