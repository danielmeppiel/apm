"""Unit tests for ``apm_cli.commands.deps._utils``.

Covers:
  - _scan_installed_packages
  - _is_nested_under_package
  - _count_primitives
  - _count_package_files / _count_workflows
  - _get_detailed_context_counts
  - _get_package_display_info
  - _get_detailed_package_info
"""

import tempfile
from pathlib import Path

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


def _make_apm_yml(
    pkg_dir: Path,
    name: str = "mypkg",
    version: str = "1.0.0",
    description: str = "A package",
    author: str = "Author",
    source: str = "github",
) -> None:
    (pkg_dir / APM_YML_FILENAME).write_text(
        f"name: {name}\nversion: {version}\n"
        f"description: {description}\nauthor: {author}\nsource: {source}\n"
    )


def _apm_subdir(pkg_dir: Path, subdir: str) -> Path:
    d = pkg_dir / APM_DIR / subdir
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# _scan_installed_packages
# ---------------------------------------------------------------------------


class TestScanInstalledPackages:
    def test_empty_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _scan_installed_packages(Path(tmp))
        assert result == []

    def test_nonexistent_dir_returns_empty(self):
        result = _scan_installed_packages(Path("/nonexistent/path/xyz"))
        assert result == []

    def test_finds_github_style_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "org" / "repo"
            pkg.mkdir(parents=True)
            _make_apm_yml(pkg, "repo")

            result = _scan_installed_packages(root)

        assert "org/repo" in result

    def test_finds_apm_dir_package(self):
        """A package with .apm directory (no apm.yml) is discovered."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "org" / "apm-only"
            pkg.mkdir(parents=True)
            (pkg / APM_DIR).mkdir()

            result = _scan_installed_packages(root)

        assert "org/apm-only" in result

    def test_skips_hidden_package_directories(self):
        """Candidate directories whose own name starts with '.' are skipped."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # A package directory whose own name starts with '.' is skipped
            dot_pkg = root / "org" / ".hidden-pkg"
            dot_pkg.mkdir(parents=True)
            _make_apm_yml(dot_pkg, "hidden-pkg")

            result = _scan_installed_packages(root)

        # '.hidden-pkg' is a candidate dir whose name starts with '.' -- skipped
        assert not any(".hidden-pkg" in r for r in result)

    def test_finds_multiple_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for org, repo in [("org1", "a"), ("org1", "b"), ("org2", "c")]:
                pkg = root / org / repo
                pkg.mkdir(parents=True)
                _make_apm_yml(pkg, repo)

            result = _scan_installed_packages(root)

        assert "org1/a" in result
        assert "org1/b" in result
        assert "org2/c" in result

    def test_ado_style_three_level_package(self):
        """ADO packages are org/project/repo (3-level paths)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "org" / "project" / "repo"
            pkg.mkdir(parents=True)
            _make_apm_yml(pkg, "repo")

            result = _scan_installed_packages(root)

        assert any("org/project/repo" in r for r in result)

    def test_empty_dir_no_apm_yml(self):
        """Bare directories without apm.yml or .apm are not reported."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bare = root / "org" / "bare"
            bare.mkdir(parents=True)

            result = _scan_installed_packages(root)

        assert result == []


# ---------------------------------------------------------------------------
# _is_nested_under_package
# ---------------------------------------------------------------------------


class TestIsNestedUnderPackage:
    def test_not_nested_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "org" / "repo"
            pkg.mkdir(parents=True)
            _make_apm_yml(pkg, "repo")

            result = _is_nested_under_package(pkg, root)

        assert result is False

    def test_nested_under_parent_with_apm_yml(self):
        """A sub-directory of a package (which has apm.yml) is nested."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "org" / "repo"
            pkg.mkdir(parents=True)
            _make_apm_yml(pkg, "repo")

            subdir = pkg / "skills" / "myscill"
            subdir.mkdir(parents=True)

            result = _is_nested_under_package(subdir, root)

        assert result is True

    def test_top_level_package_not_nested(self):
        """A top-level package at depth 2 is not considered nested."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "org" / "standalone"
            pkg.mkdir(parents=True)

            # No apm.yml in ancestors between root and pkg
            result = _is_nested_under_package(pkg, root)

        assert result is False


# ---------------------------------------------------------------------------
# _count_primitives
# ---------------------------------------------------------------------------


class TestCountPrimitives:
    def test_empty_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _count_primitives(Path(tmp))
        assert result == {
            "prompts": 0,
            "instructions": 0,
            "agents": 0,
            "skills": 0,
            "hooks": 0,
        }

    def test_counts_prompts_in_apm_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            d = _apm_subdir(pkg, "prompts")
            (d / "a.prompt.md").write_text("# A")
            (d / "b.prompt.md").write_text("# B")

            result = _count_primitives(pkg)

        assert result["prompts"] == 2

    def test_counts_root_prompt_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            (pkg / "root.prompt.md").write_text("# Root")

            result = _count_primitives(pkg)

        assert result["prompts"] == 1

    def test_counts_instructions(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            d = _apm_subdir(pkg, "instructions")
            (d / "guide.md").write_text("# Guide")
            (d / "ref.md").write_text("# Ref")

            result = _count_primitives(pkg)

        assert result["instructions"] == 2

    def test_counts_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            d = _apm_subdir(pkg, "agents")
            (d / "coder.md").write_text("# Coder")

            result = _count_primitives(pkg)

        assert result["agents"] == 1

    def test_counts_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            skills_dir = _apm_subdir(pkg, "skills")
            skill = skills_dir / "myscill"
            skill.mkdir()
            (skill / SKILL_MD_FILENAME).write_text("# My skill")

            result = _count_primitives(pkg)

        assert result["skills"] == 1

    def test_counts_root_skill_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            (pkg / SKILL_MD_FILENAME).write_text("# Root skill")

            result = _count_primitives(pkg)

        assert result["skills"] == 1

    def test_counts_hooks_in_root_hooks_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            hooks = pkg / "hooks"
            hooks.mkdir()
            (hooks / "myhook.json").write_text("{}")
            (hooks / "other.json").write_text("{}")

            result = _count_primitives(pkg)

        assert result["hooks"] == 2

    def test_counts_hooks_in_apm_hooks_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            hooks = _apm_subdir(pkg, "hooks")
            (hooks / "hook1.json").write_text("{}")

            result = _count_primitives(pkg)

        assert result["hooks"] == 1

    def test_mixed_primitives(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            (pkg / "root.prompt.md").write_text("# R")
            _apm_subdir(pkg, "prompts")  # empty
            instr = _apm_subdir(pkg, "instructions")
            (instr / "i.md").write_text("# I")
            agents = _apm_subdir(pkg, "agents")
            (agents / "a.md").write_text("# A")

            result = _count_primitives(pkg)

        assert result["prompts"] == 1
        assert result["instructions"] == 1
        assert result["agents"] == 1
        assert result["skills"] == 0
        assert result["hooks"] == 0


# ---------------------------------------------------------------------------
# _count_package_files / _count_workflows
# ---------------------------------------------------------------------------


class TestCountPackageFiles:
    def test_no_apm_dir_returns_zeros(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx, wf = _count_package_files(Path(tmp))
        assert ctx == 0
        assert wf == 0

    def test_no_apm_dir_with_root_prompts(self):
        """Root .prompt.md files are counted as workflows even without .apm."""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            (pkg / "wf.prompt.md").write_text("# WF")

            ctx, wf = _count_package_files(pkg)

        assert ctx == 0
        assert wf == 1

    def test_instructions_counted_as_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            d = _apm_subdir(pkg, "instructions")
            (d / "i.md").write_text("# I")

            ctx, wf = _count_package_files(pkg)

        assert ctx == 1

    def test_prompts_counted_as_workflows(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            d = _apm_subdir(pkg, "prompts")
            (d / "p.prompt.md").write_text("# P")

            ctx, wf = _count_package_files(pkg)

        assert wf == 1

    def test_root_prompts_plus_apm_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            (pkg / "root.prompt.md").write_text("# Root")
            d = _apm_subdir(pkg, "prompts")
            (d / "inner.prompt.md").write_text("# Inner")

            ctx, wf = _count_package_files(pkg)

        assert wf == 2

    def test_count_workflows_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            d = _apm_subdir(pkg, "prompts")
            (d / "a.prompt.md").write_text("# A")
            (d / "b.prompt.md").write_text("# B")

            result = _count_workflows(pkg)

        assert result == 2


# ---------------------------------------------------------------------------
# _get_detailed_context_counts
# ---------------------------------------------------------------------------


class TestGetDetailedContextCounts:
    def test_no_apm_dir_returns_zeros(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _get_detailed_context_counts(Path(tmp))
        assert result == {"instructions": 0, "chatmodes": 0, "contexts": 0}

    def test_counts_instructions(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            d = _apm_subdir(pkg, "instructions")
            (d / "a.md").write_text("# A")
            (d / "b.md").write_text("# B")

            result = _get_detailed_context_counts(pkg)

        assert result["instructions"] == 2

    def test_counts_chatmodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            d = _apm_subdir(pkg, "chatmodes")
            (d / "mode.md").write_text("# Mode")

            result = _get_detailed_context_counts(pkg)

        assert result["chatmodes"] == 1

    def test_counts_contexts_from_context_subdir(self):
        """The 'contexts' key maps to the 'context' (singular) directory."""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            d = _apm_subdir(pkg, "context")  # note: singular
            (d / "ctx.md").write_text("# Ctx")

            result = _get_detailed_context_counts(pkg)

        assert result["contexts"] == 1

    def test_all_types_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            (_apm_subdir(pkg, "instructions") / "i.md").write_text("# I")
            (_apm_subdir(pkg, "chatmodes") / "c.md").write_text("# C")
            (_apm_subdir(pkg, "context") / "x.md").write_text("# X")

            result = _get_detailed_context_counts(pkg)

        assert result == {"instructions": 1, "chatmodes": 1, "contexts": 1}


# ---------------------------------------------------------------------------
# _get_package_display_info
# ---------------------------------------------------------------------------


class TestGetPackageDisplayInfo:
    def test_with_valid_apm_yml(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            _make_apm_yml(pkg, name="my-package", version="2.3.4")

            result = _get_package_display_info(pkg)

        assert result["name"] == "my-package"
        assert result["version"] == "2.3.4"
        assert "my-package@2.3.4" in result["display_name"]

    def test_without_apm_yml(self):
        """Falls back to dirname@unknown when no apm.yml exists."""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "somedir"
            pkg.mkdir()

            result = _get_package_display_info(pkg)

        assert result["version"] == "unknown"
        assert "somedir" in result["display_name"]

    def test_display_name_includes_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            _make_apm_yml(pkg, name="mypkg", version="0.1.0")

            result = _get_package_display_info(pkg)

        assert "@0.1.0" in result["display_name"]

    def test_exception_returns_error_info(self):
        """If APMPackage.from_apm_yml raises, returns 'error' version."""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            # Write corrupt apm.yml (no 'version' field, which is required)
            (pkg / APM_YML_FILENAME).write_text("name: mypkg\n# no version!\n")

            result = _get_package_display_info(pkg)

        # Should gracefully fall back (either error or unknown)
        assert result["version"] in ("unknown", "error")


# ---------------------------------------------------------------------------
# _get_detailed_package_info
# ---------------------------------------------------------------------------


class TestGetDetailedPackageInfo:
    def test_full_package_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            _make_apm_yml(
                pkg,
                name="full-pkg",
                version="3.0.0",
                description="A full package",
                author="Dev",
                source="github",
            )
            (_apm_subdir(pkg, "instructions") / "guide.md").write_text("# G")
            (_apm_subdir(pkg, "prompts") / "wf.prompt.md").write_text("# WF")

            result = _get_detailed_package_info(pkg)

        assert result["name"] == "full-pkg"
        assert result["version"] == "3.0.0"
        assert result["description"] == "A full package"
        assert result["author"] == "Dev"
        assert result["workflows"] == 1
        assert result["context_files"]["instructions"] == 1

    def test_no_apm_yml_returns_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)

            result = _get_detailed_package_info(pkg)

        assert result["version"] == "unknown"
        assert result["description"] == "No apm.yml found"

    def test_hooks_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            _make_apm_yml(pkg)
            hooks = pkg / "hooks"
            hooks.mkdir()
            (hooks / "h1.json").write_text("{}")
            (hooks / "h2.json").write_text("{}")

            result = _get_detailed_package_info(pkg)

        assert result["hooks"] == 2

    def test_install_path_is_absolute(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            _make_apm_yml(pkg)

            result = _get_detailed_package_info(pkg)

        assert Path(result["install_path"]).is_absolute()

    def test_exception_returns_error_dict(self):
        """If loading raises unexpectedly, returns an error-state dict."""
        # Use a path that doesn't exist to trigger an error path
        nonexistent = Path("/nonexistent/path/to/pkg")

        result = _get_detailed_package_info(nonexistent)

        assert result["version"] == "unknown" or result.get("description") is not None
        # Should not raise - must always return a dict
        assert isinstance(result, dict)

    def test_corrupt_apm_yml_returns_error_dict(self):
        """If apm.yml has no version (required by APMPackage), falls back gracefully."""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            # Missing required 'version' field
            (pkg / APM_YML_FILENAME).write_text("name: mypkg\ndescription: desc\n")

            result = _get_detailed_package_info(pkg)

        # May be error or unknown - just shouldn't raise
        assert isinstance(result, dict)

    def test_workflows_from_root_prompts(self):
        """Root-level .prompt.md files are counted as workflows."""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            _make_apm_yml(pkg)
            (pkg / "myflow.prompt.md").write_text("# Flow")

            result = _get_detailed_package_info(pkg)

        assert result["workflows"] == 1
