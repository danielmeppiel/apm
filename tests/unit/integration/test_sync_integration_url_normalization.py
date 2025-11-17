"""Tests for sync_integration URL normalization fix.

This test file specifically covers the critical bug fix where sync_integration
was incorrectly removing ALL integrated files instead of only orphaned ones.

The bug was caused by URL format mismatch:
- Metadata stored: https://github.com/owner/repo (full URL)
- Dependency list: owner/repo (short form)
- Comparison failed, causing all files to be seen as orphans

These tests ensure the URL normalization logic works correctly across:
- GitHub repositories
- Virtual packages
- Multiple packages installed simultaneously
- Different URL formats (with/without .git suffix)
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

from apm_cli.integration import PromptIntegrator, AgentIntegrator
from apm_cli.models.apm_package import DependencyReference


class TestSyncIntegrationURLNormalization:
    """Test sync_integration URL normalization for multiple packages."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.prompt_integrator = PromptIntegrator()
        self.agent_integrator = AgentIntegrator()
    
    def teardown_method(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_sync_removes_only_uninstalled_package_prompts(self):
        """Test that uninstalling one package only removes its prompts, not others."""
        github_prompts = self.project_root / ".github" / "prompts"
        github_prompts.mkdir(parents=True)
        
        # Create integrated prompts from multiple packages with YAML frontmatter
        compliance_prompt = """---
apm:
  source: compliance-rules
  source_repo: https://github.com/danielmeppiel/compliance-rules
  version: 1.0.0
  commit: abc123
  original_path: compliance-audit.prompt.md
  installed_at: '2024-11-13T10:00:00'
  content_hash: hash1
---

# Compliance Audit"""
        
        design_prompt = """---
apm:
  source: design-guidelines
  source_repo: https://github.com/danielmeppiel/design-guidelines
  version: 1.0.0
  commit: def456
  original_path: design-review.prompt.md
  installed_at: '2024-11-13T10:00:00'
  content_hash: hash2
---

# Design Review"""
        
        virtual_prompt = """---
apm:
  source: awesome-copilot-breakdown-plan
  source_repo: https://github.com/github/awesome-copilot
  version: 1.0.0
  commit: unknown
  original_path: .apm/prompts/breakdown-plan.prompt.md
  installed_at: '2024-11-13T10:00:00'
  content_hash: hash3
---

# Breakdown Plan"""
        
        (github_prompts / "compliance-audit-apm.prompt.md").write_text(compliance_prompt)
        (github_prompts / "design-review-apm.prompt.md").write_text(design_prompt)
        (github_prompts / "breakdown-plan-apm.prompt.md").write_text(virtual_prompt)
        
        # Simulate uninstalling design-guidelines (keeping compliance-rules and virtual package)
        apm_package = Mock()
        apm_package.get_apm_dependencies.return_value = [
            DependencyReference(
                repo_url="danielmeppiel/compliance-rules",
                reference="main"
            ),
            DependencyReference(
                repo_url="github/awesome-copilot",
                reference="main"
            )
        ]
        
        # Run sync
        result = self.prompt_integrator.sync_integration(apm_package, self.project_root)
        
        # Verify only design-guidelines prompt was removed
        assert not (github_prompts / "design-review-apm.prompt.md").exists(), "design-guidelines prompt should be removed"
        assert (github_prompts / "compliance-audit-apm.prompt.md").exists(), "compliance-rules prompt should remain"
        assert (github_prompts / "breakdown-plan-apm.prompt.md").exists(), "virtual package prompt should remain"
        assert result['files_removed'] == 1, "Should remove exactly 1 file"
        assert result['errors'] == 0, "Should have no errors"
    
    def test_sync_handles_github_url_formats(self):
        """Test that sync correctly normalizes different GitHub URL formats."""
        github_prompts = self.project_root / ".github" / "prompts"
        github_prompts.mkdir(parents=True)
        
        # Test various URL formats in metadata
        test_cases = [
            ("https://github.com/owner/repo", "owner/repo"),
            ("https://github.com/owner/repo.git", "owner/repo"),
            ("https://gitlab.com/owner/repo", "owner/repo"),
            ("https://git.company.com/owner/repo", "owner/repo"),
        ]
        
        for idx, (source_repo_url, expected_match) in enumerate(test_cases):
            prompt_content = f"""---
apm:
  source: test-package-{idx}
  source_repo: {source_repo_url}
  version: 1.0.0
  commit: abc123
  original_path: test.prompt.md
  installed_at: '2024-11-13T10:00:00'
  content_hash: hash{idx}
---

# Test Prompt {idx}"""
            
            (github_prompts / f"test-{idx}-apm.prompt.md").write_text(prompt_content)
        
        # Simulate package still installed (short form)
        apm_package = Mock()
        apm_package.get_apm_dependencies.return_value = [
            DependencyReference(repo_url="owner/repo", reference="main")
        ]
        
        # Run sync
        result = self.prompt_integrator.sync_integration(apm_package, self.project_root)
        
        # All prompts should remain (they all normalize to owner/repo)
        assert result['files_removed'] == 0, "No files should be removed - all should match"
        for idx in range(len(test_cases)):
            assert (github_prompts / f"test-{idx}-apm.prompt.md").exists(), f"Prompt {idx} should still exist"
    
    def test_sync_removes_only_uninstalled_package_agents(self):
        """Test that uninstalling one package only removes its agents, not others."""
        github_agents = self.project_root / ".github" / "agents"
        github_agents.mkdir(parents=True)
        
        # Create integrated agents from multiple packages with YAML frontmatter
        compliance_agent = """---
apm:
  source: compliance-rules
  source_repo: https://github.com/danielmeppiel/compliance-rules
  version: 1.0.0
  commit: abc123
  original_path: compliance-agent.agent.md
  installed_at: '2024-11-13T10:00:00'
  content_hash: hash1
---

# Compliance Agent"""
        
        design_agent = """---
apm:
  source: design-guidelines
  source_repo: https://github.com/danielmeppiel/design-guidelines
  version: 1.0.0
  commit: def456
  original_path: design-agent.agent.md
  installed_at: '2024-11-13T10:00:00'
  content_hash: hash2
---

# Design Agent"""
        
        (github_agents / "compliance-agent-apm.agent.md").write_text(compliance_agent)
        (github_agents / "design-agent-apm.agent.md").write_text(design_agent)
        
        # Simulate uninstalling design-guidelines (keeping compliance-rules)
        apm_package = Mock()
        apm_package.get_apm_dependencies.return_value = [
            DependencyReference(
                repo_url="danielmeppiel/compliance-rules",
                reference="main"
            )
        ]
        
        # Run sync
        result = self.agent_integrator.sync_integration(apm_package, self.project_root)
        
        # Verify only design-guidelines agent was removed
        assert not (github_agents / "design-agent-apm.agent.md").exists(), "design-guidelines agent should be removed"
        assert (github_agents / "compliance-agent-apm.agent.md").exists(), "compliance-rules agent should remain"
        assert result['files_removed'] == 1, "Should remove exactly 1 file"
        assert result['errors'] == 0, "Should have no errors"
    
    def test_sync_with_three_packages_removes_one(self):
        """Test realistic scenario: 3 packages installed, uninstall 1, verify 2 remain."""
        github_prompts = self.project_root / ".github" / "prompts"
        github_prompts.mkdir(parents=True)
        
        # Create prompts from 3 packages
        packages = [
            ("pkg-a", "https://github.com/owner/pkg-a"),
            ("pkg-b", "https://github.com/owner/pkg-b"),
            ("pkg-c", "https://github.com/owner/pkg-c"),
        ]
        
        for pkg_name, repo_url in packages:
            prompt = f"""---
apm:
  source: {pkg_name}
  source_repo: {repo_url}
  version: 1.0.0
  commit: abc123
  original_path: test.prompt.md
  installed_at: '2024-11-13T10:00:00'
  content_hash: hash
---

# Prompt from {pkg_name}"""
            (github_prompts / f"{pkg_name}-apm.prompt.md").write_text(prompt)
        
        # Uninstall pkg-b (keep pkg-a and pkg-c)
        apm_package = Mock()
        apm_package.get_apm_dependencies.return_value = [
            DependencyReference(repo_url="owner/pkg-a", reference="main"),
            DependencyReference(repo_url="owner/pkg-c", reference="main")
        ]
        
        # Run sync
        result = self.prompt_integrator.sync_integration(apm_package, self.project_root)
        
        # Verify correct removal
        assert (github_prompts / "pkg-a-apm.prompt.md").exists(), "pkg-a should remain"
        assert not (github_prompts / "pkg-b-apm.prompt.md").exists(), "pkg-b should be removed"
        assert (github_prompts / "pkg-c-apm.prompt.md").exists(), "pkg-c should remain"
        assert result['files_removed'] == 1, "Should remove exactly pkg-b"
    
    def test_sync_preserves_files_without_metadata(self):
        """Test that sync doesn't remove user's custom files without APM metadata."""
        github_prompts = self.project_root / ".github" / "prompts"
        github_prompts.mkdir(parents=True)
        
        # Create a user's custom prompt without APM metadata
        custom_prompt = """# Custom User Prompt

This is a custom prompt without APM metadata."""
        (github_prompts / "my-custom-apm.prompt.md").write_text(custom_prompt)
        
        # Create an APM-integrated prompt
        apm_prompt = """---
apm:
  source: test-package
  source_repo: https://github.com/owner/test-package
  version: 1.0.0
  commit: abc123
  original_path: test.prompt.md
  installed_at: '2024-11-13T10:00:00'
  content_hash: hash
---

# APM Prompt"""
        (github_prompts / "test-apm.prompt.md").write_text(apm_prompt)
        
        # Uninstall the package (no packages remain)
        apm_package = Mock()
        apm_package.get_apm_dependencies.return_value = []
        
        # Run sync
        result = self.prompt_integrator.sync_integration(apm_package, self.project_root)
        
        # User's custom file should remain, APM file should be removed
        assert (github_prompts / "my-custom-apm.prompt.md").exists(), "Custom file should remain"
        assert not (github_prompts / "test-apm.prompt.md").exists(), "APM file should be removed"
        assert result['files_removed'] == 1, "Should only remove the APM file"
    
    def test_sync_handles_virtual_packages_correctly(self):
        """Test that virtual packages (single file imports) are handled correctly."""
        github_prompts = self.project_root / ".github" / "prompts"
        github_prompts.mkdir(parents=True)
        
        # Virtual package: github/awesome-copilot/prompts/breakdown-plan.prompt.md
        # The source_repo will be the repo root, not the file path
        virtual_prompt = """---
apm:
  source: awesome-copilot-breakdown-plan
  source_repo: https://github.com/github/awesome-copilot
  version: 1.0.0
  commit: unknown
  original_path: .apm/prompts/breakdown-plan.prompt.md
  installed_at: '2024-11-13T10:00:00'
  content_hash: hash
---

# Breakdown Plan"""
        (github_prompts / "breakdown-plan-apm.prompt.md").write_text(virtual_prompt)
        
        # Regular package
        regular_prompt = """---
apm:
  source: test-package
  source_repo: https://github.com/owner/test-package
  version: 1.0.0
  commit: abc123
  original_path: test.prompt.md
  installed_at: '2024-11-13T10:00:00'
  content_hash: hash
---

# Regular Prompt"""
        (github_prompts / "test-apm.prompt.md").write_text(regular_prompt)
        
        # Keep only the virtual package
        apm_package = Mock()
        apm_package.get_apm_dependencies.return_value = [
            DependencyReference(repo_url="github/awesome-copilot", reference="main")
        ]
        
        # Run sync
        result = self.prompt_integrator.sync_integration(apm_package, self.project_root)
        
        # Virtual package should remain, regular should be removed
        assert (github_prompts / "breakdown-plan-apm.prompt.md").exists(), "Virtual package prompt should remain"
        assert not (github_prompts / "test-apm.prompt.md").exists(), "Regular package prompt should be removed"
        assert result['files_removed'] == 1, "Should remove only the regular package"
