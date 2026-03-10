#
# GitHub Token Helper - Standalone PowerShell implementation
#
# TOKEN PRECEDENCE RULES (AUTHORITATIVE):
# ======================================
# 1. GitHub Models: GITHUB_TOKEN > GITHUB_APM_PAT
# 2. APM Modules: GITHUB_APM_PAT > GITHUB_TOKEN
#
# CRITICAL: Never overwrite existing GITHUB_TOKEN (Models access)
#

# Setup GitHub tokens with proper precedence and preservation
function Initialize-GitHubToken {
    param(
        [switch]$Quiet
    )

    if (-not $Quiet) {
        Write-Host "Setting up GitHub tokens..." -ForegroundColor Blue
    }

    # CRITICAL: Preserve existing GITHUB_TOKEN if set (for Models access)
    $preserveGithubToken = $null
    if ($env:GITHUB_TOKEN) {
        $preserveGithubToken = $env:GITHUB_TOKEN
        if (-not $Quiet) {
            Write-Host "$([char]0x2713) Preserving existing GITHUB_TOKEN for Models access ($($env:GITHUB_TOKEN.Length) chars)" -ForegroundColor Green
        }
    } else {
        Write-Host "Warning: No GITHUB_TOKEN found initially" -ForegroundColor Yellow
    }

    # 2. Setup APM module access
    # Precedence: GITHUB_APM_PAT > GITHUB_TOKEN
    if (-not $env:GITHUB_APM_PAT) {
        if ($env:GITHUB_TOKEN) {
            $env:GITHUB_APM_PAT = $env:GITHUB_TOKEN
        }
    }

    # 3. Setup Models access (GITHUB_TOKEN for Codex, GITHUB_MODELS_KEY for LLM)
    # Precedence: GITHUB_TOKEN > GITHUB_APM_PAT
    # CRITICAL: Only set GITHUB_TOKEN if not already present (never overwrite)
    if (-not $env:GITHUB_TOKEN) {
        if ($env:GITHUB_APM_PAT) {
            $env:GITHUB_TOKEN = $env:GITHUB_APM_PAT
        }
    }

    # 4. Restore preserved GITHUB_TOKEN (never overwrite Models-enabled token)
    if ($preserveGithubToken) {
        $env:GITHUB_TOKEN = $preserveGithubToken
    }

    # 5. Setup LLM Models key
    if ($env:GITHUB_TOKEN -and (-not $env:GITHUB_MODELS_KEY)) {
        $env:GITHUB_MODELS_KEY = $env:GITHUB_TOKEN
    }

    if (-not $Quiet) {
        Write-Host "GitHub token environment configured" -ForegroundColor Green
    }
}

# Get appropriate token for specific runtime
function Get-TokenForRuntime {
    param(
        [Parameter(Mandatory)]
        [string]$Runtime
    )

    switch ($Runtime) {
        { $_ -in "codex", "models", "llm" } {
            # Models: GITHUB_TOKEN > GITHUB_APM_PAT
            if ($env:GITHUB_TOKEN) { return $env:GITHUB_TOKEN }
            elseif ($env:GITHUB_APM_PAT) { return $env:GITHUB_APM_PAT }
        }
        default {
            # General: GITHUB_APM_PAT > GITHUB_TOKEN
            if ($env:GITHUB_APM_PAT) { return $env:GITHUB_APM_PAT }
            elseif ($env:GITHUB_TOKEN) { return $env:GITHUB_TOKEN }
        }
    }
    return $null
}

# Validate GitHub tokens
function Test-GitHubToken {
    $hasAnyToken = $false
    $hasModelsToken = $false

    if ($env:GITHUB_APM_PAT -or $env:GITHUB_TOKEN) {
        $hasAnyToken = $true
    }

    if ($env:GITHUB_TOKEN) {
        $hasModelsToken = $true
    }

    if (-not $hasAnyToken) {
        Write-Host "No GitHub tokens found" -ForegroundColor Red
        Write-Host "Required: Set one of these environment variables:"
        Write-Host "  GITHUB_TOKEN (user-scoped PAT for GitHub Models)"
        Write-Host "  GITHUB_APM_PAT (fine-grained PAT for APM modules)"
        return $false
    }

    if (-not $hasModelsToken) {
        Write-Host "Warning: No user-scoped PAT found. GitHub Models API may not work with fine-grained PATs." -ForegroundColor Yellow
        Write-Host "For full functionality, set GITHUB_TOKEN to a user-scoped PAT."
        return $false
    }

    Write-Host "GitHub token validation passed" -ForegroundColor Green
    return $true
}
