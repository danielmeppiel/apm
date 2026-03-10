"""APM uninstall command CLI."""

import builtins
import sys
from pathlib import Path

import click

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

from .engine import (
    _parse_dependency_entry,
    _validate_uninstall_packages,
    _dry_run_uninstall,
    _remove_packages_from_disk,
    _cleanup_transitive_orphans,
    _sync_integrations_after_uninstall,
    _cleanup_stale_mcp,
)


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
        if not Path(APM_YML_FILENAME).exists():
            _rich_error(f"No {APM_YML_FILENAME} found. Run 'apm init' first.")
            sys.exit(1)

        if not packages:
            _rich_error("No packages specified. Specify packages to uninstall.")
            sys.exit(1)

        _rich_info(f"Uninstalling {len(packages)} package(s)...")

        # Read current apm.yml
        import yaml

        apm_yml_path = Path(APM_YML_FILENAME)
        try:
            with open(apm_yml_path, "r") as f:
                data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            _rich_error(f"Failed to read {APM_YML_FILENAME}: {e}")
            sys.exit(1)

        if "dependencies" not in data:
            data["dependencies"] = {}
        if "apm" not in data["dependencies"]:
            data["dependencies"]["apm"] = []

        current_deps = data["dependencies"]["apm"] or []

        # Step 1: Validate packages
        packages_to_remove, packages_not_found = _validate_uninstall_packages(packages, current_deps)
        if not packages_to_remove:
            _rich_warning("No packages found in apm.yml to remove")
            return

        # Step 2: Dry run
        if dry_run:
            _dry_run_uninstall(packages_to_remove, Path(APM_MODULES_DIR))
            return

        # Step 3: Remove from apm.yml
        for package in packages_to_remove:
            current_deps.remove(package)
            _rich_info(f"Removed {package} from apm.yml")
        data["dependencies"]["apm"] = current_deps
        try:
            with open(apm_yml_path, "w") as f:
                yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
            _rich_success(f"Updated {APM_YML_FILENAME} (removed {len(packages_to_remove)} package(s))")
        except OSError as e:
            _rich_error(f"Failed to write {APM_YML_FILENAME}: {e}")
            sys.exit(1)

        # Step 4: Load lockfile and capture pre-uninstall MCP state
        apm_modules_dir = Path(APM_MODULES_DIR)
        from ...deps.lockfile import LockFile, get_lockfile_path
        lockfile_path = get_lockfile_path(Path("."))
        lockfile = LockFile.read(lockfile_path)
        _pre_uninstall_mcp_servers = builtins.set(lockfile.mcp_servers) if lockfile else builtins.set()

        # Step 5: Remove packages from disk
        removed_from_modules = _remove_packages_from_disk(packages_to_remove, apm_modules_dir)

        # Step 6: Cleanup transitive orphans
        orphan_removed, actual_orphans = _cleanup_transitive_orphans(
            lockfile, packages_to_remove, apm_modules_dir, apm_yml_path
        )
        removed_from_modules += orphan_removed

        # Step 7: Collect deployed files for removed packages (before lockfile mutation)
        from ...integration.base_integrator import BaseIntegrator
        removed_keys = builtins.set()
        for pkg in packages_to_remove:
            try:
                ref = _parse_dependency_entry(pkg)
                removed_keys.add(ref.get_unique_key())
            except (ValueError, TypeError, AttributeError, KeyError):
                removed_keys.add(pkg)
        removed_keys.update(actual_orphans)
        all_deployed_files = builtins.set()
        if lockfile:
            for dep_key, dep in lockfile.dependencies.items():
                if dep_key in removed_keys:
                    all_deployed_files.update(dep.deployed_files)
        all_deployed_files = BaseIntegrator.normalize_managed_files(all_deployed_files) or builtins.set()

        # Step 8: Update lockfile
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
            for orphan_key in actual_orphans:
                if orphan_key in lockfile.dependencies:
                    del lockfile.dependencies[orphan_key]
                    lockfile_updated = True
            if lockfile_updated:
                try:
                    if lockfile.dependencies:
                        lockfile.write(lockfile_path)
                    else:
                        lockfile_path.unlink(missing_ok=True)
                except Exception:
                    pass

        # Step 9: Sync integrations
        cleaned = {"prompts": 0, "agents": 0, "skills": 0, "commands": 0, "hooks": 0, "instructions": 0}
        try:
            apm_package = APMPackage.from_apm_yml(Path(APM_YML_FILENAME))
            project_root = Path(".")
            cleaned = _sync_integrations_after_uninstall(apm_package, project_root, all_deployed_files)
        except Exception:
            pass  # Best effort cleanup

        for label, count in cleaned.items():
            if count > 0:
                _rich_info(f"\u2713 Cleaned up {count} integrated {label}")

        # Step 10: MCP cleanup
        try:
            apm_package = APMPackage.from_apm_yml(Path(APM_YML_FILENAME))
            _cleanup_stale_mcp(apm_package, lockfile, lockfile_path, _pre_uninstall_mcp_servers)
        except Exception:
            _rich_warning("MCP cleanup during uninstall failed")

        # Final summary
        summary_lines = [f"Removed {len(packages_to_remove)} package(s) from apm.yml"]
        if removed_from_modules > 0:
            summary_lines.append(f"Removed {removed_from_modules} package(s) from apm_modules/")
        _rich_success("Uninstall complete: " + ", ".join(summary_lines))

        if packages_not_found:
            _rich_warning(f"Note: {len(packages_not_found)} package(s) were not found in apm.yml")

    except Exception as e:
        _rich_error(f"Error uninstalling packages: {e}")
        sys.exit(1)
