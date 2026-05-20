$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$fixturePath = Join-Path $root "fixtures\probability_basis\golden_events.psv"
$expectedPath = Join-Path $root "fixtures\probability_basis\golden_report.txt"
$expectedDir = Split-Path -Parent $expectedPath

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
    $report = cargo run -q -p cryptotehnolog-replay -- $fixturePath
    if ($LASTEXITCODE -ne 0) {
        throw "Replay runner failed."
    }

    $content = ($report -join "`n").Trim() + "`n"
    Set-Content -Path $expectedPath -Value $content -NoNewline -Encoding ascii

    Write-Output "Updated fixtures\probability_basis\golden_report.txt"
}
finally {
    Pop-Location
}
