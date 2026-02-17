# ==================== CRYPTOTEHNOLOG Environment Check Script ====================
# PowerShell script to verify all required tools are installed and configured

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CRYPTOTEHNOLOG Environment Check" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$allPassed = $true

# Function to check if a command exists
function Test-Command {
    param([string]$Command)

    try {
        $null = Get-Command $Command -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

# Function to display check result
function Show-CheckResult {
    param(
        [string]$Name,
        [bool]$Passed,
        [string]$Version = ""
    )

    if ($Passed) {
        Write-Host "✅ $Name" -ForegroundColor Green
        if ($Version) {
            Write-Host "   Version: $Version" -ForegroundColor Gray
        }
    }
    else {
        Write-Host "❌ $Name - NOT FOUND" -ForegroundColor Red
        $script:allPassed = $false
    }
}

# Check Python
Write-Host "Checking Python..." -ForegroundColor Yellow
$pythonInstalled = Test-Command "python"
if ($pythonInstalled) {
    $pythonVersion = python --version 2>&1
    Show-CheckResult "Python" $true $pythonVersion
}
else {
    Show-CheckResult "Python" $false
}

# Check Pip
Write-Host "`nChecking Pip..." -ForegroundColor Yellow
$pipInstalled = Test-Command "pip"
if ($pipInstalled) {
    $pipVersion = pip --version 2>&1
    Show-CheckResult "Pip" $true $pipVersion
}
else {
    Show-CheckResult "Pip" $false
}

# Check Rust
Write-Host "`nChecking Rust..." -ForegroundColor Yellow
$rustcInstalled = Test-Command "rustc"
if ($rustcInstalled) {
    $rustVersion = rustc --version 2>&1
    Show-CheckResult "Rust (rustc)" $true $rustVersion
}
else {
    Show-CheckResult "Rust (rustc)" $false
}

$cargoInstalled = Test-Command "cargo"
if ($cargoInstalled) {
    $cargoVersion = cargo --version 2>&1
    Show-CheckResult "Rust (cargo)" $true $cargoVersion
}
else {
    Show-CheckResult "Rust (cargo)" $false
}

# Check Docker
Write-Host "`nChecking Docker..." -ForegroundColor Yellow
$dockerInstalled = Test-Command "docker"
if ($dockerInstalled) {
    $dockerVersion = docker --version 2>&1
    Show-CheckResult "Docker" $true $dockerVersion
}
else {
    Show-CheckResult "Docker" $false
}

# Check Docker Compose
Write-Host "`nChecking Docker Compose..." -ForegroundColor Yellow
$dockerComposeInstalled = Test-Command "docker-compose"
if ($dockerComposeInstalled) {
    $dockerComposeVersion = docker-compose --version 2>&1
    Show-CheckResult "Docker Compose" $true $dockerComposeVersion
}
else {
    Show-CheckResult "Docker Compose" $false
}

# Check Git
Write-Host "`nChecking Git..." -ForegroundColor Yellow
$gitInstalled = Test-Command "git"
if ($gitInstalled) {
    $gitVersion = git --version 2>&1
    Show-CheckResult "Git" $true $gitVersion
}
else {
    Show-CheckResult "Git" $false
}

# Check Make (if available)
Write-Host "`nChecking Make..." -ForegroundColor Yellow
$makeInstalled = Test-Command "make"
if ($makeInstalled) {
    $makeVersion = make --version 2>&1 | Select-Object -First 1
    Show-CheckResult "Make" $true $makeVersion
}
else {
    Write-Host "⚠️  Make - NOT FOUND (optional, can use PowerShell commands)" -ForegroundColor Yellow
}

# Check Python packages (if venv exists)
Write-Host "`nChecking Python packages..." -ForegroundColor Yellow
$venvExists = Test-Path "venv"
if ($venvExists) {
    Write-Host "Virtual environment found. Checking packages..." -ForegroundColor Gray

    # Activate venv and check packages
    $packages = @("pydantic", "pytest", "black", "mypy", "ruff", "redis", "asyncpg")
    foreach ($pkg in $packages) {
        $installed = pip show $pkg 2>&1
        if ($LASTEXITCODE -eq 0) {
            Show-CheckResult "Python package: $pkg" $true
        }
        else {
            Show-CheckResult "Python package: $pkg" $false
        }
    }
}
else {
    Write-Host "⚠️  Virtual environment not found. Run 'make setup-env' first." -ForegroundColor Yellow
}

# Check Docker services (if running)
Write-Host "`nChecking Docker services..." -ForegroundColor Yellow
$redisRunning = docker ps --filter "name=crypto_redis" --format "{{.Names}}" 2>&1
if ($redisRunning -eq "crypto_redis") {
    Show-CheckResult "Redis (Docker)" $true "Running"
}
else {
    Write-Host "⚠️  Redis (Docker) - Not running" -ForegroundColor Yellow
}

$postgresRunning = docker ps --filter "name=crypto_timescale" --format "{{.Names}}" 2>&1
if ($postgresRunning -eq "crypto_timescale") {
    Show-CheckResult "PostgreSQL (Docker)" $true "Running"
}
else {
    Write-Host "⚠️  PostgreSQL (Docker) - Not running" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Environment Check Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if ($allPassed) {
    Write-Host "✅ All required tools are installed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Create virtual environment: python -m venv venv" -ForegroundColor White
    Write-Host "2. Activate venv: .\venv\Scripts\Activate.ps1" -ForegroundColor White
    Write-Host "3. Install dependencies: pip install -r requirements.txt" -ForegroundColor White
    Write-Host "4. Start Docker services: docker-compose up -d" -ForegroundColor White
    Write-Host "5. Run tests: pytest tests/" -ForegroundColor White
}
else {
    Write-Host "❌ Some required tools are missing!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install the missing tools:" -ForegroundColor Yellow
    Write-Host "- Python 3.11+: https://www.python.org/downloads/" -ForegroundColor White
    Write-Host "- Rust: https://rustup.rs/" -ForegroundColor White
    Write-Host "- Docker Desktop: https://www.docker.com/products/docker-desktop" -ForegroundColor White
    Write-Host "- Git: https://git-scm.com/downloads" -ForegroundColor White
}

Write-Host ""
exit 0
