"""Utilities for handling GitHub, GitHub Enterprise, and Azure DevOps hostnames and URLs."""

import os
import re
import urllib.parse
from typing import Optional


def default_host() -> str:
    """Return the default Git host (can be overridden via GITHUB_HOST env var)."""
    return os.environ.get("GITHUB_HOST", "github.com")


def is_azure_devops_hostname(hostname: Optional[str]) -> bool:
    """Return True if hostname is Azure DevOps (cloud or server).
    
    Accepts:
    - dev.azure.com (Azure DevOps Services)
    - *.visualstudio.com (legacy Azure DevOps URLs)
    - Custom Azure DevOps Server hostnames are supported via GITHUB_HOST env var
    """
    if not hostname:
        return False
    h = hostname.lower()
    if h == "dev.azure.com":
        return True
    if h.endswith(".visualstudio.com"):
        return True
    return False


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


def is_supported_git_host(hostname: Optional[str]) -> bool:
    """Return True if hostname is a supported Git hosting platform.
    
    Supports:
    - GitHub.com
    - GitHub Enterprise (*.ghe.com)
    - Azure DevOps Services (dev.azure.com)
    - Azure DevOps legacy (*.visualstudio.com)
    - Any FQDN set via GITHUB_HOST environment variable
    """
    if not hostname:
        return False
    
    # Check GitHub hosts
    if is_github_hostname(hostname):
        return True
    
    # Check Azure DevOps hosts
    if is_azure_devops_hostname(hostname):
        return True
    
    # Accept the configured default host (supports custom Azure DevOps Server, etc.)
    configured_host = os.environ.get("GITHUB_HOST", "").lower()
    if configured_host and hostname.lower() == configured_host:
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


# Azure DevOps URL builders

def build_ado_https_clone_url(org: str, project: str, repo: str, token: Optional[str] = None, host: str = "dev.azure.com") -> str:
    """Build Azure DevOps HTTPS clone URL.
    
    Azure DevOps accepts PAT as password with any username, or as bearer token.
    The standard format is: https://dev.azure.com/{org}/{project}/_git/{repo}
    
    Args:
        org: Azure DevOps organization name
        project: Azure DevOps project name
        repo: Repository name
        token: Optional Personal Access Token for authentication
        host: Azure DevOps host (default: dev.azure.com)
    
    Returns:
        str: HTTPS clone URL for Azure DevOps
    """
    if token:
        # ADO uses PAT as password with empty username
        return f"https://{token}@{host}/{org}/{project}/_git/{repo}"
    return f"https://{host}/{org}/{project}/_git/{repo}"


def build_ado_ssh_url(org: str, project: str, repo: str, host: str = "ssh.dev.azure.com") -> str:
    """Build Azure DevOps SSH clone URL for cloud or server.
    
    For Azure DevOps Services (cloud):
        git@ssh.dev.azure.com:v3/{org}/{project}/{repo}
    
    For Azure DevOps Server (on-premises):
        ssh://git@{host}/{org}/{project}/_git/{repo}
    
    Args:
        org: Azure DevOps organization name
        project: Azure DevOps project name  
        repo: Repository name
        host: SSH host (default: ssh.dev.azure.com for cloud; set to your server for on-prem)
    
    Returns:
        str: SSH clone URL for Azure DevOps
    """
    if host == "ssh.dev.azure.com":
        # Cloud format
        return f"git@ssh.dev.azure.com:v3/{org}/{project}/{repo}"
    else:
        # Server format (user@host is optional, but commonly 'git@host')
        return f"ssh://git@{host}/{org}/{project}/_git/{repo}"


def build_ado_api_url(org: str, project: str, repo: str, path: str, ref: str = "main", host: str = "dev.azure.com") -> str:
    """Build Azure DevOps REST API URL for file contents.
    
    API format: https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/items
    
    Args:
        org: Azure DevOps organization name
        project: Azure DevOps project name
        repo: Repository name
        path: Path to file within the repository
        ref: Git reference (branch, tag, or commit). Defaults to "main"
        host: Azure DevOps host (default: dev.azure.com)
    
    Returns:
        str: API URL for retrieving file contents
    """
    encoded_path = urllib.parse.quote(path, safe='')
    return (
        f"https://{host}/{org}/{project}/_apis/git/repositories/{repo}/items"
        f"?path={encoded_path}&versionDescriptor.version={ref}&api-version=7.0"
    )


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
