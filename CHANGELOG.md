# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.3] - 2025-10-29

### Added
- Auto-bootstrap `apm.yml` when running `apm install <package>` without existing config
- GitHub Enterprise Server and Data Residency Cloud support via `GITHUB_HOST` environment variable
- ARM64 Linux support

### Changed
- Refactored `apm init` to initialize projects minimally without templated prompts and instructions
- Improved next steps formatting in project initialization output

### Fixed
- GitHub token fallback handling for Codex runtime setup
- Environment variable passing to subprocess in smoke tests and runtime setup

## [0.4.2] - 2025-09-25

- Copilot CLI Support

## [0.4.1] - 2025-09-18

### Fixed
- Fix prompt file resolution for dependencies in org/repo directory structure
- APM dependency prompt files now correctly resolve from `apm_modules/org/repo/` paths
- `apm run` commands can now find and execute prompt files from installed dependencies
- Updated unit tests to match org/repo directory structure for dependency resolution

## [0.4.0] - 2025-09-18

- Context Packaging
- Context Dependencies
- Context Compilation
- GitHub MCP Registry integration
- Codex CLI Support