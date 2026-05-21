param(
    [string]$ReportDir = "fixtures\probability_basis"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$reportRoot = if ([System.IO.Path]::IsPathRooted($ReportDir)) {
    $ReportDir
} else {
    Join-Path $root $ReportDir
}

if (-not (Test-Path -LiteralPath $reportRoot)) {
    throw "Replay report directory not found: $reportRoot"
}

function Read-JsonFile {
    param([string]$Path)
    return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json)
}

function Select-EdgeBelowThresholdCount {
    param($Report)

    if ($Report.summary.edge_quality -and $Report.summary.edge_quality.PSObject.Properties["edge_below_threshold_count"]) {
        return [int]$Report.summary.edge_quality.edge_below_threshold_count
    }

    $count = 0
    foreach ($rejection in $Report.summary.rejection_counts) {
        if ($rejection.reason -eq "EdgeBelowThreshold") {
            $count += [int]$rejection.count
        }
    }
    return $count
}

function Select-MidpointFalsePositiveCount {
    param($Report)

    if ($Report.summary.edge_quality -and $Report.summary.edge_quality.PSObject.Properties["midpoint_false_positive_count"]) {
        return [int]$Report.summary.edge_quality.midpoint_false_positive_count
    }
    if ($Report.summary.PSObject.Properties["midpoint_false_positive_count"]) {
        return [int]$Report.summary.midpoint_false_positive_count
    }
    return 0
}

$rows = @()
$files = Get-ChildItem -LiteralPath $reportRoot -Filter "*_report.json" -File | Sort-Object Name
foreach ($file in $files) {
    $report = Read-JsonFile -Path $file.FullName
    $matched = [int]$report.summary.matched_count
    $edgeBelow = Select-EdgeBelowThresholdCount -Report $report
    $midpointFalsePositive = Select-MidpointFalsePositiveCount -Report $report
    $decisionTotal = $matched + $edgeBelow + $midpointFalsePositive
    $midpointFalsePositiveRate = if ($decisionTotal -gt 0) {
        [math]::Round($midpointFalsePositive / $decisionTotal, 6)
    } else {
        0
    }

    $rows += [pscustomobject]@{
        Report = $file.Name
        Matched = $matched
        EdgeBelowThreshold = $edgeBelow
        MidpointFalsePositive = $midpointFalsePositive
        MidpointFalsePositiveRate = $midpointFalsePositiveRate
    }
}

if ($rows.Count -eq 0) {
    Write-Output "No replay JSON reports found in $reportRoot"
    exit 0
}

$totalMatched = ($rows | Measure-Object -Property Matched -Sum).Sum
$totalEdgeBelow = ($rows | Measure-Object -Property EdgeBelowThreshold -Sum).Sum
$totalMidpointFalsePositive = ($rows | Measure-Object -Property MidpointFalsePositive -Sum).Sum
$totalDecisionQuality = $totalMatched + $totalEdgeBelow + $totalMidpointFalsePositive
$totalRate = if ($totalDecisionQuality -gt 0) {
    [math]::Round($totalMidpointFalsePositive / $totalDecisionQuality, 6)
} else {
    0
}

Write-Output "Replay edge quality summary"
Write-Output "ReportDir: $reportRoot"
Write-Output ""
$rows | Format-Table -AutoSize | Out-String -Width 240 | Write-Output
Write-Output "Totals: matched=$totalMatched edge_below_threshold=$totalEdgeBelow midpoint_false_positive=$totalMidpointFalsePositive midpoint_false_positive_rate=$totalRate"
