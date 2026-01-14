"""Tests for custom GitHub host support (GITHUB_HOST environment variable)."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from apm_cli.deps.github_downloader import GitHubPackageDownloader
from apm_cli.models.apm_package import DependencyReference
from apm_cli.utils.github_host import is_supported_git_host, is_valid_fqdn


class TestCustomGitHubHost:
    """Test cases for custom GitHub Server instances via GITHUB_HOST."""
    
    def test_is_valid_fqdn_for_custom_hosts(self):
        """Test FQDN validation for custom GitHub hosts."""
        # Valid custom GitHub hosts
        assert is_valid_fqdn("github.company.com")
        assert is_valid_fqdn("github.whatever.com")
        assert is_valid_fqdn("git.internal.corp")
        assert is_valid_fqdn("code.enterprise.io")
        
        # Invalid hosts
        assert not is_valid_fqdn("localhost")
        assert not is_valid_fqdn("single")
        assert not is_valid_fqdn("")
        assert not is_valid_fqdn(None)
    
    def test_is_supported_git_host_with_custom_domain(self):
        """Test that custom domains are supported when they are valid FQDNs."""
        # Custom GitHub Server instances should be supported
        assert is_supported_git_host("github.company.com")
        assert is_supported_git_host("github.whatever.com")
        assert is_supported_git_host("git.internal.corp")
        
        # Standard hosts still work
        assert is_supported_git_host("github.com")
        assert is_supported_git_host("company.ghe.com")
        assert is_supported_git_host("dev.azure.com")
    
    def test_is_supported_git_host_respects_github_host_env(self, monkeypatch):
        """Test that GITHUB_HOST env var makes the configured host supported."""
        monkeypatch.setenv("GITHUB_HOST", "custom.internal.server")
        
        # The configured host should be supported
        assert is_supported_git_host("custom.internal.server")
        
        # Other valid FQDNs should also be supported
        assert is_supported_git_host("another.server.com")
        
        monkeypatch.delenv("GITHUB_HOST", raising=False)
    
    def test_parse_package_with_custom_github_host(self):
        """Test parsing package spec with custom GitHub domain."""
        # Explicit custom domain in package path
        dep = DependencyReference.parse("github.company.com/team/internal-repo")
        assert dep.host == "github.company.com"
        assert dep.repo_url == "team/internal-repo"
        
        # Another custom domain
        dep2 = DependencyReference.parse("git.enterprise.io/org/package")
        assert dep2.host == "git.enterprise.io"
        assert dep2.repo_url == "org/package"
    
    def test_parse_package_with_github_host_env(self, monkeypatch):
        """Test parsing bare package name uses GITHUB_HOST."""
        monkeypatch.setenv("GITHUB_HOST", "github.company.com")
        
        # Bare package name should use GITHUB_HOST
        dep = DependencyReference.parse("team/internal-repo")
        # Parse sets host to default_host() which reads GITHUB_HOST
        # The actual host assignment happens during download
        assert dep.repo_url == "team/internal-repo"
        
        monkeypatch.delenv("GITHUB_HOST", raising=False)
    
    @patch('requests.get')
    def test_download_file_with_custom_github_server(self, mock_get):
        """Test downloading file from custom GitHub Server uses correct API format."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"file content"
        mock_get.return_value = mock_response
        
        downloader = GitHubPackageDownloader()
        
        # Create dependency reference with custom host
        dep_ref = DependencyReference(
            repo_url="team/internal-repo",
            host="github.company.com"
        )
        
        # Download a file
        content = downloader._download_github_file(dep_ref, "apm.yml", "main")
        
        # Verify correct API URL format for GitHub Enterprise Server
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        api_url = call_args[0][0]
        
        # Should use GitHub Enterprise Server format: https://{host}/api/v3/repos/...
        assert "github.company.com/api/v3/repos/team/internal-repo/contents/apm.yml" in api_url
        assert "api.github.company.com" not in api_url  # Should NOT use this format
        assert content == b"file content"
    
    @patch('requests.get')
    def test_download_file_with_github_dot_whatever(self, mock_get):
        """Test downloading from github.whatever.com uses GitHub Server API format."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"test content"
        mock_get.return_value = mock_response
        
        downloader = GitHubPackageDownloader()
        
        # Create dependency reference with github.whatever.com
        dep_ref = DependencyReference(
            repo_url="owner/repo",
            host="github.whatever.com"
        )
        
        # Download a file
        content = downloader._download_github_file(dep_ref, "README.md", "main")
        
        # Verify correct API URL format
        call_args = mock_get.call_args
        api_url = call_args[0][0]
        
        # Should use GitHub Enterprise Server format
        assert "github.whatever.com/api/v3/repos/owner/repo/contents/README.md" in api_url
        assert content == b"test content"
    
    @patch('requests.get')
    def test_download_file_fallback_with_custom_host(self, mock_get):
        """Test branch fallback (main->master) works with custom GitHub host."""
        # First call (main) returns 404, second call (master) succeeds
        mock_404 = Mock()
        mock_404.status_code = 404
        mock_404.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_404)
        
        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.content = b"fallback content"
        
        mock_get.side_effect = [mock_404, mock_success]
        
        downloader = GitHubPackageDownloader()
        
        dep_ref = DependencyReference(
            repo_url="team/repo",
            host="git.internal.corp"
        )
        
        # Download with main ref (should fallback to master)
        content = downloader._download_github_file(dep_ref, "apm.yml", "main")
        
        # Should have made two calls
        assert mock_get.call_count == 2
        
        # First call should try main
        first_call_url = mock_get.call_args_list[0][0][0]
        assert "ref=main" in first_call_url
        assert "git.internal.corp/api/v3" in first_call_url
        
        # Second call should try master with same host
        second_call_url = mock_get.call_args_list[1][0][0]
        assert "ref=master" in second_call_url
        assert "git.internal.corp/api/v3" in second_call_url
        
        assert content == b"fallback content"
    
    @patch('requests.get')
    def test_github_com_still_uses_correct_api_format(self, mock_get):
        """Ensure github.com still uses api.github.com format (regression test)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"content"
        mock_get.return_value = mock_response
        
        downloader = GitHubPackageDownloader()
        
        dep_ref = DependencyReference(
            repo_url="owner/repo",
            host="github.com"
        )
        
        content = downloader._download_github_file(dep_ref, "file.txt", "main")
        
        call_args = mock_get.call_args
        api_url = call_args[0][0]
        
        # Should use api.github.com format, NOT github.com/api/v3
        assert "api.github.com/repos/owner/repo" in api_url
        assert "github.com/api/v3" not in api_url
    
    @patch('requests.get')
    def test_ghe_com_still_uses_correct_api_format(self, mock_get):
        """Ensure .ghe.com hosts use api.{host} format (regression test)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"content"
        mock_get.return_value = mock_response
        
        downloader = GitHubPackageDownloader()
        
        dep_ref = DependencyReference(
            repo_url="owner/repo",
            host="myorg.ghe.com"
        )
        
        content = downloader._download_github_file(dep_ref, "file.txt", "main")
        
        call_args = mock_get.call_args
        api_url = call_args[0][0]
        
        # Should use api.myorg.ghe.com format
        assert "api.myorg.ghe.com/repos/owner/repo" in api_url
        assert "myorg.ghe.com/api/v3" not in api_url
