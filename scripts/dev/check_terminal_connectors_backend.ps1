param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Test-Listener8000 {
    $lines = netstat -ano | findstr ":8000"
    if (-not $lines) {
        return @{
            Listening = $false
            Raw = $null
        }
    }

    $listeningLine = $lines | Where-Object { $_ -match "LISTENING" } | Select-Object -First 1
    if (-not $listeningLine) {
        return @{
            Listening = $false
            Raw = ($lines | Select-Object -First 1)
        }
    }

    return @{
        Listening = $true
        Raw = $listeningLine.Trim()
    }
}

function Test-Endpoint {
    param(
        [string]$Path
    )

    $url = "$BaseUrl$Path"
    try {
        $response = Invoke-WebRequest -UseBasicParsing $url
        return @{
            Path = $Path
            Url = $url
            Outcome = [string]$response.StatusCode
            Detail = "OK"
        }
    }
    catch {
        $statusCode = $null
        try {
            if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
                $statusCode = [int]$_.Exception.Response.StatusCode
            }
        }
        catch {
            $statusCode = $null
        }

        $message = $_.Exception.Message
        if ($message -match "Unable to connect|Невозможно соединиться|connection refused") {
            $message = "connection refused"
        }

        return @{
            Path = $Path
            Url = $url
            Outcome = if ($statusCode -ne $null) { [string]$statusCode } else { "error" }
            Detail = $message
        }
    }
}

$listener = Test-Listener8000
$checks = @(
    Test-Endpoint -Path "/dashboard/settings/bybit-spot-product-snapshot"
    Test-Endpoint -Path "/dashboard/settings/bybit-spot-connector-diagnostics"
    Test-Endpoint -Path "/dashboard/settings/bybit-connector-diagnostics"
)

Write-Output ("listener 127.0.0.1:8000 = {0}" -f ($(if ($listener.Listening) { "yes" } else { "no" })))
if ($listener.Raw) {
    Write-Output ("listener detail = {0}" -f $listener.Raw)
}

foreach ($check in $checks) {
    Write-Output ("{0} = {1} ({2})" -f $check.Path, $check.Outcome, $check.Detail)
}
