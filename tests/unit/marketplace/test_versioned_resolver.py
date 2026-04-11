"""Tests for version-aware marketplace resolution.

Covers:
- parse_marketplace_ref with #version_spec suffix
- resolve_marketplace_plugin with versioned plugins
- resolve_marketplace_plugin backward compat (no versions)
- LockedDependency.version_spec round-trip serialization
"""

from unittest.mock import MagicMock, patch

import pytest

from apm_cli.deps.lockfile import LockedDependency
from apm_cli.marketplace.models import (
    MarketplaceManifest,
    MarketplacePlugin,
    MarketplaceSource,
    VersionEntry,
)
from apm_cli.marketplace.resolver import (
    parse_marketplace_ref,
    resolve_marketplace_plugin,
    resolve_plugin_source,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_versioned_plugin(
    name="my-plugin",
    repo="acme-org/my-plugin",
    source_ref="main",
    versions=None,
):
    """Build a MarketplacePlugin with a github source and optional versions."""
    if versions is None:
        versions = (
            VersionEntry(version="1.0.0", ref="v1.0.0"),
            VersionEntry(version="1.1.0", ref="v1.1.0"),
            VersionEntry(version="2.0.0", ref="v2.0.0"),
            VersionEntry(version="2.1.0", ref="abc123def"),
        )
    source = {"type": "github", "repo": repo, "ref": source_ref}
    return MarketplacePlugin(
        name=name,
        source=source,
        versions=versions,
        source_marketplace="test-mkt",
    )


def _make_unversioned_plugin(name="legacy-plugin", repo="acme-org/legacy"):
    """Build a MarketplacePlugin WITHOUT versions (backward compat)."""
    return MarketplacePlugin(
        name=name,
        source={"type": "github", "repo": repo, "ref": "v1.0"},
        versions=(),
        source_marketplace="test-mkt",
    )


def _make_manifest(*plugins, plugin_root=""):
    return MarketplaceManifest(
        name="test-mkt",
        plugins=tuple(plugins),
        plugin_root=plugin_root,
    )


def _make_source():
    return MarketplaceSource(name="test-mkt", owner="acme-org", repo="marketplace")


# ---------------------------------------------------------------------------
# parse_marketplace_ref -- version specifier suffix
# ---------------------------------------------------------------------------


class TestParseMarketplaceRefVersionSpec:
    """Parsing NAME@MARKETPLACE#version_spec."""

    def test_caret_specifier(self):
        result = parse_marketplace_ref("plugin@mkt#^2.0.0")
        assert result == ("plugin", "mkt", "^2.0.0")

    def test_tilde_specifier(self):
        result = parse_marketplace_ref("plugin@mkt#~1.1.0")
        assert result == ("plugin", "mkt", "~1.1.0")

    def test_exact_version(self):
        result = parse_marketplace_ref("plugin@mkt#2.1.0")
        assert result == ("plugin", "mkt", "2.1.0")

    def test_range_specifier(self):
        result = parse_marketplace_ref("plugin@mkt#>=1.0.0,<3.0.0")
        assert result == ("plugin", "mkt", ">=1.0.0,<3.0.0")

    def test_raw_git_ref(self):
        result = parse_marketplace_ref("plugin@mkt#main")
        assert result == ("plugin", "mkt", "main")

    def test_no_specifier(self):
        result = parse_marketplace_ref("plugin@mkt")
        assert result == ("plugin", "mkt", None)

    def test_empty_after_hash(self):
        """Trailing # with nothing after is not a valid specifier."""
        result = parse_marketplace_ref("plugin@mkt#")
        # The regex .+ requires at least 1 char after #, so # alone
        # causes the full match to fail -> None.
        assert result is None

    def test_whitespace_preserved_in_spec(self):
        """Outer whitespace is stripped; inner spec is preserved."""
        result = parse_marketplace_ref("  plugin@mkt#^2.0.0  ")
        assert result == ("plugin", "mkt", "^2.0.0")


# ---------------------------------------------------------------------------
# resolve_marketplace_plugin -- version-aware resolution
# ---------------------------------------------------------------------------


class TestResolveMarketplacePluginVersioned:
    """Test resolve_marketplace_plugin when plugin has versions."""

    def _resolve(self, plugin, version_spec=None):
        """Call resolve_marketplace_plugin with mocked I/O."""
        manifest = _make_manifest(plugin)
        source = _make_source()

        with (
            patch(
                "apm_cli.marketplace.resolver.get_marketplace_by_name",
                return_value=source,
            ),
            patch(
                "apm_cli.marketplace.resolver.fetch_or_cache",
                return_value=manifest,
            ),
        ):
            return resolve_marketplace_plugin(
                plugin.name,
                "test-mkt",
                version_spec=version_spec,
            )

    def test_caret_spec_resolves_highest_match(self):
        """^2.0.0 should pick 2.1.0 (highest in ^2 range)."""
        plugin = _make_versioned_plugin()
        canonical, resolved, resolved_version = self._resolve(plugin, version_spec="^2.0.0")
        assert canonical == "acme-org/my-plugin#abc123def"
        assert resolved.name == "my-plugin"
        assert resolved_version == "2.1.0"

    def test_exact_version_spec(self):
        """Exact version 1.1.0 should pick exactly v1.1.0."""
        plugin = _make_versioned_plugin()
        canonical, _, resolved_version = self._resolve(plugin, version_spec="1.1.0")
        assert canonical == "acme-org/my-plugin#v1.1.0"
        assert resolved_version == "1.1.0"

    def test_tilde_spec(self):
        """~1.0.0 should pick 1.1.0 (highest in ~1.0 range: >=1.0.0, <1.1.0).
        Wait -- tilde means >=1.0.0, <1.1.0. So 1.0.0 is the only match."""
        plugin = _make_versioned_plugin()
        canonical, _, resolved_version = self._resolve(plugin, version_spec="~1.0.0")
        assert canonical == "acme-org/my-plugin#v1.0.0"
        assert resolved_version == "1.0.0"

    def test_no_spec_selects_latest(self):
        """No version_spec (None) selects the highest available version."""
        plugin = _make_versioned_plugin()
        canonical, _, resolved_version = self._resolve(plugin, version_spec=None)
        # 2.1.0 is the highest -> ref = abc123def
        assert canonical == "acme-org/my-plugin#abc123def"
        assert resolved_version == "2.1.0"

    def test_source_ref_overridden_by_version(self):
        """The source.ref (main) should be replaced by the version entry ref."""
        plugin = _make_versioned_plugin(source_ref="main")
        canonical, _, resolved_version = self._resolve(plugin, version_spec="1.0.0")
        # Source had #main, but version resolution should override to v1.0.0
        assert canonical == "acme-org/my-plugin#v1.0.0"
        assert "#main" not in canonical
        assert resolved_version == "1.0.0"

    def test_no_matching_version_raises(self):
        """Specifier that matches nothing raises ValueError."""
        plugin = _make_versioned_plugin()
        with pytest.raises(ValueError, match="No version matches"):
            self._resolve(plugin, version_spec=">=99.0.0")

    def test_raw_git_ref_with_versions(self):
        """A raw git ref (not semver) overrides the canonical ref directly."""
        plugin = _make_versioned_plugin(source_ref="main")
        canonical, _, resolved_version = self._resolve(plugin, version_spec="feature-branch")
        assert canonical == "acme-org/my-plugin#feature-branch"
        assert resolved_version is None


class TestResolveMarketplacePluginUnversioned:
    """Test backward compat: plugins without versions use existing flow."""

    def _resolve(self, plugin, version_spec=None):
        manifest = _make_manifest(plugin)
        source = _make_source()

        with (
            patch(
                "apm_cli.marketplace.resolver.get_marketplace_by_name",
                return_value=source,
            ),
            patch(
                "apm_cli.marketplace.resolver.fetch_or_cache",
                return_value=manifest,
            ),
        ):
            return resolve_marketplace_plugin(
                plugin.name,
                "test-mkt",
                version_spec=version_spec,
            )

    def test_unversioned_no_spec(self):
        """Unversioned plugin without spec uses source.ref."""
        plugin = _make_unversioned_plugin()
        canonical, resolved, resolved_version = self._resolve(plugin)
        assert canonical == "acme-org/legacy#v1.0"
        assert resolved.name == "legacy-plugin"
        assert resolved_version is None

    def test_unversioned_with_spec_ignored(self):
        """Unversioned plugin ignores version_spec -- uses source.ref."""
        plugin = _make_unversioned_plugin()
        canonical, _, resolved_version = self._resolve(plugin, version_spec="^2.0.0")
        # No versions on plugin, so version_spec is silently ignored
        assert canonical == "acme-org/legacy#v1.0"
        assert resolved_version is None

    def test_unversioned_raw_ref_ignored(self):
        """Unversioned plugin ignores raw ref -- uses source.ref."""
        plugin = _make_unversioned_plugin()
        canonical, _, resolved_version = self._resolve(plugin, version_spec="develop")
        assert canonical == "acme-org/legacy#v1.0"
        assert resolved_version is None


# ---------------------------------------------------------------------------
# Canonical string correctness
# ---------------------------------------------------------------------------


class TestCanonicalStringFromVersionEntry:
    """Verify the canonical string is built correctly from version entry."""

    def test_ref_replaces_source_ref(self):
        """resolve_plugin_source produces owner/repo#source_ref;
        version resolution should replace #source_ref with #entry.ref."""
        plugin = _make_versioned_plugin(
            repo="org/repo",
            source_ref="old-branch",
            versions=(VersionEntry(version="3.0.0", ref="sha-abc"),),
        )
        manifest = _make_manifest(plugin)
        source = _make_source()

        with (
            patch(
                "apm_cli.marketplace.resolver.get_marketplace_by_name",
                return_value=source,
            ),
            patch(
                "apm_cli.marketplace.resolver.fetch_or_cache",
                return_value=manifest,
            ),
        ):
            canonical, _, resolved_version = resolve_marketplace_plugin(
                "my-plugin", "test-mkt", version_spec="3.0.0"
            )
        assert canonical == "org/repo#sha-abc"
        assert resolved_version == "3.0.0"

    def test_source_without_ref_gets_version_ref(self):
        """When source has no ref, canonical is owner/repo (no #).
        Version resolution should append #entry.ref."""
        plugin = MarketplacePlugin(
            name="no-ref-plugin",
            source={"type": "github", "repo": "org/repo"},
            versions=(VersionEntry(version="1.0.0", ref="v1.0.0"),),
            source_marketplace="test-mkt",
        )
        manifest = _make_manifest(plugin)
        source = _make_source()

        with (
            patch(
                "apm_cli.marketplace.resolver.get_marketplace_by_name",
                return_value=source,
            ),
            patch(
                "apm_cli.marketplace.resolver.fetch_or_cache",
                return_value=manifest,
            ),
        ):
            canonical, _, resolved_version = resolve_marketplace_plugin(
                "no-ref-plugin", "test-mkt"
            )
        assert canonical == "org/repo#v1.0.0"
        assert resolved_version == "1.0.0"


# ---------------------------------------------------------------------------
# LockedDependency.version_spec serialization
# ---------------------------------------------------------------------------


class TestLockedDependencyVersionSpec:
    """Verify version_spec field round-trips correctly in LockedDependency."""

    def test_default_none(self):
        dep = LockedDependency(repo_url="owner/repo")
        assert dep.version_spec is None

    def test_to_dict_omits_none(self):
        dep = LockedDependency(repo_url="owner/repo")
        d = dep.to_dict()
        assert "version_spec" not in d

    def test_to_dict_includes_value(self):
        dep = LockedDependency(repo_url="owner/repo", version_spec="^2.0.0")
        d = dep.to_dict()
        assert d["version_spec"] == "^2.0.0"

    def test_from_dict_missing_field(self):
        """Old lockfiles without version_spec still deserialize."""
        dep = LockedDependency.from_dict({"repo_url": "owner/repo"})
        assert dep.version_spec is None

    def test_from_dict_with_field(self):
        dep = LockedDependency.from_dict({
            "repo_url": "owner/repo",
            "version_spec": "~1.5.0",
        })
        assert dep.version_spec == "~1.5.0"

    def test_roundtrip(self):
        original = LockedDependency(
            repo_url="owner/repo",
            resolved_commit="abc123",
            resolved_ref="v2.1.0",
            discovered_via="acme-tools",
            marketplace_plugin_name="my-plugin",
            version_spec="^2.0.0",
        )
        restored = LockedDependency.from_dict(original.to_dict())
        assert restored.version_spec == "^2.0.0"
        assert restored.discovered_via == "acme-tools"
        assert restored.marketplace_plugin_name == "my-plugin"
        assert restored.resolved_commit == "abc123"
        assert restored.resolved_ref == "v2.1.0"

    def test_backward_compat_existing_fields(self):
        """Existing fields still work alongside version_spec."""
        dep = LockedDependency.from_dict({
            "repo_url": "owner/repo",
            "resolved_commit": "abc123",
            "content_hash": "sha256:def456",
            "is_dev": True,
            "discovered_via": "mkt",
            "version_spec": ">=1.0.0,<3.0.0",
        })
        assert dep.resolved_commit == "abc123"
        assert dep.content_hash == "sha256:def456"
        assert dep.is_dev is True
        assert dep.discovered_via == "mkt"
        assert dep.version_spec == ">=1.0.0,<3.0.0"

    def test_yaml_lockfile_roundtrip(self):
        """version_spec survives a full YAML lockfile write/read cycle."""
        from apm_cli.deps.lockfile import LockFile

        lock = LockFile()
        lock.add_dependency(LockedDependency(
            repo_url="owner/repo",
            version_spec="^2.0.0",
            discovered_via="acme-tools",
        ))

        yaml_str = lock.to_yaml()
        restored = LockFile.from_yaml(yaml_str)
        dep = restored.get_dependency("owner/repo")
        assert dep is not None
        assert dep.version_spec == "^2.0.0"
        assert dep.discovered_via == "acme-tools"


# ---------------------------------------------------------------------------
# LockedDependency.resolved_version serialization
# ---------------------------------------------------------------------------


class TestLockedDependencyResolvedVersion:
    """Verify resolved_version field round-trips correctly in LockedDependency."""

    def test_default_none(self):
        dep = LockedDependency(repo_url="owner/repo")
        assert dep.resolved_version is None

    def test_to_dict_omits_none(self):
        dep = LockedDependency(repo_url="owner/repo")
        d = dep.to_dict()
        assert "resolved_version" not in d

    def test_to_dict_includes_value(self):
        dep = LockedDependency(repo_url="owner/repo", resolved_version="2.1.0")
        d = dep.to_dict()
        assert d["resolved_version"] == "2.1.0"

    def test_from_dict_missing_field(self):
        """Old lockfiles without resolved_version still deserialize."""
        dep = LockedDependency.from_dict({"repo_url": "owner/repo"})
        assert dep.resolved_version is None

    def test_from_dict_with_field(self):
        dep = LockedDependency.from_dict({
            "repo_url": "owner/repo",
            "resolved_version": "1.5.0",
        })
        assert dep.resolved_version == "1.5.0"

    def test_roundtrip(self):
        original = LockedDependency(
            repo_url="owner/repo",
            resolved_commit="abc123",
            resolved_ref="v2.1.0",
            discovered_via="acme-tools",
            marketplace_plugin_name="my-plugin",
            version_spec="^2.0.0",
            resolved_version="2.1.0",
        )
        restored = LockedDependency.from_dict(original.to_dict())
        assert restored.resolved_version == "2.1.0"
        assert restored.version_spec == "^2.0.0"
        assert restored.discovered_via == "acme-tools"

    def test_backward_compat_existing_fields(self):
        """Existing fields still work alongside resolved_version."""
        dep = LockedDependency.from_dict({
            "repo_url": "owner/repo",
            "resolved_commit": "abc123",
            "content_hash": "sha256:def456",
            "is_dev": True,
            "discovered_via": "mkt",
            "version_spec": ">=1.0.0,<3.0.0",
            "resolved_version": "2.0.0",
        })
        assert dep.resolved_commit == "abc123"
        assert dep.content_hash == "sha256:def456"
        assert dep.is_dev is True
        assert dep.discovered_via == "mkt"
        assert dep.version_spec == ">=1.0.0,<3.0.0"
        assert dep.resolved_version == "2.0.0"

    def test_yaml_lockfile_roundtrip(self):
        """resolved_version survives a full YAML lockfile write/read cycle."""
        from apm_cli.deps.lockfile import LockFile

        lock = LockFile()
        lock.add_dependency(LockedDependency(
            repo_url="owner/repo",
            version_spec="^2.0.0",
            resolved_version="2.1.0",
            discovered_via="acme-tools",
        ))

        yaml_str = lock.to_yaml()
        restored = LockFile.from_yaml(yaml_str)
        dep = restored.get_dependency("owner/repo")
        assert dep is not None
        assert dep.resolved_version == "2.1.0"
        assert dep.version_spec == "^2.0.0"
        assert dep.discovered_via == "acme-tools"


# ---------------------------------------------------------------------------
# B7: warning_handler callback
# ---------------------------------------------------------------------------


class TestWarningHandler:
    """Verify resolve_marketplace_plugin routes security warnings to handler."""

    def test_immutability_warning_via_handler(self):
        """Ref-swap warning goes through warning_handler, not stdlib."""
        plugin = _make_versioned_plugin()
        manifest = _make_manifest(plugin)
        source = _make_source()

        captured = []

        with (
            patch(
                "apm_cli.marketplace.resolver.get_marketplace_by_name",
                return_value=source,
            ),
            patch(
                "apm_cli.marketplace.resolver.fetch_or_cache",
                return_value=manifest,
            ),
            patch(
                "apm_cli.marketplace.version_pins.check_version_pin",
                return_value="old-ref-abc",  # pretend ref changed
            ),
            patch(
                "apm_cli.marketplace.version_pins.record_version_pin",
            ),
        ):
            resolve_marketplace_plugin(
                "my-plugin",
                "test-mkt",
                warning_handler=captured.append,
            )

        # Exactly one immutability warning
        assert len(captured) == 1
        assert "ref changed" in captured[0]
        assert "ref swap attack" in captured[0]
        assert "my-plugin" in captured[0]

    def test_shadow_warning_via_handler(self):
        """Shadow detection warning goes through warning_handler."""
        # Unversioned plugin so we skip version pin logic
        plugin = _make_unversioned_plugin()
        manifest = _make_manifest(plugin)
        source = _make_source()

        captured = []

        # Shadow mock
        from unittest.mock import MagicMock
        shadow = MagicMock()
        shadow.marketplace_name = "evil-mkt"

        with (
            patch(
                "apm_cli.marketplace.resolver.get_marketplace_by_name",
                return_value=source,
            ),
            patch(
                "apm_cli.marketplace.resolver.fetch_or_cache",
                return_value=manifest,
            ),
            patch(
                "apm_cli.marketplace.shadow_detector.detect_shadows",
                return_value=[shadow],
            ),
        ):
            resolve_marketplace_plugin(
                "legacy-plugin",
                "test-mkt",
                warning_handler=captured.append,
            )

        assert len(captured) == 1
        assert "evil-mkt" in captured[0]
        assert "legacy-plugin" in captured[0]

    def test_no_handler_falls_back_to_stdlib(self, caplog):
        """Without warning_handler, warnings go through Python logging."""
        import logging

        plugin = _make_versioned_plugin()
        manifest = _make_manifest(plugin)
        source = _make_source()

        with (
            patch(
                "apm_cli.marketplace.resolver.get_marketplace_by_name",
                return_value=source,
            ),
            patch(
                "apm_cli.marketplace.resolver.fetch_or_cache",
                return_value=manifest,
            ),
            patch(
                "apm_cli.marketplace.version_pins.check_version_pin",
                return_value="old-ref",
            ),
            patch(
                "apm_cli.marketplace.version_pins.record_version_pin",
            ),
            caplog.at_level(logging.WARNING, logger="apm_cli.marketplace.resolver"),
        ):
            resolve_marketplace_plugin(
                "my-plugin",
                "test-mkt",
                # No warning_handler -- should use stdlib logging
            )

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) >= 1
        assert "ref changed" in warnings[0].message
