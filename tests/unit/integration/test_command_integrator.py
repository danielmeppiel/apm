"""Unit tests for CommandIntegrator.

Tests cover:
- Command file discovery
- Command integration during install
- Command cleanup during uninstall (sync_integration)
- Selective removal of commands for specific packages
"""

import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock
from dataclasses import dataclass

import pytest

from apm_cli.integration.command_integrator import CommandIntegrator


@dataclass
class MockDependencyReference:
    """Mock DependencyReference for testing."""
    repo_url: str
    host: str = "github.com"
    virtual_path: str = None
    is_virtual: bool = False
    
    def get_unique_key(self) -> str:
        """Get unique key matching DependencyReference behavior."""
        if self.is_virtual and self.virtual_path:
            return f"{self.repo_url}/{self.virtual_path}"
        return self.repo_url


class TestCommandIntegratorSyncIntegration:
    """Tests for sync_integration method."""

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

    def test_sync_removes_commands_from_uninstalled_packages(self, temp_project):
        """Test that sync_integration removes commands from uninstalled packages."""
        commands_dir = temp_project / ".claude" / "commands"
        
        # Create command files for two packages
        pkg1_command = commands_dir / "audit-apm.md"
        pkg1_command.write_text("""---
apm:
  source_dependency: danielmeppiel/compliance-rules
  version: 1.0.0
---
# Audit Command
""")
        
        pkg2_command = commands_dir / "review-apm.md"
        pkg2_command.write_text("""---
apm:
  source_dependency: danielmeppiel/design-guidelines
  version: 1.0.0
---
# Review Command
""")
        
        # Mock APMPackage with only design-guidelines remaining
        mock_package = MagicMock()
        mock_package.dependencies = {
            'apm': [MockDependencyReference(repo_url='danielmeppiel/design-guidelines')]
        }
        
        integrator = CommandIntegrator()
        result = integrator.sync_integration(mock_package, temp_project)
        
        # compliance-rules command should be removed
        assert result['files_removed'] == 1
        assert not pkg1_command.exists()
        
        # design-guidelines command should remain
        assert pkg2_command.exists()

    def test_sync_keeps_commands_for_installed_packages(self, temp_project):
        """Test that sync_integration keeps commands for still-installed packages."""
        commands_dir = temp_project / ".claude" / "commands"
        
        # Create command for a package
        command = commands_dir / "audit-apm.md"
        command.write_text("""---
apm:
  source_dependency: danielmeppiel/compliance-rules
  version: 1.0.0
---
# Audit Command
""")
        
        # Mock APMPackage with the package still installed
        mock_package = MagicMock()
        mock_package.dependencies = {
            'apm': [MockDependencyReference(repo_url='danielmeppiel/compliance-rules')]
        }
        
        integrator = CommandIntegrator()
        result = integrator.sync_integration(mock_package, temp_project)
        
        # Command should remain
        assert result['files_removed'] == 0
        assert command.exists()

    def test_sync_handles_empty_dependencies(self, temp_project):
        """Test sync with empty dependencies removes all commands."""
        commands_dir = temp_project / ".claude" / "commands"
        
        # Create command files
        command1 = commands_dir / "cmd1-apm.md"
        command1.write_text("""---
apm:
  source_dependency: org/pkg1
---
# Command 1
""")
        
        command2 = commands_dir / "cmd2-apm.md"
        command2.write_text("""---
apm:
  source_dependency: org/pkg2
---
# Command 2
""")
        
        # Mock APMPackage with no dependencies
        mock_package = MagicMock()
        mock_package.dependencies = {'apm': []}
        
        integrator = CommandIntegrator()
        result = integrator.sync_integration(mock_package, temp_project)
        
        # All commands should be removed
        assert result['files_removed'] == 2
        assert not command1.exists()
        assert not command2.exists()

    def test_sync_ignores_non_apm_command_files(self, temp_project):
        """Test that sync_integration ignores command files without -apm suffix."""
        commands_dir = temp_project / ".claude" / "commands"
        
        # Create a non-APM command file (user-created)
        user_command = commands_dir / "my-custom-command.md"
        user_command.write_text("""# My Custom Command
This is a user-created command that should not be touched.
""")
        
        # Mock APMPackage with no dependencies
        mock_package = MagicMock()
        mock_package.dependencies = {'apm': []}
        
        integrator = CommandIntegrator()
        result = integrator.sync_integration(mock_package, temp_project)
        
        # User command should not be touched
        assert result['files_removed'] == 0
        assert user_command.exists()

    def test_sync_handles_string_dependencies(self, temp_project):
        """Test that sync_integration handles string-type dependencies."""
        commands_dir = temp_project / ".claude" / "commands"
        
        command = commands_dir / "cmd-apm.md"
        command.write_text("""---
apm:
  source_dependency: org/package
---
# Command
""")
        
        # Mock APMPackage with string dependencies (legacy format)
        mock_package = MagicMock()
        mock_package.dependencies = {
            'apm': ['org/package']  # String, not DependencyReference
        }
        
        integrator = CommandIntegrator()
        result = integrator.sync_integration(mock_package, temp_project)
        
        # Command should remain (dependency still installed)
        assert result['files_removed'] == 0
        assert command.exists()

    def test_sync_keeps_virtual_package_commands(self, temp_project):
        """Test that sync_integration keeps commands from installed virtual packages."""
        commands_dir = temp_project / ".claude" / "commands"
        
        # Create a command from a virtual package (full path in source_dependency)
        command = commands_dir / "breakdown-plan-apm.md"
        command.write_text("""---
apm:
  source_dependency: github/awesome-copilot/prompts/breakdown-plan.prompt.md
---
# Breakdown Plan Command
""")
        
        # Mock APMPackage with virtual package installed
        mock_package = MagicMock()
        mock_package.dependencies = {
            'apm': [MockDependencyReference(
                repo_url='github/awesome-copilot',
                virtual_path='prompts/breakdown-plan.prompt.md',
                is_virtual=True
            )]
        }
        
        integrator = CommandIntegrator()
        result = integrator.sync_integration(mock_package, temp_project)
        
        # Virtual package is installed, command should remain
        assert result['files_removed'] == 0
        assert command.exists()

    def test_sync_removes_uninstalled_virtual_package_commands(self, temp_project):
        """Test that sync_integration removes commands from uninstalled virtual packages."""
        commands_dir = temp_project / ".claude" / "commands"
        
        # Create a command from a virtual package
        command = commands_dir / "breakdown-plan-apm.md"
        command.write_text("""---
apm:
  source_dependency: github/awesome-copilot/prompts/breakdown-plan.prompt.md
---
# Breakdown Plan Command
""")
        
        # Mock APMPackage with a DIFFERENT virtual package installed
        mock_package = MagicMock()
        mock_package.dependencies = {
            'apm': [MockDependencyReference(
                repo_url='github/awesome-copilot',
                virtual_path='prompts/other-prompt.prompt.md',
                is_virtual=True
            )]
        }
        
        integrator = CommandIntegrator()
        result = integrator.sync_integration(mock_package, temp_project)
        
        # Virtual package was uninstalled, command should be removed
        assert result['files_removed'] == 1
        assert not command.exists()

    def test_sync_mixed_regular_and_virtual_packages(self, temp_project):
        """Test sync with mix of regular and virtual packages."""
        commands_dir = temp_project / ".claude" / "commands"
        
        # Regular package command
        regular_cmd = commands_dir / "audit-apm.md"
        regular_cmd.write_text("""---
apm:
  source_dependency: danielmeppiel/compliance-rules
---
# Audit
""")
        
        # Virtual package command
        virtual_cmd = commands_dir / "breakdown-apm.md"
        virtual_cmd.write_text("""---
apm:
  source_dependency: github/awesome-copilot/prompts/breakdown.prompt.md
---
# Breakdown
""")
        
        # Mock APMPackage with both installed
        mock_package = MagicMock()
        mock_package.dependencies = {
            'apm': [
                MockDependencyReference(repo_url='danielmeppiel/compliance-rules'),
                MockDependencyReference(
                    repo_url='github/awesome-copilot',
                    virtual_path='prompts/breakdown.prompt.md',
                    is_virtual=True
                )
            ]
        }
        
        integrator = CommandIntegrator()
        result = integrator.sync_integration(mock_package, temp_project)
        
        # Both should remain
        assert result['files_removed'] == 0
        assert regular_cmd.exists()
        assert virtual_cmd.exists()


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

    def test_removes_only_specified_package_commands(self, temp_project):
        """Test that remove_package_commands only removes the specified package's commands."""
        commands_dir = temp_project / ".claude" / "commands"
        
        # Create commands from different packages
        pkg1_cmd1 = commands_dir / "audit-apm.md"
        pkg1_cmd1.write_text("""---
apm:
  source_dependency: danielmeppiel/compliance-rules
---
# Audit
""")
        
        pkg1_cmd2 = commands_dir / "review-apm.md"
        pkg1_cmd2.write_text("""---
apm:
  source_dependency: danielmeppiel/compliance-rules
---
# Review
""")
        
        pkg2_cmd = commands_dir / "design-apm.md"
        pkg2_cmd.write_text("""---
apm:
  source_dependency: danielmeppiel/design-guidelines
---
# Design
""")
        
        integrator = CommandIntegrator()
        removed = integrator.remove_package_commands("danielmeppiel/compliance-rules", temp_project)
        
        # Only compliance-rules commands should be removed
        assert removed == 2
        assert not pkg1_cmd1.exists()
        assert not pkg1_cmd2.exists()
        
        # design-guidelines command should remain
        assert pkg2_cmd.exists()

    def test_returns_zero_when_no_commands_dir(self, temp_project):
        """Test that remove_package_commands returns 0 when no commands directory exists."""
        # Remove the commands directory
        shutil.rmtree(temp_project / ".claude" / "commands")
        
        integrator = CommandIntegrator()
        removed = integrator.remove_package_commands("any/package", temp_project)
        
        assert removed == 0
