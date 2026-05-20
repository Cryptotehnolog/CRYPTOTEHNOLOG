$ErrorActionPreference = "Stop"

# Policy:
# This script validates only local Markdown links. It must remain local and
# network-free. Do not validate external URLs here.

$root = Split-Path -Parent $PSScriptRoot
$failures = New-Object System.Collections.Generic.List[string]

function Test-ExternalLink {
    param([string] $Target)

    return (
        $Target -match "^[a-zA-Z][a-zA-Z0-9+.-]*:" -or
        $Target.StartsWith("#") -or
        $Target.StartsWith("mailto:")
    )
}

function Resolve-MarkdownTarget {
    param(
        [string] $BaseDirectory,
        [string] $Target
    )

    $pathPart = ($Target -split "#", 2)[0]

    if ([string]::IsNullOrWhiteSpace($pathPart)) {
        return $null
    }

    $decoded = [System.Uri]::UnescapeDataString($pathPart)
    $combined = Join-Path $BaseDirectory $decoded
    return [System.IO.Path]::GetFullPath($combined)
}

$markdownFiles = Get-ChildItem -Path $root -Recurse -Filter "*.md" -File |
    Where-Object { $_.FullName -notlike "*\.git\*" -and $_.FullName -notlike "*\target\*" }

$linkPattern = '(?<!\!)\[[^\]]+\]\(([^)\s]+)(?:\s+"[^"]*")?\)'

foreach ($file in $markdownFiles) {
    $text = Get-Content -LiteralPath $file.FullName -Raw
    $baseDirectory = Split-Path -Parent $file.FullName
    $matches = [regex]::Matches($text, $linkPattern)

    foreach ($match in $matches) {
        $target = $match.Groups[1].Value.Trim()

        if (Test-ExternalLink -Target $target) {
            continue
        }

        $resolved = Resolve-MarkdownTarget -BaseDirectory $baseDirectory -Target $target
        if ($null -eq $resolved) {
            continue
        }

        if (!(Test-Path -LiteralPath $resolved)) {
            $relativeFile = [System.IO.Path]::GetRelativePath($root, $file.FullName)
            $failures.Add("Broken local link in $relativeFile -> $target")
        }
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    throw "Local Markdown link validation failed with $($failures.Count) issue(s)."
}

Write-Output "Local Markdown link validation passed. Checked $($markdownFiles.Count) Markdown files."

