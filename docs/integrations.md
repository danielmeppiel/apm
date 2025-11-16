# Integrations Guide

APM is designed to work seamlessly with your existing development tools and workflows. This guide covers integration patterns, supported AI runtimes, and compatibility with popular development tools.

## APM + Spec-kit Integration

APM manages the **context foundation** and provides **advanced context management** for software projects. It works exceptionally well alongside [Spec-kit](https://github.com/github/spec-kit) for specification-driven development, as well as with other AI Native Development methodologies like vibe coding.

### 🔧 APM: Context Foundation

APM provides the infrastructure layer for AI development:

- **Context Packaging**: Bundle project knowledge, standards, and patterns into reusable modules
- **Dynamic Loading**: Smart context composition based on file patterns and current tasks
- **Performance Optimization**: Optimized context delivery for large, complex projects
- **Memory Management**: Strategic LLM token usage across conversations

### 📋 Spec-kit: Specification Layer

When using Spec-kit for Specification-Driven Development (SDD), APM automatically integrates the Spec-kit constitution:

- **Constitution Injection**: APM automatically injects the Spec-kit `constitution.md` into the compiled context layer (`AGENTS.md`)
- **Rule Enforcement**: All coding agents respect the non-negotiable rules governing your project
- **Contextual Augmentation**: APM embeds your team's context modules into `AGENTS.md` after Spec-kit's constitution
- **SDD Enhancement**: Augments the Spec Driven Development process with additional context curated by your teams

### 🚀 Integrated Workflow

```bash
# 1. Set up APM contextual foundation
apm init my-project && apm compile

# 2. Use Spec-kit for specification-driven development
# Spec-kit constitution is automatically included in AGENTS.md

# 3. Run AI workflows with both SDD rules and team context
apm run implement-feature --param spec="user-auth" --param approach="sdd"
```

**Key Benefits of Integration**:
- **Universal Context**: APM grounds any coding agent on context regardless of workflow
- **SDD Compatibility**: Perfect for specification-driven development approaches
- **Flexible Workflows**: Also works with traditional prompting and vibe coding
- **Team Knowledge**: Combines constitutional rules with team-specific context

## Supported AI Runtimes

APM manages AI runtime installation and provides seamless integration with multiple coding agents:

### ⚡ OpenAI Codex CLI

Direct integration with OpenAI's development-focused models:

```bash
# Install and configure  
apm runtime setup copilot

# Features
- GitHub Models API backend
- Terminal-native workflow
- Customizable model parameters
- Advanced prompt engineering support
- Multi-model switching
```

**Best for**: Teams preferring terminal workflows, custom model configurations

**Configuration**:
```yaml
runtime:
  codex:
    model: "github/gpt-4o-mini"
    provider: "github-models"
    api_base: "https://models.github.ai"
    temperature: 0.2
    max_tokens: 8000
```

### 🔧 LLM Library

Flexible runtime supporting multiple model providers:

```bash
# Install and configure
apm runtime setup llm

# Features  
- Multiple model providers (OpenAI, Anthropic, Ollama)
- Local model support
- Custom plugin system
- Advanced configuration options
- Cost optimization features
```

**Best for**: Teams needing model flexibility, local development, cost optimization, custom integrations

**Configuration**:
```yaml
runtime:
  llm:
    default_model: "gpt-4"
    providers:
      - openai
      - ollama  
      - anthropic
    local_models: 
      - "llama3:8b"
    cost_limits:
      daily_max: "$50"
```

### Verify Installation

Check what runtimes are available and properly configured:

```bash
# List installed runtimes
apm runtime list

# Test runtime functionality
apm runtime test copilot
apm runtime test codex
apm runtime test llm
```

## VSCode Integration

APM works natively with VSCode's Context implementation:

### Native VSCode Context

VSCode already implements core Context concepts:

- **Chat Modes**: Domain-specific chat behavior with `.chatmode.md` files in `.github/chatmodes/`
- **Instructions Files**: Modular instructions with `copilot-instructions.md` and `.instructions.md` files
- **Prompt Files**: Reusable task templates with `.prompt.md` files in `.github/prompts/`

### Automatic Prompt Integration with APM

APM automatically integrates prompts from installed packages into VSCode's native structure:

```bash
# Install APM packages - integration happens automatically
apm install danielmeppiel/design-guidelines

# Prompts are automatically integrated to:
# .github/prompts/*-apm.prompt.md (with package metadata header)
```

**How Auto-Integration Works**:
- **Zero-Config**: Always enabled, works automatically with no configuration needed
- **Auto-Cleanup**: Removes integrated prompts when you uninstall packages
- **Smart Updates**: Tracks package version/commit; updates only when package changes
- **Metadata Headers**: Integrated prompts include source, version, and commit information
- **GitIgnore Protection**: Automatically adds pattern to `.gitignore` for integrated prompts
- **User-Safe**: Preserves any custom `*-apm.prompt.md` files without APM metadata headers

**Integration Flow**:
1. Run `apm install` to fetch APM packages
2. APM automatically creates `.github/prompts/` directory if needed
3. Discovers `.prompt.md` files in each package
4. Copies prompts to `.github/prompts/` with `-apm` suffix (e.g., `accessibility-audit-apm.prompt.md`)
5. Adds metadata headers for version tracking
6. Updates `.gitignore` to exclude integrated prompts
7. VSCode automatically loads all prompts for your coding agents
8. Run `apm uninstall` to automatically remove integrated prompts

**Intent-First Discovery**:
The `-apm` suffix pattern enables natural autocomplete in VSCode:
- Type `/design` → VSCode shows `design-review-apm.prompt.md`
- Type `/accessibility` → VSCode shows `accessibility-audit-apm.prompt.md`
- Search by what you want to do, not where it comes from

**Example**: 
```bash
# Install package with auto-integration
apm install danielmeppiel/design-guidelines

# Result in VSCode:
# .github/prompts/accessibility-audit-apm.prompt.md  ✓ Available in chat
# .github/prompts/design-review-apm.prompt.md        ✓ Available in chat
# .github/prompts/style-guide-check-apm.prompt.md    ✓ Available in chat

# Use with natural autocomplete:
# Type: /design
# VSCode suggests: design-review-apm.prompt.md ✨
```

**VSCode Native Features**:
- All integrated prompts appear in VSCode's prompt picker
- Native chat integration with primitives
- Seamless `/prompt` command support
- File-pattern based instruction application
- Chatmode support for different personas

## Development Tool Integrations

### Git Integration

APM integrates with Git workflows for context-aware development:

```yaml
# .apm/prompts/git-workflow.prompt.md
---
description: Git-aware development workflow
mode: developer
tools: ["git"]
---

# Git-Aware Development

## Current Branch Analysis
Analyze current branch: `git branch --show-current`
Recent commits: `git log --oneline -10`

## Context-Aware Changes  
Based on Git history, understand:
- Feature branch purpose
- Related file changes
- Commit message patterns
- Code review feedback
```

### CI/CD Integration

Integrate APM workflows into your CI/CD pipelines:

```yaml
# .github/workflows/apm-quality-gate.yml
name: APM Quality Gate
on: [pull_request]

jobs:
  apm-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup APM
        run: curl -sSL https://raw.githubusercontent.com/danielmeppiel/apm/main/install.sh | sh
      - name: Code Review
        run: |
          apm compile
          apm run code-review --param files="${{ github.event.pull_request.changed_files }}"
      - name: Security Scan  
        run: apm run security-review --param severity="high"
      - name: Performance Check
        run: apm run performance-review --param threshold="200ms"
```

### Docker Integration

Containerize APM workflows for consistent environments:

```dockerfile
# Dockerfile.apm
FROM python:3.12-slim

# Install APM
RUN curl -sSL https://raw.githubusercontent.com/danielmeppiel/apm/main/install.sh | sh

# Install runtimes
RUN apm runtime setup copilot

# Copy project
COPY . /workspace
WORKDIR /workspace

# Compile primitives
RUN apm compile

ENTRYPOINT ["apm"]
```

```bash
# Use in CI/CD
docker run --rm -v $(pwd):/workspace apm-cli run code-review
```

### IDE Integration

Beyond VSCode, APM works with other popular IDEs:

#### Other IDEs with GitHub Copilot

Any IDE with GitHub Copilot support (JetBrains, Visual Studio, etc.) works with APM's prompt integration:

```bash
# Install APM packages
apm install danielmeppiel/design-guidelines

# GitHub Copilot automatically picks up:
# .github/prompts/*-apm.prompt.md (integrated prompts)
# .github/chatmodes/ (chat personalities)
# .github/instructions/ (file-pattern rules)
```

**Supported IDEs**:
- JetBrains (IntelliJ, PyCharm, WebStorm, etc.)
- Visual Studio
- VS Code
- Any IDE with GitHub Copilot integration

#### Cursor

Cursor does not follow the VSCode/GitHub Copilot `.github/` structure. Use APM's context compilation instead:

```bash
# Compile APM context into AGENTS.md
apm compile

# Then use AGENTS.md with Cursor:
# 1. Open Cursor settings
# 2. Reference or copy AGENTS.md content into your cursor rules
# 3. AGENTS.md works with any agent supporting the AGENTS.md format
```

## MCP (Model Context Protocol) Integration

APM provides first-class support for MCP servers:

### MCP Server Management

```yaml
# apm.yml - MCP dependencies
dependencies:
  mcp:
    - ghcr.io/github/github-mcp-server
    - ghcr.io/modelcontextprotocol/filesystem-server
    - ghcr.io/modelcontextprotocol/postgres-server
```

```bash
# Install MCP dependencies
apm install

# List available MCP tools
apm tools list

# Test MCP server connectivity
apm tools test github-mcp-server
```

### MCP Tool Usage in Workflows

```yaml
# .apm/prompts/github-integration.prompt.md
---
description: GitHub-aware development workflow
mode: developer
mcp:
  - ghcr.io/github/github-mcp-server
---

# GitHub Integration Workflow

## Available Tools
- `github_create_issue` - Create GitHub issues
- `github_list_prs` - List pull requests  
- `github_get_file` - Read repository files
- `github_search_code` - Search code across repositories

## Example Usage
Create an issue for the bug we just identified:
```
github_create_issue(
  title="Performance regression in /api/users endpoint", 
  body="Response time increased from 100ms to 500ms",
  labels=["bug", "performance"]
)
```
```

## API and Webhook Integration

### REST API Integration

APM can generate workflows that integrate with existing APIs:

```yaml  
# .apm/context/api-endpoints.context.md

# Company API Endpoints

## Internal APIs
- **User Service**: https://api.internal.com/users/v1
- **Payment Service**: https://api.internal.com/payments/v1  
- **Analytics Service**: https://api.internal.com/analytics/v1

## External APIs
- **Stripe**: https://api.stripe.com/v1
- **SendGrid**: https://api.sendgrid.com/v3
- **Twilio**: https://api.twilio.com/2010-04-01
```

### Webhook-Driven Workflows

```yaml
# .apm/prompts/webhook-handler.prompt.md
---
description: Process incoming webhooks and trigger appropriate actions
mode: integration-developer
input: [webhook_source, event_type, payload]
---

# Webhook Event Handler

## Event Processing
Source: ${input:webhook_source}
Event: ${input:event_type}  
Payload: ${input:payload}

## Processing Rules
Based on the webhook source and event type:
1. Validate payload signature
2. Parse event data
3. Trigger appropriate business logic
4. Send confirmation response
5. Log event for audit trail
```

## Database and ORM Integration

### Database-Aware Development

```yaml
# .apm/context/database-schema.context.md

# Database Schema Context

## Core Tables
- **users**: User accounts and profiles
- **organizations**: Company/team structures  
- **projects**: Development projects
- **permissions**: Role-based access control

## Relationships
- users belong to organizations
- projects belong to organizations
- permissions link users to resources

## Conventions
- All tables have created_at/updated_at timestamps
- Use UUIDs for primary keys
- Soft deletes with deleted_at column
```

### ORM-Specific Patterns

```yaml
# .apm/instructions/sqlalchemy.instructions.md
---
applyTo: "**/*models*.py"
---

# SQLAlchemy Best Practices

## Model Definition Standards
- Use declarative base for all models
- Include __tablename__ explicitly  
- Add proper relationships with lazy loading
- Include validation at the model level

## Query Patterns
- Use select() for new code (SQLAlchemy 2.0 style)
- Implement proper connection pooling
- Use transactions for multi-table operations
- Add query optimization with proper indexing hints
```

## Security Tool Integration

### Security Scanning Integration

```bash
# Integrate security tools into APM workflows
apm run security-audit --param tools="bandit,safety,semgrep" --param scope="all"
```

```yaml
# .apm/prompts/security-audit.prompt.md
---
description: Comprehensive security audit using multiple tools
mode: security-engineer
input: [tools, scope]
---

# Security Audit Workflow

## Tools Integration
Run security analysis using: ${input:tools}
Scope: ${input:scope}

## Automated Scanning
1. **Bandit**: Python security linter
2. **Safety**: Python dependency vulnerability scanner  
3. **Semgrep**: Multi-language static analysis
4. **Custom Rules**: Company-specific security patterns

## Report Generation
Consolidate findings into prioritized security report:
- Critical vulnerabilities requiring immediate action
- High-priority issues for next sprint
- Medium/low priority items for backlog
- False positives and exceptions
```

## Monitoring and Observability

### APT Integration with Observability Stack

```yaml
# .apm/prompts/add-monitoring.prompt.md
---
description: Add comprehensive monitoring to services
mode: sre-engineer  
input: [service_name, monitoring_level]
---

# Service Monitoring Setup

## Service: ${input:service_name}
## Level: ${input:monitoring_level}

## Monitoring Components
1. **Metrics**: Application and business metrics
2. **Logging**: Structured logging with correlation IDs
3. **Tracing**: Distributed tracing for request flows  
4. **Alerting**: SLO-based alerting rules

## Implementation Steps
- Add Prometheus metrics endpoints
- Configure structured logging with correlation
- Implement OpenTelemetry tracing
- Create Grafana dashboards
- Set up PagerDuty alerting rules
```

## Team Workflow Integration

### Agile/Scrum Integration

```yaml
# .apm/prompts/sprint-planning.prompt.md
---
description: AI-assisted sprint planning and task breakdown
mode: scrum-master
input: [epic, team_capacity, sprint_duration]
---

# Sprint Planning Assistant

## Epic Breakdown
Epic: ${input:epic}
Team Capacity: ${input:team_capacity}
Sprint Duration: ${input:sprint_duration}

## Task Analysis
1. **Epic Decomposition**: Break epic into implementable stories
2. **Effort Estimation**: Use team velocity for story points
3. **Dependency Mapping**: Identify cross-team dependencies
4. **Risk Assessment**: Highlight potential blockers
5. **Capacity Planning**: Match tasks to team member skills

## Sprint Goal
Generate clear, measurable sprint goal aligned with epic objectives.
```

## Next Steps

Ready to integrate APM with your existing tools? 

- **[Getting Started](getting-started.md)** - Set up APM in your environment
- **[Context Guide](primitives.md)** - Build custom integration workflows  
- **[Examples & Use Cases](examples.md)** - See integration patterns in action
- **[CLI Reference](cli-reference.md)** - Complete command documentation

Or explore specific integration patterns:
- Review the [VSCode Copilot Customization Guide](https://code.visualstudio.com/docs/copilot/copilot-customization) for VSCode-specific features
- Check the [Spec-kit documentation](https://github.com/github/spec-kit) for SDD integration details
- Explore [MCP servers](https://modelcontextprotocol.io/servers) for tool integration options