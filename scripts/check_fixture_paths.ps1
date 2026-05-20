$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

. (Join-Path $PSScriptRoot "lib\replay_manifest.ps1")
. (Join-Path $PSScriptRoot "lib\ingestion_manifest.ps1")
. (Join-Path $PSScriptRoot "lib\phase0_pipeline_manifest.ps1")

$replayScenarios = @(Get-ReplayFixtureScenarios `
    -Root $root `
    -ManifestPath (Join-Path $root "fixtures\manifest.toml"))
$ingestionScenarios = @(Get-IngestionFixtureScenarios `
    -Root $root `
    -ManifestPath (Join-Path $root "fixtures\ingestion\manifest.toml"))
$phase0PipelineScenarios = @(Get-Phase0PipelineFixtureScenarios `
    -Root $root `
    -ManifestPath (Join-Path $root "fixtures\phase0_pipeline\manifest.toml"))

Assert-ManifestPathsExist `
    -Scenarios $replayScenarios `
    -PathPropertyNames @("FixturePath", "ExpectedJsonPath", "ExpectedTextPath") `
    -ManifestLabel "Replay fixture"

Assert-ManifestPathsExist `
    -Scenarios $ingestionScenarios `
    -PathPropertyNames @("FixturePath", "ExpectedReportPath") `
    -ManifestLabel "Ingestion fixture"

Assert-ManifestPathsExist `
    -Scenarios $phase0PipelineScenarios `
    -PathPropertyNames @("FixturePath", "ExpectedReportPath") `
    -ManifestLabel "Phase 0 pipeline fixture"

$checkedPaths = ($replayScenarios.Count * 3) + ($ingestionScenarios.Count * 2) + ($phase0PipelineScenarios.Count * 2)
$scenarioCount = $replayScenarios.Count + $ingestionScenarios.Count + $phase0PipelineScenarios.Count
Write-Output "Fixture path validation passed. Checked $checkedPaths paths across $scenarioCount scenarios."
