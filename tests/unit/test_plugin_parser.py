"""Unit tests for plugin_parser.py and find_plugin_json helper."""

import json
import os
from pathlib import Path

import pytest
import yaml

from apm_cli.deps.plugin_parser import (
    _generate_apm_yml,
    _map_plugin_artifacts,
    normalize_plugin_directory,
    parse_plugin_manifest,
    synthesize_apm_yml_from_plugin,
    validate_plugin_package,
)
from apm_cli.utils.helpers import find_plugin_json


class TestFindPluginJson:
    def test_find_plugin_json_root(self, tmp_path):
        pj = tmp_path / "plugin.json"
        pj.write_text('{"name": "root-plugin"}')

        result = find_plugin_json(tmp_path)
        assert result == pj

    def test_find_plugin_json_github_format(self, tmp_path):
        gh_dir = tmp_path / ".github" / "plugin"
        gh_dir.mkdir(parents=True)
        pj = gh_dir / "plugin.json"
        pj.write_text('{"name": "gh-plugin"}')

        result = find_plugin_json(tmp_path)
        assert result == pj

    def test_find_plugin_json_claude_format(self, tmp_path):
        claude_dir = tmp_path / ".claude-plugin"
        claude_dir.mkdir()
        pj = claude_dir / "plugin.json"
        pj.write_text('{"name": "claude-plugin"}')

        result = find_plugin_json(tmp_path)
        assert result == pj

    def test_find_plugin_json_priority_root_wins(self, tmp_path):
        root_pj = tmp_path / "plugin.json"
        root_pj.write_text('{"name": "root"}')

        gh_dir = tmp_path / ".github" / "plugin"
        gh_dir.mkdir(parents=True)
        (gh_dir / "plugin.json").write_text('{"name": "gh"}')

        result = find_plugin_json(tmp_path)
        assert result == root_pj

    def test_find_plugin_json_not_found(self, tmp_path):
        result = find_plugin_json(tmp_path)
        assert result is None

    def test_find_plugin_json_ignores_deep_nested(self, tmp_path):
        deep = tmp_path / "node_modules" / "some-pkg"
        deep.mkdir(parents=True)
        (deep / "plugin.json").write_text('{"name": "deep"}')

        result = find_plugin_json(tmp_path)
        assert result is None


class TestParsePluginManifest:
    def test_parse_valid_manifest(self, tmp_path):
        pj = tmp_path / "plugin.json"
        manifest = {
            "name": "test-plugin",
            "version": "1.2.3",
            "description": "A test plugin",
            "author": {"name": "Alice", "email": "a@b.c"},
            "license": "MIT",
            "tags": ["test", "demo"],
            "dependencies": {"dep-a": "^1.0.0"},
        }
        pj.write_text(json.dumps(manifest))

        result = parse_plugin_manifest(pj)
        assert result["name"] == "test-plugin"
        assert result["version"] == "1.2.3"
        assert result["author"]["name"] == "Alice"
        assert result["tags"] == ["test", "demo"]

    def test_parse_minimal_manifest(self, tmp_path):
        pj = tmp_path / "plugin.json"
        pj.write_text('{"name": "minimal"}')

        result = parse_plugin_manifest(pj)
        assert result == {"name": "minimal"}

    def test_parse_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_plugin_manifest(tmp_path / "nonexistent.json")

    def test_parse_invalid_json(self, tmp_path):
        pj = tmp_path / "plugin.json"
        pj.write_text("{ not valid json }")

        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_plugin_manifest(pj)


class TestMapPluginArtifacts:
    def test_map_agents_directory(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        agents = plugin_dir / "agents"
        agents.mkdir()
        (agents / "helper.agent.md").write_text("# Helper")

        apm_dir = plugin_dir / ".apm"
        apm_dir.mkdir()
        _map_plugin_artifacts(plugin_dir, apm_dir)

        assert (apm_dir / "agents" / "helper.agent.md").exists()
        assert (apm_dir / "agents" / "helper.agent.md").read_text() == "# Helper"

    def test_map_skills_directory(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        skills = plugin_dir / "skills"
        skills.mkdir()
        skill_dir = skills / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Skill")

        apm_dir = plugin_dir / ".apm"
        apm_dir.mkdir()
        _map_plugin_artifacts(plugin_dir, apm_dir)

        assert (apm_dir / "skills" / "my-skill" / "SKILL.md").exists()

    def test_map_commands_to_prompts(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        commands = plugin_dir / "commands"
        commands.mkdir()
        (commands / "run.md").write_text("# Run")
        (commands / "already.prompt.md").write_text("# Already")

        apm_dir = plugin_dir / ".apm"
        apm_dir.mkdir()
        _map_plugin_artifacts(plugin_dir, apm_dir)

        prompts = apm_dir / "prompts"
        assert prompts.exists()
        # .md → .prompt.md rename
        assert (prompts / "run.prompt.md").exists()
        assert (prompts / "run.prompt.md").read_text() == "# Run"
        # Already .prompt.md stays unchanged
        assert (prompts / "already.prompt.md").exists()

    def test_map_hooks_directory(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        hooks = plugin_dir / "hooks"
        hooks.mkdir()
        (hooks / "pre-install.sh").write_text("#!/bin/sh\necho hi")

        apm_dir = plugin_dir / ".apm"
        apm_dir.mkdir()
        _map_plugin_artifacts(plugin_dir, apm_dir)

        assert (apm_dir / "hooks" / "pre-install.sh").exists()

    def test_map_mcp_json_passthrough(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        mcp_data = {"mcpServers": {"s": {"command": "node"}}}
        (plugin_dir / ".mcp.json").write_text(json.dumps(mcp_data))

        apm_dir = plugin_dir / ".apm"
        apm_dir.mkdir()
        _map_plugin_artifacts(plugin_dir, apm_dir)

        target = apm_dir / ".mcp.json"
        assert target.exists()
        assert json.loads(target.read_text()) == mcp_data

    def test_no_symlink_follow(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        agents = plugin_dir / "agents"
        agents.mkdir()
        (agents / "real.md").write_text("# Real")

        # Create a symlink inside agents/
        external = tmp_path / "external"
        external.mkdir()
        (external / "secret.md").write_text("# Secret")
        symlink_target = agents / "linked"
        try:
            symlink_target.symlink_to(external)
        except OSError:
            pytest.skip("Symlinks not supported on this platform")

        apm_dir = plugin_dir / ".apm"
        apm_dir.mkdir()
        _map_plugin_artifacts(plugin_dir, apm_dir)

        # Real file is copied
        assert (apm_dir / "agents" / "real.md").exists()
        # _ignore_symlinks callback causes copytree to skip symlinks entirely
        copied_linked = apm_dir / "agents" / "linked"
        assert not copied_linked.exists(), "Symlinked directory should be skipped entirely by _ignore_symlinks"

    # ---- Custom component paths from plugin.json ----

    def test_custom_agents_path_string(self, tmp_path):
        """Manifest agents field as a string redirects agent discovery."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        custom = plugin_dir / "src" / "my-agents"
        custom.mkdir(parents=True)
        (custom / "bot.agent.md").write_text("# Bot")

        apm_dir = plugin_dir / ".apm"
        apm_dir.mkdir()
        _map_plugin_artifacts(plugin_dir, apm_dir, manifest={"agents": "src/my-agents"})

        assert (apm_dir / "agents" / "bot.agent.md").exists()

    def test_custom_skills_path_array(self, tmp_path):
        """Manifest skills field as an array merges multiple directories."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        s1 = plugin_dir / "skills"
        s1.mkdir()
        (s1 / "a.md").write_text("# A")
        s2 = plugin_dir / "extra-skills"
        s2.mkdir()
        (s2 / "b.md").write_text("# B")

        apm_dir = plugin_dir / ".apm"
        apm_dir.mkdir()
        _map_plugin_artifacts(
            plugin_dir, apm_dir,
            manifest={"skills": ["skills/", "extra-skills/"]},
        )

        assert (apm_dir / "skills" / "a.md").exists()
        assert (apm_dir / "skills" / "b.md").exists()

    def test_custom_commands_path(self, tmp_path):
        """Manifest commands field redirects command discovery."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        cmds = plugin_dir / "my-cmds"
        cmds.mkdir()
        (cmds / "deploy.md").write_text("# Deploy")

        apm_dir = plugin_dir / ".apm"
        apm_dir.mkdir()
        _map_plugin_artifacts(plugin_dir, apm_dir, manifest={"commands": "my-cmds"})

        assert (apm_dir / "prompts" / "deploy.prompt.md").exists()

    def test_hooks_file_path(self, tmp_path):
        """Manifest hooks as a file path copies it to .apm/hooks/hooks.json."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        hooks_data = {"hooks": {"PreToolUse": [{"matcher": "bash", "hooks": [{"type": "command", "command": "echo ok"}]}]}}
        (plugin_dir / "my-hooks.json").write_text(json.dumps(hooks_data))

        apm_dir = plugin_dir / ".apm"
        apm_dir.mkdir()
        _map_plugin_artifacts(plugin_dir, apm_dir, manifest={"hooks": "my-hooks.json"})

        target = apm_dir / "hooks" / "hooks.json"
        assert target.exists()
        assert json.loads(target.read_text()) == hooks_data

    def test_hooks_inline_object(self, tmp_path):
        """Manifest hooks as an inline object writes .apm/hooks/hooks.json."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        hooks_obj = {"hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "echo done"}]}]}}

        apm_dir = plugin_dir / ".apm"
        apm_dir.mkdir()
        _map_plugin_artifacts(plugin_dir, apm_dir, manifest={"hooks": hooks_obj})

        target = apm_dir / "hooks" / "hooks.json"
        assert target.exists()
        assert json.loads(target.read_text()) == hooks_obj

    def test_hooks_directory_path(self, tmp_path):
        """Manifest hooks as a custom directory path copies the directory."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        custom_hooks = plugin_dir / "my-hooks"
        custom_hooks.mkdir()
        (custom_hooks / "hooks.json").write_text('{"hooks": {}}')
        scripts = custom_hooks / "scripts"
        scripts.mkdir()
        (scripts / "lint.sh").write_text("#!/bin/sh\necho lint")

        apm_dir = plugin_dir / ".apm"
        apm_dir.mkdir()
        _map_plugin_artifacts(plugin_dir, apm_dir, manifest={"hooks": "my-hooks"})

        assert (apm_dir / "hooks" / "hooks.json").exists()
        assert (apm_dir / "hooks" / "scripts" / "lint.sh").exists()

    def test_nonexistent_custom_path_ignored(self, tmp_path):
        """Custom paths that don't exist are silently ignored."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()

        apm_dir = plugin_dir / ".apm"
        apm_dir.mkdir()
        _map_plugin_artifacts(
            plugin_dir, apm_dir,
            manifest={"agents": "does-not-exist/", "skills": ["also-missing/"]},
        )

        assert not (apm_dir / "agents").exists()
        assert not (apm_dir / "skills").exists()


class TestGenerateApmYml:
    def test_generate_full_metadata(self):
        manifest = {
            "name": "full-plugin",
            "version": "2.0.0",
            "description": "Full featured",
            "author": "Bob",
            "license": "Apache-2.0",
            "repository": "https://github.com/org/repo",
            "homepage": "https://example.com",
            "tags": ["ai", "copilot"],
        }

        yml_str = _generate_apm_yml(manifest)
        parsed = yaml.safe_load(yml_str)

        assert parsed["name"] == "full-plugin"
        assert parsed["version"] == "2.0.0"
        assert parsed["description"] == "Full featured"
        assert parsed["author"] == "Bob"
        assert parsed["license"] == "Apache-2.0"
        assert parsed["tags"] == ["ai", "copilot"]
        assert parsed["type"] == "hybrid"

    def test_generate_minimal_metadata(self):
        manifest = {"name": "minimal"}

        yml_str = _generate_apm_yml(manifest)
        parsed = yaml.safe_load(yml_str)

        assert parsed["name"] == "minimal"
        assert parsed["version"] == "0.0.0"
        assert parsed["description"] == ""
        assert parsed["type"] == "hybrid"

    def test_generate_author_as_dict(self):
        manifest = {
            "name": "dict-author",
            "author": {"name": "Foo Bar", "email": "foo@bar.com"},
        }

        yml_str = _generate_apm_yml(manifest)
        parsed = yaml.safe_load(yml_str)

        assert parsed["author"] == "Foo Bar"

    def test_generate_with_dependencies(self):
        manifest = {
            "name": "with-deps",
            "dependencies": {"dep-a": "^1.0", "dep-b": "~2.0"},
        }

        yml_str = _generate_apm_yml(manifest)
        parsed = yaml.safe_load(yml_str)

        assert parsed["dependencies"] == {"apm": {"dep-a": "^1.0", "dep-b": "~2.0"}}


class TestNormalizePluginDirectory:
    def test_normalize_with_manifest(self, tmp_path):
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        pj = plugin_dir / "plugin.json"
        pj.write_text(json.dumps({"name": "My Plugin", "version": "1.0.0"}))
        (plugin_dir / "agents").mkdir()
        (plugin_dir / "agents" / "bot.md").write_text("# Bot")

        result = normalize_plugin_directory(plugin_dir, pj)

        assert result == plugin_dir / "apm.yml"
        assert result.exists()
        parsed = yaml.safe_load(result.read_text())
        assert parsed["name"] == "My Plugin"
        assert (plugin_dir / ".apm" / "agents" / "bot.md").exists()

    def test_normalize_without_manifest(self, tmp_path):
        plugin_dir = tmp_path / "dir-name-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "go.md").write_text("# Go")

        result = normalize_plugin_directory(plugin_dir, plugin_json_path=None)

        assert result.exists()
        parsed = yaml.safe_load(result.read_text())
        assert parsed["name"] == "dir-name-plugin"
        assert (plugin_dir / ".apm" / "prompts" / "go.prompt.md").exists()


class TestValidatePluginPackage:
    def test_validate_with_plugin_json(self, tmp_path):
        plugin_dir = tmp_path / "valid"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text('{"name": "valid-plugin"}')

        assert validate_plugin_package(plugin_dir) is True

    def test_validate_with_component_dirs_only(self, tmp_path):
        plugin_dir = tmp_path / "components"
        plugin_dir.mkdir()
        (plugin_dir / "agents").mkdir()

        assert validate_plugin_package(plugin_dir) is True

    def test_validate_empty_directory(self, tmp_path):
        plugin_dir = tmp_path / "empty"
        plugin_dir.mkdir()

        assert validate_plugin_package(plugin_dir) is False

    def test_validate_readme_only(self, tmp_path):
        plugin_dir = tmp_path / "readme-only"
        plugin_dir.mkdir()
        (plugin_dir / "README.md").write_text("# Hello")

        assert validate_plugin_package(plugin_dir) is False
