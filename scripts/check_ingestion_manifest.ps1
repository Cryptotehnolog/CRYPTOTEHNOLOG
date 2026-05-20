$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root "fixtures\ingestion\manifest.toml"
. (Join-Path $PSScriptRoot "lib\ingestion_manifest.ps1")

$scenarios = @(Get-IngestionFixtureScenarios -Root $root -ManifestPath $manifestPath)

foreach ($scenario in $scenarios) {
    if (-not (Test-Path $scenario.FixturePath)) {
        throw "Ingestion manifest references missing fixture for scenario $($scenario.name): $($scenario.FixturePath)"
    }
}

Write-Output "Ingestion manifest validation passed. Checked $($scenarios.Count) scenarios."
