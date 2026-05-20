$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

. (Join-Path $PSScriptRoot "lib\replay_manifest.ps1")
. (Join-Path $PSScriptRoot "lib\ingestion_manifest.ps1")

$replayScenarios = @(Get-ReplayFixtureScenarios `
    -Root $root `
    -ManifestPath (Join-Path $root "fixtures\manifest.toml"))
$ingestionScenarios = @(Get-IngestionFixtureScenarios `
    -Root $root `
    -ManifestPath (Join-Path $root "fixtures\ingestion\manifest.toml"))

Assert-ManifestPathsExist `
    -Scenarios $replayScenarios `
    -PathPropertyNames @("FixturePath", "ExpectedJsonPath", "ExpectedTextPath") `
    -ManifestLabel "Replay fixture"

Assert-ManifestPathsExist `
    -Scenarios $ingestionScenarios `
    -PathPropertyNames @("FixturePath", "ExpectedReportPath") `
    -ManifestLabel "Ingestion fixture"

$checkedPaths = ($replayScenarios.Count * 3) + ($ingestionScenarios.Count * 2)
Write-Output "Fixture path validation passed. Checked $checkedPaths paths across $($replayScenarios.Count + $ingestionScenarios.Count) scenarios."
