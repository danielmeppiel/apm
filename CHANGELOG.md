# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]


## [0.8.1] - 2026-03-17

### Added

- Audit hardening — `apm unpack` content scanning, SARIF/JSON/Markdown `--format`/`--output` for CI capture, `SecurityGate` policy engine, non-zero exits on critical findings (#330)
- Install output now shows resolved git ref alongside package name (e.g. `✓ owner/repo#main (a1b2c3d4)`) (#340)
- `${input:...}` variable resolution for self-defined MCP server headers and env values — by @sergio-sisternes-epam (#344)

### Changed

- Pinning hint moved from inline tip to `── Diagnostics ──` section with aggregated count (#347)
- Install ref display uses `#` separator instead of `@` for consistency with dependency syntax (#340)
- Shorthand `@alias` syntax removed from dependency strings — use the dict format `alias:` field instead (#340)

### Fixed

- File-level downloads from private repos now use OS credential helpers (macOS Keychain, `gh auth login`, Windows Credential Manager) (#332)
- Lockfile now preserves the host for GitHub Enterprise custom domains so subsequent `apm install` clones from the correct server (#338)
- MCP registry validation no longer fails on transient network errors (#337)

## [0.8.0] - 2026-03-16

### Added

- Native Cursor IDE integration — `apm install` deploys instructions→rules (`.mdc`), agents, skills, hooks (`hooks.json`), and MCP (`mcp.json`) to `.cursor/` (#301)
- Native OpenCode integration — `apm install` deploys agents, commands, skills, and MCP (`opencode.json`) to `.opencode/` — inspired by @timvw (#306)
- Content security scanning with `apm audit` command — `--file`, `--strip`, `--dry-run`; install-time pre-deployment gate blocks critical hidden Unicode characters (#313)
- Detect variation selectors (Glassworm attack vector), invisible math operators, bidi marks, annotation markers, and deprecated formatting in content scanning — by @raye-deng (#321, #320)
- Context-aware ZWJ detection — emoji joiners preserved by `--strip`; `--strip --dry-run` preview mode (#321)
- `TargetProfile` data layer for scalable multi-target architecture (#301)
- `CursorClientAdapter` for MCP server management in `.cursor/mcp.json` (#301)
- `OpenCodeClientAdapter` for MCP server management in `opencode.json` (#306)
- Private packages guide and enhanced authentication documentation (#314)

### Changed

- Updated docs landing page to include Cursor and OpenCode (#310)
- Updated all doc pages to reflect full Cursor native support (#304)
- Added OpenCode to README headline and compile description (#308)

### Fixed

- GitHub API rate-limit 403 responses no longer misdiagnosed as authentication failures — unauthenticated users now see actionable "rate limit exceeded" guidance instead of misleading "private repository" errors

## [0.7.9] - 2026-03-13

### Added

- Local filesystem path dependencies — install packages from relative/absolute paths with `apm install ./my-package` (#270)
- Windows native support (Phase 1 & 2) — cross-platform runtime management, PowerShell helpers, and CI parity — by @sergio-sisternes-epam (#227)
- CLI logging UX agent skill for consistent CLI output conventions (#289)

### Fixed

- Resolve `UnboundLocalError` in `apm prune` crashing all prune operations (#283)
- Restore CWD before `TemporaryDirectory` cleanup on Windows — by @sergio-sisternes-epam (#281)
- Fix Codex runtime download 404 on Windows — asset naming uses `.exe.tar.gz` — by @sergio-sisternes-epam (#287)
- Fix `UnicodeEncodeError` on Windows cp1252 consoles via UTF-8 codepage configuration — by @sergio-sisternes-epam (#287)
- Fix `WinError 2` when resolving `.cmd`/`.ps1` shell wrappers via `shutil.which()` — by @sergio-sisternes-epam (#287)
- Fix `GIT_CONFIG_GLOBAL=NUL` failure on some Windows git versions — by @sergio-sisternes-epam (#287)
- Improve sub-skill overwrite UX with content skip and collision protection (#289)

### Changed

- Lockfile renamed from `apm.lock` to `apm.lock.yaml` for IDE syntax highlighting; existing `apm.lock` files are automatically migrated on the next `apm install` (#280)
- Add Windows as first-class install option across documentation site (#278)
- Clarify that `.github/` deployed files should be committed (#290)

## [0.7.8] - 2026-03-13

### Added

- Diff-aware `apm install` — manifest as source of truth: removed packages, ref/version changes, and MCP config drift in `apm.yml` all self-correct on the next `apm install` without `--update` or `--force`; introduces `drift.py` with pure helper functions (#260)
- `DiagnosticCollector` for structured install diagnostics (#267)
- Detailed file-level logging to `apm unpack` command (#252)
- Astro Starlight documentation site with narrative redesign (#243)

### Fixed

- Resolve WinError 32 during sparse-checkout fallback on Windows — by @JanDeDobbeleer (#235)
- CLI consistency: docs alignment, emoji removal, `show_default` flags (#266)

### Changed

- Minimum Python version bumped to 3.10; Black upgraded to 26.3.1 (#269)
- Refactor `cli.py` and `apm_package.py` into focused modules — by @sergio-sisternes-epam (#224)
- Revamp README as storefront for documentation site (#251, #256, #258)
- Remove duplicated content from CLI reference page (#261)
- Bump devalue 5.6.3 → 5.6.4 in docs (#263)
- Primitives models coverage 78% → 100%; add discovery and parser coverage tests (#240, #254)

## [0.7.7] - 2026-03-10

### Added

- `copilot` as the primary user-facing target name for GitHub Copilot / Cursor / Codex / Gemini output format; `vscode` and `agents` remain as aliases (#228)

### Changed

- Consolidate pack/unpack documentation into cli-reference, rename Key Commands section

## [0.7.6] - 2026-03-10

### Added

- `apm pack` and `apm unpack` commands for portable bundle creation and extraction with target filtering, archive support, and verification (#218)
- Plugin MCP Server installation — extract, convert, and deploy MCP servers defined in plugin packages (#217)

### Fixed

- Plugin agents not deployed due to directory nesting in custom agent paths (#214)
- Skip already-configured self-defined MCP servers on re-install (#191)
- CLI consistency: remove emojis from help strings, fix `apm config` bare invocation, update descriptions (#212)

### Changed

- Extract `MCPIntegrator` from `cli.py` — move MCP lifecycle orchestration (~760 lines) into standalone module with hardened error handling (#215)

## [0.7.5] - 2026-03-09

### Added

- Plugin management system with CLI commands for installing and managing plugins from marketplaces (#83)
- Generic git URL support for GitLab, Bitbucket, and any self-hosted git provider (#150)
- InstructionIntegrator for `apm install` — deploy `.instructions.md` files alongside existing integrators (#162)
- Transitive MCP dependency propagation (#123)
- MCP dependency config overlays, transitive trust flag, and related bug fixes (#166)
- Display build commit SHA in CLI version output (#176)
- Documentation: apm.yml manifest schema reference for integrators (#186)

### Fixed

- Handle multiple brace groups in `applyTo` glob patterns (#155)
- Replace substring matching with path-component matching in directory exclusions (#159)
- Handle commit SHA refs in subdirectory package clones (#178)
- Infer `registry_name` when MCP registry API returns empty values (#181)
- Resolve `set()` shadowing and sparse checkout ref issues (#184)
- CLI consistency — align help text with docs (#188)
- `--update` flag now bypasses lockfile SHA to fetch latest content (#192)
- Clean stale MCP servers on install/update/uninstall and prevent `.claude` folder creation (#201)
- Harden plugin security, validation, tests, and docs (#208)
- Use `CREATE_PR_PAT` for agentic workflows in Microsoft org (#144)

### Changed

- Unified `deployed_files` manifest for safe integration lifecycle (#163)
- Exclude `apm_modules` from compilation scanning and cache `Set[Path]` for performance (#157)
- Performance optimization for deep dependency trees (#173)
- Upgrade GitHub Agentic Workflows to v0.52.1 (#141)
- Fix CLI reference drift from consistency reports (#160, #161)
- Replace CHANGELOG link with roadmap discussion in docs index (#196)
- Update documentation for features from 2026-03-07 (#195)

## [0.7.4] - 2025-03-03

### Added

- Support hooks as an agent primitive with install-time integration and dependency display (hooks execute at agent runtime, not during `apm install`) (#97)
- Deploy agents to `.claude/agents/` during `apm install` (#95)
- Promote sub-skills inside packages to top-level `.github/skills/` entries (#102)

### Fixed

- Fix skill integration bugs, transitive dep cleanup, and simplification (#107)
- Fix transitive dependency handling in compile and orphan detection (#111)
- Fix virtual subdirectory deps marked as orphaned, skipping instruction processing (#100)
- Improve multi-host error guidance when `GITHUB_HOST` is set (#113, #130)
- Support spaces in Azure DevOps project names (#92)
- Fix GitHub Actions workflow permissions, integration test skip-propagation, and test corrections (#87, #106, #109)

### Changed

- Migrated to Microsoft OSS organization (#85, #105)
- Added CODEOWNERS, simplified PR/issue templates, triage labels, and updated CONTRIBUTING.md (#115, #118)
- Added missing `version` field in the apm.yml README example (#108)
- Slim PR pipelines to Linux-only, auto-approve integration tests, added agentic workflows for maintenance (#98, #103, #104, #119)


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