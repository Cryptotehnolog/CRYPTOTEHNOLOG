param(
    [Parameter(Mandatory = $true)]
    [string] $Title,

    [Parameter(Mandatory = $true)]
    [string] $Url,

    [string] $Author = "Unknown",

    [string] $Created = "",

    [string] $Summary = "TODO: Добавить краткое paraphrased summary.",

    [string[]] $Takeaways = @()
)

$ErrorActionPreference = "Stop"

function New-Slug {
    param([string] $Value)

    $slug = $Value.ToLowerInvariant()
    $slug = $slug -replace "[^a-z0-9]+", "-"
    $slug = $slug.Trim("-")

    if ([string]::IsNullOrWhiteSpace($slug)) {
        throw "Could not create slug from title: $Value"
    }

    return $slug
}

function Escape-Yaml {
    param([string] $Value)
    return ($Value -replace '"', '\"')
}

$root = Split-Path -Parent $PSScriptRoot
$knowledge = Join-Path $root "knowledge"
$sourceDir = Join-Path $knowledge "raw\sources"
$indexPath = Join-Path $knowledge "index.md"
$logPath = Join-Path $knowledge "log.md"
$healthCheck = Join-Path $PSScriptRoot "kb_health_check.ps1"

if (!(Test-Path $sourceDir)) {
    New-Item -ItemType Directory -Path $sourceDir | Out-Null
}

$today = Get-Date -Format "yyyy-MM-dd"
if ([string]::IsNullOrWhiteSpace($Created)) {
    $Created = $today
}

$slug = New-Slug -Value $Title
$sourceId = "$slug-$today"
$fileName = "$sourceId.md"
$sourcePath = Join-Path $sourceDir $fileName

if (Test-Path $sourcePath) {
    throw "Source note already exists: $sourcePath"
}

$takeawayLines = if ($Takeaways.Count -gt 0) {
    ($Takeaways | ForEach-Object { "- $_" }) -join "`n"
} else {
    "- TODO: Добавить key takeaway."
}

$titleYaml = Escape-Yaml -Value $Title
$authorYaml = Escape-Yaml -Value $Author

$content = @"
---
type: source
status: active
confidence: high
stability: stable
updated: $today
review_after: null
source_id: $sourceId
title: "$titleYaml"
author: "$authorYaml"
created: $Created
url: $Url
---

# Source Note: $Title

## Summary

$Summary

## Key Takeaways

$takeawayLines

## Project Impact

TODO: Объяснить, как этот source меняет CRYPTOTEHNOLOG.

## Open Questions

- TODO: Добавить unresolved questions.
"@

Set-Content -LiteralPath $sourcePath -Value $content -Encoding utf8NoBOM

$relativeIndexPath = "raw/sources/$fileName"
$indexText = Get-Content -LiteralPath $indexPath -Raw
if (!$indexText.Contains($relativeIndexPath)) {
    $entry = "- [$Title]($relativeIndexPath) - source note.`n"
    Add-Content -LiteralPath $indexPath -Value $entry -Encoding utf8NoBOM
}

$logEntry = @"

## [$today] ingest | $Title

Created raw source note `$sourceId`.
"@
Add-Content -LiteralPath $logPath -Value $logEntry -Encoding utf8NoBOM

& $healthCheck

Write-Output "Created source note: $sourcePath"
