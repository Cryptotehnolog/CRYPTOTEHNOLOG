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

    Write-Output "== Replay manifest check =="
    .\scripts\check_replay_manifest.ps1

    Write-Output "== Ingestion manifest check =="
    .\scripts\check_ingestion_manifest.ps1

    Write-Output "== Phase 0 pipeline manifest check =="
    .\scripts\check_phase0_pipeline_manifest.ps1

    Write-Output "== Fixture path check =="
    .\scripts\check_fixture_paths.ps1

    Write-Output "== Pricing model fixture policy check =="
    .\scripts\check_pricing_model_fixture_update.ps1

    Write-Output "== Manual JSON writer check =="
    .\scripts\check_manual_json_writers.ps1

    Write-Output "== Midpoint false-positive report check =="
    .\scripts\check_midpoint_false_positive_report.ps1

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

    Write-Output "== Ingestion regression =="
    .\scripts\run_ingestion_regression.ps1

    Write-Output "== Phase 0 pipeline regression =="
    .\scripts\run_phase0_pipeline_regression.ps1

    Write-Output "== Golden fixture freshness =="
    .\scripts\check_golden_fixture_current.ps1

    Write-Output "== Ingestion golden report freshness =="
    .\scripts\check_ingestion_golden_current.ps1

    Write-Output "== Phase 0 pipeline golden report freshness =="
    .\scripts\check_phase0_pipeline_golden_current.ps1

    Write-Output "All local checks passed."
}
finally {
    Pop-Location
}
