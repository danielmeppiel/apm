"""APM uninstall command."""

import builtins
import shutil
import sys
from pathlib import Path

import click

from ..utils.console import _rich_error, _rich_info, _rich_success, _rich_warning

# APM Dependencies
try:
    from ..deps.lockfile import LockFile
    from ..models.apm_package import APMPackage, DependencyReference
    from ..integration.mcp_integrator import MCPIntegrator

    APM_DEPS_AVAILABLE = True
except ImportError:
    APM_DEPS_AVAILABLE = False


@click.command(help="Remove APM packages, their integrated files, and apm.yml entries")
@click.argument("packages", nargs=-1, required=True)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be removed without removing"
)
@click.pass_context
def uninstall(ctx, packages, dry_run):
    """Remove APM packages from apm.yml and apm_modules (like npm uninstall).

    This command removes packages from both the apm.yml dependencies list
    and the apm_modules/ directory. It's the opposite of 'apm install <package>'.

    Examples:
        apm uninstall acme/my-package                # Remove one package
        apm uninstall org/pkg1 org/pkg2              # Remove multiple packages
        apm uninstall acme/my-package --dry-run      # Show what would be removed
    """
    try:
        # Check if apm.yml exists
        if not Path("apm.yml").exists():
            _rich_error("No apm.yml found. Run 'apm init' first.")
            sys.exit(1)

        if not packages:
            _rich_error("No packages specified. Specify packages to uninstall.")
            sys.exit(1)

        _rich_info(f"Uninstalling {len(packages)} package(s)...")

        # Read current apm.yml
        import yaml

        apm_yml_path = Path("apm.yml")
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
        packages_to_remove = []
        packages_not_found = []

        def _parse_dependency_entry(dep_entry):
            if isinstance(dep_entry, DependencyReference):
                return dep_entry
            if isinstance(dep_entry, str):
                return DependencyReference.parse(dep_entry)
            if isinstance(dep_entry, dict):
                return DependencyReference.parse_from_dict(dep_entry)
            raise ValueError(f"Unsupported dependency entry type: {type(dep_entry).__name__}")

        # Validate which packages can be removed
        for package in packages:
            # Validate package format (should be owner/repo or a git URL)
            if "/" not in package:
                _rich_error(
                    f"Invalid package format: {package}. Use 'owner/repo' format."
                )
                continue

            # Match by identity: parse the user input and each apm.yml entry,
            # compare using get_identity() which normalizes host differences.
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
                        matched_dep = dep_entry  # preserve original entry for removal
                        break
                except (ValueError, TypeError, AttributeError, KeyError):
                    # Fallback: exact string match
                    dep_str = dep_entry if isinstance(dep_entry, str) else str(dep_entry)
                    if dep_str == package:
                        matched_dep = dep_entry
                        break
                    pass

            if matched_dep is not None:
                packages_to_remove.append(matched_dep)
                _rich_info(f"+ {package} - found in apm.yml")
            else:
                packages_not_found.append(package)
                _rich_warning(f"x {package} - not found in apm.yml")

        if not packages_to_remove:
            _rich_warning("No packages found in apm.yml to remove")
            return

        if dry_run:
            _rich_info(f"Dry run: Would remove {len(packages_to_remove)} package(s):")
            apm_modules_dir = Path("apm_modules")
            for pkg in packages_to_remove:
                _rich_info(f"  - {pkg} from apm.yml")
                # Check if package exists in apm_modules
                try:
                    dep_ref = _parse_dependency_entry(pkg)
                    package_path = dep_ref.get_install_path(apm_modules_dir)
                except (ValueError, TypeError, AttributeError, KeyError):
                    pkg_str = pkg if isinstance(pkg, str) else str(pkg)
                    package_path = apm_modules_dir / pkg_str.split("/")[-1]
                if apm_modules_dir.exists() and package_path.exists():
                    _rich_info(f"  - {pkg} from apm_modules/")

            # Show transitive deps that would be removed
            from ..deps.lockfile import LockFile, get_lockfile_path
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
                # Find transitive orphans
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
            return

        # Remove packages from apm.yml
        for package in packages_to_remove:
            current_deps.remove(package)
            _rich_info(f"Removed {package} from apm.yml")

        # Update dependencies in apm.yml
        data["dependencies"]["apm"] = current_deps

        # Write back to apm.yml
        try:
            with open(apm_yml_path, "w") as f:
                yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
            _rich_success(
                f"Updated apm.yml (removed {len(packages_to_remove)} package(s))"
            )
        except Exception as e:
            _rich_error(f"Failed to write apm.yml: {e}")
            sys.exit(1)

        # Remove packages from apm_modules/
        apm_modules_dir = Path("apm_modules")
        removed_from_modules = 0

        # npm-style transitive dep cleanup: use lockfile to find orphaned transitive deps
        from ..deps.lockfile import LockFile, get_lockfile_path
        lockfile_path = get_lockfile_path(Path("."))
        lockfile = LockFile.read(lockfile_path)

        # Capture MCP servers from lockfile *before* it is mutated/deleted so
        # that stale-MCP cleanup can compute the diff even when all deps are removed.
        _pre_uninstall_mcp_servers = builtins.set(lockfile.mcp_servers) if lockfile else builtins.set()

        if apm_modules_dir.exists():
            deleted_pkg_paths: list = []
            for package in packages_to_remove:
                # Parse package into DependencyReference to get canonical install path
                # This correctly handles virtual packages (owner/repo-packagename) vs
                # regular packages (owner/repo) and ADO paths (org/project/repo)
                try:
                    dep_ref = _parse_dependency_entry(package)
                    package_path = dep_ref.get_install_path(apm_modules_dir)
                except (ValueError, TypeError, AttributeError, KeyError):
                    # Fallback for invalid format: use raw path segments
                    package_str = package if isinstance(package, str) else str(package)
                    repo_parts = package_str.split("/")
                    if len(repo_parts) >= 2:
                        package_path = apm_modules_dir.joinpath(*repo_parts)
                    else:
                        package_path = apm_modules_dir / package_str

                if package_path.exists():
                    try:
                        shutil.rmtree(package_path)
                        _rich_info(f"+ Removed {package} from apm_modules/")
                        removed_from_modules += 1
                        deleted_pkg_paths.append(package_path)
                    except Exception as e:
                        _rich_error(
                            f"x Failed to remove {package} from apm_modules/: {e}"
                        )
                else:
                    _rich_warning(f"Package {package} not found in apm_modules/")

            # Batch parent cleanup  -- single bottom-up pass
            from ..integration.base_integrator import BaseIntegrator as _BI2
            _BI2.cleanup_empty_parents(deleted_pkg_paths, stop_at=apm_modules_dir)

        # npm-style transitive dependency cleanup: remove orphaned transitive deps
        # After removing the direct packages, check if they had transitive deps that
        # are no longer needed by any remaining package.
        if lockfile and apm_modules_dir.exists():
            # Collect the repo_urls of removed packages
            removed_repo_urls = builtins.set()
            for pkg in packages_to_remove:
                try:
                    ref = _parse_dependency_entry(pkg)
                    removed_repo_urls.add(ref.repo_url)
                except (ValueError, TypeError, AttributeError, KeyError):
                    removed_repo_urls.add(pkg)

            # Find all transitive deps resolved_by any removed package (recursive)
            def _find_transitive_orphans(lockfile, removed_urls):
                """Recursively find all transitive deps that are no longer needed."""
                orphans = builtins.set()
                queue = builtins.list(removed_urls)
                while queue:
                    parent_url = queue.pop()
                    for dep in lockfile.get_all_dependencies():
                        key = dep.get_unique_key()
                        if key in orphans:
                            continue
                        if dep.resolved_by and dep.resolved_by == parent_url:
                            orphans.add(key)
                            # This orphan's own transitives are also orphaned
                            queue.append(dep.repo_url)
                return orphans

            potential_orphans = _find_transitive_orphans(lockfile, removed_repo_urls)

            if potential_orphans:
                # Check which orphans are still needed by remaining packages
                # Re-read updated apm.yml to get remaining deps
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

                # Also check remaining lockfile deps that are NOT orphaned
                for dep in lockfile.get_all_dependencies():
                    key = dep.get_unique_key()
                    if key not in potential_orphans and dep.repo_url not in removed_repo_urls:
                        remaining_deps.add(key)

                # Remove only true orphans (not needed by remaining deps)
                actual_orphans = potential_orphans - remaining_deps
                deleted_orphan_paths: list = []
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
                            _rich_info(f"+ Removed transitive dependency {orphan_key} from apm_modules/")
                            removed_from_modules += 1
                            deleted_orphan_paths.append(orphan_path)
                        except Exception as e:
                            _rich_error(f"x Failed to remove transitive dep {orphan_key}: {e}")

                # Batch parent cleanup  -- single bottom-up pass
                from ..integration.base_integrator import BaseIntegrator as _BI
                _BI.cleanup_empty_parents(deleted_orphan_paths, stop_at=apm_modules_dir)

        # Collect deployed_files only for REMOVED packages (direct + transitive)
        # so sync_integration doesn't iterate paths from packages still installed.
        from ..integration.base_integrator import BaseIntegrator
        removed_keys = builtins.set()
        for pkg in packages_to_remove:
            try:
                ref = _parse_dependency_entry(pkg)
                removed_keys.add(ref.get_unique_key())
            except (ValueError, TypeError, AttributeError, KeyError):
                removed_keys.add(pkg)
        if 'actual_orphans' in locals():
            removed_keys.update(actual_orphans)
        all_deployed_files = builtins.set()
        if lockfile:
            for dep_key, dep in lockfile.dependencies.items():
                if dep_key in removed_keys:
                    all_deployed_files.update(dep.deployed_files)
        # Normalize path separators once
        all_deployed_files = BaseIntegrator.normalize_managed_files(all_deployed_files) or builtins.set()

        # Update lockfile: remove entries for all removed packages (direct + transitive)
        removed_orphan_keys = builtins.set()
        if lockfile and apm_modules_dir.exists() and 'actual_orphans' in locals():
            removed_orphan_keys = actual_orphans
        if lockfile:
            lockfile_updated = False
            for pkg in packages_to_remove:
                try:
                    ref = _parse_dependency_entry(pkg)
                    key = ref.get_unique_key()
                except (ValueError, TypeError, AttributeError, KeyError):
                    key = pkg
                if key in lockfile.dependencies:
                    del lockfile.dependencies[key]
                    lockfile_updated = True
            # Also remove orphaned transitive deps from lockfile
            for orphan_key in removed_orphan_keys:
                if orphan_key in lockfile.dependencies:
                    del lockfile.dependencies[orphan_key]
                    lockfile_updated = True
            if lockfile_updated:
                try:
                    if lockfile.dependencies:
                        lockfile.write(lockfile_path)
                    else:
                        # No deps left  -- remove lockfile
                        lockfile_path.unlink(missing_ok=True)
                except Exception:
                    pass

        # Sync integrations: remove all deployed files and re-integrate from remaining packages
        prompts_cleaned = 0
        agents_cleaned = 0
        commands_cleaned = 0
        skills_cleaned = 0
        hooks_cleaned = 0
        instructions_cleaned = 0

        try:
            from ..models.apm_package import APMPackage, PackageInfo, PackageType, validate_apm_package
            from ..integration.prompt_integrator import PromptIntegrator
            from ..integration.agent_integrator import AgentIntegrator
            from ..integration.skill_integrator import SkillIntegrator
            from ..integration.command_integrator import CommandIntegrator
            from ..integration.hook_integrator import HookIntegrator
            from ..integration.instruction_integrator import InstructionIntegrator

            apm_package = APMPackage.from_apm_yml(Path("apm.yml"))
            project_root = Path(".")

            # Use pre-collected deployed_files (captured before lockfile entries were deleted)
            sync_managed = all_deployed_files if all_deployed_files else None

            # Pre-partition managed files by integration type  -- single O(M)
            # pass instead of 6x O(M) prefix scans inside each integrator.
            if sync_managed is not None:
                _buckets = BaseIntegrator.partition_managed_files(sync_managed)
            else:
                _buckets = None

            # Phase 1: Remove all APM-deployed files
            if Path(".github/prompts").exists():
                integrator = PromptIntegrator()
                result = integrator.sync_integration(apm_package, project_root,
                                                     managed_files=_buckets["prompts"] if _buckets else None)
                prompts_cleaned = result.get("files_removed", 0)

            if Path(".github/agents").exists():
                integrator = AgentIntegrator()
                result = integrator.sync_integration(apm_package, project_root,
                                                     managed_files=_buckets["agents_github"] if _buckets else None)
                agents_cleaned = result.get("files_removed", 0)

            if Path(".claude/agents").exists():
                integrator = AgentIntegrator()
                result = integrator.sync_integration_claude(apm_package, project_root,
                                                            managed_files=_buckets["agents_claude"] if _buckets else None)
                agents_cleaned += result.get("files_removed", 0)

            if Path(".github/skills").exists() or Path(".claude/skills").exists():
                integrator = SkillIntegrator()
                result = integrator.sync_integration(apm_package, project_root,
                                                     managed_files=_buckets["skills"] if _buckets else None)
                skills_cleaned = result.get("files_removed", 0)

            if Path(".claude/commands").exists():
                integrator = CommandIntegrator()
                result = integrator.sync_integration(apm_package, project_root,
                                                     managed_files=_buckets["commands"] if _buckets else None)
                commands_cleaned = result.get("files_removed", 0)

            # Clean hooks (.github/hooks/ and .claude/settings.json)
            hook_integrator_cleanup = HookIntegrator()
            result = hook_integrator_cleanup.sync_integration(apm_package, project_root,
                                                              managed_files=_buckets["hooks"] if _buckets else None)
            hooks_cleaned = result.get("files_removed", 0)

            # Clean instructions (.github/instructions/)
            if Path(".github/instructions").exists():
                integrator = InstructionIntegrator()
                result = integrator.sync_integration(apm_package, project_root,
                                                     managed_files=_buckets["instructions"] if _buckets else None)
                instructions_cleaned = result.get("files_removed", 0)

            # Phase 2: Re-integrate from remaining installed packages in apm_modules/
            # Detect target so we only re-create Claude artefacts when appropriate
            from ..core.target_detection import (
                detect_target,
                should_integrate_claude,
            )
            config_target = apm_package.target
            detected_target, _ = detect_target(
                project_root=project_root,
                explicit_target=None,
                config_target=config_target,
            )
            integrate_claude = should_integrate_claude(detected_target)

            prompt_integrator = PromptIntegrator()
            agent_integrator = AgentIntegrator()
            skill_integrator = SkillIntegrator()
            command_integrator = CommandIntegrator()
            hook_integrator_reint = HookIntegrator()
            instruction_integrator = InstructionIntegrator()

            for dep in apm_package.get_apm_dependencies():
                dep_ref = dep if hasattr(dep, 'repo_url') else None
                if not dep_ref:
                    continue
                install_path = dep_ref.get_install_path(Path("apm_modules"))
                if not install_path.exists():
                    continue

                # Build minimal PackageInfo for re-integration
                result = validate_apm_package(install_path)
                pkg = result.package if result and result.package else None
                if not pkg:
                    continue
                pkg_info = PackageInfo(
                    package=pkg,
                    install_path=install_path,
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
                    instruction_integrator.integrate_package_instructions(pkg_info, project_root)
                except Exception:
                    pass  # Best effort re-integration

        except Exception:
            pass  # Best effort cleanup  -- don't report false failures

        # Show cleanup feedback
        if prompts_cleaned > 0:
            _rich_info(f"+ Cleaned up {prompts_cleaned} integrated prompt(s)")
        if agents_cleaned > 0:
            _rich_info(f"+ Cleaned up {agents_cleaned} integrated agent(s)")
        if skills_cleaned > 0:
            _rich_info(f"+ Cleaned up {skills_cleaned} skill(s)")
        if commands_cleaned > 0:
            _rich_info(f"+ Cleaned up {commands_cleaned} command(s)")
        if hooks_cleaned > 0:
            _rich_info(f"+ Cleaned up {hooks_cleaned} hook(s)")
        if instructions_cleaned > 0:
            _rich_info(f"+ Cleaned up {instructions_cleaned} instruction(s)")

        # Clean up stale MCP servers after uninstall
        try:
            old_mcp_servers = _pre_uninstall_mcp_servers
            if old_mcp_servers:
                # Recompute MCP deps from remaining packages
                apm_modules_path = Path.cwd() / "apm_modules"
                remaining_mcp = MCPIntegrator.collect_transitive(apm_modules_path, lockfile_path, trust_private=True)
                # Also include root-level MCP deps from apm.yml
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
        except Exception:
            _rich_warning("MCP cleanup during uninstall failed")

        # Final summary
        summary_lines = []
        summary_lines.append(
            f"Removed {len(packages_to_remove)} package(s) from apm.yml"
        )
        if removed_from_modules > 0:
            summary_lines.append(
                f"Removed {removed_from_modules} package(s) from apm_modules/"
            )

        _rich_success("Uninstall complete: " + ", ".join(summary_lines))

        if packages_not_found:
            _rich_warning(
                f"Note: {len(packages_not_found)} package(s) were not found in apm.yml"
            )

    except Exception as e:
        _rich_error(f"Error uninstalling packages: {e}")
        sys.exit(1)
