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

$managedMarkdownFiles = @(
    (Join-Path $knowledge "README.md"),
    (Join-Path $knowledge "schema.md"),
    (Join-Path $knowledge "index.md"),
    (Join-Path $knowledge "graph.md"),
    (Join-Path $knowledge "log.md")
)

$managedMarkdownFiles += Get-ChildItem -Path (Join-Path $knowledge "wiki") -Recurse -Filter "*.md" -File |
    ForEach-Object { $_.FullName }

$managedMarkdownFiles += Get-ChildItem -Path (Join-Path $knowledge "raw") -Recurse -Filter "*.md" -File |
    ForEach-Object { $_.FullName }

$managedMarkdownFiles += Get-ChildItem -Path (Join-Path $knowledge "templates") -Recurse -Filter "*.md" -File |
    ForEach-Object { $_.FullName }

$failures = New-Object System.Collections.Generic.List[string]
$indexText = Get-Content -LiteralPath $index -Raw
$requiredFrontmatterFields = @("type", "status", "confidence", "stability", "updated", "review_after")

foreach ($filePath in $managedMarkdownFiles) {
    $file = Get-Item -LiteralPath $filePath
    $text = Get-Content -LiteralPath $file.FullName -Raw
    if (!$text.StartsWith("---`n") -and !$text.StartsWith("---`r`n")) {
        $failures.Add("Missing YAML frontmatter: $($file.FullName)")
        continue
    }

    if ($text -match "(?s)^---\r?\n(.*?)\r?\n---") {
        $frontmatter = $Matches[1]
        foreach ($field in $requiredFrontmatterFields) {
            if ($frontmatter -notmatch "(?m)^\s*$field\s*:") {
                $failures.Add("Missing frontmatter field '$field': $($file.FullName)")
            }
        }
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

Write-Output "Knowledge base health check passed. Checked $($managedMarkdownFiles.Count) managed Markdown files."
