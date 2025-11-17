# Context Guide

Context components are the configurable tools that deploy proven prompt engineering and context engineering techniques. APM implements these as the core building blocks for reliable, reusable AI development workflows.

## How Context Components Work

APM implements Context - the configurable tools that deploy prompt engineering and context engineering techniques to transform unreliable AI interactions into engineered systems.

### 🏗️ Initialize a project with AI-Native structure

```bash
apm init my-project  # Creates complete Context scaffolding + apm.yml
```

### ⚙️ Generated Project Structure

```yaml
my-project/
├── apm.yml              # Project configuration and script definitions
└── .apm/
    ├── agents/          # Role-based AI expertise with tool boundaries
    │   ├── backend-dev.agent.md        # API development specialist
    │   └── frontend-dev.agent.md       # UI development specialist
    ├── instructions/    # Targeted guidance by file type and domain  
    │   ├── security.instructions.md    # applyTo: "auth/**"
    │   └── testing.instructions.md     # applyTo: "**/*test*"
    ├── prompts/         # Reusable agent workflows
    │   ├── code-review.prompt.md       # Systematic review process
    │   └── feature-spec.prompt.md      # Spec-first development
    └── context/         # Optimized information retrieval
        └── architecture.context.md     # Project patterns and decisions
```

### 🔄 Intelligent Compilation

APM automatically compiles your primitives into optimized AGENTS.md files using mathematical optimization:

```bash
apm compile  # Generate optimized AGENTS.md files
apm compile --verbose  # See optimization decisions
```

**[Learn more about the Context Optimization Engine →](compilation.md)**

## Packaging & Distribution

**Manage like npm packages:**

```yaml
# apm.yml - Project configuration
name: my-ai-native-app
version: 1.0.0
scripts:
  impl-copilot: "copilot -p 'implement-feature.prompt.md'"
  review-copilot: "copilot -p 'code-review.prompt.md'" 
  docs-codex: "codex generate-docs.prompt.md -m github/gpt-4o-mini"
dependencies:
  mcp:
    - ghcr.io/github/github-mcp-server
```

**Share and reuse across projects:**
```bash
apm install                    # Install MCP dependencies
apm run impl-copilot --param feature="user-auth"
apm run review-copilot --param files="src/auth/"
```

## Overview

The APM CLI supports three types of primitives:

- **Agents** (`.agent.md`) - Define AI assistant personalities and behaviors (legacy: `.chatmode.md`)
- **Instructions** (`.instructions.md`) - Provide coding standards and guidelines for specific file types
- **Context** (`.context.md`, `.memory.md`) - Supply background information and project context

> **Note**: Both `.agent.md` (new format) and `.chatmode.md` (legacy format) are fully supported. VSCode provides Quick Fix actions to help migrate from `.chatmode.md` to `.agent.md`.

## File Structure

### Supported Locations

APM discovers primitives in these locations:

```
# APM-native structure
.apm/
├── agents/             # AI assistant definitions (new format)
│   └── *.agent.md
├── chatmodes/          # AI assistant definitions (legacy format)
│   └── *.chatmode.md
├── instructions/        # Coding standards and guidelines  
│   └── *.instructions.md
├── context/            # Project context files
│   └── *.context.md
└── memory/             # Team info, contacts, etc.
    └── *.memory.md

# VSCode-compatible structure  
.github/
├── agents/             # VSCode Copilot agents (new format)
│   └── *.agent.md
├── chatmodes/          # VSCode Copilot chatmodes (legacy format)
│   └── *.chatmode.md
└── instructions/       # VSCode Copilot instructions
    └── *.instructions.md

# Generic files (anywhere in project)
*.agent.md
*.chatmode.md
*.instructions.md
*.context.md
*.memory.md
```

## Component Types Overview

Context implements the complete [AI-Native Development framework](https://danielmeppiel.github.io/awesome-ai-native/docs/concepts/) through four core component types:

### Instructions (.instructions.md)
**Context Engineering Layer** - Targeted guidance by file type and domain

Instructions provide coding standards, conventions, and guidelines that apply automatically based on file patterns. They implement strategic context loading that gives AI exactly the right information at the right time.

```yaml
---
description: Python coding standards and documentation requirements
applyTo: "**/*.py"
---
# Python Coding Standards
- Follow PEP 8 for formatting
- Use type hints for all function parameters
- Include comprehensive docstrings with examples
```

### Agent Workflows (.prompt.md)  
**Prompt Engineering Layer** - Executable AI workflows with parameters

Agent Workflows transform ad-hoc requests into structured, repeatable workflows. They support parameter injection, context loading, and validation gates for reliable results.

```yaml
---
description: Implement secure authentication system
mode: backend-dev
input: [auth_method, session_duration]
---
# Secure Authentication Implementation
Use ${input:auth_method} with ${input:session_duration} sessions
Review [security standards](../context/security.context.md) before implementation
```

### Agents (.agent.md, legacy: .chatmode.md)
**Agent Specialization Layer** - AI assistant personalities with tool boundaries

Agents create specialized AI assistants focused on specific domains. They define expertise areas, communication styles, and available tools.

```yaml
---
description: Senior backend developer focused on API design
tools: ["terminal", "file-manager"]
expertise: ["security", "performance", "scalability"]
---
You are a senior backend engineer with 10+ years experience in API development.
Focus on security, performance, and maintainable architecture patterns.
```

> **File Format**: Use `.agent.md` for new files. Legacy `.chatmode.md` files continue to work and can be migrated using VSCode Quick Fix actions.

### Context (.context.md)
**Knowledge Management Layer** - Optimized project information for AI consumption

Context files package project knowledge, architectural decisions, and team standards in formats optimized for LLM consumption and token efficiency.

```markdown
# Project Architecture
## Core Patterns
- Repository pattern for data access
- Clean architecture with domain separation
- Event-driven communication between services
```

## Primitive Types

### Agents

Agents define AI assistant personalities and specialized behaviors for different development tasks.

**Format:** `.agent.md` (new) or `.chatmode.md` (legacy)

**Frontmatter:**
- `description` (required) - Clear explanation of the agent purpose
- `author` (optional) - Creator information
- `version` (optional) - Version string

**Example:**
```markdown
---
description: AI pair programming assistant for code review
author: Development Team
version: "1.0.0"
---

# Code Review Assistant

You are an expert software engineer specializing in code review.

## Your Role
- Analyze code for bugs, security issues, and performance problems
- Suggest improvements following best practices
- Ensure code follows team conventions

## Communication Style
- Be constructive and specific in feedback
- Explain reasoning behind suggestions
- Prioritize critical issues over style preferences
```

### Instructions

Instructions provide coding standards, conventions, and guidelines that apply to specific file types or patterns.

**Format:** `.instructions.md`

**Frontmatter:**
- `description` (required) - Clear explanation of the standards
- `applyTo` (required) - Glob pattern for file targeting (e.g., `"**/*.py"`)
- `author` (optional) - Creator information
- `version` (optional) - Version string

**Example:**
```markdown
---
description: Python coding standards and documentation requirements
applyTo: "**/*.py"
author: Development Team
version: "2.0.0"
---

# Python Coding Standards

## Style Guide
- Follow PEP 8 for formatting
- Maximum line length of 88 characters (Black formatting)
- Use type hints for all function parameters and returns

## Documentation Requirements
- All public functions must have docstrings
- Include Args, Returns, and Raises sections
- Provide usage examples for complex functions

## Example Format
```python
def calculate_metrics(data: List[Dict], threshold: float = 0.5) -> Dict[str, float]:
    """Calculate performance metrics from data.
    
    Args:
        data: List of data dictionaries containing metrics
        threshold: Minimum threshold for filtering
    
    Returns:
        Dictionary containing calculated metrics
    
    Raises:
        ValueError: If data is empty or invalid
    """
```

### Context Files

Context files provide background information, project details, and other relevant context that AI assistants should be aware of.

**Format:** `.context.md` or `.memory.md` files

**Frontmatter:**
- `description` (optional) - Brief description of the context
- `author` (optional) - Creator information
- `version` (optional) - Version string

**Examples:**

Project context (`.apm/context/project-info.context.md`):
```markdown
---
description: Project overview and architecture
---

# APM CLI Project

## Overview
Command-line tool for AI-powered development workflows.

## Key Technologies
- Python 3.9+ with Click framework
- YAML frontmatter for configuration
- Rich library for terminal output

## Architecture
- Modular runtime system
- Plugin-based workflow engine
- Extensible primitive system
```

Team information (`.apm/memory/team-contacts.memory.md`):
```markdown
# Team Contacts

## Development Team
- Lead Developer: Alice Johnson (alice@company.com)
- Backend Engineer: Bob Smith (bob@company.com)

## Emergency Contacts
- On-call: +1-555-0123
- Incidents: incidents@company.com

## Meeting Schedule
- Daily standup: 9:00 AM PST
- Sprint planning: Mondays 2:00 PM PST
```

## Discovery and Parsing

The APM CLI automatically discovers and parses all primitive files in your project.

## Validation

All primitives are automatically validated during discovery:

- **Agents**: Must have description and content (supports both `.agent.md` and `.chatmode.md`)
- **Instructions**: Must have description, applyTo pattern, and content
- **Context**: Must have content (description optional)

Invalid files are skipped with warning messages, allowing valid primitives to continue loading.

## Context Linking

Context files are **linkable knowledge modules** that other primitives can reference via markdown links, enabling composable knowledge graphs.

### Linking from Instructions

```markdown
<!-- .apm/instructions/api.instructions.md -->
---
applyTo: "backend/**/*.py"
description: API development guidelines
---

Follow [our API standards](../context/api-standards.context.md) and ensure
[GDPR compliance](../context/gdpr-compliance.context.md) for all endpoints.
```

### Linking from Agents

```markdown
<!-- .apm/agents/backend-expert.agent.md -->
---
description: Backend development expert
---

You are a backend expert. Always reference [our architecture patterns](../context/architecture.context.md)
when designing systems.
```

### Automatic Link Resolution

APM automatically resolves context file links during installation and compilation:

1. **Discovery**: Scans all primitives for context file references
2. **Resolution**: Rewrites links to point to actual source locations
3. **Direct Linking**: Links point to files in `apm_modules/` and `.apm/` directories
4. **Persistence**: Commit `apm_modules/` for link availability, or run `apm install` in CI/CD

**Result**: Links work everywhere—IDE, GitHub, all coding agents—pointing directly to source files.

### Link Resolution Examples

Links are rewritten to point to actual source locations:

**From installed prompts/agents** (`.github/` directory):
```markdown
[API Standards](../context/api.context.md)
→ [API Standards](../../apm_modules/company/standards/.apm/context/api.context.md)
```

**From compiled AGENTS.md**:
```markdown
[Architecture](../context/architecture.context.md)
→ [Architecture](.apm/context/architecture.context.md)
```

## Best Practices

### 1. Clear Naming
Use descriptive names that indicate purpose:
- `code-review-assistant.agent.md`
- `python-documentation.instructions.md`
- `team-contacts.md`

### 2. Targeted Application
Use specific `applyTo` patterns for instructions:
- `"**/*.py"` for Python files
- `"**/*.{ts,tsx}"` for TypeScript React files
- `"**/test_*.py"` for Python test files

### 3. Version Control
Keep primitives in version control alongside your code. Use semantic versioning for breaking changes.

### 4. Organized Structure
Use the structured `.apm/` directories for better organization:
```
.apm/
├── agents/
│   ├── code-reviewer.agent.md
│   └── documentation-writer.agent.md
├── instructions/
│   ├── python-style.instructions.md
│   └── typescript-conventions.instructions.md
└── context/
    ├── project-info.context.md
    └── architecture-overview.context.md
```

### 5. Team Collaboration
- Include author information in frontmatter
- Document the purpose and scope of each primitive
- Regular review and updates as standards evolve

## Integration with VSCode

For VSCode Copilot compatibility, place files in `.github/` directories:
```
.github/
├── agents/
│   └── assistant.agent.md
└── instructions/
    └── coding-standards.instructions.md
```

These files follow the same format and will be discovered alongside APM-specific primitives. 

## Error Handling

The primitive system handles errors gracefully:

- **Malformed YAML**: Files with invalid frontmatter are skipped with warnings
- **Missing required fields**: Validation errors are reported clearly
- **File access issues**: Permission and encoding problems are handled safely
- **Invalid patterns**: Glob pattern errors are caught and reported

This ensures that a single problematic file doesn't prevent other primitives from loading.

## Spec Kit Constitution Injection (Phase 0)

When present, a project-level constitution file at `memory/constitution.md` is injected at the very top of `AGENTS.md` during `apm compile`.

### Block Format
```
<!-- SPEC-KIT CONSTITUTION: BEGIN -->
hash: <sha256_12> path: memory/constitution.md
<entire original file content>
<!-- SPEC-KIT CONSTITUTION: END -->
```

### Behavior
- Enabled by default; disable via `--no-constitution` (existing block preserved)
- Idempotent: re-running compile without changes leaves file unchanged
- Drift aware: modifying `memory/constitution.md` regenerates block with new hash
- Safe: absence of constitution does not fail compilation (status MISSING in Rich table)

### Why This Matters
Ensures downstream AI tooling always has the authoritative governance / principles context without manual copy-paste. The hash enables simple drift detection or caching strategies later.