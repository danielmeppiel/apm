---
title: "Lock File Specification"
description: "The apm.lock.yaml format — how APM pins dependencies to exact versions for reproducible installs."
sidebar:
  order: 3
---

<dl>
<dt>Version</dt><dd>0.1 (Working Draft)</dd>
<dt>Date</dt><dd>2026-03-09</dd>
<dt>Editors</dt><dd>Daniel Meppiel (Microsoft)</dd>
<dt>Repository</dt><dd>https://github.com/microsoft/apm</dd>
<dt>Format</dt><dd>YAML 1.2</dd>
</dl>

## Status of This Document

This is a **Working Draft**. The lock file format is stable at version `"1"` and
breaking changes will be gated behind a `lockfile_version` bump.

## Abstract

`apm.lock.yaml` records the exact resolved state of every dependency in an APM
project. It is the receipt of what was installed — commit SHAs, source URLs,
and every file deployed into the workspace. Its role is analogous to
`package-lock.json` (npm) or `.terraform.lock.hcl` (Terraform): given the same
lock file, APM MUST reproduce the same file tree.

---

## 1. Conformance

The key words "MUST", "MUST NOT", "SHOULD", "SHOULD NOT", and "MAY" in this
document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

## 2. Purpose

The lock file serves four goals:

1. **Reproducibility** — the same lock file yields the same deployed files on
   every machine, every time.
2. **Provenance** — every dependency is traceable to an exact source commit.
3. **Completeness** — `deployed_files` lists every file APM placed in the
   project, enabling precise removal.
4. **Auditability** — `git log apm.lock.yaml` provides a full history of dependency
   changes across the lifetime of the project.

## 3. Lifecycle

`apm.lock.yaml` is created and updated at well-defined points:

| Event | Effect on `apm.lock.yaml` |
|-------|----------------------|
| `apm install` (first run) | Created. All dependencies resolved, commits pinned, files recorded. |
| `apm install` (subsequent) | Read. Locked commits reused. New dependencies appended. |
| `apm install --update` | Re-resolved. All refs re-resolved to latest matching commits. |
| `apm deps update` | Re-resolved. Refreshes versions for specified or all dependencies. |
| `apm pack` | Enriched. A `pack:` section is prepended to the bundled copy (see [section 6](#6-pack-enrichment)). |
| `apm uninstall` | Updated. Removed dependency entries and their `deployed_files` references. |

The lock file SHOULD be committed to version control. It MUST NOT be
manually edited — APM is the sole writer.

## 4. Document Structure

A conforming lock file MUST be a YAML 1.2 document with the following
top-level structure:

```yaml
lockfile_version: "1"
generated_at: "2026-03-09T14:00:00Z"
apm_version: "0.7.7"

dependencies:
  - repo_url: https://github.com/acme-corp/security-baseline
    resolved_commit: a1b2c3d4e5f6789012345678901234567890abcd
    resolved_ref: v2.1.0
    version: "2.1.0"
    depth: 1
    package_type: apm_package
    deployed_files:
      - .github/instructions/security.instructions.md
      - .github/agents/security-auditor.agent.md

  - repo_url: https://github.com/acme-corp/common-prompts
    resolved_commit: f6e5d4c3b2a1098765432109876543210fedcba9
    resolved_ref: main
    depth: 2
    resolved_by: https://github.com/acme-corp/security-baseline
    package_type: apm_package
    deployed_files:
      - .github/instructions/common-guidelines.instructions.md
```

### 4.1 Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `lockfile_version` | string | MUST | Lock file format version. Currently `"1"`. |
| `generated_at` | string (ISO 8601) | MUST | UTC timestamp of when the lock file was last written. |
| `apm_version` | string | MUST | Version of APM that generated this lock file. |
| `dependencies` | array | MUST | Ordered list of resolved dependencies (see [section 4.2](#42-dependency-entries)). |
| `mcp_servers` | array | MAY | List of MCP server identifiers registered by installed packages. |
| `mcp_configs` | mapping | MAY | Mapping of MCP server name to its manifest configuration dict. Used for diff-aware installation — when config in `apm.yml` changes, `apm install` detects the drift and re-applies without `--force`. |

### 4.2 Dependency Entries

The `dependencies` list MUST be sorted by `depth` (ascending), then by
`repo_url` (lexicographic). Each entry is a YAML mapping with the following
fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `repo_url` | string | MUST | Source repository URL. |
| `host` | string | MAY | Git host identifier (e.g., `github.com`). Omitted when inferrable from `repo_url`. |
| `resolved_commit` | string | MUST | Full 40-character commit SHA that was checked out. |
| `resolved_ref` | string | MUST | Git ref (tag, branch, SHA) that resolved to `resolved_commit`. |
| `version` | string | MAY | Semantic version of the package, if declared in its manifest. |
| `virtual_path` | string | MAY | Sub-path within the repository for virtual (monorepo) packages. |
| `is_virtual` | boolean | MAY | `true` if the package is a virtual sub-package. Omitted when `false`. |
| `depth` | integer | MUST | Dependency depth. `1` = direct dependency, `2`+ = transitive. |
| `resolved_by` | string | MAY | `repo_url` of the parent that introduced this transitive dependency. Present only when `depth >= 2`. |
| `package_type` | string | MUST | Package type: `apm_package`, `plugin`, `virtual`, or other registered types. |
| `deployed_files` | array of strings | MUST | Every file path APM deployed for this dependency, relative to project root. |

Fields with empty or default values (empty strings, `false` booleans, empty
lists) SHOULD be omitted from the serialized output to keep the file concise.

### 4.3 Unique Key

Each dependency is uniquely identified by its `repo_url`, or by the
combination of `repo_url` and `virtual_path` for virtual packages. A
conforming lock file MUST NOT contain duplicate entries for the same key.

## 5. Path Conventions

All paths in `deployed_files` MUST use forward slashes (POSIX format),
regardless of the host operating system. Paths are relative to the project
root directory.

```yaml
# Correct
deployed_files:
  - .github/instructions/security.instructions.md
  - .github/agents/code-review.agent.md

# Incorrect — backslashes are not permitted
deployed_files:
  - .github\instructions\security.instructions.md
```

This convention ensures lock files are portable across operating systems and
produce consistent diffs in version control.

## 6. Pack Enrichment

When `apm pack` creates a bundle, it prepends a `pack:` section to the lock
file copy included in the bundle. This section is informational and is not
written back to the project's `apm.lock.yaml`.

```yaml
pack:
  format: apm
  target: vscode
  packed_at: "2026-03-09T14:30:00Z"

lockfile_version: "1"
generated_at: "2026-03-09T14:00:00Z"
# ... rest of lock file
```

### 6.1 Pack Fields

| Field | Type | Description |
|-------|------|-------------|
| `pack.format` | string | Bundle format: `"apm"` or `"plugin"`. |
| `pack.target` | string | Target environment: `"vscode"`, `"claude"`, or `"all"`. |
| `pack.packed_at` | string (ISO 8601) | UTC timestamp of when the bundle was created. |

The original lock file is not mutated. The enriched copy exists only inside the
packed archive.

## 7. Resolver Behaviour

The dependency resolver interacts with the lock file as follows:

1. **First install** — resolve all refs to commits, write `apm.lock.yaml`.
2. **Subsequent installs** — read `apm.lock.yaml`, reuse locked commits. Only
   newly added dependencies trigger resolution.
3. **Update** (`--update` flag or `apm deps update`) — re-resolve all refs,
   overwrite the lock file with fresh commits.

When a locked commit is no longer reachable (force-pushed branch, deleted tag),
APM MUST report an error and refuse to install until the lock file is updated.

## 8. Migration

The lock file reader supports one historical migration:

- **`deployed_skills`** — renamed to `deployed_files`. If a lock file contains
  the legacy key, it is silently migrated on read. New lock files MUST use
  `deployed_files`.

## 9. Auditing Patterns

Because `apm.lock.yaml` is committed to version control, standard Git operations
provide a complete audit trail:

```bash
# Full history of dependency changes
git log --oneline apm.lock.yaml

# What changed in the last commit
git diff HEAD~1 -- apm.lock.yaml

# State of dependencies at a specific release
git show v4.2.1:apm.lock.yaml

# Who last modified the lock file
git log -1 --format='%an <%ae> %ai' -- apm.lock.yaml
```

In CI pipelines, `apm audit --ci` verifies the lock file is in sync with the
manifest and that all deployed files are present.

## 10. Example: Complete Lock File

```yaml
lockfile_version: "1"
generated_at: "2026-03-09T14:00:00Z"
apm_version: "0.7.7"

dependencies:
  - repo_url: https://github.com/acme-corp/security-baseline
    resolved_commit: a1b2c3d4e5f6789012345678901234567890abcd
    resolved_ref: v2.1.0
    version: "2.1.0"
    depth: 1
    package_type: apm_package
    deployed_files:
      - .github/instructions/security.instructions.md
      - .github/agents/security-auditor.agent.md
      - .github/agents/threat-model.agent.md

  - repo_url: https://github.com/acme-corp/common-prompts
    resolved_commit: f6e5d4c3b2a1098765432109876543210fedcba9
    resolved_ref: main
    depth: 2
    resolved_by: https://github.com/acme-corp/security-baseline
    package_type: apm_package
    deployed_files:
      - .github/instructions/common-guidelines.instructions.md

  - repo_url: https://github.com/example-org/monorepo-tools
    host: github.com
    resolved_commit: 0123456789abcdef0123456789abcdef01234567
    resolved_ref: v1.0.0
    version: "1.0.0"
    virtual_path: packages/linter-config
    is_virtual: true
    depth: 1
    package_type: virtual
    deployed_files:
      - .github/instructions/linter.instructions.md

mcp_servers:
  - security-scanner

mcp_configs:
  security-scanner:
    name: security-scanner
    transport: stdio
```

---

## Appendix A: Revision History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-03-09 | Initial working draft. |
