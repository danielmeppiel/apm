"""Unit tests for AuthResolver, HostInfo, and AuthContext."""

import os
from unittest.mock import patch

import pytest

from apm_cli.core.auth import AuthContext, AuthResolver, HostInfo
from apm_cli.core.token_manager import GitHubTokenManager

# ---------------------------------------------------------------------------
# TestClassifyHost
# ---------------------------------------------------------------------------

class TestClassifyHost:
    def test_github_com(self):
        hi = AuthResolver.classify_host("github.com")
        assert hi.kind == "github"
        assert hi.has_public_repos is True
        assert hi.api_base == "https://api.github.com"

    def test_ghe_cloud(self):
        hi = AuthResolver.classify_host("contoso.ghe.com")
        assert hi.kind == "ghe_cloud"
        assert hi.has_public_repos is False
        assert hi.api_base == "https://contoso.ghe.com/api/v3"

    def test_ado(self):
        hi = AuthResolver.classify_host("dev.azure.com")
        assert hi.kind == "ado"

    def test_visualstudio(self):
        hi = AuthResolver.classify_host("myorg.visualstudio.com")
        assert hi.kind == "ado"

    def test_ghes_via_env(self):
        """GITHUB_HOST set to a custom FQDN → GHES."""
        with patch.dict(os.environ, {"GITHUB_HOST": "github.mycompany.com"}):
            hi = AuthResolver.classify_host("github.mycompany.com")
            assert hi.kind == "ghes"

    def test_generic_fqdn(self):
        hi = AuthResolver.classify_host("gitlab.com")
        assert hi.kind == "generic"

    def test_case_insensitive(self):
        hi = AuthResolver.classify_host("GitHub.COM")
        assert hi.kind == "github"


# ---------------------------------------------------------------------------
# TestDetectTokenType
# ---------------------------------------------------------------------------

class TestDetectTokenType:
    def test_fine_grained(self):
        assert AuthResolver.detect_token_type("github_pat_abc123") == "fine-grained"

    def test_classic(self):
        assert AuthResolver.detect_token_type("ghp_abc123") == "classic"

    def test_oauth_user(self):
        assert AuthResolver.detect_token_type("ghu_abc123") == "oauth"

    def test_oauth_app(self):
        assert AuthResolver.detect_token_type("gho_abc123") == "oauth"

    def test_github_app_install(self):
        assert AuthResolver.detect_token_type("ghs_abc123") == "github-app"

    def test_github_app_refresh(self):
        assert AuthResolver.detect_token_type("ghr_abc123") == "github-app"

    def test_unknown(self):
        assert AuthResolver.detect_token_type("some-random-token") == "unknown"


# ---------------------------------------------------------------------------
# TestResolve
# ---------------------------------------------------------------------------

class TestResolve:
    def test_per_org_env_var(self):
        """GITHUB_APM_PAT_MICROSOFT takes precedence for org 'microsoft'."""
        with patch.dict(os.environ, {
            "GITHUB_APM_PAT_MICROSOFT": "org-specific-token",
            "GITHUB_APM_PAT": "global-token",
        }, clear=False):
            resolver = AuthResolver()
            ctx = resolver.resolve("github.com", org="microsoft")
            assert ctx.token == "org-specific-token"
            assert ctx.source == "GITHUB_APM_PAT_MICROSOFT"

    def test_per_org_with_hyphens(self):
        """Org name with hyphens → underscores in env var."""
        with patch.dict(os.environ, {
            "GITHUB_APM_PAT_CONTOSO_MICROSOFT": "emu-token",
        }, clear=False):
            resolver = AuthResolver()
            ctx = resolver.resolve("github.com", org="contoso-microsoft")
            assert ctx.token == "emu-token"
            assert ctx.source == "GITHUB_APM_PAT_CONTOSO_MICROSOFT"

    def test_falls_back_to_global(self):
        """No per-org var → falls back to GITHUB_APM_PAT."""
        with patch.dict(os.environ, {
            "GITHUB_APM_PAT": "global-token",
        }, clear=True):
            resolver = AuthResolver()
            ctx = resolver.resolve("github.com", org="unknown-org")
            assert ctx.token == "global-token"
            assert ctx.source == "GITHUB_APM_PAT"

    def test_no_token_returns_none(self):
        """No tokens at all → token is None."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value=None
            ):
                resolver = AuthResolver()
                ctx = resolver.resolve("github.com")
                assert ctx.token is None
                assert ctx.source == "none"

    def test_caching(self):
        """Second call returns cached result."""
        with patch.dict(os.environ, {"GITHUB_APM_PAT": "token"}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value=None
            ):
                resolver = AuthResolver()
                ctx1 = resolver.resolve("github.com", org="microsoft")
                ctx2 = resolver.resolve("github.com", org="microsoft")
                assert ctx1 is ctx2

    def test_different_orgs_different_cache(self):
        """Different orgs get different cache entries."""
        with patch.dict(os.environ, {
            "GITHUB_APM_PAT_ORG_A": "token-a",
            "GITHUB_APM_PAT_ORG_B": "token-b",
        }, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value=None
            ):
                resolver = AuthResolver()
                ctx_a = resolver.resolve("github.com", org="org-a")
                ctx_b = resolver.resolve("github.com", org="org-b")
                assert ctx_a.token == "token-a"
                assert ctx_b.token == "token-b"

    def test_ado_token(self):
        """ADO host resolves ADO_APM_PAT."""
        with patch.dict(os.environ, {"ADO_APM_PAT": "ado-token"}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value=None
            ):
                resolver = AuthResolver()
                ctx = resolver.resolve("dev.azure.com")
                assert ctx.token == "ado-token"

    def test_credential_fallback(self):
        """Falls back to git credential helper when no env vars."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value="cred-token"
            ):
                resolver = AuthResolver()
                ctx = resolver.resolve("github.com")
                assert ctx.token == "cred-token"
                assert ctx.source == "git-credential-fill"

    def test_global_var_resolves_for_non_default_host(self):
        """GITHUB_APM_PAT resolves for *.ghe.com (any host, not just default)."""
        with patch.dict(os.environ, {"GITHUB_APM_PAT": "global-token"}, clear=True):
            resolver = AuthResolver()
            ctx = resolver.resolve("contoso.ghe.com")
            assert ctx.token == "global-token"
            assert ctx.source == "GITHUB_APM_PAT"

    def test_global_var_resolves_for_ghes_host(self):
        """GITHUB_APM_PAT resolves for a GHES host set via GITHUB_HOST."""
        with patch.dict(os.environ, {
            "GITHUB_HOST": "github.mycompany.com",
            "GITHUB_APM_PAT": "global-token",
        }, clear=True):
            resolver = AuthResolver()
            ctx = resolver.resolve("github.mycompany.com")
            assert ctx.token == "global-token"
            assert ctx.source == "GITHUB_APM_PAT"
            assert ctx.host_info.kind == "ghes"

    def test_git_env_has_lockdown(self):
        """Resolved context has git security env vars."""
        with patch.dict(os.environ, {"GITHUB_APM_PAT": "token"}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value=None
            ):
                resolver = AuthResolver()
                ctx = resolver.resolve("github.com")
                assert ctx.git_env.get("GIT_TERMINAL_PROMPT") == "0"


# ---------------------------------------------------------------------------
# TestTryWithFallback
# ---------------------------------------------------------------------------

class TestTryWithFallback:
    def test_unauth_first_succeeds(self):
        """Unauth-first: if unauth works, auth is never tried."""
        with patch.dict(os.environ, {"GITHUB_APM_PAT": "token"}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value=None
            ):
                resolver = AuthResolver()
                calls = []

                def op(token, env):
                    calls.append(token)
                    return "success"

                result = resolver.try_with_fallback("github.com", op, unauth_first=True)
                assert result == "success"
                assert calls == [None]

    def test_unauth_first_falls_back_to_auth(self):
        """Unauth-first: if unauth fails, retries with token."""
        with patch.dict(os.environ, {"GITHUB_APM_PAT": "token"}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value=None
            ):
                resolver = AuthResolver()
                calls = []

                def op(token, env):
                    calls.append(token)
                    if token is None:
                        raise RuntimeError("Unauthorized")
                    return "success"

                result = resolver.try_with_fallback("github.com", op, unauth_first=True)
                assert result == "success"
                assert calls == [None, "token"]

    def test_ghe_cloud_auth_only(self):
        """*.ghe.com: auth-only, no unauth fallback.  Uses global env var."""
        with patch.dict(os.environ, {"GITHUB_APM_PAT": "global-token"}, clear=True):
            resolver = AuthResolver()
            calls = []

            def op(token, env):
                calls.append(token)
                return "success"

            result = resolver.try_with_fallback(
                "contoso.ghe.com", op, unauth_first=True
            )
            assert result == "success"
            # GHE Cloud has no public repos → unauth skipped, auth called once
            assert calls == ["global-token"]

    def test_auth_first_succeeds(self):
        """Auth-first (default): auth works, unauth not tried."""
        with patch.dict(os.environ, {"GITHUB_APM_PAT": "token"}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value=None
            ):
                resolver = AuthResolver()
                calls = []

                def op(token, env):
                    calls.append(token)
                    return "success"

                result = resolver.try_with_fallback("github.com", op)
                assert result == "success"
                assert calls == ["token"]

    def test_auth_first_falls_back_to_unauth(self):
        """Auth-first: if auth fails on public host, retries unauthenticated."""
        with patch.dict(os.environ, {"GITHUB_APM_PAT": "token"}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value=None
            ):
                resolver = AuthResolver()
                calls = []

                def op(token, env):
                    calls.append(token)
                    if token is not None:
                        raise RuntimeError("Token expired")
                    return "success"

                result = resolver.try_with_fallback("github.com", op)
                assert result == "success"
                assert calls == ["token", None]

    def test_no_token_tries_unauth(self):
        """No token available: tries unauthenticated directly."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value=None
            ):
                resolver = AuthResolver()
                calls = []

                def op(token, env):
                    calls.append(token)
                    return "success"

                result = resolver.try_with_fallback("github.com", op)
                assert result == "success"
                assert calls == [None]

    def test_credential_fallback_when_env_token_fails(self):
        """Env token fails on auth-only host → retries with git credential fill."""
        with patch.dict(os.environ, {"GITHUB_APM_PAT": "wrong-token"}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value="correct-cred"
            ):
                resolver = AuthResolver()
                calls = []

                def op(token, env):
                    calls.append(token)
                    if token == "wrong-token":
                        raise RuntimeError("Bad credentials")
                    return "success"

                result = resolver.try_with_fallback("contoso.ghe.com", op)
                assert result == "success"
                assert calls == ["wrong-token", "correct-cred"]

    def test_no_credential_fallback_when_source_is_credential(self):
        """When token already came from git-credential-fill, no retry on failure."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value="cred-token"
            ):
                resolver = AuthResolver()

                def op(token, env):
                    raise RuntimeError("Bad credentials")

                with pytest.raises(RuntimeError, match="Bad credentials"):
                    resolver.try_with_fallback("contoso.ghe.com", op)

    def test_credential_fallback_on_auth_first_path(self):
        """Auth-first on public host: auth fails, unauth fails → credential fill kicks in."""
        with patch.dict(os.environ, {"GITHUB_APM_PAT": "wrong-token"}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value="correct-cred"
            ):
                resolver = AuthResolver()
                calls = []

                def op(token, env):
                    calls.append(token)
                    if token in ("wrong-token", None):
                        raise RuntimeError("Failed")
                    return "success"

                result = resolver.try_with_fallback("github.com", op)
                assert result == "success"
                # auth-first → unauth fallback → credential fill
                assert calls == ["wrong-token", None, "correct-cred"]

    def test_verbose_callback(self):
        """verbose_callback is called at each step."""
        with patch.dict(os.environ, {"GITHUB_APM_PAT": "token"}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value=None
            ):
                resolver = AuthResolver()
                messages = []

                def op(token, env):
                    return "ok"

                resolver.try_with_fallback(
                    "github.com", op, verbose_callback=messages.append
                )
                assert len(messages) > 0


# ---------------------------------------------------------------------------
# TestBuildErrorContext
# ---------------------------------------------------------------------------

class TestBuildErrorContext:
    def test_no_token_message(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value=None
            ):
                resolver = AuthResolver()
                msg = resolver.build_error_context("github.com", "clone")
                assert "GITHUB_APM_PAT" in msg
                assert "--verbose" in msg

    def test_ghe_cloud_error_context(self):
        """*.ghe.com errors mention enterprise-scoped tokens."""
        with patch.dict(os.environ, {"GITHUB_APM_PAT_CONTOSO": "token"}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value=None
            ):
                resolver = AuthResolver()
                msg = resolver.build_error_context(
                    "contoso.ghe.com", "clone", org="contoso"
                )
                assert "enterprise" in msg.lower()

    def test_github_com_error_mentions_emu(self):
        """github.com errors mention EMU/SSO possibility."""
        with patch.dict(os.environ, {"GITHUB_APM_PAT": "ghp_token"}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value=None
            ):
                resolver = AuthResolver()
                msg = resolver.build_error_context("github.com", "clone")
                assert "EMU" in msg or "SAML" in msg

    def test_multi_org_hint(self):
        with patch.dict(os.environ, {"GITHUB_APM_PAT": "token"}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value=None
            ):
                resolver = AuthResolver()
                msg = resolver.build_error_context(
                    "github.com", "clone", org="microsoft"
                )
                assert "GITHUB_APM_PAT_MICROSOFT" in msg

    def test_token_present_shows_source(self):
        with patch.dict(os.environ, {"GITHUB_APM_PAT": "ghp_tok"}, clear=True):
            with patch.object(
                GitHubTokenManager, "resolve_credential_from_git", return_value=None
            ):
                resolver = AuthResolver()
                msg = resolver.build_error_context("github.com", "clone")
                assert "GITHUB_APM_PAT" in msg
                assert "SAML SSO" in msg
