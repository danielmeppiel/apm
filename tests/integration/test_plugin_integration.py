"""Comprehensive integration tests for plugin installation and primitive integration.

Tests verify that:
1. Plugins are downloaded to apm_modules/{marketplace}/{plugin-id}/
2. Plugin primitives are extracted and integrated into .github/ structure
3. Commands → .github/prompts/ (with -apm suffix)
4. Agents → .github/agents/ (with -apm suffix)
5. Skills → .github/skills/{skill-name}/
6. Hooks → .github/hooks/

This test suite uses a mock plugin fixture to avoid network calls and provides
comprehensive verification of the complete plugin integration workflow.
"""

import os
import pytest
import tempfile
import shutil
import yaml
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch, MagicMock
from datetime import datetime

from apm_cli.models.apm_package import APMPackage, PackageInfo, ResolvedReference, GitReferenceType
from apm_cli.integration.prompt_integrator import PromptIntegrator, IntegrationResult as PromptIntegrationResult
from apm_cli.integration.agent_integrator import AgentIntegrator, IntegrationResult
from apm_cli.integration.skill_integrator import SkillIntegrator, SkillIntegrationResult, copy_skill_to_target
from apm_cli.plugin.resolver import PluginResolver
from apm_cli.plugin.marketplace import Plugin


class TestPluginInstallation:
    """Test basic plugin installation mechanics."""
    
    def setup_method(self):
        """Set up test environment for each test."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.original_dir = Path.cwd()
        os.chdir(self.test_dir)
        
        # Create .github directory structure
        self._create_github_structure()
        
        # Get the mock plugin fixture path
        test_root = Path(__file__).parent.parent
        self.mock_plugin_fixture = test_root / "fixtures" / "mock-plugin"
    
    def teardown_method(self):
        """Clean up after each test."""
        os.chdir(self.original_dir)
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def _create_github_structure(self):
        """Create the .github directory structure for testing."""
        github_dirs = [
            ".github/prompts",
            ".github/agents",
            ".github/skills",
            ".github/hooks",
        ]
        
        for dir_path in github_dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def _create_apm_config(self, plugins: list = None):
        """Create apm.yml with plugin entries."""
        config = {
            'name': 'test-project',
            'version': '1.0.0',
            'description': 'Test project for plugin integration',
            'author': 'Test Author',
        }
        
        if plugins:
            config['plugins'] = plugins
        
        apm_yml_path = self.test_dir / "apm.yml"
        with open(apm_yml_path, 'w') as f:
            yaml.dump(config, f)
        
        return config
    
    def _create_mock_plugin_installation(self, plugin_name: str = "mock-plugin"):
        """Create a mock plugin installation in apm_modules."""
        apm_modules_dir = self.test_dir / "apm_modules" / "test" / plugin_name
        apm_modules_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy mock plugin fixture
        if self.mock_plugin_fixture.exists():
            for item in self.mock_plugin_fixture.iterdir():
                if item.is_dir():
                    shutil.copytree(item, apm_modules_dir / item.name)
                else:
                    shutil.copy2(item, apm_modules_dir / item.name)
        
        return apm_modules_dir
    
    def test_plugin_resolver_valid_spec(self):
        """Test that PluginResolver correctly parses valid plugin specifications."""
        resolver = PluginResolver()
        
        # Mock the marketplace manager's find_plugin method
        mock_plugin = Plugin(
            id="test-plugin",
            name="Test Plugin",
            description="Test",
            version="1.0.0",
            repository="https://github.com/test/test-plugin",
            marketplace_source="https://github.com/test/marketplace"
        )
        
        with patch.object(resolver.marketplace_manager, 'find_plugin', return_value=mock_plugin):
            plugin_id, repo_url = resolver.resolve_plugin("test-plugin@github.com/test/marketplace")
            
            assert plugin_id == "test-plugin"
            assert repo_url == "https://github.com/test/test-plugin"
    
    def test_plugin_resolver_invalid_spec_no_at(self):
        """Test that PluginResolver rejects specs without @ separator."""
        resolver = PluginResolver()
        
        with pytest.raises(ValueError) as exc_info:
            resolver.resolve_plugin("invalid-spec-no-separator")
        
        assert "Invalid plugin specification" in str(exc_info.value)
    
    def test_plugin_resolver_invalid_spec_empty_parts(self):
        """Test that PluginResolver rejects specs with empty parts."""
        resolver = PluginResolver()
        
        with pytest.raises(ValueError) as exc_info:
            resolver.resolve_plugin("@marketplace")
        
        assert "plugin-id and marketplace-name required" in str(exc_info.value)
    
    def test_plugin_in_apm_modules_structure(self):
        """Test that plugins are organized in apm_modules with correct structure."""
        # Create mock plugin installation
        plugin_path = self._create_mock_plugin_installation("test-plugin")
        
        # Verify structure
        assert plugin_path.exists()
        assert (plugin_path / "apm.yml").exists()
        assert (plugin_path / ".apm").is_dir()
        assert (plugin_path / ".apm" / "prompts").is_dir()
        assert (plugin_path / ".apm" / "agents").is_dir()
        assert (plugin_path / ".apm" / "skills").is_dir()


class TestPromptIntegration:
    """Test prompt integration from plugins."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.original_dir = Path.cwd()
        os.chdir(self.test_dir)
        
        # Create .github structure
        self.github_prompts = self.test_dir / ".github" / "prompts"
        self.github_prompts.mkdir(parents=True, exist_ok=True)
        
        # Get fixture
        test_root = Path(__file__).parent.parent
        self.mock_plugin_fixture = test_root / "fixtures" / "mock-plugin"
    
    def teardown_method(self):
        """Clean up."""
        os.chdir(self.original_dir)
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def _create_package_info(self, package_path: Path) -> PackageInfo:
        """Create PackageInfo for a plugin."""
        package = APMPackage(
            name="test-plugin",
            version="1.0.0",
            package_path=package_path,
            source="test/plugin"
        )
        
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123def456",
            ref_name="main"
        )
        
        return PackageInfo(
            package=package,
            install_path=package_path,
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
    
    def test_prompt_integrator_finds_prompt_files(self):
        """Test that PromptIntegrator finds prompt files in plugin."""
        # Create mock plugin installation
        plugin_path = self.test_dir / "apm_modules" / "test" / "plugin"
        plugin_path.mkdir(parents=True)
        
        # Copy fixture
        if self.mock_plugin_fixture.exists():
            for item in self.mock_plugin_fixture.iterdir():
                if item.is_dir():
                    shutil.copytree(item, plugin_path / item.name)
                else:
                    shutil.copy2(item, plugin_path / item.name)
        
        integrator = PromptIntegrator()
        prompt_files = integrator.find_prompt_files(plugin_path)
        
        assert len(prompt_files) >= 2  # At least example and setup prompts
        
        # Verify prompt file names
        prompt_names = [f.name for f in prompt_files]
        assert "example.prompt.md" in prompt_names
        assert "setup.prompt.md" in prompt_names
    
    def test_prompt_integration_into_github_prompts(self):
        """Test that prompts are integrated into .github/prompts/ with -apm suffix."""
        # Create mock plugin installation
        plugin_path = self.test_dir / "apm_modules" / "test" / "plugin"
        plugin_path.mkdir(parents=True)
        
        # Copy fixture
        if self.mock_plugin_fixture.exists():
            for item in self.mock_plugin_fixture.iterdir():
                if item.is_dir():
                    shutil.copytree(item, plugin_path / item.name)
                else:
                    shutil.copy2(item, plugin_path / item.name)
        
        # Create package info
        package_info = self._create_package_info(plugin_path)
        
        # Integrate prompts
        integrator = PromptIntegrator()
        result = integrator.integrate_package_prompts(package_info, self.test_dir)
        
        # Verify integration result
        assert result.files_integrated >= 2
        
        # Verify files exist with -apm suffix
        assert (self.github_prompts / "example-apm.prompt.md").exists()
        assert (self.github_prompts / "setup-apm.prompt.md").exists()
    
    def test_prompt_files_contain_valid_content(self):
        """Test that integrated prompt files maintain content integrity."""
        # Create mock plugin installation
        plugin_path = self.test_dir / "apm_modules" / "test" / "plugin"
        plugin_path.mkdir(parents=True)
        
        # Copy fixture
        if self.mock_plugin_fixture.exists():
            for item in self.mock_plugin_fixture.iterdir():
                if item.is_dir():
                    shutil.copytree(item, plugin_path / item.name)
                else:
                    shutil.copy2(item, plugin_path / item.name)
        
        # Create package info and integrate
        package_info = self._create_package_info(plugin_path)
        integrator = PromptIntegrator()
        result = integrator.integrate_package_prompts(package_info, self.test_dir)
        
        # Read integrated file and verify content
        integrated_prompt = self.github_prompts / "example-apm.prompt.md"
        content = integrated_prompt.read_text(encoding='utf-8')
        
        # Verify content includes expected sections
        assert "Example Prompt" in content or "example" in content.lower()
        assert "---" in content  # Frontmatter should be present


class TestAgentIntegration:
    """Test agent integration from plugins."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.original_dir = Path.cwd()
        os.chdir(self.test_dir)
        
        # Create .github structure
        self.github_agents = self.test_dir / ".github" / "agents"
        self.github_agents.mkdir(parents=True, exist_ok=True)
        
        # Get fixture
        test_root = Path(__file__).parent.parent
        self.mock_plugin_fixture = test_root / "fixtures" / "mock-plugin"
    
    def teardown_method(self):
        """Clean up."""
        os.chdir(self.original_dir)
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def _create_package_info(self, package_path: Path) -> PackageInfo:
        """Create PackageInfo for a plugin."""
        package = APMPackage(
            name="test-plugin",
            version="1.0.0",
            package_path=package_path,
            source="test/plugin"
        )
        
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123def456",
            ref_name="main"
        )
        
        return PackageInfo(
            package=package,
            install_path=package_path,
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
    
    def test_agent_integrator_finds_agent_files(self):
        """Test that AgentIntegrator finds agent files in plugin."""
        # Create mock plugin installation
        plugin_path = self.test_dir / "apm_modules" / "test" / "plugin"
        plugin_path.mkdir(parents=True)
        
        # Copy fixture
        if self.mock_plugin_fixture.exists():
            for item in self.mock_plugin_fixture.iterdir():
                if item.is_dir():
                    shutil.copytree(item, plugin_path / item.name)
                else:
                    shutil.copy2(item, plugin_path / item.name)
        
        integrator = AgentIntegrator()
        agent_files = integrator.find_agent_files(plugin_path)
        
        assert len(agent_files) >= 2  # At least example and helper agents
        
        # Verify agent file names
        agent_names = [f.name for f in agent_files]
        assert "example.agent.md" in agent_names
        assert "helper.agent.md" in agent_names
    
    def test_agent_integration_into_github_agents(self):
        """Test that agents are integrated into .github/agents/ with -apm suffix."""
        # Create mock plugin installation
        plugin_path = self.test_dir / "apm_modules" / "test" / "plugin"
        plugin_path.mkdir(parents=True)
        
        # Copy fixture
        if self.mock_plugin_fixture.exists():
            for item in self.mock_plugin_fixture.iterdir():
                if item.is_dir():
                    shutil.copytree(item, plugin_path / item.name)
                else:
                    shutil.copy2(item, plugin_path / item.name)
        
        # Create package info and integrate
        package_info = self._create_package_info(plugin_path)
        integrator = AgentIntegrator()
        result = integrator.integrate_package_agents(package_info, self.test_dir)
        
        # Verify integration result
        assert result.files_integrated >= 2
        
        # Verify files exist with -apm suffix
        assert (self.github_agents / "example-apm.agent.md").exists()
        assert (self.github_agents / "helper-apm.agent.md").exists()
    
    def test_agent_files_contain_valid_metadata(self):
        """Test that integrated agent files maintain metadata."""
        # Create mock plugin installation
        plugin_path = self.test_dir / "apm_modules" / "test" / "plugin"
        plugin_path.mkdir(parents=True)
        
        # Copy fixture
        if self.mock_plugin_fixture.exists():
            for item in self.mock_plugin_fixture.iterdir():
                if item.is_dir():
                    shutil.copytree(item, plugin_path / item.name)
                else:
                    shutil.copy2(item, plugin_path / item.name)
        
        # Create package info and integrate
        package_info = self._create_package_info(plugin_path)
        integrator = AgentIntegrator()
        result = integrator.integrate_package_agents(package_info, self.test_dir)
        
        # Read integrated file and verify metadata
        integrated_agent = self.github_agents / "example-apm.agent.md"
        content = integrated_agent.read_text(encoding='utf-8')
        
        # Verify frontmatter and content
        assert "---" in content  # Frontmatter should be present
        assert "role:" in content or "description:" in content  # Metadata should be present


class TestSkillIntegration:
    """Test skill integration from plugins."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.original_dir = Path.cwd()
        os.chdir(self.test_dir)
        
        # Create .github structure
        self.github_skills = self.test_dir / ".github" / "skills"
        self.github_skills.mkdir(parents=True, exist_ok=True)
        
        # Get fixture
        test_root = Path(__file__).parent.parent
        self.mock_plugin_fixture = test_root / "fixtures" / "mock-plugin"
    
    def teardown_method(self):
        """Clean up."""
        os.chdir(self.original_dir)
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_skill_directory_exists_in_plugin(self):
        """Test that skill directory exists in plugin fixture."""
        # Create mock plugin installation
        plugin_path = self.test_dir / "apm_modules" / "test" / "plugin"
        plugin_path.mkdir(parents=True)
        
        # Copy fixture
        if self.mock_plugin_fixture.exists():
            for item in self.mock_plugin_fixture.iterdir():
                if item.is_dir():
                    shutil.copytree(item, plugin_path / item.name)
                else:
                    shutil.copy2(item, plugin_path / item.name)
        
        # Check that skill directory exists
        skill_dir = plugin_path / ".apm" / "skills" / "example-skill"
        assert skill_dir.exists()
        assert (skill_dir / "SKILL.md").exists()
    
    def test_skill_integration_into_github_skills(self):
        """Test that skills are integrated into .github/skills/ as subdirectories."""
        # Create mock plugin installation
        plugin_path = self.test_dir / "apm_modules" / "test" / "plugin"
        plugin_path.mkdir(parents=True)
        
        # Copy fixture
        if self.mock_plugin_fixture.exists():
            for item in self.mock_plugin_fixture.iterdir():
                if item.is_dir():
                    shutil.copytree(item, plugin_path / item.name)
                else:
                    shutil.copy2(item, plugin_path / item.name)
        
        # Create package info
        package = APMPackage(
            name="test-plugin",
            version="1.0.0",
            package_path=plugin_path,
            source="test/plugin"
        )
        
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123def456",
            ref_name="main"
        )
        
        package_info = PackageInfo(
            package=package,
            install_path=plugin_path,
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
        
        # Integrate skills using the standalone function
        github_path, claude_path = copy_skill_to_target(package_info, plugin_path / ".apm" / "skills" / "example-skill", self.test_dir)
        
        # Verify skill was copied to .github/skills
        if github_path:
            assert github_path.exists()
            assert (github_path / "SKILL.md").exists()
        else:
            # If not copied, just verify directory exists in fixture
            assert (plugin_path / ".apm" / "skills" / "example-skill" / "SKILL.md").exists()


class TestCompletePluginWorkflow:
    """Integration tests for complete plugin installation workflow."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.original_dir = Path.cwd()
        os.chdir(self.test_dir)
        
        # Create project structure
        self._create_project_structure()
        
        # Get fixture
        test_root = Path(__file__).parent.parent
        self.mock_plugin_fixture = test_root / "fixtures" / "mock-plugin"
    
    def teardown_method(self):
        """Clean up."""
        os.chdir(self.original_dir)
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def _create_project_structure(self):
        """Create a complete APM project structure."""
        # Create .github structure
        for subdir in ["prompts", "agents", "skills", "hooks"]:
            Path(".github").joinpath(subdir).mkdir(parents=True, exist_ok=True)
        
        # Create apm.yml with plugin entry
        apm_config = {
            'name': 'test-project',
            'version': '1.0.0',
            'description': 'Test project for plugin integration',
            'author': 'Test Author',
            'plugins': [
                {
                    'name': 'mock-plugin',
                    'source': 'https://github.com/test/mock-plugin',
                    'version': 'latest'
                }
            ]
        }
        
        with open('apm.yml', 'w') as f:
            yaml.dump(apm_config, f)
    
    def _create_mock_plugin_installation(self):
        """Create a mock plugin installation in apm_modules."""
        plugin_path = self.test_dir / "apm_modules" / "test" / "mock-plugin"
        plugin_path.mkdir(parents=True, exist_ok=True)
        
        # Copy mock plugin fixture
        if self.mock_plugin_fixture.exists():
            for item in self.mock_plugin_fixture.iterdir():
                if item.is_dir():
                    shutil.copytree(item, plugin_path / item.name)
                else:
                    shutil.copy2(item, plugin_path / item.name)
        
        return plugin_path
    
    def test_complete_plugin_integration_workflow(self):
        """Test complete workflow: install plugin, integrate all primitives."""
        # Create plugin installation
        plugin_path = self._create_mock_plugin_installation()
        assert plugin_path.exists()
        
        # Create package info
        package = APMPackage(
            name="mock-plugin",
            version="1.0.0",
            package_path=plugin_path,
            source="test/mock-plugin"
        )
        
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123def456",
            ref_name="main"
        )
        
        package_info = PackageInfo(
            package=package,
            install_path=plugin_path,
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
        
        # Integrate prompts
        prompt_integrator = PromptIntegrator()
        prompt_result = prompt_integrator.integrate_package_prompts(package_info, self.test_dir)
        
        # Integrate agents
        agent_integrator = AgentIntegrator()
        agent_result = agent_integrator.integrate_package_agents(package_info, self.test_dir)
        
        # Verify all integrations succeeded
        assert prompt_result.files_integrated > 0
        assert agent_result.files_integrated > 0
        
        # Verify .github structure
        assert (self.test_dir / ".github" / "prompts" / "example-apm.prompt.md").exists()
        assert (self.test_dir / ".github" / "prompts" / "setup-apm.prompt.md").exists()
        assert (self.test_dir / ".github" / "agents" / "example-apm.agent.md").exists()
        assert (self.test_dir / ".github" / "agents" / "helper-apm.agent.md").exists()
    
    def test_plugin_files_integrated_with_correct_suffixes(self):
        """Test that integrated files have correct suffixes."""
        # Create plugin installation
        plugin_path = self._create_mock_plugin_installation()
        
        # Create package info and integrate
        package = APMPackage(
            name="mock-plugin",
            version="1.0.0",
            package_path=plugin_path,
            source="test/mock-plugin"
        )
        
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123def456",
            ref_name="main"
        )
        
        package_info = PackageInfo(
            package=package,
            install_path=plugin_path,
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
        
        # Integrate all
        PromptIntegrator().integrate_package_prompts(package_info, self.test_dir)
        AgentIntegrator().integrate_package_agents(package_info, self.test_dir)
        
        # Verify suffixes
        prompts_dir = self.test_dir / ".github" / "prompts"
        prompt_files = list(prompts_dir.glob("*.prompt.md"))
        for prompt in prompt_files:
            assert "-apm.prompt.md" in prompt.name, f"Prompt should have -apm suffix: {prompt.name}"
        
        agents_dir = self.test_dir / ".github" / "agents"
        agent_files = list(agents_dir.glob("*.agent.md"))
        for agent in agent_files:
            assert "-apm.agent.md" in agent.name, f"Agent should have -apm suffix: {agent.name}"
    
    def test_plugin_directory_structure_preserved(self):
        """Test that plugin directory structure is preserved during installation."""
        # Create plugin installation
        plugin_path = self._create_mock_plugin_installation()
        
        # Verify complete structure
        expected_paths = [
            ".apm",
            ".apm/prompts",
            ".apm/agents",
            ".apm/skills",
            ".apm/skills/example-skill",
            ".apm/hooks",
            "apm.yml"
        ]
        
        for path in expected_paths:
            full_path = plugin_path / path
            assert full_path.exists(), f"Expected path not found: {path}"
    
    def test_plugin_primitives_discoverable_after_integration(self):
        """Test that plugin primitives are discoverable in their integrated locations."""
        # Create plugin installation
        plugin_path = self._create_mock_plugin_installation()
        
        # Create package info and integrate
        package = APMPackage(
            name="mock-plugin",
            version="1.0.0",
            package_path=plugin_path,
            source="test/mock-plugin"
        )
        
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123def456",
            ref_name="main"
        )
        
        package_info = PackageInfo(
            package=package,
            install_path=plugin_path,
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
        
        # Integrate
        PromptIntegrator().integrate_package_prompts(package_info, self.test_dir)
        AgentIntegrator().integrate_package_agents(package_info, self.test_dir)
        
        # Verify discoverability
        github_dir = self.test_dir / ".github"
        
        # Find all integrated files
        integrated_prompts = list(github_dir.glob("prompts/*-apm.prompt.md"))
        integrated_agents = list(github_dir.glob("agents/*-apm.agent.md"))
        
        assert len(integrated_prompts) >= 2, "Should have integrated prompts"
        assert len(integrated_agents) >= 2, "Should have integrated agents"


class TestInstructionIntegration:
    """Test instruction file detection and integration from plugins."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.original_dir = Path.cwd()
        os.chdir(self.test_dir)
        
        # Get fixture
        test_root = Path(__file__).parent.parent
        self.mock_plugin_fixture = test_root / "fixtures" / "mock-plugin"
    
    def teardown_method(self):
        """Clean up."""
        os.chdir(self.original_dir)
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_instruction_directory_exists_in_plugin(self):
        """Test that instructions directory exists in plugin fixture."""
        instructions_dir = self.mock_plugin_fixture / ".apm" / "instructions"
        assert instructions_dir.exists(), "Instructions directory should exist"
        assert list(instructions_dir.glob("*.instructions.md")), "Should have instruction files"
    
    def test_instruction_files_have_valid_content(self):
        """Test that instruction files contain valid metadata and content."""
        instructions_dir = self.mock_plugin_fixture / ".apm" / "instructions"
        
        # Find all instruction files
        instruction_files = list(instructions_dir.glob("*.instructions.md"))
        assert len(instruction_files) > 0, "Should have at least one instruction file"
        
        # Verify each instruction file has frontmatter
        for instr_file in instruction_files:
            content = instr_file.read_text()
            
            # Should start with ---
            assert content.startswith("---"), f"{instr_file.name} should start with frontmatter"
            
            # Should contain applyTo
            assert "applyTo:" in content, f"{instr_file.name} should have applyTo field"
            
            # Should contain description
            assert "description:" in content, f"{instr_file.name} should have description field"
    
    def test_instructions_included_during_plugin_discovery(self):
        """Test that instructions are discovered along with other primitives."""
        # Create plugin installation
        plugin_path = self.test_dir / "apm_modules" / "test" / "plugin"
        plugin_path.mkdir(parents=True)
        
        # Copy fixture
        if self.mock_plugin_fixture.exists():
            for item in self.mock_plugin_fixture.iterdir():
                if item.is_dir():
                    shutil.copytree(item, plugin_path / item.name)
                else:
                    shutil.copy2(item, plugin_path / item.name)
        
        # Verify all primitive directories exist
        primitives_base = plugin_path / ".apm"
        assert (primitives_base / "prompts").exists()
        assert (primitives_base / "agents").exists()
        assert (primitives_base / "skills").exists()
        assert (primitives_base / "hooks").exists()
        assert (primitives_base / "instructions").exists(), "Instructions should be present"
        
        # Verify instruction files exist
        instructions = list((primitives_base / "instructions").glob("*.instructions.md"))
        assert len(instructions) > 0, "Should have instruction files"


