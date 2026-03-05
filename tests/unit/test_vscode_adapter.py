"""Unit tests for the VSCode client adapter."""

import os
import json
import tempfile
import unittest
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from apm_cli.adapters.client.vscode import VSCodeClientAdapter


class TestVSCodeClientAdapter(unittest.TestCase):
    """Test cases for the VSCode client adapter."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vscode_dir = os.path.join(self.temp_dir.name, ".vscode")
        os.makedirs(self.vscode_dir, exist_ok=True)
        self.temp_path = os.path.join(self.vscode_dir, "mcp.json")
        
        # Create a temporary MCP configuration file
        with open(self.temp_path, "w") as f:
            json.dump({"servers": {}}, f)
            
        # Create mock clients
        self.mock_registry_patcher = patch('apm_cli.adapters.client.vscode.SimpleRegistryClient')
        self.mock_registry_class = self.mock_registry_patcher.start()
        self.mock_registry = MagicMock()
        self.mock_registry_class.return_value = self.mock_registry
        
        self.mock_integration_patcher = patch('apm_cli.adapters.client.vscode.RegistryIntegration')
        self.mock_integration_class = self.mock_integration_patcher.start()
        self.mock_integration = MagicMock()
        self.mock_integration_class.return_value = self.mock_integration
        
        # Mock server details
        self.server_info = {
            "id": "12345",
            "name": "fetch",
            "description": "Fetch MCP server",
            "packages": [
                {
                    "name": "@mcp/fetch",
                    "version": "1.0.0",
                    "registry_name": "npm",
                    "runtime_hint": "npx"
                }
            ]
        }
        
        # Configure the mocks
        self.mock_registry.get_server_info.return_value = self.server_info
        self.mock_registry.get_server_by_name.return_value = self.server_info
        self.mock_registry.find_server_by_reference.return_value = self.server_info
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Force garbage collection to release file handles
        import gc
        gc.collect()
        # Small delay to allow Windows to release locks
        import time
        time.sleep(0.1)
        
        self.mock_registry_patcher.stop()
        self.mock_integration_patcher.stop()
        self.temp_dir.cleanup()
    
    @patch("apm_cli.adapters.client.vscode.VSCodeClientAdapter.get_config_path")
    def test_get_current_config(self, mock_get_path):
        """Test getting the current configuration."""
        mock_get_path.return_value = self.temp_path
        adapter = VSCodeClientAdapter()
        
        config = adapter.get_current_config()
        self.assertEqual(config, {"servers": {}})
    
    @patch("apm_cli.adapters.client.vscode.VSCodeClientAdapter.get_config_path")
    def test_update_config(self, mock_get_path):
        """Test updating the configuration."""
        mock_get_path.return_value = self.temp_path
        adapter = VSCodeClientAdapter()
        
        new_config = {
            "servers": {
                "test-server": {
                    "type": "stdio",
                    "command": "uvx",
                    "args": ["mcp-server-test"]
                }
            }
        }
        
        result = adapter.update_config(new_config)
        
        with open(self.temp_path, "r") as f:
            updated_config = json.load(f)
        
        self.assertEqual(updated_config, new_config)
        self.assertTrue(result)
        
    @patch("apm_cli.adapters.client.vscode.VSCodeClientAdapter.get_config_path")
    def test_update_config_nonexistent_file(self, mock_get_path):
        """Test updating configuration when file doesn't exist."""
        nonexistent_path = os.path.join(self.vscode_dir, "nonexistent.json")
        mock_get_path.return_value = nonexistent_path
        adapter = VSCodeClientAdapter()
        
        new_config = {
            "servers": {
                "test-server": {
                    "type": "stdio",
                    "command": "uvx",
                    "args": ["mcp-server-test"]
                }
            }
        }
        
        result = adapter.update_config(new_config)
        
        with open(nonexistent_path, "r") as f:
            updated_config = json.load(f)
        
        self.assertEqual(updated_config, new_config)
        self.assertTrue(result)
    
    @patch("apm_cli.adapters.client.vscode.VSCodeClientAdapter.get_config_path")
    def test_configure_mcp_server(self, mock_get_path):
        """Test configuring an MCP server."""
        mock_get_path.return_value = self.temp_path
        adapter = VSCodeClientAdapter()
        
        result = adapter.configure_mcp_server(
            server_url="fetch", 
            server_name="fetch"
        )
        
        with open(self.temp_path, "r") as f:
            updated_config = json.load(f)
        
        self.assertTrue(result)
        self.assertIn("servers", updated_config)
        self.assertIn("fetch", updated_config["servers"])
        
        # Verify the registry client was called
        self.mock_registry.find_server_by_reference.assert_called_once_with("fetch")
        
        # Verify the server configuration
        self.assertEqual(updated_config["servers"]["fetch"]["type"], "stdio")
        self.assertEqual(updated_config["servers"]["fetch"]["command"], "npx")
        self.assertEqual(updated_config["servers"]["fetch"]["args"], ["@mcp/fetch"])
    
    @patch("apm_cli.adapters.client.vscode.VSCodeClientAdapter.get_config_path")
    def test_configure_mcp_server_update_existing(self, mock_get_path):
        """Test updating an existing MCP server."""
        # Create a config with an existing server
        existing_config = {
            "servers": {
                "fetch": {
                    "type": "stdio",
                    "command": "docker",
                    "args": ["run", "-i", "--rm", "mcp/fetch"]
                }
            }
        }
        
        with open(self.temp_path, "w") as f:
            json.dump(existing_config, f)
            
        mock_get_path.return_value = self.temp_path
        adapter = VSCodeClientAdapter()
        
        result = adapter.configure_mcp_server(
            server_url="fetch", 
            server_name="fetch"
        )
        
        with open(self.temp_path, "r") as f:
            updated_config = json.load(f)
        
        self.assertTrue(result)
        self.assertIn("fetch", updated_config["servers"])
        
        # Verify the registry client was called
        self.mock_registry.find_server_by_reference.assert_called_once_with("fetch")
        
        # Verify the server configuration
        self.assertEqual(updated_config["servers"]["fetch"]["type"], "stdio")
        self.assertEqual(updated_config["servers"]["fetch"]["command"], "npx")
        self.assertEqual(updated_config["servers"]["fetch"]["args"], ["@mcp/fetch"])
    
    @patch("apm_cli.adapters.client.vscode.VSCodeClientAdapter.get_config_path")
    def test_configure_mcp_server_empty_url(self, mock_get_path):
        """Test configuring an MCP server with empty URL."""
        mock_get_path.return_value = self.temp_path
        adapter = VSCodeClientAdapter()
        
        result = adapter.configure_mcp_server(
            server_url="", 
            server_name="Example Server"
        )
        
        self.assertFalse(result)
    
    @patch("apm_cli.adapters.client.vscode.VSCodeClientAdapter.get_config_path")
    def test_configure_mcp_server_registry_error(self, mock_get_path):
        """Test error behavior when registry doesn't have server details."""
        # Configure the mock to return None when server is not found
        self.mock_registry.find_server_by_reference.return_value = None
        
        mock_get_path.return_value = self.temp_path
        adapter = VSCodeClientAdapter()
        
        # Test that ValueError is raised when server details can't be retrieved
        with self.assertRaises(ValueError) as context:
            adapter.configure_mcp_server(
                server_url="unknown-server", 
                server_name="unknown-server"
            )
        
        self.assertIn("Failed to retrieve server details for 'unknown-server'. Server not found in registry.", str(context.exception))
    
    @patch("os.getcwd")
    def test_get_config_path_repository(self, mock_getcwd):
        """Test getting the config path in the repository."""
        mock_getcwd.return_value = self.temp_dir.name
        
        adapter = VSCodeClientAdapter()
        path = adapter.get_config_path()
        
        # Create Path objects for comparison to handle platform differences
        actual_path = Path(path)
        expected_path = Path(self.temp_dir.name) / ".vscode" / "mcp.json"
        
        # Compare parts of the path to avoid string formatting issues
        self.assertEqual(actual_path.parent, expected_path.parent)
        self.assertEqual(actual_path.name, expected_path.name)

    @patch("apm_cli.adapters.client.vscode.VSCodeClientAdapter.get_config_path")
    def test_format_server_config_http_remote(self, mock_get_path):
        """Test _format_server_config handles http transport in remotes."""
        mock_get_path.return_value = self.temp_path
        adapter = VSCodeClientAdapter()

        server_info = {
            "name": "my-http-server",
            "remotes": [{"transport_type": "http", "url": "https://example.com/mcp"}],
        }
        config, inputs = adapter._format_server_config(server_info)

        self.assertEqual(config["type"], "http")
        self.assertEqual(config["url"], "https://example.com/mcp")
        self.assertEqual(config["headers"], {})
        self.assertEqual(inputs, [])

    @patch("apm_cli.adapters.client.vscode.VSCodeClientAdapter.get_config_path")
    def test_format_server_config_streamable_http_remote(self, mock_get_path):
        """Test _format_server_config handles streamable-http transport in remotes."""
        mock_get_path.return_value = self.temp_path
        adapter = VSCodeClientAdapter()

        server_info = {
            "name": "streamable-server",
            "remotes": [{"transport_type": "streamable-http", "url": "https://stream.example.com"}],
        }
        config, inputs = adapter._format_server_config(server_info)

        self.assertEqual(config["type"], "streamable-http")
        self.assertEqual(config["url"], "https://stream.example.com")

    @patch("apm_cli.adapters.client.vscode.VSCodeClientAdapter.get_config_path")
    def test_format_server_config_remote_with_list_headers(self, mock_get_path):
        """Test _format_server_config normalizes header list to dict."""
        mock_get_path.return_value = self.temp_path
        adapter = VSCodeClientAdapter()

        server_info = {
            "name": "header-server",
            "remotes": [{
                "transport_type": "http",
                "url": "https://example.com",
                "headers": [
                    {"name": "Authorization", "value": "Bearer token123"},
                    {"name": "X-Custom", "value": "val"},
                ],
            }],
        }
        config, inputs = adapter._format_server_config(server_info)

        self.assertEqual(config["type"], "http")
        self.assertEqual(config["headers"], {
            "Authorization": "Bearer token123",
            "X-Custom": "val",
        })

    @patch("apm_cli.adapters.client.vscode.VSCodeClientAdapter.get_config_path")
    def test_configure_self_defined_http_via_cache(self, mock_get_path):
        """Test configuring a self-defined HTTP server through server_info_cache."""
        mock_get_path.return_value = self.temp_path
        adapter = VSCodeClientAdapter()

        # Synthetic server_info as built by _build_self_defined_server_info
        cache = {
            "my-private-srv": {
                "name": "my-private-srv",
                "remotes": [{"transport_type": "http", "url": "http://localhost:8787/"}],
            }
        }

        result = adapter.configure_mcp_server(
            server_url="my-private-srv",
            server_name="my-private-srv",
            server_info_cache=cache,
        )

        self.assertTrue(result)
        with open(self.temp_path, "r") as f:
            config = json.load(f)

        self.assertIn("my-private-srv", config["servers"])
        self.assertEqual(config["servers"]["my-private-srv"]["type"], "http")
        self.assertEqual(config["servers"]["my-private-srv"]["url"], "http://localhost:8787/")


if __name__ == "__main__":
    unittest.main()
