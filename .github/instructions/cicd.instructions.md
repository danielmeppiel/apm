---
applyTo: ".github/workflows/**"
description: "CI/CD Pipeline configuration for PyInstaller binary packaging and release workflow"
---

# CI/CD Pipeline Instructions

## Workflow Architecture (Fork-safe)
Three workflows split by trigger and secret requirements:

1. **`ci.yml`** — `pull_request` trigger (all PRs, including forks)
   - Unit tests + build. No secrets needed. Gives fast feedback.
   - Uploads binary artifacts for downstream integration testing.
2. **`ci-integration.yml`** — `workflow_run` trigger (after CI completes, environment-gated)
   - Smoke tests, integration tests, release validation. Requires `integration-tests` environment approval.
   - Security: uses `workflow_run` (not `pull_request_target`) — PR code is NEVER checked out.
   - Downloads binary artifacts from ci.yml, runs test scripts from default branch (main).
   - Reports results back to PR via commit status API.
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
- **PR workflow**: ci.yml (test → build) then ci-integration.yml via workflow_run (approve → smoke-test → integration-tests → release-validation → report-status)
- **Push/Release workflow**: test → build → integration-tests → release-validation → create-release → publish-pypi → update-homebrew
- **Tag Triggers**: Only `v*.*.*` tags trigger full release pipeline
- **Artifact Retention**: 30 days for debugging failed releases
- **Cross-workflow artifacts**: ci-integration.yml downloads artifacts from ci.yml using `run-id` and `github-token`

## Fork PR Security Model
- Fork PRs get unit tests + build via `ci.yml` (no secrets, runs PR code safely)
- `ci-integration.yml` triggers via `workflow_run` after CI completes — NEVER checks out PR code
- Binary artifacts from ci.yml are tested using test scripts from the default branch (main)
- Environment approval gate (`integration-tests`) ensures maintainer reviews PR before integration tests run
- Commit status is reported back to the PR SHA so results appear on the PR

## Key Environment Variables
- `PYTHON_VERSION: '3.12'` - Standardized across all jobs
- `GITHUB_TOKEN` - Fallback token for compatibility (GitHub Actions built-in)

## Performance Considerations
- UPX compression when available (reduces binary size ~50%)
- Python optimization level 2 in PyInstaller
- Aggressive module exclusions (tkinter, matplotlib, etc.)
- Matrix builds across platforms but sequential execution prevents resource conflicts