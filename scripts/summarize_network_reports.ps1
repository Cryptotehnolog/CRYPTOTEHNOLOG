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
            ErrorKind = if ($null -eq $entry.error_kind) { "" } else { [string]$entry.error_kind }
        }
    }
}

$summary = foreach ($group in ($rows | Group-Object Endpoint)) {
    $ordered = @($group.Group | Sort-Object Report)
    $latency = $ordered | Measure-Object -Property LatencyMs -Average -Minimum -Maximum
    $total = $ordered.Count
    $ok = @($ordered | Where-Object { $_.Status -eq "ok" }).Count
    $errors = $total - $ok
    $firstLatency = $ordered[0].LatencyMs
    $lastLatency = $ordered[$ordered.Count - 1].LatencyMs

    [pscustomobject]@{
        Endpoint = $group.Name
        Reports = $total
        Ok = $ok
        Errors = $errors
        ErrorRatePct = [math]::Round(($errors / [double]$total) * 100.0, 2)
        AvgLatencyMs = [math]::Round($latency.Average, 2)
        MinLatencyMs = [math]::Round($latency.Minimum, 2)
        MaxLatencyMs = [math]::Round($latency.Maximum, 2)
        LastMinusFirstLatencyMs = [math]::Round($lastLatency - $firstLatency, 2)
    }
}

Write-Output "Network connectivity report summary ($($files.Count) files)"
$summary | Format-Table -AutoSize
