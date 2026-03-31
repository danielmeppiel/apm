"""Configuration management for APM."""

import json
import os
from typing import Optional

from apm_cli.apmrc import (
    DEFAULT_REGISTRY,
    MergedApmrcConfig,
    get_registry_for_scope,
    load_merged_config,
)

CONFIG_DIR = os.path.expanduser("~/.apm")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

_config_cache: Optional[dict] = None


def ensure_config_exists():
    """Ensure the configuration directory and file exist."""
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)

    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({"default_client": "vscode"}, f)


def get_config():
    """Get the current configuration.

    Results are cached for the lifetime of the process.

    Returns:
        dict: Current configuration.
    """
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    ensure_config_exists()
    with open(CONFIG_FILE, "r") as f:
        _config_cache = json.load(f)
    return _config_cache


def _invalidate_config_cache():
    """Invalidate both config caches (called after writes)."""
    global _config_cache, _apmrc_cache
    _config_cache = None
    _apmrc_cache = None


def update_config(updates):
    """Update the configuration with new values.

    Args:
        updates (dict): Dictionary of configuration values to update.
    """
    _invalidate_config_cache()
    config = get_config()
    config.update(updates)

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    _invalidate_config_cache()


def get_default_client():
    """Get the default MCP client.

    Returns:
        str: Default MCP client type.
    """
    return get_config().get("default_client", "vscode")


def set_default_client(client_type):
    """Set the default MCP client.

    Args:
        client_type (str): Type of client to set as default.
    """
    update_config({"default_client": client_type})


def get_auto_integrate() -> bool:
    """Get the auto-integrate setting.

    Returns:
        bool: Whether auto-integration is enabled (default: True).
    """
    return get_config().get("auto_integrate", True)


def set_auto_integrate(enabled: bool) -> None:
    """Set the auto-integrate setting.

    Args:
        enabled: Whether to enable auto-integration.
    """
    update_config({"auto_integrate": enabled})


# ---------------------------------------------------------------------------
# .apmrc integration
# ---------------------------------------------------------------------------

_apmrc_cache: Optional[MergedApmrcConfig] = None


def get_apmrc_config(refresh: bool = False) -> MergedApmrcConfig:
    """Return the merged .apmrc config (cached after first call).

    Args:
        refresh: If True, reload from disk and discard the cached value.

    Returns:
        MergedApmrcConfig with all layers merged.
    """
    global _apmrc_cache
    if _apmrc_cache is None or refresh:
        _apmrc_cache = load_merged_config()
    return _apmrc_cache


def get_effective_registry(scope: Optional[str] = None) -> str:
    """Return the registry URL respecting the full config hierarchy.

    Priority (highest first):
      1. ``MCP_REGISTRY_URL`` environment variable
      2. Scoped registry from .apmrc (when *scope* is given)
      3. Default registry from .apmrc
      4. Built-in default

    Args:
        scope: Optional scope string, e.g. ``'@myorg'``.

    Returns:
        Registry URL string.
    """
    env_url = os.environ.get("MCP_REGISTRY_URL")
    if env_url:
        return env_url
    rc = get_apmrc_config()
    if scope:
        return get_registry_for_scope(scope, rc)
    return rc.registry or DEFAULT_REGISTRY


def get_effective_token() -> Optional[str]:
    """Return the best available GitHub auth token.

    Priority (highest first):
      1. ``GITHUB_APM_PAT`` environment variable
      2. ``GITHUB_TOKEN`` environment variable
      3. ``GH_TOKEN`` environment variable
      4. ``github-token`` from .apmrc

    Returns:
        Token string, or None if no token is configured.
    """
    for env_key in ("GITHUB_APM_PAT", "GITHUB_TOKEN", "GH_TOKEN"):
        val = os.environ.get(env_key)
        if val:
            return val
    return get_apmrc_config().github_token
