"""Tests for untested BaseIntegrator utility methods.

Covers:
- normalize_managed_files()
- cleanup_empty_parents()
- sync_remove_files()
- find_files_by_glob()
"""

import pytest
from pathlib import Path

from apm_cli.integration.base_integrator import BaseIntegrator


# ---------------------------------------------------------------------------
# normalize_managed_files
# ---------------------------------------------------------------------------


class TestNormalizeManagedFiles:
    """Tests for BaseIntegrator.normalize_managed_files()."""

    def test_returns_none_for_none_input(self):
        result = BaseIntegrator.normalize_managed_files(None)
        assert result is None

    def test_returns_empty_set_for_empty_input(self):
        result = BaseIntegrator.normalize_managed_files(set())
        assert result == set()

    def test_forward_slashes_unchanged(self):
        files = {".github/prompts/foo.md", ".claude/commands/bar.md"}
        result = BaseIntegrator.normalize_managed_files(files)
        assert result == files

    def test_backslashes_converted_to_forward_slashes(self):
        files = {".github\\prompts\\foo.md", ".claude\\commands\\bar.md"}
        result = BaseIntegrator.normalize_managed_files(files)
        assert result == {".github/prompts/foo.md", ".claude/commands/bar.md"}

    def test_mixed_separators_normalized(self):
        files = {".github/prompts\\foo.md"}
        result = BaseIntegrator.normalize_managed_files(files)
        assert ".github/prompts/foo.md" in result

    def test_returns_new_set_not_in_place(self):
        original = {".github\\prompts\\foo.md"}
        result = BaseIntegrator.normalize_managed_files(original)
        # Original should be unchanged
        assert ".github\\prompts\\foo.md" in original
        assert ".github/prompts/foo.md" in result

    def test_deduplication_after_normalization(self):
        # Both backslash and forward-slash versions point to same path
        files = {".github\\prompts\\foo.md", ".github/prompts/foo.md"}
        result = BaseIntegrator.normalize_managed_files(files)
        assert len(result) == 1
        assert ".github/prompts/foo.md" in result

    def test_large_set_normalized(self):
        files = {f".github\\prompts\\file_{i}.md" for i in range(100)}
        result = BaseIntegrator.normalize_managed_files(files)
        assert len(result) == 100
        assert all("/" in p and "\\" not in p for p in result)


# ---------------------------------------------------------------------------
# cleanup_empty_parents
# ---------------------------------------------------------------------------


class TestCleanupEmptyParents:
    """Tests for BaseIntegrator.cleanup_empty_parents()."""

    def test_no_op_for_empty_list(self, tmp_path):
        # Should not raise
        BaseIntegrator.cleanup_empty_parents([], tmp_path)

    def test_removes_empty_intermediate_dirs(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        file_path = nested / "file.txt"
        file_path.write_text("content")
        file_path.unlink()

        BaseIntegrator.cleanup_empty_parents([file_path], tmp_path)

        assert not (tmp_path / "a").exists()

    def test_does_not_remove_stop_at_dir(self, tmp_path):
        stop_dir = tmp_path / "base"
        stop_dir.mkdir()
        nested = stop_dir / "sub"
        nested.mkdir()
        file_path = nested / "file.txt"
        file_path.write_text("content")
        file_path.unlink()

        BaseIntegrator.cleanup_empty_parents([file_path], stop_dir)

        # stop_dir should still exist
        assert stop_dir.exists()
        # sub should be removed (empty)
        assert not nested.exists()

    def test_does_not_remove_non_empty_dirs(self, tmp_path):
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        # Put another file in 'a' so it's not empty
        (tmp_path / "a" / "sibling.txt").write_text("keep me")
        deleted = nested / "file.txt"
        deleted.write_text("gone")
        deleted.unlink()
        nested.rmdir()

        BaseIntegrator.cleanup_empty_parents([deleted], tmp_path)

        # 'a' still has sibling.txt, so should remain
        assert (tmp_path / "a").exists()

    def test_multiple_deleted_files_same_dir(self, tmp_path):
        parent = tmp_path / "parent"
        parent.mkdir()
        f1 = parent / "file1.txt"
        f2 = parent / "file2.txt"
        f1.write_text("a")
        f2.write_text("b")
        f1.unlink()
        f2.unlink()

        BaseIntegrator.cleanup_empty_parents([f1, f2], tmp_path)

        assert not parent.exists()

    def test_deeply_nested_cleanup(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "d" / "e"
        deep.mkdir(parents=True)
        f = deep / "file.txt"
        f.write_text("x")
        f.unlink()

        BaseIntegrator.cleanup_empty_parents([f], tmp_path)

        assert not (tmp_path / "a").exists()

    def test_cleanup_stops_at_ancestor_boundary(self, tmp_path):
        # stop_at is a direct child of tmp_path
        stop = tmp_path / "stop_here"
        stop.mkdir()
        nested = stop / "inner" / "deep"
        nested.mkdir(parents=True)
        f = nested / "file.txt"
        f.write_text("x")
        f.unlink()

        BaseIntegrator.cleanup_empty_parents([f], stop)

        # stop_here should survive
        assert stop.exists()
        # inner and deep should be cleaned up
        assert not (stop / "inner").exists()


# ---------------------------------------------------------------------------
# sync_remove_files
# ---------------------------------------------------------------------------


class TestSyncRemoveFiles:
    """Tests for BaseIntegrator.sync_remove_files()."""

    def _make_files(self, root, paths):
        """Create files at the given relative paths under root."""
        for p in paths:
            full = root / p
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text("content")

    def test_removes_matching_files(self, tmp_path):
        self._make_files(tmp_path, [".github/prompts/foo.md"])
        managed = {".github/prompts/foo.md"}

        stats = BaseIntegrator.sync_remove_files(
            tmp_path,
            managed,
            prefix=".github/prompts/",
        )

        assert stats["files_removed"] == 1
        assert stats["errors"] == 0
        assert not (tmp_path / ".github/prompts/foo.md").exists()

    def test_skips_files_not_matching_prefix(self, tmp_path):
        self._make_files(tmp_path, [".claude/commands/foo.md"])
        managed = {".claude/commands/foo.md"}

        stats = BaseIntegrator.sync_remove_files(
            tmp_path,
            managed,
            prefix=".github/prompts/",
        )

        assert stats["files_removed"] == 0
        # File should still exist
        assert (tmp_path / ".claude/commands/foo.md").exists()

    def test_skips_nonexistent_files(self, tmp_path):
        managed = {".github/prompts/nonexistent.md"}

        stats = BaseIntegrator.sync_remove_files(
            tmp_path,
            managed,
            prefix=".github/prompts/",
        )

        assert stats["files_removed"] == 0
        assert stats["errors"] == 0

    def test_uses_legacy_glob_when_managed_files_none(self, tmp_path):
        glob_dir = tmp_path / ".github" / "prompts"
        glob_dir.mkdir(parents=True)
        (glob_dir / "foo-apm.prompt.md").write_text("x")
        (glob_dir / "unrelated.md").write_text("y")

        stats = BaseIntegrator.sync_remove_files(
            tmp_path,
            None,  # managed_files is None -> use legacy glob
            prefix=".github/prompts/",
            legacy_glob_dir=glob_dir,
            legacy_glob_pattern="*-apm.prompt.md",
        )

        assert stats["files_removed"] == 1
        assert not (glob_dir / "foo-apm.prompt.md").exists()
        assert (glob_dir / "unrelated.md").exists()

    def test_legacy_glob_skipped_when_dir_missing(self, tmp_path):
        missing_dir = tmp_path / "nonexistent"

        stats = BaseIntegrator.sync_remove_files(
            tmp_path,
            None,
            prefix=".github/prompts/",
            legacy_glob_dir=missing_dir,
            legacy_glob_pattern="*.md",
        )

        assert stats["files_removed"] == 0
        assert stats["errors"] == 0

    def test_removes_multiple_files(self, tmp_path):
        paths = [
            ".github/prompts/a.md",
            ".github/prompts/b.md",
            ".github/prompts/c.md",
        ]
        self._make_files(tmp_path, paths)
        managed = set(paths)

        stats = BaseIntegrator.sync_remove_files(
            tmp_path,
            managed,
            prefix=".github/prompts/",
        )

        assert stats["files_removed"] == 3
        for p in paths:
            assert not (tmp_path / p).exists()

    def test_rejects_traversal_paths(self, tmp_path):
        """validate_deploy_path prevents removal of paths with '..'."""
        managed = {"../etc/passwd"}

        stats = BaseIntegrator.sync_remove_files(
            tmp_path,
            managed,
            prefix="../",
        )

        # The traversal path should be rejected by validate_deploy_path
        assert stats["files_removed"] == 0

    def test_skips_files_not_in_allowed_prefix(self, tmp_path):
        # A file under /tmp/evil/ is NOT an APM-managed prefix
        managed = {"evil/file.md"}

        stats = BaseIntegrator.sync_remove_files(
            tmp_path,
            managed,
            prefix="evil/",
        )

        assert stats["files_removed"] == 0

    def test_legacy_glob_no_pattern_does_nothing(self, tmp_path):
        """Without both dir and pattern, legacy fallback is skipped."""
        stats = BaseIntegrator.sync_remove_files(
            tmp_path,
            None,
            prefix=".github/prompts/",
            legacy_glob_dir=tmp_path,
            legacy_glob_pattern=None,
        )
        assert stats["files_removed"] == 0


# ---------------------------------------------------------------------------
# find_files_by_glob
# ---------------------------------------------------------------------------


class TestFindFilesByGlob:
    """Tests for BaseIntegrator.find_files_by_glob()."""

    def test_finds_matching_files(self, tmp_path):
        (tmp_path / "a.prompt.md").write_text("x")
        (tmp_path / "b.prompt.md").write_text("x")
        (tmp_path / "other.md").write_text("x")

        results = BaseIntegrator.find_files_by_glob(tmp_path, "*.prompt.md")

        assert len(results) == 2
        names = {f.name for f in results}
        assert names == {"a.prompt.md", "b.prompt.md"}

    def test_returns_empty_list_when_no_matches(self, tmp_path):
        (tmp_path / "file.txt").write_text("x")

        results = BaseIntegrator.find_files_by_glob(tmp_path, "*.prompt.md")

        assert results == []

    def test_returns_empty_list_for_nonexistent_dir(self, tmp_path):
        missing = tmp_path / "nonexistent"

        results = BaseIntegrator.find_files_by_glob(missing, "*.md")

        assert results == []

    def test_searches_subdirs(self, tmp_path):
        subdir = tmp_path / ".apm" / "prompts"
        subdir.mkdir(parents=True)
        (subdir / "skill.prompt.md").write_text("x")

        results = BaseIntegrator.find_files_by_glob(
            tmp_path, "*.prompt.md", subdirs=[".apm/prompts"]
        )

        assert len(results) == 1
        assert results[0].name == "skill.prompt.md"

    def test_deduplicates_across_dirs(self, tmp_path):
        """If the same file appears via multiple dirs it's included once."""
        f = tmp_path / "skill.prompt.md"
        f.write_text("x")

        # Pass tmp_path as both root and subdir to force duplicate discovery
        results = BaseIntegrator.find_files_by_glob(
            tmp_path, "*.prompt.md", subdirs=["."]
        )

        names = [r.name for r in results]
        assert names.count("skill.prompt.md") == 1

    def test_combines_root_and_subdir_results(self, tmp_path):
        (tmp_path / "root.prompt.md").write_text("x")
        subdir = tmp_path / ".apm" / "prompts"
        subdir.mkdir(parents=True)
        (subdir / "sub.prompt.md").write_text("x")

        results = BaseIntegrator.find_files_by_glob(
            tmp_path, "*.prompt.md", subdirs=[".apm/prompts"]
        )

        names = {f.name for f in results}
        assert names == {"root.prompt.md", "sub.prompt.md"}

    def test_skips_missing_subdir(self, tmp_path):
        (tmp_path / "root.prompt.md").write_text("x")

        results = BaseIntegrator.find_files_by_glob(
            tmp_path, "*.prompt.md", subdirs=["missing_subdir"]
        )

        assert len(results) == 1
        assert results[0].name == "root.prompt.md"

    def test_returns_sorted_results_per_dir(self, tmp_path):
        for name in ["c.prompt.md", "a.prompt.md", "b.prompt.md"]:
            (tmp_path / name).write_text("x")

        results = BaseIntegrator.find_files_by_glob(tmp_path, "*.prompt.md")

        names = [f.name for f in results]
        assert names == sorted(names)
