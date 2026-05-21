$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$reportPath = Join-Path $root "fixtures\probability_basis\mid_edge_false_positive_report.json"

if (-not (Test-Path -LiteralPath $reportPath)) {
    throw "Missing midpoint false-positive replay report: $reportPath"
}

$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json

if (-not $report.summary) {
    throw "Replay report has no summary: $reportPath"
}

if ($null -eq $report.summary.midpoint_false_positive_count) {
    throw "Replay summary must expose midpoint_false_positive_count: $reportPath"
}

$count = [int]$report.summary.midpoint_false_positive_count
if ($count -lt 1) {
    throw "Expected midpoint_false_positive_count >= 1 for dedicated false-positive scenario, got $count"
}

Write-Output "Midpoint false-positive report check passed: midpoint_false_positive_count=$count"
