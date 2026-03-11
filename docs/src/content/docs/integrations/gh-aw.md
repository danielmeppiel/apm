---
title: "GitHub Agentic Workflows"
description: "Use APM packages with GitHub Agentic Workflows (gh-aw) for automated repository maintenance."
sidebar:
  order: 1
---

[GitHub Agentic Workflows](https://github.github.com/gh-aw/) (gh-aw) lets you write repository automation in markdown and run it as GitHub Actions using AI agents. APM and gh-aw complement each other naturally.

## How They Work Together

| Tool | Role |
|------|------|
| **APM** | Manages the *context* your AI agents use — skills, instructions, prompts |
| **gh-aw** | Manages the *automation* that triggers AI agents — event-driven workflows |

APM defines **what** agents know. gh-aw defines **when** and **how** they act.

## Example: Automated Code Review

1. **APM** installs your team's review standards:

```yaml
# apm.yml
dependencies:
  apm:
    - your-org/code-review-standards
    - github/awesome-copilot/agents/api-architect.agent.md
```

2. **gh-aw** triggers a review workflow on every PR:

```markdown
<!-- .github/workflows/review.workflow.md -->
# Code Review Workflow

When a pull request is opened, review the changed files against
the project's coding standards in AGENTS.md.

Post review comments on any violations found.
```

3. The AI agent uses the context APM compiled into `AGENTS.md` to perform a standards-aware review automatically.

## Setup

1. Install both tools:

```bash
# APM
curl -sSL https://raw.githubusercontent.com/microsoft/apm/main/install.sh | sh

# gh-aw (GitHub CLI extension)
gh extension install github/gh-aw
```

2. Configure your project with APM packages, then add gh-aw workflows that reference the compiled context.

## Learn More

- [gh-aw Documentation](https://github.github.com/gh-aw/)
- [APM Compilation Guide](/apm/guides/compilation/)
- [APM CLI Reference](/apm/reference/cli-commands/)
