"""Tests for marketplace-based version display in ``apm view NAME@MARKETPLACE versions``.

Covers the ``_display_marketplace_versions()`` path added to
``src/apm_cli/commands/view.py``.  All marketplace interactions are
mocked -- no network calls.
"""

import contextlib
import sys
import types
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from apm_cli.cli import cli
from apm_cli.marketplace.errors import (
    MarketplaceFetchError,
    MarketplaceNotFoundError,
    PluginNotFoundError,
)
from apm_cli.marketplace.models import (
    MarketplaceManifest,
    MarketplacePlugin,
    MarketplaceSource,
    VersionEntry,
)


# ------------------------------------------------------------------
# Rich-fallback helper (same approach as test_view_command.py)
# ------------------------------------------------------------------


def _force_rich_fallback():
    """Context-manager that forces the text-only code path."""

    @contextlib.contextmanager
    def _ctx():
        keys = [
            "rich",
            "rich.console",
            "rich.table",
            "rich.tree",
            "rich.panel",
            "rich.text",
        ]
        originals = {k: sys.modules.get(k) for k in keys}

        for k in keys:
            stub = types.ModuleType(k)
            stub.__path__ = []

            def _raise(name, _k=k):
                raise ImportError(f"rich not available in test: {_k}")

            stub.__getattr__ = _raise
            sys.modules[k] = stub

        try:
            yield
        finally:
            for k, v in originals.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v

    return _ctx()


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

_DUMMY_SOURCE = MarketplaceSource(
    name="acme-tools",
    owner="acme",
    repo="marketplace",
)


def _make_manifest(plugins):
    """Helper to build a MarketplaceManifest with the given plugins list."""
    return MarketplaceManifest(
        name="acme-tools",
        plugins=tuple(plugins),
    )


def _make_plugin(name, versions=(), **kwargs):
    """Helper to build a MarketplacePlugin with version entries."""
    version_entries = tuple(
        VersionEntry(version=v, ref=r) for v, r in versions
    )
    return MarketplacePlugin(
        name=name,
        source={"type": "github", "repo": "acme/plugin"},
        versions=version_entries,
        **kwargs,
    )


# Common patches for marketplace path -- target the source modules since
# _display_marketplace_versions() uses local imports.
_PATCH_GET_MARKETPLACE = "apm_cli.marketplace.registry.get_marketplace_by_name"
_PATCH_FETCH_OR_CACHE = "apm_cli.marketplace.client.fetch_or_cache"


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestMarketplaceVersionDisplay:
    """Tests for marketplace-based version display via CLI."""

    def setup_method(self):
        self.runner = CliRunner()

    # -- Happy path: plugin with versions ---------------------------------

    def test_marketplace_versions_rich_table(self):
        """``apm view plugin@marketplace versions`` renders a version table."""
        plugin = _make_plugin(
            "my-plugin",
            versions=[
                ("1.0.0", "abc1234"),
                ("2.0.0", "def5678"),
                ("1.5.0", "bbb9999"),
            ],
        )
        manifest = _make_manifest([plugin])

        with patch(
            "apm_cli.marketplace.registry.get_marketplace_by_name",
            return_value=_DUMMY_SOURCE,
        ), patch(
            "apm_cli.marketplace.client.fetch_or_cache",
            return_value=manifest,
        ):
            with _force_rich_fallback():
                result = self.runner.invoke(
                    cli, ["view", "my-plugin@acme-tools", "versions"]
                )

        assert result.exit_code == 0
        output = result.output
        # Title
        assert "my-plugin" in output
        assert "acme-tools" in output
        # All versions present
        assert "2.0.0" in output
        assert "1.5.0" in output
        assert "1.0.0" in output
        # Refs present
        assert "def5678" in output
        assert "bbb9999" in output
        assert "abc1234" in output
        # Latest badge
        assert "latest" in output
        # Install hints
        assert "apm install my-plugin@acme-tools" in output

    # -- Versions sorted descending by semver -----------------------------

    def test_marketplace_versions_sorted_descending(self):
        """Versions are sorted by semver descending (newest first)."""
        plugin = _make_plugin(
            "sorted-plugin",
            versions=[
                ("1.0.0", "ref-100"),
                ("3.0.0", "ref-300"),
                ("2.0.0", "ref-200"),
                ("2.5.0", "ref-250"),
            ],
        )
        manifest = _make_manifest([plugin])

        with patch(
            "apm_cli.marketplace.registry.get_marketplace_by_name",
            return_value=_DUMMY_SOURCE,
        ), patch(
            "apm_cli.marketplace.client.fetch_or_cache",
            return_value=manifest,
        ):
            with _force_rich_fallback():
                result = self.runner.invoke(
                    cli, ["view", "sorted-plugin@acme-tools", "versions"]
                )

        assert result.exit_code == 0
        output = result.output
        # Find positions -- 3.0.0 should come before 2.5.0, etc.
        pos_300 = output.index("3.0.0")
        pos_250 = output.index("2.5.0")
        pos_200 = output.index("2.0.0")
        pos_100 = output.index("1.0.0")
        assert pos_300 < pos_250 < pos_200 < pos_100

    # -- Latest badge only on highest semver ------------------------------

    def test_latest_badge_on_highest_semver(self):
        """Only the highest semver version gets the 'latest' badge."""
        plugin = _make_plugin(
            "badge-plugin",
            versions=[
                ("1.0.0", "ref-old"),
                ("2.0.0", "ref-new"),
            ],
        )
        manifest = _make_manifest([plugin])

        with patch(
            "apm_cli.marketplace.registry.get_marketplace_by_name",
            return_value=_DUMMY_SOURCE,
        ), patch(
            "apm_cli.marketplace.client.fetch_or_cache",
            return_value=manifest,
        ):
            with _force_rich_fallback():
                result = self.runner.invoke(
                    cli, ["view", "badge-plugin@acme-tools", "versions"]
                )

        assert result.exit_code == 0
        # "latest" should appear exactly once
        assert result.output.count("latest") == 1

    # -- Empty versions ---------------------------------------------------

    def test_marketplace_plugin_empty_versions(self):
        """Plugin with empty versions[] shows informational message."""
        plugin = _make_plugin("empty-plugin", versions=[])
        manifest = _make_manifest([plugin])

        with patch(
            "apm_cli.marketplace.registry.get_marketplace_by_name",
            return_value=_DUMMY_SOURCE,
        ), patch(
            "apm_cli.marketplace.client.fetch_or_cache",
            return_value=manifest,
        ):
            result = self.runner.invoke(
                cli, ["view", "empty-plugin@acme-tools", "versions"]
            )

        assert result.exit_code == 0
        assert "no version history" in result.output.lower()
        assert "single-ref" in result.output.lower()

    # -- Plugin not found in marketplace ----------------------------------

    def test_marketplace_plugin_not_found(self):
        """Plugin not in marketplace exits 1 with error message."""
        manifest = _make_manifest([])  # No plugins

        with patch(
            "apm_cli.marketplace.registry.get_marketplace_by_name",
            return_value=_DUMMY_SOURCE,
        ), patch(
            "apm_cli.marketplace.client.fetch_or_cache",
            return_value=manifest,
        ):
            result = self.runner.invoke(
                cli, ["view", "missing-plugin@acme-tools", "versions"]
            )

        assert result.exit_code == 1
        assert "missing-plugin" in result.output.lower()
        assert "not found" in result.output.lower()

    # -- Marketplace not registered ---------------------------------------

    def test_marketplace_not_registered(self):
        """Unregistered marketplace exits 1 with helpful error."""
        with patch(
            "apm_cli.marketplace.registry.get_marketplace_by_name",
            side_effect=MarketplaceNotFoundError("unknown-mkt"),
        ):
            result = self.runner.invoke(
                cli, ["view", "plugin@unknown-mkt", "versions"]
            )

        assert result.exit_code == 1
        assert "unknown-mkt" in result.output.lower()
        assert "not registered" in result.output.lower() or "marketplace" in result.output.lower()

    # -- Network error fetching marketplace -------------------------------

    def test_marketplace_fetch_error(self):
        """Network error exits 1 with suggestion to check network."""
        with patch(
            "apm_cli.marketplace.registry.get_marketplace_by_name",
            return_value=_DUMMY_SOURCE,
        ), patch(
            "apm_cli.marketplace.client.fetch_or_cache",
            side_effect=MarketplaceFetchError("acme-tools", "connection timeout"),
        ):
            result = self.runner.invoke(
                cli, ["view", "plugin@acme-tools", "versions"]
            )

        assert result.exit_code == 1
        assert "failed to fetch" in result.output.lower()
        assert "check your network" in result.output.lower() or "try again" in result.output.lower()

    # -- Non-marketplace package falls through to git flow ----------------

    def test_non_marketplace_uses_git_flow(self):
        """``apm view org/repo versions`` still uses the git-based path."""
        from apm_cli.models.dependency.types import GitReferenceType, RemoteRef

        mock_refs = [
            RemoteRef(
                name="v1.0.0",
                ref_type=GitReferenceType.TAG,
                commit_sha="aabbccdd11223344",
            ),
        ]
        with patch(
            "apm_cli.commands.view.GitHubPackageDownloader"
        ) as mock_cls, patch("apm_cli.commands.view.AuthResolver"):
            mock_cls.return_value.list_remote_refs.return_value = mock_refs
            with _force_rich_fallback():
                result = self.runner.invoke(
                    cli, ["view", "myorg/myrepo", "versions"]
                )

        assert result.exit_code == 0
        assert "v1.0.0" in result.output
        assert "tag" in result.output

    # -- Non-semver versions are appended after semver entries -------------

    def test_non_semver_versions_appended_at_end(self):
        """Non-semver version strings appear after sorted semver entries."""
        plugin = _make_plugin(
            "mixed-plugin",
            versions=[
                ("nightly", "ref-nightly"),
                ("2.0.0", "ref-200"),
                ("1.0.0", "ref-100"),
            ],
        )
        manifest = _make_manifest([plugin])

        with patch(
            "apm_cli.marketplace.registry.get_marketplace_by_name",
            return_value=_DUMMY_SOURCE,
        ), patch(
            "apm_cli.marketplace.client.fetch_or_cache",
            return_value=manifest,
        ):
            with _force_rich_fallback():
                result = self.runner.invoke(
                    cli, ["view", "mixed-plugin@acme-tools", "versions"]
                )

        assert result.exit_code == 0
        output = result.output
        # Semver entries before non-semver
        pos_200 = output.index("2.0.0")
        pos_100 = output.index("1.0.0")
        pos_nightly = output.index("nightly")
        assert pos_200 < pos_100 < pos_nightly
        # "latest" only on 2.0.0 (semver), not "nightly"
        assert result.output.count("latest") == 1

    # -- Pin hint uses highest version ------------------------------------

    def test_pin_hint_uses_highest_version(self):
        """Install pin hint references the highest version."""
        plugin = _make_plugin(
            "pin-plugin",
            versions=[
                ("1.0.0", "ref-1"),
                ("3.2.1", "ref-3"),
            ],
        )
        manifest = _make_manifest([plugin])

        with patch(
            "apm_cli.marketplace.registry.get_marketplace_by_name",
            return_value=_DUMMY_SOURCE,
        ), patch(
            "apm_cli.marketplace.client.fetch_or_cache",
            return_value=manifest,
        ):
            with _force_rich_fallback():
                result = self.runner.invoke(
                    cli, ["view", "pin-plugin@acme-tools", "versions"]
                )

        assert result.exit_code == 0
        assert "#^3.2.1" in result.output
