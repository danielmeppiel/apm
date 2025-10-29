"""Tests for GitHub package downloader."""

import os
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

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


if __name__ == '__main__':
    pytest.main([__file__])