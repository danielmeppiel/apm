---
title: "APM in CI/CD"
description: "Use APM in continuous integration pipelines — the apm-action, isolated compilation, and solving instruction pollution."
---

## The Problem: Instruction Pollution

When an AI agent runs in CI — reviewing PRs, generating code, or running automated checks — it inherits **all** the instructions in the repository. Developer-facing instructions like "ask me before deleting files" or "use my preferred logging style" leak into the CI context, causing the agent to:

- **Hallucinate** interactive prompts in a non-interactive pipeline
- **Waste tokens** on irrelevant developer preferences
- **Produce inconsistent results** across runs as instructions conflict

This is **instruction pollution**: CI agents receiving context that was never meant for them.

## The Solution: Isolated Compilation

APM's `compile` command supports an `--isolated` flag that strips developer-facing context and produces a minimal, CI-appropriate instruction set:

```bash
apm compile --isolated
```

In isolated mode, APM:

1. Excludes instructions scoped to interactive workflows
2. Retains only CI-relevant rules (testing, security, review standards)
3. Produces a deterministic output suitable for automated pipelines

## Using APM in GitHub Actions

### Quick Setup

Add APM to your workflow using the official GitHub Action:

```yaml
name: AI Code Review
on: [pull_request]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install APM
        run: |
          curl -fsSL https://raw.githubusercontent.com/microsoft/apm/main/install.sh | bash
          echo "$HOME/.local/bin" >> $GITHUB_PATH

      - name: Install packages and compile
        run: |
          apm install
          apm compile --isolated
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### What `--isolated` Changes

| Behaviour | Default compile | Isolated compile |
|---|---|---|
| Developer instructions | Included | Excluded |
| CI/CD rules | Included | Included |
| Interactive prompts | Included | Excluded |
| Output determinism | Best-effort | Guaranteed |

## Best Practices

### Separate CI-specific instructions

Create instructions scoped explicitly to CI:

```markdown
---
applyTo: "**"
context: ci
---
# CI Review Standards
- Flag any test without assertions
- Reject PRs that decrease coverage
- Verify all new endpoints have auth checks
```

### Pin dependencies in CI

Always run from a lockfile in CI to ensure reproducible builds:

```bash
apm install  # uses apm.lock when present
```

### Use environment tokens

Set `GITHUB_TOKEN` or `APM_GITHUB_TOKEN` so APM can fetch private packages in CI:

```yaml
env:
  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Next Steps

- [GitHub Agentic Workflows](/apm/integrations/github-agentic-workflows/) — how GitHub's agentic platform uses APM natively.
- [Compilation & Optimization](/apm/guides/compilation/) — deep dive into the compilation algorithm.
- [Dependencies & Lockfile](/apm/guides/dependencies/) — lockfile management for reproducible installs.
