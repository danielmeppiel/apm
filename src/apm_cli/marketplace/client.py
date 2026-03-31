"""Fetch, parse, and cache marketplace.json from GitHub repositories.

Uses ``AuthResolver.try_with_fallback(unauth_first=True)`` for public-first
access with automatic credential fallback for private marketplace repos.
Cache lives at ``~/.apm/cache/marketplace/`` with a 1-hour TTL.
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional

import requests

from .errors import MarketplaceFetchError
from .models import MarketplaceManifest, MarketplacePlugin, MarketplaceSource, parse_marketplace_json
from .registry import get_registered_marketplaces

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 3600  # 1 hour
_CACHE_DIR_NAME = os.path.join("cache", "marketplace")

# Candidate locations for marketplace.json in a repository (priority order)
_MARKETPLACE_PATHS = [
    "marketplace.json",
    ".github/plugin/marketplace.json",
    ".claude-plugin/marketplace.json",
]


def _cache_dir() -> str:
    """Return the cache directory, creating it if needed."""
    from ..config import CONFIG_DIR

    d = os.path.join(CONFIG_DIR, _CACHE_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def _sanitize_cache_name(name: str) -> str:
    """Sanitize marketplace name for safe use in file paths."""
    import re

    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    # Prevent path traversal even after sanitization
    safe = safe.strip(".").strip("_") or "unnamed"
    return safe


def _cache_data_path(name: str) -> str:
    return os.path.join(_cache_dir(), f"{_sanitize_cache_name(name)}.json")


def _cache_meta_path(name: str) -> str:
    return os.path.join(_cache_dir(), f"{_sanitize_cache_name(name)}.meta.json")


def _read_cache(name: str) -> Optional[Dict]:
    """Read cached marketplace data if valid (not expired)."""
    data_path = _cache_data_path(name)
    meta_path = _cache_meta_path(name)
    if not os.path.exists(data_path) or not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path, "r") as f:
            meta = json.load(f)
        fetched_at = meta.get("fetched_at", 0)
        ttl = meta.get("ttl_seconds", _CACHE_TTL_SECONDS)
        if time.time() - fetched_at > ttl:
            return None  # Expired
        with open(data_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, KeyError) as exc:
        logger.debug("Cache read failed for '%s': %s", name, exc)
        return None


def _read_stale_cache(name: str) -> Optional[Dict]:
    """Read cached data even if expired (stale-while-revalidate)."""
    data_path = _cache_data_path(name)
    if not os.path.exists(data_path):
        return None
    try:
        with open(data_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(name: str, data: Dict) -> None:
    """Write marketplace data and metadata to cache."""
    data_path = _cache_data_path(name)
    meta_path = _cache_meta_path(name)
    try:
        with open(data_path, "w") as f:
            json.dump(data, f, indent=2)
        with open(meta_path, "w") as f:
            json.dump(
                {"fetched_at": time.time(), "ttl_seconds": _CACHE_TTL_SECONDS},
                f,
            )
    except OSError as exc:
        logger.debug("Cache write failed for '%s': %s", name, exc)


def _clear_cache(name: str) -> None:
    """Remove cached data for a marketplace."""
    for path in (_cache_data_path(name), _cache_meta_path(name)):
        try:
            os.remove(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Network fetch
# ---------------------------------------------------------------------------


def _github_contents_url(source: MarketplaceSource, file_path: str) -> str:
    """Build the GitHub Contents API URL for a file."""
    from ..core.auth import AuthResolver

    host_info = AuthResolver.classify_host(source.host)
    api_base = host_info.api_base
    return f"{api_base}/repos/{source.owner}/{source.repo}/contents/{file_path}?ref={source.branch}"


def _fetch_file(
    source: MarketplaceSource,
    file_path: str,
    auth_resolver: Optional[object] = None,
) -> Optional[Dict]:
    """Fetch a JSON file from a GitHub repo via the Contents API.

    Returns parsed JSON or ``None`` if the file does not exist (404).
    Raises ``MarketplaceFetchError`` on unexpected failures.
    """
    url = _github_contents_url(source, file_path)

    def _do_fetch(token, _git_env):
        headers = {
            "Accept": "application/vnd.github.v3.raw",
            "User-Agent": "apm-cli",
        }
        if token:
            headers["Authorization"] = f"token {token}"
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    if auth_resolver is None:
        from ..core.auth import AuthResolver

        auth_resolver = AuthResolver()

    try:
        return auth_resolver.try_with_fallback(
            source.host,
            _do_fetch,
            org=source.owner,
            unauth_first=True,
        )
    except Exception as exc:
        raise MarketplaceFetchError(source.name, str(exc)) from exc


def _auto_detect_path(
    source: MarketplaceSource,
    auth_resolver: Optional[object] = None,
) -> Optional[str]:
    """Probe candidate locations and return the first that exists.

    Returns ``None`` if no location contains a marketplace.json.
    Raises ``MarketplaceFetchError`` on non-404 failures (auth errors, etc.).
    """
    for candidate in _MARKETPLACE_PATHS:
        data = _fetch_file(source, candidate, auth_resolver=auth_resolver)
        if data is not None:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_marketplace(
    source: MarketplaceSource,
    *,
    force_refresh: bool = False,
    auth_resolver: Optional[object] = None,
) -> MarketplaceManifest:
    """Fetch and parse a marketplace manifest.

    Uses cache when available (1h TTL). Falls back to stale cache on
    network errors.

    Args:
        source: Marketplace source to fetch.
        force_refresh: Skip cache and re-fetch from network.
        auth_resolver: Optional ``AuthResolver`` instance (created if None).

    Returns:
        MarketplaceManifest: Parsed manifest.

    Raises:
        MarketplaceFetchError: If fetch fails and no cache is available.
    """
    # Try fresh cache first
    if not force_refresh:
        cached = _read_cache(source.name)
        if cached is not None:
            logger.debug("Using cached marketplace data for '%s'", source.name)
            return parse_marketplace_json(cached, source.name)

    # Fetch from network
    try:
        data = _fetch_file(source, source.path, auth_resolver=auth_resolver)
        if data is None:
            raise MarketplaceFetchError(
                source.name,
                f"marketplace.json not found at '{source.path}' "
                f"in {source.owner}/{source.repo}",
            )
        _write_cache(source.name, data)
        return parse_marketplace_json(data, source.name)
    except MarketplaceFetchError:
        # Stale-while-revalidate: serve expired cache on network error
        stale = _read_stale_cache(source.name)
        if stale is not None:
            logger.warning(
                "Network error fetching '%s'; using stale cache", source.name
            )
            return parse_marketplace_json(stale, source.name)
        raise


def fetch_or_cache(
    source: MarketplaceSource,
    *,
    auth_resolver: Optional[object] = None,
) -> MarketplaceManifest:
    """Convenience wrapper -- same as ``fetch_marketplace`` with defaults."""
    return fetch_marketplace(source, auth_resolver=auth_resolver)


def search_all_marketplaces(
    query: str,
    *,
    auth_resolver: Optional[object] = None,
) -> List[MarketplacePlugin]:
    """Search across all registered marketplaces.

    Returns plugins matching the query, annotated with their source marketplace.
    """
    results: List[MarketplacePlugin] = []
    for source in get_registered_marketplaces():
        try:
            manifest = fetch_marketplace(source, auth_resolver=auth_resolver)
            results.extend(manifest.search(query))
        except MarketplaceFetchError as exc:
            logger.warning("Skipping marketplace '%s': %s", source.name, exc)
    return results


def clear_marketplace_cache(name: Optional[str] = None) -> int:
    """Clear cached data for one or all marketplaces.

    Returns the number of caches cleared.
    """
    if name:
        _clear_cache(name)
        return 1
    count = 0
    for source in get_registered_marketplaces():
        _clear_cache(source.name)
        count += 1
    return count
