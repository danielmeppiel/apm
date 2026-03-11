---
title: "Installation"
sidebar:
  order: 1
---

Get APM running in seconds. No tokens, no configuration — just install and go.

## Quick Install (Recommended)

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
- `.github/prompts/*.prompt.md` - Reusable prompt templates
- `.github/agents/*.agent.md` - Agent definitions
- `.github/skills/{folder-name}/` - Skills with `SKILL.md` meta-guide

For Claude Code (when `.claude/` exists):
- `.claude/commands/*.md` - Slash commands

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

See [Prompts Guide](../../guides/prompts/#running-prompts) for complete auto-discovery documentation.

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

1. **Learn the concepts**: Read [Core Concepts](../../introduction/how-it-works/) to understand the AI-Native Development framework
2. **Study examples**: Check [Examples & Use Cases](../../reference/examples/) for real-world patterns  
3. **Build workflows**: See [Context Guide](../../introduction/key-concepts/) to create advanced workflows
4. **Explore dependencies**: See [Dependency Management](../../guides/dependencies/) for sharing context across projects
5. **Explore integrations**: Review [Integrations Guide](../../integrations/ide-tool-integration/) for tool compatibility

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

Ready to build reliable AI workflows? Let's explore the [core concepts](../../introduction/how-it-works/) next!