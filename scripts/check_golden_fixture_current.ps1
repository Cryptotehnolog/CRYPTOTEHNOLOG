$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$goldenTextPath = Join-Path $root "fixtures\probability_basis\golden_report.txt"
$goldenJsonPath = Join-Path $root "fixtures\probability_basis\golden_report.json"

if (-not (Test-Path $goldenTextPath)) {
    throw "Missing golden fixture: $goldenTextPath"
}

if (-not (Test-Path $goldenJsonPath)) {
    throw "Missing golden fixture: $goldenJsonPath"
}

Push-Location $root
try {
    $beforeText = Get-Content $goldenTextPath -Raw
    $beforeJson = Get-Content $goldenJsonPath -Raw

    .\scripts\update_golden_fixture.ps1

    $afterText = Get-Content $goldenTextPath -Raw
    $afterJson = Get-Content $goldenJsonPath -Raw

    if ($beforeText -ne $afterText -or $beforeJson -ne $afterJson) {
        Write-Output "Golden fixtures are stale. Run scripts\update_golden_fixture.ps1 and review the diff."
        throw "Golden fixture check failed."
    }

    Write-Output "Golden fixture is current."
}
finally {
    Pop-Location
}
