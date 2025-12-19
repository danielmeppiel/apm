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
    
    def test_copy_agent_with_metadata(self):
        """Test copying agent file with metadata in frontmatter."""
        source = self.project_root / "source.agent.md"
        target = self.project_root / "target.agent.md"
        
        source_content = "# Security Agent\n\nSome agent content."
        source.write_text(source_content)
        
        package = APMPackage(
            name="test-pkg",
            version="1.0.0",
            package_path=Path("/fake/path"),
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
            install_path=Path("/fake/install"),
            resolved_reference=resolved_ref,
            installed_at="2024-11-13T10:00:00"
        )
        
        self.integrator.copy_agent_with_metadata(source, target, package_info, source)
        
        target_content = target.read_text()
        assert "---" in target_content  # YAML frontmatter
        assert "apm:" in target_content
        assert "version: 1.0.0" in target_content
        assert "commit: abc123" in target_content
        assert "Some agent content" in target_content
    
    def test_get_target_filename_agent_format(self):
        """Test target filename generation with -apm suffix for .agent.md."""
        source = Path("/package/security.agent.md")
        package_name = "danielmeppiel/security-standards"
        
        target = self.integrator.get_target_filename(source, package_name)
        # Intent-first naming: -apm suffix before extension
        assert target == "security-apm.agent.md"
    
    def test_get_target_filename_chatmode_format(self):
        """Test target filename generation with -apm suffix for .chatmode.md."""
        source = Path("/package/default.chatmode.md")
        package_name = "danielmeppiel/design-guidelines"
        
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
    
    def test_integrate_package_agents_skips_unchanged_files(self):
        """Test that integration skips files with same version and commit."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "security.agent.md").write_text("# Security Agent")
        
        github_agents = self.project_root / ".github" / "agents"
        github_agents.mkdir(parents=True)
        
        # Pre-create the target file with matching frontmatter
        existing_content = """---
apm:
  source: test-pkg
  source_repo: github.com/test/repo
  version: 1.0.0
  commit: abc123
  original_path: security.agent.md
  installed_at: '2024-01-01T00:00:00'
  content_hash: da39a3ee5e6b4b0d3255bfef95601890afd80709
---

# Existing"""
        (github_agents / "security-apm.agent.md").write_text(existing_content)
        
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
        
        assert result.files_integrated == 0
        assert result.files_updated == 0
        assert result.files_skipped == 1
    
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
        gitignore.write_text(".github/agents/*-apm.agent.md\n.github/agents/*-apm.chatmode.md\n")
        
        updated = self.integrator.update_gitignore_for_integrated_agents(self.project_root)
        
        assert updated == False
    
    # ========== Header-based Versioning Tests ==========
    
    def test_parse_header_metadata_valid(self):
        """Test parsing metadata from valid YAML frontmatter."""
        header_content = """---
apm:
  source: security-standards
  source_repo: danielmeppiel/security-standards
  version: 1.0.0
  commit: abc123def456
  original_path: security.agent.md
  installed_at: '2024-11-13T10:30:00Z'
---

# Agent content here"""
        
        test_file = self.project_root / "test.agent.md"
        test_file.write_text(header_content)
        
        metadata = self.integrator._parse_header_metadata(test_file)
        
        assert metadata['Source'] == 'security-standards (danielmeppiel/security-standards)'
        assert metadata['Version'] == '1.0.0'
        assert metadata['Commit'] == 'abc123def456'
        assert metadata['Original'] == 'security.agent.md'
        assert metadata['Installed'] == '2024-11-13T10:30:00Z'
    
    def test_parse_header_metadata_no_header(self):
        """Test parsing file without header returns empty dict."""
        test_file = self.project_root / "test.agent.md"
        test_file.write_text("# Just content, no header")
        
        metadata = self.integrator._parse_header_metadata(test_file)
        
        assert metadata == {}
    
    def test_parse_header_metadata_malformed(self):
        """Test parsing malformed header returns empty dict."""
        test_file = self.project_root / "test.agent.md"
        test_file.write_text("<!-- Incomplete header\nNo closing tag")
        
        metadata = self.integrator._parse_header_metadata(test_file)
        
        assert metadata == {}
    
    def test_should_update_agent_new_version(self):
        """Test that agent should be updated when version changes."""
        existing_header = {
            'Version': '1.0.0',
            'Commit': 'abc123'
        }
        
        package = APMPackage(
            name="test-pkg",
            version="2.0.0",  # Version changed
            package_path=Path("/fake/path")
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=Path("/fake/install"),
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
        
        should_update, was_modified = self.integrator._should_update_agent(existing_header, package_info)
        
        assert should_update == True
        assert was_modified == False
    
    def test_should_update_agent_new_commit(self):
        """Test that agent should be updated when commit changes."""
        existing_header = {
            'Version': '1.0.0',
            'Commit': 'abc123'
        }
        
        package = APMPackage(
            name="test-pkg",
            version="1.0.0",
            package_path=Path("/fake/path")
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="def456",  # Commit changed
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=Path("/fake/install"),
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
        
        should_update, was_modified = self.integrator._should_update_agent(existing_header, package_info)
        
        assert should_update == True
        assert was_modified == False
    
    def test_should_update_agent_no_change(self):
        """Test that agent should not be updated when version and commit match."""
        existing_header = {
            'Version': '1.0.0',
            'Commit': 'abc123'
        }
        
        package = APMPackage(
            name="test-pkg",
            version="1.0.0",  # Same version
            package_path=Path("/fake/path")
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",  # Same commit
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=Path("/fake/install"),
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
        
        should_update, was_modified = self.integrator._should_update_agent(existing_header, package_info)
        
        assert should_update == False
        assert was_modified == False
    
    def test_should_update_agent_no_header(self):
        """Test that agent should be updated when no valid header exists."""
        existing_header = {}
        
        package = APMPackage(
            name="test-pkg",
            version="1.0.0",
            package_path=Path("/fake/path")
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=Path("/fake/install"),
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
        
        should_update, was_modified = self.integrator._should_update_agent(existing_header, package_info)
        
        assert should_update == True
        assert was_modified == False
    
    def test_integrate_first_time_creates_with_header(self):
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
        
        # Verify frontmatter was added
        target_file = github_agents / "security-apm.agent.md"
        content = target_file.read_text()
        assert content.startswith('---')  # YAML frontmatter
        assert 'apm:' in content
        assert 'version: 1.0.0' in content
        assert 'commit: abc123' in content
        assert '# Security Agent Content' in content
    
    def test_integrate_with_new_version_updates_file(self):
        """Test that integration with new version updates existing file."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "security.agent.md").write_text("# Updated Agent Content")
        
        github_agents = self.project_root / ".github" / "agents"
        github_agents.mkdir(parents=True)
        
        # Pre-create file with old version in frontmatter
        old_content = """---
apm:
  source: test-pkg
  source_repo: github.com/test/repo
  version: 1.0.0
  commit: abc123
  original_path: security.agent.md
  installed_at: '2024-11-13T10:00:00'
  content_hash: da39a3ee5e6b4b0d3255bfef95601890afd80709
---

# Old Content"""
        (github_agents / "security-apm.agent.md").write_text(old_content)
        
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
        
        assert result.files_integrated == 0
        assert result.files_updated == 1
        assert result.files_skipped == 0
        
        # Verify content was updated with new frontmatter
        target_file = github_agents / "security-apm.agent.md"
        content = target_file.read_text()
        assert 'version: 2.0.0' in content
        assert '# Updated Agent Content' in content
        assert '# Old Content' not in content
    
    def test_integrate_mixed_operations(self):
        """Test integration with mix of new, updated, and skipped files."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        # Create 3 agent files in package
        (package_dir / "new.agent.md").write_text("# New Agent")
        (package_dir / "update.agent.md").write_text("# Updated Agent")
        (package_dir / "skip.agent.md").write_text("# Unchanged Agent")
        
        github_agents = self.project_root / ".github" / "agents"
        github_agents.mkdir(parents=True)
        
        # Pre-create file to be updated (old version) in YAML frontmatter format
        update_old = """---
apm:
  source: test-pkg
  source_repo: github.com/test/repo
  version: 1.0.0
  commit: abc123
  original_path: update.agent.md
  installed_at: '2024-11-13T10:00:00'
  content_hash: abc123
---

# Old Content"""
        (github_agents / "update-apm.agent.md").write_text(update_old)
        
        # Pre-create file to be skipped (same version) - need to calculate correct hash
        import hashlib
        skip_content = "# Unchanged Agent"
        skip_hash = hashlib.sha256(skip_content.encode()).hexdigest()
        skip_same = f"""---
apm:
  source: test-pkg
  source_repo: github.com/test/repo
  version: 2.0.0
  commit: def456
  original_path: skip.agent.md
  installed_at: '2024-11-13T10:00:00'
  content_hash: {skip_hash}
---

{skip_content}"""
        (github_agents / "skip-apm.agent.md").write_text(skip_same)
        
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
        
        assert result.files_integrated == 1  # new.agent.md
        assert result.files_updated == 1      # update.agent.md (version/commit match but content hash differs)
        assert result.files_skipped == 1      # skip.agent.md
        
        # Verify new file exists
        assert (github_agents / "new-apm.agent.md").exists()
        
        # Verify updated file has new version (YAML format)
        update_content = (github_agents / "update-apm.agent.md").read_text()
        assert 'version: 2.0.0' in update_content
        
        # Verify skipped file is unchanged
        skip_content = (github_agents / "skip-apm.agent.md").read_text()
        assert skip_content == skip_same
    
    # ========== Sync Integration Tests (Cleanup) ==========
    
    def test_sync_integration_removes_orphaned_agents(self):
        """Test that sync removes agents from uninstalled packages."""
        github_agents = self.project_root / ".github" / "agents"
        github_agents.mkdir(parents=True)
        
        # Create integrated agents from two packages in YAML frontmatter format
        agent1 = """---
apm:
  source: security-standards
  source_repo: danielmeppiel/security-standards
  version: 1.0.0
  commit: abc123
  original_path: security.agent.md
  installed_at: '2024-11-13T10:00:00'
---

# Security Agent"""
        (github_agents / "security-apm.agent.md").write_text(agent1)
        
        agent2 = """---
apm:
  source: compliance-rules
  source_repo: danielmeppiel/compliance-rules
  version: 1.0.0
  commit: def456
  original_path: compliance.agent.md
  installed_at: '2024-11-13T10:00:00'
---

# Compliance Agent"""
        (github_agents / "compliance-apm.agent.md").write_text(agent2)
        
        # Create APM package with only one dependency (security-standards uninstalled)
        from apm_cli.models.apm_package import DependencyReference
        
        apm_package = Mock()
        apm_package.get_apm_dependencies.return_value = [
            DependencyReference(
                repo_url="danielmeppiel/compliance-rules",
                reference="main"
            )
        ]
        
        # Run sync
        result = self.integrator.sync_integration(apm_package, self.project_root)
        
        # Verify orphaned agent removed, existing agent preserved
        assert result['files_removed'] == 1
        assert not (github_agents / "security-apm.agent.md").exists()
        assert (github_agents / "compliance-apm.agent.md").exists()
    
    def test_sync_integration_removes_orphaned_chatmodes(self):
        """Test that sync removes legacy chatmode files from uninstalled packages."""
        github_agents = self.project_root / ".github" / "agents"
        github_agents.mkdir(parents=True)
        
        # Create integrated legacy chatmode in YAML frontmatter format
        chatmode1 = """---
apm:
  source: old-package
  source_repo: danielmeppiel/old-package
  version: 1.0.0
  commit: abc123
  original_path: default.chatmode.md
  installed_at: '2024-11-13T10:00:00'
---

# Default Chatmode"""
        (github_agents / "default-apm.chatmode.md").write_text(chatmode1)
        
        # Create APM package with no dependencies
        apm_package = Mock()
        apm_package.get_apm_dependencies.return_value = []
        
        # Run sync
        result = self.integrator.sync_integration(apm_package, self.project_root)
        
        # Verify orphaned chatmode removed
        assert result['files_removed'] == 1
        assert not (github_agents / "default-apm.chatmode.md").exists()
    
    def test_sync_integration_preserves_installed_agents(self):
        """Test that sync doesn't remove agents from installed packages."""
        github_agents = self.project_root / ".github" / "agents"
        github_agents.mkdir(parents=True)
        
        # Create integrated agent in YAML frontmatter format
        agent1 = """---
apm:
  source: security-standards
  source_repo: danielmeppiel/security-standards
  version: 1.0.0
  commit: abc123
  original_path: security.agent.md
  installed_at: '2024-11-13T10:00:00'
---

# Security Agent"""
        (github_agents / "security-apm.agent.md").write_text(agent1)
        
        # Create APM package with the dependency still installed
        from apm_cli.models.apm_package import DependencyReference
        
        apm_package = Mock()
        apm_package.get_apm_dependencies.return_value = [
            DependencyReference(
                repo_url="danielmeppiel/security-standards",
                reference="main"
            )
        ]
        
        # Run sync
        self.integrator.sync_integration(apm_package, self.project_root)
        
        # Verify agent still exists
        assert (github_agents / "security-apm.agent.md").exists()
    
    def test_sync_integration_handles_missing_agents_dir(self):
        """Test that sync gracefully handles missing .github/agents/ directory."""
        from apm_cli.models.apm_package import DependencyReference
        
        apm_package = Mock()
        apm_package.get_apm_dependencies.return_value = [
            DependencyReference(
                repo_url="danielmeppiel/test",
                reference="main"
            )
        ]
        
        # Should not raise exception
        self.integrator.sync_integration(apm_package, self.project_root)
    
    def test_sync_integration_handles_files_without_metadata(self):
        """Test that sync preserves files without valid metadata headers (user's custom files)."""
        github_agents = self.project_root / ".github" / "agents"
        github_agents.mkdir(parents=True)
        
        # Create file without proper header - could be user's custom agent
        (github_agents / "custom-apm.agent.md").write_text("# Custom agent without header")
        
        from apm_cli.models.apm_package import DependencyReference
        
        apm_package = Mock()
        apm_package.get_apm_dependencies.return_value = []
        
        # Should not raise exception
        self.integrator.sync_integration(apm_package, self.project_root)
        
        # File without header should be preserved (not removed) - it's a user's file
        assert (github_agents / "custom-apm.agent.md").exists()

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
