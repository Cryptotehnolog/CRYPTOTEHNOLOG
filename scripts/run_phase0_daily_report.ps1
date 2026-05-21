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

function Format-OptionalValue {
    param($Value)

    if ($null -eq $Value) {
        return ""
    }

    return [string]$Value
}

function Convert-NullableInt64 {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    return [int64]::Parse($text, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Convert-UnixMsToUtcDate {
    param($Value)

    $timestampMs = Convert-NullableInt64 $Value
    if ($null -eq $timestampMs) {
        return ""
    }

    return [DateTimeOffset]::FromUnixTimeMilliseconds($timestampMs).UtcDateTime.ToString("yyyy-MM-dd")
}

function Select-ExpiryDate {
    param(
        $DateValue,
        $TimestampMs
    )

    $dateText = Format-OptionalValue $DateValue
    if (-not [string]::IsNullOrWhiteSpace($dateText)) {
        return $dateText
    }

    return Convert-UnixMsToUtcDate $TimestampMs
}

function Select-BasisAlignmentStatus {
    param($Selection)

    $statusText = Format-OptionalValue $Selection.basis_alignment_status
    if (-not [string]::IsNullOrWhiteSpace($statusText)) {
        return $statusText
    }

    $deribitInstrument = Format-OptionalValue $Selection.selected_deribit_instrument
    $polymarketMarket = Format-OptionalValue $Selection.selected_polymarket_market_slug
    if ([string]::IsNullOrWhiteSpace($deribitInstrument) -or [string]::IsNullOrWhiteSpace($polymarketMarket)) {
        return "missing"
    }

    $strikeDistance = $Selection.strike_distance
    $strikeMismatch = if ($null -ne $Selection.strike_mismatch) {
        [System.Convert]::ToBoolean($Selection.strike_mismatch)
    } elseif ($null -ne $strikeDistance) {
        [double]::Parse([string]$strikeDistance, [System.Globalization.CultureInfo]::InvariantCulture) -gt 0.0
    } else {
        $false
    }

    $targetExpiryTsMs = Convert-NullableInt64 $Selection.target_expiry_ts_ms
    $selectedExpiryTsMs = Convert-NullableInt64 $Selection.selected_expiry_ts_ms
    $expiryMismatch = if ($null -ne $Selection.expiry_mismatch) {
        [System.Convert]::ToBoolean($Selection.expiry_mismatch)
    } else {
        $null -ne $targetExpiryTsMs -and $null -ne $selectedExpiryTsMs -and $targetExpiryTsMs -ne $selectedExpiryTsMs
    }

    $targetExpiryDate = Select-ExpiryDate $Selection.target_expiry_date $targetExpiryTsMs
    $selectedPolymarketEndTsMs = Convert-NullableInt64 $Selection.selected_polymarket_end_ts_ms
    $selectedPolymarketEndDate = Select-ExpiryDate $Selection.selected_polymarket_end_date $selectedPolymarketEndTsMs
    $polymarketExpiryMismatch = if ($null -ne $Selection.polymarket_expiry_mismatch) {
        [System.Convert]::ToBoolean($Selection.polymarket_expiry_mismatch)
    } else {
        -not [string]::IsNullOrWhiteSpace($targetExpiryDate) -and -not [string]::IsNullOrWhiteSpace($selectedPolymarketEndDate) -and $targetExpiryDate -ne $selectedPolymarketEndDate
    }

    if ($strikeMismatch) {
        return "strike_mismatch"
    }

    if ($polymarketExpiryMismatch) {
        return "polymarket_date_mismatch"
    }

    if ($expiryMismatch) {
        return "deribit_expiry_nearby"
    }

    return "exact"
}

$replayReports = @()
$replayReportFiles = Get-ChildItem -Path (Join-Path $root "fixtures/probability_basis") -Filter "*_report.json" -File |
    Sort-Object Name
foreach ($file in $replayReportFiles) {
    $json = Read-JsonFile -Path $file.FullName
    $edgeQuality = $json.summary.edge_quality
    $edgeBelowThresholdCount = if ($edgeQuality -and $edgeQuality.PSObject.Properties["edge_below_threshold_count"]) {
        [int]$edgeQuality.edge_below_threshold_count
    } else {
        $edgeCount = 0
        foreach ($rejection in $json.summary.rejection_counts) {
            if ($rejection.reason -eq "EdgeBelowThreshold") {
                $edgeCount += [int]$rejection.count
            }
        }
        $edgeCount
    }
    $midpointFalsePositiveCount = if ($edgeQuality -and $edgeQuality.PSObject.Properties["midpoint_false_positive_count"]) {
        [int]$edgeQuality.midpoint_false_positive_count
    } elseif ($json.summary.PSObject.Properties["midpoint_false_positive_count"]) {
        [int]$json.summary.midpoint_false_positive_count
    } else {
        0
    }
    $replayReports += [pscustomobject]@{
        file = RelPath $file.FullName
        pricing_model_version = $json.pricing_model_version
        matched_count = [int]$json.summary.matched_count
        rejected_count = [int]$json.summary.rejected_count
        edge_below_threshold_count = $edgeBelowThresholdCount
        midpoint_false_positive_count = $midpointFalsePositiveCount
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

$liveProbeReports = @()
$liveProbeReportFiles = Get-ChildItem -Path $outputRoot -File -Filter "live_probe_replay_report*.json" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTimeUtc -Descending
foreach ($file in $liveProbeReportFiles) {
    $json = Read-JsonFile -Path $file.FullName
    $edgeQuality = $json.replay_summary.edge_quality
    $basisAlignmentStatus = Select-BasisAlignmentStatus $json.selection_report
    $candidatePolicy = Format-OptionalValue $json.selection_report.candidate_policy
    if ([string]::IsNullOrWhiteSpace($candidatePolicy)) {
        if ($basisAlignmentStatus -eq "exact") {
            $candidatePolicy = "clean_basis_candidate"
        } elseif ($basisAlignmentStatus -eq "missing") {
            $candidatePolicy = "missing"
        } else {
            $candidatePolicy = "diagnostic_only"
        }
    }
    $liveProbeReports += [pscustomobject]@{
        file = RelPath $file.FullName
        matched_count = if ($edgeQuality) { [int]$edgeQuality.matched_count } else { [int]$json.replay_summary.matched }
        edge_below_threshold_count = if ($edgeQuality) { [int]$edgeQuality.edge_below_threshold_count } else { 0 }
        midpoint_false_positive_count = if ($edgeQuality) { [int]$edgeQuality.midpoint_false_positive_count } else { 0 }
        basis_alignment_status = $basisAlignmentStatus
        candidate_policy = $candidatePolicy
    }
}

$liveProbeTrendSummaryPath = Join-Path $outputRoot "live_probe_replay_trend_summary.txt"
$liveProbeTrendSummary = $null
if (Test-Path -LiteralPath $liveProbeTrendSummaryPath) {
    $liveProbeTrendSummary = [pscustomobject]@{
        file = RelPath $liveProbeTrendSummaryPath
        preview = @((Get-Content -LiteralPath $liveProbeTrendSummaryPath -TotalCount 12))
    }
}

$phase0PipelineErrorCount = @($phase0PipelineReports | Where-Object { $_.status -ne "ok" }).Count
$warnings = @()
if ($phase0PipelineErrorCount -gt 0) {
    $warnings += "Phase 0 pipeline has $phase0PipelineErrorCount scenario(s) with non-ok status. Check phase0_pipeline.reports for controlled failure paths."
}
$liveProbeMatchedCount = ($liveProbeReports | Measure-Object -Property matched_count -Sum).Sum
$liveProbeMidpointFalsePositiveCount = ($liveProbeReports | Measure-Object -Property midpoint_false_positive_count -Sum).Sum
if ($liveProbeReports.Count -gt 0 -and $liveProbeMidpointFalsePositiveCount -gt $liveProbeMatchedCount) {
    $warnings += "Live probe midpoint false positives ($liveProbeMidpointFalsePositiveCount) exceed matched opportunities ($liveProbeMatchedCount). Current matching may look better at midpoint than at executable pricing."
}
$liveProbeNonExactAlignmentReports = @($liveProbeReports | Where-Object { $_.basis_alignment_status -ne "exact" })
if ($liveProbeNonExactAlignmentReports.Count -gt 0) {
    $statusCounts = @($liveProbeNonExactAlignmentReports |
        Group-Object basis_alignment_status |
        Sort-Object Name |
        ForEach-Object { "$($_.Name)=$($_.Count)" })
    $warnings += "Live probe basis alignment is not exact for $($liveProbeNonExactAlignmentReports.Count) report(s): $($statusCounts -join ', '). Selected pair is not yet a clean basis candidate."
}
$liveProbeDiagnosticOnlyReports = @($liveProbeReports | Where-Object { $_.candidate_policy -eq "diagnostic_only" })
if ($liveProbeDiagnosticOnlyReports.Count -gt 0) {
    $warnings += "Live probe has $($liveProbeDiagnosticOnlyReports.Count) diagnostic-only candidate report(s). These observations can be logged for discovery/debugging but must not count toward clean Phase 0 basis candidate metrics."
}

$report = [pscustomobject]@{
    schema_version = 1
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    warnings = $warnings
    replay = [pscustomobject]@{
        scenario_count = $replayReports.Count
        matched_count = ($replayReports | Measure-Object -Property matched_count -Sum).Sum
        rejected_count = ($replayReports | Measure-Object -Property rejected_count -Sum).Sum
        edge_quality = [pscustomobject]@{
            matched_count = ($replayReports | Measure-Object -Property matched_count -Sum).Sum
            edge_below_threshold_count = ($replayReports | Measure-Object -Property edge_below_threshold_count -Sum).Sum
            midpoint_false_positive_count = ($replayReports | Measure-Object -Property midpoint_false_positive_count -Sum).Sum
        }
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
    live_probe_review = [pscustomobject]@{
        report_count = $liveProbeReports.Count
        clean_candidate_count = @($liveProbeReports | Where-Object { $_.candidate_policy -eq "clean_basis_candidate" }).Count
        diagnostic_only_count = $liveProbeDiagnosticOnlyReports.Count
        matched_count = $liveProbeMatchedCount
        edge_below_threshold_count = ($liveProbeReports | Measure-Object -Property edge_below_threshold_count -Sum).Sum
        midpoint_false_positive_count = $liveProbeMidpointFalsePositiveCount
        reports = $liveProbeReports
        trend_summary = $liveProbeTrendSummary
    }
}

$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = New-Object System.Collections.Generic.List[string]
$markdown.Add("# Phase 0 Daily Report")
$markdown.Add("")
$markdown.Add("- Generated UTC: $($report.generated_at_utc)")
$markdown.Add("- Warnings: $($report.warnings.Count)")
$markdown.Add("- Replay scenarios: $($report.replay.scenario_count)")
$markdown.Add("- Replay matched/rejected: $($report.replay.matched_count)/$($report.replay.rejected_count)")
$markdown.Add("- Replay edge quality matched/edge-below/midpoint-fp: $($report.replay.edge_quality.matched_count)/$($report.replay.edge_quality.edge_below_threshold_count)/$($report.replay.edge_quality.midpoint_false_positive_count)")
$markdown.Add("- Ingestion scenarios: $($report.ingestion.scenario_count)")
$markdown.Add("- Ingestion accepted/rejected normalized events: $($report.ingestion.normalized_events_accepted)/$($report.ingestion.normalized_events_rejected)")
$markdown.Add("- Phase 0 pipeline scenarios ok/error: $($report.phase0_pipeline.ok_count)/$($report.phase0_pipeline.error_count)")
if ($report.live_probe_review.report_count -gt 0) {
    $markdown.Add("- Live probe edge quality matched/edge-below/midpoint-fp: $($report.live_probe_review.matched_count)/$($report.live_probe_review.edge_below_threshold_count)/$($report.live_probe_review.midpoint_false_positive_count)")
    $markdown.Add("- Live probe clean/diagnostic-only candidates: $($report.live_probe_review.clean_candidate_count)/$($report.live_probe_review.diagnostic_only_count)")
}
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
$markdown.Add("| File | Matched | Rejected | Edge Below | Midpoint FP | Avg Net Edge |")
$markdown.Add("| --- | ---: | ---: | ---: | ---: | ---: |")
foreach ($item in $replayReports) {
    $markdown.Add("| $($item.file) | $($item.matched_count) | $($item.rejected_count) | $($item.edge_below_threshold_count) | $($item.midpoint_false_positive_count) | $($item.net_edge_average) |")
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

$markdown.Add("")
$markdown.Add("## Live Probe Review")
$markdown.Add("")
if ($liveProbeReports.Count -eq 0) {
    $markdown.Add("No live probe replay reports found.")
} else {
    $markdown.Add("| File | Alignment | Policy | Matched | Edge Below | Midpoint FP |")
    $markdown.Add("| --- | --- | --- | ---: | ---: | ---: |")
    foreach ($item in $liveProbeReports) {
        $markdown.Add("| $($item.file) | $($item.basis_alignment_status) | $($item.candidate_policy) | $($item.matched_count) | $($item.edge_below_threshold_count) | $($item.midpoint_false_positive_count) |")
    }
}

if ($null -ne $liveProbeTrendSummary) {
    $markdown.Add("")
    $markdown.Add("### Live Probe Trend Summary")
    $markdown.Add("")
    $markdown.Add(('Source: `{0}`' -f $liveProbeTrendSummary.file))
    $markdown.Add("")
    $markdown.Add('```text')
    foreach ($line in $liveProbeTrendSummary.preview) {
        $markdown.Add($line)
    }
    $markdown.Add('```')
}

$markdown | Set-Content -LiteralPath $markdownPath -Encoding UTF8

Write-Output "Phase 0 daily report written:"
Write-Output "JSON: $jsonPath"
Write-Output "Markdown: $markdownPath"
