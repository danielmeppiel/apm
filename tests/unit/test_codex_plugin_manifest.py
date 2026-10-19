"""Tests for .codex-plugin/plugin.json recognition (issue #2992).

A marketplace plugin whose only manifest sits at .codex-plugin/plugin.json
must be recognised as a plugin (not reduced to skill_bundle) and its
mcpServers must be extracted through the normal marketplace_plugin path.
"""

import json
from pathlib import Path

import pytest

from apm_cli.deps.plugin_parser import (
    _extract_mcp_servers,
    parse_plugin_manifest,
)
from apm_cli.models.format_detection import (
    ClaudePluginDetector,
    DetectionReport,
    NormalizationPlanner,
    PackageFormatRegistry,
)
from apm_cli.utils.helpers import find_plugin_json


# ── find_plugin_json ─────────────────────────────────────────────────


class TestFindPluginJsonCodex:
    """Verifying that .codex-plugin/plugin.json is discovered."""

    def test_codex_plugin_json_is_found(self, tmp_path: Path) -> None:
        """A plugin.json under .codex-plugin/ is returned by find_plugin_json."""
        codex_dir = tmp_path / ".codex-plugin"
        codex_dir.mkdir()
        pj = codex_dir / "plugin.json"
        pj.write_text(json.dumps({"name": "codex-plugin"}))

        result = find_plugin_json(tmp_path)
        assert result == pj

    def test_codex_plugin_json_priority_below_root(self, tmp_path: Path) -> None:
        """Root plugin.json still wins over .codex-plugin/plugin.json."""
        root_pj = tmp_path / "plugin.json"
        root_pj.write_text(json.dumps({"name": "root"}))

        codex_dir = tmp_path / ".codex-plugin"
        codex_dir.mkdir()
        (codex_dir / "plugin.json").write_text(json.dumps({"name": "codex"}))

        result = find_plugin_json(tmp_path)
        assert result == root_pj

    def test_codex_plugin_json_priority_below_claude(self, tmp_path: Path) -> None:
        """.claude-plugin/plugin.json wins over .codex-plugin/plugin.json."""
        claude_dir = tmp_path / ".claude-plugin"
        claude_dir.mkdir()
        (claude_dir / "plugin.json").write_text(json.dumps({"name": "claude"}))

        codex_dir = tmp_path / ".codex-plugin"
        codex_dir.mkdir()
        (codex_dir / "plugin.json").write_text(json.dumps({"name": "codex"}))

        result = find_plugin_json(tmp_path)
        assert result == claude_dir / "plugin.json"

    def test_codex_plugin_json_found_when_only_option(self, tmp_path: Path) -> None:
        """When only .codex-plugin/ has plugin.json, it is found."""
        codex_dir = tmp_path / ".codex-plugin"
        codex_dir.mkdir()
        pj = codex_dir / "plugin.json"
        pj.write_text(json.dumps({"name": "codex-only"}))

        result = find_plugin_json(tmp_path)
        assert result == pj


# ── Format detection ─────────────────────────────────────────────────


class TestCodexPluginFormatDetection:
    """Verifying that a Codex-only manifest yields MARKETPLACE_PLUGIN."""

    def _make_codex_plugin(self, tmp_path: Path, mcp_config: dict | None = None) -> Path:
        """Create a minimal plugin at .codex-plugin/plugin.json."""
        codex_dir = tmp_path / ".codex-plugin"
        codex_dir.mkdir()
        manifest = {"name": "codex-test", "skills": "./skills"}
        if mcp_config:
            manifest["mcpServers"] = mcp_config
        (codex_dir / "plugin.json").write_text(json.dumps(manifest))
        return tmp_path

    def test_codex_manifest_yields_claude_plugin_evidence(self, tmp_path: Path) -> None:
        """ClaudePluginDetector recognises .codex-plugin/plugin.json."""
        pkg = self._make_codex_plugin(tmp_path)
        detector = ClaudePluginDetector()
        evidence = detector.detect(pkg)
        assert evidence is not None
        assert evidence.plugin_json_path == pkg / ".codex-plugin" / "plugin.json"

    def test_codex_manifest_classifies_as_marketplace_plugin(self, tmp_path: Path) -> None:
        """A Codex-only plugin is MARKETPLACE_PLUGIN, not SKILL_BUNDLE."""
        pkg = self._make_codex_plugin(tmp_path)
        registry = PackageFormatRegistry()
        report = registry.detect(pkg)
        planner = NormalizationPlanner()
        package_type, _ = planner.plan(report)
        from apm_cli.models.validation import PackageType

        assert package_type == PackageType.MARKETPLACE_PLUGIN

    def test_codex_manifest_no_skill_md_still_marketplace(self, tmp_path: Path) -> None:
        """Even without skills/, Codex manifest → MARKETPLACE_PLUGIN."""
        pkg = self._make_codex_plugin(tmp_path)
        # Ensure no SKILL.md exists anywhere
        assert not (pkg / "SKILL.md").exists()
        assert not (pkg / "skills").exists()

        registry = PackageFormatRegistry()
        report = registry.detect(pkg)
        planner = NormalizationPlanner()
        package_type, _ = planner.plan(report)
        from apm_cli.models.validation import PackageType

        assert package_type == PackageType.MARKETPLACE_PLUGIN


# ── MCP server extraction ────────────────────────────────────────────


class TestCodexMcpExtraction:
    """Verifying that MCP servers in .codex-plugin/plugin.json are extracted."""

    def _make_codex_plugin_with_mcp(
        self, tmp_path: Path, mcp_content: dict
    ) -> tuple[Path, dict]:
        """Create plugin with .mcp.codex.json and plugin.json pointing to it."""
        codex_dir = tmp_path / ".codex-plugin"
        codex_dir.mkdir()
        mcp_file = tmp_path / ".mcp.codex.json"
        mcp_file.write_text(json.dumps(mcp_content))
        manifest = {
            "name": "codex-mcp-test",
            "mcpServers": "./.mcp.codex.json",
        }
        (codex_dir / "plugin.json").write_text(json.dumps(manifest))
        return tmp_path, manifest

    def test_codex_mcp_servers_extracted(self, tmp_path: Path) -> None:
        """MCP servers referenced from .codex-plugin/plugin.json are parsed."""
        pkg, manifest = self._make_codex_plugin_with_mcp(
            tmp_path,
            {"mcpServers": {"example": {"command": "npx", "args": ["-y", "example-mcp"]}}},
        )
        servers = _extract_mcp_servers(pkg, manifest, substitute_plugin_root=False)
        assert "example" in servers
        assert servers["example"]["command"] == "npx"
        assert servers["example"]["args"] == ["-y", "example-mcp"]

    def test_codex_inline_mcp_servers_extracted(self, tmp_path: Path) -> None:
        """Inline mcpServers dict in .codex-plugin/plugin.json is parsed."""
        codex_dir = tmp_path / ".codex-plugin"
        codex_dir.mkdir()
        manifest = {
            "name": "codex-inline-mcp",
            "mcpServers": {
                "inline-server": {"command": "echo", "args": ["hello"]}
            },
        }
        (codex_dir / "plugin.json").write_text(json.dumps(manifest))
        servers = _extract_mcp_servers(tmp_path, manifest, substitute_plugin_root=False)
        assert "inline-server" in servers
