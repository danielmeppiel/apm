"""APM uninstall engine — validation, removal, and cleanup helpers."""

import builtins
import shutil
from pathlib import Path

from ...constants import APM_MODULES_DIR, APM_YML_FILENAME
from ...utils.console import _rich_error, _rich_info, _rich_success, _rich_warning

# APM Dependencies
try:
    from ...deps.lockfile import LockFile
    from ...models.apm_package import APMPackage, DependencyReference
    from ...integration.mcp_integrator import MCPIntegrator

    APM_DEPS_AVAILABLE = True
except ImportError:
    APM_DEPS_AVAILABLE = False


def _parse_dependency_entry(dep_entry):
    """Parse a dependency entry from apm.yml into a DependencyReference."""
    if isinstance(dep_entry, DependencyReference):
        return dep_entry
    if isinstance(dep_entry, str):
        return DependencyReference.parse(dep_entry)
    if isinstance(dep_entry, builtins.dict):
        return DependencyReference.parse_from_dict(dep_entry)
    raise ValueError(f"Unsupported dependency entry type: {type(dep_entry).__name__}")


def _validate_uninstall_packages(packages, current_deps):
    """Validate which packages can be removed and return matched/unmatched lists."""
    packages_to_remove = []
    packages_not_found = []

    for package in packages:
        if "/" not in package:
            _rich_error(f"Invalid package format: {package}. Use 'owner/repo' format.")
            continue

        matched_dep = None
        try:
            pkg_ref = DependencyReference.parse(package)
            pkg_identity = pkg_ref.get_identity()
        except Exception:
            pkg_identity = package

        for dep_entry in current_deps:
            try:
                dep_ref = _parse_dependency_entry(dep_entry)
                if dep_ref.get_identity() == pkg_identity:
                    matched_dep = dep_entry
                    break
            except (ValueError, TypeError, AttributeError, KeyError):
                dep_str = dep_entry if isinstance(dep_entry, str) else str(dep_entry)
                if dep_str == package:
                    matched_dep = dep_entry
                    break

        if matched_dep is not None:
            packages_to_remove.append(matched_dep)
            _rich_info(f"\u2713 {package} - found in apm.yml")
        else:
            packages_not_found.append(package)
            _rich_warning(f"\u2717 {package} - not found in apm.yml")

    return packages_to_remove, packages_not_found


def _dry_run_uninstall(packages_to_remove, apm_modules_dir):
    """Show what would be removed without making changes."""
    _rich_info(f"Dry run: Would remove {len(packages_to_remove)} package(s):")
    for pkg in packages_to_remove:
        _rich_info(f"  - {pkg} from apm.yml")
        try:
            dep_ref = _parse_dependency_entry(pkg)
            package_path = dep_ref.get_install_path(apm_modules_dir)
        except (ValueError, TypeError, AttributeError, KeyError):
            pkg_str = pkg if isinstance(pkg, str) else str(pkg)
            package_path = apm_modules_dir / pkg_str.split("/")[-1]
        if apm_modules_dir.exists() and package_path.exists():
            _rich_info(f"  - {pkg} from apm_modules/")

    from ...deps.lockfile import LockFile, get_lockfile_path
    lockfile_path = get_lockfile_path(Path("."))
    lockfile = LockFile.read(lockfile_path)
    if lockfile:
        removed_repo_urls = builtins.set()
        for pkg in packages_to_remove:
            try:
                ref = _parse_dependency_entry(pkg)
                removed_repo_urls.add(ref.repo_url)
            except (ValueError, TypeError, AttributeError, KeyError):
                removed_repo_urls.add(pkg)
        queue = builtins.list(removed_repo_urls)
        potential_orphans = builtins.set()
        while queue:
            parent_url = queue.pop()
            for dep in lockfile.get_all_dependencies():
                key = dep.get_unique_key()
                if key in potential_orphans:
                    continue
                if dep.resolved_by and dep.resolved_by == parent_url:
                    potential_orphans.add(key)
                    queue.append(dep.repo_url)
        if potential_orphans:
            _rich_info(f"  Transitive dependencies that would be removed:")
            for orphan_key in sorted(potential_orphans):
                _rich_info(f"    - {orphan_key}")

    _rich_success("Dry run complete - no changes made")


def _remove_packages_from_disk(packages_to_remove, apm_modules_dir):
    """Remove direct packages from apm_modules/ and return removal count."""
    removed = 0
    if not apm_modules_dir.exists():
        return removed

    deleted_pkg_paths = []
    for package in packages_to_remove:
        try:
            dep_ref = _parse_dependency_entry(package)
            package_path = dep_ref.get_install_path(apm_modules_dir)
        except (ValueError, TypeError, AttributeError, KeyError):
            package_str = package if isinstance(package, str) else str(package)
            repo_parts = package_str.split("/")
            if len(repo_parts) >= 2:
                package_path = apm_modules_dir.joinpath(*repo_parts)
            else:
                package_path = apm_modules_dir / package_str

        if package_path.exists():
            try:
                shutil.rmtree(package_path)
                _rich_info(f"\u2713 Removed {package} from apm_modules/")
                removed += 1
                deleted_pkg_paths.append(package_path)
            except Exception as e:
                _rich_error(f"\u2717 Failed to remove {package} from apm_modules/: {e}")
        else:
            _rich_warning(f"Package {package} not found in apm_modules/")

    from ...integration.base_integrator import BaseIntegrator as _BI2
    _BI2.cleanup_empty_parents(deleted_pkg_paths, stop_at=apm_modules_dir)
    return removed


def _cleanup_transitive_orphans(lockfile, packages_to_remove, apm_modules_dir, apm_yml_path):
    """Remove orphaned transitive deps and return (removed_count, actual_orphan_keys)."""
    import yaml

    if not lockfile or not apm_modules_dir.exists():
        return 0, builtins.set()

    removed_repo_urls = builtins.set()
    for pkg in packages_to_remove:
        try:
            ref = _parse_dependency_entry(pkg)
            removed_repo_urls.add(ref.repo_url)
        except (ValueError, TypeError, AttributeError, KeyError):
            removed_repo_urls.add(pkg)

    # Find transitive orphans recursively
    orphans = builtins.set()
    queue = builtins.list(removed_repo_urls)
    while queue:
        parent_url = queue.pop()
        for dep in lockfile.get_all_dependencies():
            key = dep.get_unique_key()
            if key in orphans:
                continue
            if dep.resolved_by and dep.resolved_by == parent_url:
                orphans.add(key)
                queue.append(dep.repo_url)

    if not orphans:
        return 0, builtins.set()

    # Determine remaining deps to avoid removing still-needed packages
    remaining_deps = builtins.set()
    try:
        with open(apm_yml_path, "r") as f:
            updated_data = yaml.safe_load(f) or {}
        for dep_str in updated_data.get("dependencies", {}).get("apm", []) or []:
            try:
                ref = _parse_dependency_entry(dep_str)
                remaining_deps.add(ref.get_unique_key())
            except (ValueError, TypeError, AttributeError, KeyError):
                remaining_deps.add(dep_str)
    except Exception:
        pass

    for dep in lockfile.get_all_dependencies():
        key = dep.get_unique_key()
        if key not in orphans and dep.repo_url not in removed_repo_urls:
            remaining_deps.add(key)

    actual_orphans = orphans - remaining_deps
    removed = 0
    deleted_orphan_paths = []
    for orphan_key in actual_orphans:
        orphan_dep = lockfile.get_dependency(orphan_key)
        if not orphan_dep:
            continue
        try:
            orphan_ref = DependencyReference.parse(orphan_key)
            orphan_path = orphan_ref.get_install_path(apm_modules_dir)
        except ValueError:
            parts = orphan_key.split("/")
            orphan_path = apm_modules_dir.joinpath(*parts) if len(parts) >= 2 else apm_modules_dir / orphan_key

        if orphan_path.exists():
            try:
                shutil.rmtree(orphan_path)
                _rich_info(f"\u2713 Removed transitive dependency {orphan_key} from apm_modules/")
                removed += 1
                deleted_orphan_paths.append(orphan_path)
            except Exception as e:
                _rich_error(f"\u2717 Failed to remove transitive dep {orphan_key}: {e}")

    from ...integration.base_integrator import BaseIntegrator as _BI
    _BI.cleanup_empty_parents(deleted_orphan_paths, stop_at=apm_modules_dir)
    return removed, actual_orphans


def _sync_integrations_after_uninstall(apm_package, project_root, all_deployed_files):
    """Remove deployed files and re-integrate from remaining packages."""
    from ...integration.base_integrator import BaseIntegrator
    from ...models.apm_package import PackageInfo, validate_apm_package
    from ...integration.prompt_integrator import PromptIntegrator
    from ...integration.agent_integrator import AgentIntegrator
    from ...integration.skill_integrator import SkillIntegrator
    from ...integration.command_integrator import CommandIntegrator
    from ...integration.hook_integrator import HookIntegrator
    from ...integration.instruction_integrator import InstructionIntegrator

    sync_managed = all_deployed_files if all_deployed_files else None
    if sync_managed is not None:
        _buckets = BaseIntegrator.partition_managed_files(sync_managed)
    else:
        _buckets = None

    counts = {"prompts": 0, "agents": 0, "skills": 0, "commands": 0, "hooks": 0, "instructions": 0}

    # Phase 1: Remove all APM-deployed files
    if Path(".github/prompts").exists():
        integrator = PromptIntegrator()
        result = integrator.sync_integration(apm_package, project_root,
                                             managed_files=_buckets["prompts"] if _buckets else None)
        counts["prompts"] = result.get("files_removed", 0)

    if Path(".github/agents").exists():
        integrator = AgentIntegrator()
        result = integrator.sync_integration(apm_package, project_root,
                                             managed_files=_buckets["agents_github"] if _buckets else None)
        counts["agents"] = result.get("files_removed", 0)

    if Path(".claude/agents").exists():
        integrator = AgentIntegrator()
        result = integrator.sync_integration_claude(apm_package, project_root,
                                                    managed_files=_buckets["agents_claude"] if _buckets else None)
        counts["agents"] += result.get("files_removed", 0)

    if Path(".github/skills").exists() or Path(".claude/skills").exists():
        integrator = SkillIntegrator()
        result = integrator.sync_integration(apm_package, project_root,
                                             managed_files=_buckets["skills"] if _buckets else None)
        counts["skills"] = result.get("files_removed", 0)

    if Path(".claude/commands").exists():
        integrator = CommandIntegrator()
        result = integrator.sync_integration(apm_package, project_root,
                                             managed_files=_buckets["commands"] if _buckets else None)
        counts["commands"] = result.get("files_removed", 0)

    hook_integrator_cleanup = HookIntegrator()
    result = hook_integrator_cleanup.sync_integration(apm_package, project_root,
                                                      managed_files=_buckets["hooks"] if _buckets else None)
    counts["hooks"] = result.get("files_removed", 0)

    if Path(".github/instructions").exists():
        integrator = InstructionIntegrator()
        result = integrator.sync_integration(apm_package, project_root,
                                             managed_files=_buckets["instructions"] if _buckets else None)
        counts["instructions"] = result.get("files_removed", 0)

    # Phase 2: Re-integrate from remaining installed packages
    from ...core.target_detection import detect_target, should_integrate_claude
    config_target = apm_package.target
    detected_target, _ = detect_target(
        project_root=project_root, explicit_target=None, config_target=config_target,
    )
    integrate_claude = should_integrate_claude(detected_target)

    prompt_integrator = PromptIntegrator()
    agent_integrator = AgentIntegrator()
    skill_integrator = SkillIntegrator()
    command_integrator = CommandIntegrator()
    hook_integrator_reint = HookIntegrator()
    instruction_integrator_reint = InstructionIntegrator()

    for dep in apm_package.get_apm_dependencies():
        dep_ref = dep if hasattr(dep, 'repo_url') else None
        if not dep_ref:
            continue
        install_path = dep_ref.get_install_path(Path(APM_MODULES_DIR))
        if not install_path.exists():
            continue

        result = validate_apm_package(install_path)
        pkg = result.package if result and result.package else None
        if not pkg:
            continue
        pkg_info = PackageInfo(
            package=pkg, install_path=install_path,
            dependency_ref=dep_ref,
            package_type=result.package_type if result else None,
        )

        try:
            if prompt_integrator.should_integrate(project_root):
                prompt_integrator.integrate_package_prompts(pkg_info, project_root)
            if agent_integrator.should_integrate(project_root):
                agent_integrator.integrate_package_agents(pkg_info, project_root)
                if integrate_claude:
                    agent_integrator.integrate_package_agents_claude(pkg_info, project_root)
            skill_integrator.integrate_package_skill(pkg_info, project_root)
            if integrate_claude:
                command_integrator.integrate_package_commands(pkg_info, project_root)
            hook_integrator_reint.integrate_package_hooks(pkg_info, project_root)
            if integrate_claude:
                hook_integrator_reint.integrate_package_hooks_claude(pkg_info, project_root)
            instruction_integrator_reint.integrate_package_instructions(pkg_info, project_root)
        except Exception:
            pass  # Best effort re-integration

    return counts


def _cleanup_stale_mcp(apm_package, lockfile, lockfile_path, old_mcp_servers):
    """Remove MCP servers that are no longer needed after uninstall."""
    if not old_mcp_servers:
        return
    apm_modules_path = Path.cwd() / APM_MODULES_DIR
    remaining_mcp = MCPIntegrator.collect_transitive(apm_modules_path, lockfile_path, trust_private=True)
    try:
        remaining_root_mcp = apm_package.get_mcp_dependencies()
    except Exception:
        remaining_root_mcp = []
    all_remaining_mcp = MCPIntegrator.deduplicate(remaining_root_mcp + remaining_mcp)
    new_mcp_servers = MCPIntegrator.get_server_names(all_remaining_mcp)
    stale_servers = old_mcp_servers - new_mcp_servers
    if stale_servers:
        MCPIntegrator.remove_stale(stale_servers)
    MCPIntegrator.update_lockfile(new_mcp_servers, lockfile_path)
