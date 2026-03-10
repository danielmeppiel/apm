---
title: "Installation"
description: "Install APM on macOS, Linux, or from source."
sidebar:
  order: 1
---

## Requirements

- macOS or Linux (x86_64 or ARM64)
- [git](https://git-scm.com/) for dependency management
- Python 3.10+ (only for pip or from-source installs)

## Quick install (recommended)

```bash
curl -sSL https://raw.githubusercontent.com/microsoft/apm/main/install.sh | sh
```

On Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/microsoft/apm/main/install.ps1 | iex"
```

This script automatically:
- Detects your platform (macOS/Linux/Windows, Intel/ARM)
- Downloads the latest binary
- Installs to `/usr/local/bin/` on macOS/Linux
- Installs under `%LOCALAPPDATA%\Programs\apm\` on Windows and adds a user-level `apm` shim to `PATH`
- Verifies installation

### Windows Package Managers

APM is available through popular Windows package managers:

#### Scoop

```powershell
scoop bucket add apm https://github.com/microsoft/scoop-apm
scoop install apm
```

#### Chocolatey

```powershell
choco install apm
```

#### winget

```powershell
winget install Microsoft.APM
```

## pip install

```bash
pip install apm-cli
```

Requires Python 3.10+.

## Manual binary install

Download the archive for your platform from [GitHub Releases](https://github.com/microsoft/apm/releases/latest) and install manually:

#### Windows x86_64
Use the PowerShell installer for the supported Windows install path:

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/microsoft/apm/main/install.ps1 | iex"
```

#### macOS / Linux
```bash
# Example: macOS Apple Silicon
curl -L https://github.com/microsoft/apm/releases/latest/download/apm-darwin-arm64.tar.gz | tar -xz
sudo mkdir -p /usr/local/lib/apm
sudo cp -r apm-darwin-arm64/* /usr/local/lib/apm/
sudo ln -sf /usr/local/lib/apm/apm /usr/local/bin/apm
```

Replace `apm-darwin-arm64` with the archive name for your platform:

| Platform           | Archive name         |
|--------------------|----------------------|
| macOS Apple Silicon | `apm-darwin-arm64`  |
| macOS Intel        | `apm-darwin-x86_64`  |
| Linux x86_64       | `apm-linux-x86_64`   |
| Linux ARM64        | `apm-linux-arm64`    |

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

### `apm: command not found`

Ensure `/usr/local/bin` is in your `PATH`:

```bash
echo $PATH | tr ':' '\n' | grep /usr/local/bin
```

If missing, add it to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.):

```bash
export PATH="/usr/local/bin:$PATH"
```

### Permission denied during install

Use `sudo` for system-wide installation, or install to a user-writable directory instead:

```bash
mkdir -p ~/bin
# then install the binary to ~/bin/apm and add ~/bin to PATH
```

### Windows Runtime Setup

Runtime setup works natively on Windows. No WSL is required:

```powershell
apm runtime setup copilot
apm runtime setup codex
apm runtime setup llm
```

APM automatically uses PowerShell scripts on Windows and bash scripts on macOS and Linux.

### Verify Installation

Check what runtimes are available:

### Authentication errors when installing packages

If `apm install` fails with authentication errors for private repositories, ensure you have a valid GitHub token configured:

```bash
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
```

## Next steps

See the [Quick Start](../quick-start/) to set up your first project.