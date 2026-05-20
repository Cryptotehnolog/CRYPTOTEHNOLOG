$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root "fixtures\phase0_pipeline\manifest.toml"
. (Join-Path $PSScriptRoot "lib\phase0_pipeline_manifest.ps1")

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "cargo executable not found. Install Rust toolchain before updating Phase 0 pipeline golden report."
}

Push-Location $root
try {
    $scenarios = @(Get-Phase0PipelineFixtureScenarios -Root $root -ManifestPath $manifestPath)

    foreach ($scenario in $scenarios) {
        if (-not (Test-Path -LiteralPath $scenario.FixturePath)) {
            throw "Cannot update Phase 0 pipeline report for missing fixture: $($scenario.FixturePath)"
        }

        $outputDirectory = Split-Path -Parent $scenario.ExpectedReportPath
        if (-not (Test-Path -LiteralPath $outputDirectory)) {
            New-Item -ItemType Directory -Path $outputDirectory | Out-Null
        }

        $reportLines = & cargo run --quiet -p cryptotehnolog-ingestion --bin render_phase0_pipeline_report -- $scenario.FixturePath
        if ($LASTEXITCODE -ne 0) {
            throw "render_phase0_pipeline_report failed for scenario $($scenario.name)."
        }

        $report = $reportLines -join [Environment]::NewLine
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($scenario.ExpectedReportPath, ($report + [Environment]::NewLine), $utf8NoBom)
        Write-Output "Updated $($scenario.expected_report)"
    }
}
finally {
    Pop-Location
}
