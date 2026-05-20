$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$failures = New-Object System.Collections.Generic.List[string]

$forbiddenRootFiles = @(
    "requirements.txt",
    "setup.py",
    "Pipfile",
    "Pipfile.lock",
    "poetry.lock"
)

foreach ($file in $forbiddenRootFiles) {
    $path = Join-Path $root $file
    if (Test-Path -LiteralPath $path) {
        $failures.Add("Forbidden dependency-management file found: $file")
    }
}

$scanFiles = @()
$scanFiles += Get-ChildItem -Path $root -Recurse -File -Filter "Dockerfile*" |
    Where-Object { $_.FullName -notlike "*\.git\*" -and $_.FullName -notlike "*\target\*" }

$scriptsDir = Join-Path $root "scripts"
if (Test-Path $scriptsDir) {
    $scanFiles += Get-ChildItem -Path $scriptsDir -Recurse -File |
        Where-Object { $_.Extension -in @(".ps1", ".sh", ".py", ".cmd", ".bat") }
}

foreach ($file in $scanFiles) {
    $text = Get-Content -LiteralPath $file.FullName -Raw
    if ($text -match "(?im)(^|\s)pip\s+install(\s|$)") {
        $relative = [System.IO.Path]::GetRelativePath($root, $file.FullName)
        $failures.Add("Forbidden 'pip install' command found in $relative. Use uv sync/uv run instead.")
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    throw "Compliance check failed with $($failures.Count) issue(s)."
}

Write-Output "Compliance check passed."

