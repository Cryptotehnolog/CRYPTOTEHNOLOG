$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$fixturePath = Join-Path $root "fixtures\probability_basis\golden_events.psv"
$expectedTextPath = Join-Path $root "fixtures\probability_basis\golden_report.txt"
$expectedJsonPath = Join-Path $root "fixtures\probability_basis\golden_report.json"

Push-Location $root
try {
    $actualJson = cargo run -q -p cryptotehnolog-replay -- --format json $fixturePath
    if ($LASTEXITCODE -ne 0) {
        throw "Replay runner JSON report failed."
    }

    $expectedJson = Get-Content $expectedJsonPath

    $actualJsonText = ($actualJson -join "`n").Trim()
    $expectedJsonText = ($expectedJson -join "`n").Trim()

    if ($actualJsonText -ne $expectedJsonText) {
        Write-Output "Expected replay JSON report:"
        Write-Output $expectedJsonText
        Write-Output ""
        Write-Output "Actual replay JSON report:"
        Write-Output $actualJsonText
        throw "Replay regression failed: JSON report differs from golden fixture."
    }

    $actualText = cargo run -q -p cryptotehnolog-replay -- --format text $fixturePath
    if ($LASTEXITCODE -ne 0) {
        throw "Replay runner text report failed."
    }

    $expectedText = Get-Content $expectedTextPath

    $actualTextJoined = ($actualText -join "`n").Trim()
    $expectedTextJoined = ($expectedText -join "`n").Trim()

    if ($actualTextJoined -ne $expectedTextJoined) {
        Write-Output "Expected replay text report:"
        Write-Output $expectedTextJoined
        Write-Output ""
        Write-Output "Actual replay text report:"
        Write-Output $actualTextJoined
        throw "Replay regression failed: text report differs from golden fixture."
    }

    Write-Output "Replay regression passed."
}
finally {
    Pop-Location
}
