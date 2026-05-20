$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root "fixtures\manifest.toml"

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

        $scenario | Add-Member -NotePropertyName FixturePath -NotePropertyValue (Join-Path $Root $scenario.fixture)
        $scenario | Add-Member -NotePropertyName ExpectedJsonPath -NotePropertyValue (Join-Path $Root $scenario.expected_json)
        $scenario | Add-Member -NotePropertyName ExpectedTextPath -NotePropertyValue (Join-Path $Root $scenario.expected_text)
    }

    return $scenarios
}

Push-Location $root
try {
    $scenarios = @(Get-ReplayFixtureScenarios -Root $root -ManifestPath $manifestPath)

    foreach ($scenario in $scenarios) {
        if (-not (Test-Path $scenario.FixturePath)) {
            throw "Missing replay fixture for scenario $($scenario.name): $($scenario.FixturePath)"
        }
        if (-not (Test-Path $scenario.ExpectedJsonPath)) {
            throw "Missing expected JSON report for scenario $($scenario.name): $($scenario.ExpectedJsonPath)"
        }
        if (-not (Test-Path $scenario.ExpectedTextPath)) {
            throw "Missing expected text report for scenario $($scenario.name): $($scenario.ExpectedTextPath)"
        }

        $actualJson = cargo run -q -p cryptotehnolog-replay -- --format json $scenario.FixturePath
        if ($LASTEXITCODE -ne 0) {
            throw "Replay runner JSON report failed for scenario $($scenario.name)."
        }

        $expectedJson = Get-Content $scenario.ExpectedJsonPath
        $actualJsonText = ($actualJson -join "`n").Trim()
        $expectedJsonText = ($expectedJson -join "`n").Trim()

        if ($actualJsonText -ne $expectedJsonText) {
            Write-Output "Expected replay JSON report for $($scenario.name):"
            Write-Output $expectedJsonText
            Write-Output ""
            Write-Output "Actual replay JSON report for $($scenario.name):"
            Write-Output $actualJsonText
            throw "Replay regression failed: JSON report differs from golden fixture for scenario $($scenario.name)."
        }

        $actualText = cargo run -q -p cryptotehnolog-replay -- --format text $scenario.FixturePath
        if ($LASTEXITCODE -ne 0) {
            throw "Replay runner text report failed for scenario $($scenario.name)."
        }

        $expectedText = Get-Content $scenario.ExpectedTextPath
        $actualTextJoined = ($actualText -join "`n").Trim()
        $expectedTextJoined = ($expectedText -join "`n").Trim()

        if ($actualTextJoined -ne $expectedTextJoined) {
            Write-Output "Expected replay text report for $($scenario.name):"
            Write-Output $expectedTextJoined
            Write-Output ""
            Write-Output "Actual replay text report for $($scenario.name):"
            Write-Output $actualTextJoined
            throw "Replay regression failed: text report differs from golden fixture for scenario $($scenario.name)."
        }

        Write-Output "Replay regression passed for scenario: $($scenario.name)"
    }

    Write-Output "Replay regression passed for $($scenarios.Count) scenarios."
}
finally {
    Pop-Location
}
