"""Unit tests for orphan detection in agent and prompt integrators.

These tests validate the fix for orphan detection with virtual packages.
The fix ensures that orphan detection compares full dependency strings
instead of just base repo URLs.
"""

import tempfile
from pathlib import Path

from src.apm_cli.integration.agent_integrator import AgentIntegrator
from src.apm_cli.integration.prompt_integrator import PromptIntegrator
from src.apm_cli.models.apm_package import APMPackage, DependencyReference


def create_test_integrated_file(path: Path, source_repo: str, source_dependency: str = None):
    """Create a test integrated file with APM metadata.
    
    Args:
        path: Path to create the file at
        source_repo: The source_repo value (e.g., "owner/repo")
        source_dependency: The full dependency string (e.g., "owner/repo/collections/name")
                          If None, uses old format without source_dependency field
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    
    if source_dependency:
        # New format with source_dependency
        content = f"""---
apm:
  source: test-package
  source_repo: {source_repo}
  source_dependency: {source_dependency}
  version: 1.0.0
  commit: abc123
  content_hash: deadbeef
---
# Test content
"""
    else:
        # Old format without source_dependency
        content = f"""---
apm:
  source: test-package
  source_repo: {source_repo}
  version: 1.0.0
  commit: abc123
  content_hash: deadbeef
---
# Test content
"""
    
    path.write_text(content)


def create_mock_apm_package(dependencies: list) -> APMPackage:
    """Create a mock APMPackage with the given dependencies."""
    parsed_deps = [DependencyReference.parse(d) for d in dependencies]
    return APMPackage(
        name="test-project",
        version="1.0.0",
        dependencies={'apm': parsed_deps}
    )


class TestAgentIntegratorOrphanDetection:
    """Test orphan detection in AgentIntegrator with virtual packages."""
    
    def test_orphan_detection_regular_package(self):
        """Regular package orphan detection (baseline)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            agents_dir = project_root / ".github" / "agents"
            
            # Create an integrated agent from owner/repo
            create_test_integrated_file(
                agents_dir / "test-apm.agent.md",
                source_repo="owner/repo",
                source_dependency="owner/repo"
            )
            
            # Mock package with owner/repo installed
            apm_package = create_mock_apm_package(["owner/repo"])
            
            integrator = AgentIntegrator()
            result = integrator.sync_integration(apm_package, project_root)
            
            # Should NOT be removed (package is installed)
            assert result['files_removed'] == 0
            assert (agents_dir / "test-apm.agent.md").exists()
    
    def test_orphan_detection_removes_uninstalled_package(self):
        """Uninstalled package should be detected as orphan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            agents_dir = project_root / ".github" / "agents"
            
            # Create an integrated agent from owner/repo
            create_test_integrated_file(
                agents_dir / "test-apm.agent.md",
                source_repo="owner/repo",
                source_dependency="owner/repo"
            )
            
            # Mock package with different package installed
            apm_package = create_mock_apm_package(["other/package"])
            
            integrator = AgentIntegrator()
            result = integrator.sync_integration(apm_package, project_root)
            
            # Should be removed (package not installed)
            assert result['files_removed'] == 1
            assert not (agents_dir / "test-apm.agent.md").exists()
    
    def test_orphan_detection_virtual_package_new_format(self):
        """Virtual package with new format source_dependency should be matched correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            agents_dir = project_root / ".github" / "agents"
            
            # Create agent from virtual collection
            create_test_integrated_file(
                agents_dir / "azure-apm.agent.md",
                source_repo="github/awesome-copilot",
                source_dependency="github/awesome-copilot/collections/azure-cloud-development"
            )
            
            # Mock package with the virtual collection installed
            apm_package = create_mock_apm_package([
                "github/awesome-copilot/collections/azure-cloud-development"
            ])
            
            integrator = AgentIntegrator()
            result = integrator.sync_integration(apm_package, project_root)
            
            # Should NOT be removed (exact virtual package is installed)
            assert result['files_removed'] == 0
            assert (agents_dir / "azure-apm.agent.md").exists()
    
    def test_orphan_detection_virtual_package_removed(self):
        """When a virtual package is removed, its agents should be orphaned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            agents_dir = project_root / ".github" / "agents"
            
            # Create agent from virtual collection
            create_test_integrated_file(
                agents_dir / "azure-apm.agent.md",
                source_repo="github/awesome-copilot",
                source_dependency="github/awesome-copilot/collections/azure-cloud-development"
            )
            
            # Mock package with a DIFFERENT virtual collection installed
            apm_package = create_mock_apm_package([
                "github/awesome-copilot/collections/different-collection"
            ])
            
            integrator = AgentIntegrator()
            result = integrator.sync_integration(apm_package, project_root)
            
            # Should be removed (different virtual package from same repo)
            assert result['files_removed'] == 1
            assert not (agents_dir / "azure-apm.agent.md").exists()
    
    def test_orphan_detection_old_format_fallback(self):
        """Old format without source_dependency falls back to repo URL matching."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            agents_dir = project_root / ".github" / "agents"
            
            # Create agent using old format (no source_dependency)
            create_test_integrated_file(
                agents_dir / "test-apm.agent.md",
                source_repo="owner/repo",
                source_dependency=None  # Old format
            )
            
            # Mock package with owner/repo installed
            apm_package = create_mock_apm_package(["owner/repo"])
            
            integrator = AgentIntegrator()
            result = integrator.sync_integration(apm_package, project_root)
            
            # Should NOT be removed (backwards compatibility)
            assert result['files_removed'] == 0
            assert (agents_dir / "test-apm.agent.md").exists()
    
    def test_orphan_detection_chatmode_files(self):
        """Legacy .chatmode.md files should also be cleaned up."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            agents_dir = project_root / ".github" / "agents"
            
            # Create a chatmode file
            create_test_integrated_file(
                agents_dir / "test-apm.chatmode.md",
                source_repo="owner/repo",
                source_dependency="owner/repo"
            )
            
            # Mock package with nothing installed
            apm_package = create_mock_apm_package([])
            
            integrator = AgentIntegrator()
            result = integrator.sync_integration(apm_package, project_root)
            
            # Should be removed
            assert result['files_removed'] == 1
            assert not (agents_dir / "test-apm.chatmode.md").exists()


class TestPromptIntegratorOrphanDetection:
    """Test orphan detection in PromptIntegrator with virtual packages."""
    
    def test_orphan_detection_regular_package(self):
        """Regular package orphan detection (baseline)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            prompts_dir = project_root / ".github" / "prompts"
            
            # Create an integrated prompt from owner/repo
            create_test_integrated_file(
                prompts_dir / "test-apm.prompt.md",
                source_repo="owner/repo",
                source_dependency="owner/repo"
            )
            
            # Mock package with owner/repo installed
            apm_package = create_mock_apm_package(["owner/repo"])
            
            integrator = PromptIntegrator()
            result = integrator.sync_integration(apm_package, project_root)
            
            # Should NOT be removed (package is installed)
            assert result['files_removed'] == 0
            assert (prompts_dir / "test-apm.prompt.md").exists()
    
    def test_orphan_detection_removes_uninstalled_package(self):
        """Uninstalled package should be detected as orphan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            prompts_dir = project_root / ".github" / "prompts"
            
            # Create an integrated prompt from owner/repo
            create_test_integrated_file(
                prompts_dir / "test-apm.prompt.md",
                source_repo="owner/repo",
                source_dependency="owner/repo"
            )
            
            # Mock package with different package installed
            apm_package = create_mock_apm_package(["other/package"])
            
            integrator = PromptIntegrator()
            result = integrator.sync_integration(apm_package, project_root)
            
            # Should be removed (package not installed)
            assert result['files_removed'] == 1
            assert not (prompts_dir / "test-apm.prompt.md").exists()
    
    def test_orphan_detection_virtual_package_new_format(self):
        """Virtual package with new format source_dependency should be matched correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            prompts_dir = project_root / ".github" / "prompts"
            
            # Create prompt from virtual file
            create_test_integrated_file(
                prompts_dir / "code-review-apm.prompt.md",
                source_repo="github/awesome-copilot",
                source_dependency="github/awesome-copilot/prompts/code-review.prompt.md"
            )
            
            # Mock package with the virtual file installed
            apm_package = create_mock_apm_package([
                "github/awesome-copilot/prompts/code-review.prompt.md"
            ])
            
            integrator = PromptIntegrator()
            result = integrator.sync_integration(apm_package, project_root)
            
            # Should NOT be removed (exact virtual package is installed)
            assert result['files_removed'] == 0
            assert (prompts_dir / "code-review-apm.prompt.md").exists()
    
    def test_orphan_detection_virtual_package_removed(self):
        """When a virtual package is removed, its prompts should be orphaned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            prompts_dir = project_root / ".github" / "prompts"
            
            # Create prompt from virtual file
            create_test_integrated_file(
                prompts_dir / "code-review-apm.prompt.md",
                source_repo="github/awesome-copilot",
                source_dependency="github/awesome-copilot/prompts/code-review.prompt.md"
            )
            
            # Mock package with a DIFFERENT virtual file installed
            apm_package = create_mock_apm_package([
                "github/awesome-copilot/prompts/other-file.prompt.md"
            ])
            
            integrator = PromptIntegrator()
            result = integrator.sync_integration(apm_package, project_root)
            
            # Should be removed (different virtual package from same repo)
            assert result['files_removed'] == 1
            assert not (prompts_dir / "code-review-apm.prompt.md").exists()
    
    def test_orphan_detection_old_format_fallback(self):
        """Old format without source_dependency falls back to repo URL matching."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            prompts_dir = project_root / ".github" / "prompts"
            
            # Create prompt using old format (no source_dependency)
            create_test_integrated_file(
                prompts_dir / "test-apm.prompt.md",
                source_repo="owner/repo",
                source_dependency=None  # Old format
            )
            
            # Mock package with owner/repo installed
            apm_package = create_mock_apm_package(["owner/repo"])
            
            integrator = PromptIntegrator()
            result = integrator.sync_integration(apm_package, project_root)
            
            # Should NOT be removed (backwards compatibility)
            assert result['files_removed'] == 0
            assert (prompts_dir / "test-apm.prompt.md").exists()


class TestMixedScenarios:
    """Test complex scenarios with multiple packages and virtual packages."""
    
    def test_multiple_virtual_packages_from_same_repo(self):
        """Multiple virtual packages from same repo handled correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            agents_dir = project_root / ".github" / "agents"
            
            # Create agents from two different virtual collections
            create_test_integrated_file(
                agents_dir / "azure-apm.agent.md",
                source_repo="github/awesome-copilot",
                source_dependency="github/awesome-copilot/collections/azure"
            )
            create_test_integrated_file(
                agents_dir / "aws-apm.agent.md",
                source_repo="github/awesome-copilot",
                source_dependency="github/awesome-copilot/collections/aws"
            )
            
            # Mock package with only azure collection installed
            apm_package = create_mock_apm_package([
                "github/awesome-copilot/collections/azure"
            ])
            
            integrator = AgentIntegrator()
            result = integrator.sync_integration(apm_package, project_root)
            
            # Only aws should be removed
            assert result['files_removed'] == 1
            assert (agents_dir / "azure-apm.agent.md").exists()
            assert not (agents_dir / "aws-apm.agent.md").exists()
    
    def test_regular_and_virtual_packages_mixed(self):
        """Mix of regular and virtual packages handled correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            prompts_dir = project_root / ".github" / "prompts"
            
            # Create prompt from regular package
            create_test_integrated_file(
                prompts_dir / "regular-apm.prompt.md",
                source_repo="owner/regular-pkg",
                source_dependency="owner/regular-pkg"
            )
            # Create prompt from virtual package
            create_test_integrated_file(
                prompts_dir / "virtual-apm.prompt.md",
                source_repo="github/awesome-copilot",
                source_dependency="github/awesome-copilot/prompts/virtual.prompt.md"
            )
            
            # Mock package with both installed
            apm_package = create_mock_apm_package([
                "owner/regular-pkg",
                "github/awesome-copilot/prompts/virtual.prompt.md"
            ])
            
            integrator = PromptIntegrator()
            result = integrator.sync_integration(apm_package, project_root)
            
            # Neither should be removed
            assert result['files_removed'] == 0
            assert (prompts_dir / "regular-apm.prompt.md").exists()
            assert (prompts_dir / "virtual-apm.prompt.md").exists()
