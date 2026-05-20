$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root "fixtures\phase0_pipeline\manifest.toml"
. (Join-Path $PSScriptRoot "lib\phase0_pipeline_manifest.ps1")

function Normalize-Newlines {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    return $Value.Replace("`r`n", "`n").Trim()
}

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "cargo executable not found. Install Rust toolchain before running Phase 0 pipeline regression."
}

Push-Location $root
try {
    $scenarios = @(Get-Phase0PipelineFixtureScenarios -Root $root -ManifestPath $manifestPath)

    foreach ($scenario in $scenarios) {
        if (-not (Test-Path -LiteralPath $scenario.FixturePath)) {
            throw "Missing Phase 0 pipeline fixture for scenario $($scenario.name): $($scenario.FixturePath)"
        }
        if (-not (Test-Path -LiteralPath $scenario.ExpectedReportPath)) {
            throw "Missing Phase 0 pipeline expected report for scenario $($scenario.name): $($scenario.ExpectedReportPath)"
        }

        $actual = & cargo run --quiet -p cryptotehnolog-ingestion --bin render_phase0_pipeline_report -- $scenario.FixturePath
        if ($LASTEXITCODE -ne 0) {
            throw "render_phase0_pipeline_report failed for scenario $($scenario.name)."
        }

        $expected = Get-Content -LiteralPath $scenario.ExpectedReportPath -Raw

        if ((Normalize-Newlines ($actual -join [Environment]::NewLine)) -ne (Normalize-Newlines $expected)) {
            Write-Output "Phase 0 pipeline regression mismatch for scenario: $($scenario.name)"
            Write-Output "Expected report: $($scenario.expected_report)"
            throw "Phase 0 pipeline regression failed."
        }

        Write-Output "Phase 0 pipeline regression passed for scenario: $($scenario.name)"
    }

    Write-Output "Phase 0 pipeline regression passed for $($scenarios.Count) scenarios."
}
finally {
    Pop-Location
}
