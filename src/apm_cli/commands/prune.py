"""APM prune command."""

import shutil
import sys
from pathlib import Path

import click

from ..utils.console import _rich_error, _rich_info, _rich_success, _rich_warning
from ._helpers import _build_expected_install_paths, _scan_installed_packages

# APM Dependencies
from ..deps.lockfile import LockFile
from ..models.apm_package import APMPackage


@click.command(help="Remove APM packages not listed in apm.yml")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be removed without removing"
)
@click.pass_context
def prune(ctx, dry_run):
    """Remove installed APM packages that are not listed in apm.yml (like npm prune).

    This command cleans up the apm_modules/ directory by removing packages that
    were previously installed but are no longer declared as dependencies in apm.yml.

    Examples:
        apm prune           # Remove orphaned packages
        apm prune --dry-run # Show what would be removed
    """
    try:
        # Check if apm.yml exists
        if not Path("apm.yml").exists():
            _rich_error("No apm.yml found. Run 'apm init' first.")
            sys.exit(1)

        # Check if apm_modules exists
        apm_modules_dir = Path("apm_modules")
        if not apm_modules_dir.exists():
            _rich_info("No apm_modules/ directory found. Nothing to prune.")
            return

        _rich_info("Analyzing installed packages vs apm.yml...")

        # Build expected vs installed using shared helpers
        try:
            apm_package = APMPackage.from_apm_yml(Path("apm.yml"))
            declared_deps = apm_package.get_apm_dependencies()
            lockfile = LockFile.read(Path.cwd() / "apm.lock")
            expected_installed = _build_expected_install_paths(declared_deps, lockfile, apm_modules_dir)
        except Exception as e:
            _rich_error(f"Failed to parse apm.yml: {e}")
            sys.exit(1)

        installed_packages = _scan_installed_packages(apm_modules_dir)
        orphaned_packages = [p for p in installed_packages if p not in expected_installed]

        if not orphaned_packages:
            _rich_success("No orphaned packages found. apm_modules/ is clean.")
            return

        # Show what will be removed
        _rich_info(f"Found {len(orphaned_packages)} orphaned package(s):")
        for pkg_name in orphaned_packages:
            if dry_run:
                _rich_info(f"  - {pkg_name} (would be removed)")
            else:
                _rich_info(f"  - {pkg_name}")

        if dry_run:
            _rich_success("Dry run complete - no changes made")
            return

        # Remove orphaned packages
        removed_count = 0
        pruned_keys = []
        deleted_pkg_paths: list = []
        for org_repo_name in orphaned_packages:
            path_parts = org_repo_name.split("/")
            pkg_path = apm_modules_dir.joinpath(*path_parts)
            try:
                shutil.rmtree(pkg_path)
                _rich_info(f"+ Removed {org_repo_name}")
                removed_count += 1
                pruned_keys.append(org_repo_name)
                deleted_pkg_paths.append(pkg_path)
            except Exception as e:
                _rich_error(f"x Failed to remove {org_repo_name}: {e}")

        # Batch parent cleanup  -- single bottom-up pass
        from ..integration.base_integrator import BaseIntegrator
        BaseIntegrator.cleanup_empty_parents(deleted_pkg_paths, stop_at=apm_modules_dir)

        # Clean deployed files for pruned packages and update lockfile
        if pruned_keys:
            from ..deps.lockfile import get_lockfile_path
            lockfile_path = get_lockfile_path(Path("."))
            lockfile = LockFile.read(lockfile_path)
            project_root = Path(".")
            if lockfile:
                deployed_cleaned = 0
                deleted_targets: list = []
                for dep_key in pruned_keys:
                    dep = lockfile.get_dependency(dep_key)
                    if dep and dep.deployed_files:
                        for rel_path in dep.deployed_files:
                            if not BaseIntegrator.validate_deploy_path(rel_path, project_root):
                                continue
                            target = project_root / rel_path
                            if target.is_file():
                                target.unlink()
                                deployed_cleaned += 1
                                deleted_targets.append(target)
                            elif target.is_dir():
                                shutil.rmtree(target)
                                deployed_cleaned += 1
                                deleted_targets.append(target)
                    # Remove from lockfile
                    if dep_key in lockfile.dependencies:
                        del lockfile.dependencies[dep_key]
                # Batch parent cleanup  -- single bottom-up pass
                BaseIntegrator.cleanup_empty_parents(deleted_targets, stop_at=project_root)
                if deployed_cleaned > 0:
                    _rich_info(f"+ Cleaned {deployed_cleaned} deployed integration file(s)")
                # Write updated lockfile (or remove if empty)
                try:
                    if lockfile.dependencies:
                        lockfile.write(lockfile_path)
                    else:
                        lockfile_path.unlink(missing_ok=True)
                except Exception:
                    pass

        # Final summary
        if removed_count > 0:
            _rich_success(f"Pruned {removed_count} orphaned package(s)")
        else:
            _rich_warning("No packages were removed")

    except Exception as e:
        _rich_error(f"Error pruning packages: {e}")
        sys.exit(1)
