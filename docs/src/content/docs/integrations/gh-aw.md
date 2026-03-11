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

## Integration Tiers

APM integrates with GitHub Agentic Workflows at three levels of depth.

### Tier 1: Pre-Step with apm-action (Works Today)

The minimum viable integration. Zero changes to gh-aw. Uses the `steps:` frontmatter field:

```yaml
---
on:
  issues:
    types: [opened]
engine: copilot

steps:
  - name: Install agent primitives
    uses: microsoft/apm-action@v1
    with:
      script: install
    env:
      GITHUB_TOKEN: ${{ github.token }}
---

# Issue Triage

Triage this issue using the installed compliance rules and security skills.
```

The repo has an `apm.yml` with dependencies and `apm.lock` for reproducibility. The APM action runs `apm install && apm compile` as a pre-agent step. Primitives deploy to `.github/`. The coding agent discovers them naturally.

### Tier 2: Inline Dependencies (APM Enhancement)

Declare dependencies directly in workflow frontmatter -- no separate `apm.yml` needed:

```yaml
---
on:
  issues:
    types: [opened]
engine: copilot

steps:
  - uses: microsoft/apm-action@v1
    with:
      dependencies: |
        microsoft/compliance-rules@v2.1.0
        myorg/security-skill@v1.0.0
      isolated: true
---

# Issue Triage
Analyze the opened issue for security implications.
```

`isolated: true` means: install packages to a clean workspace, ignore the repo's existing `.github/instructions/`. The agent sees only APM-managed context.

### Tier 3: Native Frontmatter Integration (Future Vision)

The endgame: gh-aw recognizes APM as a dependency manager natively via an `apm:` frontmatter field. No `steps:` boilerplate. Subject to gh-aw team collaboration.

## Using APM Bundles with gh-aw

For sandboxed environments where network access is restricted, use pre-built APM bundles:

```yaml
---
on: pull_request
engine: copilot
imports:
  - .github/agents/code-reviewer.md     # produced by APM bundle
  - .github/agents/security-auditor.md   # produced by APM bundle
---

# Code Review
Review the PR using team standards.
```

Bundles complement gh-aw's native `imports:` -- resolving full dependency trees rather than individual files, with zero network required at workflow runtime.

See the [CI/CD Integration guide](/apm/integrations/ci-cd/) for details on building and distributing bundles.

## Solving Instruction Pollution

When a gh-aw workflow runs in a repo with developer-focused instructions (like "use 4-space tabs"), those instructions become noise for an automated triage bot. APM's `--isolated` mode (Tier 2) addresses this by creating a clean execution context with only the workflow's declared dependencies.

## Learn More

- [gh-aw Documentation](https://github.github.com/gh-aw/)
- [APM Compilation Guide](/apm/guides/compilation/)
- [APM CLI Reference](/apm/reference/cli-commands/)
- [CI/CD Integration](/apm/integrations/ci-cd/)
