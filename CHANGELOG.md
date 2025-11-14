# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.2] - 2025-11-14

### Added
- **Prompt Integration with GitHub** - Automatically sync downloaded prompts to `.github/prompts/` for GitHub Copilot

### Changed
- Improved installer UX and console output

## [0.5.1] - 2025-11-09

### Added
- Package FQDN support - install from any Git host using fully qualified domain names (thanks @richgo for PR #25)

### Fixed
- **Security**: CWE-20 URL validation vulnerability - proper hostname validation using `urllib.parse` prevents malicious URL bypass attacks
- Package validation HTTPS URL construction for git ls-remote checks
- Virtual package orphan detection in `apm deps list` command

### Changed
- GitHub Enterprise support via `GITHUB_HOST` environment variable (thanks @richgo for PR #25)
- Build pipeline updates for macOS compatibility

## [0.5.0] - 2025-10-30

### Added - Virtual Packages
- **Virtual Package Support**: Install individual files directly from any repository without requiring full APM package structure
  - Individual file packages: `apm install owner/repo/path/to/file.prompt.md`
- **Collection Support**: Install curated collections of primitives from [Awesome Copilot](https://github.com/github/awesome-copilot): `apm install github/awesome-copilot/collections/collection-name`
  - Collection manifest parser for `.collection.yml` format
  - Batch download of collection items into organized `.apm/` structure
  - Integration with github/awesome-copilot collections

### Added - Runnable Prompts
- **Auto-Discovery of Prompts**: Run installed prompts without manual script configuration
  - `apm run <prompt-name>` automatically discovers and executes prompts without having to wire a script in `apm.yml`
  - Search priority: local root → .apm/prompts → .github/prompts → dependencies
  - Qualified path support: `apm run owner/repo/prompt-name` for disambiguation
  - Collision detection with helpful error messages when multiple prompts found
  - Explicit scripts in apm.yml always take precedence over auto-discovery
- **Automatic Runtime Detection**: Detects installed runtime (copilot > codex) and generates proper commands
- **Zero-Configuration Execution**: Install and run prompts immediately without apm.yml scripts section

### Changed
- Enhanced dependency resolution to support virtual package unique keys
- Improved GitHub downloader with virtual file and collection package support
- Extended `DependencyReference.parse()` to detect and validate virtual packages (3+ path segments)
- Script runner now falls back to prompt discovery when script not found in apm.yml

### Developer Experience
- Streamlined workflow: `apm install <file>` → `apm run <name>` works immediately
- No manual script configuration needed for simple use cases
- Power users retain full control via explicit scripts in apm.yml
- Better error messages for ambiguous prompt names with disambiguation guidance

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