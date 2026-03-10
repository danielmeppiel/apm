---
title: "Skills & Prompts"
description: "Create and use Skills (SKILL.md) and Prompts (.prompt.md) to build reusable AI workflows."
---

Skills (`SKILL.md`) are package meta-guides that help AI agents quickly understand what an APM package does and how to leverage its content. They provide a concise summary optimized for AI consumption.

## What are Skills?

Skills describe an APM package in a format AI agents can quickly parse:
- **What** the package provides (name, description)
- **How** to use it (body content with guidelines)
- **Resources** available (bundled scripts, references, examples)

### Skills Can Be Used Two Ways

1. **Package meta-guides for your own package**: Add a `SKILL.md` to your APM package to help AI agents understand what your package does
2. **Installed from Claude skill repositories**: Install skills from monorepos like `ComposioHQ/awesome-claude-skills` to gain new capabilities

When you install a package with a SKILL.md, AI agents can quickly understand how to use it.

## Installing Skills

### From Claude Skill Repositories

Many Claude Skills are hosted in monorepos. Install any skill directly:

```bash
# Install a skill from a monorepo subdirectory
apm install ComposioHQ/awesome-claude-skills/brand-guidelines

# Install skill with resources (scripts, references, etc.)
apm install ComposioHQ/awesome-claude-skills/skill-creator
```

## What Happens During Install

When you run `apm install`, APM handles skill integration automatically:

### Step 1: Download to apm_modules/
APM downloads packages to `apm_modules/owner/repo/` (or `apm_modules/owner/repo/skill-name/` for subdirectory packages).

### Step 2: Skill Integration
APM copies skills directly to `.github/skills/` (primary) and `.claude/skills/` (compatibility):

| Package Type | Behavior |
|--------------|----------|
| **Has existing SKILL.md** | Entire skill folder copied to `.github/skills/{skill-name}/` |
| **Has sub-skills in `.apm/skills/`** | Each `.apm/skills/*/SKILL.md` also promoted to `.github/skills/{sub-skill-name}/` |
| **No SKILL.md and no primitives** | No skill folder created |

**Target Directories:**
- **Primary**: `.github/skills/{skill-name}/` — Works with Copilot, Cursor, Codex, Gemini
- **Compatibility**: `.claude/skills/{skill-name}/` — Only if `.claude/` folder already exists

### Skill Folder Naming

Skill names are validated per the [agentskills.io](https://agentskills.io/) spec:
- 1-64 characters
- Lowercase alphanumeric + hyphens only
- No consecutive hyphens (`--`)
- Cannot start/end with hyphen

```
.github/skills/
├── mcp-builder/           # From ComposioHQ/awesome-claude-skills/mcp-builder
└── apm-sample-package/    # From microsoft/apm-sample-package
```

### Step 3: Primitive Integration
APM also integrates prompts and commands from the package (using their original filenames).

### Installation Path Structure

Skills maintain their natural path hierarchy:

```
apm_modules/
└── ComposioHQ/
    └── awesome-claude-skills/
        └── brand-guidelines/      # Skill subdirectory
            ├── SKILL.md           # Original skill file
            ├── apm.yml            # Auto-generated
            └── LICENSE.txt        # Any bundled files
```

## SKILL.md Format

### Basic Structure

```markdown
---
name: Skill Name
description: One-line description of what this skill does
---

# Skill Body

Detailed instructions for the AI agent on how to use this skill.

## Guidelines
- Guideline 1
- Guideline 2

## Examples
...
```

### Required Frontmatter

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name for the skill |
| `description` | string | One-line description |

### Body Content

The body contains:
- **Instructions** for the AI agent
- **Guidelines** and best practices
- **Examples** of usage
- **References** to bundled resources

## Bundled Resources

Skills can include additional resources:

```
my-skill/
├── SKILL.md           # Main skill file
├── scripts/           # Executable code
│   └── validate.py
├── references/        # Documentation
│   └── style-guide.md
├── examples/          # Sample files
│   └── sample.json
└── assets/            # Templates, images
    └── logo.png
```

**Note:** All resources stay in `apm_modules/` where AI agents can reference them.

## Creating Your Own Skills

### Quick Start with apm init

`apm init` creates a minimal project:

```bash
apm init my-skill && cd my-skill
```

This creates:
```
my-skill/
├── apm.yml       # Package manifest
└── .apm/         # Primitives folder
```

Add a `SKILL.md` at root to make it a publishable skill (see below).

### Option 1: Standalone Skill

Create a repo with just `SKILL.md`:

```bash
mkdir my-skill && cd my-skill

cat > SKILL.md << 'EOF'
---
name: My Custom Skill
description: Does something useful
---

# My Custom Skill

## Overview
Describe what this skill does...

## Guidelines
- Follow these rules...

## Examples
...
EOF

git init && git add . && git commit -m "Initial skill"
git push origin main
```

Anyone can now install it:
```bash
apm install your-org/my-skill
```

### Option 2: Skill in APM Package

Add `SKILL.md` to any existing APM package:

```
my-package/
├── apm.yml
├── SKILL.md          # Add this for Claude compatibility
└── .apm/
    ├── instructions/
    └── prompts/
```

This creates a **hybrid package** that works with both APM primitives and Claude Skills.

### Option 3: Skills Collection (Monorepo)

Organize multiple skills in a monorepo:

```
awesome-skills/
├── skill-1/
│   ├── SKILL.md
│   └── references/
├── skill-2/
│   └── SKILL.md
└── skill-3/
    ├── SKILL.md
    └── scripts/
```

Users install individual skills:
```bash
apm install your-org/awesome-skills/skill-1
apm install your-org/awesome-skills/skill-2
```

### Option 4: Multi-skill Package

Bundle multiple skills inside a single APM package using `.apm/skills/`:

```
my-package/
├── apm.yml
├── SKILL.md              # Parent skill (package-level guide)
└── .apm/
    ├── instructions/
    ├── prompts/
    └── skills/
        ├── skill-a/
        │   └── SKILL.md  # Sub-skill A
        └── skill-b/
            └── SKILL.md  # Sub-skill B
```

On install, APM promotes each sub-skill to a top-level `.github/skills/` entry alongside the parent — see [Sub-skill Promotion](#sub-skill-promotion) below.

### Sub-skill Promotion

When a package contains sub-skills in `.apm/skills/*/` subdirectories, APM promotes each to a top-level entry under `.github/skills/`. This ensures Copilot can discover them independently, since it only scans direct children of `.github/skills/`.

```
# Installed package with sub-skills:
apm_modules/org/repo/my-package/
├── SKILL.md
└── .apm/
    └── skills/
        └── azure-naming/
            └── SKILL.md

# Result after install:
.github/skills/
├── my-package/              # Parent skill
│   └── SKILL.md
└── azure-naming/            # Promoted sub-skill
    └── SKILL.md
```

## Package Detection

APM automatically detects package types:

| Has | Type | Detection |
|-----|------|-----------|
| `apm.yml` only | APM Package | Standard APM primitives |
| `SKILL.md` only | Claude Skill | Treated as native skill |
| `hooks/*.json` only | Hook Package | Hook handlers only |
| Both files | Hybrid Package | Best of both worlds |

## Target Detection

APM decides where to output skills based on project structure:

| Condition | Skill Output |
|-----------|---------------|
| `.github/` exists | `.github/skills/{skill-name}/SKILL.md` |
| `.claude/` also exists | Also copies to `.claude/skills/{skill-name}/SKILL.md` |
| Neither exists | Creates `.github/skills/` |

Override with:
```bash
apm install skill-name --target vscode
apm compile --target claude
```

Or set in `apm.yml`:
```yaml
name: my-project
target: vscode  # or claude, or all
```

## Best Practices

### 1. Clear Naming
Use descriptive, lowercase-hyphenated names:
- ✅ `brand-guidelines`
- ✅ `code-review-expert`
- ❌ `mySkill`
- ❌ `Skill_1`

### 2. Focused Description
Keep the description to one line:
- ✅ `Applies corporate brand colors and typography`
- ❌ `This skill helps you with branding and it can also do typography and it uses the company colors...`

### 3. Structured Body
Organize with clear sections:
```markdown
## Overview
What this skill does

## Guidelines
Rules to follow

## Examples
How to use it

## References
Links to resources
```

### 4. Resource Organization
Keep bundled files organized:
```
my-skill/
├── SKILL.md
├── scripts/      # Executable code only
├── references/   # Documentation
├── examples/     # Sample files
└── assets/       # Static resources
```

### 5. Version Control
Keep skills in version control. Use semantic versioning in the generated `apm.yml` for tracking.

## Integration with Other Primitives

Skills complement other APM primitives:

| Primitive | Purpose | Works With Skills |
|-----------|---------|-------------------|
| Instructions | Coding standards | Skills can reference instruction context |
| Prompts | Executable workflows | Skills describe how to use prompts |
| Agents | AI personalities | Skills explain what agents are available |
| Context | Project knowledge | Skills can link to context files |

## Troubleshooting

### Skill Not Installing

```
Error: Could not find SKILL.md or apm.yml
```

**Solution:** Verify the path is correct. For subdirectories, use full path:
```bash
apm install owner/repo/subdirectory
```

### Skill Name Validation Error

If you see a skill name validation warning:

1. **Check naming:** Names must be lowercase, 1-64 chars, hyphens only (no underscores)
2. **Auto-normalization:** APM automatically normalizes invalid names when possible

### Metadata Missing

If skill lacks APM metadata:

1. Check the skill was installed via APM (not manually copied)
2. Reinstall the package

## Related Documentation

- [Core Concepts](/apm/introduction/how-it-works/) - Understanding APM architecture
- [Primitives Guide](/apm/introduction/key-concepts/) - All primitive types
- [CLI Reference](/apm/reference/cli/) - Full command documentation
- [Dependencies](/apm/guides/dependencies/) - Package management

---


Prompts are the building blocks of APM - focused, reusable AI instructions that accomplish specific tasks. They are executed through scripts defined in your `apm.yml` configuration.

## How Prompts Work in APM

APM uses a script-based architecture:

1. **Scripts** are defined in `apm.yml` and specify which runtime and prompt to use
2. **Prompts** (`.prompt.md` files) contain the AI instructions with parameter placeholders
3. **Compilation** happens when scripts reference `.prompt.md` files - APM compiles them with parameter substitution
4. **Execution** runs the compiled prompt through the specified runtime

```bash
# Script execution flow
apm run start --param key=value
  ↓
Script: "codex my-prompt.prompt.md"
  ↓
APM compiles my-prompt.prompt.md with parameters
  ↓
Codex executes the compiled prompt
```

## What are Prompts?

A prompt is a single-purpose AI instruction stored in a `.prompt.md` file. Prompts are:
- **Focused**: Each prompt does one thing well
- **Reusable**: Can be used across multiple scripts
- **Parameterized**: Accept inputs to customize behavior
- **Testable**: Easy to run and validate independently

## Prompt File Structure

Prompts follow the VSCode `.prompt.md` convention with YAML frontmatter:

```markdown
---
description: Analyzes application logs to identify errors and patterns
author: DevOps Team
mcp:
  - logs-analyzer
input:
  - service_name
  - time_window
  - log_level
---

# Analyze Application Logs

You are a expert DevOps engineer analyzing application logs to identify issues and patterns.

## Context
- Service: ${input:service_name}
- Time window: ${input:time_window}
- Log level: ${input:log_level}

## Task
1. Retrieve logs for the specified service and time window
2. Identify any ERROR or FATAL level messages
3. Look for patterns in warnings that might indicate emerging issues
4. Summarize findings with:
   - Critical issues requiring immediate attention
   - Trends or patterns worth monitoring
   - Recommended next steps

## Output Format
Provide a structured summary with:
- **Status**: CRITICAL | WARNING | NORMAL
- **Issues Found**: List of specific problems
- **Patterns**: Recurring themes or trends
- **Recommendations**: Suggested actions
```

## Key Components

### YAML Frontmatter
- **description**: Clear explanation of what the prompt does
- **author**: Who created/maintains this prompt
- **mcp**: Required MCP servers for tool access
- **input**: Parameters the prompt expects

### Prompt Body
- **Clear instructions**: Tell the AI exactly what to do
- **Context section**: Provide relevant background information
- **Input references**: Use `${input:parameter_name}` for dynamic values
- **Output format**: Specify how results should be structured

## Input Parameters

Reference script inputs using the `${input:name}` syntax:

```markdown
## Analysis Target
- Service: ${input:service_name}
- Environment: ${input:environment}
- Start time: ${input:start_time}
```

## MCP Tool Integration (Phase 2 - Coming Soon)

> **⚠️ Note**: MCP integration is planned work. Currently, prompts work with natural language instructions only.

**Future capability** - Prompts will be able to use MCP servers for external tools:

```yaml
---
description: Future MCP-enabled prompt
mcp:
  - kubernetes-mcp    # For cluster access
  - github-mcp        # For repository operations  
  - slack-mcp         # For team communication
---
```

**Current workaround**: Use detailed natural language instructions:
```markdown
---
description: Current approach without MCP tools
---

# Kubernetes Analysis

Please analyze the Kubernetes cluster by:
1. Examining the deployment configurations I'll provide
2. Reviewing resource usage patterns
3. Suggesting optimization opportunities

[Include relevant data in the prompt or as context]
```

See [IDE & Tool Integration](/apm/integrations/ide-tools/) for MCP server configuration and usage.

## Writing Effective Prompts

### Be Specific
```markdown
# Good
Analyze the last 24 hours of application logs for service ${input:service_name}, 
focusing on ERROR and FATAL messages, and identify any patterns that might 
indicate performance degradation.

# Avoid
Look at some logs and tell me if there are problems.
```

### Structure Your Instructions
```markdown
## Task
1. First, do this specific thing
2. Then, analyze the results looking for X, Y, and Z
3. Finally, summarize findings in the specified format

## Success Criteria
- All ERROR messages are categorized
- Performance trends are identified
- Clear recommendations are provided
```

### Specify Output Format
```markdown
## Output Format
**Summary**: One-line status
**Critical Issues**: Numbered list of immediate concerns
**Recommendations**: Specific next steps with priority levels
```

## Example Prompts

### Code Review Prompt
```markdown
---
description: Reviews code changes for best practices and potential issues
author: Engineering Team
input:
  - pull_request_url
  - focus_areas
---

# Code Review Assistant

Review the code changes in pull request ${input:pull_request_url} with focus on ${input:focus_areas}.

## Review Criteria
1. **Security**: Check for potential vulnerabilities
2. **Performance**: Identify optimization opportunities  
3. **Maintainability**: Assess code clarity and structure
4. **Testing**: Evaluate test coverage and quality

## Output
Provide feedback in standard PR review format with:
- Specific line comments for issues
- Overall assessment score (1-10)
- Required changes vs suggestions
```

### Deployment Health Check
```markdown
---
description: Verifies deployment success and system health
author: Platform Team
mcp:
  - kubernetes-tools
  - monitoring-api
input:
  - service_name
  - deployment_version
---

# Deployment Health Check

Verify the successful deployment of ${input:service_name} version ${input:deployment_version}.

## Health Check Steps
1. Confirm pods are running and ready
2. Check service endpoints are responding
3. Verify metrics show normal operation
4. Test critical user flows

## Success Criteria
- All pods STATUS = Running
- Health endpoint returns 200
- Error rate < 1%
- Response time < 500ms
```

## Running Prompts

APM provides two ways to run prompts: **explicit scripts** (configured in `apm.yml`) and **auto-discovery** (zero configuration).

### Auto-Discovery (Zero Configuration)

Starting with v0.5.0, APM can automatically discover and run prompts without manual script configuration:

```bash
# Install a prompt from any repository
apm install github/awesome-copilot/skills/review-and-refactor

# Run it immediately - no apm.yml configuration needed!
apm run review-and-refactor
```

**How it works:**

1. APM searches for prompts with matching names in this priority order:
   - Local root: `./prompt-name.prompt.md`
   - APM prompts directory: `.apm/prompts/prompt-name.prompt.md`
   - GitHub convention: `.github/prompts/prompt-name.prompt.md`
   - Dependencies: `apm_modules/**/.apm/prompts/prompt-name.prompt.md`

2. When found, APM automatically:
   - Detects installed runtime (GitHub Copilot CLI or Codex)
   - Generates appropriate command with recommended flags
   - Compiles prompt with parameters
   - Executes through the runtime

**Qualified paths for disambiguation:**

If you have multiple prompts with the same name from different sources:

```bash
# Collision detected - APM shows all matches with guidance
apm run code-review
# Error: Multiple prompts found for 'code-review':
#   - owner/test-repo (apm_modules/owner/test-repo-code-review/...)
#   - acme/standards (apm_modules/acme/standards/...)
# 
# Use qualified path:
#   apm run github/awesome-copilot/code-review
#   apm run acme/standards/code-review

# Run specific version using qualified path
apm run github/awesome-copilot/code-review --param pr_url=...
```

**Local prompts always take precedence** over dependency prompts with the same name.

### Explicit Scripts (Power Users)

For advanced use cases, define scripts explicitly in `apm.yml`:

```yaml
scripts:
  # Custom runtime flags
  start: "copilot --full-auto -p analyze-logs.prompt.md"
  
  # Specific model selection
  llm: "llm analyze-logs.prompt.md -m github/gpt-4o-mini"
  
  # Environment variables
  debug: "RUST_LOG=debug codex analyze-logs.prompt.md"
  
  # Friendly aliases
  review: "copilot -p code-review.prompt.md"
```

**Explicit scripts always take precedence** over auto-discovery. This gives power users full control while maintaining zero-config convenience for simple cases.

### Running Scripts

```bash
# With auto-discovery (no apm.yml scripts needed)
apm run code-review --param pull_request_url="https://github.com/org/repo/pull/123"

# With explicit scripts
apm run start --param service_name=api-gateway --param time_window="1h"
apm run llm --param service_name=api-gateway --param time_window="1h"
apm run debug --param service_name=api-gateway --param time_window="1h"

# Preview compiled prompts before execution
apm preview start --param service_name=api-gateway --param time_window="1h"
```

### Example Project Structure

```
my-devops-project/
├── apm.yml                              # Project configuration
├── README.md                            # Project documentation
├── analyze-logs.prompt.md               # Main log analysis prompt
├── prompts/
│   ├── code-review.prompt.md           # Code review prompt
│   └── health-check.prompt.md          # Deployment health check
└── .github/
    └── workflows/
        └── apm-ci.yml                  # CI using APM scripts
```

### Corresponding apm.yml

```yaml
name: my-devops-project
version: 1.0.0
description: DevOps automation prompts for log analysis and system monitoring
author: Platform Team

scripts:
  # Default script using Codex runtime
  start: "codex analyze-logs.prompt.md"
  
  # LLM script with GitHub Models
  llm: "llm analyze-logs.prompt.md -m github/gpt-4o-mini"
  
  # Debug script with environment variables
  debug: "RUST_LOG=debug codex analyze-logs.prompt.md"
  
  # Code review script
  review: "codex prompts/code-review.prompt.md"
  
  # Health check script
  health: "llm prompts/health-check.prompt.md -m github/gpt-4o"

dependencies:
  mcp:
    - ghcr.io/github/github-mcp-server
    - ghcr.io/kubernetes/k8s-mcp-server
```

This structure allows you to run any prompt via scripts:
```bash
apm run start --param service_name=api-gateway --param time_window="1h"
apm run review --param pull_request_url=https://github.com/org/repo/pull/123
apm run health --param service_name=frontend --param deployment_version=v2.1.0
```

## Best Practices

### 1. Single Responsibility
Each prompt should do one thing well. Break complex operations into multiple prompts.

### 2. Clear Naming
Use descriptive names that indicate the prompt's purpose:
- `analyze-performance-metrics.prompt.md`
- `create-incident-ticket.prompt.md`
- `validate-deployment-config.prompt.md`

### 3. Document Inputs
Always specify what inputs are required and their expected format:

```yaml
input:
  - service_name     # String: name of the service to analyze
  - time_window      # String: time range (e.g., "1h", "24h", "7d")
  - severity_level   # String: minimum log level ("ERROR", "WARN", "INFO")
```

### 4. Version Control
Keep prompts in version control alongside scripts. Use semantic versioning for breaking changes.

## Next Steps

- Learn about [Runtime Integration](/apm/integrations/runtimes/) to setup and use different AI runtimes
- See [CLI Reference](/apm/reference/cli/) for complete script execution commands
- Check [Development Guide](/apm/contributing/development-guide/) for local development setup
