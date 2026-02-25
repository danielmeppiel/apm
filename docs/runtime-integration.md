# Runtime Integration Guide

APM manages LLM runtime installation and configuration automatically. This guide covers the supported runtimes, how to use them, and how to extend APM with additional runtimes.

## Overview

APM acts as a runtime package manager, downloading and configuring LLM runtimes from their official sources. Currently supports three runtimes:

| Runtime | Description | Best For | Configuration |
|---------|-------------|----------|---------------|
| [**GitHub Copilot CLI**](https://github.com/github/copilot-cli) | GitHub's Copilot CLI (Recommended) | Advanced AI coding, native MCP support | Auto-configured, no auth needed |
| [**OpenAI Codex**](https://github.com/openai/codex) | OpenAI's Codex CLI | Code tasks, GitHub Models API | Auto-configured with GitHub Models |
| [**LLM Library**](https://llm.datasette.io/en/stable/index.html) | Simon Willison's `llm` CLI | General use, many providers | Manual API key setup |

## Quick Setup

### Install APM and Setup Runtime
```bash
# 1. Install APM
curl -sSL https://raw.githubusercontent.com/microsoft/apm/main/install.sh | sh

# 2. Setup AI runtime (downloads and configures automatically)
apm runtime setup copilot
```

### Runtime Management
```bash
apm runtime list              # Show installed runtimes
apm runtime setup llm         # Install LLM library
apm runtime setup copilot     # Install GitHub Copilot CLI (Recommended)
apm runtime setup codex       # Install Codex CLI
```

## GitHub Copilot CLI Runtime (Recommended)

APM automatically installs GitHub Copilot CLI from the public npm registry. Copilot CLI provides advanced AI coding assistance with native MCP integration and GitHub context awareness.

### Setup

#### 1. Install via APM
```bash
apm runtime setup copilot
```

This automatically:
- Installs GitHub Copilot CLI from public npm registry
- Requires Node.js v22+ and npm v10+
- Creates MCP configuration directory at `~/.copilot/`
- No authentication required for installation

### Usage

APM executes scripts defined in your `apm.yml`. When scripts reference `.prompt.md` files, APM compiles them with parameter substitution. See [Prompts Guide](prompts.md) for details.

```bash
# Run scripts (from apm.yml) with parameters
apm run start --param service_name=api-gateway
apm run debug --param service_name=api-gateway
```

**Script Configuration (apm.yml):**
```yaml
scripts:
  start: "copilot --full-auto -p analyze-logs.prompt.md"
  debug: "copilot --full-auto -p analyze-logs.prompt.md --log-level debug"
```

## OpenAI Codex Runtime

APM automatically downloads, installs, and configures the Codex CLI with GitHub Models for free usage.

### Setup

#### 1. Install via APM
```bash
apm runtime setup codex
```

This automatically:
- Downloads the latest Codex binary for your platform
- Installs to `~/.apm/runtimes/codex`
- Creates configuration for GitHub Models (`github/gpt-4o`)
- Updates your PATH

#### 2. Set GitHub Token
```bash
# Get a fine-grained GitHub token (preferred) with "Models" permissions
export GITHUB_TOKEN=your_github_token
```

### Usage

```bash
# Run scripts (from apm.yml) with parameters
apm run start --param service_name=api-gateway
apm run debug --param service_name=api-gateway
```

**Script Configuration (apm.yml):**
```yaml
scripts:
  start: "codex analyze-logs.prompt.md"
  debug: "RUST_LOG=debug codex analyze-logs.prompt.md"
```

## LLM Runtime

APM also supports the LLM library runtime with multiple model providers and manual configuration.

### Setup

#### 1. Install via APM
```bash
apm runtime setup llm
```

This automatically:
- Creates a Python virtual environment
- Installs the `llm` library and dependencies
- Creates a wrapper script at `~/.apm/runtimes/llm`

#### 2. Configure API Keys (Manual)
```bash
# GitHub Models (free)
llm keys set github
# Paste your GitHub PAT when prompted

# Other providers
llm keys set openai     # OpenAI API key
llm keys set anthropic  # Anthropic API key
```

### Usage

APM executes scripts defined in your `apm.yml`. See [Prompts Guide](prompts.md) for details on prompt compilation.

```bash
# Run scripts that use LLM runtime
apm run llm-script --param service_name=api-gateway
apm run analysis --param time_window="24h"
```

**Script Configuration (apm.yml):**
```yaml
scripts:
  llm-script: "llm analyze-logs.prompt.md -m github/gpt-4o-mini"
  analysis: "llm performance-analysis.prompt.md -m gpt-4o"
```

## Examples by Use Case

### Basic Usage
```bash
# Run scripts defined in apm.yml
apm run start --param service_name=api-gateway
apm run copilot-analysis --param service_name=api-gateway
apm run debug --param service_name=api-gateway
```

### Code Analysis with Copilot CLI
```bash
# Scripts that use Copilot CLI for advanced code understanding
apm run code-review --param pull_request=123
apm run analyze-code --param file_path="src/main.py"
apm run refactor --param component="UserService"
```

### Code Analysis with Codex
```bash
# Scripts that use Codex for code understanding
apm run codex-review --param pull_request=123
apm run codex-analyze --param file_path="src/main.py"
```

### Documentation Tasks
```bash
# Scripts that use LLM for text processing
apm run document --param project_name=my-project
apm run summarize --param report_type="weekly"
```

## Troubleshooting

**"Runtime not found"**
```bash
# Install missing runtime
apm runtime setup copilot  # Recommended
apm runtime setup codex
apm runtime setup llm

# Check installed runtimes
apm runtime list
```

**"Command not found: copilot"**
```bash
# Ensure Node.js v22+ and npm v10+ are installed
node --version  # Should be v22+
npm --version   # Should be v10+

# Reinstall Copilot CLI
apm runtime setup copilot
```

**"Command not found: codex"**
```bash
# Ensure PATH is updated (restart terminal)
# Or reinstall runtime
apm runtime setup codex
```

## Extending APM with New Runtimes

APM's runtime system is designed to be extensible. To add support for a new runtime:

### Architecture

APM's runtime system consists of three main components:

1. **Runtime Adapter** (`src/apm_cli/runtime/`) - Python interface for executing prompts
2. **Setup Script** (`scripts/runtime/`) - Shell script for installation and configuration  
3. **Runtime Manager** (`src/apm_cli/runtime/manager.py`) - Orchestrates installation and discovery

### Adding a New Runtime

1. **Create Runtime Adapter** - Extend `RuntimeAdapter` in `src/apm_cli/runtime/your_runtime.py`
2. **Create Setup Script** - Add installation script in `scripts/runtime/setup-your-runtime.sh`
3. **Register Runtime** - Add entry to `supported_runtimes` in `RuntimeManager`
4. **Update CLI** - Add runtime to command choices in `cli.py`
5. **Update Factory** - Add runtime to `RuntimeFactory`

### Best Practices

- Follow the `RuntimeAdapter` interface
- Use `setup-common.sh` utilities for platform detection and PATH management
- Handle errors gracefully with clear messages
- Test installation works after setup completes
- Support vanilla mode (no APM-specific configuration)

### Contributing

To contribute a new runtime to APM:

1. Fork the repository and follow the extension guide above
2. Add tests and update documentation
3. Submit a pull request

The APM team welcomes contributions for popular LLM runtimes!
