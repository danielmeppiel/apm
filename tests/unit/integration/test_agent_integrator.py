"""Tests for agent integration functionality."""

import tempfile
from pathlib import Path
from unittest.mock import Mock
from datetime import datetime

from apm_cli.integration import AgentIntegrator
from apm_cli.models.apm_package import PackageInfo, APMPackage, ResolvedReference, GitReferenceType


class TestAgentIntegrator:
    """Test agent integration logic."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.integrator = AgentIntegrator()
    
    def teardown_method(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_should_integrate_always_returns_true(self):
        """Test integration is always enabled (zero-config approach)."""
        # No .github/ directory needed
        assert self.integrator.should_integrate(self.project_root) == True
        
        # Even with .github/ present
        github_dir = self.project_root / ".github"
        github_dir.mkdir()
        assert self.integrator.should_integrate(self.project_root) == True
    
    def test_find_agent_files_in_root_new_format(self):
        """Test finding .agent.md files in package root."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        # Create test agent files
        (package_dir / "security.agent.md").write_text("# Security Agent")
        (package_dir / "planner.agent.md").write_text("# Planner Agent")
        (package_dir / "readme.md").write_text("# Readme")  # Should not be found
        
        agents = self.integrator.find_agent_files(package_dir)
        assert len(agents) == 2
        assert all(p.name.endswith('.agent.md') for p in agents)
    
    def test_find_agent_files_in_root_legacy_format(self):
        """Test finding .chatmode.md files in package root (legacy)."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        # Create legacy chatmode files
        (package_dir / "default.chatmode.md").write_text("# Default Chatmode")
        (package_dir / "backend.chatmode.md").write_text("# Backend Chatmode")
        
        agents = self.integrator.find_agent_files(package_dir)
        assert len(agents) == 2
        assert all(p.name.endswith('.chatmode.md') for p in agents)
    
    def test_find_agent_files_in_apm_agents(self):
        """Test finding .agent.md files in .apm/agents/ (new standard)."""
        package_dir = self.project_root / "package"
        apm_agents = package_dir / ".apm" / "agents"
        apm_agents.mkdir(parents=True)
        
        (apm_agents / "security.agent.md").write_text("# Security Agent")
        
        agents = self.integrator.find_agent_files(package_dir)
        assert len(agents) == 1
        assert agents[0].name == "security.agent.md"
    
    def test_find_agent_files_in_apm_chatmodes(self):
        """Test finding .chatmode.md files in .apm/chatmodes/ (legacy)."""
        package_dir = self.project_root / "package"
        apm_chatmodes = package_dir / ".apm" / "chatmodes"
        apm_chatmodes.mkdir(parents=True)
        
        (apm_chatmodes / "default.chatmode.md").write_text("# Default Chatmode")
        
        agents = self.integrator.find_agent_files(package_dir)
        assert len(agents) == 1
        assert agents[0].name == "default.chatmode.md"
    
    def test_find_agent_files_mixed_formats(self):
        """Test finding both .agent.md and .chatmode.md files."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        (package_dir / "new.agent.md").write_text("# New Agent")
        (package_dir / "old.chatmode.md").write_text("# Old Chatmode")
        
        agents = self.integrator.find_agent_files(package_dir)
        assert len(agents) == 2
        extensions = {tuple(p.name.split('.')[-2:]) for p in agents}
        assert extensions == {('agent', 'md'), ('chatmode', 'md')}
    
    def test_copy_agent_verbatim(self):
        """Test copying agent file verbatim (no metadata injection)."""
        source = self.project_root / "source.agent.md"
        target = self.project_root / "target.agent.md"
        
        source_content = "# Security Agent\n\nSome agent content."
        source.write_text(source_content)
        
        self.integrator.copy_agent(source, target)
        
        target_content = target.read_text()
        assert target_content == source_content
    
    def test_get_target_filename_agent_format(self):
        """Test target filename generation with -apm suffix for .agent.md."""
        source = Path("/package/security.agent.md")
        package_name = "acme/security-standards"
        
        target = self.integrator.get_target_filename(source, package_name)
        # Intent-first naming: -apm suffix before extension
        assert target == "security-apm.agent.md"
    
    def test_get_target_filename_chatmode_format(self):
        """Test target filename generation with -apm suffix for .chatmode.md."""
        source = Path("/package/default.chatmode.md")
        package_name = "microsoft/apm-sample-package"
        
        target = self.integrator.get_target_filename(source, package_name)
        # Preserve original extension
        assert target == "default-apm.chatmode.md"
    

    
    def test_integrate_package_agents_creates_directory(self):
        """Test that integration creates .github/agents/ if missing."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "security.agent.md").write_text("# Security Agent")
        
        github_dir = self.project_root / ".github"
        github_dir.mkdir()
        
        package = APMPackage(
            name="test-pkg",
            version="1.0.0",
            package_path=package_dir
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=package_dir,
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
        
        result = self.integrator.integrate_package_agents(package_info, self.project_root)
        
        assert result.files_integrated == 1
        assert (self.project_root / ".github" / "agents").exists()
    
    def test_integrate_package_agents_always_overwrites(self):
        """Test that integration always overwrites existing files."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "security.agent.md").write_text("# Security Agent")
        
        github_agents = self.project_root / ".github" / "agents"
        github_agents.mkdir(parents=True)
        
        # Pre-create the target file with old content
        (github_agents / "security-apm.agent.md").write_text("# Old Content")
        
        package = APMPackage(
            name="test-pkg",
            version="1.0.0",
            package_path=package_dir,
            source="github.com/test/repo"
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=package_dir,
            resolved_reference=resolved_ref,
            installed_at="2024-01-01T00:00:00"
        )
        
        result = self.integrator.integrate_package_agents(package_info, self.project_root)
        
        assert result.files_integrated == 1
        assert result.files_updated == 0
        assert result.files_skipped == 0
        # Verify content was overwritten
        content = (github_agents / "security-apm.agent.md").read_text()
        assert content == "# Security Agent"
    
    def test_update_gitignore_adds_patterns(self):
        """Test that gitignore is updated with integrated agents patterns."""
        gitignore = self.project_root / ".gitignore"
        gitignore.write_text("# Existing content\napm_modules/\n")
        
        updated = self.integrator.update_gitignore_for_integrated_agents(self.project_root)
        
        assert updated == True
        content = gitignore.read_text()
        assert ".github/agents/*-apm.agent.md" in content
        assert ".github/agents/*-apm.chatmode.md" in content
    
    def test_update_gitignore_skips_if_exists(self):
        """Test that gitignore update is skipped if patterns exist."""
        gitignore = self.project_root / ".gitignore"
        gitignore.write_text(".github/agents/*-apm.agent.md\n.github/agents/*-apm.chatmode.md\n.claude/agents/*-apm.agent.md\n.claude/agents/*-apm.chatmode.md\n")
        
        updated = self.integrator.update_gitignore_for_integrated_agents(self.project_root)
        
        assert updated == False
    
    # ========== Verbatim Copy Tests ==========
    
    def test_copy_agent_preserves_frontmatter(self):
        """Test that copy_agent preserves existing YAML frontmatter as-is."""
        source = self.project_root / "source.agent.md"
        target = self.project_root / "target.agent.md"
        
        source_content = """---
description: My agent
tools: []
---

# Agent content here"""
        source.write_text(source_content)
        
        self.integrator.copy_agent(source, target)
        
        assert target.read_text() == source_content
    
    def test_integrate_first_time_copies_verbatim(self):
        """Test that first-time integration creates files with proper frontmatter metadata."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "security.agent.md").write_text("# Security Agent Content")
        
        github_agents = self.project_root / ".github" / "agents"
        github_agents.mkdir(parents=True)
        
        package = APMPackage(
            name="test-pkg",
            version="1.0.0",
            package_path=package_dir,
            source="github.com/test/repo"
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=package_dir,
            resolved_reference=resolved_ref,
            installed_at="2024-11-13T10:00:00"
        )
        
        result = self.integrator.integrate_package_agents(package_info, self.project_root)
        
        assert result.files_integrated == 1
        assert result.files_updated == 0
        assert result.files_skipped == 0
        
        # Verify verbatim copy — no frontmatter injected
        target_file = github_agents / "security-apm.agent.md"
        content = target_file.read_text()
        assert content == "# Security Agent Content"
        assert 'apm:' not in content
    
    def test_integrate_overwrites_existing_file(self):
        """Test that integration always overwrites existing files."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "security.agent.md").write_text("# Updated Agent Content")
        
        github_agents = self.project_root / ".github" / "agents"
        github_agents.mkdir(parents=True)
        
        # Pre-create file with old content
        (github_agents / "security-apm.agent.md").write_text("# Old Content")
        
        package = APMPackage(
            name="test-pkg",
            version="2.0.0",  # New version
            package_path=package_dir,
            source="github.com/test/repo"
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=package_dir,
            resolved_reference=resolved_ref,
            installed_at="2024-11-13T11:00:00"
        )
        
        result = self.integrator.integrate_package_agents(package_info, self.project_root)
        
        assert result.files_integrated == 1
        assert result.files_updated == 0
        assert result.files_skipped == 0
        
        # Verify content was overwritten verbatim
        target_file = github_agents / "security-apm.agent.md"
        content = target_file.read_text()
        assert content == "# Updated Agent Content"
    
    def test_integrate_all_files_always_copied(self):
        """Test integration copies all agent files regardless of existing state."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        # Create 3 agent files in package
        (package_dir / "new.agent.md").write_text("# New Agent")
        (package_dir / "existing.agent.md").write_text("# Updated Agent")
        (package_dir / "another.agent.md").write_text("# Another Agent")
        
        github_agents = self.project_root / ".github" / "agents"
        github_agents.mkdir(parents=True)
        
        # Pre-create some target files
        (github_agents / "existing-apm.agent.md").write_text("# Old Content")
        (github_agents / "another-apm.agent.md").write_text("# Old Another")
        
        package = APMPackage(
            name="test-pkg",
            version="2.0.0",
            package_path=package_dir,
            source="github.com/test/repo"
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="def456",
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=package_dir,
            resolved_reference=resolved_ref,
            installed_at="2024-11-13T11:00:00"
        )
        
        result = self.integrator.integrate_package_agents(package_info, self.project_root)
        
        assert result.files_integrated == 3  # All files always copied
        assert result.files_updated == 0
        assert result.files_skipped == 0
        
        # Verify all files exist with verbatim content
        assert (github_agents / "new-apm.agent.md").read_text() == "# New Agent"
        assert (github_agents / "existing-apm.agent.md").read_text() == "# Updated Agent"
        assert (github_agents / "another-apm.agent.md").read_text() == "# Another Agent"
    
    # ========== Sync Integration Tests (Nuke & Regenerate) ==========
    
    def test_sync_integration_removes_all_apm_agents(self):
        """Test that sync removes all APM-managed agent files."""
        github_agents = self.project_root / ".github" / "agents"
        github_agents.mkdir(parents=True)
        
        # Create APM-managed agent files
        (github_agents / "security-apm.agent.md").write_text("# Security Agent")
        (github_agents / "compliance-apm.agent.md").write_text("# Compliance Agent")
        
        apm_package = Mock()
        
        result = self.integrator.sync_integration(apm_package, self.project_root)
        
        assert result['files_removed'] == 2
        assert not (github_agents / "security-apm.agent.md").exists()
        assert not (github_agents / "compliance-apm.agent.md").exists()
    
    def test_sync_integration_removes_apm_chatmodes(self):
        """Test that sync removes APM-managed chatmode files."""
        github_agents = self.project_root / ".github" / "agents"
        github_agents.mkdir(parents=True)
        
        (github_agents / "default-apm.chatmode.md").write_text("# Default Chatmode")
        
        apm_package = Mock()
        
        result = self.integrator.sync_integration(apm_package, self.project_root)
        
        assert result['files_removed'] == 1
        assert not (github_agents / "default-apm.chatmode.md").exists()
    
    def test_sync_integration_preserves_non_apm_files(self):
        """Test that sync does not remove non-APM files."""
        github_agents = self.project_root / ".github" / "agents"
        github_agents.mkdir(parents=True)
        
        # Create APM and non-APM files
        (github_agents / "security-apm.agent.md").write_text("# APM Agent")
        (github_agents / "custom.agent.md").write_text("# Custom Agent")
        (github_agents / "my-agent.agent.md").write_text("# My Agent")
        
        apm_package = Mock()
        
        result = self.integrator.sync_integration(apm_package, self.project_root)
        
        assert result['files_removed'] == 1
        assert (github_agents / "custom.agent.md").exists()
        assert (github_agents / "my-agent.agent.md").exists()
    
    def test_sync_integration_handles_missing_agents_dir(self):
        """Test that sync gracefully handles missing .github/agents/ directory."""
        apm_package = Mock()
        
        # Should not raise exception
        result = self.integrator.sync_integration(apm_package, self.project_root)
        assert result['files_removed'] == 0
    
    def test_sync_integration_removes_apm_files_regardless_of_content(self):
        """Test that sync removes all *-apm files, regardless of content."""
        github_agents = self.project_root / ".github" / "agents"
        github_agents.mkdir(parents=True)
        
        # APM-managed file with no frontmatter — still removed by pattern
        (github_agents / "custom-apm.agent.md").write_text("# Custom agent without header")
        
        apm_package = Mock()
        
        result = self.integrator.sync_integration(apm_package, self.project_root)
        
        assert result['files_removed'] == 1
        assert not (github_agents / "custom-apm.agent.md").exists()

    # ========== Skill Separation Regression Tests (T5) ==========
    # ARCHITECTURE DECISION: Skills are NOT Agents
    # Skills go to .github/skills/ via SkillIntegrator
    # Agents go to .github/agents/ via AgentIntegrator  
    # These tests verify agent_integrator does NOT transform skills
    
    def test_skill_files_not_converted_to_agents(self):
        """Regression test: SKILL.md files must NOT be transformed to .agent.md.
        
        This was removed in T5 of the Skills Strategy refactoring.
        Skills and Agents have different semantics:
        - Skills: Declarative context/knowledge packages (.github/skills/)
        - Agents: Executable VSCode chat modes (.github/agents/)
        """
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        # Create a SKILL.md file
        (package_dir / "SKILL.md").write_text("""---
name: test-skill
description: A test skill
---
# Test Skill

This is a skill, not an agent.""")
        
        github_dir = self.project_root / ".github"
        github_dir.mkdir()
        
        package = APMPackage(
            name="skill-pkg",
            version="1.0.0",
            package_path=package_dir
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=package_dir,
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
        
        result = self.integrator.integrate_package_agents(package_info, self.project_root)
        
        # No agents should be created from skills
        assert result.files_integrated == 0
        
        # Verify .github/agents/ does NOT contain skill-derived files
        agents_dir = self.project_root / ".github" / "agents"
        if agents_dir.exists():
            agent_files = list(agents_dir.glob("*.agent.md"))
            for agent_file in agent_files:
                assert "skill" not in agent_file.name.lower(), \
                    f"SKILL.md was incorrectly transformed to agent: {agent_file}"

    def test_find_agent_files_ignores_skill_files(self):
        """AgentIntegrator.find_agent_files() must not find SKILL.md files."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        # Create various files
        (package_dir / "security.agent.md").write_text("# Real Agent")
        (package_dir / "SKILL.md").write_text("# This is a skill")
        (package_dir / "skill.md").write_text("# Also a skill")
        
        agents = self.integrator.find_agent_files(package_dir)
        
        # Only .agent.md files should be found
        assert len(agents) == 1
        assert agents[0].name == "security.agent.md"
        
        # Verify no SKILL.md files were picked up
        found_names = [a.name for a in agents]
        assert "SKILL.md" not in found_names
        assert "skill.md" not in found_names


class TestAgentSuffixPattern:
    """Test -apm suffix pattern edge cases for agents."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.integrator = AgentIntegrator()
    
    def test_suffix_with_simple_agent_filename(self):
        """Test suffix pattern with simple agent filename."""
        source = Path("security.agent.md")
        result = self.integrator.get_target_filename(source, "pkg")
        assert result == "security-apm.agent.md"
    
    def test_suffix_with_simple_chatmode_filename(self):
        """Test suffix pattern with simple chatmode filename."""
        source = Path("default.chatmode.md")
        result = self.integrator.get_target_filename(source, "pkg")
        assert result == "default-apm.chatmode.md"
    
    def test_suffix_with_hyphenated_filename(self):
        """Test suffix pattern with hyphenated filename."""
        source = Path("backend-engineer.agent.md")
        result = self.integrator.get_target_filename(source, "pkg")
        assert result == "backend-engineer-apm.agent.md"
    
    def test_suffix_with_multi_part_filename(self):
        """Test suffix pattern with multi-part filename."""
        source = Path("security-audit-tool.agent.md")
        result = self.integrator.get_target_filename(source, "pkg")
        assert result == "security-audit-tool-apm.agent.md"
    
    def test_suffix_preserves_original_name(self):
        """Test that original filename structure is preserved."""
        source = Path("my_custom-agent.agent.md")
        result = self.integrator.get_target_filename(source, "pkg")
        assert result == "my_custom-agent-apm.agent.md"
    
    def test_gitignore_pattern_matches_suffix_files(self):
        """Test that gitignore patterns match -apm suffix files."""
        import fnmatch
        
        agent_pattern = "*-apm.agent.md"
        chatmode_pattern = "*-apm.chatmode.md"
        
        # Agent pattern should match
        assert fnmatch.fnmatch("security-apm.agent.md", agent_pattern)
        assert fnmatch.fnmatch("test-apm.agent.md", agent_pattern)
        assert fnmatch.fnmatch("a-b-c-apm.agent.md", agent_pattern)
        
        # Chatmode pattern should match
        assert fnmatch.fnmatch("default-apm.chatmode.md", chatmode_pattern)
        assert fnmatch.fnmatch("backend-apm.chatmode.md", chatmode_pattern)
        
        # Should NOT match
        assert not fnmatch.fnmatch("security.agent.md", agent_pattern)
        assert not fnmatch.fnmatch("apm.agent.md", agent_pattern)
        assert not fnmatch.fnmatch("default.chatmode.md", chatmode_pattern)
