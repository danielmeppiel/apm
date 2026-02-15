"""Plugin name resolution and download coordination."""

from typing import Optional, Tuple
from pathlib import Path
from .marketplace import MarketplaceManager, Plugin


class PluginResolver:
    """Resolves plugin names to repository URLs and coordinates downloads."""
    
    def __init__(self):
        """Initialize the plugin resolver."""
        self.marketplace_manager = MarketplaceManager()
    
    def resolve_plugin(self, plugin_spec: str) -> Tuple[str, str]:
        """Resolve a plugin specification to a repository URL.
        
        Args:
            plugin_spec: Plugin specification in format "plugin-name@marketplace-name"
                        Examples:
                        - "commit-commands@claude" -> From Claude official marketplace
                        - "my-plugin@https://github.com/owner/repo" -> From custom marketplace
                        - "skill@github" -> From GitHub plugins
            
        Returns:
            Tuple of (plugin_name, repository_url)
            
        Raises:
            ValueError: If plugin specification is invalid or plugin not found
        """
        # Parse plugin specification
        if "@" not in plugin_spec:
            raise ValueError(
                f"Invalid plugin specification: {plugin_spec}. "
                f"Format: plugin-name@marketplace-name or plugin-name@url"
            )
        
        plugin_name, marketplace_source = plugin_spec.rsplit("@", 1)
        
        if not plugin_name or not marketplace_source:
            raise ValueError(
                f"Invalid plugin specification: {plugin_spec}. "
                f"Both plugin-name and marketplace-name required."
            )
        
        # Resolve marketplace source
        marketplace_url = self._resolve_marketplace_url(marketplace_source)
        
        # Find plugin in marketplace
        plugin = self.marketplace_manager.find_plugin(plugin_name, marketplace_url)
        
        if not plugin:
            raise ValueError(
                f"Plugin '{plugin_name}' not found in marketplace '{marketplace_source}'"
            )
        
        return plugin.name, plugin.repository
    
    def _resolve_marketplace_url(self, marketplace_source: str) -> str:
        """Resolve marketplace source to a URL.
        
        Args:
            marketplace_source: Marketplace identifier or URL
                               Examples: "claude", "https://github.com/owner/repo"
            
        Returns:
            Marketplace URL
            
        Raises:
            ValueError: If marketplace source is invalid
        """
        # Handle 'claude' shorthand for Claude official marketplace
        if marketplace_source == "claude":
            return "https://github.com/anthropics/claude-code"
        
        # If it's a URL, use it directly
        if marketplace_source.startswith("http://") or marketplace_source.startswith("https://"):
            return marketplace_source
        
        # GitHub paths without protocol
        if "github.com/" in marketplace_source:
            return f"https://{marketplace_source}"
        
        # Default to GitHub if it looks like owner/repo
        if "/" in marketplace_source and not "." in marketplace_source:
            return f"https://github.com/{marketplace_source}"
        
        raise ValueError(
            f"Invalid marketplace source: {marketplace_source}. "
            f"Use 'claude' for Claude official, a GitHub 'owner/repo', "
            f"or a full URL."
        )
