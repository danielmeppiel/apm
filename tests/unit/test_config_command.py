"""Tests for the apm config command."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from apm_cli.commands.config import config


class TestConfigShow:
    """Tests for `apm config` (show current configuration)."""

    def setup_method(self):
        self.runner = CliRunner()
        self.original_dir = os.getcwd()

    def teardown_method(self):
        try:
            os.chdir(self.original_dir)
        except (FileNotFoundError, OSError):
            pass

    def test_config_show_outside_project(self):
        """Show config when not in an APM project directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                with patch("apm_cli.commands.config.get_version", return_value="1.2.3"):
                    result = self.runner.invoke(config, [])
            finally:
                os.chdir(self.original_dir)
        assert result.exit_code == 0

    def test_config_show_inside_project(self):
        """Show config when apm.yml is present."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                apm_yml = Path(tmp_dir) / "apm.yml"
                apm_yml.write_text("name: myproject\nversion: '0.1'\n")
                with (
                    patch("apm_cli.commands.config.get_version", return_value="1.2.3"),
                    patch(
                        "apm_cli.commands.config._load_apm_config",
                        return_value={
                            "name": "myproject",
                            "version": "0.1",
                            "entrypoint": "main.md",
                        },
                    ),
                ):
                    result = self.runner.invoke(config, [])
            finally:
                os.chdir(self.original_dir)
        assert result.exit_code == 0

    def test_config_show_inside_project_with_compilation(self):
        """Show config when apm.yml has compilation settings."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                apm_yml = Path(tmp_dir) / "apm.yml"
                apm_yml.write_text("name: myproject\ncompilation:\n  output: AGENTS.md\n")
                apm_config = {
                    "name": "myproject",
                    "version": "0.1",
                    "compilation": {
                        "output": "AGENTS.md",
                        "chatmode": "copilot",
                        "resolve_links": False,
                    },
                    "dependencies": {"mcp": ["server1", "server2"]},
                }
                with (
                    patch("apm_cli.commands.config.get_version", return_value="1.2.3"),
                    patch(
                        "apm_cli.commands.config._load_apm_config", return_value=apm_config
                    ),
                ):
                    result = self.runner.invoke(config, [])
            finally:
                os.chdir(self.original_dir)
        assert result.exit_code == 0

    def test_config_show_rich_import_error_fallback(self):
        """Fallback plain-text display when Rich (rich.table.Table) is unavailable."""
        import rich.table

        mock_table_cls = MagicMock(side_effect=ImportError("no rich"))
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                with (
                    patch("apm_cli.commands.config.get_version", return_value="0.9.0"),
                    patch.object(rich.table, "Table", side_effect=ImportError("no rich")),
                ):
                    result = self.runner.invoke(config, [])
            finally:
                os.chdir(self.original_dir)
        assert result.exit_code == 0

    def test_config_show_fallback_inside_project(self):
        """Fallback display inside a project directory when console/table unavailable."""
        import rich.table

        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                apm_yml = Path(tmp_dir) / "apm.yml"
                apm_yml.write_text("name: proj\n")
                apm_config = {
                    "name": "proj",
                    "version": "1.0",
                    "entrypoint": None,
                    "dependencies": {"mcp": []},
                }
                with (
                    patch("apm_cli.commands.config.get_version", return_value="0.9.0"),
                    patch(
                        "apm_cli.commands.config._load_apm_config", return_value=apm_config
                    ),
                    patch.object(rich.table, "Table", side_effect=ImportError("no rich")),
                ):
                    result = self.runner.invoke(config, [])
            finally:
                os.chdir(self.original_dir)
        assert result.exit_code == 0


class TestConfigSet:
    """Tests for `apm config set <key> <value>`."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_set_auto_integrate_true(self):
        """Enable auto-integration."""
        with patch("apm_cli.config.set_auto_integrate") as mock_set:
            result = self.runner.invoke(config, ["set", "auto-integrate", "true"])
        assert result.exit_code == 0
        mock_set.assert_called_once_with(True)

    def test_set_auto_integrate_yes(self):
        """Enable auto-integration with 'yes' alias."""
        with patch("apm_cli.config.set_auto_integrate") as mock_set:
            result = self.runner.invoke(config, ["set", "auto-integrate", "yes"])
        assert result.exit_code == 0
        mock_set.assert_called_once_with(True)

    def test_set_auto_integrate_one(self):
        """Enable auto-integration with '1' alias."""
        with patch("apm_cli.config.set_auto_integrate") as mock_set:
            result = self.runner.invoke(config, ["set", "auto-integrate", "1"])
        assert result.exit_code == 0
        mock_set.assert_called_once_with(True)

    def test_set_auto_integrate_false(self):
        """Disable auto-integration."""
        with patch("apm_cli.config.set_auto_integrate") as mock_set:
            result = self.runner.invoke(config, ["set", "auto-integrate", "false"])
        assert result.exit_code == 0
        mock_set.assert_called_once_with(False)

    def test_set_auto_integrate_no(self):
        """Disable auto-integration with 'no' alias."""
        with patch("apm_cli.config.set_auto_integrate") as mock_set:
            result = self.runner.invoke(config, ["set", "auto-integrate", "no"])
        assert result.exit_code == 0
        mock_set.assert_called_once_with(False)

    def test_set_auto_integrate_zero(self):
        """Disable auto-integration with '0' alias."""
        with patch("apm_cli.config.set_auto_integrate") as mock_set:
            result = self.runner.invoke(config, ["set", "auto-integrate", "0"])
        assert result.exit_code == 0
        mock_set.assert_called_once_with(False)

    def test_set_auto_integrate_invalid_value(self):
        """Reject an invalid value for auto-integrate."""
        result = self.runner.invoke(config, ["set", "auto-integrate", "maybe"])
        assert result.exit_code == 1

    def test_set_unknown_key(self):
        """Reject an unknown configuration key."""
        result = self.runner.invoke(config, ["set", "nonexistent", "value"])
        assert result.exit_code == 1

    def test_set_auto_integrate_case_insensitive(self):
        """Value comparison is case-insensitive."""
        with patch("apm_cli.config.set_auto_integrate") as mock_set:
            result = self.runner.invoke(config, ["set", "auto-integrate", "TRUE"])
        assert result.exit_code == 0
        mock_set.assert_called_once_with(True)


class TestConfigGet:
    """Tests for `apm config get [key]`."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_get_auto_integrate(self):
        """Get the auto-integrate setting."""
        with patch("apm_cli.config.get_auto_integrate", return_value=True):
            result = self.runner.invoke(config, ["get", "auto-integrate"])
        assert result.exit_code == 0
        assert "auto-integrate: True" in result.output

    def test_get_auto_integrate_disabled(self):
        """Get auto-integrate when disabled."""
        with patch("apm_cli.config.get_auto_integrate", return_value=False):
            result = self.runner.invoke(config, ["get", "auto-integrate"])
        assert result.exit_code == 0
        assert "auto-integrate: False" in result.output

    def test_get_unknown_key(self):
        """Reject an unknown key."""
        result = self.runner.invoke(config, ["get", "nonexistent"])
        assert result.exit_code == 1

    def test_get_all_config(self):
        """Show all config when no key is provided."""
        fake_config = {"auto_integrate": True, "default_client": "vscode"}
        with patch("apm_cli.config.get_config", return_value=fake_config):
            result = self.runner.invoke(config, ["get"])
        assert result.exit_code == 0
        assert "auto-integrate: True" in result.output
        # Internal keys must not appear — users cannot set them via apm config set
        assert "default_client" not in result.output

    def test_get_all_config_internal_keys_suppressed(self):
        """Internal config keys are not shown to users."""
        fake_config = {"default_client": "vscode"}
        with patch("apm_cli.config.get_config", return_value=fake_config):
            result = self.runner.invoke(config, ["get"])
        assert result.exit_code == 0
        assert "default_client" not in result.output


class TestAutoIntegrateFunctions:
    """Tests for get_auto_integrate and set_auto_integrate in apm_cli.config."""

    def test_get_auto_integrate_default(self):
        """Default value is True when not set."""
        import apm_cli.config as cfg_module

        with patch.object(cfg_module, "get_config", return_value={}):
            assert cfg_module.get_auto_integrate() is True

    def test_get_auto_integrate_false(self):
        """Returns False when set to False."""
        import apm_cli.config as cfg_module

        with patch.object(
            cfg_module, "get_config", return_value={"auto_integrate": False}
        ):
            assert cfg_module.get_auto_integrate() is False

    def test_set_auto_integrate_calls_update_config(self):
        """set_auto_integrate delegates to update_config."""
        import apm_cli.config as cfg_module

        with patch.object(cfg_module, "update_config") as mock_update:
            cfg_module.set_auto_integrate(True)
            mock_update.assert_called_once_with({"auto_integrate": True})

    def test_set_auto_integrate_false_calls_update_config(self):
        """set_auto_integrate(False) passes False to update_config."""
        import apm_cli.config as cfg_module

        with patch.object(cfg_module, "update_config") as mock_update:
            cfg_module.set_auto_integrate(False)
            mock_update.assert_called_once_with({"auto_integrate": False})
