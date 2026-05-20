$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root "fixtures\ingestion\manifest.toml"
. (Join-Path $PSScriptRoot "lib\ingestion_manifest.ps1")

$scenarios = @(Get-IngestionFixtureScenarios -Root $root -ManifestPath $manifestPath)

Write-Output "Ingestion manifest validation passed. Checked $($scenarios.Count) scenarios."
