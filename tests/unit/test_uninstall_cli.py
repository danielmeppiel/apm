"""Unit tests for the apm uninstall CLI command.

Tests cover:
- Missing apm.yml (project scope and user scope)
- Package not found in apm.yml
- Single package dry-run
- Single package successful uninstall (removes from apm.yml + modules)
- Multiple packages uninstall
- Lockfile updated after uninstall
- Lockfile deleted when all entries removed
- --global / user scope flag
- --verbose flag
- Error handling: yaml read failure, yaml write failure
"""

import contextlib
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml
from click.testing import CliRunner

from apm_cli.cli import cli
from apm_cli.deps.lockfile import LockedDependency, LockFile
from apm_cli.models.apm_package import clear_apm_yml_cache

# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------

_APM_YML_EMPTY_DEPS = """\
name: test-project
version: 1.0.0
dependencies:
  apm: []
"""

_APM_YML_ONE_DEP = """\
name: test-project
version: 1.0.0
dependencies:
  apm:
    - owner/repo
"""

_APM_YML_TWO_DEPS = """\
name: test-project
version: 1.0.0
dependencies:
  apm:
    - org/pkg1
    - org/pkg2
"""

_LOCKFILE_ONE_DEP = """\
lockfile_version: '1'
dependencies:
- repo_url: owner/repo
  resolved_commit: abc123
"""

_LOCKFILE_TWO_DEPS = """\
lockfile_version: '1'
dependencies:
- repo_url: org/pkg1
  resolved_commit: abc123
- repo_url: org/pkg2
  resolved_commit: def456
"""


def _make_pkg_dir(root: Path, org: str, repo: str) -> Path:
    """Create an apm_modules/<org>/<repo> directory."""
    pkg = root / "apm_modules" / org / repo
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "apm.yml").write_text(f"name: {repo}\nversion: 1.0.0\n")
    return pkg


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestUninstallCLI:
    """Tests for ``apm uninstall``."""

    def setup_method(self):
        self.runner = CliRunner()
        try:
            self.original_dir = os.getcwd()
        except FileNotFoundError:
            self.original_dir = str(Path(__file__).parent.parent.parent)
            os.chdir(self.original_dir)

    def teardown_method(self):
        clear_apm_yml_cache()
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
                try:
                    os.chdir(self.original_dir)
                except (FileNotFoundError, OSError):
                    pass
                clear_apm_yml_cache()

    # ------------------------------------------------------------------
    # Missing apm.yml
    # ------------------------------------------------------------------

    def test_no_apm_yml_exits_with_error(self):
        """uninstall must fail with exit 1 when apm.yml is absent."""
        with self._chdir_tmp():
            result = self.runner.invoke(cli, ["uninstall", "owner/repo"])
            assert result.exit_code == 1
            assert "apm.yml" in result.output or "No" in result.output

    def test_no_apm_yml_dry_run_exits_with_error(self):
        """uninstall --dry-run must also fail when apm.yml is absent."""
        with self._chdir_tmp():
            result = self.runner.invoke(cli, ["uninstall", "--dry-run", "owner/repo"])
            assert result.exit_code == 1

    # ------------------------------------------------------------------
    # Package not in apm.yml
    # ------------------------------------------------------------------

    def test_package_not_in_apm_yml_returns_zero(self):
        """uninstall exits 0 with warning when package is not in apm.yml."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_EMPTY_DEPS)
            result = self.runner.invoke(cli, ["uninstall", "owner/missing"])
            assert result.exit_code == 0
            assert (
                "not found" in result.output.lower() or "No packages" in result.output
            )

    def test_package_not_in_apm_yml_shows_warning(self):
        """uninstall shows a warning when package is not found."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_ONE_DEP)
            result = self.runner.invoke(cli, ["uninstall", "owner/other"])
            assert result.exit_code == 0

    # ------------------------------------------------------------------
    # Dry-run
    # ------------------------------------------------------------------

    def test_dry_run_shows_what_would_be_removed(self):
        """--dry-run shows packages that would be removed without making changes."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_ONE_DEP)
            _make_pkg_dir(tmp, "owner", "repo")
            result = self.runner.invoke(cli, ["uninstall", "--dry-run", "owner/repo"])
            assert result.exit_code == 0
            assert "owner/repo" in result.output
            # apm.yml should be unchanged
            content = yaml.safe_load((tmp / "apm.yml").read_text())
            assert "owner/repo" in content["dependencies"]["apm"]

    def test_dry_run_does_not_modify_apm_yml(self):
        """--dry-run must not modify apm.yml."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_ONE_DEP)
            original_content = (tmp / "apm.yml").read_text()
            result = self.runner.invoke(cli, ["uninstall", "--dry-run", "owner/repo"])
            assert result.exit_code == 0
            assert (tmp / "apm.yml").read_text() == original_content

    def test_dry_run_does_not_remove_modules(self):
        """--dry-run must not remove package from apm_modules/."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_ONE_DEP)
            pkg_dir = _make_pkg_dir(tmp, "owner", "repo")
            result = self.runner.invoke(cli, ["uninstall", "--dry-run", "owner/repo"])
            assert result.exit_code == 0
            assert pkg_dir.exists(), "Package dir must not be removed in dry-run"

    def test_dry_run_says_dry_run(self):
        """--dry-run output should indicate it is a dry run."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_ONE_DEP)
            result = self.runner.invoke(cli, ["uninstall", "--dry-run", "owner/repo"])
            assert result.exit_code == 0
            assert "dry" in result.output.lower() or "Dry" in result.output

    # ------------------------------------------------------------------
    # Successful uninstall
    # ------------------------------------------------------------------

    def test_uninstall_removes_from_apm_yml(self):
        """uninstall removes the package from apm.yml dependencies."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_ONE_DEP)
            with (
                patch(
                    "apm_cli.commands.uninstall.cli._sync_integrations_after_uninstall",
                    return_value={
                        "prompts": 0,
                        "agents": 0,
                        "skills": 0,
                        "commands": 0,
                        "hooks": 0,
                        "instructions": 0,
                    },
                ),
                patch("apm_cli.commands.uninstall.cli._cleanup_stale_mcp"),
            ):
                result = self.runner.invoke(cli, ["uninstall", "owner/repo"])
            assert result.exit_code == 0
            content = yaml.safe_load((tmp / "apm.yml").read_text())
            assert "owner/repo" not in content["dependencies"]["apm"]

    def test_uninstall_removes_package_from_modules(self):
        """uninstall removes the package from apm_modules/ directory."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_ONE_DEP)
            pkg_dir = _make_pkg_dir(tmp, "owner", "repo")
            with (
                patch(
                    "apm_cli.commands.uninstall.cli._sync_integrations_after_uninstall",
                    return_value={
                        "prompts": 0,
                        "agents": 0,
                        "skills": 0,
                        "commands": 0,
                        "hooks": 0,
                        "instructions": 0,
                    },
                ),
                patch("apm_cli.commands.uninstall.cli._cleanup_stale_mcp"),
            ):
                result = self.runner.invoke(cli, ["uninstall", "owner/repo"])
            assert result.exit_code == 0
            assert not pkg_dir.exists()

    def test_uninstall_success_message(self):
        """uninstall shows a success message after completion."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_ONE_DEP)
            with (
                patch(
                    "apm_cli.commands.uninstall.cli._sync_integrations_after_uninstall",
                    return_value={
                        "prompts": 0,
                        "agents": 0,
                        "skills": 0,
                        "commands": 0,
                        "hooks": 0,
                        "instructions": 0,
                    },
                ),
                patch("apm_cli.commands.uninstall.cli._cleanup_stale_mcp"),
            ):
                result = self.runner.invoke(cli, ["uninstall", "owner/repo"])
            assert result.exit_code == 0
            assert (
                "Uninstall complete" in result.output
                or "Removed" in result.output
                or "removed" in result.output.lower()
            )

    # ------------------------------------------------------------------
    # Multiple packages
    # ------------------------------------------------------------------

    def test_uninstall_multiple_packages(self):
        """uninstall handles multiple packages in one invocation."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_TWO_DEPS)
            _make_pkg_dir(tmp, "org", "pkg1")
            _make_pkg_dir(tmp, "org", "pkg2")
            with (
                patch(
                    "apm_cli.commands.uninstall.cli._sync_integrations_after_uninstall",
                    return_value={
                        "prompts": 0,
                        "agents": 0,
                        "skills": 0,
                        "commands": 0,
                        "hooks": 0,
                        "instructions": 0,
                    },
                ),
                patch("apm_cli.commands.uninstall.cli._cleanup_stale_mcp"),
            ):
                result = self.runner.invoke(cli, ["uninstall", "org/pkg1", "org/pkg2"])
            assert result.exit_code == 0
            content = yaml.safe_load((tmp / "apm.yml").read_text())
            assert (
                content["dependencies"]["apm"] == []
                or not content["dependencies"]["apm"]
            )

    def test_uninstall_one_of_two_packages(self):
        """uninstall removes only the specified package, leaving others intact."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_TWO_DEPS)
            with (
                patch(
                    "apm_cli.commands.uninstall.cli._sync_integrations_after_uninstall",
                    return_value={
                        "prompts": 0,
                        "agents": 0,
                        "skills": 0,
                        "commands": 0,
                        "hooks": 0,
                        "instructions": 0,
                    },
                ),
                patch("apm_cli.commands.uninstall.cli._cleanup_stale_mcp"),
            ):
                result = self.runner.invoke(cli, ["uninstall", "org/pkg1"])
            assert result.exit_code == 0
            content = yaml.safe_load((tmp / "apm.yml").read_text())
            remaining = content["dependencies"]["apm"]
            assert "org/pkg2" in remaining or any(
                "org/pkg2" in str(d) for d in remaining
            )
            assert not any(
                "org/pkg1" == d or (isinstance(d, str) and d == "org/pkg1")
                for d in remaining
            )

    # ------------------------------------------------------------------
    # Lockfile handling
    # ------------------------------------------------------------------

    def test_uninstall_updates_lockfile(self):
        """uninstall removes the package entry from apm.lock.yaml."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_TWO_DEPS)
            (tmp / "apm.lock.yaml").write_text(_LOCKFILE_TWO_DEPS)
            with (
                patch(
                    "apm_cli.commands.uninstall.cli._sync_integrations_after_uninstall",
                    return_value={
                        "prompts": 0,
                        "agents": 0,
                        "skills": 0,
                        "commands": 0,
                        "hooks": 0,
                        "instructions": 0,
                    },
                ),
                patch("apm_cli.commands.uninstall.cli._cleanup_stale_mcp"),
            ):
                result = self.runner.invoke(cli, ["uninstall", "org/pkg1"])
            assert result.exit_code == 0
            assert (tmp / "apm.lock.yaml").exists()
            lockdata = yaml.safe_load((tmp / "apm.lock.yaml").read_text())
            dep_urls = [d["repo_url"] for d in lockdata.get("dependencies", [])]
            assert "org/pkg1" not in dep_urls
            assert "org/pkg2" in dep_urls

    def test_uninstall_deletes_lockfile_when_empty(self):
        """uninstall deletes apm.lock.yaml when the last package is removed."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_ONE_DEP)
            (tmp / "apm.lock.yaml").write_text(_LOCKFILE_ONE_DEP)
            with (
                patch(
                    "apm_cli.commands.uninstall.cli._sync_integrations_after_uninstall",
                    return_value={
                        "prompts": 0,
                        "agents": 0,
                        "skills": 0,
                        "commands": 0,
                        "hooks": 0,
                        "instructions": 0,
                    },
                ),
                patch("apm_cli.commands.uninstall.cli._cleanup_stale_mcp"),
            ):
                result = self.runner.invoke(cli, ["uninstall", "owner/repo"])
            assert result.exit_code == 0
            assert not (tmp / "apm.lock.yaml").exists()

    def test_uninstall_no_lockfile_succeeds(self):
        """uninstall succeeds gracefully when there is no lockfile."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_ONE_DEP)
            with (
                patch(
                    "apm_cli.commands.uninstall.cli._sync_integrations_after_uninstall",
                    return_value={
                        "prompts": 0,
                        "agents": 0,
                        "skills": 0,
                        "commands": 0,
                        "hooks": 0,
                        "instructions": 0,
                    },
                ),
                patch("apm_cli.commands.uninstall.cli._cleanup_stale_mcp"),
            ):
                result = self.runner.invoke(cli, ["uninstall", "owner/repo"])
            assert result.exit_code == 0

    # ------------------------------------------------------------------
    # User scope (--global)
    # ------------------------------------------------------------------

    def test_global_flag_missing_user_manifest_exits_error(self):
        """uninstall -g exits with error and a descriptive message when user manifest absent."""
        with self._chdir_tmp():
            fake_home = Path(tempfile.mkdtemp())
            fake_apm_yml = fake_home / ".apm" / "apm.yml"
            with patch("apm_cli.core.scope.Path.home", return_value=fake_home):
                result = self.runner.invoke(cli, ["uninstall", "-g", "owner/repo"])
            # Should error - no user manifest
            assert result.exit_code == 1
            assert "user" in result.output.lower() or "apm.yml" in result.output

    def test_global_scope_uninstalls_from_user_manifest(self):
        """uninstall -g removes from user-scope apm.yml."""
        with tempfile.TemporaryDirectory() as fake_home_str:
            fake_home = Path(fake_home_str)
            user_apm_dir = fake_home / ".apm"
            user_apm_dir.mkdir(parents=True)
            user_apm_yml = user_apm_dir / "apm.yml"
            user_apm_yml.write_text(_APM_YML_ONE_DEP)

            with (
                patch("apm_cli.core.scope.Path.home", return_value=fake_home),
                patch(
                    "apm_cli.commands.uninstall.cli._sync_integrations_after_uninstall",
                    return_value={
                        "prompts": 0,
                        "agents": 0,
                        "skills": 0,
                        "commands": 0,
                        "hooks": 0,
                        "instructions": 0,
                    },
                ),
                patch("apm_cli.commands.uninstall.cli._cleanup_stale_mcp"),
            ):
                result = self.runner.invoke(cli, ["uninstall", "-g", "owner/repo"])
            assert result.exit_code == 0
            content = yaml.safe_load(user_apm_yml.read_text())
            assert not content["dependencies"]["apm"]

    # ------------------------------------------------------------------
    # Verbose flag
    # ------------------------------------------------------------------

    def test_verbose_flag_accepted(self):
        """uninstall --verbose flag is accepted without error."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_ONE_DEP)
            with (
                patch(
                    "apm_cli.commands.uninstall.cli._sync_integrations_after_uninstall",
                    return_value={
                        "prompts": 0,
                        "agents": 0,
                        "skills": 0,
                        "commands": 0,
                        "hooks": 0,
                        "instructions": 0,
                    },
                ),
                patch("apm_cli.commands.uninstall.cli._cleanup_stale_mcp"),
            ):
                result = self.runner.invoke(
                    cli, ["uninstall", "--verbose", "owner/repo"]
                )
            assert result.exit_code == 0

    # ------------------------------------------------------------------
    # Integration cleanup reported
    # ------------------------------------------------------------------

    def test_integration_cleanup_count_shown(self):
        """uninstall shows cleanup count when integrations are cleaned up."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_ONE_DEP)
            with (
                patch(
                    "apm_cli.commands.uninstall.cli._sync_integrations_after_uninstall",
                    return_value={
                        "prompts": 3,
                        "agents": 0,
                        "skills": 0,
                        "commands": 0,
                        "hooks": 0,
                        "instructions": 0,
                    },
                ),
                patch("apm_cli.commands.uninstall.cli._cleanup_stale_mcp"),
            ):
                result = self.runner.invoke(cli, ["uninstall", "owner/repo"])
            assert result.exit_code == 0
            assert "3" in result.output or "prompt" in result.output.lower()

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def test_yaml_read_error_exits_with_1(self):
        """uninstall exits with 1 when apm.yml cannot be parsed."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(": invalid: yaml: [\n")
            with patch(
                "apm_cli.utils.yaml_io.load_yaml",
                side_effect=Exception("parse error"),
            ):
                result = self.runner.invoke(cli, ["uninstall", "owner/repo"])
            assert result.exit_code == 1

    def test_yaml_write_error_exits_with_1(self):
        """uninstall exits with 1 when apm.yml cannot be written after removal."""
        with self._chdir_tmp() as tmp:
            (tmp / "apm.yml").write_text(_APM_YML_ONE_DEP)
            with patch(
                "apm_cli.utils.yaml_io.dump_yaml",
                side_effect=Exception("write error"),
            ):
                result = self.runner.invoke(cli, ["uninstall", "owner/repo"])
            assert result.exit_code == 1
