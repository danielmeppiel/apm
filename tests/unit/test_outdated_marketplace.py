"""Unit tests for marketplace-based version checking in ``apm outdated``."""

from unittest.mock import MagicMock, patch

import pytest

from apm_cli.commands.outdated import (
    _check_marketplace_versions,
    _check_one_dep,
)
from apm_cli.deps.lockfile import LockedDependency
from apm_cli.marketplace.models import (
    MarketplaceManifest,
    MarketplacePlugin,
    MarketplaceSource,
    VersionEntry,
)
from apm_cli.models.dependency.types import GitReferenceType, RemoteRef


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _marketplace_dep(
    repo_url="acme-org/skill-auth",
    discovered_via="acme-tools",
    marketplace_plugin_name="skill-auth",
    version="2.1.0",
    resolved_ref="v2.1.0",
    resolved_commit="aaa111",
    host=None,
):
    """Build a marketplace-sourced LockedDependency."""
    return LockedDependency(
        repo_url=repo_url,
        host=host,
        resolved_ref=resolved_ref,
        resolved_commit=resolved_commit,
        discovered_via=discovered_via,
        marketplace_plugin_name=marketplace_plugin_name,
        version=version,
    )


def _git_dep(
    repo_url="org/some-repo",
    resolved_ref="v1.0.0",
    resolved_commit="abc1234",
    host=None,
):
    """Build a plain git-sourced LockedDependency (no marketplace)."""
    return LockedDependency(
        repo_url=repo_url,
        host=host,
        resolved_ref=resolved_ref,
        resolved_commit=resolved_commit,
    )


def _make_source(name="acme-tools"):
    """Build a MarketplaceSource."""
    return MarketplaceSource(
        name=name, owner="acme-org", repo="marketplace",
    )


def _make_manifest(name="acme-tools", plugins=None):
    """Build a MarketplaceManifest."""
    return MarketplaceManifest(
        name=name,
        plugins=tuple(plugins or []),
    )


def _make_plugin(name="skill-auth", versions=None):
    """Build a MarketplacePlugin with version entries."""
    entries = tuple(
        VersionEntry(version=v, ref=f"v{v}")
        for v in (versions or [])
    )
    return MarketplacePlugin(
        name=name,
        source={"type": "github", "repo": "acme-org/skill-auth"},
        versions=entries,
        source_marketplace="acme-tools",
    )


def _remote_tag(name, sha="abc123"):
    """Build a RemoteRef tag."""
    return RemoteRef(name=name, ref_type=GitReferenceType.TAG, commit_sha=sha)


# Patch targets -- marketplace imports are lazy (inside function body)
_PATCH_GET_MKT = "apm_cli.marketplace.registry.get_marketplace_by_name"
_PATCH_FETCH = "apm_cli.marketplace.client.fetch_or_cache"


# ---------------------------------------------------------------------------
# Tests: _check_marketplace_versions
# ---------------------------------------------------------------------------

class TestCheckMarketplaceVersions:
    """Tests for the ``_check_marketplace_versions`` helper."""

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_newer_version_available(self, mock_get_mkt, mock_fetch):
        """Marketplace dep with a newer version reports as outdated."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", ["2.1.0", "3.0.0"])],
        )
        dep = _marketplace_dep(version="2.1.0")

        result = _check_marketplace_versions(dep, verbose=False)

        assert result is not None
        package, current, latest, status, extra, source = result
        assert package == "skill-auth@acme-tools"
        assert current == "2.1.0"
        assert latest == "3.0.0"
        assert status == "outdated"
        assert source == "marketplace: acme-tools"
        assert extra == []

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_already_at_latest(self, mock_get_mkt, mock_fetch):
        """Marketplace dep at latest version reports as up-to-date."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", ["2.1.0", "3.0.0"])],
        )
        dep = _marketplace_dep(version="3.0.0")

        result = _check_marketplace_versions(dep, verbose=False)

        assert result is not None
        package, current, latest, status, extra, source = result
        assert package == "skill-auth@acme-tools"
        assert current == "3.0.0"
        assert latest == "3.0.0"
        assert status == "up-to-date"
        assert source == "marketplace: acme-tools"

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_no_versions_falls_through(self, mock_get_mkt, mock_fetch):
        """Plugin with empty versions[] returns None (fall through to git)."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", versions=[])],
        )
        dep = _marketplace_dep(version="2.1.0")

        result = _check_marketplace_versions(dep, verbose=False)
        assert result is None

    def test_non_marketplace_dep_returns_none(self):
        """Dep without discovered_via returns None immediately."""
        dep = _git_dep()
        result = _check_marketplace_versions(dep, verbose=False)
        assert result is None

    @patch(_PATCH_GET_MKT)
    def test_marketplace_not_found_falls_through(self, mock_get_mkt):
        """MarketplaceNotFoundError returns None with a warning."""
        from apm_cli.marketplace.errors import MarketplaceNotFoundError

        mock_get_mkt.side_effect = MarketplaceNotFoundError("acme-tools")
        dep = _marketplace_dep(version="2.1.0")

        result = _check_marketplace_versions(dep, verbose=False)
        assert result is None

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_fetch_error_falls_through(self, mock_get_mkt, mock_fetch):
        """MarketplaceFetchError returns None with a warning."""
        from apm_cli.marketplace.errors import MarketplaceFetchError

        mock_get_mkt.return_value = _make_source()
        mock_fetch.side_effect = MarketplaceFetchError("acme-tools", "timeout")
        dep = _marketplace_dep(version="2.1.0")

        result = _check_marketplace_versions(dep, verbose=False)
        assert result is None

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_plugin_not_found_falls_through(self, mock_get_mkt, mock_fetch):
        """Plugin name not in manifest returns None (fall through)."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("other-plugin", ["1.0.0"])],
        )
        dep = _marketplace_dep(
            marketplace_plugin_name="skill-auth", version="2.1.0",
        )

        result = _check_marketplace_versions(dep, verbose=False)
        assert result is None

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_verbose_shows_version_list(self, mock_get_mkt, mock_fetch):
        """In verbose mode, extra contains available version strings."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", ["1.0.0", "2.0.0", "3.0.0"])],
        )
        dep = _marketplace_dep(version="1.0.0")

        result = _check_marketplace_versions(dep, verbose=True)

        assert result is not None
        _, _, _, status, extra, _ = result
        assert status == "outdated"
        assert "1.0.0" in extra
        assert "3.0.0" in extra

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_dep_without_version_falls_through(self, mock_get_mkt, mock_fetch):
        """Marketplace dep with empty version string returns None."""
        dep = _marketplace_dep(version="")

        result = _check_marketplace_versions(dep, verbose=False)
        assert result is None
        # Should NOT call marketplace APIs when version is empty
        mock_get_mkt.assert_not_called()

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_invalid_current_version_falls_through(
        self, mock_get_mkt, mock_fetch,
    ):
        """Non-semver current version returns None (fall through)."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", ["2.1.0"])],
        )
        dep = _marketplace_dep(version="not-a-version")

        result = _check_marketplace_versions(dep, verbose=False)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: _check_one_dep integration with marketplace
# ---------------------------------------------------------------------------

class TestCheckOneDepMarketplace:
    """Tests for ``_check_one_dep`` marketplace integration."""

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_marketplace_dep_skips_git(self, mock_get_mkt, mock_fetch):
        """Marketplace dep with versions does NOT call the git downloader."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", ["2.1.0", "3.0.0"])],
        )
        dep = _marketplace_dep(version="2.1.0")
        downloader = MagicMock()

        result = _check_one_dep(dep, downloader, verbose=False)

        package, current, latest, status, extra, source = result
        assert status == "outdated"
        assert source == "marketplace: acme-tools"
        # Git downloader should NOT have been called
        downloader.list_remote_refs.assert_not_called()

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_marketplace_fallback_to_git(self, mock_get_mkt, mock_fetch):
        """Marketplace dep with no versions falls back to git check."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", versions=[])],
        )
        dep = _marketplace_dep(version="2.1.0")
        downloader = MagicMock()
        downloader.list_remote_refs.return_value = [
            _remote_tag("v2.1.0", sha="aaa111"),
            _remote_tag("v3.0.0", sha="bbb222"),
        ]

        result = _check_one_dep(dep, downloader, verbose=False)

        _, _, _, status, _, source = result
        # Should have fallen back to git-based check
        assert source == "git tags"
        downloader.list_remote_refs.assert_called_once()

    def test_git_dep_uses_git_check(self):
        """Non-marketplace dep goes through git path and includes source."""
        dep = _git_dep(resolved_ref="v1.0.0", resolved_commit="aaa111")
        downloader = MagicMock()
        downloader.list_remote_refs.return_value = [
            _remote_tag("v2.0.0", sha="bbb222"),
            _remote_tag("v1.0.0", sha="aaa111"),
        ]

        result = _check_one_dep(dep, downloader, verbose=False)

        package, current, latest, status, extra, source = result
        assert source == "git tags"
        assert status == "outdated"
        downloader.list_remote_refs.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: mixed marketplace + git deps
# ---------------------------------------------------------------------------

class TestMixedDeps:
    """Both marketplace and git deps are checked correctly."""

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_mixed_deps_checked_correctly(self, mock_get_mkt, mock_fetch):
        """Marketplace deps use marketplace, git deps use git."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", ["2.1.0", "3.0.0"])],
        )

        mkt_dep = _marketplace_dep(version="2.1.0")
        git_dep = _git_dep(resolved_ref="v1.0.0", resolved_commit="aaa111")

        downloader = MagicMock()
        downloader.list_remote_refs.return_value = [
            _remote_tag("v1.0.0", sha="aaa111"),
        ]

        mkt_result = _check_one_dep(mkt_dep, downloader, verbose=False)
        git_result = _check_one_dep(git_dep, downloader, verbose=False)

        # Marketplace dep
        _, _, _, mkt_status, _, mkt_source = mkt_result
        assert mkt_source == "marketplace: acme-tools"
        assert mkt_status == "outdated"

        # Git dep
        _, _, _, git_status, _, git_source = git_result
        assert git_source == "git tags"
        assert git_status == "up-to-date"

        # Git downloader called only for the git dep
        assert downloader.list_remote_refs.call_count == 1


# ---------------------------------------------------------------------------
# Tests: version_spec handling
# ---------------------------------------------------------------------------

class TestVersionSpec:
    """Tests for version_spec range checking."""

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_latest_outside_range(self, mock_get_mkt, mock_fetch):
        """Latest version outside version_spec is reported with annotation."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", ["2.1.0", "3.0.0"])],
        )
        dep = _marketplace_dep(version="2.1.0")
        # Simulate version_spec field from parallel task
        dep.version_spec = "^2.0.0"  # type: ignore[attr-defined]

        result = _check_marketplace_versions(dep, verbose=False)

        assert result is not None
        _, _, latest, status, _, _ = result
        assert status == "outdated"
        # 3.0.0 is outside ^2.0.0 range
        assert "outside range" in latest
        assert "^2.0.0" in latest

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_latest_within_range(self, mock_get_mkt, mock_fetch):
        """Latest version within version_spec shows plain version."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", ["2.1.0", "2.5.0"])],
        )
        dep = _marketplace_dep(version="2.1.0")
        dep.version_spec = "^2.0.0"  # type: ignore[attr-defined]

        result = _check_marketplace_versions(dep, verbose=False)

        assert result is not None
        _, _, latest, status, _, _ = result
        assert status == "outdated"
        assert latest == "2.5.0"
        assert "outside range" not in latest

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_no_version_spec_plain_display(self, mock_get_mkt, mock_fetch):
        """Without version_spec, latest version shown without annotation."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", ["2.1.0", "3.0.0"])],
        )
        dep = _marketplace_dep(version="2.1.0")

        result = _check_marketplace_versions(dep, verbose=False)

        assert result is not None
        _, _, latest, status, _, _ = result
        assert status == "outdated"
        assert latest == "3.0.0"
        assert "outside range" not in latest


# ---------------------------------------------------------------------------
# Tests: resolved_version fallback (B6)
# ---------------------------------------------------------------------------

class TestResolvedVersionFallback:
    """Tests for resolved_version priority in current version detection."""

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_resolved_version_used_when_available(
        self, mock_get_mkt, mock_fetch,
    ):
        """resolved_version takes priority over dep.version."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", ["1.2.0", "2.0.0"])],
        )
        dep = _marketplace_dep(version="1.0.0")
        # resolved_version is more accurate (e.g., resolved from ^1.0.0)
        dep.resolved_version = "1.2.0"  # type: ignore[attr-defined]

        result = _check_marketplace_versions(dep, verbose=False)

        assert result is not None
        _, current, latest, status, _, _ = result
        # Should use resolved_version, not dep.version
        assert current == "1.2.0"
        assert latest == "2.0.0"
        assert status == "outdated"

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_falls_back_to_version_when_no_resolved(
        self, mock_get_mkt, mock_fetch,
    ):
        """Without resolved_version, falls back to dep.version."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", ["2.1.0", "3.0.0"])],
        )
        dep = _marketplace_dep(version="2.1.0")
        # No resolved_version attribute set

        result = _check_marketplace_versions(dep, verbose=False)

        assert result is not None
        _, current, _, _, _, _ = result
        assert current == "2.1.0"

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_version_spec_regex_extraction(self, mock_get_mkt, mock_fetch):
        """Extracts base version from version_spec via regex when version is None."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", ["1.0.0", "2.0.0"])],
        )
        dep = _marketplace_dep(version=None)
        dep.version_spec = "^1.0.0"  # type: ignore[attr-defined]

        result = _check_marketplace_versions(dep, verbose=False)

        assert result is not None
        _, current, latest, status, _, _ = result
        assert current == "1.0.0"
        assert status == "outdated"
        # 2.0.0 is outside ^1.0.0 range, so annotation is expected
        assert "outside range" in latest

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_compound_version_spec_extraction(self, mock_get_mkt, mock_fetch):
        """Extracts first version from compound spec like >=1.0.0,<2.0.0."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", ["1.0.0", "1.5.0", "2.0.0"])],
        )
        dep = _marketplace_dep(version=None)
        dep.version_spec = ">=1.0.0,<2.0.0"  # type: ignore[attr-defined]

        result = _check_marketplace_versions(dep, verbose=False)

        assert result is not None
        _, current, _, status, _, _ = result
        # Should extract "1.0.0" from ">=1.0.0,<2.0.0"
        assert current == "1.0.0"
        assert status == "outdated"

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_no_version_no_spec_returns_none(self, mock_get_mkt, mock_fetch):
        """Returns None when neither version nor version_spec available."""
        dep = _marketplace_dep(version=None)
        # version_spec defaults to None on LockedDependency

        result = _check_marketplace_versions(dep, verbose=False)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: best-in-range display (B5)
# ---------------------------------------------------------------------------

class TestBestInRange:
    """Tests for showing best upgrade within version range."""

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_shows_best_in_range_when_available(
        self, mock_get_mkt, mock_fetch,
    ):
        """When latest is outside range but upgrades exist within, show both."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin(
                "skill-auth", ["1.0.0", "1.2.0", "1.5.0", "2.0.0"],
            )],
        )
        dep = _marketplace_dep(version="1.0.0")
        dep.version_spec = "^1.0.0"  # type: ignore[attr-defined]

        result = _check_marketplace_versions(dep, verbose=False)

        assert result is not None
        _, current, latest, status, _, _ = result
        assert current == "1.0.0"
        assert status == "outdated"
        # 2.0.0 is outside ^1.0.0, but 1.5.0 is the best within range
        assert "outside range ^1.0.0" in latest
        assert "best in range: 1.5.0" in latest

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_no_best_in_range_when_already_at_max(
        self, mock_get_mkt, mock_fetch,
    ):
        """When at highest within range, no best-in-range annotation."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", ["1.5.0", "2.0.0"])],
        )
        dep = _marketplace_dep(version="1.5.0")
        dep.version_spec = "^1.0.0"  # type: ignore[attr-defined]

        result = _check_marketplace_versions(dep, verbose=False)

        assert result is not None
        _, _, latest, status, _, _ = result
        assert status == "outdated"
        assert "outside range ^1.0.0" in latest
        assert "best in range" not in latest

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_best_in_range_picks_highest(self, mock_get_mkt, mock_fetch):
        """Best-in-range is the highest valid version, not just any."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin(
                "skill-auth", ["1.0.0", "1.1.0", "1.3.0", "1.9.0", "2.0.0"],
            )],
        )
        dep = _marketplace_dep(version="1.0.0")
        dep.version_spec = "^1.0.0"  # type: ignore[attr-defined]

        result = _check_marketplace_versions(dep, verbose=False)

        assert result is not None
        _, _, latest, _, _, _ = result
        # Should pick 1.9.0 as best in range, not 1.1.0 or 1.3.0
        assert "best in range: 1.9.0" in latest

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_latest_within_range_no_annotation(self, mock_get_mkt, mock_fetch):
        """When latest version IS within range, no outside-range annotation."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", ["1.0.0", "1.5.0"])],
        )
        dep = _marketplace_dep(version="1.0.0")
        dep.version_spec = "^1.0.0"  # type: ignore[attr-defined]

        result = _check_marketplace_versions(dep, verbose=False)

        assert result is not None
        _, _, latest, status, _, _ = result
        assert status == "outdated"
        assert latest == "1.5.0"
        assert "outside range" not in latest


# ---------------------------------------------------------------------------
# Tests: result tuple shape
# ---------------------------------------------------------------------------

class TestResultTupleShape:
    """All code paths produce 6-element tuples."""

    @patch(_PATCH_FETCH)
    @patch(_PATCH_GET_MKT)
    def test_marketplace_result_has_six_elements(
        self, mock_get_mkt, mock_fetch,
    ):
        """Marketplace result tuple has (pkg, current, latest, status, extra, source)."""
        mock_get_mkt.return_value = _make_source()
        mock_fetch.return_value = _make_manifest(
            plugins=[_make_plugin("skill-auth", ["2.1.0", "3.0.0"])],
        )
        dep = _marketplace_dep(version="2.1.0")

        result = _check_marketplace_versions(dep, verbose=False)
        assert result is not None
        assert len(result) == 6

    def test_git_tag_result_has_six_elements(self):
        """Git tag check result tuple has 6 elements."""
        dep = _git_dep(resolved_ref="v1.0.0", resolved_commit="aaa111")
        downloader = MagicMock()
        downloader.list_remote_refs.return_value = [
            _remote_tag("v1.0.0", sha="aaa111"),
        ]

        result = _check_one_dep(dep, downloader, verbose=False)
        assert len(result) == 6

    def test_git_unknown_result_has_six_elements(self):
        """Unknown git result tuple has 6 elements."""
        dep = _git_dep(resolved_ref="v1.0.0")
        downloader = MagicMock()
        downloader.list_remote_refs.side_effect = Exception("network error")

        result = _check_one_dep(dep, downloader, verbose=False)
        assert len(result) == 6
