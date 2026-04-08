"""Unit tests for BaseIntegrator core infrastructure.

Covers:
- IntegrationResult dataclass
- check_collision() - collision detection logic
- normalize_managed_files() - path separator normalization
- validate_deploy_path() - security gate for deploy paths
- partition_bucket_key() - canonical bucket key with aliases
- partition_managed_files() - O(1) path routing to buckets
- cleanup_empty_parents() - bottom-up empty dir removal
- sync_remove_files() - managed-file removal with validation
- find_files_by_glob() - file discovery with dedup
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apm_cli.integration.base_integrator import BaseIntegrator, IntegrationResult


# ---------------------------------------------------------------------------
# IntegrationResult
# ---------------------------------------------------------------------------


class TestIntegrationResult:
    def test_default_links_resolved(self):
        r = IntegrationResult(
            files_integrated=3,
            files_updated=0,
            files_skipped=1,
            target_paths=[],
        )
        assert r.links_resolved == 0

    def test_explicit_links_resolved(self):
        r = IntegrationResult(
            files_integrated=2,
            files_updated=0,
            files_skipped=0,
            target_paths=[Path("/some/path")],
            links_resolved=5,
        )
        assert r.links_resolved == 5
        assert len(r.target_paths) == 1


# ---------------------------------------------------------------------------
# check_collision
# ---------------------------------------------------------------------------


class TestCheckCollision:
    def test_no_managed_files_never_collides(self, tmp_path):
        target = tmp_path / "file.md"
        target.write_text("user content")
        assert BaseIntegrator.check_collision(target, "file.md", None, False) is False

    def test_file_absent_never_collides(self, tmp_path):
        target = tmp_path / "nonexistent.md"
        managed = set()
        assert BaseIntegrator.check_collision(target, "nonexistent.md", managed, False) is False

    def test_file_in_managed_set_not_a_collision(self, tmp_path):
        target = tmp_path / "managed.md"
        target.write_text("apm content")
        managed = {"managed.md"}
        assert BaseIntegrator.check_collision(target, "managed.md", managed, False) is False

    def test_unmanaged_existing_file_is_collision(self, tmp_path):
        target = tmp_path / "user_file.md"
        target.write_text("user content")
        managed = set()  # empty managed set
        with patch("apm_cli.integration.base_integrator._rich_warning"):
            result = BaseIntegrator.check_collision(target, "user_file.md", managed, False)
        assert result is True

    def test_force_flag_skips_collision(self, tmp_path):
        target = tmp_path / "user_file.md"
        target.write_text("user content")
        managed = set()
        assert BaseIntegrator.check_collision(target, "user_file.md", managed, True) is False

    def test_backslash_normalized_in_rel_path(self, tmp_path):
        target = tmp_path / "sub" / "file.md"
        target.parent.mkdir()
        target.write_text("apm content")
        # managed_files uses forward slashes; rel_path uses backslashes
        managed = {"sub/file.md"}
        assert BaseIntegrator.check_collision(target, "sub\\file.md", managed, False) is False

    def test_diagnostics_called_on_collision(self, tmp_path):
        target = tmp_path / "conflict.md"
        target.write_text("user content")
        managed = set()
        diag = MagicMock()
        result = BaseIntegrator.check_collision(target, "conflict.md", managed, False, diagnostics=diag)
        assert result is True
        diag.skip.assert_called_once_with("conflict.md")

    def test_warning_emitted_without_diagnostics(self, tmp_path):
        target = tmp_path / "conflict.md"
        target.write_text("user content")
        managed = set()
        with patch("apm_cli.integration.base_integrator._rich_warning") as mock_warn:
            BaseIntegrator.check_collision(target, "conflict.md", managed, False)
        mock_warn.assert_called_once()


# ---------------------------------------------------------------------------
# normalize_managed_files
# ---------------------------------------------------------------------------


class TestNormalizeManagedFiles:
    def test_none_returns_none(self):
        assert BaseIntegrator.normalize_managed_files(None) is None

    def test_forward_slashes_unchanged(self):
        files = {".github/prompts/foo.md", ".claude/commands/bar.md"}
        result = BaseIntegrator.normalize_managed_files(files)
        assert result == files

    def test_backslashes_converted(self):
        files = {".github\\prompts\\foo.md", ".claude\\commands\\bar.md"}
        result = BaseIntegrator.normalize_managed_files(files)
        assert result == {".github/prompts/foo.md", ".claude/commands/bar.md"}

    def test_mixed_separators(self):
        files = {"sub\\dir/file.md"}
        result = BaseIntegrator.normalize_managed_files(files)
        assert result == {"sub/dir/file.md"}

    def test_empty_set(self):
        assert BaseIntegrator.normalize_managed_files(set()) == set()


# ---------------------------------------------------------------------------
# validate_deploy_path
# ---------------------------------------------------------------------------


class TestValidateDeployPath:
    def test_valid_github_prompts_path(self, tmp_path):
        assert BaseIntegrator.validate_deploy_path(".github/prompts/foo.md", tmp_path) is True

    def test_valid_claude_commands_path(self, tmp_path):
        assert BaseIntegrator.validate_deploy_path(".claude/commands/foo.md", tmp_path) is True

    def test_dotdot_traversal_rejected(self, tmp_path):
        assert BaseIntegrator.validate_deploy_path("../etc/passwd", tmp_path) is False

    def test_embedded_dotdot_rejected(self, tmp_path):
        assert BaseIntegrator.validate_deploy_path(".github/prompts/../../etc/passwd", tmp_path) is False

    def test_unknown_prefix_rejected(self, tmp_path):
        assert BaseIntegrator.validate_deploy_path("random/path/file.md", tmp_path) is False

    def test_absolute_path_string_rejected(self, tmp_path):
        # Absolute path strings don't start with known prefixes
        assert BaseIntegrator.validate_deploy_path("/etc/passwd", tmp_path) is False

    def test_valid_cursor_rules_path(self, tmp_path):
        assert BaseIntegrator.validate_deploy_path(".cursor/rules/foo.mdc", tmp_path) is True

    def test_custom_allowed_prefixes(self, tmp_path):
        result = BaseIntegrator.validate_deploy_path(
            "custom/path/file.md",
            tmp_path,
            allowed_prefixes=("custom/",),
        )
        assert result is True

    def test_symlink_escape_rejected(self, tmp_path):
        # Create a symlink that points outside the project root
        outside = tmp_path.parent / "outside_file.txt"
        outside.write_text("secret")
        link = tmp_path / ".github" / "prompts" / "evil_link.md"
        link.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(outside, link)
            result = BaseIntegrator.validate_deploy_path(
                ".github/prompts/evil_link.md", tmp_path
            )
            assert result is False
        finally:
            if link.exists() or link.is_symlink():
                link.unlink()


# ---------------------------------------------------------------------------
# partition_bucket_key
# ---------------------------------------------------------------------------


class TestPartitionBucketKey:
    def test_prompts_copilot_alias(self):
        assert BaseIntegrator.partition_bucket_key("prompts", "copilot") == "prompts"

    def test_agents_copilot_alias(self):
        assert BaseIntegrator.partition_bucket_key("agents", "copilot") == "agents_github"

    def test_commands_claude_alias(self):
        assert BaseIntegrator.partition_bucket_key("commands", "claude") == "commands"

    def test_instructions_copilot_alias(self):
        assert BaseIntegrator.partition_bucket_key("instructions", "copilot") == "instructions"

    def test_instructions_cursor_alias(self):
        assert BaseIntegrator.partition_bucket_key("instructions", "cursor") == "rules_cursor"

    def test_instructions_claude_alias(self):
        assert BaseIntegrator.partition_bucket_key("instructions", "claude") == "rules_claude"

    def test_no_alias_returns_raw_key(self):
        # Unknown combo: no alias, returns raw
        assert BaseIntegrator.partition_bucket_key("agents", "cursor") == "agents_cursor"


# ---------------------------------------------------------------------------
# partition_managed_files
# ---------------------------------------------------------------------------


class TestPartitionManagedFiles:
    def test_empty_set_returns_empty_buckets(self):
        result = BaseIntegrator.partition_managed_files(set())
        # All buckets present but empty
        assert all(len(v) == 0 for v in result.values())

    def test_prompts_routed_to_prompts_bucket(self):
        files = {".github/prompts/foo-apm.prompt.md"}
        result = BaseIntegrator.partition_managed_files(files)
        assert ".github/prompts/foo-apm.prompt.md" in result["prompts"]

    def test_instructions_routed_to_instructions_bucket(self):
        files = {".github/instructions/foo-apm.instructions.md"}
        result = BaseIntegrator.partition_managed_files(files)
        assert ".github/instructions/foo-apm.instructions.md" in result["instructions"]

    def test_skills_routed_to_skills_bucket(self):
        files = {".github/skills/mypkg/skill.md"}
        result = BaseIntegrator.partition_managed_files(files)
        assert ".github/skills/mypkg/skill.md" in result["skills"]

    def test_claude_commands_routed_to_commands_bucket(self):
        files = {".claude/commands/foo.md"}
        result = BaseIntegrator.partition_managed_files(files)
        assert ".claude/commands/foo.md" in result["commands"]

    def test_cursor_rules_routed_to_rules_cursor_bucket(self):
        files = {".cursor/rules/foo.mdc"}
        result = BaseIntegrator.partition_managed_files(files)
        assert ".cursor/rules/foo.mdc" in result["rules_cursor"]

    def test_unknown_prefix_not_added_to_any_bucket(self):
        files = {"random/path/file.md"}
        result = BaseIntegrator.partition_managed_files(files)
        all_values = set()
        for v in result.values():
            all_values.update(v)
        assert "random/path/file.md" not in all_values

    def test_multiple_files_routed_correctly(self):
        files = {
            ".github/prompts/p.md",
            ".github/instructions/i.md",
            ".claude/commands/c.md",
            ".cursor/rules/r.mdc",
        }
        result = BaseIntegrator.partition_managed_files(files)
        assert ".github/prompts/p.md" in result["prompts"]
        assert ".github/instructions/i.md" in result["instructions"]
        assert ".claude/commands/c.md" in result["commands"]
        assert ".cursor/rules/r.mdc" in result["rules_cursor"]

    def test_hooks_bucket_always_present(self):
        result = BaseIntegrator.partition_managed_files(set())
        assert "hooks" in result
        assert "skills" in result

    def test_skills_and_hooks_are_cross_target_buckets(self):
        # Skills bucket collects from all targets
        files = {".github/skills/mypkg/skill.md"}
        result = BaseIntegrator.partition_managed_files(files)
        assert len(result["skills"]) == 1
        # Not duplicated in any other bucket
        all_non_skills = set()
        for k, v in result.items():
            if k != "skills":
                all_non_skills.update(v)
        assert ".github/skills/mypkg/skill.md" not in all_non_skills


# ---------------------------------------------------------------------------
# cleanup_empty_parents
# ---------------------------------------------------------------------------


class TestCleanupEmptyParents:
    def test_removes_empty_parent_dir(self, tmp_path):
        sub = tmp_path / "a" / "b" / "c"
        sub.mkdir(parents=True)
        deleted_file = sub / "file.md"
        # Don't actually create the file (simulating post-deletion state)
        BaseIntegrator.cleanup_empty_parents([deleted_file], tmp_path)
        # a/b/c, a/b, a should all be removed (they're empty)
        assert not (tmp_path / "a").exists()

    def test_does_not_remove_nonempty_parent(self, tmp_path):
        sub = tmp_path / "a" / "b"
        sub.mkdir(parents=True)
        keeper = tmp_path / "a" / "keeper.md"
        keeper.write_text("keep me")
        deleted_file = sub / "deleted.md"
        BaseIntegrator.cleanup_empty_parents([deleted_file], tmp_path)
        # 'a' should still exist because keeper.md is there
        assert (tmp_path / "a").exists()
        # 'b' is empty and should be removed
        assert not (tmp_path / "a" / "b").exists()

    def test_stop_at_respected(self, tmp_path):
        stop = tmp_path / "stop_here"
        sub = stop / "child"
        sub.mkdir(parents=True)
        deleted_file = sub / "file.md"
        BaseIntegrator.cleanup_empty_parents([deleted_file], stop)
        # stop_here itself should NOT be removed
        assert stop.exists()
        # child should be removed (it's empty)
        assert not sub.exists()

    def test_empty_deleted_paths_no_op(self, tmp_path):
        BaseIntegrator.cleanup_empty_parents([], tmp_path)
        # No error, nothing changed

    def test_multiple_deleted_paths_batch(self, tmp_path):
        sub1 = tmp_path / "pkg" / "a"
        sub2 = tmp_path / "pkg" / "b"
        sub1.mkdir(parents=True)
        sub2.mkdir(parents=True)
        deleted = [sub1 / "f1.md", sub2 / "f2.md"]
        BaseIntegrator.cleanup_empty_parents(deleted, tmp_path)
        # Both sub1, sub2, and pkg should be removed
        assert not (tmp_path / "pkg").exists()

    def test_oserror_on_rmdir_ignored(self, tmp_path):
        sub = tmp_path / "a" / "b"
        sub.mkdir(parents=True)
        deleted_file = sub / "file.md"
        with patch.object(Path, "rmdir", side_effect=OSError("busy")):
            # Should not raise
            BaseIntegrator.cleanup_empty_parents([deleted_file], tmp_path)


# ---------------------------------------------------------------------------
# sync_remove_files
# ---------------------------------------------------------------------------


class TestSyncRemoveFiles:
    def test_removes_matching_managed_file(self, tmp_path):
        f = tmp_path / ".github" / "prompts" / "foo-apm.prompt.md"
        f.parent.mkdir(parents=True)
        f.write_text("content")
        managed = {".github/prompts/foo-apm.prompt.md"}
        result = BaseIntegrator.sync_remove_files(tmp_path, managed, ".github/prompts/")
        assert result["files_removed"] == 1
        assert result["errors"] == 0
        assert not f.exists()

    def test_skips_non_matching_prefix(self, tmp_path):
        f = tmp_path / ".claude" / "commands" / "cmd.md"
        f.parent.mkdir(parents=True)
        f.write_text("content")
        managed = {".claude/commands/cmd.md"}
        # Pass .github/prompts/ prefix -> shouldn't touch .claude/
        result = BaseIntegrator.sync_remove_files(tmp_path, managed, ".github/prompts/")
        assert result["files_removed"] == 0
        assert f.exists()

    def test_skips_nonexistent_file_gracefully(self, tmp_path):
        managed = {".github/prompts/ghost.md"}
        result = BaseIntegrator.sync_remove_files(tmp_path, managed, ".github/prompts/")
        assert result["files_removed"] == 0
        assert result["errors"] == 0

    def test_legacy_glob_fallback_when_no_managed(self, tmp_path):
        glob_dir = tmp_path / ".github" / "prompts"
        glob_dir.mkdir(parents=True)
        (glob_dir / "foo-apm.prompt.md").write_text("x")
        (glob_dir / "bar-apm.prompt.md").write_text("y")
        (glob_dir / "unrelated.md").write_text("keep")
        result = BaseIntegrator.sync_remove_files(
            tmp_path,
            None,
            ".github/prompts/",
            legacy_glob_dir=glob_dir,
            legacy_glob_pattern="*-apm.prompt.md",
        )
        assert result["files_removed"] == 2
        assert (glob_dir / "unrelated.md").exists()

    def test_validate_deploy_path_blocks_traversal(self, tmp_path):
        # A traversal path in managed_files should be silently skipped
        managed = {"../evil.txt"}
        result = BaseIntegrator.sync_remove_files(tmp_path, managed, "../")
        assert result["files_removed"] == 0

    def test_managed_files_none_no_legacy_no_op(self, tmp_path):
        result = BaseIntegrator.sync_remove_files(tmp_path, None, ".github/prompts/")
        assert result == {"files_removed": 0, "errors": 0}

    def test_unlink_error_increments_errors(self, tmp_path):
        f = tmp_path / ".github" / "prompts" / "foo-apm.prompt.md"
        f.parent.mkdir(parents=True)
        f.write_text("content")
        managed = {".github/prompts/foo-apm.prompt.md"}
        with patch.object(Path, "unlink", side_effect=PermissionError("no")):
            result = BaseIntegrator.sync_remove_files(tmp_path, managed, ".github/prompts/")
        assert result["errors"] == 1
        assert result["files_removed"] == 0


# ---------------------------------------------------------------------------
# find_files_by_glob
# ---------------------------------------------------------------------------


class TestFindFilesByGlob:
    def test_finds_files_matching_pattern(self, tmp_path):
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "foo.prompt.md").write_text("x")
        (pkg / "bar.prompt.md").write_text("y")
        (pkg / "other.txt").write_text("z")
        result = BaseIntegrator.find_files_by_glob(pkg, "*.prompt.md")
        names = {f.name for f in result}
        assert names == {"foo.prompt.md", "bar.prompt.md"}

    def test_returns_empty_for_no_match(self, tmp_path):
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "foo.txt").write_text("x")
        result = BaseIntegrator.find_files_by_glob(pkg, "*.prompt.md")
        assert result == []

    def test_subdirs_searched(self, tmp_path):
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        subdir = pkg / ".apm" / "prompts"
        subdir.mkdir(parents=True)
        (subdir / "foo.prompt.md").write_text("x")
        result = BaseIntegrator.find_files_by_glob(pkg, "*.prompt.md", subdirs=[".apm/prompts"])
        assert len(result) == 1
        assert result[0].name == "foo.prompt.md"

    def test_deduplication_across_dirs(self, tmp_path):
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        subdir = pkg / ".apm" / "prompts"
        subdir.mkdir(parents=True)
        # Same file found from root and subdir (symlink scenario is complex,
        # test same file from root glob + subdir glob deduplicated)
        f = pkg / "foo.prompt.md"
        f.write_text("x")
        # Also put one in subdir with same name
        (subdir / "bar.prompt.md").write_text("y")
        result = BaseIntegrator.find_files_by_glob(pkg, "*.prompt.md", subdirs=[".apm/prompts"])
        names = {f.name for f in result}
        assert "foo.prompt.md" in names
        assert "bar.prompt.md" in names

    def test_nonexistent_subdir_ignored(self, tmp_path):
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "foo.prompt.md").write_text("x")
        result = BaseIntegrator.find_files_by_glob(pkg, "*.prompt.md", subdirs=["nonexistent"])
        assert len(result) == 1

    def test_sorted_output(self, tmp_path):
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        for name in ["c.prompt.md", "a.prompt.md", "b.prompt.md"]:
            (pkg / name).write_text("x")
        result = BaseIntegrator.find_files_by_glob(pkg, "*.prompt.md")
        names = [f.name for f in result]
        assert names == sorted(names)
