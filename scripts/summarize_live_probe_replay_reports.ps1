param(
    [string]$ReportsGlob = "artifacts\live_probe_replay_report*.json"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

function Convert-NullableDouble {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    return [double]::Parse($text, [System.Globalization.CultureInfo]::InvariantCulture)
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

function Format-OptionalValue {
    param($Value)

    if ($null -eq $Value) {
        return ""
    }

    return [string]$Value
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

function Select-MismatchFlag {
    param(
        $FlagValue,
        [bool]$Fallback
    )

    if ($null -eq $FlagValue) {
        return $Fallback
    }

    return [System.Convert]::ToBoolean($FlagValue)
}

function Select-SelectionQuality {
    param(
        $QualityValue,
        $DeribitInstrument,
        $PolymarketMarket,
        [bool]$StrikeMismatch,
        [bool]$ExpiryMismatch,
        [bool]$PolymarketExpiryMismatch
    )

    $qualityText = Format-OptionalValue $QualityValue
    if (-not [string]::IsNullOrWhiteSpace($qualityText)) {
        return $qualityText
    }

    if ([string]::IsNullOrWhiteSpace((Format-OptionalValue $DeribitInstrument)) -or
        [string]::IsNullOrWhiteSpace((Format-OptionalValue $PolymarketMarket))) {
        return "missing"
    }

    $mismatchCount = 0
    if ($StrikeMismatch) { $mismatchCount++ }
    if ($ExpiryMismatch) { $mismatchCount++ }
    if ($PolymarketExpiryMismatch) { $mismatchCount++ }

    if ($mismatchCount -gt 1) {
        return "mismatch"
    }

    if ($mismatchCount -eq 1) {
        return "nearby"
    }

    return "exact"
}

function Select-ReplayEdgeQuality {
    param($Report)

    $quality = $Report.replay_summary.edge_quality
    if ($quality) {
        return [pscustomobject]@{
            Matched = [int]$quality.matched_count
            EdgeBelowThreshold = [int]$quality.edge_below_threshold_count
            MidpointFalsePositive = [int]$quality.midpoint_false_positive_count
        }
    }

    return [pscustomobject]@{
        Matched = [int]$Report.replay_summary.matched
        EdgeBelowThreshold = 0
        MidpointFalsePositive = 0
    }
}

if (-not [System.IO.Path]::IsPathRooted($ReportsGlob)) {
    $ReportsGlob = Join-Path $root $ReportsGlob
}

$files = @(Get-ChildItem -Path $ReportsGlob -File | Sort-Object FullName)
if ($files.Count -eq 0) {
    throw "No live probe replay reports found for pattern: $ReportsGlob"
}

$reportRows = @()
$selectionRows = @()
$deribitCandidateRows = @()
$polymarketCandidateRows = @()
$payloadShapeRows = @()
$mismatchRows = @()
$warningRows = @()
$errorRows = @()
foreach ($file in $files) {
    $report = Get-Content $file.FullName -Raw | ConvertFrom-Json
    $errors = @($report.errors)
    $warnings = @($report.warnings)
    $parseErrors = @($errors | Where-Object { $_.stage -eq "parse" })
    $httpErrors = @($errors | Where-Object { $_.stage -eq "http" })
    $selection = $report.selection_report
    $accepted = [int]$report.ingestion_report.total_normalized_events_accepted
    $decisions = [int]$report.replay_summary.decisions
    $observations = [int]$report.replay_summary.observations
    $edgeQuality = Select-ReplayEdgeQuality -Report $report
    $matcherReady = ($accepted -ge 2 -and $decisions -gt 0)
    $targetExpiryTsMs = Convert-NullableInt64 $selection.target_expiry_ts_ms
    $selectedExpiryTsMs = Convert-NullableInt64 $selection.selected_expiry_ts_ms
    $strikeDistance = Convert-NullableDouble $selection.strike_distance
    $targetExpiryDate = Select-ExpiryDate $selection.target_expiry_date $targetExpiryTsMs
    $selectedExpiryDate = Select-ExpiryDate $selection.selected_expiry_date $selectedExpiryTsMs
    $selectedPolymarketEndTsMs = Convert-NullableInt64 $selection.selected_polymarket_end_ts_ms
    $selectedPolymarketEndDate = Select-ExpiryDate $selection.selected_polymarket_end_date $selectedPolymarketEndTsMs
    $fallbackStrikeMismatch = ($null -ne $strikeDistance -and $strikeDistance -gt 0.0)
    $fallbackExpiryMismatch = ($null -ne $targetExpiryTsMs -and $null -ne $selectedExpiryTsMs -and $selectedExpiryTsMs -ne $targetExpiryTsMs)
    $fallbackPolymarketExpiryMismatch = (-not [string]::IsNullOrWhiteSpace($targetExpiryDate) -and -not [string]::IsNullOrWhiteSpace($selectedPolymarketEndDate) -and $targetExpiryDate -ne $selectedPolymarketEndDate)
    $hasStrikeMismatch = Select-MismatchFlag $selection.strike_mismatch $fallbackStrikeMismatch
    $hasExpiryMismatch = Select-MismatchFlag $selection.expiry_mismatch $fallbackExpiryMismatch
    $hasPolymarketExpiryMismatch = Select-MismatchFlag $selection.polymarket_expiry_mismatch $fallbackPolymarketExpiryMismatch
    $selectionQuality = Select-SelectionQuality $selection.selection_quality $selection.selected_deribit_instrument $selection.selected_polymarket_market_slug $hasStrikeMismatch $hasExpiryMismatch $hasPolymarketExpiryMismatch
    $warningReasons = @()
    if ($hasStrikeMismatch) {
        $warningReasons += "strike_distance > 0"
    }
    if ($hasExpiryMismatch) {
        $warningReasons += "selected_expiry_ts_ms != target_expiry_ts_ms"
    }
    if ($hasPolymarketExpiryMismatch) {
        $warningReasons += "selected_polymarket_end_date != target_expiry_date"
    }

    $reportRows += [pscustomobject]@{
        Report = $file.Name
        ProbeOk = @($report.probe_reports | Where-Object { $_.status -eq "ok" }).Count
        ProbeErrors = @($report.probe_reports | Where-Object { $_.status -ne "ok" }).Count
        ParseErrors = $parseErrors.Count
        HttpErrors = $httpErrors.Count
        Warnings = $warnings.Count
        AcceptedNormalized = $accepted
        MatcherDecisions = $decisions
        Observations = $observations
        Matched = $edgeQuality.Matched
        EdgeBelowThreshold = $edgeQuality.EdgeBelowThreshold
        MidpointFalsePositive = $edgeQuality.MidpointFalsePositive
        MatcherReady = $matcherReady
    }

    $selectionRow = [pscustomobject]@{
        Report = $file.Name
        Quality = $selectionQuality
        DeribitInstrument = Format-OptionalValue $selection.selected_deribit_instrument
        PolymarketMarket = Format-OptionalValue $selection.selected_polymarket_market_slug
        TargetExpiryDate = $targetExpiryDate
        SelectedExpiryDate = $selectedExpiryDate
        PolymarketEndDate = $selectedPolymarketEndDate
        StrikeDistance = Format-OptionalValue $strikeDistance
        Warning = if ($warningReasons.Count -gt 0) { $warningReasons -join "; " } else { "" }
    }
    $selectionRows += $selectionRow

    if ($warningReasons.Count -gt 0) {
        $mismatchRows += $selectionRow
    }

    foreach ($candidate in @($selection.deribit_expiry_candidates)) {
        $deribitCandidateRows += [pscustomobject]@{
            Report = $file.Name
            Instrument = [string]$candidate.instrument_name
            ExpiryDate = Format-OptionalValue $candidate.expiry_date
            ExpiryDistanceDays = Convert-NullableDouble $candidate.expiry_distance_days
            Strike = Convert-NullableDouble $candidate.strike
            StrikeDistance = Convert-NullableDouble $candidate.strike_distance
            WithinExpiryWindow = [System.Convert]::ToBoolean($candidate.within_expiry_window)
            WithinStrikeWindow = [System.Convert]::ToBoolean($candidate.within_strike_window)
        }
    }

    foreach ($payloadShape in @($report.payload_shape_versions)) {
        $payloadShapeRows += [pscustomobject]@{
            Report = $file.Name
            Endpoint = [string]$payloadShape.endpoint
            PayloadShapeVersion = [string]$payloadShape.payload_shape_version
        }
    }

    foreach ($candidate in @($report.polymarket_discovery_diagnostics)) {
        $polymarketCandidateRows += [pscustomobject]@{
            Report = $file.Name
            Market = [string]$candidate.market_slug
            OutcomeFound = [System.Convert]::ToBoolean($candidate.outcome_found)
            LiquidityUsd = Convert-NullableDouble $candidate.liquidity_usd
            LiquidityOk = [System.Convert]::ToBoolean($candidate.liquidity_ok)
            Active = [System.Convert]::ToBoolean($candidate.active)
            Closed = [System.Convert]::ToBoolean($candidate.closed)
            MissingTerms = (@($candidate.missing_terms) -join ",")
            RejectionReasons = (@($candidate.rejection_reasons) -join ",")
        }
    }

    foreach ($warningEntry in $warnings) {
        $warningRows += [pscustomobject]@{
            Report = $file.Name
            Stage = [string]$warningEntry.stage
            Endpoint = [string]$warningEntry.endpoint
            Kind = [string]$warningEntry.kind
            Message = [string]$warningEntry.message
        }
    }

    foreach ($errorEntry in $errors) {
        $errorRows += [pscustomobject]@{
            Report = $file.Name
            Stage = [string]$errorEntry.stage
            Endpoint = [string]$errorEntry.endpoint
            Kind = [string]$errorEntry.kind
            Message = [string]$errorEntry.message
        }
    }
}

$totalReports = $reportRows.Count
$readyReports = @($reportRows | Where-Object { $_.MatcherReady }).Count
$reportsWithParseErrors = @($reportRows | Where-Object { $_.ParseErrors -gt 0 }).Count
$reportsWithHttpErrors = @($reportRows | Where-Object { $_.HttpErrors -gt 0 }).Count
$totalWarnings = ($reportRows | Measure-Object -Property Warnings -Sum).Sum
$warningKinds = @($warningRows |
    Group-Object Kind |
    Sort-Object Name |
    ForEach-Object { "$($_.Name)=$($_.Count)" })
$totalMatched = ($reportRows | Measure-Object -Property Matched -Sum).Sum
$totalEdgeBelowThreshold = ($reportRows | Measure-Object -Property EdgeBelowThreshold -Sum).Sum
$totalMidpointFalsePositive = ($reportRows | Measure-Object -Property MidpointFalsePositive -Sum).Sum

Write-Output "Live probe replay summary ($totalReports files)"
Write-Output "Matcher readiness: $readyReports/$totalReports reports ready ($([math]::Round(($readyReports / [double]$totalReports) * 100.0, 2))%)"
Write-Output "Reports with parse errors: $reportsWithParseErrors/$totalReports"
Write-Output "Reports with HTTP errors: $reportsWithHttpErrors/$totalReports"
Write-Output "Warnings: $totalWarnings"
Write-Output "Warning kinds: $(if ($warningKinds.Count -gt 0) { $warningKinds -join ', ' } else { 'none' })"
Write-Output "Edge quality totals: matched=$totalMatched edge_below_threshold=$totalEdgeBelowThreshold midpoint_false_positive=$totalMidpointFalsePositive"
Write-Output ""

$reportRows | Format-Table -AutoSize

if ($selectionRows.Count -gt 0) {
    Write-Output ""
    Write-Output "Selected Candidates"
    $selectionRows | Format-Table -AutoSize
}

if ($mismatchRows.Count -gt 0) {
    Write-Output ""
    Write-Output "WARNING: Basis mismatch risk detected in selected candidates"
    foreach ($row in $mismatchRows) {
        Write-Output "- $($row.Report): $($row.Warning) (Deribit=$($row.DeribitInstrument), Polymarket=$($row.PolymarketMarket), target_expiry_date=$($row.TargetExpiryDate), selected_expiry_date=$($row.SelectedExpiryDate), polymarket_end_date=$($row.PolymarketEndDate), strike_distance=$($row.StrikeDistance))"
    }
}

if ($deribitCandidateRows.Count -gt 0) {
    Write-Output ""
    Write-Output "Deribit expiry candidates"
    foreach ($row in $deribitCandidateRows) {
        Write-Output "- $($row.Report): instrument=$($row.Instrument) expiry_date=$($row.ExpiryDate) expiry_distance_days=$($row.ExpiryDistanceDays) strike=$($row.Strike) strike_distance=$($row.StrikeDistance) within_expiry_window=$($row.WithinExpiryWindow) within_strike_window=$($row.WithinStrikeWindow)"
    }
}

if ($polymarketCandidateRows.Count -gt 0) {
    Write-Output ""
    Write-Output "Polymarket Gamma candidate diagnostics"
    foreach ($row in $polymarketCandidateRows) {
        Write-Output "- $($row.Report): market=$($row.Market) reasons=$($row.RejectionReasons) missing_terms=$($row.MissingTerms) liquidity_usd=$($row.LiquidityUsd) liquidity_ok=$($row.LiquidityOk) active=$($row.Active) closed=$($row.Closed) outcome_found=$($row.OutcomeFound)"
    }
}

if ($payloadShapeRows.Count -gt 0) {
    Write-Output ""
    Write-Output "Payload Shapes"
    $payloadShapeRows | Format-Table -AutoSize
}

if ($warningRows.Count -gt 0) {
    Write-Output ""
    Write-Output "Warnings by stage/endpoint/kind"
    $warningRows |
        Group-Object Stage, Endpoint, Kind |
        ForEach-Object {
            [pscustomobject]@{
                Stage = $_.Group[0].Stage
                Endpoint = $_.Group[0].Endpoint
                Kind = $_.Group[0].Kind
                Count = $_.Count
            }
        } |
        Sort-Object Stage, Endpoint, Kind |
        Format-Table -AutoSize
}

if ($errorRows.Count -gt 0) {
    Write-Output ""
    Write-Output "Errors by stage/endpoint/kind"
    $errorRows |
        Group-Object Stage, Endpoint, Kind |
        ForEach-Object {
            [pscustomobject]@{
                Stage = $_.Group[0].Stage
                Endpoint = $_.Group[0].Endpoint
                Kind = $_.Group[0].Kind
                Count = $_.Count
            }
        } |
        Sort-Object Stage, Endpoint, Kind |
        Format-Table -AutoSize
}
