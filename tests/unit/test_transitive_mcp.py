"""Tests for transitive MCP dependency collection, deduplication, and inline installation."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import yaml

from apm_cli.models.apm_package import APMPackage
from apm_cli.cli import (
    _collect_transitive_mcp_deps,
    _deduplicate_mcp_deps,
    _install_inline_mcp_deps,
    _install_mcp_dependencies,
    _validate_inline_url,
)


# ---------------------------------------------------------------------------
# APMPackage – MCP dict parsing
# ---------------------------------------------------------------------------
class TestAPMPackageMCPParsing(unittest.TestCase):
    """Ensure apm_package preserves both string and dict MCP entries."""

    def test_parse_string_mcp_deps(self):
        """String-only MCP deps parse correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            yml = Path(tmp) / "apm.yml"
            yml.write_text(yaml.dump({
                "name": "pkg",
                "version": "1.0.0",
                "dependencies": {"mcp": ["ghcr.io/some/server"]},
            }))
            pkg = APMPackage.from_apm_yml(yml)
            deps = pkg.get_mcp_dependencies()

            self.assertEqual(deps, ["ghcr.io/some/server"])

    def test_parse_dict_mcp_deps(self):
        """Inline dict MCP deps are preserved."""
        inline = {"name": "my-srv", "type": "sse", "url": "https://example.com"}
        with tempfile.TemporaryDirectory() as tmp:
            yml = Path(tmp) / "apm.yml"
            yml.write_text(yaml.dump({
                "name": "pkg",
                "version": "1.0.0",
                "dependencies": {"mcp": [inline]},
            }))
            pkg = APMPackage.from_apm_yml(yml)
            deps = pkg.get_mcp_dependencies()

            self.assertEqual(len(deps), 1)
            self.assertIsInstance(deps[0], dict)
            self.assertEqual(deps[0]["name"], "my-srv")

    def test_parse_mixed_mcp_deps(self):
        """A mix of string and dict entries is preserved in order."""
        inline = {"name": "inline-srv", "type": "http", "url": "https://x"}
        with tempfile.TemporaryDirectory() as tmp:
            yml = Path(tmp) / "apm.yml"
            yml.write_text(yaml.dump({
                "name": "pkg",
                "version": "1.0.0",
                "dependencies": {"mcp": ["registry-srv", inline]},
            }))
            pkg = APMPackage.from_apm_yml(yml)
            deps = pkg.get_mcp_dependencies()

            self.assertEqual(len(deps), 2)
            self.assertIsInstance(deps[0], str)
            self.assertIsInstance(deps[1], dict)

    def test_no_mcp_section(self):
        """Missing MCP section returns empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            yml = Path(tmp) / "apm.yml"
            yml.write_text(yaml.dump({
                "name": "pkg",
                "version": "1.0.0",
            }))
            pkg = APMPackage.from_apm_yml(yml)
            self.assertEqual(pkg.get_mcp_dependencies(), [])

    def test_mcp_null_returns_empty(self):
        """mcp: null should return empty list, not raise TypeError."""
        with tempfile.TemporaryDirectory() as tmp:
            yml = Path(tmp) / "apm.yml"
            yml.write_text(yaml.dump({
                "name": "pkg",
                "version": "1.0.0",
                "dependencies": {"mcp": None},
            }))
            pkg = APMPackage.from_apm_yml(yml)
            self.assertEqual(pkg.get_mcp_dependencies(), [])

    def test_mcp_empty_list_returns_empty(self):
        """mcp: [] should return empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            yml = Path(tmp) / "apm.yml"
            yml.write_text(yaml.dump({
                "name": "pkg",
                "version": "1.0.0",
                "dependencies": {"mcp": []},
            }))
            pkg = APMPackage.from_apm_yml(yml)
            self.assertEqual(pkg.get_mcp_dependencies(), [])


# ---------------------------------------------------------------------------
# _collect_transitive_mcp_deps
# ---------------------------------------------------------------------------
class TestCollectTransitiveMCPDeps(unittest.TestCase):
    """Tests for scanning apm_modules/ for MCP deps."""

    def test_empty_when_dir_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _collect_transitive_mcp_deps(Path(tmp) / "nonexistent")
            self.assertEqual(result, [])

    def test_collects_string_deps(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "org" / "pkg-a"
            pkg_dir.mkdir(parents=True)
            (pkg_dir / "apm.yml").write_text(yaml.dump({
                "name": "pkg-a",
                "version": "1.0.0",
                "dependencies": {"mcp": ["ghcr.io/a/server"]},
            }))
            result = _collect_transitive_mcp_deps(Path(tmp))
            self.assertEqual(result, ["ghcr.io/a/server"])

    def test_collects_dict_deps(self):
        inline = {"name": "kb", "type": "sse", "url": "https://kb.example.com"}
        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "org" / "pkg-b"
            pkg_dir.mkdir(parents=True)
            (pkg_dir / "apm.yml").write_text(yaml.dump({
                "name": "pkg-b",
                "version": "1.0.0",
                "dependencies": {"mcp": [inline]},
            }))
            result = _collect_transitive_mcp_deps(Path(tmp))
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["name"], "kb")

    def test_collects_from_multiple_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i, dep in enumerate(["ghcr.io/a/s1", "ghcr.io/b/s2"]):
                d = Path(tmp) / "org" / f"pkg-{i}"
                d.mkdir(parents=True)
                (d / "apm.yml").write_text(yaml.dump({
                    "name": f"pkg-{i}",
                    "version": "1.0.0",
                    "dependencies": {"mcp": [dep]},
                }))
            result = _collect_transitive_mcp_deps(Path(tmp))
            self.assertEqual(len(result), 2)

    def test_skips_unparseable_apm_yml(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "org" / "bad-pkg"
            pkg_dir.mkdir(parents=True)
            (pkg_dir / "apm.yml").write_text("invalid: yaml: [")
            # Should not raise
            result = _collect_transitive_mcp_deps(Path(tmp))
            self.assertEqual(result, [])

    def test_lockfile_scopes_collection_to_locked_packages(self):
        """Lock-file filtering should only collect MCP deps from locked packages."""
        with tempfile.TemporaryDirectory() as tmp:
            apm_modules = Path(tmp) / "apm_modules"
            # Package that IS in the lock file
            locked_dir = apm_modules / "org" / "locked-pkg"
            locked_dir.mkdir(parents=True)
            (locked_dir / "apm.yml").write_text(yaml.dump({
                "name": "locked-pkg",
                "version": "1.0.0",
                "dependencies": {"mcp": ["ghcr.io/locked/server"]},
            }))
            # Package that is NOT in the lock file (orphan)
            orphan_dir = apm_modules / "org" / "orphan-pkg"
            orphan_dir.mkdir(parents=True)
            (orphan_dir / "apm.yml").write_text(yaml.dump({
                "name": "orphan-pkg",
                "version": "1.0.0",
                "dependencies": {"mcp": ["ghcr.io/orphan/server"]},
            }))
            # Write lock file referencing only the locked package
            lock_path = Path(tmp) / "apm.lock"
            lock_path.write_text(yaml.dump({
                "lockfile_version": "1",
                "dependencies": [
                    {"repo_url": "org/locked-pkg", "host": "github.com"},
                ],
            }))
            result = _collect_transitive_mcp_deps(apm_modules, lock_path)
            self.assertEqual(result, ["ghcr.io/locked/server"])

    def test_lockfile_with_virtual_path(self):
        """Lock-file filtering works for subdirectory (virtual_path) packages."""
        with tempfile.TemporaryDirectory() as tmp:
            apm_modules = Path(tmp) / "apm_modules"
            # Subdirectory package matching lock entry
            sub_dir = apm_modules / "org" / "monorepo" / "skills" / "azure"
            sub_dir.mkdir(parents=True)
            (sub_dir / "apm.yml").write_text(yaml.dump({
                "name": "azure-skill",
                "version": "1.0.0",
                "dependencies": {"mcp": [{"name": "learn", "type": "http", "url": "https://learn.example.com"}]},
            }))
            # Another subdirectory NOT in the lock
            other_dir = apm_modules / "org" / "monorepo" / "skills" / "other"
            other_dir.mkdir(parents=True)
            (other_dir / "apm.yml").write_text(yaml.dump({
                "name": "other-skill",
                "version": "1.0.0",
                "dependencies": {"mcp": ["ghcr.io/other/server"]},
            }))
            lock_path = Path(tmp) / "apm.lock"
            lock_path.write_text(yaml.dump({
                "lockfile_version": "1",
                "dependencies": [
                    {"repo_url": "org/monorepo", "host": "github.com", "virtual_path": "skills/azure"},
                ],
            }))
            result = _collect_transitive_mcp_deps(apm_modules, lock_path)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["name"], "learn")

    def test_lockfile_paths_do_not_use_full_rglob_scan(self):
        """When lock-derived paths are available, avoid full recursive scanning."""
        with tempfile.TemporaryDirectory() as tmp:
            apm_modules = Path(tmp) / "apm_modules"
            locked_dir = apm_modules / "org" / "locked-pkg"
            locked_dir.mkdir(parents=True)
            (locked_dir / "apm.yml").write_text(yaml.dump({
                "name": "locked-pkg",
                "version": "1.0.0",
                "dependencies": {"mcp": ["ghcr.io/locked/server"]},
            }))

            lock_path = Path(tmp) / "apm.lock"
            lock_path.write_text(yaml.dump({
                "lockfile_version": "1",
                "dependencies": [
                    {"repo_url": "org/locked-pkg", "host": "github.com"},
                ],
            }))

            with patch("pathlib.Path.rglob", side_effect=AssertionError("rglob should not be called")):
                result = _collect_transitive_mcp_deps(apm_modules, lock_path)

            self.assertEqual(result, ["ghcr.io/locked/server"])

    def test_invalid_lockfile_falls_back_to_rglob_scan(self):
        """If lock parsing fails, function falls back to scanning all apm.yml files."""
        with tempfile.TemporaryDirectory() as tmp:
            apm_modules = Path(tmp) / "apm_modules"
            pkg_dir = apm_modules / "org" / "pkg-a"
            pkg_dir.mkdir(parents=True)
            (pkg_dir / "apm.yml").write_text(yaml.dump({
                "name": "pkg-a",
                "version": "1.0.0",
                "dependencies": {"mcp": ["ghcr.io/a/server"]},
            }))

            lock_path = Path(tmp) / "apm.lock"
            lock_path.write_text("dependencies: [")

            result = _collect_transitive_mcp_deps(apm_modules, lock_path)
            self.assertEqual(result, ["ghcr.io/a/server"])


# ---------------------------------------------------------------------------
# _deduplicate_mcp_deps
# ---------------------------------------------------------------------------
class TestDeduplicateMCPDeps(unittest.TestCase):

    def test_deduplicates_strings(self):
        deps = ["a", "b", "a", "c", "b"]
        self.assertEqual(_deduplicate_mcp_deps(deps), ["a", "b", "c"])

    def test_deduplicates_dicts_by_name(self):
        d1 = {"name": "srv", "type": "sse", "url": "https://one"}
        d2 = {"name": "srv", "type": "sse", "url": "https://two"}  # same name
        d3 = {"name": "other", "type": "sse", "url": "https://three"}
        result = _deduplicate_mcp_deps([d1, d2, d3])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["url"], "https://one")  # first wins

    def test_mixed_dedup(self):
        inline = {"name": "kb", "type": "sse", "url": "https://kb"}
        deps = ["a", inline, "a", {"name": "kb", "type": "sse", "url": "https://kb2"}]
        result = _deduplicate_mcp_deps(deps)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], str)
        self.assertIsInstance(result[1], dict)

    def test_empty_list(self):
        self.assertEqual(_deduplicate_mcp_deps([]), [])

    def test_dict_without_name_kept(self):
        """Dicts without 'name' are kept if not already in result."""
        d = {"type": "sse", "url": "https://x"}
        result = _deduplicate_mcp_deps([d, d])
        self.assertEqual(len(result), 1)

    def test_root_deps_take_precedence_over_transitive(self):
        """When root and transitive share a key, the first (root) wins."""
        root = [{"name": "shared", "type": "sse", "url": "https://root-url"}]
        transitive = [{"name": "shared", "type": "sse", "url": "https://transitive-url"}]
        # Root deps come first in the combined list
        combined = root + transitive
        result = _deduplicate_mcp_deps(combined)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["url"], "https://root-url")


# ---------------------------------------------------------------------------
# _validate_inline_url
# ---------------------------------------------------------------------------
class TestValidateInlineUrl(unittest.TestCase):

    def test_allows_https(self):
        self.assertTrue(_validate_inline_url("https://example.com/mcp", "srv"))

    def test_allows_http(self):
        self.assertTrue(_validate_inline_url("http://localhost:8080", "srv"))

    @patch("apm_cli.cli._rich_warning")
    def test_rejects_file_scheme(self, mock_warn):
        self.assertFalse(_validate_inline_url("file:///etc/passwd", "bad"))
        mock_warn.assert_called_once()
        self.assertIn("disallowed URL scheme", mock_warn.call_args[0][0])

    @patch("apm_cli.cli._rich_warning")
    def test_rejects_data_scheme(self, mock_warn):
        self.assertFalse(_validate_inline_url("data:text/html,<h1>hi</h1>", "bad"))

    @patch("apm_cli.cli._rich_warning")
    def test_rejects_empty_scheme(self, mock_warn):
        self.assertFalse(_validate_inline_url("no-scheme-url", "bad"))


# ---------------------------------------------------------------------------
# _install_inline_mcp_deps
# ---------------------------------------------------------------------------
class TestInstallInlineMCPDeps(unittest.TestCase):

    @patch("apm_cli.cli._get_console", return_value=None)
    @patch("apm_cli.factory.ClientFactory")
    def test_delegates_to_vscode_adapter(self, mock_factory, _console):
        mock_adapter = MagicMock()
        mock_adapter.get_current_config.return_value = {"servers": {}}
        mock_factory.create_client.return_value = mock_adapter

        deps = [{"name": "s1", "type": "sse", "url": "https://s1.example.com"}]
        count = _install_inline_mcp_deps(deps, ["vscode"])

        self.assertEqual(count, 1)
        mock_factory.create_client.assert_called_with("vscode")
        # VSCode path: read-merge-write with full config
        mock_adapter.get_current_config.assert_called_once()
        call_config = mock_adapter.update_config.call_args[0][0]
        self.assertIn("s1", call_config["servers"])
        self.assertEqual(call_config["servers"]["s1"]["url"], "https://s1.example.com")

    @patch("apm_cli.cli._get_console", return_value=None)
    @patch("apm_cli.factory.ClientFactory")
    def test_delegates_to_copilot_adapter(self, mock_factory, _console):
        mock_adapter = MagicMock()
        mock_factory.create_client.return_value = mock_adapter

        deps = [{"name": "s1", "type": "sse", "url": "https://s1.example.com"}]
        count = _install_inline_mcp_deps(deps, ["copilot"])

        self.assertEqual(count, 1)
        mock_factory.create_client.assert_called_with("copilot")
        # Copilot path: merge dict passed directly
        call_config = mock_adapter.update_config.call_args[0][0]
        self.assertIn("s1", call_config)

    @patch("apm_cli.cli._get_console", return_value=None)
    @patch("apm_cli.factory.ClientFactory")
    def test_codex_uses_own_adapter_not_copilot(self, mock_factory, _console):
        mock_adapter = MagicMock()
        mock_factory.create_client.return_value = mock_adapter

        deps = [{"name": "s1", "type": "sse", "url": "https://s1.example.com"}]
        count = _install_inline_mcp_deps(deps, ["codex"])

        self.assertEqual(count, 1)
        mock_factory.create_client.assert_called_with("codex")
        # Codex path: merge dict (adapter writes TOML internally)
        call_config = mock_adapter.update_config.call_args[0][0]
        self.assertIn("s1", call_config)

    @patch("apm_cli.cli._get_console", return_value=None)
    @patch("apm_cli.factory.ClientFactory")
    def test_installs_for_multiple_runtimes(self, mock_factory, _console):
        mock_adapter = MagicMock()
        mock_adapter.get_current_config.return_value = {"servers": {}}
        mock_factory.create_client.return_value = mock_adapter

        deps = [{"name": "s1", "type": "sse", "url": "https://s1.example.com"}]
        count = _install_inline_mcp_deps(deps, ["vscode", "copilot", "codex"])

        self.assertEqual(count, 1)
        self.assertEqual(mock_factory.create_client.call_count, 3)

    @patch("apm_cli.cli._rich_warning")
    @patch("apm_cli.cli._get_console", return_value=None)
    def test_skips_dep_without_name(self, _console, mock_warn):
        deps = [{"type": "sse", "url": "https://no-name"}]
        count = _install_inline_mcp_deps(deps, ["vscode"])
        self.assertEqual(count, 0)
        self.assertIn("safe fields", mock_warn.call_args[0][0])
        self.assertNotIn("https://no-name", mock_warn.call_args[0][0])

    @patch("apm_cli.cli._rich_warning")
    @patch("apm_cli.cli._get_console", return_value=None)
    def test_skips_dep_with_disallowed_scheme(self, _console, mock_warn):
        deps = [{"name": "bad", "type": "sse", "url": "file:///etc/passwd"}]
        count = _install_inline_mcp_deps(deps, ["vscode"])
        self.assertEqual(count, 0)
        self.assertIn("disallowed URL scheme", mock_warn.call_args[0][0])

    @patch("apm_cli.cli._get_console", return_value=None)
    @patch("apm_cli.factory.ClientFactory")
    def test_includes_headers_in_server_config(self, mock_factory, _console):
        mock_adapter = MagicMock()
        mock_adapter.get_current_config.return_value = {"servers": {}}
        mock_factory.create_client.return_value = mock_adapter

        deps = [{"name": "s1", "type": "sse", "url": "https://s1", "headers": {"Authorization": "Bearer x"}}]
        _install_inline_mcp_deps(deps, ["vscode"])

        call_config = mock_adapter.update_config.call_args[0][0]
        self.assertIn("headers", call_config["servers"]["s1"])

    @patch("apm_cli.cli._get_console", return_value=None)
    @patch("apm_cli.factory.ClientFactory")
    def test_continues_on_adapter_failure(self, mock_factory, _console):
        mock_adapter = MagicMock()
        mock_adapter.get_current_config.side_effect = Exception("write failed")
        mock_factory.create_client.return_value = mock_adapter

        deps = [
            {"name": "fail", "type": "sse", "url": "https://fail"},
            {"name": "also-fail", "type": "sse", "url": "https://also"},
        ]
        count = _install_inline_mcp_deps(deps, ["vscode"])
        self.assertEqual(count, 0)

    @patch("apm_cli.cli._rich_warning")
    @patch("apm_cli.cli._get_console", return_value=None)
    def test_missing_fields_warning_does_not_expose_headers(self, _console, mock_warn):
        deps = [{"type": "sse", "headers": {"Authorization": "Bearer secret"}}]
        _install_inline_mcp_deps(deps, ["vscode"])
        warning_msg = mock_warn.call_args[0][0]
        self.assertNotIn("secret", warning_msg)
        self.assertNotIn("Authorization", warning_msg)


# ---------------------------------------------------------------------------
# _install_mcp_dependencies
# ---------------------------------------------------------------------------
class TestInstallMCPDependencies(unittest.TestCase):

    @patch("apm_cli.cli._get_console", return_value=None)
    @patch("apm_cli.registry.operations.MCPServerOperations")
    def test_already_configured_registry_servers_not_counted_as_new(
        self, mock_ops_cls, _console
    ):
        mock_ops = mock_ops_cls.return_value
        mock_ops.validate_servers_exist.return_value = (["ghcr.io/org/server"], [])
        mock_ops.check_servers_needing_installation.return_value = []

        count = _install_mcp_dependencies(["ghcr.io/org/server"], runtime="vscode")

        self.assertEqual(count, 0)

    @patch("apm_cli.cli._install_for_runtime")
    @patch("apm_cli.cli._get_console", return_value=None)
    @patch("apm_cli.registry.operations.MCPServerOperations")
    def test_counts_only_newly_configured_registry_servers(
        self, mock_ops_cls, _console, mock_install_runtime
    ):
        mock_ops = mock_ops_cls.return_value
        mock_ops.validate_servers_exist.return_value = (
            ["ghcr.io/org/already", "ghcr.io/org/new"],
            [],
        )
        mock_ops.check_servers_needing_installation.return_value = ["ghcr.io/org/new"]
        mock_ops.batch_fetch_server_info.return_value = {"ghcr.io/org/new": {}}
        mock_ops.collect_environment_variables.return_value = {}
        mock_ops.collect_runtime_variables.return_value = {}

        count = _install_mcp_dependencies(
            ["ghcr.io/org/already", "ghcr.io/org/new"], runtime="vscode"
        )

        self.assertEqual(count, 1)
        mock_install_runtime.assert_called_once()

    @patch("apm_cli.cli._install_for_runtime")
    @patch("apm_cli.registry.operations.MCPServerOperations")
    def test_mixed_registry_servers_show_already_configured_and_count_only_new(
        self, mock_ops_cls, mock_install_runtime
    ):
        mock_console = unittest.mock.MagicMock()
        mock_ops = mock_ops_cls.return_value
        mock_ops.validate_servers_exist.return_value = (
            ["ghcr.io/org/already", "ghcr.io/org/new"],
            [],
        )
        mock_ops.check_servers_needing_installation.return_value = ["ghcr.io/org/new"]
        mock_ops.batch_fetch_server_info.return_value = {"ghcr.io/org/new": {}}
        mock_ops.collect_environment_variables.return_value = {}
        mock_ops.collect_runtime_variables.return_value = {}

        with patch("apm_cli.cli._get_console", return_value=mock_console):
            count = _install_mcp_dependencies(
                ["ghcr.io/org/already", "ghcr.io/org/new"], runtime="vscode"
            )

        self.assertEqual(count, 1)
        mock_install_runtime.assert_called_once()
        printed_lines = "\n".join(
            str(call.args[0]) for call in mock_console.print.call_args_list if call.args
        )
        self.assertIn("ghcr.io/org/already", printed_lines)
        self.assertIn("already configured", printed_lines)


if __name__ == "__main__":
    unittest.main()
