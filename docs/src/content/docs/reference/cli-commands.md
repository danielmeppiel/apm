---
title: "CLI Commands"
sidebar:
  order: 1
---

Complete reference for all APM CLI commands and options.

:::tip[New to APM?]
See [Installation](../../getting-started/installation/) and [Quick Start](../../getting-started/quick-start/) to get up and running.
:::

## Global Options

```bash
apm [OPTIONS] COMMAND [ARGS]...
```

### Options
- `--version` - Show version and exit
- `--help` - Show help message and exit

## Core Commands

### `apm init` - Initialize new APM project

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

### `apm install` - Install APM and MCP dependencies

Install APM package and MCP server dependencies from `apm.yml` (like `npm install`). Auto-creates minimal `apm.yml` when packages are specified but no manifest exists.

```bash
apm install [PACKAGES...] [OPTIONS]
```

**Arguments:**
- `PACKAGES` - Optional APM packages to add and install. Accepts shorthand (`owner/repo`), HTTPS URLs, SSH URLs, FQDN shorthand (`host/owner/repo`), or local filesystem paths (`./path`, `../path`, `/absolute/path`, `~/path`). All forms are normalized to canonical format in `apm.yml`.

**Options:**
- `--runtime TEXT` - Target specific runtime only (copilot, codex, vscode)
- `--exclude TEXT` - Exclude specific runtime from installation
- `--only [apm|mcp]` - Install only specific dependency type
- `--update` - Update dependencies to latest Git references  
- `--force` - Overwrite locally-authored files on collision
- `--dry-run` - Show what would be installed without installing
- `--parallel-downloads INTEGER` - Max concurrent package downloads (default: 4, 0 to disable)
- `--verbose` - Show individual file paths and full error details in the diagnostic summary
- `--trust-transitive-mcp` - Trust self-defined MCP servers from transitive packages (skip re-declaration requirement)

**Behavior:**
- `apm install` (no args): Installs **all** packages from `apm.yml`
- `apm install <package>`: Installs **only** the specified package (adds to `apm.yml` if not present)

**Diff-Aware Installation (manifest as source of truth):**
- MCP servers already configured with matching config are skipped (`already configured`)
- MCP servers already configured but with changed manifest config are re-applied automatically (`updated`)
- APM packages removed from `apm.yml` have their deployed files cleaned up on the next full `apm install`
- APM packages whose ref/version changed in `apm.yml` are re-downloaded automatically (no `--update` needed)
- `--force` remains available for full overwrite/reset scenarios

**Examples:**
```bash
# Install all dependencies from apm.yml
apm install

# Install ONLY this package (not others in apm.yml)
apm install microsoft/apm-sample-package

# Install via HTTPS URL (normalized to owner/repo in apm.yml)
apm install https://github.com/microsoft/apm-sample-package.git

# Install from a non-GitHub host (FQDN preserved)
apm install https://gitlab.com/acme/coding-standards.git

# Add multiple packages and install
apm install org/pkg1 org/pkg2

# Install a Claude Skill from a subdirectory
apm install ComposioHQ/awesome-claude-skills/brand-guidelines

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

# Trust self-defined MCP servers from transitive packages
apm install --trust-transitive-mcp

# Install from a local path (copies to apm_modules/_local/)
apm install ./packages/my-shared-skills
apm install /home/user/repos/my-ai-package
```

**Auto-Bootstrap Behavior:**
- **With packages + no apm.yml**: Automatically creates minimal `apm.yml`, adds packages, and installs
- **Without packages + no apm.yml**: Shows helpful error suggesting `apm init` or `apm install <org/repo>`
- **With apm.yml**: Works as before - installs existing dependencies or adds new packages

**Dependency Types:**

- **APM Dependencies**: Git repositories containing `apm.yml` (GitHub, GitLab, Bitbucket, or any git host)
- **Claude Skills**: Repositories with `SKILL.md` (auto-generates `apm.yml` upon installation)
  - Example: `apm install ComposioHQ/awesome-claude-skills/brand-guidelines`
  - Skills are transformed to `.github/agents/*.agent.md` for VSCode target
- **Hook Packages**: Repositories with `hooks/*.json` (no `apm.yml` or `SKILL.md` required)
  - Example: `apm install anthropics/claude-plugins-official/plugins/hookify`
- **Virtual Packages**: Single files or collections installed directly from URLs
  - Single `.prompt.md` or `.agent.md` files from any GitHub repository
  - Collections from curated sources (e.g., `github/awesome-copilot`)
  - Example: `apm install github/awesome-copilot/skills/review-and-refactor`
- **MCP Dependencies**: Model Context Protocol servers for runtime integration

**Working Example with Dependencies:**
```yaml
# Example apm.yml with APM dependencies
name: my-compliance-project
version: 1.0.0
dependencies:
  apm:
    - microsoft/apm-sample-package  # Design standards, prompts
    - github/awesome-copilot/skills/review-and-refactor  # Code review skill
  mcp:
    - io.github.github/github-mcp-server
```

```bash
# Install all dependencies (APM + MCP)
apm install

# Install only APM dependencies for faster setup
apm install --only=apm

# Preview what would be installed  
apm install --dry-run
```

**Auto-Detection:**

APM automatically detects which integrations to enable based on your project structure:

- **VSCode integration**: Enabled when `.github/` directory exists
- **Claude integration**: Enabled when `.claude/` directory exists
- **Cursor integration**: Enabled when `.cursor/` directory exists
- All integrations can coexist in the same project

**VSCode Integration (`.github/` present):**

When you run `apm install`, APM automatically integrates primitives from installed packages:

- **Prompts**: `.prompt.md` files → `.github/prompts/*.prompt.md`
- **Agents**: `.agent.md` files → `.github/agents/*.agent.md`
- **Chatmodes**: `.chatmode.md` files → `.github/agents/*.agent.md` (renamed to modern format)
- **Instructions**: `.instructions.md` files → `.github/instructions/*.instructions.md`
- **Control**: Disable with `apm config set auto-integrate false`
- **Smart updates**: Only updates when package version/commit changes
- **Hooks**: Hook `.json` files → `.github/hooks/*.json` with scripts bundled
- **Collision detection**: Skips local files that aren't managed by APM; use `--force` to overwrite

**Diagnostic Summary:**

After installation completes, APM prints a grouped diagnostic summary instead of inline warnings. Categories include collisions (skipped files), cross-package skill replacements, warnings, and errors.

- **Normal mode**: Shows counts and actionable tips (e.g., "9 files skipped -- use `apm install --force` to overwrite")
- **Verbose mode** (`--verbose`): Additionally lists individual file paths grouped by package, and full error details

```bash
# See exactly which files were skipped or had issues
apm install --verbose
```

**Claude Integration (`.claude/` present):**

APM also integrates with Claude Code when `.claude/` directory exists:

- **Agents**: `.agent.md` and `.chatmode.md` files → `.claude/agents/*.md`
- **Commands**: `.prompt.md` files → `.claude/commands/*.md`
- **Hooks**: Hook definitions merged into `.claude/settings.json` hooks key

**Skill Integration:**

Skills are copied directly to target directories:

- **Primary**: `.github/skills/{skill-name}/` — Entire skill folder copied
- **Compatibility**: `.claude/skills/{skill-name}/` — Also copied if `.claude/` folder exists

**Example Integration Output**:
```
✓ microsoft/apm-sample-package
  ├─ 3 prompts integrated → .github/prompts/
  ├─ 1 instruction(s) integrated → .github/instructions/
  ├─ 1 agents integrated → .claude/agents/
  └─ 3 commands integrated → .claude/commands/
```

This makes all package primitives available in VSCode, Cursor, Claude Code, and compatible editors for immediate use with your coding agents.

### `apm uninstall` - Remove APM packages

Remove installed APM packages and their integrated files.

```bash
apm uninstall [OPTIONS] PACKAGES...
```

**Arguments:**
- `PACKAGES...` - One or more packages to uninstall. Accepts any format — shorthand (`owner/repo`), HTTPS URL, SSH URL, or FQDN. APM resolves each to the canonical identity stored in `apm.yml`.

**Options:**
- `--dry-run` - Show what would be removed without removing

**Examples:**
```bash
# Uninstall a package
apm uninstall microsoft/apm-sample-package

# Uninstall using an HTTPS URL (resolves to same identity)
apm uninstall https://github.com/microsoft/apm-sample-package.git

# Preview what would be removed
apm uninstall microsoft/apm-sample-package --dry-run
```

**What Gets Removed:**

| Item | Location |
|------|----------|
| Package entry | `apm.yml` dependencies section |
| Package folder | `apm_modules/owner/repo/` |
| Transitive deps | `apm_modules/` (orphaned transitive dependencies) |
| Integrated prompts | `.github/prompts/*.prompt.md` |
| Integrated agents | `.github/agents/*.agent.md` |
| Integrated chatmodes | `.github/agents/*.agent.md` |
| Claude commands | `.claude/commands/*.md` |
| Skill folders | `.github/skills/{folder-name}/` |
| Integrated hooks | `.github/hooks/*.json` |
| Claude hook settings | `.claude/settings.json` (hooks key cleaned) |
| Cursor rules | `.cursor/rules/*.mdc` |
| Cursor agents | `.cursor/agents/*.md` |
| Cursor skills | `.cursor/skills/{folder-name}/` |
| Cursor hooks | `.cursor/hooks.json` (hooks key cleaned) |
| Lockfile entries | `apm.lock.yaml` (removed packages + orphaned transitives) |

**Behavior:**
- Removes package from `apm.yml` dependencies
- Deletes package folder from `apm_modules/`
- Removes orphaned transitive dependencies (npm-style pruning via `apm.lock.yaml`)
- Removes all deployed integration files tracked in `apm.lock.yaml` `deployed_files`
- Updates `apm.lock.yaml` (or deletes it if no dependencies remain)
- Cleans up empty parent directories
- Safe operation: only removes files tracked in the `deployed_files` manifest

### `apm prune` - Remove orphaned packages

Remove APM packages from `apm_modules/` that are not listed in `apm.yml`, along with their deployed integration files (prompts, agents, hooks, etc.).

```bash
apm prune [OPTIONS]
```

**Options:**
- `--dry-run` - Show what would be removed without removing

**Examples:**
```bash
# Remove orphaned packages and their deployed files
apm prune

# Preview what would be removed
apm prune --dry-run
```

**Behavior:**
- Removes orphaned package directories from `apm_modules/`
- Removes deployed integration files (prompts, agents, hooks, etc.) for pruned packages using the `deployed_files` manifest in `apm.lock.yaml`
- Updates `apm.lock.yaml` to reflect the pruned state

### `apm pack` - Create a portable bundle

Create a self-contained bundle from installed APM dependencies using the `deployed_files` recorded in `apm.lock.yaml` as the source of truth.

```bash
apm pack [OPTIONS]
```

**Options:**
- `-o, --output PATH` - Output directory (default: `./build`)
- `-t, --target [copilot|vscode|claude|all]` - Filter files by target. Auto-detects from `apm.yml` if not specified. `vscode` is an alias for `copilot`
- `--archive` - Produce a `.tar.gz` archive instead of a directory
- `--dry-run` - List files that would be packed without writing anything
- `--format [apm|plugin]` - Bundle format (default: `apm`)

**Examples:**
```bash
# Pack to ./build/<name>-<version>/
apm pack

# Pack as a .tar.gz archive
apm pack --archive

# Pack only VS Code / Copilot files
apm pack --target vscode

# Preview what would be packed
apm pack --dry-run

# Custom output directory
apm pack -o dist/
```

**Behavior:**
- Reads `apm.lock.yaml` to enumerate all `deployed_files` from installed dependencies
- Copies files preserving directory structure
- Writes an enriched `apm.lock.yaml` inside the bundle with a `pack:` metadata section (the project's own `apm.lock.yaml` is never modified)

**Target filtering:**

| Target | Includes paths starting with |
|--------|------------------------------|
| `vscode` | `.github/` |
| `claude` | `.claude/` |
| `all` | both |

**Enriched lockfile example:**
```yaml
pack:
  format: apm
  target: vscode
  packed_at: '2026-03-09T12:00:00+00:00'
lockfile_version: '1'
generated_at: ...
dependencies:
  - repo_url: owner/repo
    ...
```

### `apm unpack` - Extract a bundle

Extract an APM bundle into the current project with optional completeness verification.

```bash
apm unpack BUNDLE_PATH [OPTIONS]
```

**Arguments:**
- `BUNDLE_PATH` - Path to a `.tar.gz` archive or an unpacked bundle directory

**Options:**
- `-o, --output PATH` - Target project directory (default: current directory)
- `--skip-verify` - Skip completeness verification against the bundle lockfile
- `--dry-run` - Show what would be extracted without writing anything

**Examples:**
```bash
# Unpack an archive into the current directory
apm unpack ./build/my-pkg-1.0.0.tar.gz

# Unpack into a specific directory
apm unpack bundle.tar.gz --output /path/to/project

# Skip verification (useful for partial bundles)
apm unpack bundle.tar.gz --skip-verify

# Preview what would be extracted
apm unpack bundle.tar.gz --dry-run
```

**Behavior:**
- **Additive-only**: only writes files listed in the bundle's `apm.lock.yaml`; never deletes existing files
- If a local file has the same path as a bundle file, the bundle file wins (overwrite)
- Verification checks that all `deployed_files` from the bundle lockfile are present in the bundle
- The bundle's `apm.lock.yaml` is metadata only — it is **not** copied to the output directory

### `apm update` - Update APM to the latest version

Update the APM CLI to the latest version available on GitHub releases.

```bash
apm update [OPTIONS]
```

**Options:**
- `--check` - Only check for updates without installing

**Examples:**
```bash
# Check if an update is available
apm update --check

# Update to the latest version
apm update
```

**Behavior:**
- Fetches latest release from GitHub
- Compares with current installed version
- Downloads and runs the official platform installer (`install.sh` on macOS/Linux, `install.ps1` on Windows)
- Preserves existing configuration and projects
- Shows progress and success/failure status

**Version Checking:**
APM automatically checks for updates (at most once per day) when running any command. If a newer version is available, you'll see a yellow warning:

```
⚠️  A new version of APM is available: 0.7.0 (current: 0.6.3)
Run apm update to upgrade
```

This check is non-blocking and cached to avoid slowing down the CLI.

**Manual Update:**
If the automatic update fails, you can always update manually:

#### Linux / macOS
```bash
curl -sSL https://raw.githubusercontent.com/microsoft/apm/main/install.sh | sh
```

#### Windows
```powershell
powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/microsoft/apm/main/install.ps1 | iex"
```

### `apm deps` - Manage APM package dependencies

Manage APM package dependencies with installation status, tree visualization, and package information.

```bash
apm deps COMMAND [OPTIONS]
```

#### `apm deps list` - List installed APM dependencies

Show all installed APM dependencies in a Rich table format with per-primitive counts.

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
┌─────────────────────┬─────────┬──────────┬─────────┬──────────────┬────────┬────────┐
│ Package             │ Version │ Source   │ Prompts │ Instructions │ Agents │ Skills │
├─────────────────────┼─────────┼──────────┼─────────┼──────────────┼────────┼────────┤
│ compliance-rules    │ 1.0.0   │ github   │    2    │      1       │   -    │   1    │
│ design-guidelines   │ 1.0.0   │ github   │    -    │      1       │   1    │   -    │
└─────────────────────┴─────────┴──────────┴─────────┴──────────────┴────────┴────────┘
```

**Output includes:**
- Package name and version
- Source information
- Per-primitive counts (prompts, instructions, agents, skills)

#### `apm deps tree` - Show dependency tree structure

Display dependencies in hierarchical tree format with primitive counts.

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

#### `apm deps info` - Show detailed package information

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

#### `apm deps clean` - Remove all APM dependencies

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

#### `apm deps update` - Update APM dependencies

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

### `apm mcp` - Browse MCP server registry

Browse and discover MCP servers from the GitHub MCP Registry.

```bash
apm mcp COMMAND [OPTIONS]
```

#### `apm mcp list` - List MCP servers

List all available MCP servers from the registry.

```bash
apm mcp list [OPTIONS]
```

**Options:**
- `--limit INTEGER` - Number of results to show

**Examples:**
```bash
# List available MCP servers
apm mcp list

# Limit results
apm mcp list --limit 20
```

#### `apm mcp search` - Search MCP servers

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

#### `apm mcp show` - Show MCP server details

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

### `apm run` (Experimental) - Execute prompts

Execute a script defined in your apm.yml with parameters and real-time output streaming.

> See the [Agent Workflows guide](../../guides/agent-workflows/) for usage details.

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

### `apm preview` - Preview compiled scripts

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

### `apm list` - List available scripts

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

### `apm compile` - Compile APM context into distributed AGENTS.md files

Compile APM context files (chatmodes, instructions, contexts) into distributed AGENTS.md files with conditional sections, markdown link resolution, and project setup auto-detection.

```bash
apm compile [OPTIONS]
```

**Options:**
- `-o, --output TEXT` - Output file path (for single-file mode)
- `-t, --target [vscode|agents|claude|all]` - Target agent format. `agents` is an alias for `vscode`. Auto-detects if not specified.
- `--chatmode TEXT` - Chatmode to prepend to the AGENTS.md file
- `--dry-run` - Preview compilation without writing files (shows placement decisions)
- `--no-links` - Skip markdown link resolution
- `--with-constitution/--no-constitution` - Include Spec Kit `memory/constitution.md` verbatim at top inside a delimited block (default: `--with-constitution`). When disabled, any existing block is preserved but not regenerated.
- `--watch` - Auto-regenerate on changes (file system monitoring)
- `--validate` - Validate primitives without compiling
- `--single-agents` - Force single-file compilation (legacy mode)
- `-v, --verbose` - Show detailed source attribution and optimizer analysis
- `--local-only` - Ignore dependencies, compile only local primitives
- `--clean` - Remove orphaned AGENTS.md files that are no longer generated

**Target Auto-Detection:**

When `--target` is not specified, APM auto-detects based on existing project structure:

| Condition | Target | Output |
|-----------|--------|--------|
| `.github/` exists only | `vscode` | AGENTS.md + .github/ |
| `.claude/` exists only | `claude` | CLAUDE.md + .claude/ |
| Both folders exist | `all` | All outputs |
| Neither folder exists | `minimal` | AGENTS.md only |

You can also set a persistent target in `apm.yml`:
```yaml
name: my-project
version: 1.0.0
target: vscode  # or claude, or all
```

**Target Formats (explicit):**

| Target | Output Files | Best For |
|--------|--------------|----------|
| `vscode` | AGENTS.md, .github/prompts/, .github/agents/, .github/skills/ | GitHub Copilot, Cursor, Codex, Gemini |
| `claude` | CLAUDE.md, .claude/commands/, SKILL.md | Claude Code, Claude Desktop |
| `all` | All of the above | Universal compatibility |

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

# Target specific agent formats
apm compile --target vscode    # AGENTS.md + .github/ only
apm compile --target claude    # CLAUDE.md + .claude/ only
apm compile --target all       # All formats (default)

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
  exclude:                      # Directory exclusion patterns (glob syntax)
    - "apm_modules/**"          # Exclude installed packages
    - "tmp/**"                  # Exclude temporary files
    - "coverage/**"             # Exclude test coverage
    - "**/test-fixtures/**"     # Exclude test fixtures at any depth
```

**Directory Exclusion Patterns:**

Use the `exclude` field to skip directories during compilation. This improves performance in large monorepos and prevents duplicate instruction discovery from source package development directories.

**Pattern examples:**
- `tmp` - Matches directory named "tmp" at any depth
- `projects/packages/apm` - Matches specific nested path
- `**/node_modules` - Matches "node_modules" at any depth
- `coverage/**` - Matches "coverage" and all subdirectories
- `projects/**/apm/**` - Complex nested matching with `**`

**Default exclusions** (always applied, matched on exact path components):
- `node_modules`, `__pycache__`, `.git`, `dist`, `build`, `apm_modules`
- Hidden directories (starting with `.`)

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

### `apm config` - Configure APM CLI

Manage APM CLI configuration settings. Running `apm config` without subcommands displays the current configuration.

```bash
apm config [COMMAND]
```

#### `apm config` - Show current configuration (default behavior)

Display current APM CLI configuration and project settings.

```bash
apm config
```

**What's displayed:**
- Project configuration from `apm.yml` (if in an APM project)
  - Project name, version, entrypoint
  - Number of MCP dependencies
  - Compilation settings (output, chatmode, resolve_links)
- Global configuration
  - APM CLI version
  - `auto-integrate` setting

**Examples:**
```bash
# Show current configuration
apm config
```

#### `apm config get` - Get a configuration value

Get a specific configuration value or display all configuration values.

```bash
apm config get [KEY]
```

**Arguments:**
- `KEY` (optional) - Configuration key to retrieve. Supported keys:
  - `auto-integrate` - Whether to automatically integrate `.prompt.md` files into AGENTS.md

If `KEY` is omitted, displays all configuration values.

**Examples:**
```bash
# Get auto-integrate setting
apm config get auto-integrate

# Show all configuration
apm config get
```

#### `apm config set` - Set a configuration value

Set a configuration value globally for APM CLI.

```bash
apm config set KEY VALUE
```

**Arguments:**
- `KEY` - Configuration key to set. Supported keys:
  - `auto-integrate` - Enable/disable automatic integration of `.prompt.md` files
- `VALUE` - Value to set. For boolean keys, use: `true`, `false`, `yes`, `no`, `1`, `0`

**Configuration Keys:**

**`auto-integrate`** - Control automatic prompt integration
- **Type:** Boolean
- **Default:** `true`
- **Description:** When enabled, APM automatically discovers and integrates `.prompt.md` files from `.github/prompts/` and `.apm/prompts/` directories into the compiled AGENTS.md file. This ensures all prompts are available to coding agents without manual compilation.
- **Use Cases:**
  - Set to `false` if you want to manually manage which prompts are compiled
  - Set to `true` to ensure all prompts are always included in the context

**Examples:**
```bash
# Enable auto-integration (default)
apm config set auto-integrate true

# Disable auto-integration
apm config set auto-integrate false

# Using alternative boolean values
apm config set auto-integrate yes
apm config set auto-integrate 1
```

## Runtime Management (Experimental)

### `apm runtime` (Experimental) - Manage AI runtimes

APM manages AI runtime installation and configuration automatically. Currently supports three runtimes: `copilot`, `codex`, and `llm`.

> See the [Agent Workflows guide](../../guides/agent-workflows/) for usage details.

```bash
apm runtime COMMAND [OPTIONS]
```

**Supported Runtimes:**
- **`copilot`** - GitHub Copilot coding agent
- **`codex`** - OpenAI Codex CLI with GitHub Models support
- **`llm`** - Simon Willison's LLM library with multiple providers

#### `apm runtime setup` - Install AI runtime

Download and configure an AI runtime from official sources.

```bash
apm runtime setup [OPTIONS] {copilot|codex|llm}
```

**Arguments:**
- `{copilot|codex|llm}` - Runtime to install

**Options:**
- `--version TEXT` - Specific version to install
- `--vanilla` - Install runtime without APM configuration (uses runtime's native defaults)

**Examples:**
```bash
# Install Codex with APM defaults
apm runtime setup codex

# Install LLM with APM defaults  
apm runtime setup llm
```

**Windows support:**
- On Windows, APM runs the setup scripts through PowerShell automatically
- No special flags are required
- Platform detection is automatic

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

#### `apm runtime list` - Show installed runtimes

List all available runtimes and their installation status.

```bash
apm runtime list
```

**Output includes:**
- Runtime name and description
- Installation status (✅ Installed / ❌ Not installed)
- Installation path and version
- Configuration details

#### `apm runtime remove` - Uninstall runtime

Remove an installed runtime and its configuration.

```bash
apm runtime remove [OPTIONS] {copilot|codex|llm}
```

**Arguments:**
- `{copilot|codex|llm}` - Runtime to remove

**Options:**
- `--yes` - Confirm the action without prompting

#### `apm runtime status` - Show runtime status

Display which runtime APM will use for execution and runtime preference order.

```bash
apm runtime status
```

**Output includes:**
- Runtime preference order (copilot → codex → llm)
- Currently active runtime
- Next steps if no runtime is available

