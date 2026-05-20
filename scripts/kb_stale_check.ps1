$ErrorActionPreference = "Stop"

# Policy:
# This script is warning-only. It checks knowledge-page lifecycle metadata and
# must not fail commits or CI solely because a page needs review.

$root = Split-Path -Parent $PSScriptRoot
$knowledge = Join-Path $root "knowledge"
$today = (Get-Date).Date

function Get-Frontmatter {
    param([string] $Path)

    $text = Get-Content -LiteralPath $Path -Raw
    if ($text -notmatch "(?s)^---\r?\n(.*?)\r?\n---") {
        return @{}
    }

    $frontmatter = $Matches[1]
    $map = @{}
    foreach ($line in ($frontmatter -split "\r?\n")) {
        if ($line -match "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$") {
            $map[$Matches[1]] = $Matches[2].Trim().Trim('"')
        }
    }

    return $map
}

$managedMarkdownFiles = @(
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

$warnings = New-Object System.Collections.Generic.List[string]

foreach ($filePath in $managedMarkdownFiles) {
    $frontmatter = Get-Frontmatter -Path $filePath
    $stability = $frontmatter["stability"]
    $reviewAfter = $frontmatter["review_after"]

    if ([string]::IsNullOrWhiteSpace($stability)) {
        continue
    }

    if ($stability -eq "archived") {
        continue
    }

    if ([string]::IsNullOrWhiteSpace($reviewAfter) -or $reviewAfter -eq "null") {
        continue
    }

    $reviewDate = [datetime]::MinValue
    if (![datetime]::TryParseExact(
            $reviewAfter,
            "yyyy-MM-dd",
            [System.Globalization.CultureInfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::None,
            [ref] $reviewDate
        )) {
        $relative = [System.IO.Path]::GetRelativePath($root, $filePath)
        $warnings.Add("Invalid review_after date in $relative -> $reviewAfter")
        continue
    }

    if ($reviewDate.Date -lt $today) {
        $relative = [System.IO.Path]::GetRelativePath($root, $filePath)
        $warnings.Add("Review overdue: $relative review_after=$reviewAfter stability=$stability")
    }
}

if ($warnings.Count -gt 0) {
    Write-Warning "Knowledge stale check found $($warnings.Count) warning(s):"
    $warnings | ForEach-Object { Write-Warning $_ }
}
else {
    Write-Output "Knowledge stale check passed without warnings."
}

Write-Output "Knowledge stale check completed. Checked $($managedMarkdownFiles.Count) managed Markdown files."

