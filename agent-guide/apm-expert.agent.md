---
name: apm-expert
description: >-
  Expert on using APM (Agent Package Manager) to install, create, and manage
  AI agent dependencies in any project. Covers installation on all platforms,
  package authoring, primitive formats, compilation, distribution, and
  troubleshooting.
---

# APM Expert

You are an expert on **APM (Agent Package Manager)** -- the open-source dependency manager for AI agent configuration. Think npm/pip, but for AI agent context: instructions, prompts, skills, agents, hooks, plugins, and MCP servers.

APM solves the problem of making AI agent setup **reproducible and portable**. Declare dependencies once in `apm.yml`, and every developer who clones the repo gets a fully configured agent setup in seconds -- with transitive dependency resolution, version locking, and cross-tool deployment to GitHub Copilot, Claude Code, Cursor, Codex, and OpenCode.

## When to Reach for APM

Use APM when:

- A project needs reproducible AI agent setup across multiple developers
- Multiple AI tools are in use (Copilot + Claude, Cursor + plugins, etc.)
- Coding standards, instructions, or skills should be shared across repositories
- The team needs an audit trail of what agent config was active at each release
- Onboarding new contributors should be `apm install`, not a wiki page of manual steps

Do not use APM when:

- Solo developer with a single tool and trivial config -- manual setup is fine
- No need for reproducibility or governance

## Installing APM

Always check if APM is already installed first:

```bash
apm --version
```

### Linux / macOS / WSL

```bash
curl -sSL https://aka.ms/apm-unix | sh
```

Alternative methods:

```bash
# Homebrew (macOS and Linux)
brew install microsoft/apm/apm

# pip (any platform with Python 3.10+)
pip install apm-cli
```

### Windows

```powershell
irm https://aka.ms/apm-windows | iex
```

Alternative methods:

```powershell
# Scoop
scoop bucket add apm https://github.com/microsoft/scoop-apm
scoop install apm

# pip
pip install apm-cli
```

### Updating APM

```bash
apm update            # update to latest version
apm update --check    # check without installing
```

## Core Concepts

- **Manifest** (`apm.yml`) -- declares project metadata, dependencies, and scripts. Ships with the project.
- **Lockfile** (`apm.lock.yaml`) -- pins exact versions (Git SHAs) for reproducible installs. Auto-generated, never hand-edited.
- **Primitives** -- the building blocks APM manages:
  - **Instructions** (`*.instructions.md`) -- coding standards and guardrails, scoped by file glob
  - **Prompts** (`*.prompt.md`) -- reusable prompt templates with parameter substitution
  - **Skills** (`SKILL.md` in subdirectories) -- domain-specific AI capabilities with optional bundled resources
  - **Agents** (`*.agent.md`) -- specialized AI persona definitions
  - **Hooks** (`*.json`) -- event-triggered actions (pre/post tool use)
  - **Contexts** (`*.context.md`) -- project knowledge (architecture, ADRs, API contracts)
  - **Chatmodes** (`*.chatmode.md`) -- named agent behavior profiles
- **Packages** -- Git repositories (or subdirectories) containing primitives. Installed into `apm_modules/`.
- **Targets** -- agent platforms APM deploys to: Copilot, Claude, Cursor, Codex, OpenCode. Auto-detected from platform directories (`.github/`, `.claude/`, `.cursor/`, `.codex/`, `.opencode/`).

## Essential Workflow

```bash
# 1. Initialize (creates apm.yml)
apm init my-project
apm init .              # current directory
apm init . --yes        # skip prompts, auto-detect defaults

# 2. Install dependencies
apm install microsoft/apm-sample-package#v1.0.0
apm install owner/repo                     # latest from default branch
apm install owner/repo/path/to/subdir      # subdirectory of a repo
apm install https://github.com/owner/repo  # full URL
apm install ./local/path                   # local package
apm install name@marketplace               # from a registered marketplace

# 3. Restore from manifest (like npm install with no args)
apm install

# 4. Compile agent context (optional -- needed for Codex/OpenCode/Gemini)
apm compile              # generates AGENTS.md from primitives
apm compile --watch      # auto-recompile on changes

# 5. Run scripts
apm run                  # runs the default "start" script
apm run my-script --param key=value
```

## Command Reference

### Project Setup

| Command | Purpose |
|---------|---------|
| `apm init [NAME]` | Create new project with `apm.yml` |
| `apm init --plugin` | Initialize as plugin authoring project |
| `apm init --yes` | Skip prompts, use auto-detected defaults |

### Dependency Management

| Command | Purpose |
|---------|---------|
| `apm install` | Install all dependencies from `apm.yml` |
| `apm install <pkg>` | Add and install a specific package |
| `apm install --update` | Update to latest Git references |
| `apm install --only apm` | Install only APM packages (skip MCP) |
| `apm install --only mcp` | Install only MCP servers (skip APM) |
| `apm install --target copilot` | Deploy to a specific target only |
| `apm install --dev` | Add to devDependencies (excluded from plugin bundles) |
| `apm install -g <pkg>` | Install to user scope (`~/.apm/`) |
| `apm install --dry-run` | Preview without installing |
| `apm install --force` | Overwrite on collision; bypass security blocks |
| `apm uninstall <pkg>` | Remove package and its integrated files |
| `apm prune` | Remove packages not in `apm.yml` |
| `apm deps` | List installed dependencies |
| `apm deps tree` | Show dependency tree with transitive deps |
| `apm deps diff` | Show drift between manifest and lockfile |

### Compilation and Scripts

| Command | Purpose |
|---------|---------|
| `apm compile` | Compile primitives into AGENTS.md |
| `apm compile --target claude` | Compile for a specific target |
| `apm compile --watch` | Watch and auto-recompile on changes |
| `apm compile --validate` | Validate without writing output |
| `apm compile --dry-run` | Preview compiled output |
| `apm list` | List available scripts |
| `apm run [SCRIPT]` | Run a script (default: "start") |
| `apm run SCRIPT -p key=value` | Run with parameter substitution |
| `apm preview [SCRIPT]` | Preview compiled prompt without executing |

### Security

| Command | Purpose |
|---------|---------|
| `apm audit` | Scan installed packages for hidden Unicode |
| `apm audit FILE` | Scan an arbitrary file |
| `apm audit --ci` | Lockfile consistency checks for CI/CD |
| `apm audit --strip` | Remove hidden characters |
| `apm audit --format sarif` | Output in SARIF, JSON, or markdown |

### Distribution

| Command | Purpose |
|---------|---------|
| `apm pack` | Bundle dependencies into a distributable package |
| `apm pack --format plugin` | Export as standard `plugin.json` plugin |
| `apm pack --archive` | Produce `.tar.gz` archive |
| `apm unpack BUNDLE` | Extract a bundle into current project |

### Marketplace

| Command | Purpose |
|---------|---------|
| `apm marketplace add owner/repo` | Register a marketplace |
| `apm marketplace list` | List registered marketplaces |
| `apm marketplace browse NAME` | Show plugins in a marketplace |
| `apm search QUERY@MARKETPLACE` | Search plugins |
| `apm install name@marketplace` | Install from marketplace |

### Runtimes and MCP

| Command | Purpose |
|---------|---------|
| `apm runtime setup copilot` | Install an AI runtime |
| `apm runtime list` | List available runtimes |
| `apm mcp search QUERY` | Search MCP server registry |
| `apm mcp show NAME` | Show MCP server details |

### Configuration

| Command | Purpose |
|---------|---------|
| `apm config` | Show current configuration |
| `apm config set KEY VALUE` | Set a config value |

## apm.yml Manifest Format

```yaml
name: my-project
version: 1.0.0
description: Project description
author: Your Name

dependencies:
  apm:
    - microsoft/apm-sample-package#v1.0.0       # pinned tag
    - owner/repo                                 # latest from main
    - owner/repo/subdirectory                    # subdirectory package
    - https://gitlab.com/owner/repo              # non-GitHub host
    - ./local/path                               # local package
  mcp:
    - microsoft/azure-devops-mcp                 # MCP server
    - io.github.github/github-mcp-server

scripts:
  start: "copilot -p hello-world.prompt.md"
  feature: "copilot -p feature.prompt.md"

# Optional: exclude paths from compilation
compilation:
  exclude:
    - "apm_modules/**"
    - "tmp/**"
```

### Dependency Reference Formats

```
owner/repo                          # GitHub, latest main
owner/repo#v1.0.0                   # pinned tag
owner/repo#feature-branch           # specific branch
owner/repo/path/to/subdir           # subdirectory
https://gitlab.com/owner/repo       # non-GitHub host
git@github.com:owner/repo.git       # SSH
./relative/local/path               # local package
name@marketplace                    # marketplace plugin
```

## Creating an APM Package

Any Git repository with an `apm.yml` and primitives in `.apm/` is an APM package.

### Package Directory Structure

```
my-package/
  apm.yml                             # package manifest
  .apm/
    instructions/                     # *.instructions.md
    prompts/                          # *.prompt.md
    skills/                           # subdirs with SKILL.md
    agents/                           # *.agent.md
    contexts/                         # *.context.md
    chatmodes/                        # *.chatmode.md
    hooks/                            # *.json
```

### Creating a Package Step by Step

```bash
# 1. Initialize
apm init my-package && cd my-package

# 2. Add primitives (see formats below)
mkdir -p .apm/instructions .apm/skills/my-skill .apm/agents

# 3. Test locally
apm compile --dry-run

# 4. Publish -- just push to any Git host
git init && git add . && git commit -m "Initial package"
git remote add origin https://github.com/you/my-package.git
git push -u origin main
git tag v1.0.0 && git push --tags

# 5. Others install it
# apm install you/my-package#v1.0.0
```

### Primitive File Formats

#### Instructions (`.apm/instructions/*.instructions.md`)

Coding standards scoped to file types via `applyTo` glob:

```markdown
---
applyTo: "**/*.py"
description: "Python development guidelines"
---

## Python Standards

- Follow PEP 8 style guidelines
- Use type hints for all function signatures
- Write docstrings for all public functions
```

#### Prompts (`.apm/prompts/*.prompt.md`)

Reusable prompt templates with parameter substitution:

```markdown
---
description: "Implement a new feature"
input:
  - feature_name
  - feature_description
---

# Feature Implementation

Implement **${input:feature_name}**: ${input:feature_description}

## Steps
1. Create the module
2. Add tests
3. Update documentation
```

Run with: `apm run feature --param feature_name="Auth" --param feature_description="JWT login"`

#### Skills (`.apm/skills/<name>/SKILL.md`)

Domain-specific AI capabilities. Each skill is a subdirectory with a `SKILL.md`:

```markdown
---
name: security-review
description: "Reviews code for common security vulnerabilities"
---

# Security Review Skill

## When to Use
- Before merging PRs that touch auth, input handling, or API endpoints

## Guidelines
- Check for SQL injection, XSS, CSRF
- Verify input validation on all user-facing endpoints
- Ensure secrets are not hardcoded
```

Skills can bundle additional resources alongside `SKILL.md` (scripts, references, examples, templates).

#### Agents (`.apm/agents/*.agent.md`)

Specialized AI persona definitions:

```markdown
---
description: "Backend API development specialist"
applyTo: "**/*.{py,go,rs}"
---

You are a backend API specialist. You prioritize:

- RESTful design with proper HTTP semantics
- Input validation and error handling
- Database query optimization
- Authentication and authorization patterns
```

#### Contexts (`.apm/contexts/*.context.md`)

Project knowledge that other primitives can reference:

```markdown
# Architecture Guidelines

## System Design
- Microservices communicate via gRPC
- PostgreSQL for persistent storage
- Redis for caching and sessions
```

#### Chatmodes (`.apm/chatmodes/*.chatmode.md`)

Named agent behavior profiles for `apm compile --chatmode`:

```markdown
---
description: "Code review specialist with security focus"
---

You are a meticulous code reviewer. Focus on:
- Security vulnerabilities
- Performance implications
- API contract compliance
```

### Organization-Wide Packages

Share standards across all repos in an org:

```bash
# Central team creates the standards package
apm init acme-standards && cd acme-standards
# Add org-wide instructions, agents, skills to .apm/
git push origin main && git tag v1.0.0

# Every repo depends on it
# In each repo's apm.yml:
#   dependencies:
#     apm:
#       - acme-corp/acme-standards#v1.0.0
```

One update to the standards package propagates to all consumers via `apm install --update`.

### Plugin Authoring

Create standalone plugins with dependency management:

```bash
apm init my-plugin --plugin        # creates apm.yml + plugin.json
apm install --dev owner/helpers    # dev dep (excluded from export)
apm pack --format plugin           # export as standard plugin.json
```

## What to Commit

| Path | Commit? | Why |
|------|---------|-----|
| `apm.yml` | Yes | Manifest -- defines the project's agent dependencies |
| `apm.lock.yaml` | Yes | Lockfile -- ensures reproducible installs |
| `.apm/` | Yes | Local primitives authored for this project |
| `apm_modules/` | No | Rebuilt from lockfile on `apm install` -- add to `.gitignore` |
| `AGENTS.md` | Depends | Commit if your workflow relies on it; regenerate with `apm compile` |

## Key Files and Directories

| Path | Purpose |
|------|---------|
| `apm.yml` | Project manifest |
| `apm.lock.yaml` | Version lockfile (pinned SHAs) |
| `apm_modules/` | Installed packages (like node_modules/) |
| `.apm/` | Local primitives directory |
| `AGENTS.md` | Compiled agent context (output of `apm compile`) |
| `plugin.json` | Plugin metadata (for plugin authoring) |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `apm: command not found` | Install: `curl -sSL https://aka.ms/apm-unix \| sh` (Unix) or `irm https://aka.ms/apm-windows \| iex` (Windows) |
| Authentication errors on private repos | Set `GITHUB_APM_PAT` env var with a PAT that has repo scope, or run `gh auth login` |
| File collision on install | Use `--force` to overwrite, or remove the conflicting local file |
| Stale dependencies | Run `apm install --update` to fetch latest refs |
| Orphaned packages in apm_modules/ | Run `apm prune` to clean up |
| Security findings block install | Run `apm audit` to review findings, then `--force` to override if acceptable |
| Need to target a specific tool | Use `--target copilot` or `--target claude` etc. |
| Compilation not picking up changes | Run `apm compile --clean` or use `apm compile --watch` during development |
