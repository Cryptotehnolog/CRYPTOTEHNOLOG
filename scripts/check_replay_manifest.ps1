$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root "fixtures\manifest.toml"
. (Join-Path $PSScriptRoot "lib\replay_manifest.ps1")

$scenarios = @(Get-ReplayFixtureScenarios -Root $root -ManifestPath $manifestPath)

foreach ($scenario in $scenarios) {
    if (-not (Test-Path $scenario.FixturePath)) {
        throw "Replay manifest references missing fixture for scenario $($scenario.name): $($scenario.FixturePath)"
    }
    if (-not (Test-Path $scenario.ExpectedJsonPath)) {
        throw "Replay manifest references missing expected JSON report for scenario $($scenario.name): $($scenario.ExpectedJsonPath)"
    }
    if (-not (Test-Path $scenario.ExpectedTextPath)) {
        throw "Replay manifest references missing expected text report for scenario $($scenario.name): $($scenario.ExpectedTextPath)"
    }
}

Write-Output "Replay manifest validation passed. Checked $($scenarios.Count) scenarios."
