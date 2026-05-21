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

$phase0PipelineReports = @()
$phase0PipelineReportFiles = Get-ChildItem -Path (Join-Path $root "fixtures/phase0_pipeline") -Filter "*_report.json" -File |
    Sort-Object Name
foreach ($file in $phase0PipelineReportFiles) {
    $json = Read-JsonFile -Path $file.FullName
    $status = if ($json.PSObject.Properties["status"]) { [string]$json.status } else { "unknown" }
    $errorStage = if ($json.PSObject.Properties["error_stage"]) { $json.error_stage } else { $null }
    $errorMessage = if ($json.PSObject.Properties["error_message"]) { $json.error_message } else { $null }

    $phase0PipelineReports += [pscustomobject]@{
        file = RelPath $file.FullName
        status = $status
        raw_events = [int]$json.raw_events
        normalized_events = [int]$json.normalized_events
        journal_rows = [int]$json.journal_rows
        match_decisions = [int]$json.match_decisions
        observations = [int]$json.observations
        observation_rows = [int]$json.observation_rows
        error_stage = $errorStage
        error_message = $errorMessage
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

$phase0PipelineErrorCount = @($phase0PipelineReports | Where-Object { $_.status -ne "ok" }).Count
$warnings = @()
if ($phase0PipelineErrorCount -gt 0) {
    $warnings += "Phase 0 pipeline has $phase0PipelineErrorCount scenario(s) with non-ok status. Check phase0_pipeline.reports for controlled failure paths."
}

$report = [pscustomobject]@{
    schema_version = 1
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    warnings = $warnings
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
    phase0_pipeline = [pscustomobject]@{
        scenario_count = $phase0PipelineReports.Count
        ok_count = @($phase0PipelineReports | Where-Object { $_.status -eq "ok" }).Count
        error_count = $phase0PipelineErrorCount
        raw_events = ($phase0PipelineReports | Measure-Object -Property raw_events -Sum).Sum
        normalized_events = ($phase0PipelineReports | Measure-Object -Property normalized_events -Sum).Sum
        observations = ($phase0PipelineReports | Measure-Object -Property observations -Sum).Sum
        observation_rows = ($phase0PipelineReports | Measure-Object -Property observation_rows -Sum).Sum
        reports = $phase0PipelineReports
    }
    artifacts = $artifactReports
}

$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = New-Object System.Collections.Generic.List[string]
$markdown.Add("# Phase 0 Daily Report")
$markdown.Add("")
$markdown.Add("- Generated UTC: $($report.generated_at_utc)")
$markdown.Add("- Warnings: $($report.warnings.Count)")
$markdown.Add("- Replay scenarios: $($report.replay.scenario_count)")
$markdown.Add("- Replay matched/rejected: $($report.replay.matched_count)/$($report.replay.rejected_count)")
$markdown.Add("- Ingestion scenarios: $($report.ingestion.scenario_count)")
$markdown.Add("- Ingestion accepted/rejected normalized events: $($report.ingestion.normalized_events_accepted)/$($report.ingestion.normalized_events_rejected)")
$markdown.Add("- Phase 0 pipeline scenarios ok/error: $($report.phase0_pipeline.ok_count)/$($report.phase0_pipeline.error_count)")
$markdown.Add("")
if ($report.warnings.Count -gt 0) {
    $markdown.Add("## Warnings")
    $markdown.Add("")
    foreach ($warning in $report.warnings) {
        $markdown.Add("- $warning")
    }
    $markdown.Add("")
}
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
$markdown.Add("## Phase 0 Pipeline Reports")
$markdown.Add("")
if ($phase0PipelineReports.Count -eq 0) {
    $markdown.Add("No Phase 0 pipeline reports found.")
} else {
    $markdown.Add("| File | Status | Raw | Normalized | Decisions | Observations | Rows | Error Stage |")
    $markdown.Add("| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |")
    foreach ($item in $phase0PipelineReports) {
        $markdown.Add("| $($item.file) | $($item.status) | $($item.raw_events) | $($item.normalized_events) | $($item.match_decisions) | $($item.observations) | $($item.observation_rows) | $($item.error_stage) |")
    }
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
