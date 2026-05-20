$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "manifest_utils.ps1")

function Normalize-Newlines {
    param([string]$Value)

    return $Value.Replace("`r`n", "`n")
}

function Get-ReplayFixtureScenarios {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,

        [Parameter(Mandatory = $true)]
        [string]$ManifestPath
    )

    $scenarios = @(Read-SimpleScenarioManifest `
        -ManifestPath $ManifestPath `
        -RequiredFields @("name", "fixture", "expected_json", "expected_text") `
        -ManifestLabel "Replay fixture")

    foreach ($scenario in $scenarios) {
        $scenario | Add-Member -NotePropertyName FixturePath -NotePropertyValue (Join-Path $Root $scenario.fixture)
        $scenario | Add-Member -NotePropertyName ExpectedJsonPath -NotePropertyValue (Join-Path $Root $scenario.expected_json)
        $scenario | Add-Member -NotePropertyName ExpectedTextPath -NotePropertyValue (Join-Path $Root $scenario.expected_text)
    }

    Assert-ManifestUniqueValues `
        -Scenarios $scenarios `
        -PathFields @("fixture", "expected_json", "expected_text") `
        -ManifestLabel "Replay fixture"

    return $scenarios
}
