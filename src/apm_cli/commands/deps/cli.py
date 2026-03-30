"""APM dependency management CLI commands."""

import sys
import shutil
import click
from pathlib import Path
from typing import List, Optional, Dict, Any

# Import existing APM components
from ...constants import APM_DIR, APM_MODULES_DIR, APM_YML_FILENAME, SKILL_MD_FILENAME
from ...models.apm_package import APMPackage, ValidationResult, validate_apm_package
from ...core.command_logger import CommandLogger

from ._utils import (
    _is_nested_under_package,
    _count_primitives,
    _count_package_files,
    _count_workflows,
    _get_detailed_context_counts,
    _get_package_display_info,
    _get_detailed_package_info,
)


@click.group(help="Manage APM package dependencies")
def deps():
    """APM dependency management commands."""
    pass


@deps.command(name="list", help="List installed APM dependencies")
def list_packages():
    """Show all installed APM dependencies with context files and agent workflows."""
    logger = CommandLogger("deps-list")

    try:
        # Import Rich components with fallback
        from rich.table import Table
        from rich.console import Console
        import shutil
        term_width = shutil.get_terminal_size((120, 24)).columns
        console = Console(width=max(120, term_width))
        has_rich = True
    except ImportError:
        has_rich = False
        console = None
    
    try:
        project_root = Path(".")
        apm_modules_path = project_root / APM_MODULES_DIR
        
        # Check if apm_modules exists
        if not apm_modules_path.exists():
            logger.progress("No APM dependencies installed yet")
            logger.verbose_detail("Run 'apm install' to install dependencies from apm.yml")
            return
        
        # Load project dependencies to check for orphaned packages
        # GitHub: owner/repo or owner/virtual-pkg-name (2 levels)
        # Azure DevOps: org/project/repo or org/project/virtual-pkg-name (3 levels)
        declared_sources = {}  # dep_path -> 'github' | 'azure-devops'
        try:
            apm_yml_path = project_root / APM_YML_FILENAME
            if apm_yml_path.exists():
                project_package = APMPackage.from_apm_yml(apm_yml_path)
                for dep in project_package.get_apm_dependencies():
                    # Build the expected installed package name
                    repo_parts = dep.repo_url.split('/')
                    source = 'azure-devops' if dep.is_azure_devops() else 'github'
                    is_ado = dep.is_azure_devops() and len(repo_parts) >= 3
                    is_gh = len(repo_parts) >= 2

                    if not dep.is_virtual:
                        # Regular package: use full repo_url path
                        if is_ado:
                            declared_sources[f"{repo_parts[0]}/{repo_parts[1]}/{repo_parts[2]}"] = source
                        elif is_gh:
                            declared_sources[f"{repo_parts[0]}/{repo_parts[1]}"] = source
                        continue

                    if dep.is_virtual_subdirectory() and dep.virtual_path:
                        # Virtual subdirectory packages keep natural path structure.
                        if is_ado:
                            declared_sources[
                                f"{repo_parts[0]}/{repo_parts[1]}/{repo_parts[2]}/{dep.virtual_path}"
                            ] = source
                        elif is_gh:
                            declared_sources[
                                f"{repo_parts[0]}/{repo_parts[1]}/{dep.virtual_path}"
                            ] = source
                        continue

                    # Virtual file/collection packages are flattened.
                    package_name = dep.get_virtual_package_name()
                    if is_ado:
                        declared_sources[f"{repo_parts[0]}/{repo_parts[1]}/{package_name}"] = source
                    elif is_gh:
                        declared_sources[f"{repo_parts[0]}/{package_name}"] = source
        except Exception:
            pass  # Continue without orphan detection if apm.yml parsing fails
        
        # Also load lockfile deps to avoid false orphan flags on transitive deps
        try:
            from ...deps.lockfile import LockFile, get_lockfile_path
            lockfile_path = get_lockfile_path(project_root)
            if lockfile_path.exists():
                lockfile = LockFile.read(lockfile_path)
                for dep in lockfile.dependencies.values():
                    # Lockfile keys match declared_sources format (owner/repo)
                    dep_key = dep.get_unique_key()
                    if dep_key and dep_key not in declared_sources:
                        declared_sources[dep_key] = 'github'
        except Exception:
            pass  # Continue without lockfile if it can't be read
        
        # Scan for installed packages in org-namespaced structure
        # Walks the tree to find directories containing apm.yml or SKILL.md,
        # handling GitHub (2-level), ADO (3-level), and subdirectory (4+ level) packages.
        installed_packages = []
        orphaned_packages = []
        for candidate in apm_modules_path.rglob("*"):
            if not candidate.is_dir() or candidate.name.startswith('.'):
                continue
            has_apm_yml = (candidate / APM_YML_FILENAME).exists()
            has_skill_md = (candidate / SKILL_MD_FILENAME).exists()
            if not has_apm_yml and not has_skill_md:
                continue
            rel_parts = candidate.relative_to(apm_modules_path).parts
            if len(rel_parts) < 2:
                continue
            org_repo_name = "/".join(rel_parts)
            
            # Skip sub-skills inside .apm/ directories  -- they belong to the parent package
            if '.apm' in rel_parts:
                continue

            # Skip skill sub-dirs nested inside another package (e.g. plugin
            # skills/ directories that are deployment artifacts, not packages).
            if has_skill_md and not has_apm_yml and _is_nested_under_package(candidate, apm_modules_path):
                continue

            try:
                version = 'unknown'
                if has_apm_yml:
                    package = APMPackage.from_apm_yml(candidate / APM_YML_FILENAME)
                    version = package.version or 'unknown'
                primitives = _count_primitives(candidate)
                
                is_orphaned = org_repo_name not in declared_sources
                if is_orphaned:
                    orphaned_packages.append(org_repo_name)
                
                installed_packages.append({
                    'name': org_repo_name,
                    'version': version, 
                    'source': 'orphaned' if is_orphaned else declared_sources.get(org_repo_name, 'github'),
                    'primitives': primitives,
                    'path': str(candidate),
                    'is_orphaned': is_orphaned
                })
            except Exception as e:
                logger.warning(f"Failed to read package {org_repo_name}: {e}")
        
        if not installed_packages:
            logger.progress("apm_modules/ directory exists but contains no valid packages")
            return
        
        # Display packages in table format
        if has_rich:
            table = Table(title=" APM Dependencies", show_header=True, header_style="bold cyan")
            table.add_column("Package", style="bold white")
            table.add_column("Version", style="yellow") 
            table.add_column("Source", style="blue")
            table.add_column("Prompts", style="magenta", justify="center")
            table.add_column("Instructions", style="green", justify="center")
            table.add_column("Agents", style="cyan", justify="center")
            table.add_column("Skills", style="yellow", justify="center")
            table.add_column("Hooks", style="red", justify="center")
            
            for pkg in installed_packages:
                p = pkg['primitives']
                table.add_row(
                    pkg['name'],
                    pkg['version'],
                    pkg['source'],
                    str(p.get('prompts', 0)) if p.get('prompts', 0) > 0 else "-",
                    str(p.get('instructions', 0)) if p.get('instructions', 0) > 0 else "-",
                    str(p.get('agents', 0)) if p.get('agents', 0) > 0 else "-",
                    str(p.get('skills', 0)) if p.get('skills', 0) > 0 else "-",
                    str(p.get('hooks', 0)) if p.get('hooks', 0) > 0 else "-",
                )
            
            console.print(table)
            
            # Show orphaned packages warning
            if orphaned_packages:
                console.print(f"\n[!]  {len(orphaned_packages)} orphaned package(s) found (not in apm.yml):", style="yellow")
                for pkg in orphaned_packages:
                    console.print(f"  * {pkg}", style="dim yellow")
                console.print("\n Run 'apm prune' to remove orphaned packages", style="cyan")
        else:
            # Fallback text table
            click.echo(" APM Dependencies:")
            click.echo(f"{'Package':<30} {'Version':<10} {'Source':<12} {'Prompts':>7} {'Instr':>7} {'Agents':>7} {'Skills':>7} {'Hooks':>7}")
            click.echo("-" * 98)
            
            for pkg in installed_packages:
                p = pkg['primitives']
                name = pkg['name'][:28]
                version = pkg['version'][:8]
                source = pkg['source'][:10]
                prompts = str(p.get('prompts', 0)) if p.get('prompts', 0) > 0 else "-"
                instructions = str(p.get('instructions', 0)) if p.get('instructions', 0) > 0 else "-"
                agents = str(p.get('agents', 0)) if p.get('agents', 0) > 0 else "-"
                skills = str(p.get('skills', 0)) if p.get('skills', 0) > 0 else "-"
                hooks = str(p.get('hooks', 0)) if p.get('hooks', 0) > 0 else "-"
                click.echo(f"{name:<30} {version:<10} {source:<12} {prompts:>7} {instructions:>7} {agents:>7} {skills:>7} {hooks:>7}")
            
            # Show orphaned packages warning
            if orphaned_packages:
                click.echo(f"\n[!]  {len(orphaned_packages)} orphaned package(s) found (not in apm.yml):")
                for pkg in orphaned_packages:
                    click.echo(f"  * {pkg}")
                click.echo("\n Run 'apm prune' to remove orphaned packages")

    except Exception as e:
        logger.error(f"Error listing dependencies: {e}")
        sys.exit(1)


@deps.command(help="Show dependency tree structure")  
def tree():
    """Display dependencies in hierarchical tree format using lockfile."""
    logger = CommandLogger("deps-tree")

    try:
        # Import Rich components with fallback
        from rich.tree import Tree
        from rich.console import Console
        console = Console()
        has_rich = True
    except ImportError:
        has_rich = False
        console = None
    
    try:
        project_root = Path(".")
        apm_modules_path = project_root / APM_MODULES_DIR
        
        # Load project info
        project_name = "my-project"
        try:
            apm_yml_path = project_root / APM_YML_FILENAME
            if apm_yml_path.exists():
                root_package = APMPackage.from_apm_yml(apm_yml_path)
                project_name = root_package.name
        except Exception:
            pass
        
        # Try to load lockfile for accurate tree with depth/parent info
        lockfile_deps = None
        try:
            from ...deps.lockfile import LockFile, get_lockfile_path
            lockfile_path = get_lockfile_path(project_root)
            if lockfile_path.exists():
                lockfile = LockFile.read(lockfile_path)
                if lockfile:
                    lockfile_deps = lockfile.get_all_dependencies()
        except Exception:
            pass
        
        if lockfile_deps:
            # Build tree from lockfile (accurate depth + parent info)
            # Separate direct (depth=1) from transitive (depth>1)
            direct = [d for d in lockfile_deps if d.depth <= 1]
            transitive = [d for d in lockfile_deps if d.depth > 1]
            
            # Build parent->children map
            children_map: Dict[str, list] = {}
            for dep in transitive:
                parent_key = dep.resolved_by or ""
                if parent_key not in children_map:
                    children_map[parent_key] = []
                children_map[parent_key].append(dep)
            
            def _dep_display_name(dep) -> str:
                """Get display name for a locked dependency."""
                key = dep.get_unique_key()
                version = dep.version or (dep.resolved_commit[:7] if dep.resolved_commit else None) or dep.resolved_ref or "latest"
                return f"{key}@{version}"
            
            def _add_children(parent_branch, parent_repo_url, depth=0):
                """Recursively add transitive deps as nested children."""
                kids = children_map.get(parent_repo_url, [])
                for child_dep in kids:
                    child_name = _dep_display_name(child_dep)
                    if has_rich:
                        child_branch = parent_branch.add(f"[dim]{child_name}[/dim]")
                    else:
                        child_branch = child_name
                    if depth < 5:  # Prevent infinite recursion
                        _add_children(child_branch, child_dep.repo_url, depth + 1)
            
            if has_rich:
                root_tree = Tree(f"[bold cyan]{project_name}[/bold cyan] (local)")
                
                if not direct:
                    root_tree.add("[dim]No dependencies installed[/dim]")
                else:
                    for dep in direct:
                        display = _dep_display_name(dep)
                        # Get primitive counts if install path exists
                        install_key = dep.get_unique_key()
                        install_path = apm_modules_path / install_key
                        branch = root_tree.add(f"[green]{display}[/green]")
                        
                        if install_path.exists():
                            primitives = _count_primitives(install_path)
                            prim_parts = []
                            for ptype, count in primitives.items():
                                if count > 0:
                                    prim_parts.append(f"{count} {ptype}")
                            if prim_parts:
                                branch.add(f"[dim]{', '.join(prim_parts)}[/dim]")
                        
                        # Add transitive deps as nested children
                        _add_children(branch, dep.repo_url)
                
                console.print(root_tree)
            else:
                click.echo(f"{project_name} (local)")
                
                if not direct:
                    click.echo("+-- No dependencies installed")
                else:
                    for i, dep in enumerate(direct):
                        is_last = i == len(direct) - 1
                        prefix = "+-- " if is_last else "|-- "
                        display = _dep_display_name(dep)
                        click.echo(f"{prefix}{display}")
                        
                        # Show transitive deps
                        kids = children_map.get(dep.repo_url, [])
                        sub_prefix = "    " if is_last else "|   "
                        for j, child in enumerate(kids):
                            child_is_last = j == len(kids) - 1
                            child_prefix = "+-- " if child_is_last else "|-- "
                            click.echo(f"{sub_prefix}{child_prefix}{_dep_display_name(child)}")
        else:
            # Fallback: scan apm_modules directory (no lockfile)
            if has_rich:
                root_tree = Tree(f"[bold cyan]{project_name}[/bold cyan] (local)")
                
                if not apm_modules_path.exists():
                    root_tree.add("[dim]No dependencies installed[/dim]")
                else:
                    for candidate in sorted(apm_modules_path.rglob("*")):
                        if not candidate.is_dir() or candidate.name.startswith('.'):
                            continue
                        has_apm = (candidate / APM_YML_FILENAME).exists()
                        has_skill = (candidate / SKILL_MD_FILENAME).exists()
                        if not has_apm and not has_skill:
                            continue
                        rel_parts = candidate.relative_to(apm_modules_path).parts
                        if len(rel_parts) < 2:
                            continue
                        if '.apm' in rel_parts:
                            continue
                        if has_skill and not has_apm and _is_nested_under_package(candidate, apm_modules_path):
                            continue
                        display = "/".join(rel_parts)
                        info = _get_package_display_info(candidate)
                        branch = root_tree.add(f"[green]{info['display_name']}[/green]")
                        primitives = _count_primitives(candidate)
                        prim_parts = []
                        for ptype, count in primitives.items():
                            if count > 0:
                                prim_parts.append(f"{count} {ptype}")
                        if prim_parts:
                            branch.add(f"[dim]{', '.join(prim_parts)}[/dim]")
                
                console.print(root_tree)
            else:
                click.echo(f"{project_name} (local)")
                if not apm_modules_path.exists():
                    click.echo("+-- No dependencies installed")

    except Exception as e:
        logger.error(f"Error showing dependency tree: {e}")
        sys.exit(1)


@deps.command(help="Remove all APM dependencies")
@click.option("--dry-run", is_flag=True, default=False, help="Show what would be removed without removing")
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip confirmation prompt")
def clean(dry_run: bool, yes: bool):
    """Remove entire apm_modules/ directory."""
    logger = CommandLogger("deps-clean")

    project_root = Path(".")
    apm_modules_path = project_root / APM_MODULES_DIR
    
    if not apm_modules_path.exists():
        logger.progress("No apm_modules/ directory found - already clean")
        return
    
    # Count actual installed packages (not just top-level dirs like org namespaces or _local)
    from ._utils import _scan_installed_packages
    packages = _scan_installed_packages(apm_modules_path)
    package_count = len(packages)
    
    if dry_run:
        logger.progress(f"Dry run: would remove apm_modules/ ({package_count} package(s))")
        for pkg in sorted(packages):
            logger.progress(f"  - {pkg}")
        return
    
    logger.warning(f"This will remove the entire apm_modules/ directory ({package_count} package(s))")
    
    # Confirmation prompt (skip if --yes provided)
    if not yes:
        try:
            from rich.prompt import Confirm
            confirm = Confirm.ask("Continue?")
        except ImportError:
            confirm = click.confirm("Continue?")
        
        if not confirm:
            logger.progress("Operation cancelled")
            return
    
    try:
        shutil.rmtree(apm_modules_path)
        logger.success("Successfully removed apm_modules/ directory")
    except Exception as e:
        logger.error(f"Error removing apm_modules/: {e}")
        sys.exit(1)


@deps.command(help="Update APM dependencies to latest refs")
@click.argument("packages", nargs=-1)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed update information")
@click.option(
    "--force", is_flag=True,
    help="Overwrite locally-authored files on collision",
)
@click.option(
    "--target", "-t",
    type=click.Choice(
        ["copilot", "claude", "cursor", "opencode", "vscode", "agents", "all"],
        case_sensitive=False,
    ),
    default=None,
    help="Force deployment to a specific target (overrides auto-detection)",
)
@click.option(
    "--parallel-downloads",
    type=int,
    default=4,
    show_default=True,
    help="Max concurrent package downloads (0 to disable parallelism)",
)
def update(packages, verbose, force, target, parallel_downloads):
    """Update APM dependencies to latest git refs.

    Re-resolves git references (branches/tags) to their current SHAs,
    downloads updated content, re-integrates primitives, and regenerates
    the lockfile.

    \b
    Examples:
        apm deps update                    # Update all packages
        apm deps update org/repo           # Update one package
        apm deps update org/a org/b        # Update specific packages
        apm deps update --verbose          # Show detailed progress
    """
    from ..install import (
        _install_apm_dependencies,
        APM_DEPS_AVAILABLE,
        _APM_IMPORT_ERROR,
    )
    from ...core.command_logger import InstallLogger
    from ...core.auth import AuthResolver

    logger = InstallLogger(verbose=verbose, partial=bool(packages))

    if not APM_DEPS_AVAILABLE:
        logger.error("APM dependency system not available")
        if _APM_IMPORT_ERROR:
            logger.progress(f"Import error: {_APM_IMPORT_ERROR}")
        sys.exit(1)

    project_root = Path.cwd()
    apm_yml_path = project_root / APM_YML_FILENAME

    if not apm_yml_path.exists():
        logger.error(f"No {APM_YML_FILENAME} found in current directory")
        sys.exit(1)

    try:
        apm_package = APMPackage.from_apm_yml(apm_yml_path)
    except Exception as e:
        logger.error(f"Failed to parse {APM_YML_FILENAME}: {e}")
        sys.exit(1)

    all_deps = apm_package.get_apm_dependencies() + apm_package.get_dev_apm_dependencies()
    if not all_deps:
        logger.progress("No APM dependencies defined in apm.yml")
        return

    # Validate requested packages exist in manifest
    only_pkgs = None
    if packages:
        only_pkgs = list(packages)
        known_keys = set()
        for dep in all_deps:
            known_keys.add(dep.get_unique_key())
            known_keys.add(dep.get_display_name())
            known_keys.add(dep.repo_url)
            if hasattr(dep, "alias") and dep.alias:
                known_keys.add(dep.alias)
            parts = dep.repo_url.split("/")
            if len(parts) >= 2:
                known_keys.add(parts[-1])

        for pkg in only_pkgs:
            if pkg not in known_keys:
                available = ", ".join(dep.get_display_name() for dep in all_deps)
                logger.error(f"Package '{pkg}' not found in {APM_YML_FILENAME}")
                logger.progress(f"Available: {available}")
                sys.exit(1)

    # Snapshot old lockfile SHAs for before/after diff
    from ...deps.lockfile import LockFile, get_lockfile_path, migrate_lockfile_if_needed

    lockfile_path = get_lockfile_path(project_root)
    old_lockfile = LockFile.read(lockfile_path)
    old_shas: dict = {}
    if old_lockfile:
        for key, dep in old_lockfile.dependencies.items():
            old_shas[key] = dep.resolved_commit

    migrate_lockfile_if_needed(project_root)

    auth_resolver = AuthResolver()

    if packages:
        noun = f"{len(packages)} package(s)"
    else:
        noun = f"all {len(all_deps)} dependencies"
    logger.start(f"Updating {noun}...")

    try:
        install_result = _install_apm_dependencies(
            apm_package,
            update_refs=True,
            verbose=verbose,
            only_packages=only_pkgs,
            force=force,
            parallel_downloads=parallel_downloads,
            logger=logger,
            auth_resolver=auth_resolver,
            target=target,
        )
    except Exception as e:
        logger.error(f"Update failed: {e}")
        if not verbose:
            logger.progress("Run with --verbose for detailed diagnostics")
        sys.exit(1)

    # Show diagnostics if any
    if install_result.diagnostics and install_result.diagnostics.has_diagnostics:
        install_result.diagnostics.render_summary()

    # Compare old vs new lockfile SHAs to show what changed
    new_lockfile = LockFile.read(lockfile_path)
    changed: list = []
    if new_lockfile:
        for key, dep in new_lockfile.dependencies.items():
            old_sha = old_shas.get(key)
            new_sha = dep.resolved_commit
            if old_sha and new_sha and old_sha != new_sha:
                changed.append(
                    (key, old_sha[:8], new_sha[:8], dep.resolved_ref or "")
                )

    error_count = 0
    if install_result.diagnostics:
        try:
            error_count = int(install_result.diagnostics.error_count)
        except (TypeError, ValueError):
            error_count = 0

    if changed:
        pkg_noun = "package" if len(changed) == 1 else "packages"
        if error_count > 0:
            logger.warning(
                f"Updated {len(changed)} {pkg_noun} with {error_count} error(s)."
            )
        else:
            logger.success(f"Updated {len(changed)} {pkg_noun}:")
        for key, old_sha, new_sha, ref in changed:
            ref_str = f" ({ref})" if ref else ""
            click.echo(f"  {key}{ref_str}: {old_sha} -> {new_sha}")
    elif error_count > 0:
        logger.error(f"Update failed with {error_count} error(s).")
    else:
        logger.success("All packages already at latest refs.")


@deps.command(help="Show detailed package information")
@click.argument('package', required=True)
def info(package: str):
    """Show detailed information about a specific package including context files and workflows."""
    logger = CommandLogger("deps-info")

    project_root = Path(".")
    apm_modules_path = project_root / APM_MODULES_DIR
    
    if not apm_modules_path.exists():
        logger.error("No apm_modules/ directory found")
        logger.progress("Run 'apm install' to install dependencies first")
        sys.exit(1)
    
    # Find the package directory - handle org/repo and deep sub-path structures
    package_path = None
    # First try direct path match (handles any depth: org/repo, org/repo/subdir/pkg)
    direct_match = apm_modules_path / package
    if direct_match.is_dir() and (
        (direct_match / APM_YML_FILENAME).exists() or (direct_match / SKILL_MD_FILENAME).exists()
    ):
        package_path = direct_match
    else:
        # Fallback: scan org/repo structure (2-level) for short package names
        for org_dir in apm_modules_path.iterdir():
            if org_dir.is_dir() and not org_dir.name.startswith('.'):
                for package_dir in org_dir.iterdir():
                    if package_dir.is_dir() and not package_dir.name.startswith('.'):
                        if package_dir.name == package or f"{org_dir.name}/{package_dir.name}" == package:
                            package_path = package_dir
                            break
                if package_path:
                    break
    
    if not package_path:
        logger.error(f"Package '{package}' not found in apm_modules/")
        logger.progress("Available packages:")
        
        for org_dir in apm_modules_path.iterdir():
            if org_dir.is_dir() and not org_dir.name.startswith('.'):
                for package_dir in org_dir.iterdir():
                    if package_dir.is_dir() and not package_dir.name.startswith('.'):
                        click.echo(f"  - {org_dir.name}/{package_dir.name}")
        sys.exit(1)
    
    try:
        # Load package information
        package_info = _get_detailed_package_info(package_path)
        
        # Display with Rich panel if available
        try:
            from rich.panel import Panel
            from rich.console import Console
            from rich.text import Text
            console = Console()
            
            content_lines = []
            content_lines.append(f"[bold]Name:[/bold] {package_info['name']}")
            content_lines.append(f"[bold]Version:[/bold] {package_info['version']}")
            content_lines.append(f"[bold]Description:[/bold] {package_info['description']}")
            content_lines.append(f"[bold]Author:[/bold] {package_info['author']}")
            content_lines.append(f"[bold]Source:[/bold] {package_info['source']}")
            content_lines.append(f"[bold]Install Path:[/bold] {package_info['install_path']}")
            content_lines.append("")
            content_lines.append("[bold]Context Files:[/bold]")
            
            for context_type, count in package_info['context_files'].items():
                if count > 0:
                    content_lines.append(f"  * {count} {context_type}")
            
            if not any(count > 0 for count in package_info['context_files'].values()):
                content_lines.append("  * No context files found")
                
            content_lines.append("")
            content_lines.append("[bold]Agent Workflows:[/bold]")
            if package_info['workflows'] > 0:
                content_lines.append(f"  * {package_info['workflows']} executable workflows")
            else:
                content_lines.append("  * No agent workflows found")
            
            if package_info.get('hooks', 0) > 0:
                content_lines.append("")
                content_lines.append("[bold]Hooks:[/bold]")
                content_lines.append(f"  * {package_info['hooks']} hook file(s)")
            
            content = "\n".join(content_lines)
            panel = Panel(content, title=f"[i] Package Info: {package}", border_style="cyan")
            console.print(panel)
            
        except ImportError:
            # Fallback text display
            click.echo(f"[i] Package Info: {package}")
            click.echo("=" * 40)
            click.echo(f"Name: {package_info['name']}")
            click.echo(f"Version: {package_info['version']}")
            click.echo(f"Description: {package_info['description']}")
            click.echo(f"Author: {package_info['author']}")
            click.echo(f"Source: {package_info['source']}")
            click.echo(f"Install Path: {package_info['install_path']}")
            click.echo("")
            click.echo("Context Files:")
            
            for context_type, count in package_info['context_files'].items():
                if count > 0:
                    click.echo(f"  * {count} {context_type}")
            
            if not any(count > 0 for count in package_info['context_files'].values()):
                click.echo("  * No context files found")
                
            click.echo("")
            click.echo("Agent Workflows:")
            if package_info['workflows'] > 0:
                click.echo(f"  * {package_info['workflows']} executable workflows")
            else:
                click.echo("  * No agent workflows found")
            
            if package_info.get('hooks', 0) > 0:
                click.echo("")
                click.echo("Hooks:")
                click.echo(f"  * {package_info['hooks']} hook file(s)")
    
    except Exception as e:
        logger.error(f"Error reading package information: {e}")
        sys.exit(1)
