$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$fixturePath = Join-Path $root "fixtures\ingestion\happy_path_batches.psv"
$expectedReportPath = Join-Path $root "fixtures\phase0_pipeline\golden_report.json"

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "cargo executable not found. Install Rust toolchain before updating Phase 0 pipeline golden report."
}

if (-not (Test-Path -LiteralPath $fixturePath)) {
    throw "Phase 0 pipeline fixture not found: $fixturePath"
}

$outputDirectory = Split-Path -Parent $expectedReportPath
if (-not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory | Out-Null
}

Push-Location $root
try {
    $reportLines = & cargo run --quiet -p cryptotehnolog-ingestion --bin render_phase0_pipeline_report -- $fixturePath
    if ($LASTEXITCODE -ne 0) {
        throw "render_phase0_pipeline_report failed."
    }

    $report = $reportLines -join [Environment]::NewLine
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($expectedReportPath, ($report + [Environment]::NewLine), $utf8NoBom)
    Write-Output "Updated fixtures/phase0_pipeline/golden_report.json"
}
finally {
    Pop-Location
}
