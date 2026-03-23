"""Tests for target detection module."""

from apm_cli.core.target_detection import (
    detect_target,
    should_integrate_vscode,
    should_integrate_claude,
    should_integrate_cursor,
    should_integrate_opencode,
    should_compile_agents_md,
    should_compile_claude_md,
    get_target_description,
)


class TestDetectTarget:
    """Tests for detect_target function."""

    def test_explicit_target_vscode_wins(self, tmp_path):
        """Explicit --target vscode always wins."""
        # Create both folders - should still use explicit
        (tmp_path / ".github").mkdir()
        (tmp_path / ".claude").mkdir()
        
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target="vscode",
            config_target="claude",
        )
        
        assert target == "vscode"
        assert reason == "explicit --target flag"

    def test_explicit_target_copilot_maps_to_vscode(self, tmp_path):
        """Explicit --target copilot maps to vscode."""
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target="copilot",
        )
        
        assert target == "vscode"
        assert reason == "explicit --target flag"

    def test_explicit_target_agents_maps_to_vscode(self, tmp_path):
        """Explicit --target agents maps to vscode."""
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target="agents",
        )
        
        assert target == "vscode"
        assert reason == "explicit --target flag"

    def test_explicit_target_claude_wins(self, tmp_path):
        """Explicit --target claude always wins."""
        (tmp_path / ".github").mkdir()
        
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target="claude",
        )
        
        assert target == "claude"
        assert reason == "explicit --target flag"

    def test_explicit_target_all_wins(self, tmp_path):
        """Explicit --target all always wins."""
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target="all",
        )
        
        assert target == "all"
        assert reason == "explicit --target flag"

    def test_config_target_copilot(self, tmp_path):
        """Config target copilot maps to vscode."""
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target=None,
            config_target="copilot",
        )
        
        assert target == "vscode"
        assert reason == "apm.yml target"

    def test_config_target_vscode(self, tmp_path):
        """Config target vscode is used when no explicit target."""
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target=None,
            config_target="vscode",
        )
        
        assert target == "vscode"
        assert reason == "apm.yml target"

    def test_config_target_claude(self, tmp_path):
        """Config target claude is used when no explicit target."""
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target=None,
            config_target="claude",
        )
        
        assert target == "claude"
        assert reason == "apm.yml target"

    def test_config_target_all(self, tmp_path):
        """Config target all is used when no explicit target."""
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target=None,
            config_target="all",
        )
        
        assert target == "all"
        assert reason == "apm.yml target"

    def test_auto_detect_github_only(self, tmp_path):
        """Auto-detect vscode when only .github/ exists."""
        (tmp_path / ".github").mkdir()
        
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target=None,
            config_target=None,
        )
        
        assert target == "vscode"
        assert "detected .github/ folder" in reason

    def test_auto_detect_claude_only(self, tmp_path):
        """Auto-detect claude when only .claude/ exists."""
        (tmp_path / ".claude").mkdir()
        
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target=None,
            config_target=None,
        )
        
        assert target == "claude"
        assert "detected .claude/ folder" in reason

    def test_auto_detect_both_folders(self, tmp_path):
        """Auto-detect all when both folders exist."""
        (tmp_path / ".github").mkdir()
        (tmp_path / ".claude").mkdir()
        
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target=None,
            config_target=None,
        )
        
        assert target == "all"
        assert ".github/" in reason and ".claude/" in reason

    def test_auto_detect_neither_folder(self, tmp_path):
        """Auto-detect minimal when neither folder exists."""
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target=None,
            config_target=None,
        )
        
        assert target == "minimal"
        assert "no .github/" in reason


class TestShouldIntegrateVscode:
    """Tests for should_integrate_vscode function."""

    def test_vscode_target(self):
        """VSCode integration enabled for vscode target."""
        assert should_integrate_vscode("vscode") is True

    def test_all_target(self):
        """VSCode integration enabled for all target."""
        assert should_integrate_vscode("all") is True

    def test_claude_target(self):
        """VSCode integration disabled for claude target."""
        assert should_integrate_vscode("claude") is False

    def test_minimal_target(self):
        """VSCode integration disabled for minimal target."""
        assert should_integrate_vscode("minimal") is False


class TestShouldIntegrateClaude:
    """Tests for should_integrate_claude function."""

    def test_claude_target(self):
        """Claude integration enabled for claude target."""
        assert should_integrate_claude("claude") is True

    def test_all_target(self):
        """Claude integration enabled for all target."""
        assert should_integrate_claude("all") is True

    def test_vscode_target(self):
        """Claude integration disabled for vscode target."""
        assert should_integrate_claude("vscode") is False

    def test_minimal_target(self):
        """Claude integration disabled for minimal target."""
        assert should_integrate_claude("minimal") is False


class TestShouldCompileAgentsMd:
    """Tests for should_compile_agents_md function."""

    def test_vscode_target(self):
        """AGENTS.md compiled for vscode target."""
        assert should_compile_agents_md("vscode") is True

    def test_all_target(self):
        """AGENTS.md compiled for all target."""
        assert should_compile_agents_md("all") is True

    def test_minimal_target(self):
        """AGENTS.md compiled for minimal target (universal format)."""
        assert should_compile_agents_md("minimal") is True

    def test_claude_target(self):
        """AGENTS.md not compiled for claude target."""
        assert should_compile_agents_md("claude") is False


class TestShouldCompileClaudeMd:
    """Tests for should_compile_claude_md function."""

    def test_claude_target(self):
        """CLAUDE.md compiled for claude target."""
        assert should_compile_claude_md("claude") is True

    def test_all_target(self):
        """CLAUDE.md compiled for all target."""
        assert should_compile_claude_md("all") is True

    def test_vscode_target(self):
        """CLAUDE.md not compiled for vscode target."""
        assert should_compile_claude_md("vscode") is False

    def test_minimal_target(self):
        """CLAUDE.md not compiled for minimal target."""
        assert should_compile_claude_md("minimal") is False


class TestGetTargetDescription:
    """Tests for get_target_description function."""

    def test_copilot_description(self):
        """Description for copilot target."""
        desc = get_target_description("copilot")
        assert "AGENTS.md" in desc
        assert ".github/" in desc

    def test_vscode_description(self):
        """Description for vscode target."""
        desc = get_target_description("vscode")
        assert "AGENTS.md" in desc
        assert ".github/" in desc

    def test_claude_description(self):
        """Description for claude target."""
        desc = get_target_description("claude")
        assert "CLAUDE.md" in desc
        assert ".claude/" in desc

    def test_all_description(self):
        """Description for all target."""
        desc = get_target_description("all")
        assert "AGENTS.md" in desc
        assert "CLAUDE.md" in desc

    def test_minimal_description(self):
        """Description for minimal target."""
        desc = get_target_description("minimal")
        assert "AGENTS.md only" in desc

    def test_opencode_description(self):
        """Description for opencode target."""
        desc = get_target_description("opencode")
        assert "AGENTS.md" in desc
        assert ".opencode/" in desc


class TestShouldIntegrateCursor:
    """Tests for should_integrate_cursor function."""

    def test_cursor_target(self):
        """Cursor integration enabled for cursor target."""
        assert should_integrate_cursor("cursor") is True

    def test_all_target(self):
        """Cursor integration enabled for all target."""
        assert should_integrate_cursor("all") is True

    def test_vscode_target(self):
        """Cursor integration disabled for vscode target."""
        assert should_integrate_cursor("vscode") is False

    def test_claude_target(self):
        """Cursor integration disabled for claude target."""
        assert should_integrate_cursor("claude") is False

    def test_minimal_target(self):
        """Cursor integration disabled for minimal target."""
        assert should_integrate_cursor("minimal") is False


class TestShouldIntegrateOpencode:
    """Tests for should_integrate_opencode function."""

    def test_opencode_target(self):
        """OpenCode integration enabled for opencode target."""
        assert should_integrate_opencode("opencode") is True

    def test_all_target(self):
        """OpenCode integration enabled for all target."""
        assert should_integrate_opencode("all") is True

    def test_vscode_target(self):
        """OpenCode integration disabled for vscode target."""
        assert should_integrate_opencode("vscode") is False

    def test_claude_target(self):
        """OpenCode integration disabled for claude target."""
        assert should_integrate_opencode("claude") is False

    def test_minimal_target(self):
        """OpenCode integration disabled for minimal target."""
        assert should_integrate_opencode("minimal") is False


class TestDetectTargetCursor:
    """Tests for auto-detection and explicit cursor target."""

    def test_explicit_target_cursor(self, tmp_path):
        """Explicit --target cursor always wins."""
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target="cursor",
        )
        assert target == "cursor"
        assert reason == "explicit --target flag"

    def test_config_target_cursor(self, tmp_path):
        """Config target cursor is used when no explicit target."""
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target=None,
            config_target="cursor",
        )
        assert target == "cursor"
        assert reason == "apm.yml target"

    def test_auto_detect_cursor_only(self, tmp_path):
        """Auto-detect cursor when only .cursor/ exists."""
        (tmp_path / ".cursor").mkdir()
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target=None,
            config_target=None,
        )
        assert target == "cursor"
        assert ".cursor/" in reason

    def test_auto_detect_cursor_plus_github(self, tmp_path):
        """Auto-detect all when .cursor/ and .github/ exist."""
        (tmp_path / ".github").mkdir()
        (tmp_path / ".cursor").mkdir()
        target, _ = detect_target(
            project_root=tmp_path,
            explicit_target=None,
            config_target=None,
        )
        assert target == "all"

    def test_cursor_no_compile_agents_md(self):
        """Cursor target should NOT compile AGENTS.md (uses .cursor/agents/)."""
        assert should_compile_agents_md("cursor") is False

    def test_cursor_no_compile_claude_md(self):
        """Cursor target should NOT compile CLAUDE.md."""
        assert should_compile_claude_md("cursor") is False

    def test_cursor_description(self):
        """Description for cursor target."""
        desc = get_target_description("cursor")
        assert ".cursor/" in desc


class TestDetectTargetOpencode:
    """Tests for auto-detection of OpenCode folders."""

    def test_auto_detect_opencode_only(self, tmp_path):
        """Auto-detect opencode when only .opencode/ exists."""
        (tmp_path / ".opencode").mkdir()
        target, reason = detect_target(
            project_root=tmp_path,
            explicit_target=None,
            config_target=None,
        )
        assert target == "opencode"
        assert ".opencode/" in reason

    def test_auto_detect_opencode_plus_github(self, tmp_path):
        """Auto-detect all when .opencode/ and .github/ exist."""
        (tmp_path / ".github").mkdir()
        (tmp_path / ".opencode").mkdir()
        target, _ = detect_target(
            project_root=tmp_path,
            explicit_target=None,
            config_target=None,
        )
        assert target == "all"

    def test_opencode_compile_agents_md(self):
        """OpenCode target should compile AGENTS.md."""
        assert should_compile_agents_md("opencode") is True

    def test_opencode_no_compile_claude_md(self):
        """OpenCode target should NOT compile CLAUDE.md."""
        assert should_compile_claude_md("opencode") is False
