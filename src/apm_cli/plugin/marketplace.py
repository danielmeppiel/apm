"""Plugin marketplace discovery and parsing."""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
import requests


@dataclass
class Plugin:
    """Represents a plugin from a marketplace."""
    
    id: str
    name: str
    description: str
    version: str
    repository: str
    marketplace_source: str  # Source marketplace URL
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert plugin to dictionary format."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "repository": self.repository,
            "marketplace_source": self.marketplace_source,
        }
    
    @classmethod
    def from_claude_format(cls, data: Dict[str, Any], marketplace_source: str) -> "Plugin":
        """Create a Plugin from Claude marketplace format.
        
        Args:
            data: Plugin data from marketplace.json
            marketplace_source: The marketplace URL this came from
            
        Returns:
            Plugin instance
        """
        # Claude format uses "source" field with relative paths
        # Default to marketplace source for plugins within the same repo
        repository = data.get("repository") or marketplace_source
        
        return cls(
            id=data.get("id") or data.get("name"),
            name=data.get("name"),
            description=data.get("description", ""),
            version=data.get("version", "latest"),
            repository=repository,
            marketplace_source=marketplace_source,
        )
    
    @classmethod
    def from_github_format(cls, data: Dict[str, Any], marketplace_source: str) -> "Plugin":
        """Create a Plugin from GitHub marketplace format.
        
        Args:
            data: Plugin data from marketplace.json
            marketplace_source: The marketplace URL this came from
            
        Returns:
            Plugin instance
        """
        return cls(
            id=data.get("id") or data.get("name"),
            name=data.get("name"),
            description=data.get("description", ""),
            version=data.get("version", "latest"),
            repository=data.get("repository") or data.get("url"),
            marketplace_source=marketplace_source,
        )


class MarketplaceManager:
    """Manages plugin marketplace discovery and parsing."""
    
    # Known marketplaces
    KNOWN_MARKETPLACES = {
        "claude": "https://github.com/anthropics/claude-code",
        "awesome-copilot": "https://github.com/github/awesome-copilot",
    }
    
    def __init__(self):
        """Initialize the marketplace manager."""
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
    
    def fetch_marketplace(self, marketplace_url: str) -> Dict[str, Any]:
        """Fetch and parse a marketplace.json file.
        
        Args:
            marketplace_url: URL to the marketplace (repo URL or direct marketplace.json URL)
            
        Returns:
            Parsed marketplace data with plugins list
            
        Raises:
            ValueError: If marketplace cannot be fetched or parsed
        """
        # Handle short names
        if marketplace_url in self.KNOWN_MARKETPLACES:
            marketplace_url = self.KNOWN_MARKETPLACES[marketplace_url]
        
        # Normalize GitHub URLs
        if marketplace_url.startswith("github.com/") or "github.com/" in marketplace_url:
            marketplace_url = f"https://{marketplace_url}" if not marketplace_url.startswith("http") else marketplace_url
            marketplace_url = marketplace_url.rstrip("/")
        
        # Try Claude format first: .claude-plugin/marketplace.json
        marketplace_data = self._try_fetch_marketplace_file(
            marketplace_url,
            ".claude-plugin/marketplace.json"
        )
        
        if marketplace_data:
            return {
                "plugins": [
                    Plugin.from_claude_format(p, marketplace_url).to_dict()
                    for p in marketplace_data.get("plugins", [])
                ]
            }
        
        # Try GitHub format: .github/plugin/marketplace.json
        marketplace_data = self._try_fetch_marketplace_file(
            marketplace_url,
            ".github/plugin/marketplace.json"
        )
        
        if marketplace_data:
            return {
                "plugins": [
                    Plugin.from_github_format(p, marketplace_url).to_dict()
                    for p in marketplace_data.get("plugins", [])
                ]
            }
        
        raise ValueError(
            f"Could not find marketplace.json in {marketplace_url}. "
            f"Tried: .claude-plugin/marketplace.json and .github/plugin/marketplace.json"
        )
    
    def _try_fetch_marketplace_file(self, marketplace_url: str, path: str) -> Optional[Dict[str, Any]]:
        """Try to fetch a marketplace file from a URL.
        
        Args:
            marketplace_url: Base marketplace URL
            path: Path to marketplace file (e.g., ".claude-plugin/marketplace.json")
            
        Returns:
            Parsed marketplace data or None if not found
        """
        # If it's a GitHub repo, construct raw.githubusercontent.com URL
        if "github.com" in marketplace_url:
            # Convert github.com/owner/repo to raw.githubusercontent.com/owner/repo/main
            parts = urlparse(marketplace_url)
            path_parts = parts.path.strip("/").split("/")
            
            if len(path_parts) >= 2:
                owner, repo = path_parts[0], path_parts[1]
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{path}"
            else:
                return None
        else:
            # For non-GitHub URLs, append the path directly
            raw_url = urljoin(marketplace_url.rstrip("/") + "/", path)
        
        try:
            response = self.session.get(raw_url, timeout=10)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, json.JSONDecodeError):
            return None
    
    def find_plugin(self, plugin_name: str, marketplace_url: str) -> Optional[Plugin]:
        """Find a plugin by name in a marketplace.
        
        Args:
            plugin_name: Name of the plugin to find
            marketplace_url: URL to the marketplace
            
        Returns:
            Plugin instance or None if not found
        """
        try:
            marketplace_data = self.fetch_marketplace(marketplace_url)
            for plugin_dict in marketplace_data.get("plugins", []):
                if plugin_dict["id"] == plugin_name:
                    return Plugin(**plugin_dict)
            return None
        except ValueError:
            return None
    
    def list_plugins(self, marketplace_url: str) -> List[Plugin]:
        """List all plugins in a marketplace.
        
        Args:
            marketplace_url: URL to the marketplace
            
        Returns:
            List of Plugin instances
            
        Raises:
            ValueError: If marketplace cannot be fetched
        """
        marketplace_data = self.fetch_marketplace(marketplace_url)
        return [
            Plugin(**plugin_dict)
            for plugin_dict in marketplace_data.get("plugins", [])
        ]
