"""Extended tests for the apm list command covering all branches."""

import sys
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from apm_cli.commands.list_cmd import list as list_command


class TestListCommandNoScripts:
    """Tests for the list command when no scripts are found."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_no_scripts_exits_zero(self):
        """Empty scripts dict should produce exit code 0."""
        with patch("apm_cli.commands.list_cmd._list_available_scripts", return_value={}):
            result = self.runner.invoke(list_command, obj={})
        assert result.exit_code == 0

    def test_no_scripts_shows_warning(self):
        """Empty scripts dict should show 'No scripts found' warning."""
        with patch("apm_cli.commands.list_cmd._list_available_scripts", return_value={}):
            result = self.runner.invoke(list_command, obj={})
        assert "No scripts found" in result.output

    def test_no_scripts_fallback_shows_example(self):
        """Fallback (no Rich) path for empty scripts shows apm.yml example."""
        with patch(
            "apm_cli.commands.list_cmd._list_available_scripts", return_value={}
        ), patch("apm_cli.commands.list_cmd._rich_panel", side_effect=ImportError):
            result = self.runner.invoke(list_command, obj={})
        assert result.exit_code == 0
        assert "scripts:" in result.output


class TestListCommandWithScripts:
    """Tests for the list command when scripts are available."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_scripts_without_start_exits_zero(self):
        """Scripts without 'start' key should list successfully."""
        with patch(
            "apm_cli.commands.list_cmd._list_available_scripts",
            return_value={"lint": "ruff check ."},
        ), patch("apm_cli.commands.list_cmd._get_console", return_value=None):
            result = self.runner.invoke(list_command, obj={})
        assert result.exit_code == 0

    def test_scripts_without_start_no_default_label(self):
        """Without 'start' key, the default script label should not appear."""
        with patch(
            "apm_cli.commands.list_cmd._list_available_scripts",
            return_value={"lint": "ruff check ."},
        ), patch("apm_cli.commands.list_cmd._get_console", return_value=None):
            result = self.runner.invoke(list_command, obj={})
        assert "default script" not in result.output

    def test_scripts_with_start_shows_default_label(self):
        """With 'start' key, the default script label should appear."""
        with patch(
            "apm_cli.commands.list_cmd._list_available_scripts",
            return_value={"start": "python main.py", "lint": "ruff check ."},
        ), patch("apm_cli.commands.list_cmd._get_console", return_value=None):
            result = self.runner.invoke(list_command, obj={})
        assert result.exit_code == 0
        assert "default script" in result.output

    def test_scripts_fallback_renders_all_scripts(self):
        """Fallback path should render all script names."""
        scripts = {"start": "python main.py", "test": "pytest", "lint": "ruff ."}
        with patch(
            "apm_cli.commands.list_cmd._list_available_scripts",
            return_value=scripts,
        ), patch("apm_cli.commands.list_cmd._get_console", return_value=None):
            result = self.runner.invoke(list_command, obj={})
        assert result.exit_code == 0
        for name in scripts:
            assert name in result.output

    def test_scripts_fallback_renders_commands(self):
        """Fallback path should render script commands."""
        with patch(
            "apm_cli.commands.list_cmd._list_available_scripts",
            return_value={"start": "python main.py"},
        ), patch("apm_cli.commands.list_cmd._get_console", return_value=None):
            result = self.runner.invoke(list_command, obj={})
        assert "python main.py" in result.output


class TestListCommandRichPath:
    """Tests for the list command with a mocked Rich console."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_rich_path_exits_zero(self):
        """With a Rich console, command should succeed."""
        mock_console = MagicMock()
        with patch(
            "apm_cli.commands.list_cmd._list_available_scripts",
            return_value={"start": "python main.py"},
        ), patch("apm_cli.commands.list_cmd._get_console", return_value=mock_console):
            result = self.runner.invoke(list_command, obj={})
        assert result.exit_code == 0

    def test_rich_console_print_called(self):
        """With a Rich console, console.print should be called."""
        mock_console = MagicMock()
        with patch(
            "apm_cli.commands.list_cmd._list_available_scripts",
            return_value={"start": "python main.py"},
        ), patch("apm_cli.commands.list_cmd._get_console", return_value=mock_console):
            self.runner.invoke(list_command, obj={})
        assert mock_console.print.called

    def test_rich_exception_falls_back_to_text(self):
        """If Rich table raises, command falls back to plain text output."""
        mock_console = MagicMock()
        mock_console.print.side_effect = Exception("Rich failure")
        with patch(
            "apm_cli.commands.list_cmd._list_available_scripts",
            return_value={"start": "python main.py"},
        ), patch("apm_cli.commands.list_cmd._get_console", return_value=mock_console):
            result = self.runner.invoke(list_command, obj={})
        assert result.exit_code == 0
        assert "Available scripts:" in result.output


class TestListCommandErrorHandling:
    """Tests for error handling in the list command."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_exception_in_list_scripts_exits_one(self):
        """If _list_available_scripts raises, command should exit with code 1."""
        with patch(
            "apm_cli.commands.list_cmd._list_available_scripts",
            side_effect=RuntimeError("disk read error"),
        ):
            result = self.runner.invoke(list_command, obj={})
        assert result.exit_code == 1

    def test_exception_shows_error_message(self):
        """If _list_available_scripts raises, error message should be shown."""
        with patch(
            "apm_cli.commands.list_cmd._list_available_scripts",
            side_effect=RuntimeError("disk read error"),
        ):
            result = self.runner.invoke(list_command, obj={})
        assert "Error listing scripts" in result.output
