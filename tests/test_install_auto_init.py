import os
from pathlib import Path

import yaml
import pytest
from click.testing import CliRunner

import apm_cli.cli as cli_mod
from apm_cli.cli import cli


def test_install_creates_minimal_project(tmp_path, monkeypatch):
    """When apm.yml is missing and a package is passed to `apm install`,
    the CLI should create a minimal apm.yml and .apm/ structure so the
    installation can proceed (dry-run used to avoid network operations).
    """
    runner = CliRunner()
    # Avoid network/git checks during validation
    monkeypatch.setattr(cli_mod, "_validate_package_exists", lambda pkg: True)

    # CliRunner.invoke in this environment does not accept cwd reliably, so
    # change directory manually for the duration of the invocation.
    old_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        result = runner.invoke(cli, ["install", "owner/repo", "--dry-run"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0, result.output

    apm_yml = tmp_path / "apm.yml"
    assert apm_yml.exists(), "apm.yml should be created when running install with packages"

    # Load config to ensure it is valid YAML and contains expected keys
    cfg = yaml.safe_load(apm_yml.read_text())
    assert isinstance(cfg, dict)
    assert "dependencies" in cfg


def test_install_conflict_aborts(tmp_path, monkeypatch):
    """If the package already exists in apm.yml, `apm install <pkg>` should
    report a conflict and abort (non-zero exit)."""
    runner = CliRunner()
    # Create an apm.yml that already contains the package
    content = {
        "name": "proj",
        "version": "1.0.0",
        "dependencies": {"apm": ["owner/repo"], "mcp": []},
    }
    apm_yml = tmp_path / "apm.yml"
    apm_yml.write_text(yaml.safe_dump(content))

    # Avoid network/git checks during validation
    monkeypatch.setattr(cli_mod, "_validate_package_exists", lambda pkg: True)

    old_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        result = runner.invoke(cli, ["install", "owner/repo"])
    finally:
        os.chdir(old_cwd)

    # The CLI should exit with non-zero status due to conflict
    assert result.exit_code != 0
    assert "Package conflict" in result.output or "Aborting due to" in result.output
