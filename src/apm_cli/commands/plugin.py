"""APM plugin management commands."""

import json
import click
from pathlib import Path
from typing import Dict, Any
import yaml

from ..plugin.resolver import PluginResolver
from ..plugin.plugin_installer import (
    PluginInstaller,
    PluginAlreadyInstalledException,
    PluginNotFoundException,
)
from ..utils.console import _rich_success, _rich_error, _rich_info, _rich_warning, _get_console, STATUS_SYMBOLS
from rich.table import Table
from rich.panel import Panel


@click.group(help="Manage APM plugins from Claude Code and GitHub marketplaces")
def plugin():
    """APM plugin management commands."""
    pass


@plugin.command(name="install", help="📦 Install a plugin from marketplace")
@click.argument("plugin_spec")
def install_plugin(plugin_spec: str):
    """Install a plugin from a marketplace.
    
    PLUGIN_SPEC: Plugin specification in format "plugin-name@marketplace-name"
                 Examples:
                 - commit-commands@claude
                 - my-skill@https://github.com/owner/repo
                 - plugin-name@awesome-copilot
    """
    try:
        resolver = PluginResolver()
        
        # Show what we're installing
        _rich_info(f"🔍 Resolving plugin: {plugin_spec}")
        
        # Resolve plugin to repository URL
        plugin_name, repo_url = resolver.resolve_plugin(plugin_spec)
        _rich_success(f"✓ Found plugin '{plugin_name}' at {repo_url}")
        
        # Check if apm.yml exists
        apm_yml_path = Path("apm.yml")
        if not apm_yml_path.exists():
            _rich_error("❌ apm.yml not found. Run this command in an APM project root.")
            raise click.Abort()
        
        # Track plugin installation  
        _track_plugin_in_apm_yml(plugin_name, repo_url, plugin_spec)
        
        _rich_success(f"✅ Plugin '{plugin_name}' tracked in apm.yml")
        _rich_info(f"💡 Run 'apm install' to download and integrate plugin primitives into your project")
        
    except ValueError as e:
        _rich_error(f"❌ {str(e)}")
        raise click.Abort()
    except Exception as e:
        _rich_error(f"❌ Unexpected error: {str(e)}")
        raise click.Abort()


@plugin.command(name="list", help="📋 List available plugins in a marketplace")
@click.argument("marketplace", default="claude", required=False)
def list_plugins(marketplace: str = "claude"):
    """List all plugins available in a marketplace.
    
    MARKETPLACE: Marketplace identifier or URL (default: "claude")
                Examples: claude, github, https://github.com/owner/repo
    """
    try:
        resolver = PluginResolver()
        
        _rich_info(f"🔍 Fetching plugins from marketplace: {marketplace}")
        
        # Resolve marketplace URL
        marketplace_url = resolver._resolve_marketplace_url(marketplace)
        
        # List plugins
        plugins = resolver.marketplace_manager.list_plugins(marketplace_url)
        
        if not plugins:
            _rich_info(f"📭 No plugins found in {marketplace}")
            return
        
        # Display plugins table
        from rich.table import Table
        from rich.console import Console
        
        table = Table(title=f"Plugins in {marketplace}")
        
        table.add_column("Plugin ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Description", style="white")
        table.add_column("Version", style="yellow")
        
        for plugin in plugins:
            table.add_row(
                plugin.id,
                plugin.name,
                plugin.description[:50] + "..." if len(plugin.description) > 50 else plugin.description,
                plugin.version
            )
        
        console = _get_console()
        if console:
            console.print(table)
        
        _rich_info(f"💡 Install a plugin with: apm plugin install <plugin-id>@{marketplace or 'claude'}")
        
    except ValueError as e:
        _rich_error(f"❌ {str(e)}")
        raise click.Abort()
    except Exception as e:
        _rich_error(f"❌ Unexpected error: {str(e)}")
        raise click.Abort()


def _track_plugin_in_apm_yml(plugin_name: str, repo_url: str, plugin_spec: str) -> None:
    """Track plugin installation in apm.yml.
    
    Args:
        plugin_name: The plugin name
        repo_url: The repository URL
        plugin_spec: The original plugin specification
    """
    apm_yml_path = Path("apm.yml")
    
    # Load existing apm.yml
    with open(apm_yml_path, "r") as f:
        data = yaml.safe_load(f) or {}
    
    # Ensure plugins section exists
    if "plugins" not in data:
        data["plugins"] = []
    
    # Check if plugin already installed
    existing_plugin = next(
        (p for p in data["plugins"] if p.get("name") == plugin_name),
        None
    )
    
    if existing_plugin:
        _rich_warning(f"⚠️  Plugin '{plugin_name}' already tracked in apm.yml")
        return
    
    # Add plugin entry
    plugin_entry = {
        "name": plugin_name,
        "source": repo_url,
        "version": "latest"
    }
    
    data["plugins"].append(plugin_entry)
    
    # Write back to apm.yml
    with open(apm_yml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


@plugin.command(name="search", help="🔍 Search for plugins in the marketplace")
@click.argument("query", required=False)
@click.option("--tag", "-t", multiple=True, help="Filter by tag")
def search_plugins(query: str = None, tag: tuple = ()):
    """Search for plugins in the APM marketplace.
    
    QUERY: Optional search query (searches in name and description)
    """
    try:
        installer = PluginInstaller()
        
        # Convert tag tuple to list
        tags = list(tag) if tag else None
        
        # Search marketplace
        results = installer.search(query=query, tags=tags)
        
        if not results:
            _rich_info(f"{STATUS_SYMBOLS.get('search', '🔍')} No plugins found matching your search")
            return
        
        # Display results in a table
        table = Table(title=f"Plugin Search Results ({len(results)} found)")
        
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Description", style="white")
        table.add_column("Author", style="yellow")
        table.add_column("Tags", style="magenta")
        
        for entry in results:
            tags_str = ", ".join(entry.tags[:3]) if entry.tags else ""
            if len(entry.tags) > 3:
                tags_str += "..."
            
            table.add_row(
                entry.id,
                entry.name,
                entry.description[:50] + "..." if len(entry.description) > 50 else entry.description,
                entry.author,
                tags_str,
            )
        
        console = _get_console()
        if console:
            console.print(table)
            console.print(f"\n{STATUS_SYMBOLS.get('info', '💡')} Install with: [bold]apm plugin install <plugin-id>[/bold]")
            console.print(f"{STATUS_SYMBOLS.get('info', '💡')} Show details with: [bold]apm plugin info <plugin-id>[/bold]")
        
    except Exception as e:
        _rich_error(f"❌ Error searching marketplace: {str(e)}")
        raise click.Abort()


@plugin.command(name="info", help="ℹ️ Show detailed information about a plugin")
@click.argument("plugin_name")
def plugin_info(plugin_name: str):
    """Show detailed information about a plugin from the marketplace.
    
    PLUGIN_NAME: The plugin name
    """
    try:
        installer = PluginInstaller()
        
        # Get plugin info
        entry = installer.get_plugin_info(plugin_name)
        
        # Check if installed
        is_installed = installer.is_installed(plugin_name)
        
        # Build info text
        info_lines = [
            f"[bold cyan]{entry.name}[/bold cyan]",
            f"",
            f"[bold]ID:[/bold] {entry.id}",
            f"[bold]Version:[/bold] {entry.version}",
            f"[bold]Author:[/bold] {entry.author}",
            f"[bold]Repository:[/bold] {entry.repository}",
            f"",
            f"[bold]Description:[/bold]",
            f"{entry.description}",
        ]
        
        if entry.tags:
            info_lines.extend([
                f"",
                f"[bold]Tags:[/bold] {', '.join(entry.tags)}",
            ])
        
        info_lines.extend([
            f"",
            f"[bold]Status:[/bold] {'[green]Installed ✓[/green]' if is_installed else '[yellow]Not installed[/yellow]'}",
        ])
        
        if entry.downloads > 0:
            info_lines.append(f"[bold]Downloads:[/bold] {entry.downloads}")
        
        if entry.stars > 0:
            info_lines.append(f"[bold]Stars:[/bold] {entry.stars}")
        
        # Display panel
        panel = Panel(
            "\n".join(info_lines),
            title=f"{STATUS_SYMBOLS.get('plugin', '🔌')} Plugin Information",
            border_style="cyan",
        )
        
        console = _get_console()
        if console:
            console.print(panel)
        
        if not is_installed:
            if console:
                console.print(f"\n{STATUS_SYMBOLS.get('info', '💡')} Install with: [bold]apm plugin install {plugin_id}[/bold]")
        
    except PluginNotFoundException as e:
        _rich_error(f"❌ {str(e)}")
        raise click.Abort()
    except Exception as e:
        _rich_error(f"❌ Error fetching plugin info: {str(e)}")
        raise click.Abort()


@plugin.command(name="installed", help="📋 List installed plugins")
def list_installed_plugins():
    """List all plugins installed in the current project."""
    try:
        installer = PluginInstaller()
        
        plugins = installer.list_installed()
        
        if not plugins:
            _rich_info(f"{STATUS_SYMBOLS.get('info', '💡')} No plugins installed")
            _rich_info(f"💡 Search marketplace with: apm plugin search")
            return
        
        # Display plugins in a table
        table = Table(title=f"Installed Plugins ({len(plugins)})")
        
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Version", style="yellow")
        table.add_column("Components", style="white")
        
        for plugin in plugins:
            components = []
            if plugin.agents:
                components.append(f"{len(plugin.agents)} agents")
            if plugin.skills:
                components.append(f"{len(plugin.skills)} skills")
            if plugin.commands:
                components.append(f"{len(plugin.commands)} commands")
            
            components_str = ", ".join(components) if components else "None"
            
            table.add_row(
                plugin.metadata.id,
                plugin.metadata.name,
                plugin.metadata.version,
                components_str,
            )
        
        console = _get_console()
        if console:
            console.print(table)
        
    except Exception as e:
        _rich_error(f"❌ Error listing plugins: {str(e)}")
        raise click.Abort()

