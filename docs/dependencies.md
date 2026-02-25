# APM Package Dependencies Guide

Complete guide to APM package dependency management - share and reuse context collections across projects for consistent, scalable AI-native development.

## What Are APM Dependencies?

APM dependencies are GitHub repositories containing `.apm/` directories with context collections (instructions, chatmodes, contexts) and agent workflows (prompts). They enable teams to:

- **Share proven workflows** across projects and team members
- **Standardize compliance and design patterns** organization-wide
- **Build on tested context** instead of starting from scratch
- **Maintain consistency** across multiple repositories and teams

## Dependency Types

APM supports multiple dependency types:

| Type | Detection | Example |
|------|-----------|---------|
| **APM Package** | Has `apm.yml` | `microsoft/apm-sample-package` |
| **Claude Skill** | Has `SKILL.md` (no `apm.yml`) | `ComposioHQ/awesome-claude-skills/brand-guidelines` |
| **Virtual Subdirectory Package** | Folder path in monorepo | `ComposioHQ/awesome-claude-skills/mcp-builder` |
| **Virtual Subdirectory Package** | Folder path in repo | `github/awesome-copilot/skills/review-and-refactor` |
| **ADO Package** | Azure DevOps repo | `dev.azure.com/org/project/_git/repo` |

**Virtual Subdirectory Packages** are skill folders from monorepos - they download an entire folder and may contain a SKILL.md plus resources.

**Virtual File Packages** download a single file (like a prompt or instruction) and integrate it directly.

### Claude Skills

Claude Skills are packages with a `SKILL.md` file that describe capabilities for AI agents. APM can install them and transform them for your target platform:

```bash
# Install a Claude Skill
apm install ComposioHQ/awesome-claude-skills/brand-guidelines

# For VSCode target: generates .github/agents/brand-guidelines.agent.md
# For Claude target: keeps native SKILL.md format
```

#### Skill Integration During Install

Skills are integrated to `.github/skills/`:

| Source | Result |
|--------|--------|
| Package with existing `SKILL.md` | Skill folder copied to `.github/skills/{folder-name}/` |
| APM package with `.apm/` primitives (no SKILL.md) | SKILL.md auto-generated, folder copied to `.github/skills/{folder-name}/` |
| Package without SKILL.md or primitives | No skill folder created |

#### Skill Folder Naming

Skill folders use the **source folder name directly** (not flattened paths):

```
.github/skills/
├── brand-guidelines/      # From ComposioHQ/awesome-claude-skills/brand-guidelines
├── mcp-builder/           # From ComposioHQ/awesome-claude-skills/mcp-builder
└── apm-sample-package/     # From microsoft/apm-sample-package
```

→ See [Skills Guide](skills.md) for complete documentation.

## Quick Start

### 1. Add Dependencies to Your Project

Add APM dependencies to your `apm.yml` file:

```yaml
name: my-project
version: 1.0.0
dependencies:
  apm:
    - microsoft/apm-sample-package  # Design standards, prompts
    - github/awesome-copilot/skills/review-and-refactor  # Code review skill
  mcp:
    - io.github.github/github-mcp-server
```

### 2. Install Dependencies

```bash
# Install all dependencies
apm install

# Install only APM dependencies (faster)
apm install --only=apm

# Preview what will be installed
apm install --dry-run
```

### 3. Verify Installation

```bash
# List installed packages
apm deps list

# Show dependency tree
apm deps tree

# Get package details
apm deps info apm-sample-package
```

### 4. Use Dependencies in Compilation

```bash
# Compile with dependencies
apm compile

# The compilation process generates distributed AGENTS.md files across the project
# Instructions with matching applyTo patterns are merged from all sources
# See docs/wip/distributed-agents-compilation-strategy.md for detailed compilation logic
```

## GitHub Authentication Setup

APM dependencies require GitHub authentication for downloading repositories. Set up your tokens:

### Option 1: Fine-grained Token (Recommended)

Create a fine-grained personal access token at [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new):

- **Repository access**: Select specific repositories or "All repositories"
- **Permissions**: 
  - Contents: Read (to access repository files)
  - Metadata: Read (to access basic repository information)

```bash
export GITHUB_CLI_PAT=your_fine_grained_token
```

### Option 2: Classic Token (Fallback)

Create a classic personal access token with `repo` scope:

```bash
export GITHUB_TOKEN=your_classic_token
```

### Verify Authentication

```bash
# Test that your token works
apm install --dry-run
```

If authentication fails, you'll see an error with guidance on token setup.

## Real-World Example: Corporate Website Project

This example shows how APM dependencies enable powerful layered functionality by combining multiple specialized packages. The company website project uses [microsoft/apm-sample-package](https://github.com/microsoft/apm-sample-package) as a full APM package and individual prompts from [github/awesome-copilot](https://github.com/github/awesome-copilot) to supercharge development workflows:

```yaml
# company-website/apm.yml
name: company-website
version: 1.0.0
description: Corporate website with design standards and code review
dependencies:
  apm:
    - microsoft/apm-sample-package
    - github/awesome-copilot/skills/review-and-refactor
  mcp:
    - io.github.github/github-mcp-server

scripts:
  # Design workflows  
  design-review: "codex --skip-git-repo-check design-review.prompt.md"
  accessibility: "codex --skip-git-repo-check accessibility-audit.prompt.md"
```

### Package Contributions

The combined packages provide comprehensive coverage:

**[apm-sample-package](https://github.com/microsoft/apm-sample-package) contributes:**
- **Agent Workflows**: `.apm/prompts/design-review.prompt.md`, `.apm/prompts/accessibility-audit.prompt.md`
- **Instructions**: `.apm/instructions/design-standards.instructions.md` - Design guidelines
- **Agents**: `.apm/agents/design-reviewer.agent.md` - Design review persona
- **Skills**: `.apm/skills/style-checker/SKILL.md` - Style checking capability

**[github/awesome-copilot](https://github.com/github/awesome-copilot) virtual packages contribute:**
- **Prompts**: Individual prompt files installed via virtual package references

### Compounding Benefits

When both packages are installed, your project gains:
- **Accessibility audit** capabilities for web components
- **Design system enforcement** with automated style checking
- **Code review** workflows from community prompts
- **Rich context** about design standards

## Dependency Resolution

### Installation Process

1. **Parse Configuration**: APM reads the `dependencies.apm` section from `apm.yml`
2. **Download Repositories**: Clone or update each GitHub repository to `apm_modules/`
3. **Validate Packages**: Ensure each repository has valid APM package structure
4. **Build Dependency Graph**: Resolve transitive dependencies recursively
5. **Check Conflicts**: Identify any circular dependencies or conflicts

### File Processing and Content Merging

APM uses instruction-level merging rather than file-level precedence. When local and dependency files contribute instructions with overlapping `applyTo` patterns:

```
my-project/
├── .apm/
│   └── instructions/
│       └── security.instructions.md      # Local instructions (applyTo: "**/*.py")
├── apm_modules/
│   └── compliance-rules/
│       └── .apm/
│           └── instructions/
│               └── compliance.instructions.md  # Dependency instructions (applyTo: "**/*.py")
└── apm.yml
```

During compilation, APM merges instruction content by `applyTo` patterns:
1. **Pattern-Based Grouping**: Instructions are grouped by their `applyTo` patterns, not by filename
2. **Content Merging**: All instructions matching the same pattern are concatenated in the final AGENTS.md
3. **Source Attribution**: Each instruction includes source file attribution when compiled

This allows multiple packages to contribute complementary instructions for the same file types, enabling rich layered functionality.

### Dependency Tree Structure

Based on the actual structure of our real-world examples:

```
my-project/
├── apm_modules/                     # Dependency installation directory
│   ├── microsoft/
│   │   └── apm-sample-package/      # From microsoft/apm-sample-package
│   │       ├── .apm/
│   │       │   ├── instructions/
│   │       │   │   └── design-standards.instructions.md
│   │       │   ├── prompts/
│   │       │   │   ├── design-review.prompt.md
│   │       │   │   └── accessibility-audit.prompt.md
│   │       │   ├── agents/
│   │       │   │   └── design-reviewer.agent.md
│   │       │   └── skills/
│   │       │       └── style-checker/SKILL.md
│   │       └── apm.yml
│   └── github/
│       └── awesome-copilot/              # Virtual subdirectory from github/awesome-copilot
│           └── skills/
│               └── review-and-refactor/
│                   ├── SKILL.md
│                   └── apm.yml
├── .apm/                            # Local context (highest priority)
├── apm.yml                          # Project configuration
└── .gitignore                       # Manually add apm_modules/ to ignore
```

**Note**: Full APM packages store primitives under `.apm/` subdirectories. Virtual file packages extract individual files from monorepos like `github/awesome-copilot`.

## Advanced Scenarios

### Branch and Tag References

Specify specific branches, tags, or commits for dependency versions:

```yaml
dependencies:
  apm:
    - github/awesome-copilot/skills/review-and-refactor#v2.1.0    # Specific tag
    - microsoft/apm-sample-package#main     # Specific branch  
    - company/internal-standards#abc123        # Specific commit
```

### Updating Dependencies

```bash
# Update all dependencies to latest versions
apm deps update

# Update specific dependency  
apm deps update apm-sample-package

# Install with updates (equivalent to update)
apm install --update
```

## Reproducible Builds with apm.lock

APM generates a lockfile (`apm.lock`) after each successful install to ensure reproducible builds across machines and CI environments.

### What is apm.lock?

The `apm.lock` file captures the exact state of your dependency tree:

```yaml
lockfile_version: "1.0"
generated_at: "2026-01-22T10:30:00Z"
apm_version: "0.8.0"
dependencies:
  microsoft/apm-sample-package:
    repo_url: "https://github.com/microsoft/apm-sample-package"
    resolved_commit: "abc123def456"
    resolved_ref: "main"
    version: "1.0.0"
    depth: 1
  acme/validation-patterns:
    repo_url: "https://github.com/acme/validation-patterns"
    resolved_commit: "789xyz012"
    resolved_ref: "main"
    version: "1.2.0"
    depth: 2
    resolved_by: "microsoft/apm-sample-package"
```

### How It Works

1. **First install**: APM resolves dependencies, downloads packages, and writes `apm.lock`
2. **Subsequent installs**: APM reads `apm.lock` and uses locked commits for exact reproducibility
3. **Updating**: Use `--update` to re-resolve dependencies and generate a fresh lockfile

### Version Control

**Commit `apm.lock`** to version control:

```bash
git add apm.lock
git commit -m "Lock dependencies"
```

This ensures all team members and CI pipelines get identical dependencies.

### Forcing Re-resolution

When you want the latest versions (ignoring the lockfile):

```bash
# Re-resolve all dependencies and update lockfile
apm install --update
```

### Transitive Dependencies

APM fully resolves transitive dependencies. If package A depends on B, and B depends on C:

```
apm install acme/package-a
```

Result:
- Downloads A, B, and C
- Records all three in `apm.lock` with depth information
- `depth: 1` = direct dependency
- `depth: 2+` = transitive dependency

### Cleaning Dependencies

```bash
# Remove all APM dependencies
apm deps clean

# This removes the entire apm_modules/ directory
# Use with caution - requires reinstallation
```

## Best Practices

### Package Structure

Create well-structured APM packages for maximum reusability:

```
your-package/
├── .apm/
│   ├── instructions/        # Context for AI behavior
│   ├── contexts/           # Domain knowledge and facts  
│   ├── chatmodes/          # Interactive chat configurations
│   └── prompts/            # Agent workflows
├── apm.yml                 # Package metadata
├── README.md               # Package documentation
└── examples/               # Usage examples (optional)
```

### Package Naming

- Use descriptive, specific names: `compliance-rules`, `design-guidelines`
- Follow GitHub repository naming conventions
- Consider organization/team prefixes: `company/platform-standards`

### Version Management

- Use semantic versioning for package releases
- Tag releases for stable dependency references
- Document breaking changes clearly

### Documentation

- Include clear README.md with usage examples
- Document all prompts and their parameters
- Provide integration examples

## Troubleshooting

### Common Issues

#### "Authentication failed" 
**Problem**: GitHub token is missing or invalid
**Solution**: 
```bash
# Verify token is set
echo $GITHUB_CLI_PAT

# Test token access
curl -H "Authorization: token $GITHUB_CLI_PAT" https://api.github.com/user
```

#### "Package validation failed"
**Problem**: Repository doesn't have valid APM package structure
**Solution**: 
- Ensure target repository has `.apm/` directory
- Check that `apm.yml` exists and is valid
- Verify repository is accessible with your token

#### "Circular dependency detected"
**Problem**: Packages depend on each other in a loop
**Solution**:
- Review your dependency chain
- Remove circular references
- Consider merging closely related packages

#### "File conflicts during compilation"
**Problem**: Multiple packages or local files have same names
**Resolution**: Local files automatically override dependency files with same names

### Getting Help

```bash
# Show detailed package information
apm deps info package-name

# Show full dependency tree
apm deps tree

# Preview installation without changes
apm install --dry-run

# Enable verbose logging
apm compile --verbose
```

## Integration with Workflows

### Continuous Integration

Add dependency installation to your CI/CD pipelines:

```yaml
# .github/workflows/apm.yml
- name: Install APM dependencies
  run: |
    apm install --only=apm
    apm compile
```

### Team Development

1. **Share dependencies** through your `apm.yml` file in version control
2. **Pin specific versions** for consistency across team members
3. **Document dependency choices** in your project README
4. **Update together** to avoid version conflicts

### Local Development

```bash
# Quick setup for new team members
git clone your-project
cd your-project
apm install
apm compile

# Now all team contexts and workflows are available
apm run design-review --param component="login-form"
```

## Next Steps

- **[CLI Reference](cli-reference.md)** - Complete command documentation
- **[Getting Started](getting-started.md)** - Basic APM usage
- **[Context Guide](concepts.md)** - Understanding the AI-Native Development framework
- **[Creating Packages](primitives.md)** - Build your own APM packages

Ready to create your own APM packages? See the [Context Guide](primitives.md) for detailed instructions on building reusable context collections and agent workflows.