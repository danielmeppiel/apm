# APM CLI Reference

Complete command-line interface reference for Agent Package Manager (APM).

## Quick Start

```bash
# 1. Set your GitHub tokens (minimal setup)
export GITHUB_APM_PAT=your_fine_grained_token_here
# Optional: export GITHUB_TOKEN=your_models_token           # For Codex CLI with GitHub Models

# 2. Install APM CLI (GitHub org members)
curl -sSL https://raw.githubusercontent.com/danielmeppiel/apm/main/install.sh | sh

# 3. Setup runtime
apm runtime setup copilot  

# 4. Create project
apm init my-project && cd my-project

# 5. Run your first workflow
apm compile && apm run start --param name="<YourGitHubHandle>"
```

## Installation

### Quick Install (Recommended)
```bash
curl -sSL https://raw.githubusercontent.com/danielmeppiel/apm/main/install.sh | sh
```

### Manual Download
Download from [GitHub Releases](https://github.com/danielmeppiel/apm/releases/latest):
```bash
# Linux x86_64
curl -L https://github.com/danielmeppiel/apm/releases/latest/download/apm-linux-x86_64 -o apm && chmod +x apm

# macOS Intel
curl -L https://github.com/danielmeppiel/apm/releases/latest/download/apm-darwin-x86_64 -o apm && chmod +x apm

# macOS Apple Silicon  
curl -L https://github.com/danielmeppiel/apm/releases/latest/download/apm-darwin-arm64 -o apm && chmod +x apm
```

### From Source (Developers)
```bash
git clone https://github.com/danielmeppiel/apm-cli.git
cd apm-cli && pip install -e .
```

## Global Options

```bash
apm [OPTIONS] COMMAND [ARGS]...
```

### Options
- `--version` - Show version and exit
- `--help` - Show help message and exit

## Core Commands

### `apm init` - 🚀 Initialize new APM project

Initialize a new APM project with minimal `apm.yml` configuration (like `npm init`).

```bash
apm init [PROJECT_NAME] [OPTIONS]
```

**Arguments:**
- `PROJECT_NAME` - Optional name for new project directory. Use `.` to explicitly initialize in current directory

**Options:**
- `-y, --yes` - Skip interactive prompts and use auto-detected defaults

**Examples:**
```bash
# Initialize in current directory (interactive)
apm init

# Initialize in current directory with defaults
apm init --yes

# Create new project directory
apm init my-hello-world

# Create project with auto-detected defaults
apm init my-project --yes
```

**Behavior:**
- **Minimal by default**: Creates only `apm.yml` with auto-detected metadata
- **Interactive mode**: Prompts for project details unless `--yes` specified
- **Auto-detection**: Automatically detects author from `git config user.name` and description from project context
- **Brownfield friendly**: Works cleanly in existing projects without file pollution

**Creates:**
- `apm.yml` - Minimal project configuration with empty dependencies and scripts sections

**Auto-detected fields:**
- `name` - From project directory name
- `author` - From `git config user.name` (fallback: "Developer")
- `description` - Generated from project name
- `version` - Defaults to "1.0.0"

### `apm install` - 📦 Install APM and MCP dependencies

Install APM package and MCP server dependencies from `apm.yml` (like `npm install`). Auto-creates minimal `apm.yml` when packages are specified but no manifest exists.

```bash
apm install [PACKAGES...] [OPTIONS]
```

**Arguments:**
- `PACKAGES` - Optional APM packages to add and install (format: `owner/repo`)

**Options:**
- `--runtime TEXT` - Target specific runtime only (copilot, codex, vscode)
- `--exclude TEXT` - Exclude specific runtime from installation
- `--only [apm|mcp]` - Install only specific dependency type
- `--update` - Update dependencies to latest Git references  
- `--dry-run` - Show what would be installed without installing

**Examples:**
```bash
# Install all dependencies from apm.yml
apm install

# Auto-create apm.yml and install package (no init needed!)
apm install danielmeppiel/design-guidelines

# Add multiple packages and install
apm install org/pkg1 org/pkg2

# Install only APM dependencies (skip MCP servers)
apm install --only=apm

# Install only MCP dependencies (skip APM packages)  
apm install --only=mcp

# Preview what would be installed
apm install --dry-run

# Update existing dependencies to latest versions
apm install --update

# Install for all runtimes except Codex
apm install --exclude codex
```

**Auto-Bootstrap Behavior:**
- **With packages + no apm.yml**: Automatically creates minimal `apm.yml`, adds packages, and installs
- **Without packages + no apm.yml**: Shows helpful error suggesting `apm init` or `apm install <org/repo>`
- **With apm.yml**: Works as before - installs existing dependencies or adds new packages

**Dependency Types:**
- **APM Dependencies**: GitHub repositories containing `.apm/` context collections
- **MCP Dependencies**: Model Context Protocol servers for runtime integration

**Working Example with Dependencies:**
```yaml
# Example apm.yml with APM dependencies
name: my-compliance-project
version: 1.0.0
dependencies:
  apm:
    - danielmeppiel/compliance-rules  # GDPR, legal review workflows
    - danielmeppiel/design-guidelines # Accessibility, UI standards
  mcp:
    - github/github-mcp-server
```

```bash
# Install all dependencies (APM + MCP)
apm install

# Install only APM dependencies for faster setup
apm install --only=apm

# Preview what would be installed  
apm install --dry-run
```

### `apm deps` - 🔗 Manage APM package dependencies

Manage APM package dependencies with installation status, tree visualization, and package information.

```bash
apm deps COMMAND [OPTIONS]
```

#### `apm deps list` - 📋 List installed APM dependencies

Show all installed APM dependencies in a Rich table format with context files and agent workflows.

```bash
apm deps list
```

**Examples:**
```bash
# Show all installed APM packages
apm deps list
```

**Sample Output:**
```
┌─────────────────────┬─────────┬──────────────┬─────────────┬─────────────┐
│ Package             │ Version │ Source       │ Context     │ Workflows   │
├─────────────────────┼─────────┼──────────────┼─────────────┼─────────────┤
│ compliance-rules    │ 1.0.0   │ main         │ 2 files     │ 3 wf        │
│ design-guidelines   │ 1.0.0   │ main         │ 1 files     │ 3 wf        │
└─────────────────────┴─────────┴──────────────┴─────────────┴─────────────┘
```

**Output includes:**
- Package name and version
- Source repository/branch information
- Number of context files (instructions, chatmodes, contexts)
- Number of agent workflows (prompts)
- Installation path and status

#### `apm deps tree` - 🌳 Show dependency tree structure

Display dependencies in hierarchical tree format showing context and agent workflows.

```bash
apm deps tree  
```

**Examples:**
```bash
# Show dependency tree
apm deps tree
```

**Sample Output:**
```
company-website (local)
├── compliance-rules@1.0.0
│   ├── 1 instructions
│   ├── 1 chatmodes
│   └── 3 agent workflows
└── design-guidelines@1.0.0
    ├── 1 instructions
    └── 3 agent workflows
```

**Output format:**
- Hierarchical tree showing project name and dependencies
- File counts grouped by type (instructions, chatmodes, agent workflows)
- Version numbers from dependency package metadata
- Version information for each dependency

#### `apm deps info` - ℹ️ Show detailed package information

Display comprehensive information about a specific installed package.

```bash
apm deps info PACKAGE_NAME
```

**Arguments:**
- `PACKAGE_NAME` - Name of the package to show information about

**Examples:**
```bash
# Show details for compliance rules package
apm deps info compliance-rules

# Show info for design guidelines package  
apm deps info design-guidelines
```

**Output includes:**
- Complete package metadata (name, version, description, author)
- Source repository and installation details
- Detailed context file counts by type
- Agent workflow descriptions and counts
- Installation path and status

#### `apm deps clean` - 🧹 Remove all APM dependencies

Remove the entire `apm_modules/` directory and all installed APM packages.

```bash
apm deps clean
```

**Examples:**
```bash
# Remove all APM dependencies (with confirmation)
apm deps clean
```

**Behavior:**
- Shows confirmation prompt before deletion
- Removes entire `apm_modules/` directory
- Displays count of packages that will be removed
- Can be cancelled with Ctrl+C or 'n' response

#### `apm deps update` - 🔄 Update APM dependencies

Update installed APM dependencies to their latest versions.

```bash
apm deps update [PACKAGE_NAME]
```

**Arguments:**
- `PACKAGE_NAME` - Optional. Update specific package only

**Examples:**
```bash
# Update all APM dependencies to latest versions
apm deps update

# Update specific package to latest version
apm deps update compliance-rules
```

**Note:** Package update functionality requires dependency downloading infrastructure from enhanced install command.

### `apm mcp search` - 🔍 Search MCP servers

Search for MCP servers in the GitHub MCP Registry.

```bash
apm mcp search QUERY [OPTIONS]
```

**Arguments:**
- `QUERY` - Search term to find MCP servers

**Options:**
- `--limit INTEGER` - Number of results to show (default: 10)

**Examples:**
```bash
# Search for filesystem-related servers
apm mcp search filesystem

# Search with custom limit
apm mcp search database --limit 5

# Search for GitHub integration
apm mcp search github
```

### `apm mcp show` - 📋 Show MCP server details

Show detailed information about a specific MCP server from the registry.

```bash
apm mcp show SERVER_NAME
```

**Arguments:**
- `SERVER_NAME` - Name or ID of the MCP server to show

**Examples:**
```bash
# Show details for a server by name
apm mcp show @modelcontextprotocol/servers/src/filesystem

# Show details by server ID
apm mcp show a5e8a7f0-d4e4-4a1d-b12f-2896a23fd4f1
```

**Output includes:**
- Server name and description
- Latest version information
- Repository URL
- Available installation packages
- Installation instructions

### `apm run` - 🚀 Execute prompts

Execute a script defined in your apm.yml with parameters and real-time output streaming.

```bash
apm run [SCRIPT_NAME] [OPTIONS]
```

**Arguments:**
- `SCRIPT_NAME` - Name of script to run from apm.yml scripts section

**Options:**
- `-p, --param TEXT` - Parameter in format `name=value` (can be used multiple times)

**Examples:**
```bash
# Run start script (default script)
apm run start --param name="<YourGitHubHandle>"

# Run with different scripts 
apm run start --param name="Alice"
apm run llm --param service=api
apm run debug --param service=api

# Run specific scripts with parameters
apm run llm --param service=api --param environment=prod
```

**Return Codes:**
- `0` - Success
- `1` - Execution failed or error occurred

### `apm preview` - 👀 Preview compiled scripts

Show the processed prompt content with parameters substituted, without executing.

```bash
apm preview [SCRIPT_NAME] [OPTIONS]
```

**Arguments:**
- `SCRIPT_NAME` - Name of script to preview from apm.yml scripts section

**Options:**
- `-p, --param TEXT` - Parameter in format `name=value`

**Examples:**
```bash
# Preview start script
apm preview start --param name="<YourGitHubHandle>"

# Preview specific script with parameters
apm preview llm --param name="Alice"
```

### `apm list` - 📋 List available scripts

Display all scripts defined in apm.yml.

```bash
apm list
```

**Examples:**
```bash
# List all prompts in project
apm list
```

**Output format:**
```
Available scripts:
  start: codex hello-world.prompt.md
  llm: llm hello-world.prompt.md -m github/gpt-4o-mini  
  debug: RUST_LOG=debug codex hello-world.prompt.md
```

### `apm compile` - 📝 Compile APM context files into AGENTS.md

Compile APM context files (chatmodes, instructions, contexts) into a single intelligent AGENTS.md file with conditional sections, markdown link resolution, and project setup auto-detection.

```bash
apm compile [OPTIONS]
```

**Options:**
- `-o, --output TEXT` - Output file path (default: AGENTS.md)
- `--chatmode TEXT` - Chatmode to prepend to the AGENTS.md file
- `--dry-run` - Generate content without writing file
- `--no-links` - Skip markdown link resolution
- `--with-constitution/--no-constitution` - Include Spec Kit `memory/constitution.md` verbatim at top inside a delimited block (default: `--with-constitution`). When disabled, any existing block is preserved but not regenerated.
- `--watch` - Auto-regenerate on changes (file system monitoring)
- `--validate` - Validate context without compiling

**Examples:**
```bash
# Basic compilation with auto-detected context
apm compile

# Generate with specific chatmode
apm compile --chatmode architect

# Preview without writing file
apm compile --dry-run

# Custom output file
apm compile --output docs/AI-CONTEXT.md

# Validate context without generating output
apm compile --validate

# Watch for changes and auto-recompile (development mode)
apm compile --watch

# Watch mode with dry-run for testing
apm compile --watch --dry-run

# Compile injecting Spec Kit constitution (auto-detected)
apm compile --with-constitution

# Recompile WITHOUT updating the block but preserving previous injection
apm compile --no-constitution
```

**Watch Mode:**
- Monitors `.apm/`, `.github/instructions/`, `.github/chatmodes/` directories
- Auto-recompiles when `.md` or `apm.yml` files change
- Includes 1-second debounce to prevent rapid recompilation
- Press Ctrl+C to stop watching
- Requires `watchdog` library (automatically installed)

**Validation Mode:**
- Checks primitive structure and frontmatter completeness
- Displays actionable suggestions for fixing validation errors
- Exits with error code 1 if validation fails
- No output file generation in validation-only mode

**Configuration Integration:**
The compile command supports configuration via `apm.yml`:

```yaml
compilation:
  output: "AGENTS.md"           # Default output file
  chatmode: "backend-engineer"  # Default chatmode to use
  resolve_links: true           # Enable markdown link resolution
```

Command-line options always override `apm.yml` settings. Priority order:
1. Command-line flags (highest priority)
2. `apm.yml` compilation section
3. Built-in defaults (lowest priority)

**Generated AGENTS.md structure:**
- **Header** - Generation metadata and APM version
- **(Optional) Spec Kit Constitution Block** - Delimited block:
  - Markers: `<!-- SPEC-KIT CONSTITUTION: BEGIN -->` / `<!-- SPEC-KIT CONSTITUTION: END -->`
  - Second line includes `hash: <sha256_12>` for drift detection
  - Entire raw file content in between (Phase 0: no summarization)
- **Pattern-based Sections** - Content grouped by exact `applyTo` patterns from instruction context files (e.g., "Files matching `**/*.py`")
- **Footer** - Regeneration instructions

The structure is entirely dictated by the instruction context found in `.apm/` and `.github/instructions/` directories. No predefined sections or project detection are applied.

**Primitive Discovery:**
- **Chatmodes**: `.chatmode.md` files in `.apm/chatmodes/`, `.github/chatmodes/`
- **Instructions**: `.instructions.md` files in `.apm/instructions/`, `.github/instructions/`
- **Contexts**: `.context.md`, `.memory.md` files in `.apm/context/`, `.github/context/`
- **Workflows**: `.prompt.md` files in project and `.github/prompts/`

APM integrates seamlessly with [Spec-kit](https://github.com/github/spec-kit) for specification-driven development, automatically injecting Spec-kit `constitution` into the compiled context layer.

### `apm config` - ⚙️ Configure APM CLI

Display APM CLI configuration information.

```bash
apm config [OPTIONS]
```

**Options:**
- `--show` - Show current configuration

**Examples:**
```bash
# Show current configuration
apm config --show
```

## Runtime Management

### `apm runtime` - 🤖 Manage AI runtimes

APM manages AI runtime installation and configuration automatically. Currently supports two runtimes: `codex`, and `llm`.

```bash
apm runtime COMMAND [OPTIONS]
```

**Supported Runtimes:**
- **`codex`** - OpenAI Codex CLI with GitHub Models support
- **`llm`** - Simon Willison's LLM library with multiple providers

#### `apm runtime setup` - ⚙️ Install AI runtime

Download and configure an AI runtime from official sources.

```bash
apm runtime setup RUNTIME_NAME [OPTIONS]
```

**Arguments:**
- `RUNTIME_NAME` - Runtime to remove: `codex`, or `llm`

**Options:**
- `--vanilla` - Install runtime without APM configuration (uses runtime's native defaults)

**Examples:**
```bash
# Install Codex with APM defaults
apm runtime setup codex

# Install LLM with APM defaults  
apm runtime setup llm
```

**Default Behavior:**
- Installs runtime binary from official sources
- Configures with GitHub Models (free) as APM default
- Creates configuration file at `~/.codex/config.toml` or similar
- Provides clear logging about what's being configured

**Vanilla Behavior (`--vanilla` flag):**
- Installs runtime binary only
- No APM-specific configuration applied
- Uses runtime's native defaults (e.g., OpenAI for Codex)
- No configuration files created by APM

#### `apm runtime list` - 📋 Show installed runtimes

List all available runtimes and their installation status.

```bash
apm runtime list
```

**Output includes:**
- Runtime name and description
- Installation status (✅ Installed / ❌ Not installed)
- Installation path and version
- Configuration details

#### `apm runtime remove` - 🗑️ Uninstall runtime

Remove an installed runtime and its configuration.

```bash
apm runtime remove RUNTIME_NAME
```

**Arguments:**
- `RUNTIME_NAME` - Runtime to remove: `codex`, or `llm`

#### `apm runtime status` - 📊 Show runtime status

Display which runtime APM will use for execution and runtime preference order.

```bash
apm runtime status
```

**Output includes:**
- Runtime preference order (codex → llm)
- Currently active runtime
- Next steps if no runtime is available

#### `apm runtime status` - Show runtime status

Display detailed status for a specific runtime.

```bash
apm runtime status RUNTIME_NAME
```

**Arguments:**
- `RUNTIME_NAME` - Runtime to check: `codex` or `llm`

## File Formats

### APM Project Configuration (`apm.yml`)
```yaml
name: my-project
version: 1.0.0
description: My APM application
author: Your Name
scripts:
  start: "codex hello-world.prompt.md"
  llm: "llm hello-world.prompt.md -m github/gpt-4o-mini"
  debug: "RUST_LOG=debug codex hello-world.prompt.md"

dependencies:
  mcp:
    - ghcr.io/github/github-mcp-server
```

### Prompt Format (`.prompt.md`)
```markdown
---
description: Brief description of what this prompt does
mcp:
  - ghcr.io/github/github-mcp-server
input:
  - param1
  - param2
---

# Prompt Title

Your prompt content here with ${input:param1} substitution.
```

### Supported Prompt Locations
APM discovers `.prompt.md` files anywhere in your project:
- `./hello-world.prompt.md`
- `./prompts/my-prompt.prompt.md`
- `./.github/prompts/workflow.prompt.md` 
- `./docs/prompts/helper.prompt.md`

## Quick Start Workflow

```bash
# 1. Initialize new project (like npm init)
apm init my-hello-world

# 2. Navigate to project
cd my-hello-world

# 3. Discover MCP servers (optional)
apm search filesystem
apm show @modelcontextprotocol/servers/src/filesystem

# 4. Install dependencies (like npm install)
apm install

# 5. Run the hello world prompt
apm run start --param name="<YourGitHubHandle>"

# 6. Preview before execution
apm preview start --param name="<YourGitHubHandle>"

# 7. List available prompts
apm list
```

## Tips & Best Practices

1. **Start with runtime setup**: Run `apm runtime setup copilot` 
2. **Use GitHub Models for free tier**: Set `GITHUB_TOKEN` (user-scoped with Models read permission) for free Codex access
3. **Discover MCP servers**: Use `apm search` to find available MCP servers before adding to apm.yml
4. **Preview before running**: Use `apm preview` to check parameter substitution
5. **Organize prompts**: Use descriptive names and place in logical directories
6. **Version control**: Include `.prompt.md` files and `apm.yml` in your git repository
7. **Parameter naming**: Use clear, descriptive parameter names in prompts
8. **Error handling**: Always check return codes in scripts and CI/CD
9. **MCP integration**: Declare MCP dependencies in both `apm.yml` and prompt frontmatter

## Integration Examples

### In CI/CD (GitHub Actions)
```yaml
- name: Setup APM runtime
  run: |
    apm runtime setup codex  
    # Purpose-specific authentication
    export GITHUB_APM_PAT=${{ secrets.GITHUB_APM_PAT }}          # Private modules + fallback
    export GITHUB_TOKEN=${{ secrets.GITHUB_TOKEN }}              # Optional: Codex CLI with GitHub Models
    
- name: Setup APM project
  run: apm install
    
- name: Run code review
  run: |
    apm run code-review \
      --param pr_number=${{ github.event.number }}
```

### In Development Scripts
```bash
#!/bin/bash
# Setup and run APM project
apm runtime setup codex  
# Fine-grained token preferred
export GITHUB_APM_PAT=your_fine_grained_token      # Private modules + fallback auth
export GITHUB_TOKEN=your_models_token              # Codex CLI with GitHub Models

cd my-apm-project
apm install

# Run documentation analysis
if apm run document --param project_name=$(basename $PWD); then
    echo "Documentation analysis completed"
else
    echo "Documentation analysis failed" 
    exit 1
fi
```

### Project Structure Example
```
my-apm-project/
├── apm.yml                           # Project configuration
├── README.md                         # Project documentation  
├── hello-world.prompt.md             # Main prompt file
├── prompts/
│   ├── code-review.prompt.md         # Code review prompt
│   └── documentation.prompt.md       # Documentation prompt
└── .github/
    └── workflows/
        └── apm-ci.yml                # CI using APM prompts
```
