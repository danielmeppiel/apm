# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [0.7.3] - 2025-02-15

### Added

- **SUPPORT.md**: Added Microsoft repo-template support file directing users to GitHub Issues and Discussions for community support

### Changed

- **README Rewording**: Clarified APM as "an open-source, community-driven dependency manager" to set correct expectations under Microsoft GitHub org
- **Microsoft Open Source Compliance**: Updated LICENSE, SECURITY.md, CODE_OF_CONDUCT.md, CONTRIBUTING.md, and added Trademark Notice to README
- **Source Integrity**: Fixed source integrity for all integrators and restructured README

### Fixed

- **Install Script**: Use `grep -o` for single-line JSON extraction in install.sh
- **CI**: Fixed integration test script to handle existing venv from CI workflow

### Security

- Bumped `azure-core` 1.35.1 → 1.38.0, `aiohttp` 3.12.15 → 3.13.3, `pip` 25.2 → 26.0, `urllib3` 2.5.0 → 2.6.3

## [0.7.2] - 2025-01-23

### Added

- **Transitive Dependencies**: Full dependency resolution with `apm.lock` lockfile generation

### Fixed

- **Install Script and `apm update`**: Repaired corrupted header in install.sh. Use awk instead of sed for shell subprocess compatibility. Directed shell output to terminal for password input during update process. 

## [0.7.1] - 2025-01-22

### Fixed

- **Collection Extension Handling**: Prevent double `.collection.yml` extension when user specifies full path
- **SKILL.md Parsing**: Parse SKILL.md directly without requiring apm.yml generation
- **Git Host Errors**: Actionable error messages for unsupported Git hosts

## [0.7.0] - 2025-12-19

### Changed

- **Native Skills Support**: Skills now install to `.github/skills/` as the primary target (per [agentskills.io](https://agentskills.io/) standard)
- **Skills ≠ Agents**: Removed skill → agent transformation; skills and agents are now separate primitives
- **Explicit Package Types**: Added `type` field to apm.yml (`instructions`, `skill`, `hybrid`, `prompts`) for routing control
- **Skill Name Validation**: Validates and normalizes skill names per agentskills.io spec (lowercase, hyphens, 1-64 chars)
- **Claude Compatibility**: Skills also copy to `.claude/skills/` when `.claude/` folder exists

### Added

- Auto-creates `.github/` directory on install if neither `.github/` nor `.claude/` exists

## [0.6.3] - 2025-12-09

### Fixed

- **Selective Package Install**: `apm install <package>` now only installs the specified package instead of all packages from apm.yml. Previously, installing a single package would also install unrelated packages. `apm install` (no args) continues to install all packages from the manifest.

## [0.6.2] - 2025-12-09

### Fixed

- **Claude Skills Integration**: Virtual subdirectory packages (like `ComposioHQ/awesome-claude-skills/mcp-builder`) now correctly trigger skill generation. Previously all virtual packages were skipped, but only virtual files and collections should be skipped—subdirectory packages are complete skill packages.

## [0.6.1] - 2025-12-08

### Added

- **SKILL.md as first-class primitive**: meta-description of what an APM Package does for agents to read
- **Claude Skills Installation**: Install Claude Skills directly as APM Packages
- **Bidirectional Format Support**: 
  - APM packages → SKILL.md (for Claude target)
  - Claude Skills → .agent.md (for VSCode target)
- **Skills Documentation**: New `docs/skills.md` guide

## [0.6.0] - 2025-12-08

### Added

- **Claude Integration**: First-class support for Claude Code and Claude Desktop
  - `CLAUDE.md` generation alongside `AGENTS.md`
  - `.claude/commands/` auto-integration from installed packages
  - `SKILL.md` generation for Claude Skills format
  - Commands get `-apm` suffix (same pattern as VSCode prompts)

- **Target Auto-Detection**: Smart compilation based on project structure
  - `.github/` only → generates `AGENTS.md` + VSCode integration
  - `.claude/` only → generates `CLAUDE.md` + Claude integration  
  - Both folders → generates all formats
  - Neither folder → generates `AGENTS.md` only (universal format)

- **`target` field in apm.yml**: Persistent target configuration
  ```yaml
  target: vscode  # or claude, or all
  ```
  Applies to both `apm compile` and `apm install`

- **`--target` flag**: Override auto-detection
  ```bash
  apm compile --target claude
  apm compile --target vscode
  apm compile --target all
  ```

### Fixed

- Virtual package uninstall sync: `apm uninstall` now correctly removes only the specific virtual package's integrated files (uses `get_unique_key()` for proper path matching)

### Changed

- `apm compile` default: Changed from `--target all` to auto-detect
- README refactored with npm-style zero-friction onboarding
- Documentation reorganized with Claude integration guide

## [0.5.9] - 2025-12-04

### Fixed

- **ADO Package Commands**: `compile`, `prune`, and `deps list` now work correctly with Azure DevOps packages

## [0.5.8] - 2025-12-02

### Fixed

- **ADO Path Structure**: Azure DevOps packages now use correct 3-level paths (`org/project/repo`) throughout install, discovery, update, prune, and uninstall commands
- **Virtual Packages**: ADO collections and individual files install to correct 3-level paths
- **Prune Command**: Fixed undefined variable bug in directory cleanup

## [0.5.7] - 2025-12-01

### Added

- **Azure DevOps Support**: Install packages from Azure DevOps Services and Server
  - New `ADO_APM_PAT` environment variable for ADO authentication (separate from GitHub tokens)
  - Supports `dev.azure.com/org/project/_git/repo` URL format
  - Works alongside GitHub and GitHub Enterprise in mixed-source projects
- **Debug Mode**: Set `APM_DEBUG=1` to see detailed authentication and URL resolution output

### Fixed

- **GitHub Enterprise Private Repos**: Fixed authentication for `git ls-remote` validation on non-github.com hosts
- **Token Selection**: Correct token now used per-platform (GitHub vs ADO) in mixed-source installations

## [0.5.6] - 2025-12-01

### Fixed

- Enterprise GitHub host support: fallback clone now respects `GITHUB_HOST` env var instead of hardcoding github.com
- Version validation crash when YAML parses version as numeric type (e.g., `1.0` vs `"1.0"`)

### Changed

- CI/CD: Updated runner from macos-13 and macos-14 to macos-15 for both x86_64 and ARM64 builds

## [0.5.5] - 2025-11-17

### Added
- **Context Link Resolution**: Automatic markdown link resolution for `.context.md` files across installation and compilation
  - Links in prompts/agents automatically resolve to actual source locations (`apm_modules/` or `.apm/context/`)
  - Works everywhere: IDE, GitHub, all coding agents supporting AGENTS.md
  - No file copying needed—links point directly to source files

## [0.5.4] - 2025-11-17

### Added
- **Agent Integration**: Automatic sync of `.agent.md` files to `.github/agents/` with `-apm` suffix (same pattern as prompt integration)

### Fixed
- `sync_integration` URL normalization bug that caused ALL integrated files to be removed during uninstall instead of only the uninstalled package's files
  - Root cause: Metadata stored full URLs (`https://github.com/owner/repo`) while dependency list used short form (`owner/repo`)
  - Impact: Uninstalling one package would incorrectly remove prompts/agents from ALL other packages
  - Fix: Normalize both URL formats to `owner/repo` before comparison
  - Added comprehensive test coverage for multi-package scenarios
- Uninstall command now correctly removes only `apm_modules/owner/repo/` directory (not `apm_modules/owner/`)

## [0.5.3] - 2025-11-16

### Changed
- **Prompt Naming Pattern**: Migrated from `@` prefix to `-apm` suffix for integrated prompts
- **GitIgnore Pattern**: Updated from `.github/prompts/@*.prompt.md` to `.github/prompts/*-apm.prompt.md`

### Migration Notes
- **Existing Users**: Old `@`-prefixed files will not be automatically removed
- **Action Required**: Manually delete old `@*.prompt.md` files from `.github/prompts/` after upgrading

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