---
title: "Pack & Distribute"
description: "Bundle resolved dependencies for offline distribution, CI pipelines, and air-gapped environments."
sidebar:
  order: 6
---

Bundle your resolved APM dependencies into a portable artifact that can be distributed, cached, and consumed without APM, Python, or network access.

## Why bundles?

Every CI job that runs `apm install` pays the same tax: install APM, authenticate against GitHub, clone N repositories, compile prompts. Multiply that across a matrix of jobs, nightly builds, and staging environments and the cost adds up fast.

A bundle removes all of that. You resolve once, pack the output, and distribute the artifact. Consumers extract it and get the exact files that `apm install` would have produced — no toolchain required.

Common motivations:

- **CI cost reduction** — resolve once, fan out to many jobs
- **Air-gapped environments** — no network access at deploy time
- **Reproducibility** — the bundle is a snapshot of exactly what was resolved
- **Faster onboarding** — new contributors get pre-built context without running install
- **Audit trail** — attach the bundle to a release for traceability

## The pipeline

The pack/distribute workflow fits between install and consumption:

```
apm install  ->  apm pack  ->  upload artifact  ->  download  ->  apm unpack (or tar xzf)
```

The left side (install, pack) runs where APM is available. The right side (download, unpack) runs anywhere — a CI job, a dev container, a colleague's laptop. The bundle is the boundary.

## `apm pack`

Creates a self-contained bundle from installed dependencies. Reads the `deployed_files` manifest in `apm.lock.yaml` as the source of truth — it does not scan the disk.

```bash
# Default: apm format, target auto-detected from apm.yml
apm pack

# Filter by target
apm pack --target vscode          # only .github/ files
apm pack --target claude          # only .claude/ files
apm pack --target all             # both targets

# Bundle format
apm pack --format plugin          # valid plugin directory structure

# Produce a .tar.gz archive
apm pack --archive

# Custom output directory (default: ./build)
apm pack -o ./dist/

# Preview without writing
apm pack --dry-run
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--format` | `apm` | Bundle format (`apm` or `plugin`) |
| `-t, --target` | auto-detect | File filter: `copilot`, `vscode`, `claude`, `cursor`, `all`. `vscode` is an alias for `copilot` |
| `--archive` | off | Produce `.tar.gz` instead of directory |
| `-o, --output` | `./build` | Output directory |
| `--dry-run` | off | List files without writing |

### Target filtering

The target flag controls which deployed files are included based on path prefix:

| Target | Includes |
|--------|----------|
| `copilot` | Paths starting with `.github/` |
| `vscode` | Alias for `copilot` |
| `claude` | Paths starting with `.claude/` |
| `cursor` | Paths starting with `.cursor/` |
| `all` | `.github/`, `.claude/`, and `.cursor/` |

When no target is specified, APM auto-detects from the `target` field in `apm.yml`, falling back to `all`.

## Bundle structure

The bundle mirrors the directory structure that `apm install` produces. It is not an intermediate format — extract it at the project root and the files land exactly where they belong.

Output is written to `./build/<name>-<version>/` by default, where name and version come from `apm.yml`.

### VS Code / Copilot target

```
build/my-project-1.0.0/
  .github/
    prompts/
      design-review.prompt.md
      code-quality.prompt.md
    agents/
      architect.md
    skills/
      security-scan/
        skill.md
  apm.lock.yaml                         # enriched copy (see below)
```

### Claude target

```
build/my-project-1.0.0/
  .claude/
    commands/
      review.md
      debug.md
    skills/
      code-analysis/
        skill.md
  apm.lock.yaml
```

### All targets

```
build/my-project-1.0.0/
  .github/
    prompts/
      ...
    agents/
      ...
  .claude/
    commands/
      ...
  .cursor/
    rules/
      ...
    agents/
      ...
  apm.lock.yaml
```

The bundle is self-describing: its `apm.lock.yaml` lists every file it contains and the dependency graph that produced them.

## Lockfile enrichment

The bundle includes a copy of `apm.lock.yaml` enriched with a `pack:` section. The project's own `apm.lock.yaml` is never modified.

```yaml
pack:
  format: apm
  target: vscode
  packed_at: '2025-07-14T09:30:00+00:00'
lockfile_version: '1'
generated_at: '2025-07-14T09:28:00+00:00'
apm_version: '0.5.0'
dependencies:
  - repo_url: microsoft/apm-sample-package
    host: github.com
    resolved_commit: a1b2c3d4
    resolved_ref: main
    version: 1.0.0
    depth: 1
    package_type: apm
    deployed_files:
      - .github/prompts/design-review.prompt.md
      - .github/agents/architect.md
```

The `pack:` section records:

- **format** — the bundle format used (`apm` or `plugin`)
- **target** — the effective target filter applied
- **packed_at** — UTC timestamp of when the bundle was created

This metadata lets consumers verify what they received and trace it back to a build.

## `apm unpack`

Extracts an APM bundle into a project directory. Accepts both `.tar.gz` archives and unpacked bundle directories.

```bash
# Extract and verify
apm unpack ./build/my-project-1.0.0.tar.gz

# Extract to a specific directory
apm unpack ./build/my-project-1.0.0.tar.gz -o ./

# Skip integrity check
apm unpack --skip-verify ./build/my-project-1.0.0.tar.gz

# Preview without writing
apm unpack ./build/my-project-1.0.0.tar.gz --dry-run
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-o, --output` | `.` (current dir) | Target project directory |
| `--skip-verify` | off | Skip completeness check against lockfile |
| `--dry-run` | off | List files without writing |

### Behavior

- **Additive-only**: `unpack` writes files listed in the bundle's lockfile. It never deletes existing files in the target directory.
- **Overwrite on conflict**: if a file already exists at the target path, the bundle file wins.
- **Verification**: by default, `unpack` checks that every path in the bundle's `deployed_files` manifest exists in the bundle before extracting. Pass `--skip-verify` to skip this check for partial bundles.
- **Lockfile not copied**: the bundle's enriched `apm.lock.yaml` is metadata for verification only — it is not written to the output directory.

## Consumption scenarios

### CI: cross-job artifact sharing

Resolve once in a setup job, fan out to N consumer jobs. No APM installation in downstream jobs.

```yaml
# .github/workflows/ci.yml
jobs:
  setup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: microsoft/apm-action@v1
      - run: apm pack --archive
      - uses: actions/upload-artifact@v4
        with:
          name: apm-bundle
          path: build/*.tar.gz

  test:
    needs: setup
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: apm-bundle
          path: ./bundle
      - run: tar xzf ./bundle/*.tar.gz -C .
      # Prompts and agents are now in place — no APM needed
```

### Agentic workflows

GitHub's agentic workflow runners operate in sandboxed environments with no network access. Pre-pack the bundle and include it as a workflow artifact so the agent has full context from the start.

### Release audit trail

Attach the bundle as a release artifact. Anyone auditing the release can inspect exactly which prompts, agents, and skills shipped with that version.

```bash
apm pack --archive -o ./release-artifacts/
gh release upload v1.2.0 ./release-artifacts/*.tar.gz
```

### Dev Containers and Codespaces

Include a pre-built bundle in the dev container image or restore it during `onCreateCommand`. New contributors get working AI context without running `apm install`.

```json
{
  "onCreateCommand": "tar xzf .devcontainer/apm-bundle.tar.gz -C ."
}
```

### Org-wide distribution

A central platform team maintains the canonical prompt library. Monthly, they run `apm install && apm pack --archive`, publish the bundle to an internal artifact registry, and downstream repos pull it during CI or onboarding.

## `apm-action` integration

The official [apm-action](https://github.com/microsoft/apm-action) supports pack and restore as first-class modes.

### Pack mode

Generate a bundle as part of a GitHub Actions workflow:

```yaml
- uses: microsoft/apm-action@v1
  with:
    pack: true
```

### Restore mode

Consume a bundle without installing APM. The action extracts the archive directly:

```yaml
- uses: microsoft/apm-action@v1
  with:
    bundle: ./path/to/bundle.tar.gz
```

No APM binary, no Python runtime, no network calls. The action handles extraction and verification internally.

## Prerequisites

`apm pack` requires two things:

1. **`apm.lock.yaml`** — the resolved lockfile produced by `apm install`. Pack reads the `deployed_files` manifest from this file to know what to include.
2. **Installed files on disk** — the actual files referenced in `deployed_files` must exist at their expected paths. Pack verifies this and fails with a clear error if files are missing.
3. **No local path dependencies** — `apm pack` rejects packages that depend on local filesystem paths (`./path` or `/absolute/path`). Replace local dependencies with remote references before packing.

The typical sequence is:

```bash
apm install     # resolve dependencies and deploy files
apm pack        # bundle the deployed files
```

Pack reads from the lockfile, not from a disk scan. If a file exists on disk but is not listed in `apm.lock.yaml`, it will not be included. If a file is listed in `apm.lock.yaml` but missing from disk, pack will fail and prompt you to re-run `apm install`.

## Troubleshooting

### "apm.lock.yaml not found"

Pack requires a lockfile. Run `apm install` first to resolve dependencies and generate `apm.lock.yaml`.

### "deployed files are missing on disk"

The lockfile references files that do not exist. This usually means dependencies were installed but the files were deleted. Run `apm install` to restore them.

### "bundle verification failed"

During unpack, verification found files listed in the bundle's lockfile that are missing from the bundle itself. The bundle may have been created from a partial install or corrupted during transfer. Re-pack from a clean install, or pass `--skip-verify` if you know the bundle is intentionally partial.

### Empty bundle

If `apm pack` produces zero files, check that your dependencies have `deployed_files` entries in `apm.lock.yaml`. This can happen if `apm install` completed but no integration files were deployed (e.g., the package has no prompts or agents for the active target).
