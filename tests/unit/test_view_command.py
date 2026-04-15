"""Tests for the top-level ``apm view`` command (renamed from ``apm info``)."""

import contextlib
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from apm_cli.cli import cli
from apm_cli.models.dependency.types import GitReferenceType, RemoteRef


# ------------------------------------------------------------------
# Rich-fallback helper (same approach as test_deps_list_tree_info.py)
# ------------------------------------------------------------------

def _force_rich_fallback():
    """Context-manager that forces the text-only code path."""

    @contextlib.contextmanager
    def _ctx():
        keys = [
            "rich",
            "rich.console",
            "rich.table",
            "rich.tree",
            "rich.panel",
            "rich.text",
        ]
        originals = {k: sys.modules.get(k) for k in keys}

        for k in keys:
            stub = types.ModuleType(k)
            stub.__path__ = []

            def _raise(name, _k=k):
                raise ImportError(f"rich not available in test: {_k}")

            stub.__getattr__ = _raise
            sys.modules[k] = stub

        try:
            yield
        finally:
            for k, v in originals.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v

    return _ctx()


# ------------------------------------------------------------------
# Base class with temp-dir helpers
# ------------------------------------------------------------------


class _InfoCmdBase:
    """Shared CWD-management helpers."""

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

    @staticmethod
    def _make_package(root: Path, org: str, repo: str, **kwargs) -> Path:
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


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestViewCommand(_InfoCmdBase):
    """Tests for the top-level ``apm view`` command."""

    # -- basic metadata display -------------------------------------------

    def test_view_shows_package_details(self):
        """``apm view org/repo`` shows package metadata (fallback mode)."""
        with self._chdir_tmp() as tmp:
            self._make_package(
                tmp,
                "myorg",
                "myrepo",
                version="2.5.0",
                description="My awesome package",
                author="Alice",
            )
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["view", "myorg/myrepo"])
        assert result.exit_code == 0
        assert "2.5.0" in result.output
        assert "My awesome package" in result.output
        assert "Alice" in result.output

    # -- missing apm_modules/ ---------------------------------------------

    def test_view_no_apm_modules(self):
        """``apm view`` exits with error when apm_modules/ is missing."""
        with self._chdir_tmp():
            result = self.runner.invoke(cli, ["view", "noorg/norepo"])
        assert result.exit_code == 1

    # -- field: versions (placeholder) ------------------------------------

    def test_view_versions_lists_refs(self):
        """``apm view org/repo versions`` shows tags and branches."""
        mock_refs = [
            RemoteRef(name="v2.0.0", ref_type=GitReferenceType.TAG,
                      commit_sha="aabbccdd11223344"),
            RemoteRef(name="v1.0.0", ref_type=GitReferenceType.TAG,
                      commit_sha="11223344aabbccdd"),
            RemoteRef(name="main", ref_type=GitReferenceType.BRANCH,
                      commit_sha="deadbeef12345678"),
        ]
        with patch(
            "apm_cli.commands.view.GitHubPackageDownloader"
        ) as mock_cls, patch(
            "apm_cli.commands.view.AuthResolver"
        ):
            mock_cls.return_value.list_remote_refs.return_value = mock_refs
            with _force_rich_fallback():
                result = self.runner.invoke(
                    cli, ["view", "myorg/myrepo", "versions"]
                )
        assert result.exit_code == 0
        assert "v2.0.0" in result.output
        assert "v1.0.0" in result.output
        assert "main" in result.output
        assert "tag" in result.output
        assert "branch" in result.output
        assert "aabbccdd" in result.output
        assert "deadbeef" in result.output

    def test_view_versions_empty_refs(self):
        """``apm view org/repo versions`` with no refs shows info message."""
        with patch(
            "apm_cli.commands.view.GitHubPackageDownloader"
        ) as mock_cls, patch(
            "apm_cli.commands.view.AuthResolver"
        ):
            mock_cls.return_value.list_remote_refs.return_value = []
            result = self.runner.invoke(
                cli, ["view", "myorg/myrepo", "versions"]
            )
        assert result.exit_code == 0
        assert "no versions found" in result.output.lower()

    def test_view_versions_runtime_error(self):
        """``apm view org/repo versions`` exits 1 on RuntimeError."""
        with patch(
            "apm_cli.commands.view.GitHubPackageDownloader"
        ) as mock_cls, patch(
            "apm_cli.commands.view.AuthResolver"
        ):
            mock_cls.return_value.list_remote_refs.side_effect = RuntimeError(
                "auth failed"
            )
            result = self.runner.invoke(
                cli, ["view", "myorg/myrepo", "versions"]
            )
        assert result.exit_code == 1
        assert "failed to list versions" in result.output.lower()

    def test_view_versions_with_ref_shorthand(self):
        """``apm view owner/repo#v1.0 versions`` parses ref correctly."""
        mock_refs = [
            RemoteRef(name="v1.0.0", ref_type=GitReferenceType.TAG,
                      commit_sha="abcdef1234567890"),
        ]
        with patch(
            "apm_cli.commands.view.GitHubPackageDownloader"
        ) as mock_cls, patch(
            "apm_cli.commands.view.AuthResolver"
        ):
            mock_cls.return_value.list_remote_refs.return_value = mock_refs
            with _force_rich_fallback():
                result = self.runner.invoke(
                    cli, ["view", "myorg/myrepo#v1.0", "versions"]
                )
        assert result.exit_code == 0
        assert "v1.0.0" in result.output

    def test_view_versions_does_not_require_apm_modules(self):
        """``apm view org/repo versions`` works without apm_modules/."""
        mock_refs = [
            RemoteRef(name="main", ref_type=GitReferenceType.BRANCH,
                      commit_sha="1234567890abcdef"),
        ]
        with self._chdir_tmp():
            # No apm_modules/ created -- should still succeed
            with patch(
                "apm_cli.commands.view.GitHubPackageDownloader"
            ) as mock_cls, patch(
                "apm_cli.commands.view.AuthResolver"
            ):
                mock_cls.return_value.list_remote_refs.return_value = mock_refs
                with _force_rich_fallback():
                    result = self.runner.invoke(
                        cli, ["view", "myorg/myrepo", "versions"]
                    )
        assert result.exit_code == 0
        assert "main" in result.output

    # -- invalid field ----------------------------------------------------

    def test_view_invalid_field(self):
        """``apm view org/repo bad-field`` shows error with valid fields."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "forg", "frepo")
            os.chdir(tmp)
            result = self.runner.invoke(cli, ["view", "forg/frepo", "bad-field"])
        assert result.exit_code == 1
        assert "bad-field" in result.output
        assert "versions" in result.output

    # -- short name resolution --------------------------------------------

    def test_view_short_package_name(self):
        """``apm view repo`` resolves by short repo name."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "shortorg", "shortrepo")
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["view", "shortrepo"])
        assert result.exit_code == 0
        assert "shortrepo" in result.output

    # -- package not found ------------------------------------------------

    def test_view_package_not_found(self):
        """``apm view`` shows error and lists available packages."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "existorg", "existrepo")
            os.chdir(tmp)
            result = self.runner.invoke(cli, ["view", "doesnotexist"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "error" in result.output.lower()
        assert "existorg/existrepo" in result.output

    # -- SKILL.md-only package (no apm.yml) --------------------------------

    def test_view_skill_only_package(self):
        """``apm view`` works for packages with SKILL.md but no apm.yml."""
        with self._chdir_tmp() as tmp:
            pkg_dir = tmp / "apm_modules" / "skillorg" / "skillrepo"
            pkg_dir.mkdir(parents=True)
            (pkg_dir / "SKILL.md").write_text("# My Skill\n")
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["view", "skillorg/skillrepo"])
        assert result.exit_code == 0
        assert "skillrepo" in result.output

    # -- bare package (no context files / no workflows) -------------------

    def test_view_bare_package_no_context(self):
        """``apm view`` reports 'No context files found' for bare packages."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "bareorg", "barerepo")
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["view", "bareorg/barerepo"])
        assert result.exit_code == 0
        assert "No context files found" in result.output

    def test_view_bare_package_no_workflows(self):
        """``apm view`` reports 'No agent workflows found' for bare packages."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "wforg", "wfrepo")
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["view", "wforg/wfrepo"])
        assert result.exit_code == 0
        assert "No agent workflows found" in result.output

    # -- no args: Click should show error / usage -------------------------

    def test_view_no_args_shows_error(self):
        """``apm view`` with no arguments shows an error (PACKAGE is required)."""
        result = self.runner.invoke(cli, ["view"])
        # Click exits 2 for missing required arguments
        assert result.exit_code == 2
        # Should mention the missing argument or show usage
        assert "PACKAGE" in result.output or "Missing argument" in result.output or "Usage" in result.output

    # -- DependencyReference.parse failure for versions field -------------

    def test_view_versions_invalid_parse(self):
        """``apm view <pkg> versions`` exits 1 when DependencyReference.parse raises ValueError."""
        with patch(
            "apm_cli.commands.view.DependencyReference"
        ) as mock_dep_ref_cls:
            mock_dep_ref_cls.parse.side_effect = ValueError("unsupported host: ftp")
            result = self.runner.invoke(
                cli, ["view", "ftp://bad-host/invalid", "versions"]
            )
        assert result.exit_code == 1
        assert "invalid" in result.output.lower() or "ftp" in result.output.lower()

    # -- path traversal prevention ----------------------------------------

    def test_view_rejects_path_traversal(self):
        """``apm view ../../../etc/passwd`` is rejected as a traversal attempt."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "org", "legit")
            os.chdir(tmp)
            result = self.runner.invoke(cli, ["view", "../../../etc/passwd"])
        assert result.exit_code == 1
        assert "traversal" in result.output.lower()

    def test_view_rejects_dot_segment(self):
        """``apm view org/../../../etc/passwd`` is rejected."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "org", "legit")
            os.chdir(tmp)
            result = self.runner.invoke(cli, ["view", "org/../../../etc/passwd"])
        assert result.exit_code == 1
        assert "traversal" in result.output.lower()


class TestViewCommandRichDisplay(_InfoCmdBase):
    """Tests for Rich rendering paths in ``apm view``."""

    def test_view_rich_panel_display(self):
        """``apm view`` renders a Rich panel when Rich is available."""
        with self._chdir_tmp() as tmp:
            self._make_package(
                tmp, "richorg", "richrepo", version="3.0.0",
                description="Rich panel test", author="Carol",
            )
            os.chdir(tmp)
            # No _force_rich_fallback -- let Rich render
            result = self.runner.invoke(cli, ["view", "richorg/richrepo"])
        assert result.exit_code == 0
        assert "3.0.0" in result.output
        assert "Rich panel test" in result.output
        assert "Carol" in result.output

    def test_view_rich_panel_with_hooks(self):
        """``apm view`` Rich panel includes hook count when hooks exist."""
        with self._chdir_tmp() as tmp:
            pkg_dir = self._make_package(tmp, "hookorg", "hookrepo")
            hooks_dir = pkg_dir / "hooks"
            hooks_dir.mkdir()
            (hooks_dir / "pre-commit.json").write_text('{"hooks": []}')
            os.chdir(tmp)
            result = self.runner.invoke(cli, ["view", "hookorg/hookrepo"])
        assert result.exit_code == 0
        assert "hook" in result.output.lower()

    def test_view_rich_panel_with_context_files(self):
        """``apm view`` Rich panel shows context file count when present."""
        with self._chdir_tmp() as tmp:
            pkg_dir = self._make_package(tmp, "ctxorg", "ctxrepo")
            instr_dir = pkg_dir / ".apm" / "instructions"
            instr_dir.mkdir(parents=True)
            (instr_dir / "coding-style.md").write_text("# Style guide")
            os.chdir(tmp)
            result = self.runner.invoke(cli, ["view", "ctxorg/ctxrepo"])
        assert result.exit_code == 0
        assert "instructions" in result.output.lower() or "context" in result.output.lower()

    def test_view_rich_panel_with_workflows(self):
        """``apm view`` Rich panel shows workflow count when present."""
        with self._chdir_tmp() as tmp:
            pkg_dir = self._make_package(tmp, "wforg2", "wfrepo2")
            prompts_dir = pkg_dir / ".apm" / "prompts"
            prompts_dir.mkdir(parents=True)
            (prompts_dir / "build.prompt.md").write_text("# Build workflow")
            os.chdir(tmp)
            result = self.runner.invoke(cli, ["view", "wforg2/wfrepo2"])
        assert result.exit_code == 0
        assert "workflow" in result.output.lower() or "1" in result.output

    def test_view_rich_versions_table(self):
        """``apm view org/repo versions`` renders a Rich table when Rich is available."""
        mock_refs = [
            RemoteRef(name="v1.0.0", ref_type=GitReferenceType.TAG,
                      commit_sha="aabbccdd11223344"),
            RemoteRef(name="main", ref_type=GitReferenceType.BRANCH,
                      commit_sha="deadbeef12345678"),
        ]
        with patch(
            "apm_cli.commands.view.GitHubPackageDownloader"
        ) as mock_cls, patch("apm_cli.commands.view.AuthResolver"):
            mock_cls.return_value.list_remote_refs.return_value = mock_refs
            # No _force_rich_fallback -- let Rich render
            result = self.runner.invoke(
                cli, ["view", "richorg/richrepo", "versions"]
            )
        assert result.exit_code == 0
        assert "v1.0.0" in result.output
        assert "main" in result.output


class TestViewLockfileRef(_InfoCmdBase):
    """Tests for lockfile ref/commit display in ``apm view``."""

    def _write_lockfile(self, project_root: Path, repo_url: str,
                        resolved_ref: str, resolved_commit: str) -> None:
        """Write a minimal apm.lock.yaml for testing."""
        import yaml

        lockfile_data = {
            "lockfile_version": "1",
            "generated_at": "2026-01-01T00:00:00Z",
            "dependencies": [
                {
                    "repo_url": repo_url,
                    "host": "github.com",
                    "resolved_ref": resolved_ref,
                    "resolved_commit": resolved_commit,
                    "depth": 0,
                    "resolved_by": "direct",
                }
            ],
        }
        lockfile_path = project_root / "apm.lock.yaml"
        lockfile_path.write_text(yaml.safe_dump(lockfile_data), encoding="utf-8")

    def test_view_shows_lockfile_ref(self):
        """``apm view`` displays resolved ref from apm.lock.yaml."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "lockorg", "lockrepo")
            self._write_lockfile(
                tmp,
                repo_url="https://github.com/lockorg/lockrepo",
                resolved_ref="v2.5.0",
                resolved_commit="abc123def456abc1",
            )
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["view", "lockorg/lockrepo"])
        assert result.exit_code == 0
        assert "v2.5.0" in result.output

    def test_view_shows_lockfile_commit(self):
        """``apm view`` displays truncated commit SHA from apm.lock.yaml."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "lockorg2", "lockrepo2")
            self._write_lockfile(
                tmp,
                repo_url="https://github.com/lockorg2/lockrepo2",
                resolved_ref="main",
                resolved_commit="deadbeef12345678abcdef",
            )
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["view", "lockorg2/lockrepo2"])
        assert result.exit_code == 0
        assert "deadbeef" in result.output  # first 12 chars of commit

    def test_view_no_lockfile_shows_no_ref(self):
        """``apm view`` works fine when no lockfile exists."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "nolock", "nolockpkg")
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["view", "nolock/nolockpkg"])
        assert result.exit_code == 0
        # No ref/commit info, but metadata is still shown
        assert "nolockpkg" in result.output

    def test_view_rich_shows_lockfile_ref(self):
        """``apm view`` Rich panel shows resolved ref from apm.lock.yaml."""
        with self._chdir_tmp() as tmp:
            self._make_package(tmp, "richlockorg", "richlockrepo")
            self._write_lockfile(
                tmp,
                repo_url="https://github.com/richlockorg/richlockrepo",
                resolved_ref="v3.1.4",
                resolved_commit="cafebabe12345678",
            )
            os.chdir(tmp)
            result = self.runner.invoke(cli, ["view", "richlockorg/richlockrepo"])
        assert result.exit_code == 0
        assert "v3.1.4" in result.output


class TestViewHooks(_InfoCmdBase):
    """Tests for hook display in ``apm view``."""

    def test_view_plain_text_shows_hooks(self):
        """``apm view`` plain-text fallback shows hook count."""
        with self._chdir_tmp() as tmp:
            pkg_dir = self._make_package(tmp, "hkorg", "hkrepo")
            hooks_dir = pkg_dir / "hooks"
            hooks_dir.mkdir()
            (hooks_dir / "commit-msg.json").write_text('{"hooks": []}')
            (hooks_dir / "pre-push.json").write_text('{"hooks": []}')
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["view", "hkorg/hkrepo"])
        assert result.exit_code == 0
        assert "hook" in result.output.lower()
        assert "2" in result.output

    def test_view_plain_text_shows_context_files(self):
        """``apm view`` plain-text fallback shows context file count."""
        with self._chdir_tmp() as tmp:
            pkg_dir = self._make_package(tmp, "ctxorg2", "ctxrepo2")
            instr_dir = pkg_dir / ".apm" / "instructions"
            instr_dir.mkdir(parents=True)
            (instr_dir / "guide.md").write_text("# Guide")
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["view", "ctxorg2/ctxrepo2"])
        assert result.exit_code == 0
        assert "instructions" in result.output.lower() or "1" in result.output

    def test_view_plain_text_shows_workflows(self):
        """``apm view`` plain-text fallback shows workflow count when present."""
        with self._chdir_tmp() as tmp:
            pkg_dir = self._make_package(tmp, "wforg3", "wfrepo3")
            prompts_dir = pkg_dir / ".apm" / "prompts"
            prompts_dir.mkdir(parents=True)
            (prompts_dir / "build.prompt.md").write_text("# Build")
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["view", "wforg3/wfrepo3"])
        assert result.exit_code == 0
        assert "workflow" in result.output.lower() or "executable" in result.output.lower()


class TestViewGlobalScope(_InfoCmdBase):
    """Tests for ``apm view --global`` scope handling."""

    def test_view_global_flag_uses_user_scope(self):
        """``apm view --global`` resolves packages from user scope."""
        import tempfile as _tempfile

        with _tempfile.TemporaryDirectory() as user_apm_dir:
            user_apm_path = Path(user_apm_dir)
            # Create a package in the simulated user APM dir
            pkg_dir = user_apm_path / "apm_modules" / "globalorg" / "globalrepo"
            pkg_dir.mkdir(parents=True)
            (pkg_dir / "apm.yml").write_text(
                "name: globalrepo\nversion: 9.9.9\n"
                "description: Global pkg\nauthor: Eve\n"
            )
            with patch(
                "apm_cli.core.scope.get_apm_dir",
                return_value=user_apm_path,
            ):
                with _force_rich_fallback():
                    result = self.runner.invoke(
                        cli, ["view", "globalorg/globalrepo", "--global"]
                    )
        assert result.exit_code == 0
        assert "9.9.9" in result.output
        assert "Global pkg" in result.output

    def test_view_global_flag_missing_apm_modules(self):
        """``apm view --global`` exits with error when user scope has no apm_modules/."""
        import tempfile as _tempfile

        with _tempfile.TemporaryDirectory() as user_apm_dir:
            user_apm_path = Path(user_apm_dir)
            # No apm_modules/ in user scope
            with patch(
                "apm_cli.core.scope.get_apm_dir",
                return_value=user_apm_path,
            ):
                result = self.runner.invoke(
                    cli, ["view", "missing/pkg", "--global"]
                )
        assert result.exit_code == 1


class TestInfoAlias(_InfoCmdBase):
    """Verify ``apm info`` still works as a hidden backward-compatible alias."""

    def test_info_alias_shows_package_details(self):
        """``apm info org/repo`` produces the same output as ``apm view``."""
        with self._chdir_tmp() as tmp:
            self._make_package(
                tmp, "myorg", "myrepo",
                version="2.5.0", description="Alias test", author="Bob",
            )
            os.chdir(tmp)
            with _force_rich_fallback():
                result = self.runner.invoke(cli, ["info", "myorg/myrepo"])
        assert result.exit_code == 0
        assert "2.5.0" in result.output
        assert "Alias test" in result.output

    def test_info_alias_hidden_from_help(self):
        """``apm info`` does NOT appear in top-level ``--help`` output."""
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        # "view" should be visible; "info" should not
        assert "view" in result.output
        # Check that "info" doesn't appear as a listed command
        # (it may appear in other text, so check the commands section)
        lines = result.output.splitlines()
        command_lines = [
            l.strip() for l in lines
            if l.strip().startswith("info") and not l.strip().startswith("info")  # skip false match
        ]
        # More robust: "info" should not be in the commands listing
        # The help output lists commands like "  view    View package..."
        # "info" as hidden should be absent from this listing
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("info "):
                pytest.fail(f"'info' should be hidden but found in help: {line}")
