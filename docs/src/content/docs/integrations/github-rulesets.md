---
title: "GitHub Rulesets"
description: "Enforce AI agent configuration governance using APM with GitHub branch protection and Rulesets."
sidebar:
  order: 5
---

GitHub Rulesets and branch protection rules can require status checks before merging. APM's `apm audit --ci` integrates as a required status check to enforce agent configuration governance, ensuring that changes to agent context go through the manifest and lock file rather than being made ad hoc.

## How It Works

The workflow is straightforward:

1. `apm audit --ci` runs in a GitHub Actions workflow on every pull request.
2. It verifies that the lock file matches the installed state, no undeclared config changes exist, and all dependencies are resolvable.
3. You configure this workflow as a required status check in branch protection or Rulesets.
4. PRs that change agent config without updating the manifest or lock file are blocked from merging.

This turns APM from a development convenience into an enforceable policy.

## Setup

### Step 1: Create the GitHub Actions Workflow

Add a workflow file at `.github/workflows/apm-audit.yml`:

```yaml
# .github/workflows/apm-audit.yml
name: APM Audit
on:
  pull_request:

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install & audit
        uses: microsoft/apm-action@v1
        with:
          commands: |
            apm install
            apm audit --ci
        env:
          GITHUB_APM_PAT: ${{ secrets.APM_PAT }}
```

The `GITHUB_APM_PAT` secret is only required if your `apm.yml` references private repositories. For public dependencies you can omit it.

### Step 2: Add the Required Status Check

1. Go to your repository **Settings** > **Rules**.
2. Select an existing branch ruleset or create a new one targeting your default branch.
3. Enable **Require status checks to pass** and add `APM Audit` (the workflow job name) as a required check.

Alternatively, in classic branch protection rules under **Settings** > **Branches** > **Branch protection rules**, enable **Require status checks to pass before merging** and search for `APM Audit`.

Once configured, any PR that modifies agent configuration files without a corresponding manifest and lock file update will fail the check.

## What It Catches

`apm audit --ci` detects the following issues:

- **Lock file out of sync** — `apm.lock.yaml` does not match the current state of `apm.yml`.
- **Undeclared config changes** — manual edits to files in `.github/instructions/` or other managed paths that bypass the manifest.
- **Missing dependencies** — packages declared in `apm.yml` that cannot be resolved.
- **Deleted or modified managed files** — files that APM deployed but were removed or altered outside of APM.

When any of these conditions is detected, the command exits with a non-zero status code and the check fails.

## Governance Levels

APM's integration with GitHub governance is evolving:

| Level | Description | Status |
|-------|-------------|--------|
| 1 | `apm audit --ci` as a required status check | Available now |
| 2 | GitHub recommends apm-action for agent governance | Future |
| 3 | Native Rulesets UI for agent configuration policy | Future |

Level 1 is fully functional today. Levels 2 and 3 represent deeper platform integration that would reduce setup friction.

## Combining with Other Checks

APM audit complements your existing CI checks — it does not replace them. A typical PR pipeline might include:

- **Linting and formatting** — code style enforcement
- **Unit and integration tests** — functional correctness
- **Security scanning** — vulnerability detection
- **APM audit** — agent configuration governance

Each check has a distinct purpose. APM audit focuses exclusively on whether agent context changes are properly declared and consistent.

## Customizing the Workflow

### Running Audit Alongside Compile

You can combine audit with compilation to catch both governance violations and output drift in a single workflow:

```yaml
jobs:
  apm:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: APM checks
        uses: microsoft/apm-action@v1
        with:
          commands: |
            apm install
            apm audit --ci
            # Optional: only needed if targeting Codex, Gemini, or similar
            # apm compile
            # git diff --exit-code AGENTS.md || \
            #   (echo "Compiled output is out of date. Run 'apm compile' locally." && exit 1)
        env:
          GITHUB_APM_PAT: ${{ secrets.APM_PAT }}
```

### Separate Jobs for Granular Status

If your project uses `apm compile` (for Codex, Gemini, or other tools without native APM integration), you can add audit and compile as separate required checks:

```yaml
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

  compile:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: microsoft/apm-action@v1
        with:
          commands: |
            apm install
            apm compile --verbose
```

This lets you require both `audit` and `compile` as independent status checks in your ruleset. The compile job is only needed if your project targets tools that require compiled instruction files.

## Troubleshooting

### Audit Fails on a Clean PR

If `apm audit --ci` fails on a PR that did not touch agent config, the lock file is likely already out of sync on the base branch. Run `apm install && apm audit` locally on the base branch to confirm, then commit the fix.

### Status Check Not Appearing in Rulesets

The status check name must match the **job name** in your workflow file (e.g., `audit`), not the workflow name. Run the workflow at least once so GitHub registers the check name, then add it to your ruleset.

## Related

- [CI/CD Pipelines](../ci-cd/) — full CI integration guide
- [Manifest Schema](../../reference/manifest-schema/) — manifest and lock file reference
