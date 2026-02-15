"""Tests for plugin management system."""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from apm_cli.models.plugin import PluginMetadata, Plugin, MarketplaceEntry
from apm_cli.plugin.plugin_installer import (
    PluginInstaller,
    PluginAlreadyInstalledException,
    PluginNotFoundException,
)
from apm_cli.models.apm_package import DependencyReference
from apm_cli.primitives.discovery import scan_plugin_primitives
from apm_cli.primitives.models import PrimitiveCollection


class TestPluginMetadata:
    """Tests for PluginMetadata model."""
    
    def test_plugin_metadata_creation(self):
        """Test creating a PluginMetadata instance."""
        metadata = PluginMetadata(
            id="test-plugin",
            name="Test Plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
            repository="owner/repo",
        )
        
        assert metadata.id == "test-plugin"
        assert metadata.name == "Test Plugin"
        assert metadata.version == "1.0.0"
        assert metadata.description == "A test plugin"
        assert metadata.author == "Test Author"
        assert metadata.repository == "owner/repo"
    
    def test_plugin_metadata_to_dict(self):
        """Test converting metadata to dictionary."""
        metadata = PluginMetadata(
            id="test-plugin",
            name="Test Plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
            tags=["testing", "sample"],
        )
        
        data = metadata.to_dict()
        assert data["id"] == "test-plugin"
        assert data["name"] == "Test Plugin"
        assert data["tags"] == ["testing", "sample"]
    
    def test_plugin_metadata_from_dict(self):
        """Test creating metadata from dictionary."""
        data = {
            "id": "test-plugin",
            "name": "Test Plugin",
            "version": "1.0.0",
            "description": "A test plugin",
            "author": "Test Author",
            "tags": ["testing"],
        }
        
        metadata = PluginMetadata.from_dict(data)
        assert metadata.id == "test-plugin"
        assert metadata.name == "Test Plugin"
        assert metadata.tags == ["testing"]


class TestMarketplaceEntry:
    """Tests for MarketplaceEntry model."""
    
    def test_github_repository_format(self):
        """Test GitHub repository format."""
        entry = MarketplaceEntry(
            id="gh-plugin",
            name="GitHub Plugin",
            description="A GitHub plugin",
            repository="owner/repo",
            version="1.0.0",
            author="Author",
        )
        
        assert entry.repository == "owner/repo"
        assert "/" in entry.repository
    
    def test_azure_devops_repository_format(self):
        """Test Azure DevOps repository format."""
        entry = MarketplaceEntry(
            id="ado-plugin",
            name="ADO Plugin",
            description="An Azure DevOps plugin",
            repository="dev.azure.com/myorg/myproject/myrepo",
            version="1.0.0",
            author="Author",
        )
        
        assert entry.repository == "dev.azure.com/myorg/myproject/myrepo"
        assert "dev.azure.com" in entry.repository
    
    def test_azure_devops_with_host_field(self):
        """Test Azure DevOps repository with explicit host field."""
        entry = MarketplaceEntry(
            id="ado-plugin",
            name="ADO Plugin",
            description="An Azure DevOps plugin",
            repository="myorg/myproject/myrepo",
            host="dev.azure.com",
            version="1.0.0",
            author="Author",
        )
        
        assert entry.repository == "myorg/myproject/myrepo"
        assert entry.host == "dev.azure.com"
    
    def test_marketplace_entry_with_host_to_dict(self):
        """Test converting entry with host to dictionary."""
        entry = MarketplaceEntry(
            id="ado-plugin",
            name="ADO Plugin",
            description="Test",
            repository="org/project/repo",
            host="dev.azure.com",
            version="1.0.0",
            author="Test",
        )
        
        data = entry.to_dict()
        assert data["host"] == "dev.azure.com"
        assert data["repository"] == "org/project/repo"
    
    def test_marketplace_entry_from_dict_with_host(self):
        """Test creating entry from dictionary with host field."""
        data = {
            "id": "ado-plugin",
            "name": "ADO Plugin",
            "description": "Test",
            "repository": "org/project/repo",
            "host": "dev.azure.com",
            "version": "1.0.0",
            "author": "Test",
        }
        
        entry = MarketplaceEntry.from_dict(data)
        assert entry.host == "dev.azure.com"
        assert entry.repository == "org/project/repo"
    
    def test_marketplace_entry_from_dict(self):
        """Test creating entry from dictionary."""
        data = {
            "id": "test-plugin",
            "name": "Test Plugin",
            "description": "Test",
            "repository": "owner/repo",
            "version": "1.0.0",
            "author": "Test",
            "tags": ["test"],
        }
        
        entry = MarketplaceEntry.from_dict(data)
        assert entry.id == "test-plugin"
        assert entry.repository == "owner/repo"


class TestPlugin:
    """Tests for Plugin model."""
    
    def test_plugin_from_path(self, tmp_path):
        """Test loading a plugin from path."""
        plugin_dir = tmp_path / "test-plugin"
        plugin_dir.mkdir()
        
        # Create plugin.json
        metadata = {
            "id": "test-plugin",
            "name": "Test Plugin",
            "version": "1.0.0",
            "description": "Test",
            "author": "Test",
        }
        
        (plugin_dir / "plugin.json").write_text(json.dumps(metadata))
        
        # Create plugins subdirectory
        plugins_subdir = plugin_dir / "plugins"
        plugins_subdir.mkdir()
        
        # Create some plugin components in plugins/ subdirectory
        agents_dir = plugins_subdir / "agents"
        agents_dir.mkdir()
        (agents_dir / "test.agent.md").write_text("# Test Agent")
        
        skills_dir = plugins_subdir / "skills"
        skills_dir.mkdir()
        test_skill_dir = skills_dir / "test-skill"
        test_skill_dir.mkdir()
        (test_skill_dir / "SKILL.md").write_text("# Test Skill")
        
        # Load plugin
        plugin = Plugin.from_path(plugin_dir)
        
        assert plugin.metadata.id == "test-plugin"
        assert len(plugin.agents) == 1
        assert len(plugin.skills) == 1
    
    def test_plugin_from_path_missing_metadata(self, tmp_path):
        """Test loading plugin without plugin.json fails."""
        plugin_dir = tmp_path / "test-plugin"
        plugin_dir.mkdir()
        
        with pytest.raises(FileNotFoundError):
            Plugin.from_path(plugin_dir)


class TestPluginInstaller:
    """Tests for PluginInstaller."""
    
    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        return project_dir
    
    @pytest.fixture
    def installer(self, temp_project):
        """Create a PluginInstaller instance."""
        return PluginInstaller(base_dir=temp_project)
    
    def test_installer_initialization(self, installer, temp_project):
        """Test installer initialization."""
        assert installer.base_dir == temp_project
        assert installer.apm_modules_dir == temp_project / "apm_modules"
    
    @patch("apm_cli.plugin.plugin_installer.requests.get")
    def test_load_marketplace(self, mock_get, installer):
        """Test loading marketplace catalog."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "version": "1.0.0",
            "plugins": [
                {
                    "id": "test-plugin",
                    "name": "Test Plugin",
                    "description": "Test",
                    "repository": "owner/repo",
                    "version": "1.0.0",
                    "author": "Test",
                }
            ],
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        entries = installer._load_marketplace()
        
        assert len(entries) == 1
        assert entries[0].id == "test-plugin"
    
    @patch("apm_cli.plugin.plugin_installer.requests.get")
    def test_search_plugins(self, mock_get, installer):
        """Test searching for plugins."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "version": "1.0.0",
            "plugins": [
                {
                    "id": "plugin-one",
                    "name": "Plugin One",
                    "description": "First plugin",
                    "repository": "owner/repo1",
                    "version": "1.0.0",
                    "author": "Test",
                    "tags": ["testing"],
                },
                {
                    "id": "plugin-two",
                    "name": "Plugin Two",
                    "description": "Second plugin",
                    "repository": "owner/repo2",
                    "version": "1.0.0",
                    "author": "Test",
                    "tags": ["production"],
                },
            ],
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Search by query
        results = installer.search(query="First")
        assert len(results) == 1
        assert results[0].id == "plugin-one"
        
        # Search by tag
        results = installer.search(tags=["production"])
        assert len(results) == 1
        assert results[0].id == "plugin-two"
    
    @patch("apm_cli.plugin.plugin_installer.requests.get")
    def test_get_plugin_info(self, mock_get, installer):
        """Test getting plugin information."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "version": "1.0.0",
            "plugins": [
                {
                    "id": "test-plugin",
                    "name": "Test Plugin",
                    "description": "Test",
                    "repository": "owner/repo",
                    "version": "1.0.0",
                    "author": "Test",
                }
            ],
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        entry = installer.get_plugin_info("test-plugin")
        
        assert entry.id == "test-plugin"
        assert entry.name == "Test Plugin"
    
    @patch("apm_cli.plugin.plugin_installer.requests.get")
    def test_get_plugin_info_not_found(self, mock_get, installer):
        """Test getting info for non-existent plugin."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "version": "1.0.0",
            "plugins": [],
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        with pytest.raises(PluginNotFoundException):
            installer.get_plugin_info("non-existent")
    
    def test_is_installed(self, installer, temp_project):
        """Test checking if plugin is installed."""
        # Initially not installed
        assert not installer.is_installed("test-plugin")
        
        # Create plugin directory with metadata in apm_modules/{owner}/{repo}
        plugin_dir = temp_project / "apm_modules" / "test-owner" / "test-plugin"
        plugin_dir.mkdir(parents=True)
        
        metadata = {
            "id": "test-plugin",
            "name": "Test Plugin",
            "version": "1.0.0",
            "description": "Test",
            "author": "Test",
        }
        (plugin_dir / "plugin.json").write_text(json.dumps(metadata))
        
        # Now it's installed
        assert installer.is_installed("test-plugin")
    
    def test_list_installed(self, installer, temp_project):
        """Test listing installed plugins."""
        # Initially empty
        plugins = installer.list_installed()
        assert len(plugins) == 0
        
        # Install first plugin in apm_modules/{owner}/{repo}
        plugin1_dir = temp_project / "apm_modules" / "owner1" / "plugin1"
        plugin1_dir.mkdir(parents=True)
        metadata1 = {
            "id": "plugin1",
            "name": "Plugin 1",
            "version": "1.0.0",
            "description": "Test",
            "author": "Test",
        }
        (plugin1_dir / "plugin.json").write_text(json.dumps(metadata1))
        
        # Install second plugin
        plugin2_dir = temp_project / "apm_modules" / "owner2" / "plugin2"
        plugin2_dir.mkdir(parents=True)
        metadata2 = {
            "id": "plugin2",
            "name": "Plugin 2",
            "version": "1.0.0",
            "description": "Test",
            "author": "Test",
        }
        (plugin2_dir / "plugin.json").write_text(json.dumps(metadata2))
        
        # List plugins
        plugins = installer.list_installed()
        assert len(plugins) == 2
        plugin_ids = [p.metadata.id for p in plugins]
        assert "plugin1" in plugin_ids
        assert "plugin2" in plugin_ids


class TestPluginDownload:
    """Tests for plugin download with GitHub and Azure DevOps support."""
    
    def test_dependency_reference_parse_github(self):
        """Test parsing GitHub repository reference."""
        dep_ref = DependencyReference.parse("owner/repo")
        
        assert not dep_ref.is_azure_devops()
        assert dep_ref.repo_url == "owner/repo"
    
    def test_dependency_reference_parse_azure_devops_full_url(self):
        """Test parsing Azure DevOps repository with full URL."""
        dep_ref = DependencyReference.parse("https://dev.azure.com/myorg/myproject/_git/myrepo")
        
        assert dep_ref.is_azure_devops()
        # Verify it was properly parsed
        assert dep_ref.ado_organization == "myorg"
        assert dep_ref.ado_project == "myproject"
    
    def test_marketplace_entry_github_simple_format(self):
        """Test marketplace entry with simple GitHub format."""
        entry = MarketplaceEntry(
            id="gh-plugin",
            name="GitHub Plugin",
            description="A GitHub plugin",
            repository="owner/repo",  # Simple format defaults to GitHub
            version="1.0.0",
            author="Author",
        )
        
        dep_ref = DependencyReference.parse(entry.repository)
        assert not dep_ref.is_azure_devops()
    
    def test_marketplace_entry_ado_full_url(self):
        """Test marketplace entry with Azure DevOps full URL."""
        entry = MarketplaceEntry(
            id="ado-plugin",
            name="ADO Plugin",
            description="An Azure DevOps plugin",
            repository="https://dev.azure.com/myorg/myproject/_git/myrepo",  # Full URL
            version="1.0.0",
            author="Author",
        )
        
        dep_ref = DependencyReference.parse(entry.repository)
        assert dep_ref.is_azure_devops()
        assert dep_ref.ado_organization == "myorg"
        assert dep_ref.ado_project == "myproject"
    
    def test_marketplace_entry_github_enterprise_full_url(self, monkeypatch):
        """Test marketplace entry with GitHub Enterprise full URL."""
        # Set GITHUB_HOST to allow custom GitHub Enterprise host
        monkeypatch.setenv("GITHUB_HOST", "github.company.com")
        
        entry = MarketplaceEntry(
            id="ghe-plugin",
            name="GHE Plugin",
            description="A GitHub Enterprise plugin",
            repository="https://github.company.com/org/repo",  # Full URL
            version="1.0.0",
            author="Author",
        )
        
        dep_ref = DependencyReference.parse(entry.repository)
        # Should not be ADO
        assert not dep_ref.is_azure_devops()
        # Should have custom host
        assert dep_ref.host == "github.company.com"


class TestPluginDiscovery:
    """Tests for plugin primitive discovery."""
    
    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with plugins."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        
        # Create plugin directory structure in apm_modules/{owner}/{repo}
        plugin_dir = project_dir / "apm_modules" / "test-owner" / "test-plugin"
        plugin_dir.mkdir(parents=True)
        
        # Create plugin metadata
        metadata = {
            "id": "test-plugin",
            "name": "Test Plugin",
            "version": "1.0.0",
            "description": "Test",
            "author": "Test",
        }
        (plugin_dir / "plugin.json").write_text(json.dumps(metadata))
        
        # Create plugins subdirectory for primitives
        plugins_subdir = plugin_dir / "plugins"
        plugins_subdir.mkdir()
        
        # Create agents in plugins/agents/
        agents_dir = plugins_subdir / "agents"
        agents_dir.mkdir()
        (agents_dir / "test.agent.md").write_text("""---
name: Test Agent
description: A test agent
---

# Test Agent

This is a test agent from a plugin.
""")
        
        # Create skills in plugins/skills/ subdirectories
        skills_dir = plugins_subdir / "skills"
        skills_dir.mkdir()
        test_skill_dir = skills_dir / "test-skill"
        test_skill_dir.mkdir()
        (test_skill_dir / "SKILL.md").write_text("""# Test Skill

This is a test skill from a plugin.
""")
        
        # Create instructions in plugins/instructions/
        instructions_dir = plugins_subdir / "instructions"
        instructions_dir.mkdir()
        (instructions_dir / "test.instructions.md").write_text("""---
applyTo: "**/*.py"
description: Test instructions
---

# Test Instructions

These are test instructions from a plugin.
""")
        
        return project_dir
    
    def test_scan_plugin_primitives(self, temp_project):
        """Test scanning plugins for primitives."""
        collection = PrimitiveCollection()
        
        scan_plugin_primitives(str(temp_project), collection)
        
        # Verify primitives were discovered
        primitives = collection.all_primitives()
        assert len(primitives) > 0
        
        # Check that at least one primitive has plugin source
        plugin_sources = [p.source for p in primitives if p.source.startswith("plugin:")]
        assert len(plugin_sources) > 0
        assert "plugin:test-plugin" in plugin_sources
    
    def test_scan_plugin_primitives_no_plugins_dir(self, tmp_path):
        """Test scanning when plugins directory doesn't exist."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        
        collection = PrimitiveCollection()
        scan_plugin_primitives(str(project_dir), collection)
        
        # Should not fail, just return empty
        assert len(collection.all_primitives()) == 0
    
    def test_plugin_primitive_source_tracking(self, temp_project):
        """Test that plugin primitives have correct source tracking."""
        collection = PrimitiveCollection()
        
        scan_plugin_primitives(str(temp_project), collection)
        
        primitives = collection.all_primitives()
        
        for primitive in primitives:
            # All primitives from this test should have plugin source
            assert primitive.source.startswith("plugin:")
            assert "test-plugin" in primitive.source
