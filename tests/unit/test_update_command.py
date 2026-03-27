"""Tests for the platform-aware update command."""

import unittest
from unittest.mock import Mock, patch

from click.testing import CliRunner

import apm_cli.commands.update as update_module
from apm_cli.cli import cli


class TestUpdateHelpers(unittest.TestCase):
    """Unit tests for platform-detection helper functions."""

    def test_installer_url_is_windows_on_win32(self):
        with patch.object(update_module.sys, "platform", "win32"):
            self.assertIn("apm-windows", update_module._get_update_installer_url())

    def test_installer_url_is_unix_on_linux(self):
        with patch.object(update_module.sys, "platform", "linux"):
            self.assertIn("apm-unix", update_module._get_update_installer_url())

    def test_installer_suffix_is_ps1_on_windows(self):
        with patch.object(update_module.sys, "platform", "win32"):
            self.assertEqual(".ps1", update_module._get_update_installer_suffix())

    def test_installer_suffix_is_sh_on_unix(self):
        with patch.object(update_module.sys, "platform", "linux"):
            self.assertEqual(".sh", update_module._get_update_installer_suffix())

    def test_installer_run_command_unix_uses_bin_sh_when_exists(self):
        with patch.object(update_module.sys, "platform", "linux"), \
             patch.object(update_module.os.path, "exists", return_value=True):
            cmd = update_module._get_installer_run_command("/tmp/install.sh")
        self.assertEqual(cmd[0], "/bin/sh")
        self.assertEqual(cmd[1], "/tmp/install.sh")

    def test_installer_run_command_unix_falls_back_to_sh(self):
        with patch.object(update_module.sys, "platform", "linux"), \
             patch.object(update_module.os.path, "exists", return_value=False):
            cmd = update_module._get_installer_run_command("/tmp/install.sh")
        self.assertEqual(cmd[0], "sh")

    def test_installer_run_command_windows_raises_when_no_powershell(self):
        with patch.object(update_module.sys, "platform", "win32"), \
             patch.object(update_module.shutil, "which", return_value=None):
            with self.assertRaises(FileNotFoundError):
                update_module._get_installer_run_command("/tmp/install.ps1")

    def test_installer_run_command_windows_uses_pwsh_fallback(self):
        def which_side_effect(name):
            return "pwsh.exe" if name == "pwsh" else None

        with patch.object(update_module.sys, "platform", "win32"), \
             patch.object(update_module.shutil, "which", side_effect=which_side_effect):
            cmd = update_module._get_installer_run_command("/tmp/install.ps1")
        self.assertEqual(cmd[0], "pwsh.exe")


class TestUpdateCommand(unittest.TestCase):
    """Verify update command behavior across supported installer platforms."""

    def setUp(self):
        self.runner = CliRunner()

    def test_manual_update_command_uses_windows_installer(self):
        """Windows manual update instructions should point to aka.ms/apm-windows."""
        with patch.object(update_module.sys, "platform", "win32"):
            command = update_module._get_manual_update_command()

        self.assertIn("aka.ms/apm-windows", command)
        self.assertIn("powershell", command.lower())

    @patch("requests.get")
    @patch("subprocess.run")
    @patch("apm_cli.commands.update.get_version", return_value="0.6.3")
    @patch("apm_cli.commands.update.shutil.which", return_value="powershell.exe")
    @patch("apm_cli.commands.update.os.chmod")
    @patch("apm_cli.utils.version_checker.get_latest_version_from_github", return_value="0.7.0")
    def test_update_uses_powershell_installer_on_windows(
        self,
        mock_latest,
        mock_chmod,
        mock_which,
        mock_version,
        mock_run,
        mock_get,
    ):
        """Windows updates should execute the PowerShell installer path."""
        mock_response = Mock()
        mock_response.text = "Write-Host 'install'"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        mock_run.return_value = Mock(returncode=0)

        with patch.object(update_module.sys, "platform", "win32"):
            result = self.runner.invoke(cli, ["update"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Successfully updated to version 0.7.0", result.output)
        mock_get.assert_called_once()
        self.assertTrue(mock_get.call_args.args[0].endswith("apm-windows"))
        mock_run.assert_called_once()
        run_command = mock_run.call_args.args[0]
        self.assertEqual(run_command[:3], ["powershell.exe", "-ExecutionPolicy", "Bypass"])
        self.assertEqual(run_command[3], "-File")
        mock_chmod.assert_not_called()

    @patch("requests.get")
    @patch("subprocess.run")
    @patch("apm_cli.commands.update.get_version", return_value="0.6.3")
    @patch("apm_cli.commands.update.os.chmod")
    @patch("apm_cli.utils.version_checker.get_latest_version_from_github", return_value="0.7.0")
    def test_update_uses_shell_installer_on_unix(
        self,
        mock_latest,
        mock_chmod,
        mock_version,
        mock_run,
        mock_get,
    ):
        """Unix updates should continue to execute the shell installer path."""
        mock_response = Mock()
        mock_response.text = "echo install"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        mock_run.return_value = Mock(returncode=0)

        with patch.object(update_module.sys, "platform", "darwin"), \
             patch("apm_cli.commands.update.os.path.exists", return_value=True):
            result = self.runner.invoke(cli, ["update"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Successfully updated to version 0.7.0", result.output)
        mock_get.assert_called_once()
        self.assertTrue(mock_get.call_args.args[0].endswith("apm-unix"))
        mock_run.assert_called_once()
        run_command = mock_run.call_args.args[0]
        self.assertEqual(run_command[0], "/bin/sh")
        self.assertEqual(run_command[1][-3:], ".sh")
        mock_chmod.assert_called_once()

    def test_update_dev_version_returns_early(self):
        """Development (unknown) version should warn and return without fetching."""
        with patch("apm_cli.commands.update.get_version", return_value="unknown"):
            result = self.runner.invoke(cli, ["update"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("development", result.output.lower())

    def test_update_dev_version_with_check_returns_early(self):
        """--check with unknown version should also return early cleanly."""
        with patch("apm_cli.commands.update.get_version", return_value="unknown"):
            result = self.runner.invoke(cli, ["update", "--check"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("development", result.output.lower())

    @patch("apm_cli.utils.version_checker.get_latest_version_from_github", return_value=None)
    @patch("apm_cli.commands.update.get_version", return_value="0.6.3")
    def test_update_exits_when_version_fetch_fails(self, mock_version, mock_latest):
        """Should exit(1) when GitHub version fetch returns None."""
        result = self.runner.invoke(cli, ["update"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Unable to fetch latest version", result.output)

    @patch("apm_cli.utils.version_checker.get_latest_version_from_github", return_value="0.6.3")
    @patch("apm_cli.commands.update.get_version", return_value="0.6.3")
    def test_update_already_latest_exits_cleanly(self, mock_version, mock_latest):
        """Should print already-latest message and return 0 when up to date."""
        result = self.runner.invoke(cli, ["update"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("already on the latest version", result.output)

    @patch("apm_cli.utils.version_checker.get_latest_version_from_github", return_value="0.7.0")
    @patch("apm_cli.commands.update.get_version", return_value="0.6.3")
    def test_check_flag_shows_update_available_without_installing(self, mock_version, mock_latest):
        """--check should report available update but NOT download or run installer."""
        result = self.runner.invoke(cli, ["update", "--check"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Update available", result.output)
        self.assertIn("0.6.3", result.output)
        self.assertIn("0.7.0", result.output)
        # Must not actually run the installer
        self.assertNotIn("Downloading", result.output)

    @patch("requests.get")
    @patch("subprocess.run")
    @patch("apm_cli.commands.update.get_version", return_value="0.6.3")
    @patch("apm_cli.commands.update.os.chmod")
    @patch("apm_cli.utils.version_checker.get_latest_version_from_github", return_value="0.7.0")
    def test_update_exits_when_installer_fails(
        self, mock_latest, mock_chmod, mock_version, mock_run, mock_get
    ):
        """Should exit(1) and print error when subprocess installer returns non-zero."""
        mock_response = Mock()
        mock_response.text = "echo install"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        mock_run.return_value = Mock(returncode=1)

        with patch.object(update_module.sys, "platform", "linux"), \
             patch("apm_cli.commands.update.os.path.exists", return_value=True):
            result = self.runner.invoke(cli, ["update"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Installation failed", result.output)

    @patch("apm_cli.utils.version_checker.get_latest_version_from_github", return_value="0.7.0")
    @patch("apm_cli.commands.update.get_version", return_value="0.6.3")
    def test_update_import_error_for_requests(self, mock_version, mock_latest):
        """Should fallback to manual instructions when requests is unavailable."""
        with patch.dict("sys.modules", {"requests": None}):
            result = self.runner.invoke(cli, ["update"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("manually", result.output.lower())

    @patch("requests.get", side_effect=Exception("network error"))
    @patch("apm_cli.commands.update.get_version", return_value="0.6.3")
    @patch("apm_cli.utils.version_checker.get_latest_version_from_github", return_value="0.7.0")
    def test_update_download_exception_shows_manual_instructions(
        self, mock_latest, mock_version, mock_get
    ):
        """Should show manual update command when download raises an exception."""
        result = self.runner.invoke(cli, ["update"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("manually", result.output.lower())

    def test_manual_update_command_uses_unix_installer(self):
        """Unix manual update instructions should use curl and aka.ms/apm-unix."""
        with patch.object(update_module.sys, "platform", "linux"):
            command = update_module._get_manual_update_command()

        self.assertIn("aka.ms/apm-unix", command)
        self.assertIn("curl", command)


if __name__ == "__main__":
    unittest.main()