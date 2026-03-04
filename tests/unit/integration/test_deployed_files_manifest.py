"""Tests for deployed_files manifest tracking across lockfile and integrators.

Covers:
- LockedDependency serialization/deserialization of deployed_files
- Migration from legacy deployed_skills → deployed_files
- Collision detection in PromptIntegrator
- Collision detection in AgentIntegrator (github + claude)
- Manifest-based sync (cleanup) in all integrators
"""

import pytest
from datetime import datetime
from pathlib import Path

from apm_cli.deps.lockfile import LockedDependency, LockFile
from apm_cli.integration.prompt_integrator import PromptIntegrator
from apm_cli.integration.agent_integrator import AgentIntegrator
from apm_cli.models.apm_package import (
    APMPackage,
    PackageInfo,
    ResolvedReference,
    GitReferenceType,
)


def _make_package_info(tmp_path: Path, name: str = "test-pkg",
                       prompt_files: dict = None, agent_files: dict = None) -> PackageInfo:
    """Create a PackageInfo with optional prompt/agent files on disk."""
    pkg_dir = tmp_path / "apm_modules" / name
    pkg_dir.mkdir(parents=True, exist_ok=True)

    for fname, content in (prompt_files or {}).items():
        (pkg_dir / fname).write_text(content, encoding="utf-8")
    for fname, content in (agent_files or {}).items():
        (pkg_dir / fname).write_text(content, encoding="utf-8")

    package = APMPackage(name=name, version="1.0.0", package_path=pkg_dir)
    resolved = ResolvedReference(
        original_ref="main",
        ref_type=GitReferenceType.BRANCH,
        resolved_commit="abc123",
        ref_name="main",
    )
    return PackageInfo(
        package=package,
        install_path=pkg_dir,
        resolved_reference=resolved,
        installed_at=datetime.now().isoformat(),
    )


# ---------------------------------------------------------------------------
# 1. Lockfile deployed_files serialization
# ---------------------------------------------------------------------------


class TestLockedDependencyDeployedFiles:
    """Serialization and deserialization of the deployed_files field."""

    def test_serialize_with_deployed_files(self):
        """Produce a dict containing sorted deployed_files."""
        dep = LockedDependency(
            repo_url="github.com/o/r",
            deployed_files=[".github/prompts/b.prompt.md", ".github/prompts/a.prompt.md"],
        )
        d = dep.to_dict()
        assert d["deployed_files"] == [
            ".github/prompts/a.prompt.md",
            ".github/prompts/b.prompt.md",
        ]

    def test_empty_deployed_files_omitted_from_yaml(self):
        """Omit deployed_files key when the list is empty (smaller lockfile)."""
        dep = LockedDependency(repo_url="github.com/o/r")
        d = dep.to_dict()
        assert "deployed_files" not in d

    def test_deserialize_deployed_files(self):
        """Round-trip through from_dict preserves deployed_files."""
        data = {
            "repo_url": "github.com/o/r",
            "deployed_files": [".github/agents/sec.agent.md"],
        }
        dep = LockedDependency.from_dict(data)
        assert dep.deployed_files == [".github/agents/sec.agent.md"]

    def test_migrate_deployed_skills_to_deployed_files(self):
        """Legacy deployed_skills is migrated to deployed_files paths."""
        data = {
            "repo_url": "github.com/o/r",
            "deployed_skills": ["code-review", "accessibility"],
        }
        dep = LockedDependency.from_dict(data)
        assert ".github/skills/code-review/" in dep.deployed_files
        assert ".github/skills/accessibility/" in dep.deployed_files
        assert len(dep.deployed_files) == 2

    def test_deployed_files_wins_over_legacy_skills(self):
        """When both fields exist, deployed_files takes precedence."""
        data = {
            "repo_url": "github.com/o/r",
            "deployed_files": [".github/prompts/a.prompt.md"],
            "deployed_skills": ["ignored-skill"],
        }
        dep = LockedDependency.from_dict(data)
        assert dep.deployed_files == [".github/prompts/a.prompt.md"]


# ---------------------------------------------------------------------------
# 2. Prompt integrator — collision detection
# ---------------------------------------------------------------------------


class TestPromptCollisionDetection:
    """Collision detection in PromptIntegrator.integrate_package_prompts."""

    def test_managed_files_none_no_collision_check(self, tmp_path: Path):
        """Legacy mode: managed_files=None → always overwrite."""
        prompts_dir = tmp_path / ".github" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "review.prompt.md").write_text("# user version")

        info = _make_package_info(
            tmp_path, prompt_files={"review.prompt.md": "# pkg version"}
        )
        result = PromptIntegrator().integrate_package_prompts(
            info, tmp_path, force=False, managed_files=None
        )
        assert result.files_integrated == 1
        assert result.files_skipped == 0
        assert (prompts_dir / "review.prompt.md").read_text() == "# pkg version"

    def test_empty_managed_set_all_collisions(self, tmp_path: Path):
        """managed_files=set() → every pre-existing file is a collision."""
        prompts_dir = tmp_path / ".github" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "review.prompt.md").write_text("# user version")

        info = _make_package_info(
            tmp_path, prompt_files={"review.prompt.md": "# pkg version"}
        )
        result = PromptIntegrator().integrate_package_prompts(
            info, tmp_path, force=False, managed_files=set()
        )
        assert result.files_integrated == 0
        assert result.files_skipped == 1
        assert (prompts_dir / "review.prompt.md").read_text() == "# user version"

    def test_managed_file_not_collision(self, tmp_path: Path):
        """File listed in managed_files is overwritten (not a collision)."""
        prompts_dir = tmp_path / ".github" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "review.prompt.md").write_text("# old")

        info = _make_package_info(
            tmp_path, prompt_files={"review.prompt.md": "# new"}
        )
        managed = {".github/prompts/review.prompt.md"}
        result = PromptIntegrator().integrate_package_prompts(
            info, tmp_path, force=False, managed_files=managed
        )
        assert result.files_integrated == 1
        assert result.files_skipped == 0
        assert (prompts_dir / "review.prompt.md").read_text() == "# new"

    def test_unmanaged_file_is_collision(self, tmp_path: Path):
        """File NOT in managed_files is skipped as a collision."""
        prompts_dir = tmp_path / ".github" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "review.prompt.md").write_text("# user")

        info = _make_package_info(
            tmp_path, prompt_files={"review.prompt.md": "# pkg"}
        )
        managed = {".github/prompts/OTHER.prompt.md"}
        result = PromptIntegrator().integrate_package_prompts(
            info, tmp_path, force=False, managed_files=managed
        )
        assert result.files_integrated == 0
        assert result.files_skipped == 1

    def test_force_overrides_collision(self, tmp_path: Path):
        """force=True overwrites even unmanaged files."""
        prompts_dir = tmp_path / ".github" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "review.prompt.md").write_text("# user")

        info = _make_package_info(
            tmp_path, prompt_files={"review.prompt.md": "# pkg"}
        )
        result = PromptIntegrator().integrate_package_prompts(
            info, tmp_path, force=True, managed_files=set()
        )
        assert result.files_integrated == 1
        assert result.files_skipped == 0
        assert (prompts_dir / "review.prompt.md").read_text() == "# pkg"

    def test_target_paths_only_includes_deployed(self, tmp_path: Path):
        """Skipped (collision) files are excluded from target_paths."""
        prompts_dir = tmp_path / ".github" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "a.prompt.md").write_text("# user a")

        info = _make_package_info(
            tmp_path,
            prompt_files={
                "a.prompt.md": "# pkg a",
                "b.prompt.md": "# pkg b",
            },
        )
        managed = {".github/prompts/b.prompt.md"}  # only b is managed
        result = PromptIntegrator().integrate_package_prompts(
            info, tmp_path, force=False, managed_files=managed
        )
        rel_paths = [str(p.relative_to(tmp_path)) for p in result.target_paths]
        assert ".github/prompts/b.prompt.md" in rel_paths
        assert ".github/prompts/a.prompt.md" not in rel_paths


# ---------------------------------------------------------------------------
# 3. Prompt integrator — manifest-based sync
# ---------------------------------------------------------------------------


class TestPromptSync:
    """Manifest-based cleanup in PromptIntegrator.sync_integration."""

    def test_sync_removes_managed_files(self, tmp_path: Path):
        """Only files in managed_files are removed."""
        prompts_dir = tmp_path / ".github" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "a.prompt.md").write_text("managed")
        (prompts_dir / "b.prompt.md").write_text("user")

        managed = {".github/prompts/a.prompt.md"}
        stats = PromptIntegrator().sync_integration(None, tmp_path, managed_files=managed)

        assert stats["files_removed"] == 1
        assert not (prompts_dir / "a.prompt.md").exists()
        assert (prompts_dir / "b.prompt.md").exists()

    def test_sync_legacy_fallback_glob(self, tmp_path: Path):
        """managed_files=None → legacy glob removes *-apm.prompt.md only."""
        prompts_dir = tmp_path / ".github" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "review-apm.prompt.md").write_text("old style")
        (prompts_dir / "my-custom.prompt.md").write_text("user")

        stats = PromptIntegrator().sync_integration(None, tmp_path, managed_files=None)

        assert stats["files_removed"] == 1
        assert not (prompts_dir / "review-apm.prompt.md").exists()
        assert (prompts_dir / "my-custom.prompt.md").exists()

    def test_sync_ignores_non_prompt_paths(self, tmp_path: Path):
        """Managed paths outside .github/prompts/ are ignored by prompt sync."""
        prompts_dir = tmp_path / ".github" / "prompts"
        prompts_dir.mkdir(parents=True)
        agents_dir = tmp_path / ".github" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "sec.agent.md").write_text("agent")

        managed = {".github/agents/sec.agent.md"}
        stats = PromptIntegrator().sync_integration(None, tmp_path, managed_files=managed)
        assert stats["files_removed"] == 0
        assert (agents_dir / "sec.agent.md").exists()


# ---------------------------------------------------------------------------
# 4. Agent integrator — collision detection (github + claude)
# ---------------------------------------------------------------------------


class TestAgentCollisionDetection:
    """Collision detection in AgentIntegrator for .github/agents/."""

    def test_managed_files_none_no_collision_check(self, tmp_path: Path):
        """Legacy mode: always overwrite when managed_files=None."""
        agents_dir = tmp_path / ".github" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "security.agent.md").write_text("# user")

        info = _make_package_info(
            tmp_path, agent_files={"security.agent.md": "# pkg"}
        )
        result = AgentIntegrator().integrate_package_agents(
            info, tmp_path, force=False, managed_files=None
        )
        assert result.files_integrated >= 1
        assert result.files_skipped == 0

    def test_empty_managed_set_all_collisions(self, tmp_path: Path):
        """managed_files=set() → every pre-existing file is a collision."""
        agents_dir = tmp_path / ".github" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "security.agent.md").write_text("# user")

        info = _make_package_info(
            tmp_path, agent_files={"security.agent.md": "# pkg"}
        )
        result = AgentIntegrator().integrate_package_agents(
            info, tmp_path, force=False, managed_files=set()
        )
        assert result.files_skipped >= 1

    def test_force_overrides_agent_collision(self, tmp_path: Path):
        """force=True overwrites even unmanaged agent files."""
        agents_dir = tmp_path / ".github" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "security.agent.md").write_text("# user")

        info = _make_package_info(
            tmp_path, agent_files={"security.agent.md": "# pkg"}
        )
        result = AgentIntegrator().integrate_package_agents(
            info, tmp_path, force=True, managed_files=set()
        )
        assert result.files_integrated >= 1
        assert result.files_skipped == 0


class TestClaudeAgentCollisionDetection:
    """Collision detection in AgentIntegrator for .claude/agents/."""

    def test_managed_files_none_no_collision_check(self, tmp_path: Path):
        """Legacy mode: always overwrite when managed_files=None."""
        claude_dir = tmp_path / ".claude" / "agents"
        claude_dir.mkdir(parents=True)
        (claude_dir / "security.md").write_text("# user")

        info = _make_package_info(
            tmp_path, agent_files={"security.agent.md": "# pkg"}
        )
        result = AgentIntegrator().integrate_package_agents_claude(
            info, tmp_path, force=False, managed_files=None
        )
        assert result.files_integrated >= 1
        assert result.files_skipped == 0

    def test_empty_managed_set_all_collisions(self, tmp_path: Path):
        """managed_files=set() → every pre-existing file is a collision."""
        claude_dir = tmp_path / ".claude" / "agents"
        claude_dir.mkdir(parents=True)
        (claude_dir / "security.md").write_text("# user")

        info = _make_package_info(
            tmp_path, agent_files={"security.agent.md": "# pkg"}
        )
        result = AgentIntegrator().integrate_package_agents_claude(
            info, tmp_path, force=False, managed_files=set()
        )
        assert result.files_skipped >= 1

    def test_force_overrides_claude_collision(self, tmp_path: Path):
        """force=True bypasses collision check for Claude agents."""
        claude_dir = tmp_path / ".claude" / "agents"
        claude_dir.mkdir(parents=True)
        (claude_dir / "security.md").write_text("# user")

        info = _make_package_info(
            tmp_path, agent_files={"security.agent.md": "# pkg"}
        )
        result = AgentIntegrator().integrate_package_agents_claude(
            info, tmp_path, force=True, managed_files=set()
        )
        assert result.files_integrated >= 1
        assert result.files_skipped == 0


# ---------------------------------------------------------------------------
# 5. Agent integrator — manifest-based sync
# ---------------------------------------------------------------------------


class TestAgentSync:
    """Manifest-based cleanup in AgentIntegrator sync methods."""

    def test_sync_github_removes_managed_files(self, tmp_path: Path):
        """Only managed agent files in .github/agents/ are removed."""
        agents_dir = tmp_path / ".github" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "a.agent.md").write_text("managed")
        (agents_dir / "b.agent.md").write_text("user")

        managed = {".github/agents/a.agent.md"}
        stats = AgentIntegrator().sync_integration(None, tmp_path, managed_files=managed)

        assert stats["files_removed"] == 1
        assert not (agents_dir / "a.agent.md").exists()
        assert (agents_dir / "b.agent.md").exists()

    def test_sync_github_legacy_glob(self, tmp_path: Path):
        """Legacy fallback removes *-apm.agent.md files."""
        agents_dir = tmp_path / ".github" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "sec-apm.agent.md").write_text("old")
        (agents_dir / "custom.agent.md").write_text("user")

        stats = AgentIntegrator().sync_integration(None, tmp_path, managed_files=None)

        assert stats["files_removed"] == 1
        assert not (agents_dir / "sec-apm.agent.md").exists()
        assert (agents_dir / "custom.agent.md").exists()

    def test_sync_claude_removes_managed_files(self, tmp_path: Path):
        """Only managed agent files in .claude/agents/ are removed."""
        claude_dir = tmp_path / ".claude" / "agents"
        claude_dir.mkdir(parents=True)
        (claude_dir / "a.md").write_text("managed")
        (claude_dir / "b.md").write_text("user")

        managed = {".claude/agents/a.md"}
        stats = AgentIntegrator().sync_integration_claude(
            None, tmp_path, managed_files=managed
        )

        assert stats["files_removed"] == 1
        assert not (claude_dir / "a.md").exists()
        assert (claude_dir / "b.md").exists()

    def test_sync_claude_legacy_glob(self, tmp_path: Path):
        """Legacy fallback removes *-apm.md files from .claude/agents/."""
        claude_dir = tmp_path / ".claude" / "agents"
        claude_dir.mkdir(parents=True)
        (claude_dir / "sec-apm.md").write_text("old")
        (claude_dir / "custom.md").write_text("user")

        stats = AgentIntegrator().sync_integration_claude(
            None, tmp_path, managed_files=None
        )

        assert stats["files_removed"] == 1
        assert not (claude_dir / "sec-apm.md").exists()
        assert (claude_dir / "custom.md").exists()
