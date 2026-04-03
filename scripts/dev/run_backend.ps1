$env:ENVIRONMENT = "test"
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_USER = "bot_user"
$env:POSTGRES_PASSWORD = "bot_password_dev"
$env:POSTGRES_DB = "trading_dev"

Set-Location "D:\CRYPTOTEHNOLOG"
& ".\.venv\Scripts\python.exe" -m cryptotechnolog.dashboard
