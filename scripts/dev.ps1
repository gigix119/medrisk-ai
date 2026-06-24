# Convenience launcher for local development on Windows (PowerShell).
# Prints every command it runs - nothing here is hidden magic.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Virtual environment not found at .venv. Create it first:"
    Write-Host "  py -3.12 -m venv .venv"
    Write-Host "  .venv\Scripts\python.exe -m pip install -r requirements-dev.txt"
    exit 1
}

Write-Host "Running: $venvPython -m uvicorn app.main:app --reload"
& $venvPython -m uvicorn app.main:app --reload
