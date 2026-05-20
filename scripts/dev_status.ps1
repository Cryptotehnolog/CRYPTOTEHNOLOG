$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

function Write-Section {
    param([string] $Title)
    Write-Output ""
    Write-Output "== $Title =="
}

function Get-CommandVersion {
    param(
        [string] $Command,
        [string[]] $Arguments
    )

    $cmd = Get-Command $Command -ErrorAction SilentlyContinue
    if ($null -eq $cmd) {
        return "${Command}: not installed"
    }

    try {
        $output = & $Command @Arguments 2>&1 | Select-Object -First 1
        return "${Command}: $output"
    }
    catch {
        return "${Command}: failed to read version ($($_.Exception.Message))"
    }
}

Push-Location $root
try {
    Write-Output "CRYPTOTEHNOLOG development status"
    Write-Output "Root: $root"

    Write-Section "Git"
    if (Test-Path ".git") {
        $branch = git branch --show-current
        $status = git status --short
        $lastCommit = git log --oneline -1

        Write-Output "Branch: $branch"
        Write-Output "Last commit: $lastCommit"
        if ([string]::IsNullOrWhiteSpace($status)) {
            Write-Output "Working tree: clean"
        }
        else {
            Write-Output "Working tree:"
            $status | ForEach-Object { Write-Output "  $_" }
        }
    }
    else {
        Write-Output "Not a Git working tree."
    }

    Write-Section "Remote"
    if (Test-Path ".git") {
        $remotes = git remote -v
        if ([string]::IsNullOrWhiteSpace($remotes)) {
            Write-Output "No Git remotes configured."
        }
        else {
            $remotes | ForEach-Object { Write-Output $_ }
        }
    }

    Write-Section "CI"
    $ciPath = Join-Path $root ".github\workflows\ci.yml"
    if (Test-Path $ciPath) {
        Write-Output "GitHub Actions workflow: present (.github/workflows/ci.yml)"
        Write-Output "Hint: check the Actions tab after each push."
    }
    else {
        Write-Output "GitHub Actions workflow: missing"
    }

    Write-Section "Git Hooks"
    $preCommit = Join-Path $root ".git\hooks\pre-commit"
    if (Test-Path $preCommit) {
        Write-Output "pre-commit hook: installed"
    }
    else {
        Write-Output "pre-commit hook: missing"
        Write-Output "Install with: .\scripts\install_hooks.ps1"
    }

    Write-Section "Tool Versions"
    Write-Output (Get-CommandVersion -Command "rustc" -Arguments @("--version"))
    Write-Output (Get-CommandVersion -Command "cargo" -Arguments @("--version"))
    Write-Output (Get-CommandVersion -Command "uv" -Arguments @("--version"))
    Write-Output (Get-CommandVersion -Command "git" -Arguments @("--version"))

    Write-Section "Fast Checks"
    Write-Output "Run: .\scripts\check_all.ps1"
}
finally {
    Pop-Location
}
