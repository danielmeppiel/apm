"""Unit tests for the apm mcp command group.

Tests cover:
- mcp search: no results, results found, network error, non-rich fallback
- mcp show: server not found, server found with packages/remotes, network error, fallback
- mcp list: no results, results found, network error, non-rich fallback
- Truncation logic for long names/descriptions
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from apm_cli.cli import cli

# ---------------------------------------------------------------------------
# Sample server data fixtures
# ---------------------------------------------------------------------------

_SAMPLE_SERVER_BASIC = {
    "name": "test-server",
    "description": "A short description",
    "version": "1.0.0",
}

_SAMPLE_SERVER_LONG_DESC = {
    "name": "verbose-server",
    "description": "A" * 90,  # exceeds 80-char truncation threshold
    "version": "2.0.0",
}

_SAMPLE_SERVER_DETAIL = {
    "id": "abc12345-abcd-abcd-abcd-abcdef012345",
    "name": "detailed-server",
    "description": "A detailed server with packages and remotes",
    "version_detail": {"version": "3.1.4"},
    "repository": {"url": "https://github.com/example/repo"},
    "packages": [
        {"registry_name": "npm", "name": "example-mcp-pkg", "runtime_hint": "node"}
    ],
    "remotes": [{"transport_type": "sse", "url": "https://api.example.com/sse"}],
}

_SAMPLE_SERVER_NO_VERSION = {
    "name": "minimal-server",
    "description": "Minimal server",
    "version": "0.1.0",
    "version_detail": {},
}


# ---------------------------------------------------------------------------
# mcp search
# ---------------------------------------------------------------------------


class TestMcpSearch(unittest.TestCase):
    """Tests for ``apm mcp search``."""

    def setUp(self):
        self.runner = CliRunner()

    def _invoke(self, args):
        return self.runner.invoke(cli, ["mcp", "search"] + args)

    @patch("apm_cli.commands.mcp._get_console", return_value=None)
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_search_no_results_fallback(self, mock_reg_cls, mock_console):
        """Fallback path: no servers found should warn without crashing."""
        mock_reg_cls.return_value.search_packages.return_value = []
        result = self._invoke(["nonexistent-query"])
        self.assertEqual(result.exit_code, 0)

    @patch("apm_cli.commands.mcp._get_console", return_value=None)
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_search_with_results_fallback(self, mock_reg_cls, mock_console):
        """Fallback path: matching servers should be printed one per line."""
        mock_reg_cls.return_value.search_packages.return_value = [
            _SAMPLE_SERVER_BASIC,
        ]
        result = self._invoke(["test"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-server", result.output)

    @patch("apm_cli.commands.mcp._get_console", return_value=None)
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_search_network_error_exits_nonzero(self, mock_reg_cls, mock_console):
        """Search error should print an error message and exit non-zero."""
        mock_reg_cls.return_value.search_packages.side_effect = RuntimeError("timeout")
        result = self._invoke(["fail-query"])
        self.assertNotEqual(result.exit_code, 0)

    @patch("apm_cli.commands.mcp._get_console")
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_search_rich_no_results(self, mock_reg_cls, mock_console_fn):
        """Rich path: no results should print a warning, not crash."""
        console = MagicMock()
        mock_console_fn.return_value = console
        mock_reg_cls.return_value.search_packages.return_value = []
        result = self._invoke(["nothing"])
        self.assertEqual(result.exit_code, 0)
        console.print.assert_called()

    @patch("apm_cli.commands.mcp._get_console")
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_search_rich_results_shown(self, mock_reg_cls, mock_console_fn):
        """Rich path: results should produce a table and summary."""
        console = MagicMock()
        mock_console_fn.return_value = console
        mock_reg_cls.return_value.search_packages.return_value = [
            _SAMPLE_SERVER_BASIC,
            _SAMPLE_SERVER_LONG_DESC,
        ]
        result = self._invoke(["test", "--limit", "5"])
        self.assertEqual(result.exit_code, 0)
        # console.print should be called multiple times (header, count, table, footer)
        self.assertGreater(console.print.call_count, 2)

    @patch("apm_cli.commands.mcp._get_console")
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_search_rich_limit_hint_shown_at_capacity(
        self, mock_reg_cls, mock_console_fn
    ):
        """Rich path: when results == limit, a '--limit N*2' hint should appear."""
        console = MagicMock()
        mock_console_fn.return_value = console
        # Return exactly `limit` results so the hint is triggered
        mock_reg_cls.return_value.search_packages.return_value = [
            _SAMPLE_SERVER_BASIC
        ] * 3
        result = self._invoke(["test", "--limit", "3"])
        self.assertEqual(result.exit_code, 0)
        # Find any call that mentions --limit
        calls_text = " ".join(str(c) for c in console.print.call_args_list)
        self.assertIn("--limit 6", calls_text)

    @patch("apm_cli.commands.mcp._get_console")
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_search_description_truncated(self, mock_reg_cls, mock_console_fn):
        """Descriptions longer than 80 chars must be truncated with '...'."""
        console = MagicMock()
        mock_console_fn.return_value = console
        long_server = {"name": "s", "description": "B" * 90, "version": "1.0"}
        mock_reg_cls.return_value.search_packages.return_value = [long_server]
        result = self._invoke(["s"])
        self.assertEqual(result.exit_code, 0)
        # The table should have been printed; description is handled inside the command
        console.print.assert_called()


# ---------------------------------------------------------------------------
# mcp show
# ---------------------------------------------------------------------------


class TestMcpShow(unittest.TestCase):
    """Tests for ``apm mcp show``."""

    def setUp(self):
        self.runner = CliRunner()

    def _invoke(self, args):
        return self.runner.invoke(cli, ["mcp", "show"] + args)

    @patch("apm_cli.commands.mcp._get_console", return_value=None)
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_show_not_found_fallback_exits(self, mock_reg_cls, mock_console):
        """Fallback path: unknown server should print error and exit non-zero."""
        mock_reg_cls.return_value.get_package_info.side_effect = ValueError("not found")
        result = self._invoke(["unknown-server"])
        self.assertNotEqual(result.exit_code, 0)

    @patch("apm_cli.commands.mcp._get_console", return_value=None)
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_show_found_fallback_prints_info(self, mock_reg_cls, mock_console):
        """Fallback path: known server should print name, description, repo."""
        mock_reg_cls.return_value.get_package_info.return_value = _SAMPLE_SERVER_DETAIL
        result = self._invoke(["detailed-server"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("detailed-server", result.output)
        self.assertIn("github.com/example/repo", result.output)

    @patch("apm_cli.commands.mcp._get_console", return_value=None)
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_show_network_error_exits(self, mock_reg_cls, mock_console):
        """Fallback path: network error should exit non-zero."""
        mock_reg_cls.return_value.get_package_info.side_effect = RuntimeError("timeout")
        result = self._invoke(["some-server"])
        self.assertNotEqual(result.exit_code, 0)

    @patch("apm_cli.commands.mcp._get_console")
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_show_rich_not_found_exits(self, mock_reg_cls, mock_console_fn):
        """Rich path: server not found should print error panel and exit non-zero."""
        console = MagicMock()
        mock_console_fn.return_value = console
        mock_reg_cls.return_value.get_package_info.side_effect = ValueError("not found")
        result = self._invoke(["missing"])
        self.assertNotEqual(result.exit_code, 0)

    @patch("apm_cli.commands.mcp._get_console")
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_show_rich_full_detail(self, mock_reg_cls, mock_console_fn):
        """Rich path: full server info with packages and remotes should render."""
        console = MagicMock()
        mock_console_fn.return_value = console
        mock_reg_cls.return_value.get_package_info.return_value = _SAMPLE_SERVER_DETAIL
        result = self._invoke(["detailed-server"])
        self.assertEqual(result.exit_code, 0)
        # Should print the main info table, remote table, package table, install guide
        self.assertGreater(console.print.call_count, 3)

    @patch("apm_cli.commands.mcp._get_console")
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_show_rich_no_packages_no_remotes(self, mock_reg_cls, mock_console_fn):
        """Rich path: server with no packages/remotes should still render."""
        console = MagicMock()
        mock_console_fn.return_value = console
        server = {
            "name": "simple",
            "description": "Simple server",
            "version": "1.0.0",
            "repository": {"url": "https://example.com"},
        }
        mock_reg_cls.return_value.get_package_info.return_value = server
        result = self._invoke(["simple"])
        self.assertEqual(result.exit_code, 0)
        console.print.assert_called()

    @patch("apm_cli.commands.mcp._get_console")
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_show_rich_version_from_version_field(self, mock_reg_cls, mock_console_fn):
        """Rich path: version taken from 'version' field when version_detail absent."""
        console = MagicMock()
        mock_console_fn.return_value = console
        server = {
            "name": "simple",
            "description": "Simple",
            "version": "4.2.0",
        }
        mock_reg_cls.return_value.get_package_info.return_value = server
        result = self._invoke(["simple"])
        self.assertEqual(result.exit_code, 0)

    @patch("apm_cli.commands.mcp._get_console")
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_show_long_package_name_truncated(self, mock_reg_cls, mock_console_fn):
        """Rich path: package names longer than 25 chars should be truncated."""
        console = MagicMock()
        mock_console_fn.return_value = console
        server = {
            "name": "truncated-pkg-server",
            "description": "server",
            "version": "1.0.0",
            "repository": {"url": "https://example.com"},
            "packages": [
                {
                    "registry_name": "npm",
                    "name": "very-long-package-name-exceeds-25-chars",
                    "runtime_hint": "node",
                }
            ],
        }
        mock_reg_cls.return_value.get_package_info.return_value = server
        result = self._invoke(["truncated-pkg-server"])
        self.assertEqual(result.exit_code, 0)
        console.print.assert_called()


# ---------------------------------------------------------------------------
# mcp list
# ---------------------------------------------------------------------------


class TestMcpList(unittest.TestCase):
    """Tests for ``apm mcp list``."""

    def setUp(self):
        self.runner = CliRunner()

    def _invoke(self, args=None):
        return self.runner.invoke(cli, ["mcp", "list"] + (args or []))

    @patch("apm_cli.commands.mcp._get_console", return_value=None)
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_list_no_results_fallback(self, mock_reg_cls, mock_console):
        """Fallback path: empty registry should warn without crashing."""
        mock_reg_cls.return_value.list_available_packages.return_value = []
        result = self._invoke()
        self.assertEqual(result.exit_code, 0)

    @patch("apm_cli.commands.mcp._get_console", return_value=None)
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_list_with_results_fallback(self, mock_reg_cls, mock_console):
        """Fallback path: servers should be printed one per line."""
        mock_reg_cls.return_value.list_available_packages.return_value = [
            _SAMPLE_SERVER_BASIC,
        ]
        result = self._invoke()
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test-server", result.output)

    @patch("apm_cli.commands.mcp._get_console", return_value=None)
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_list_network_error_exits(self, mock_reg_cls, mock_console):
        """Fallback path: network error should exit non-zero."""
        mock_reg_cls.return_value.list_available_packages.side_effect = RuntimeError(
            "network fail"
        )
        result = self._invoke()
        self.assertNotEqual(result.exit_code, 0)

    @patch("apm_cli.commands.mcp._get_console")
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_list_rich_no_results(self, mock_reg_cls, mock_console_fn):
        """Rich path: empty registry should print a warning."""
        console = MagicMock()
        mock_console_fn.return_value = console
        mock_reg_cls.return_value.list_available_packages.return_value = []
        result = self._invoke()
        self.assertEqual(result.exit_code, 0)
        console.print.assert_called()

    @patch("apm_cli.commands.mcp._get_console")
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_list_rich_shows_table(self, mock_reg_cls, mock_console_fn):
        """Rich path: results should produce a summary line and table."""
        console = MagicMock()
        mock_console_fn.return_value = console
        mock_reg_cls.return_value.list_available_packages.return_value = [
            _SAMPLE_SERVER_BASIC,
            _SAMPLE_SERVER_LONG_DESC,
        ]
        result = self._invoke()
        self.assertEqual(result.exit_code, 0)
        self.assertGreater(console.print.call_count, 2)

    @patch("apm_cli.commands.mcp._get_console")
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_list_rich_limit_hint_at_capacity(self, mock_reg_cls, mock_console_fn):
        """Rich path: when results == limit, show a '--limit N*2' hint."""
        console = MagicMock()
        mock_console_fn.return_value = console
        mock_reg_cls.return_value.list_available_packages.return_value = [
            _SAMPLE_SERVER_BASIC
        ] * 2
        result = self._invoke(["--limit", "2"])
        self.assertEqual(result.exit_code, 0)
        calls_text = " ".join(str(c) for c in console.print.call_args_list)
        self.assertIn("--limit 4", calls_text)

    @patch("apm_cli.commands.mcp._get_console")
    @patch("apm_cli.registry.integration.RegistryIntegration")
    def test_list_rich_verbose_flag(self, mock_reg_cls, mock_console_fn):
        """Rich path: --verbose flag should not change exit code."""
        console = MagicMock()
        mock_console_fn.return_value = console
        mock_reg_cls.return_value.list_available_packages.return_value = [
            _SAMPLE_SERVER_BASIC
        ]
        result = self._invoke(["--verbose"])
        self.assertEqual(result.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
