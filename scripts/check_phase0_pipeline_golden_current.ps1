$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$expectedReportPath = Join-Path $root "fixtures\phase0_pipeline\golden_report.json"

function Normalize-Newlines {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    return $Value.Replace("`r`n", "`n").Trim()
}

Push-Location $root
try {
    if (-not (Test-Path -LiteralPath $expectedReportPath)) {
        throw "Missing Phase 0 pipeline golden report: $expectedReportPath"
    }

    $before = Normalize-Newlines (Get-Content -LiteralPath $expectedReportPath -Raw)

    .\scripts\update_phase0_pipeline_golden.ps1

    $after = Normalize-Newlines (Get-Content -LiteralPath $expectedReportPath -Raw)

    if ($before -ne $after) {
        Write-Output "Phase 0 pipeline golden report is stale. Run scripts\update_phase0_pipeline_golden.ps1 and review the diff."
        throw "Phase 0 pipeline golden report check failed."
    }

    Write-Output "Phase 0 pipeline golden report is current."
}
finally {
    Pop-Location
}
