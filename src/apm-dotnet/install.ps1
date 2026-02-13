#!/usr/bin/env pwsh
# APM CLI Installer Script (.NET NativeAOT)
# Usage: irm https://raw.githubusercontent.com/danielmeppiel/apm/main/src/apm-dotnet/install.ps1 | iex
# For private repos: $env:GITHUB_APM_PAT = "your_token"; irm ... | iex

#Requires -Version 7.0
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# --- PowerShell version gate ---
if ($PSVersionTable.PSVersion.Major -lt 7) {
    Write-Host "Error: PowerShell 7+ is required. You are running $($PSVersionTable.PSVersion)." -ForegroundColor Red
    Write-Host "Install pwsh: https://aka.ms/install-powershell" -ForegroundColor Yellow
    exit 1
}

# --- Configuration ---
$Repo = 'danielmeppiel/apm'
$BinaryName = 'apm'
$ApiUrl = "https://api.github.com/repos/$Repo/releases/latest"

# --- Helpers ---
function Write-Banner {
    Write-Host ''
    Write-Host '╔══════════════════════════════════════════════════════════════╗' -ForegroundColor Cyan
    Write-Host '║                    APM CLI Installer                        ║' -ForegroundColor Cyan
    Write-Host '║              The NPM for AI-Native Development              ║' -ForegroundColor Cyan
    Write-Host '╚══════════════════════════════════════════════════════════════╝' -ForegroundColor Cyan
    Write-Host ''
}

function Write-Step  { param([string]$Msg) Write-Host $Msg -ForegroundColor Yellow }
function Write-Ok    { param([string]$Msg) Write-Host "✓ $Msg" -ForegroundColor Green }
function Write-Info  { param([string]$Msg) Write-Host $Msg -ForegroundColor Cyan }
function Write-Warn  { param([string]$Msg) Write-Host "⚠ $Msg" -ForegroundColor Yellow }
function Write-Err   { param([string]$Msg) Write-Host "❌ $Msg" -ForegroundColor Red }

function Write-QuickStart {
    Write-Host ''
    Write-Host '🎉 Installation complete!' -ForegroundColor Green
    Write-Host ''
    Write-Info 'Quick start:'
    Write-Host '  apm init my-app          # Create a new APM project'
    Write-Host '  cd my-app && apm install # Install dependencies'
    Write-Host '  apm run                  # Run your first prompt'
    Write-Host ''
    Write-Info "Documentation: https://github.com/$Repo"
    Write-Info "Need help? https://github.com/$Repo/issues"
}

# --- Platform detection ---
function Get-PlatformRid {
    $os   = [System.Runtime.InteropServices.RuntimeInformation]::OSDescription
    $arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture

    # Determine OS component
    if ($IsWindows) {
        $osPart = 'win'
    } elseif ($IsMacOS) {
        $osPart = 'osx'
    } elseif ($IsLinux) {
        $osPart = 'linux'
    } else {
        Write-Err "Unsupported OS: $os"
        exit 1
    }

    # Determine architecture component
    switch ($arch) {
        'X64'   { $archPart = 'x64'   }
        'Arm64' { $archPart = 'arm64' }
        default {
            Write-Err "Unsupported architecture: $arch"
            Write-Host 'Supported: x64, arm64' -ForegroundColor Yellow
            exit 1
        }
    }

    return "$osPart-$archPart"
}

# --- GitHub API helpers ---
function Get-AuthHeaders {
    $headers = @{ 'User-Agent' = 'apm-installer' }
    $token = if ($env:GITHUB_APM_PAT) { $env:GITHUB_APM_PAT }
             elseif ($env:GITHUB_TOKEN) { $env:GITHUB_TOKEN }
             else { $null }
    if ($token) {
        $headers['Authorization'] = "token $token"
        $tokenSource = if ($env:GITHUB_APM_PAT) { 'GITHUB_APM_PAT' } else { 'GITHUB_TOKEN' }
        Write-Info "Using $tokenSource for authentication"
    }
    return @{ Headers = $headers; HasToken = [bool]$token }
}

function Get-LatestRelease {
    $auth = Get-AuthHeaders

    # Try without auth first (public repos)
    $headersNoAuth = @{ 'User-Agent' = 'apm-installer' }
    try {
        $response = Invoke-RestMethod -Uri $ApiUrl -Headers $headersNoAuth -ErrorAction Stop
        return $response
    } catch {
        # Fall through to authenticated attempt
    }

    # Try with auth if available
    if ($auth.HasToken) {
        Write-Info 'Repository appears private, retrying with authentication...'
        try {
            $response = Invoke-RestMethod -Uri $ApiUrl -Headers $auth.Headers -ErrorAction Stop
            return $response
        } catch {
            Write-Err "GitHub API request failed: $_"
            exit 1
        }
    }

    Write-Err 'Failed to fetch release info. For private repos set GITHUB_APM_PAT or GITHUB_TOKEN.'
    Write-Host '  $env:GITHUB_APM_PAT = "ghp_..."' -ForegroundColor Yellow
    Write-Host '  irm https://raw.githubusercontent.com/danielmeppiel/apm/main/src/apm-dotnet/install.ps1 | iex' -ForegroundColor Yellow
    exit 1
}

# --- Download helpers ---
function Get-AssetDownloadUrl {
    param(
        [object]$Release,
        [string]$AssetName
    )
    $asset = $Release.assets | Where-Object { $_.name -eq $AssetName } | Select-Object -First 1
    if (-not $asset) {
        return $null
    }
    return @{
        BrowserUrl = $asset.browser_download_url
        ApiUrl     = $asset.url
    }
}

function Invoke-AssetDownload {
    param(
        [hashtable]$Urls,
        [string]$OutFile
    )
    $auth = Get-AuthHeaders

    # Try public browser URL first
    try {
        Invoke-WebRequest -Uri $Urls.BrowserUrl -OutFile $OutFile -ErrorAction Stop
        return
    } catch {
        # Fall through
    }

    # Try API URL with auth (private repos)
    if ($auth.HasToken -and $Urls.ApiUrl) {
        $dlHeaders = $auth.Headers.Clone()
        $dlHeaders['Accept'] = 'application/octet-stream'
        try {
            Invoke-WebRequest -Uri $Urls.ApiUrl -Headers $dlHeaders -OutFile $OutFile -ErrorAction Stop
            return
        } catch {
            # Fall through
        }
    }

    throw "Download failed for asset."
}

# --- Installation ---
function Install-Unix {
    param([string]$TarPath, [string]$Rid)

    $installDir = '/usr/local/lib/apm'
    $binDir     = '/usr/local/bin'
    $tmpExtract = Join-Path ([System.IO.Path]::GetTempPath()) "apm-extract-$(Get-Random)"

    try {
        New-Item -ItemType Directory -Path $tmpExtract -Force | Out-Null
        tar -xzf $TarPath -C $tmpExtract
        if ($LASTEXITCODE -ne 0) { throw "tar extraction failed" }

        # Find the extracted binary (could be in a subdirectory or root)
        $binary = Get-ChildItem -Path $tmpExtract -Recurse -Filter $BinaryName |
                  Where-Object { -not $_.PSIsContainer } |
                  Select-Object -First 1
        if (-not $binary) { throw "Binary '$BinaryName' not found in archive" }

        # Determine if we need sudo
        $parentDir = Split-Path $installDir -Parent
        $needSudo = $true
        if (Test-Path $parentDir -ErrorAction SilentlyContinue) {
            & test -w $parentDir 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { $needSudo = $false }
        }

        $sudo = if ($needSudo) { 'sudo' } else { '' }

        # Install files
        & bash -c "$sudo rm -rf '$installDir' && $sudo mkdir -p '$installDir' && $sudo cp -r '$($binary.Directory.FullName)'/* '$installDir/' && $sudo chmod +x '$installDir/$BinaryName' && $sudo ln -sf '$installDir/$BinaryName' '$binDir/$BinaryName'"
        if ($LASTEXITCODE -ne 0) { throw "Installation to $installDir failed" }

        Write-Ok "Installed to $installDir"
        Write-Info "Symlink: $binDir/$BinaryName -> $installDir/$BinaryName"
    } finally {
        Remove-Item -Path $tmpExtract -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Install-Windows {
    param([string]$ZipPath)

    $installDir = Join-Path $env:LOCALAPPDATA 'apm'

    # Clean previous installation
    if (Test-Path $installDir) {
        Remove-Item -Path $installDir -Recurse -Force
    }

    # Extract
    Expand-Archive -Path $ZipPath -DestinationPath $installDir -Force

    # If archive contains a nested folder, flatten it
    $nested = Get-ChildItem -Path $installDir -Directory | Select-Object -First 1
    if ($nested -and (Test-Path (Join-Path $nested.FullName "$BinaryName.exe"))) {
        $nestedPath = $nested.FullName
        Get-ChildItem -Path $nestedPath | Move-Item -Destination $installDir -Force
        Remove-Item -Path $nestedPath -Recurse -Force
    }

    Write-Ok "Installed to $installDir"

    # Add to user PATH if not already present
    $userPath = [System.Environment]::GetEnvironmentVariable('PATH', 'User')
    if ($userPath -notlike "*$installDir*") {
        [System.Environment]::SetEnvironmentVariable('PATH', "$installDir;$userPath", 'User')
        $env:PATH = "$installDir;$env:PATH"
        Write-Ok 'Added to user PATH (restart your terminal for changes to take effect)'
    }
}

# ============================================================
# Main
# ============================================================
try {
    Write-Banner

    # 1 - Detect platform
    $rid = Get-PlatformRid
    Write-Info "Detected platform: $rid"

    # Determine asset name: .zip for Windows, .tar.gz otherwise
    if ($rid.StartsWith('win')) {
        $assetName = "apm-$rid.zip"
    } else {
        $assetName = "apm-$rid.tar.gz"
    }
    Write-Info "Target asset: $assetName"

    # 2 - Fetch latest release
    Write-Step 'Fetching latest release...'
    $release = Get-LatestRelease
    $tagName = $release.tag_name
    if (-not $tagName) {
        Write-Err 'Could not determine latest release version.'
        exit 1
    }
    Write-Ok "Latest version: $tagName"

    # 3 - Resolve download URL
    $urls = Get-AssetDownloadUrl -Release $release -AssetName $assetName
    if (-not $urls) {
        Write-Err "No asset '$assetName' found in release $tagName."
        Write-Host "Available assets:" -ForegroundColor Yellow
        $release.assets | ForEach-Object { Write-Host "  $($_.name)" }
        Write-Host ''
        Write-Warn 'Fallback: install the .NET tool instead:'
        Write-Host '  dotnet tool install -g apm-cli' -ForegroundColor Cyan
        exit 1
    }

    # 4 - Download
    Write-Step "Downloading $assetName..."
    $tmpDir  = Join-Path ([System.IO.Path]::GetTempPath()) "apm-install-$(Get-Random)"
    New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
    $outFile = Join-Path $tmpDir $assetName

    try {
        Invoke-AssetDownload -Urls $urls -OutFile $outFile
        Write-Ok 'Download successful'
    } catch {
        Write-Err "Download failed: $_"
        Write-Host ''
        Write-Warn 'Fallback: install via .NET tool instead:'
        Write-Host '  dotnet tool install -g apm-cli' -ForegroundColor Cyan
        exit 1
    }

    # 5 - Install
    Write-Step 'Installing...'
    if ($rid.StartsWith('win')) {
        Install-Windows -ZipPath $outFile
    } else {
        Install-Unix -TarPath $outFile -Rid $rid
    }

    # 6 - Verify
    Write-Step 'Verifying installation...'
    $apmCmd = Get-Command $BinaryName -ErrorAction SilentlyContinue
    if ($apmCmd) {
        $version = & $BinaryName --version 2>&1
        Write-Ok "apm $version"
        Write-Info "Location: $($apmCmd.Source)"
    } else {
        Write-Warn 'apm not found in PATH. You may need to restart your terminal.'
    }

    # 7 - Quick start
    Write-QuickStart

} catch {
    Write-Err "Installation failed: $_"
    Write-Host ''
    Write-Warn 'Alternative install methods:'
    Write-Host '  dotnet tool install -g apm-cli    # .NET global tool' -ForegroundColor Cyan
    Write-Host "  git clone https://github.com/$Repo && cd apm/src/apm-dotnet && dotnet build" -ForegroundColor Cyan
    exit 1
} finally {
    # Cleanup temp directory
    if ($tmpDir -and (Test-Path $tmpDir -ErrorAction SilentlyContinue)) {
        Remove-Item -Path $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
