$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$pricingModelPath = "crates/common/src/probability_basis.rs"

function Test-GitRefExists {
    param([string]$Ref)

    git rev-parse --verify --quiet $Ref *> $null
    return $LASTEXITCODE -eq 0
}

Push-Location $root
try {
    $workingTreeChangedFiles = @(git diff --name-only HEAD)

    if ($workingTreeChangedFiles.Count -gt 0) {
        $changedFiles = $workingTreeChangedFiles
        $pricingDiff = @(git diff --unified=0 HEAD -- $pricingModelPath)
    }
    elseif (Test-GitRefExists -Ref "HEAD^") {
        $changedFiles = @(git diff --name-only HEAD^ HEAD)
        $pricingDiff = @(git diff --unified=0 HEAD^ HEAD -- $pricingModelPath)
    }
    else {
        Write-Output "Pricing model fixture policy check skipped: no parent commit available."
        return
    }

    $pricingVersionChanged = $pricingDiff | Where-Object {
        $_ -match '^[+-].*PRICING_MODEL_VERSION' -and
        $_ -notmatch '^\+\+\+' -and
        $_ -notmatch '^---'
    }

    if ($pricingVersionChanged.Count -eq 0) {
        Write-Output "Pricing model fixture policy check passed: PRICING_MODEL_VERSION unchanged."
        return
    }

    $updatedGoldenReports = $changedFiles | Where-Object {
        $_ -match '^fixtures/probability_basis/.+_report\.(json|txt)$'
    }

    if ($updatedGoldenReports.Count -eq 0) {
        Write-Output "Detected PRICING_MODEL_VERSION change:"
        $pricingVersionChanged | ForEach-Object { Write-Output "  $_" }
        throw "PRICING_MODEL_VERSION changed without updating replay golden report fixtures. Run scripts\update_golden_fixture.ps1 and commit the fixture changes with the model version change."
    }

    Write-Output "Pricing model fixture policy check passed. Updated golden reports:"
    $updatedGoldenReports | ForEach-Object { Write-Output "  $_" }
}
finally {
    Pop-Location
}
