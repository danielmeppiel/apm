"""Tests for the apm init command."""

import pytest
import tempfile
import os
import yaml
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch

from apm_cli.cli import cli


class TestInitCommand:
    """Test cases for apm init command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        # Use a safe fallback directory if current directory is not accessible
        try:
            self.original_dir = os.getcwd()
        except FileNotFoundError:
            # If current directory doesn't exist, use the repo root
            self.original_dir = str(Path(__file__).parent.parent.parent)
            os.chdir(self.original_dir)

    def teardown_method(self):
        """Clean up after tests."""
        try:
            os.chdir(self.original_dir)
        except (FileNotFoundError, OSError):
            # If original directory doesn't exist anymore, go to repo root
            repo_root = Path(__file__).parent.parent.parent
            os.chdir(str(repo_root))

    def test_init_current_directory(self):
        """Test initialization in current directory (minimal mode)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)

            result = self.runner.invoke(cli, ["init", "--yes"])

            assert result.exit_code == 0
            assert "APM project initialized successfully!" in result.output
            assert Path("apm.yml").exists()
            # Minimal mode: no template files created
            assert not Path("hello-world.prompt.md").exists()
            assert not Path("README.md").exists()
            assert not Path(".apm").exists()

    def test_init_explicit_current_directory(self):
        """Test initialization with explicit '.' argument (minimal mode)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)

            result = self.runner.invoke(cli, ["init", ".", "--yes"])

            assert result.exit_code == 0
            assert "APM project initialized successfully!" in result.output
            assert Path("apm.yml").exists()
            # Minimal mode: no template files created
            assert not Path("hello-world.prompt.md").exists()

    def test_init_new_directory(self):
        """Test initialization in new directory (minimal mode)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)

            result = self.runner.invoke(cli, ["init", "my-project", "--yes"])

            assert result.exit_code == 0
            assert "Created project directory: my-project" in result.output
            # Use absolute path to check files
            project_path = Path(tmp_dir) / "my-project"
            assert project_path.exists()
            assert project_path.is_dir()
            assert (project_path / "apm.yml").exists()
            # Minimal mode: no template files created
            assert not (project_path / "hello-world.prompt.md").exists()
            assert not (project_path / "README.md").exists()
            assert not (project_path / ".apm").exists()

    def test_init_existing_project_without_force(self):
        """Test initialization over existing apm.yml without --force (removed flag)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)

            # Create existing apm.yml
            Path("apm.yml").write_text("name: existing-project\nversion: 0.1.0\n")

            # Try to init without interactive confirmation (should prompt)
            result = self.runner.invoke(cli, ["init", "--yes"])

            assert result.exit_code == 0
            assert "apm.yml already exists" in result.output
            assert "--yes specified, overwriting apm.yml..." in result.output

    def test_init_existing_project_with_force(self):
        """Test initialization over existing apm.yml (--force flag removed, behavior same as --yes)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)

            # Create existing apm.yml
            Path("apm.yml").write_text("name: existing-project\nversion: 0.1.0\n")

            result = self.runner.invoke(cli, ["init", "--yes"])

            assert result.exit_code == 0
            assert "APM project initialized successfully!" in result.output
            # Should overwrite the file with minimal structure
            with open("apm.yml") as f:
                config = yaml.safe_load(f)
                # Minimal structure
                assert "dependencies" in config
                assert config["dependencies"] == {"apm": [], "mcp": []}
                assert "scripts" in config
                assert config["scripts"] == {}

    def test_init_preserves_existing_config(self):
        """Test that init with --yes overwrites existing apm.yml (no merge in minimal mode)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)

            # Create existing apm.yml with custom values
            existing_config = {
                "name": "my-custom-project",
                "version": "2.0.0",
                "description": "Custom description",
                "author": "Custom Author",
            }
            with open("apm.yml", "w") as f:
                yaml.dump(existing_config, f)

            result = self.runner.invoke(cli, ["init", "--yes"])

            assert result.exit_code == 0
            # Minimal mode: overwrites with auto-detected values
            assert "apm.yml already exists" in result.output

    def test_init_interactive_mode(self):
        """Test interactive mode with user input."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)

            # Simulate user input
            user_input = "my-test-project\n1.5.0\nTest description\nTest Author\ny\n"

            result = self.runner.invoke(cli, ["init"], input=user_input)

            assert result.exit_code == 0
            assert "Setting up your APM project" in result.output
            assert "Project name" in result.output
            assert "Version" in result.output
            assert "Description" in result.output
            assert "Author" in result.output

            # Verify the interactive values were applied to apm.yml
            with open("apm.yml") as f:
                config = yaml.safe_load(f)
                assert config["name"] == "my-test-project"
                assert config["version"] == "1.5.0"
                assert config["description"] == "Test description"
                assert config["author"] == "Test Author"

    def test_init_interactive_mode_abort(self):
        """Test aborting interactive mode."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)

            # Simulate user input with 'no' to confirmation
            user_input = "my-test-project\n1.5.0\nTest description\nTest Author\nn\n"

            result = self.runner.invoke(cli, ["init"], input=user_input)

            assert result.exit_code == 0
            assert "Aborted" in result.output
            assert not Path("apm.yml").exists()

    def test_init_existing_project_interactive_cancel(self):
        """Test cancelling when existing apm.yml detected in interactive mode."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)

            # Create existing apm.yml
            Path("apm.yml").write_text("name: existing-project\nversion: 0.1.0\n")

            # Simulate user saying 'no' to overwrite
            result = self.runner.invoke(cli, ["init"], input="n\n")

            assert result.exit_code == 0
            assert "apm.yml already exists" in result.output
            assert "Initialization cancelled" in result.output

    def test_init_validates_project_structure(self):
        """Test that init creates minimal project structure."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)

            result = self.runner.invoke(cli, ["init", "test-project", "--yes"])

            assert result.exit_code == 0

            # Use absolute path for checking files
            project_path = Path(tmp_dir) / "test-project"

            # Verify apm.yml minimal structure
            with open(project_path / "apm.yml") as f:
                config = yaml.safe_load(f)
                assert config["name"] == "test-project"
                assert "version" in config
                assert "dependencies" in config
                assert config["dependencies"] == {"apm": [], "mcp": []}
                assert "scripts" in config
                assert config["scripts"] == {}

            # Minimal mode: no template files created
            assert not (project_path / "hello-world.prompt.md").exists()
            assert not (project_path / "README.md").exists()
            assert not (project_path / ".apm").exists()

    def test_init_auto_detection(self):
        """Test auto-detection of project metadata."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)

            # Initialize git repo and set author
            import subprocess

            git_init = subprocess.run(["git", "init"], capture_output=True)
            assert git_init.returncode == 0, f"git init failed: {git_init.stderr}"

            git_config = subprocess.run(
                ["git", "config", "user.name", "Test User"], capture_output=True
            )
            assert (
                git_config.returncode == 0
            ), f"git config failed: {git_config.stderr}"

            result = self.runner.invoke(cli, ["init", "--yes"])

            assert result.exit_code == 0

            with open("apm.yml") as f:
                config = yaml.safe_load(f)
                # Should auto-detect author from git
                assert config["author"] == "Test User"
                # Should auto-detect description
                assert "APM project" in config["description"]

    def test_init_creates_skill_md(self):
        """Test that init creates SKILL.md alongside apm.yml."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)

            result = self.runner.invoke(cli, ["init", "--yes"])

            assert result.exit_code == 0
            assert Path("SKILL.md").exists()

    def test_init_skill_md_contains_frontmatter(self):
        """Test that SKILL.md contains proper YAML frontmatter."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)

            result = self.runner.invoke(cli, ["init", "--yes"])

            assert result.exit_code == 0
            
            skill_content = Path("SKILL.md").read_text()
            # Check frontmatter structure
            assert skill_content.startswith("---")
            assert "name:" in skill_content
            assert "description:" in skill_content
            # Frontmatter should be closed
            assert skill_content.count("---") >= 2

    def test_init_skill_md_reflects_project_name(self):
        """Test that SKILL.md reflects the project name and description."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)

            result = self.runner.invoke(cli, ["init", "my-awesome-package", "--yes"])

            assert result.exit_code == 0
            
            project_path = Path(tmp_dir) / "my-awesome-package"
            skill_content = (project_path / "SKILL.md").read_text()
            
            # Check project name appears in frontmatter and title
            assert "name: my-awesome-package" in skill_content
            assert "# my-awesome-package" in skill_content
            # Check install command uses project name
            assert "apm install your-org/my-awesome-package" in skill_content

    def test_init_skill_md_has_expected_sections(self):
        """Test that SKILL.md contains expected content sections."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)

            result = self.runner.invoke(cli, ["init", "--yes"])

            assert result.exit_code == 0
            
            skill_content = Path("SKILL.md").read_text()
            
            # Check for expected sections
            assert "## What This Package Does" in skill_content
            assert "## Getting Started" in skill_content
            assert "## Available Primitives" in skill_content
            # Check primitive types are listed
            assert "Instructions" in skill_content
            assert "Prompts" in skill_content
            assert "Agents" in skill_content

    def test_init_interactive_creates_skill_md_with_custom_values(self):
        """Test that interactive mode creates SKILL.md with user-provided values."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)

            # Simulate user input
            user_input = "custom-project\n1.0.0\nMy custom description\nTest Author\ny\n"

            result = self.runner.invoke(cli, ["init"], input=user_input)

            assert result.exit_code == 0
            assert Path("SKILL.md").exists()
            
            skill_content = Path("SKILL.md").read_text()
            
            # Check custom values appear
            assert "name: custom-project" in skill_content
            assert "description: My custom description" in skill_content
            assert "# custom-project" in skill_content
            assert "My custom description" in skill_content
