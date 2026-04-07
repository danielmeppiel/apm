"""Auto-discover and fetch org-level apm-policy.yml files.

Discovery flow:
1. Extract org from git remote (github.com/contoso/my-project -> "contoso")
2. Fetch <org>/.github/apm-policy.yml via GitHub API (Contents API)
3. Cache locally with configurable TTL
4. Parse and return ApmPolicy

Supports:
- GitHub.com and GitHub Enterprise (*.ghe.com)
- Manual override via --policy <path|url>
- Cache with TTL (default 1 hour), --no-cache bypass
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests

from .parser import PolicyValidationError, load_policy
from .schema import ApmPolicy

logger = logging.getLogger(__name__)

# Cache location: apm_modules/.policy-cache/<hash>.yml + <hash>.meta.json
POLICY_CACHE_DIR = ".policy-cache"
DEFAULT_CACHE_TTL = 3600  # 1 hour


@dataclass
class PolicyFetchResult:
    """Result of a policy fetch attempt."""

    policy: Optional[ApmPolicy] = None
    source: str = ""  # "org:contoso/.github", "file:/path", "url:https://..."
    cached: bool = False  # True if served from cache
    error: Optional[str] = None  # Error message if fetch failed

    @property
    def found(self) -> bool:
        return self.policy is not None


def discover_policy(
    project_root: Path,
    *,
    policy_override: Optional[str] = None,
    no_cache: bool = False,
) -> PolicyFetchResult:
    """Discover and load the applicable policy for a project.

    Resolution order:
    1. If policy_override is a local file path -> load from file
    2. If policy_override is a URL -> fetch from URL
    3. If policy_override is "org" -> auto-discover from org
    4. If policy_override is None -> auto-discover from org
    """
    if policy_override:
        path = Path(policy_override)
        if path.exists() and path.is_file():
            return _load_from_file(path)
        if policy_override.startswith("http://"):
            return PolicyFetchResult(
                error="Refusing plaintext http:// policy URL -- use https://",
                source=f"url:{policy_override}",
            )
        if policy_override.startswith("https://"):
            return _fetch_from_url(policy_override, project_root, no_cache=no_cache)
        if policy_override != "org":
            # Try as owner/repo reference
            return _fetch_from_repo(
                policy_override, project_root, no_cache=no_cache
            )

    # Auto-discover from git remote
    return _auto_discover(project_root, no_cache=no_cache)


def _load_from_file(path: Path) -> PolicyFetchResult:
    """Load policy from a local file."""
    try:
        policy, _warnings = load_policy(path)
        return PolicyFetchResult(policy=policy, source=f"file:{path}")
    except PolicyValidationError as e:
        return PolicyFetchResult(error=f"Invalid policy file {path}: {e}")
    except Exception as e:
        return PolicyFetchResult(error=f"Failed to read {path}: {e}")


def _auto_discover(
    project_root: Path, *, no_cache: bool = False
) -> PolicyFetchResult:
    """Auto-discover policy from org's .github repo.

    1. Run git remote get-url origin
    2. Parse org from URL
    3. Fetch <org>/.github/apm-policy.yml
    """
    org_and_host = _extract_org_from_git_remote(project_root)
    if org_and_host is None:
        return PolicyFetchResult(error="Could not determine org from git remote")

    org, host = org_and_host
    repo_ref = f"{org}/.github"
    if host and host != "github.com":
        repo_ref = f"{host}/{repo_ref}"

    return _fetch_from_repo(repo_ref, project_root, no_cache=no_cache)


def _extract_org_from_git_remote(
    project_root: Path,
) -> Optional[Tuple[str, str]]:
    """Extract (org, host) from git remote origin URL.

    Handles:
    - https://github.com/contoso/my-project.git -> ("contoso", "github.com")
    - git@github.com:contoso/my-project.git -> ("contoso", "github.com")
    - https://github.example.com/contoso/my-project.git -> ("contoso", "github.example.com")
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=project_root,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        return _parse_remote_url(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _parse_remote_url(url: str) -> Optional[Tuple[str, str]]:
    """Parse a git remote URL into (org, host).

    Returns None if URL can't be parsed.
    """
    if not url:
        return None

    # SSH: git@github.com:owner/repo.git
    if url.startswith("git@"):
        try:
            host_part, path_part = url.split(":", 1)
            host = host_part.replace("git@", "")
            parts = path_part.rstrip("/").removesuffix(".git").split("/")
            if parts and parts[0]:
                return (parts[0], host)
        except (ValueError, IndexError):
            return None
        return None

    # HTTPS: https://github.com/owner/repo.git
    # ADO:   https://dev.azure.com/org/project/_git/repo
    if "://" in url:
        try:
            parsed = urlparse(url)
            host = parsed.hostname or ""
            path_parts = (
                parsed.path.strip("/").removesuffix(".git").rstrip("/").split("/")
            )
            if host and path_parts and path_parts[0]:
                return (path_parts[0], host)
        except Exception:
            return None

    return None


def _fetch_from_url(
    url: str,
    project_root: Path,
    *,
    no_cache: bool = False,
) -> PolicyFetchResult:
    """Fetch policy YAML from a direct URL."""

    # Use URL as cache key
    if not no_cache:
        cached = _read_cache(url, project_root)
        if cached is not None:
            return cached

    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 404:
            return PolicyFetchResult(source=f"url:{url}", error="404: Policy file not found")
        if resp.status_code != 200:
            return PolicyFetchResult(
                error=f"HTTP {resp.status_code} fetching {url}", source=f"url:{url}"
            )
        content = resp.text
    except requests.exceptions.Timeout:
        return PolicyFetchResult(error=f"Timeout fetching {url}", source=f"url:{url}")
    except requests.exceptions.ConnectionError:
        return PolicyFetchResult(
            error=f"Connection error fetching {url}", source=f"url:{url}"
        )
    except Exception as e:
        return PolicyFetchResult(error=f"Error fetching {url}: {e}", source=f"url:{url}")

    try:
        policy, _warnings = load_policy(content)
        result = PolicyFetchResult(policy=policy, source=f"url:{url}")
        _write_cache(url, content, project_root)
        return result
    except PolicyValidationError as e:
        return PolicyFetchResult(
            error=f"Invalid policy from {url}: {e}", source=f"url:{url}"
        )


def _fetch_from_repo(
    repo_ref: str,
    project_root: Path,
    *,
    no_cache: bool = False,
) -> PolicyFetchResult:
    """Fetch apm-policy.yml from a GitHub repo via Contents API.

    repo_ref format: "owner/.github" or "host/owner/.github"
    """
    if not no_cache:
        cached = _read_cache(repo_ref, project_root)
        if cached is not None:
            return cached

    content, error = _fetch_github_contents(repo_ref, "apm-policy.yml")

    if error:
        # 404 = no policy, not an error
        if "404" in error:
            return PolicyFetchResult(source=f"org:{repo_ref}")
        return PolicyFetchResult(error=error, source=f"org:{repo_ref}")

    if content is None:
        return PolicyFetchResult(source=f"org:{repo_ref}")

    try:
        policy, _warnings = load_policy(content)
        result = PolicyFetchResult(policy=policy, source=f"org:{repo_ref}")
        _write_cache(repo_ref, content, project_root)
        return result
    except PolicyValidationError as e:
        return PolicyFetchResult(
            error=f"Invalid policy in {repo_ref}: {e}", source=f"org:{repo_ref}"
        )


def _fetch_github_contents(
    repo_ref: str,
    file_path: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Fetch file contents from GitHub API.

    Returns (content_string, error_string). One will be None.
    """

    # Parse repo_ref: "owner/repo" or "host/owner/repo"
    parts = repo_ref.split("/")
    if len(parts) == 2:
        host = "github.com"
        owner, repo = parts
    elif len(parts) >= 3:
        host = parts[0]
        owner = parts[1]
        repo = "/".join(parts[2:])
    else:
        return None, f"Invalid repo reference: {repo_ref}"

    # Build API URL
    if host == "github.com":
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
    else:
        api_url = (
            f"https://{host}/api/v3/repos/{owner}/{repo}/contents/{file_path}"
        )

    headers = {"Accept": "application/vnd.github.v3+json"}
    token = _get_token_for_host(host)
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        resp = requests.get(api_url, headers=headers, timeout=10)
        if resp.status_code == 404:
            return None, "404: Policy file not found"
        if resp.status_code == 403:
            return None, f"403: Access denied to {repo_ref}"
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code} fetching policy from {repo_ref}"

        data = resp.json()
        if data.get("encoding") == "base64" and data.get("content"):
            content = base64.b64decode(data["content"]).decode("utf-8")
            return content, None
        elif data.get("content"):
            return data["content"], None
        else:
            return None, f"Unexpected response format from {repo_ref}"
    except requests.exceptions.Timeout:
        return None, f"Timeout fetching policy from {repo_ref}"
    except requests.exceptions.ConnectionError:
        return None, f"Connection error fetching policy from {repo_ref}"
    except Exception as e:
        return None, f"Error fetching policy from {repo_ref}: {e}"


def _is_github_host(host: str) -> bool:
    """Return True if *host* is a known GitHub-family hostname."""
    if host == "github.com":
        return True
    if host.endswith(".ghe.com"):
        return True
    gh_host = os.environ.get("GITHUB_HOST", "")
    if gh_host and host == gh_host:
        return True
    return False


def _get_token_for_host(host: str) -> Optional[str]:
    """Get authentication token for a given host.

    Environment-variable tokens (GITHUB_TOKEN, GITHUB_APM_PAT, GH_TOKEN)
    are only returned when *host* is a recognized GitHub-family hostname.
    For other hosts the token manager + git credential helpers are used.
    """
    try:
        from ..core.token_manager import GitHubTokenManager

        manager = GitHubTokenManager()
        return manager.get_token_with_credential_fallback("modules", host)
    except Exception:
        if _is_github_host(host):
            return (
                os.environ.get("GITHUB_TOKEN")
                or os.environ.get("GITHUB_APM_PAT")
                or os.environ.get("GH_TOKEN")
            )
        return None


# -- Cache ----------------------------------------------------------


def _get_cache_dir(project_root: Path) -> Path:
    """Get the policy cache directory."""
    return project_root / "apm_modules" / POLICY_CACHE_DIR


def _cache_key(repo_ref: str) -> str:
    """Generate a deterministic cache filename from repo ref."""
    return hashlib.sha256(repo_ref.encode()).hexdigest()[:16]


def _read_cache(
    repo_ref: str,
    project_root: Path,
    ttl: int = DEFAULT_CACHE_TTL,
) -> Optional[PolicyFetchResult]:
    """Read policy from cache if still valid.

    Returns None if cache miss or expired.
    """
    cache_dir = _get_cache_dir(project_root)
    key = _cache_key(repo_ref)
    policy_file = cache_dir / f"{key}.yml"
    meta_file = cache_dir / f"{key}.meta.json"

    if not policy_file.exists() or not meta_file.exists():
        return None

    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        cached_at = meta.get("cached_at", 0)
        if time.time() - cached_at > ttl:
            return None  # expired

        policy, _warnings = load_policy(policy_file)
        # Determine source label: use "url:" for HTTP(S) URLs, "org:" otherwise
        if repo_ref.startswith("http://") or repo_ref.startswith("https://"):
            source = f"url:{repo_ref}"
        else:
            source = f"org:{repo_ref}"
        return PolicyFetchResult(
            policy=policy,
            source=source,
            cached=True,
        )
    except Exception:
        return None


def _write_cache(
    repo_ref: str,
    yaml_content: str,
    project_root: Path,
) -> None:
    """Write policy YAML and metadata to cache."""
    cache_dir = _get_cache_dir(project_root)
    cache_dir.mkdir(parents=True, exist_ok=True)

    key = _cache_key(repo_ref)
    policy_file = cache_dir / f"{key}.yml"
    meta_file = cache_dir / f"{key}.meta.json"

    policy_file.write_text(yaml_content, encoding="utf-8")
    meta = {
        "repo_ref": repo_ref,
        "cached_at": time.time(),
    }
    meta_file.write_text(json.dumps(meta), encoding="utf-8")
