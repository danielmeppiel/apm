---
applyTo: ".github/workflows/**"
description: "CI/CD Pipeline configuration for PyInstaller binary packaging and release workflow"
---

# CI/CD Pipeline Instructions

## Workflow Architecture (Fork-safe)
Three workflows split by trigger and secret requirements:

1. **`ci.yml`** — `pull_request` trigger (all PRs, including forks)
   - Unit tests + build. No secrets needed. Gives fast feedback.
2. **`ci-integration.yml`** — `pull_request_target` trigger (environment-gated)
   - Smoke tests, integration tests, release validation. Requires `integration-tests` environment approval.
   - Security: workflow code comes from main, only source checkout uses PR HEAD sha.
3. **`build-release.yml`** — `push` to main, tags, schedule, `workflow_dispatch`
   - Full pipeline for post-merge / release. Secrets always available.

## PyInstaller Binary Packaging
- **CRITICAL**: Uses `--onedir` mode (NOT `--onefile`) for faster CLI startup performance
- **Binary Structure**: Creates `dist/{binary_name}/apm` (nested directory containing executable + dependencies)
- **Platform Naming**: `apm-{platform}-{arch}` (e.g., `apm-darwin-arm64`, `apm-linux-x86_64`)
- **Spec File**: `build/apm.spec` handles data bundling, hidden imports, and UPX compression

## Artifact Flow Quirks
- **Upload**: Artifacts include both binary directory + test scripts for isolation testing
- **Download**: GitHub Actions creates nested structure: `{artifact_name}/dist/{binary_name}/apm`
- **Release Prep**: Extract binary from nested path using `tar -czf "${binary}.tar.gz" -C "${artifact_dir}/dist" "${binary}"`

## Critical Testing Phases
1. **Integration Tests**: Full source code access for comprehensive testing
2. **Release Validation**: ISOLATION testing - no source checkout, validates exact shipped binary experience
3. **Path Resolution**: Use symlinks and PATH manipulation for isolated binary testing

## Release Flow Dependencies
- **PR workflow**: ci.yml (test → build) + ci-integration.yml (approve → smoke-test + build → integration-tests → release-validation)
- **Push/Release workflow**: test → build → integration-tests → release-validation → create-release → publish-pypi → update-homebrew
- **Tag Triggers**: Only `v*.*.*` tags trigger full release pipeline
- **Artifact Retention**: 30 days for debugging failed releases

## Fork PR Security Model
- Fork PRs get unit tests + build via `ci.yml` (no secrets)
- Integration tests require maintainer approval via `integration-tests` environment
- `pull_request_target` ensures workflow code comes from main (not the fork)
- Only source code is checked out from PR HEAD after approval

## Key Environment Variables
- `PYTHON_VERSION: '3.12'` - Standardized across all jobs
- `GITHUB_TOKEN` - Fallback token for compatibility (GitHub Actions built-in)

## Performance Considerations
- UPX compression when available (reduces binary size ~50%)
- Python optimization level 2 in PyInstaller
- Aggressive module exclusions (tkinter, matplotlib, etc.)
- Matrix builds across platforms but sequential execution prevents resource conflicts