"""Tests for marketplace manifest validator and validate CLI command."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from apm_cli.marketplace.models import (
    MarketplaceManifest,
    MarketplacePlugin,
    MarketplaceSource,
    VersionEntry,
)
from apm_cli.marketplace.validator import (
    ValidationResult,
    validate_marketplace,
    validate_no_duplicate_names,
    validate_no_duplicate_versions,
    validate_plugin_schema,
    validate_version_format,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path, monkeypatch):
    """Isolate filesystem writes (mirrors test_marketplace_commands.py)."""
    config_dir = str(tmp_path / ".apm")
    monkeypatch.setattr("apm_cli.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr(
        "apm_cli.config.CONFIG_FILE", str(tmp_path / ".apm" / "config.json")
    )
    monkeypatch.setattr("apm_cli.config._config_cache", None)
    monkeypatch.setattr(
        "apm_cli.marketplace.registry._registry_cache", None
    )


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------


def _plugin(name="test-plugin", source="owner/repo", versions=()):
    """Convenience builder for a MarketplacePlugin."""
    return MarketplacePlugin(
        name=name,
        source=source,
        versions=tuple(versions),
    )


def _version(ver="1.0.0", ref="abc123"):
    """Convenience builder for a VersionEntry."""
    return VersionEntry(version=ver, ref=ref)


def _manifest(*plugins, name="test-marketplace"):
    """Convenience builder for a MarketplaceManifest."""
    return MarketplaceManifest(name=name, plugins=tuple(plugins))


# ===================================================================
# Unit tests -- validate_plugin_schema
# ===================================================================


class TestValidatePluginSchema:
    """validate_plugin_schema checks name + source are present."""

    def test_valid_plugins_pass(self):
        plugins = [_plugin("a", "owner/a"), _plugin("b", "owner/b")]
        result = validate_plugin_schema(plugins)
        assert result.passed is True
        assert result.errors == []

    def test_plugin_missing_name(self):
        plugins = [_plugin(name="", source="owner/repo")]
        result = validate_plugin_schema(plugins)
        assert result.passed is False
        assert any("empty name" in e for e in result.errors)

    def test_plugin_missing_source(self):
        plugins = [MarketplacePlugin(name="orphan", source=None)]
        result = validate_plugin_schema(plugins)
        assert result.passed is False
        assert any("source" in e.lower() for e in result.errors)

    def test_empty_list_passes(self):
        result = validate_plugin_schema([])
        assert result.passed is True


# ===================================================================
# Unit tests -- validate_version_format
# ===================================================================


class TestValidateVersionFormat:
    """validate_version_format checks semver + non-empty ref."""

    def test_valid_versions_pass(self):
        plugins = [
            _plugin(
                versions=[_version("1.0.0", "abc"), _version("2.3.4", "def")]
            )
        ]
        result = validate_version_format(plugins)
        assert result.passed is True
        assert result.warnings == []
        assert result.errors == []

    def test_invalid_semver_warns(self):
        plugins = [_plugin(versions=[_version("not-semver", "abc123")])]
        result = validate_version_format(plugins)
        assert result.passed is False
        assert len(result.warnings) == 1
        assert "not valid semver" in result.warnings[0]

    def test_empty_ref_errors(self):
        plugins = [_plugin(versions=[_version("1.0.0", "")])]
        result = validate_version_format(plugins)
        assert result.passed is False
        assert len(result.errors) == 1
        assert "empty ref" in result.errors[0]

    def test_whitespace_only_ref_errors(self):
        plugins = [_plugin(versions=[_version("1.0.0", "   ")])]
        result = validate_version_format(plugins)
        assert result.passed is False
        assert any("empty ref" in e for e in result.errors)

    def test_plugin_with_no_versions_passes(self):
        plugins = [_plugin(versions=[])]
        result = validate_version_format(plugins)
        assert result.passed is True


# ===================================================================
# Unit tests -- validate_no_duplicate_versions
# ===================================================================


class TestValidateNoDuplicateVersions:
    """validate_no_duplicate_versions checks per-plugin uniqueness."""

    def test_unique_versions_pass(self):
        plugins = [
            _plugin(versions=[_version("1.0.0"), _version("2.0.0")])
        ]
        result = validate_no_duplicate_versions(plugins)
        assert result.passed is True
        assert result.warnings == []

    def test_duplicate_version_warns(self):
        plugins = [
            _plugin(
                name="code-review",
                versions=[_version("1.0.0", "aaa"), _version("1.0.0", "bbb")],
            )
        ]
        result = validate_no_duplicate_versions(plugins)
        assert result.passed is False
        assert len(result.warnings) == 1
        assert "code-review" in result.warnings[0]
        assert "1.0.0" in result.warnings[0]

    def test_same_version_across_plugins_is_ok(self):
        plugins = [
            _plugin(name="a", versions=[_version("1.0.0")]),
            _plugin(name="b", versions=[_version("1.0.0")]),
        ]
        result = validate_no_duplicate_versions(plugins)
        assert result.passed is True

    def test_empty_versions_pass(self):
        plugins = [_plugin(versions=[])]
        result = validate_no_duplicate_versions(plugins)
        assert result.passed is True


# ===================================================================
# Unit tests -- validate_no_duplicate_names
# ===================================================================


class TestValidateNoDuplicateNames:
    """validate_no_duplicate_names is case-insensitive."""

    def test_unique_names_pass(self):
        plugins = [_plugin(name="alpha"), _plugin(name="beta")]
        result = validate_no_duplicate_names(plugins)
        assert result.passed is True
        assert result.errors == []

    def test_duplicate_names_case_insensitive(self):
        plugins = [_plugin(name="MyPlugin"), _plugin(name="myplugin")]
        result = validate_no_duplicate_names(plugins)
        assert result.passed is False
        assert len(result.errors) == 1
        assert "myplugin" in result.errors[0].lower()

    def test_empty_list_passes(self):
        result = validate_no_duplicate_names([])
        assert result.passed is True


# ===================================================================
# Unit tests -- validate_marketplace (integration of all checks)
# ===================================================================


class TestValidateMarketplace:
    """validate_marketplace returns all check results."""

    def test_valid_marketplace_returns_all_passed(self):
        manifest = _manifest(
            _plugin("a", "owner/a", versions=[_version("1.0.0")]),
            _plugin("b", "owner/b", versions=[_version("2.0.0")]),
        )
        results = validate_marketplace(manifest)
        assert len(results) == 4
        assert all(r.passed for r in results)

    def test_empty_marketplace_passes_all(self):
        manifest = _manifest()
        results = validate_marketplace(manifest)
        assert len(results) == 4
        assert all(r.passed for r in results)

    def test_returns_mixed_results(self):
        manifest = _manifest(
            _plugin(
                name="good",
                source="owner/good",
                versions=[_version("1.0.0"), _version("1.0.0")],
            ),
        )
        results = validate_marketplace(manifest)
        # Schema and Names should pass; Duplicate versions should fail
        names_by_pass = {r.check_name: r.passed for r in results}
        assert names_by_pass["Schema"] is True
        assert names_by_pass["Names"] is True
        assert names_by_pass["Duplicate versions"] is False


# ===================================================================
# CLI command tests -- apm marketplace validate
# ===================================================================


class TestValidateCommand:
    """CLI command output and behavior."""

    @patch("apm_cli.marketplace.client.fetch_marketplace")
    @patch("apm_cli.marketplace.registry.get_marketplace_by_name")
    def test_output_format(self, mock_get, mock_fetch, runner):
        from apm_cli.commands.marketplace import marketplace

        mock_get.return_value = MarketplaceSource(
            name="acme", owner="acme-org", repo="plugins"
        )
        mock_fetch.return_value = _manifest(
            _plugin("a", "owner/a", versions=[_version("1.0.0")]),
            _plugin("b", "owner/b", versions=[_version("2.0.0")]),
        )
        result = runner.invoke(marketplace, ["validate", "acme"])
        assert result.exit_code == 0
        assert "Validating marketplace" in result.output
        assert "Validation Results:" in result.output
        assert "Summary:" in result.output
        assert "passed" in result.output

    @patch("apm_cli.marketplace.client.fetch_marketplace")
    @patch("apm_cli.marketplace.registry.get_marketplace_by_name")
    def test_verbose_shows_per_plugin_details(
        self, mock_get, mock_fetch, runner
    ):
        from apm_cli.commands.marketplace import marketplace

        mock_get.return_value = MarketplaceSource(
            name="acme", owner="acme-org", repo="plugins"
        )
        mock_fetch.return_value = _manifest(
            _plugin("alpha", "owner/alpha", versions=[_version("1.0.0")]),
        )
        result = runner.invoke(
            marketplace, ["validate", "acme", "--verbose"]
        )
        assert result.exit_code == 0
        assert "alpha" in result.output
        assert "1 versions" in result.output or "source type" in result.output

    @patch("apm_cli.marketplace.registry.get_marketplace_by_name")
    def test_unregistered_marketplace_errors(self, mock_get, runner):
        from apm_cli.marketplace.errors import MarketplaceNotFoundError
        from apm_cli.commands.marketplace import marketplace

        mock_get.side_effect = MarketplaceNotFoundError("nope")
        result = runner.invoke(marketplace, ["validate", "nope"])
        assert result.exit_code != 0

    @patch("apm_cli.marketplace.client.fetch_marketplace")
    @patch("apm_cli.marketplace.registry.get_marketplace_by_name")
    def test_check_refs_shows_warning(self, mock_get, mock_fetch, runner):
        from apm_cli.commands.marketplace import marketplace

        mock_get.return_value = MarketplaceSource(
            name="acme", owner="acme-org", repo="plugins"
        )
        mock_fetch.return_value = _manifest(
            _plugin("a", "owner/a"),
        )
        result = runner.invoke(
            marketplace, ["validate", "acme", "--check-refs"]
        )
        assert result.exit_code == 0
        assert "not yet implemented" in result.output.lower()

    @patch("apm_cli.marketplace.client.fetch_marketplace")
    @patch("apm_cli.marketplace.registry.get_marketplace_by_name")
    def test_validation_errors_cause_nonzero_exit(
        self, mock_get, mock_fetch, runner
    ):
        from apm_cli.commands.marketplace import marketplace

        mock_get.return_value = MarketplaceSource(
            name="acme", owner="acme-org", repo="plugins"
        )
        # Plugin with empty ref triggers an error
        mock_fetch.return_value = _manifest(
            _plugin("bad", "owner/bad", versions=[_version("1.0.0", "")]),
        )
        result = runner.invoke(marketplace, ["validate", "acme"])
        assert result.exit_code != 0
        assert "error" in result.output.lower()

    @patch("apm_cli.marketplace.client.fetch_marketplace")
    @patch("apm_cli.marketplace.registry.get_marketplace_by_name")
    def test_plugin_count_in_output(self, mock_get, mock_fetch, runner):
        from apm_cli.commands.marketplace import marketplace

        mock_get.return_value = MarketplaceSource(
            name="acme", owner="acme-org", repo="plugins"
        )
        mock_fetch.return_value = _manifest(
            _plugin("a", "o/a"),
            _plugin("b", "o/b"),
            _plugin("c", "o/c"),
        )
        result = runner.invoke(marketplace, ["validate", "acme"])
        assert result.exit_code == 0
        assert "3 plugins" in result.output
