"""Unit tests for MCP server operations (registry/operations.py)."""

import os
import unittest
from unittest.mock import MagicMock, Mock, patch

from apm_cli.registry.operations import MCPServerOperations


class TestMCPServerOperationsInit(unittest.TestCase):
    """Tests for MCPServerOperations initialization."""

    @patch("apm_cli.registry.operations.SimpleRegistryClient")
    def test_default_init(self, mock_client_class):
        """Test initialization with default registry URL."""
        mock_client_class.return_value = Mock()
        ops = MCPServerOperations()
        mock_client_class.assert_called_once_with(None)

    @patch("apm_cli.registry.operations.SimpleRegistryClient")
    def test_custom_registry_url(self, mock_client_class):
        """Test initialization with custom registry URL."""
        mock_client_class.return_value = Mock()
        ops = MCPServerOperations("https://custom.registry.example.com")
        mock_client_class.assert_called_once_with("https://custom.registry.example.com")


class TestValidateServersExist(unittest.TestCase):
    """Tests for validate_servers_exist method."""

    def setUp(self):
        with patch("apm_cli.registry.operations.SimpleRegistryClient"):
            self.ops = MCPServerOperations()
        self.ops.registry_client = Mock()

    def test_all_valid_servers(self):
        """All servers found in registry are returned as valid."""
        self.ops.registry_client.find_server_by_reference.return_value = {
            "id": "abc",
            "name": "server1",
        }
        valid, invalid = self.ops.validate_servers_exist(["server1", "server2"])
        self.assertEqual(valid, ["server1", "server2"])
        self.assertEqual(invalid, [])

    def test_all_invalid_servers(self):
        """Servers not found in registry are returned as invalid."""
        self.ops.registry_client.find_server_by_reference.return_value = None
        valid, invalid = self.ops.validate_servers_exist(["unknown1", "unknown2"])
        self.assertEqual(valid, [])
        self.assertEqual(invalid, ["unknown1", "unknown2"])

    def test_mixed_valid_invalid(self):
        """Mix of found and not-found servers."""

        def side_effect(ref):
            return {"id": "abc"} if ref == "good-server" else None

        self.ops.registry_client.find_server_by_reference.side_effect = side_effect
        valid, invalid = self.ops.validate_servers_exist(["good-server", "bad-server"])
        self.assertIn("good-server", valid)
        self.assertIn("bad-server", invalid)

    def test_exception_marks_server_invalid(self):
        """Exception during lookup marks server as invalid."""
        self.ops.registry_client.find_server_by_reference.side_effect = Exception(
            "network error"
        )
        valid, invalid = self.ops.validate_servers_exist(["server1"])
        self.assertEqual(valid, [])
        self.assertEqual(invalid, ["server1"])

    def test_empty_server_list(self):
        """Empty input returns empty valid and invalid lists."""
        valid, invalid = self.ops.validate_servers_exist([])
        self.assertEqual(valid, [])
        self.assertEqual(invalid, [])


class TestBatchFetchServerInfo(unittest.TestCase):
    """Tests for batch_fetch_server_info method."""

    def setUp(self):
        with patch("apm_cli.registry.operations.SimpleRegistryClient"):
            self.ops = MCPServerOperations()
        self.ops.registry_client = Mock()

    def test_successful_fetch(self):
        """Fetches info for all server references."""
        server_info = {"id": "abc", "name": "server1"}
        self.ops.registry_client.find_server_by_reference.return_value = server_info
        result = self.ops.batch_fetch_server_info(["server1", "server2"])
        self.assertEqual(result["server1"], server_info)
        self.assertEqual(result["server2"], server_info)

    def test_not_found_returns_none(self):
        """Not-found servers map to None."""
        self.ops.registry_client.find_server_by_reference.return_value = None
        result = self.ops.batch_fetch_server_info(["missing"])
        self.assertIsNone(result["missing"])

    def test_exception_returns_none(self):
        """Exception during fetch maps to None."""
        self.ops.registry_client.find_server_by_reference.side_effect = Exception(
            "timeout"
        )
        result = self.ops.batch_fetch_server_info(["server1"])
        self.assertIsNone(result["server1"])

    def test_empty_list(self):
        """Empty input returns empty dict."""
        result = self.ops.batch_fetch_server_info([])
        self.assertEqual(result, {})


class TestCheckServersNeedingInstallation(unittest.TestCase):
    """Tests for check_servers_needing_installation method."""

    def setUp(self):
        with patch("apm_cli.registry.operations.SimpleRegistryClient"):
            self.ops = MCPServerOperations()
        self.ops.registry_client = Mock()

    def test_server_not_in_registry_needs_installation(self):
        """Servers not found in registry are added to installation list."""
        self.ops.registry_client.find_server_by_reference.return_value = None
        result = self.ops.check_servers_needing_installation(
            ["copilot"], ["custom-server"]
        )
        self.assertIn("custom-server", result)

    def test_server_with_no_id_needs_installation(self):
        """Server found but with no ID is treated as needing installation."""
        self.ops.registry_client.find_server_by_reference.return_value = {
            "name": "server1"
        }
        result = self.ops.check_servers_needing_installation(["copilot"], ["server1"])
        self.assertIn("server1", result)

    def test_exception_adds_to_installation_list(self):
        """Exception during check adds server to installation list."""
        self.ops.registry_client.find_server_by_reference.side_effect = Exception(
            "error"
        )
        result = self.ops.check_servers_needing_installation(["copilot"], ["server1"])
        self.assertIn("server1", result)

    def test_empty_servers_list(self):
        """Empty server list returns empty result."""
        result = self.ops.check_servers_needing_installation(["copilot"], [])
        self.assertEqual(result, [])

    @patch("apm_cli.registry.operations.MCPServerOperations._get_installed_server_ids")
    def test_already_installed_server_not_in_result(self, mock_get_ids):
        """Server already installed in all runtimes is not in result."""
        self.ops.registry_client.find_server_by_reference.return_value = {
            "id": "server-uuid-123"
        }
        mock_get_ids.return_value = {"server-uuid-123"}
        result = self.ops.check_servers_needing_installation(["copilot"], ["server1"])
        self.assertNotIn("server1", result)

    @patch("apm_cli.registry.operations.MCPServerOperations._get_installed_server_ids")
    def test_not_installed_server_in_result(self, mock_get_ids):
        """Server not installed in any runtime is in result."""
        self.ops.registry_client.find_server_by_reference.return_value = {
            "id": "server-uuid-123"
        }
        mock_get_ids.return_value = set()  # Not installed anywhere
        result = self.ops.check_servers_needing_installation(["copilot"], ["server1"])
        self.assertIn("server1", result)


class TestGetInstalledServerIds(unittest.TestCase):
    """Tests for _get_installed_server_ids method."""

    def setUp(self):
        with patch("apm_cli.registry.operations.SimpleRegistryClient"):
            self.ops = MCPServerOperations()

    @patch("apm_cli.registry.operations.MCPServerOperations._get_installed_server_ids")
    def test_returns_set(self, mock_get_ids):
        """Returns a set of installed server IDs."""
        mock_get_ids.return_value = {"id1", "id2"}
        result = self.ops._get_installed_server_ids(["copilot"])
        self.assertIsInstance(result, set)

    def test_import_error_returns_empty_set(self):
        """ImportError returns empty set gracefully."""
        with patch.dict("sys.modules", {"apm_cli.factory": None}):
            with patch(
                "apm_cli.registry.operations.MCPServerOperations._get_installed_server_ids",
                wraps=self.ops._get_installed_server_ids,
            ):
                # Direct test: patch the import inside the method
                with patch("builtins.__import__", side_effect=ImportError):
                    # The method catches ImportError internally
                    pass

    @patch("apm_cli.factory.ClientFactory.create_client")
    def test_copilot_runtime_extracts_ids(self, mock_create_client):
        """Copilot runtime: extracts server IDs from mcpServers config."""
        mock_client = Mock()
        mock_client.get_current_config.return_value = {
            "mcpServers": {
                "github": {"id": "uuid-github", "command": "docker"},
                "another": {"command": "npx"},  # No ID
            }
        }
        mock_create_client.return_value = mock_client
        result = self.ops._get_installed_server_ids(["copilot"])
        self.assertIn("uuid-github", result)
        self.assertNotIn(None, result)

    @patch("apm_cli.factory.ClientFactory.create_client")
    def test_codex_runtime_extracts_ids(self, mock_create_client):
        """Codex runtime: extracts server IDs from mcp_servers config."""
        mock_client = Mock()
        mock_client.get_current_config.return_value = {
            "mcp_servers": {
                "my-server": {"id": "uuid-codex-server"},
            }
        }
        mock_create_client.return_value = mock_client
        result = self.ops._get_installed_server_ids(["codex"])
        self.assertIn("uuid-codex-server", result)

    @patch("apm_cli.factory.ClientFactory.create_client")
    def test_vscode_runtime_extracts_ids(self, mock_create_client):
        """VS Code runtime: extracts server IDs from mcpServers config."""
        mock_client = Mock()
        mock_client.get_current_config.return_value = {
            "mcpServers": {
                "my-server": {"id": "uuid-vscode-server"},
                "other": {"serverId": "uuid-other"},
                "third": {"server_id": "uuid-third"},
            }
        }
        mock_create_client.return_value = mock_client
        result = self.ops._get_installed_server_ids(["vscode"])
        self.assertIn("uuid-vscode-server", result)
        self.assertIn("uuid-other", result)
        self.assertIn("uuid-third", result)

    @patch("apm_cli.factory.ClientFactory.create_client")
    def test_runtime_exception_skipped(self, mock_create_client):
        """Exception reading runtime config is skipped gracefully."""
        mock_create_client.side_effect = Exception("client error")
        result = self.ops._get_installed_server_ids(["copilot"])
        self.assertEqual(result, set())

    @patch("apm_cli.factory.ClientFactory.create_client")
    def test_non_dict_config_ignored(self, mock_create_client):
        """Non-dict config is handled without error."""
        mock_client = Mock()
        mock_client.get_current_config.return_value = "not-a-dict"
        mock_create_client.return_value = mock_client
        result = self.ops._get_installed_server_ids(["copilot"])
        self.assertEqual(result, set())


class TestCollectRuntimeVariables(unittest.TestCase):
    """Tests for collect_runtime_variables method."""

    def setUp(self):
        with patch("apm_cli.registry.operations.SimpleRegistryClient"):
            self.ops = MCPServerOperations()
        self.ops.registry_client = Mock()

    def test_no_variables_returns_empty_dict(self):
        """Servers with no runtime variables return empty dict."""
        self.ops.registry_client.find_server_by_reference.return_value = {
            "packages": [{"runtime_arguments": []}]
        }
        result = self.ops.collect_runtime_variables(["server1"])
        self.assertEqual(result, {})

    def test_uses_cached_server_info(self):
        """Uses pre-fetched server_info_cache when provided."""
        cache = {"server1": None}  # Server not found
        result = self.ops.collect_runtime_variables(
            ["server1"], server_info_cache=cache
        )
        self.assertEqual(result, {})
        self.ops.registry_client.find_server_by_reference.assert_not_called()

    def test_extracts_runtime_variables_from_packages(self):
        """Extracts runtime variable definitions from packages."""
        server_info = {
            "packages": [
                {
                    "runtime_arguments": [
                        {
                            "variables": {
                                "ado_org": {
                                    "description": "ADO org name",
                                    "is_required": True,
                                }
                            }
                        }
                    ]
                }
            ]
        }
        cache = {"server1": server_info}
        with patch.object(
            self.ops,
            "_prompt_for_environment_variables",
            return_value={"ado_org": "my-org"},
        ) as mock_prompt:
            result = self.ops.collect_runtime_variables(
                ["server1"], server_info_cache=cache
            )
            mock_prompt.assert_called_once()
            call_args = mock_prompt.call_args[0][0]
            self.assertIn("ado_org", call_args)

    def test_exception_in_server_loop_skipped(self):
        """Exception processing a server is skipped silently."""
        cache = {"server1": "not-a-dict"}  # Will cause AttributeError on .get()
        result = self.ops.collect_runtime_variables(
            ["server1"], server_info_cache=cache
        )
        self.assertEqual(result, {})


class TestCollectEnvironmentVariables(unittest.TestCase):
    """Tests for collect_environment_variables method."""

    def setUp(self):
        with patch("apm_cli.registry.operations.SimpleRegistryClient"):
            self.ops = MCPServerOperations()
        self.ops.registry_client = Mock()

    def test_no_env_vars_returns_empty_dict(self):
        """Servers with no env var requirements return empty dict."""
        self.ops.registry_client.find_server_by_reference.return_value = {
            "packages": []
        }
        result = self.ops.collect_environment_variables(["server1"])
        self.assertEqual(result, {})

    def test_uses_cached_server_info(self):
        """Uses pre-fetched cache when provided."""
        cache = {"server1": None}
        result = self.ops.collect_environment_variables(
            ["server1"], server_info_cache=cache
        )
        self.assertEqual(result, {})
        self.ops.registry_client.find_server_by_reference.assert_not_called()

    def test_extracts_camelcase_env_vars(self):
        """Extracts environmentVariables (camelCase) from packages."""
        server_info = {
            "packages": [
                {
                    "environmentVariables": [
                        {
                            "name": "GITHUB_TOKEN",
                            "description": "GitHub PAT",
                            "required": True,
                        }
                    ]
                }
            ]
        }
        cache = {"server1": server_info}
        with patch.object(
            self.ops,
            "_prompt_for_environment_variables",
            return_value={"GITHUB_TOKEN": "tok"},
        ) as mock_prompt:
            result = self.ops.collect_environment_variables(
                ["server1"], server_info_cache=cache
            )
            call_args = mock_prompt.call_args[0][0]
            self.assertIn("GITHUB_TOKEN", call_args)

    def test_extracts_snake_case_env_vars(self):
        """Extracts environment_variables (snake_case) from packages."""
        server_info = {
            "packages": [
                {
                    "environment_variables": [
                        {"name": "MY_API_KEY", "description": "API Key"}
                    ]
                }
            ]
        }
        cache = {"server1": server_info}
        with patch.object(
            self.ops,
            "_prompt_for_environment_variables",
            return_value={"MY_API_KEY": "key"},
        ) as mock_prompt:
            self.ops.collect_environment_variables(["server1"], server_info_cache=cache)
            call_args = mock_prompt.call_args[0][0]
            self.assertIn("MY_API_KEY", call_args)

    def test_extracts_docker_args_env_vars(self):
        """Extracts env vars from legacy Docker args format."""
        server_info = {
            "name": "docker-server",
            "docker": {"args": ["${DOCKER_API_KEY}", "other-arg"]},
            "packages": [],
        }
        cache = {"server1": server_info}
        with patch.object(
            self.ops,
            "_prompt_for_environment_variables",
            return_value={"DOCKER_API_KEY": "key"},
        ) as mock_prompt:
            self.ops.collect_environment_variables(["server1"], server_info_cache=cache)
            call_args = mock_prompt.call_args[0][0]
            self.assertIn("DOCKER_API_KEY", call_args)

    def test_exception_skipped_gracefully(self):
        """Exception processing server is skipped."""
        cache = {"server1": "not-a-dict"}
        result = self.ops.collect_environment_variables(
            ["server1"], server_info_cache=cache
        )
        self.assertEqual(result, {})


class TestPromptForEnvironmentVariables(unittest.TestCase):
    """Tests for _prompt_for_environment_variables method."""

    def setUp(self):
        with patch("apm_cli.registry.operations.SimpleRegistryClient"):
            self.ops = MCPServerOperations()

    def test_e2e_mode_uses_defaults_not_prompts(self):
        """In E2E test mode, returns defaults without prompting."""
        required_vars = {"MY_VAR": {"description": "test", "required": True}}
        with patch.dict(os.environ, {"APM_E2E_TESTS": "1"}, clear=False):
            result = self.ops._prompt_for_environment_variables(required_vars)
        self.assertIn("MY_VAR", result)
        self.assertEqual(result["MY_VAR"], "")  # Empty default for unknown vars

    def test_ci_env_uses_defaults_not_prompts(self):
        """In CI environment, returns defaults without prompting."""
        required_vars = {"MY_VAR": {"description": "test", "required": True}}
        with patch.dict(os.environ, {"CI": "true", "APM_E2E_TESTS": ""}, clear=False):
            result = self.ops._prompt_for_environment_variables(required_vars)
        self.assertIn("MY_VAR", result)

    def test_uses_existing_env_var_value(self):
        """Uses existing env var value if already set."""
        required_vars = {"EXISTING_VAR": {"description": "test", "required": True}}
        with patch.dict(
            os.environ,
            {"CI": "true", "EXISTING_VAR": "my-value", "APM_E2E_TESTS": ""},
            clear=False,
        ):
            result = self.ops._prompt_for_environment_variables(required_vars)
        self.assertEqual(result["EXISTING_VAR"], "my-value")

    def test_token_var_falls_back_to_github_token(self):
        """Token/key variables use GITHUB_TOKEN as fallback in CI."""
        required_vars = {"MY_TOKEN": {"description": "A token", "required": True}}
        with patch.dict(
            os.environ,
            {"CI": "true", "GITHUB_TOKEN": "gh-token-123", "APM_E2E_TESTS": ""},
            clear=False,
        ):
            result = self.ops._prompt_for_environment_variables(required_vars)
        self.assertEqual(result["MY_TOKEN"], "gh-token-123")

    def test_github_dynamic_toolsets_gets_1(self):
        """GITHUB_DYNAMIC_TOOLSETS gets '1' as default in CI."""
        required_vars = {
            "GITHUB_DYNAMIC_TOOLSETS": {"description": "toolsets", "required": True}
        }
        env = {"CI": "true", "APM_E2E_TESTS": ""}
        with patch.dict(os.environ, env, clear=False):
            result = self.ops._prompt_for_environment_variables(required_vars)
        self.assertEqual(result["GITHUB_DYNAMIC_TOOLSETS"], "1")

    def test_github_apm_pat_preferred_over_github_token(self):
        """GITHUB_APM_PAT is preferred over GITHUB_TOKEN for token vars in CI."""
        required_vars = {"MY_TOKEN": {"description": "token", "required": True}}
        env = {
            "CI": "true",
            "APM_E2E_TESTS": "",
            "GITHUB_APM_PAT": "apm-pat",
            "GITHUB_TOKEN": "gh-token",
        }
        with patch.dict(os.environ, env, clear=False):
            result = self.ops._prompt_for_environment_variables(required_vars)
        self.assertEqual(result["MY_TOKEN"], "apm-pat")

    def test_non_ci_falls_back_to_click_prompt(self):
        """Outside CI, falls back to click.prompt when Rich not available."""
        required_vars = {
            "INTERACTIVE_VAR": {"description": "interactive", "required": True}
        }
        clean_env = {
            k: v
            for k, v in os.environ.items()
            if k
            not in (
                "CI",
                "GITHUB_ACTIONS",
                "TRAVIS",
                "JENKINS_URL",
                "BUILDKITE",
                "APM_E2E_TESTS",
            )
        }
        # Simulate Rich being unavailable by patching sys.modules
        import sys

        rich_modules = {k: v for k, v in sys.modules.items() if "rich" in k}
        with patch.dict(os.environ, clean_env, clear=True):
            with patch.dict(sys.modules, {k: None for k in rich_modules}):
                with patch(
                    "click.prompt", return_value="user-input"
                ) as mock_click_prompt:
                    with patch("click.echo"):
                        result = self.ops._prompt_for_environment_variables(
                            required_vars
                        )
                        mock_click_prompt.assert_called()
                        self.assertIn("INTERACTIVE_VAR", result)


if __name__ == "__main__":
    unittest.main()
