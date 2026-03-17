"""Comprehensive tests for GitHubTokenManager."""

import os
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from src.apm_cli.core.token_manager import GitHubTokenManager


class TestModulesTokenPrecedence:
    """Test GH_TOKEN addition to the modules token precedence chain."""

    def test_gh_token_used_when_no_other_tokens(self):
        """GH_TOKEN is used when GITHUB_APM_PAT and GITHUB_TOKEN are not set."""
        with patch.dict(os.environ, {'GH_TOKEN': 'gh-cli-token'}, clear=True):
            manager = GitHubTokenManager()
            token = manager.get_token_for_purpose('modules')
            assert token == 'gh-cli-token'

    def test_github_apm_pat_takes_precedence_over_gh_token(self):
        """GITHUB_APM_PAT takes precedence over GH_TOKEN."""
        with patch.dict(os.environ, {
            'GITHUB_APM_PAT': 'apm-pat',
            'GH_TOKEN': 'gh-cli-token',
        }, clear=True):
            manager = GitHubTokenManager()
            token = manager.get_token_for_purpose('modules')
            assert token == 'apm-pat'

    def test_github_token_takes_precedence_over_gh_token(self):
        """GITHUB_TOKEN takes precedence over GH_TOKEN."""
        with patch.dict(os.environ, {
            'GITHUB_TOKEN': 'generic-token',
            'GH_TOKEN': 'gh-cli-token',
        }, clear=True):
            manager = GitHubTokenManager()
            token = manager.get_token_for_purpose('modules')
            assert token == 'generic-token'

    def test_all_three_tokens_apm_pat_wins(self):
        """When all three tokens are present, GITHUB_APM_PAT wins."""
        with patch.dict(os.environ, {
            'GITHUB_APM_PAT': 'apm-pat',
            'GITHUB_TOKEN': 'generic-token',
            'GH_TOKEN': 'gh-cli-token',
        }, clear=True):
            manager = GitHubTokenManager()
            token = manager.get_token_for_purpose('modules')
            assert token == 'apm-pat'

    def test_modules_precedence_order(self):
        """TOKEN_PRECEDENCE['modules'] has the expected order."""
        assert GitHubTokenManager.TOKEN_PRECEDENCE['modules'] == [
            'GITHUB_APM_PAT', 'GITHUB_TOKEN', 'GH_TOKEN',
        ]

    def test_no_tokens_returns_none(self):
        """Returns None when no module tokens are set."""
        with patch.dict(os.environ, {}, clear=True):
            manager = GitHubTokenManager()
            assert manager.get_token_for_purpose('modules') is None


class TestResolveCredentialFromGit:
    """Test resolve_credential_from_git static method."""

    def test_success_returns_password(self):
        """Parses password from successful git credential fill output."""
        mock_result = MagicMock(
            returncode=0,
            stdout="protocol=https\nhost=github.com\nusername=user\npassword=ghp_token123\n",
        )
        with patch('subprocess.run', return_value=mock_result):
            token = GitHubTokenManager.resolve_credential_from_git('github.com')
            assert token == 'ghp_token123'

    def test_no_password_line_returns_none(self):
        """Returns None when output has no password= line."""
        mock_result = MagicMock(
            returncode=0,
            stdout="protocol=https\nhost=github.com\nusername=user\n",
        )
        with patch('subprocess.run', return_value=mock_result):
            assert GitHubTokenManager.resolve_credential_from_git('github.com') is None

    def test_empty_password_returns_none(self):
        """Returns None when password= value is empty."""
        mock_result = MagicMock(
            returncode=0,
            stdout="protocol=https\nhost=github.com\npassword=\n",
        )
        with patch('subprocess.run', return_value=mock_result):
            assert GitHubTokenManager.resolve_credential_from_git('github.com') is None

    def test_nonzero_exit_code_returns_none(self):
        """Returns None on non-zero exit code."""
        mock_result = MagicMock(returncode=1, stdout="")
        with patch('subprocess.run', return_value=mock_result):
            assert GitHubTokenManager.resolve_credential_from_git('github.com') is None

    def test_timeout_returns_none(self):
        """Returns None when subprocess times out."""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired(cmd='git', timeout=5)):
            assert GitHubTokenManager.resolve_credential_from_git('github.com') is None

    def test_file_not_found_returns_none(self):
        """Returns None when git is not installed."""
        with patch('subprocess.run', side_effect=FileNotFoundError):
            assert GitHubTokenManager.resolve_credential_from_git('github.com') is None

    def test_os_error_returns_none(self):
        """Returns None on generic OSError."""
        with patch('subprocess.run', side_effect=OSError("unexpected")):
            assert GitHubTokenManager.resolve_credential_from_git('github.com') is None

    def test_correct_input_sent(self):
        """Verifies protocol=https and host are sent as input."""
        mock_result = MagicMock(returncode=0, stdout="password=tok\n")
        with patch('subprocess.run', return_value=mock_result) as mock_run:
            GitHubTokenManager.resolve_credential_from_git('github.com')
            call_kwargs = mock_run.call_args
            assert call_kwargs.kwargs['input'] == "protocol=https\nhost=github.com\n\n"

    def test_git_terminal_prompt_disabled(self):
        """GIT_TERMINAL_PROMPT=0 is set in the subprocess env."""
        mock_result = MagicMock(returncode=0, stdout="password=tok\n")
        with patch('subprocess.run', return_value=mock_result) as mock_run:
            GitHubTokenManager.resolve_credential_from_git('github.com')
            call_env = mock_run.call_args.kwargs['env']
            assert call_env['GIT_TERMINAL_PROMPT'] == '0'


class TestGetTokenWithCredentialFallback:
    """Test get_token_with_credential_fallback method."""

    def test_returns_env_token_without_credential_fill(self):
        """Returns env var token and never calls credential fill."""
        with patch.dict(os.environ, {'GITHUB_APM_PAT': 'env-token'}, clear=True):
            manager = GitHubTokenManager()
            with patch.object(GitHubTokenManager, 'resolve_credential_from_git') as mock_cred:
                token = manager.get_token_with_credential_fallback('modules', 'github.com')
                assert token == 'env-token'
                mock_cred.assert_not_called()

    def test_falls_back_to_credential_fill(self):
        """Falls back to resolve_credential_from_git when no env token."""
        with patch.dict(os.environ, {}, clear=True):
            manager = GitHubTokenManager()
            with patch.object(
                GitHubTokenManager, 'resolve_credential_from_git', return_value='cred-token'
            ) as mock_cred:
                token = manager.get_token_with_credential_fallback('modules', 'github.com')
                assert token == 'cred-token'
                mock_cred.assert_called_once_with('github.com')

    def test_caches_credential_result(self):
        """Second call uses cache, subprocess not invoked again."""
        with patch.dict(os.environ, {}, clear=True):
            manager = GitHubTokenManager()
            with patch.object(
                GitHubTokenManager, 'resolve_credential_from_git', return_value='cached-tok'
            ) as mock_cred:
                first = manager.get_token_with_credential_fallback('modules', 'github.com')
                second = manager.get_token_with_credential_fallback('modules', 'github.com')
                assert first == second == 'cached-tok'
                mock_cred.assert_called_once()

    def test_caches_none_results(self):
        """None results are cached to avoid retrying failed lookups."""
        with patch.dict(os.environ, {}, clear=True):
            manager = GitHubTokenManager()
            with patch.object(
                GitHubTokenManager, 'resolve_credential_from_git', return_value=None
            ) as mock_cred:
                first = manager.get_token_with_credential_fallback('modules', 'github.com')
                second = manager.get_token_with_credential_fallback('modules', 'github.com')
                assert first is None
                assert second is None
                mock_cred.assert_called_once()

    def test_different_hosts_separate_cache(self):
        """Different hosts get independent cache entries."""
        with patch.dict(os.environ, {}, clear=True):
            manager = GitHubTokenManager()
            with patch.object(
                GitHubTokenManager,
                'resolve_credential_from_git',
                side_effect=lambda h: f'tok-{h}',
            ) as mock_cred:
                tok1 = manager.get_token_with_credential_fallback('modules', 'github.com')
                tok2 = manager.get_token_with_credential_fallback('modules', 'gitlab.com')
                assert tok1 == 'tok-github.com'
                assert tok2 == 'tok-gitlab.com'
                assert mock_cred.call_count == 2
