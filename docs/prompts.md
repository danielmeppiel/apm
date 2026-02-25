# Prompts Guide

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

See [MCP Integration Status](wip/mcp-integration.md) for Phase 2 development plans.

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

- Learn about [Runtime Integration](runtime-integration.md) to setup and use different AI runtimes
- See [CLI Reference](cli-reference.md) for complete script execution commands
- Check [Development Guide](development.md) for local development setup
