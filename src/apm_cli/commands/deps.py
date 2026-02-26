"""APM dependency management commands."""

import sys
import shutil
import click
from pathlib import Path
from typing import List, Optional, Dict, Any

# Import existing APM components
from ..models.apm_package import APMPackage, ValidationResult, validate_apm_package
from ..utils.console import _rich_success, _rich_error, _rich_info, _rich_warning

# Import APM dependency system components (with fallback)
from ..deps.github_downloader import GitHubPackageDownloader
from ..deps.apm_resolver import APMDependencyResolver



@click.group(help="Manage APM package dependencies")
def deps():
    """APM dependency management commands."""
    pass


@deps.command(name="list", help="📋 List installed APM dependencies")
def list_packages():
    """Show all installed APM dependencies with context files and agent workflows."""
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
        apm_modules_path = project_root / "apm_modules"
        
        # Check if apm_modules exists
        if not apm_modules_path.exists():
            if has_rich:
                console.print("💡 No APM dependencies installed yet", style="cyan")
                console.print("Run 'apm install' to install dependencies from apm.yml", style="dim")
            else:
                click.echo("💡 No APM dependencies installed yet")
                click.echo("Run 'apm install' to install dependencies from apm.yml")
            return
        
        # Load project dependencies to check for orphaned packages
        # GitHub: owner/repo or owner/virtual-pkg-name (2 levels)
        # Azure DevOps: org/project/repo or org/project/virtual-pkg-name (3 levels)
        declared_sources = {}  # dep_path → 'github' | 'azure-devops'
        try:
            apm_yml_path = project_root / "apm.yml"
            if apm_yml_path.exists():
                project_package = APMPackage.from_apm_yml(apm_yml_path)
                for dep in project_package.get_apm_dependencies():
                    # Build the expected installed package name
                    repo_parts = dep.repo_url.split('/')
                    source = 'azure-devops' if dep.is_azure_devops() else 'github'
                    if dep.is_virtual:
                        if dep.is_virtual_subdirectory() and dep.virtual_path:
                            # Virtual subdirectory packages keep natural path structure.
                            # GitHub: owner/repo/subdir
                            # ADO: org/project/repo/subdir
                            if dep.is_azure_devops() and len(repo_parts) >= 3:
                                declared_sources[
                                    f"{repo_parts[0]}/{repo_parts[1]}/{repo_parts[2]}/{dep.virtual_path}"
                                ] = source
                            elif len(repo_parts) >= 2:
                                declared_sources[
                                    f"{repo_parts[0]}/{repo_parts[1]}/{dep.virtual_path}"
                                ] = source
                        else:
                            # Virtual file/collection packages are flattened.
                            package_name = dep.get_virtual_package_name()
                            if dep.is_azure_devops() and len(repo_parts) >= 3:
                                # ADO structure: org/project/virtual-pkg-name
                                declared_sources[f"{repo_parts[0]}/{repo_parts[1]}/{package_name}"] = source
                            elif len(repo_parts) >= 2:
                                # GitHub structure: owner/virtual-pkg-name
                                declared_sources[f"{repo_parts[0]}/{package_name}"] = source
                    else:
                        # Regular package: use full repo_url path
                        if dep.is_azure_devops() and len(repo_parts) >= 3:
                            # ADO structure: org/project/repo
                            declared_sources[f"{repo_parts[0]}/{repo_parts[1]}/{repo_parts[2]}"] = source
                        elif len(repo_parts) >= 2:
                            # GitHub structure: owner/repo
                            declared_sources[f"{repo_parts[0]}/{repo_parts[1]}"] = source
        except Exception:
            pass  # Continue without orphan detection if apm.yml parsing fails
        
        # Also load lockfile deps to avoid false orphan flags on transitive deps
        try:
            from ..deps.lockfile import LockFile, get_lockfile_path
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
            has_apm_yml = (candidate / "apm.yml").exists()
            has_skill_md = (candidate / "SKILL.md").exists()
            if not has_apm_yml and not has_skill_md:
                continue
            rel_parts = candidate.relative_to(apm_modules_path).parts
            if len(rel_parts) < 2:
                continue
            org_repo_name = "/".join(rel_parts)
            
            # Skip sub-skills inside .apm/ directories — they belong to the parent package
            if '.apm' in rel_parts:
                continue
            
            try:
                version = 'unknown'
                if has_apm_yml:
                    package = APMPackage.from_apm_yml(candidate / "apm.yml")
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
                click.echo(f"⚠️ Warning: Failed to read package {org_repo_name}: {e}")
        
        if not installed_packages:
            if has_rich:
                console.print("💡 apm_modules/ directory exists but contains no valid packages", style="cyan")
            else:
                click.echo("💡 apm_modules/ directory exists but contains no valid packages")
            return
        
        # Display packages in table format
        if has_rich:
            table = Table(title="📋 APM Dependencies", show_header=True, header_style="bold cyan")
            table.add_column("Package", style="bold white")
            table.add_column("Version", style="yellow") 
            table.add_column("Source", style="blue")
            table.add_column("Prompts", style="magenta", justify="center")
            table.add_column("Instructions", style="green", justify="center")
            table.add_column("Agents", style="cyan", justify="center")
            table.add_column("Skills", style="yellow", justify="center")
            
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
                )
            
            console.print(table)
            
            # Show orphaned packages warning
            if orphaned_packages:
                console.print(f"\n⚠️  {len(orphaned_packages)} orphaned package(s) found (not in apm.yml):", style="yellow")
                for pkg in orphaned_packages:
                    console.print(f"  • {pkg}", style="dim yellow")
                console.print("\n💡 Run 'apm prune' to remove orphaned packages", style="cyan")
        else:
            # Fallback text table
            click.echo("📋 APM Dependencies:")
            click.echo(f"{'Package':<30} {'Version':<10} {'Source':<12} {'Prompts':>7} {'Instr':>7} {'Agents':>7} {'Skills':>7}")
            click.echo("-" * 90)
            
            for pkg in installed_packages:
                p = pkg['primitives']
                name = pkg['name'][:28]
                version = pkg['version'][:8]
                source = pkg['source'][:10]
                prompts = str(p.get('prompts', 0)) if p.get('prompts', 0) > 0 else "-"
                instructions = str(p.get('instructions', 0)) if p.get('instructions', 0) > 0 else "-"
                agents = str(p.get('agents', 0)) if p.get('agents', 0) > 0 else "-"
                skills = str(p.get('skills', 0)) if p.get('skills', 0) > 0 else "-"
                click.echo(f"{name:<30} {version:<10} {source:<12} {prompts:>7} {instructions:>7} {agents:>7} {skills:>7}")
            
            # Show orphaned packages warning
            if orphaned_packages:
                click.echo(f"\n⚠️  {len(orphaned_packages)} orphaned package(s) found (not in apm.yml):")
                for pkg in orphaned_packages:
                    click.echo(f"  • {pkg}")
                click.echo("\n💡 Run 'apm prune' to remove orphaned packages")

    except Exception as e:
        _rich_error(f"Error listing dependencies: {e}")
        sys.exit(1)


@deps.command(help="🌳 Show dependency tree structure")  
def tree():
    """Display dependencies in hierarchical tree format using lockfile."""
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
        apm_modules_path = project_root / "apm_modules"
        
        # Load project info
        project_name = "my-project"
        try:
            apm_yml_path = project_root / "apm.yml"
            if apm_yml_path.exists():
                root_package = APMPackage.from_apm_yml(apm_yml_path)
                project_name = root_package.name
        except Exception:
            pass
        
        # Try to load lockfile for accurate tree with depth/parent info
        lockfile_deps = None
        try:
            from ..deps.lockfile import LockFile, get_lockfile_path
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
            
            # Build parent→children map
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
                    click.echo("└── No dependencies installed")
                else:
                    for i, dep in enumerate(direct):
                        is_last = i == len(direct) - 1
                        prefix = "└── " if is_last else "├── "
                        display = _dep_display_name(dep)
                        click.echo(f"{prefix}{display}")
                        
                        # Show transitive deps
                        kids = children_map.get(dep.repo_url, [])
                        sub_prefix = "    " if is_last else "│   "
                        for j, child in enumerate(kids):
                            child_is_last = j == len(kids) - 1
                            child_prefix = "└── " if child_is_last else "├── "
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
                        has_apm = (candidate / "apm.yml").exists()
                        has_skill = (candidate / "SKILL.md").exists()
                        if not has_apm and not has_skill:
                            continue
                        rel_parts = candidate.relative_to(apm_modules_path).parts
                        if len(rel_parts) < 2:
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
                    click.echo("└── No dependencies installed")

    except Exception as e:
        _rich_error(f"Error showing dependency tree: {e}")
        sys.exit(1)


@deps.command(help="🧹 Remove all APM dependencies")
def clean():
    """Remove entire apm_modules/ directory."""
    project_root = Path(".")
    apm_modules_path = project_root / "apm_modules"
    
    if not apm_modules_path.exists():
        _rich_info("No apm_modules/ directory found - already clean")
        return
    
    # Show what will be removed
    package_count = len([d for d in apm_modules_path.iterdir() if d.is_dir()])
    
    _rich_warning(f"This will remove the entire apm_modules/ directory ({package_count} packages)")
    
    # Confirmation prompt
    try:
        from rich.prompt import Confirm
        confirm = Confirm.ask("Continue?")
    except ImportError:
        confirm = click.confirm("Continue?")
    
    if not confirm:
        _rich_info("Operation cancelled")
        return
    
    try:
        shutil.rmtree(apm_modules_path)
        _rich_success("Successfully removed apm_modules/ directory")
    except Exception as e:
        _rich_error(f"Error removing apm_modules/: {e}")
        sys.exit(1)


@deps.command(help="🔄 Update APM dependencies")
@click.argument('package', required=False)
def update(package: Optional[str]):
    """Update specific package or all if no package specified."""
    
    project_root = Path(".")
    apm_modules_path = project_root / "apm_modules"
    
    if not apm_modules_path.exists():
        _rich_info("No apm_modules/ directory found - no packages to update")
        return
    
    # Get project dependencies to validate updates
    try:
        apm_yml_path = project_root / "apm.yml"
        if not apm_yml_path.exists():
            _rich_error("No apm.yml found in current directory")
            return
            
        project_package = APMPackage.from_apm_yml(apm_yml_path)
        project_deps = project_package.get_apm_dependencies()
        
        if not project_deps:
            _rich_info("No APM dependencies defined in apm.yml")
            return
            
    except Exception as e:
        _rich_error(f"Error reading apm.yml: {e}")
        return
    
    if package:
        # Update specific package
        _update_single_package(package, project_deps, apm_modules_path)
    else:
        # Update all packages
        _update_all_packages(project_deps, apm_modules_path)


@deps.command(help="ℹ️ Show detailed package information")
@click.argument('package', required=True)
def info(package: str):
    """Show detailed information about a specific package including context files and workflows."""
    project_root = Path(".")
    apm_modules_path = project_root / "apm_modules"
    
    if not apm_modules_path.exists():
        _rich_error("No apm_modules/ directory found")
        _rich_info("Run 'apm install' to install dependencies first")
        sys.exit(1)
    
    # Find the package directory - handle org/repo structure
    package_path = None
    for org_dir in apm_modules_path.iterdir():
        if org_dir.is_dir() and not org_dir.name.startswith('.'):
            for package_dir in org_dir.iterdir():
                if package_dir.is_dir() and not package_dir.name.startswith('.'):
                    # Check both package name and org/package format
                    if package_dir.name == package or f"{org_dir.name}/{package_dir.name}" == package:
                        package_path = package_dir
                        break
            if package_path:
                break
    
    if not package_path:
        _rich_error(f"Package '{package}' not found in apm_modules/")
        _rich_info("Available packages:")
        
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
                    content_lines.append(f"  • {count} {context_type}")
            
            if not any(count > 0 for count in package_info['context_files'].values()):
                content_lines.append("  • No context files found")
                
            content_lines.append("")
            content_lines.append("[bold]Agent Workflows:[/bold]")
            if package_info['workflows'] > 0:
                content_lines.append(f"  • {package_info['workflows']} executable workflows")
            else:
                content_lines.append("  • No agent workflows found")
            
            content = "\n".join(content_lines)
            panel = Panel(content, title=f"ℹ️ Package Info: {package}", border_style="cyan")
            console.print(panel)
            
        except ImportError:
            # Fallback text display
            click.echo(f"ℹ️ Package Info: {package}")
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
                    click.echo(f"  • {count} {context_type}")
            
            if not any(count > 0 for count in package_info['context_files'].values()):
                click.echo("  • No context files found")
                
            click.echo("")
            click.echo("Agent Workflows:")
            if package_info['workflows'] > 0:
                click.echo(f"  • {package_info['workflows']} executable workflows")
            else:
                click.echo("  • No agent workflows found")
    
    except Exception as e:
        _rich_error(f"Error reading package information: {e}")
        sys.exit(1)


# Helper functions

def _count_primitives(package_path: Path) -> Dict[str, int]:
    """Count primitives by type in a package.
    
    Returns:
        dict: Counts for 'prompts', 'instructions', 'agents', 'skills'
    """
    counts = {'prompts': 0, 'instructions': 0, 'agents': 0, 'skills': 0}
    
    apm_dir = package_path / ".apm"
    if apm_dir.exists():
        prompts_path = apm_dir / "prompts"
        if prompts_path.exists() and prompts_path.is_dir():
            counts['prompts'] += len(list(prompts_path.glob("*.prompt.md")))
        
        instructions_path = apm_dir / "instructions"
        if instructions_path.exists() and instructions_path.is_dir():
            counts['instructions'] += len(list(instructions_path.glob("*.md")))
        
        agents_path = apm_dir / "agents"
        if agents_path.exists() and agents_path.is_dir():
            counts['agents'] += len(list(agents_path.glob("*.md")))
        
        skills_path = apm_dir / "skills"
        if skills_path.exists() and skills_path.is_dir():
            counts['skills'] += len([d for d in skills_path.iterdir() 
                                     if d.is_dir() and (d / "SKILL.md").exists()])
    
    # Also count root-level .prompt.md files
    counts['prompts'] += len(list(package_path.glob("*.prompt.md")))
    
    # Count root-level SKILL.md as a skill
    if (package_path / "SKILL.md").exists():
        counts['skills'] += 1
    
    return counts


def _count_package_files(package_path: Path) -> tuple[int, int]:
    """Count context files and workflows in a package.
    
    Returns:
        tuple: (context_count, workflow_count)
    """
    apm_dir = package_path / ".apm"
    if not apm_dir.exists():
        # Also check root directory for .prompt.md files
        workflow_count = len(list(package_path.glob("*.prompt.md")))
        return 0, workflow_count
    
    context_count = 0
    context_dirs = ['instructions', 'chatmodes', 'contexts']
    
    for context_dir in context_dirs:
        context_path = apm_dir / context_dir
        if context_path.exists() and context_path.is_dir():
            context_count += len(list(context_path.glob("*.md")))
    
    # Count workflows in both .apm/prompts and root directory
    workflow_count = 0
    prompts_path = apm_dir / "prompts"
    if prompts_path.exists() and prompts_path.is_dir():
        workflow_count += len(list(prompts_path.glob("*.prompt.md")))
    
    # Also check root directory for .prompt.md files
    workflow_count += len(list(package_path.glob("*.prompt.md")))
    
    return context_count, workflow_count


def _count_workflows(package_path: Path) -> int:
    """Count agent workflows (.prompt.md files) in a package."""
    _, workflow_count = _count_package_files(package_path)
    return workflow_count


def _get_detailed_context_counts(package_path: Path) -> Dict[str, int]:
    """Get detailed context file counts by type."""
    apm_dir = package_path / ".apm"
    if not apm_dir.exists():
        return {'instructions': 0, 'chatmodes': 0, 'contexts': 0}
    
    counts = {}
    context_directories = {
        'instructions': 'instructions',
        'chatmodes': 'chatmodes', 
        'contexts': 'context'  # Note: directory is 'context', not 'contexts'
    }
    
    for context_type, directory_name in context_directories.items():
        count = 0
        context_path = apm_dir / directory_name
        if context_path.exists() and context_path.is_dir():
            # Count all .md files in the directory regardless of specific naming
            count = len(list(context_path.glob("*.md")))
        counts[context_type] = count
    
    return counts


def _get_package_display_info(package_path: Path) -> Dict[str, str]:
    """Get package display information."""
    try:
        apm_yml_path = package_path / "apm.yml"
        if apm_yml_path.exists():
            package = APMPackage.from_apm_yml(apm_yml_path)
            version_info = f"@{package.version}" if package.version else "@unknown"
            return {
                'display_name': f"{package.name}{version_info}",
                'name': package.name,
                'version': package.version or 'unknown'
            }
        else:
            return {
                'display_name': f"{package_path.name}@unknown",
                'name': package_path.name,
                'version': 'unknown'
            }
    except Exception:
        return {
            'display_name': f"{package_path.name}@error",
            'name': package_path.name,
            'version': 'error'
        }


def _get_detailed_package_info(package_path: Path) -> Dict[str, Any]:
    """Get detailed package information for the info command."""
    try:
        apm_yml_path = package_path / "apm.yml"
        if apm_yml_path.exists():
            package = APMPackage.from_apm_yml(apm_yml_path)
            context_count, workflow_count = _count_package_files(package_path)
            return {
                'name': package.name,
                'version': package.version or 'unknown',
                'description': package.description or 'No description',
                'author': package.author or 'Unknown',
                'source': package.source or 'local',
                'install_path': str(package_path.resolve()),
                'context_files': _get_detailed_context_counts(package_path),
                'workflows': workflow_count
            }
        else:
            context_count, workflow_count = _count_package_files(package_path)
            return {
                'name': package_path.name,
                'version': 'unknown',
                'description': 'No apm.yml found',
                'author': 'Unknown',
                'source': 'unknown',
                'install_path': str(package_path.resolve()),
                'context_files': _get_detailed_context_counts(package_path),
                'workflows': workflow_count
            }
    except Exception as e:
        return {
            'name': package_path.name,
            'version': 'error',
            'description': f'Error loading package: {e}',
            'author': 'Unknown',
            'source': 'unknown',
            'install_path': str(package_path.resolve()),
            'context_files': {'instructions': 0, 'chatmodes': 0, 'contexts': 0},
            'workflows': 0
        }


def _update_single_package(package_name: str, project_deps: List, apm_modules_path: Path):
    """Update a specific package."""
    # Find the dependency reference for this package
    target_dep = None
    for dep in project_deps:
        if dep.get_display_name() == package_name or dep.repo_url.split('/')[-1] == package_name:
            target_dep = dep
            break
    
    if not target_dep:
        _rich_error(f"Package '{package_name}' not found in apm.yml dependencies")
        return
    
    # Find the installed package directory using namespaced structure
    # GitHub: owner/repo (2 parts)
    # Azure DevOps: org/project/repo (3 parts)
    package_dir = None
    if target_dep.alias:
        package_dir = apm_modules_path / target_dep.alias
    else:
        # Parse path from repo_url
        repo_parts = target_dep.repo_url.split('/')
        if target_dep.is_azure_devops() and len(repo_parts) >= 3:
            # ADO structure: apm_modules/org/project/repo
            package_dir = apm_modules_path / repo_parts[0] / repo_parts[1] / repo_parts[2]
        elif len(repo_parts) >= 2:
            package_dir = apm_modules_path / repo_parts[0] / repo_parts[1]
        else:
            # Fallback to simple name matching
            package_dir = apm_modules_path / package_name
        
    if not package_dir.exists():
        _rich_error(f"Package '{package_name}' not installed in apm_modules/")
        _rich_info(f"Run 'apm install' to install it first")
        return
    
    try:
        downloader = GitHubPackageDownloader()
        _rich_info(f"Updating {target_dep.repo_url}...")
        
        # Download latest version
        package_info = downloader.download_package(str(target_dep), package_dir)
        
        _rich_success(f"✅ Updated {target_dep.repo_url}")
        
    except Exception as e:
        _rich_error(f"Failed to update {package_name}: {e}")


def _update_all_packages(project_deps: List, apm_modules_path: Path):
    """Update all packages."""
    if not project_deps:
        _rich_info("No APM dependencies to update")
        return
        
    _rich_info(f"Updating {len(project_deps)} APM dependencies...")
    
    downloader = GitHubPackageDownloader()
    updated_count = 0
    
    for dep in project_deps:
        # Determine package directory using namespaced structure
        # GitHub: apm_modules/owner/repo (2 parts)
        # Azure DevOps: apm_modules/org/project/repo (3 parts)
        if dep.alias:
            package_dir = apm_modules_path / dep.alias
        else:
            # Parse path from repo_url
            repo_parts = dep.repo_url.split('/')
            if dep.is_azure_devops() and len(repo_parts) >= 3:
                # ADO structure
                package_dir = apm_modules_path / repo_parts[0] / repo_parts[1] / repo_parts[2]
            elif len(repo_parts) >= 2:
                package_dir = apm_modules_path / repo_parts[0] / repo_parts[1]
            else:
                # Fallback to simple repo name (shouldn't happen)
                package_dir = apm_modules_path / dep.repo_url
            
        if not package_dir.exists():
            _rich_warning(f"⚠️ {dep.repo_url} not installed - skipping")
            continue
            
        try:
            _rich_info(f"  Updating {dep.repo_url}...")
            package_info = downloader.download_package(str(dep), package_dir)
            updated_count += 1
            _rich_success(f"  ✅ {dep.repo_url}")
            
        except Exception as e:
            _rich_error(f"  ❌ Failed to update {dep.repo_url}: {e}")
            continue
    
    _rich_success(f"Updated {updated_count} of {len(project_deps)} packages")

