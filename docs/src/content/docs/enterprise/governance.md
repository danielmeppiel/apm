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
| **Verify** | Scan deployed content for hidden threats | `apm audit` output |
| **Enforce** | Block merges when verification fails | Required status check |

Each stage builds on the previous one. The lock file provides the audit trail, content scanning verifies file safety, and the CI gate prevents unapproved changes from reaching protected branches.

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

APM uses a two-layer security model for hidden Unicode threats. **Layer 1 is automatic:** `apm install`, `apm compile`, and `apm unpack` all scan for hidden characters and block critical findings before deployment — zero configuration required. **Layer 2 is explicit:** `apm audit` provides reporting (SARIF/JSON/markdown for CI artifacts), remediation (`--strip`), and standalone scanning (`--file`) independent of the install flow. For the threat model, severity levels, and gate behavior, see [Content scanning](../security/#content-scanning) in the security model.

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

## CI enforcement

`apm install` is the CI gate — it blocks deployment of packages with critical content findings, exiting with code 1. No additional configuration is needed.

`apm audit` adds reporting on top. Run it after install to generate SARIF reports for GitHub Code Scanning, JSON for tooling, or markdown for step summaries.

### Lockfile consistency checking

`apm audit --ci` verifies that the manifest, lock file, and deployed files are in sync. It runs 6 baseline checks with no configuration:

| Check | Validates |
|-------|-----------|
| `lockfile-exists` | `apm.lock.yaml` is present when `apm.yml` declares dependencies |
| `ref-consistency` | Every dependency's manifest ref matches the lockfile's resolved ref |
| `deployed-files-present` | All files listed in lockfile `deployed_files` exist on disk |
| `no-orphaned-packages` | No lockfile packages are absent from the manifest |
| `config-consistency` | MCP server configs match lockfile baseline |
| `content-integrity` | Deployed files contain no critical hidden Unicode characters |

```bash
# Run baseline checks
apm audit --ci

# JSON output for tooling
apm audit --ci -f json

# SARIF output for GitHub Code Scanning
apm audit --ci -f sarif -o audit.sarif
```

Exit codes: **0** = all checks passed, **1** = one or more checks failed.

### Recommended workflow

Use `microsoft/apm-action@v1` to install packages and optionally generate an audit report in one step:

```yaml
name: APM
on:
  pull_request:
    paths:
      - 'apm.yml'
      - 'apm.lock.yaml'
      - '.github/agents/**'
      - '.github/skills/**'
      - '.copilot/agents/**'

jobs:
  install:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v4
      - uses: microsoft/apm-action@v1
        id: apm
        with:
          audit-report: true
        env:
          GITHUB_APM_PAT: ${{ secrets.APM_PAT }}
      - uses: github/codeql-action/upload-sarif@v3
        if: always() && steps.apm.outputs.audit-report-path
        with:
          sarif_file: ${{ steps.apm.outputs.audit-report-path }}
          category: apm-audit
```

### Configuring as a required check

Once the workflow runs on PRs, configure it as a required status check:

1. Navigate to your repository settings.
2. Under **Rules** (or **Branches** for legacy branch protection), select the target branch.
3. Add the `APM` workflow job as a required status check.
4. PRs that introduce packages with critical findings or lockfile inconsistencies cannot be merged.

---

## Organization policy governance

`apm audit --ci --policy org` enforces organization-wide rules defined in `apm-policy.yml`. This adds 16 policy checks on top of the 6 baseline checks.

### How it works

1. **Define policy** — create `apm-policy.yml` in your org's `.github` repository.
2. **Auto-discover** — `--policy org` fetches the policy via GitHub API from `<org>/.github/apm-policy.yml`.
3. **Enforce** — `apm audit --ci --policy org` runs all 22 checks (6 baseline + 16 policy).

### Policy schema

The policy file controls dependencies (allow/deny/require), MCP governance, compilation rules, manifest requirements, and unmanaged file detection:

```yaml
name: "Contoso Engineering"
version: "1.0.0"
enforcement: block

dependencies:
  allow: ["contoso/**"]
  deny: ["untrusted-org/**"]
  require: ["contoso/agent-standards"]
  max_depth: 5

mcp:
  self_defined: warn
  transport:
    allow: [stdio, streamable-http]

unmanaged_files:
  action: warn
```

For the complete schema, all check names, and pattern matching rules, see the [Policy Reference](../policy-reference/).

### Two-tier enforcement

| Tier | Command | Checks | Requires policy |
|------|---------|--------|-----------------|
| Baseline | `apm audit --ci` | 6 lockfile consistency checks | No |
| Policy | `apm audit --ci --policy org` | 6 baseline + 16 policy checks | Yes |

Baseline catches configuration drift. Policy enforces organizational standards.

### Inheritance

Policies support a three-level inheritance chain using `extends`:

```
Enterprise hub → Org policy → Repo override
```

Child policies can only tighten constraints — deny lists grow (union), allow lists shrink (intersection), scalar values escalate to the stricter option. See [Inheritance](../policy-reference/#inheritance) for merge rules.

### CI integration

```bash
# Baseline only (no policy needed)
apm audit --ci

# Full policy enforcement (auto-discover from org)
apm audit --ci --policy org --no-cache

# SARIF output for GitHub Code Scanning
apm audit --ci --policy org --no-cache -f sarif -o policy.sarif
```

`--no-cache` forces a fresh policy fetch — recommended for CI. The policy is cached locally with a configurable TTL (default: 1 hour) to avoid repeated API calls during development.

For step-by-step CI setup, see the [CI Policy Enforcement guide](../../guides/ci-policy-setup/).

---

## Drift detection

:::note[Planned Feature]
`apm audit --drift` is not yet available. The following describes planned behavior and is provided to illustrate the intended workflow.
:::

For unmanaged file detection (files in governance directories not tracked by APM), use `apm audit --ci --policy` with the `unmanaged_files` policy section. See the [Policy Reference](../policy-reference/#unmanaged_files) for configuration.

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

### Approved sources

Use the `dependencies.allow` and `dependencies.deny` fields in `apm-policy.yml` to restrict which packages repositories can depend on. For manual enforcement without a policy file, combine with GitHub's CODEOWNERS:

```
# CODEOWNERS
apm.yml    @contoso/platform-engineering
apm.lock.yaml   @contoso/platform-engineering
```

See the [Policy Reference](../policy-reference/#dependencies) for pattern syntax.

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

Configure the APM workflow as a required status check through Rulesets (see [CI enforcement](#ci-enforcement) above):

1. Create a new Ruleset at the organization or repository level.
2. Target the branches you want to protect (e.g., `main`, `release/*`).
3. Add a **Require status checks to pass** rule.
4. Select the `APM` workflow job as a required check.

This blocks any PR that introduces packages with critical content findings from merging into protected branches.

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
4. **Verification.** `apm audit --ci` verifies lockfile consistency. Add `--policy org` for organizational policy enforcement.
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
| CI enforcement (content scanning) | Built into `apm install`; `apm audit` for SARIF reporting | Available |
| CI enforcement (lockfile consistency) | `apm audit --ci` for manifest/lockfile verification | Available |
| Organization policy enforcement | `apm audit --ci --policy org` with `apm-policy.yml` | Available |
| Policy inheritance | `extends:` for enterprise → org → repo chains | Available |
| Drift detection | `apm audit --drift` | Planned |
| GitHub Rulesets integration | Required status checks | Available |

For CI/CD setup details, see the [CI/CD integration guide](../../integrations/ci-cd/). For policy schema and check details, see the [Policy Reference](../policy-reference/). For lock file internals, see [Key Concepts](../../introduction/key-concepts/).
