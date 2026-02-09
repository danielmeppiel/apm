"""Integration test for plugin support.

This test verifies the complete plugin workflow:
1. Detection of plugin.json in various locations
2. Synthesis of apm.yml from plugin.json metadata
3. Artifact mapping to .apm/ structure
4. Package validation and error handling
"""

import json
import shutil
from pathlib import Path
import pytest
from src.apm_cli.models.apm_package import validate_apm_package, PackageType


class TestPluginIntegration:
    """Test complete plugin integration."""
    
    def test_plugin_detection_and_synthesis(self, tmp_path):
        """Test that plugin.json is detected and apm.yml is synthesized (root location)."""
        plugin_dir = tmp_path / "test-plugin"
        plugin_dir.mkdir()
        
        # Create plugin.json
        plugin_json = {
            "name": "Test Plugin",
            "version": "1.0.0",
            "description": "A test plugin",
            "author": "Test Author",
            "license": "MIT",
            "tags": ["testing"]
        }
        
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(plugin_json, f)
        
        # Create some plugin artifacts
        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test.md").write_text("# Test Command")
        
        # Run validation
        result = validate_apm_package(plugin_dir)
        
        # Verify detection
        assert result.package_type == PackageType.MARKETPLACE_PLUGIN
        assert result.package is not None
        assert result.package.name == "Test Plugin"
        assert result.package.version == "1.0.0"
        
        # Verify synthesized apm.yml exists
        apm_yml_path = plugin_dir / "apm.yml"
        assert apm_yml_path.exists()
        
        # Verify .apm directory was created
        apm_dir = plugin_dir / ".apm"
        assert apm_dir.exists()
    
    def test_github_copilot_plugin_format(self, tmp_path):
        """Test that .github/plugin/plugin.json format is detected."""
        plugin_dir = tmp_path / "copilot-plugin"
        plugin_dir.mkdir()
        
        # Create .github/plugin/plugin.json (GitHub Copilot format)
        github_plugin_dir = plugin_dir / ".github" / "plugin"
        github_plugin_dir.mkdir(parents=True)
        
        plugin_json = {
            "name": "GitHub Copilot Plugin",
            "version": "2.0.0",
            "description": "A GitHub Copilot plugin"
        }
        
        with open(github_plugin_dir / "plugin.json", "w") as f:
            json.dump(plugin_json, f)
        
        # Create primitives at repository root
        (plugin_dir / "agents").mkdir()
        (plugin_dir / "agents" / "test.agent.md").write_text("# Test Agent")
        
        # Run validation
        result = validate_apm_package(plugin_dir)
        
        # Verify detection
        assert result.package_type == PackageType.MARKETPLACE_PLUGIN
        assert result.package is not None
        assert result.package.name == "GitHub Copilot Plugin"
        assert result.package.version == "2.0.0"
    
    def test_claude_plugin_format(self, tmp_path):
        """Test that .claude-plugin/plugin.json format is detected."""
        plugin_dir = tmp_path / "claude-plugin"
        plugin_dir.mkdir()
        
        # Create .claude-plugin/plugin.json (Claude format)
        claude_plugin_dir = plugin_dir / ".claude-plugin"
        claude_plugin_dir.mkdir(parents=True)
        
        plugin_json = {
            "name": "Claude Plugin",
            "version": "3.0.0",
            "description": "A Claude plugin"
        }
        
        with open(claude_plugin_dir / "plugin.json", "w") as f:
            json.dump(plugin_json, f)
        
        # Create primitives at repository root
        (plugin_dir / "skills").mkdir()
        skill_dir = plugin_dir / "skills" / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test Skill")
        
        # Run validation
        result = validate_apm_package(plugin_dir)
        
        # Verify detection
        assert result.package_type == PackageType.MARKETPLACE_PLUGIN
        assert result.package is not None
        assert result.package.name == "Claude Plugin"
        assert result.package.version == "3.0.0"
    
    def test_plugin_location_priority(self, tmp_path):
        """Test that plugin.json is found at root first, then recursively in subdirectories."""
        # Test 1: Root plugin.json takes priority over subdirectories
        plugin_dir = tmp_path / "priority-test"
        plugin_dir.mkdir()
        
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump({"name": "Root Plugin", "version": "1.0.0", "description": "Root"}, f)
        
        # Create in .claude-plugin/
        (plugin_dir / ".claude-plugin").mkdir()
        with open(plugin_dir / ".claude-plugin" / "plugin.json", "w") as f:
            json.dump({"name": "Claude Plugin", "version": "3.0.0", "description": "Claude"}, f)
        
        # Create in .github/plugin/
        (plugin_dir / ".github" / "plugin").mkdir(parents=True)
        with open(plugin_dir / ".github" / "plugin" / "plugin.json", "w") as f:
            json.dump({"name": "GitHub Plugin", "version": "4.0.0", "description": "GitHub"}, f)
        
        # Root should win
        result = validate_apm_package(plugin_dir)
        assert result.package_type == PackageType.MARKETPLACE_PLUGIN
        assert result.package is not None
        assert result.package.name == "Root Plugin"
        assert result.package.version == "1.0.0"
        
        # Test 2: Recursive search finds .github/plugin/ when no root
        plugin_dir2 = tmp_path / "github-test"
        plugin_dir2.mkdir()
        (plugin_dir2 / ".github" / "plugin").mkdir(parents=True)
        with open(plugin_dir2 / ".github" / "plugin" / "plugin.json", "w") as f:
            json.dump({"name": "GitHub Plugin", "version": "2.0.0", "description": "GitHub"}, f)
            
        result2 = validate_apm_package(plugin_dir2)
        assert result2.package_type == PackageType.MARKETPLACE_PLUGIN
        assert result2.package.name == "GitHub Plugin"
        assert result2.package.version == "2.0.0"
        
        # Test 3: Recursive search finds .claude-plugin/ when no root
        plugin_dir3 = tmp_path / "claude-test"
        plugin_dir3.mkdir()
        (plugin_dir3 / ".claude-plugin").mkdir()
        with open(plugin_dir3 / ".claude-plugin" / "plugin.json", "w") as f:
            json.dump({"name": "Claude Plugin", "version": "3.0.0", "description": "Claude"}, f)
            
        result3 = validate_apm_package(plugin_dir3)
        assert result3.package_type == PackageType.MARKETPLACE_PLUGIN
        assert result3.package.name == "Claude Plugin"
        assert result3.package.version == "3.0.0"
    
    def test_plugin_detection_and_structure_mapping(self):
        """Test that a plugin is detected and mapped correctly using fixtures."""
        # Use the mock plugin fixture
        fixture_path = Path(__file__).parent.parent / "fixtures" / "mock-marketplace-plugin"
        
        if not fixture_path.exists():
            pytest.skip("Mock marketplace plugin fixture not available")
        
        # Validate the plugin package
        result = validate_apm_package(fixture_path)
        
        # Verify package type detection
        assert result.package_type == PackageType.MARKETPLACE_PLUGIN, \
            f"Expected MARKETPLACE_PLUGIN, got {result.package_type}"
        
        # Verify no errors
        assert result.is_valid, f"Package validation failed: {result.errors}"
        
        # Verify package was created
        assert result.package is not None, "Package should be created"
        assert result.package.name == "Mock Marketplace Plugin"
        assert result.package.version == "1.0.0"
        assert result.package.description == "A test marketplace plugin for APM integration testing"
        
        # Verify apm.yml was synthesized
        apm_yml_path = fixture_path / "apm.yml"
        assert apm_yml_path.exists(), "apm.yml should be synthesized"
        
        # Verify .apm directory structure was created
        apm_dir = fixture_path / ".apm"
        assert apm_dir.exists(), ".apm directory should exist"
        
        # Verify artifact mapping
        agents_dir = apm_dir / "agents"
        assert agents_dir.exists(), "agents/ should be mapped to .apm/agents/"
        assert (agents_dir / "test-agent.agent.md").exists(), "Agent file should be mapped"
        
        skills_dir = apm_dir / "skills"
        assert skills_dir.exists(), "skills/ should be mapped to .apm/skills/"
        assert (skills_dir / "test-skill" / "SKILL.md").exists(), "Skill should be mapped"
        
        prompts_dir = apm_dir / "prompts"
        assert prompts_dir.exists(), "commands/ should be mapped to .apm/prompts/"
        assert (prompts_dir / "test-command.md").exists(), "Command should be mapped to prompts"
        
        # Cleanup synthesized files for next test run
        if apm_yml_path.exists():
            apm_yml_path.unlink()
        if apm_dir.exists():
            shutil.rmtree(apm_dir)
    
    def test_plugin_with_dependencies(self, tmp_path):
        """Test plugin with dependencies are handled correctly."""
        plugin_dir = tmp_path / "plugin-with-deps"
        plugin_dir.mkdir()
        
        # Create plugin.json with dependencies
        plugin_json = plugin_dir / "plugin.json"
        plugin_json.write_text("""
{
  "name": "Plugin With Dependencies",
  "version": "2.0.0",
  "description": "A plugin with dependencies",
  "author": "Test Author",
  "dependencies": [
    "owner/dependency-package",
    "another/required-package#v1.0"
  ]
}
""")
        
        # Validate
        result = validate_apm_package(plugin_dir)
        
        assert result.package_type == PackageType.MARKETPLACE_PLUGIN
        assert result.is_valid
        assert result.package is not None
        
        # Verify dependencies are in apm.yml
        apm_yml = plugin_dir / "apm.yml"
        assert apm_yml.exists()
        
        content = apm_yml.read_text()
        assert "dependencies:" in content
        assert "owner/dependency-package" in content
        assert "another/required-package#v1.0" in content
    
    def test_plugin_metadata_preservation(self, tmp_path):
        """Test that all plugin metadata is preserved in apm.yml."""
        plugin_dir = tmp_path / "metadata-plugin"
        plugin_dir.mkdir()
        
        # Create plugin.json with all metadata fields
        plugin_json = plugin_dir / "plugin.json"
        plugin_json.write_text("""
{
  "name": "Full Metadata Plugin",
  "version": "1.5.0",
  "description": "A plugin with complete metadata",
  "author": "APM Contributors",
  "license": "Apache-2.0",
  "repository": "microsoft/apm-plugin",
  "homepage": "https://apm.dev/plugins/test",
  "tags": ["ai", "agents", "testing"]
}
""")
        
        # Validate
        result = validate_apm_package(plugin_dir)
        
        assert result.is_valid
        package = result.package
        
        # Verify all metadata
        assert package.name == "Full Metadata Plugin"
        assert package.version == "1.5.0"
        assert package.description == "A plugin with complete metadata"
        assert package.author == "APM Contributors"
        assert package.license == "Apache-2.0"
        
        # Read apm.yml and verify fields
        apm_yml = (plugin_dir / "apm.yml").read_text()
        assert "repository: microsoft/apm-plugin" in apm_yml
        assert "homepage: https://apm.dev/plugins/test" in apm_yml
        assert "tags:" in apm_yml
        assert "ai" in apm_yml
        assert "agents" in apm_yml
    
    def test_invalid_plugin_json(self, tmp_path):
        """Test that invalid plugin.json is handled gracefully."""
        plugin_dir = tmp_path / "invalid-plugin"
        plugin_dir.mkdir()
        
        # Create invalid plugin.json (missing required fields)
        plugin_json = plugin_dir / "plugin.json"
        plugin_json.write_text("""
{
  "name": "Invalid Plugin"
}
""")
        
        # Validate
        result = validate_apm_package(plugin_dir)
        
        # Should fail validation
        assert not result.is_valid
        assert len(result.errors) > 0
        assert any("version" in err.lower() or "required" in err.lower() 
                   for err in result.errors)
    
    def test_plugin_without_artifacts(self, tmp_path):
        """Test plugin with only plugin.json and no artifacts."""
        plugin_dir = tmp_path / "minimal-plugin"
        plugin_dir.mkdir()
        
        # Create minimal plugin.json
        plugin_json = plugin_dir / "plugin.json"
        plugin_json.write_text("""
{
  "name": "Minimal Plugin",
  "version": "0.1.0",
  "description": "A minimal plugin"
}
""")
        
        # Validate
        result = validate_apm_package(plugin_dir)
        
        assert result.package_type == PackageType.MARKETPLACE_PLUGIN
        assert result.is_valid
        assert result.package is not None
        
        # .apm directory should still be created even if empty
        apm_dir = plugin_dir / ".apm"
        assert apm_dir.exists()
