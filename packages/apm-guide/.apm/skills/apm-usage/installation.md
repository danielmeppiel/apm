# Installation

## Quick install (recommended)

```bash
# macOS / Linux
curl -sSL https://aka.ms/apm-unix | sh

# Windows (PowerShell)
irm https://aka.ms/apm-windows | iex
```

## Package managers

```bash
# Homebrew (macOS / Linux)
brew install microsoft/apm/apm

# Scoop (Windows)
scoop bucket add apm https://github.com/microsoft/scoop-apm
scoop install apm

# pip (all platforms, requires Python 3.10+)
pip install apm-cli
```

## Verify

```bash
apm --version
```

## Update

```bash
apm update          # update APM itself
apm update --check  # check for updates without installing
```

## Troubleshooting

- **macOS/Linux "command not found":** ensure `/usr/local/bin` is in `$PATH`.
- **Windows antivirus locks:** set `$env:APM_DEBUG = "1"` and retry.
