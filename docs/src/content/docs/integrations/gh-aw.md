---
title: "GitHub Agentic Workflows"
description: "How APM integrates with GitHub Agentic Workflows for automated agent pipelines."
sidebar:
  order: 2
---

[GitHub Agentic Workflows](https://github.github.com/gh-aw/) (gh-aw) lets you write repository automation in markdown and run it as GitHub Actions using AI agents. APM and gh-aw have a native integration: gh-aw recognizes APM packages as first-class dependencies.

## How They Work Together

| Tool | Role |
|------|------|
| **APM** | Manages the *context* your AI agents use -- skills, instructions, prompts, agents |
| **gh-aw** | Manages the *automation* that triggers AI agents -- event-driven workflows |

APM defines **what** agents know. gh-aw defines **when** and **how** they act.

## Integration Approaches

### Frontmatter Dependencies (Recommended)

gh-aw natively supports APM through a [`dependencies:` frontmatter field](https://github.github.com/gh-aw/reference/frontmatter/#apm-dependencies-dependencies). Declare APM packages directly in your workflow's frontmatter and gh-aw handles the rest.

**Simple array format:**

```yaml
---
on:
  pull_request:
    types: [opened]
engine: copilot

dependencies:
  - microsoft/apm-sample-package
  - github/awesome-copilot/skills/review-and-refactor
---

# Code Review

Review the pull request using the installed coding standards and skills.
```

**Object format with options:**

```yaml
---
on:
  issues:
    types: [opened]
engine: copilot

dependencies:
  packages:
    - microsoft/apm-sample-package
    - your-org/security-compliance
  isolated: true
---

# Issue Triage

Analyze the opened issue for security implications.
```

Each entry is a standard APM package reference -- either `owner/repo` for a full package or `owner/repo/path/to/skill` for an individual primitive.

**How it works:**

1. The gh-aw compiler detects the `dependencies:` field in your workflow frontmatter.
2. In the **activation job**, APM resolves the full dependency tree and packs the result.
3. In the **agent job**, the bundle is unpacked into the workspace and the agent discovers the primitives.

The APM compilation target is automatically inferred from the configured `engine:` field (`copilot`, `claude`, or `all` for other engines). No manual target configuration is needed.

### apm-action Pre-Step

For more control over the installation process, use [`microsoft/apm-action@v1`](https://github.com/microsoft/apm-action) as an explicit workflow step. This approach runs `apm install` directly, giving you access to the full APM CLI. To also compile, add `compile: true` to the action configuration.

```yaml
---
on:
  pull_request:
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

# Code Review

Review the PR using the installed coding standards.
```

The repo needs an `apm.yml` with dependencies and `apm.lock.yaml` for reproducibility. The action runs as a pre-agent step, deploying primitives to `.github/` where the agent discovers them.

**When to use this over frontmatter dependencies:**

- Custom compilation options (specific targets, flags)
- Running additional APM commands (audit, preview)
- Workflows that need `apm.yml`-based configuration
- Debugging dependency resolution

## Using APM Bundles

For sandboxed environments where network access is restricted during workflow execution, use pre-built APM bundles:

1. Run `apm pack` in your CI pipeline to produce a self-contained bundle.
2. Distribute the bundle as a workflow artifact or commit it to the repository.
3. Reference the bundled primitives in your workflow.

```yaml
---
on: pull_request
engine: copilot
imports:
  - .github/agents/code-reviewer.md
  - .github/agents/security-auditor.md
---

# Code Review
Review the PR using team standards.
```

Bundles resolve full dependency trees ahead of time, so workflows need zero network access at runtime.

See the [CI/CD Integration guide](../ci-cd/) for details on building and distributing bundles.

## Content Scanning

APM automatically scans dependencies for hidden Unicode characters during installation. Critical findings block deployment. This applies to both direct `apm install` and when GitHub Agentic Workflows resolves frontmatter dependencies via apm-action.

For CI visibility into scan results (SARIF reports, step summaries), see the [CI/CD Integration guide](../../integrations/ci-cd/#content-scanning-in-ci).

For details on what APM detects, see [Content scanning](../../enterprise/security/#content-scanning).

## Isolated Mode

When a gh-aw workflow runs in a repository that already has developer-focused instructions (like "use 4-space tabs" or "prefer functional style"), those instructions become noise for an automated agent that should only follow its declared dependencies.

The `isolated` flag addresses this. When set to `true` in the object format:

```yaml
dependencies:
  packages:
    - your-org/triage-rules
  isolated: true
```

gh-aw clears existing `.github/` primitive directories (instructions, skills, agents) before unpacking the APM bundle. The agent sees only the context declared by the workflow, preventing instruction pollution from the host repository.

## Learn More

- [gh-aw Documentation](https://github.github.com/gh-aw/)
- [gh-aw Frontmatter Reference](https://github.github.com/gh-aw/reference/frontmatter/)
- [APM Compilation Guide](../../guides/compilation/)
- [APM CLI Reference](../../reference/cli-commands/)
- [CI/CD Integration](../ci-cd/)
