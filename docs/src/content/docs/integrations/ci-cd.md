---
title: "APM in CI/CD"
description: "Automate APM install and compile in GitHub Actions, Azure Pipelines, and other CI systems."
sidebar:
  order: 1
---

APM integrates into your CI/CD pipeline to ensure agent context is always up to date and compiled correctly.

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
  compile:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install APM & compile
        uses: microsoft/apm-action@v1
        with:
          commands: |
            apm install
            apm compile --verbose
```

### Private Dependencies

For private repositories, pass a GitHub token:

```yaml
      - name: Install APM & compile
        uses: microsoft/apm-action@v1
        with:
          commands: |
            apm install
            apm compile
        env:
          GITHUB_APM_PAT: ${{ secrets.APM_PAT }}
```

### Verify Compiled Output

Add a check to ensure `AGENTS.md` stays in sync with `apm.yml`:

```yaml
      - name: Check for drift
        run: |
          apm compile
          git diff --exit-code AGENTS.md CLAUDE.md || \
            (echo "Compiled output is out of date. Run 'apm compile' locally." && exit 1)
```

## Azure Pipelines

```yaml
steps:
  - script: |
      curl -sSL https://raw.githubusercontent.com/microsoft/apm/main/install.sh | sh
      apm install
      apm compile
    displayName: 'APM Install & Compile'
    env:
      ADO_APM_PAT: $(ADO_PAT)
```

## General CI

For any CI system with Python available:

```bash
pip install apm-cli
apm install
apm compile --verbose
```

## Governance with `apm audit`

> **Roadmap:** `apm audit --ci` is not yet available. This section describes the planned CI governance workflow for a future release. Today, commit `apm.lock` and review its diff in pull requests to detect configuration drift manually.

Run `apm audit --ci` in pull requests to verify the lock file matches the installed state. This catches configuration drift before it reaches your default branch.

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
            apm audit --ci
        env:
          GITHUB_APM_PAT: ${{ secrets.APM_PAT }}
```

Configure this workflow as a **required status check** in your branch protection rules (or [GitHub Rulesets](../github-rulesets/)) to block PRs that introduce config drift. See the [Governance & Compliance](../../enterprise/governance/) page for policy details.

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
- **Commit `apm.lock`** so CI resolves the same dependency versions as local development
- **Run `apm compile` in CI** and fail the build if the output differs from what's committed — this catches drift early
- **Use `GITHUB_APM_PAT`** for private dependencies; never use the default `GITHUB_TOKEN` for cross-repo access
