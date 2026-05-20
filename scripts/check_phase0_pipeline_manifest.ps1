$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root "fixtures\phase0_pipeline\manifest.toml"
. (Join-Path $PSScriptRoot "lib\phase0_pipeline_manifest.ps1")

$scenarios = @(Get-Phase0PipelineFixtureScenarios -Root $root -ManifestPath $manifestPath)

Assert-ManifestPathsExist `
    -Scenarios $scenarios `
    -PathPropertyNames @("FixturePath", "ExpectedReportPath") `
    -ManifestLabel "Phase 0 pipeline fixture"

Write-Output "Phase 0 pipeline manifest validation passed. Checked $($scenarios.Count) scenarios."
