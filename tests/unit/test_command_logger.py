"""Unit tests for CommandLogger, InstallLogger, and _ValidationOutcome."""

from unittest.mock import MagicMock, patch

from apm_cli.core.command_logger import CommandLogger, InstallLogger, _ValidationOutcome


class TestValidationOutcome:
    def test_all_failed(self):
        outcome = _ValidationOutcome(valid=[], invalid=[("pkg", "not found")])
        assert outcome.all_failed is True
        assert outcome.has_failures is True

    def test_partial_failure(self):
        outcome = _ValidationOutcome(
            valid=[("pkg1", False)],
            invalid=[("pkg2", "not found")],
        )
        assert outcome.all_failed is False
        assert outcome.has_failures is True

    def test_all_valid(self):
        outcome = _ValidationOutcome(
            valid=[("pkg1", False), ("pkg2", True)],
            invalid=[],
        )
        assert outcome.all_failed is False
        assert outcome.has_failures is False

    def test_new_packages(self):
        outcome = _ValidationOutcome(
            valid=[("pkg1", False), ("pkg2", True), ("pkg3", False)],
            invalid=[],
        )
        new = outcome.new_packages
        assert len(new) == 2
        assert ("pkg1", False) in new
        assert ("pkg3", False) in new

    def test_empty(self):
        outcome = _ValidationOutcome(valid=[], invalid=[])
        assert outcome.all_failed is False
        assert outcome.has_failures is False


class TestCommandLogger:
    @patch("apm_cli.core.command_logger._rich_info")
    def test_start(self, mock_info):
        logger = CommandLogger("test")
        logger.start("Starting operation...")
        mock_info.assert_called_once_with("Starting operation...", symbol="running")

    @patch("apm_cli.core.command_logger._rich_success")
    def test_success(self, mock_success):
        logger = CommandLogger("test")
        logger.success("Done!")
        mock_success.assert_called_once_with("Done!", symbol="sparkles")

    @patch("apm_cli.core.command_logger._rich_error")
    def test_error(self, mock_error):
        logger = CommandLogger("test")
        logger.error("Failed!")
        mock_error.assert_called_once_with("Failed!", symbol="error")

    @patch("apm_cli.core.command_logger._rich_warning")
    def test_warning(self, mock_warning):
        logger = CommandLogger("test")
        logger.warning("Careful!")
        mock_warning.assert_called_once_with("Careful!", symbol="warning")

    @patch("apm_cli.core.command_logger._rich_echo")
    def test_verbose_detail_when_verbose(self, mock_echo):
        logger = CommandLogger("test", verbose=True)
        logger.verbose_detail("Some detail")
        mock_echo.assert_called_once_with("Some detail", color="dim")

    @patch("apm_cli.core.command_logger._rich_echo")
    def test_verbose_detail_when_not_verbose(self, mock_echo):
        logger = CommandLogger("test", verbose=False)
        logger.verbose_detail("Some detail")
        mock_echo.assert_not_called()

    def test_should_execute_default(self):
        logger = CommandLogger("test")
        assert logger.should_execute is True

    def test_should_execute_dry_run(self):
        logger = CommandLogger("test", dry_run=True)
        assert logger.should_execute is False

    def test_diagnostics_lazy_init(self):
        logger = CommandLogger("test")
        assert logger._diagnostics is None
        diag = logger.diagnostics
        assert diag is not None
        assert logger.diagnostics is diag  # Same instance

    def test_diagnostics_verbose_propagated(self):
        logger = CommandLogger("test", verbose=True)
        assert logger.diagnostics.verbose is True

    @patch("apm_cli.core.command_logger._rich_echo")
    def test_auth_step_verbose(self, mock_echo):
        logger = CommandLogger("test", verbose=True)
        logger.auth_step("Trying GITHUB_APM_PAT", success=True, detail="found")
        mock_echo.assert_called_once()
        call_args = mock_echo.call_args
        assert "GITHUB_APM_PAT" in call_args[0][0]
        assert call_args[1].get("symbol") == "check"

    @patch("apm_cli.core.command_logger._rich_echo")
    def test_auth_step_not_verbose(self, mock_echo):
        logger = CommandLogger("test", verbose=False)
        logger.auth_step("Trying GITHUB_APM_PAT", success=True)
        mock_echo.assert_not_called()

    @patch("apm_cli.core.command_logger._rich_echo")
    def test_auth_resolved_with_token(self, mock_echo):
        logger = CommandLogger("test", verbose=True)
        mock_ctx = MagicMock()
        mock_ctx.source = "GITHUB_APM_PAT"
        mock_ctx.token_type = "fine-grained"
        mock_ctx.token = "some-token"
        logger.auth_resolved(mock_ctx)
        mock_echo.assert_called_once()
        assert "GITHUB_APM_PAT" in mock_echo.call_args[0][0]

    @patch("apm_cli.core.command_logger._rich_echo")
    def test_auth_resolved_no_token(self, mock_echo):
        logger = CommandLogger("test", verbose=True)
        mock_ctx = MagicMock()
        mock_ctx.token = None
        logger.auth_resolved(mock_ctx)
        mock_echo.assert_called_once()
        assert "no credentials" in mock_echo.call_args[0][0]

    @patch("apm_cli.core.command_logger._rich_echo")
    def test_auth_resolved_not_verbose(self, mock_echo):
        logger = CommandLogger("test", verbose=False)
        mock_ctx = MagicMock()
        mock_ctx.token = "tok"
        logger.auth_resolved(mock_ctx)
        mock_echo.assert_not_called()

    def test_render_summary_no_diagnostics(self):
        """render_summary with no diagnostics should not crash."""
        logger = CommandLogger("test")
        logger.render_summary()  # No-op, no diagnostics

    @patch("apm_cli.core.command_logger._rich_info")
    def test_progress(self, mock_info):
        logger = CommandLogger("test")
        logger.progress("Processing 3 files...")
        mock_info.assert_called_once_with("Processing 3 files...", symbol="info")

    @patch("apm_cli.core.command_logger._rich_info")
    def test_dry_run_notice(self, mock_info):
        logger = CommandLogger("test", dry_run=True)
        logger.dry_run_notice("Would compile 3 files")
        mock_info.assert_called_once_with(
            "[dry-run] Would compile 3 files", symbol="info"
        )

    @patch("apm_cli.core.command_logger._rich_echo")
    def test_auth_step_failure(self, mock_echo):
        logger = CommandLogger("test", verbose=True)
        logger.auth_step("Trying gh CLI", success=False)
        mock_echo.assert_called_once()
        assert mock_echo.call_args[1].get("symbol") == "error"


class TestInstallLogger:
    def test_partial_flag(self):
        logger = InstallLogger(partial=True)
        assert logger.partial is True
        assert logger.command == "install"

    @patch("apm_cli.core.command_logger._rich_info")
    def test_validation_start(self, mock_info):
        logger = InstallLogger()
        logger.validation_start(3)
        mock_info.assert_called_once_with("Validating 3 packages...", symbol="gear")

    @patch("apm_cli.core.command_logger._rich_info")
    def test_validation_start_singular(self, mock_info):
        logger = InstallLogger()
        logger.validation_start(1)
        mock_info.assert_called_once_with("Validating 1 package...", symbol="gear")

    @patch("apm_cli.core.command_logger._rich_success")
    def test_validation_pass_new(self, mock_success):
        logger = InstallLogger()
        logger.validation_pass("microsoft/repo", already_present=False)
        mock_success.assert_called_once()

    @patch("apm_cli.core.command_logger._rich_echo")
    def test_validation_pass_existing(self, mock_echo):
        logger = InstallLogger()
        logger.validation_pass("microsoft/repo", already_present=True)
        assert "already in apm.yml" in mock_echo.call_args[0][0]

    @patch("apm_cli.core.command_logger._rich_error")
    def test_validation_fail(self, mock_error):
        logger = InstallLogger()
        logger.validation_fail("bad/pkg", "not accessible")
        assert "bad/pkg" in mock_error.call_args[0][0]

    @patch("apm_cli.core.command_logger._rich_error")
    def test_validation_summary_all_failed(self, mock_error):
        logger = InstallLogger()
        outcome = _ValidationOutcome(valid=[], invalid=[("pkg", "reason")])
        result = logger.validation_summary(outcome)
        assert result is False
        mock_error.assert_called()

    @patch("apm_cli.core.command_logger._rich_warning")
    def test_validation_summary_partial_failure(self, mock_warning):
        logger = InstallLogger()
        outcome = _ValidationOutcome(
            valid=[("pkg1", False)],
            invalid=[("pkg2", "reason")],
        )
        result = logger.validation_summary(outcome)
        assert result is True
        mock_warning.assert_called()

    def test_validation_summary_all_valid(self):
        logger = InstallLogger()
        outcome = _ValidationOutcome(valid=[("pkg", False)], invalid=[])
        result = logger.validation_summary(outcome)
        assert result is True

    @patch("apm_cli.core.command_logger._rich_info")
    def test_resolution_start_partial(self, mock_info):
        logger = InstallLogger(partial=True)
        logger.resolution_start(to_install_count=1, lockfile_count=4)
        assert "1 new package" in mock_info.call_args[0][0]

    @patch("apm_cli.core.command_logger._rich_info")
    def test_resolution_start_full(self, mock_info):
        logger = InstallLogger(partial=False)
        logger.resolution_start(to_install_count=4, lockfile_count=4)
        first_call = mock_info.call_args_list[0][0][0]
        assert "apm.yml" in first_call
        # Second call shows lockfile info
        second_call = mock_info.call_args_list[1][0][0]
        assert "4 locked dependencies" in second_call

    @patch("apm_cli.core.command_logger._rich_info")
    def test_nothing_to_install_partial(self, mock_info):
        logger = InstallLogger(partial=True)
        logger.nothing_to_install()
        assert "already installed" in mock_info.call_args[0][0]

    @patch("apm_cli.core.command_logger._rich_success")
    def test_nothing_to_install_full(self, mock_success):
        logger = InstallLogger(partial=False)
        logger.nothing_to_install()
        assert "up to date" in mock_success.call_args[0][0]

    @patch("apm_cli.core.command_logger._rich_success")
    def test_install_summary_apm_only(self, mock_success):
        logger = InstallLogger()
        logger.install_summary(apm_count=3, mcp_count=0)
        assert "3 APM dependencies" in mock_success.call_args[0][0]

    @patch("apm_cli.core.command_logger._rich_success")
    def test_install_summary_both(self, mock_success):
        logger = InstallLogger()
        logger.install_summary(apm_count=2, mcp_count=1)
        call_msg = mock_success.call_args[0][0]
        assert "APM" in call_msg
        assert "MCP" in call_msg

    @patch("apm_cli.core.command_logger._rich_warning")
    def test_install_summary_with_errors(self, mock_warning):
        logger = InstallLogger()
        logger.install_summary(apm_count=2, mcp_count=0, errors=1)
        assert "error" in mock_warning.call_args[0][0]

    @patch("apm_cli.core.command_logger._rich_error")
    def test_install_summary_all_errors(self, mock_error):
        logger = InstallLogger()
        logger.install_summary(apm_count=0, mcp_count=0, errors=3)
        assert "3 error" in mock_error.call_args[0][0]

    @patch("apm_cli.core.command_logger._rich_error")
    def test_download_failed(self, mock_error):
        logger = InstallLogger()
        logger.download_failed("pkg/repo", "timeout")
        assert "pkg/repo" in mock_error.call_args[0][0]

    @patch("apm_cli.core.command_logger._rich_echo")
    def test_download_complete(self, mock_echo):
        logger = InstallLogger()
        logger.download_complete("pkg/repo", ref_suffix="v1.0")
        call_msg = mock_echo.call_args[0][0]
        assert "pkg/repo" in call_msg
        assert "v1.0" in call_msg

    @patch("apm_cli.core.command_logger._rich_echo")
    def test_download_complete_no_ref(self, mock_echo):
        logger = InstallLogger()
        logger.download_complete("pkg/repo")
        assert "pkg/repo" in mock_echo.call_args[0][0]
