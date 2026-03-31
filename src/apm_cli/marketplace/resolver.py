"""Resolve ``NAME@MARKETPLACE`` specifiers to canonical ``owner/repo#ref`` strings.

The ``@`` disambiguation rule:
- If input matches ``^[a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+$`` (no ``/``, no ``:``),
  it is a marketplace ref.
- Everything else goes to the existing ``DependencyReference.parse()`` path.
- These inputs previously raised ``ValueError`` ("Use 'user/repo' format"),
  so this is a backward-compatible grammar extension.
"""

import logging
import re
from typing import Optional, Tuple

from .client import fetch_or_cache
from .errors import MarketplaceFetchError, PluginNotFoundError
from .models import MarketplacePlugin
from .registry import get_marketplace_by_name

logger = logging.getLogger(__name__)

_MARKETPLACE_RE = re.compile(r"^([a-zA-Z0-9._-]+)@([a-zA-Z0-9._-]+)$")


def parse_marketplace_ref(specifier: str) -> Optional[Tuple[str, str]]:
    """Parse a ``NAME@MARKETPLACE`` specifier.

    Returns:
        ``(plugin_name, marketplace_name)`` if the specifier matches,
        or ``None`` if it does not look like a marketplace ref.
    """
    s = specifier.strip()
    # Quick rejection: slashes and colons belong to other formats
    if "/" in s or ":" in s:
        return None
    match = _MARKETPLACE_RE.match(s)
    if match:
        return (match.group(1), match.group(2))
    return None


def _resolve_github_source(source: dict) -> str:
    """Resolve a ``github`` source type to ``owner/repo[#ref]``."""
    repo = source.get("repo", "")
    ref = source.get("ref", "")
    if not repo or "/" not in repo:
        raise ValueError(
            f"Invalid github source: 'repo' field must be 'owner/repo', got '{repo}'"
        )
    if ref:
        return f"{repo}#{ref}"
    return repo


def _resolve_url_source(source: dict) -> str:
    """Resolve a ``url`` source type.

    APM is Git-native -- URL sources that point to GitHub repos are
    resolved to ``owner/repo``. Non-GitHub URLs are rejected.
    """
    url = source.get("url", "")
    # Try to extract owner/repo from common GitHub URL patterns
    for prefix in ("https://github.com/", "http://github.com/"):
        if url.lower().startswith(prefix):
            path = url[len(prefix) :].rstrip("/").split("?")[0]
            # Remove .git suffix
            if path.endswith(".git"):
                path = path[:-4]
            parts = path.split("/")
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}"

    raise ValueError(
        f"Cannot resolve URL source '{url}' to a Git coordinate. "
        f"APM requires Git-based sources (owner/repo format)."
    )


def _resolve_git_subdir_source(source: dict) -> str:
    """Resolve a ``git-subdir`` source type to ``owner/repo[#ref]``."""
    repo = source.get("repo", "")
    ref = source.get("ref", "")
    # subdir = source.get("subdir", "")  # Not used in canonical string
    if not repo or "/" not in repo:
        raise ValueError(
            f"Invalid git-subdir source: 'repo' must be 'owner/repo', got '{repo}'"
        )
    if ref:
        return f"{repo}#{ref}"
    return repo


def _resolve_relative_source(source: str, marketplace_owner: str, marketplace_repo: str) -> str:
    """Resolve a relative path source to ``owner/repo``.

    Relative sources point to subdirectories within the marketplace repo itself.
    """
    return f"{marketplace_owner}/{marketplace_repo}"


def resolve_plugin_source(
    plugin: MarketplacePlugin,
    marketplace_owner: str = "",
    marketplace_repo: str = "",
) -> str:
    """Resolve a plugin's source to a canonical ``owner/repo[#ref]`` string.

    Handles 4 source types: relative, github, url, git-subdir.
    NPM sources are rejected with a clear message.

    Args:
        plugin: The marketplace plugin to resolve.
        marketplace_owner: Owner of the marketplace repo (for relative sources).
        marketplace_repo: Repo name of the marketplace (for relative sources).

    Returns:
        Canonical ``owner/repo[#ref]`` string.

    Raises:
        ValueError: If the source type is unsupported or the source is invalid.
    """
    source = plugin.source
    if source is None:
        raise ValueError(f"Plugin '{plugin.name}' has no source defined")

    # String source = relative path
    if isinstance(source, str):
        return _resolve_relative_source(source, marketplace_owner, marketplace_repo)

    if not isinstance(source, dict):
        raise ValueError(
            f"Plugin '{plugin.name}' has unrecognized source format: {type(source).__name__}"
        )

    source_type = source.get("type", "")

    if source_type == "github":
        return _resolve_github_source(source)
    elif source_type == "url":
        return _resolve_url_source(source)
    elif source_type == "git-subdir":
        return _resolve_git_subdir_source(source)
    elif source_type == "npm":
        raise ValueError(
            f"Plugin '{plugin.name}' uses npm source type which is not supported by APM. "
            f"APM requires Git-based sources. "
            f"Consider asking the marketplace maintainer to add a 'github' source."
        )
    else:
        raise ValueError(
            f"Plugin '{plugin.name}' has unsupported source type: '{source_type}'"
        )


def resolve_marketplace_plugin(
    plugin_name: str,
    marketplace_name: str,
    *,
    auth_resolver: Optional[object] = None,
) -> Tuple[str, MarketplacePlugin]:
    """Resolve a marketplace plugin reference to a canonical string.

    Args:
        plugin_name: Plugin name within the marketplace.
        marketplace_name: Registered marketplace name.
        auth_resolver: Optional ``AuthResolver`` instance.

    Returns:
        Tuple of (canonical ``owner/repo[#ref]`` string, resolved plugin).

    Raises:
        MarketplaceNotFoundError: If the marketplace is not registered.
        PluginNotFoundError: If the plugin is not in the marketplace.
        MarketplaceFetchError: If the marketplace cannot be fetched.
        ValueError: If the plugin source cannot be resolved.
    """
    source = get_marketplace_by_name(marketplace_name)
    manifest = fetch_or_cache(source, auth_resolver=auth_resolver)

    plugin = manifest.find_plugin(plugin_name)
    if plugin is None:
        raise PluginNotFoundError(plugin_name, marketplace_name)

    canonical = resolve_plugin_source(
        plugin,
        marketplace_owner=source.owner,
        marketplace_repo=source.repo,
    )

    logger.debug(
        "Resolved %s@%s -> %s",
        plugin_name,
        marketplace_name,
        canonical,
    )

    return canonical, plugin
