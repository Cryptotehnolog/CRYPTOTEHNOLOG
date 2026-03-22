Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repoRoot

$env:PYTHONPATH = "src"

& ".venv\Scripts\python.exe" -m cryptotechnolog.dashboard
