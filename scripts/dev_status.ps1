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

function Get-GitHubRepoSlug {
    $remoteUrl = git remote get-url origin 2>$null
    if ([string]::IsNullOrWhiteSpace($remoteUrl)) {
        return $null
    }

    if ($remoteUrl -match "github\.com[:/](?<owner>[^/]+)/(?<repo>[^/.]+)(\.git)?$") {
        return "$($matches.owner)/$($matches.repo)"
    }

    return $null
}

function Get-LatestGitHubActionsStatus {
    param([string]$RepoSlug)

    if ([string]::IsNullOrWhiteSpace($RepoSlug)) {
        return "Latest GitHub Actions: unavailable (origin is not a GitHub repository)."
    }

    $headers = @{
        "User-Agent" = "CRYPTOTEHNOLOG-dev-status"
        "Accept" = "application/vnd.github+json"
    }

    if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) {
        $headers["Authorization"] = "Bearer $env:GITHUB_TOKEN"
    }

    try {
        $uri = "https://api.github.com/repos/$RepoSlug/actions/runs?branch=main&per_page=1"
        $response = Invoke-RestMethod -Uri $uri -Headers $headers -TimeoutSec 5
        if ($response.total_count -lt 1 -or $response.workflow_runs.Count -lt 1) {
            return "Latest GitHub Actions: unavailable (no workflow runs found for main)."
        }

        $run = $response.workflow_runs[0]
        $shortSha = $run.head_sha.Substring(0, 7)
        $result = if ($null -eq $run.conclusion) { $run.status } else { "$($run.status)/$($run.conclusion)" }
        $statusLine = "Latest GitHub Actions: $result on main ($shortSha, $($run.display_title))"
        if ($result -ne "completed/success") {
            return "$statusLine`nWARNING: latest GitHub Actions status is not completed/success."
        }

        return $statusLine
    }
    catch {
        return "Latest GitHub Actions: unavailable ($($_.Exception.Message)). If running inside Codex sandbox, GitHub API may be unavailable without explicit network approval. Public repos usually work without a token; for rate limits or private repos set GITHUB_TOKEN with read-only repository Actions/Metadata access."
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
        if (Test-Path ".git") {
            $repoSlug = Get-GitHubRepoSlug
            Write-Output (Get-LatestGitHubActionsStatus -RepoSlug $repoSlug)
        }
        else {
            Write-Output "Latest GitHub Actions: unavailable (not a Git working tree)."
        }
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

    Write-Section "Advisory Skills"
    $rustSkillsPath = Join-Path $env:USERPROFILE ".codex\skills\rust-skills\SKILL.md"
    if (Test-Path $rustSkillsPath) {
        Write-Output "rust-skills: present ($rustSkillsPath)"
    }
    else {
        Write-Output "rust-skills: missing (optional advisory review tool)"
        Write-Output "Install example: git clone https://github.com/leonardomso/rust-skills.git `"$env:USERPROFILE\.codex\skills\rust-skills`""
    }

    Write-Section "Fast Checks"
    Write-Output "Run: .\scripts\check_all.ps1"
}
finally {
    Pop-Location
}
