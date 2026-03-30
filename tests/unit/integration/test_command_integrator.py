"""Unit tests for CommandIntegrator.

Tests cover:
- Command file discovery
- Command integration during install (no metadata injection)
- Command cleanup during uninstall (nuke-and-regenerate via sync_integration)
- Removal of all APM command files
"""

import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock
from dataclasses import dataclass

import pytest
import frontmatter

from apm_cli.integration.command_integrator import CommandIntegrator


class TestCommandIntegratorSyncIntegration:
    """Tests for sync_integration method (nuke-and-regenerate)."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project with .claude/commands directory."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        
        # Create commands directory
        commands_dir = temp_path / ".claude" / "commands"
        commands_dir.mkdir(parents=True)
        
        yield temp_path
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sync_removes_all_apm_commands(self, temp_project):
        """Test that sync_integration removes all *-apm.md files."""
        commands_dir = temp_project / ".claude" / "commands"
        
        # Create command files for two packages
        pkg1_command = commands_dir / "audit-apm.md"
        pkg1_command.write_text("# Audit Command\n")
        
        pkg2_command = commands_dir / "review-apm.md"
        pkg2_command.write_text("# Review Command\n")
        
        integrator = CommandIntegrator()
        result = integrator.sync_integration(None, temp_project)
        
        assert result['files_removed'] == 2
        assert not pkg1_command.exists()
        assert not pkg2_command.exists()

    def test_sync_handles_empty_dependencies(self, temp_project):
        """Test sync removes all apm commands regardless of dependencies."""
        commands_dir = temp_project / ".claude" / "commands"
        
        command1 = commands_dir / "cmd1-apm.md"
        command1.write_text("# Command 1\n")
        
        command2 = commands_dir / "cmd2-apm.md"
        command2.write_text("# Command 2\n")
        
        mock_package = MagicMock()
        mock_package.dependencies = {'apm': []}
        
        integrator = CommandIntegrator()
        result = integrator.sync_integration(mock_package, temp_project)
        
        assert result['files_removed'] == 2
        assert not command1.exists()
        assert not command2.exists()

    def test_sync_ignores_non_apm_command_files(self, temp_project):
        """Test that sync_integration ignores command files without -apm suffix."""
        commands_dir = temp_project / ".claude" / "commands"
        
        # Create a non-APM command file (user-created)
        user_command = commands_dir / "my-custom-command.md"
        user_command.write_text("# My Custom Command\n")
        
        integrator = CommandIntegrator()
        result = integrator.sync_integration(None, temp_project)
        
        assert result['files_removed'] == 0
        assert user_command.exists()

    def test_sync_handles_nonexistent_commands_dir(self):
        """Test sync handles missing .claude/commands directory."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        
        try:
            integrator = CommandIntegrator()
            result = integrator.sync_integration(None, temp_path)
            assert result['files_removed'] == 0
            assert result['errors'] == 0
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sync_apm_package_param_is_unused(self, temp_project):
        """Test that sync works regardless of what apm_package is passed."""
        commands_dir = temp_project / ".claude" / "commands"
        
        cmd = commands_dir / "test-apm.md"
        cmd.write_text("# Test\n")
        
        integrator = CommandIntegrator()
        
        # Works with None
        result = integrator.sync_integration(None, temp_project)
        assert result['files_removed'] == 1


class TestRemovePackageCommands:
    """Tests for remove_package_commands method."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project with .claude/commands directory."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        
        commands_dir = temp_path / ".claude" / "commands"
        commands_dir.mkdir(parents=True)
        
        yield temp_path
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_removes_all_apm_commands(self, temp_project):
        """Test that remove_package_commands removes all *-apm.md files."""
        commands_dir = temp_project / ".claude" / "commands"
        
        cmd1 = commands_dir / "audit-apm.md"
        cmd1.write_text("# Audit\n")
        
        cmd2 = commands_dir / "review-apm.md"
        cmd2.write_text("# Review\n")
        
        cmd3 = commands_dir / "design-apm.md"
        cmd3.write_text("# Design\n")
        
        integrator = CommandIntegrator()
        removed = integrator.remove_package_commands("any/package", temp_project)
        
        assert removed == 3
        assert not cmd1.exists()
        assert not cmd2.exists()
        assert not cmd3.exists()

    def test_returns_zero_when_no_commands_dir(self, temp_project):
        """Test that remove_package_commands returns 0 when no commands directory exists."""
        shutil.rmtree(temp_project / ".claude" / "commands")
        
        integrator = CommandIntegrator()
        removed = integrator.remove_package_commands("any/package", temp_project)
        
        assert removed == 0

    def test_preserves_non_apm_files(self, temp_project):
        """Test that non-APM files are preserved."""
        commands_dir = temp_project / ".claude" / "commands"
        
        user_cmd = commands_dir / "my-command.md"
        user_cmd.write_text("# User command\n")
        
        apm_cmd = commands_dir / "test-apm.md"
        apm_cmd.write_text("# APM command\n")
        
        integrator = CommandIntegrator()
        removed = integrator.remove_package_commands("any/package", temp_project)
        
        assert removed == 1
        assert not apm_cmd.exists()
        assert user_cmd.exists()


class TestIntegrateCommandNoMetadata:
    """Tests that integrate_command does NOT inject APM metadata."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project with source and target dirs."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        
        (temp_path / "source").mkdir()
        (temp_path / ".claude" / "commands").mkdir(parents=True)
        
        yield temp_path
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_no_apm_metadata_in_output(self, temp_project):
        """Test that integrated command files contain no APM metadata block."""
        source = temp_project / "source" / "audit.prompt.md"
        source.write_text("""---
description: Run audit checks
---
# Audit Command
Run compliance audit.
""")
        
        target = temp_project / ".claude" / "commands" / "audit-apm.md"
        
        mock_info = MagicMock()
        mock_info.package.name = "test/pkg"
        mock_info.package.version = "1.0.0"
        mock_info.package.source = "https://github.com/test/pkg"
        mock_info.resolved_reference = None
        mock_info.install_path = temp_project / "source"
        mock_info.installed_at = "2024-01-01"
        mock_info.get_canonical_dependency_string.return_value = "test/pkg"
        
        integrator = CommandIntegrator()
        integrator.integrate_command(source, target, mock_info, source)
        
        # Verify no APM metadata
        post = frontmatter.load(target)
        assert 'apm' not in post.metadata
        
        # Verify legitimate metadata IS preserved
        assert post.metadata.get('description') == 'Run audit checks'

    def test_content_preserved_verbatim(self, temp_project):
        """Test that command content is preserved without modification."""
        content = "# My Command\nDo something useful.\n\n## Steps\n1. First\n2. Second"
        source = temp_project / "source" / "test.prompt.md"
        source.write_text(f"---\ndescription: Test\n---\n{content}\n")
        
        target = temp_project / ".claude" / "commands" / "test-apm.md"
        
        mock_info = MagicMock()
        mock_info.resolved_reference = None
        
        integrator = CommandIntegrator()
        integrator.integrate_command(source, target, mock_info, source)
        
        post = frontmatter.load(target)
        assert content in post.content

    def test_claude_metadata_mapping(self, temp_project):
        """Test that Claude-specific frontmatter fields are mapped correctly."""
        source = temp_project / "source" / "cmd.prompt.md"
        source.write_text("""---
description: A command
allowed-tools: ["bash", "edit"]
model: claude-sonnet
argument-hint: "file path"
---
# Command
""")
        
        target = temp_project / ".claude" / "commands" / "cmd-apm.md"
        
        mock_info = MagicMock()
        mock_info.resolved_reference = None
        
        integrator = CommandIntegrator()
        integrator.integrate_command(source, target, mock_info, source)
        
        post = frontmatter.load(target)
        assert post.metadata['description'] == 'A command'
        assert post.metadata['allowed-tools'] == ['bash', 'edit']
        assert post.metadata['model'] == 'claude-sonnet'
        assert post.metadata['argument-hint'] == 'file path'
        assert 'apm' not in post.metadata


class TestOpenCodeCommandIntegration:
    """Tests for OpenCode command integration."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project with .opencode/ directory."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        (temp_path / ".opencode").mkdir()
        yield temp_path
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def temp_project_no_opencode(self):
        """Create a temporary project without .opencode/ directory."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        yield temp_path
        shutil.rmtree(temp_dir, ignore_errors=True)

    def _make_package(self, project_root, prompts):
        """Create a package with .prompt.md files and return PackageInfo."""
        pkg_dir = project_root / "apm_modules" / "test-pkg"
        pkg_dir.mkdir(parents=True)
        prompts_dir = pkg_dir / ".apm" / "prompts"
        prompts_dir.mkdir(parents=True)
        for name, content in prompts.items():
            (prompts_dir / name).write_text(content)

        mock_info = MagicMock()
        mock_info.install_path = pkg_dir
        mock_info.resolved_reference = None
        mock_info.package = MagicMock()
        mock_info.package.name = "test-pkg"
        return mock_info

    def test_skips_when_opencode_dir_missing(self, temp_project_no_opencode):
        """Opt-in: skip if .opencode/ does not exist."""
        pkg_info = self._make_package(
            temp_project_no_opencode,
            {"test.prompt.md": "---\ndescription: Test\n---\n# Test"},
        )
        integrator = CommandIntegrator()
        result = integrator.integrate_package_commands_opencode(
            pkg_info, temp_project_no_opencode
        )
        assert result.files_integrated == 0
        assert not (temp_project_no_opencode / ".opencode" / "commands").exists()

    def test_deploys_prompts_to_opencode_commands(self, temp_project):
        """Deploy .prompt.md → .opencode/commands/<name>.md."""
        pkg_info = self._make_package(
            temp_project,
            {"test.prompt.md": "---\ndescription: A test\n---\n# Test command"},
        )
        integrator = CommandIntegrator()
        result = integrator.integrate_package_commands_opencode(
            pkg_info, temp_project
        )
        assert result.files_integrated == 1
        target = temp_project / ".opencode" / "commands" / "test.md"
        assert target.exists()

    def test_deploys_multiple_prompts(self, temp_project):
        """Deploy multiple prompts to .opencode/commands/."""
        pkg_info = self._make_package(
            temp_project,
            {
                "review.prompt.md": "---\ndescription: Review\n---\n# Review",
                "fix.prompt.md": "---\ndescription: Fix\n---\n# Fix",
            },
        )
        integrator = CommandIntegrator()
        result = integrator.integrate_package_commands_opencode(
            pkg_info, temp_project
        )
        assert result.files_integrated == 2

    def test_sync_removes_apm_commands(self, temp_project):
        """Sync removes APM-managed commands from .opencode/commands/."""
        cmds = temp_project / ".opencode" / "commands"
        cmds.mkdir(parents=True)
        (cmds / "test-apm.md").write_text("# APM managed")
        (cmds / "custom.md").write_text("# User created")

        integrator = CommandIntegrator()
        result = integrator.sync_integration_opencode(None, temp_project)

        assert result["files_removed"] == 1
        assert not (cmds / "test-apm.md").exists()
        assert (cmds / "custom.md").exists()

    def test_sync_handles_missing_dir(self, temp_project_no_opencode):
        """Sync handles missing .opencode/commands/ gracefully."""
        integrator = CommandIntegrator()
        result = integrator.sync_integration_opencode(None, temp_project_no_opencode)
        assert result["files_removed"] == 0


class TestIntegratePackagePrimitivesTargetGating:
    """Tests that _integrate_package_primitives respects the integrate_claude flag.

    Regression test for: CommandIntegrator was called unconditionally, causing
    .claude/commands/ to be created even when target=copilot (integrate_claude=False).
    """

    def _make_mock_integrators(self):
        """Return a dict of MagicMock integrators for _integrate_package_primitives."""
        from unittest.mock import MagicMock

        def _empty_result(*args, **kwargs):
            r = MagicMock()
            r.files_integrated = 0
            r.files_updated = 0
            r.links_resolved = 0
            r.target_paths = []
            r.skill_created = False
            r.sub_skills_promoted = 0
            r.hooks_integrated = 0
            return r

        integrators = {}
        for name in (
            "prompt_integrator",
            "agent_integrator",
            "skill_integrator",
            "instruction_integrator",
            "command_integrator",
            "hook_integrator",
        ):
            m = MagicMock()
            for method in (
                "integrate_package_prompts",
                "integrate_package_agents",
                "integrate_package_agents_claude",
                "integrate_package_agents_cursor",
                "integrate_package_agents_opencode",
                "integrate_package_skill",
                "integrate_package_instructions",
                "integrate_package_instructions_cursor",
                "integrate_package_commands",
                "integrate_package_commands_opencode",
                "integrate_package_hooks",
                "integrate_package_hooks_claude",
                "integrate_package_hooks_cursor",
            ):
                getattr(m, method).side_effect = _empty_result
            integrators[name] = m
        return integrators

    def test_integrate_claude_false_does_not_call_integrate_package_commands(self):
        """When integrate_claude=False, integrate_package_commands must not be called.

        This is the regression test for the bug where .claude/commands/ was created
        even when target=copilot (vscode) set integrate_claude=False.
        """
        import tempfile, shutil
        from apm_cli.commands.install import _integrate_package_primitives
        from apm_cli.utils.diagnostics import DiagnosticCollector

        temp_dir = tempfile.mkdtemp()
        try:
            project_root = Path(temp_dir)
            (project_root / ".github").mkdir()

            package_info = MagicMock()
            integrators = self._make_mock_integrators()
            diagnostics = DiagnosticCollector(verbose=False)

            _integrate_package_primitives(
                package_info,
                project_root,
                integrate_vscode=True,
                integrate_claude=False,
                integrate_opencode=False,
                managed_files=set(),
                force=False,
                diagnostics=diagnostics,
                **integrators,
            )

            integrators["command_integrator"].integrate_package_commands.assert_not_called()
            assert not (project_root / ".claude" / "commands").exists()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_integrate_claude_true_calls_integrate_package_commands(self):
        """When integrate_claude=True, integrate_package_commands must be called."""
        import tempfile, shutil
        from apm_cli.commands.install import _integrate_package_primitives
        from apm_cli.utils.diagnostics import DiagnosticCollector

        temp_dir = tempfile.mkdtemp()
        try:
            project_root = Path(temp_dir)
            (project_root / ".claude").mkdir()

            package_info = MagicMock()
            integrators = self._make_mock_integrators()
            diagnostics = DiagnosticCollector(verbose=False)

            _integrate_package_primitives(
                package_info,
                project_root,
                integrate_vscode=False,
                integrate_claude=True,
                integrate_opencode=False,
                managed_files=set(),
                force=False,
                diagnostics=diagnostics,
                **integrators,
            )

            integrators["command_integrator"].integrate_package_commands.assert_called_once()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_opencode_only_does_not_call_github_prompts_or_agents(self):
        """When only integrate_opencode=True, .github/ prompts and agents must not run.

        Regression test for: prompts and .github/agents were called unconditionally,
        creating .github/ even when --target opencode was set.
        """
        import tempfile, shutil
        from apm_cli.commands.install import _integrate_package_primitives
        from apm_cli.utils.diagnostics import DiagnosticCollector

        temp_dir = tempfile.mkdtemp()
        try:
            project_root = Path(temp_dir)
            (project_root / ".opencode").mkdir()

            package_info = MagicMock()
            integrators = self._make_mock_integrators()
            diagnostics = DiagnosticCollector(verbose=False)

            _integrate_package_primitives(
                package_info,
                project_root,
                integrate_vscode=False,
                integrate_claude=False,
                integrate_opencode=True,
                integrate_cursor=False,
                managed_files=set(),
                force=False,
                diagnostics=diagnostics,
                **integrators,
            )

            integrators["prompt_integrator"].integrate_package_prompts.assert_not_called()
            integrators["agent_integrator"].integrate_package_agents.assert_not_called()
            integrators["instruction_integrator"].integrate_package_instructions.assert_not_called()
            integrators["hook_integrator"].integrate_package_hooks.assert_not_called()
            assert not (project_root / ".github").exists()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_opencode_only_calls_opencode_agents_and_commands(self):
        """When only integrate_opencode=True, OpenCode agents and commands must run."""
        import tempfile, shutil
        from apm_cli.commands.install import _integrate_package_primitives
        from apm_cli.utils.diagnostics import DiagnosticCollector

        temp_dir = tempfile.mkdtemp()
        try:
            project_root = Path(temp_dir)
            (project_root / ".opencode").mkdir()

            package_info = MagicMock()
            integrators = self._make_mock_integrators()
            diagnostics = DiagnosticCollector(verbose=False)

            _integrate_package_primitives(
                package_info,
                project_root,
                integrate_vscode=False,
                integrate_claude=False,
                integrate_opencode=True,
                integrate_cursor=False,
                managed_files=set(),
                force=False,
                diagnostics=diagnostics,
                **integrators,
            )

            integrators["agent_integrator"].integrate_package_agents_opencode.assert_called_once()
            integrators["command_integrator"].integrate_package_commands_opencode.assert_called_once()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_cursor_only_does_not_call_github_or_claude_or_opencode(self):
        """When only integrate_cursor=True, only cursor-specific integrations run."""
        import tempfile, shutil
        from apm_cli.commands.install import _integrate_package_primitives
        from apm_cli.utils.diagnostics import DiagnosticCollector

        temp_dir = tempfile.mkdtemp()
        try:
            project_root = Path(temp_dir)
            (project_root / ".cursor").mkdir()

            package_info = MagicMock()
            integrators = self._make_mock_integrators()
            diagnostics = DiagnosticCollector(verbose=False)

            _integrate_package_primitives(
                package_info,
                project_root,
                integrate_vscode=False,
                integrate_claude=False,
                integrate_opencode=False,
                integrate_cursor=True,
                managed_files=set(),
                force=False,
                diagnostics=diagnostics,
                **integrators,
            )

            # .github/ integrations must NOT run
            integrators["prompt_integrator"].integrate_package_prompts.assert_not_called()
            integrators["agent_integrator"].integrate_package_agents.assert_not_called()
            integrators["instruction_integrator"].integrate_package_instructions.assert_not_called()
            integrators["hook_integrator"].integrate_package_hooks.assert_not_called()
            # Claude must NOT run
            integrators["command_integrator"].integrate_package_commands.assert_not_called()
            integrators["agent_integrator"].integrate_package_agents_claude.assert_not_called()
            integrators["hook_integrator"].integrate_package_hooks_claude.assert_not_called()
            # OpenCode must NOT run
            integrators["agent_integrator"].integrate_package_agents_opencode.assert_not_called()
            integrators["command_integrator"].integrate_package_commands_opencode.assert_not_called()
            # Cursor MUST run
            integrators["instruction_integrator"].integrate_package_instructions_cursor.assert_called_once()
            integrators["agent_integrator"].integrate_package_agents_cursor.assert_called_once()
            integrators["hook_integrator"].integrate_package_hooks_cursor.assert_called_once()
            assert not (project_root / ".github").exists()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_vscode_only_does_not_call_opencode_or_cursor(self):
        """When only integrate_vscode=True, OpenCode and Cursor integrations must not run."""
        import tempfile, shutil
        from apm_cli.commands.install import _integrate_package_primitives
        from apm_cli.utils.diagnostics import DiagnosticCollector

        temp_dir = tempfile.mkdtemp()
        try:
            project_root = Path(temp_dir)
            (project_root / ".github").mkdir()

            package_info = MagicMock()
            integrators = self._make_mock_integrators()
            diagnostics = DiagnosticCollector(verbose=False)

            _integrate_package_primitives(
                package_info,
                project_root,
                integrate_vscode=True,
                integrate_claude=False,
                integrate_opencode=False,
                integrate_cursor=False,
                managed_files=set(),
                force=False,
                diagnostics=diagnostics,
                **integrators,
            )

            # .github/ integrations MUST run
            integrators["prompt_integrator"].integrate_package_prompts.assert_called_once()
            integrators["agent_integrator"].integrate_package_agents.assert_called_once()
            integrators["instruction_integrator"].integrate_package_instructions.assert_called_once()
            integrators["hook_integrator"].integrate_package_hooks.assert_called_once()
            # OpenCode must NOT run
            integrators["agent_integrator"].integrate_package_agents_opencode.assert_not_called()
            integrators["command_integrator"].integrate_package_commands_opencode.assert_not_called()
            # Cursor must NOT run
            integrators["instruction_integrator"].integrate_package_instructions_cursor.assert_not_called()
            integrators["agent_integrator"].integrate_package_agents_cursor.assert_not_called()
            integrators["hook_integrator"].integrate_package_hooks_cursor.assert_not_called()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
