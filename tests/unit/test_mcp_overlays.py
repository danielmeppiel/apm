"""Tests for MCP overlay functionality: MCPDependency model, self-defined server
info building, overlay application, and install flow integration."""

import pytest
from unittest.mock import patch, MagicMock

from apm_cli.models.apm_package import MCPDependency
from apm_cli.cli import (
    _build_self_defined_server_info,
    _apply_mcp_overlay,
    _install_mcp_dependencies,
    _deduplicate_mcp_deps,
)


# ---------------------------------------------------------------------------
# MCPDependency Model
# ---------------------------------------------------------------------------
class TestMCPDependencyModel:

    def test_from_string(self):
        dep = MCPDependency.from_string("io.github.github/github-mcp-server")
        assert dep.name == "io.github.github/github-mcp-server"
        assert dep.transport is None
        assert dep.env is None
        assert dep.args is None
        assert dep.version is None
        assert dep.package is None
        assert dep.headers is None
        assert dep.tools is None
        assert dep.url is None
        assert dep.command is None
        assert dep.is_registry_resolved is True
        assert dep.is_self_defined is False

    def test_from_dict_minimal(self):
        dep = MCPDependency.from_dict({"name": "my-server"})
        assert dep.name == "my-server"
        assert dep.transport is None
        assert dep.env is None

    def test_from_dict_full_overlay(self):
        dep = MCPDependency.from_dict({
            "name": "full-server",
            "transport": "stdio",
            "env": {"KEY": "value"},
            "args": ["--flag"],
            "version": "1.2.3",
            "package": "npm",
            "headers": {"X-Auth": "token"},
            "tools": ["read", "write"],
        })
        assert dep.name == "full-server"
        assert dep.transport == "stdio"
        assert dep.env == {"KEY": "value"}
        assert dep.args == ["--flag"]
        assert dep.version == "1.2.3"
        assert dep.package == "npm"
        assert dep.headers == {"X-Auth": "token"}
        assert dep.tools == ["read", "write"]

    def test_from_dict_self_defined_http(self):
        dep = MCPDependency.from_dict({
            "name": "acme-kb",
            "registry": False,
            "transport": "http",
            "url": "http://localhost:8080",
        })
        assert dep.is_self_defined is True
        assert dep.is_registry_resolved is False
        assert dep.transport == "http"
        assert dep.url == "http://localhost:8080"

    def test_from_dict_self_defined_stdio(self):
        dep = MCPDependency.from_dict({
            "name": "my-local",
            "registry": False,
            "transport": "stdio",
            "command": "my-mcp-server",
        })
        assert dep.is_self_defined is True
        assert dep.transport == "stdio"
        assert dep.command == "my-mcp-server"

    def test_from_dict_legacy_type_mapped_to_transport(self):
        dep = MCPDependency.from_dict({"name": "x", "type": "stdio"})
        assert dep.transport == "stdio"

    def test_validate_self_defined_missing_transport(self):
        with pytest.raises(ValueError, match="requires 'transport'"):
            MCPDependency.from_dict({"name": "x", "registry": False})

    def test_validate_self_defined_http_missing_url(self):
        with pytest.raises(ValueError, match="requires 'url'"):
            MCPDependency.from_dict({
                "name": "x",
                "registry": False,
                "transport": "http",
            })

    def test_validate_self_defined_stdio_missing_command(self):
        with pytest.raises(ValueError, match="requires 'command'"):
            MCPDependency.from_dict({
                "name": "x",
                "registry": False,
                "transport": "stdio",
            })

    def test_to_dict_roundtrip(self):
        dep = MCPDependency(
            name="rt-server",
            transport="sse",
            env={"A": "1"},
            args={"org": "my-org"},
            version="2.0.0",
            package="npm",
            headers={"X-H": "v"},
            tools=["tool1"],
            url="http://example.com",
            command="cmd",
        )
        d = dep.to_dict()
        assert d["name"] == "rt-server"
        assert d["transport"] == "sse"
        assert d["env"] == {"A": "1"}
        assert d["args"] == {"org": "my-org"}
        assert d["version"] == "2.0.0"
        assert d["package"] == "npm"
        assert d["headers"] == {"X-H": "v"}
        assert d["tools"] == ["tool1"]
        assert d["url"] == "http://example.com"
        assert d["command"] == "cmd"

        dep2 = MCPDependency.from_dict(d)
        assert dep2.name == dep.name
        assert dep2.transport == dep.transport
        assert dep2.env == dep.env

    def test_to_dict_excludes_none_fields(self):
        dep = MCPDependency.from_string("simple-server")
        d = dep.to_dict()
        assert d == {"name": "simple-server"}

    def test_args_accepts_list(self):
        dep = MCPDependency.from_dict({"name": "x", "args": ["--port", "8080"]})
        assert dep.args == ["--port", "8080"]
        assert isinstance(dep.args, list)

    def test_args_accepts_dict(self):
        dep = MCPDependency.from_dict({"name": "x", "args": {"org": "my-org"}})
        assert dep.args == {"org": "my-org"}
        assert isinstance(dep.args, dict)

    # -- __str__ / __repr__ --------------------------------------------------

    def test_str_with_transport(self):
        dep = MCPDependency(name="my-srv", transport="stdio")
        assert str(dep) == "my-srv (stdio)"

    def test_str_without_transport(self):
        dep = MCPDependency(name="my-srv")
        assert str(dep) == "my-srv"

    def test_repr_does_not_leak_env(self):
        dep = MCPDependency(
            name="leaky", transport="stdio",
            env={"SECRET": "s3cret"}, headers={"Authorization": "Bearer token"},
        )
        r = repr(dep)
        assert "s3cret" not in r
        assert "Bearer" not in r
        assert "MCPDependency(leaky (stdio))" == r

    # -- transport validation ------------------------------------------------

    def test_validate_invalid_transport_rejected(self):
        with pytest.raises(ValueError, match="unsupported transport"):
            MCPDependency.from_dict(
                {"name": "x", "registry": False, "transport": "foo", "command": "cmd"}
            )

    def test_validate_valid_transports_accepted(self):
        for t in ("stdio", "sse", "http", "streamable-http"):
            dep = MCPDependency(name="x", transport=t)
            # Should not raise for registry-resolved deps (no extra required fields)
            dep.validate()


# ---------------------------------------------------------------------------
# _build_self_defined_server_info
# ---------------------------------------------------------------------------
class TestBuildSelfDefinedServerInfo:

    def test_http_transport_builds_remote(self):
        dep = MCPDependency(
            name="http-srv", registry=False, transport="http",
            url="http://example.com",
        )
        result = _build_self_defined_server_info(dep)
        assert "remotes" in result
        assert len(result["remotes"]) == 1
        assert result["remotes"][0]["url"] == "http://example.com"
        assert result["remotes"][0]["transport_type"] == "http"
        assert "packages" not in result

    def test_sse_transport_builds_remote(self):
        dep = MCPDependency(
            name="sse-srv", registry=False, transport="sse",
            url="http://example.com/sse",
        )
        result = _build_self_defined_server_info(dep)
        assert "remotes" in result
        assert result["remotes"][0]["transport_type"] == "sse"
        assert result["remotes"][0]["url"] == "http://example.com/sse"

    def test_stdio_transport_builds_package(self):
        dep = MCPDependency(
            name="stdio-srv", registry=False, transport="stdio",
            command="my-cmd",
        )
        result = _build_self_defined_server_info(dep)
        assert "packages" in result
        assert len(result["packages"]) == 1
        assert result["packages"][0]["runtime_hint"] == "my-cmd"
        assert "remotes" not in result

    def test_http_with_headers(self):
        dep = MCPDependency(
            name="hdr-srv", registry=False, transport="http",
            url="http://example.com",
            headers={"Authorization": "Bearer token"},
        )
        result = _build_self_defined_server_info(dep)
        headers = result["remotes"][0]["headers"]
        assert len(headers) == 1
        assert headers[0] == {"name": "Authorization", "value": "Bearer token"}

    def test_stdio_with_env(self):
        dep = MCPDependency(
            name="env-srv", registry=False, transport="stdio",
            command="x", env={"KEY": "val"},
        )
        result = _build_self_defined_server_info(dep)
        env_vars = result["packages"][0]["environment_variables"]
        assert len(env_vars) == 1
        assert env_vars[0]["name"] == "KEY"

    def test_stdio_with_list_args(self):
        dep = MCPDependency(
            name="args-srv", registry=False, transport="stdio",
            command="npx", args=["-y", "pkg"],
        )
        result = _build_self_defined_server_info(dep)
        runtime_args = result["packages"][0]["runtime_arguments"]
        assert len(runtime_args) == 2
        assert runtime_args[0]["value_hint"] == "-y"
        assert runtime_args[1]["value_hint"] == "pkg"

    def test_tools_override_embedded(self):
        dep = MCPDependency(
            name="tools-srv", registry=False, transport="stdio",
            command="cmd", tools=["read", "write"],
        )
        result = _build_self_defined_server_info(dep)
        assert result["_apm_tools_override"] == ["read", "write"]

    def test_no_tools_no_key(self):
        dep = MCPDependency(
            name="no-tools", registry=False, transport="stdio",
            command="cmd",
        )
        result = _build_self_defined_server_info(dep)
        assert "_apm_tools_override" not in result


# ---------------------------------------------------------------------------
# _apply_mcp_overlay
# ---------------------------------------------------------------------------
class TestApplyMCPOverlay:

    def test_transport_stdio_removes_remotes(self):
        cache = {
            "srv": {
                "packages": [{"registry_name": "npm", "runtime_hint": "npx"}],
                "remotes": [{"url": "http://x", "transport_type": "http"}],
            }
        }
        dep = MCPDependency(name="srv", transport="stdio")
        _apply_mcp_overlay(cache, dep)
        assert "remotes" not in cache["srv"]
        assert "packages" in cache["srv"]

    def test_transport_http_removes_packages(self):
        cache = {
            "srv": {
                "packages": [{"registry_name": "npm", "runtime_hint": "npx"}],
                "remotes": [{"url": "http://x", "transport_type": "http"}],
            }
        }
        dep = MCPDependency(name="srv", transport="http")
        _apply_mcp_overlay(cache, dep)
        assert "packages" not in cache["srv"]
        assert "remotes" in cache["srv"]

    def test_package_type_filters(self):
        cache = {
            "srv": {
                "packages": [
                    {"registry_name": "npm", "runtime_hint": "npx"},
                    {"registry_name": "pypi", "runtime_hint": "pip"},
                ],
            }
        }
        dep = MCPDependency(name="srv", package="npm")
        _apply_mcp_overlay(cache, dep)
        assert len(cache["srv"]["packages"]) == 1
        assert cache["srv"]["packages"][0]["registry_name"] == "npm"

    def test_headers_merged_into_remotes(self):
        cache = {
            "srv": {
                "remotes": [{"url": "http://x", "headers": []}],
            }
        }
        dep = MCPDependency(name="srv", headers={"X-Custom": "val"})
        _apply_mcp_overlay(cache, dep)
        headers = cache["srv"]["remotes"][0]["headers"]
        assert len(headers) == 1
        assert headers[0] == {"name": "X-Custom", "value": "val"}

    def test_tools_embedded(self):
        cache = {"srv": {"packages": [{"registry_name": "npm"}]}}
        dep = MCPDependency(name="srv", tools=["repos"])
        _apply_mcp_overlay(cache, dep)
        assert cache["srv"]["_apm_tools_override"] == ["repos"]

    def test_no_overlay_no_change(self):
        original = {"packages": [{"registry_name": "npm", "runtime_hint": "npx"}]}
        cache = {"srv": original.copy()}
        dep = MCPDependency(name="srv")
        _apply_mcp_overlay(cache, dep)
        assert cache["srv"]["packages"] == original["packages"]

    def test_missing_server_info_noop(self):
        cache = {}
        dep = MCPDependency(name="nonexistent", transport="stdio")
        # Should not raise
        _apply_mcp_overlay(cache, dep)
        assert cache == {}

    def test_args_list_merged_into_packages(self):
        cache = {
            "srv": {
                "packages": [{"registry_name": "npm", "runtime_hint": "npx"}],
            }
        }
        dep = MCPDependency(name="srv", args=["--org", "acme"])
        _apply_mcp_overlay(cache, dep)
        rt_args = cache["srv"]["packages"][0]["runtime_arguments"]
        assert len(rt_args) == 2
        assert rt_args[0]["value_hint"] == "--org"
        assert rt_args[1]["value_hint"] == "acme"

    def test_args_dict_merged_into_packages(self):
        cache = {
            "srv": {
                "packages": [{"registry_name": "npm", "runtime_hint": "npx"}],
            }
        }
        dep = MCPDependency(name="srv", args={"org": "acme"})
        _apply_mcp_overlay(cache, dep)
        rt_args = cache["srv"]["packages"][0]["runtime_arguments"]
        assert len(rt_args) == 1
        assert rt_args[0]["value_hint"] == "--org=acme"


# ---------------------------------------------------------------------------
# Install Flow Integration (with mocking)
# ---------------------------------------------------------------------------
class TestInstallMCPDepsWithOverlays:

    @patch("apm_cli.cli._install_for_runtime")
    @patch("apm_cli.cli._get_console", return_value=None)
    def test_self_defined_deps_skip_registry_validation(
        self, _console, mock_install_runtime
    ):
        dep = MCPDependency(
            name="my-local", registry=False, transport="stdio", command="my-cmd",
        )

        count = _install_mcp_dependencies([dep], runtime="vscode")

        # Self-defined deps should NOT go through registry validation
        # (MCPServerOperations is never instantiated for self-defined-only lists)
        mock_install_runtime.assert_called_once()
        call_args = mock_install_runtime.call_args
        # First positional arg is runtime, second is dep list
        assert call_args[0][0] == "vscode"
        assert call_args[0][1] == ["my-local"]
        # Fourth positional arg is server_info_cache with synthetic info
        server_cache = call_args[0][3]
        assert "my-local" in server_cache
        assert "packages" in server_cache["my-local"]
        assert count == 1

    @patch("apm_cli.cli._install_for_runtime")
    @patch("apm_cli.cli._get_console", return_value=None)
    @patch("apm_cli.registry.operations.MCPServerOperations")
    def test_registry_deps_use_dep_names(
        self, mock_ops_cls, _console, mock_install_runtime
    ):
        mock_ops = mock_ops_cls.return_value
        mock_ops.validate_servers_exist.return_value = (
            ["github/github-mcp-server"], []
        )
        mock_ops.check_servers_needing_installation.return_value = [
            "github/github-mcp-server"
        ]
        mock_ops.batch_fetch_server_info.return_value = {
            "github/github-mcp-server": {}
        }
        mock_ops.collect_environment_variables.return_value = {}
        mock_ops.collect_runtime_variables.return_value = {}

        dep = MCPDependency.from_string("github/github-mcp-server")
        count = _install_mcp_dependencies([dep], runtime="vscode")

        mock_ops.validate_servers_exist.assert_called_once_with(
            ["github/github-mcp-server"]
        )
        assert count == 1

    @patch("apm_cli.cli._install_for_runtime")
    @patch("apm_cli.cli._get_console", return_value=None)
    @patch("apm_cli.registry.operations.MCPServerOperations")
    def test_mixed_deps_both_paths(
        self, mock_ops_cls, _console, mock_install_runtime
    ):
        mock_ops = mock_ops_cls.return_value
        mock_ops.validate_servers_exist.return_value = (
            ["github/github-mcp-server"], []
        )
        mock_ops.check_servers_needing_installation.return_value = [
            "github/github-mcp-server"
        ]
        mock_ops.batch_fetch_server_info.return_value = {
            "github/github-mcp-server": {}
        }
        mock_ops.collect_environment_variables.return_value = {}
        mock_ops.collect_runtime_variables.return_value = {}

        registry_dep = MCPDependency.from_string("github/github-mcp-server")
        self_defined_dep = MCPDependency(
            name="my-local", registry=False, transport="stdio", command="my-cmd",
        )

        count = _install_mcp_dependencies(
            [registry_dep, self_defined_dep], runtime="vscode"
        )

        # Registry dep goes through validation
        mock_ops.validate_servers_exist.assert_called_once_with(
            ["github/github-mcp-server"]
        )
        # Both deps result in _install_for_runtime calls (1 registry + 1 self-defined)
        assert mock_install_runtime.call_count == 2
        assert count == 2
