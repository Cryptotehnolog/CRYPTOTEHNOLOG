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
        [bool]$ExpiryMismatch
    )

    $qualityText = Format-OptionalValue $QualityValue
    if (-not [string]::IsNullOrWhiteSpace($qualityText)) {
        return $qualityText
    }

    if ([string]::IsNullOrWhiteSpace((Format-OptionalValue $DeribitInstrument)) -or
        [string]::IsNullOrWhiteSpace((Format-OptionalValue $PolymarketMarket))) {
        return "missing"
    }

    if ($StrikeMismatch -and $ExpiryMismatch) {
        return "mismatch"
    }

    if ($StrikeMismatch -or $ExpiryMismatch) {
        return "nearby"
    }

    return "exact"
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
$payloadShapeRows = @()
$mismatchRows = @()
$errorRows = @()
foreach ($file in $files) {
    $report = Get-Content $file.FullName -Raw | ConvertFrom-Json
    $errors = @($report.errors)
    $parseErrors = @($errors | Where-Object { $_.stage -eq "parse" })
    $httpErrors = @($errors | Where-Object { $_.stage -eq "http" })
    $selection = $report.selection_report
    $accepted = [int]$report.ingestion_report.total_normalized_events_accepted
    $decisions = [int]$report.replay_summary.decisions
    $observations = [int]$report.replay_summary.observations
    $matcherReady = ($accepted -ge 2 -and $decisions -gt 0)
    $targetExpiryTsMs = Convert-NullableInt64 $selection.target_expiry_ts_ms
    $selectedExpiryTsMs = Convert-NullableInt64 $selection.selected_expiry_ts_ms
    $strikeDistance = Convert-NullableDouble $selection.strike_distance
    $targetExpiryDate = Select-ExpiryDate $selection.target_expiry_date $targetExpiryTsMs
    $selectedExpiryDate = Select-ExpiryDate $selection.selected_expiry_date $selectedExpiryTsMs
    $fallbackStrikeMismatch = ($null -ne $strikeDistance -and $strikeDistance -gt 0.0)
    $fallbackExpiryMismatch = ($null -ne $targetExpiryTsMs -and $null -ne $selectedExpiryTsMs -and $selectedExpiryTsMs -ne $targetExpiryTsMs)
    $hasStrikeMismatch = Select-MismatchFlag $selection.strike_mismatch $fallbackStrikeMismatch
    $hasExpiryMismatch = Select-MismatchFlag $selection.expiry_mismatch $fallbackExpiryMismatch
    $selectionQuality = Select-SelectionQuality $selection.selection_quality $selection.selected_deribit_instrument $selection.selected_polymarket_market_slug $hasStrikeMismatch $hasExpiryMismatch
    $warningReasons = @()
    if ($hasStrikeMismatch) {
        $warningReasons += "strike_distance > 0"
    }
    if ($hasExpiryMismatch) {
        $warningReasons += "selected_expiry_ts_ms != target_expiry_ts_ms"
    }

    $reportRows += [pscustomobject]@{
        Report = $file.Name
        ProbeOk = @($report.probe_reports | Where-Object { $_.status -eq "ok" }).Count
        ProbeErrors = @($report.probe_reports | Where-Object { $_.status -ne "ok" }).Count
        ParseErrors = $parseErrors.Count
        HttpErrors = $httpErrors.Count
        AcceptedNormalized = $accepted
        MatcherDecisions = $decisions
        Observations = $observations
        MatcherReady = $matcherReady
    }

    $selectionRow = [pscustomobject]@{
        Report = $file.Name
        Quality = $selectionQuality
        DeribitInstrument = Format-OptionalValue $selection.selected_deribit_instrument
        PolymarketMarket = Format-OptionalValue $selection.selected_polymarket_market_slug
        TargetExpiryDate = $targetExpiryDate
        SelectedExpiryDate = $selectedExpiryDate
        StrikeDistance = Format-OptionalValue $strikeDistance
        Warning = if ($warningReasons.Count -gt 0) { $warningReasons -join "; " } else { "" }
    }
    $selectionRows += $selectionRow

    if ($warningReasons.Count -gt 0) {
        $mismatchRows += $selectionRow
    }

    foreach ($payloadShape in @($report.payload_shape_versions)) {
        $payloadShapeRows += [pscustomobject]@{
            Report = $file.Name
            Endpoint = [string]$payloadShape.endpoint
            PayloadShapeVersion = [string]$payloadShape.payload_shape_version
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

Write-Output "Live probe replay summary ($totalReports files)"
Write-Output "Matcher readiness: $readyReports/$totalReports reports ready ($([math]::Round(($readyReports / [double]$totalReports) * 100.0, 2))%)"
Write-Output "Reports with parse errors: $reportsWithParseErrors/$totalReports"
Write-Output "Reports with HTTP errors: $reportsWithHttpErrors/$totalReports"
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
        Write-Output "- $($row.Report): $($row.Warning) (Deribit=$($row.DeribitInstrument), Polymarket=$($row.PolymarketMarket), target_expiry_date=$($row.TargetExpiryDate), selected_expiry_date=$($row.SelectedExpiryDate), strike_distance=$($row.StrikeDistance))"
    }
}

if ($payloadShapeRows.Count -gt 0) {
    Write-Output ""
    Write-Output "Payload Shapes"
    $payloadShapeRows | Format-Table -AutoSize
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
