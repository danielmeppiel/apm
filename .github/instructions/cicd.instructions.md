---
applyTo: ".github/workflows/**"
description: "CI/CD Pipeline configuration for PyInstaller binary packaging and release workflow"
---

# CI/CD Pipeline Instructions

## Workflow Architecture (Fork-safe)
Three workflows split by trigger and secret requirements:

1. **`ci.yml`** — `pull_request` trigger (all PRs, including forks)
   - **Linux + Windows** (ubuntu-24.04, windows-latest). Unit tests in parallel on both platforms + single Linux binary build. No secrets needed.
   - Windows job catches path separator, encoding, and platform-specific issues before merge.
   - Uploads Linux x86_64 binary artifact for downstream integration testing.
2. **`ci-integration.yml`** — `workflow_run` trigger (after CI completes, environment-gated)
   - **Linux-only**. Smoke tests, integration tests, release validation. Requires `integration-tests` environment approval.
   - Security: uses `workflow_run` (not `pull_request_target`) — PR code is NEVER checked out.
   - Downloads Linux binary artifact from ci.yml, runs test scripts from default branch (main).
   - Reports results back to PR via commit status API.
3. **`build-release.yml`** — `push` to main, tags, schedule, `workflow_dispatch`
   - **Linux + Windows** run separate `test → build → integration-tests → release-validation` jobs.
   - **macOS Intel** uses `build-and-validate-macos-intel` (always runs — Intel runners are plentiful with <1 min queue). Builds the binary on every push for early regression feedback; integration + release-validation phases conditional on tag/schedule/dispatch.
   - **macOS ARM** uses `build-and-validate-macos-arm` (tag/schedule/dispatch only — ARM runners are extremely scarce with 2-4h+ queue waits). Only requested when the binary is actually needed for a release.
   - Secrets always available. Full 5-platform binary output (linux x86_64/arm64, darwin x86_64/arm64, windows x86_64).

## Platform Testing Strategy
- **PR time**: Linux + Windows in parallel. Catches logic bugs, dependency issues, path separators, encoding, and Windows-specific problems before merge.
- **Post-merge**: Full 5-platform matrix (linux x86_64/arm64, darwin x86_64/arm64, windows x86_64) catches remaining platform-specific issues on main.
- **Rationale**: Linux + Windows PR coverage catches the two fundamentally different platform families (Unix vs Windows). macOS-specific issues are rare and caught post-merge.

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
- **PR workflow**: ci.yml (test → build, Linux-only) then ci-integration.yml via workflow_run (approve → smoke-test → integration-tests → release-validation → report-status, all Linux-only)
- **Push/Release workflow (Linux + Windows)**: test → build → integration-tests → release-validation → create-release → publish-pypi → update-homebrew
- **Push/Release workflow (macOS Intel)**: test → build-and-validate-macos-intel (build always + conditional integration/release-validation) → create-release
- **Push/Release workflow (macOS ARM)**: test → build-and-validate-macos-arm (tag/schedule/dispatch only; all phases run) → create-release
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
- **PR CI is Linux-only**: Eliminates macOS runner queue delays. Full platform coverage runs post-merge.
- **macOS runner consolidation**: Each macOS arch has a single consolidated job (build + integration + release-validation). Intel (`build-and-validate-macos-intel`) runs on every push since Intel runners are plentiful. ARM (`build-and-validate-macos-arm`) is gated to tag/schedule/dispatch only since ARM runners are extremely scarce (2-4h+ queue waits). This avoids serial re-queuing of runners across multiple jobs.
- **Unit tests skip macOS**: Python unit tests are platform-agnostic; Linux + Windows coverage is sufficient. macOS-specific validation (binary build, integration tests, release validation) still runs via the consolidated job.
- UPX compression when available (reduces binary size ~50%)
- Python optimization level 2 in PyInstaller
- Aggressive module exclusions (tkinter, matplotlib, etc.)