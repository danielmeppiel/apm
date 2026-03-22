---
title: "Installation"
description: "Install APM on macOS, Linux, Windows, or from source."
sidebar:
  order: 1
---

## Requirements

- macOS, Linux, or Windows (x86_64 or ARM64)
- [git](https://git-scm.com/) for dependency management
- Python 3.10+ (only for pip or from-source installs)

## Quick install (recommended)

**macOS / Linux:**

```bash
curl -sSL https://aka.ms/apm-unix | sh
```

**Windows (PowerShell):**

```powershell
irm https://aka.ms/apm-windows | iex
```

The installer automatically detects your platform (macOS/Linux/Windows, Intel/ARM), downloads the latest binary, and adds `apm` to your `PATH`.

## Package managers

**Homebrew (macOS/Linux):**

```bash
brew install microsoft/apm/apm
```

**Scoop (Windows):**

```powershell
scoop bucket add apm https://github.com/microsoft/scoop-apm
scoop install apm
```

## pip install

```bash
pip install apm-cli
```

Requires Python 3.10+.

## Docker

Run APM in a container to avoid Python versioning issues:

```bash
docker pull ghcr.io/microsoft/apm:latest
docker run --rm -v "$(pwd):/workspace" -w /workspace ghcr.io/microsoft/apm install
```

Container images are published to [GitHub Container Registry](https://github.com/microsoft/apm/pkgs/container/apm) on every release.

## Manual binary install

Download the archive for your platform from [GitHub Releases](https://github.com/microsoft/apm/releases/latest) and install manually:

#### Windows x86_64

```powershell
# Download and extract the Windows binary
Invoke-WebRequest -Uri https://github.com/microsoft/apm/releases/latest/download/apm-windows-x86_64.zip -OutFile apm-windows-x86_64.zip
Expand-Archive -Path .\apm-windows-x86_64.zip -DestinationPath .

# Copy to a permanent location and add to PATH
$installDir = "$env:LOCALAPPDATA\Programs\apm"
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
Copy-Item -Path .\apm-windows-x86_64\* -Destination $installDir -Recurse -Force
[Environment]::SetEnvironmentVariable("Path", "$installDir;" + [Environment]::GetEnvironmentVariable("Path", "User"), "User")
```

#### macOS / Linux
```bash
# Example: macOS Apple Silicon
curl -L https://github.com/microsoft/apm/releases/latest/download/apm-darwin-arm64.tar.gz | tar -xz
sudo mkdir -p /usr/local/lib/apm
sudo cp -r apm-darwin-arm64/* /usr/local/lib/apm/
sudo ln -sf /usr/local/lib/apm/apm /usr/local/bin/apm
```

Replace `apm-darwin-arm64` with the archive name for your macOS or Linux platform:

| Platform            | Archive name          |
|---------------------|-----------------------|
| macOS Apple Silicon | `apm-darwin-arm64`    |
| macOS Intel         | `apm-darwin-x86_64`   |
| Linux x86_64        | `apm-linux-x86_64`    |
| Linux ARM64         | `apm-linux-arm64`     |

## From source (contributors)

```bash
git clone https://github.com/microsoft/apm.git
cd apm

# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create environment and install in development mode
uv venv
uv pip install -e ".[dev]"
source .venv/bin/activate
```

## Build binary from source

To build a standalone binary with PyInstaller:

```bash
cd apm  # cloned repo from step above
uv pip install pyinstaller
chmod +x scripts/build-binary.sh
./scripts/build-binary.sh
```

The output binary is at `./dist/apm-{platform}-{arch}/apm`.

## Verify installation

```bash
apm --version
```

## Troubleshooting

### `apm: command not found` (macOS / Linux)

Ensure `/usr/local/bin` is in your `PATH`:

```bash
echo $PATH | tr ':' '\n' | grep /usr/local/bin
```

If missing, add it to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.):

```bash
export PATH="/usr/local/bin:$PATH"
```

### Permission denied during install (macOS / Linux)

Use `sudo` for system-wide installation, or install to a user-writable directory instead:

```bash
mkdir -p ~/bin
# then install the binary to ~/bin/apm and add ~/bin to PATH
```

### Authentication errors when installing packages

If `apm install` fails with authentication errors for private repositories, ensure you have a valid GitHub token configured:

```bash
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
```

## Next steps

See the [Quick Start](../quick-start/) to set up your first project.