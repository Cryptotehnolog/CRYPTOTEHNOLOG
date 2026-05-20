param(
    [string]$ReportsGlob = "artifacts\live_probe_replay_report*.json"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

if (-not [System.IO.Path]::IsPathRooted($ReportsGlob)) {
    $ReportsGlob = Join-Path $root $ReportsGlob
}

$files = @(Get-ChildItem -Path $ReportsGlob -File | Sort-Object FullName)
if ($files.Count -eq 0) {
    throw "No live probe replay reports found for pattern: $ReportsGlob"
}

$reportRows = @()
$errorRows = @()
foreach ($file in $files) {
    $report = Get-Content $file.FullName -Raw | ConvertFrom-Json
    $errors = @($report.errors)
    $parseErrors = @($errors | Where-Object { $_.stage -eq "parse" })
    $httpErrors = @($errors | Where-Object { $_.stage -eq "http" })
    $payloadShapes = @($report.payload_shape_versions | ForEach-Object { "$($_.endpoint)=$($_.payload_shape_version)" })
    $selection = $report.selection_report
    $accepted = [int]$report.ingestion_report.total_normalized_events_accepted
    $decisions = [int]$report.replay_summary.decisions
    $observations = [int]$report.replay_summary.observations
    $matcherReady = ($accepted -ge 2 -and $decisions -gt 0)

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
        PayloadShapes = ($payloadShapes -join ";")
        SelectedDeribit = [string]$selection.selected_deribit_instrument
        SelectedPolymarket = [string]$selection.selected_polymarket_market_slug
        StrikeDistance = if ($null -eq $selection.strike_distance) { "" } else { [string]$selection.strike_distance }
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
