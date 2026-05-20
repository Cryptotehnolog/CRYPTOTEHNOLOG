$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root "fixtures\ingestion\manifest.toml"
. (Join-Path $PSScriptRoot "lib\ingestion_manifest.ps1")

function Normalize-Newlines {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    return $Value.Replace("`r`n", "`n").Trim()
}

Push-Location $root
try {
    $scenarios = @(Get-IngestionFixtureScenarios -Root $root -ManifestPath $manifestPath)
    $before = @{}

    foreach ($scenario in $scenarios) {
        if (-not (Test-Path $scenario.ExpectedReportPath)) {
            throw "Missing ingestion golden report for scenario $($scenario.name): $($scenario.ExpectedReportPath)"
        }

        $before[$scenario.ExpectedReportPath] = Normalize-Newlines (Get-Content $scenario.ExpectedReportPath -Raw)
    }

    .\scripts\update_ingestion_golden.ps1

    foreach ($scenario in $scenarios) {
        $after = Normalize-Newlines (Get-Content $scenario.ExpectedReportPath -Raw)

        if ($before[$scenario.ExpectedReportPath] -ne $after) {
            Write-Output "Ingestion golden report is stale for scenario $($scenario.name). Run scripts\update_ingestion_golden.ps1 and review the diff."
            throw "Ingestion golden report check failed."
        }
    }

    Write-Output "Ingestion golden reports are current."
}
finally {
    Pop-Location
}
