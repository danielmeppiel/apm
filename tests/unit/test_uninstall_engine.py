"""Unit tests for apm_cli.commands.uninstall.engine helper functions.

Covers:
- _parse_dependency_entry
- _validate_uninstall_packages
- _dry_run_uninstall
- _remove_packages_from_disk
- _cleanup_transitive_orphans
- _cleanup_stale_mcp
"""

import builtins
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apm_cli.commands.uninstall.engine import (
    _cleanup_stale_mcp,
    _cleanup_transitive_orphans,
    _dry_run_uninstall,
    _parse_dependency_entry,
    _remove_packages_from_disk,
    _validate_uninstall_packages,
)
from apm_cli.deps.lockfile import LockedDependency
from apm_cli.models.apm_package import DependencyReference


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_logger():
    return MagicMock()


def _make_locked_dep(repo_url, resolved_by=None):
    """Create a LockedDependency for test use."""
    dep = LockedDependency.__new__(LockedDependency)
    dep.repo_url = repo_url
    dep.host = "github.com"
    dep.ref = "main"
    dep.resolved_by = resolved_by
    dep.content_hash = ""
    dep.virtual_path = ""
    return dep


# ---------------------------------------------------------------------------
# _parse_dependency_entry
# ---------------------------------------------------------------------------

class TestParseDependencyEntry:
    def test_passthrough_dependency_reference(self):
        ref = DependencyReference.parse("github.com/owner/repo")
        result = _parse_dependency_entry(ref)
        assert result is ref

    def test_string_github_url(self):
        result = _parse_dependency_entry("github.com/owner/repo")
        assert result.repo_url == "owner/repo"

    def test_string_shorthand(self):
        result = _parse_dependency_entry("owner/repo")
        assert result.repo_url == "owner/repo"

    def test_dict_git_key(self):
        result = _parse_dependency_entry({"git": "github.com/owner/repo"})
        assert result.repo_url == "owner/repo"

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported dependency entry type"):
            _parse_dependency_entry(42)

    def test_invalid_type_list_raises(self):
        with pytest.raises(ValueError, match="Unsupported dependency entry type"):
            _parse_dependency_entry([])


# ---------------------------------------------------------------------------
# _validate_uninstall_packages
# ---------------------------------------------------------------------------

class TestValidateUninstallPackages:
    def test_invalid_format_no_slash(self):
        logger = _make_logger()
        matched, unmatched = _validate_uninstall_packages(["invalid"], [], logger)
        assert matched == []
        assert unmatched == []
        logger.error.assert_called_once()
        assert "owner/repo" in logger.error.call_args[0][0]

    def test_package_not_in_deps(self):
        logger = _make_logger()
        matched, unmatched = _validate_uninstall_packages(
            ["owner/missing"], ["github.com/owner/other"], logger
        )
        assert matched == []
        assert unmatched == ["owner/missing"]
        logger.warning.assert_called_once()

    def test_package_matched_by_identity(self):
        logger = _make_logger()
        deps = ["github.com/owner/repo"]
        matched, unmatched = _validate_uninstall_packages(["owner/repo"], deps, logger)
        assert matched == ["github.com/owner/repo"]
        assert unmatched == []

    def test_package_matched_exact_string(self):
        logger = _make_logger()
        deps = ["owner/repo"]
        matched, unmatched = _validate_uninstall_packages(["owner/repo"], deps, logger)
        assert matched == ["owner/repo"]
        assert unmatched == []

    def test_multiple_packages_mixed(self):
        logger = _make_logger()
        deps = ["github.com/owner/repo1", "github.com/owner/repo2"]
        matched, unmatched = _validate_uninstall_packages(
            ["owner/repo1", "owner/missing"], deps, logger
        )
        assert len(matched) == 1
        assert len(unmatched) == 1
        assert unmatched[0] == "owner/missing"

    def test_empty_packages_list(self):
        logger = _make_logger()
        matched, unmatched = _validate_uninstall_packages([], ["github.com/owner/repo"], logger)
        assert matched == []
        assert unmatched == []

    def test_empty_deps_list(self):
        logger = _make_logger()
        matched, unmatched = _validate_uninstall_packages(["owner/repo"], [], logger)
        assert matched == []
        assert unmatched == ["owner/repo"]

    def test_dependency_reference_object_in_deps(self):
        logger = _make_logger()
        ref = DependencyReference.parse("github.com/owner/repo")
        matched, unmatched = _validate_uninstall_packages(["owner/repo"], [ref], logger)
        assert len(matched) == 1
        assert unmatched == []


# ---------------------------------------------------------------------------
# _dry_run_uninstall
# ---------------------------------------------------------------------------

class TestDryRunUninstall:
    def test_dry_run_no_packages(self, tmp_path):
        logger = _make_logger()
        _dry_run_uninstall([], tmp_path, logger)
        logger.progress.assert_called()
        assert "0" in logger.progress.call_args_list[0][0][0]

    def test_dry_run_package_exists_on_disk(self, tmp_path):
        pkg_dir = tmp_path / "owner" / "repo"
        pkg_dir.mkdir(parents=True)
        logger = _make_logger()
        _dry_run_uninstall(["github.com/owner/repo"], tmp_path, logger)
        progress_messages = [c[0][0] for c in logger.progress.call_args_list]
        assert any("apm_modules" in m for m in progress_messages)

    def test_dry_run_package_not_on_disk(self, tmp_path):
        logger = _make_logger()
        _dry_run_uninstall(["github.com/owner/missing"], tmp_path, logger)
        # Should not crash even if directory doesn't exist
        assert logger.progress.called

    def test_dry_run_shows_lockfile_info(self, tmp_path):
        lockfile_path = tmp_path / "apm.lock.yaml"
        lockfile_path.write_text("dependencies: {}\n")
        logger = _make_logger()
        _dry_run_uninstall(["github.com/owner/repo"], tmp_path, logger)
        # Should complete without error
        assert logger.progress.called


# ---------------------------------------------------------------------------
# _remove_packages_from_disk
# ---------------------------------------------------------------------------

class TestRemovePackagesFromDisk:
    def test_removes_existing_package(self, tmp_path):
        pkg_dir = tmp_path / "owner" / "repo"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "apm.yml").write_text("name: test\nversion: 1.0.0\n")
        logger = _make_logger()
        count = _remove_packages_from_disk(["github.com/owner/repo"], tmp_path, logger)
        assert count == 1
        assert not pkg_dir.exists()

    def test_warns_for_missing_package(self, tmp_path):
        logger = _make_logger()
        count = _remove_packages_from_disk(["github.com/owner/notexist"], tmp_path, logger)
        assert count == 0
        logger.warning.assert_called_once()

    def test_returns_zero_when_modules_dir_absent(self, tmp_path):
        absent = tmp_path / "no_such_dir"
        logger = _make_logger()
        count = _remove_packages_from_disk(["github.com/owner/repo"], absent, logger)
        assert count == 0

    def test_removes_multiple_packages(self, tmp_path):
        for i in range(3):
            d = tmp_path / "owner" / f"repo{i}"
            d.mkdir(parents=True)
        logger = _make_logger()
        packages = [f"github.com/owner/repo{i}" for i in range(3)]
        count = _remove_packages_from_disk(packages, tmp_path, logger)
        assert count == 3

    def test_string_package_fallback(self, tmp_path):
        """String package without parseable URL uses string split."""
        # Create a directory matching the string split approach
        pkg_dir = tmp_path / "owner" / "myrepo"
        pkg_dir.mkdir(parents=True)
        logger = _make_logger()
        # Use a string that won't parse as a proper dep ref but has owner/repo shape
        # _parse_dependency_entry("owner/myrepo") succeeds -- just test removal
        count = _remove_packages_from_disk(["owner/myrepo"], tmp_path, logger)
        assert count == 1

    def test_path_traversal_rejected(self, tmp_path):
        """PathTraversalError during get_install_path should skip with error."""
        from apm_cli.utils.path_security import PathTraversalError

        logger = _make_logger()
        mock_ref = MagicMock()
        mock_ref.get_install_path.side_effect = PathTraversalError("traversal")

        with patch(
            "apm_cli.commands.uninstall.engine._parse_dependency_entry",
            return_value=mock_ref,
        ):
            count = _remove_packages_from_disk(["owner/malicious"], tmp_path, logger)

        assert count == 0
        logger.error.assert_called_once()


# ---------------------------------------------------------------------------
# _cleanup_transitive_orphans
# ---------------------------------------------------------------------------

class TestCleanupTransitiveOrphans:
    def test_no_lockfile_returns_zero(self, tmp_path):
        logger = _make_logger()
        removed, orphans = _cleanup_transitive_orphans(
            None, ["github.com/owner/repo"], tmp_path, tmp_path / "apm.yml", logger
        )
        assert removed == 0
        assert orphans == builtins.set()

    def test_modules_dir_absent_returns_zero(self, tmp_path):
        logger = _make_logger()
        lockfile = MagicMock()
        absent = tmp_path / "absent"
        removed, orphans = _cleanup_transitive_orphans(
            lockfile, ["github.com/owner/repo"], absent, tmp_path / "apm.yml", logger
        )
        assert removed == 0
        assert orphans == builtins.set()

    def test_no_orphans_when_no_transitive_deps(self, tmp_path):
        logger = _make_logger()
        lockfile = MagicMock()
        direct = _make_locked_dep("owner/direct")
        lockfile.get_all_dependencies.return_value = [direct]
        removed, orphans = _cleanup_transitive_orphans(
            lockfile, ["github.com/owner/direct"], tmp_path, tmp_path / "apm.yml", logger
        )
        assert removed == 0
        assert orphans == builtins.set()

    def test_removes_orphaned_transitive_dep(self, tmp_path):
        logger = _make_logger()
        lockfile = MagicMock()

        # transitive dep was resolved by the direct dep we're removing
        transitive = _make_locked_dep("owner/transitive", resolved_by="owner/direct")
        lockfile.get_all_dependencies.return_value = [transitive]
        lockfile.get_dependency.return_value = transitive

        # Create the orphan directory on disk
        orphan_dir = tmp_path / "owner" / "transitive"
        orphan_dir.mkdir(parents=True)

        # apm.yml with no remaining deps
        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text("dependencies:\n  apm: []\n")

        removed, orphans = _cleanup_transitive_orphans(
            lockfile,
            ["github.com/owner/direct"],
            tmp_path,
            apm_yml,
            logger,
        )
        assert removed == 1
        assert "owner/transitive" in orphans
        assert not orphan_dir.exists()

    def test_does_not_remove_still_needed_dep(self, tmp_path):
        logger = _make_logger()
        lockfile = MagicMock()

        # transitive orphan candidate
        transitive = _make_locked_dep("owner/transitive", resolved_by="owner/direct")
        lockfile.get_all_dependencies.return_value = [transitive]
        lockfile.get_dependency.return_value = transitive

        # apm.yml still lists the transitive dep directly
        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text("dependencies:\n  apm:\n    - github.com/owner/transitive\n")

        orphan_dir = tmp_path / "owner" / "transitive"
        orphan_dir.mkdir(parents=True)

        removed, orphans = _cleanup_transitive_orphans(
            lockfile,
            ["github.com/owner/direct"],
            tmp_path,
            apm_yml,
            logger,
        )
        # Orphan should be excluded from actual_orphans because it's still in apm.yml
        assert removed == 0

    def test_transitive_not_on_disk_skips_gracefully(self, tmp_path):
        logger = _make_logger()
        lockfile = MagicMock()
        transitive = _make_locked_dep("owner/transitive", resolved_by="owner/direct")
        lockfile.get_all_dependencies.return_value = [transitive]
        lockfile.get_dependency.return_value = transitive

        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text("dependencies:\n  apm: []\n")
        # Don't create the orphan dir -- test graceful skip
        removed, orphans = _cleanup_transitive_orphans(
            lockfile, ["github.com/owner/direct"], tmp_path, apm_yml, logger
        )
        assert removed == 0
        assert "owner/transitive" in orphans  # detected but not on disk

    def test_chain_of_transitive_orphans(self, tmp_path):
        """A->B->C: removing A should mark B and C as orphans."""
        logger = _make_logger()
        lockfile = MagicMock()

        dep_b = _make_locked_dep("owner/b", resolved_by="owner/a")
        dep_c = _make_locked_dep("owner/c", resolved_by="owner/b")
        lockfile.get_all_dependencies.return_value = [dep_b, dep_c]
        lockfile.get_dependency.side_effect = lambda k: {
            "owner/b": dep_b, "owner/c": dep_c
        }.get(k)

        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text("dependencies:\n  apm: []\n")

        removed, orphans = _cleanup_transitive_orphans(
            lockfile, ["github.com/owner/a"], tmp_path, apm_yml, logger
        )
        assert "owner/b" in orphans
        assert "owner/c" in orphans


# ---------------------------------------------------------------------------
# _cleanup_stale_mcp
# ---------------------------------------------------------------------------

class TestCleanupStaleMcp:
    def test_no_op_when_no_old_servers(self, tmp_path):
        """Should return immediately if old_mcp_servers is empty."""
        apm_package = MagicMock()
        lockfile = MagicMock()
        lockfile_path = tmp_path / "apm.lock.yaml"
        # Should not call MCPIntegrator at all
        with patch("apm_cli.commands.uninstall.engine.MCPIntegrator") as mock_mcp:
            _cleanup_stale_mcp(apm_package, lockfile, lockfile_path, set())
            mock_mcp.collect_transitive.assert_not_called()

    def test_removes_stale_servers(self, tmp_path):
        apm_package = MagicMock()
        apm_package.get_mcp_dependencies.return_value = []
        lockfile = MagicMock()
        lockfile_path = tmp_path / "apm.lock.yaml"
        old_servers = {"stale-server", "still-needed"}

        with patch("apm_cli.commands.uninstall.engine.MCPIntegrator") as mock_mcp:
            mock_mcp.collect_transitive.return_value = []
            mock_mcp.deduplicate.return_value = []
            mock_mcp.get_server_names.return_value = {"still-needed"}
            _cleanup_stale_mcp(
                apm_package, lockfile, lockfile_path, old_servers, modules_dir=tmp_path
            )
            mock_mcp.remove_stale.assert_called_once_with({"stale-server"})
            mock_mcp.update_lockfile.assert_called_once_with({"still-needed"}, lockfile_path)

    def test_no_stale_servers_when_all_remain(self, tmp_path):
        apm_package = MagicMock()
        apm_package.get_mcp_dependencies.return_value = []
        lockfile = MagicMock()
        lockfile_path = tmp_path / "apm.lock.yaml"
        old_servers = {"server-a"}

        with patch("apm_cli.commands.uninstall.engine.MCPIntegrator") as mock_mcp:
            mock_mcp.collect_transitive.return_value = []
            mock_mcp.deduplicate.return_value = []
            mock_mcp.get_server_names.return_value = {"server-a"}  # still present
            _cleanup_stale_mcp(
                apm_package, lockfile, lockfile_path, old_servers, modules_dir=tmp_path
            )
            mock_mcp.remove_stale.assert_not_called()

    def test_exception_in_get_mcp_dependencies_handled(self, tmp_path):
        apm_package = MagicMock()
        apm_package.get_mcp_dependencies.side_effect = RuntimeError("boom")
        lockfile = MagicMock()
        lockfile_path = tmp_path / "apm.lock.yaml"

        with patch("apm_cli.commands.uninstall.engine.MCPIntegrator") as mock_mcp:
            mock_mcp.collect_transitive.return_value = []
            mock_mcp.deduplicate.return_value = []
            mock_mcp.get_server_names.return_value = set()
            # Should not raise
            _cleanup_stale_mcp(
                apm_package, lockfile, lockfile_path, {"stale"}, modules_dir=tmp_path
            )
            mock_mcp.remove_stale.assert_called_once_with({"stale"})
