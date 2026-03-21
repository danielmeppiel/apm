"""Tests for the apm install command auto-bootstrap feature."""

import contextlib
import pytest
import tempfile
import os
import yaml
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from apm_cli.models.results import InstallResult

from apm_cli.cli import cli


class TestInstallCommandAutoBootstrap:
    """Test cases for apm install command auto-bootstrap feature."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        try:
            self.original_dir = os.getcwd()
        except FileNotFoundError:
            self.original_dir = str(Path(__file__).parent.parent.parent)
            os.chdir(self.original_dir)

    def teardown_method(self):
        """Clean up after tests."""
        try:
            os.chdir(self.original_dir)
        except (FileNotFoundError, OSError):
            repo_root = Path(__file__).parent.parent.parent
            os.chdir(str(repo_root))

    @contextlib.contextmanager
    def _chdir_tmp(self):
        """Context manager: create a temp dir, chdir into it, restore CWD on exit.

        Restoring CWD *before* TemporaryDirectory.__exit__ avoids
        PermissionError [WinError 32] on Windows when the process's current
        directory is inside the directory being deleted.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                os.chdir(tmp_dir)
                yield Path(tmp_dir)
            finally:
                os.chdir(self.original_dir)

    def test_install_no_apm_yml_no_packages_shows_helpful_error(self):
        """Test that install without apm.yml and without packages shows helpful error."""
        with self._chdir_tmp():
            result = self.runner.invoke(cli, ["install"])

            assert result.exit_code == 1
            assert "No apm.yml found" in result.output
            assert "apm init" in result.output
            assert "apm install <org/repo>" in result.output

    @patch("apm_cli.commands.install._validate_package_exists")
    @patch("apm_cli.commands.install.APM_DEPS_AVAILABLE", True)
    @patch("apm_cli.commands.install.APMPackage")
    @patch("apm_cli.commands.install._install_apm_dependencies")
    def test_install_no_apm_yml_with_packages_creates_minimal_apm_yml(
        self, mock_install_apm, mock_apm_package, mock_validate, monkeypatch
    ):
        """Test that install with packages but no apm.yml creates minimal apm.yml."""
        with self._chdir_tmp():
            # Mock package validation to return True
            mock_validate.return_value = True

            # Mock APMPackage to return empty dependencies
            mock_pkg_instance = MagicMock()
            mock_pkg_instance.get_apm_dependencies.return_value = [
                MagicMock(repo_url="test/package", reference="main")
            ]
            mock_pkg_instance.get_mcp_dependencies.return_value = []
            mock_apm_package.from_apm_yml.return_value = mock_pkg_instance

            # Mock the install function to avoid actual installation
            mock_install_apm.return_value = InstallResult(diagnostics=MagicMock(has_diagnostics=False, has_critical_security=False))

            result = self.runner.invoke(cli, ["install", "test/package"])
            assert result.exit_code == 0
            assert "Created apm.yml" in result.output
            assert Path("apm.yml").exists()

            # Verify apm.yml structure
            with open("apm.yml") as f:
                config = yaml.safe_load(f)
                assert "dependencies" in config
                assert "apm" in config["dependencies"]
                assert "test/package" in config["dependencies"]["apm"]
                assert config["dependencies"]["mcp"] == []

    @patch("apm_cli.commands.install._validate_package_exists")
    @patch("apm_cli.commands.install.APM_DEPS_AVAILABLE", True)
    @patch("apm_cli.commands.install.APMPackage")
    @patch("apm_cli.commands.install._install_apm_dependencies")
    def test_install_no_apm_yml_with_multiple_packages(
        self, mock_install_apm, mock_apm_package, mock_validate, monkeypatch
    ):
        """Test that install with multiple packages creates apm.yml and adds all."""
        with self._chdir_tmp():
            # Mock package validation
            mock_validate.return_value = True

            # Mock APMPackage
            mock_pkg_instance = MagicMock()
            mock_pkg_instance.get_apm_dependencies.return_value = [
                MagicMock(repo_url="org1/pkg1", reference="main"),
                MagicMock(repo_url="org2/pkg2", reference="main"),
            ]
            mock_pkg_instance.get_mcp_dependencies.return_value = []
            mock_apm_package.from_apm_yml.return_value = mock_pkg_instance

            mock_install_apm.return_value = InstallResult(diagnostics=MagicMock(has_diagnostics=False, has_critical_security=False))

            result = self.runner.invoke(cli, ["install", "org1/pkg1", "org2/pkg2"])

            assert result.exit_code == 0
            assert "Created apm.yml" in result.output
            assert Path("apm.yml").exists()

            # Verify both packages are in apm.yml
            with open("apm.yml") as f:
                config = yaml.safe_load(f)
                assert "org1/pkg1" in config["dependencies"]["apm"]
                assert "org2/pkg2" in config["dependencies"]["apm"]

    @patch("apm_cli.commands.install.APM_DEPS_AVAILABLE", True)
    @patch("apm_cli.commands.install.APMPackage")
    @patch("apm_cli.commands.install._install_apm_dependencies")
    def test_install_existing_apm_yml_preserves_behavior(
        self, mock_install_apm, mock_apm_package
    ):
        """Test that install with existing apm.yml works as before."""
        with self._chdir_tmp():
            # Create existing apm.yml
            existing_config = {
                "name": "test-project",
                "version": "1.0.0",
                "description": "Test project",
                "author": "Test Author",
                "dependencies": {"apm": [], "mcp": []},
                "scripts": {},
            }
            with open("apm.yml", "w") as f:
                yaml.dump(existing_config, f)

            # Mock APMPackage
            mock_pkg_instance = MagicMock()
            mock_pkg_instance.get_apm_dependencies.return_value = []
            mock_pkg_instance.get_mcp_dependencies.return_value = []
            mock_apm_package.from_apm_yml.return_value = mock_pkg_instance

            mock_install_apm.return_value = InstallResult(diagnostics=MagicMock(has_diagnostics=False, has_critical_security=False))

            result = self.runner.invoke(cli, ["install"])

            # Should succeed and NOT show "Created apm.yml"
            assert result.exit_code == 0
            assert "Created apm.yml" not in result.output

            # Verify original config is preserved
            with open("apm.yml") as f:
                config = yaml.safe_load(f)
                assert config["name"] == "test-project"
                assert config["author"] == "Test Author"

    @patch("apm_cli.commands.install._validate_package_exists")
    @patch("apm_cli.commands.install.APM_DEPS_AVAILABLE", True)
    @patch("apm_cli.commands.install.APMPackage")
    @patch("apm_cli.commands.install._install_apm_dependencies")
    def test_install_auto_created_apm_yml_has_correct_metadata(
        self, mock_install_apm, mock_apm_package, mock_validate
    ):
        """Test that auto-created apm.yml has correct metadata."""
        with self._chdir_tmp() as tmp_dir:
            # Create a directory with a specific name to test project name detection
            project_dir = tmp_dir / "my-awesome-project"
            project_dir.mkdir()
            os.chdir(project_dir)

            # Mock validation and installation
            mock_validate.return_value = True

            mock_pkg_instance = MagicMock()
            mock_pkg_instance.get_apm_dependencies.return_value = [
                MagicMock(repo_url="test/package", reference="main")
            ]
            mock_pkg_instance.get_mcp_dependencies.return_value = []
            mock_apm_package.from_apm_yml.return_value = mock_pkg_instance

            mock_install_apm.return_value = InstallResult(diagnostics=MagicMock(has_diagnostics=False, has_critical_security=False))

            result = self.runner.invoke(cli, ["install", "test/package"])

            assert result.exit_code == 0
            assert Path("apm.yml").exists()

            # Verify auto-detected project name
            with open("apm.yml") as f:
                config = yaml.safe_load(f)
                assert config["name"] == "my-awesome-project"
                assert "version" in config
                assert "description" in config
                assert "APM project" in config["description"]

    @patch("apm_cli.commands.install._validate_package_exists")
    def test_install_invalid_package_format_with_no_apm_yml(self, mock_validate):
        """Test that invalid package format fails gracefully even with auto-bootstrap."""
        with self._chdir_tmp():
            # Don't mock validation - let it handle invalid format
            result = self.runner.invoke(cli, ["install", "invalid-package"])

            # Should create apm.yml but fail to add invalid package
            assert Path("apm.yml").exists()
            assert "invalid format" in result.output

    @patch("apm_cli.commands.install._validate_package_exists")
    @patch("apm_cli.commands.install.APM_DEPS_AVAILABLE", True)
    @patch("apm_cli.commands.install.APMPackage")
    @patch("apm_cli.commands.install._install_apm_dependencies")
    def test_install_dry_run_with_no_apm_yml_shows_what_would_be_created(
        self, mock_install_apm, mock_apm_package, mock_validate
    ):
        """Test that dry-run with no apm.yml shows what would be created."""
        with self._chdir_tmp():
            mock_validate.return_value = True

            mock_pkg_instance = MagicMock()
            mock_pkg_instance.get_apm_dependencies.return_value = []
            mock_pkg_instance.get_mcp_dependencies.return_value = []
            mock_apm_package.from_apm_yml.return_value = mock_pkg_instance

            result = self.runner.invoke(cli, ["install", "test/package", "--dry-run"])

            # Should show what would be added
            assert result.exit_code == 0
            assert "Would add" in result.output or "Dry run" in result.output
            # apm.yml should still be created (for dry-run to work)
            assert Path("apm.yml").exists()


class TestValidationFailureReasonMessages:
    """Test that validation failure reasons include actionable auth guidance."""

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
            os.chdir(str(Path(__file__).parent.parent.parent))

    @contextlib.contextmanager
    def _chdir_tmp(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                os.chdir(tmp_dir)
                yield Path(tmp_dir)
            finally:
                os.chdir(self.original_dir)

    @patch("apm_cli.commands.install._validate_package_exists", return_value=False)
    def test_validation_failure_without_verbose_includes_verbose_hint(self, mock_validate):
        """When validation fails without --verbose, reason should suggest --verbose."""
        with self._chdir_tmp():
            # Create apm.yml so we exercise the validation path
            Path("apm.yml").write_text("name: test\ndependencies:\n  apm: []\n  mcp: []\n")
            result = self.runner.invoke(cli, ["install", "owner/repo"])
            # Normalize terminal line-wrapping before checking
            output = " ".join(result.output.split())
            assert "run with --verbose for auth details" in output

    @patch("apm_cli.commands.install._validate_package_exists", return_value=False)
    def test_validation_failure_with_verbose_omits_verbose_hint(self, mock_validate):
        """When validation fails with --verbose, reason should NOT suggest --verbose."""
        with self._chdir_tmp():
            Path("apm.yml").write_text("name: test\ndependencies:\n  apm: []\n  mcp: []\n")
            result = self.runner.invoke(cli, ["install", "owner/repo", "--verbose"])
            assert "not accessible or doesn't exist" in result.output
            assert "run with --verbose for auth details" not in result.output

    @patch("apm_cli.core.token_manager.GitHubTokenManager.resolve_credential_from_git", return_value=None)
    @patch("urllib.request.urlopen")
    def test_verbose_validation_failure_calls_build_error_context(self, mock_urlopen, _mock_cred):
        """When GitHub validation fails in verbose mode, build_error_context should be invoked."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.github.com/repos/owner/repo", code=404,
            msg="Not Found", hdrs={}, fp=None,
        )

        with patch.object(
            __import__("apm_cli.core.auth", fromlist=["AuthResolver"]).AuthResolver,
            "build_error_context",
            return_value="Authentication failed for accessing owner/repo on github.com.\nNo token available.",
        ) as mock_build_ctx:
            from apm_cli.commands.install import _validate_package_exists
            result = _validate_package_exists("owner/repo", verbose=True)
            assert result is False
            mock_build_ctx.assert_called_once()
            call_args = mock_build_ctx.call_args
            assert "github.com" in call_args[0][0]  # host
            assert "owner/repo" in call_args[0][1]  # operation


# ---------------------------------------------------------------------------
# Transitive dep parent chain breadcrumb
# ---------------------------------------------------------------------------


class TestTransitiveDepParentChain:
    """Tests for DependencyNode.get_ancestor_chain() breadcrumb."""

    def test_get_ancestor_chain_returns_breadcrumb(self):
        """get_ancestor_chain walks up parent links and returns 'a > b > c'."""
        from apm_cli.deps.dependency_graph import DependencyNode
        from apm_cli.models.apm_package import APMPackage, DependencyReference

        root_ref = DependencyReference.parse("acme/root-pkg")
        mid_ref = DependencyReference.parse("acme/mid-pkg")
        leaf_ref = DependencyReference.parse("other-org/leaf-pkg")

        root_node = DependencyNode(
            package=APMPackage(name="root-pkg", version="1.0", source="acme/root-pkg"),
            dependency_ref=root_ref,
            depth=1,
        )
        mid_node = DependencyNode(
            package=APMPackage(name="mid-pkg", version="1.0", source="acme/mid-pkg"),
            dependency_ref=mid_ref,
            depth=2,
            parent=root_node,
        )
        leaf_node = DependencyNode(
            package=APMPackage(name="leaf-pkg", version="1.0", source="other-org/leaf-pkg"),
            dependency_ref=leaf_ref,
            depth=3,
            parent=mid_node,
        )

        chain = leaf_node.get_ancestor_chain()
        assert chain == "acme/root-pkg > acme/mid-pkg > other-org/leaf-pkg"

    def test_get_ancestor_chain_single_node(self):
        """Direct dep (no parent) returns just its own name."""
        from apm_cli.deps.dependency_graph import DependencyNode
        from apm_cli.models.apm_package import APMPackage, DependencyReference

        ref = DependencyReference.parse("acme/direct-pkg")
        node = DependencyNode(
            package=APMPackage(name="direct-pkg", version="1.0", source="acme/direct-pkg"),
            dependency_ref=ref,
            depth=1,
        )
        chain = node.get_ancestor_chain()
        assert chain == "acme/direct-pkg"

    def test_get_ancestor_chain_root_node(self):
        """Root node (no parent) returns just the node's display name."""
        from apm_cli.deps.dependency_graph import DependencyNode
        from apm_cli.models.apm_package import APMPackage, DependencyReference

        ref = DependencyReference.parse("acme/root-pkg")
        node = DependencyNode(
            package=APMPackage(name="root-pkg", version="1.0", source="acme/root-pkg"),
            dependency_ref=ref,
            depth=0,
        )
        assert node.get_ancestor_chain() == "acme/root-pkg"

    def test_download_callback_includes_chain_in_error(self, tmp_path):
        """When a transitive dep download fails, the error message includes
        the parent chain breadcrumb for debugging.

        Tests the resolver + callback interaction directly: we create a
        resolver with a callback that fails on the leaf dep, and verify
        the parent_chain arg is passed through correctly.
        """
        from apm_cli.deps.apm_resolver import APMDependencyResolver
        from apm_cli.models.apm_package import APMPackage, DependencyReference

        # Set up apm_modules with root-pkg that declares leaf-pkg as dep
        modules_dir = tmp_path / "apm_modules"
        root_dir = modules_dir / "acme" / "root-pkg"
        root_dir.mkdir(parents=True)
        (root_dir / "apm.yml").write_text(yaml.safe_dump({
            "name": "root-pkg",
            "version": "1.0.0",
            "dependencies": {"apm": ["other-org/leaf-pkg"], "mcp": []},
        }))

        # Write root apm.yml that depends on root-pkg
        (tmp_path / "apm.yml").write_text(yaml.safe_dump({
            "name": "test-project",
            "version": "0.0.1",
            "dependencies": {"apm": ["acme/root-pkg"], "mcp": []},
        }))

        # Track what the callback receives
        callback_calls = []

        def tracking_callback(dep_ref, mods_dir, parent_chain=""):
            callback_calls.append({
                "dep": dep_ref.get_display_name(),
                "parent_chain": parent_chain,
            })
            if "leaf-pkg" in dep_ref.get_display_name():
                # Simulate what the real callback does: catch internal error,
                # return None (non-blocking). The resolver treats None as
                # "download failed, skip transitive deps".
                return None
            # Root-pkg is already on disk, return its path
            return dep_ref.get_install_path(mods_dir)

        resolver = APMDependencyResolver(
            apm_modules_dir=modules_dir,
            download_callback=tracking_callback,
        )

        os.chdir(tmp_path)
        resolver.resolve_dependencies(tmp_path)

        # The callback should have been called for leaf-pkg
        leaf_calls = [c for c in callback_calls if "leaf-pkg" in c["dep"]]
        assert len(leaf_calls) == 1, (
            f"Expected 1 call for leaf-pkg, got {len(leaf_calls)}. "
            f"All calls: {callback_calls}"
        )

        # The parent chain should contain root-pkg
        chain = leaf_calls[0]["parent_chain"]
        assert "root-pkg" in chain, (
            f"Expected 'root-pkg' in parent chain, got: '{chain}'"
        )
        # Chain should show the full path: root > leaf
        assert ">" in chain, (
            f"Expected '>' separator in chain, got: '{chain}'"
        )
