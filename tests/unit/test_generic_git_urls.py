"""Unit tests for generic git URL support in dependency parsing.

Tests that APM can parse dependency references from any git host using
standard git protocol URLs (HTTPS and SSH), including GitLab, Bitbucket,
and self-hosted instances.
"""

from pathlib import Path

import pytest

from src.apm_cli.models.apm_package import DependencyReference
from src.apm_cli.utils.github_host import (
    build_https_clone_url,
    build_ssh_url,
    is_supported_git_host,
)


class TestGenericHostSupport:
    """Test that any valid FQDN is accepted as a git host."""

    def test_gitlab_com_is_supported(self):
        assert is_supported_git_host("gitlab.com")

    def test_bitbucket_org_is_supported(self):
        assert is_supported_git_host("bitbucket.org")

    def test_self_hosted_gitlab_is_supported(self):
        assert is_supported_git_host("gitlab.company.internal")

    def test_self_hosted_gitea_is_supported(self):
        assert is_supported_git_host("gitea.myorg.com")

    def test_custom_git_server_is_supported(self):
        assert is_supported_git_host("git.example.com")

    def test_localhost_not_supported(self):
        """Single-label hostnames are not valid FQDNs."""
        assert not is_supported_git_host("localhost")

    def test_empty_not_supported(self):
        assert not is_supported_git_host("")
        assert not is_supported_git_host(None)


class TestGitLabHTTPS:
    """Test HTTPS git URL parsing for GitLab repositories."""

    def test_gitlab_https_url(self):
        dep = DependencyReference.parse("https://gitlab.com/acme/coding-standards.git")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/coding-standards"
        assert dep.reference is None

    def test_gitlab_https_url_no_git_suffix(self):
        dep = DependencyReference.parse("https://gitlab.com/acme/coding-standards")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/coding-standards"

    def test_gitlab_https_url_with_ref(self):
        dep = DependencyReference.parse("https://gitlab.com/acme/coding-standards.git#v2.0")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/coding-standards"
        assert dep.reference == "v2.0"

    def test_gitlab_https_url_with_alias(self):
        dep = DependencyReference.parse("https://gitlab.com/acme/coding-standards.git@my-rules")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/coding-standards"
        assert dep.alias == "my-rules"

    def test_gitlab_https_url_with_ref_and_alias(self):
        dep = DependencyReference.parse("https://gitlab.com/acme/coding-standards.git#main@rules")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/coding-standards"
        assert dep.reference == "main"
        assert dep.alias == "rules"

    def test_gitlab_fqdn_format(self):
        """Test gitlab.com/owner/repo format (without https://)."""
        dep = DependencyReference.parse("gitlab.com/acme/coding-standards")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/coding-standards"

    def test_self_hosted_gitlab_https(self):
        dep = DependencyReference.parse("https://gitlab.company.internal/team/rules.git")
        assert dep.host == "gitlab.company.internal"
        assert dep.repo_url == "team/rules"

    def test_self_hosted_gitlab_fqdn(self):
        dep = DependencyReference.parse("gitlab.company.internal/team/rules")
        assert dep.host == "gitlab.company.internal"
        assert dep.repo_url == "team/rules"


class TestGitLabSSH:
    """Test SSH git URL parsing for GitLab repositories."""

    def test_gitlab_ssh_git_at(self):
        dep = DependencyReference.parse("git@gitlab.com:acme/coding-standards.git")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/coding-standards"

    def test_gitlab_ssh_git_at_no_suffix(self):
        dep = DependencyReference.parse("git@gitlab.com:acme/coding-standards")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/coding-standards"

    def test_gitlab_ssh_git_at_with_ref(self):
        dep = DependencyReference.parse("git@gitlab.com:acme/coding-standards.git#v1.0")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/coding-standards"
        assert dep.reference == "v1.0"

    def test_gitlab_ssh_protocol(self):
        """Test ssh:// protocol URL normalization."""
        dep = DependencyReference.parse("ssh://git@gitlab.com/acme/coding-standards.git")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/coding-standards"

    def test_gitlab_ssh_protocol_with_ref(self):
        dep = DependencyReference.parse("ssh://git@gitlab.com/acme/coding-standards.git#main")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/coding-standards"
        assert dep.reference == "main"

    def test_self_hosted_gitlab_ssh(self):
        dep = DependencyReference.parse("git@gitlab.company.internal:team/rules.git")
        assert dep.host == "gitlab.company.internal"
        assert dep.repo_url == "team/rules"

    def test_self_hosted_ssh_protocol(self):
        dep = DependencyReference.parse("ssh://git@gitlab.company.internal/team/rules.git")
        assert dep.host == "gitlab.company.internal"
        assert dep.repo_url == "team/rules"

    def test_ssh_protocol_with_port(self):
        """Port is stripped during normalization to git@ format, which uses SSH config for custom ports."""
        dep = DependencyReference.parse("ssh://git@gitlab.com:2222/acme/repo.git")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/repo"


class TestBitbucketHTTPS:
    """Test HTTPS git URL parsing for Bitbucket repositories."""

    def test_bitbucket_https_url(self):
        dep = DependencyReference.parse("https://bitbucket.org/acme/security-rules.git")
        assert dep.host == "bitbucket.org"
        assert dep.repo_url == "acme/security-rules"

    def test_bitbucket_https_no_suffix(self):
        dep = DependencyReference.parse("https://bitbucket.org/acme/security-rules")
        assert dep.host == "bitbucket.org"
        assert dep.repo_url == "acme/security-rules"

    def test_bitbucket_https_with_ref(self):
        dep = DependencyReference.parse("https://bitbucket.org/acme/security-rules.git#v1.0")
        assert dep.host == "bitbucket.org"
        assert dep.repo_url == "acme/security-rules"
        assert dep.reference == "v1.0"

    def test_bitbucket_fqdn_format(self):
        dep = DependencyReference.parse("bitbucket.org/acme/security-rules")
        assert dep.host == "bitbucket.org"
        assert dep.repo_url == "acme/security-rules"


class TestBitbucketSSH:
    """Test SSH git URL parsing for Bitbucket repositories."""

    def test_bitbucket_ssh_git_at(self):
        dep = DependencyReference.parse("git@bitbucket.org:acme/security-rules.git")
        assert dep.host == "bitbucket.org"
        assert dep.repo_url == "acme/security-rules"

    def test_bitbucket_ssh_protocol(self):
        dep = DependencyReference.parse("ssh://git@bitbucket.org/acme/security-rules.git")
        assert dep.host == "bitbucket.org"
        assert dep.repo_url == "acme/security-rules"


class TestGitHubURLs:
    """Test that GitHub URLs still work correctly with generic support."""

    def test_github_https_url(self):
        dep = DependencyReference.parse("https://github.com/microsoft/apm.git")
        assert dep.host == "github.com"
        assert dep.repo_url == "microsoft/apm"

    def test_github_https_no_suffix(self):
        dep = DependencyReference.parse("https://github.com/microsoft/apm")
        assert dep.host == "github.com"
        assert dep.repo_url == "microsoft/apm"

    def test_github_ssh_url(self):
        dep = DependencyReference.parse("git@github.com:microsoft/apm.git")
        assert dep.host == "github.com"
        assert dep.repo_url == "microsoft/apm"

    def test_github_ssh_protocol(self):
        dep = DependencyReference.parse("ssh://git@github.com/microsoft/apm.git")
        assert dep.host == "github.com"
        assert dep.repo_url == "microsoft/apm"

    def test_github_shorthand_still_works(self):
        dep = DependencyReference.parse("microsoft/apm")
        assert dep.host == "github.com"
        assert dep.repo_url == "microsoft/apm"

    def test_github_fqdn_format(self):
        dep = DependencyReference.parse("github.com/microsoft/apm")
        assert dep.host == "github.com"
        assert dep.repo_url == "microsoft/apm"


class TestSSHProtocolNormalization:
    """Test ssh:// protocol URL normalization."""

    def test_basic_ssh_protocol(self):
        result = DependencyReference._normalize_ssh_protocol_url(
            "ssh://git@gitlab.com/acme/repo.git"
        )
        assert result == "git@gitlab.com:acme/repo.git"

    def test_ssh_protocol_with_port(self):
        result = DependencyReference._normalize_ssh_protocol_url(
            "ssh://git@gitlab.com:2222/acme/repo.git"
        )
        assert result == "git@gitlab.com:acme/repo.git"

    def test_ssh_protocol_no_user(self):
        """ssh:// without user@ defaults to git@."""
        result = DependencyReference._normalize_ssh_protocol_url(
            "ssh://gitlab.com/acme/repo.git"
        )
        assert result == "git@gitlab.com:acme/repo.git"

    def test_non_ssh_url_unchanged(self):
        result = DependencyReference._normalize_ssh_protocol_url(
            "https://gitlab.com/acme/repo.git"
        )
        assert result == "https://gitlab.com/acme/repo.git"

    def test_git_at_url_unchanged(self):
        result = DependencyReference._normalize_ssh_protocol_url(
            "git@gitlab.com:acme/repo.git"
        )
        assert result == "git@gitlab.com:acme/repo.git"


class TestCloneURLBuilding:
    """Test that clone URLs are correctly built for generic hosts."""

    def test_gitlab_https_clone_url(self):
        url = build_https_clone_url("gitlab.com", "acme/repo")
        assert url == "https://gitlab.com/acme/repo"

    def test_gitlab_https_clone_url_with_token(self):
        url = build_https_clone_url("gitlab.com", "acme/repo", token="glpat-xxx")
        assert url == "https://x-access-token:glpat-xxx@gitlab.com/acme/repo.git"

    def test_bitbucket_https_clone_url(self):
        url = build_https_clone_url("bitbucket.org", "acme/repo")
        assert url == "https://bitbucket.org/acme/repo"

    def test_gitlab_ssh_clone_url(self):
        url = build_ssh_url("gitlab.com", "acme/repo")
        assert url == "git@gitlab.com:acme/repo.git"

    def test_bitbucket_ssh_clone_url(self):
        url = build_ssh_url("bitbucket.org", "acme/repo")
        assert url == "git@bitbucket.org:acme/repo.git"

    def test_self_hosted_ssh_clone_url(self):
        url = build_ssh_url("git.company.internal", "team/repo")
        assert url == "git@git.company.internal:team/repo.git"


class TestToGithubURLGenericHosts:
    """Test that to_github_url works correctly for generic hosts."""

    def test_gitlab_to_url(self):
        dep = DependencyReference.parse("https://gitlab.com/acme/repo.git")
        assert dep.to_github_url() == "https://gitlab.com/acme/repo"

    def test_bitbucket_to_url(self):
        dep = DependencyReference.parse("git@bitbucket.org:acme/repo.git")
        assert dep.to_github_url() == "https://bitbucket.org/acme/repo"

    def test_self_hosted_to_url(self):
        dep = DependencyReference.parse("git@git.company.internal:team/rules.git")
        assert dep.to_github_url() == "https://git.company.internal/team/rules"


class TestGetInstallPathGenericHosts:
    """Test that install paths work correctly for generic hosts."""

    def test_gitlab_install_path(self):
        dep = DependencyReference.parse("https://gitlab.com/acme/repo.git")
        path = dep.get_install_path(Path("apm_modules"))
        assert path == Path("apm_modules/acme/repo")

    def test_bitbucket_install_path(self):
        dep = DependencyReference.parse("git@bitbucket.org:team/rules.git")
        path = dep.get_install_path(Path("apm_modules"))
        assert path == Path("apm_modules/team/rules")

    def test_self_hosted_install_path(self):
        dep = DependencyReference.parse("git@git.company.internal:team/rules.git")
        path = dep.get_install_path(Path("apm_modules"))
        assert path == Path("apm_modules/team/rules")


class TestSecurityWithGenericHosts:
    """Test that security protections still work with generic host support."""

    def test_protocol_relative_rejected(self):
        with pytest.raises(ValueError, match="Protocol-relative"):
            DependencyReference.parse("//evil.com/user/repo")

    def test_control_characters_rejected(self):
        with pytest.raises(ValueError, match="control characters"):
            DependencyReference.parse("gitlab.com/user/repo\n")

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError, match="Empty"):
            DependencyReference.parse("")

    def test_path_injection_still_rejected(self):
        """Embedding a hostname in a sub-path position is still rejected."""
        with pytest.raises(ValueError):
            DependencyReference.parse("evil.com/github.com/user/repo")

    def test_invalid_characters_rejected(self):
        with pytest.raises(ValueError, match="Invalid repository path component"):
            DependencyReference.parse("https://gitlab.com/user/repo$bad")
