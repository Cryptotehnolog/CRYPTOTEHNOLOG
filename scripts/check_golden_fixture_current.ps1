$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root "fixtures\manifest.toml"
. (Join-Path $PSScriptRoot "lib\replay_manifest.ps1")

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
