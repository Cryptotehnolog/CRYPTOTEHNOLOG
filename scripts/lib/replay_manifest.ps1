$ErrorActionPreference = "Stop"

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

    if (-not (Test-Path $ManifestPath)) {
        throw "Missing replay fixture manifest: $ManifestPath"
    }

    $scenarios = @()
    $current = [ordered]@{}

    foreach ($line in Get-Content $ManifestPath) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith("#")) {
            continue
        }

        if ($trimmed -eq "[[scenario]]") {
            if ($current.Count -gt 0) {
                $scenarios += [pscustomobject]$current
                $current = [ordered]@{}
            }
            continue
        }

        if ($trimmed -match '^([A-Za-z_]+)\s*=\s*"([^"]*)"\s*$') {
            $current[$matches[1]] = $matches[2]
            continue
        }

        throw "Unsupported replay manifest line: $line"
    }

    if ($current.Count -gt 0) {
        $scenarios += [pscustomobject]$current
    }

    if ($scenarios.Count -eq 0) {
        throw "Replay fixture manifest contains no scenarios."
    }

    foreach ($scenario in $scenarios) {
        foreach ($field in @("name", "fixture", "expected_json", "expected_text")) {
            if (-not $scenario.PSObject.Properties[$field]) {
                throw "Replay fixture scenario is missing required field: $field"
            }
        }

        $scenario | Add-Member -NotePropertyName FixturePath -NotePropertyValue (Join-Path $Root $scenario.fixture)
        $scenario | Add-Member -NotePropertyName ExpectedJsonPath -NotePropertyValue (Join-Path $Root $scenario.expected_json)
        $scenario | Add-Member -NotePropertyName ExpectedTextPath -NotePropertyValue (Join-Path $Root $scenario.expected_text)
    }

    return $scenarios
}
