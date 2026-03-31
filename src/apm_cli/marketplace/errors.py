"""Marketplace-specific error hierarchy."""


class MarketplaceError(Exception):
    """Base class for marketplace errors."""

    pass


class MarketplaceNotFoundError(MarketplaceError):
    """Raised when a registered marketplace cannot be found."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(
            f"Marketplace '{name}' is not registered. "
            f"Run 'apm marketplace add OWNER/REPO' to register it, "
            f"or 'apm marketplace list' to see registered marketplaces."
        )


class PluginNotFoundError(MarketplaceError):
    """Raised when a plugin is not found in a marketplace."""

    def __init__(self, plugin_name: str, marketplace_name: str):
        self.plugin_name = plugin_name
        self.marketplace_name = marketplace_name
        super().__init__(
            f"Plugin '{plugin_name}' not found in marketplace '{marketplace_name}'. "
            f"Run 'apm marketplace browse {marketplace_name}' to see available plugins."
        )


class MarketplaceFetchError(MarketplaceError):
    """Raised when fetching marketplace data fails."""

    def __init__(self, name: str, reason: str = ""):
        self.name = name
        self.reason = reason
        detail = f": {reason}" if reason else ""
        super().__init__(
            f"Failed to fetch marketplace '{name}'{detail}. "
            f"Run 'apm marketplace update {name}' to retry."
        )
