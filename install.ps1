param(
    [string]$Repo = "microsoft/apm"
)

$ErrorActionPreference = "Stop"

$installRoot = Join-Path $env:LOCALAPPDATA "Programs\apm"
$binDir = Join-Path $installRoot "bin"
$releasesDir = Join-Path $installRoot "releases"
$assetName = "apm-windows-x86_64.zip"

function Write-Info {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Green
}

function Write-WarningText {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Yellow
}

function Get-AuthHeaders {
    if ($env:GITHUB_APM_PAT) {
        return @{ Authorization = "token $($env:GITHUB_APM_PAT)" }
    }

    if ($env:GITHUB_TOKEN) {
        return @{ Authorization = "token $($env:GITHUB_TOKEN)" }
    }

    return @{}
}

function Invoke-GitHubJson {
    param(
        [string]$Url,
        [hashtable]$Headers
    )

    if ($Headers.Count -gt 0) {
        return Invoke-RestMethod -Uri $Url -Headers $Headers
    }

    return Invoke-RestMethod -Uri $Url
}

function Add-ToUserPath {
    param([string]$PathEntry)

    $currentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $userEntries = @()
    if ($currentUserPath) {
        $userEntries = $currentUserPath.Split(";", [System.StringSplitOptions]::RemoveEmptyEntries)
    }

    if ($userEntries -notcontains $PathEntry) {
        $newUserPath = if ($currentUserPath) { "$PathEntry;$currentUserPath" } else { $PathEntry }
        [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
        Write-Info "Added $PathEntry to your user PATH."
    }

    if (($env:Path -split ";") -notcontains $PathEntry) {
        $env:Path = "$PathEntry;$env:Path"
    }
}

Write-Info "APM Installer (Windows)"
Write-Info "Fetching latest release information..."

$headers = Get-AuthHeaders
$release = Invoke-GitHubJson -Url "https://api.github.com/repos/$Repo/releases/latest" -Headers $headers

if (-not $release.tag_name) {
    throw "Could not determine the latest release tag."
}

$asset = $release.assets | Where-Object { $_.name -eq $assetName } | Select-Object -First 1
if (-not $asset) {
    throw "Release $($release.tag_name) does not contain $assetName."
}

$tagName = $release.tag_name
$releaseDir = Join-Path $releasesDir $tagName
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("apm-install-" + [System.Guid]::NewGuid().ToString("N"))
$zipPath = Join-Path $tempDir $assetName

New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
New-Item -ItemType Directory -Force -Path $binDir | Out-Null
New-Item -ItemType Directory -Force -Path $releasesDir | Out-Null

try {
    Write-Info "Downloading $assetName from $tagName..."
    if ($headers.Count -gt 0) {
        Invoke-WebRequest -Uri $asset.browser_download_url -Headers $headers -OutFile $zipPath
    } else {
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath
    }

    Write-Info "Extracting package..."
    Expand-Archive -Path $zipPath -DestinationPath $tempDir -Force

    $packageDir = Join-Path $tempDir "apm-windows-x86_64"
    $exePath = Join-Path $packageDir "apm.exe"
    if (-not (Test-Path $exePath)) {
        throw "Extracted package is missing apm.exe."
    }

    if (Test-Path $releaseDir) {
        Remove-Item -Recurse -Force $releaseDir
    }

    Move-Item -Path $packageDir -Destination $releaseDir

    $shimPath = Join-Path $binDir "apm.cmd"
    $shimContent = "@echo off`r`n`"$releaseDir\apm.exe`" %*`r`n"
    Set-Content -Path $shimPath -Value $shimContent -Encoding ASCII

    Add-ToUserPath -PathEntry $binDir

    Write-Success "APM $tagName installed successfully."
    Write-Info "Command shim: $shimPath"
    Write-Info "Run 'apm --version' in a new terminal to verify the installation."
} finally {
    if (Test-Path $tempDir) {
        Remove-Item -Recurse -Force $tempDir
    }
}