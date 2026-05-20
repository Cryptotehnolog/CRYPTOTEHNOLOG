$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root "fixtures\ingestion\manifest.toml"
. (Join-Path $PSScriptRoot "lib\ingestion_manifest.ps1")

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "cargo executable not found. Install Rust toolchain before updating ingestion golden reports."
}

$scenarios = @(Get-IngestionFixtureScenarios -Root $root -ManifestPath $manifestPath)

Push-Location $root
try {
    foreach ($scenario in $scenarios) {
        if (-not (Test-Path $scenario.FixturePath)) {
            throw "Cannot update ingestion report for missing fixture: $($scenario.FixturePath)"
        }

        $outputDirectory = Split-Path -Parent $scenario.ExpectedReportPath
        if (-not (Test-Path $outputDirectory)) {
            New-Item -ItemType Directory -Path $outputDirectory | Out-Null
        }

        $report = & cargo run --quiet -p cryptotehnolog-ingestion --bin render_ingestion_report -- $scenario.FixturePath
        if ($LASTEXITCODE -ne 0) {
            throw "render_ingestion_report failed for scenario $($scenario.name)."
        }

        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($scenario.ExpectedReportPath, ($report + [Environment]::NewLine), $utf8NoBom)
        Write-Output "Updated $($scenario.expected_report)"
    }
}
finally {
    Pop-Location
}
