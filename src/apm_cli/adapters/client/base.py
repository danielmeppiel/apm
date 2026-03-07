"""Base adapter interface for MCP clients."""

from abc import ABC, abstractmethod


class MCPClientAdapter(ABC):
    """Base adapter for MCP clients."""

    @abstractmethod
    def get_config_path(self):
        """Get the path to the MCP configuration file."""
        pass

    @abstractmethod
    def update_config(self, config_updates):
        """Update the MCP configuration."""
        pass

    @abstractmethod
    def get_current_config(self):
        """Get the current MCP configuration."""
        pass

    @abstractmethod
    def configure_mcp_server(self, server_url, server_name=None, enabled=True, env_overrides=None, server_info_cache=None, runtime_vars=None):
        """Configure an MCP server in the client configuration.

        Args:
            server_url (str): URL of the MCP server.
            server_name (str, optional): Name of the server. Defaults to None.
            enabled (bool, optional): Whether to enable the server. Defaults to True.
            env_overrides (dict, optional): Environment variable overrides. Defaults to None.
            server_info_cache (dict, optional): Pre-fetched server info to avoid duplicate registry calls.
            runtime_vars (dict, optional): Runtime variable values. Defaults to None.

        Returns:
            bool: True if successful, False otherwise.
        """
        pass

    @staticmethod
    def _infer_registry_name(package):
        """Infer the registry type from package metadata.

        The MCP registry API often returns empty ``registry_name``.  This
        method derives the registry from explicit fields first, then falls
        back to heuristics on the package name.

        Args:
            package (dict): A single package entry from the registry.

        Returns:
            str: Inferred registry name (e.g. "npm", "pypi", "docker") or "".
        """
        if not package:
            return ""

        explicit = package.get("registry_name", "")
        if explicit:
            return explicit

        name = package.get("name", "")
        runtime_hint = package.get("runtime_hint", "")

        # Infer from runtime_hint
        if runtime_hint in ("npx", "npm"):
            return "npm"
        if runtime_hint in ("uvx", "pip", "pipx"):
            return "pypi"
        if runtime_hint == "docker":
            return "docker"
        if runtime_hint in ("dotnet", "dnx"):
            return "nuget"

        # Infer from package name patterns
        if name.startswith("@") and "/" in name:
            return "npm"  # scoped npm package, e.g. @azure/mcp
        if name.startswith(("ghcr.io/", "mcr.microsoft.com/", "docker.io/")):
            return "docker"
        if name.startswith("https://") and name.endswith(".mcpb"):
            return "mcpb"
        # PascalCase with dots usually means nuget (e.g. Azure.Mcp)
        if "." in name and not name.startswith("http") and name[0].isupper():
            return "nuget"

        return ""
