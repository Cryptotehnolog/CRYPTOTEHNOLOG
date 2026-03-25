Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location (Join-Path $repoRoot "dashboard-frontend")

if (Test-Path Env:VITE_DASHBOARD_API_BASE_URL) {
    Remove-Item Env:VITE_DASHBOARD_API_BASE_URL
}

& npm run dev -- --host 127.0.0.1 --port 5173
