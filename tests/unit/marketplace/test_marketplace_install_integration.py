"""Tests for the install flow with mocked marketplace resolution."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from apm_cli.marketplace.resolver import parse_marketplace_ref


class TestInstallMarketplacePreParse:
    """The pre-parse intercept in _validate_and_add_packages_to_apm_yml."""

    def test_marketplace_ref_detected(self):
        """NAME@MARKETPLACE triggers marketplace resolution."""
        result = parse_marketplace_ref("security-checks@acme-tools")
        assert result == ("security-checks", "acme-tools", None)

    def test_owner_repo_not_intercepted(self):
        """owner/repo should NOT be intercepted."""
        result = parse_marketplace_ref("owner/repo")
        assert result is None

    def test_owner_repo_at_alias_not_intercepted(self):
        """owner/repo@alias should NOT be intercepted (has slash)."""
        result = parse_marketplace_ref("owner/repo@alias")
        assert result is None

    def test_bare_name_not_intercepted(self):
        """Just a name without @ should NOT be intercepted."""
        result = parse_marketplace_ref("just-a-name")
        assert result is None

    def test_ssh_not_intercepted(self):
        """SSH URLs should NOT be intercepted (has colon)."""
        result = parse_marketplace_ref("git@github.com:o/r")
        assert result is None


class TestValidationOutcomeProvenance:
    """Verify marketplace provenance is attached to ValidationOutcome."""

    def test_outcome_has_provenance_field(self):
        from apm_cli.core.command_logger import _ValidationOutcome

        outcome = _ValidationOutcome(
            valid=[("owner/repo", False)],
            invalid=[],
            marketplace_provenance={
                "owner/repo": {
                    "discovered_via": "acme-tools",
                    "marketplace_plugin_name": "security-checks",
                }
            },
        )
        assert outcome.marketplace_provenance is not None
        assert "owner/repo" in outcome.marketplace_provenance

    def test_outcome_no_provenance(self):
        from apm_cli.core.command_logger import _ValidationOutcome

        outcome = _ValidationOutcome(valid=[], invalid=[])
        assert outcome.marketplace_provenance is None


class TestInstallExitCodeOnAllFailed:
    """Bug B2: install must exit(1) when ALL packages fail validation."""

    @patch("apm_cli.commands.install._validate_and_add_packages_to_apm_yml")
    @patch("apm_cli.commands.install.InstallLogger")
    @patch("apm_cli.commands.install.DiagnosticCollector")
    def test_all_failed_exits_nonzero(
        self, mock_diag_cls, mock_logger_cls, mock_validate, tmp_path, monkeypatch
    ):
        """When outcome.all_failed is True, install raises SystemExit(1)."""
        from apm_cli.core.command_logger import _ValidationOutcome

        outcome = _ValidationOutcome(
            valid=[],
            invalid=[("bad-pkg", "not found")],
        )
        mock_validate.return_value = ([], outcome)

        mock_logger = MagicMock()
        mock_logger_cls.return_value = mock_logger

        # Create minimal apm.yml so pre-flight check passes
        import yaml
        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text(yaml.dump({
            "name": "test", "version": "0.1.0",
            "dependencies": {"apm": []},
        }))
        monkeypatch.chdir(tmp_path)

        from click.testing import CliRunner
        from apm_cli.commands.install import install

        runner = CliRunner()
        result = runner.invoke(install, ["bad-pkg"], catch_exceptions=False)
        assert result.exit_code != 0, (
            f"Expected non-zero exit but got {result.exit_code}"
        )


class TestVerboseResolvedVersion:
    """Bug B3: verbose install shows resolved version when available."""

    @patch("apm_cli.commands.install._validate_package_exists", return_value=True)
    @patch("apm_cli.commands.install._rich_success")
    @patch("apm_cli.marketplace.resolver.resolve_marketplace_plugin")
    @patch("apm_cli.marketplace.resolver.parse_marketplace_ref")
    def test_resolved_version_logged(
        self, mock_parse, mock_resolve, mock_success, mock_validate,
        tmp_path, monkeypatch,
    ):
        """When resolved_version is set, verbose_detail shows it."""
        import yaml

        mock_parse.return_value = ("developer", "agent-forge", "^1.0.0")
        mock_resolve.return_value = (
            "acme-org/agent-forge/agents/developer#abc123",
            MagicMock(),  # resolved_plugin
            "1.2.0",       # resolved_version
        )

        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text(yaml.dump({
            "name": "test", "version": "0.1.0",
            "dependencies": {"apm": []},
        }))
        monkeypatch.chdir(tmp_path)

        logger = MagicMock()
        logger.verbose = True

        from apm_cli.commands.install import _validate_and_add_packages_to_apm_yml

        _validate_and_add_packages_to_apm_yml(
            ["developer@agent-forge#^1.0.0"],
            logger=logger,
        )

        # Check verbose_detail was called with the resolved version
        calls = [str(c) for c in logger.verbose_detail.call_args_list]
        version_calls = [c for c in calls if "Resolved version: 1.2.0" in c]
        assert len(version_calls) == 1, (
            f"Expected one 'Resolved version: 1.2.0' call, got: {calls}"
        )

    @patch("apm_cli.commands.install._validate_package_exists", return_value=True)
    @patch("apm_cli.commands.install._rich_success")
    @patch("apm_cli.marketplace.resolver.resolve_marketplace_plugin")
    @patch("apm_cli.marketplace.resolver.parse_marketplace_ref")
    def test_no_resolved_version_skips_log(
        self, mock_parse, mock_resolve, mock_success, mock_validate,
        tmp_path, monkeypatch,
    ):
        """When resolved_version is None, no version line is logged."""
        import yaml

        mock_parse.return_value = ("developer", "agent-forge", None)
        mock_resolve.return_value = (
            "acme-org/agent-forge/agents/developer#main",
            MagicMock(),  # resolved_plugin
            None,          # no resolved_version
        )

        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text(yaml.dump({
            "name": "test", "version": "0.1.0",
            "dependencies": {"apm": []},
        }))
        monkeypatch.chdir(tmp_path)

        logger = MagicMock()
        logger.verbose = True

        from apm_cli.commands.install import _validate_and_add_packages_to_apm_yml

        _validate_and_add_packages_to_apm_yml(
            ["developer@agent-forge"],
            logger=logger,
        )

        calls = [str(c) for c in logger.verbose_detail.call_args_list]
        version_calls = [c for c in calls if "Resolved version:" in c]
        assert len(version_calls) == 0, (
            f"Expected no 'Resolved version' call, got: {calls}"
        )
