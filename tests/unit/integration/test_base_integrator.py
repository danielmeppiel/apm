"""Unit tests for BaseIntegrator utility methods.

Covers methods that are exercised indirectly through integrator
subclasses but lack direct unit tests:
- cleanup_empty_parents
- find_files_by_glob
- normalize_managed_files
- check_collision (diagnostics path)
- resolve_links / init_link_resolver
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apm_cli.integration.base_integrator import BaseIntegrator, IntegrationResult

# ---------------------------------------------------------------------------
# IntegrationResult dataclass
# ---------------------------------------------------------------------------


class TestIntegrationResult:
    def test_defaults(self):
        r = IntegrationResult(
            files_integrated=1,
            files_updated=0,
            files_skipped=0,
            target_paths=[],
        )
        assert r.links_resolved == 0
        assert r.scripts_copied == 0
        assert r.sub_skills_promoted == 0
        assert r.skill_created is False

    def test_custom_values(self):
        r = IntegrationResult(
            files_integrated=3,
            files_updated=1,
            files_skipped=2,
            target_paths=[Path("/a"), Path("/b")],
            links_resolved=5,
            scripts_copied=2,
            sub_skills_promoted=1,
            skill_created=True,
        )
        assert r.files_integrated == 3
        assert r.links_resolved == 5
        assert r.skill_created is True
        assert len(r.target_paths) == 2


# ---------------------------------------------------------------------------
# cleanup_empty_parents
# ---------------------------------------------------------------------------


class TestCleanupEmptyParents:
    def test_empty_list_is_noop(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        BaseIntegrator.cleanup_empty_parents([], tmp_path)
        assert deep.exists()

    def test_removes_empty_parent(self, tmp_path):
        parent = tmp_path / "owner" / "repo"
        parent.mkdir(parents=True)
        child_file = parent / "file.txt"
        child_file.write_text("x")
        # Remove file manually, then clean parents
        child_file.unlink()
        BaseIntegrator.cleanup_empty_parents([child_file], tmp_path)
        assert not parent.exists()
        # stop_at (tmp_path) itself must remain
        assert tmp_path.exists()

    def test_does_not_remove_nonempty_parent(self, tmp_path):
        parent = tmp_path / "owner" / "repo"
        parent.mkdir(parents=True)
        sibling = parent / "other.txt"
        sibling.write_text("keep me")
        deleted = parent / "gone.txt"
        BaseIntegrator.cleanup_empty_parents([deleted], tmp_path)
        assert parent.exists()

    def test_stops_at_stop_at_boundary(self, tmp_path):
        stop = tmp_path / "base"
        stop.mkdir()
        inner = stop / "inner"
        inner.mkdir()
        deleted = inner / "file.txt"
        BaseIntegrator.cleanup_empty_parents([deleted], stop)
        # inner should be removed (it was empty)
        assert not inner.exists()
        # stop itself should remain
        assert stop.exists()
        # tmp_path above stop should also remain
        assert tmp_path.exists()

    def test_deep_hierarchy_removed_bottom_up(self, tmp_path):
        a = tmp_path / "a"
        b = a / "b"
        c = b / "c"
        c.mkdir(parents=True)
        f = c / "f.txt"
        BaseIntegrator.cleanup_empty_parents([f], tmp_path)
        assert not c.exists()
        assert not b.exists()
        assert not a.exists()

    def test_sibling_preserved_when_other_branch_removed(self, tmp_path):
        shared = tmp_path / "shared"
        shared.mkdir()
        branch_a = shared / "branch_a"
        branch_b = shared / "branch_b"
        branch_a.mkdir()
        branch_b.mkdir()
        (branch_b / "keep.txt").write_text("keep")
        deleted = branch_a / "gone.txt"
        BaseIntegrator.cleanup_empty_parents([deleted], tmp_path)
        assert not branch_a.exists()
        assert branch_b.exists()
        assert shared.exists()

    def test_nonexistent_paths_handled_gracefully(self, tmp_path):
        ghost = tmp_path / "nonexistent" / "file.txt"
        # Should not raise even if the parent never existed
        BaseIntegrator.cleanup_empty_parents([ghost], tmp_path)


# ---------------------------------------------------------------------------
# find_files_by_glob
# ---------------------------------------------------------------------------


class TestFindFilesByGlob:
    def test_empty_dir_returns_empty(self, tmp_path):
        results = BaseIntegrator.find_files_by_glob(tmp_path, "*.md")
        assert results == []

    def test_finds_files_matching_pattern(self, tmp_path):
        (tmp_path / "a.prompt.md").write_text("A")
        (tmp_path / "b.prompt.md").write_text("B")
        (tmp_path / "readme.txt").write_text("ignore")
        results = BaseIntegrator.find_files_by_glob(tmp_path, "*.prompt.md")
        names = {r.name for r in results}
        assert names == {"a.prompt.md", "b.prompt.md"}

    def test_searches_subdirs(self, tmp_path):
        sub = tmp_path / ".apm" / "prompts"
        sub.mkdir(parents=True)
        (sub / "extra.prompt.md").write_text("extra")
        (tmp_path / "root.prompt.md").write_text("root")
        results = BaseIntegrator.find_files_by_glob(
            tmp_path, "*.prompt.md", subdirs=[".apm/prompts"]
        )
        names = {r.name for r in results}
        assert names == {"extra.prompt.md", "root.prompt.md"}

    def test_deduplicates_overlapping_results(self, tmp_path):
        f = tmp_path / "file.md"
        f.write_text("x")
        # Include tmp_path itself twice via subdirs trick (same resolved path)
        results = BaseIntegrator.find_files_by_glob(tmp_path, "*.md", subdirs=["."])
        # Should not duplicate
        assert len(results) == 1

    def test_nonexistent_subdir_silently_skipped(self, tmp_path):
        (tmp_path / "root.md").write_text("r")
        results = BaseIntegrator.find_files_by_glob(
            tmp_path, "*.md", subdirs=["nonexistent/dir"]
        )
        assert len(results) == 1

    def test_nonexistent_package_path_returns_empty(self, tmp_path):
        gone = tmp_path / "does_not_exist"
        results = BaseIntegrator.find_files_by_glob(gone, "*.md")
        assert results == []

    def test_returns_sorted_results(self, tmp_path):
        for name in ["z.md", "a.md", "m.md"]:
            (tmp_path / name).write_text(name)
        results = BaseIntegrator.find_files_by_glob(tmp_path, "*.md")
        names = [r.name for r in results]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# normalize_managed_files
# ---------------------------------------------------------------------------


class TestNormalizeManagedFiles:
    def test_none_returns_none(self):
        assert BaseIntegrator.normalize_managed_files(None) is None

    def test_already_normalized_unchanged(self):
        files = {"a/b/c.md", "x/y.txt"}
        result = BaseIntegrator.normalize_managed_files(files)
        assert result == files

    def test_backslashes_converted(self):
        files = {"a\\b\\c.md", "x\\y.txt"}
        result = BaseIntegrator.normalize_managed_files(files)
        assert result == {"a/b/c.md", "x/y.txt"}

    def test_mixed_separators(self):
        files = {"a\\b/c.md"}
        result = BaseIntegrator.normalize_managed_files(files)
        assert result == {"a/b/c.md"}

    def test_empty_set(self):
        result = BaseIntegrator.normalize_managed_files(set())
        assert result == set()


# ---------------------------------------------------------------------------
# check_collision -- diagnostics parameter
# ---------------------------------------------------------------------------


class TestCheckCollisionDiagnostics:
    """Test the diagnostics path in check_collision."""

    def test_diagnostics_skip_called_on_collision(self, tmp_path):
        target = tmp_path / "user_file.md"
        target.write_text("user content")
        managed = {"other/file.md"}  # does NOT contain target's rel_path
        diagnostics = MagicMock()

        result = BaseIntegrator.check_collision(
            target_path=target,
            rel_path="user_file.md",
            managed_files=managed,
            force=False,
            diagnostics=diagnostics,
        )

        assert result is True
        diagnostics.skip.assert_called_once_with("user_file.md")

    def test_no_warning_emitted_when_diagnostics_provided(self, tmp_path):
        target = tmp_path / "user_file.md"
        target.write_text("content")
        managed = set()
        diagnostics = MagicMock()

        with patch("apm_cli.integration.base_integrator._rich_warning") as mock_warn:
            BaseIntegrator.check_collision(
                target_path=target,
                rel_path="user_file.md",
                managed_files=managed,
                force=False,
                diagnostics=diagnostics,
            )
            mock_warn.assert_not_called()

    def test_warning_emitted_when_no_diagnostics(self, tmp_path):
        target = tmp_path / "user_file.md"
        target.write_text("content")
        managed = set()

        with patch("apm_cli.integration.base_integrator._rich_warning") as mock_warn:
            result = BaseIntegrator.check_collision(
                target_path=target,
                rel_path="user_file.md",
                managed_files=managed,
                force=False,
                diagnostics=None,
            )
            assert result is True
            mock_warn.assert_called_once()


# ---------------------------------------------------------------------------
# resolve_links / init_link_resolver
# ---------------------------------------------------------------------------


class TestResolveLinks:
    def test_returns_unchanged_when_no_resolver(self):
        integrator = BaseIntegrator()
        assert integrator.link_resolver is None
        content = "Some content with [link](ref)"
        result, count = integrator.resolve_links(
            content, Path("src.md"), Path("dst.md")
        )
        assert result == content
        assert count == 0

    def test_returns_zero_links_when_resolver_returns_same(self):
        integrator = BaseIntegrator()
        mock_resolver = MagicMock()
        mock_resolver.resolve_links_for_installation.return_value = "unchanged"
        integrator.link_resolver = mock_resolver

        result, count = integrator.resolve_links(
            "unchanged", Path("src.md"), Path("dst.md")
        )
        assert result == "unchanged"
        assert count == 0

    def test_counts_resolved_links(self):
        integrator = BaseIntegrator()
        mock_resolver = MagicMock()
        original = "See [guide](../guides/guide.md) and [ref](../refs/ref.md)"
        resolved = "See [guide](guides/guide.md) and [ref](refs/ref.md)"
        mock_resolver.resolve_links_for_installation.return_value = resolved
        integrator.link_resolver = mock_resolver

        result, count = integrator.resolve_links(
            original, Path("src.md"), Path("dst.md")
        )
        assert result == resolved
        assert count == 2

    def test_init_link_resolver_sets_none_on_exception(self, tmp_path):
        """If discover_primitives raises, link_resolver should be None."""
        integrator = BaseIntegrator()
        package_info = MagicMock()
        package_info.install_path = tmp_path / "nonexistent"

        with patch(
            "apm_cli.integration.base_integrator.discover_primitives",
            side_effect=Exception("fail"),
        ):
            integrator.init_link_resolver(package_info, tmp_path)

        assert integrator.link_resolver is None

    def test_init_link_resolver_sets_resolver_on_success(self, tmp_path):
        integrator = BaseIntegrator()
        package_info = MagicMock()
        package_info.install_path = tmp_path

        with (
            patch(
                "apm_cli.integration.base_integrator.discover_primitives",
                return_value={},
            ),
            patch(
                "apm_cli.integration.base_integrator.UnifiedLinkResolver"
            ) as MockResolver,
        ):
            mock_instance = MagicMock()
            MockResolver.return_value = mock_instance
            integrator.init_link_resolver(package_info, tmp_path)

        assert integrator.link_resolver is mock_instance


# ---------------------------------------------------------------------------
# should_integrate
# ---------------------------------------------------------------------------


class TestShouldIntegrate:
    def test_always_returns_true(self, tmp_path):
        integrator = BaseIntegrator()
        assert integrator.should_integrate(tmp_path) is True
