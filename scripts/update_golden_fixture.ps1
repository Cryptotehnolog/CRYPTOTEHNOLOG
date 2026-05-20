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

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "cargo executable was not found in PATH."
}

Push-Location $root
try {
    $scenarios = @(Get-ReplayFixtureScenarios -Root $root -ManifestPath $manifestPath)

    foreach ($scenario in $scenarios) {
        if (-not (Test-Path $scenario.FixturePath)) {
            throw "Missing replay fixture for scenario $($scenario.name): $($scenario.FixturePath)"
        }

        $expectedTextDir = Split-Path -Parent $scenario.ExpectedTextPath
        $expectedJsonDir = Split-Path -Parent $scenario.ExpectedJsonPath
        if (-not (Test-Path $expectedTextDir)) {
            throw "Missing golden text fixture directory for scenario $($scenario.name): $expectedTextDir"
        }
        if (-not (Test-Path $expectedJsonDir)) {
            throw "Missing golden JSON fixture directory for scenario $($scenario.name): $expectedJsonDir"
        }

        $textReport = cargo run -q -p cryptotehnolog-replay -- --format text $scenario.FixturePath
        if ($LASTEXITCODE -ne 0) {
            throw "Replay runner text report failed for scenario $($scenario.name)."
        }

        $jsonReport = cargo run -q -p cryptotehnolog-replay -- --format json $scenario.FixturePath
        if ($LASTEXITCODE -ne 0) {
            throw "Replay runner JSON report failed for scenario $($scenario.name)."
        }

        $textContent = ($textReport -join "`n").Trim() + "`n"
        $jsonContent = ($jsonReport -join "`n").Trim() + "`n"

        Set-Content -Path $scenario.ExpectedTextPath -Value $textContent -NoNewline -Encoding ascii
        Set-Content -Path $scenario.ExpectedJsonPath -Value $jsonContent -NoNewline -Encoding ascii

        Write-Output "Updated $($scenario.expected_text)"
        Write-Output "Updated $($scenario.expected_json)"
    }
}
finally {
    Pop-Location
}
