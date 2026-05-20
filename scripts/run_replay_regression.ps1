$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$fixturePath = Join-Path $root "fixtures\probability_basis\golden_events.psv"
$expectedPath = Join-Path $root "fixtures\probability_basis\golden_report.txt"

Push-Location $root
try {
    $actual = cargo run -q -p cryptotehnolog-replay -- $fixturePath
    if ($LASTEXITCODE -ne 0) {
        throw "Replay runner failed."
    }

    $expected = Get-Content $expectedPath

    $actualText = ($actual -join "`n").Trim()
    $expectedText = ($expected -join "`n").Trim()

    if ($actualText -ne $expectedText) {
        Write-Output "Expected replay report:"
        Write-Output $expectedText
        Write-Output ""
        Write-Output "Actual replay report:"
        Write-Output $actualText
        throw "Replay regression failed: report differs from golden fixture."
    }

    Write-Output "Replay regression passed."
}
finally {
    Pop-Location
}
