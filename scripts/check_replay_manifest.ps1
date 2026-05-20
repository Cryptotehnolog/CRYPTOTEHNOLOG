$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root "fixtures\manifest.toml"
. (Join-Path $PSScriptRoot "lib\replay_manifest.ps1")

$scenarios = @(Get-ReplayFixtureScenarios -Root $root -ManifestPath $manifestPath)

Write-Output "Replay manifest validation passed. Checked $($scenarios.Count) scenarios."
