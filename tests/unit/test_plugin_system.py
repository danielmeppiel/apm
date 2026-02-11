"""Unit tests for the plugin system."""

import pytest
import json
import tempfile
from unittest.mock import patch, MagicMock

from src.apm_cli.plugin.marketplace import MarketplaceManager, Plugin
from src.apm_cli.plugin.resolver import PluginResolver


class TestMarketplaceManager:
    """Test MarketplaceManager functionality."""
    
    def test_plugin_from_claude_format(self):
        """Test creating a Plugin from Claude marketplace format."""
        data = {
            "id": "test-plugin",
            "name": "Test Plugin",
            "description": "A test plugin",
            "version": "1.0.0",
            "repository": "https://github.com/owner/test-plugin",
        }
        
        plugin = Plugin.from_claude_format(data, "https://github.com/anthropics/claude-code")
        
        assert plugin.id == "test-plugin"
        assert plugin.name == "Test Plugin"
        assert plugin.repository == "https://github.com/owner/test-plugin"
        assert plugin.marketplace_source == "https://github.com/anthropics/claude-code"
    
    def test_plugin_from_github_format(self):
        """Test creating a Plugin from GitHub marketplace format."""
        data = {
            "id": "skill-id",
            "name": "Test Skill",
            "description": "A test skill",
            "version": "2.0.0",
            "url": "https://github.com/owner/test-skill",
        }
        
        plugin = Plugin.from_github_format(data, "https://github.com/owner/plugins")
        
        assert plugin.id == "skill-id"
        assert plugin.name == "Test Skill"
        assert plugin.repository == "https://github.com/owner/test-skill"
    
    def test_plugin_to_dict(self):
        """Test converting Plugin to dictionary."""
        plugin = Plugin(
            id="test",
            name="Test",
            description="Test desc",
            version="1.0",
            repository="https://github.com/owner/test",
            marketplace_source="https://test.com"
        )
        
        d = plugin.to_dict()
        assert d["id"] == "test"
        assert d["name"] == "Test"
        assert isinstance(d, dict)
    
    @patch('requests.Session.get')
    def test_fetch_marketplace_claude_format(self, mock_get):
        """Test fetching Claude format marketplace."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "plugins": [
                {
                    "id": "plugin1",
                    "name": "Plugin 1",
                    "description": "First plugin",
                    "version": "1.0",
                    "repository": "https://github.com/owner/plugin1"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        manager = MarketplaceManager()
        result = manager.fetch_marketplace("https://github.com/anthropics/claude-code")
        
        assert "plugins" in result
        assert len(result["plugins"]) == 1
        assert result["plugins"][0]["id"] == "plugin1"
    
    @patch('requests.Session.get')
    def test_resolve_marketplace_url_claude_short_name(self, mock_get):
        """Test resolving 'claude' to official marketplace URL."""
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("", "", 0)
        mock_get.return_value = mock_response
        
        manager = MarketplaceManager()
        url = manager._try_fetch_marketplace_file(
            "https://github.com/anthropics/claude-code",
            ".claude-plugin/marketplace.json"
        )
        # The URL should be assembled correctly
        call_args = mock_get.call_args[0][0] if mock_get.called else ""
        assert "anthropics" in call_args
        assert "claude-code" in call_args


class TestPluginResolver:
    """Test PluginResolver functionality."""
    
    def test_resolve_marketplace_url_claude(self):
        """Test resolving 'claude' marketplace source."""
        resolver = PluginResolver()
        url = resolver._resolve_marketplace_url("claude")
        
        assert "anthropics" in url
        assert "claude-code" in url
    
    def test_resolve_marketplace_url_github_owner_repo(self):
        """Test resolving 'owner/repo' marketplace source."""
        resolver = PluginResolver()
        url = resolver._resolve_marketplace_url("owner/repo")
        
        assert url == "https://github.com/owner/repo"
    
    def test_resolve_marketplace_url_full_url(self):
        """Test resolving full URL marketplace source."""
        test_url = "https://github.com/custom/plugins"
        resolver = PluginResolver()
        url = resolver._resolve_marketplace_url(test_url)
        
        assert url == test_url
    
    def test_resolve_marketplace_url_github_com_prefix(self):
        """Test resolving 'github.com/owner/repo' marketplace source."""
        resolver = PluginResolver()
        url = resolver._resolve_marketplace_url("github.com/owner/repo")
        
        assert url == "https://github.com/owner/repo"
    
    def test_resolve_marketplace_url_invalid(self):
        """Test resolving invalid marketplace source."""
        resolver = PluginResolver()
        
        with pytest.raises(ValueError):
            resolver._resolve_marketplace_url("invalid.source.name")
    
    @patch('src.apm_cli.plugin.resolver.MarketplaceManager')
    def test_resolve_plugin_valid_spec(self, mock_manager_cls):
        """Test resolving a valid plugin specification."""
        mock_plugin = MagicMock()
        mock_plugin.repository = "https://github.com/owner/plugin-name"
        
        mock_instance = MagicMock()
        mock_instance.find_plugin.return_value = mock_plugin
        mock_instance.KNOWN_MARKETPLACES = {
            "claude": "https://github.com/anthropics/claude-code",
            "awesome-copilot": "https://github.com/github/awesome-copilot",
        }
        mock_manager_cls.return_value = mock_instance
        
        resolver = PluginResolver()
        
        plugin_id, repo_url = resolver.resolve_plugin("my-plugin@claude")
        
        assert plugin_id == "my-plugin"
        assert repo_url == "https://github.com/owner/plugin-name"
    
    def test_resolve_plugin_invalid_spec_no_at(self):
        """Test resolving plugin spec without @ separator."""
        resolver = PluginResolver()
        
        with pytest.raises(ValueError) as exc_info:
            resolver.resolve_plugin("invalid-plugin-spec")
        
        assert "Invalid plugin specification" in str(exc_info.value)
    
    def test_resolve_plugin_invalid_spec_empty_parts(self):
        """Test resolving plugin spec with empty parts."""
        resolver = PluginResolver()
        
        with pytest.raises(ValueError) as exc_info:
            resolver.resolve_plugin("@marketplace")
        
        assert "plugin-id and marketplace-name required" in str(exc_info.value)
    
    @patch('src.apm_cli.plugin.resolver.MarketplaceManager')
    def test_resolve_plugin_not_found(self, mock_manager_cls):
        """Test resolving plugin that doesn't exist."""
        mock_instance = MagicMock()
        mock_instance.find_plugin.return_value = None
        mock_instance.KNOWN_MARKETPLACES = {
            "claude": "https://github.com/anthropics/claude-code",
            "awesome-copilot": "https://github.com/github/awesome-copilot",
        }
        mock_manager_cls.return_value = mock_instance
        
        resolver = PluginResolver()
        
        with pytest.raises(ValueError) as exc_info:
            resolver.resolve_plugin("nonexistent@claude")
        
        assert "not found in marketplace" in str(exc_info.value)


class TestPluginIntegration:
    """Integration tests for plugin system."""
    
    def test_end_to_end_plugin_resolution(self):
        """Test end-to-end plugin resolution flow."""
        # This is a basic integration test that verifies the resolver
        # can parse plugin specs and resolve marketplace URLs
        
        resolver = PluginResolver()
        
        # Test valid marketplace URL resolution
        url = resolver._resolve_marketplace_url("claude")
        assert url is not None
        assert isinstance(url, str)
        assert url.startswith("https://")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
