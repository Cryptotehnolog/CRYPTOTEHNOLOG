param(
    [string]$OutputPath,
    [switch]$Timestamped
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    if ($Timestamped) {
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $OutputPath = "artifacts\network_connectivity_report_$timestamp.json"
    }
    else {
        $OutputPath = "artifacts\network_connectivity_report.json"
    }
}

if (-not [System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath = Join-Path $root $OutputPath
}

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "cargo executable not found. Install Rust toolchain before running network connectivity check."
}

Push-Location $root
try {
    $outputDirectory = Split-Path -Parent $OutputPath
    if (-not (Test-Path $outputDirectory)) {
        New-Item -ItemType Directory -Path $outputDirectory | Out-Null
    }

    $report = & cargo run --quiet -p cryptotehnolog-ingestion --features network-integration --bin network_connectivity_check
    $exitCode = $LASTEXITCODE
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($OutputPath, ($report + [Environment]::NewLine), $utf8NoBom)
    Write-Output "Network connectivity report written to $OutputPath"
    Write-Output $report

    if ($exitCode -ne 0) {
        throw "network connectivity check failed."
    }
}
finally {
    Pop-Location
}
