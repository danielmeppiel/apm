"""Plugin installer for APM marketplace plugins."""

import json
import requests
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from ..deps.github_downloader import GitHubPackageDownloader
from ..models.apm_package import (
    DependencyReference,
    APMPackage,
    PackageInfo,
    ResolvedReference,
    GitReferenceType,
    validate_apm_package,
)
from ..models.plugin import Plugin, PluginMetadata, MarketplaceEntry
from ..utils.console import _get_console, STATUS_SYMBOLS
from ..integration.prompt_integrator import PromptIntegrator
from ..integration.agent_integrator import AgentIntegrator
from ..integration.skill_integrator import SkillIntegrator
from ..integration.command_integrator import CommandIntegrator
from ..core.target_detection import (
    detect_target,
    should_integrate_vscode,
    should_integrate_claude,
)


class PluginAlreadyInstalledException(Exception):
    """Raised when trying to install a plugin that is already installed."""
    pass


class PluginNotFoundException(Exception):
    """Raised when a plugin is not found in the marketplace."""
    pass


class PluginInstaller:
    """Manages plugin installation from the APM marketplace.
    
    This installer:
    - Downloads plugins from GitHub or Azure DevOps repositories
    - Validates plugin structure and metadata
    - Installs plugins to the plugins/ directory
    - Handles plugin dependencies
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize the plugin installer.
        
        Args:
            base_dir: Base directory for the APM project (defaults to current directory)
        """
        self.base_dir = Path(base_dir or Path.cwd())
        self.apm_modules_dir = self.base_dir / "apm_modules"
        self.downloader = GitHubPackageDownloader()
        self.marketplace_url = "https://raw.githubusercontent.com/danielmeppiel/apm/main/.github/plugin/marketplace.json"
        self._marketplace_cache: Optional[List[MarketplaceEntry]] = None
        
        # Initialize integrators
        self.prompt_integrator = PromptIntegrator()
        self.agent_integrator = AgentIntegrator()
        self.skill_integrator = SkillIntegrator()
        self.command_integrator = CommandIntegrator()
    
    def _load_marketplace(self) -> List[MarketplaceEntry]:
        """Load the marketplace catalog.
        
        Returns:
            List of marketplace entries
            
        Raises:
            RuntimeError: If marketplace cannot be loaded
        """
        if self._marketplace_cache is not None:
            return self._marketplace_cache
        
        try:
            response = requests.get(self.marketplace_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            entries = [MarketplaceEntry.from_dict(plugin) for plugin in data.get("plugins", [])]
            self._marketplace_cache = entries
            return entries
        except Exception as e:
            raise RuntimeError(f"Failed to load marketplace: {e}")
    
    def search(self, query: Optional[str] = None, tags: Optional[List[str]] = None) -> List[MarketplaceEntry]:
        """Search for plugins in the marketplace.
        
        Args:
            query: Search query (searches in name and description)
            tags: Filter by tags
            
        Returns:
            List of matching marketplace entries
        """
        entries = self._load_marketplace()
        
        if query:
            query_lower = query.lower()
            entries = [
                e for e in entries
                if query_lower in e.name.lower() or query_lower in e.description.lower()
            ]
        
        if tags:
            tag_set = set(t.lower() for t in tags)
            entries = [
                e for e in entries
                if any(tag.lower() in tag_set for tag in e.tags)
            ]
        
        return entries
    
    def get_plugin_info(self, plugin_name: str) -> MarketplaceEntry:
        """Get information about a plugin from the marketplace.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            MarketplaceEntry for the plugin
            
        Raises:
            PluginNotFoundException: If plugin is not found
        """
        entries = self._load_marketplace()
        for entry in entries:
            if entry.name == plugin_name:
                return entry
        
        raise PluginNotFoundException(f"Plugin '{plugin_name}' not found in marketplace")
    
    def _search_plugin_in_dir(self, owner_dir: Path, plugin_name: str) -> bool:
        """Search for plugin in owner directory."""
        if not owner_dir.is_dir():
            return False
        
        for repo_dir in owner_dir.iterdir():
            if self._is_plugin_dir(repo_dir, plugin_name):
                return True
        return False
    
    def _is_plugin_dir(self, repo_dir: Path, plugin_name: str) -> bool:
        """Check if directory contains the plugin."""
        if not repo_dir.is_dir():
            return False
        
        plugin_json = repo_dir / "plugin.json"
        if not plugin_json.exists():
            return False
        
        return self._plugin_name_matches(plugin_json, plugin_name)
    
    def _plugin_name_matches(self, plugin_json: Path, plugin_name: str) -> bool:
        """Check if plugin.json contains matching name."""
        try:
            with open(plugin_json) as f:
                data = json.load(f)
                return data.get("name") == plugin_name
        except (json.JSONDecodeError, OSError):
            return False
    
    def is_installed(self, plugin_name: str) -> bool:
        """Check if a plugin is installed.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            True if plugin is installed
        """
        if not self.apm_modules_dir.exists():
            return False
        
        for owner_dir in self.apm_modules_dir.iterdir():
            if self._search_plugin_in_dir(owner_dir, plugin_name):
                return True
        return False
    
    def _try_load_plugin(self, repo_dir: Path) -> Optional[Plugin]:
        """Try to load plugin from directory."""
        try:
            return Plugin.from_path(repo_dir)
        except (FileNotFoundError, ValueError):
            return None
    
    def _collect_plugins_from_owner_dir(self, owner_dir: Path) -> List[Plugin]:
        """Collect all plugins from owner directory."""
        if not owner_dir.is_dir():
            return []
        
        plugins = []
        for repo_dir in owner_dir.iterdir():
            if self._is_plugin_directory(repo_dir):
                plugin = self._try_load_plugin(repo_dir)
                if plugin:
                    plugins.append(plugin)
        return plugins
    
    def _is_plugin_directory(self, repo_dir: Path) -> bool:
        """Check if directory is a plugin directory."""
        return repo_dir.is_dir() and (repo_dir / "plugin.json").exists()
    
    def list_installed(self) -> List[Plugin]:
        """List all installed plugins.
        
        Returns:
            List of installed plugins
        """
        if not self.apm_modules_dir.exists():
            return []
        
        plugins = []
        for owner_dir in self.apm_modules_dir.iterdir():
            plugins.extend(self._collect_plugins_from_owner_dir(owner_dir))
        return plugins
    
    def _build_repository_reference(self, entry: MarketplaceEntry) -> str:
        """Build full repository reference from entry."""
        if not entry.host:
            return entry.repository
        
        return self._build_hosted_reference(entry)
    
    def _build_hosted_reference(self, entry: MarketplaceEntry) -> str:
        """Build repository reference with host."""
        if entry.host in ["github", "github.com"]:
            return entry.repository
        
        if entry.host in ["ado", "dev.azure.com"]:
            return f"dev.azure.com/{entry.repository}"
        
        return f"{entry.host}/{entry.repository}"
    
    def _validate_plugin_structure(self, temp_path: Path, entry: MarketplaceEntry) -> None:
        """Validate plugin has required files."""
        plugin_json = temp_path / "plugin.json"
        if not plugin_json.exists():
            raise RuntimeError(
                f"Invalid plugin: plugin.json not found in {entry.repository}"
            )
    
    def _copy_plugin_files(self, temp_path: Path, destination: Path) -> None:
        """Copy plugin files to destination."""
        destination.mkdir(parents=True, exist_ok=True)
        
        for item in temp_path.iterdir():
            if item.name != '.git':
                self._copy_item(item, destination / item.name)
    
    def _copy_item(self, source: Path, destination: Path) -> None:
        """Copy file or directory."""
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)
    
    def _download_to_temp(self, dep_ref: DependencyReference, repo_ref: str) -> Path:
        """Download plugin to temporary directory."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / "plugin"
        
        console = _get_console()
        if console:
            console.print(f"{STATUS_SYMBOLS.get('download', '📥')} Downloading from {repo_ref}...")
        
        self.downloader._clone_with_fallback(
            repo_url_base=dep_ref.repo_url,
            target_path=temp_path,
            dep_ref=dep_ref,
            depth=1
        )
        
        return temp_path
    
    def _download_plugin(self, entry: MarketplaceEntry, destination: Path) -> None:
        """Download a plugin from its repository.
        
        Args:
            entry: Marketplace entry for the plugin
            destination: Destination path for the plugin
            
        Raises:
            RuntimeError: If download fails
        """
        repo_ref = self._build_repository_reference(entry)
        dep_ref = DependencyReference.parse(repo_ref)
        temp_path = self._download_to_temp(dep_ref, repo_ref)
        
        try:
            self._validate_plugin_structure(temp_path, entry)
            self._copy_plugin_files(temp_path, destination)
        finally:
            shutil.rmtree(temp_path.parent)
    
    def _validate_plugin_metadata(self, plugin_path: Path, expected_name: str) -> PluginMetadata:
        """Validate plugin metadata.
        
        Args:
            plugin_path: Path to the plugin directory
            expected_name: Expected plugin name
            
        Returns:
            PluginMetadata from the plugin
            
        Raises:
            ValueError: If validation fails
        """
        metadata_file = plugin_path / "plugin.json"
        
        with open(metadata_file, "r") as f:
            data = json.load(f)
        
        metadata = PluginMetadata.from_dict(data)
        
        if metadata.name != expected_name:
            raise ValueError(
                f"Plugin name mismatch: expected '{expected_name}', got '{metadata.name}'"
            )
        
        return metadata
    
    def _ensure_github_directory_exists(self) -> None:
        """Create .github/ directory if needed."""
        github_dir = self.base_dir / ".github"
        claude_dir = self.base_dir / ".claude"
        
        if self._should_create_github_dir(github_dir, claude_dir):
            self._create_github_directory(github_dir)
    
    def _should_create_github_dir(self, github_dir: Path, claude_dir: Path) -> bool:
        """Check if .github/ directory should be created."""
        return not github_dir.exists() and not claude_dir.exists()
    
    def _create_github_directory(self, github_dir: Path) -> None:
        """Create .github/ directory and notify user."""
        github_dir.mkdir(parents=True, exist_ok=True)
        console = _get_console()
        if console:
            console.print(f"   Created .github/ as standard skills root and to enable VSCode/Copilot integration")
    
    def _detect_integration_target(self) -> Tuple[bool, bool]:
        """Detect if VSCode and/or Claude integration should be performed.
        
        Returns:
            Tuple of (integrate_vscode, integrate_claude)
        """
        self._ensure_github_directory_exists()
        detected_target, _ = detect_target(project_root=self.base_dir)
        return (
            should_integrate_vscode(detected_target),
            should_integrate_claude(detected_target)
        )
    
    def _load_or_create_package(self, plugin_path: Path, entry: MarketplaceEntry) -> APMPackage:
        """Load existing package or create minimal one."""
        result = validate_apm_package(plugin_path)
        
        if result and result.package:
            return result.package
        
        return self._create_minimal_package(entry, plugin_path)
    
    def _create_minimal_package(self, entry: MarketplaceEntry, plugin_path: Path) -> APMPackage:
        """Create minimal APMPackage from entry metadata."""
        return APMPackage(
            name=entry.name,
            version=entry.version,
            package_path=plugin_path,
            source=entry.repository,
        )
    
    def _create_resolved_reference(self, dep_ref: DependencyReference) -> ResolvedReference:
        """Create resolved reference for plugin."""
        return ResolvedReference(
            original_ref=dep_ref.reference or "latest",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="latest",
            ref_name=dep_ref.reference or "main",
        )
    
    def _create_package_info(self, plugin_path: Path, entry: MarketplaceEntry) -> PackageInfo:
        """Create PackageInfo from installed plugin.
        
        Args:
            plugin_path: Path to the installed plugin
            entry: Marketplace entry for the plugin
            
        Returns:
            PackageInfo instance
        """
        package = self._load_or_create_package(plugin_path, entry)
        dep_ref = DependencyReference.parse(entry.repository)
        resolved_ref = self._create_resolved_reference(dep_ref)
        
        return PackageInfo(
            package=package,
            install_path=plugin_path,
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat(),
            dependency_ref=dep_ref,
        )
    
    def _integrate_prompts(self, package_info: PackageInfo) -> int:
        """Integrate prompts and return count."""
        result = self.prompt_integrator.integrate_package_prompts(
            package_info, self.base_dir
        )
        
        if result.files_integrated > 0:
            console = _get_console()
            if console:
                console.print(
                    f"   ├─ {result.files_integrated} prompts integrated → .github/prompts/"
                )
        
        return result.files_integrated
    
    def _integrate_agents(self, package_info: PackageInfo) -> int:
        """Integrate agents and return count."""
        result = self.agent_integrator.integrate_package_agents(
            package_info, self.base_dir
        )
        
        if result.files_integrated > 0:
            console = _get_console()
            if console:
                console.print(
                    f"   ├─ {result.files_integrated} agents integrated → .github/agents/"
                )
        
        return result.files_integrated
    
    def _integrate_skills(self, package_info: PackageInfo) -> int:
        """Integrate skills and return count."""
        result = self.skill_integrator.integrate_package_skill(
            package_info, self.base_dir
        )
        
        if result.skill_created:
            console = _get_console()
            if console:
                console.print(f"   ├─ Skill integrated → .github/skills/")
            return 1
        
        return 0
    
    def _integrate_commands(self, package_info: PackageInfo) -> int:
        """Integrate commands and return count."""
        result = self.command_integrator.integrate_package_commands(
            package_info, self.base_dir
        )
        
        if result.files_integrated > 0:
            console = _get_console()
            if console:
                console.print(
                    f"   ├─ {result.files_integrated} commands integrated → .claude/commands/"
                )
        
        return result.files_integrated
    
    def _integrate_vscode_primitives(self, package_info: PackageInfo, stats: Dict[str, int]) -> None:
        """Integrate VSCode-specific primitives."""
        stats["prompts"] = self._integrate_prompts(package_info)
        stats["agents"] = self._integrate_agents(package_info)
    
    def _integrate_skill_primitives(self, package_info: PackageInfo, stats: Dict[str, int]) -> None:
        """Integrate skill primitives."""
        stats["skills"] = self._integrate_skills(package_info)
    
    def _integrate_claude_primitives(self, package_info: PackageInfo, stats: Dict[str, int]) -> None:
        """Integrate Claude-specific primitives."""
        stats["commands"] = self._integrate_commands(package_info)
    
    def _integrate_plugin_primitives(
        self,
        package_info: PackageInfo,
        integrate_vscode: bool,
        integrate_claude: bool,
    ) -> Dict[str, int]:
        """Integrate plugin primitives into project.
        
        Args:
            package_info: Package information
            integrate_vscode: Whether to integrate VSCode primitives
            integrate_claude: Whether to integrate Claude primitives
            
        Returns:
            Dictionary with integration statistics
        """
        stats = {"prompts": 0, "agents": 0, "skills": 0, "commands": 0}
        
        try:
            if integrate_vscode:
                self._integrate_vscode_primitives(package_info, stats)
            
            if integrate_vscode or integrate_claude:
                self._integrate_skill_primitives(package_info, stats)
            
            if integrate_claude:
                self._integrate_claude_primitives(package_info, stats)
        
        except Exception as e:
            console = _get_console()
            if console:
                console.print(f"   ⚠ Failed to integrate primitives: {e}")
        
        return stats
    
    def _check_not_already_installed(self, plugin_name: str) -> None:
        """Raise exception if plugin is already installed."""
        if self.is_installed(plugin_name):
            raise PluginAlreadyInstalledException(
                f"Plugin '{plugin_name}' is already installed"
            )
    
    def _print_plugin_info(self, entry: MarketplaceEntry) -> None:
        """Print plugin installation information."""
        console = _get_console()
        if console:
            console.print(
                f"\n{STATUS_SYMBOLS.get('plugin', '🔌')} Installing plugin: [bold]{entry.name}[/bold]"
            )
            console.print(f"   Repository: {entry.repository}")
            console.print(f"   Version: {entry.version}")
            console.print(f"   Author: {entry.author}")
    
    def _create_mock_plugin(self, entry: MarketplaceEntry, plugin_path: Path) -> Plugin:
        """Create mock plugin for dry run."""
        return Plugin(
            metadata=PluginMetadata(
                id=entry.id,
                name=entry.name,
                version=entry.version,
                description=entry.description,
                author=entry.author,
                repository=entry.repository,
            ),
            path=plugin_path,
        )
    
    def _handle_dry_run(self, entry: MarketplaceEntry) -> Plugin:
        """Handle dry run mode and return mock plugin."""
        console = _get_console()
        if console:
            console.print(
                f"\n{STATUS_SYMBOLS.get('success', '✓')} [bold green]Dry run completed[/bold green] - no changes made"
            )
        dep_ref = DependencyReference.parse(entry.repository)
        plugin_path = self.apm_modules_dir / dep_ref.repo_url
        return self._create_mock_plugin(entry, plugin_path)
    
    def _install_dependencies(self, metadata: PluginMetadata) -> None:
        """Install plugin dependencies if any."""
        if not metadata.dependencies:
            return
        
        console = _get_console()
        if console:
            console.print(f"\n{STATUS_SYMBOLS.get('info', 'ℹ')} Installing dependencies...")
        
        for dep_id in metadata.dependencies:
            self._install_single_dependency(dep_id)
    
    def _install_single_dependency(self, dep_id: str) -> None:
        """Install a single dependency."""
        console = _get_console()
        if not self.is_installed(dep_id):
            if console:
                console.print(f"   Installing dependency: {dep_id}")
            self.install(dep_id, dry_run=False)
        else:
            if console:
                console.print(f"   Dependency already installed: {dep_id}")
    
    def _perform_integration(self, plugin_path: Path, entry: MarketplaceEntry) -> Dict[str, int]:
        """Perform primitive integration and return stats."""
        integrate_vscode, integrate_claude = self._detect_integration_target()
        package_info = self._create_package_info(plugin_path, entry)
        
        console = _get_console()
        if console:
            console.print(f"\n{STATUS_SYMBOLS.get('info', 'ℹ')} Integrating plugin primitives...")
        
        return self._integrate_plugin_primitives(
            package_info,
            integrate_vscode,
            integrate_claude,
        )
    
    def _print_integration_summary(self, stats: Dict[str, int]) -> None:
        """Print integration summary if any primitives were integrated."""
        total_integrated = sum(stats.values())
        
        if total_integrated == 0:
            return
        
        console = _get_console()
        if console:
            console.print(f"\n   Integration Summary:")
            
            if stats["prompts"] > 0:
                console.print(f"      └─ {stats['prompts']} prompts")
            if stats["agents"] > 0:
                console.print(f"      └─ {stats['agents']} agents")
            if stats["skills"] > 0:
                console.print(f"      └─ {stats['skills']} skills")
            if stats["commands"] > 0:
                console.print(f"      └─ {stats['commands']} commands")
    
    def _cleanup_failed_installation(self, plugin_path: Path) -> None:
        """Clean up plugin directory after failed installation."""
        if plugin_path.exists():
            shutil.rmtree(plugin_path)
    
    def _perform_installation(
        self,
        plugin_name: str,
        entry: MarketplaceEntry,
        plugin_path: Path
    ) -> Plugin:
        """Perform the actual plugin installation."""
        self._download_plugin(entry, plugin_path)
        metadata = self._validate_plugin_metadata(plugin_path, plugin_name)
        self._install_dependencies(metadata)
        
        integration_stats = self._perform_integration(plugin_path, entry)
        plugin = Plugin.from_path(plugin_path)
        
        console.print(
            f"\n{STATUS_SYMBOLS.get('success', '✓')} [bold green]Plugin installed successfully![/bold green]"
        )
        self._print_integration_summary(integration_stats)
        
        return plugin
    
    def install(self, plugin_name: str, dry_run: bool = False) -> Plugin:
        """Install a plugin from the marketplace.
        
        Args:
            plugin_name: Plugin name
            dry_run: If True, simulate installation without making changes
            
        Returns:
            Installed Plugin instance
            
        Raises:
            PluginNotFoundException: If plugin is not found in marketplace
            PluginAlreadyInstalledException: If plugin is already installed
            RuntimeError: If installation fails
        """
        self._check_not_already_installed(plugin_name)
        entry = self.get_plugin_info(plugin_name)
        self._print_plugin_info(entry)
        
        if dry_run:
            return self._handle_dry_run(entry)
        
        dep_ref = DependencyReference.parse(entry.repository)
        plugin_path = self.apm_modules_dir / dep_ref.repo_url
        
        try:
            return self._perform_installation(plugin_name, entry, plugin_path)
        except Exception as e:
            self._cleanup_failed_installation(plugin_path)
            raise RuntimeError(f"Failed to install plugin '{plugin_name}': {e}")
    
    def _find_and_remove_plugin(self, plugin_name: str) -> bool:
        """Find and remove plugin from apm_modules/."""
        for owner_dir in self.apm_modules_dir.iterdir():
            if self._try_remove_from_owner_dir(owner_dir, plugin_name):
                return True
        return False
    
    def _try_remove_from_owner_dir(self, owner_dir: Path, plugin_name: str) -> bool:
        """Try to remove plugin from owner directory."""
        if not owner_dir.is_dir():
            return False
        
        for repo_dir in owner_dir.iterdir():
            if self._try_remove_plugin_dir(repo_dir, plugin_name):
                return True
        return False
    
    def _try_remove_plugin_dir(self, repo_dir: Path, plugin_name: str) -> bool:
        """Try to remove plugin directory if it matches."""
        if not repo_dir.is_dir():
            return False
        
        plugin_json = repo_dir / "plugin.json"
        if not plugin_json.exists():
            return False
        
        if self._matches_and_remove(plugin_json, repo_dir, plugin_name):
            return True
        return False
    
    def _matches_and_remove(self, plugin_json: Path, repo_dir: Path, plugin_name: str) -> bool:
        """Check if plugin matches and remove it."""
        try:
            with open(plugin_json) as f:
                data = json.load(f)
                if data.get("name") == plugin_name:
                    shutil.rmtree(repo_dir)
                    console.print(
                        f"{STATUS_SYMBOLS.get('success', '✓')} Plugin '{plugin_name}' uninstalled"
                    )
                    return True
        except (json.JSONDecodeError, OSError):
            # Skip invalid plugin.json or inaccessible directories
            pass
        return False
    
    def uninstall(self, plugin_name: str) -> None:
        """Uninstall a plugin.
        
        Args:
            plugin_name: Plugin name
            
        Raises:
            PluginNotFoundException: If plugin is not installed
        """
        if not self.is_installed(plugin_name):
            raise PluginNotFoundException(f"Plugin '{plugin_name}' is not installed")
        
        if not self._find_and_remove_plugin(plugin_name):
            raise PluginNotFoundException(
                f"Plugin '{plugin_name}' not found in apm_modules/"
            )
