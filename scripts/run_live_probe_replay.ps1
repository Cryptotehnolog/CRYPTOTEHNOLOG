param(
    [string]$OutputPath,
    [switch]$Timestamped
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    if ($Timestamped) {
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $OutputPath = "artifacts\live_probe_replay_report_$timestamp.json"
    }
    else {
        $OutputPath = "artifacts\live_probe_replay_report.json"
    }
}

if (-not [System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath = Join-Path $root $OutputPath
}

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "cargo executable not found. Install Rust toolchain before running live probe replay."
}

Push-Location $root
try {
    $outputDirectory = Split-Path -Parent $OutputPath
    if (-not (Test-Path $outputDirectory)) {
        New-Item -ItemType Directory -Path $outputDirectory | Out-Null
    }

    $report = & cargo run --quiet -p cryptotehnolog-ingestion --features network-integration --bin live_probe_replay
    $exitCode = $LASTEXITCODE
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($OutputPath, ($report + [Environment]::NewLine), $utf8NoBom)
    Write-Output "Live probe replay report written to $OutputPath"
    Write-Output $report

    if ($exitCode -ne 0) {
        throw "live probe replay failed."
    }
}
finally {
    Pop-Location
}
