$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "cargo executable not found. Install Rust toolchain before running network connectivity check."
}

Push-Location $root
try {
    cargo run -p cryptotehnolog-ingestion --features network-integration --bin network_connectivity_check
    if ($LASTEXITCODE -ne 0) {
        throw "network connectivity check failed."
    }
}
finally {
    Pop-Location
}
