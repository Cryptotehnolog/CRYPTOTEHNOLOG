$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$fixturePath = Join-Path $root "fixtures\probability_basis\golden_events.psv"
$expectedTextPath = Join-Path $root "fixtures\probability_basis\golden_report.txt"
$expectedJsonPath = Join-Path $root "fixtures\probability_basis\golden_report.json"
$expectedDir = Split-Path -Parent $expectedTextPath

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "cargo executable was not found in PATH."
}

if (-not (Test-Path $fixturePath)) {
    throw "Missing replay fixture: $fixturePath"
}

if (-not (Test-Path $expectedDir)) {
    throw "Missing golden fixture directory: $expectedDir"
}

Push-Location $root
try {
    $textReport = cargo run -q -p cryptotehnolog-replay -- --format text $fixturePath
    if ($LASTEXITCODE -ne 0) {
        throw "Replay runner text report failed."
    }

    $jsonReport = cargo run -q -p cryptotehnolog-replay -- --format json $fixturePath
    if ($LASTEXITCODE -ne 0) {
        throw "Replay runner JSON report failed."
    }

    $textContent = ($textReport -join "`n").Trim() + "`n"
    $jsonContent = ($jsonReport -join "`n").Trim() + "`n"

    Set-Content -Path $expectedTextPath -Value $textContent -NoNewline -Encoding ascii
    Set-Content -Path $expectedJsonPath -Value $jsonContent -NoNewline -Encoding ascii

    Write-Output "Updated fixtures\probability_basis\golden_report.txt"
    Write-Output "Updated fixtures\probability_basis\golden_report.json"
}
finally {
    Pop-Location
}
