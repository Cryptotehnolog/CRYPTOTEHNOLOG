Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location (Join-Path $repoRoot "dashboard-frontend")

$env:VITE_DASHBOARD_API_BASE_URL = "http://127.0.0.1:8000"

& npm run dev -- --host 127.0.0.1 --port 5173
