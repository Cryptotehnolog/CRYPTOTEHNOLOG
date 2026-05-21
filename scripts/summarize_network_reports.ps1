param(
    [string]$ReportsGlob = "artifacts\network_connectivity_report*.json"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

if (-not [System.IO.Path]::IsPathRooted($ReportsGlob)) {
    $ReportsGlob = Join-Path $root $ReportsGlob
}

$files = @(Get-ChildItem -Path $ReportsGlob -File | Sort-Object FullName)
if ($files.Count -eq 0) {
    throw "No network connectivity reports found for pattern: $ReportsGlob"
}

$rows = @()
foreach ($file in $files) {
    $entries = Get-Content $file.FullName -Raw | ConvertFrom-Json
    foreach ($entry in $entries) {
        $rows += [pscustomobject]@{
            Report = $file.Name
            Endpoint = [string]$entry.endpoint
            Status = [string]$entry.status
            PayloadBytes = [int]$entry.payload_bytes
            LatencyMs = [double]$entry.latency_ms
            Attempts = if ($null -eq $entry.attempts) { 1 } else { [int]$entry.attempts }
            ErrorKind = if ($null -eq $entry.error_kind) { "" } else { [string]$entry.error_kind }
        }
    }
}

$summary = foreach ($group in ($rows | Group-Object Endpoint)) {
    $ordered = @($group.Group | Sort-Object Report)
    $latency = $ordered | Measure-Object -Property LatencyMs -Average -Minimum -Maximum
    $total = $ordered.Count
    $ok = @($ordered | Where-Object { $_.Status -eq "ok" }).Count
    $transient = @($ordered | Where-Object { $_.Status -eq "transient_http_failure" }).Count
    $errors = $total - $ok
    $attempts = $ordered | Measure-Object -Property Attempts -Average -Maximum
    $firstLatency = $ordered[0].LatencyMs
    $lastLatency = $ordered[$ordered.Count - 1].LatencyMs

    [pscustomobject]@{
        Endpoint = $group.Name
        Reports = $total
        Ok = $ok
        TransientHttpFailures = $transient
        Errors = $errors
        ErrorRatePct = [math]::Round(($errors / [double]$total) * 100.0, 2)
        AvgAttempts = [math]::Round($attempts.Average, 2)
        MaxAttempts = [int]$attempts.Maximum
        AvgLatencyMs = [math]::Round($latency.Average, 2)
        MinLatencyMs = [math]::Round($latency.Minimum, 2)
        MaxLatencyMs = [math]::Round($latency.Maximum, 2)
        LastMinusFirstLatencyMs = [math]::Round($lastLatency - $firstLatency, 2)
    }
}

Write-Output "Network connectivity report summary ($($files.Count) files)"
$summary | Format-Table -AutoSize
