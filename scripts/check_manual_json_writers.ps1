$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$failures = New-Object System.Collections.Generic.List[string]

$scanRoots = @(
    "crates/replay/src"
)

$forbiddenPatterns = @(
    @{ Pattern = 'fn\s+json_escape\s*\('; Message = 'manual json_escape helper' },
    @{ Pattern = 'fn\s+json_option\w*\s*\('; Message = 'manual JSON option helper' },
    @{ Pattern = 'push_str\s*\(\s*&?format!\s*\('; Message = 'manual JSON push_str(format!) writer' },
    @{ Pattern = 'format!\s*\(\s*"\{\\"'; Message = 'manual escaped JSON format! writer' }
)

foreach ($relativeRoot in $scanRoots) {
    $scanRoot = Join-Path $root $relativeRoot
    if (-not (Test-Path -LiteralPath $scanRoot)) {
        continue
    }

    $files = Get-ChildItem -Path $scanRoot -Recurse -File -Filter "*.rs"
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($root.Length).TrimStart("\", "/")
        $lines = Get-Content -LiteralPath $file.FullName
        for ($index = 0; $index -lt $lines.Count; $index++) {
            $line = $lines[$index]
            foreach ($rule in $forbiddenPatterns) {
                if ($line -match $rule.Pattern) {
                    $lineNumber = $index + 1
                    $failures.Add("${relative}:${lineNumber} contains $($rule.Message). Use typed DTO + serde Serialize/serde_json instead.")
                }
            }
        }
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    throw "Manual JSON writer check failed with $($failures.Count) issue(s)."
}

Write-Output "Manual JSON writer check passed."
