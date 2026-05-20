$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$outputPath = Join-Path $root "artifacts\network_connectivity_report.json"

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "cargo executable not found. Install Rust toolchain before running network connectivity check."
}

Push-Location $root
try {
    $outputDirectory = Split-Path -Parent $outputPath
    if (-not (Test-Path $outputDirectory)) {
        New-Item -ItemType Directory -Path $outputDirectory | Out-Null
    }

    $report = & cargo run --quiet -p cryptotehnolog-ingestion --features network-integration --bin network_connectivity_check
    $exitCode = $LASTEXITCODE
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($outputPath, ($report + [Environment]::NewLine), $utf8NoBom)
    Write-Output "Network connectivity report written to $outputPath"
    Write-Output $report

    if ($exitCode -ne 0) {
        throw "network connectivity check failed."
    }
}
finally {
    Pop-Location
}
