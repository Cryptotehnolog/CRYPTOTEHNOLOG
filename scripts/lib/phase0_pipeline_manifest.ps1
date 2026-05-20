$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "manifest_utils.ps1")

function Get-Phase0PipelineFixtureScenarios {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,

        [Parameter(Mandatory = $true)]
        [string]$ManifestPath
    )

    $scenarios = @(Read-SimpleScenarioManifest `
        -ManifestPath $ManifestPath `
        -RequiredFields @("name", "fixture", "expected_report") `
        -ManifestLabel "Phase 0 pipeline fixture")

    foreach ($scenario in $scenarios) {
        $scenario | Add-Member -NotePropertyName FixturePath -NotePropertyValue (Join-Path $Root $scenario.fixture)
        $scenario | Add-Member -NotePropertyName ExpectedReportPath -NotePropertyValue (Join-Path $Root $scenario.expected_report)
    }

    Assert-ManifestUniqueValues `
        -Scenarios $scenarios `
        -PathFields @("fixture", "expected_report") `
        -ManifestLabel "Phase 0 pipeline fixture"

    return $scenarios
}
