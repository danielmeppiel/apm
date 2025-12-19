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
| **APM Package** | Has `apm.yml` | `danielmeppiel/compliance-rules` |
| **Claude Skill** | Has `SKILL.md` (no `apm.yml`) | `ComposioHQ/awesome-claude-skills/brand-guidelines` |
| **Virtual Subdirectory Package** | Folder path in monorepo | `ComposioHQ/awesome-claude-skills/mcp-builder` |
| **Virtual File Package** | Single file path | `github/awesome-copilot/prompts/code-review.prompt.md` |
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
└── compliance-rules/      # From danielmeppiel/compliance-rules
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
    - danielmeppiel/compliance-rules  # GDPR, legal review workflows
    - danielmeppiel/design-guidelines # Accessibility, UI standards
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
apm deps info compliance-rules
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

This example shows how APM dependencies enable powerful layered functionality by combining multiple specialized packages. The company website project uses both [danielmeppiel/compliance-rules](https://github.com/danielmeppiel/compliance-rules) and [danielmeppiel/design-guidelines](https://github.com/danielmeppiel/design-guidelines) to supercharge development workflows:

```yaml
# company-website/apm.yml
name: company-website
version: 1.0.0
description: Corporate website with compliance and design standards
dependencies:
  apm:
    - danielmeppiel/compliance-rules
    - danielmeppiel/design-guidelines
  mcp:
    - io.github.github/github-mcp-server

scripts:
  # Compliance workflows
  audit: "codex --skip-git-repo-check compliance-audit.prompt.md"
  gdpr-check: "codex --skip-git-repo-check gdpr-assessment.prompt.md"
  legal-review: "codex --skip-git-repo-check legal-review.prompt.md"
  
  # Design workflows  
  design-review: "codex --skip-git-repo-check design-review.prompt.md"
  accessibility: "codex --skip-git-repo-check accessibility-audit.prompt.md"
  style-check: "codex --skip-git-repo-check style-guide-check.prompt.md"
```

### Package Contributions

The combined packages provide comprehensive coverage:

**[compliance-rules](https://github.com/danielmeppiel/compliance-rules) contributes:**
- **Agent Workflows**: `compliance-audit.prompt.md`, `gdpr-assessment.prompt.md`, `legal-review.prompt.md`
- **Context Files**: `.apm/context/legal-compliance.context.md` - Legal compliance framework and requirements
- **Instructions**: `.apm/instructions/compliance.instructions.md` - Compliance checking guidelines
- **Chat Modes**: `.apm/chatmodes/legal-compliance.chatmode.md` - Interactive legal consultation mode

**[design-guidelines](https://github.com/danielmeppiel/design-guidelines) contributes:**
- **Agent Workflows**: `design-review.prompt.md`, `accessibility-audit.prompt.md`, `style-guide-check.prompt.md`
- **Context Files**: `.apm/context/design-system.context.md` - Design system specifications and standards
- **Instructions**: `.apm/instructions/design-standards.instructions.md` - UI/UX design guidelines and best practices

### Compounding Benefits

When both packages are installed, your project gains:
- **Legal compliance** validation for all code changes
- **Accessibility audit** capabilities for web components
- **Design system enforcement** with automated style checking
- **GDPR assessment** workflows for data handling
- **Rich context** about legal requirements AND design standards

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
│   ├── compliance-rules/            # From danielmeppiel/compliance-rules
│   │   ├── .apm/
│   │   │   ├── instructions/
│   │   │   │   └── compliance.instructions.md
│   │   │   ├── context/
│   │   │   │   └── legal-compliance.context.md
│   │   │   └── chatmodes/
│   │   │       └── legal-compliance.chatmode.md
│   │   ├── compliance-audit.prompt.md         # Agent workflows in root
│   │   ├── gdpr-assessment.prompt.md
│   │   ├── legal-review.prompt.md
│   │   └── apm.yml
│   └── design-guidelines/           # From danielmeppiel/design-guidelines
│       ├── .apm/
│       │   ├── instructions/
│       │   │   └── design-standards.instructions.md
│       │   └── context/
│       │       └── design-system.context.md
│       ├── accessibility-audit.prompt.md      # Agent workflows in root
│       ├── design-review.prompt.md
│       ├── style-guide-check.prompt.md
│       └── apm.yml
├── .apm/                            # Local context (highest priority)
├── apm.yml                          # Project configuration
└── .gitignore                       # Manually add apm_modules/ to ignore
```

**Note**: These repositories store agent workflows (`.prompt.md` files) in the root directory, while context files, instructions, and chat modes are organized under `.apm/` subdirectories.

## Advanced Scenarios

### Branch and Tag References

Specify specific branches, tags, or commits for dependency versions:

```yaml
dependencies:
  apm:
    - danielmeppiel/compliance-rules#v2.1.0    # Specific tag
    - danielmeppiel/design-guidelines#main     # Specific branch  
    - company/internal-standards#abc123        # Specific commit
```

### Updating Dependencies

```bash
# Update all dependencies to latest versions
apm deps update

# Update specific dependency  
apm deps update compliance-rules

# Install with updates (equivalent to update)
apm install --update
```

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