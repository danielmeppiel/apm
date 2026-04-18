"""Unit tests for apm_cli/commands/deps/_utils.py utility helpers."""

import tempfile
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
    _scan_installed_packages,
)
from apm_cli.constants import APM_DIR, APM_YML_FILENAME, SKILL_MD_FILENAME

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_apm_yml(
    path: Path, name: str = "pkg", version: str = "1.0.0", **kwargs
) -> None:
    """Write a minimal apm.yml at *path*."""
    data = {"name": name, "version": version}
    data.update(kwargs)
    path.write_text(yaml.dump(data))


# ---------------------------------------------------------------------------
# _scan_installed_packages
# ---------------------------------------------------------------------------


class TestScanInstalledPackages:
    def test_nonexistent_dir_returns_empty(self, tmp_path):
        result = _scan_installed_packages(tmp_path / "missing")
        assert result == []

    def test_empty_dir_returns_empty(self, tmp_path):
        (tmp_path / "apm_modules").mkdir()
        result = _scan_installed_packages(tmp_path / "apm_modules")
        assert result == []

    def test_github_2level_package(self, tmp_path):
        """owner/repo structure with apm.yml."""
        pkg = tmp_path / "owner" / "repo"
        pkg.mkdir(parents=True)
        _make_apm_yml(pkg / APM_YML_FILENAME)
        result = _scan_installed_packages(tmp_path)
        assert "owner/repo" in result

    def test_ado_3level_package(self, tmp_path):
        """org/project/repo structure with apm.yml."""
        pkg = tmp_path / "org" / "project" / "repo"
        pkg.mkdir(parents=True)
        _make_apm_yml(pkg / APM_YML_FILENAME)
        result = _scan_installed_packages(tmp_path)
        assert "org/project/repo" in result

    def test_package_with_apm_dir_instead_of_yml(self, tmp_path):
        """Package detected via .apm dir even without apm.yml."""
        pkg = tmp_path / "owner" / "repo"
        pkg.mkdir(parents=True)
        (pkg / APM_DIR).mkdir()
        result = _scan_installed_packages(tmp_path)
        assert "owner/repo" in result

    def test_single_level_not_returned(self, tmp_path):
        """Top-level dirs are not included (need at least 2-level)."""
        pkg = tmp_path / "repo"
        pkg.mkdir()
        _make_apm_yml(pkg / APM_YML_FILENAME)
        result = _scan_installed_packages(tmp_path)
        assert result == []

    def test_hidden_dirs_skipped(self, tmp_path):
        """.hidden directories are ignored."""
        hidden = tmp_path / "owner" / ".hidden"
        hidden.mkdir(parents=True)
        _make_apm_yml(hidden / APM_YML_FILENAME)
        result = _scan_installed_packages(tmp_path)
        assert result == []

    def test_multiple_packages(self, tmp_path):
        for repo in ["alpha", "beta", "gamma"]:
            pkg = tmp_path / "owner" / repo
            pkg.mkdir(parents=True)
            _make_apm_yml(pkg / APM_YML_FILENAME)
        result = _scan_installed_packages(tmp_path)
        assert len(result) == 3
        assert "owner/alpha" in result
        assert "owner/beta" in result
        assert "owner/gamma" in result


# ---------------------------------------------------------------------------
# _is_nested_under_package
# ---------------------------------------------------------------------------


class TestIsNestedUnderPackage:
    def test_not_nested_when_no_parent_has_apm_yml(self, tmp_path):
        candidate = tmp_path / "owner" / "repo" / "skills" / "skill1"
        candidate.mkdir(parents=True)
        assert not _is_nested_under_package(candidate, tmp_path)

    def test_nested_when_parent_has_apm_yml(self, tmp_path):
        pkg = tmp_path / "owner" / "repo"
        pkg.mkdir(parents=True)
        _make_apm_yml(pkg / APM_YML_FILENAME)
        candidate = pkg / "skills" / "my-skill"
        candidate.mkdir(parents=True)
        assert _is_nested_under_package(candidate, tmp_path)

    def test_not_nested_when_apm_yml_at_same_level(self, tmp_path):
        """Candidate itself has apm.yml, parent does not - should not be nested."""
        candidate = tmp_path / "owner" / "repo"
        candidate.mkdir(parents=True)
        _make_apm_yml(candidate / APM_YML_FILENAME)
        # candidate is the package itself; parent (owner/) has no apm.yml
        assert not _is_nested_under_package(candidate, tmp_path)

    def test_deeply_nested(self, tmp_path):
        """Three levels of nesting, parent at top is a package."""
        pkg = tmp_path / "owner" / "repo"
        pkg.mkdir(parents=True)
        _make_apm_yml(pkg / APM_YML_FILENAME)
        deep = pkg / "a" / "b" / "c"
        deep.mkdir(parents=True)
        assert _is_nested_under_package(deep, tmp_path)


# ---------------------------------------------------------------------------
# _count_primitives
# ---------------------------------------------------------------------------


class TestCountPrimitives:
    def test_empty_dir_returns_zeros(self, tmp_path):
        counts = _count_primitives(tmp_path)
        assert counts == {
            "prompts": 0,
            "instructions": 0,
            "agents": 0,
            "skills": 0,
            "hooks": 0,
        }

    def test_counts_prompt_files_in_apm_prompts(self, tmp_path):
        prompts = tmp_path / APM_DIR / "prompts"
        prompts.mkdir(parents=True)
        (prompts / "a.prompt.md").write_text("")
        (prompts / "b.prompt.md").write_text("")
        (prompts / "not_a_prompt.md").write_text("")  # should not be counted
        counts = _count_primitives(tmp_path)
        assert counts["prompts"] == 2

    def test_counts_root_prompt_files(self, tmp_path):
        (tmp_path / "root.prompt.md").write_text("")
        counts = _count_primitives(tmp_path)
        assert counts["prompts"] == 1

    def test_counts_instructions(self, tmp_path):
        instructions = tmp_path / APM_DIR / "instructions"
        instructions.mkdir(parents=True)
        (instructions / "guide.md").write_text("")
        (instructions / "rules.md").write_text("")
        counts = _count_primitives(tmp_path)
        assert counts["instructions"] == 2

    def test_counts_agents(self, tmp_path):
        agents = tmp_path / APM_DIR / "agents"
        agents.mkdir(parents=True)
        (agents / "agent1.md").write_text("")
        counts = _count_primitives(tmp_path)
        assert counts["agents"] == 1

    def test_counts_skills_with_skill_md(self, tmp_path):
        skills = tmp_path / APM_DIR / "skills"
        skills.mkdir(parents=True)
        for skill in ["skill-a", "skill-b"]:
            s = skills / skill
            s.mkdir()
            (s / SKILL_MD_FILENAME).write_text("")
        # Also a skill dir without SKILL.md (not counted)
        (skills / "no-skill-file").mkdir()
        counts = _count_primitives(tmp_path)
        assert counts["skills"] == 2

    def test_counts_root_level_skill_md(self, tmp_path):
        (tmp_path / SKILL_MD_FILENAME).write_text("")
        counts = _count_primitives(tmp_path)
        assert counts["skills"] == 1

    def test_counts_hooks_in_apm_hooks(self, tmp_path):
        hooks = tmp_path / APM_DIR / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "pre-push.json").write_text("{}")
        (hooks / "post-commit.json").write_text("{}")
        counts = _count_primitives(tmp_path)
        assert counts["hooks"] == 2

    def test_counts_hooks_in_root_hooks_dir(self, tmp_path):
        hooks = tmp_path / "hooks"
        hooks.mkdir()
        (hooks / "pre-push.json").write_text("{}")
        counts = _count_primitives(tmp_path)
        assert counts["hooks"] == 1

    def test_counts_combined_primitives(self, tmp_path):
        apm = tmp_path / APM_DIR
        (apm / "prompts").mkdir(parents=True)
        (apm / "prompts" / "wf.prompt.md").write_text("")
        (apm / "instructions").mkdir(parents=True)
        (apm / "instructions" / "rules.md").write_text("")
        (apm / "agents").mkdir(parents=True)
        (apm / "agents" / "agent.md").write_text("")
        skill = apm / "skills" / "my-skill"
        skill.mkdir(parents=True)
        (skill / SKILL_MD_FILENAME).write_text("")
        counts = _count_primitives(tmp_path)
        assert counts["prompts"] == 1
        assert counts["instructions"] == 1
        assert counts["agents"] == 1
        assert counts["skills"] == 1


# ---------------------------------------------------------------------------
# _count_package_files / _count_workflows
# ---------------------------------------------------------------------------


class TestCountPackageFiles:
    def test_no_apm_dir_returns_zero_context(self, tmp_path):
        context, workflows = _count_package_files(tmp_path)
        assert context == 0

    def test_no_apm_dir_counts_root_prompts_as_workflows(self, tmp_path):
        (tmp_path / "a.prompt.md").write_text("")
        (tmp_path / "b.prompt.md").write_text("")
        context, workflows = _count_package_files(tmp_path)
        assert context == 0
        assert workflows == 2

    def test_counts_instruction_md_files(self, tmp_path):
        instructions = tmp_path / APM_DIR / "instructions"
        instructions.mkdir(parents=True)
        (instructions / "x.md").write_text("")
        context, _ = _count_package_files(tmp_path)
        assert context >= 1

    def test_counts_workflows_in_prompts(self, tmp_path):
        prompts = tmp_path / APM_DIR / "prompts"
        prompts.mkdir(parents=True)
        (prompts / "flow.prompt.md").write_text("")
        _, workflows = _count_package_files(tmp_path)
        assert workflows >= 1

    def test_count_workflows_helper(self, tmp_path):
        prompts = tmp_path / APM_DIR / "prompts"
        prompts.mkdir(parents=True)
        (prompts / "flow.prompt.md").write_text("")
        assert _count_workflows(tmp_path) >= 1


# ---------------------------------------------------------------------------
# _get_detailed_context_counts
# ---------------------------------------------------------------------------


class TestGetDetailedContextCounts:
    def test_no_apm_dir_returns_zeros(self, tmp_path):
        counts = _get_detailed_context_counts(tmp_path)
        assert counts == {"instructions": 0, "chatmodes": 0, "contexts": 0}

    def test_counts_instructions(self, tmp_path):
        (tmp_path / APM_DIR / "instructions").mkdir(parents=True)
        (tmp_path / APM_DIR / "instructions" / "guide.md").write_text("")
        counts = _get_detailed_context_counts(tmp_path)
        assert counts["instructions"] == 1
        assert counts["chatmodes"] == 0
        assert counts["contexts"] == 0

    def test_counts_chatmodes(self, tmp_path):
        (tmp_path / APM_DIR / "chatmodes").mkdir(parents=True)
        (tmp_path / APM_DIR / "chatmodes" / "mode.md").write_text("")
        counts = _get_detailed_context_counts(tmp_path)
        assert counts["chatmodes"] == 1

    def test_counts_context_directory(self, tmp_path):
        # Note: directory is 'context' (singular), key is 'contexts'
        (tmp_path / APM_DIR / "context").mkdir(parents=True)
        (tmp_path / APM_DIR / "context" / "ctx.md").write_text("")
        counts = _get_detailed_context_counts(tmp_path)
        assert counts["contexts"] == 1

    def test_non_md_files_not_counted(self, tmp_path):
        (tmp_path / APM_DIR / "instructions").mkdir(parents=True)
        (tmp_path / APM_DIR / "instructions" / "guide.txt").write_text("")
        counts = _get_detailed_context_counts(tmp_path)
        assert counts["instructions"] == 0


# ---------------------------------------------------------------------------
# _get_package_display_info
# ---------------------------------------------------------------------------


class TestGetPackageDisplayInfo:
    def test_with_valid_apm_yml(self, tmp_path):
        _make_apm_yml(tmp_path / APM_YML_FILENAME, name="my-pkg", version="2.3.1")
        info = _get_package_display_info(tmp_path)
        assert info["name"] == "my-pkg"
        assert info["version"] == "2.3.1"
        assert "my-pkg@2.3.1" in info["display_name"]

    def test_without_apm_yml(self, tmp_path):
        pkg = tmp_path / "some-package"
        pkg.mkdir()
        info = _get_package_display_info(pkg)
        assert info["name"] == "some-package"
        assert info["version"] == "unknown"
        assert "some-package@unknown" in info["display_name"]

    def test_handles_broken_apm_yml(self, tmp_path):
        (tmp_path / APM_YML_FILENAME).write_text("!!!! invalid: [yaml")
        info = _get_package_display_info(tmp_path)
        # Should not raise; falls back to error info
        assert "name" in info

    def test_display_name_includes_version(self, tmp_path):
        _make_apm_yml(tmp_path / APM_YML_FILENAME, name="tool", version="0.1.0")
        info = _get_package_display_info(tmp_path)
        assert info["display_name"] == "tool@0.1.0"


# ---------------------------------------------------------------------------
# _get_detailed_package_info
# ---------------------------------------------------------------------------


class TestGetDetailedPackageInfo:
    def test_with_full_apm_yml(self, tmp_path):
        _make_apm_yml(
            tmp_path / APM_YML_FILENAME,
            name="full-pkg",
            version="1.0.0",
            description="A test package",
            author="Jane Doe",
            source="github",
        )
        info = _get_detailed_package_info(tmp_path)
        assert info["name"] == "full-pkg"
        assert info["version"] == "1.0.0"
        assert info["description"] == "A test package"
        assert info["author"] == "Jane Doe"
        assert "install_path" in info
        assert "context_files" in info
        assert "workflows" in info
        assert "hooks" in info

    def test_without_apm_yml(self, tmp_path):
        pkg = tmp_path / "bare-pkg"
        pkg.mkdir()
        info = _get_detailed_package_info(pkg)
        assert info["name"] == "bare-pkg"
        assert info["version"] == "unknown"
        assert "No apm.yml found" in info["description"]

    def test_handles_exception_gracefully(self, tmp_path):
        """Broken apm.yml content returns error info without raising."""
        (tmp_path / APM_YML_FILENAME).write_text("!!!! not yaml: [broken")
        info = _get_detailed_package_info(tmp_path)
        # Should have all expected keys even after error
        assert "name" in info
        assert "context_files" in info
        assert "workflows" in info

    def test_includes_install_path(self, tmp_path):
        _make_apm_yml(tmp_path / APM_YML_FILENAME)
        info = _get_detailed_package_info(tmp_path)
        assert Path(info["install_path"]).is_absolute()

    def test_counts_workflows(self, tmp_path):
        _make_apm_yml(tmp_path / APM_YML_FILENAME)
        prompts = tmp_path / APM_DIR / "prompts"
        prompts.mkdir(parents=True)
        (prompts / "flow.prompt.md").write_text("")
        info = _get_detailed_package_info(tmp_path)
        assert info["workflows"] == 1

    def test_minimal_apm_yml_no_optional_fields(self, tmp_path):
        """apm.yml with only required fields; optional fields default gracefully."""
        _make_apm_yml(tmp_path / APM_YML_FILENAME, name="minimal", version="0.0.1")
        info = _get_detailed_package_info(tmp_path)
        assert info["name"] == "minimal"
        assert info["description"] == "No description"
        assert info["author"] == "Unknown"
