"""Tests for apm deps list, tree, and info subcommands."""

import contextlib
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from apm_cli.cli import cli


def _force_rich_fallback():
    """Context-manager patches that force the text-only code path.

    Rich imports inside function bodies are resolved from ``sys.modules`` at
    call time, so we stub out the modules there instead of the per-attribute
    path used when the symbols are in a module-level namespace.
    """
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        fakes = {
            "rich": None,
            "rich.console": None,
            "rich.table": None,
            "rich.tree": None,
            "rich.panel": None,
            "rich.text": None,
        }
        # Stash originals (None if not imported yet)
        originals = {k: sys.modules.get(k) for k in fakes}
        # Mark each as failed import by removing from sys.modules so the
        # ``from rich.xxx import Yyy`` inside function bodies raises ImportError
        for k in fakes:
            sys.modules.pop(k, None)
        # Now install a sentinel module that raises on attribute access
        sentinel = MagicMock()
        sentinel.__path__ = []  # make it look like a package

        class _BrokenModule:
            def __getattr__(self, name):
                raise ImportError(f"rich not available in test")

        broken = _BrokenModule()
        broken.__path__ = []
        for k in fakes:
            sys.modules[k] = broken  # type: ignore[assignment]
        try:
            yield
        finally:
            for k, v in originals.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v

    return _ctx()


class TestDepsListCommand:
    """Tests for apm deps list."""

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

    @contextlib.contextmanager
    def _chdir_tmp(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                os.chdir(tmp_dir)
                yield Path(tmp_dir)
            finally:
                os.chdir(self.original_dir)

    def _make_package(self, root: Path, org: str, repo: str, version: str = "1.0.0") -> Path:
        """Create a minimal installed package under apm_modules/."""
        pkg_dir = root / "apm_modules" / org / repo
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "apm.yml").write_text(
            f"name: {repo}\nversion: {version}\ndescription: Test pkg\n"
        )
        return pkg_dir

    def test_list_no_apm_modules(self):
        """Without apm_modules/, list reports no deps installed."""
        with self._chdir_tmp() as tmp:
            with patch("apm_cli.core.scope.get_apm_dir", return_value=tmp):
                result = self.runner.invoke(cli, ["deps", "list"])
        assert result.exit_code == 0
        assert "No APM dependencies installed" in result.output

    def test_list_project_scope_shows_package(self):
        """list (project scope) shows installed package in fallback text mode."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "myorg", "myrepo")
            with patch("apm_cli.core.scope.get_apm_dir", return_value=tmp), _force_rich_fallback():
                result = self.runner.invoke(cli, ["deps", "list"])
        assert result.exit_code == 0
        assert "myorg/myrepo" in result.output

    def test_list_global_flag(self):
        """--global flag targets user scope directory."""
        from apm_cli.core.scope import InstallScope

        with self._chdir_tmp() as tmp:
            user_dir = tmp / "user"
            user_dir.mkdir()
            self._make_package(user_dir, "globalorg", "globalrepo")
            called_scopes = []

            def fake_get_apm_dir(scope):
                called_scopes.append(scope)
                return user_dir if scope == InstallScope.USER else tmp

            with patch("apm_cli.core.scope.get_apm_dir", side_effect=fake_get_apm_dir):
                result = self.runner.invoke(cli, ["deps", "list", "--global"])

        assert InstallScope.USER in called_scopes
        assert result.exit_code == 0

    def test_list_all_flag_calls_both_scopes(self):
        """--all flag calls _show_scope_deps for both project and user scopes."""
        from apm_cli.core.scope import InstallScope

        with self._chdir_tmp() as tmp:
            proj_dir = tmp / "proj"
            user_dir = tmp / "user"
            proj_dir.mkdir()
            user_dir.mkdir()
            self._make_package(proj_dir, "porg", "prepo")
            self._make_package(user_dir, "uorg", "urepo")
            scopes_seen = []

            def fake_get_apm_dir(scope):
                scopes_seen.append(scope)
                return user_dir if scope == InstallScope.USER else proj_dir

            with patch("apm_cli.core.scope.get_apm_dir", side_effect=fake_get_apm_dir):
                result = self.runner.invoke(cli, ["deps", "list", "--all"])

        assert result.exit_code == 0
        assert InstallScope.PROJECT in scopes_seen
        assert InstallScope.USER in scopes_seen

    def test_list_empty_apm_modules_dir(self):
        """apm_modules/ exists but has no valid packages."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm_modules").mkdir()
            with patch("apm_cli.core.scope.get_apm_dir", return_value=tmp):
                result = self.runner.invoke(cli, ["deps", "list"])
        assert result.exit_code == 0
        assert "no valid packages" in result.output

    def test_list_shows_orphaned_warning(self):
        """Packages not in apm.yml should be flagged as orphaned."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "orphanorg", "orphanrepo")
            # No apm.yml at project root -> package is orphaned
            with patch("apm_cli.core.scope.get_apm_dir", return_value=tmp), _force_rich_fallback():
                result = self.runner.invoke(cli, ["deps", "list"])
        assert result.exit_code == 0
        assert "orphaned" in result.output.lower()

    def test_list_version_shown(self):
        """Version from apm.yml should appear in fallback text output."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "verorg", "verrepo", version="2.3.1")
            with patch("apm_cli.core.scope.get_apm_dir", return_value=tmp), _force_rich_fallback():
                result = self.runner.invoke(cli, ["deps", "list"])
        assert result.exit_code == 0
        assert "2.3.1" in result.output


class TestDepsTreeCommand:
    """Tests for apm deps tree."""

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

    @contextlib.contextmanager
    def _chdir_tmp(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                os.chdir(tmp_dir)
                yield Path(tmp_dir)
            finally:
                os.chdir(self.original_dir)

    def _make_package(self, root: Path, org: str, repo: str) -> Path:
        pkg_dir = root / "apm_modules" / org / repo
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "apm.yml").write_text(f"name: {repo}\nversion: 1.0.0\n")
        return pkg_dir

    def test_tree_no_apm_modules_fallback(self):
        """Without apm_modules/ and no Rich, tree shows 'No dependencies installed'."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text("name: myproject\nversion: 1.0.0\n")
            with patch("apm_cli.core.scope.get_apm_dir", return_value=tmp), _force_rich_fallback():
                result = self.runner.invoke(cli, ["deps", "tree"])
        assert result.exit_code == 0
        # Fallback text: project name shown, then no deps line
        assert "No dependencies installed" in result.output

    def test_tree_with_package_no_lockfile(self):
        """tree command succeeds with installed packages and no lockfile."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "treeorg", "treerepo")
            (tmp / "apm.yml").write_text("name: testproject\nversion: 1.0.0\n")
            with patch("apm_cli.core.scope.get_apm_dir", return_value=tmp), _force_rich_fallback():
                result = self.runner.invoke(cli, ["deps", "tree"])
        assert result.exit_code == 0
        # Project name is read from apm.yml
        assert "testproject" in result.output

    def test_tree_global_flag(self):
        """--global flag targets user scope for tree."""
        from apm_cli.core.scope import InstallScope

        with self._chdir_tmp() as tmp:
            user_dir = tmp / "user"
            user_dir.mkdir()
            scopes_seen = []

            def fake_get_apm_dir(scope):
                scopes_seen.append(scope)
                return user_dir if scope == InstallScope.USER else tmp

            with patch("apm_cli.core.scope.get_apm_dir", side_effect=fake_get_apm_dir):
                result = self.runner.invoke(cli, ["deps", "tree", "--global"])

        assert InstallScope.USER in scopes_seen
        assert result.exit_code == 0

    def test_tree_with_lockfile_shows_dep(self):
        """tree uses lockfile data and displays dep key + version."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "lkorg", "lkrepo")
            (tmp / "apm.yml").write_text("name: myproj\n")

            mock_dep = MagicMock()
            mock_dep.depth = 1
            mock_dep.resolved_by = None
            mock_dep.repo_url = "lkorg/lkrepo"
            mock_dep.version = "1.2.3"
            mock_dep.resolved_commit = None
            mock_dep.resolved_ref = None
            mock_dep.get_unique_key.return_value = "lkorg/lkrepo"

            mock_lockfile = MagicMock()
            mock_lockfile.get_all_dependencies.return_value = [mock_dep]

            mock_lf_path = MagicMock()
            mock_lf_path.exists.return_value = True

            with patch("apm_cli.core.scope.get_apm_dir", return_value=tmp), _force_rich_fallback(), patch(
                "apm_cli.deps.lockfile.LockFile.read", return_value=mock_lockfile
            ), patch(
                "apm_cli.deps.lockfile.get_lockfile_path", return_value=mock_lf_path
            ):
                result = self.runner.invoke(cli, ["deps", "tree"])

        assert result.exit_code == 0
        assert "lkorg/lkrepo" in result.output
        assert "1.2.3" in result.output

    def test_tree_project_name_from_apm_yml(self):
        """tree uses project name from apm.yml as root node."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text("name: awesomeproject\nversion: 1.0.0\n")
            with patch("apm_cli.core.scope.get_apm_dir", return_value=tmp), _force_rich_fallback():
                result = self.runner.invoke(cli, ["deps", "tree"])
        assert result.exit_code == 0
        assert "awesomeproject" in result.output


class TestDepsInfoCommand:
    """Tests for apm deps info."""

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

    @contextlib.contextmanager
    def _chdir_tmp(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                os.chdir(tmp_dir)
                yield Path(tmp_dir)
            finally:
                os.chdir(self.original_dir)

    def _make_package(self, root: Path, org: str, repo: str, **kwargs) -> Path:
        pkg_dir = root / "apm_modules" / org / repo
        pkg_dir.mkdir(parents=True)
        version = kwargs.get("version", "1.0.0")
        description = kwargs.get("description", "A test package")
        author = kwargs.get("author", "TestAuthor")
        content = (
            f"name: {repo}\nversion: {version}\n"
            f"description: {description}\nauthor: {author}\n"
        )
        (pkg_dir / "apm.yml").write_text(content)
        return pkg_dir

    def test_info_no_apm_modules(self):
        """info exits with error when apm_modules/ is missing."""
        with self._chdir_tmp():
            result = self.runner.invoke(cli, ["deps", "info", "myorg/myrepo"])
        assert result.exit_code == 1

    def test_info_package_not_found(self):
        """info exits with error when the package is not in apm_modules/."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm_modules").mkdir()
            os.chdir(tmp)
            result = self.runner.invoke(cli, ["deps", "info", "noorg/norepo"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_info_shows_package_details_fallback(self):
        """info displays name, version, description in fallback (no-Rich) mode."""
        with self._chdir_tmp() as tmp:
            self._make_package(
                tmp,
                "infoorg",
                "inforepo",
                version="3.1.4",
                description="Detailed test package",
                author="InfoAuthor",
            )
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["deps", "info", "infoorg/inforepo"])
        assert result.exit_code == 0
        assert "3.1.4" in result.output
        assert "Detailed test package" in result.output
        assert "InfoAuthor" in result.output

    def test_info_short_package_name_fallback(self):
        """info resolves package by short repo name (no org/ prefix)."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "shortorg", "shortrepo")
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["deps", "info", "shortrepo"])
        assert result.exit_code == 0
        assert "shortrepo" in result.output

    def test_info_lists_available_packages_on_not_found(self):
        """When package not found, info lists available packages."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "availorg", "availrepo")
            os.chdir(tmp)
            result = self.runner.invoke(cli, ["deps", "info", "doesnotexist"])
        assert result.exit_code == 1
        assert "availorg/availrepo" in result.output

    def test_info_without_apm_yml(self):
        """info handles packages that have no apm.yml (skill-only packages)."""
        with self._chdir_tmp() as tmp:
            pkg_dir = tmp / "apm_modules" / "skillorg" / "skillrepo"
            pkg_dir.mkdir(parents=True)
            (pkg_dir / "SKILL.md").write_text("# My Skill\n")
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["deps", "info", "skillorg/skillrepo"])
        assert result.exit_code == 0
        assert "skillrepo" in result.output

    def test_info_shows_no_context_files_for_bare_package(self):
        """info reports 'No context files found' for a package with no context dirs."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "bareorg", "barerepo")
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["deps", "info", "bareorg/barerepo"])
        assert result.exit_code == 0
        assert "No context files found" in result.output

    def test_info_shows_no_workflows_for_bare_package(self):
        """info reports 'No agent workflows found' for a package without .prompt.md."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "wforg", "wfrepo")
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["deps", "info", "wforg/wfrepo"])
        assert result.exit_code == 0
        assert "No agent workflows found" in result.output
