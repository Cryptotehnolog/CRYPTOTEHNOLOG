$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$phaseGatePath = Join-Path $root "config\phase_gate.toml"

if (-not (Test-Path $phaseGatePath)) {
    throw "Missing config\phase_gate.toml."
}

$phaseGate = Get-Content $phaseGatePath -Raw

function Get-TomlBool {
    param(
        [Parameter(Mandatory=$true)][string]$Content,
        [Parameter(Mandatory=$true)][string]$Key
    )

    $pattern = "(?m)^\s*$([regex]::Escape($Key))\s*=\s*(true|false)\s*$"
    $match = [regex]::Match($Content, $pattern)
    if (-not $match.Success) {
        throw "Missing boolean key `$Key` in config\phase_gate.toml."
    }

    return $match.Groups[1].Value -eq "true"
}

$phaseOneEnabled = Get-TomlBool -Content $phaseGate -Key "phase_1_research_enabled"

if ($phaseOneEnabled) {
    Write-Output "Phase gate check skipped: phase_1_research_enabled=true."
    exit 0
}

$violations = New-Object System.Collections.Generic.List[string]

$forbiddenPathPatterns = @(
    "\.mcp($|[\\/])",
    "mcp[\\/].*",
    ".*lightrag.*",
    ".*hermes.*agent.*",
    ".*omniroute.*"
)

$allowedKnowledgePattern = "^(knowledge[\\/](raw|wiki)[\\/]|knowledge[\\/]index\.md$|knowledge[\\/]graph\.md$|knowledge[\\/]log\.md$)"
$allowedConfigPattern = "^config[\\/]phase_gate\.toml$"

$trackedFiles = git -C $root ls-files
if ($LASTEXITCODE -ne 0) {
    throw "git ls-files failed."
}

foreach ($file in $trackedFiles) {
    $normalized = $file -replace "\\", "/"

    if ($normalized -match $allowedKnowledgePattern -or $normalized -match $allowedConfigPattern) {
        continue
    }

    foreach ($pattern in $forbiddenPathPatterns) {
        if ($normalized -match $pattern) {
            $violations.Add("Forbidden Phase 1 path before gate: $file")
            break
        }
    }
}

$scanFiles = $trackedFiles | Where-Object {
    $_ -match '(^|[\\/])Dockerfile$' -or
    $_ -match '(^|[\\/])Dockerfile\.' -or
    $_ -match '^docker-compose.*\.ya?ml$' -or
    $_ -match '^\.github[\\/]workflows[\\/].*\.ya?ml$' -or
    $_ -match '^crates[\\/].*Cargo\.toml$' -or
    $_ -match '^Cargo\.toml$' -or
    $_ -match '^config[\\/].*\.(toml|ya?ml|json)$' -or
    $_ -match '^scripts[\\/].*\.(ps1|py|sh)$'
}

foreach ($file in $scanFiles) {
    $normalized = $file -replace "\\", "/"

    if ($normalized -eq "config/phase_gate.toml" -or $normalized -eq "scripts/check_phase_gate.ps1") {
        continue
    }

    $path = Join-Path $root $file
    if (-not (Test-Path $path)) {
        continue
    }

    $content = Get-Content $path -Raw
    if ($content -match "(?i)\blightrag\b") {
        $violations.Add("Forbidden LightRAG wiring reference before Phase 1: $file")
    }
    if ($content -match "(?i)\bmcp\b") {
        $violations.Add("Forbidden MCP wiring reference before Phase 1: $file")
    }
}

if ($violations.Count -gt 0) {
    $violations | ForEach-Object { Write-Error $_ }
    throw "Phase gate check failed. Keep LightRAG/MCP/Docker wiring out until phase_1_research_enabled=true."
}

Write-Output "Phase gate check passed."
