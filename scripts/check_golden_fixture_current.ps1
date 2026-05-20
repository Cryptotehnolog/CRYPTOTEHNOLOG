$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$goldenPath = Join-Path $root "fixtures\probability_basis\golden_report.txt"

if (-not (Test-Path $goldenPath)) {
    throw "Missing golden fixture: $goldenPath"
}

Push-Location $root
try {
    $before = Get-Content $goldenPath -Raw

    .\scripts\update_golden_fixture.ps1

    $after = Get-Content $goldenPath -Raw

    if ($before -ne $after) {
        Write-Output "Golden fixture is stale. Run scripts\update_golden_fixture.ps1 and review the diff."
        throw "Golden fixture check failed."
    }

    Write-Output "Golden fixture is current."
}
finally {
    Pop-Location
}
