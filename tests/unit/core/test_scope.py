"""Tests for installation scope resolution."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from apm_cli.core.scope import (
    InstallScope,
    USER_APM_DIR,
    USER_SCOPE_TARGETS,
    ensure_user_dirs,
    get_apm_dir,
    get_deploy_root,
    get_lockfile_dir,
    get_manifest_path,
    get_modules_dir,
)


# ---------------------------------------------------------------------------
# InstallScope enum
# ---------------------------------------------------------------------------


class TestInstallScope:
    """Basic enum sanity checks."""

    def test_values(self):
        assert InstallScope.PROJECT.value == "project"
        assert InstallScope.USER.value == "user"

    def test_from_string(self):
        assert InstallScope("project") is InstallScope.PROJECT
        assert InstallScope("user") is InstallScope.USER

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            InstallScope("global")


# ---------------------------------------------------------------------------
# get_deploy_root
# ---------------------------------------------------------------------------


class TestGetDeployRoot:
    """Tests for get_deploy_root."""

    def test_project_returns_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert get_deploy_root(InstallScope.PROJECT) == tmp_path

    def test_user_returns_home(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            assert get_deploy_root(InstallScope.USER) == tmp_path


# ---------------------------------------------------------------------------
# get_apm_dir
# ---------------------------------------------------------------------------


class TestGetApmDir:
    """Tests for get_apm_dir."""

    def test_project_is_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert get_apm_dir(InstallScope.PROJECT) == tmp_path

    def test_user_is_home_dot_apm(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            assert get_apm_dir(InstallScope.USER) == tmp_path / USER_APM_DIR


# ---------------------------------------------------------------------------
# get_modules_dir
# ---------------------------------------------------------------------------


class TestGetModulesDir:
    """Tests for get_modules_dir."""

    def test_project_modules(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert get_modules_dir(InstallScope.PROJECT) == tmp_path / "apm_modules"

    def test_user_modules(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            assert get_modules_dir(InstallScope.USER) == tmp_path / ".apm" / "apm_modules"


# ---------------------------------------------------------------------------
# get_manifest_path
# ---------------------------------------------------------------------------


class TestGetManifestPath:
    """Tests for get_manifest_path."""

    def test_project_manifest(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert get_manifest_path(InstallScope.PROJECT) == tmp_path / "apm.yml"

    def test_user_manifest(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            assert get_manifest_path(InstallScope.USER) == tmp_path / ".apm" / "apm.yml"


# ---------------------------------------------------------------------------
# get_lockfile_dir
# ---------------------------------------------------------------------------


class TestGetLockfileDir:
    """Tests for get_lockfile_dir."""

    def test_project_lockfile(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert get_lockfile_dir(InstallScope.PROJECT) == tmp_path

    def test_user_lockfile(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            assert get_lockfile_dir(InstallScope.USER) == tmp_path / ".apm"


# ---------------------------------------------------------------------------
# ensure_user_dirs
# ---------------------------------------------------------------------------


class TestEnsureUserDirs:
    """Tests for ensure_user_dirs."""

    def test_creates_dirs(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            result = ensure_user_dirs()
            assert result == tmp_path / ".apm"
            assert result.is_dir()
            assert (result / "apm_modules").is_dir()

    def test_idempotent(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            ensure_user_dirs()
            ensure_user_dirs()  # Should not raise
            assert (tmp_path / ".apm").is_dir()


# ---------------------------------------------------------------------------
# USER_SCOPE_TARGETS registry
# ---------------------------------------------------------------------------


class TestUserScopeTargets:
    """Validate the target support registry."""

    def test_all_known_targets_present(self):
        expected = {"copilot", "claude", "cursor", "opencode"}
        assert set(USER_SCOPE_TARGETS.keys()) == expected

    def test_each_target_has_required_keys(self):
        for name, info in USER_SCOPE_TARGETS.items():
            assert "supported" in info, f"{name} missing 'supported'"
            assert "user_root" in info, f"{name} missing 'user_root'"
            assert "description" in info, f"{name} missing 'description'"

    def test_user_roots_start_with_tilde(self):
        for name, info in USER_SCOPE_TARGETS.items():
            assert info["user_root"].startswith("~/"), (
                f"{name} user_root should start with '~/'"
            )
