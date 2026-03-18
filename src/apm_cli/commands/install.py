"""APM install command and dependency installation engine."""

import builtins
import sys
from pathlib import Path
from typing import List

import click

from ..drift import build_download_ref, detect_orphans, detect_ref_change
from ..utils.console import _rich_error, _rich_info, _rich_success, _rich_warning
from ..utils.diagnostics import DiagnosticCollector
from ..utils.github_host import default_host, is_valid_fqdn
from ..utils.path_security import safe_rmtree
from ._helpers import (
    _create_minimal_apm_yml,
    _get_default_config,
    _load_apm_config,
    _rich_blank_line,
    _update_gitignore_for_apm_modules,
)

# CRITICAL: Shadow Python builtins that share names with Click commands
set = builtins.set
list = builtins.list
dict = builtins.dict

# APM Dependencies (conditional import for graceful degradation)
APM_DEPS_AVAILABLE = False
_APM_IMPORT_ERROR = None
try:
    from ..deps.apm_resolver import APMDependencyResolver
    from ..deps.github_downloader import GitHubPackageDownloader
    from ..deps.lockfile import LockFile, get_lockfile_path, migrate_lockfile_if_needed
    from ..integration import AgentIntegrator, PromptIntegrator
    from ..integration.mcp_integrator import MCPIntegrator
    from ..models.apm_package import APMPackage, DependencyReference

    APM_DEPS_AVAILABLE = True
except ImportError as e:
    _APM_IMPORT_ERROR = str(e)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_and_add_packages_to_apm_yml(packages, dry_run=False):
    """Validate packages exist and can be accessed, then add to apm.yml dependencies section.

    Implements normalize-on-write: any input form (HTTPS URL, SSH URL, FQDN, shorthand)
    is canonicalized before storage. Default host (github.com) is stripped;
    non-default hosts are preserved. Duplicates are detected by identity.
    """
    import subprocess
    import tempfile
    from pathlib import Path

    import yaml

    apm_yml_path = Path("apm.yml")

    # Read current apm.yml
    try:
        with open(apm_yml_path, "r") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        _rich_error(f"Failed to read apm.yml: {e}")
        sys.exit(1)

    # Ensure dependencies structure exists
    if "dependencies" not in data:
        data["dependencies"] = {}
    if "apm" not in data["dependencies"]:
        data["dependencies"]["apm"] = []

    current_deps = data["dependencies"]["apm"] or []
    validated_packages = []

    # Build identity set from existing deps for duplicate detection
    existing_identities = builtins.set()
    for dep_entry in current_deps:
        try:
            if isinstance(dep_entry, str):
                ref = DependencyReference.parse(dep_entry)
            elif isinstance(dep_entry, builtins.dict):
                ref = DependencyReference.parse_from_dict(dep_entry)
            else:
                continue
            existing_identities.add(ref.get_identity())
        except (ValueError, TypeError, AttributeError, KeyError):
            continue

    # First, validate all packages
    _rich_info(f"Validating {len(packages)} package(s)...")

    for package in packages:
        # Validate package format (should be owner/repo, a git URL, or a local path)
        if "/" not in package and not DependencyReference.is_local_path(package):
            _rich_error(f"Invalid package format: {package}. Use 'owner/repo' format.")
            continue

        # Canonicalize input
        try:
            dep_ref = DependencyReference.parse(package)
            canonical = dep_ref.to_canonical()
            identity = dep_ref.get_identity()
        except ValueError as e:
            _rich_error(f"Invalid package: {package} — {e}")
            continue

        # Check if package is already in dependencies (by identity)
        already_in_deps = identity in existing_identities

        # Validate package exists and is accessible
        if _validate_package_exists(package):
            if already_in_deps:
                _rich_info(
                    f"✓ {canonical} - already in apm.yml, ensuring installation..."
                )
            else:
                validated_packages.append(canonical)
                existing_identities.add(identity)  # prevent duplicates within batch
                _rich_info(f"✓ {canonical} - accessible")
        else:
            _rich_error(f"✗ {package} - not accessible or doesn't exist")

    if not validated_packages:
        if dry_run:
            _rich_warning("No new packages to add")
        # If all packages already exist in apm.yml, that's OK - we'll reinstall them
        return []

    if dry_run:
        _rich_info(
            f"Dry run: Would add {len(validated_packages)} package(s) to apm.yml:"
        )
        for pkg in validated_packages:
            _rich_info(f"  + {pkg}")
        return validated_packages

    # Add validated packages to dependencies (already canonical)
    for package in validated_packages:
        current_deps.append(package)
        _rich_info(f"Added {package} to apm.yml")

    # Update dependencies
    data["dependencies"]["apm"] = current_deps

    # Write back to apm.yml
    try:
        with open(apm_yml_path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        _rich_success(f"Updated apm.yml with {len(validated_packages)} new package(s)")
    except Exception as e:
        _rich_error(f"Failed to write apm.yml: {e}")
        sys.exit(1)

    return validated_packages


def _validate_package_exists(package):
    """Validate that a package exists and is accessible on GitHub, Azure DevOps, or locally."""
    import os
    import subprocess
    import tempfile

    try:
        # Parse the package to check if it's a virtual package or ADO
        from apm_cli.models.apm_package import DependencyReference
        from apm_cli.deps.github_downloader import GitHubPackageDownloader

        dep_ref = DependencyReference.parse(package)

        # For local packages, validate directory exists and has valid package content
        if dep_ref.is_local and dep_ref.local_path:
            local = Path(dep_ref.local_path).expanduser()
            if not local.is_absolute():
                local = Path.cwd() / local
            local = local.resolve()
            if not local.is_dir():
                return False
            # Must contain apm.yml or SKILL.md
            return (local / "apm.yml").exists() or (local / "SKILL.md").exists()

        # For virtual packages, use the downloader's validation method
        if dep_ref.is_virtual:
            downloader = GitHubPackageDownloader()
            return downloader.validate_virtual_package_exists(dep_ref)

        # For Azure DevOps or GitHub Enterprise (non-github.com hosts),
        # use the downloader which handles authentication properly
        if dep_ref.is_azure_devops() or (dep_ref.host and dep_ref.host != "github.com"):
            from apm_cli.utils.github_host import is_github_hostname, is_azure_devops_hostname

            downloader = GitHubPackageDownloader()
            # Set the host
            if dep_ref.host:
                downloader.github_host = dep_ref.host

            # Build authenticated URL using downloader's auth
            package_url = downloader._build_repo_url(
                dep_ref.repo_url, use_ssh=False, dep_ref=dep_ref
            )

            # For generic hosts (not GitHub, not ADO), relax the env so native
            # credential helpers (SSH keys, macOS Keychain, etc.) can work.
            # This mirrors _clone_with_fallback() which does the same relaxation.
            is_generic = not is_github_hostname(dep_ref.host) and not is_azure_devops_hostname(dep_ref.host)
            if is_generic:
                validate_env = {k: v for k, v in downloader.git_env.items()
                                if k not in ('GIT_ASKPASS', 'GIT_CONFIG_GLOBAL', 'GIT_CONFIG_NOSYSTEM')}
                validate_env['GIT_TERMINAL_PROMPT'] = '0'
            else:
                validate_env = {**os.environ, **downloader.git_env}

            cmd = ["git", "ls-remote", "--heads", "--exit-code", package_url]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                env=validate_env,
            )
            return result.returncode == 0

        # For GitHub.com, use standard approach (public repos don't need auth)
        package_url = f"{dep_ref.to_github_url()}.git"

        # For regular packages, use git ls-remote
        with tempfile.TemporaryDirectory() as temp_dir:
            try:

                # Try cloning with minimal fetch
                cmd = [
                    "git",
                    "ls-remote",
                    "--heads",
                    "--exit-code",
                    package_url,
                ]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=30  # 30 second timeout
                )

                return result.returncode == 0

            except subprocess.TimeoutExpired:
                return False
            except Exception:
                return False

    except Exception:
        # If parsing fails, assume it's a regular GitHub package
        package_url = (
            f"https://{package}.git"
            if is_valid_fqdn(package)
            else f"https://{default_host()}/{package}.git"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                cmd = [
                    "git",
                    "ls-remote",
                    "--heads",
                    "--exit-code",
                    package_url,
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                return result.returncode == 0

            except subprocess.TimeoutExpired:
                return False
            except Exception:
                return False


# ---------------------------------------------------------------------------
# Install command
# ---------------------------------------------------------------------------


@click.command(
    help="Install APM and MCP dependencies (auto-creates apm.yml when installing packages)"
)
@click.argument("packages", nargs=-1)
@click.option("--runtime", help="Target specific runtime only (copilot, codex, vscode)")
@click.option("--exclude", help="Exclude specific runtime from installation")
@click.option(
    "--only",
    type=click.Choice(["apm", "mcp"]),
    help="Install only specific dependency type",
)
@click.option(
    "--update", is_flag=True, help="Update dependencies to latest Git references"
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be installed without installing"
)
@click.option("--force", is_flag=True, help="Overwrite locally-authored files on collision and deploy despite critical security findings")
@click.option("--verbose", is_flag=True, help="Show detailed installation information")
@click.option(
    "--trust-transitive-mcp",
    is_flag=True,
    help="Trust self-defined MCP servers from transitive packages (skip re-declaration requirement)",
)
@click.option(
    "--parallel-downloads",
    type=int,
    default=4,
    show_default=True,
    help="Max concurrent package downloads (0 to disable parallelism)",
)
@click.pass_context
def install(ctx, packages, runtime, exclude, only, update, dry_run, force, verbose, trust_transitive_mcp, parallel_downloads):
    """Install APM and MCP dependencies from apm.yml (like npm install).

    This command automatically detects AI runtimes from your apm.yml scripts and installs
    MCP servers for all detected and available runtimes. It also installs APM package
    dependencies from GitHub repositories.

    Examples:
        apm install                             # Install existing deps from apm.yml
        apm install org/pkg1                    # Add package to apm.yml and install
        apm install org/pkg1 org/pkg2           # Add multiple packages and install
        apm install --exclude codex             # Install for all except Codex CLI
        apm install --only=apm                  # Install only APM dependencies
        apm install --only=mcp                  # Install only MCP dependencies
        apm install --update                    # Update dependencies to latest Git refs
        apm install --dry-run                   # Show what would be installed
    """
    try:
        # Check if apm.yml exists
        apm_yml_exists = Path("apm.yml").exists()

        # Auto-bootstrap: create minimal apm.yml when packages specified but no apm.yml
        if not apm_yml_exists and packages:
            # Get current directory name as project name
            project_name = Path.cwd().name
            config = _get_default_config(project_name)
            _create_minimal_apm_yml(config)
            _rich_success("Created apm.yml", symbol="sparkles")

        # Error when NO apm.yml AND NO packages
        if not apm_yml_exists and not packages:
            _rich_error("No apm.yml found")
            _rich_info("💡 Run 'apm init' to create one, or:")
            _rich_info("   apm install <org/repo> to auto-create + install")
            sys.exit(1)

        # If packages are specified, validate and add them to apm.yml first
        if packages:
            validated_packages = _validate_and_add_packages_to_apm_yml(
                packages, dry_run
            )
            # Note: Empty validated_packages is OK if packages are already in apm.yml
            # We'll proceed with installation from apm.yml to ensure everything is synced

        _rich_info("Installing dependencies from apm.yml...")

        # Parse apm.yml to get both APM and MCP dependencies
        try:
            apm_package = APMPackage.from_apm_yml(Path("apm.yml"))
        except Exception as e:
            _rich_error(f"Failed to parse apm.yml: {e}")
            sys.exit(1)

        # Get APM and MCP dependencies
        apm_deps = apm_package.get_apm_dependencies()
        mcp_deps = apm_package.get_mcp_dependencies()

        # Determine what to install based on --only flag
        should_install_apm = only != "mcp"
        should_install_mcp = only != "apm"

        # Show what will be installed if dry run
        if dry_run:
            _rich_info("Dry run mode - showing what would be installed:")

            if should_install_apm and apm_deps:
                _rich_info(f"APM dependencies ({len(apm_deps)}):")
                for dep in apm_deps:
                    action = "update" if update else "install"
                    _rich_info(
                        f"  - {dep.repo_url}#{dep.reference or 'main'} → {action}"
                    )

            if should_install_mcp and mcp_deps:
                _rich_info(f"MCP dependencies ({len(mcp_deps)}):")
                for dep in mcp_deps:
                    _rich_info(f"  - {dep}")

            if not apm_deps and not mcp_deps:
                _rich_warning("No dependencies found in apm.yml")

            _rich_success("Dry run complete - no changes made")
            return

        # Install APM dependencies first (if requested)
        apm_count = 0
        prompt_count = 0
        agent_count = 0

        # Migrate legacy apm.lock → apm.lock.yaml if needed (one-time, transparent)
        migrate_lockfile_if_needed(Path.cwd())

        # Capture old MCP servers and configs from lockfile BEFORE
        # _install_apm_dependencies regenerates it (which drops the fields).
        # We always read this — even when --only=apm — so we can restore the
        # field after the lockfile is regenerated by the APM install step.
        old_mcp_servers: builtins.set = builtins.set()
        old_mcp_configs: builtins.dict = {}
        _lock_path = get_lockfile_path(Path.cwd())
        _existing_lock = LockFile.read(_lock_path)
        if _existing_lock:
            old_mcp_servers = builtins.set(_existing_lock.mcp_servers)
            old_mcp_configs = builtins.dict(_existing_lock.mcp_configs)

        apm_diagnostics = None
        if should_install_apm and apm_deps:
            if not APM_DEPS_AVAILABLE:
                _rich_error("APM dependency system not available")
                _rich_info(f"Import error: {_APM_IMPORT_ERROR}")
                sys.exit(1)

            try:
                # If specific packages were requested, only install those
                # Otherwise install all from apm.yml
                only_pkgs = builtins.list(packages) if packages else None
                apm_count, prompt_count, agent_count, apm_diagnostics = _install_apm_dependencies(
                    apm_package, update, verbose, only_pkgs, force=force,
                    parallel_downloads=parallel_downloads,
                )
            except Exception as e:
                _rich_error(f"Failed to install APM dependencies: {e}")
                sys.exit(1)
        elif should_install_apm and not apm_deps:
            _rich_info("No APM dependencies found in apm.yml")

        # When --update is used, package files on disk may have changed.
        # Clear the parse cache so transitive MCP collection reads fresh data.
        if update:
            from apm_cli.models.apm_package import clear_apm_yml_cache
            clear_apm_yml_cache()

        # Collect transitive MCP dependencies from resolved APM packages
        apm_modules_path = Path.cwd() / "apm_modules"
        if should_install_mcp and apm_modules_path.exists():
            lock_path = get_lockfile_path(Path.cwd())
            transitive_mcp = MCPIntegrator.collect_transitive(apm_modules_path, lock_path, trust_transitive_mcp)
            if transitive_mcp:
                _rich_info(f"Collected {len(transitive_mcp)} transitive MCP dependency(ies)")
                mcp_deps = MCPIntegrator.deduplicate(mcp_deps + transitive_mcp)

        # Continue with MCP installation (existing logic)
        mcp_count = 0
        new_mcp_servers: builtins.set = builtins.set()
        if should_install_mcp and mcp_deps:
            mcp_count = MCPIntegrator.install(
                mcp_deps, runtime, exclude, verbose,
                stored_mcp_configs=old_mcp_configs,
            )
            new_mcp_servers = MCPIntegrator.get_server_names(mcp_deps)
            new_mcp_configs = MCPIntegrator.get_server_configs(mcp_deps)

            # Remove stale MCP servers that are no longer needed
            stale_servers = old_mcp_servers - new_mcp_servers
            if stale_servers:
                MCPIntegrator.remove_stale(stale_servers, runtime, exclude)

            # Persist the new MCP server set and configs in the lockfile
            MCPIntegrator.update_lockfile(new_mcp_servers, mcp_configs=new_mcp_configs)
        elif should_install_mcp and not mcp_deps:
            # No MCP deps at all — remove any old APM-managed servers
            if old_mcp_servers:
                MCPIntegrator.remove_stale(old_mcp_servers, runtime, exclude)
                MCPIntegrator.update_lockfile(builtins.set(), mcp_configs={})
            _rich_warning("No MCP dependencies found in apm.yml")
        elif not should_install_mcp and old_mcp_servers:
            # --only=apm: APM install regenerated the lockfile and dropped
            # mcp_servers.  Restore the previous set so it is not lost.
            MCPIntegrator.update_lockfile(old_mcp_servers, mcp_configs=old_mcp_configs)

        # Show beautiful post-install summary
        if apm_diagnostics and apm_diagnostics.has_diagnostics:
            apm_diagnostics.render_summary()
        else:
            _rich_blank_line()
        if not only:
            # Load apm.yml config for summary
            apm_config = _load_apm_config()
            _show_install_summary(
                apm_count, prompt_count, agent_count, mcp_count, apm_config
            )
        elif only == "apm":
            _rich_success(f"Installed {apm_count} APM dependencies")
        elif only == "mcp":
            _rich_success(f"Configured {mcp_count} MCP servers")

        # Hard-fail when critical security findings blocked any package.
        # Consistent with apm unpack which also hard-fails on critical.
        # Use --force to override.
        if not force and apm_diagnostics and apm_diagnostics.has_critical_security:
            sys.exit(1)

    except Exception as e:
        _rich_error(f"Error installing dependencies: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Install engine
# ---------------------------------------------------------------------------


def _pre_deploy_security_scan(
    install_path: Path,
    diagnostics: DiagnosticCollector,
    package_name: str = "",
    force: bool = False,
) -> bool:
    """Scan package source files for hidden characters BEFORE deployment.

    Delegates to :class:`SecurityGate` for the scan→classify→decide pipeline.
    Inline CLI feedback (error/info lines) is kept here because it is
    install-specific formatting.

    Returns:
        True if deployment should proceed, False to block.
    """
    from ..security.gate import BLOCK_POLICY, SecurityGate

    verdict = SecurityGate.scan_files(
        install_path, policy=BLOCK_POLICY, force=force
    )
    if not verdict.has_findings:
        return True

    # Record into diagnostics (consistent messaging via gate)
    SecurityGate.report(verdict, diagnostics, package=package_name, force=force)

    if verdict.should_block:
        _rich_error(
            f"  Blocked: {package_name or 'package'} contains "
            f"critical hidden character(s)"
        )
        _rich_info(f"  └─ Inspect source: {install_path}")
        _rich_info("  └─ Use --force to deploy anyway")
        return False

    return True


def _integrate_package_primitives(
    package_info,
    project_root,
    *,
    integrate_vscode,
    integrate_claude,
    integrate_opencode=False,
    prompt_integrator,
    agent_integrator,
    skill_integrator,
    instruction_integrator,
    command_integrator,
    hook_integrator,
    force,
    managed_files,
    diagnostics,
    package_name="",
):
    """Run the full integration pipeline for a single package.

    Returns a dict with integration counters and the list of deployed file paths.
    """
    result = {
        "prompts": 0,
        "agents": 0,
        "skills": 0,
        "sub_skills": 0,
        "instructions": 0,
        "commands": 0,
        "hooks": 0,
        "links_resolved": 0,
        "deployed_files": [],
    }

    deployed = result["deployed_files"]

    if not (integrate_vscode or integrate_claude or integrate_opencode):
        return result

    # --- prompts ---
    prompt_result = prompt_integrator.integrate_package_prompts(
        package_info, project_root,
        force=force, managed_files=managed_files,
        diagnostics=diagnostics,
    )
    if prompt_result.files_integrated > 0:
        result["prompts"] += prompt_result.files_integrated
        _rich_info(f"  └─ {prompt_result.files_integrated} prompts integrated → .github/prompts/")
    if prompt_result.files_updated > 0:
        _rich_info(f"  └─ {prompt_result.files_updated} prompts updated")
    result["links_resolved"] += prompt_result.links_resolved
    for tp in prompt_result.target_paths:
        deployed.append(tp.relative_to(project_root).as_posix())

    # --- agents (.github) ---
    agent_result = agent_integrator.integrate_package_agents(
        package_info, project_root,
        force=force, managed_files=managed_files,
        diagnostics=diagnostics,
    )
    if agent_result.files_integrated > 0:
        result["agents"] += agent_result.files_integrated
        _rich_info(f"  └─ {agent_result.files_integrated} agents integrated → .github/agents/")
    if agent_result.files_updated > 0:
        _rich_info(f"  └─ {agent_result.files_updated} agents updated")
    result["links_resolved"] += agent_result.links_resolved
    for tp in agent_result.target_paths:
        deployed.append(tp.relative_to(project_root).as_posix())

    # --- skills ---
    if integrate_vscode or integrate_claude or integrate_opencode:
        skill_result = skill_integrator.integrate_package_skill(
            package_info, project_root,
            diagnostics=diagnostics, managed_files=managed_files, force=force,
        )
        if skill_result.skill_created:
            result["skills"] += 1
            _rich_info(f"  └─ Skill integrated → .github/skills/")
        if skill_result.sub_skills_promoted > 0:
            result["sub_skills"] += skill_result.sub_skills_promoted
            _rich_info(f"  └─ {skill_result.sub_skills_promoted} skill(s) integrated → .github/skills/")
        for tp in skill_result.target_paths:
            deployed.append(tp.relative_to(project_root).as_posix())

    # --- instructions (.github) ---
    if integrate_vscode:
        instruction_result = instruction_integrator.integrate_package_instructions(
            package_info, project_root,
            force=force, managed_files=managed_files,
            diagnostics=diagnostics,
        )
        if instruction_result.files_integrated > 0:
            result["instructions"] += instruction_result.files_integrated
            _rich_info(f"  └─ {instruction_result.files_integrated} instruction(s) integrated → .github/instructions/")
        result["links_resolved"] += instruction_result.links_resolved
        for tp in instruction_result.target_paths:
            deployed.append(tp.relative_to(project_root).as_posix())

    # --- Cursor rules (.cursor/rules/) ---
    cursor_rules_result = instruction_integrator.integrate_package_instructions_cursor(
        package_info, project_root,
        force=force, managed_files=managed_files,
        diagnostics=diagnostics,
    )
    if cursor_rules_result.files_integrated > 0:
        result["instructions"] += cursor_rules_result.files_integrated
        _rich_info(f"  └─ {cursor_rules_result.files_integrated} rule(s) integrated → .cursor/rules/")
    result["links_resolved"] += cursor_rules_result.links_resolved
    for tp in cursor_rules_result.target_paths:
        deployed.append(tp.relative_to(project_root).as_posix())

    # --- Claude agents (.claude) ---
    if integrate_claude:
        claude_agent_result = agent_integrator.integrate_package_agents_claude(
            package_info, project_root,
            force=force, managed_files=managed_files,
            diagnostics=diagnostics,
        )
        if claude_agent_result.files_integrated > 0:
            result["agents"] += claude_agent_result.files_integrated
            _rich_info(f"  └─ {claude_agent_result.files_integrated} agents integrated → .claude/agents/")
        result["links_resolved"] += claude_agent_result.links_resolved
        for tp in claude_agent_result.target_paths:
            deployed.append(tp.relative_to(project_root).as_posix())

    # --- Cursor agents (.cursor) ---
    cursor_agent_result = agent_integrator.integrate_package_agents_cursor(
        package_info, project_root,
        force=force, managed_files=managed_files,
        diagnostics=diagnostics,
    )
    if cursor_agent_result.files_integrated > 0:
        result["agents"] += cursor_agent_result.files_integrated
        _rich_info(f"  └─ {cursor_agent_result.files_integrated} agents integrated → .cursor/agents/")
    result["links_resolved"] += cursor_agent_result.links_resolved
    for tp in cursor_agent_result.target_paths:
        deployed.append(tp.relative_to(project_root).as_posix())

    # --- OpenCode agents (.opencode) ---
    opencode_agent_result = agent_integrator.integrate_package_agents_opencode(
        package_info, project_root,
        force=force, managed_files=managed_files,
        diagnostics=diagnostics,
    )
    if opencode_agent_result.files_integrated > 0:
        result["agents"] += opencode_agent_result.files_integrated
        _rich_info(f"  └─ {opencode_agent_result.files_integrated} agents integrated → .opencode/agents/")
    result["links_resolved"] += opencode_agent_result.links_resolved
    for tp in opencode_agent_result.target_paths:
        deployed.append(tp.relative_to(project_root).as_posix())

    # --- commands (.claude) ---
    command_result = command_integrator.integrate_package_commands(
        package_info, project_root,
        force=force, managed_files=managed_files,
        diagnostics=diagnostics,
    )
    if command_result.files_integrated > 0:
        result["commands"] += command_result.files_integrated
        _rich_info(f"  └─ {command_result.files_integrated} commands integrated → .claude/commands/")
    if command_result.files_updated > 0:
        _rich_info(f"  └─ {command_result.files_updated} commands updated")
    result["links_resolved"] += command_result.links_resolved
    for tp in command_result.target_paths:
        deployed.append(tp.relative_to(project_root).as_posix())

    # --- OpenCode commands (.opencode) ---
    opencode_command_result = command_integrator.integrate_package_commands_opencode(
        package_info, project_root,
        force=force, managed_files=managed_files,
        diagnostics=diagnostics,
    )
    if opencode_command_result.files_integrated > 0:
        result["commands"] += opencode_command_result.files_integrated
        _rich_info(f"  └─ {opencode_command_result.files_integrated} commands integrated → .opencode/commands/")
    result["links_resolved"] += opencode_command_result.links_resolved
    for tp in opencode_command_result.target_paths:
        deployed.append(tp.relative_to(project_root).as_posix())

    # --- hooks ---
    if integrate_vscode:
        hook_result = hook_integrator.integrate_package_hooks(
            package_info, project_root,
            force=force, managed_files=managed_files,
            diagnostics=diagnostics,
        )
        if hook_result.hooks_integrated > 0:
            result["hooks"] += hook_result.hooks_integrated
            _rich_info(f"  └─ {hook_result.hooks_integrated} hook(s) integrated → .github/hooks/")
        for tp in hook_result.target_paths:
            deployed.append(tp.relative_to(project_root).as_posix())
    if integrate_claude:
        hook_result_claude = hook_integrator.integrate_package_hooks_claude(
            package_info, project_root,
            force=force, managed_files=managed_files,
            diagnostics=diagnostics,
        )
        if hook_result_claude.hooks_integrated > 0:
            result["hooks"] += hook_result_claude.hooks_integrated
            _rich_info(f"  └─ {hook_result_claude.hooks_integrated} hook(s) integrated → .claude/settings.json")
        for tp in hook_result_claude.target_paths:
            deployed.append(tp.relative_to(project_root).as_posix())

    # Cursor hooks (.cursor/hooks.json) — method self-guards on .cursor/ existence
    hook_result_cursor = hook_integrator.integrate_package_hooks_cursor(
        package_info, project_root,
        force=force, managed_files=managed_files,
        diagnostics=diagnostics,
    )
    if hook_result_cursor.hooks_integrated > 0:
        result["hooks"] += hook_result_cursor.hooks_integrated
        _rich_info(f"  └─ {hook_result_cursor.hooks_integrated} hook(s) integrated → .cursor/hooks.json")
    for tp in hook_result_cursor.target_paths:
        deployed.append(tp.relative_to(project_root).as_posix())

    return result


def _copy_local_package(dep_ref, install_path, project_root):
    """Copy a local package to apm_modules/.

    Args:
        dep_ref: DependencyReference with is_local=True
        install_path: Target path under apm_modules/
        project_root: Project root for resolving relative paths

    Returns:
        install_path on success, None on failure
    """
    import shutil

    local = Path(dep_ref.local_path).expanduser()
    if not local.is_absolute():
        local = (project_root / local).resolve()
    else:
        local = local.resolve()

    if not local.is_dir():
        _rich_error(f"Local package path does not exist: {dep_ref.local_path}")
        return None
    if not (local / "apm.yml").exists() and not (local / "SKILL.md").exists():
        _rich_error(
            f"Local package is not a valid APM package (no apm.yml or SKILL.md): {dep_ref.local_path}"
        )
        return None

    # Ensure parent exists and clean target (always re-copy for local deps)
    install_path.parent.mkdir(parents=True, exist_ok=True)
    if install_path.exists():
        # install_path is already validated by get_install_path() (Layer 2),
        # but use safe_rmtree for defense-in-depth.
        apm_modules_dir = install_path.parent.parent  # _local/<name> → apm_modules
        safe_rmtree(install_path, apm_modules_dir)

    shutil.copytree(local, install_path, dirs_exist_ok=False, symlinks=True)
    return install_path


def _install_apm_dependencies(
    apm_package: "APMPackage",
    update_refs: bool = False,
    verbose: bool = False,
    only_packages: "builtins.list" = None,
    force: bool = False,
    parallel_downloads: int = 4,
):
    """Install APM package dependencies.

    Args:
        apm_package: Parsed APM package with dependencies
        update_refs: Whether to update existing packages to latest refs
        verbose: Show detailed installation information
        only_packages: If provided, only install these specific packages (not all from apm.yml)
        force: Whether to overwrite locally-authored files on collision
        parallel_downloads: Max concurrent downloads (0 disables parallelism)
    """
    if not APM_DEPS_AVAILABLE:
        raise RuntimeError("APM dependency system not available")

    apm_deps = apm_package.get_apm_dependencies()
    if not apm_deps:
        return 0, 0, 0

    _rich_info(f"Installing APM dependencies ({len(apm_deps)})...")

    project_root = Path.cwd()

    # T5: Check for existing lockfile - use locked versions for reproducible installs
    from apm_cli.deps.lockfile import LockFile, get_lockfile_path
    lockfile_path = get_lockfile_path(project_root)
    existing_lockfile = None
    if lockfile_path.exists() and not update_refs:
        existing_lockfile = LockFile.read(lockfile_path)
        if existing_lockfile and existing_lockfile.dependencies:
            _rich_info(f"Using apm.lock.yaml ({len(existing_lockfile.dependencies)} locked dependencies)")

    apm_modules_dir = project_root / "apm_modules"
    apm_modules_dir.mkdir(exist_ok=True)

    # Create downloader early so it can be used for transitive dependency resolution
    downloader = GitHubPackageDownloader()

    # Track direct dependency keys so the download callback can distinguish them from transitive
    direct_dep_keys = builtins.set(dep.get_unique_key() for dep in apm_deps)

    # Track paths already downloaded by the resolver callback to avoid re-downloading
    # Maps dep_key -> resolved_commit (SHA or None) so the cached path can use it
    callback_downloaded = {}

    # Create a download callback for transitive dependency resolution
    # This allows the resolver to fetch packages on-demand during tree building
    def download_callback(dep_ref, modules_dir):
        """Download a package during dependency resolution."""
        install_path = dep_ref.get_install_path(modules_dir)
        if install_path.exists():
            return install_path
        try:
            # Handle local packages: copy instead of git clone
            if dep_ref.is_local and dep_ref.local_path:
                result_path = _copy_local_package(dep_ref, install_path, project_root)
                if result_path:
                    callback_downloaded[dep_ref.get_unique_key()] = None
                    return result_path
                return None

            # Build repo_ref string - include host for GHE/ADO/Artifactory, plus reference if specified
            repo_ref = dep_ref.repo_url
            if dep_ref.host and dep_ref.host not in ("github.com", None):
                if dep_ref.artifactory_prefix:
                    repo_ref = f"{dep_ref.host}/{dep_ref.artifactory_prefix}/{dep_ref.repo_url}"
                else:
                    repo_ref = f"{dep_ref.host}/{dep_ref.repo_url}"
            if dep_ref.virtual_path:
                repo_ref = f"{repo_ref}/{dep_ref.virtual_path}"

            # T5: Use locked commit if available (reproducible installs)
            locked_ref = None
            if existing_lockfile:
                locked_dep = existing_lockfile.get_dependency(dep_ref.get_unique_key())
                if locked_dep and locked_dep.resolved_commit and locked_dep.resolved_commit != "cached":
                    locked_ref = locked_dep.resolved_commit

            # Priority: locked commit > explicit reference > default branch
            if locked_ref:
                repo_ref = f"{repo_ref}#{locked_ref}"
            elif dep_ref.reference:
                repo_ref = f"{repo_ref}#{dep_ref.reference}"

            # Silent download - no progress display for transitive deps
            result = downloader.download_package(repo_ref, install_path)
            # Capture resolved commit SHA for lockfile
            resolved_sha = None
            if result and hasattr(result, 'resolved_reference') and result.resolved_reference:
                resolved_sha = result.resolved_reference.resolved_commit
            callback_downloaded[dep_ref.get_unique_key()] = resolved_sha
            return install_path
        except Exception as e:
            # Log but don't fail - allow resolution to continue
            if verbose:
                _rich_error(f"  └─ Failed to resolve transitive dep {dep_ref.repo_url}: {e}")
            return None

    # Resolve dependencies with transitive download support
    resolver = APMDependencyResolver(
        apm_modules_dir=apm_modules_dir,
        download_callback=download_callback
    )

    try:
        dependency_graph = resolver.resolve_dependencies(project_root)

        # Check for circular dependencies
        if dependency_graph.circular_dependencies:
            _rich_error("Circular dependencies detected:")
            for circular in dependency_graph.circular_dependencies:
                cycle_path = " → ".join(circular.cycle_path)
                _rich_error(f"  {cycle_path}")
            raise RuntimeError("Cannot install packages with circular dependencies")

        # Get flattened dependencies for installation
        flat_deps = dependency_graph.flattened_dependencies
        deps_to_install = flat_deps.get_installation_list()

        # If specific packages were requested, filter to only those
        # **and their full transitive dependency subtrees** so that
        # sub-deps (and their MCP servers) are installed and recorded
        # in the lockfile.
        if only_packages:
            # Build identity set from user-supplied package specs.
            # Accepts any input form: git URLs, FQDN, shorthand.
            only_identities = builtins.set()
            for p in only_packages:
                try:
                    ref = DependencyReference.parse(p)
                    only_identities.add(ref.get_identity())
                except Exception:
                    only_identities.add(p)

            # Expand the set to include transitive descendants of the
            # requested packages so their MCP servers, primitives, etc.
            # are correctly installed and written to the lockfile.
            tree = dependency_graph.dependency_tree

            def _collect_descendants(node, visited=None):
                """Walk the tree and add every child identity (cycle-safe)."""
                if visited is None:
                    visited = builtins.set()
                for child in node.children:
                    identity = child.dependency_ref.get_identity()
                    if identity not in visited:
                        visited.add(identity)
                        only_identities.add(identity)
                        _collect_descendants(child, visited)

            for node in tree.nodes.values():
                if node.dependency_ref.get_identity() in only_identities:
                    _collect_descendants(node)

            deps_to_install = [
                dep for dep in deps_to_install
                if dep.get_identity() in only_identities
            ]

        if not deps_to_install:
            _rich_info("No APM dependencies to install", symbol="check")
            return 0, 0, 0

        # ------------------------------------------------------------------
        # Orphan detection: packages in lockfile no longer in the manifest.
        # Only relevant for a full install (not apm install <pkg>).
        # We compute this NOW, before the download loop, so we know which old
        # lockfile entries to remove from the merge and which deployed files
        # to clean up after the loop.
        # ------------------------------------------------------------------
        intended_dep_keys: builtins.set = builtins.set(
            d.get_unique_key() for d in deps_to_install
        )

        # apm_modules directory already created above

        # Auto-detect target for integration (same logic as compile)
        from apm_cli.core.target_detection import (
            detect_target,
            should_integrate_vscode,
            should_integrate_claude,
            should_integrate_opencode,
            get_target_description,
        )

        # Get config target from apm.yml if available
        config_target = apm_package.target

        # Auto-create .github/ if neither .github/ nor .claude/ exists.
        # Per skill-strategy Decision 1, .github/skills/ is the standard skills location;
        # creating .github/ here ensures a consistent skills root and also enables
        # VSCode/Copilot integration by default (quick path to value), even for
        # projects that don't yet use .claude/.
        github_dir = project_root / ".github"
        claude_dir = project_root / ".claude"
        if not github_dir.exists() and not claude_dir.exists():
            github_dir.mkdir(parents=True, exist_ok=True)
            _rich_info(
                "Created .github/ as standard skills root (.github/skills/) and to enable VSCode/Copilot integration"
            )

        detected_target, detection_reason = detect_target(
            project_root=project_root,
            explicit_target=None,  # No explicit flag for install
            config_target=config_target,
        )

        # Determine which integrations to run based on detected target
        integrate_vscode = should_integrate_vscode(detected_target)
        integrate_claude = should_integrate_claude(detected_target)
        integrate_opencode = should_integrate_opencode(detected_target)

        # Initialize integrators
        prompt_integrator = PromptIntegrator()
        agent_integrator = AgentIntegrator()
        from apm_cli.integration.skill_integrator import SkillIntegrator, should_install_skill
        from apm_cli.integration.command_integrator import CommandIntegrator
        from apm_cli.integration.hook_integrator import HookIntegrator
        from apm_cli.integration.instruction_integrator import InstructionIntegrator

        skill_integrator = SkillIntegrator()
        command_integrator = CommandIntegrator()
        hook_integrator = HookIntegrator()
        instruction_integrator = InstructionIntegrator()
        diagnostics = DiagnosticCollector(verbose=verbose)
        total_prompts_integrated = 0
        total_agents_integrated = 0
        total_skills_integrated = 0
        total_sub_skills_promoted = 0
        total_instructions_integrated = 0
        total_commands_integrated = 0
        total_hooks_integrated = 0
        total_links_resolved = 0

        # Collect installed packages for lockfile generation
        from apm_cli.deps.lockfile import LockFile, LockedDependency, get_lockfile_path
        installed_packages: List[tuple] = []  # List of (dep_ref, resolved_commit, depth, resolved_by)
        package_deployed_files: builtins.dict = {}  # dep_key → list of relative deployed paths
        package_types: builtins.dict = {}  # dep_key → package type string

        # Build managed_files from existing lockfile for collision detection
        managed_files = builtins.set()
        existing_lockfile = LockFile.read(get_lockfile_path(project_root)) if project_root else None
        if existing_lockfile:
            for dep in existing_lockfile.dependencies.values():
                managed_files.update(dep.deployed_files)
        # Normalize path separators once for O(1) lookups in check_collision
        from apm_cli.integration.base_integrator import BaseIntegrator
        managed_files = BaseIntegrator.normalize_managed_files(managed_files)

        # Collect deployed file paths for packages that are no longer in the manifest.
        # detect_orphans() returns an empty set for partial installs automatically.
        orphaned_deployed_files = detect_orphans(
            existing_lockfile,
            intended_dep_keys,
            only_packages=only_packages,
        )

        # Install each dependency with Rich progress display
        from rich.progress import (
            Progress,
            SpinnerColumn,
            TextColumn,
            BarColumn,
            TaskProgressColumn,
        )

        # downloader already created above for transitive resolution
        installed_count = 0
        unpinned_count = 0

        # Phase 4 (#171): Parallel package downloads using ThreadPoolExecutor
        # Pre-download all non-cached packages in parallel for wall-clock speedup.
        # Results are stored and consumed by the sequential integration loop below.
        from concurrent.futures import ThreadPoolExecutor, as_completed as _futures_completed

        _pre_download_results = {}   # dep_key -> PackageInfo
        _need_download = []
        for _pd_ref in deps_to_install:
            _pd_key = _pd_ref.get_unique_key()
            _pd_path = (apm_modules_dir / _pd_ref.alias) if _pd_ref.alias else _pd_ref.get_install_path(apm_modules_dir)
            # Skip local packages — they are copied, not downloaded
            if _pd_ref.is_local:
                continue
            # Skip if already downloaded during BFS resolution
            if _pd_key in callback_downloaded:
                continue
            # Detect if manifest ref changed from what's recorded in the lockfile.
            # detect_ref_change() handles all transitions including None→ref.
            _pd_locked_chk = (
                existing_lockfile.get_dependency(_pd_key)
                if existing_lockfile and not update_refs
                else None
            )
            _pd_ref_changed = detect_ref_change(
                _pd_ref, _pd_locked_chk, update_refs=update_refs
            )
            # Skip if lockfile SHA matches local HEAD (Phase 5 check)
            # — but only if the ref itself has not changed in the manifest.
            if _pd_path.exists() and existing_lockfile and not update_refs and not _pd_ref_changed:
                _pd_locked = existing_lockfile.get_dependency(_pd_key)
                if _pd_locked and _pd_locked.resolved_commit and _pd_locked.resolved_commit != "cached":
                    try:
                        from git import Repo as _PDGitRepo
                        if _PDGitRepo(_pd_path).head.commit.hexsha == _pd_locked.resolved_commit:
                            continue
                    except Exception:
                        pass
            # Build download ref (use locked commit for reproducibility).
            # build_download_ref() uses the manifest ref when ref_changed is True.
            _pd_dlref = build_download_ref(
                _pd_ref, existing_lockfile, update_refs=update_refs, ref_changed=_pd_ref_changed
            )
            _need_download.append((_pd_ref, _pd_path, _pd_dlref))

        if _need_download and parallel_downloads > 0:
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]{task.description}[/cyan]"),
                BarColumn(),
                TaskProgressColumn(),
                transient=True,
            ) as _dl_progress:
                _max_workers = min(parallel_downloads, len(_need_download))
                with ThreadPoolExecutor(max_workers=_max_workers) as _executor:
                    _futures = {}
                    for _pd_ref, _pd_path, _pd_dlref in _need_download:
                        _pd_disp = str(_pd_ref) if _pd_ref.is_virtual else _pd_ref.repo_url
                        _pd_short = _pd_disp.split("/")[-1] if "/" in _pd_disp else _pd_disp
                        _pd_tid = _dl_progress.add_task(description=f"Fetching {_pd_short}", total=None)
                        _pd_fut = _executor.submit(
                            downloader.download_package, _pd_dlref, _pd_path,
                            progress_task_id=_pd_tid, progress_obj=_dl_progress,
                        )
                        _futures[_pd_fut] = (_pd_ref, _pd_tid, _pd_disp)
                    for _pd_fut in _futures_completed(_futures):
                        _pd_ref, _pd_tid, _pd_disp = _futures[_pd_fut]
                        _pd_key = _pd_ref.get_unique_key()
                        try:
                            _pd_info = _pd_fut.result()
                            _pre_download_results[_pd_key] = _pd_info
                            _dl_progress.update(_pd_tid, visible=False)
                            _dl_progress.refresh()
                        except Exception:
                            _dl_progress.remove_task(_pd_tid)
                            # Silent: sequential loop below will retry and report errors

        _pre_downloaded_keys = builtins.set(_pre_download_results.keys())

        # Create progress display for sequential integration
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]{task.description}[/cyan]"),
            BarColumn(),
            TaskProgressColumn(),
            transient=True,  # Progress bar disappears when done
        ) as progress:
            for dep_ref in deps_to_install:
                # Determine installation directory using namespaced structure
                # e.g., microsoft/apm-sample-package -> apm_modules/microsoft/apm-sample-package/
                # For virtual packages: owner/repo/prompts/file.prompt.md -> apm_modules/owner/repo-file/
                # For subdirectory packages: owner/repo/subdir -> apm_modules/owner/repo/subdir/
                if dep_ref.alias:
                    # If alias is provided, use it directly (assume user handles namespacing)
                    install_name = dep_ref.alias
                    install_path = apm_modules_dir / install_name
                else:
                    # Use the canonical install path from DependencyReference
                    install_path = dep_ref.get_install_path(apm_modules_dir)

                # --- Local package: copy from filesystem (no git download) ---
                if dep_ref.is_local and dep_ref.local_path:
                    result_path = _copy_local_package(dep_ref, install_path, project_root)
                    if not result_path:
                        diagnostics.error(
                            f"Failed to copy local package: {dep_ref.local_path}",
                            package=dep_ref.local_path,
                        )
                        continue

                    installed_count += 1
                    _rich_success(f"✓ {dep_ref.local_path} (local)")

                    # Build minimal PackageInfo for integration
                    from apm_cli.models.apm_package import (
                        APMPackage,
                        PackageInfo,
                        PackageType,
                        ResolvedReference,
                        GitReferenceType,
                    )
                    from datetime import datetime

                    local_apm_yml = install_path / "apm.yml"
                    if local_apm_yml.exists():
                        local_pkg = APMPackage.from_apm_yml(local_apm_yml)
                        if not local_pkg.source:
                            local_pkg.source = dep_ref.local_path
                    else:
                        local_pkg = APMPackage(
                            name=Path(dep_ref.local_path).name,
                            version="0.0.0",
                            package_path=install_path,
                            source=dep_ref.local_path,
                        )

                    local_ref = ResolvedReference(
                        original_ref="local",
                        ref_type=GitReferenceType.BRANCH,
                        resolved_commit="local",
                        ref_name="local",
                    )
                    local_info = PackageInfo(
                        package=local_pkg,
                        install_path=install_path,
                        resolved_reference=local_ref,
                        installed_at=datetime.now().isoformat(),
                        dependency_ref=dep_ref,
                    )

                    # Detect package type
                    has_skill = (install_path / "SKILL.md").exists()
                    has_apm = (install_path / "apm.yml").exists()
                    from apm_cli.utils.helpers import find_plugin_json
                    has_plugin = find_plugin_json(install_path) is not None
                    if has_plugin and not has_apm:
                        local_info.package_type = PackageType.MARKETPLACE_PLUGIN
                    elif has_skill and has_apm:
                        local_info.package_type = PackageType.HYBRID
                    elif has_skill:
                        local_info.package_type = PackageType.CLAUDE_SKILL
                    elif has_apm:
                        local_info.package_type = PackageType.APM_PACKAGE

                    # Record for lockfile
                    node = dependency_graph.dependency_tree.get_node(dep_ref.get_unique_key())
                    depth = node.depth if node else 1
                    resolved_by = node.parent.dependency_ref.repo_url if node and node.parent else None
                    installed_packages.append((dep_ref, None, depth, resolved_by))
                    dep_key = dep_ref.get_unique_key()
                    dep_deployed_files: builtins.list = []

                    if hasattr(local_info, 'package_type') and local_info.package_type:
                        package_types[dep_key] = local_info.package_type.value

                    # Use the same variable name as the rest of the loop
                    package_info = local_info

                    # Run shared integration pipeline
                    try:
                        # Pre-deploy security gate
                        if not _pre_deploy_security_scan(
                            install_path, diagnostics,
                            package_name=dep_key, force=force,
                        ):
                            package_deployed_files[dep_key] = []
                            continue

                        int_result = _integrate_package_primitives(
                            package_info, project_root,
                            integrate_vscode=integrate_vscode,
                            integrate_claude=integrate_claude,
                            integrate_opencode=integrate_opencode,
                            prompt_integrator=prompt_integrator,
                            agent_integrator=agent_integrator,
                            skill_integrator=skill_integrator,
                            instruction_integrator=instruction_integrator,
                            command_integrator=command_integrator,
                            hook_integrator=hook_integrator,
                            force=force,
                            managed_files=managed_files,
                            diagnostics=diagnostics,
                            package_name=dep_key,
                        )
                        total_prompts_integrated += int_result["prompts"]
                        total_agents_integrated += int_result["agents"]
                        total_skills_integrated += int_result["skills"]
                        total_sub_skills_promoted += int_result["sub_skills"]
                        total_instructions_integrated += int_result["instructions"]
                        total_commands_integrated += int_result["commands"]
                        total_hooks_integrated += int_result["hooks"]
                        total_links_resolved += int_result["links_resolved"]
                        dep_deployed_files.extend(int_result["deployed_files"])
                    except Exception as e:
                        diagnostics.error(
                            f"Failed to integrate primitives from local package: {e}",
                            package=dep_ref.local_path,
                        )

                    package_deployed_files[dep_key] = dep_deployed_files
                    continue

                # npm-like behavior: Branches always fetch latest, only tags/commits use cache
                # Resolve git reference to determine type
                from apm_cli.models.apm_package import GitReferenceType

                resolved_ref = None
                if dep_ref.reference and dep_ref.get_unique_key() not in _pre_downloaded_keys:
                    try:
                        resolved_ref = downloader.resolve_git_reference(
                            f"{dep_ref.repo_url}@{dep_ref.reference}"
                        )
                    except Exception:
                        pass  # If resolution fails, skip cache (fetch latest)

                # Use cache only for tags and commits (not branches)
                is_cacheable = resolved_ref and resolved_ref.ref_type in [
                    GitReferenceType.TAG,
                    GitReferenceType.COMMIT,
                ]
                # Skip download if: already fetched by resolver callback, or cached tag/commit
                already_resolved = dep_ref.get_unique_key() in callback_downloaded
                # Detect if manifest ref changed vs what the lockfile recorded.
                # detect_ref_change() handles all transitions including None→ref.
                _dep_locked_chk = (
                    existing_lockfile.get_dependency(dep_ref.get_unique_key())
                    if existing_lockfile and not update_refs
                    else None
                )
                ref_changed = detect_ref_change(
                    dep_ref, _dep_locked_chk, update_refs=update_refs
                )
                # Phase 5 (#171): Also skip when lockfile SHA matches local HEAD
                # — but not when the manifest ref has changed (user wants different version).
                lockfile_match = False
                if install_path.exists() and existing_lockfile and not update_refs and not ref_changed:
                    locked_dep = existing_lockfile.get_dependency(dep_ref.get_unique_key())
                    if locked_dep and locked_dep.resolved_commit and locked_dep.resolved_commit != "cached":
                        try:
                            from git import Repo as GitRepo
                            local_repo = GitRepo(install_path)
                            if local_repo.head.commit.hexsha == locked_dep.resolved_commit:
                                lockfile_match = True
                        except Exception:
                            pass  # Not a git repo or invalid — fall through to download
                skip_download = install_path.exists() and (
                    (is_cacheable and not update_refs) or already_resolved or lockfile_match
                )

                if skip_download:
                    display_name = (
                        str(dep_ref) if dep_ref.is_virtual else dep_ref.repo_url
                    )
                    # Show resolved ref from lockfile for consistency with fresh installs
                    ref_str = ""
                    if _dep_locked_chk and _dep_locked_chk.resolved_commit and _dep_locked_chk.resolved_commit != "cached":
                        short_sha = _dep_locked_chk.resolved_commit[:8]
                        if dep_ref.reference:
                            ref_str = f"#{dep_ref.reference} ({short_sha})"
                        else:
                            ref_str = f"#{short_sha}"
                    elif dep_ref.reference:
                        ref_str = f"#{dep_ref.reference}"
                    _rich_info(f"✓ {display_name}{ref_str} (cached)")
                    installed_count += 1
                    if not dep_ref.reference:
                        unpinned_count += 1

                    # Still need to integrate prompts for cached packages (zero-config behavior)
                    if integrate_vscode or integrate_claude or integrate_opencode:
                        try:
                            # Create PackageInfo from cached package
                            from apm_cli.models.apm_package import (
                                APMPackage,
                                PackageInfo,
                                PackageType,
                                ResolvedReference,
                                GitReferenceType,
                            )
                            from datetime import datetime

                            # Load package from apm.yml in install path
                            apm_yml_path = install_path / "apm.yml"
                            if apm_yml_path.exists():
                                cached_package = APMPackage.from_apm_yml(apm_yml_path)
                                # Ensure source is set to the repo URL for sync matching
                                if not cached_package.source:
                                    cached_package.source = dep_ref.repo_url
                            else:
                                # Virtual package or no apm.yml - create minimal package
                                cached_package = APMPackage(
                                    name=dep_ref.repo_url.split("/")[-1],
                                    version="unknown",
                                    package_path=install_path,
                                    source=dep_ref.repo_url,
                                )

                            # Create basic resolved reference for cached packages
                            resolved_ref = ResolvedReference(
                                original_ref=dep_ref.reference or "default",
                                ref_type=GitReferenceType.BRANCH,
                                resolved_commit="cached",  # Mark as cached since we don't know exact commit
                                ref_name=dep_ref.reference or "default",
                            )

                            cached_package_info = PackageInfo(
                                package=cached_package,
                                install_path=install_path,
                                resolved_reference=resolved_ref,
                                installed_at=datetime.now().isoformat(),
                                dependency_ref=dep_ref,  # Store for canonical dependency string
                            )

                            # Detect package_type from disk contents so
                            # skill integration is not silently skipped
                            skill_md_exists = (install_path / "SKILL.md").exists()
                            apm_yml_exists = (install_path / "apm.yml").exists()
                            from apm_cli.utils.helpers import find_plugin_json
                            plugin_json_exists = find_plugin_json(install_path) is not None
                            if plugin_json_exists and not apm_yml_exists:
                                cached_package_info.package_type = PackageType.MARKETPLACE_PLUGIN
                            elif skill_md_exists and apm_yml_exists:
                                cached_package_info.package_type = PackageType.HYBRID
                            elif skill_md_exists:
                                cached_package_info.package_type = PackageType.CLAUDE_SKILL
                            elif apm_yml_exists:
                                cached_package_info.package_type = PackageType.APM_PACKAGE

                            # Collect for lockfile (cached packages still need to be tracked)
                            node = dependency_graph.dependency_tree.get_node(dep_ref.get_unique_key())
                            depth = node.depth if node else 1
                            resolved_by = node.parent.dependency_ref.repo_url if node and node.parent else None
                            # Get commit SHA: callback capture > existing lockfile > explicit reference
                            dep_key = dep_ref.get_unique_key()
                            cached_commit = callback_downloaded.get(dep_key)
                            if not cached_commit and existing_lockfile:
                                locked_dep = existing_lockfile.get_dependency(dep_key)
                                if locked_dep:
                                    cached_commit = locked_dep.resolved_commit
                            if not cached_commit:
                                cached_commit = dep_ref.reference
                            installed_packages.append((dep_ref, cached_commit, depth, resolved_by))
                            dep_deployed: builtins.list = []  # collect deployed paths for this package

                            # Track package type for lockfile
                            if hasattr(cached_package_info, 'package_type') and cached_package_info.package_type:
                                package_types[dep_key] = cached_package_info.package_type.value

                            # Pre-deploy security gate
                            if not _pre_deploy_security_scan(
                                install_path, diagnostics,
                                package_name=dep_key, force=force,
                            ):
                                package_deployed_files[dep_key] = []
                                continue

                            # VSCode + Claude + OpenCode integration (prompts + agents)
                            if integrate_vscode or integrate_claude or integrate_opencode:
                                # Integrate prompts
                                prompt_result = (
                                    prompt_integrator.integrate_package_prompts(
                                        cached_package_info, project_root,
                                        force=force, managed_files=managed_files,
                                        diagnostics=diagnostics,
                                    )
                                )
                                if prompt_result.files_integrated > 0:
                                    total_prompts_integrated += (
                                        prompt_result.files_integrated
                                    )
                                    _rich_info(
                                        f"  └─ {prompt_result.files_integrated} prompts integrated → .github/prompts/"
                                    )
                                if prompt_result.files_updated > 0:
                                    _rich_info(
                                        f"  └─ {prompt_result.files_updated} prompts updated"
                                    )
                                # Track links resolved
                                total_links_resolved += prompt_result.links_resolved
                                for tp in prompt_result.target_paths:
                                    dep_deployed.append(tp.relative_to(project_root).as_posix())

                                # Integrate agents
                                agent_result = (
                                    agent_integrator.integrate_package_agents(
                                        cached_package_info, project_root,
                                        force=force, managed_files=managed_files,
                                        diagnostics=diagnostics,
                                    )
                                )
                                if agent_result.files_integrated > 0:
                                    total_agents_integrated += (
                                        agent_result.files_integrated
                                    )
                                    _rich_info(
                                        f"  └─ {agent_result.files_integrated} agents integrated → .github/agents/"
                                    )
                                if agent_result.files_updated > 0:
                                    _rich_info(
                                        f"  └─ {agent_result.files_updated} agents updated"
                                    )
                                # Track links resolved
                                total_links_resolved += agent_result.links_resolved
                                for tp in agent_result.target_paths:
                                    dep_deployed.append(tp.relative_to(project_root).as_posix())

                            # Skill integration (works for VSCode, Claude, and OpenCode)
                            # Skills go to .github/skills/ (primary) and .claude/skills/ (if .claude/ exists)
                            if integrate_vscode or integrate_claude or integrate_opencode:
                                skill_result = skill_integrator.integrate_package_skill(
                                    cached_package_info, project_root,
                                    diagnostics=diagnostics, managed_files=managed_files, force=force,
                                )
                                if skill_result.skill_created:
                                    total_skills_integrated += 1
                                    _rich_info(
                                        f"  └─ Skill integrated → .github/skills/"
                                    )
                                if skill_result.sub_skills_promoted > 0:
                                    total_sub_skills_promoted += skill_result.sub_skills_promoted
                                    _rich_info(
                                        f"  └─ {skill_result.sub_skills_promoted} skill(s) integrated → .github/skills/"
                                    )
                                for tp in skill_result.target_paths:
                                    dep_deployed.append(tp.relative_to(project_root).as_posix())

                            # Integrate instructions → .github/instructions/
                            if integrate_vscode:
                                instruction_result = (
                                    instruction_integrator.integrate_package_instructions(
                                        cached_package_info, project_root,
                                        force=force, managed_files=managed_files,
                                        diagnostics=diagnostics,
                                    )
                                )
                                if instruction_result.files_integrated > 0:
                                    total_instructions_integrated += (
                                        instruction_result.files_integrated
                                    )
                                    _rich_info(
                                        f"  └─ {instruction_result.files_integrated} instruction(s) integrated → .github/instructions/"
                                    )
                                total_links_resolved += instruction_result.links_resolved
                                for tp in instruction_result.target_paths:
                                    dep_deployed.append(tp.relative_to(project_root).as_posix())

                            # Integrate instructions → .cursor/rules/
                            cursor_rules_result = (
                                instruction_integrator.integrate_package_instructions_cursor(
                                    cached_package_info, project_root,
                                    force=force, managed_files=managed_files,
                                    diagnostics=diagnostics,
                                )
                            )
                            if cursor_rules_result.files_integrated > 0:
                                total_instructions_integrated += (
                                    cursor_rules_result.files_integrated
                                )
                                _rich_info(
                                    f"  └─ {cursor_rules_result.files_integrated} rule(s) integrated → .cursor/rules/"
                                )
                            total_links_resolved += cursor_rules_result.links_resolved
                            for tp in cursor_rules_result.target_paths:
                                dep_deployed.append(tp.relative_to(project_root).as_posix())

                            # Claude-specific integration (agents + commands)
                            if integrate_claude:
                                # Integrate agents to .claude/agents/
                                claude_agent_result = (
                                    agent_integrator.integrate_package_agents_claude(
                                        cached_package_info, project_root,
                                        force=force, managed_files=managed_files,
                                        diagnostics=diagnostics,
                                    )
                                )
                                if claude_agent_result.files_integrated > 0:
                                    total_agents_integrated += (
                                        claude_agent_result.files_integrated
                                    )
                                    _rich_info(
                                        f"  └─ {claude_agent_result.files_integrated} agents integrated → .claude/agents/"
                                    )
                                total_links_resolved += claude_agent_result.links_resolved
                                for tp in claude_agent_result.target_paths:
                                    dep_deployed.append(tp.relative_to(project_root).as_posix())

                            # Cursor agents (.cursor/agents/) — opt-in
                            cursor_agent_result = (
                                agent_integrator.integrate_package_agents_cursor(
                                    cached_package_info, project_root,
                                    force=force, managed_files=managed_files,
                                    diagnostics=diagnostics,
                                )
                            )
                            if cursor_agent_result.files_integrated > 0:
                                total_agents_integrated += (
                                    cursor_agent_result.files_integrated
                                )
                                _rich_info(
                                    f"  └─ {cursor_agent_result.files_integrated} agents integrated → .cursor/agents/"
                                )
                            total_links_resolved += cursor_agent_result.links_resolved
                            for tp in cursor_agent_result.target_paths:
                                dep_deployed.append(tp.relative_to(project_root).as_posix())

                            # OpenCode agents (.opencode/agents/) — opt-in
                            opencode_agent_result = (
                                agent_integrator.integrate_package_agents_opencode(
                                    cached_package_info, project_root,
                                    force=force, managed_files=managed_files,
                                    diagnostics=diagnostics,
                                )
                            )
                            if opencode_agent_result.files_integrated > 0:
                                total_agents_integrated += (
                                    opencode_agent_result.files_integrated
                                )
                                _rich_info(
                                    f"  └─ {opencode_agent_result.files_integrated} agents integrated → .opencode/agents/"
                                )
                            total_links_resolved += opencode_agent_result.links_resolved
                            for tp in opencode_agent_result.target_paths:
                                dep_deployed.append(tp.relative_to(project_root).as_posix())

                            # Claude-specific integration (commands)
                            if integrate_claude:
                                command_result = (
                                    command_integrator.integrate_package_commands(
                                        cached_package_info, project_root,
                                        force=force, managed_files=managed_files,
                                        diagnostics=diagnostics,
                                    )
                                )
                                if command_result.files_integrated > 0:
                                    total_commands_integrated += (
                                        command_result.files_integrated
                                    )
                                    _rich_info(
                                        f"  └─ {command_result.files_integrated} commands integrated → .claude/commands/"
                                    )
                                if command_result.files_updated > 0:
                                    _rich_info(
                                        f"  └─ {command_result.files_updated} commands updated"
                                    )
                                total_links_resolved += command_result.links_resolved
                                for tp in command_result.target_paths:
                                    dep_deployed.append(tp.relative_to(project_root).as_posix())

                            # OpenCode commands (.opencode/commands/) — opt-in
                            opencode_command_result = (
                                command_integrator.integrate_package_commands_opencode(
                                    cached_package_info, project_root,
                                    force=force, managed_files=managed_files,
                                    diagnostics=diagnostics,
                                )
                            )
                            if opencode_command_result.files_integrated > 0:
                                total_commands_integrated += (
                                    opencode_command_result.files_integrated
                                )
                                _rich_info(
                                    f"  └─ {opencode_command_result.files_integrated} commands integrated → .opencode/commands/"
                                )
                            total_links_resolved += opencode_command_result.links_resolved
                            for tp in opencode_command_result.target_paths:
                                dep_deployed.append(tp.relative_to(project_root).as_posix())

                            # Hook integration (target-aware)
                            if integrate_vscode:
                                hook_result = hook_integrator.integrate_package_hooks(
                                    cached_package_info, project_root,
                                    force=force, managed_files=managed_files,
                                    diagnostics=diagnostics,
                                )
                                if hook_result.hooks_integrated > 0:
                                    total_hooks_integrated += hook_result.hooks_integrated
                                    _rich_info(
                                        f"  └─ {hook_result.hooks_integrated} hook(s) integrated → .github/hooks/"
                                    )
                                for tp in hook_result.target_paths:
                                    dep_deployed.append(tp.relative_to(project_root).as_posix())
                            if integrate_claude:
                                hook_result_claude = hook_integrator.integrate_package_hooks_claude(
                                    cached_package_info, project_root,
                                    force=force, managed_files=managed_files,
                                    diagnostics=diagnostics,
                                )
                                if hook_result_claude.hooks_integrated > 0:
                                    total_hooks_integrated += hook_result_claude.hooks_integrated
                                    _rich_info(
                                        f"  └─ {hook_result_claude.hooks_integrated} hook(s) integrated → .claude/settings.json"
                                    )
                                for tp in hook_result_claude.target_paths:
                                    dep_deployed.append(tp.relative_to(project_root).as_posix())

                            # Cursor hooks (.cursor/hooks.json)
                            hook_result_cursor = hook_integrator.integrate_package_hooks_cursor(
                                cached_package_info, project_root,
                                force=force, managed_files=managed_files,
                                diagnostics=diagnostics,
                            )
                            if hook_result_cursor.hooks_integrated > 0:
                                total_hooks_integrated += hook_result_cursor.hooks_integrated
                                _rich_info(
                                    f"  └─ {hook_result_cursor.hooks_integrated} hook(s) integrated → .cursor/hooks.json"
                                )
                            for tp in hook_result_cursor.target_paths:
                                dep_deployed.append(tp.relative_to(project_root).as_posix())

                            # Record deployed files for this package
                            package_deployed_files[dep_key] = dep_deployed
                        except Exception as e:
                            # Don't fail installation if integration fails
                            diagnostics.error(
                                f"Failed to integrate primitives from cached package: {e}",
                                package=dep_key,
                            )

                    continue

                # Download the package with progress feedback
                try:
                    display_name = (
                        str(dep_ref) if dep_ref.is_virtual else dep_ref.repo_url
                    )
                    short_name = (
                        display_name.split("/")[-1]
                        if "/" in display_name
                        else display_name
                    )

                    # Create a progress task for this download
                    task_id = progress.add_task(
                        description=f"Fetching {short_name}",
                        total=None,  # Indeterminate initially; git will update with actual counts
                    )

                    # T5: Build download ref - use locked commit if available.
                    # build_download_ref() uses manifest ref when ref_changed is True.
                    download_ref = build_download_ref(
                        dep_ref, existing_lockfile, update_refs=update_refs, ref_changed=ref_changed
                    )

                    # Phase 4 (#171): Use pre-downloaded result if available
                    _dep_key = dep_ref.get_unique_key()
                    if _dep_key in _pre_download_results:
                        package_info = _pre_download_results[_dep_key]
                    else:
                        # Fallback: sequential download (should rarely happen)
                        package_info = downloader.download_package(
                            download_ref,
                            install_path,
                            progress_task_id=task_id,
                            progress_obj=progress,
                        )

                    # CRITICAL: Hide progress BEFORE printing success message to avoid overlap
                    progress.update(task_id, visible=False)
                    progress.refresh()  # Force immediate refresh to hide the bar

                    installed_count += 1

                    # Show resolved ref alongside package name for visibility
                    resolved = getattr(package_info, 'resolved_reference', None)
                    ref_suffix = f"#{resolved}" if resolved else ""
                    _rich_success(f"✓ {display_name}{ref_suffix}")

                    # Track unpinned deps for aggregated diagnostic
                    if not dep_ref.reference:
                        unpinned_count += 1

                    # Collect for lockfile: get resolved commit and depth
                    resolved_commit = None
                    if resolved:
                        resolved_commit = package_info.resolved_reference.resolved_commit
                    # Get depth from dependency tree
                    node = dependency_graph.dependency_tree.get_node(dep_ref.get_unique_key())
                    depth = node.depth if node else 1
                    resolved_by = node.parent.dependency_ref.repo_url if node and node.parent else None
                    installed_packages.append((dep_ref, resolved_commit, depth, resolved_by))
                    dep_deployed_fresh: builtins.list = []  # collect deployed paths for this package

                    # Track package type for lockfile
                    if hasattr(package_info, 'package_type') and package_info.package_type:
                        package_types[dep_ref.get_unique_key()] = package_info.package_type.value

                    # Show package type in verbose mode
                    if verbose and hasattr(package_info, "package_type"):
                        from apm_cli.models.apm_package import PackageType

                        package_type = package_info.package_type
                        if package_type == PackageType.CLAUDE_SKILL:
                            _rich_info(
                                f"  └─ Package type: Skill (SKILL.md detected)"
                            )
                        elif package_type == PackageType.MARKETPLACE_PLUGIN:
                            _rich_info(
                                f"  └─ Package type: Marketplace Plugin (plugin.json detected)"
                            )
                        elif package_type == PackageType.HYBRID:
                            _rich_info(
                                f"  └─ Package type: Hybrid (apm.yml + SKILL.md)"
                            )
                        elif package_type == PackageType.APM_PACKAGE:
                            _rich_info(f"  └─ Package type: APM Package (apm.yml)")

                    # Auto-integrate prompts and agents if enabled
                    # Pre-deploy security gate
                    if not _pre_deploy_security_scan(
                        package_info.install_path, diagnostics,
                        package_name=dep_ref.get_unique_key(), force=force,
                    ):
                        package_deployed_files[dep_ref.get_unique_key()] = []
                        continue

                    if integrate_vscode or integrate_claude or integrate_opencode:
                        try:
                            # Integrate prompts + agents (dual-target: .github/ + .claude/)
                            # Integrate prompts
                            prompt_result = (
                                prompt_integrator.integrate_package_prompts(
                                    package_info, project_root,
                                    force=force, managed_files=managed_files,
                                    diagnostics=diagnostics,
                                )
                            )
                            if prompt_result.files_integrated > 0:
                                total_prompts_integrated += (
                                    prompt_result.files_integrated
                                )
                                _rich_info(
                                    f"  └─ {prompt_result.files_integrated} prompts integrated → .github/prompts/"
                                )
                            if prompt_result.files_updated > 0:
                                _rich_info(
                                    f"  └─ {prompt_result.files_updated} prompts updated"
                                )
                            # Track links resolved
                            total_links_resolved += prompt_result.links_resolved
                            for tp in prompt_result.target_paths:
                                dep_deployed_fresh.append(tp.relative_to(project_root).as_posix())

                            # Integrate agents
                            agent_result = (
                                agent_integrator.integrate_package_agents(
                                    package_info, project_root,
                                    force=force, managed_files=managed_files,
                                    diagnostics=diagnostics,
                                )
                            )
                            if agent_result.files_integrated > 0:
                                total_agents_integrated += (
                                    agent_result.files_integrated
                                )
                                _rich_info(
                                    f"  └─ {agent_result.files_integrated} agents integrated → .github/agents/"
                                )
                            if agent_result.files_updated > 0:
                                _rich_info(
                                    f"  └─ {agent_result.files_updated} agents updated"
                                )
                            # Track links resolved
                            total_links_resolved += agent_result.links_resolved
                            for tp in agent_result.target_paths:
                                dep_deployed_fresh.append(tp.relative_to(project_root).as_posix())

                            # Skill integration (works for VSCode, Claude, and OpenCode)
                            # Skills go to .github/skills/ (primary) and .claude/skills/ (if .claude/ exists)
                            if integrate_vscode or integrate_claude or integrate_opencode:
                                skill_result = skill_integrator.integrate_package_skill(
                                    package_info, project_root,
                                    diagnostics=diagnostics, managed_files=managed_files, force=force,
                                )
                                if skill_result.skill_created:
                                    total_skills_integrated += 1
                                    _rich_info(
                                        f"  └─ Skill integrated → .github/skills/"
                                    )
                                if skill_result.sub_skills_promoted > 0:
                                    total_sub_skills_promoted += skill_result.sub_skills_promoted
                                    _rich_info(
                                        f"  └─ {skill_result.sub_skills_promoted} skill(s) integrated → .github/skills/"
                                    )
                                for tp in skill_result.target_paths:
                                    dep_deployed_fresh.append(tp.relative_to(project_root).as_posix())

                            # Integrate instructions → .github/instructions/
                            if integrate_vscode:
                                instruction_result = (
                                    instruction_integrator.integrate_package_instructions(
                                        package_info, project_root,
                                        force=force, managed_files=managed_files,
                                        diagnostics=diagnostics,
                                    )
                                )
                                if instruction_result.files_integrated > 0:
                                    total_instructions_integrated += (
                                        instruction_result.files_integrated
                                    )
                                    _rich_info(
                                        f"  └─ {instruction_result.files_integrated} instruction(s) integrated → .github/instructions/"
                                    )
                                total_links_resolved += instruction_result.links_resolved
                                for tp in instruction_result.target_paths:
                                    dep_deployed_fresh.append(tp.relative_to(project_root).as_posix())

                            # Integrate instructions → .cursor/rules/
                            cursor_rules_result = (
                                instruction_integrator.integrate_package_instructions_cursor(
                                    package_info, project_root,
                                    force=force, managed_files=managed_files,
                                    diagnostics=diagnostics,
                                )
                            )
                            if cursor_rules_result.files_integrated > 0:
                                total_instructions_integrated += (
                                    cursor_rules_result.files_integrated
                                )
                                _rich_info(
                                    f"  └─ {cursor_rules_result.files_integrated} rule(s) integrated → .cursor/rules/"
                                )
                            total_links_resolved += cursor_rules_result.links_resolved
                            for tp in cursor_rules_result.target_paths:
                                dep_deployed_fresh.append(tp.relative_to(project_root).as_posix())

                            # Claude-specific integration (agents + commands)
                            if integrate_claude:
                                # Integrate agents to .claude/agents/
                                claude_agent_result = (
                                    agent_integrator.integrate_package_agents_claude(
                                        package_info, project_root,
                                        force=force, managed_files=managed_files,
                                        diagnostics=diagnostics,
                                    )
                                )
                                if claude_agent_result.files_integrated > 0:
                                    total_agents_integrated += (
                                        claude_agent_result.files_integrated
                                    )
                                    _rich_info(
                                        f"  └─ {claude_agent_result.files_integrated} agents integrated → .claude/agents/"
                                    )
                                total_links_resolved += claude_agent_result.links_resolved
                                for tp in claude_agent_result.target_paths:
                                    dep_deployed_fresh.append(tp.relative_to(project_root).as_posix())

                            # Cursor agents (.cursor/agents/) — opt-in
                            cursor_agent_result = (
                                agent_integrator.integrate_package_agents_cursor(
                                    package_info, project_root,
                                    force=force, managed_files=managed_files,
                                    diagnostics=diagnostics,
                                )
                            )
                            if cursor_agent_result.files_integrated > 0:
                                total_agents_integrated += (
                                    cursor_agent_result.files_integrated
                                )
                                _rich_info(
                                    f"  └─ {cursor_agent_result.files_integrated} agents integrated → .cursor/agents/"
                                )
                            total_links_resolved += cursor_agent_result.links_resolved
                            for tp in cursor_agent_result.target_paths:
                                dep_deployed_fresh.append(tp.relative_to(project_root).as_posix())

                            # OpenCode agents (.opencode/agents/) — opt-in
                            opencode_agent_result = (
                                agent_integrator.integrate_package_agents_opencode(
                                    package_info, project_root,
                                    force=force, managed_files=managed_files,
                                    diagnostics=diagnostics,
                                )
                            )
                            if opencode_agent_result.files_integrated > 0:
                                total_agents_integrated += (
                                    opencode_agent_result.files_integrated
                                )
                                _rich_info(
                                    f"  └─ {opencode_agent_result.files_integrated} agents integrated → .opencode/agents/"
                                )
                            total_links_resolved += opencode_agent_result.links_resolved
                            for tp in opencode_agent_result.target_paths:
                                dep_deployed_fresh.append(tp.relative_to(project_root).as_posix())

                            # Claude-specific integration (commands)
                            if integrate_claude:
                                command_result = (
                                    command_integrator.integrate_package_commands(
                                        package_info, project_root,
                                        force=force, managed_files=managed_files,
                                        diagnostics=diagnostics,
                                    )
                                )
                                if command_result.files_integrated > 0:
                                    total_commands_integrated += (
                                        command_result.files_integrated
                                    )
                                    _rich_info(
                                        f"  └─ {command_result.files_integrated} commands integrated → .claude/commands/"
                                    )
                                if command_result.files_updated > 0:
                                    _rich_info(
                                        f"  └─ {command_result.files_updated} commands updated"
                                    )
                                total_links_resolved += command_result.links_resolved
                                for tp in command_result.target_paths:
                                    dep_deployed_fresh.append(tp.relative_to(project_root).as_posix())

                            # OpenCode commands (.opencode/commands/) — opt-in
                            opencode_command_result = (
                                command_integrator.integrate_package_commands_opencode(
                                    package_info, project_root,
                                    force=force, managed_files=managed_files,
                                    diagnostics=diagnostics,
                                )
                            )
                            if opencode_command_result.files_integrated > 0:
                                total_commands_integrated += (
                                    opencode_command_result.files_integrated
                                )
                                _rich_info(
                                    f"  └─ {opencode_command_result.files_integrated} commands integrated → .opencode/commands/"
                                )
                            total_links_resolved += opencode_command_result.links_resolved
                            for tp in opencode_command_result.target_paths:
                                dep_deployed_fresh.append(tp.relative_to(project_root).as_posix())

                            # Hook integration (target-aware)
                            if integrate_vscode:
                                hook_result = hook_integrator.integrate_package_hooks(
                                    package_info, project_root,
                                    force=force, managed_files=managed_files,
                                    diagnostics=diagnostics,
                                )
                                if hook_result.hooks_integrated > 0:
                                    total_hooks_integrated += hook_result.hooks_integrated
                                    _rich_info(
                                        f"  └─ {hook_result.hooks_integrated} hook(s) integrated → .github/hooks/"
                                    )
                                for tp in hook_result.target_paths:
                                    dep_deployed_fresh.append(tp.relative_to(project_root).as_posix())
                            if integrate_claude:
                                hook_result_claude = hook_integrator.integrate_package_hooks_claude(
                                    package_info, project_root,
                                    force=force, managed_files=managed_files,
                                    diagnostics=diagnostics,
                                )
                                if hook_result_claude.hooks_integrated > 0:
                                    total_hooks_integrated += hook_result_claude.hooks_integrated
                                    _rich_info(
                                        f"  └─ {hook_result_claude.hooks_integrated} hook(s) integrated → .claude/settings.json"
                                    )
                                for tp in hook_result_claude.target_paths:
                                    dep_deployed_fresh.append(tp.relative_to(project_root).as_posix())

                            # Cursor hooks (.cursor/hooks.json)
                            hook_result_cursor = hook_integrator.integrate_package_hooks_cursor(
                                package_info, project_root,
                                force=force, managed_files=managed_files,
                                diagnostics=diagnostics,
                            )
                            if hook_result_cursor.hooks_integrated > 0:
                                total_hooks_integrated += hook_result_cursor.hooks_integrated
                                _rich_info(
                                    f"  └─ {hook_result_cursor.hooks_integrated} hook(s) integrated → .cursor/hooks.json"
                                )
                            for tp in hook_result_cursor.target_paths:
                                dep_deployed_fresh.append(tp.relative_to(project_root).as_posix())

                            # Record deployed files for this package
                            package_deployed_files[dep_ref.get_unique_key()] = dep_deployed_fresh
                        except Exception as e:
                            # Don't fail installation if integration fails
                            diagnostics.error(
                                f"Failed to integrate primitives: {e}",
                                package=dep_ref.get_unique_key(),
                            )

                except Exception as e:
                    display_name = (
                        str(dep_ref) if dep_ref.is_virtual else dep_ref.repo_url
                    )
                    # Remove the progress task on error
                    if "task_id" in locals():
                        progress.remove_task(task_id)
                    diagnostics.error(
                        f"Failed to install {display_name}: {e}",
                        package=dep_ref.get_unique_key(),
                    )
                    # Continue with other packages instead of failing completely
                    continue

        # Update .gitignore
        _update_gitignore_for_apm_modules()

        # ------------------------------------------------------------------
        # Orphan cleanup: remove deployed files for packages that were
        # removed from the manifest.  This happens on every full install
        # (no only_packages), making apm install idempotent with the manifest.
        # Handles both regular files and directory entries (e.g., legacy skills).
        # ------------------------------------------------------------------
        if orphaned_deployed_files:
            import shutil as _shutil
            _removed_orphan_count = 0
            _failed_orphan_count = 0
            _deleted_orphan_paths: builtins.list = []
            for _orphan_path in sorted(orphaned_deployed_files):
                # validate_deploy_path() is the safety gate: it rejects path-traversal,
                # requires .github/ or .claude/ prefix, and checks the resolved path
                # stays within project_root — so rmtree is safe here.
                if BaseIntegrator.validate_deploy_path(_orphan_path, project_root):
                    _target = project_root / _orphan_path
                    if _target.exists():
                        try:
                            if _target.is_dir():
                                _shutil.rmtree(_target)
                            else:
                                _target.unlink()
                            _deleted_orphan_paths.append(_target)
                            _removed_orphan_count += 1
                        except Exception as _orphan_err:
                            _rich_warning(
                                f"  └─ Could not remove orphaned path {_orphan_path}: {_orphan_err}"
                            )
                            _failed_orphan_count += 1
            # Clean up empty parent directories left after file removal
            if _deleted_orphan_paths:
                BaseIntegrator.cleanup_empty_parents(_deleted_orphan_paths, project_root)
            if _removed_orphan_count > 0:
                _rich_info(
                    f"Removed {_removed_orphan_count} file(s) from packages "
                    "no longer in apm.yml"
                )

        # Generate apm.lock for reproducible installs (T4: lockfile generation)
        if installed_packages:
            try:
                lockfile = LockFile.from_installed_packages(installed_packages, dependency_graph)
                # Attach deployed_files and package_type to each LockedDependency
                for dep_key, dep_files in package_deployed_files.items():
                    if dep_key in lockfile.dependencies:
                        lockfile.dependencies[dep_key].deployed_files = dep_files
                for dep_key, pkg_type in package_types.items():
                    if dep_key in lockfile.dependencies:
                        lockfile.dependencies[dep_key].package_type = pkg_type
                # Selectively merge entries from the existing lockfile:
                #   - For partial installs (only_packages): preserve all old entries
                #     (sequential install — only the specified package was processed).
                #   - For full installs: only preserve entries for packages still in
                #     the manifest that failed to download (in intended_dep_keys but
                #     not in the new lockfile due to a download error).
                #   - Orphaned entries (not in intended_dep_keys) are intentionally
                #     dropped so the lockfile matches the manifest.
                # Skip merge entirely when update_refs is set — stale entries must not survive.
                if existing_lockfile and not update_refs:
                    for dep_key, dep in existing_lockfile.dependencies.items():
                        if dep_key not in lockfile.dependencies:
                            if only_packages or dep_key in intended_dep_keys:
                                # Preserve: partial install (sequential install support)
                                # OR package still in manifest but failed to download.
                                lockfile.dependencies[dep_key] = dep
                            # else: orphan — package was in lockfile but is no longer in
                            # the manifest (full install only). Don't preserve so the
                            # lockfile stays in sync with what apm.yml declares.
                lockfile_path = get_lockfile_path(project_root)

                # When installing a subset of packages (apm install <pkg>),
                # merge new entries into the existing lockfile instead of
                # overwriting it — otherwise the uninstalled packages disappear.
                if only_packages:
                    existing = LockFile.read(lockfile_path)
                    if existing:
                        for key, dep in lockfile.dependencies.items():
                            existing.add_dependency(dep)
                        lockfile = existing

                lockfile.save(lockfile_path)
                _rich_info(f"Generated apm.lock.yaml with {len(lockfile.dependencies)} dependencies")
            except Exception as e:
                _rich_warning(f"Could not generate apm.lock.yaml: {e}")

        # Show link resolution stats if any were resolved
        if total_links_resolved > 0:
            _rich_info(f"✓ Resolved {total_links_resolved} context file links")

        # Show Claude commands stats if any were integrated
        if total_commands_integrated > 0:
            _rich_info(f"✓ Integrated {total_commands_integrated} command(s)")

        # Show hooks stats if any were integrated
        if total_hooks_integrated > 0:
            _rich_info(f"✓ Integrated {total_hooks_integrated} hook(s)")

        # Show instructions stats if any were integrated
        if total_instructions_integrated > 0:
            _rich_info(f"✓ Integrated {total_instructions_integrated} instruction(s)")

        _rich_success(f"Installed {installed_count} APM dependencies")

        if unpinned_count:
            noun = "dependency has" if unpinned_count == 1 else "dependencies have"
            diagnostics.info(
                f"{unpinned_count} {noun} no pinned version "
                f"-- pin with #tag or #sha to prevent drift"
            )

        return installed_count, total_prompts_integrated, total_agents_integrated, diagnostics

    except Exception as e:
        raise RuntimeError(f"Failed to resolve APM dependencies: {e}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def _show_install_summary(
    apm_count: int, prompt_count: int, agent_count: int, mcp_count: int, apm_config
):
    """Show post-install summary.

    Args:
        apm_count: Number of APM packages installed
        prompt_count: Number of prompts integrated
        agent_count: Number of agents integrated
        mcp_count: Number of MCP servers configured
        apm_config: The apm.yml configuration dict
    """
    parts = []
    if apm_count > 0:
        parts.append(f"{apm_count} APM package(s)")
    if mcp_count > 0:
        parts.append(f"{mcp_count} MCP server(s)")
    if parts:
        _rich_success(f"Installation complete: {', '.join(parts)}")
    else:
        _rich_success("Installation complete")
