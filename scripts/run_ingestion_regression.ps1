$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root "fixtures\ingestion\manifest.toml"
. (Join-Path $PSScriptRoot "lib\ingestion_manifest.ps1")

function Normalize-Newlines {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    return $Value.Replace("`r`n", "`n").Trim()
}

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "cargo executable not found. Install Rust toolchain before running ingestion regression."
}

Push-Location $root
try {
    $scenarios = @(Get-IngestionFixtureScenarios -Root $root -ManifestPath $manifestPath)

    foreach ($scenario in $scenarios) {
        if (-not (Test-Path $scenario.FixturePath)) {
            throw "Missing ingestion fixture for scenario $($scenario.name): $($scenario.FixturePath)"
        }
        if (-not (Test-Path $scenario.ExpectedReportPath)) {
            throw "Missing ingestion expected report for scenario $($scenario.name): $($scenario.ExpectedReportPath)"
        }

        $actual = & cargo run --quiet -p cryptotehnolog-ingestion --bin render_ingestion_report -- $scenario.FixturePath
        if ($LASTEXITCODE -ne 0) {
            throw "render_ingestion_report failed for scenario $($scenario.name)."
        }

        $expected = Get-Content $scenario.ExpectedReportPath -Raw

        if ((Normalize-Newlines $actual) -ne (Normalize-Newlines $expected)) {
            Write-Output "Ingestion regression mismatch for scenario: $($scenario.name)"
            Write-Output "Expected report: $($scenario.expected_report)"
            throw "Ingestion regression failed."
        }

        Write-Output "Ingestion regression passed for scenario: $($scenario.name)"
    }

    Write-Output "Ingestion regression passed for $($scenarios.Count) scenarios."
}
finally {
    Pop-Location
}
