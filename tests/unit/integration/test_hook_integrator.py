"""Unit tests for HookIntegrator.

Tests cover:
- Hook file discovery (.apm/hooks/ and hooks/ directories)
- VSCode integration (JSON copy + script copy + path rewriting)
- Claude integration (settings.json merge + script copy)
- Sync/cleanup integration (nuke-and-regenerate)
- Official plugin formats (hookify, learning-output-style, ralph-loop)
- Script path rewriting for ${CLAUDE_PLUGIN_ROOT} references
- Gitignore updates
"""

import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from apm_cli.integration.hook_integrator import HookIntegrator, HookIntegrationResult
from apm_cli.models.apm_package import APMPackage, PackageInfo


def _make_package_info(install_path: Path, name: str = "test-pkg") -> PackageInfo:
    """Create a minimal PackageInfo for testing."""
    package = APMPackage(name=name, version="1.0.0")
    return PackageInfo(package=package, install_path=install_path)


# ─── Hook file fixtures mirroring official Claude plugins ─────────────────────

HOOKIFY_HOOKS_JSON = {
    "description": "Hookify plugin - User-configurable hooks from .local.md files",
    "hooks": {
        "PreToolUse": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/pretooluse.py",
                        "timeout": 10,
                    }
                ]
            }
        ],
        "PostToolUse": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/posttooluse.py",
                        "timeout": 10,
                    }
                ]
            }
        ],
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/stop.py",
                        "timeout": 10,
                    }
                ]
            }
        ],
        "UserPromptSubmit": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/userpromptsubmit.py",
                        "timeout": 10,
                    }
                ]
            }
        ],
    },
}

LEARNING_OUTPUT_STYLE_HOOKS_JSON = {
    "description": "Learning mode hook that adds interactive learning instructions",
    "hooks": {
        "SessionStart": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "${CLAUDE_PLUGIN_ROOT}/hooks-handlers/session-start.sh",
                    }
                ]
            }
        ]
    },
}

RALPH_LOOP_HOOKS_JSON = {
    "description": "Ralph Loop plugin stop hook for self-referential loops",
    "hooks": {
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "${CLAUDE_PLUGIN_ROOT}/hooks/stop-hook.sh",
                    }
                ]
            }
        ]
    },
}


# ─── Discovery tests ─────────────────────────────────────────────────────────


class TestHookDiscovery:
    """Tests for finding hook JSON files in packages."""

    @pytest.fixture
    def temp_project(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_find_no_hooks(self, temp_project):
        """No hooks found when package has no hook directories."""
        pkg_dir = temp_project / "pkg"
        pkg_dir.mkdir()
        integrator = HookIntegrator()
        assert integrator.find_hook_files(pkg_dir) == []

    def test_find_hooks_in_apm_hooks(self, temp_project):
        """Find hook JSON files in .apm/hooks/ directory."""
        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / ".apm" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "security.json").write_text(json.dumps({"hooks": {}}))
        (hooks_dir / "quality.json").write_text(json.dumps({"hooks": {}}))
        (hooks_dir / "readme.md").write_text("# Not a hook")  # Should be ignored

        integrator = HookIntegrator()
        files = integrator.find_hook_files(pkg_dir)
        assert len(files) == 2
        assert all(f.suffix == ".json" for f in files)

    def test_find_hooks_in_hooks_dir(self, temp_project):
        """Find hook JSON files in hooks/ directory (Claude-native convention)."""
        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "hooks.json").write_text(json.dumps({"hooks": {}}))

        integrator = HookIntegrator()
        files = integrator.find_hook_files(pkg_dir)
        assert len(files) == 1
        assert files[0].name == "hooks.json"

    def test_find_hooks_deduplicates(self, temp_project):
        """Do not return duplicate hook files when .apm/hooks/ and hooks/ overlap."""
        pkg_dir = temp_project / "pkg"
        # Create both directories pointing to the same conceptual hooks
        apm_hooks = pkg_dir / ".apm" / "hooks"
        apm_hooks.mkdir(parents=True)
        (apm_hooks / "a.json").write_text(json.dumps({"hooks": {}}))

        hooks_dir = pkg_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "b.json").write_text(json.dumps({"hooks": {}}))

        integrator = HookIntegrator()
        files = integrator.find_hook_files(pkg_dir)
        assert len(files) == 2  # Different files, should both be found

    def test_should_integrate_always_true(self, temp_project):
        """Integration is always enabled (zero-config)."""
        integrator = HookIntegrator()
        assert integrator.should_integrate(temp_project)


# ─── Parsing tests ────────────────────────────────────────────────────────────


class TestHookParsing:
    """Tests for parsing hook JSON files."""

    @pytest.fixture
    def temp_project(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_parse_valid_hook_json(self, temp_project):
        hook_file = temp_project / "hooks.json"
        hook_file.write_text(json.dumps(HOOKIFY_HOOKS_JSON))

        integrator = HookIntegrator()
        data = integrator._parse_hook_json(hook_file)
        assert data is not None
        assert "hooks" in data
        assert "PreToolUse" in data["hooks"]

    def test_parse_invalid_json(self, temp_project):
        hook_file = temp_project / "bad.json"
        hook_file.write_text("not valid json {{{")

        integrator = HookIntegrator()
        assert integrator._parse_hook_json(hook_file) is None

    def test_parse_non_dict_json(self, temp_project):
        hook_file = temp_project / "array.json"
        hook_file.write_text(json.dumps([1, 2, 3]))

        integrator = HookIntegrator()
        assert integrator._parse_hook_json(hook_file) is None

    def test_parse_missing_file(self, temp_project):
        integrator = HookIntegrator()
        assert integrator._parse_hook_json(temp_project / "missing.json") is None


# ─── VSCode integration tests ────────────────────────────────────────────────


class TestVSCodeIntegration:
    """Tests for VSCode hook integration (.github/hooks/)."""

    @pytest.fixture
    def temp_project(self):
        temp_dir = tempfile.mkdtemp()
        project = Path(temp_dir)
        (project / ".github").mkdir()
        yield project
        shutil.rmtree(temp_dir, ignore_errors=True)

    def _setup_hookify_package(self, project: Path) -> PackageInfo:
        """Create a hookify-like package structure."""
        pkg_dir = project / "apm_modules" / "anthropics" / "hookify"
        hooks_dir = pkg_dir / "hooks"
        hooks_dir.mkdir(parents=True)

        (hooks_dir / "hooks.json").write_text(json.dumps(HOOKIFY_HOOKS_JSON, indent=2))

        # Create the script files
        for script in ["pretooluse.py", "posttooluse.py", "stop.py", "userpromptsubmit.py"]:
            (hooks_dir / script).write_text(f"#!/usr/bin/env python3\n# {script}")

        return _make_package_info(pkg_dir, "hookify")

    def test_integrate_hookify_vscode(self, temp_project):
        """Test VSCode integration of hookify plugin (multiple events + Python scripts)."""
        pkg_info = self._setup_hookify_package(temp_project)
        integrator = HookIntegrator()

        result = integrator.integrate_package_hooks(pkg_info, temp_project)

        assert result.hooks_integrated == 1
        assert result.scripts_copied == 4

        # Check hook JSON was created
        target_json = temp_project / ".github" / "hooks" / "hookify-hooks-apm.json"
        assert target_json.exists()

        # Verify rewritten paths
        data = json.loads(target_json.read_text())
        cmd = data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        assert "${CLAUDE_PLUGIN_ROOT}" not in cmd
        assert ".github/hooks/scripts/hookify/hooks/pretooluse.py" in cmd
        assert cmd.startswith("python3 ")

        # Check scripts were copied
        scripts_dir = temp_project / ".github" / "hooks" / "scripts" / "hookify" / "hooks"
        assert (scripts_dir / "pretooluse.py").exists()
        assert (scripts_dir / "posttooluse.py").exists()
        assert (scripts_dir / "stop.py").exists()
        assert (scripts_dir / "userpromptsubmit.py").exists()

    def test_integrate_learning_output_style_vscode(self, temp_project):
        """Test VSCode integration of learning-output-style plugin (different script dir)."""
        pkg_dir = temp_project / "apm_modules" / "anthropics" / "learning-output-style"
        hooks_dir = pkg_dir / "hooks"
        handlers_dir = pkg_dir / "hooks-handlers"
        hooks_dir.mkdir(parents=True)
        handlers_dir.mkdir(parents=True)

        (hooks_dir / "hooks.json").write_text(json.dumps(LEARNING_OUTPUT_STYLE_HOOKS_JSON))
        (handlers_dir / "session-start.sh").write_text("#!/bin/bash\necho 'start'")

        pkg_info = _make_package_info(pkg_dir, "learning-output-style")
        integrator = HookIntegrator()

        result = integrator.integrate_package_hooks(pkg_info, temp_project)

        assert result.hooks_integrated == 1
        assert result.scripts_copied == 1

        # Verify rewritten paths
        target_json = temp_project / ".github" / "hooks" / "learning-output-style-hooks-apm.json"
        data = json.loads(target_json.read_text())
        cmd = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        assert "${CLAUDE_PLUGIN_ROOT}" not in cmd
        assert "learning-output-style" in cmd
        assert "session-start.sh" in cmd

        # Check script was copied
        assert (
            temp_project
            / ".github"
            / "hooks"
            / "scripts"
            / "learning-output-style"
            / "hooks-handlers"
            / "session-start.sh"
        ).exists()

    def test_integrate_ralph_loop_vscode(self, temp_project):
        """Test VSCode integration of ralph-loop plugin (Stop hook)."""
        pkg_dir = temp_project / "apm_modules" / "anthropics" / "ralph-loop"
        hooks_dir = pkg_dir / "hooks"
        hooks_dir.mkdir(parents=True)

        (hooks_dir / "hooks.json").write_text(json.dumps(RALPH_LOOP_HOOKS_JSON))
        (hooks_dir / "stop-hook.sh").write_text("#!/bin/bash\nexit 0")

        pkg_info = _make_package_info(pkg_dir, "ralph-loop")
        integrator = HookIntegrator()

        result = integrator.integrate_package_hooks(pkg_info, temp_project)

        assert result.hooks_integrated == 1
        assert result.scripts_copied == 1

        target_json = temp_project / ".github" / "hooks" / "ralph-loop-hooks-apm.json"
        data = json.loads(target_json.read_text())
        cmd = data["hooks"]["Stop"][0]["hooks"][0]["command"]
        assert "ralph-loop" in cmd
        assert "stop-hook.sh" in cmd

    def test_integrate_no_hooks(self, temp_project):
        """Test integration with package that has no hooks."""
        pkg_dir = temp_project / "pkg"
        pkg_dir.mkdir()

        pkg_info = _make_package_info(pkg_dir)
        integrator = HookIntegrator()

        result = integrator.integrate_package_hooks(pkg_info, temp_project)
        assert result.hooks_integrated == 0
        assert result.scripts_copied == 0

    def test_integrate_hooks_from_apm_convention(self, temp_project):
        """Test VSCode integration using .apm/hooks/ convention."""
        pkg_dir = temp_project / "apm_modules" / "myorg" / "security-hooks"
        hooks_dir = pkg_dir / ".apm" / "hooks"
        scripts_dir = pkg_dir / "scripts"
        hooks_dir.mkdir(parents=True)
        scripts_dir.mkdir(parents=True)

        hook_data = {
            "hooks": {
                "PreToolUse": [
                    {
                        "hooks": [
                            {"type": "command", "command": "./scripts/validate.sh"}
                        ]
                    }
                ]
            }
        }
        (hooks_dir / "security.json").write_text(json.dumps(hook_data))
        (scripts_dir / "validate.sh").write_text("#!/bin/bash\necho 'validate'")

        pkg_info = _make_package_info(pkg_dir, "security-hooks")
        integrator = HookIntegrator()

        result = integrator.integrate_package_hooks(pkg_info, temp_project)

        assert result.hooks_integrated == 1
        target_json = temp_project / ".github" / "hooks" / "security-hooks-security-apm.json"
        assert target_json.exists()

    def test_integrate_system_command_passthrough(self, temp_project):
        """Test that system commands without file paths are passed through unchanged."""
        pkg_dir = temp_project / "apm_modules" / "myorg" / "format-pkg"
        hooks_dir = pkg_dir / "hooks"
        hooks_dir.mkdir(parents=True)

        hook_data = {
            "hooks": {
                "PreToolUse": [
                    {
                        "hooks": [
                            {"type": "command", "command": "npx prettier --check ."}
                        ]
                    }
                ]
            }
        }
        (hooks_dir / "format.json").write_text(json.dumps(hook_data))

        pkg_info = _make_package_info(pkg_dir, "format-pkg")
        integrator = HookIntegrator()

        result = integrator.integrate_package_hooks(pkg_info, temp_project)

        assert result.hooks_integrated == 1
        assert result.scripts_copied == 0  # No scripts to copy for system commands

        target_json = temp_project / ".github" / "hooks" / "format-pkg-format-apm.json"
        data = json.loads(target_json.read_text())
        cmd = data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        assert cmd == "npx prettier --check ."

    def test_invalid_json_skipped(self, temp_project):
        """Test that invalid JSON hook files are skipped gracefully."""
        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "bad.json").write_text("not json")

        pkg_info = _make_package_info(pkg_dir)
        integrator = HookIntegrator()

        result = integrator.integrate_package_hooks(pkg_info, temp_project)
        assert result.hooks_integrated == 0

    def test_creates_github_hooks_dir(self, temp_project):
        """Test that .github/hooks/ directory is created if it doesn't exist."""
        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "hooks.json").write_text(json.dumps({"hooks": {"Stop": []}}))

        pkg_info = _make_package_info(pkg_dir)
        integrator = HookIntegrator()

        result = integrator.integrate_package_hooks(pkg_info, temp_project)
        assert (temp_project / ".github" / "hooks").exists()


# ─── Claude integration tests ────────────────────────────────────────────────


class TestClaudeIntegration:
    """Tests for Claude hook integration (.claude/settings.json merge)."""

    @pytest.fixture
    def temp_project(self):
        temp_dir = tempfile.mkdtemp()
        project = Path(temp_dir)
        (project / ".claude").mkdir()
        yield project
        shutil.rmtree(temp_dir, ignore_errors=True)

    def _setup_hookify_package(self, project: Path) -> PackageInfo:
        """Create a hookify-like package structure."""
        pkg_dir = project / "apm_modules" / "anthropics" / "hookify"
        hooks_dir = pkg_dir / "hooks"
        hooks_dir.mkdir(parents=True)

        (hooks_dir / "hooks.json").write_text(json.dumps(HOOKIFY_HOOKS_JSON, indent=2))

        for script in ["pretooluse.py", "posttooluse.py", "stop.py", "userpromptsubmit.py"]:
            (hooks_dir / script).write_text(f"#!/usr/bin/env python3\n# {script}")

        return _make_package_info(pkg_dir, "hookify")

    def test_integrate_hookify_claude(self, temp_project):
        """Test Claude integration of hookify plugin (merge into settings.json)."""
        pkg_info = self._setup_hookify_package(temp_project)
        integrator = HookIntegrator()

        result = integrator.integrate_package_hooks_claude(pkg_info, temp_project)

        assert result.hooks_integrated == 1
        assert result.scripts_copied == 4

        # Check settings.json was created/updated
        settings_path = temp_project / ".claude" / "settings.json"
        assert settings_path.exists()

        settings = json.loads(settings_path.read_text())
        assert "hooks" in settings
        assert "PreToolUse" in settings["hooks"]
        assert "PostToolUse" in settings["hooks"]
        assert "Stop" in settings["hooks"]
        assert "UserPromptSubmit" in settings["hooks"]

        # Check APM source marker for cleanup
        assert settings["hooks"]["PreToolUse"][0]["_apm_source"] == "hookify"

        # Verify rewritten paths
        cmd = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        assert ".claude/hooks/hookify/hooks/pretooluse.py" in cmd

    def test_integrate_learning_output_style_claude(self, temp_project):
        """Test Claude integration of learning-output-style plugin."""
        pkg_dir = temp_project / "apm_modules" / "anthropics" / "learning-output-style"
        hooks_dir = pkg_dir / "hooks"
        handlers_dir = pkg_dir / "hooks-handlers"
        hooks_dir.mkdir(parents=True)
        handlers_dir.mkdir(parents=True)

        (hooks_dir / "hooks.json").write_text(json.dumps(LEARNING_OUTPUT_STYLE_HOOKS_JSON))
        (handlers_dir / "session-start.sh").write_text("#!/bin/bash\necho 'start'")

        pkg_info = _make_package_info(pkg_dir, "learning-output-style")
        integrator = HookIntegrator()

        result = integrator.integrate_package_hooks_claude(pkg_info, temp_project)

        assert result.hooks_integrated == 1
        settings = json.loads((temp_project / ".claude" / "settings.json").read_text())
        assert "SessionStart" in settings["hooks"]

    def test_integrate_ralph_loop_claude(self, temp_project):
        """Test Claude integration of ralph-loop plugin."""
        pkg_dir = temp_project / "apm_modules" / "anthropics" / "ralph-loop"
        hooks_dir = pkg_dir / "hooks"
        hooks_dir.mkdir(parents=True)

        (hooks_dir / "hooks.json").write_text(json.dumps(RALPH_LOOP_HOOKS_JSON))
        (hooks_dir / "stop-hook.sh").write_text("#!/bin/bash\nexit 0")

        pkg_info = _make_package_info(pkg_dir, "ralph-loop")
        integrator = HookIntegrator()

        result = integrator.integrate_package_hooks_claude(pkg_info, temp_project)

        assert result.hooks_integrated == 1
        settings = json.loads((temp_project / ".claude" / "settings.json").read_text())
        assert "Stop" in settings["hooks"]
        cmd = settings["hooks"]["Stop"][0]["hooks"][0]["command"]
        assert "ralph-loop" in cmd

    def test_merge_into_existing_settings(self, temp_project):
        """Test that hooks are merged into existing settings.json without clobbering."""
        settings_path = temp_project / ".claude" / "settings.json"
        settings_path.write_text(json.dumps({
            "model": "claude-sonnet-4-20250514",
            "hooks": {
                "PreToolUse": [{"hooks": [{"type": "command", "command": "echo user-hook"}]}]
            }
        }))

        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "hooks.json").write_text(json.dumps(RALPH_LOOP_HOOKS_JSON))
        (hooks_dir / "stop-hook.sh").write_text("#!/bin/bash\nexit 0")

        pkg_info = _make_package_info(pkg_dir, "ralph-loop")
        integrator = HookIntegrator()

        result = integrator.integrate_package_hooks_claude(pkg_info, temp_project)

        settings = json.loads(settings_path.read_text())
        # Original settings preserved
        assert settings["model"] == "claude-sonnet-4-20250514"
        # User hook preserved
        assert len(settings["hooks"]["PreToolUse"]) == 1
        # New hook added
        assert "Stop" in settings["hooks"]

    def test_additive_merge_same_event(self, temp_project):
        """Test that multiple packages can add hooks to the same event (additive)."""
        integrator = HookIntegrator()

        # First package: ralph-loop with Stop hook
        pkg1_dir = temp_project / "pkg1"
        hooks1_dir = pkg1_dir / "hooks"
        hooks1_dir.mkdir(parents=True)
        (hooks1_dir / "hooks.json").write_text(json.dumps(RALPH_LOOP_HOOKS_JSON))
        (hooks1_dir / "stop-hook.sh").write_text("#!/bin/bash\nexit 0")
        pkg1_info = _make_package_info(pkg1_dir, "ralph-loop")

        integrator.integrate_package_hooks_claude(pkg1_info, temp_project)

        # Second package: also has Stop hook
        pkg2_dir = temp_project / "pkg2"
        hooks2_dir = pkg2_dir / "hooks"
        hooks2_dir.mkdir(parents=True)
        other_hooks = {
            "hooks": {
                "Stop": [{"hooks": [{"type": "command", "command": "echo other-stop"}]}]
            }
        }
        (hooks2_dir / "hooks.json").write_text(json.dumps(other_hooks))
        pkg2_info = _make_package_info(pkg2_dir, "other-pkg")

        integrator.integrate_package_hooks_claude(pkg2_info, temp_project)

        settings = json.loads((temp_project / ".claude" / "settings.json").read_text())
        # Both Stop hooks should be present (additive)
        assert len(settings["hooks"]["Stop"]) == 2

    def test_no_hooks_returns_empty_result(self, temp_project):
        """Test Claude integration with no hook files returns empty result."""
        pkg_dir = temp_project / "pkg"
        pkg_dir.mkdir()

        pkg_info = _make_package_info(pkg_dir)
        integrator = HookIntegrator()

        result = integrator.integrate_package_hooks_claude(pkg_info, temp_project)
        assert result.hooks_integrated == 0

    def test_creates_settings_json(self, temp_project):
        """Test that .claude/settings.json is created if it doesn't exist."""
        # Remove existing .claude dir
        shutil.rmtree(temp_project / ".claude")

        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "hooks.json").write_text(json.dumps(RALPH_LOOP_HOOKS_JSON))
        (hooks_dir / "stop-hook.sh").write_text("#!/bin/bash\nexit 0")

        pkg_info = _make_package_info(pkg_dir, "ralph-loop")
        integrator = HookIntegrator()

        result = integrator.integrate_package_hooks_claude(pkg_info, temp_project)
        assert result.hooks_integrated == 1
        assert (temp_project / ".claude" / "settings.json").exists()

    def test_integrate_hooks_with_scripts_in_hooks_subdir_claude(self, temp_project):
        """Test Claude integration when hook JSON and scripts are both inside hooks/ subdir."""
        pkg_dir = temp_project / "apm_modules" / "myorg" / "lint-hooks"
        hooks_dir = pkg_dir / "hooks"
        scripts_dir = hooks_dir / "scripts"
        scripts_dir.mkdir(parents=True)

        hook_data = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": {"tool_name": "write_to_file"},
                        "hooks": [
                            {"type": "command", "command": "./scripts/lint.sh", "timeout": 10}
                        ]
                    }
                ]
            }
        }
        (hooks_dir / "hooks.json").write_text(json.dumps(hook_data))
        (scripts_dir / "lint.sh").write_text("#!/bin/bash\necho lint")

        pkg_info = _make_package_info(pkg_dir, "lint-hooks")
        integrator = HookIntegrator()

        result = integrator.integrate_package_hooks_claude(pkg_info, temp_project)

        assert result.hooks_integrated == 1
        assert result.scripts_copied == 1

        # Verify rewritten command in settings.json
        settings = json.loads((temp_project / ".claude" / "settings.json").read_text())
        cmd = settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
        assert ".claude/hooks/lint-hooks/scripts/lint.sh" in cmd
        assert "./" not in cmd

        # Verify script was copied to Claude target location
        copied_script = temp_project / ".claude" / "hooks" / "lint-hooks" / "scripts" / "lint.sh"
        assert copied_script.exists()
        assert copied_script.read_text() == "#!/bin/bash\necho lint"


# ─── Sync/cleanup tests ──────────────────────────────────────────────────────


class TestSyncIntegration:
    """Tests for sync_integration (nuke-and-regenerate during uninstall)."""

    @pytest.fixture
    def temp_project(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sync_removes_vscode_hook_files(self, temp_project):
        """Test that sync removes all *-apm.json files from .github/hooks/."""
        hooks_dir = temp_project / ".github" / "hooks"
        hooks_dir.mkdir(parents=True)

        (hooks_dir / "hookify-hooks-apm.json").write_text("{}")
        (hooks_dir / "ralph-loop-hooks-apm.json").write_text("{}")
        (hooks_dir / "user-custom.json").write_text("{}")  # Should NOT be removed

        integrator = HookIntegrator()
        stats = integrator.sync_integration(None, temp_project)

        assert stats["files_removed"] == 2
        assert not (hooks_dir / "hookify-hooks-apm.json").exists()
        assert not (hooks_dir / "ralph-loop-hooks-apm.json").exists()
        assert (hooks_dir / "user-custom.json").exists()

    def test_sync_removes_scripts_directory(self, temp_project):
        """Test that sync removes the scripts/ directory from .github/hooks/."""
        hooks_dir = temp_project / ".github" / "hooks"
        scripts_dir = hooks_dir / "scripts" / "hookify" / "hooks"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "pretooluse.py").write_text("# script")

        integrator = HookIntegrator()
        stats = integrator.sync_integration(None, temp_project)

        assert not (hooks_dir / "scripts").exists()

    def test_sync_removes_claude_hook_entries(self, temp_project):
        """Test that sync removes APM-managed entries from .claude/settings.json."""
        claude_dir = temp_project / ".claude"
        claude_dir.mkdir()
        settings_path = claude_dir / "settings.json"

        settings = {
            "model": "claude-sonnet-4-20250514",
            "hooks": {
                "Stop": [
                    {"_apm_source": "ralph-loop", "hooks": [{"type": "command", "command": "..."}]},
                    {"hooks": [{"type": "command", "command": "echo user-hook"}]},
                ],
                "PreToolUse": [
                    {"_apm_source": "hookify", "hooks": [{"type": "command", "command": "..."}]}
                ],
            },
        }
        settings_path.write_text(json.dumps(settings))

        integrator = HookIntegrator()
        stats = integrator.sync_integration(None, temp_project)

        updated_settings = json.loads(settings_path.read_text())
        # Model preserved
        assert updated_settings["model"] == "claude-sonnet-4-20250514"
        # APM entries removed, user entries preserved
        assert "Stop" in updated_settings["hooks"]
        assert len(updated_settings["hooks"]["Stop"]) == 1
        assert "_apm_source" not in updated_settings["hooks"]["Stop"][0]
        # PreToolUse completely removed (only had APM entries)
        assert "PreToolUse" not in updated_settings["hooks"]

    def test_sync_removes_claude_hooks_dir(self, temp_project):
        """Test that sync removes .claude/hooks/ directory."""
        claude_hooks = temp_project / ".claude" / "hooks" / "hookify"
        claude_hooks.mkdir(parents=True)
        (claude_hooks / "pretooluse.py").write_text("# script")

        integrator = HookIntegrator()
        stats = integrator.sync_integration(None, temp_project)

        assert not (temp_project / ".claude" / "hooks").exists()

    def test_sync_empty_project(self, temp_project):
        """Test sync on project with no hook artifacts."""
        integrator = HookIntegrator()
        stats = integrator.sync_integration(None, temp_project)
        assert stats["files_removed"] == 0
        assert stats["errors"] == 0

    def test_sync_removes_empty_hooks_key(self, temp_project):
        """Test that empty hooks key is removed from settings.json after cleanup."""
        claude_dir = temp_project / ".claude"
        claude_dir.mkdir()
        settings_path = claude_dir / "settings.json"
        settings = {
            "hooks": {
                "Stop": [{"_apm_source": "test", "hooks": []}]
            }
        }
        settings_path.write_text(json.dumps(settings))

        integrator = HookIntegrator()
        integrator.sync_integration(None, temp_project)

        updated = json.loads(settings_path.read_text())
        assert "hooks" not in updated  # Completely removed when empty


# ─── Script path rewriting tests ─────────────────────────────────────────────


class TestScriptPathRewriting:
    """Tests for command path rewriting logic."""

    @pytest.fixture
    def temp_project(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_rewrite_claude_plugin_root(self, temp_project):
        """Test rewriting ${CLAUDE_PLUGIN_ROOT} variable."""
        pkg_dir = temp_project / "pkg"
        (pkg_dir / "hooks").mkdir(parents=True)
        (pkg_dir / "hooks" / "script.sh").write_text("#!/bin/bash")

        integrator = HookIntegrator()
        cmd, scripts = integrator._rewrite_command_for_target(
            "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/script.sh",
            pkg_dir,
            "my-pkg",
            "vscode",
        )

        assert "${CLAUDE_PLUGIN_ROOT}" not in cmd
        assert ".github/hooks/scripts/my-pkg/hooks/script.sh" in cmd
        assert len(scripts) == 1

    def test_rewrite_relative_path(self, temp_project):
        """Test rewriting relative ./path references."""
        pkg_dir = temp_project / "pkg"
        (pkg_dir / "scripts").mkdir(parents=True)
        (pkg_dir / "scripts" / "check.sh").write_text("#!/bin/bash")

        integrator = HookIntegrator()
        cmd, scripts = integrator._rewrite_command_for_target(
            "./scripts/check.sh",
            pkg_dir,
            "my-pkg",
            "vscode",
        )

        assert "./" not in cmd
        assert ".github/hooks/scripts/my-pkg/scripts/check.sh" in cmd
        assert len(scripts) == 1

    def test_system_command_unchanged(self, temp_project):
        """Test that system commands are not modified."""
        pkg_dir = temp_project / "pkg"
        pkg_dir.mkdir(parents=True)

        integrator = HookIntegrator()
        cmd, scripts = integrator._rewrite_command_for_target(
            "npx prettier --check .",
            pkg_dir,
            "my-pkg",
            "vscode",
        )

        assert cmd == "npx prettier --check ."
        assert len(scripts) == 0

    def test_rewrite_for_claude_target(self, temp_project):
        """Test that Claude target uses .claude/hooks/ path."""
        pkg_dir = temp_project / "pkg"
        (pkg_dir / "hooks").mkdir(parents=True)
        (pkg_dir / "hooks" / "run.sh").write_text("#!/bin/bash")

        integrator = HookIntegrator()
        cmd, scripts = integrator._rewrite_command_for_target(
            "${CLAUDE_PLUGIN_ROOT}/hooks/run.sh",
            pkg_dir,
            "my-pkg",
            "claude",
        )

        assert ".claude/hooks/my-pkg/hooks/run.sh" in cmd
        assert len(scripts) == 1

    def test_nonexistent_script_not_rewritten(self, temp_project):
        """Test that references to non-existent scripts are left as-is."""
        pkg_dir = temp_project / "pkg"
        pkg_dir.mkdir(parents=True)

        integrator = HookIntegrator()
        cmd, scripts = integrator._rewrite_command_for_target(
            "${CLAUDE_PLUGIN_ROOT}/missing/script.sh",
            pkg_dir,
            "my-pkg",
            "vscode",
        )

        # Variable is left in the command since the file doesn't exist
        assert "${CLAUDE_PLUGIN_ROOT}" in cmd
        assert len(scripts) == 0

    def test_rewrite_preserves_binary_prefix(self, temp_project):
        """Test that binary prefix (e.g., python3) is preserved in rewritten commands."""
        pkg_dir = temp_project / "pkg"
        (pkg_dir / "hooks").mkdir(parents=True)
        (pkg_dir / "hooks" / "check.py").write_text("#!/usr/bin/env python3")

        integrator = HookIntegrator()
        cmd, _ = integrator._rewrite_command_for_target(
            "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/check.py",
            pkg_dir,
            "my-pkg",
            "vscode",
        )

        assert cmd.startswith("python3 ")
        assert cmd.endswith("hooks/check.py")

    def test_rewrite_relative_path_with_hook_file_dir(self, temp_project):
        """Test that ./path is resolved from hook_file_dir, not package root."""
        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / "hooks"
        scripts_dir = hooks_dir / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "lint.sh").write_text("#!/bin/bash")

        integrator = HookIntegrator()
        # Script lives at hooks/scripts/lint.sh — only resolvable from hooks/ dir
        cmd, scripts = integrator._rewrite_command_for_target(
            "./scripts/lint.sh",
            pkg_dir,
            "my-pkg",
            "vscode",
            hook_file_dir=hooks_dir,
        )

        assert "./" not in cmd
        assert ".github/hooks/scripts/my-pkg/scripts/lint.sh" in cmd
        assert len(scripts) == 1
        assert scripts[0][0] == (scripts_dir / "lint.sh").resolve()

    def test_rewrite_relative_path_fails_without_hook_file_dir(self, temp_project):
        """Test that ./path is NOT found when resolved from package root (no hook_file_dir)."""
        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / "hooks"
        scripts_dir = hooks_dir / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "lint.sh").write_text("#!/bin/bash")

        integrator = HookIntegrator()
        # Without hook_file_dir, resolves from pkg_dir — scripts/lint.sh doesn't exist there
        cmd, scripts = integrator._rewrite_command_for_target(
            "./scripts/lint.sh",
            pkg_dir,
            "my-pkg",
            "vscode",
        )

        # Script not found at pkg_dir/scripts/lint.sh, so left unchanged
        assert cmd == "./scripts/lint.sh"
        assert len(scripts) == 0

    def test_rewrite_rejects_plugin_root_path_traversal(self, temp_project):
        """Test that ${CLAUDE_PLUGIN_ROOT}/../ paths are rejected (path traversal)."""
        pkg_dir = temp_project / "pkg"
        pkg_dir.mkdir(parents=True)
        # Create a file outside the package directory
        secret = temp_project / "secrets.txt"
        secret.write_text("top-secret")

        integrator = HookIntegrator()
        cmd, scripts = integrator._rewrite_command_for_target(
            "cat ${CLAUDE_PLUGIN_ROOT}/../secrets.txt",
            pkg_dir,
            "evil-pkg",
            "vscode",
        )

        # The traversal path should NOT be rewritten and no scripts copied
        assert "${CLAUDE_PLUGIN_ROOT}/../secrets.txt" in cmd
        assert len(scripts) == 0

    def test_rewrite_rejects_relative_path_traversal(self, temp_project):
        """Test that ./../../ paths are rejected (path traversal via relative refs)."""
        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        # Create a file outside the package directory
        secret = temp_project / "secrets.txt"
        secret.write_text("top-secret")

        integrator = HookIntegrator()
        cmd, scripts = integrator._rewrite_command_for_target(
            "./../../secrets.txt",
            pkg_dir,
            "evil-pkg",
            "claude",
            hook_file_dir=hooks_dir,
        )

        # The traversal path should NOT be rewritten and no scripts copied
        assert cmd == "./../../secrets.txt"
        assert len(scripts) == 0

    def test_integrate_hooks_with_scripts_in_hooks_subdir(self, temp_project):
        """Test full integration when hook JSON and scripts are both inside hooks/ subdir."""
        pkg_dir = temp_project / "apm_modules" / "myorg" / "lint-hooks"
        hooks_dir = pkg_dir / "hooks"
        scripts_dir = hooks_dir / "scripts"
        scripts_dir.mkdir(parents=True)

        hook_data = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": {"tool_name": "write_to_file"},
                        "hooks": [
                            {"type": "command", "command": "./scripts/lint.sh", "timeout": 10}
                        ]
                    }
                ]
            }
        }
        (hooks_dir / "hooks.json").write_text(json.dumps(hook_data))
        (scripts_dir / "lint.sh").write_text("#!/bin/bash\necho lint")

        pkg_info = _make_package_info(pkg_dir, "lint-hooks")
        integrator = HookIntegrator()

        result = integrator.integrate_package_hooks(pkg_info, temp_project)

        assert result.hooks_integrated == 1
        assert result.scripts_copied == 1

        # Verify the rewritten command points to the bundled script
        target_json = temp_project / ".github" / "hooks" / "lint-hooks-hooks-apm.json"
        data = json.loads(target_json.read_text())
        cmd = data["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
        assert ".github/hooks/scripts/lint-hooks/scripts/lint.sh" in cmd
        assert "./" not in cmd

        # Verify the script was actually copied
        copied_script = temp_project / ".github" / "hooks" / "scripts" / "lint-hooks" / "scripts" / "lint.sh"
        assert copied_script.exists()
        assert copied_script.read_text() == "#!/bin/bash\necho lint"


# ─── Gitignore tests ─────────────────────────────────────────────────────────


class TestGitignore:
    """Tests for .gitignore updates."""

    @pytest.fixture
    def temp_project(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_update_gitignore_adds_patterns(self, temp_project):
        """Test that hook patterns are added to .gitignore."""
        (temp_project / ".gitignore").write_text("node_modules/\n")

        integrator = HookIntegrator()
        result = integrator.update_gitignore(temp_project)

        assert result is True
        content = (temp_project / ".gitignore").read_text()
        assert ".github/hooks/*-apm.json" in content
        assert ".github/hooks/scripts/" in content

    def test_update_gitignore_idempotent(self, temp_project):
        """Test that patterns are not duplicated on repeated calls."""
        (temp_project / ".gitignore").write_text(
            "node_modules/\n\n# APM integrated hooks\n.github/hooks/*-apm.json\n.github/hooks/scripts/\n"
        )

        integrator = HookIntegrator()
        result = integrator.update_gitignore(temp_project)

        assert result is False

    def test_update_gitignore_creates_file(self, temp_project):
        """Test that .gitignore is created if it doesn't exist."""
        integrator = HookIntegrator()
        result = integrator.update_gitignore(temp_project)

        assert result is True
        assert (temp_project / ".gitignore").exists()


# ─── End-to-end: install → verify → cleanup ──────────────────────────────────


class TestEndToEnd:
    """End-to-end tests covering full install → verify → cleanup cycle."""

    @pytest.fixture
    def temp_project(self):
        temp_dir = tempfile.mkdtemp()
        project = Path(temp_dir)
        (project / ".github").mkdir()
        (project / ".claude").mkdir()
        yield project
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_full_hookify_lifecycle(self, temp_project):
        """Test full lifecycle: install hookify → verify → cleanup."""
        integrator = HookIntegrator()

        # Setup hookify package
        pkg_dir = temp_project / "apm_modules" / "anthropics" / "hookify"
        hooks_dir = pkg_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "hooks.json").write_text(json.dumps(HOOKIFY_HOOKS_JSON))
        for script in ["pretooluse.py", "posttooluse.py", "stop.py", "userpromptsubmit.py"]:
            (hooks_dir / script).write_text(f"# {script}")

        pkg_info = _make_package_info(pkg_dir, "hookify")

        # Install VSCode hooks
        vscode_result = integrator.integrate_package_hooks(pkg_info, temp_project)
        assert vscode_result.hooks_integrated == 1
        assert vscode_result.scripts_copied == 4

        # Install Claude hooks
        claude_result = integrator.integrate_package_hooks_claude(pkg_info, temp_project)
        assert claude_result.hooks_integrated == 1

        # Verify files exist
        assert (temp_project / ".github" / "hooks" / "hookify-hooks-apm.json").exists()
        assert (temp_project / ".claude" / "settings.json").exists()

        # Cleanup
        stats = integrator.sync_integration(None, temp_project)
        assert stats["files_removed"] > 0

        # Verify cleanup
        assert not (temp_project / ".github" / "hooks" / "hookify-hooks-apm.json").exists()
        assert not (temp_project / ".github" / "hooks" / "scripts").exists()
        assert not (temp_project / ".claude" / "hooks").exists()

    def test_multiple_packages_lifecycle(self, temp_project):
        """Test installing hooks from multiple packages, then cleaning up."""
        integrator = HookIntegrator()

        # Package 1: ralph-loop
        pkg1_dir = temp_project / "apm_modules" / "anthropics" / "ralph-loop"
        hooks1_dir = pkg1_dir / "hooks"
        hooks1_dir.mkdir(parents=True)
        (hooks1_dir / "hooks.json").write_text(json.dumps(RALPH_LOOP_HOOKS_JSON))
        (hooks1_dir / "stop-hook.sh").write_text("#!/bin/bash")
        pkg1_info = _make_package_info(pkg1_dir, "ralph-loop")

        # Package 2: learning-output-style
        pkg2_dir = temp_project / "apm_modules" / "anthropics" / "learning-output-style"
        hooks2_dir = pkg2_dir / "hooks"
        handlers_dir = pkg2_dir / "hooks-handlers"
        hooks2_dir.mkdir(parents=True)
        handlers_dir.mkdir(parents=True)
        (hooks2_dir / "hooks.json").write_text(json.dumps(LEARNING_OUTPUT_STYLE_HOOKS_JSON))
        (handlers_dir / "session-start.sh").write_text("#!/bin/bash")
        pkg2_info = _make_package_info(pkg2_dir, "learning-output-style")

        # Install both
        integrator.integrate_package_hooks(pkg1_info, temp_project)
        integrator.integrate_package_hooks(pkg2_info, temp_project)

        # Both hook JSONs should exist
        assert (temp_project / ".github" / "hooks" / "ralph-loop-hooks-apm.json").exists()
        assert (temp_project / ".github" / "hooks" / "learning-output-style-hooks-apm.json").exists()

        # Cleanup removes all
        stats = integrator.sync_integration(None, temp_project)
        assert stats["files_removed"] >= 2
        assert not (temp_project / ".github" / "hooks" / "ralph-loop-hooks-apm.json").exists()
        assert not (temp_project / ".github" / "hooks" / "learning-output-style-hooks-apm.json").exists()


# ─── Deep copy safety test ───────────────────────────────────────────────────


class TestDeepCopySafety:
    """Test that rewriting doesn't mutate the original data."""

    @pytest.fixture
    def temp_project(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_rewrite_does_not_mutate_original(self, temp_project):
        """Ensure _rewrite_hooks_data returns a copy, not mutating original."""
        pkg_dir = temp_project / "pkg"
        (pkg_dir / "hooks").mkdir(parents=True)
        (pkg_dir / "hooks" / "script.sh").write_text("#!/bin/bash")

        data = {
            "hooks": {
                "Stop": [{"hooks": [{"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/script.sh"}]}]
            }
        }
        original_cmd = data["hooks"]["Stop"][0]["hooks"][0]["command"]

        integrator = HookIntegrator()
        rewritten, _ = integrator._rewrite_hooks_data(data, pkg_dir, "test", "vscode")

        # Original should be unchanged
        assert data["hooks"]["Stop"][0]["hooks"][0]["command"] == original_cmd
        # Rewritten should be different
        assert rewritten["hooks"]["Stop"][0]["hooks"][0]["command"] != original_cmd
