$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root "fixtures\manifest.toml"

function Normalize-Newlines {
    param([string]$Value)

    return $Value.Replace("`r`n", "`n")
}

function Get-ReplayFixtureScenarios {
    param(
        [string]$Root,
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

        $scenario | Add-Member -NotePropertyName ExpectedJsonPath -NotePropertyValue (Join-Path $Root $scenario.expected_json)
        $scenario | Add-Member -NotePropertyName ExpectedTextPath -NotePropertyValue (Join-Path $Root $scenario.expected_text)
    }

    return $scenarios
}

Push-Location $root
try {
    $scenarios = @(Get-ReplayFixtureScenarios -Root $root -ManifestPath $manifestPath)
    $before = @{}

    foreach ($scenario in $scenarios) {
        if (-not (Test-Path $scenario.ExpectedTextPath)) {
            throw "Missing golden text fixture for scenario $($scenario.name): $($scenario.ExpectedTextPath)"
        }
        if (-not (Test-Path $scenario.ExpectedJsonPath)) {
            throw "Missing golden JSON fixture for scenario $($scenario.name): $($scenario.ExpectedJsonPath)"
        }

        $before[$scenario.ExpectedTextPath] = Normalize-Newlines (Get-Content $scenario.ExpectedTextPath -Raw)
        $before[$scenario.ExpectedJsonPath] = Normalize-Newlines (Get-Content $scenario.ExpectedJsonPath -Raw)
    }

    .\scripts\update_golden_fixture.ps1

    foreach ($scenario in $scenarios) {
        $afterText = Normalize-Newlines (Get-Content $scenario.ExpectedTextPath -Raw)
        $afterJson = Normalize-Newlines (Get-Content $scenario.ExpectedJsonPath -Raw)

        if ($before[$scenario.ExpectedTextPath] -ne $afterText -or $before[$scenario.ExpectedJsonPath] -ne $afterJson) {
            Write-Output "Golden fixtures are stale for scenario $($scenario.name). Run scripts\update_golden_fixture.ps1 and review the diff."
            throw "Golden fixture check failed."
        }
    }

    Write-Output "Golden fixture is current."
}
finally {
    Pop-Location
}
