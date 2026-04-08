Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Clear-BrokenLocalProxyEnv {
    $proxyVarNames = @(
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy"
    )
    $brokenProxyTargets = @(
        "http://127.0.0.1:9",
        "https://127.0.0.1:9",
        "http://localhost:9",
        "https://localhost:9",
        "http://[::1]:9",
        "https://[::1]:9"
    )

    foreach ($proxyVarName in $proxyVarNames) {
        $proxyValue = [Environment]::GetEnvironmentVariable($proxyVarName)
        if ([string]::IsNullOrWhiteSpace($proxyValue)) {
            continue
        }
        if ($brokenProxyTargets -contains $proxyValue.Trim().ToLowerInvariant()) {
            Set-Item -Path ("Env:{0}" -f $proxyVarName) -Value ""
        }
    }
}

$env:ENVIRONMENT = "test"
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_USER = "bot_user"
$env:POSTGRES_PASSWORD = "bot_password_dev"
$env:POSTGRES_DB = "trading_dev"
$env:PYTHONPATH = "src"
Clear-BrokenLocalProxyEnv

Set-Location "D:\CRYPTOTEHNOLOG"
& ".\.venv\Scripts\python.exe" -m cryptotechnolog.dashboard
