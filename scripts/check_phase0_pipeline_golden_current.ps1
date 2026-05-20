$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root "fixtures\phase0_pipeline\manifest.toml"
. (Join-Path $PSScriptRoot "lib\phase0_pipeline_manifest.ps1")

function Normalize-Newlines {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    return $Value.Replace("`r`n", "`n").Trim()
}

Push-Location $root
try {
    $scenarios = @(Get-Phase0PipelineFixtureScenarios -Root $root -ManifestPath $manifestPath)
    $before = @{}

    foreach ($scenario in $scenarios) {
        if (-not (Test-Path -LiteralPath $scenario.ExpectedReportPath)) {
            throw "Missing Phase 0 pipeline golden report for scenario $($scenario.name): $($scenario.ExpectedReportPath)"
        }

        $before[$scenario.ExpectedReportPath] = Normalize-Newlines (Get-Content -LiteralPath $scenario.ExpectedReportPath -Raw)
    }

    .\scripts\update_phase0_pipeline_golden.ps1

    foreach ($scenario in $scenarios) {
        $after = Normalize-Newlines (Get-Content -LiteralPath $scenario.ExpectedReportPath -Raw)

        if ($before[$scenario.ExpectedReportPath] -ne $after) {
            Write-Output "Phase 0 pipeline golden report is stale for scenario $($scenario.name). Run scripts\update_phase0_pipeline_golden.ps1 and review the diff."
            throw "Phase 0 pipeline golden report check failed."
        }
    }

    Write-Output "Phase 0 pipeline golden reports are current."
}
finally {
    Pop-Location
}
