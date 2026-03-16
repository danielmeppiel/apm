---
title: "APM in CI/CD"
description: "Automate APM install in GitHub Actions, Azure Pipelines, and other CI systems."
sidebar:
  order: 1
---

APM integrates into your CI/CD pipeline to ensure agent context is always up to date.

## GitHub Actions

Use the official [apm-action](https://github.com/microsoft/apm-action) to install APM and run commands in your workflows:

```yaml
# .github/workflows/apm.yml
name: APM
on:
  push:
    branches: [main]
  pull_request:

jobs:
  install:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install APM packages
        uses: microsoft/apm-action@v1
        with:
          commands: |
            apm install
            # Optional: only needed if targeting Codex, Gemini, or other
            # tools without native APM integration
            # apm compile --verbose
```

### Private Dependencies

For private repositories, pass a GitHub token:

```yaml
      - name: Install APM packages
        uses: microsoft/apm-action@v1
        with:
          commands: |
            apm install
        env:
          GITHUB_APM_PAT: ${{ secrets.APM_PAT }}
```

### Verify Compiled Output (Optional)

If your project uses `apm compile` to target tools like Cursor, Codex, or Gemini, add a check to ensure compiled output stays in sync:

```yaml
      - name: Check for drift
        run: |
          apm compile
          if [ -n "$(git status --porcelain -- AGENTS.md CLAUDE.md)" ]; then
            echo "Compiled output is out of date. Run 'apm compile' locally and commit."
            exit 1
          fi
```

This step is not needed if your team only uses GitHub Copilot and Claude, which read deployed primitives natively.

### Verify Deployed Primitives

To ensure `.github/`, `.claude/`, `.cursor/`, and `.opencode/` integration files stay in sync with `apm.yml`, add a drift check:

```yaml
      - name: Check APM integration drift
        run: |
          apm install
          if [ -n "$(git status --porcelain -- .github/ .claude/ .cursor/ .opencode/)" ]; then
            echo "APM integration files are out of date. Run 'apm install' and commit."
            exit 1
          fi
```

This catches cases where a developer updates `apm.yml` but forgets to re-run `apm install`.

## Azure Pipelines

```yaml
steps:
  - script: |
      curl -sSL https://raw.githubusercontent.com/microsoft/apm/main/install.sh | sh
      apm install
      # Optional: only if targeting Codex, Gemini, or similar tools
      # apm compile
    displayName: 'APM Install'
    env:
      ADO_APM_PAT: $(ADO_PAT)
```

## General CI

For any CI system with Python available:

```bash
pip install apm-cli
apm install
# Optional: only if targeting Codex, Gemini, or similar tools
# apm compile --verbose
```

## Governance with `apm audit`

Run `apm audit` in pull requests to scan for hidden Unicode characters and other content issues. The command uses exit codes to signal results: **0** = clean, **1** = critical findings, **2** = warnings only. This lets CI gate on the result without any special flags.

:::note[Planned]
Lockfile consistency checking (`apm audit --ci`) is planned but not yet available. The workflow below uses `apm audit` exit codes, which work today.
:::

```yaml
# .github/workflows/apm-audit.yml
name: APM Audit
on: [pull_request]
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: microsoft/apm-action@v1
        with:
          commands: |
            apm install
            apm audit
        env:
          GITHUB_APM_PAT: ${{ secrets.APM_PAT }}
```

Configure this workflow as a **required status check** in your branch protection rules (or [GitHub Rulesets](../github-rulesets/)) to block PRs that introduce content issues. See the [Governance & Compliance](../../enterprise/governance/) page for policy details.

## Pack & Distribute

Use `apm pack` in CI to build a distributable bundle once, then consume it in downstream jobs without needing APM installed.

### Pack in CI (build once)

```yaml
- uses: microsoft/apm-action@v1
  with:
    commands: |
      apm install
      apm pack --archive --target all
- uses: actions/upload-artifact@v4
  with:
    name: agent-config
    path: build/*.tar.gz
```

### Consume in another job (no APM needed)

```yaml
- uses: actions/download-artifact@v4
  with:
    name: agent-config
- run: tar xzf build/*.tar.gz -C ./
```

Or use the apm-action restore mode to unpack a bundle directly:

```yaml
- uses: microsoft/apm-action@v1
  with:
    bundle: ./agent-config.tar.gz
```

See the [Pack & Distribute guide](../../guides/pack-distribute/) for the full workflow.

## Best Practices

- **Pin APM version** in CI to avoid unexpected changes: `pip install apm-cli==0.7.7`
- **Commit `apm.lock.yaml`** so CI resolves the same dependency versions as local development
- **Commit `.github/`, `.claude/`, `.cursor/`, and `.opencode/` deployed files** so contributors and cloud-based Copilot get agent context without running `apm install`
- **If using `apm compile`** (for Codex, Gemini), run it in CI and fail the build if the output differs from what's committed
- **Use `GITHUB_APM_PAT`** for private dependencies; never use the default `GITHUB_TOKEN` for cross-repo access
