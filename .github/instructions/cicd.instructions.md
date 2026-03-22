---
applyTo: ".github/workflows/**"
description: "CI/CD Pipeline configuration for PyInstaller binary packaging and release workflow"
---

# CI/CD Pipeline Instructions

## Workflow Architecture (Fork-safe)
Four workflows split by trigger and secret requirements:

1. **`ci.yml`** — `pull_request` trigger (all PRs, including forks)
   - **Linux-only** (ubuntu-24.04). Combined `build-and-test` job: unit tests + binary build in a single runner. No secrets needed.
   - Uploads Linux x86_64 binary artifact for downstream integration testing.
2. **`ci-integration.yml`** — `workflow_run` trigger (after CI completes, environment-gated)
   - **Linux-only**. Smoke tests, integration tests, release validation. Requires `integration-tests` environment approval.
   - Security: uses `workflow_run` (not `pull_request_target`) — PR code is NEVER checked out.
   - Downloads Linux binary artifact from ci.yml, runs test scripts from default branch (main).
   - Reports results back to PR via commit status API.
   - Detects CI circular dependency (upstream failure → reports `pending` instead of blocking).
   - Annotates originating PR URL for traceability.
3. **`build-release.yml`** — `push` to main, tags, schedule, `workflow_dispatch`
   - **Linux + Windows** run combined `build-and-test` (unit tests + binary build in one job).
   - **macOS Intel** uses `build-and-validate-macos-intel` (root node, runs own unit tests — no dependency on `build-and-test`). Builds the binary on every push for early regression feedback; integration + release-validation phases conditional on tag/schedule/dispatch.
   - **macOS ARM** uses `build-and-validate-macos-arm` (root node, tag/schedule/dispatch only — ARM runners are extremely scarce with 2-4h+ queue waits). Only requested when the binary is actually needed for a release.
   - Secrets always available. Full 5-platform binary output (linux x86_64/arm64, darwin x86_64/arm64, windows x86_64).
   - Docker image published to ghcr.io on tag releases.
4. **`ci-runtime.yml`** — nightly schedule, manual dispatch, path-filtered push
   - **Linux x86_64 only**. Live inference smoke tests (`apm run`) isolated from release pipeline.
   - Uses `GH_MODELS_PAT` for GitHub Models API access.
   - Failures do not block releases — annotated as warnings.

## Platform Testing Strategy
- **PR time**: Linux-only combined build-and-test in `ci.yml`. Catches logic bugs and dependency issues before merge. Windows + macOS are tested post-merge (platform-specific issues are rare and the full matrix runs on every push to main).
- **Post-merge**: Full 5-platform matrix (linux x86_64/arm64, darwin x86_64/arm64, windows x86_64) catches remaining platform-specific issues on main.
- **Rationale**: ci.yml has always been Linux-only — Windows and macOS are covered by `build-release.yml` on every push to main. This keeps PR feedback fast while still catching platform issues before release.

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

## Inference Testing (Decoupled)
- Live inference tests (`apm run`) are **isolated** in `ci-runtime.yml` — they do NOT gate releases
- `APM_RUN_INFERENCE_TESTS=1` env var enables inference in test scripts; absent = skipped
- `GH_MODELS_PAT` is only used in `ci-runtime.yml` and smoke-test jobs — NOT in integration-tests or release-validation
- Rationale: 8 inference executions × 2% failure rate = 14.9% false-negative per release; APM core UVPs require zero live inference

## Release Flow Dependencies
- **PR workflow**: ci.yml (build-and-test, Linux-only) then ci-integration.yml via workflow_run (approve → smoke-test → integration-tests → release-validation → report-status, all Linux-only)
- **Push/Release workflow (Linux + Windows)**: build-and-test → integration-tests → release-validation → create-release → publish-docker + gh-aw-compat → publish-pypi → update-homebrew
- **Push/Release workflow (macOS Intel)**: build-and-validate-macos-intel (root node: unit tests + build always + conditional integration/release-validation) → create-release
- **Push/Release workflow (macOS ARM)**: build-and-validate-macos-arm (root node, tag/schedule/dispatch only; all phases run) → create-release
- **Tag Triggers**: Only `v*.*.*` tags trigger full release pipeline
- **Artifact Retention**: 30 days for debugging failed releases
- **Cross-workflow artifacts**: ci-integration.yml downloads artifacts from ci.yml using `run-id` and `github-token`

## Docker Image Publishing
- Built from source using `Dockerfile` at repo root (Python 3.12-slim + git + pip install)
- Published to `ghcr.io/microsoft/apm` on all tag releases (public repos only)
- Tags: semver (`0.8.4`), minor (`0.8`), `latest` (stable releases only)
- Runs after `create-release` job, in parallel with `gh-aw-compat`

## Fork PR Security Model
- Fork PRs get unit tests + build via `ci.yml` (no secrets, runs PR code safely)
- `ci-integration.yml` triggers via `workflow_run` after CI completes — NEVER checks out PR code
- Binary artifacts from ci.yml are tested using test scripts from the default branch (main)
- Environment approval gate (`integration-tests`) ensures maintainer reviews PR before integration tests run
- Commit status is reported back to the PR SHA so results appear on the PR

## Key Environment Variables
- `PYTHON_VERSION: '3.12'` - Standardized across all jobs
- `GITHUB_TOKEN` - Fallback token for compatibility (GitHub Actions built-in)
- `APM_RUN_INFERENCE_TESTS` - When `1`, enables live inference tests in validation scripts

## Performance Considerations
- **Combined build-and-test**: Eliminates ~1.5m runner re-provisioning overhead by running unit tests and binary build in the same job.
- **macOS as root nodes**: macOS consolidated jobs run their own unit tests and start immediately — no dependency on Linux/Windows test completion.
- **Native uv caching**: `setup-uv` action with `enable-cache: true` replaces manual `actions/cache@v3` blocks.
- **No setup-node in test/build**: Node.js is only needed in integration-tests and release-validation (for `apm runtime setup copilot` → npm install).
- **macOS runner consolidation**: Each macOS arch has a single consolidated job (build + integration + release-validation). Intel (`build-and-validate-macos-intel`) runs on every push since Intel runners are plentiful. ARM (`build-and-validate-macos-arm`) is gated to tag/schedule/dispatch only since ARM runners are extremely scarce (2-4h+ queue waits). This avoids serial re-queuing of runners across multiple jobs.
- **Unit tests skip macOS**: Python unit tests are platform-agnostic; Linux + Windows coverage is sufficient. macOS-specific validation (binary build, integration tests, release validation) still runs via the consolidated job.
- UPX compression when available (reduces binary size ~50%)
- Python optimization level 2 in PyInstaller
- Aggressive module exclusions (tkinter, matplotlib, etc.)