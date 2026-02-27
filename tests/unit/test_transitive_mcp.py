"""Tests for transitive MCP dependency collection, deduplication, and inline installation."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from apm_cli.models.apm_package import APMPackage
from apm_cli.cli import (
    _collect_transitive_mcp_deps,
    _deduplicate_mcp_deps,
    _install_inline_mcp_deps,
    _write_inline_mcp_vscode,
    _write_inline_mcp_copilot,
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


# ---------------------------------------------------------------------------
# _write_inline_mcp_vscode
# ---------------------------------------------------------------------------
class TestWriteInlineMCPVscode(unittest.TestCase):

    def test_creates_file_from_scratch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("apm_cli.cli.Path.cwd", return_value=Path(tmp)):
                _write_inline_mcp_vscode("test-srv", {"type": "sse", "url": "https://x"})

            mcp_path = Path(tmp) / ".vscode" / "mcp.json"
            self.assertTrue(mcp_path.exists())
            data = json.loads(mcp_path.read_text())
            self.assertIn("test-srv", data["servers"])
            self.assertEqual(data["servers"]["test-srv"]["url"], "https://x")

    def test_merges_into_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            vscode_dir = Path(tmp) / ".vscode"
            vscode_dir.mkdir()
            mcp_path = vscode_dir / "mcp.json"
            mcp_path.write_text(json.dumps({"servers": {"existing": {"type": "stdio"}}}))

            with patch("apm_cli.cli.Path.cwd", return_value=Path(tmp)):
                _write_inline_mcp_vscode("new-srv", {"type": "sse", "url": "https://new"})

            data = json.loads(mcp_path.read_text())
            self.assertIn("existing", data["servers"])
            self.assertIn("new-srv", data["servers"])

    def test_overwrites_same_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            vscode_dir = Path(tmp) / ".vscode"
            vscode_dir.mkdir()
            mcp_path = vscode_dir / "mcp.json"
            mcp_path.write_text(json.dumps({"servers": {"srv": {"type": "sse", "url": "https://old"}}}))

            with patch("apm_cli.cli.Path.cwd", return_value=Path(tmp)):
                _write_inline_mcp_vscode("srv", {"type": "sse", "url": "https://new"})

            data = json.loads(mcp_path.read_text())
            self.assertEqual(data["servers"]["srv"]["url"], "https://new")


# ---------------------------------------------------------------------------
# _write_inline_mcp_copilot
# ---------------------------------------------------------------------------
class TestWriteInlineMCPCopilot(unittest.TestCase):

    def test_creates_file_from_scratch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("apm_cli.cli.Path.home", return_value=Path(tmp)):
                _write_inline_mcp_copilot("cp-srv", {"type": "sse", "url": "https://cp"})

            config_path = Path(tmp) / ".copilot" / "mcp-config.json"
            self.assertTrue(config_path.exists())
            data = json.loads(config_path.read_text())
            self.assertIn("cp-srv", data["mcpServers"])

    def test_merges_into_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            copilot_dir = Path(tmp) / ".copilot"
            copilot_dir.mkdir()
            config_path = copilot_dir / "mcp-config.json"
            config_path.write_text(json.dumps({"mcpServers": {"old": {"type": "stdio"}}}))

            with patch("apm_cli.cli.Path.home", return_value=Path(tmp)):
                _write_inline_mcp_copilot("new", {"type": "sse", "url": "https://new"})

            data = json.loads(config_path.read_text())
            self.assertIn("old", data["mcpServers"])
            self.assertIn("new", data["mcpServers"])


# ---------------------------------------------------------------------------
# _install_inline_mcp_deps
# ---------------------------------------------------------------------------
class TestInstallInlineMCPDeps(unittest.TestCase):

    @patch("apm_cli.cli._write_inline_mcp_vscode")
    @patch("apm_cli.cli._write_inline_mcp_copilot")
    @patch("apm_cli.cli._get_console", return_value=None)
    def test_installs_for_all_runtimes(self, _console, mock_copilot, mock_vscode):
        deps = [{"name": "s1", "type": "sse", "url": "https://s1"}]
        count = _install_inline_mcp_deps(deps, ["vscode", "copilot"])

        self.assertEqual(count, 1)
        mock_vscode.assert_called_once()
        mock_copilot.assert_called_once()

    @patch("apm_cli.cli._write_inline_mcp_vscode")
    @patch("apm_cli.cli._write_inline_mcp_copilot")
    @patch("apm_cli.cli._get_console", return_value=None)
    def test_skips_dep_without_name(self, _console, mock_copilot, mock_vscode):
        deps = [{"type": "sse", "url": "https://no-name"}]
        count = _install_inline_mcp_deps(deps, ["vscode"])

        self.assertEqual(count, 0)
        mock_vscode.assert_not_called()

    @patch("apm_cli.cli._write_inline_mcp_vscode")
    @patch("apm_cli.cli._write_inline_mcp_copilot")
    @patch("apm_cli.cli._get_console", return_value=None)
    def test_skips_dep_without_url(self, _console, mock_copilot, mock_vscode):
        deps = [{"name": "srv"}]
        count = _install_inline_mcp_deps(deps, ["vscode"])

        self.assertEqual(count, 0)
        mock_vscode.assert_not_called()

    @patch("apm_cli.cli._write_inline_mcp_vscode")
    @patch("apm_cli.cli._get_console", return_value=None)
    def test_includes_headers_when_present(self, _console, mock_vscode):
        deps = [{"name": "s", "type": "sse", "url": "https://s", "headers": {"Authorization": "Bearer x"}}]
        _install_inline_mcp_deps(deps, ["vscode"])

        call_args = mock_vscode.call_args
        server_config = call_args[0][1]
        self.assertIn("headers", server_config)
        self.assertEqual(server_config["headers"]["Authorization"], "Bearer x")

    @patch("apm_cli.cli._write_inline_mcp_vscode", side_effect=Exception("write failed"))
    @patch("apm_cli.cli._get_console", return_value=None)
    def test_continues_on_write_failure(self, _console, mock_vscode):
        """Failure writing one dep should not prevent the next from being attempted."""
        deps = [
            {"name": "fail", "type": "sse", "url": "https://fail"},
            {"name": "ok", "type": "sse", "url": "https://ok"},
        ]
        # Both raise, so no deps are successfully configured
        count = _install_inline_mcp_deps(deps, ["vscode"])
        self.assertEqual(count, 0)
        # But both were attempted
        self.assertEqual(mock_vscode.call_count, 2)

    @patch("apm_cli.cli._write_inline_mcp_copilot")
    @patch("apm_cli.cli._get_console", return_value=None)
    def test_codex_runtime_uses_copilot_writer(self, _console, mock_copilot):
        deps = [{"name": "s", "type": "sse", "url": "https://s"}]
        _install_inline_mcp_deps(deps, ["codex"])

        mock_copilot.assert_called_once()


if __name__ == "__main__":
    unittest.main()
