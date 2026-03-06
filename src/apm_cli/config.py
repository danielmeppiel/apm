"""Configuration management for APM."""

import os
import json
from typing import Optional


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
    """Invalidate the config cache (called after writes)."""
    global _config_cache
    _config_cache = None


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
