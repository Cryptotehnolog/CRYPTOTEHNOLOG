param(
    [string]$OutputDir = "artifacts",
    [switch]$Timestamped
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$outputRoot = Join-Path $root $OutputDir
if (-not (Test-Path -LiteralPath $outputRoot)) {
    New-Item -ItemType Directory -Path $outputRoot | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$baseName = if ($Timestamped) { "phase0_daily_report_$timestamp" } else { "phase0_daily_report" }
$jsonPath = Join-Path $outputRoot "$baseName.json"
$markdownPath = Join-Path $outputRoot "$baseName.md"

function Read-JsonFile {
    param([string]$Path)
    $text = Get-Content -LiteralPath $Path -Raw
    return $text | ConvertFrom-Json
}

function RelPath {
    param([string]$Path)
    return $Path.Substring($root.Length).TrimStart("\", "/")
}

$replayReports = @()
$replayReportFiles = Get-ChildItem -Path (Join-Path $root "fixtures/probability_basis") -Filter "*_report.json" -File |
    Sort-Object Name
foreach ($file in $replayReportFiles) {
    $json = Read-JsonFile -Path $file.FullName
    $replayReports += [pscustomobject]@{
        file = RelPath $file.FullName
        pricing_model_version = $json.pricing_model_version
        matched_count = [int]$json.summary.matched_count
        rejected_count = [int]$json.summary.rejected_count
        net_edge_average = $json.summary.net_edge.average
        net_edge_min = $json.summary.net_edge.min
        net_edge_max = $json.summary.net_edge.max
    }
}

$ingestionReports = @()
$ingestionReportFiles = Get-ChildItem -Path (Join-Path $root "fixtures/ingestion") -Filter "*_report.json" -File |
    Sort-Object Name
foreach ($file in $ingestionReportFiles) {
    $json = Read-JsonFile -Path $file.FullName
    $ingestionReports += [pscustomobject]@{
        file = RelPath $file.FullName
        raw_events_received = [int]$json.total_raw_events_received
        normalized_events_received = [int]$json.total_normalized_events_received
        normalized_events_accepted = [int]$json.total_normalized_events_accepted
        normalized_events_rejected = [int]$json.total_normalized_events_rejected
    }
}

$artifactReports = @()
$artifactFiles = Get-ChildItem -Path $outputRoot -File -Filter "*.json" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -like "network_connectivity_report*.json" -or
        $_.Name -like "live_probe_replay_report*.json"
    } |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 5
foreach ($file in $artifactFiles) {
    $artifactReports += [pscustomobject]@{
        file = RelPath $file.FullName
        last_write_utc = $file.LastWriteTimeUtc.ToString("o")
        bytes = $file.Length
    }
}

$report = [pscustomobject]@{
    schema_version = 1
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    replay = [pscustomobject]@{
        scenario_count = $replayReports.Count
        matched_count = ($replayReports | Measure-Object -Property matched_count -Sum).Sum
        rejected_count = ($replayReports | Measure-Object -Property rejected_count -Sum).Sum
        reports = $replayReports
    }
    ingestion = [pscustomobject]@{
        scenario_count = $ingestionReports.Count
        raw_events_received = ($ingestionReports | Measure-Object -Property raw_events_received -Sum).Sum
        normalized_events_accepted = ($ingestionReports | Measure-Object -Property normalized_events_accepted -Sum).Sum
        normalized_events_rejected = ($ingestionReports | Measure-Object -Property normalized_events_rejected -Sum).Sum
        reports = $ingestionReports
    }
    artifacts = $artifactReports
}

$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = New-Object System.Collections.Generic.List[string]
$markdown.Add("# Phase 0 Daily Report")
$markdown.Add("")
$markdown.Add("- Generated UTC: $($report.generated_at_utc)")
$markdown.Add("- Replay scenarios: $($report.replay.scenario_count)")
$markdown.Add("- Replay matched/rejected: $($report.replay.matched_count)/$($report.replay.rejected_count)")
$markdown.Add("- Ingestion scenarios: $($report.ingestion.scenario_count)")
$markdown.Add("- Ingestion accepted/rejected normalized events: $($report.ingestion.normalized_events_accepted)/$($report.ingestion.normalized_events_rejected)")
$markdown.Add("")
$markdown.Add("## Replay Reports")
$markdown.Add("")
$markdown.Add("| File | Matched | Rejected | Avg Net Edge |")
$markdown.Add("| --- | ---: | ---: | ---: |")
foreach ($item in $replayReports) {
    $markdown.Add("| $($item.file) | $($item.matched_count) | $($item.rejected_count) | $($item.net_edge_average) |")
}
$markdown.Add("")
$markdown.Add("## Ingestion Reports")
$markdown.Add("")
$markdown.Add("| File | Raw | Accepted | Rejected |")
$markdown.Add("| --- | ---: | ---: | ---: |")
foreach ($item in $ingestionReports) {
    $markdown.Add("| $($item.file) | $($item.raw_events_received) | $($item.normalized_events_accepted) | $($item.normalized_events_rejected) |")
}
$markdown.Add("")
$markdown.Add("## Recent Probe Artifacts")
$markdown.Add("")
if ($artifactReports.Count -eq 0) {
    $markdown.Add("No network/live probe artifacts found.")
} else {
    $markdown.Add("| File | Last Write UTC | Bytes |")
    $markdown.Add("| --- | --- | ---: |")
    foreach ($item in $artifactReports) {
        $markdown.Add("| $($item.file) | $($item.last_write_utc) | $($item.bytes) |")
    }
}

$markdown | Set-Content -LiteralPath $markdownPath -Encoding UTF8

Write-Output "Phase 0 daily report written:"
Write-Output "JSON: $jsonPath"
Write-Output "Markdown: $markdownPath"
