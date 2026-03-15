# ==================== Infisical Setup Script (Windows) ====================
# Generates secure secrets and starts Infisical Docker Compose
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_infisical.ps1

param(
    [switch]$SkipSecrets
)

$ErrorActionPreference = "Stop"

Write-Host "🔐 CRYPTOTEHNOLOG Infisical Setup" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan

# Check if Docker is running
try {
    docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker is not running"
    }
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $ProjectRoot ".env.infisical"

if (-not $SkipSecrets) {
    Write-Host "📝 Generating secure secrets..." -ForegroundColor Yellow

    # Generate secrets using Python (use 'python' on Windows)
    # ENCRYPTION_KEY: 32 bytes = 64 hex characters
    # AUTH_SECRET: 32 bytes = base64 encoded (required by Infisical!)
    $ENCRYPTION_KEY = python -c "import secrets; print(secrets.token_hex(32))"
    $AUTH_SECRET = python -c "import secrets; print(secrets.token_urlsafe(32))"
    $DB_PASSWORD = python -c "import secrets; print(secrets.token_hex(32))"

    # Create .env file
    Write-Host "📄 Creating .env.infisical file..." -ForegroundColor Yellow

    @"
# Infisical Secrets - DO NOT COMMIT TO VERSION CONTROL!
# Generated automatically on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

# Database password (32 bytes hex = 64 characters)
DB_PASSWORD=$DB_PASSWORD

# Encryption key for data at rest (32 bytes hex = 64 characters)
ENCRYPTION_KEY=$ENCRYPTION_KEY

# Auth secret for JWT tokens (32 bytes hex = 64 characters)
AUTH_SECRET=$AUTH_SECRET
"@ | Out-File -FilePath $EnvFile -Encoding UTF8

    Write-Host "✅ Secrets generated and saved to .env.infisical" -ForegroundColor Green
} else {
    if (-not (Test-Path $EnvFile)) {
        Write-Host "❌ .env.infisical not found. Run without -SkipSecrets first." -ForegroundColor Red
        exit 1
    }
    Write-Host "📄 Using existing .env.infisical file..." -ForegroundColor Yellow
}

# Load environment variables
Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], [System.EnvironmentVariableTarget]::Process)
    }
}

# Start Infisical
Write-Host "🚀 Starting Infisical Docker Compose..." -ForegroundColor Yellow
Set-Location $ProjectRoot
docker-compose --env-file $EnvFile -f docker-compose-infisical.yml up -d

# Wait for Infisical to be ready
Write-Host "⏳ Waiting for Infisical to initialize..." -ForegroundColor Yellow
$MaxRetries = 30
$RetryCount = 0

while ($RetryCount -lt $MaxRetries) {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8080/api/status" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ Infisical is ready!" -ForegroundColor Green
            Write-Host ""
            Write-Host "========================================" -ForegroundColor Cyan
            Write-Host "🎉 Infisical setup complete!" -ForegroundColor Green
            Write-Host "========================================" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "📍 Access Infisical UI:" -ForegroundColor White
            Write-Host "   http://127.0.0.1:8080" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "📁 Secrets file:" -ForegroundColor White
            Write-Host "   $EnvFile" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "⚠️  IMPORTANT:" -ForegroundColor Red
            Write-Host "   - NEVER commit .env.infisical to version control" -ForegroundColor White
            Write-Host "   - Add .env.infisical to .gitignore" -ForegroundColor White
            Write-Host "   - Backup this file securely" -ForegroundColor White
            Write-Host ""
            Write-Host "🔧 Next steps:" -ForegroundColor White
            Write-Host "   1. Open http://127.0.0.1:8080" -ForegroundColor Yellow
            Write-Host "   2. Create admin account" -ForegroundColor Yellow
            Write-Host "   3. Create project: crypto-trading" -ForegroundColor Yellow
            Write-Host "   4. Create environments: development, staging, production" -ForegroundColor Yellow
            Write-Host "   5. Add secrets:" -ForegroundColor Yellow
            Write-Host "      - /crypto/exchange/bybit/api_key" -ForegroundColor Gray
            Write-Host "      - /crypto/exchange/bybit/api_secret" -ForegroundColor Gray
            Write-Host "      - /telegram/bot_token" -ForegroundColor Gray
            Write-Host "   6. Create Machine Identity for bot access" -ForegroundColor Yellow
            Write-Host ""
            exit 0
        }
    } catch {
        # Continue waiting
    }
    $RetryCount++
    Write-Host "   Waiting... ($RetryCount/$MaxRetries)" -ForegroundColor Gray
    Start-Sleep -Seconds 2
}

Write-Host "❌ Infisical failed to start within expected time" -ForegroundColor Red
Write-Host "   Check logs: docker-compose -f docker-compose-infisical.yml logs" -ForegroundColor Yellow
exit 1
