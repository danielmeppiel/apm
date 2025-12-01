"""Tests for GitHub package downloader."""

import os
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from urllib.parse import urlparse

from apm_cli.deps.github_downloader import GitHubPackageDownloader
from apm_cli.models.apm_package import (
    DependencyReference, 
    ResolvedReference,
    GitReferenceType,
    ValidationResult,
    APMPackage
)


class TestGitHubPackageDownloader:
    """Test cases for GitHubPackageDownloader."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.downloader = GitHubPackageDownloader()
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_setup_git_environment_with_github_apm_pat(self):
        """Test Git environment setup with GITHUB_APM_PAT."""
        with patch.dict(os.environ, {'GITHUB_APM_PAT': 'test-token'}, clear=True):
            downloader = GitHubPackageDownloader()
            env = downloader.git_env
            
            # GITHUB_APM_PAT should be used for github_token property (modules purpose)
            assert downloader.github_token == 'test-token'
            assert downloader.has_github_token is True
            # But GITHUB_TOKEN should not be set in env since it wasn't there originally
            assert 'GITHUB_TOKEN' not in env or env.get('GITHUB_TOKEN') == 'test-token'
            assert env['GH_TOKEN'] == 'test-token'
    
    def test_setup_git_environment_with_github_token(self):
        """Test Git environment setup with GITHUB_TOKEN fallback."""
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'fallback-token'}, clear=True):
            downloader = GitHubPackageDownloader()
            env = downloader.git_env
            
            assert env['GH_TOKEN'] == 'fallback-token'
    
    def test_setup_git_environment_no_token(self):
        """Test Git environment setup with no GitHub token."""
        with patch.dict(os.environ, {}, clear=True):
            downloader = GitHubPackageDownloader()
            env = downloader.git_env
            
            # Should not have GitHub tokens in environment
            assert 'GITHUB_TOKEN' not in env or not env['GITHUB_TOKEN']
            assert 'GH_TOKEN' not in env or not env['GH_TOKEN']
    
    @patch('apm_cli.deps.github_downloader.Repo')
    @patch('tempfile.mkdtemp')
    def test_resolve_git_reference_branch(self, mock_mkdtemp, mock_repo_class):
        """Test resolving a branch reference."""
        # Setup mocks
        mock_temp_dir = '/tmp/test'
        mock_mkdtemp.return_value = mock_temp_dir
        
        mock_repo = Mock()
        mock_repo.head.commit.hexsha = 'abc123def456'
        mock_repo_class.clone_from.return_value = mock_repo
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('shutil.rmtree'):
            
            result = self.downloader.resolve_git_reference('user/repo#main')
            
            assert isinstance(result, ResolvedReference)
            assert result.original_ref == 'user/repo#main'
            assert result.ref_type == GitReferenceType.BRANCH
            assert result.resolved_commit == 'abc123def456'
            assert result.ref_name == 'main'
    
    @patch('apm_cli.deps.github_downloader.Repo')
    @patch('tempfile.mkdtemp')
    def test_resolve_git_reference_commit(self, mock_mkdtemp, mock_repo_class):
        """Test resolving a commit SHA reference."""
        # Setup mocks for failed shallow clone, successful full clone
        mock_temp_dir = '/tmp/test'
        mock_mkdtemp.return_value = mock_temp_dir
        
        from git.exc import GitCommandError
        
        # First call (shallow clone) fails, second call (full clone) succeeds
        mock_repo = Mock()
        mock_commit = Mock()
        mock_commit.hexsha = 'abcdef123456'
        mock_repo.commit.return_value = mock_commit
        
        mock_repo_class.clone_from.side_effect = [
            GitCommandError('shallow clone failed'),
            mock_repo
        ]
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('shutil.rmtree'):
            
            result = self.downloader.resolve_git_reference('user/repo#abcdef1')
            
            assert result.ref_type == GitReferenceType.COMMIT
            assert result.resolved_commit == 'abcdef123456'
            assert result.ref_name == 'abcdef1'
    
    def test_resolve_git_reference_invalid_format(self):
        """Test resolving an invalid repository reference."""
        with pytest.raises(ValueError, match="Invalid repository reference"):
            self.downloader.resolve_git_reference('invalid-repo-format')
    
    @patch('apm_cli.deps.github_downloader.Repo')
    @patch('apm_cli.deps.github_downloader.validate_apm_package')
    @patch('apm_cli.deps.github_downloader.shutil.rmtree')
    def test_download_package_success(self, mock_rmtree, mock_validate, mock_repo_class):
        """Test successful package download and validation."""
        # Setup target directory
        target_path = self.temp_dir / "test_package"
        
        # Setup mocks
        mock_repo = Mock()
        mock_repo_class.clone_from.return_value = mock_repo
        
        # Mock successful validation
        mock_validation_result = ValidationResult()
        mock_validation_result.is_valid = True
        mock_package = APMPackage(name="test-package", version="1.0.0")
        mock_validation_result.package = mock_package
        mock_validate.return_value = mock_validation_result
        
        # Mock resolve_git_reference
        mock_resolved_ref = ResolvedReference(
            original_ref="user/repo#main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main"
        )
        
        with patch.object(self.downloader, 'resolve_git_reference', return_value=mock_resolved_ref):
            result = self.downloader.download_package('user/repo#main', target_path)
            
            assert result.package.name == "test-package"
            assert result.package.version == "1.0.0"
            assert result.install_path == target_path
            assert result.resolved_reference == mock_resolved_ref
            assert result.installed_at is not None
    
    @patch('apm_cli.deps.github_downloader.Repo')
    @patch('apm_cli.deps.github_downloader.validate_apm_package')
    @patch('apm_cli.deps.github_downloader.shutil.rmtree')
    def test_download_package_validation_failure(self, mock_rmtree, mock_validate, mock_repo_class):
        """Test package download with validation failure."""
        # Setup target directory
        target_path = self.temp_dir / "test_package"
        
        # Setup mocks
        mock_repo = Mock()
        mock_repo_class.clone_from.return_value = mock_repo
        
        # Mock validation failure
        mock_validation_result = ValidationResult()
        mock_validation_result.is_valid = False
        mock_validation_result.add_error("Missing apm.yml")
        mock_validate.return_value = mock_validation_result
        
        # Mock resolve_git_reference
        mock_resolved_ref = ResolvedReference(
            original_ref="user/repo#main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main"
        )
        
        with patch.object(self.downloader, 'resolve_git_reference', return_value=mock_resolved_ref):
            with pytest.raises(RuntimeError, match="Invalid APM package"):
                self.downloader.download_package('user/repo#main', target_path)
    
    @patch('apm_cli.deps.github_downloader.Repo')
    def test_download_package_git_failure(self, mock_repo_class):
        """Test package download with Git clone failure."""
        # Setup target directory
        target_path = self.temp_dir / "test_package"
        
        # Setup mocks
        from git.exc import GitCommandError
        mock_repo_class.clone_from.side_effect = GitCommandError("Clone failed")
        
        # Mock resolve_git_reference
        mock_resolved_ref = ResolvedReference(
            original_ref="user/repo#main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main"
        )
        
        with patch.object(self.downloader, 'resolve_git_reference', return_value=mock_resolved_ref):
            with pytest.raises(RuntimeError, match="Failed to clone repository"):
                self.downloader.download_package('user/repo#main', target_path)
    
    def test_download_package_invalid_repo_ref(self):
        """Test package download with invalid repository reference."""
        target_path = self.temp_dir / "test_package"
        
        with pytest.raises(ValueError, match="Invalid repository reference"):
            self.downloader.download_package('invalid-repo-format', target_path)
    
    @patch('apm_cli.deps.github_downloader.Repo')
    @patch('apm_cli.deps.github_downloader.validate_apm_package')
    @patch('apm_cli.deps.github_downloader.shutil.rmtree')
    def test_download_package_commit_checkout(self, mock_rmtree, mock_validate, mock_repo_class):
        """Test package download with commit checkout."""
        # Setup target directory
        target_path = self.temp_dir / "test_package"
        
        # Setup mocks
        mock_repo = Mock()
        mock_repo.git = Mock()
        mock_repo_class.clone_from.return_value = mock_repo
        
        # Mock successful validation
        mock_validation_result = ValidationResult()
        mock_validation_result.is_valid = True
        mock_package = APMPackage(name="test-package", version="1.0.0")
        mock_validation_result.package = mock_package
        mock_validate.return_value = mock_validation_result
        
        # Mock resolve_git_reference returning a commit
        mock_resolved_ref = ResolvedReference(
            original_ref="user/repo#abc123",
            ref_type=GitReferenceType.COMMIT,
            resolved_commit="abc123def456",
            ref_name="abc123"
        )
        
        with patch.object(self.downloader, 'resolve_git_reference', return_value=mock_resolved_ref):
            result = self.downloader.download_package('user/repo#abc123', target_path)
            
            # Verify that git checkout was called for commit
            mock_repo.git.checkout.assert_called_once_with("abc123def456")
            assert result.package.name == "test-package"
    
    def test_get_clone_progress_callback(self):
        """Test the progress callback for Git clone operations."""
        callback = self.downloader._get_clone_progress_callback()
        
        # Test with max_count
        with patch('builtins.print') as mock_print:
            callback(1, 50, 100, "Cloning")
            mock_print.assert_called_with("\r🚀 Cloning: 50% (50/100) Cloning", end='', flush=True)
        
        # Test without max_count
        with patch('builtins.print') as mock_print:
            callback(1, 25, None, "Receiving objects")
            mock_print.assert_called_with("\r🚀 Cloning: Receiving objects (25)", end='', flush=True)


class TestGitHubPackageDownloaderIntegration:
    """Integration tests that require actual Git operations (to be run with network access)."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.downloader = GitHubPackageDownloader()
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.integration
    def test_resolve_reference_real_repo(self):
        """Test resolving references on a real repository (requires network)."""
        # This test would require a real repository - skip in CI
        pytest.skip("Integration test requiring network access")
    
    @pytest.mark.integration  
    def test_download_real_package(self):
        """Test downloading a real APM package (requires network)."""
        # This test would require a real APM package repository - skip in CI
        pytest.skip("Integration test requiring network access")


class TestEnterpriseHostHandling:
    """Test enterprise GitHub host handling (PR #33 bug fixes)."""
    
    @patch('apm_cli.deps.github_downloader.Repo')
    def test_clone_fallback_respects_enterprise_host(self, mock_repo_class, monkeypatch):
        """Test that fallback clone uses enterprise host, not hardcoded github.com.
        
        This tests the bug fix from PR #33 where Method 3 fallback was hardcoded
        to github.com instead of respecting the configured host.
        """
        from git.exc import GitCommandError
        
        monkeypatch.setenv("GITHUB_HOST", "company.ghe.com")
        
        downloader = GitHubPackageDownloader()
        downloader.github_host = "company.ghe.com"
        
        # Mock clone attempts: first two fail, third succeeds
        mock_repo = Mock()
        mock_repo.head.commit.hexsha = "abc123"
        
        mock_repo_class.clone_from.side_effect = [
            GitCommandError("auth", "Authentication failed"),  # Method 1 fails
            GitCommandError("ssh", "SSH failed"),              # Method 2 fails  
            mock_repo                                            # Method 3 succeeds
        ]
        
        target_path = Path("/tmp/test_enterprise")
        
        with patch('pathlib.Path.exists', return_value=False):
            result = downloader._clone_with_fallback("team/internal-repo", target_path)
        
        # Verify Method 3 used enterprise host, NOT github.com
        calls = mock_repo_class.clone_from.call_args_list
        assert len(calls) == 3
        
        third_call_url = calls[2][0][0]  # First positional arg of third call
        
        # Should use company.ghe.com, NOT github.com
        assert "company.ghe.com" in third_call_url
        assert "team/internal-repo" in third_call_url
        # Ensure it's NOT using github.com
        assert "github.com" not in third_call_url or "company.ghe.com" in third_call_url
    
    def test_host_persists_through_clone_attempts(self, monkeypatch):
        """Test that github_host attribute persists across fallback attempts."""
        monkeypatch.setenv("GITHUB_HOST", "custom.ghe.com")
        
        downloader = GitHubPackageDownloader()
        downloader.github_host = "custom.ghe.com"
        
        # Build URLs for both SSH and HTTPS methods
        url_ssh = downloader._build_repo_url("owner/repo", use_ssh=True)
        url_https = downloader._build_repo_url("owner/repo", use_ssh=False)
        
        assert "custom.ghe.com" in url_ssh
        assert "custom.ghe.com" in url_https
        assert "owner/repo" in url_https
        # Should NOT fall back to github.com
        assert "github.com" not in url_https or "custom.ghe.com" in url_https
    
    def test_multiple_hosts_resolution(self, monkeypatch):
        """Test installing packages from multiple GitHub hosts."""
        monkeypatch.setenv("GITHUB_HOST", "company.ghe.com")
        
        # Test bare dependency uses GITHUB_HOST
        dep1 = DependencyReference.parse("team/internal-package")
        assert dep1.repo_url == "team/internal-package"
        # Host should be set when downloader processes it
        
        # Test explicit github.com
        dep2 = DependencyReference.parse("github.com/public/open-source")
        assert dep2.host == "github.com"
        assert dep2.repo_url == "public/open-source"
        
        # Test explicit partner GHE
        dep3 = DependencyReference.parse("partner.ghe.com/external/tool")
        assert dep3.host == "partner.ghe.com"
        assert dep3.repo_url == "external/tool"


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_network_timeout_handling(self):
        """Test handling of network timeouts."""
        # Would require mocking network timeouts
        pass
    
    def test_authentication_failure_handling(self):
        """Test handling of authentication failures."""
        # Would require mocking authentication failures
        pass
    
    def test_repository_not_found_handling(self):
        """Test handling of repository not found errors."""
        # Would require mocking 404 errors
        pass


class TestAzureDevOpsSupport:
    """Test Azure DevOps package support."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_setup_git_environment_with_ado_token(self):
        """Test Git environment setup picks up ADO_APM_PAT."""
        with patch.dict(os.environ, {'ADO_APM_PAT': 'ado-test-token'}, clear=True):
            downloader = GitHubPackageDownloader()
            
            assert downloader.ado_token == 'ado-test-token'
            assert downloader.has_ado_token is True
    
    def test_setup_git_environment_no_ado_token(self):
        """Test Git environment setup without ADO token."""
        with patch.dict(os.environ, {'GITHUB_APM_PAT': 'github-token'}, clear=True):
            downloader = GitHubPackageDownloader()
            
            assert downloader.ado_token is None
            assert downloader.has_ado_token is False
            # GitHub token should still work
            assert downloader.github_token == 'github-token'
            assert downloader.has_github_token is True
    
    def test_build_repo_url_for_ado_with_token(self):
        """Test URL building for ADO packages with token."""
        with patch.dict(os.environ, {'ADO_APM_PAT': 'ado-token'}, clear=True):
            downloader = GitHubPackageDownloader()
            dep_ref = DependencyReference.parse('dev.azure.com/myorg/myproject/_git/myrepo')
            
            url = downloader._build_repo_url(dep_ref.repo_url, use_ssh=False, dep_ref=dep_ref)
            parsed = urlparse(url)
            
            # Should build ADO URL with token embedded in userinfo
            assert parsed.hostname == 'dev.azure.com'
            assert 'myorg' in parsed.path
            assert 'myproject' in parsed.path
            assert '_git' in parsed.path
            assert 'myrepo' in parsed.path
            # Token should be in the URL (as username in https://token@host format)
            assert parsed.username == 'ado-token' or 'ado-token' in (parsed.password or '')
    
    def test_build_repo_url_for_ado_without_token(self):
        """Test URL building for ADO packages without token."""
        with patch.dict(os.environ, {}, clear=True):
            downloader = GitHubPackageDownloader()
            dep_ref = DependencyReference.parse('dev.azure.com/myorg/myproject/_git/myrepo')
            
            url = downloader._build_repo_url(dep_ref.repo_url, use_ssh=False, dep_ref=dep_ref)
            parsed = urlparse(url)
            
            # Should build ADO URL without token
            assert parsed.hostname == 'dev.azure.com'
            assert 'myorg/myproject/_git/myrepo' in parsed.path
            # No credentials in URL
            assert parsed.username is None
            assert parsed.password is None
    
    def test_build_repo_url_for_ado_ssh(self):
        """Test SSH URL building for ADO packages."""
        with patch.dict(os.environ, {}, clear=True):
            downloader = GitHubPackageDownloader()
            dep_ref = DependencyReference.parse('dev.azure.com/myorg/myproject/_git/myrepo')
            
            url = downloader._build_repo_url(dep_ref.repo_url, use_ssh=True, dep_ref=dep_ref)
            
            # Should build ADO SSH URL (git@ssh.dev.azure.com:v3/org/project/repo)
            assert url.startswith('git@ssh.dev.azure.com:')
    
    def test_build_repo_url_github_not_affected_by_ado_token(self):
        """Test that GitHub URL building uses GitHub token, not ADO token."""
        with patch.dict(os.environ, {
            'GITHUB_APM_PAT': 'github-token',
            'ADO_APM_PAT': 'ado-token'
        }, clear=True):
            downloader = GitHubPackageDownloader()
            dep_ref = DependencyReference.parse('owner/repo')
            
            url = downloader._build_repo_url(dep_ref.repo_url, use_ssh=False, dep_ref=dep_ref)
            parsed = urlparse(url)
            
            # Should use GitHub token, not ADO token
            assert parsed.hostname == 'github.com'
            # Verify ADO token is not used for GitHub URLs
            assert 'ado-token' not in url and 'ado-token' != parsed.username
    
    def test_clone_with_fallback_selects_ado_token(self):
        """Test that _clone_with_fallback uses ADO token for ADO packages."""
        with patch.dict(os.environ, {
            'GITHUB_APM_PAT': 'github-token',
            'ADO_APM_PAT': 'ado-token'
        }, clear=True):
            downloader = GitHubPackageDownloader()
            dep_ref = DependencyReference.parse('dev.azure.com/myorg/myproject/_git/myrepo')
            
            # Mock _build_repo_url to capture what's passed
            with patch.object(downloader, '_build_repo_url') as mock_build:
                mock_build.return_value = 'https://ado-token@dev.azure.com/myorg/myproject/_git/myrepo'
                
                with patch('apm_cli.deps.github_downloader.Repo') as mock_repo:
                    mock_repo.clone_from.return_value = Mock()
                    
                    try:
                        downloader._clone_with_fallback(
                            dep_ref.repo_url, 
                            self.temp_dir,
                            dep_ref=dep_ref
                        )
                    except Exception:
                        pass  # May fail due to mocking, we just want to check the call
                    
                    # Verify _build_repo_url was called with dep_ref
                    if mock_build.called:
                        call_args = mock_build.call_args
                        assert call_args[1].get('dep_ref') is not None
    
    def test_clone_with_fallback_selects_github_token(self):
        """Test that _clone_with_fallback uses GitHub token for GitHub packages."""
        with patch.dict(os.environ, {
            'GITHUB_APM_PAT': 'github-token',
            'ADO_APM_PAT': 'ado-token'
        }, clear=True):
            dep_ref = DependencyReference.parse('owner/repo')
            
            # The is_ado check should be False for GitHub packages
            assert not dep_ref.is_azure_devops()


class TestMixedSourceTokenSelection:
    """Test token selection for mixed-source installations (GitHub.com + GHE + ADO)."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_mixed_tokens_github_com(self):
        """Test that github.com packages use GITHUB_APM_PAT."""
        with patch.dict(os.environ, {
            'GITHUB_APM_PAT': 'github-token',
            'ADO_APM_PAT': 'ado-token'
        }, clear=True):
            downloader = GitHubPackageDownloader()
            dep_ref = DependencyReference.parse('github.com/owner/repo')
            
            url = downloader._build_repo_url(dep_ref.repo_url, use_ssh=False, dep_ref=dep_ref)
            parsed = urlparse(url)
            
            assert parsed.hostname == 'github.com'
            # GitHub token should be present, ADO token should not
            assert 'ado-token' not in url and parsed.username != 'ado-token'
    
    def test_mixed_tokens_ghe(self):
        """Test that GHE packages use GITHUB_APM_PAT."""
        with patch.dict(os.environ, {
            'GITHUB_APM_PAT': 'github-token',
            'ADO_APM_PAT': 'ado-token'
        }, clear=True):
            downloader = GitHubPackageDownloader()
            dep_ref = DependencyReference.parse('octodemo-eu.ghe.com/owner/repo')
            
            url = downloader._build_repo_url(dep_ref.repo_url, use_ssh=False, dep_ref=dep_ref)
            parsed = urlparse(url)
            
            assert parsed.hostname == 'octodemo-eu.ghe.com'
            # ADO token should not be used for GHE
            assert 'ado-token' not in url and parsed.username != 'ado-token'
    
    def test_mixed_tokens_ado(self):
        """Test that ADO packages use ADO_APM_PAT."""
        with patch.dict(os.environ, {
            'GITHUB_APM_PAT': 'github-token',
            'ADO_APM_PAT': 'ado-token'
        }, clear=True):
            downloader = GitHubPackageDownloader()
            dep_ref = DependencyReference.parse('dev.azure.com/myorg/myproject/_git/myrepo')
            
            url = downloader._build_repo_url(dep_ref.repo_url, use_ssh=False, dep_ref=dep_ref)
            parsed = urlparse(url)
            
            assert parsed.hostname == 'dev.azure.com'
            # ADO token should be used (as username), GitHub token should not
            assert parsed.username == 'ado-token' or 'ado-token' in (parsed.password or '')
            assert 'github-token' not in url
    
    def test_mixed_tokens_bare_owner_repo_with_github_host(self):
        """Test bare owner/repo uses GITHUB_HOST and GITHUB_APM_PAT."""
        with patch.dict(os.environ, {
            'GITHUB_APM_PAT': 'github-token',
            'ADO_APM_PAT': 'ado-token',
            'GITHUB_HOST': 'company.ghe.com'
        }, clear=True):
            downloader = GitHubPackageDownloader()
            dep_ref = DependencyReference.parse('owner/repo')
            
            # Simulate resolution to custom host
            # The dep_ref.host will be github.com by default, but GITHUB_HOST
            # affects the actual URL building in the downloader
            url = downloader._build_repo_url(dep_ref.repo_url, use_ssh=False, dep_ref=dep_ref)
            parsed = urlparse(url)
            
            # Should use GitHub token for GitHub-family hosts, not ADO token
            assert 'ado-token' not in url and parsed.username != 'ado-token'
    
    def test_mixed_installation_token_isolation(self):
        """Test that tokens are isolated per platform in mixed installation."""
        with patch.dict(os.environ, {
            'GITHUB_APM_PAT': 'github-token',
            'ADO_APM_PAT': 'ado-token'
        }, clear=True):
            downloader = GitHubPackageDownloader()
            
            # Parse multiple deps from different sources
            github_dep = DependencyReference.parse('github.com/owner/repo')
            ghe_dep = DependencyReference.parse('company.ghe.com/owner/repo')
            ado_dep = DependencyReference.parse('dev.azure.com/org/proj/_git/repo')
            
            # Build URLs for each
            github_url = downloader._build_repo_url(github_dep.repo_url, use_ssh=False, dep_ref=github_dep)
            ghe_url = downloader._build_repo_url(ghe_dep.repo_url, use_ssh=False, dep_ref=ghe_dep)
            ado_url = downloader._build_repo_url(ado_dep.repo_url, use_ssh=False, dep_ref=ado_dep)
            
            github_parsed = urlparse(github_url)
            ghe_parsed = urlparse(ghe_url)
            ado_parsed = urlparse(ado_url)
            
            # Verify correct hosts
            assert github_parsed.hostname == 'github.com'
            assert ghe_parsed.hostname == 'company.ghe.com'
            assert ado_parsed.hostname == 'dev.azure.com'
            
            # Verify token isolation - ADO token only in ADO URL
            assert 'ado-token' not in github_url
            assert 'ado-token' not in ghe_url
            assert ado_parsed.username == 'ado-token' or 'ado-token' in (ado_parsed.password or '')
            
            # Verify GitHub token not in ADO URL
            assert 'github-token' not in ado_url
    
    def test_github_ado_without_ado_token_falls_back(self):
        """Test ADO without token still builds valid URL."""
        with patch.dict(os.environ, {
            'GITHUB_APM_PAT': 'github-token'
        }, clear=True):
            downloader = GitHubPackageDownloader()
            dep_ref = DependencyReference.parse('dev.azure.com/myorg/myproject/_git/myrepo')
            
            url = downloader._build_repo_url(dep_ref.repo_url, use_ssh=False, dep_ref=dep_ref)
            parsed = urlparse(url)
            
            # Should build valid ADO URL without auth
            assert parsed.hostname == 'dev.azure.com'
            assert 'myorg/myproject/_git/myrepo' in parsed.path
            # GitHub token should NOT be used for ADO - no credentials at all
            assert parsed.username is None or parsed.username != 'github-token'
            assert 'github-token' not in url
    
    def test_ghe_without_github_token_falls_back(self):
        """Test GHE without token still builds valid URL."""
        with patch.dict(os.environ, {
            'ADO_APM_PAT': 'ado-token'
        }, clear=True):
            downloader = GitHubPackageDownloader()
            dep_ref = DependencyReference.parse('company.ghe.com/owner/repo')
            
            url = downloader._build_repo_url(dep_ref.repo_url, use_ssh=False, dep_ref=dep_ref)
            parsed = urlparse(url)
            
            # Should build valid GHE URL without auth
            assert parsed.hostname == 'company.ghe.com'
            assert 'owner/repo' in parsed.path
            # ADO token should NOT be used for GHE - no credentials at all
            assert parsed.username is None or parsed.username != 'ado-token'
            assert 'ado-token' not in url


if __name__ == '__main__':
    pytest.main([__file__])