# Getting Started with APM

Welcome to APM - the AI Package Manager that transforms any project into reliable AI-Native Development. This guide will walk you through setup, installation, and creating your first AI-native project.

## Prerequisites

### GitHub Tokens Required

APM requires GitHub tokens for accessing models and package registries. Get your tokens at [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new):

#### Required Tokens

##### GITHUB_APM_PAT (Fine-grained PAT - Recommended)
```bash
export GITHUB_APM_PAT=ghp_finegrained_token_here  
```
- **Purpose**: Access to private APM modules
- **Type**: Fine-grained Personal Access Token (org or user-scoped)
- **Permissions**: Repository read access to whatever repositories you want APM to install APM modules from
- **Required**: Only for private modules (public modules work without auth)
- **Fallback**: Public module installation works without any token

##### GITHUB_TOKEN (User PAT - Optional)
```bash
export GITHUB_TOKEN=ghp_user_token_here
```
- **Purpose**: Codex CLI authentication for GitHub Models free inference
- **Type**: Fine-grained Personal Access Token (user-scoped)
- **Permissions**: Models scope (read)
- **Required**: Only when using Codex CLI with GitHub Models
- **Fallback**: Used by Codex CLI when no dedicated token is provided

### Common Setup Scenarios

#### Scenario 1: Basic Setup (Public modules + Codex)
```bash
export GITHUB_TOKEN=ghp_models_token         # For GitHub Models (optional)
```

#### Scenario 2: Enterprise Setup (Private org modules + GitHub Models)
```bash
export GITHUB_APM_PAT=ghp_org_token          # For private org modules
export GITHUB_TOKEN=ghp_models_token         # For GitHub Models free inference
```

#### Scenario 3: Minimal Setup (Public modules only)
```bash
# No tokens needed for public modules
# APM will work with public modules without any authentication
```

### GitHub Enterprise Support

APM supports all GitHub Enterprise deployment models. Configuration depends on your organization's GitHub deployment.

#### Default Behavior (github.com)

By default, APM resolves package references to `github.com`:

```bash
apm install danielmeppiel/compliance-rules
# Resolves to: github.com/danielmeppiel/compliance-rules
```

#### GitHub Enterprise Server (Self-Hosted)

For organizations using self-hosted GitHub Enterprise with custom domains:

```bash
# Set your enterprise domain as default
export GITHUB_HOST=github.company.com
export GITHUB_APM_PAT=ghp_enterprise_token

# Packages now resolve to your enterprise domain
apm install team/internal-package
# Resolves to: github.company.com/team/internal-package
```

#### GitHub Enterprise Cloud with Data Residency

For organizations using GitHub Enterprise Cloud with regional data residency (`.ghe.com` domains):

```bash
# Set your GHE Cloud domain as default
export GITHUB_HOST=myorg.ghe.com
export GITHUB_APM_PAT=ghp_data_residency_token

# Packages now resolve to your data residency domain
apm install platform/standards
# Resolves to: myorg.ghe.com/platform/standards
```

#### Multiple GitHub Instances

If your organization uses multiple GitHub instances simultaneously:

```bash
# Configure primary host for bare package names
export GITHUB_HOST=github.company.com

# Bare packages use GITHUB_HOST
apm install team/package
# Resolves to: github.company.com/team/package

# FQDN packages work directly (no configuration needed)
apm install partner.ghe.com/external/integration
apm install vendor.github.io/third-party/tool
apm install github.com/public/open-source-package
```

**Key Insight:** Use `GITHUB_HOST` to set your default for bare package names (e.g., `team/repo`). Use FQDN syntax (e.g., `host.com/org/repo`) to explicitly specify any Git host. No allowlist configuration needed.

### Azure DevOps Support

APM supports Azure DevOps Services (cloud) and Azure DevOps Server (self-hosted).

#### Azure DevOps URL Format

Azure DevOps uses a different URL structure than GitHub:
- **GitHub**: `owner/repo` (2 segments)
- **Azure DevOps**: `org/project/repo` (3 segments)

The `_git` segment in Azure DevOps URLs is handled automatically:
```bash
# Both formats work:
apm install dev.azure.com/myorg/myproject/_git/myrepo
apm install dev.azure.com/myorg/myproject/myrepo
```

#### Azure DevOps Services (Cloud)

For Azure DevOps hosted at `dev.azure.com`:

```bash
# Full FQDN syntax (recommended)
apm install dev.azure.com/myorg/myproject/myrepo

# With git reference
apm install dev.azure.com/myorg/myproject/myrepo#main
```

#### Azure DevOps Authentication

Set `GITHUB_APM_PAT` with an Azure DevOps Personal Access Token:

1. Go to: `https://dev.azure.com/{org}/_usersSettings/tokens`
2. Create PAT with **Code (Read)** scope

```bash
export GITHUB_APM_PAT=your_ado_pat
apm install dev.azure.com/myorg/myproject/myrepo
```

#### Legacy visualstudio.com URLs

Legacy Azure DevOps URLs are also supported:

```bash
apm install mycompany.visualstudio.com/myorg/myproject/myrepo
```

#### Azure DevOps Server (Self-Hosted)

For self-hosted Azure DevOps Server instances:

```bash
# Set your Azure DevOps Server as default
export GITHUB_HOST=ado.company.internal
export GITHUB_APM_PAT=your_ado_server_pat

# Install using org/project/repo format
apm install myorg/myproject/myrepo
```

#### Mixed GitHub and Azure DevOps

If your organization uses both GitHub and Azure DevOps:

```bash
# Use bare names for your primary host (GitHub)
export GITHUB_HOST=github.company.com

# Install from GitHub (2-segment format)
apm install team/package

# Use FQDN for Azure DevOps repositories (3-segment format)
apm install dev.azure.com/azure-org/azure-project/compliance-rules
apm install mycompany.visualstudio.com/team/project/standards
```

#### Virtual Packages on Azure DevOps

Virtual packages (individual files) work with Azure DevOps using the 4-segment format:

```bash
# Install individual prompt file from ADO
apm install dev.azure.com/myorg/myproject/myrepo/prompts/code-review.prompt.md
```

### Token Creation Guide

1. **Create Fine-grained PAT** for `GITHUB_APM_PAT`:
   - Go to [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new)  
   - Select "Fine-grained Personal Access Token"
   - Scope: Organization or Personal account (as needed)
   - Permissions: Repository read access


2. **Create User PAT** for `GITHUB_TOKEN` (if using Codex with GitHub Models):
   - Go to [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new)
   - Select "Fine-grained Personal Access Token" 
   - Permissions: Models scope with read access
   - Required for Codex CLI to unlock free GitHub Models inference

## Installation

### Quick Install (Recommended)

The fastest way to get APM running:

```bash
curl -sSL https://raw.githubusercontent.com/danielmeppiel/apm/main/install.sh | sh
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

Download the binary for your platform from [GitHub Releases](https://github.com/danielmeppiel/apm/releases/latest):

#### macOS Apple Silicon
```bash
curl -L https://github.com/danielmeppiel/apm/releases/latest/download/apm-darwin-arm64.tar.gz | tar -xz
sudo mkdir -p /usr/local/lib/apm
sudo cp -r apm-darwin-arm64/* /usr/local/lib/apm/
sudo ln -sf /usr/local/lib/apm/apm /usr/local/bin/apm
```

#### macOS Intel
```bash
curl -L https://github.com/danielmeppiel/apm/releases/latest/download/apm-darwin-x86_64.tar.gz | tar -xz
sudo mkdir -p /usr/local/lib/apm
sudo cp -r apm-darwin-x86_64/* /usr/local/lib/apm/
sudo ln -sf /usr/local/lib/apm/apm /usr/local/bin/apm
```

#### Linux x86_64
```bash
curl -L https://github.com/danielmeppiel/apm/releases/latest/download/apm-linux-x86_64.tar.gz | tar -xz
sudo mkdir -p /usr/local/lib/apm
sudo cp -r apm-linux-x86_64/* /usr/local/lib/apm/
sudo ln -sf /usr/local/lib/apm/apm /usr/local/bin/apm
```

### From Source (Developers)

For development or customization:

```bash
git clone https://github.com/danielmeppiel/apm-cli.git
cd apm-cli

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
git clone https://github.com/danielmeppiel/apm-cli.git
cd apm-cli

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
└── .apm/
    ├── agents/          # AI assistant personalities
    ├── instructions/    # Context and coding standards
    ├── prompts/         # Reusable agent workflows
    └── context/         # Project knowledge base
```

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

Transform your context into the universal `AGENTS.md` format:

```bash
apm compile
```

This generates `AGENTS.md` - a file compatible with all major coding agents.

### 4. Install Dependencies

Install APM and MCP dependencies from your `apm.yml` configuration:

```bash
apm install
```

#### Adding APM Dependencies (Optional)

For reusable context from other projects, add APM dependencies:

```yaml
# Add to apm.yml
dependencies:
  apm:
    - danielmeppiel/compliance-rules  # GDPR, legal workflows  
    - danielmeppiel/design-guidelines # UI/UX standards
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

**What are Virtual Packages?**

Instead of installing an entire package (`owner/repo`), you can install specific files:

```bash
# Install individual files directly
apm install github/awesome-copilot/prompts/architecture-blueprint-generator.prompt.md
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
apm install github/awesome-copilot/prompts/code-review.prompt.md
```

Creates:
```
apm_modules/
└── github/
    └── awesome-copilot-code-review/
        ├── apm.yml
        └── .apm/
            └── prompts/
                └── code-review.prompt.md
```

**Adding to apm.yml:**

Virtual packages work in `apm.yml` just like regular packages:

```yaml
dependencies:
  apm:
    # Regular packages
    - danielmeppiel/compliance-rules
    
    # Virtual packages - individual files
    - github/awesome-copilot/prompts/architecture-blueprint-generator.prompt.md
    - myorg/engineering/instructions/testing-standards.instructions.md
```

**Branch/Tag Support:**

Use `@ref` syntax for specific versions:

```bash
# Install from specific branch
apm install github/awesome-copilot/prompts/code-review.prompt.md@develop

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
apm install github/awesome-copilot/prompts/architecture-blueprint-generator.prompt.md

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
- `.apm/` - Context directory
- `AGENTS.md` - Generated compatibility layer
- `apm_modules/` - Installed APM dependencies
- `*.prompt.md` - Executable agent workflows

Ready to build reliable AI workflows? Let's explore the [core concepts](concepts.md) next!