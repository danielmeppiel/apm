"""Unit tests for apm_cli.commands.deps._utils helpers.

These are pure filesystem-based utilities; each test uses ``tmp_path``
to create a minimal directory structure and exercises the function in
isolation without patching IO.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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


def _make_apm_yml(path: Path, name: str = "test-pkg", version: str = "1.0.0") -> Path:
    """Write a minimal apm.yml into *path* and return the file path."""
    path.mkdir(parents=True, exist_ok=True)
    apm_yml = path / APM_YML_FILENAME
    apm_yml.write_text(f"name: {name}\nversion: {version}\ndescription: Test package\n")
    return apm_yml


def _make_apm_dir(package_path: Path) -> Path:
    """Create .apm directory inside *package_path* and return it."""
    apm_dir = package_path / APM_DIR
    apm_dir.mkdir(parents=True, exist_ok=True)
    return apm_dir


# ---------------------------------------------------------------------------
# _scan_installed_packages
# ---------------------------------------------------------------------------


class TestScanInstalledPackages:
    def test_returns_empty_when_dir_missing(self, tmp_path):
        result = _scan_installed_packages(tmp_path / "nonexistent")
        assert result == []

    def test_returns_empty_when_dir_is_empty(self, tmp_path):
        modules = tmp_path / "apm_modules"
        modules.mkdir()
        assert _scan_installed_packages(modules) == []

    def test_finds_github_style_two_level_package_with_apm_yml(self, tmp_path):
        modules = tmp_path / "apm_modules"
        pkg = modules / "owner" / "repo"
        _make_apm_yml(pkg)
        result = _scan_installed_packages(modules)
        assert "owner/repo" in result

    def test_finds_github_style_two_level_package_with_apm_dir(self, tmp_path):
        modules = tmp_path / "apm_modules"
        pkg = modules / "owner" / "repo"
        pkg.mkdir(parents=True)
        (pkg / APM_DIR).mkdir()
        result = _scan_installed_packages(modules)
        assert "owner/repo" in result

    def test_finds_ado_style_three_level_package(self, tmp_path):
        modules = tmp_path / "apm_modules"
        pkg = modules / "org" / "project" / "repo"
        _make_apm_yml(pkg)
        result = _scan_installed_packages(modules)
        assert "org/project/repo" in result

    def test_skips_hidden_top_level_dir(self, tmp_path):
        """Directories whose OWN name starts with '.' are skipped.
        The .hidden dir is skipped, but repo inside it is not filtered."""
        modules = tmp_path / "apm_modules"
        hidden = modules / ".hidden" / "repo"
        _make_apm_yml(hidden)
        # The .hidden directory is skipped by the check, but 'repo' inside is
        # still enumerated by rglob and doesn't start with '.'. The current
        # implementation does not recurse-skip inside hidden dirs.
        result = _scan_installed_packages(modules)
        # 'repo' has only 2 rel_parts from modules: ('.hidden', 'repo'),
        # so it ends up in the result set.
        assert ".hidden/repo" in result

    def test_skips_single_level_entry(self, tmp_path):
        """A directory at depth=1 has only 1 rel_part; should be skipped."""
        modules = tmp_path / "apm_modules"
        top = modules / "owner"
        _make_apm_yml(top)
        result = _scan_installed_packages(modules)
        # "owner" alone has len(parts)==1, not >=2
        assert result == []

    def test_returns_multiple_packages(self, tmp_path):
        modules = tmp_path / "apm_modules"
        _make_apm_yml(modules / "ownerA" / "repoA")
        _make_apm_yml(modules / "ownerB" / "repoB")
        result = _scan_installed_packages(modules)
        assert "ownerA/repoA" in result
        assert "ownerB/repoB" in result
        assert len(result) == 2

    def test_ignores_dir_without_apm_yml_or_apm_dir(self, tmp_path):
        modules = tmp_path / "apm_modules"
        pkg = modules / "owner" / "repo"
        pkg.mkdir(parents=True)
        # No apm.yml and no .apm dir
        result = _scan_installed_packages(modules)
        assert result == []


# ---------------------------------------------------------------------------
# _is_nested_under_package
# ---------------------------------------------------------------------------


class TestIsNestedUnderPackage:
    def test_returns_false_when_parent_has_no_apm_yml(self, tmp_path):
        modules = tmp_path / "apm_modules"
        pkg = modules / "owner" / "repo"
        subdir = pkg / "skills" / "my-skill"
        subdir.mkdir(parents=True)
        # No apm.yml anywhere between subdir and modules
        assert _is_nested_under_package(subdir, modules) is False

    def test_returns_true_when_parent_has_apm_yml(self, tmp_path):
        modules = tmp_path / "apm_modules"
        pkg = modules / "owner" / "repo"
        _make_apm_yml(pkg)
        subdir = pkg / "skills" / "my-skill"
        subdir.mkdir(parents=True)
        assert _is_nested_under_package(subdir, modules) is True

    def test_returns_false_at_immediate_child_of_modules(self, tmp_path):
        modules = tmp_path / "apm_modules"
        child = modules / "owner"
        child.mkdir(parents=True)
        # parent of child IS modules; loop doesn't run
        assert _is_nested_under_package(child, modules) is False

    def test_deeply_nested_with_grandparent_apm_yml(self, tmp_path):
        modules = tmp_path / "apm_modules"
        root = modules / "owner" / "repo"
        _make_apm_yml(root)
        deep = root / "a" / "b" / "c"
        deep.mkdir(parents=True)
        assert _is_nested_under_package(deep, modules) is True


# ---------------------------------------------------------------------------
# _count_primitives
# ---------------------------------------------------------------------------


class TestCountPrimitives:
    def test_returns_zeros_when_no_apm_dir(self, tmp_path):
        counts = _count_primitives(tmp_path)
        assert counts == {
            "prompts": 0,
            "instructions": 0,
            "agents": 0,
            "skills": 0,
            "hooks": 0,
        }

    def test_counts_prompts_in_apm_dir(self, tmp_path):
        apm_dir = _make_apm_dir(tmp_path)
        prompts = apm_dir / "prompts"
        prompts.mkdir()
        (prompts / "a.prompt.md").write_text("")
        (prompts / "b.prompt.md").write_text("")
        counts = _count_primitives(tmp_path)
        assert counts["prompts"] == 2

    def test_counts_root_level_prompt_md_files(self, tmp_path):
        (tmp_path / "root.prompt.md").write_text("")
        counts = _count_primitives(tmp_path)
        assert counts["prompts"] == 1

    def test_counts_instructions_in_apm_dir(self, tmp_path):
        apm_dir = _make_apm_dir(tmp_path)
        instructions = apm_dir / "instructions"
        instructions.mkdir()
        (instructions / "guide.md").write_text("")
        counts = _count_primitives(tmp_path)
        assert counts["instructions"] == 1

    def test_counts_agents_in_apm_dir(self, tmp_path):
        apm_dir = _make_apm_dir(tmp_path)
        agents = apm_dir / "agents"
        agents.mkdir()
        (agents / "agent1.md").write_text("")
        (agents / "agent2.md").write_text("")
        counts = _count_primitives(tmp_path)
        assert counts["agents"] == 2

    def test_counts_skills_with_skill_md(self, tmp_path):
        apm_dir = _make_apm_dir(tmp_path)
        skills_dir = apm_dir / "skills"
        skills_dir.mkdir()
        skill1 = skills_dir / "my-skill"
        skill1.mkdir()
        (skill1 / SKILL_MD_FILENAME).write_text("")
        # Second skill without SKILL.md should NOT count
        skill2 = skills_dir / "empty-skill"
        skill2.mkdir()
        counts = _count_primitives(tmp_path)
        assert counts["skills"] == 1

    def test_counts_root_level_skill_md(self, tmp_path):
        (tmp_path / SKILL_MD_FILENAME).write_text("")
        counts = _count_primitives(tmp_path)
        assert counts["skills"] == 1

    def test_counts_hooks_in_hooks_dir(self, tmp_path):
        hooks = tmp_path / "hooks"
        hooks.mkdir()
        (hooks / "pre-commit.json").write_text("{}")
        counts = _count_primitives(tmp_path)
        assert counts["hooks"] == 1

    def test_counts_hooks_in_apm_hooks_dir(self, tmp_path):
        apm_dir = _make_apm_dir(tmp_path)
        apm_hooks = apm_dir / "hooks"
        apm_hooks.mkdir()
        (apm_hooks / "hook1.json").write_text("{}")
        (apm_hooks / "hook2.json").write_text("{}")
        counts = _count_primitives(tmp_path)
        assert counts["hooks"] == 2

    def test_combined_primitives(self, tmp_path):
        apm_dir = _make_apm_dir(tmp_path)
        (apm_dir / "prompts").mkdir()
        (apm_dir / "prompts" / "p.prompt.md").write_text("")
        (apm_dir / "instructions").mkdir()
        (apm_dir / "instructions" / "i.md").write_text("")
        (apm_dir / "agents").mkdir()
        (apm_dir / "agents" / "a.md").write_text("")
        skill_dir = apm_dir / "skills" / "s"
        skill_dir.mkdir(parents=True)
        (skill_dir / SKILL_MD_FILENAME).write_text("")
        hooks = tmp_path / "hooks"
        hooks.mkdir()
        (hooks / "h.json").write_text("{}")
        counts = _count_primitives(tmp_path)
        assert counts == {
            "prompts": 1,
            "instructions": 1,
            "agents": 1,
            "skills": 1,
            "hooks": 1,
        }


# ---------------------------------------------------------------------------
# _count_package_files
# ---------------------------------------------------------------------------


class TestCountPackageFiles:
    def test_no_apm_dir_no_root_prompts(self, tmp_path):
        context, workflow = _count_package_files(tmp_path)
        assert context == 0
        assert workflow == 0

    def test_no_apm_dir_with_root_prompt_md(self, tmp_path):
        (tmp_path / "wf.prompt.md").write_text("")
        context, workflow = _count_package_files(tmp_path)
        assert context == 0
        assert workflow == 1

    def test_counts_instructions_as_context(self, tmp_path):
        apm_dir = _make_apm_dir(tmp_path)
        inst = apm_dir / "instructions"
        inst.mkdir()
        (inst / "a.md").write_text("")
        (inst / "b.md").write_text("")
        context, _ = _count_package_files(tmp_path)
        assert context == 2

    def test_counts_chatmodes_as_context(self, tmp_path):
        apm_dir = _make_apm_dir(tmp_path)
        cm = apm_dir / "chatmodes"
        cm.mkdir()
        (cm / "chat.md").write_text("")
        context, _ = _count_package_files(tmp_path)
        assert context == 1

    def test_counts_contexts_dir_as_context(self, tmp_path):
        apm_dir = _make_apm_dir(tmp_path)
        ctx = apm_dir / "contexts"
        ctx.mkdir()
        (ctx / "c.md").write_text("")
        context, _ = _count_package_files(tmp_path)
        assert context == 1

    def test_counts_workflows_in_apm_prompts_dir(self, tmp_path):
        apm_dir = _make_apm_dir(tmp_path)
        prompts = apm_dir / "prompts"
        prompts.mkdir()
        (prompts / "wf.prompt.md").write_text("")
        _, workflow = _count_package_files(tmp_path)
        assert workflow == 1

    def test_counts_root_prompts_with_apm_dir(self, tmp_path):
        _make_apm_dir(tmp_path)
        (tmp_path / "root.prompt.md").write_text("")
        _, workflow = _count_package_files(tmp_path)
        assert workflow == 1

    def test_combined_counts(self, tmp_path):
        apm_dir = _make_apm_dir(tmp_path)
        inst = apm_dir / "instructions"
        inst.mkdir()
        (inst / "a.md").write_text("")
        prompts = apm_dir / "prompts"
        prompts.mkdir()
        (prompts / "b.prompt.md").write_text("")
        context, workflow = _count_package_files(tmp_path)
        assert context == 1
        assert workflow == 1


# ---------------------------------------------------------------------------
# _count_workflows
# ---------------------------------------------------------------------------


class TestCountWorkflows:
    def test_delegates_to_count_package_files(self, tmp_path):
        apm_dir = _make_apm_dir(tmp_path)
        prompts = apm_dir / "prompts"
        prompts.mkdir()
        (prompts / "wf.prompt.md").write_text("")
        assert _count_workflows(tmp_path) == 1

    def test_zero_when_no_prompts(self, tmp_path):
        assert _count_workflows(tmp_path) == 0


# ---------------------------------------------------------------------------
# _get_detailed_context_counts
# ---------------------------------------------------------------------------


class TestGetDetailedContextCounts:
    def test_returns_zeros_when_no_apm_dir(self, tmp_path):
        result = _get_detailed_context_counts(tmp_path)
        assert result == {"instructions": 0, "chatmodes": 0, "contexts": 0}

    def test_counts_instructions(self, tmp_path):
        apm_dir = _make_apm_dir(tmp_path)
        inst = apm_dir / "instructions"
        inst.mkdir()
        (inst / "a.md").write_text("")
        (inst / "b.md").write_text("")
        result = _get_detailed_context_counts(tmp_path)
        assert result["instructions"] == 2
        assert result["chatmodes"] == 0
        assert result["contexts"] == 0

    def test_counts_chatmodes(self, tmp_path):
        apm_dir = _make_apm_dir(tmp_path)
        cm = apm_dir / "chatmodes"
        cm.mkdir()
        (cm / "c.md").write_text("")
        result = _get_detailed_context_counts(tmp_path)
        assert result["chatmodes"] == 1

    def test_counts_contexts_using_context_dirname(self, tmp_path):
        """The 'contexts' key maps to the 'context' directory (not 'contexts')."""
        apm_dir = _make_apm_dir(tmp_path)
        ctx = apm_dir / "context"  # Note: directory name is 'context'
        ctx.mkdir()
        (ctx / "c.md").write_text("")
        result = _get_detailed_context_counts(tmp_path)
        assert result["contexts"] == 1

    def test_ignores_non_md_files(self, tmp_path):
        apm_dir = _make_apm_dir(tmp_path)
        inst = apm_dir / "instructions"
        inst.mkdir()
        (inst / "a.md").write_text("")
        (inst / "b.txt").write_text("")
        result = _get_detailed_context_counts(tmp_path)
        assert result["instructions"] == 1

    def test_combined_context_types(self, tmp_path):
        apm_dir = _make_apm_dir(tmp_path)
        (apm_dir / "instructions").mkdir()
        (apm_dir / "instructions" / "i.md").write_text("")
        (apm_dir / "chatmodes").mkdir()
        (apm_dir / "chatmodes" / "c.md").write_text("")
        (apm_dir / "context").mkdir()
        (apm_dir / "context" / "x.md").write_text("")
        result = _get_detailed_context_counts(tmp_path)
        assert result == {"instructions": 1, "chatmodes": 1, "contexts": 1}


# ---------------------------------------------------------------------------
# _get_package_display_info
# ---------------------------------------------------------------------------


class TestGetPackageDisplayInfo:
    def test_with_valid_apm_yml(self, tmp_path):
        _make_apm_yml(tmp_path, name="my-pkg", version="2.3.0")
        result = _get_package_display_info(tmp_path)
        assert result["name"] == "my-pkg"
        assert result["version"] == "2.3.0"
        assert result["display_name"] == "my-pkg@2.3.0"

    def test_without_apm_yml(self, tmp_path):
        pkg = tmp_path / "some-dir"
        pkg.mkdir()
        result = _get_package_display_info(pkg)
        assert result["name"] == "some-dir"
        assert result["version"] == "unknown"
        assert result["display_name"] == "some-dir@unknown"

    def test_handles_exception_gracefully(self, tmp_path):
        """If APMPackage.from_apm_yml raises, should return error dict."""
        _make_apm_yml(tmp_path, name="bad-pkg", version="1.0.0")
        with patch(
            "apm_cli.commands.deps._utils.APMPackage.from_apm_yml",
            side_effect=Exception("parse error"),
        ):
            result = _get_package_display_info(tmp_path)
        assert result["version"] == "error"
        assert "error" in result["display_name"]


# ---------------------------------------------------------------------------
# _get_detailed_package_info
# ---------------------------------------------------------------------------


class TestGetDetailedPackageInfo:
    def test_with_valid_apm_yml_and_primitives(self, tmp_path):
        _make_apm_yml(tmp_path, name="detailed-pkg", version="0.9.0")
        apm_dir = _make_apm_dir(tmp_path)
        inst = apm_dir / "instructions"
        inst.mkdir()
        (inst / "a.md").write_text("")
        result = _get_detailed_package_info(tmp_path)
        assert result["name"] == "detailed-pkg"
        assert result["version"] == "0.9.0"
        assert result["context_files"]["instructions"] == 1
        assert result["workflows"] == 0
        assert result["hooks"] == 0

    def test_without_apm_yml(self, tmp_path):
        pkg = tmp_path / "no-yml"
        pkg.mkdir()
        result = _get_detailed_package_info(pkg)
        assert result["name"] == "no-yml"
        assert result["version"] == "unknown"
        assert result["description"] == "No apm.yml found"
        assert "context_files" in result
        assert "workflows" in result
        assert "hooks" in result

    def test_handles_exception(self, tmp_path):
        """Exception during APMPackage.from_apm_yml returns error dict."""
        _make_apm_yml(tmp_path)
        with patch(
            "apm_cli.commands.deps._utils.APMPackage.from_apm_yml",
            side_effect=RuntimeError("fail"),
        ):
            result = _get_detailed_package_info(tmp_path)
        assert result["version"] == "error"
        assert "Error loading package" in result["description"]
        assert result["context_files"] == {
            "instructions": 0,
            "chatmodes": 0,
            "contexts": 0,
        }
        assert result["workflows"] == 0
        assert result["hooks"] == 0

    def test_includes_install_path(self, tmp_path):
        _make_apm_yml(tmp_path)
        result = _get_detailed_package_info(tmp_path)
        assert result["install_path"] == str(tmp_path.resolve())

    def test_counts_hooks_from_primitives(self, tmp_path):
        _make_apm_yml(tmp_path)
        hooks = tmp_path / "hooks"
        hooks.mkdir()
        (hooks / "h.json").write_text("{}")
        result = _get_detailed_package_info(tmp_path)
        assert result["hooks"] == 1

    def test_with_description_and_author(self, tmp_path):
        pkg = tmp_path
        pkg.mkdir(exist_ok=True)
        apm_yml = pkg / APM_YML_FILENAME
        apm_yml.write_text(
            "name: full-pkg\nversion: 1.0.0\ndescription: Full package\nauthor: Alice\n"
        )
        result = _get_detailed_package_info(pkg)
        assert result["description"] == "Full package"
        assert result["author"] == "Alice"
        # source is not parsed from apm.yml; it falls back to 'local'
        assert result["source"] == "local"
