param(
    [string]$FixturePath = "fixtures\ingestion\happy_path_batches.psv",
    [string]$OutputPath = "artifacts\phase0_pipeline_report.json"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$fixtureFullPath = Join-Path $root $FixturePath
$outputFullPath = Join-Path $root $OutputPath
$outputDir = Split-Path -Parent $outputFullPath

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "cargo executable not found. Install Rust toolchain before running Phase 0 pipeline report."
}

if (-not (Test-Path -LiteralPath $fixtureFullPath)) {
    throw "Phase 0 pipeline fixture not found: $fixtureFullPath"
}

if (-not (Test-Path -LiteralPath $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

Push-Location $root
try {
    $report = & cargo run --quiet -p cryptotehnolog-ingestion --bin render_phase0_pipeline_report -- $fixtureFullPath
    if ($LASTEXITCODE -ne 0) {
        throw "render_phase0_pipeline_report failed."
    }

    $report | Set-Content -LiteralPath $outputFullPath -Encoding UTF8
    Write-Output "Phase 0 pipeline report written: $outputFullPath"
}
finally {
    Pop-Location
}
