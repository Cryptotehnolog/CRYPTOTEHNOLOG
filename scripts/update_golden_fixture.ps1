$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root "fixtures\manifest.toml"
. (Join-Path $PSScriptRoot "lib\replay_manifest.ps1")

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
