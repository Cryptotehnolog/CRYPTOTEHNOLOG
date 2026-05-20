$ErrorActionPreference = "Stop"

function Normalize-ManifestPathKey {
    param([Parameter(Mandatory = $true)][string]$Path)

    return $Path.Replace("/", "\").ToLowerInvariant()
}

function Read-SimpleScenarioManifest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ManifestPath,

        [Parameter(Mandatory = $true)]
        [string[]]$RequiredFields,

        [string[]]$IntegerFields = @(),

        [Parameter(Mandatory = $true)]
        [string]$ManifestLabel
    )

    if (-not (Test-Path $ManifestPath)) {
        throw "Missing ${ManifestLabel} manifest: $ManifestPath"
    }

    $scenarios = @()
    $current = [ordered]@{}

    foreach ($line in Get-Content $ManifestPath) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith("#")) {
            continue
        }

        if ($trimmed -eq "[[scenario]]") {
            if ($current.Count -gt 0) {
                $scenarios += [pscustomobject]$current
                $current = [ordered]@{}
            }
            continue
        }

        if ($trimmed -match '^([A-Za-z_]+)\s*=\s*"([^"]*)"\s*$') {
            $current[$matches[1]] = $matches[2]
            continue
        }

        if ($trimmed -match '^([A-Za-z_]+)\s*=\s*([0-9]+)\s*$') {
            $key = $matches[1]
            if ($IntegerFields -notcontains $key) {
                throw "Unsupported ${ManifestLabel} manifest integer field: $line"
            }
            $current[$key] = [int]$matches[2]
            continue
        }

        throw "Unsupported ${ManifestLabel} manifest line: $line"
    }

    if ($current.Count -gt 0) {
        $scenarios += [pscustomobject]$current
    }

    if ($scenarios.Count -eq 0) {
        throw "$ManifestLabel manifest contains no scenarios."
    }

    foreach ($scenario in $scenarios) {
        foreach ($field in $RequiredFields) {
            if (-not $scenario.PSObject.Properties[$field]) {
                throw "$ManifestLabel scenario is missing required field: $field"
            }
        }
    }

    return $scenarios
}

function Assert-ManifestUniqueValues {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Scenarios,

        [Parameter(Mandatory = $true)]
        [string[]]$PathFields,

        [Parameter(Mandatory = $true)]
        [string]$ManifestLabel
    )

    $names = @{}
    $paths = @{}

    foreach ($scenario in $Scenarios) {
        $nameKey = $scenario.name.ToLowerInvariant()
        if ($names.ContainsKey($nameKey)) {
            throw "$ManifestLabel manifest has duplicate scenario name: $($scenario.name)"
        }
        $names[$nameKey] = $true

        foreach ($field in $PathFields) {
            $rawPath = $scenario.$field
            $pathKey = Normalize-ManifestPathKey -Path $rawPath
            if ($paths.ContainsKey($pathKey)) {
                throw "$ManifestLabel manifest has duplicate path `$rawPath` in scenario $($scenario.name)."
            }
            $paths[$pathKey] = $true
        }
    }
}
