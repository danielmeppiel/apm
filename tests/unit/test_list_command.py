"""Tests for the apm list command."""

from unittest.mock import patch

from click.testing import CliRunner

from apm_cli.commands.list_cmd import list as list_command


def test_list_fallback_renders_scripts_once():
    """The non-Rich fallback should render the scripts list only once."""
    runner = CliRunner()

    with patch(
        "apm_cli.commands.list_cmd._list_available_scripts",
        return_value={"start": "python main.py", "lint": "ruff check ."},
    ), patch("apm_cli.commands.list_cmd._get_console", return_value=None):
        result = runner.invoke(list_command, obj={})

    assert result.exit_code == 0
    assert result.output.count("Available scripts:") == 1
