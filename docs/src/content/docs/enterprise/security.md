---
title: "Security Model"
description: "How APM handles dependency provenance, path security, and supply chain integrity."
sidebar:
  order: 3
---

This page documents APM's security posture for enterprise security reviews, compliance audits, and supply chain assessments.

## What APM does

APM is a build-time dependency manager for AI prompts and configuration. It performs four operations:

1. **Resolves git repositories** — clones or sparse-checks-out packages from GitHub or Azure DevOps.
2. **Deploys static files** — copies markdown, JSON, and YAML files into project directories (`.github/`, `.claude/`).
3. **Generates compiled output** — produces `AGENTS.md`, `CLAUDE.md`, and similar files from templates and prompts.
4. **Records a lock file** — writes `apm.lock` with exact commit SHAs for every resolved dependency.

## What APM does NOT do

APM has no runtime footprint. Once `apm install` or `apm compile` completes, the process exits.

- **No runtime component.** APM generates files then terminates. It does not run alongside your application.
- **No network calls after install.** All network activity (git clone/fetch) occurs during dependency resolution. There are no callbacks, webhooks, or phone-home requests.
- **No arbitrary code execution.** APM does not execute scripts from packages, evaluate expressions in templates, or run downloaded code.
- **No access to application data.** APM never reads databases, API responses, application state, or user data.
- **No persistent background processes.** APM does not install daemons, services, or scheduled tasks.
- **No telemetry or data collection.** APM collects no usage data, analytics, or diagnostics. Nothing is transmitted to Microsoft or any third party.

## Dependency provenance

APM resolves dependencies directly from git repositories. There is no intermediary registry, proxy, or mirror.

### Exact commit pinning

Every resolved dependency is recorded in `apm.lock` with its full commit SHA:

```yaml
lockfile_version: "1"
dependencies:
  - repo_url: owner/repo
    host: github.com
    resolved_commit: a1b2c3d4e5f6...
    resolved_ref: main
    depth: 1
    deployed_files:
      - .github/skills/example/skill.md
```

The `resolved_commit` field is a full 40-character SHA, not a branch name or tag. Subsequent `apm install` calls resolve to the same commit unless the lock file is explicitly updated.

### No registry

APM does not use a package registry. Dependencies are specified as git repository URLs in `apm.yml`. This eliminates the registry compromise vector entirely — there is no centralized service that can be poisoned to redirect installs.

### Reproducible installs

Given the same `apm.lock`, `apm install` produces identical file output regardless of when or where it runs. The lock file is the single source of truth for dependency state.

## Path security

APM deploys files only to controlled subdirectories within the project root. Three mechanisms enforce this boundary.

### Path traversal prevention

All deploy paths are validated before any file operation. The `validate_deploy_path` check enforces three rules:

1. **No `..` segments.** Any path containing `..` is rejected outright.
2. **Allowed prefixes only.** Paths must start with an allowed prefix (`.github/` or `.claude/`).
3. **Resolution containment.** The fully resolved path must remain within the project root directory.

A path must pass all three checks. Failure on any check prevents the file from being written.

### Symlink handling

Symlinks are never followed during artifact operations:

- **Tree copy operations** skip symlinks entirely — they are excluded from the copy via an ignore filter.
- **MCP configuration files** that are symlinks are rejected with a warning and not parsed.
- **Manifest parsing** requires files to pass both `.is_file()` and `not .is_symlink()` checks.

This prevents symlink-based attacks that could escape allowed directories or cause APM to read or write outside the project root.

### Collision detection

When APM deploys a file, it checks whether a file already exists at the target path:

- If the file is **tracked in the managed files set** (deployed by a previous APM install), it is overwritten.
- If the file is **not tracked** (user-authored or created by another tool), APM skips it and prints a warning.
- The `--force` flag overrides collision detection, allowing APM to overwrite untracked files.

Managed file lookups use pre-normalized paths for O(1) set membership checks.

### Managed files tracking

The lock file records every file deployed by APM in the `deployed_files` list for each dependency. This enables:

- **Clean uninstall.** `apm uninstall` removes exactly the files APM deployed, nothing more.
- **Orphan detection.** Files present on disk but absent from the lock file are flagged.
- **Collision awareness.** The managed set distinguishes APM-deployed files from user-authored files.

## MCP server trust model

APM integrates MCP (Model Context Protocol) server configurations from packages. Trust is explicit and scoped by dependency depth.

### Direct dependencies

MCP servers declared by your direct dependencies (packages listed in your `apm.yml`) are auto-trusted. You explicitly chose to depend on these packages, so their MCP server declarations are accepted.

### Transitive dependencies

MCP servers declared by transitive dependencies (dependencies of your dependencies) are **blocked by default**. APM prints a warning and skips the MCP server entry.

To allow transitive MCP servers, you must either:

- **Re-declare the dependency** in your own `apm.yml`, promoting it to a direct dependency.
- **Pass `--trust-transitive-mcp`** to explicitly opt in to transitive MCP servers for that install.

### Design rationale

Transitive MCP servers can request tool access, file system permissions, or network capabilities from the AI assistant. Blocking them by default ensures that adding a prompt package cannot silently grant MCP access to an unknown transitive dependency.

## Token handling

APM authenticates to git hosts using personal access tokens (PATs) read from environment variables.

### Token resolution

| Purpose | Environment variables (checked in order) |
|---|---|
| GitHub packages | `GITHUB_APM_PAT`, `GITHUB_TOKEN`, `GH_TOKEN` |
| Azure DevOps packages | `ADO_APM_PAT` |

### Security properties

- **Never stored in files.** Tokens are read from the environment at runtime. They are never written to `apm.yml`, `apm.lock`, or any generated file.
- **Never logged.** Token values are not included in console output, error messages, or debug logs.
- **Scoped to their git host.** A GitHub token is only sent to GitHub. An Azure DevOps token is only sent to Azure DevOps. Tokens are never transmitted to any other endpoint.

### Recommended token scope

For GitHub, a fine-grained PAT with read-only `Contents` permission on the repositories you depend on is sufficient. APM only performs git clone and fetch operations.

## Supply chain considerations

### Attack surface comparison

APM's design eliminates several supply chain attack vectors common in traditional package managers:

| Vector | Traditional package manager | APM |
|---|---|---|
| Registry compromise | Attacker poisons central registry | No registry exists |
| Version substitution | Malicious version replaces legitimate one | Lock file pins exact commit SHA |
| Post-install scripts | Arbitrary code runs after install | No code execution |
| Typosquatting | Similar package names on registry | Dependencies are full git URLs |
| Build-time injection | Malicious build steps execute | No build step — files are copied |

### Auditing dependency changes

Because `apm.lock` is a plain YAML file checked into version control, standard git tooling provides a full audit trail:

```bash
# View all dependency changes over time
git log --oneline apm.lock

# See exactly what changed in a specific commit
git diff HEAD~1 -- apm.lock

# Find when a specific dependency was added
git log --all -p -- apm.lock | grep -A5 "owner/repo"
```

### Pinning and updates

- `apm install` respects the existing lock file. Dependencies are not re-resolved unless explicitly requested.
- `apm update` re-resolves dependencies and updates the lock file. The diff is visible in version control before merging.
- There is no automatic update mechanism. Dependency changes require a deliberate action and a code review.

## Frequently asked questions

### Does APM execute any code from packages?

No. APM copies static files (markdown, JSON, YAML) and generates compiled output from templates. It does not execute scripts, evaluate expressions, or run any code from the packages it installs.

### Does APM phone home or collect telemetry?

No. APM makes no network requests beyond git clone/fetch operations to resolve dependencies. There is no telemetry, analytics, or usage reporting of any kind.

### Can a malicious package write files outside the project?

No. All deploy paths are validated against the project root using path traversal checks, prefix allowlists, and resolved path containment. Symlinks are skipped entirely. A package cannot write files outside `.github/` or `.claude/` within the project root.

### Can a transitive dependency inject MCP servers?

Not by default. Transitive MCP server declarations are blocked unless you explicitly opt in with `--trust-transitive-mcp` or re-declare the dependency as a direct dependency.

### How do I audit what APM installed?

The `apm.lock` file records every dependency (with exact commit SHA) and every file deployed. It is a plain YAML file suitable for automated policy checks, diff review, and compliance tooling.

### Is the APM binary signed?

APM is distributed as:

- A PyPI package (`apm-cli`) built and published through GitHub Actions CI/CD.
- Pre-built binaries attached to GitHub Releases under the `microsoft` GitHub organization.

Both distribution channels use GitHub Actions workflows with pinned dependencies and are auditable through the public repository.

### Where is the source code?

APM is open source under the MIT license, hosted on GitHub under the `microsoft` organization. The full source code, build pipeline, and release process are publicly auditable.
