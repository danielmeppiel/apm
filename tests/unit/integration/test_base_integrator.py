"""Unit tests for BaseIntegrator shared infrastructure.

Covers:
- IntegrationResult dataclass defaults and fields
- should_integrate() always returns True
- normalize_managed_files() path-separator normalisation
- cleanup_empty_parents() bottom-up empty-dir removal
- sync_remove_files() manifest mode and legacy glob fallback
- find_files_by_glob() file discovery, deduplication, and subdir support
"""

import pytest
from pathlib import Path

from apm_cli.integration.base_integrator import BaseIntegrator, IntegrationResult


# ---------------------------------------------------------------------------
# IntegrationResult dataclass
# ---------------------------------------------------------------------------


class TestIntegrationResult:
    def test_required_fields(self):
        result = IntegrationResult(
            files_integrated=3,
            files_updated=0,
            files_skipped=1,
            target_paths=[Path("/tmp/a"), Path("/tmp/b")],
        )
        assert result.files_integrated == 3
        assert result.files_updated == 0
        assert result.files_skipped == 1
        assert len(result.target_paths) == 2

    def test_optional_fields_default_to_zero_or_false(self):
        result = IntegrationResult(
            files_integrated=0,
            files_updated=0,
            files_skipped=0,
            target_paths=[],
        )
        assert result.links_resolved == 0
        assert result.scripts_copied == 0
        assert result.sub_skills_promoted == 0
        assert result.skill_created is False

    def test_optional_fields_can_be_set(self):
        result = IntegrationResult(
            files_integrated=1,
            files_updated=0,
            files_skipped=0,
            target_paths=[],
            links_resolved=2,
            scripts_copied=1,
            sub_skills_promoted=3,
            skill_created=True,
        )
        assert result.links_resolved == 2
        assert result.scripts_copied == 1
        assert result.sub_skills_promoted == 3
        assert result.skill_created is True


# ---------------------------------------------------------------------------
# should_integrate
# ---------------------------------------------------------------------------


class TestShouldIntegrate:
    def test_always_returns_true(self, tmp_path):
        integrator = BaseIntegrator()
        assert integrator.should_integrate(tmp_path) is True

    def test_returns_true_for_nonexistent_root(self, tmp_path):
        integrator = BaseIntegrator()
        assert integrator.should_integrate(tmp_path / "nonexistent") is True


# ---------------------------------------------------------------------------
# normalize_managed_files
# ---------------------------------------------------------------------------


class TestNormalizeManagedFiles:
    def test_returns_none_for_none_input(self):
        assert BaseIntegrator.normalize_managed_files(None) is None

    def test_normalizes_backslashes_to_forward_slashes(self):
        result = BaseIntegrator.normalize_managed_files({
            ".github\\prompts\\foo.md",
            ".github\\prompts\\bar.md",
        })
        assert ".github/prompts/foo.md" in result
        assert ".github/prompts/bar.md" in result

    def test_forward_slashes_unchanged(self):
        files = {".github/prompts/foo.md", ".claude/commands/bar.md"}
        result = BaseIntegrator.normalize_managed_files(files)
        assert result == files

    def test_empty_set_returns_empty_set(self):
        result = BaseIntegrator.normalize_managed_files(set())
        assert result == set()

    def test_mixed_separators(self):
        result = BaseIntegrator.normalize_managed_files({
            ".github\\prompts/foo.md",
        })
        assert ".github/prompts/foo.md" in result


# ---------------------------------------------------------------------------
# cleanup_empty_parents
# ---------------------------------------------------------------------------


class TestCleanupEmptyParents:
    def test_removes_empty_parent_directories(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        target_file = deep / "file.md"
        target_file.write_text("content", encoding="utf-8")
        target_file.unlink()

        BaseIntegrator.cleanup_empty_parents([deep / "file.md"], tmp_path)

        assert not (tmp_path / "a" / "b" / "c").exists()
        assert not (tmp_path / "a" / "b").exists()
        assert not (tmp_path / "a").exists()

    def test_does_not_remove_stop_at_directory(self, tmp_path):
        base = tmp_path / "base"
        sub = base / "sub"
        sub.mkdir(parents=True)
        file = sub / "file.md"
        file.write_text("content", encoding="utf-8")
        file.unlink()

        BaseIntegrator.cleanup_empty_parents([file], base)

        # sub is removed (it's empty), but base is kept
        assert not sub.exists()
        assert base.exists()

    def test_does_not_remove_non_empty_parent(self, tmp_path):
        parent = tmp_path / "parent"
        child1 = parent / "child1"
        child1.mkdir(parents=True)
        sibling = parent / "sibling.txt"
        sibling.write_text("keep me", encoding="utf-8")

        file = child1 / "file.md"
        file.write_text("content", encoding="utf-8")
        file.unlink()

        BaseIntegrator.cleanup_empty_parents([file], tmp_path)

        # child1 removed (empty), parent kept (has sibling.txt)
        assert not child1.exists()
        assert parent.exists()
        assert sibling.exists()

    def test_handles_empty_deleted_paths(self, tmp_path):
        # Should not raise or remove anything
        BaseIntegrator.cleanup_empty_parents([], tmp_path)
        assert tmp_path.exists()

    def test_multiple_deleted_files_share_parent(self, tmp_path):
        dir_a = tmp_path / "a" / "b"
        dir_a.mkdir(parents=True)
        f1 = dir_a / "file1.md"
        f2 = dir_a / "file2.md"
        f1.write_text("1", encoding="utf-8")
        f2.write_text("2", encoding="utf-8")
        f1.unlink()
        f2.unlink()

        BaseIntegrator.cleanup_empty_parents([f1, f2], tmp_path)
        assert not dir_a.exists()
        assert not (tmp_path / "a").exists()

    def test_skips_already_removed_paths(self, tmp_path):
        deep = tmp_path / "x" / "y"
        deep.mkdir(parents=True)
        ghost = deep / "ghost.md"
        # ghost never created on disk -- should not raise

        BaseIntegrator.cleanup_empty_parents([ghost], tmp_path)
        # x/y should be cleaned up since it's empty
        assert not deep.exists()


# ---------------------------------------------------------------------------
# sync_remove_files
# ---------------------------------------------------------------------------


class TestSyncRemoveFiles:
    def test_removes_file_matching_prefix(self, tmp_path):
        prompt_dir = tmp_path / ".github" / "prompts"
        prompt_dir.mkdir(parents=True)
        f = prompt_dir / "foo-apm.prompt.md"
        f.write_text("content", encoding="utf-8")

        managed = {".github/prompts/foo-apm.prompt.md"}
        stats = BaseIntegrator.sync_remove_files(
            tmp_path, managed, prefix=".github/prompts/"
        )

        assert stats["files_removed"] == 1
        assert stats["errors"] == 0
        assert not f.exists()

    def test_skips_file_not_matching_prefix(self, tmp_path):
        prompt_dir = tmp_path / ".github" / "prompts"
        prompt_dir.mkdir(parents=True)
        f = prompt_dir / "keep-me.prompt.md"
        f.write_text("content", encoding="utf-8")

        managed = {".github/prompts/keep-me.prompt.md"}
        # Use a different prefix
        stats = BaseIntegrator.sync_remove_files(
            tmp_path, managed, prefix=".claude/commands/"
        )

        assert stats["files_removed"] == 0
        assert f.exists()

    def test_skips_nonexistent_file(self, tmp_path):
        managed = {".github/prompts/ghost.prompt.md"}
        stats = BaseIntegrator.sync_remove_files(
            tmp_path, managed, prefix=".github/prompts/"
        )
        assert stats["files_removed"] == 0
        assert stats["errors"] == 0

    def test_legacy_glob_fallback_when_no_managed_files(self, tmp_path):
        prompt_dir = tmp_path / ".github" / "prompts"
        prompt_dir.mkdir(parents=True)
        f1 = prompt_dir / "a-apm.prompt.md"
        f2 = prompt_dir / "b-apm.prompt.md"
        keep = prompt_dir / "user.prompt.md"
        f1.write_text("a", encoding="utf-8")
        f2.write_text("b", encoding="utf-8")
        keep.write_text("keep", encoding="utf-8")

        stats = BaseIntegrator.sync_remove_files(
            tmp_path,
            managed_files=None,
            prefix=".github/prompts/",
            legacy_glob_dir=prompt_dir,
            legacy_glob_pattern="*-apm.prompt.md",
        )

        assert stats["files_removed"] == 2
        assert not f1.exists()
        assert not f2.exists()
        assert keep.exists()

    def test_legacy_glob_skipped_when_dir_missing(self, tmp_path):
        missing_dir = tmp_path / "nonexistent"
        stats = BaseIntegrator.sync_remove_files(
            tmp_path,
            managed_files=None,
            prefix=".github/prompts/",
            legacy_glob_dir=missing_dir,
            legacy_glob_pattern="*.md",
        )
        assert stats["files_removed"] == 0

    def test_no_legacy_glob_when_managed_files_is_empty_set(self, tmp_path):
        # Empty set means manifest mode -- legacy glob must NOT run.
        prompt_dir = tmp_path / ".github" / "prompts"
        prompt_dir.mkdir(parents=True)
        f = prompt_dir / "legacy.prompt.md"
        f.write_text("x", encoding="utf-8")

        stats = BaseIntegrator.sync_remove_files(
            tmp_path,
            managed_files=set(),
            prefix=".github/prompts/",
            legacy_glob_dir=prompt_dir,
            legacy_glob_pattern="*.prompt.md",
        )
        assert stats["files_removed"] == 0
        assert f.exists()

    def test_skips_path_traversal_in_managed_files(self, tmp_path):
        # A path with ".." should be rejected by validate_deploy_path
        managed = {"../../etc/passwd"}
        stats = BaseIntegrator.sync_remove_files(
            tmp_path, managed, prefix="../../"
        )
        assert stats["files_removed"] == 0


# ---------------------------------------------------------------------------
# find_files_by_glob
# ---------------------------------------------------------------------------


class TestFindFilesByGlob:
    def test_finds_files_in_root(self, tmp_path):
        (tmp_path / "a.prompt.md").write_text("a", encoding="utf-8")
        (tmp_path / "b.prompt.md").write_text("b", encoding="utf-8")
        (tmp_path / "other.txt").write_text("x", encoding="utf-8")

        results = BaseIntegrator.find_files_by_glob(tmp_path, "*.prompt.md")
        names = {f.name for f in results}
        assert names == {"a.prompt.md", "b.prompt.md"}

    def test_finds_files_in_subdirs(self, tmp_path):
        sub = tmp_path / ".apm" / "prompts"
        sub.mkdir(parents=True)
        (sub / "c.prompt.md").write_text("c", encoding="utf-8")

        results = BaseIntegrator.find_files_by_glob(
            tmp_path, "*.prompt.md", subdirs=[".apm/prompts"]
        )
        names = {f.name for f in results}
        assert "c.prompt.md" in names

    def test_deduplicates_same_file_via_subdir(self, tmp_path):
        # If same file is reachable via root AND subdir, it should appear once.
        sub = tmp_path / "nested"
        sub.mkdir()
        (sub / "dup.prompt.md").write_text("dup", encoding="utf-8")

        results = BaseIntegrator.find_files_by_glob(
            tmp_path, "*.prompt.md", subdirs=["nested"]
        )
        names = [f.name for f in results]
        assert names.count("dup.prompt.md") == 1

    def test_skips_missing_subdirs(self, tmp_path):
        results = BaseIntegrator.find_files_by_glob(
            tmp_path, "*.md", subdirs=["nonexistent"]
        )
        assert results == []

    def test_returns_empty_for_no_matches(self, tmp_path):
        results = BaseIntegrator.find_files_by_glob(tmp_path, "*.prompt.md")
        assert results == []

    def test_rejects_symlinks(self, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        target = outside / "secret.md"
        target.write_text("secret", encoding="utf-8")

        pkg = tmp_path / "pkg"
        pkg.mkdir()
        link = pkg / "evil.md"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks not supported on this platform")

        results = BaseIntegrator.find_files_by_glob(pkg, "*.md")
        names = [f.name for f in results]
        assert "evil.md" not in names

    def test_no_subdirs_argument(self, tmp_path):
        (tmp_path / "only.md").write_text("x", encoding="utf-8")
        results = BaseIntegrator.find_files_by_glob(tmp_path, "*.md")
        assert len(results) == 1
        assert results[0].name == "only.md"
