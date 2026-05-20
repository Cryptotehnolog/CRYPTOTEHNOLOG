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

    Write-Output "== Compliance check =="
    .\scripts\check_compliance.ps1

    Write-Output "== Phase gate check =="
    .\scripts\check_phase_gate.ps1

    Write-Output "== Rust formatting check =="
    cargo fmt --check
    if ($LASTEXITCODE -ne 0) { throw "cargo fmt --check failed." }

    Write-Output "== Rust workspace check =="
    cargo check
    if ($LASTEXITCODE -ne 0) { throw "cargo check failed." }

    Write-Output "== Rust tests =="
    cargo test
    if ($LASTEXITCODE -ne 0) { throw "cargo test failed." }

    Write-Output "== Replay regression =="
    .\scripts\run_replay_regression.ps1

    Write-Output "All local checks passed."
}
finally {
    Pop-Location
}
