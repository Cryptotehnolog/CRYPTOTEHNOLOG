$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$goldenPath = "fixtures/probability_basis/golden_report.txt"

Push-Location $root
try {
    .\scripts\update_golden_fixture.ps1

    $diff = git diff -- $goldenPath
    if ($LASTEXITCODE -ne 0) {
        throw "git diff failed."
    }

    if (-not [string]::IsNullOrWhiteSpace(($diff -join "`n"))) {
        Write-Output "Golden fixture is stale. Run scripts\update_golden_fixture.ps1 and review the diff."
        Write-Output ($diff -join "`n")
        throw "Golden fixture check failed."
    }

    Write-Output "Golden fixture is current."
}
finally {
    Pop-Location
}
