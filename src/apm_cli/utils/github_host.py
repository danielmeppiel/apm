"""Utilities for handling GitHub and GitHub Enterprise hostnames and URLs."""

import os
import re
import urllib.parse
from typing import Optional


def default_host() -> str:
    """Return the default GitHub host (can be overridden via GITHUB_HOST env var)."""
    return os.environ.get("GITHUB_HOST", "github.com")


def is_github_hostname(hostname: Optional[str]) -> bool:
    """Return True if hostname should be treated as GitHub (cloud or enterprise).

    Accepts 'github.com' and hosts that end with '.ghe.com'.
    
    Note: This is primarily for internal hostname classification.
    APM accepts any Git host via FQDN syntax without validation.
    """
    if not hostname:
        return False
    h = hostname.lower()
    if h == "github.com":
        return True
    if h.endswith(".ghe.com"):
        return True
    return False


def build_ssh_url(host: str, repo_ref: str) -> str:
    """Build an SSH clone URL for the given host and repo_ref (owner/repo)."""
    return f"git@{host}:{repo_ref}.git"


def build_https_clone_url(host: str, repo_ref: str, token: Optional[str] = None) -> str:
    """Build an HTTPS clone URL. If token provided, use x-access-token format (no escaping done).

    Note: callers must avoid logging raw token-bearing URLs.
    """
    if token:
        # Use x-access-token format which is compatible with GitHub Enterprise and GH Actions
        return f"https://x-access-token:{token}@{host}/{repo_ref}.git"
    return f"https://{host}/{repo_ref}"


def is_valid_fqdn(hostname: str) -> bool:
    """Validate if a string is a valid Fully Qualified Domain Name (FQDN).

    Args:
        hostname: The hostname string to validate

    Returns:
        bool: True if the hostname is a valid FQDN, False otherwise

    Valid FQDN must:
    - Contain labels separated by dots
    - Labels must contain only alphanumeric chars and hyphens
    - Labels must not start or end with hyphens
    - Have at least one dot
    """
    if not hostname:
        return False
    
    hostname = hostname.split('/')[0]  # Remove any path components
    
    # Single regex to validate all FQDN rules:
    # - Starts with alphanumeric
    # - Labels only contain alphanumeric and hyphens
    # - Labels don't start/end with hyphens
    # - At least two labels (one dot)
    pattern = r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)+$"
    return bool(re.match(pattern, hostname))


def sanitize_token_url_in_message(message: str, host: Optional[str] = None) -> str:
    """Sanitize occurrences of token-bearing https URLs for the given host in message.

    If host is None, default_host() is used. Replaces https://<anything>@host with https://***@host
    """
    if not host:
        host = default_host()

    # Escape host for regex
    host_re = re.escape(host)
    pattern = rf"https://[^@\s]+@{host_re}"
    return re.sub(pattern, f"https://***@{host}", message)
