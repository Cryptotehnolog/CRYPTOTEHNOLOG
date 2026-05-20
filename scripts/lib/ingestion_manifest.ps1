$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "manifest_utils.ps1")

function Get-IngestionFixtureScenarios {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,

        [Parameter(Mandatory = $true)]
        [string]$ManifestPath
    )

    $scenarios = @(Read-SimpleScenarioManifest `
        -ManifestPath $ManifestPath `
        -RequiredFields @("name", "fixture", "expected_observations", "expected_raw_events", "expected_normalized_events", "expected_validation_errors") `
        -IntegerFields @("expected_observations", "expected_raw_events", "expected_normalized_events", "expected_validation_errors") `
        -ManifestLabel "Ingestion fixture")

    foreach ($scenario in $scenarios) {
        $scenario | Add-Member -NotePropertyName FixturePath -NotePropertyValue (Join-Path $Root $scenario.fixture)
    }

    Assert-ManifestUniqueValues `
        -Scenarios $scenarios `
        -PathFields @("fixture") `
        -ManifestLabel "Ingestion fixture"

    return $scenarios
}
