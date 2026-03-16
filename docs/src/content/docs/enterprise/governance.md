---
title: "Governance & Compliance"
description: "Enforce AI agent configuration policies with lock files, audit trails, and CI gates."
sidebar:
  order: 2
---

## The governance challenge

As AI agents become integral to software development, organizations face questions that traditional tooling was never designed to answer:

- **Incident response.** What agent instructions were active during a production incident?
- **Change management.** Who approved this agent configuration change, and when?
- **Policy enforcement.** Are all teams using approved plugins and instruction sources?
- **Audit readiness.** Can we produce evidence of agent configuration state at any point in time?

APM addresses these by treating agent configuration as auditable infrastructure, managed through the same version control and CI/CD practices that govern application code.

---

## APM's governance pipeline

Agent governance in APM follows a four-stage pipeline:

```
apm.yml (declare) -> apm.lock.yaml (pin) -> apm audit (verify) -> CI gate (enforce)
```

| Stage | Purpose | Artifact |
|-------|---------|----------|
| **Declare** | Define dependencies and their sources | `apm.yml` |
| **Pin** | Resolve every dependency to an exact commit | `apm.lock.yaml` |
| **Verify** | Confirm on-disk state matches the lock file | `apm audit` output |
| **Enforce** | Block merges when verification fails | Required status check |

Each stage builds on the previous one. The lock file provides the audit trail, the audit command detects drift, and the CI gate prevents unapproved changes from reaching protected branches.

---

## Lock file as audit trail

The `apm.lock.yaml` file is the single source of truth for what agent configuration is deployed. Every dependency is pinned to an exact commit SHA, making the lock file a complete, point-in-time record of agent state.

### What the lock file captures

```yaml
lockfile_version: '1'
generated_at: '2025-03-11T18:13:45.123456+00:00'
apm_version: 0.25.0
dependencies:
  - repo_url: https://github.com/contoso/agent-standards.git
    resolved_commit: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0
    resolved_ref: main
    version: 2.1.0
    depth: 1
    deployed_files:
      - .github/agents/code-review.md
      - .github/agents/security-scan.md
  - repo_url: https://github.com/contoso/shared-skills.git
    virtual_path: shared-skills/api-design
    resolved_commit: f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9
    resolved_ref: v1.4.0
    is_virtual: true
    depth: 2
    resolved_by: contoso/agent-standards.git
    deployed_files:
      - .github/skills/api-design/
```

Key fields for governance:

- **`resolved_commit`**: Exact commit SHA. No ambiguity about what code was deployed.
- **`depth`**: `1` for direct dependencies, `2+` for transitive. Identifies supply chain depth.
- **`resolved_by`**: For transitive dependencies, traces which direct dependency introduced them.
- **`deployed_files`**: Explicit list of files placed in the repository.
- **`generated_at`** and **`apm_version`**: Metadata for forensic reconstruction.

### Using git history for auditing

Because `apm.lock.yaml` is a committed file, standard git operations answer governance questions directly:

```bash
# Full history of every agent configuration change
git log --oneline apm.lock.yaml

# Who changed agent config, and when
git log --format="%h %ai %an: %s" apm.lock.yaml

# What was the exact agent configuration at release v4.2.1
git show v4.2.1:apm.lock.yaml

# Diff agent config between two releases
git diff v4.1.0..v4.2.1 -- apm.lock.yaml

# Find the commit that introduced a specific dependency
git log -p --all -S 'contoso/agent-standards' -- apm.lock.yaml
```

No additional tooling is required. The lock file turns git into an agent configuration audit log.

---

## Content scanning with `apm audit`

APM scans for hidden Unicode characters that can embed invisible instructions in prompt files. For background on the threat model, severity levels, and the pre-deployment gate that blocks critical findings during `apm install`, see [Content scanning](../security/#content-scanning) in the security model.

`apm audit` provides on-demand scanning independent of the install flow.

### Usage

```bash
apm audit                              # Scan all installed packages
apm audit <package>                    # Scan a specific package
apm audit --file .cursorrules          # Scan any file (even non-APM-managed)
apm audit --strip                      # Remove hidden characters (preserves emoji)
apm audit --strip --dry-run            # Preview what --strip would remove
apm audit -f sarif                     # SARIF output (for GitHub Code Scanning)
apm audit -o report.sarif              # Write SARIF report to file
apm audit -f json -o results.json      # JSON report to file
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Clean — no findings, info-only, or successful strip |
| 1 | Critical findings — tag characters, bidi overrides, or variation selectors 17–256 |
| 2 | Warnings only — zero-width characters, bidi marks, or other suspicious content |

### The `--file` escape hatch

`apm audit --file .cursorrules` scans any file, not just APM-managed ones. This is useful for inspecting files obtained outside the APM workflow — downloaded rules files, copy-pasted instructions, or files from PRs.

---

## CI enforcement with `apm audit`

Today, `apm audit` runs content scanning and returns exit codes (**0** = clean, **1** = critical findings, **2** = warnings), making it usable as a CI gate.

:::note[Planned Feature]
Lockfile consistency checking (`apm audit --ci`) is planned but not yet available. The planned behavior — verifying that the lock file matches the manifest and that deployed files are present — is described below for reference.
:::

### What works today

`apm audit` scans installed packages for hidden Unicode characters and content issues. Use it in CI to block PRs with critical findings:

```yaml
name: APM Audit
on:
  pull_request:
    paths:
      - 'apm.yml'
      - 'apm.lock.yaml'
      - '.github/agents/**'
      - '.github/skills/**'
      - '.copilot/agents/**'

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install and audit APM
        uses: microsoft/apm-action@v1
        with:
          commands: |
            apm install
            apm audit

      # Optional: upload SARIF to GitHub Code Scanning
      - name: SARIF audit report
        if: always()
        uses: microsoft/apm-action@v1
        with:
          commands: |
            apm audit -f sarif -o results.sarif
        continue-on-error: true

      - name: Upload SARIF
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: results.sarif

      - name: Step summary
        if: always()
        run: apm audit -f markdown >> $GITHUB_STEP_SUMMARY
```

### Planned: lockfile consistency checking

When `apm audit --ci` is available, it will additionally catch:

- **Lock file out of sync.** A dependency was added to `apm.yml` but `apm install` was not re-run.
- **Unapproved manual changes.** Someone hand-edited an agent instruction file that APM manages.
- **Missing dependencies.** A declared package failed to resolve or deploy.

### Configuring as a required check

Once the workflow runs on PRs, configure it as a required status check:

1. Navigate to your repository settings.
2. Under **Rules** (or **Branches** for legacy branch protection), select the target branch.
3. Add the `APM Audit` workflow job as a required status check.
4. PRs that fail the audit cannot be merged until the issue is corrected.

This ensures every merge to a protected branch passes content scanning.

---

## Drift detection with `apm audit --drift`

:::note[Planned Feature]
`apm audit --drift` is not yet available. The following describes planned behavior and is provided to illustrate the intended workflow.
:::

Drift occurs when the on-disk state of agent configuration diverges from what the lock file declares. The `apm audit --drift` command detects this divergence.

### What drift detection catches

- **Manual plugin additions.** Files added to agent directories that are not tracked by APM.
- **Hand-edited instruction files.** Modifications to APM-managed files outside the `apm install` workflow.
- **Removed dependencies.** Files deleted from disk that the lock file expects to be present.
- **Stale files.** Files from previously uninstalled packages that were not cleaned up.

### Usage

```bash
# Check for drift (human-readable output)
apm audit --drift

# Check for drift in CI (non-zero exit code on detection)
apm audit --drift --ci

# Use as a pre-commit check
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: apm-drift
        name: APM drift check
        entry: apm audit --drift
        language: system
        pass_filenames: false
```

Drift detection complements lock file verification. The audit checks that the lock file matches the manifest; drift detection checks that the file system matches the lock file.

---

## Policy enforcement patterns

Beyond CI gates, APM provides mechanisms to enforce organizational policies on agent configuration.

### Approved sources only

Restrict dependencies to packages from specific organizations or repositories. Review PRs that modify `apm.yml` to ensure all `source` entries reference approved origins:

```yaml
# apm.yml — all sources from approved org
packages:
  - name: code-review-standards
    source: https://github.com/contoso/agent-standards.git
    ref: v2.1.0
  - name: security-policies
    source: https://github.com/contoso/security-agents.git
    ref: v1.3.0
```

Combine with GitHub's CODEOWNERS to require security team approval for changes to `apm.yml`:

```
# CODEOWNERS
apm.yml    @contoso/platform-engineering
apm.lock.yaml   @contoso/platform-engineering
```

### Version pinning policy

Require exact version references rather than floating branch refs. Pinned versions ensure reproducibility and prevent unreviewed upstream changes from propagating:

```yaml
# Preferred: pinned to exact tag
ref: v2.1.0

# Acceptable: pinned to exact commit
ref: a1b2c3d4e5f6

# Discouraged: floating branch ref
ref: main
```

Enforce this policy through PR review or by scripting a check against `apm.yml` in CI.

### Transitive MCP server trust

When a dependency declares MCP server configurations, APM requires explicit opt-in before installing them transitively. The `--trust-transitive-mcp` flag on `apm install` controls this behavior:

```bash
# Default: transitive MCP servers are NOT installed
apm install

# Explicit opt-in: trust transitive MCP servers
apm install --trust-transitive-mcp
```

Without this flag, transitive MCP server declarations are skipped. This prevents a dependency from silently introducing tool access that the consuming repository did not explicitly approve.

### Constitution injection

A constitution is an organization-wide rules block applied to all compiled agent instructions. Define it in `memory/constitution.md` and APM injects it into every compilation output with hash verification:

```markdown
<!-- memory/constitution.md -->
## Organization Standards

- All code suggestions must include error handling.
- Never suggest credentials or secrets in code.
- Follow the organization's API design guidelines.
- Escalate security-sensitive operations to a human reviewer.
```

The constitution block is rendered into compiled output with a SHA-256 hash, enabling drift detection if the block is tampered with after compilation:

```markdown
<!-- APM_CONSTITUTION_BEGIN -->
hash: e3b0c44298fc1c14 path: memory/constitution.md
[Constitution content]
<!-- APM_CONSTITUTION_END -->
```

This ensures that organizational rules are consistently applied across all teams and cannot be silently bypassed.

---

## Integration with GitHub Rulesets

GitHub Rulesets provide a scalable way to enforce APM governance across multiple repositories.

### Level 1: Required status check

Configure `apm audit` as a required status check through Rulesets (see [CI enforcement](#ci-enforcement-with-apm-audit) above):

1. Create a new Ruleset at the organization or repository level.
2. Target the branches you want to protect (e.g., `main`, `release/*`).
3. Add a **Require status checks to pass** rule.
4. Select the `APM Audit` workflow job as a required check.

This blocks any PR that introduces agent configuration drift from merging into protected branches.

For detailed setup instructions, see the [CI/CD integration guide](../../integrations/ci-cd/).

---

## Compliance scenarios

### SOC 2 evidence

SOC 2 audits require evidence that configuration changes are authorized and traceable. APM's lock file provides this:

- **Change authorization.** Every `apm.lock.yaml` change goes through a PR, requiring review and approval.
- **Change history.** `git log apm.lock.yaml` produces a complete, tamper-evident history of every agent configuration change with author, timestamp, and diff.
- **Point-in-time state.** `git show <tag>:apm.lock.yaml` reconstructs the exact agent configuration active at any release.

Link auditors directly to the lock file history in your repository. No separate audit system is needed.

### Security audit

When a security review requires understanding what instructions agents were following:

```bash
# What agent configuration was active at the time of the incident
git show <commit-at-incident-time>:apm.lock.yaml

# What files were deployed by a specific package
grep -A 10 'contoso/agent-standards' apm.lock.yaml

# Full diff of agent config changes in the last 90 days
git log --since="90 days ago" -p -- apm.lock.yaml
```

The lock file answers "what was running" without requiring access to the original package repositories. The `resolved_commit` field points to the exact source code that was deployed.

### Change management

APM enforces change management by design:

1. **Declaration.** Changes start in `apm.yml`, which is a committed, reviewable file.
2. **Resolution.** `apm install` resolves declarations to exact commits in `apm.lock.yaml`.
3. **Review.** Both files are included in the PR diff for peer review.
4. **Verification.** `apm audit` scans for content issues before merge. Lockfile consistency checking (`apm audit --ci`) is planned — currently achieved through PR review of `apm.lock.yaml` diffs.
5. **Traceability.** Git history provides a permanent record of who changed what and when.

No agent configuration change can reach a protected branch without passing through this pipeline.

---

## Summary

| Capability | Mechanism | Status |
|---|---|---|
| Dependency pinning | `apm.lock.yaml` with exact commit SHAs | Available |
| Audit trail | Git history of `apm.lock.yaml` | Available |
| Constitution injection | `memory/constitution.md` with hash verification | Available |
| Transitive MCP trust control | `--trust-transitive-mcp` flag | Available |
| Content scanning | Pre-deploy gate blocks critical hidden Unicode; `apm audit` for on-demand checks | Available |
| CI enforcement (content scanning) | `apm audit` exit codes as required status check | Available |
| CI enforcement (lockfile consistency) | `apm audit --ci` for manifest/lockfile verification | Planned |
| Drift detection | `apm audit --drift` | Planned |
| Approved source policies | CODEOWNERS + PR review | Available (manual) |
| GitHub Rulesets integration | Required status checks | Available |

For CI/CD setup details, see the [CI/CD integration guide](../../integrations/ci-cd/). For lock file internals, see [Key Concepts](../../introduction/key-concepts/).
