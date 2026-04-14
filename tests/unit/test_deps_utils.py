"""Tests for apm_cli.commands.deps._utils utility functions.

Covers the helper functions not exercised elsewhere:
- _is_nested_under_package
- _count_primitives
- _count_package_files
- _count_workflows
- _get_detailed_context_counts
- _get_package_display_info
- _get_detailed_package_info
"""

from pathlib import Path

import pytest
import yaml

from apm_cli.commands.deps._utils import (
    _count_package_files,
    _count_primitives,
    _count_workflows,
    _get_detailed_context_counts,
    _get_detailed_package_info,
    _get_package_display_info,
    _is_nested_under_package,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_apm_yml(path: Path, name: str = "test-pkg", version: str = "1.0.0", **extra):
    """Write a minimal apm.yml at *path*."""
    data = {"name": name, "version": version}
    data.update(extra)
    path.write_text(yaml.dump(data), encoding="utf-8")


def _touch(path: Path) -> Path:
    """Create *path* (and its parents) as an empty file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _is_nested_under_package
# ---------------------------------------------------------------------------


class TestIsNestedUnderPackage:
    """Tests for _is_nested_under_package."""

    def test_returns_false_when_no_parent_has_apm_yml(self, tmp_path):
        apm_modules = tmp_path / ".apm_modules"
        candidate = apm_modules / "owner" / "repo" / "skills" / "mypkg"
        candidate.mkdir(parents=True)
        assert _is_nested_under_package(candidate, apm_modules) is False

    def test_returns_true_when_parent_has_apm_yml(self, tmp_path):
        apm_modules = tmp_path / ".apm_modules"
        pkg_root = apm_modules / "owner" / "repo"
        pkg_root.mkdir(parents=True)
        _make_apm_yml(pkg_root / "apm.yml")
        # candidate is a sub-dir under the package
        candidate = pkg_root / "skills" / "sub-skill"
        candidate.mkdir(parents=True)
        assert _is_nested_under_package(candidate, apm_modules) is True

    def test_returns_false_when_candidate_is_direct_child_of_apm_modules(self, tmp_path):
        apm_modules = tmp_path / ".apm_modules"
        candidate = apm_modules / "owner"
        candidate.mkdir(parents=True)
        assert _is_nested_under_package(candidate, apm_modules) is False

    def test_handles_deeply_nested_path(self, tmp_path):
        apm_modules = tmp_path / ".apm_modules"
        pkg_root = apm_modules / "a" / "b"
        pkg_root.mkdir(parents=True)
        _make_apm_yml(pkg_root / "apm.yml")
        deep = pkg_root / "x" / "y" / "z"
        deep.mkdir(parents=True)
        assert _is_nested_under_package(deep, apm_modules) is True


# ---------------------------------------------------------------------------
# _count_primitives
# ---------------------------------------------------------------------------


class TestCountPrimitives:
    """Tests for _count_primitives."""

    def test_empty_directory_returns_zero_counts(self, tmp_path):
        counts = _count_primitives(tmp_path)
        assert counts == {"prompts": 0, "instructions": 0, "agents": 0, "skills": 0, "hooks": 0}

    def test_counts_prompts_in_apm_dir(self, tmp_path):
        prompts_dir = tmp_path / ".apm" / "prompts"
        prompts_dir.mkdir(parents=True)
        _touch(prompts_dir / "one.prompt.md")
        _touch(prompts_dir / "two.prompt.md")
        counts = _count_primitives(tmp_path)
        assert counts["prompts"] == 2

    def test_counts_instructions_in_apm_dir(self, tmp_path):
        instr_dir = tmp_path / ".apm" / "instructions"
        instr_dir.mkdir(parents=True)
        _touch(instr_dir / "base.md")
        _touch(instr_dir / "extra.md")
        counts = _count_primitives(tmp_path)
        assert counts["instructions"] == 2

    def test_counts_agents_in_apm_dir(self, tmp_path):
        agents_dir = tmp_path / ".apm" / "agents"
        agents_dir.mkdir(parents=True)
        _touch(agents_dir / "agent.md")
        counts = _count_primitives(tmp_path)
        assert counts["agents"] == 1

    def test_counts_skills_with_skill_md(self, tmp_path):
        skills_dir = tmp_path / ".apm" / "skills"
        skill1 = skills_dir / "skill-a"
        skill2 = skills_dir / "skill-b"
        skill1.mkdir(parents=True)
        skill2.mkdir(parents=True)
        _touch(skill1 / "SKILL.md")
        _touch(skill2 / "SKILL.md")
        # dir without SKILL.md should not be counted
        (skills_dir / "not-a-skill").mkdir()
        counts = _count_primitives(tmp_path)
        assert counts["skills"] == 2

    def test_counts_root_level_prompt_files(self, tmp_path):
        _touch(tmp_path / "foo.prompt.md")
        _touch(tmp_path / "bar.prompt.md")
        counts = _count_primitives(tmp_path)
        assert counts["prompts"] == 2

    def test_counts_root_level_skill_md(self, tmp_path):
        _touch(tmp_path / "SKILL.md")
        counts = _count_primitives(tmp_path)
        assert counts["skills"] == 1

    def test_counts_hooks_in_hooks_dir(self, tmp_path):
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()
        _touch(hooks_dir / "pre-tool-call.json")
        _touch(hooks_dir / "post-tool-call.json")
        counts = _count_primitives(tmp_path)
        assert counts["hooks"] == 2

    def test_counts_hooks_in_apm_hooks_dir(self, tmp_path):
        hooks_dir = tmp_path / ".apm" / "hooks"
        hooks_dir.mkdir(parents=True)
        _touch(hooks_dir / "hook1.json")
        counts = _count_primitives(tmp_path)
        assert counts["hooks"] == 1

    def test_counts_all_primitive_types_together(self, tmp_path):
        apm = tmp_path / ".apm"
        _touch(apm / "prompts" / "p.prompt.md")
        _touch(apm / "instructions" / "i.md")
        _touch(apm / "agents" / "a.md")
        skill = apm / "skills" / "s"
        skill.mkdir(parents=True)
        _touch(skill / "SKILL.md")
        _touch(tmp_path / "hooks" / "h.json")
        counts = _count_primitives(tmp_path)
        assert counts["prompts"] == 1
        assert counts["instructions"] == 1
        assert counts["agents"] == 1
        assert counts["skills"] == 1
        assert counts["hooks"] == 1

    def test_no_apm_dir_only_root_files(self, tmp_path):
        _touch(tmp_path / "w.prompt.md")
        _touch(tmp_path / "SKILL.md")
        counts = _count_primitives(tmp_path)
        assert counts["prompts"] == 1
        assert counts["skills"] == 1
        assert counts["instructions"] == 0


# ---------------------------------------------------------------------------
# _count_package_files
# ---------------------------------------------------------------------------


class TestCountPackageFiles:
    """Tests for _count_package_files."""

    def test_empty_dir_returns_zeros(self, tmp_path):
        ctx, wf = _count_package_files(tmp_path)
        assert ctx == 0
        assert wf == 0

    def test_no_apm_dir_root_prompt_files_counted_as_workflows(self, tmp_path):
        _touch(tmp_path / "a.prompt.md")
        _touch(tmp_path / "b.prompt.md")
        ctx, wf = _count_package_files(tmp_path)
        assert ctx == 0
        assert wf == 2

    def test_counts_instructions_as_context(self, tmp_path):
        instr_dir = tmp_path / ".apm" / "instructions"
        instr_dir.mkdir(parents=True)
        _touch(instr_dir / "a.md")
        _touch(instr_dir / "b.md")
        ctx, wf = _count_package_files(tmp_path)
        assert ctx == 2
        assert wf == 0

    def test_counts_chatmodes_as_context(self, tmp_path):
        chat_dir = tmp_path / ".apm" / "chatmodes"
        chat_dir.mkdir(parents=True)
        _touch(chat_dir / "c.md")
        ctx, wf = _count_package_files(tmp_path)
        assert ctx == 1

    def test_counts_contexts_dir_as_context(self, tmp_path):
        # _count_package_files uses 'contexts' (plural) as the directory name
        context_dir = tmp_path / ".apm" / "contexts"
        context_dir.mkdir(parents=True)
        _touch(context_dir / "x.md")
        ctx, wf = _count_package_files(tmp_path)
        assert ctx == 1

    def test_counts_prompts_as_workflows(self, tmp_path):
        prompts_dir = tmp_path / ".apm" / "prompts"
        prompts_dir.mkdir(parents=True)
        _touch(prompts_dir / "one.prompt.md")
        _touch(prompts_dir / "two.prompt.md")
        ctx, wf = _count_package_files(tmp_path)
        assert wf == 2

    def test_root_prompt_files_added_to_workflow_count(self, tmp_path):
        prompts_dir = tmp_path / ".apm" / "prompts"
        prompts_dir.mkdir(parents=True)
        _touch(prompts_dir / "a.prompt.md")
        _touch(tmp_path / "b.prompt.md")
        ctx, wf = _count_package_files(tmp_path)
        assert wf == 2

    def test_combined_context_and_workflow(self, tmp_path):
        apm = tmp_path / ".apm"
        _touch(apm / "instructions" / "i.md")
        _touch(apm / "chatmodes" / "c.md")
        _touch(apm / "prompts" / "p.prompt.md")
        ctx, wf = _count_package_files(tmp_path)
        assert ctx == 2
        assert wf == 1


# ---------------------------------------------------------------------------
# _count_workflows
# ---------------------------------------------------------------------------


class TestCountWorkflows:
    """Tests for _count_workflows."""

    def test_returns_workflow_count(self, tmp_path):
        prompts_dir = tmp_path / ".apm" / "prompts"
        prompts_dir.mkdir(parents=True)
        _touch(prompts_dir / "wf.prompt.md")
        assert _count_workflows(tmp_path) == 1

    def test_returns_zero_for_empty_package(self, tmp_path):
        assert _count_workflows(tmp_path) == 0

    def test_counts_root_level_prompts(self, tmp_path):
        _touch(tmp_path / "w1.prompt.md")
        _touch(tmp_path / "w2.prompt.md")
        assert _count_workflows(tmp_path) == 2


# ---------------------------------------------------------------------------
# _get_detailed_context_counts
# ---------------------------------------------------------------------------


class TestGetDetailedContextCounts:
    """Tests for _get_detailed_context_counts."""

    def test_no_apm_dir_returns_zeros(self, tmp_path):
        counts = _get_detailed_context_counts(tmp_path)
        assert counts == {"instructions": 0, "chatmodes": 0, "contexts": 0}

    def test_counts_instructions(self, tmp_path):
        instr = tmp_path / ".apm" / "instructions"
        instr.mkdir(parents=True)
        _touch(instr / "a.md")
        _touch(instr / "b.md")
        counts = _get_detailed_context_counts(tmp_path)
        assert counts["instructions"] == 2

    def test_counts_chatmodes(self, tmp_path):
        chat = tmp_path / ".apm" / "chatmodes"
        chat.mkdir(parents=True)
        _touch(chat / "c.md")
        counts = _get_detailed_context_counts(tmp_path)
        assert counts["chatmodes"] == 1

    def test_counts_context_directory_as_contexts(self, tmp_path):
        # Note: the dir is "context" (singular) but reported as "contexts"
        ctx_dir = tmp_path / ".apm" / "context"
        ctx_dir.mkdir(parents=True)
        _touch(ctx_dir / "x.md")
        counts = _get_detailed_context_counts(tmp_path)
        assert counts["contexts"] == 1

    def test_returns_zeros_when_apm_dir_empty(self, tmp_path):
        (tmp_path / ".apm").mkdir()
        counts = _get_detailed_context_counts(tmp_path)
        assert counts == {"instructions": 0, "chatmodes": 0, "contexts": 0}

    def test_all_context_types_together(self, tmp_path):
        apm = tmp_path / ".apm"
        _touch(apm / "instructions" / "i.md")
        _touch(apm / "chatmodes" / "c.md")
        _touch(apm / "context" / "x.md")
        _touch(apm / "context" / "y.md")
        counts = _get_detailed_context_counts(tmp_path)
        assert counts["instructions"] == 1
        assert counts["chatmodes"] == 1
        assert counts["contexts"] == 2


# ---------------------------------------------------------------------------
# _get_package_display_info
# ---------------------------------------------------------------------------


class TestGetPackageDisplayInfo:
    """Tests for _get_package_display_info."""

    def test_with_valid_apm_yml(self, tmp_path):
        _make_apm_yml(tmp_path / "apm.yml", name="my-pkg", version="2.3.4")
        info = _get_package_display_info(tmp_path)
        assert info["name"] == "my-pkg"
        assert info["version"] == "2.3.4"
        assert info["display_name"] == "my-pkg@2.3.4"

    def test_without_apm_yml_uses_dir_name(self, tmp_path):
        pkg_dir = tmp_path / "my-package"
        pkg_dir.mkdir()
        info = _get_package_display_info(pkg_dir)
        assert info["name"] == "my-package"
        assert info["version"] == "unknown"
        assert "my-package@unknown" in info["display_name"]

    def test_corrupted_apm_yml_falls_back_to_error(self, tmp_path):
        (tmp_path / "apm.yml").write_text("::invalid yaml::", encoding="utf-8")
        info = _get_package_display_info(tmp_path)
        assert "error" in info["version"] or "error" in info["display_name"]

    def test_display_name_includes_version(self, tmp_path):
        _make_apm_yml(tmp_path / "apm.yml", name="pkg", version="0.1.0")
        info = _get_package_display_info(tmp_path)
        assert "@0.1.0" in info["display_name"]


# ---------------------------------------------------------------------------
# _get_detailed_package_info
# ---------------------------------------------------------------------------


class TestGetDetailedPackageInfo:
    """Tests for _get_detailed_package_info."""

    def test_with_full_apm_yml(self, tmp_path):
        _make_apm_yml(
            tmp_path / "apm.yml",
            name="full-pkg",
            version="1.2.3",
            description="A full package",
            author="Test Author",
        )
        info = _get_detailed_package_info(tmp_path)
        assert info["name"] == "full-pkg"
        assert info["version"] == "1.2.3"
        assert info["description"] == "A full package"
        assert info["author"] == "Test Author"
        assert "install_path" in info
        assert "context_files" in info
        assert "workflows" in info
        assert "hooks" in info

    def test_without_apm_yml(self, tmp_path):
        pkg_dir = tmp_path / "bare-pkg"
        pkg_dir.mkdir()
        info = _get_detailed_package_info(pkg_dir)
        assert info["name"] == "bare-pkg"
        assert info["version"] == "unknown"
        assert "No apm.yml found" in info["description"]

    def test_corrupted_apm_yml_returns_error_dict(self, tmp_path):
        (tmp_path / "apm.yml").write_text("::invalid::", encoding="utf-8")
        info = _get_detailed_package_info(tmp_path)
        assert info["version"] == "error"
        assert "Error loading package" in info["description"]
        assert info["context_files"] == {"instructions": 0, "chatmodes": 0, "contexts": 0}
        assert info["workflows"] == 0
        assert info["hooks"] == 0

    def test_counts_files_when_apm_dir_present(self, tmp_path):
        _make_apm_yml(tmp_path / "apm.yml", name="pkg", version="1.0.0")
        apm = tmp_path / ".apm"
        _touch(apm / "instructions" / "a.md")
        _touch(apm / "prompts" / "p.prompt.md")
        _touch(tmp_path / "hooks" / "h.json")
        info = _get_detailed_package_info(tmp_path)
        assert info["context_files"]["instructions"] == 1
        assert info["workflows"] == 1
        assert info["hooks"] == 1

    def test_optional_fields_default_gracefully(self, tmp_path):
        # apm.yml with only name+version (no description/author/source)
        _make_apm_yml(tmp_path / "apm.yml", name="min-pkg", version="0.0.1")
        info = _get_detailed_package_info(tmp_path)
        assert info["description"] == "No description"
        assert info["author"] == "Unknown"
        assert info["source"] == "local"

    def test_install_path_is_string(self, tmp_path):
        _make_apm_yml(tmp_path / "apm.yml", name="p", version="1.0.0")
        info = _get_detailed_package_info(tmp_path)
        assert isinstance(info["install_path"], str)
