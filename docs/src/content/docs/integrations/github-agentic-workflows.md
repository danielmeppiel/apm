---
title: "GitHub Agentic Workflows"
description: "How GitHub's Agentic Workflows platform uses APM natively — the integration model and three-tier architecture."
---

## APM in the GitHub Agentic Workflows Ecosystem

[GitHub Agentic Workflows](https://github.github.com/gh-aw/) (gh-aw) is GitHub's platform for running AI agents as first-class participants in the development lifecycle — reviewing PRs, triaging issues, and executing multi-step workflows.

APM is natively integrated into gh-aw as the **package management layer** for agent instructions. When a gh-aw agent starts, it uses APM to resolve, install, and compile the instruction context it needs.

## The Three-Tier Model

gh-aw organizes agent context into three tiers, each managed by APM:

### Tier 1: Platform Instructions

Base instructions provided by the gh-aw platform. These establish universal agent behaviour — safety rails, output formatting, and tool usage policies.

### Tier 2: Organization Packages

Shared instruction packages installed at the organization level. Platform engineers define coding standards, security policies, and review checklists that apply across all repositories.

```yaml
# org-level apm.yml
dependencies:
  security-standards: github/org/security-baseline
  review-policy: github/org/code-review-checklist
  style-guide: github/org/style-guide
```

### Tier 3: Repository Packages

Per-repo instruction packages that customize agent behaviour for a specific project:

```yaml
# repo-level apm.yml
dependencies:
  api-patterns: github/org/rest-api-patterns
  testing-kit: github/org/testing-best-practices
```

## How It Works

When a gh-aw agent is triggered (e.g., on a PR event):

1. **APM resolves** dependencies from all three tiers
2. **APM compiles** instructions with proper scoping and deduplication
3. **The agent receives** a single, optimized context — no pollution, no conflicts
4. **The agent executes** using the compiled instructions

This is the same `apm install && apm compile` workflow developers use locally, running automatically in the GitHub platform.

## Why This Matters

Without APM, platform engineers would need to manually maintain instruction files across hundreds of repositories. With APM:

- **Consistency**: Every agent gets the same base standards
- **Customization**: Repos can layer project-specific instructions on top
- **Isolation**: CI agents don't inherit developer-facing instructions
- **Versioning**: Instruction updates propagate through dependency resolution, not copy-paste

## Getting Started

If you're using gh-aw and want to leverage APM packages:

1. Add an `apm.yml` to your repository with your instruction dependencies
2. Run `apm install && apm compile` in your workflow setup
3. The compiled `AGENTS.md` becomes the agent's context

If you're a platform engineer setting up gh-aw for your organization, see the [gh-aw documentation](https://github.github.com/gh-aw/) for the full integration guide.

## Next Steps

- [APM in CI/CD](/apm/guides/cicd/) — isolated compilation for automated pipelines.
- [IDE & Tool Integration](/apm/integrations/ide-tools/) — APM with VS Code, GitHub Actions, and MCP servers.
- [Dependencies & Lockfile](/apm/guides/dependencies/) — managing instruction dependencies at scale.
