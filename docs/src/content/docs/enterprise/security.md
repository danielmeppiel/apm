---
title: "Security Model"
description: "How APM handles supply chain security for AI prompts — content scanning, dependency provenance, path safety, and MCP trust."
sidebar:
  order: 3
---

This page documents APM's security posture for enterprise security reviews, compliance audits, and supply chain assessments.

## The prompt supply chain is different

Traditional package managers install code that sits inert until a developer or CI pipeline explicitly executes it. Between `npm install` and `npm start`, there is a gap — time for `npm audit`, code review, and policy checks.

**Prompt files have no such gap.** The moment a `.md` file lands in `.github/prompts/` or `.claude/agents/`, any IDE agent watching the filesystem — Copilot, Cursor, Claude Code — may already be ingesting it. There is no "execution step." File presence IS execution.

This changes the security model fundamentally. A post-install scan that warns about a bad file is a smoke detector — useful, but the fire is already burning. APM treats prompt deployment as a **pre-deployment gate**: scan first, deploy only if clean.

## Content scanning

### The threat

Researchers have found hidden Unicode characters embedded in popular shared rules files. Tag characters (U+E0001–E007F) map 1:1 to invisible ASCII. Bidirectional overrides can reorder visible text. Zero-width joiners create invisible gaps. LLMs tokenize all of these individually, meaning models process instructions that developers cannot see on screen.

### What APM detects

| Severity | Characters | Risk |
|----------|-----------|------|
| Critical | Tag characters (U+E0001–E007F), bidi overrides (U+202A–E, U+2066–9) | Hidden instruction embedding. Zero legitimate use in prompt files. |
| Warning | Zero-width spaces/joiners (U+200B–D), mid-file BOM (U+FEFF) | Common copy-paste debris, but can hide content. |
| Info | Non-breaking spaces (U+00A0), unusual whitespace (U+2000–200A) | Mostly harmless, flagged for awareness. |

### Pre-deployment gate

During `apm install`, source files in `apm_modules/` are scanned **before** any integrator copies them to target directories:

```
download → scan source → block or deploy → report
```

- **Critical findings block deployment.** The package is downloaded and cached so you can inspect it (`apm_modules/owner/package/`), but nothing reaches agent-readable directories.
- **Warnings are non-blocking.** Zero-width characters are flagged in the diagnostics summary. Files are deployed normally.
- **`--force` overrides the block.** Consistent with existing collision semantics — an explicit "I know what I'm doing."
- **Multi-package installs continue.** A blocked package doesn't stop other packages from installing.

### On-demand scanning

`apm audit` scans deployed files or any arbitrary file, independent of the install flow:

```bash
apm audit                        # Scan all installed packages
apm audit --file .cursorrules    # Scan any file
apm audit --strip                # Remove non-critical characters
```

The `--file` flag is useful for inspecting files obtained outside APM — downloaded rules files, copy-pasted instructions, or files from pull requests.

See [Content scanning with `apm audit`](../governance/#content-scanning-with-apm-audit) for usage details and exit codes.

### Limitations

Content scanning detects hidden Unicode characters. It does not detect:

- Plain-text prompt injection (visible but malicious instructions)
- Homoglyph substitution (visually similar characters from different scripts)
- Semantic manipulation (subtly misleading but syntactically normal text)
- Binary payload embedding

`--strip` removes non-critical characters from deployed copies. It does not modify the source package — the next `apm install` restores them. For persistent remediation, fix the upstream package or pin to a clean commit.

## What APM does

APM is a build-time dependency manager for AI prompts and configuration. It performs four operations:

1. **Resolves git repositories** — clones or sparse-checks-out packages from GitHub or Azure DevOps.
2. **Deploys static files** — copies markdown, JSON, and YAML files into project directories (`.github/`, `.claude/`, `.cursor/`, `.opencode/`).
3. **Generates compiled output** — produces `AGENTS.md`, `CLAUDE.md`, and similar files from templates and prompts.
4. **Records a lock file** — writes `apm.lock.yaml` with exact commit SHAs for every resolved dependency.

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

Every resolved dependency is recorded in `apm.lock.yaml` with its full commit SHA:

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

APM does not use a package registry. Dependencies are specified as git repository URLs in `apm.yaml`. This eliminates the registry compromise vector entirely — there is no centralized service that can be poisoned to redirect installs.

### Reproducible installs

Given the same `apm.lock.yaml`, `apm install` produces identical file output regardless of when or where it runs. The lock file is the single source of truth for dependency state.

## Path security

APM deploys files only to controlled subdirectories within the project root. Three mechanisms enforce this boundary.

### Path traversal prevention

All deploy paths are validated before any file operation. The `validate_deploy_path` check enforces three rules:

1. **No `..` segments.** Any path containing `..` is rejected outright.
2. **Allowed prefixes only.** Paths must start with an allowed prefix (`.github/`, `.claude/`, `.cursor/`, or `.opencode/`).
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

MCP servers declared by your direct dependencies (packages listed in your `apm.yaml`) are auto-trusted. You explicitly chose to depend on these packages, so their MCP server declarations are accepted.

### Transitive dependencies

MCP servers declared by transitive dependencies (dependencies of your dependencies) are **blocked by default**. APM prints a warning and skips the MCP server entry.

To allow transitive MCP servers, you must either:

- **Re-declare the dependency** in your own `apm.yaml`, promoting it to a direct dependency.
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

- **Never stored in files.** Tokens are read from the environment at runtime. They are never written to `apm.yaml`, `apm.lock.yaml`, or any generated file.
- **Never logged.** Token values are not included in console output, error messages, or debug logs.
- **Scoped to their git host.** A GitHub token is only sent to GitHub. An Azure DevOps token is only sent to Azure DevOps. Tokens are never transmitted to any other endpoint.

### Recommended token scope

For GitHub, a fine-grained PAT with read-only `Contents` permission on the repositories you depend on is sufficient. APM only performs git clone and fetch operations.

## Attack surface comparison

APM's design eliminates several supply chain attack vectors common in traditional package managers:

| Vector | Traditional package manager | APM |
|---|---|---|
| Registry compromise | Attacker poisons central registry | No registry exists |
| Version substitution | Malicious version replaces legitimate one | Lock file pins exact commit SHA |
| Post-install scripts | Arbitrary code runs after install | No code execution |
| Typosquatting | Similar package names on registry | Dependencies are full git URLs |
| Build-time injection | Malicious build steps execute | No build step — files are copied |
| Hidden content injection | Not applicable (binary packages) | Pre-deploy scan blocks critical hidden Unicode; `apm audit` for on-demand checks |

## Frequently asked questions

### Does APM execute any code from packages?

No. APM copies static files (markdown, JSON, YAML) and generates compiled output from templates. It does not execute scripts, evaluate expressions, or run any code from the packages it installs.

### Does APM phone home or collect telemetry?

No. APM makes no network requests beyond git clone/fetch operations to resolve dependencies. There is no telemetry, analytics, or usage reporting of any kind.

### Can a malicious package write files outside the project?

No. All deploy paths are validated against the project root using path traversal checks, prefix allowlists, and resolved path containment. Symlinks are skipped entirely. A package cannot write files outside `.github/`, `.claude/`, `.cursor/`, or `.opencode/` within the project root.

### Can a transitive dependency inject MCP servers?

Not by default. Transitive MCP server declarations are blocked unless you explicitly opt in with `--trust-transitive-mcp` or re-declare the dependency as a direct dependency.

### Can a package embed hidden instructions?

Not without detection. APM scans all package source files before deployment. Critical hidden characters (tag characters, bidi overrides) block deployment. `apm audit` provides on-demand scanning for any file, including those obtained outside APM.

### How do I audit what APM installed?

The `apm.lock.yaml` file records every dependency (with exact commit SHA) and every file deployed. It is a plain YAML file suitable for automated policy checks, diff review, and compliance tooling. See [Governance & Compliance](../governance/) for audit workflows.

### Is the APM binary signed?

APM is distributed as:

- A PyPI package (`apm-cli`) built and published through GitHub Actions CI/CD.
- Pre-built binaries attached to GitHub Releases under the `microsoft` GitHub organization.

Both distribution channels use GitHub Actions workflows with pinned dependencies and are auditable through the public repository.

### Where is the source code?

APM is open source under the MIT license, hosted on GitHub under the `microsoft` organization. The full source code, build pipeline, and release process are publicly auditable.
