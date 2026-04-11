"""Tests for ``apm marketplace publish`` command."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from apm_cli.marketplace.models import (
    MarketplaceManifest,
    MarketplacePlugin,
    MarketplaceSource,
    VersionEntry,
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path, monkeypatch):
    """Isolate filesystem writes so tests never touch real config."""
    config_dir = str(tmp_path / ".apm")
    monkeypatch.setattr("apm_cli.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr(
        "apm_cli.config.CONFIG_FILE", str(tmp_path / ".apm" / "config.json")
    )
    monkeypatch.setattr("apm_cli.config._config_cache", None)
    monkeypatch.setattr("apm_cli.marketplace.registry._registry_cache", None)


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_ACME_SOURCE = MarketplaceSource(
    name="acme-tools",
    owner="acme-org",
    repo="marketplace",
)

_MANIFEST_WITH_PLUGIN = MarketplaceManifest(
    name="acme-tools",
    plugins=(
        MarketplacePlugin(
            name="skill-auth",
            source={"type": "github", "repo": "acme-org/skill-auth"},
            description="Auth skill",
            version="2.0.0",
            versions=(
                VersionEntry(version="1.0.0", ref="aaa111"),
                VersionEntry(version="2.0.0", ref="bbb222"),
            ),
        ),
    ),
)

_MANIFEST_NO_VERSIONS = MarketplaceManifest(
    name="acme-tools",
    plugins=(
        MarketplacePlugin(
            name="skill-auth",
            source={"type": "github", "repo": "acme-org/skill-auth"},
            description="Auth skill",
        ),
    ),
)


def _make_mock_package(name="skill-auth", version="3.0.0"):
    pkg = MagicMock()
    pkg.name = name
    pkg.version = version
    return pkg


def _make_marketplace_json(tmp_path, plugins=None):
    """Write a minimal marketplace.json and return its path."""
    if plugins is None:
        plugins = [
            {
                "name": "skill-auth",
                "source": {"type": "github", "repo": "acme-org/skill-auth"},
                "description": "Auth skill",
                "version": "2.0.0",
                "versions": [
                    {"version": "1.0.0", "ref": "aaa111"},
                    {"version": "2.0.0", "ref": "bbb222"},
                ],
            }
        ]
    data = {"name": "acme-tools", "plugins": plugins}
    mp_file = tmp_path / "marketplace.json"
    mp_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return str(mp_file)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPublishDefaults:
    """Publish with all defaults -- reads apm.yml + git HEAD."""

    @patch("apm_cli.commands.marketplace._update_marketplace_file")
    @patch("apm_cli.commands.marketplace._find_local_marketplace_repo")
    @patch("apm_cli.marketplace.client.fetch_marketplace")
    @patch("apm_cli.marketplace.registry.get_marketplace_by_name")
    @patch("apm_cli.marketplace.registry.get_registered_marketplaces")
    @patch("apm_cli.commands.marketplace._get_git_head_sha")
    @patch("apm_cli.models.apm_package.APMPackage.from_apm_yml")
    def test_publish_all_defaults(
        self,
        mock_from_apm,
        mock_git_sha,
        mock_get_all,
        mock_get_by_name,
        mock_fetch,
        mock_find_local,
        mock_update_file,
        runner,
        tmp_path,
    ):
        from apm_cli.commands.marketplace import marketplace

        mock_from_apm.return_value = _make_mock_package()
        mock_git_sha.return_value = "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3"
        mock_get_all.return_value = [_ACME_SOURCE]
        mock_get_by_name.return_value = _ACME_SOURCE
        mock_fetch.return_value = _MANIFEST_NO_VERSIONS
        mock_find_local.return_value = str(tmp_path)
        mock_update_file.return_value = str(tmp_path / "marketplace.json")

        # Create apm.yml and a placeholder marketplace.json
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("apm.yml").write_text("name: skill-auth\nversion: 3.0.0\n")
            _make_marketplace_json(tmp_path)
            result = runner.invoke(marketplace, ["publish"])

        assert result.exit_code == 0, result.output
        assert "skill-auth" in result.output
        assert "v3.0.0" in result.output
        mock_update_file.assert_called_once_with(
            str(tmp_path / "marketplace.json"),
            "skill-auth",
            "3.0.0",
            "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3",
            False,
        )


class TestPublishExplicitArgs:
    """Publish with explicit --version, --ref, --marketplace, --plugin."""

    @patch("apm_cli.commands.marketplace._update_marketplace_file")
    @patch("apm_cli.commands.marketplace._find_local_marketplace_repo")
    @patch("apm_cli.marketplace.client.fetch_marketplace")
    @patch("apm_cli.marketplace.registry.get_marketplace_by_name")
    def test_publish_explicit_options(
        self,
        mock_get_by_name,
        mock_fetch,
        mock_find_local,
        mock_update_file,
        runner,
        tmp_path,
    ):
        from apm_cli.commands.marketplace import marketplace

        mock_get_by_name.return_value = _ACME_SOURCE
        mock_fetch.return_value = _MANIFEST_NO_VERSIONS
        mock_find_local.return_value = str(tmp_path)
        mock_update_file.return_value = str(tmp_path / "marketplace.json")

        _make_marketplace_json(tmp_path)

        result = runner.invoke(
            marketplace,
            [
                "publish",
                "--marketplace",
                "acme-tools",
                "--version",
                "4.0.0",
                "--ref",
                "abc123def456",
                "--plugin",
                "skill-auth",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "v4.0.0" in result.output
        mock_update_file.assert_called_once_with(
            str(tmp_path / "marketplace.json"),
            "skill-auth",
            "4.0.0",
            "abc123def456",
            False,
        )


class TestPublishVersionConflict:
    """Version already exists -- same ref (skip) or different ref (error)."""

    @patch("apm_cli.marketplace.client.fetch_marketplace")
    @patch("apm_cli.marketplace.registry.get_marketplace_by_name")
    def test_same_version_same_ref_skips(
        self, mock_get_by_name, mock_fetch, runner
    ):
        from apm_cli.commands.marketplace import marketplace

        mock_get_by_name.return_value = _ACME_SOURCE
        mock_fetch.return_value = _MANIFEST_WITH_PLUGIN

        result = runner.invoke(
            marketplace,
            [
                "publish",
                "--marketplace",
                "acme-tools",
                "--version",
                "2.0.0",
                "--ref",
                "bbb222",
                "--plugin",
                "skill-auth",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "already published" in result.output.lower()

    @patch("apm_cli.marketplace.client.fetch_marketplace")
    @patch("apm_cli.marketplace.registry.get_marketplace_by_name")
    def test_same_version_different_ref_errors(
        self, mock_get_by_name, mock_fetch, runner
    ):
        from apm_cli.commands.marketplace import marketplace

        mock_get_by_name.return_value = _ACME_SOURCE
        mock_fetch.return_value = _MANIFEST_WITH_PLUGIN

        result = runner.invoke(
            marketplace,
            [
                "publish",
                "--marketplace",
                "acme-tools",
                "--version",
                "2.0.0",
                "--ref",
                "different_sha",
                "--plugin",
                "skill-auth",
            ],
        )

        assert result.exit_code != 0
        assert "already exists" in result.output.lower()
        assert "--force" in result.output


class TestPublishForce:
    """--force overwrites existing version entry with different ref."""

    @patch("apm_cli.commands.marketplace._update_marketplace_file")
    @patch("apm_cli.commands.marketplace._find_local_marketplace_repo")
    @patch("apm_cli.marketplace.client.fetch_marketplace")
    @patch("apm_cli.marketplace.registry.get_marketplace_by_name")
    def test_force_overwrites(
        self,
        mock_get_by_name,
        mock_fetch,
        mock_find_local,
        mock_update_file,
        runner,
        tmp_path,
    ):
        from apm_cli.commands.marketplace import marketplace

        mock_get_by_name.return_value = _ACME_SOURCE
        mock_fetch.return_value = _MANIFEST_WITH_PLUGIN
        mock_find_local.return_value = str(tmp_path)
        mock_update_file.return_value = str(tmp_path / "marketplace.json")

        _make_marketplace_json(tmp_path)

        result = runner.invoke(
            marketplace,
            [
                "publish",
                "--marketplace",
                "acme-tools",
                "--version",
                "2.0.0",
                "--ref",
                "new_sha_999",
                "--plugin",
                "skill-auth",
                "--force",
            ],
        )

        assert result.exit_code == 0, result.output
        mock_update_file.assert_called_once_with(
            str(tmp_path / "marketplace.json"),
            "skill-auth",
            "2.0.0",
            "new_sha_999",
            True,
        )


class TestPublishDryRun:
    """--dry-run shows what would be published without writing."""

    @patch("apm_cli.commands.marketplace._update_marketplace_file")
    @patch("apm_cli.marketplace.client.fetch_marketplace")
    @patch("apm_cli.marketplace.registry.get_marketplace_by_name")
    def test_dry_run_no_writes(
        self,
        mock_get_by_name,
        mock_fetch,
        mock_update_file,
        runner,
    ):
        from apm_cli.commands.marketplace import marketplace

        mock_get_by_name.return_value = _ACME_SOURCE
        mock_fetch.return_value = _MANIFEST_NO_VERSIONS

        result = runner.invoke(
            marketplace,
            [
                "publish",
                "--marketplace",
                "acme-tools",
                "--version",
                "5.0.0",
                "--ref",
                "abc123",
                "--plugin",
                "skill-auth",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "dry-run" in result.output.lower()
        mock_update_file.assert_not_called()


class TestPublishErrorCases:
    """Error paths: marketplace not registered, plugin missing, bad semver, etc."""

    @patch("apm_cli.marketplace.registry.get_marketplace_by_name")
    def test_marketplace_not_registered(self, mock_get_by_name, runner):
        from apm_cli.commands.marketplace import marketplace
        from apm_cli.marketplace.errors import MarketplaceNotFoundError

        mock_get_by_name.side_effect = MarketplaceNotFoundError("ghost")

        result = runner.invoke(
            marketplace,
            [
                "publish",
                "--marketplace",
                "ghost",
                "--version",
                "1.0.0",
                "--ref",
                "abc",
                "--plugin",
                "some-plugin",
            ],
        )

        assert result.exit_code != 0
        assert "ghost" in result.output.lower()

    @patch("apm_cli.marketplace.client.fetch_marketplace")
    @patch("apm_cli.marketplace.registry.get_marketplace_by_name")
    def test_plugin_not_found(self, mock_get_by_name, mock_fetch, runner):
        from apm_cli.commands.marketplace import marketplace

        mock_get_by_name.return_value = _ACME_SOURCE
        mock_fetch.return_value = MarketplaceManifest(
            name="acme-tools", plugins=()
        )

        result = runner.invoke(
            marketplace,
            [
                "publish",
                "--marketplace",
                "acme-tools",
                "--version",
                "1.0.0",
                "--ref",
                "abc",
                "--plugin",
                "nonexistent-plugin",
            ],
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_invalid_semver_version(self, runner):
        from apm_cli.commands.marketplace import marketplace

        result = runner.invoke(
            marketplace,
            [
                "publish",
                "--marketplace",
                "acme-tools",
                "--version",
                "not-a-version",
                "--ref",
                "abc",
                "--plugin",
                "skill-auth",
            ],
        )

        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "semver" in result.output.lower()

    def test_no_apm_yml_and_no_flags(self, runner, tmp_path):
        from apm_cli.commands.marketplace import marketplace

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                marketplace,
                [
                    "publish",
                    "--marketplace",
                    "acme-tools",
                    "--ref",
                    "abc123",
                ],
            )

        assert result.exit_code != 0
        assert "apm.yml" in result.output.lower() or "--plugin" in result.output

    @patch("apm_cli.marketplace.registry.get_registered_marketplaces")
    def test_no_marketplaces_registered(self, mock_get_all, runner):
        from apm_cli.commands.marketplace import marketplace

        mock_get_all.return_value = []

        result = runner.invoke(
            marketplace,
            [
                "publish",
                "--version",
                "1.0.0",
                "--ref",
                "abc",
                "--plugin",
                "skill-auth",
            ],
        )

        assert result.exit_code != 0
        assert "no marketplace" in result.output.lower()

    @patch("apm_cli.marketplace.registry.get_registered_marketplaces")
    def test_multiple_marketplaces_without_flag(self, mock_get_all, runner):
        from apm_cli.commands.marketplace import marketplace

        mock_get_all.return_value = [
            MarketplaceSource(name="m1", owner="a", repo="b"),
            MarketplaceSource(name="m2", owner="c", repo="d"),
        ]

        result = runner.invoke(
            marketplace,
            [
                "publish",
                "--version",
                "1.0.0",
                "--ref",
                "abc",
                "--plugin",
                "skill-auth",
            ],
        )

        assert result.exit_code != 0
        assert "multiple" in result.output.lower() or "--marketplace" in result.output


class TestPublishAutoDetect:
    """Auto-detect marketplace when only one is registered."""

    @patch("apm_cli.commands.marketplace._update_marketplace_file")
    @patch("apm_cli.commands.marketplace._find_local_marketplace_repo")
    @patch("apm_cli.marketplace.client.fetch_marketplace")
    @patch("apm_cli.marketplace.registry.get_marketplace_by_name")
    @patch("apm_cli.marketplace.registry.get_registered_marketplaces")
    def test_auto_selects_single_marketplace(
        self,
        mock_get_all,
        mock_get_by_name,
        mock_fetch,
        mock_find_local,
        mock_update_file,
        runner,
        tmp_path,
    ):
        from apm_cli.commands.marketplace import marketplace

        mock_get_all.return_value = [_ACME_SOURCE]
        mock_get_by_name.return_value = _ACME_SOURCE
        mock_fetch.return_value = _MANIFEST_NO_VERSIONS
        mock_find_local.return_value = str(tmp_path)
        mock_update_file.return_value = str(tmp_path / "marketplace.json")

        _make_marketplace_json(tmp_path)

        result = runner.invoke(
            marketplace,
            [
                "publish",
                "--version",
                "1.0.0",
                "--ref",
                "sha123",
                "--plugin",
                "skill-auth",
            ],
        )

        assert result.exit_code == 0, result.output
        # Should have resolved to acme-tools
        mock_get_by_name.assert_called_once_with("acme-tools")


# ---------------------------------------------------------------------------
# _update_marketplace_file unit tests (real file I/O on tmp_path)
# ---------------------------------------------------------------------------


class TestUpdateMarketplaceFile:
    """Integration-style tests for the raw JSON read/modify/write helper."""

    def test_adds_new_version_entry(self, tmp_path):
        from apm_cli.commands.marketplace import _update_marketplace_file

        mp_file = _make_marketplace_json(tmp_path)
        _update_marketplace_file(mp_file, "skill-auth", "3.0.0", "ccc333", False)

        data = json.loads(Path(mp_file).read_text(encoding="utf-8"))
        versions = data["plugins"][0]["versions"]
        assert len(versions) == 3
        assert versions[-1] == {"version": "3.0.0", "ref": "ccc333"}

    def test_force_replaces_existing_version(self, tmp_path):
        from apm_cli.commands.marketplace import _update_marketplace_file

        mp_file = _make_marketplace_json(tmp_path)
        _update_marketplace_file(mp_file, "skill-auth", "2.0.0", "new_ref", True)

        data = json.loads(Path(mp_file).read_text(encoding="utf-8"))
        versions = data["plugins"][0]["versions"]
        # Old 2.0.0 replaced, 1.0.0 still present
        ver_map = {v["version"]: v["ref"] for v in versions}
        assert ver_map["2.0.0"] == "new_ref"
        assert ver_map["1.0.0"] == "aaa111"
        assert len(versions) == 2

    def test_raises_on_missing_plugin(self, tmp_path):
        from apm_cli.commands.marketplace import _update_marketplace_file

        mp_file = _make_marketplace_json(tmp_path)
        with pytest.raises(ValueError, match="not found"):
            _update_marketplace_file(mp_file, "nonexistent", "1.0.0", "ref", False)

    def test_case_insensitive_plugin_match(self, tmp_path):
        from apm_cli.commands.marketplace import _update_marketplace_file

        mp_file = _make_marketplace_json(tmp_path)
        _update_marketplace_file(mp_file, "SKILL-AUTH", "3.0.0", "ccc333", False)

        data = json.loads(Path(mp_file).read_text(encoding="utf-8"))
        versions = data["plugins"][0]["versions"]
        assert len(versions) == 3

    def test_creates_versions_array_when_missing(self, tmp_path):
        from apm_cli.commands.marketplace import _update_marketplace_file

        plugins = [
            {
                "name": "bare-plugin",
                "source": {"type": "github", "repo": "acme-org/bare"},
            }
        ]
        mp_file = _make_marketplace_json(tmp_path, plugins=plugins)
        _update_marketplace_file(mp_file, "bare-plugin", "1.0.0", "sha1", False)

        data = json.loads(Path(mp_file).read_text(encoding="utf-8"))
        versions = data["plugins"][0]["versions"]
        assert versions == [{"version": "1.0.0", "ref": "sha1"}]


# ---------------------------------------------------------------------------
# _get_git_head_sha unit tests
# ---------------------------------------------------------------------------


class TestGetGitHeadSha:
    """Tests for the git HEAD SHA helper."""

    @patch("subprocess.run")
    def test_returns_sha(self, mock_run):
        from apm_cli.commands.marketplace import _get_git_head_sha

        mock_run.return_value = MagicMock(
            returncode=0, stdout="abc123def456\n"
        )
        assert _get_git_head_sha() == "abc123def456"

    @patch("subprocess.run")
    def test_returns_none_on_failure(self, mock_run):
        from apm_cli.commands.marketplace import _get_git_head_sha

        mock_run.return_value = MagicMock(returncode=128, stdout="")
        assert _get_git_head_sha() is None

    @patch("subprocess.run", side_effect=OSError("no git"))
    def test_returns_none_on_exception(self, mock_run):
        from apm_cli.commands.marketplace import _get_git_head_sha

        assert _get_git_head_sha() is None
