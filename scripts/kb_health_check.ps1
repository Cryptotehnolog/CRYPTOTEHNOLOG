$ErrorActionPreference = "Stop"

# Policy:
# This script is allowed in pre-commit hooks, so it must remain fast, local,
# deterministic, and network-free. Do not call LLMs, external APIs, external
# URL validators, long-running audits, Docker, databases, or heavy test suites
# from this script. Put those checks in CI or a separate manual audit script.

$root = Split-Path -Parent $PSScriptRoot
$knowledge = Join-Path $root "knowledge"
$index = Join-Path $knowledge "index.md"
$log = Join-Path $knowledge "log.md"

if (!(Test-Path $knowledge)) {
    throw "Missing knowledge directory: $knowledge"
}

if (!(Test-Path $index)) {
    throw "Missing knowledge index: $index"
}

if (!(Test-Path $log)) {
    throw "Missing knowledge log: $log"
}

$markdownFiles = Get-ChildItem -Path $knowledge -Recurse -Filter "*.md" -File
$failures = New-Object System.Collections.Generic.List[string]
$indexText = Get-Content -LiteralPath $index -Raw

foreach ($file in $markdownFiles) {
    $text = Get-Content -LiteralPath $file.FullName -Raw
    if (!$text.StartsWith("---`n") -and !$text.StartsWith("---`r`n")) {
        $failures.Add("Missing YAML frontmatter: $($file.FullName)")
    }

    if ($file.FullName -like "*\knowledge\wiki\*") {
        $relative = Resolve-Path -LiteralPath $file.FullName -Relative
        $indexPath = ($relative -replace "^\.\\knowledge\\", "") -replace "\\", "/"
        if (!$indexText.Contains($indexPath)) {
            $failures.Add("Wiki page missing from index: $indexPath")
        }
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    throw "Knowledge base health check failed with $($failures.Count) issue(s)."
}

Write-Output "Knowledge base health check passed. Checked $($markdownFiles.Count) Markdown files."
