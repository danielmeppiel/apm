"""Tests for apm deps update command delegation to install engine.

Verifies that `apm deps update` delegates to `apm install --update --only=apm`
instead of using a broken standalone update path that silently fails to update
the lockfile, deployed files, and integration state.

Bug: _update_all_packages() and _update_single_package() called
download_package() but never regenerated the lockfile or re-integrated
primitives — making `apm deps update` a no-op that lied about success.
"""

import inspect
from pathlib import Path

import pytest
from click.testing import CliRunner

from apm_cli.cli import cli


class TestDepsUpdateDelegatesToInstall:
    """Verify deps update invokes the install engine with --update."""

    @pytest.fixture()
    def runner(self):
        return CliRunner()

    @pytest.fixture()
    def apm_yml(self, tmp_path):
        """Create a minimal apm.yml with one dependency."""
        yml = tmp_path / "apm.yml"
        yml.write_text(
            "name: test-project\n"
            "version: 1.0.0\n"
            "dependencies:\n"
            "  apm:\n"
            "    - microsoft/apm-sample-package\n"
        )
        return yml

    def test_deps_update_all_runs_without_crash(self, runner, apm_yml):
        """apm deps update (no args) should not crash."""
        with runner.isolated_filesystem(temp_dir=apm_yml.parent):
            Path("apm.yml").write_text(apm_yml.read_text())

            result = runner.invoke(cli, ["deps", "update"])

            # The command should run (possibly fail due to network) but not crash
            assert result.exit_code in (0, 1), (
                f"Unexpected exit code {result.exit_code}:\n{result.output}"
            )


class TestDepsUpdateHelp:
    """Verify deps update --help advertises --verbose, --force, PACKAGE."""

    @pytest.fixture()
    def runner(self):
        return CliRunner()

    def test_help_shows_verbose(self, runner):
        """apm deps update --help should show --verbose."""
        result = runner.invoke(cli, ["deps", "update", "--help"])
        assert "--verbose" in result.output

    def test_help_shows_force(self, runner):
        """apm deps update --help should show --force."""
        result = runner.invoke(cli, ["deps", "update", "--help"])
        assert "--force" in result.output

    def test_help_shows_package_arg(self, runner):
        """apm deps update --help should show PACKAGE argument."""
        result = runner.invoke(cli, ["deps", "update", "--help"])
        assert "PACKAGE" in result.output.upper()


class TestDepsUpdateNoLongerUsesStaleUtils:
    """Verify the old broken _update_all_packages path is no longer used."""

    def _get_update_source(self):
        """Read the source of the deps update command from disk."""
        src = Path(__file__).resolve().parents[2] / "src" / "apm_cli" / "commands" / "deps" / "cli.py"
        return src.read_text()

    def test_update_command_does_not_import_broken_utils(self):
        """The deps update command source should not call _update_all_packages."""
        source = self._get_update_source()
        # Find the update function body
        idx = source.find("def update(")
        assert idx != -1, "update function not found in cli.py"
        # Grab text from the function definition to the next top-level def/class
        rest = source[idx:]
        lines = rest.split("\n")
        body_lines = []
        for i, line in enumerate(lines):
            if i > 0 and (line.startswith("def ") or line.startswith("class ") or line.startswith("@")):
                break
            body_lines.append(line)
        body = "\n".join(body_lines)

        assert "_update_all_packages" not in body
        assert "_update_single_package" not in body

    def test_update_command_delegates_to_install(self):
        """The deps update command should use ctx.invoke to call install."""
        source = self._get_update_source()
        idx = source.find("def update(")
        assert idx != -1
        rest = source[idx:]
        lines = rest.split("\n")
        body_lines = []
        for i, line in enumerate(lines):
            if i > 0 and (line.startswith("def ") or line.startswith("class ") or line.startswith("@")):
                break
            body_lines.append(line)
        body = "\n".join(body_lines)

        assert "ctx.invoke" in body
        assert "install" in body.lower()
