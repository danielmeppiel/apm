"""Centralized authentication resolution for APM CLI.

Every APM operation that touches a remote host MUST use AuthResolver.
Resolution is per-(host, org) pair, thread-safe, and cached per-process.

Usage::

    resolver = AuthResolver()
    ctx = resolver.resolve("github.com", org="microsoft")
    # ctx.token, ctx.source, ctx.token_type, ctx.host_info, ctx.git_env

For dependencies::

    ctx = resolver.resolve_for_dep(dep_ref)

For operations with automatic auth/unauth fallback::

    result = resolver.try_with_fallback(
        "github.com", lambda token, env: download(token, env),
        org="microsoft",
    )
"""

from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional, TypeVar

from apm_cli.core.token_manager import GitHubTokenManager
from apm_cli.utils.github_host import (
    default_host,
    is_azure_devops_hostname,
    is_github_hostname,
    is_valid_fqdn,
)

if TYPE_CHECKING:
    from apm_cli.models.dependency.reference import DependencyReference

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HostInfo:
    """Immutable description of a remote Git host."""

    host: str
    kind: str  # "github" | "ghe_cloud" | "ghes" | "ado" | "generic"
    has_public_repos: bool
    api_base: str


@dataclass
class AuthContext:
    """Resolved authentication for a single (host, org) pair.

    Treat as immutable after construction — fields are never mutated.
    Not frozen because ``git_env`` is a dict (unhashable).
    """

    token: Optional[str]
    source: str  # e.g. "GITHUB_APM_PAT_ORGNAME", "GITHUB_TOKEN", "none"
    token_type: str  # "fine-grained", "classic", "emu", "ado", "artifactory", "unknown"
    host_info: HostInfo
    git_env: dict = field(compare=False, repr=False)


# ---------------------------------------------------------------------------
# AuthResolver
# ---------------------------------------------------------------------------

class AuthResolver:
    """Single source of truth for auth resolution.

    Every APM operation that touches a remote host MUST use this class.
    Resolution is per-(host, org) pair, thread-safe, cached per-process.
    """

    def __init__(self, token_manager: Optional[GitHubTokenManager] = None):
        self._token_manager = token_manager or GitHubTokenManager()
        self._cache: dict[tuple, AuthContext] = {}
        self._lock = threading.Lock()

    # -- host classification ------------------------------------------------

    @staticmethod
    def classify_host(host: str) -> HostInfo:
        """Return a ``HostInfo`` describing *host*."""
        h = host.lower()

        if h == "github.com":
            return HostInfo(
                host=host,
                kind="github",
                has_public_repos=True,
                api_base="https://api.github.com",
            )

        if h.endswith(".ghe.com"):
            return HostInfo(
                host=host,
                kind="ghe_cloud",
                has_public_repos=False,
                api_base=f"https://{host}/api/v3",
            )

        if is_azure_devops_hostname(host):
            return HostInfo(
                host=host,
                kind="ado",
                has_public_repos=True,
                api_base="https://dev.azure.com",
            )

        # GHES: GITHUB_HOST is set to a non-github.com, non-ghe.com FQDN
        ghes_host = os.environ.get("GITHUB_HOST", "").lower()
        if ghes_host and ghes_host == h and ghes_host != "github.com" and not ghes_host.endswith(".ghe.com"):
            if is_valid_fqdn(ghes_host):
                return HostInfo(
                    host=host,
                    kind="ghes",
                    has_public_repos=True,
                    api_base=f"https://{host}/api/v3",
                )

        # Generic FQDN (GitLab, Bitbucket, self-hosted, etc.)
        return HostInfo(
            host=host,
            kind="generic",
            has_public_repos=True,
            api_base=f"https://{host}/api/v3",
        )

    # -- token type detection -----------------------------------------------

    @staticmethod
    def detect_token_type(token: str) -> str:
        """Classify a token string by its prefix."""
        if token.startswith("github_pat_"):
            return "fine-grained"
        if token.startswith("ghp_"):
            return "classic"
        if token.startswith("ghu_"):
            return "emu"
        if token.startswith(("gho_", "ghs_", "ghr_")):
            return "classic"
        return "unknown"

    # -- core resolution ----------------------------------------------------

    def resolve(self, host: str, org: Optional[str] = None) -> AuthContext:
        """Resolve auth for *(host, org)*.  Cached & thread-safe."""
        key = (host, org)
        with self._lock:
            if key in self._cache:
                return self._cache[key]

        host_info = self.classify_host(host)
        token, source = self._resolve_token(host_info, org)
        token_type = self.detect_token_type(token) if token else "unknown"
        git_env = self._build_git_env(token)

        ctx = AuthContext(
            token=token,
            source=source,
            token_type=token_type,
            host_info=host_info,
            git_env=git_env,
        )

        with self._lock:
            self._cache[key] = ctx
        return ctx

    def resolve_for_dep(self, dep_ref: "DependencyReference") -> AuthContext:
        """Resolve auth from a ``DependencyReference``."""
        host = dep_ref.host or default_host()
        org: Optional[str] = None
        if dep_ref.repo_url:
            parts = dep_ref.repo_url.split("/")
            if parts:
                org = parts[0]
        return self.resolve(host, org)

    # -- fallback strategy --------------------------------------------------

    def try_with_fallback(
        self,
        host: str,
        operation: Callable[..., T],
        *,
        org: Optional[str] = None,
        unauth_first: bool = False,
        verbose_callback: Optional[Callable[[str], None]] = None,
    ) -> T:
        """Execute *operation* with automatic auth/unauth fallback.

        Parameters
        ----------
        host:
            Target git host.
        operation:
            ``operation(token, git_env) -> T`` — the work to do.
        org:
            Optional organisation for per-org token lookup.
        unauth_first:
            If *True*, try unauthenticated first (saves rate limits, EMU-safe).
        verbose_callback:
            Called with a human-readable step description at each attempt.
        """
        auth_ctx = self.resolve(host, org)
        host_info = auth_ctx.host_info
        git_env = auth_ctx.git_env

        def _log(msg: str) -> None:
            if verbose_callback:
                verbose_callback(msg)

        # Hosts that never have public repos → auth-only, no fallback
        if host_info.kind in ("ghe_cloud", "ado"):
            _log(f"Auth-only attempt for {host_info.kind} host {host}")
            return operation(auth_ctx.token, git_env)

        if unauth_first:
            # Validation path: save rate limits, EMU-safe
            try:
                _log(f"Trying unauthenticated access to {host}")
                return operation(None, git_env)
            except Exception:
                if auth_ctx.token:
                    _log(f"Unauthenticated failed, retrying with token (source: {auth_ctx.source})")
                    return operation(auth_ctx.token, git_env)
                raise
        else:
            # Download path: auth-first for higher rate limits
            if auth_ctx.token:
                try:
                    _log(f"Trying authenticated access to {host} (source: {auth_ctx.source})")
                    return operation(auth_ctx.token, git_env)
                except Exception:
                    if host_info.has_public_repos:
                        _log("Authenticated failed, retrying without token")
                        return operation(None, git_env)
                    raise
            else:
                _log(f"No token available, trying unauthenticated access to {host}")
                return operation(None, git_env)

    # -- error context ------------------------------------------------------

    def build_error_context(
        self, host: str, operation: str, org: Optional[str] = None
    ) -> str:
        """Build an actionable error message for auth failures."""
        auth_ctx = self.resolve(host, org)
        lines: list[str] = [f"Authentication failed for {operation} on {host}."]

        if auth_ctx.token:
            lines.append(f"Token was provided (source: {auth_ctx.source}, type: {auth_ctx.token_type}).")
            if auth_ctx.token_type == "emu":
                lines.append(
                    "EMU tokens are scoped to your enterprise and cannot "
                    "access public github.com repos."
                )
            lines.append(
                "If your organization uses SAML SSO, you may need to "
                "authorize your token at https://github.com/settings/tokens"
            )
        else:
            lines.append("No token available.")
            lines.append(
                "Set GITHUB_APM_PAT or GITHUB_TOKEN, or run 'gh auth login'."
            )

        if org:
            lines.append(
                f"If packages span multiple organizations, set per-org tokens: "
                f"GITHUB_APM_PAT_{_org_to_env_suffix(org)}"
            )

        lines.append("Run with --verbose for detailed auth diagnostics.")
        return "\n".join(lines)

    # -- internals ----------------------------------------------------------

    def _resolve_token(
        self, host_info: HostInfo, org: Optional[str]
    ) -> tuple[Optional[str], str]:
        """Walk the token resolution chain.  Returns (token, source).

        Global env vars (``GITHUB_APM_PAT``, ``GITHUB_TOKEN``, ``GH_TOKEN``)
        are only checked for the default host and ADO.  Non-default hosts
        (GHES, GHE Cloud, generic) resolve via per-org env vars or git
        credential helpers — leaking a github.com PAT to an enterprise
        server would be a security risk and would fail auth anyway.
        """
        # 1. Per-org env var (any host)
        if org:
            env_name = f"GITHUB_APM_PAT_{_org_to_env_suffix(org)}"
            token = os.environ.get(env_name)
            if token:
                return token, env_name

        # 2. Global env var chain — only for default host or ADO
        _is_default = host_info.host.lower() == default_host().lower()
        purpose = self._purpose_for_host(host_info)
        if _is_default or host_info.kind == "ado":
            token = self._token_manager.get_token_for_purpose(purpose)
            if token:
                source = self._identify_env_source(purpose)
                return token, source

        # 3. Git credential helper (not for ADO — uses its own PAT)
        if host_info.kind not in ("ado",):
            credential = self._token_manager.resolve_credential_from_git(host_info.host)
            if credential:
                return credential, "git-credential-fill"

        return None, "none"

    @staticmethod
    def _purpose_for_host(host_info: HostInfo) -> str:
        if host_info.kind == "ado":
            return "ado_modules"
        return "modules"

    def _identify_env_source(self, purpose: str) -> str:
        """Return the name of the first env var that matched for *purpose*."""
        for var in self._token_manager.TOKEN_PRECEDENCE.get(purpose, []):
            if os.environ.get(var):
                return var
        return "env"

    @staticmethod
    def _build_git_env(token: Optional[str] = None) -> dict:
        """Pre-built env dict for subprocess git calls."""
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        # On Windows, GIT_ASKPASS='' can cause issues; use 'echo' instead
        env["GIT_ASKPASS"] = "" if sys.platform != "win32" else "echo"
        if token:
            env["GIT_TOKEN"] = token
        return env


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _org_to_env_suffix(org: str) -> str:
    """Convert an org name to an env-var suffix (upper-case, hyphens → underscores)."""
    return org.upper().replace("-", "_")
