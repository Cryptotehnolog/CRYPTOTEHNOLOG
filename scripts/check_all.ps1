$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

Push-Location $root
try {
    Write-Output "== Knowledge base health check =="
    .\scripts\kb_health_check.ps1

    Write-Output "== Local Markdown link check =="
    .\scripts\validate_local_links.ps1

    Write-Output "== Knowledge stale check (warning-only) =="
    .\scripts\kb_stale_check.ps1

    Write-Output "== Rust formatting check =="
    cargo fmt --check

    Write-Output "== Rust workspace check =="
    cargo check

    Write-Output "== Rust tests =="
    cargo test

    Write-Output "All local checks passed."
}
finally {
    Pop-Location
}
