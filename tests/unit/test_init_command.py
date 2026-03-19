"""Tests for the apm init command."""

import json
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
            try:

                result = self.runner.invoke(cli, ["init", "--yes"])

                assert result.exit_code == 0
                assert "APM project initialized successfully!" in result.output
                assert Path("apm.yml").exists()
                # Minimal mode: no template files created
                assert not Path("hello-world.prompt.md").exists()
                assert not Path("README.md").exists()
                assert not Path(".apm").exists()
            finally:
                os.chdir(self.original_dir)  # restore CWD before TemporaryDirectory cleanup

    def test_init_explicit_current_directory(self):
        """Test initialization with explicit '.' argument (minimal mode)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:

                result = self.runner.invoke(cli, ["init", ".", "--yes"])

                assert result.exit_code == 0
                assert "APM project initialized successfully!" in result.output
                assert Path("apm.yml").exists()
                # Minimal mode: no template files created
                assert not Path("hello-world.prompt.md").exists()
            finally:
                os.chdir(self.original_dir)  # restore CWD before TemporaryDirectory cleanup

    def test_init_new_directory(self):
        """Test initialization in new directory (minimal mode)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:

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
            finally:
                os.chdir(self.original_dir)  # restore CWD before TemporaryDirectory cleanup

    def test_init_existing_project_without_force(self):
        """Test initialization over existing apm.yml without --force (removed flag)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:

                # Create existing apm.yml
                Path("apm.yml").write_text("name: existing-project\nversion: 0.1.0\n")

                # Try to init without interactive confirmation (should prompt)
                result = self.runner.invoke(cli, ["init", "--yes"])

                assert result.exit_code == 0
                assert "apm.yml already exists" in result.output
                assert "--yes specified, overwriting apm.yml..." in result.output
            finally:
                os.chdir(self.original_dir)  # restore CWD before TemporaryDirectory cleanup

    def test_init_existing_project_with_force(self):
        """Test initialization over existing apm.yml (--force flag removed, behavior same as --yes)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:

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
            finally:
                os.chdir(self.original_dir)  # restore CWD before TemporaryDirectory cleanup

    def test_init_preserves_existing_config(self):
        """Test that init with --yes overwrites existing apm.yml (no merge in minimal mode)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:

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
            finally:
                os.chdir(self.original_dir)  # restore CWD before TemporaryDirectory cleanup

    def test_init_interactive_mode(self):
        """Test interactive mode with user input."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:

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
            finally:
                os.chdir(self.original_dir)  # restore CWD before TemporaryDirectory cleanup

    def test_init_interactive_mode_abort(self):
        """Test aborting interactive mode."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:

                # Simulate user input with 'no' to confirmation
                user_input = "my-test-project\n1.5.0\nTest description\nTest Author\nn\n"

                result = self.runner.invoke(cli, ["init"], input=user_input)

                assert result.exit_code == 0
                assert "Aborted" in result.output
                assert not Path("apm.yml").exists()
            finally:
                os.chdir(self.original_dir)  # restore CWD before TemporaryDirectory cleanup

    def test_init_existing_project_interactive_cancel(self):
        """Test cancelling when existing apm.yml detected in interactive mode."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:

                # Create existing apm.yml
                Path("apm.yml").write_text("name: existing-project\nversion: 0.1.0\n")

                # Simulate user saying 'no' to overwrite
                result = self.runner.invoke(cli, ["init"], input="n\n")

                assert result.exit_code == 0
                assert "apm.yml already exists" in result.output
                assert "Initialization cancelled" in result.output
            finally:
                os.chdir(self.original_dir)  # restore CWD before TemporaryDirectory cleanup

    def test_init_validates_project_structure(self):
        """Test that init creates minimal project structure."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:

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
            finally:
                os.chdir(self.original_dir)  # restore CWD before TemporaryDirectory cleanup

    def test_init_auto_detection(self):
        """Test auto-detection of project metadata."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:

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
            finally:
                os.chdir(self.original_dir)  # restore CWD before TemporaryDirectory cleanup

    def test_init_does_not_create_skill_md(self):
        """Test that init does not create SKILL.md (only apm.yml)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:

                result = self.runner.invoke(cli, ["init", "--yes"])

                assert result.exit_code == 0
                assert Path("apm.yml").exists()
                assert not Path("SKILL.md").exists()
            finally:
                os.chdir(self.original_dir)  # restore CWD before TemporaryDirectory cleanup


class TestInitPluginFlag:
    """Test cases for apm init --plugin."""

    def setup_method(self):
        self.runner = CliRunner()
        try:
            self.original_dir = os.getcwd()
        except FileNotFoundError:
            self.original_dir = str(Path(__file__).parent.parent.parent)
            os.chdir(self.original_dir)

    def teardown_method(self):
        try:
            os.chdir(self.original_dir)
        except (FileNotFoundError, OSError):
            repo_root = Path(__file__).parent.parent.parent
            os.chdir(str(repo_root))

    def test_plugin_creates_both_files(self):
        """Test --plugin creates plugin.json and apm.yml, nothing else."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "my-plugin"
            project_dir.mkdir()
            os.chdir(project_dir)
            try:
                result = self.runner.invoke(cli, ["init", "--plugin", "--yes"])

                assert result.exit_code == 0, result.output
                assert Path("apm.yml").exists()
                assert Path("plugin.json").exists()
                assert not Path("SKILL.md").exists()
            finally:
                os.chdir(self.original_dir)

    def test_plugin_json_structure(self):
        """Test plugin.json has correct schema."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "my-plugin"
            project_dir.mkdir()
            os.chdir(project_dir)
            try:
                result = self.runner.invoke(cli, ["init", "--plugin", "--yes"])
                assert result.exit_code == 0, result.output

                with open("plugin.json") as f:
                    data = json.load(f)

                assert data["name"] == "my-plugin"
                assert data["version"] == "0.1.0"
                assert isinstance(data["description"], str)
                assert isinstance(data["author"], dict)
                assert "name" in data["author"]
                assert data["license"] == "MIT"
            finally:
                os.chdir(self.original_dir)

    def test_plugin_json_trailing_newline(self):
        """Test plugin.json ends with a newline."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "my-plugin"
            project_dir.mkdir()
            os.chdir(project_dir)
            try:
                self.runner.invoke(cli, ["init", "--plugin", "--yes"])
                raw = Path("plugin.json").read_text()
                assert raw.endswith("\n")
            finally:
                os.chdir(self.original_dir)

    def test_plugin_apm_yml_has_dev_dependencies(self):
        """Test apm.yml includes devDependencies when --plugin."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "my-plugin"
            project_dir.mkdir()
            os.chdir(project_dir)
            try:
                result = self.runner.invoke(cli, ["init", "--plugin", "--yes"])
                assert result.exit_code == 0, result.output

                with open("apm.yml") as f:
                    config = yaml.safe_load(f)

                assert "devDependencies" in config
                assert config["devDependencies"] == {"apm": []}
                assert config["dependencies"] == {"apm": [], "mcp": []}
                assert config["scripts"] == {}
            finally:
                os.chdir(self.original_dir)

    def test_plugin_with_project_name_arg(self):
        """Test --plugin with explicit project_name argument."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                result = self.runner.invoke(cli, ["init", "cool-plugin", "--plugin", "--yes"])

                assert result.exit_code == 0, result.output
                project_path = Path(tmp_dir) / "cool-plugin"
                assert (project_path / "apm.yml").exists()
                assert (project_path / "plugin.json").exists()

                with open(project_path / "plugin.json") as f:
                    data = json.load(f)
                assert data["name"] == "cool-plugin"
            finally:
                os.chdir(self.original_dir)

    def test_plugin_name_validation_rejects_uppercase(self):
        """Test that uppercase names are rejected for plugins."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "MyPlugin"
            project_dir.mkdir()
            os.chdir(project_dir)
            try:
                result = self.runner.invoke(cli, ["init", "--plugin", "--yes"])

                assert result.exit_code != 0
                assert "Invalid plugin name" in result.output
            finally:
                os.chdir(self.original_dir)

    def test_plugin_name_validation_rejects_underscores(self):
        """Test that underscores are rejected for plugins."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "my_plugin"
            project_dir.mkdir()
            os.chdir(project_dir)
            try:
                result = self.runner.invoke(cli, ["init", "--plugin", "--yes"])

                assert result.exit_code != 0
                assert "Invalid plugin name" in result.output
            finally:
                os.chdir(self.original_dir)

    def test_plugin_name_validation_rejects_start_with_number(self):
        """Test names starting with numbers are rejected."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "1plugin"
            project_dir.mkdir()
            os.chdir(project_dir)
            try:
                result = self.runner.invoke(cli, ["init", "--plugin", "--yes"])

                assert result.exit_code != 0
                assert "Invalid plugin name" in result.output
            finally:
                os.chdir(self.original_dir)

    def test_plugin_name_validation_accepts_valid_kebab(self):
        """Test valid kebab-case names are accepted."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "my-cool-plugin-v2"
            project_dir.mkdir()
            os.chdir(project_dir)
            try:
                result = self.runner.invoke(cli, ["init", "--plugin", "--yes"])
                assert result.exit_code == 0, result.output
            finally:
                os.chdir(self.original_dir)

    def test_plugin_shows_plugin_next_steps(self):
        """Test --plugin shows plugin-specific next steps."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "my-plugin"
            project_dir.mkdir()
            os.chdir(project_dir)
            try:
                result = self.runner.invoke(cli, ["init", "--plugin", "--yes"])
                assert result.exit_code == 0, result.output
                assert "apm pack" in result.output
            finally:
                os.chdir(self.original_dir)

    def test_plugin_does_not_create_empty_dirs(self):
        """Test --plugin creates only files, no empty directories."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "my-plugin"
            project_dir.mkdir()
            os.chdir(project_dir)
            try:
                self.runner.invoke(cli, ["init", "--plugin", "--yes"])
                entries = list(project_dir.iterdir())
                file_names = {e.name for e in entries}
                assert file_names == {"apm.yml", "plugin.json"}
            finally:
                os.chdir(self.original_dir)

    def test_regular_init_no_dev_dependencies(self):
        """Test that regular init (no --plugin) does NOT add devDependencies."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                result = self.runner.invoke(cli, ["init", "--yes"])
                assert result.exit_code == 0

                with open("apm.yml") as f:
                    config = yaml.safe_load(f)
                assert "devDependencies" not in config
            finally:
                os.chdir(self.original_dir)

    def test_plugin_version_is_0_1_0(self):
        """Test --plugin --yes uses 0.1.0 as default version."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "my-plugin"
            project_dir.mkdir()
            os.chdir(project_dir)
            try:
                self.runner.invoke(cli, ["init", "--plugin", "--yes"])

                with open("apm.yml") as f:
                    config = yaml.safe_load(f)
                assert config["version"] == "0.1.0"

                with open("plugin.json") as f:
                    data = json.load(f)
                assert data["version"] == "0.1.0"
            finally:
                os.chdir(self.original_dir)


class TestPluginNameValidation:
    """Unit tests for _validate_plugin_name helper."""

    def test_valid_names(self):
        from apm_cli.commands._helpers import _validate_plugin_name

        assert _validate_plugin_name("a") is True
        assert _validate_plugin_name("my-plugin") is True
        assert _validate_plugin_name("plugin2") is True
        assert _validate_plugin_name("a" * 64) is True

    def test_invalid_names(self):
        from apm_cli.commands._helpers import _validate_plugin_name

        assert _validate_plugin_name("") is False
        assert _validate_plugin_name("A") is False
        assert _validate_plugin_name("my_plugin") is False
        assert _validate_plugin_name("1plugin") is False
        assert _validate_plugin_name("-plugin") is False
        assert _validate_plugin_name("a" * 65) is False
        assert _validate_plugin_name("My-Plugin") is False
