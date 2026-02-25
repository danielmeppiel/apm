# Getting Started with APM

Welcome to APM - the AI Package Manager that transforms any project into reliable AI-Native Development. This guide will walk you through setup, installation, and creating your first AI-native project.

## Prerequisites

### Token Configuration (All Optional)

APM works without any tokens for public modules. Tokens unlock additional capabilities:

#### For Private Module Access

| Variable | Purpose | When Needed |
|----------|---------|-------------|
| `GITHUB_APM_PAT` | Private GitHub/GHE repos | Private GitHub packages |
| `ADO_APM_PAT` | Private Azure DevOps repos | Private ADO packages |

##### GITHUB_APM_PAT
```bash
export GITHUB_APM_PAT=ghp_finegrained_token_here  
```
- **Purpose**: Access to private APM modules on GitHub/GitHub Enterprise
- **Type**: Fine-grained Personal Access Token (org or user-scoped)
- **Permissions**: Repository read access to repositories you want to install from

##### ADO_APM_PAT
```bash
export ADO_APM_PAT=your_ado_pat
```
- **Purpose**: Access to private APM modules on Azure DevOps
- **Type**: Azure DevOps Personal Access Token
- **Permissions**: Code (Read) scope

#### For Running Prompts (`apm run`)

| Variable | Purpose | When Needed |
|----------|---------|-------------|
| `GITHUB_COPILOT_PAT` | Copilot runtime | `apm run` with Copilot |

##### GITHUB_COPILOT_PAT
```bash
export GITHUB_COPILOT_PAT=ghp_copilot_token
```
- **Purpose**: Authentication for `apm run` with Copilot runtime
- **Type**: Personal Access Token with Copilot access
- **Fallback**: Falls back to `GITHUB_TOKEN` if not set

#### Host Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `GITHUB_HOST` | Default host for bare package names | `github.com` |

##### GITHUB_HOST
```bash
export GITHUB_HOST=github.company.com
```
- **Purpose**: Set default host for bare package names (e.g., `owner/repo`)
- **Default**: `github.com`
- **Note**: Azure DevOps has no equivalent - always use FQDN syntax (e.g., `dev.azure.com/org/project/repo`)

### Common Setup Scenarios

#### Scenario 1: Public Modules Only (Most Users)
```bash
# No tokens needed - just works!
apm install microsoft/apm-sample-package
apm compile
```

#### Scenario 2: Private GitHub Modules
```bash
export GITHUB_APM_PAT=ghp_org_token    # For GitHub/GHE
```

#### Scenario 3: Private Azure DevOps Modules  
```bash
export ADO_APM_PAT=your_ado_pat
# Note: Always use FQDN syntax for ADO
apm install dev.azure.com/org/project/repo
```

#### Scenario 4: GitHub Enterprise as Default
```bash
export GITHUB_HOST=github.company.com
export GITHUB_APM_PAT=ghp_enterprise_token
# Now bare packages resolve to your enterprise
apm install team/package  # → github.company.com/team/package
```

#### Scenario 5: Running Prompts
```bash
export GITHUB_COPILOT_PAT=ghp_copilot_token  # For apm run
```

## Package Sources

APM installs packages from multiple sources. Use the format that matches your repository host:

| Source | Format | Example |
|--------|--------|---------|
| GitHub.com | `owner/repo` | `apm install microsoft/apm-sample-package` |
| GitHub Enterprise | `ghe.company.com/owner/repo` | `apm install ghe.myco.com/team/standards` |
| Azure DevOps | `dev.azure.com/org/project/repo` | `apm install dev.azure.com/myorg/proj/rules` |
| Virtual Package | `owner/repo/path/to/skill` | `apm install github/awesome-copilot/skills/review-and-refactor` |

### GitHub Enterprise Support

APM supports all GitHub Enterprise deployment models via `GITHUB_HOST` (see [Host Configuration](#host-configuration)).

#### Examples

```bash
# GitHub Enterprise Server
export GITHUB_HOST=github.company.com
apm install team/package  # → github.company.com/team/package

# GitHub Enterprise Cloud with Data Residency
export GITHUB_HOST=myorg.ghe.com
apm install platform/standards  # → myorg.ghe.com/platform/standards

# Multiple instances: Use FQDN for explicit hosts
apm install partner.ghe.com/external/integration  # FQDN always works
apm install github.com/public/open-source-package
```

**Key Insight:** Use `GITHUB_HOST` to set your default for bare package names. Use FQDN syntax to specify supported hosts explicitly (e.g., `github.com`, `*.ghe.com`, Azure DevOps). Custom hosts require setting `GITHUB_HOST`.

### Azure DevOps Support

APM supports Azure DevOps Services (cloud) and Azure DevOps Server (self-hosted). **Note:** There is no `ADO_HOST` equivalent - Azure DevOps always requires FQDN syntax.

#### URL Format

Azure DevOps uses 3 segments vs GitHub's 2:
- **GitHub**: `owner/repo`
- **Azure DevOps**: `org/project/repo`

```bash
# Both formats work (the _git segment is optional):
apm install dev.azure.com/myorg/myproject/myrepo
apm install dev.azure.com/myorg/myproject/_git/myrepo

# With git reference
apm install dev.azure.com/myorg/myproject/myrepo#main

# Legacy visualstudio.com URLs
apm install mycompany.visualstudio.com/myorg/myproject/myrepo

# Self-hosted Azure DevOps Server
apm install ado.company.internal/myorg/myproject/myrepo

# Virtual packages (individual files)
apm install dev.azure.com/myorg/myproject/myrepo/prompts/code-review.prompt.md
```

For authentication, see [Token Configuration](#token-configuration-all-optional).

### Token Creation Guide

1. **Create Fine-grained PAT** for `GITHUB_APM_PAT` (Private GitHub modules):
   - Go to [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new)  
   - Select "Fine-grained Personal Access Token"
   - Scope: Organization or Personal account (as needed)
   - Permissions: Repository read access

2. **Create Azure DevOps PAT** for `ADO_APM_PAT` (Private ADO modules):
   - Go to `https://dev.azure.com/{org}/_usersSettings/tokens`
   - Create PAT with **Code (Read)** scope

3. **Create Copilot PAT** for `GITHUB_COPILOT_PAT` (Running prompts):
   - Go to [github.com/settings/tokens](https://github.com/settings/tokens)
   - Create token with Copilot access

## Installation

### Quick Install (Recommended)

The fastest way to get APM running:

```bash
curl -sSL https://raw.githubusercontent.com/microsoft/apm/main/install.sh | sh
```

This script automatically:
- Detects your platform (macOS/Linux, Intel/ARM)
- Downloads the latest binary
- Installs to `/usr/local/bin/`
- Verifies installation

### Python Package

If you prefer managing APM through Python:

```bash
pip install apm-cli
```

**Note**: This requires Python 3.8+ and may have additional dependencies.

### Manual Installation

Download the binary for your platform from [GitHub Releases](https://github.com/microsoft/apm/releases/latest):

#### macOS Apple Silicon
```bash
curl -L https://github.com/microsoft/apm/releases/latest/download/apm-darwin-arm64.tar.gz | tar -xz
sudo mkdir -p /usr/local/lib/apm
sudo cp -r apm-darwin-arm64/* /usr/local/lib/apm/
sudo ln -sf /usr/local/lib/apm/apm /usr/local/bin/apm
```

#### macOS Intel
```bash
curl -L https://github.com/microsoft/apm/releases/latest/download/apm-darwin-x86_64.tar.gz | tar -xz
sudo mkdir -p /usr/local/lib/apm
sudo cp -r apm-darwin-x86_64/* /usr/local/lib/apm/
sudo ln -sf /usr/local/lib/apm/apm /usr/local/bin/apm
```

#### Linux x86_64
```bash
curl -L https://github.com/microsoft/apm/releases/latest/download/apm-linux-x86_64.tar.gz | tar -xz
sudo mkdir -p /usr/local/lib/apm
sudo cp -r apm-linux-x86_64/* /usr/local/lib/apm/
sudo ln -sf /usr/local/lib/apm/apm /usr/local/bin/apm
```

### From Source (Developers)

For development or customization:

```bash
git clone https://github.com/microsoft/apm.git
cd apm

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install in development mode
uv venv
uv pip install -e ".[dev]"

# Activate the environment for development
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate   # On Windows
```

### Build Binary from Source

To build a platform-specific binary using PyInstaller:

```bash
# Clone and setup (if not already done)
git clone https://github.com/microsoft/apm.git
cd apm

# Install uv and dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv
uv pip install -e ".[dev]"
uv pip install pyinstaller

# Activate environment
source .venv/bin/activate

# Build binary for your platform
chmod +x scripts/build-binary.sh
./scripts/build-binary.sh
```

This creates a platform-specific binary at `./dist/apm-{platform}-{arch}/apm` that can be distributed without Python dependencies.

**Build features**:
- **Cross-platform**: Automatically detects macOS/Linux and Intel/ARM architectures
- **UPX compression**: Automatically compresses binary if UPX is available (`brew install upx`)
- **Self-contained**: Binary includes all Python dependencies
- **Fast startup**: Uses `--onedir` mode for optimal CLI performance
- **Verification**: Automatically tests the built binary and generates checksums

## Setup AI Runtime

APM works with multiple AI coding agents. Choose your preferred runtime:

### GitHub Copilot CLI (Recommended)

```bash
apm runtime setup copilot
```

Uses GitHub Copilot CLI with native MCP integration and advanced AI coding assistance.

### OpenAI Codex CLI

```bash
apm runtime setup codex
```

Uses GitHub Models API for GPT-4 access through Codex CLI.

### LLM Library

```bash
apm runtime setup llm
```

Installs the LLM library for local and cloud model access.

### Verify Installation

Check what runtimes are available:

```bash
apm runtime list
```

## First Project Walkthrough

Let's create your first AI-native project step by step:

### 1. Initialize Project

```bash
apm init my-first-project
cd my-first-project
```

This creates a complete Context structure:

```yaml
my-first-project/
├── apm.yml              # Project configuration
├── SKILL.md             # Package meta-guide for AI discovery
└── .apm/
    ├── agents/          # AI assistant personalities
    ├── instructions/    # Context and coding standards
    ├── prompts/         # Reusable agent workflows
    └── context/         # Project knowledge base
```

**About SKILL.md:** This file serves as a meta-guide that helps AI agents discover and understand the package's capabilities. When your package is installed as a dependency, the `SKILL.md` content helps the AI understand what skills/workflows are available and how to use them.

> **Note**: Legacy `.apm/chatmodes/` directory with `.chatmode.md` files is still supported.

### 2. Explore Generated Files

Let's look at what was created:

```bash
# See project structure
ls -la .apm/

# Check the main configuration
cat apm.yml

# Look at available workflows
ls .apm/prompts/
```

### 3. Compile Context

Transform your context into agent-specific formats:

```bash
apm compile
```

**Auto-Detection:** APM automatically detects which integrations to generate based on folder presence:
- If `.github/` exists → VSCode/Copilot integration (generates `AGENTS.md`)
- If `.claude/` exists → Claude Code integration (generates `CLAUDE.md`)
- Both can coexist - APM generates outputs for all detected integrations

**Generated Files:**
- `AGENTS.md` - Contains instructions grouped by `applyTo` patterns (VSCode-compatible)
- `CLAUDE.md` - Contains instructions with `@import` syntax (Claude-compatible)

> **Note:** These files contain **only instructions** - prompts and agents are installed separately during `apm install`.

### 4. Install Dependencies

Install APM and MCP dependencies from your `apm.yml` configuration:

```bash
apm install
```

**What gets installed:**

For VSCode/Copilot (when `.github/` exists):
- `.github/prompts/*-apm.prompt.md` - Reusable prompt templates
- `.github/agents/*-apm.agent.md` - Agent definitions
- `.github/skills/{folder-name}/` - Skills with `SKILL.md` meta-guide

For Claude Code (when `.claude/` exists):
- `.claude/commands/*-apm.md` - Slash commands

> **Tip:** Both integrations can coexist in the same project. APM installs to all detected targets.

#### Adding APM Dependencies (Optional)

For reusable context from other projects, add APM dependencies:

```yaml
# Add to apm.yml
dependencies:
  apm:
    - microsoft/apm-sample-package  # Design standards, prompts
    - github/awesome-copilot/skills/review-and-refactor  # Code review skill
  mcp:
    - io.github.github/github-mcp-server
```

```bash
# Install APM dependencies
apm install --only=apm

# View installed dependencies
apm deps list

# See dependency tree
apm deps tree
```

#### Virtual Packages

APM supports **virtual packages** - installing individual files directly from any repository without requiring a full APM package structure. This is perfect for reusing individual workflow files or configuration from existing projects.

> 💡 **Explore ready-to-use prompts and agents!**  
> Browse [github/awesome-copilot](https://github.com/github/awesome-copilot) for a curated collection of community-contributed skills, instructions, and agents across all major languages and frameworks. Install any subdirectory directly with APM. Also works with Awesome Copilot's plugins.

**What are Virtual Packages?**

Instead of installing an entire package (`owner/repo`), you can install specific files:

```bash
# Install individual files directly
apm install github/awesome-copilot/skills/architecture-blueprint-generator
apm install myorg/standards/instructions/code-review.instructions.md
apm install company/templates/chatmodes/qa-assistant.chatmode.md
```

**How it Works:**

1. **Path Detection**: APM detects paths with 3+ segments as virtual packages
2. **File Download**: Downloads the file from GitHub's raw content API
3. **Structure Generation**: Creates a minimal APM package automatically:
   - Generates `apm.yml` with metadata extracted from file frontmatter
   - Places file in correct `.apm/` subdirectory based on extension
   - Creates sanitized package name from path

**Supported File Types:**

- `.prompt.md` - Agent workflows
- `.instructions.md` - Context and rules
- `.agent.md` - Agent definitions

**Installation Structure:**

Files install to `apm_modules/{owner}/{sanitized-package-name}/`:

```bash
apm install github/awesome-copilot/skills/review-and-refactor
```

Creates:
```
apm_modules/
└── github/
    └── awesome-copilot/
        └── skills/
            └── review-and-refactor/
                ├── apm.yml
                └── SKILL.md
```

**Adding to apm.yml:**

Virtual packages work in `apm.yml` just like regular packages:

```yaml
dependencies:
  apm:
    # Regular packages
    - microsoft/apm-sample-package
    
    # Virtual packages - individual files
    - github/awesome-copilot/skills/architecture-blueprint-generator
    - myorg/engineering/instructions/testing-standards.instructions.md
```

**Branch/Tag Support:**

Use `@ref` syntax for specific versions:

```bash
# Install from specific branch
apm install github/awesome-copilot/skills/review-and-refactor@develop

# Install from tag
apm install myorg/templates/chatmodes/assistant.chatmode.md@v2.1.0
```

**Use Cases:**

- **Quick Prototyping**: Test individual workflows without package overhead
- **Selective Adoption**: Pull single files from large repositories
- **Cross-Team Sharing**: Share individual standards without full package structure
- **Legacy Migration**: Gradually adopt APM by importing existing files

**Example Workflow:**

```bash
# 1. Find useful prompt in another repo
# Browse: github.com/awesome-org/best-practices

# 2. Install specific file
apm install awesome-org/best-practices/prompts/security-scan.prompt.md

# 3. Use immediately - no apm.yml configuration needed!
apm run security-scan --param target="./src"

# 4. Or add explicit script to apm.yml for custom flags
# scripts:
#   security: "copilot --full-auto -p security-scan.prompt.md"
```

**Benefits:**

- ✅ **Zero overhead** - No package creation required
- ✅ **Instant reuse** - Install any file from any repository
- ✅ **Auto-discovery** - Run installed prompts without script configuration
- ✅ **Automatic structure** - APM creates package layout for you
- ✅ **Full compatibility** - Works with `apm compile` and all commands
- ✅ **Version control** - Support for branches and tags

### Runnable Prompts (Auto-Discovery)

Starting with v0.5.0, installed prompts are **immediately runnable** without manual configuration:

```bash
# Install a prompt
apm install github/awesome-copilot/skills/architecture-blueprint-generator

# Run immediately - APM auto-discovers it!
apm run architecture-blueprint-generator --param project_name="my-app"

# Auto-discovery works for:
# - Installed virtual packages
# - Local prompts (./my-prompt.prompt.md)
# - Prompts in .apm/prompts/ or .github/prompts/
# - All prompts from installed regular packages
```

**How auto-discovery works:**

1. **No script found in apm.yml?** APM searches for matching prompt files
2. **Runtime detection:** Automatically uses GitHub Copilot CLI (preferred) or Codex
3. **Smart defaults:** Applies recommended flags for chosen runtime
4. **Collision handling:** If multiple prompts found, use qualified path: `owner/repo/prompt-name`

**Priority:**
- Explicit scripts in `apm.yml` **always win** (power user control)
- Auto-discovery provides zero-config convenience for simple cases

**Disambiguation with qualified paths:**

```bash
# If you have prompts from multiple sources
apm run github/awesome-copilot/code-review
apm run acme/standards/code-review
```

See [Prompts Guide](prompts.md#running-prompts) for complete auto-discovery documentation.

### 5. Run Your First Workflow

Execute the default "start" workflow:

```bash
apm run start --param name="<YourGitHubHandle>"
```

This runs the AI workflow with your chosen runtime, demonstrating how APM enables reliable, reusable AI interactions.

### 6. Explore Available Scripts

See what workflows are available:

```bash
apm list
```

### 7. Preview Workflows

Before running, you can preview what will be executed:

```bash
apm preview start --param name="<YourGitHubHandle>"
```

## Common Troubleshooting

### Token Issues

**Problem**: "Authentication failed" or "Token invalid"
**Solution**: 
1. Verify token has correct permissions
2. Check token expiration
3. Ensure environment variables are set correctly

```bash
# Test token access
curl -H "Authorization: token $GITHUB_CLI_PAT" https://api.github.com/user
```

### Runtime Installation Fails

**Problem**: `apm runtime setup` fails
**Solution**:
1. Check internet connection
2. Verify system requirements
3. Try installing specific runtime manually

### Command Not Found

**Problem**: `apm: command not found`
**Solution**:
1. Check if `/usr/local/bin` is in your PATH
2. Try `which apm` to locate the binary
3. Reinstall using the quick install script

### Permission Denied

**Problem**: Permission errors during installation
**Solution**:
1. Use `sudo` for system-wide installation
2. Or install to user directory: `~/bin/`

## Next Steps

Now that you have APM set up:

1. **Learn the concepts**: Read [Core Concepts](concepts.md) to understand the AI-Native Development framework
2. **Study examples**: Check [Examples & Use Cases](examples.md) for real-world patterns  
3. **Build workflows**: See [Context Guide](primitives.md) to create advanced workflows
4. **Explore dependencies**: See [Dependency Management](dependencies.md) for sharing context across projects
5. **Explore integrations**: Review [Integrations Guide](integrations.md) for tool compatibility

## Quick Reference

### Essential Commands
```bash
apm init <project>     # 🏗️ Initialize AI-native project
apm compile           # ⚙️ Generate AGENTS.md compatibility layer
apm run <workflow>    # 🚀 Execute agent workflows
apm runtime setup     # ⚡ Install coding agents
apm list              # 📋 Show available workflows
apm install           # 📦 Install APM & MCP dependencies
apm deps list         # 🔗 Show installed APM dependencies
```

### File Structure
- `apm.yml` - Project configuration and scripts
- `.apm/` - Context directory (source primitives)
- `SKILL.md` - Package meta-guide for AI discovery
- `AGENTS.md` - Generated VSCode/Copilot instructions
- `CLAUDE.md` - Generated Claude Code instructions
- `.github/prompts/`, `.github/agents/`, `.github/skills/` - Installed VSCode primitives and skills
- `.claude/commands/` - Installed Claude commands
- `apm_modules/` - Installed APM dependencies
- `*.prompt.md` - Executable agent workflows

Ready to build reliable AI workflows? Let's explore the [core concepts](concepts.md) next!