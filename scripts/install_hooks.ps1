$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$gitDir = Join-Path $root ".git"
$hooksDir = Join-Path $gitDir "hooks"
$preCommitPath = Join-Path $hooksDir "pre-commit"

if (!(Test-Path $gitDir)) {
    throw "This script must be run from a Git working tree with a .git directory."
}

if (!(Test-Path $hooksDir)) {
    New-Item -ItemType Directory -Path $hooksDir | Out-Null
}

$hook = @'
#!/bin/sh
set -eu

echo "Running CRYPTOTEHNOLOG pre-commit checks..."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/kb_health_check.ps1
'@

Set-Content -LiteralPath $preCommitPath -Value $hook -Encoding ascii

Write-Output "Installed pre-commit hook: $preCommitPath"

