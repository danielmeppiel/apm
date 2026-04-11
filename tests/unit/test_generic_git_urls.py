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

    def test_gitlab_https_url_with_alias_shorthand_removed(self):
        """Shorthand @alias on HTTPS URLs is no longer supported."""
        with pytest.raises(ValueError):
            DependencyReference.parse("https://gitlab.com/acme/coding-standards.git@my-rules")

    def test_gitlab_https_url_with_ref_and_alias_shorthand_not_parsed(self):
        """Shorthand #ref@alias on HTTPS URLs — @ is no longer parsed as alias separator."""
        dep = DependencyReference.parse("https://gitlab.com/acme/coding-standards.git#main@rules")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/coding-standards"
        assert dep.reference == "main@rules"
        assert dep.alias is None

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


class TestBitbucketDatacenterSSH:
    """Regression tests for issue #661: ssh:// URLs with custom ports must be preserved.

    Bitbucket Datacenter (and other self-hosted instances) commonly use non-standard
    SSH ports (e.g. 7999). When a user explicitly specifies an ssh:// URL in apm.yml
    the original URL must be kept verbatim so git clones against the correct port
    instead of silently falling back to HTTPS.
    """

    def test_preserve_bitbucket_datacenter_ssh_url_with_port(self):
        """ssh:// URL with custom port must be stored in original_ssh_url."""
        url = "ssh://git@bitbucket.domain.ext:7999/project/repo.git"
        dep = DependencyReference.parse(url)
        assert dep.original_ssh_url == url

    def test_bitbucket_datacenter_host_and_repo_still_parsed(self):
        """Parsed host/repo_url fields should still be populated correctly."""
        dep = DependencyReference.parse(
            "ssh://git@bitbucket.domain.ext:7999/project/repo.git"
        )
        assert dep.host == "bitbucket.domain.ext"
        assert dep.repo_url == "project/repo"

    def test_preserve_standard_ssh_protocol_url(self):
        """ssh:// without a port also stores the original URL."""
        url = "ssh://git@github.com/org/repo.git"
        dep = DependencyReference.parse(url)
        assert dep.original_ssh_url == url

    def test_https_url_does_not_set_original_ssh_url(self):
        """HTTPS dependencies must not set original_ssh_url."""
        dep = DependencyReference.parse(
            "https://bitbucket.domain.ext/scm/project/repo.git"
        )
        assert dep.original_ssh_url is None

    def test_git_at_url_does_not_set_original_ssh_url(self):
        """git@ SSH shorthand does not go through ssh:// normalisation."""
        dep = DependencyReference.parse("git@bitbucket.org:acme/rules.git")
        assert dep.original_ssh_url is None


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
        """Embedding a hostname in a sub-path position is valid with nested groups.
        
        With nested group support on generic hosts, all path segments are part
        of the repo path. The host is correctly identified from the first segment.
        """
        dep = DependencyReference.parse("evil.com/github.com/user/repo")
        assert dep.host == "evil.com"
        assert dep.repo_url == "github.com/user/repo"
        assert dep.is_virtual is False

    def test_invalid_characters_rejected(self):
        with pytest.raises(ValueError, match="Invalid repository path component"):
            DependencyReference.parse("https://gitlab.com/user/repo$bad")


class TestFQDNVirtualPaths:
    """Test FQDN shorthand with virtual paths on generic hosts.

    Git protocol URLs (https://, git@) are repo-level and cannot embed paths.
    Use FQDN shorthand (host/owner/repo/path) for virtual packages on any host.
    """

    def test_gitlab_virtual_file(self):
        dep = DependencyReference.parse("gitlab.com/acme/repo/prompts/file.prompt.md")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/repo"
        assert dep.virtual_path == "prompts/file.prompt.md"
        assert dep.is_virtual is True
        assert dep.is_virtual_file() is True

    def test_bitbucket_virtual_collection(self):
        dep = DependencyReference.parse("bitbucket.org/team/rules/collections/security")
        assert dep.host == "bitbucket.org"
        assert dep.repo_url == "team/rules"
        assert dep.virtual_path == "collections/security"
        assert dep.is_virtual is True
        assert dep.is_virtual_collection() is True

    def test_self_hosted_virtual_subdirectory(self):
        """Without virtual indicators, all segments are repo path on generic hosts.
        
        Virtual subdirectory packages on generic hosts with nested groups
        require the dict format: {git: 'host/group/repo', path: 'subdir'}
        """
        dep = DependencyReference.parse("git.company.internal/team/skills/brand-guidelines")
        assert dep.host == "git.company.internal"
        assert dep.repo_url == "team/skills/brand-guidelines"
        assert dep.is_virtual is False

    def test_gitlab_virtual_file_with_ref(self):
        dep = DependencyReference.parse("gitlab.com/acme/repo/prompts/file.prompt.md#v2.0")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/repo"
        assert dep.virtual_path == "prompts/file.prompt.md"
        assert dep.reference == "v2.0"

    def test_https_url_with_path_rejected(self):
        """HTTPS git URLs can't embed virtual paths — use dict format instead."""
        with pytest.raises(ValueError, match="virtual file extension"):
            DependencyReference.parse("https://gitlab.com/acme/repo/prompts/file.prompt.md")

    def test_ssh_url_with_path_rejected(self):
        """SSH git URLs can't embed virtual paths — use dict format instead."""
        with pytest.raises(ValueError, match="virtual file extension"):
            DependencyReference.parse("git@gitlab.com:acme/repo/prompts/code-review.prompt.md")


class TestNestedGroupSupport:
    """Test nested group/subgroup support for generic hosts (GitLab, Gitea, etc.).

    GitLab supports up to 20 levels of nested groups: gitlab.com/group/subgroup/.../repo.
    For generic hosts (non-GitHub, non-ADO), ALL path segments are treated as repo path
    unless virtual indicators (file extensions, /collections/) are present.
    """

    # --- FQDN shorthand ---

    def test_gitlab_two_level_group(self):
        dep = DependencyReference.parse("gitlab.com/group/subgroup/repo")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "group/subgroup/repo"
        assert dep.is_virtual is False

    def test_gitlab_three_level_group(self):
        dep = DependencyReference.parse("gitlab.com/org/team/project/repo")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "org/team/project/repo"
        assert dep.is_virtual is False

    def test_gitlab_simple_owner_repo_unchanged(self):
        dep = DependencyReference.parse("gitlab.com/owner/repo")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "owner/repo"
        assert dep.is_virtual is False

    def test_nested_group_with_ref(self):
        dep = DependencyReference.parse("gitlab.com/group/subgroup/repo#v2.0")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "group/subgroup/repo"
        assert dep.reference == "v2.0"
        assert dep.is_virtual is False

    def test_nested_group_with_alias_shorthand_removed(self):
        """Shorthand @alias on nested groups is no longer supported."""
        with pytest.raises(ValueError):
            DependencyReference.parse("gitlab.com/group/subgroup/repo@my-alias")

    def test_nested_group_with_ref_and_alias_shorthand_not_parsed(self):
        """Shorthand #ref@alias on nested groups — @ is no longer parsed as alias separator."""
        dep = DependencyReference.parse("gitlab.com/group/subgroup/repo#main@alias")
        assert dep.repo_url == "group/subgroup/repo"
        assert dep.reference == "main@alias"
        assert dep.alias is None

    # --- SSH URLs ---

    def test_ssh_nested_group(self):
        dep = DependencyReference.parse("git@gitlab.com:group/subgroup/repo.git")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "group/subgroup/repo"
        assert dep.is_virtual is False

    def test_ssh_three_level_group(self):
        dep = DependencyReference.parse("git@gitlab.com:org/team/project/repo.git")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "org/team/project/repo"

    def test_ssh_nested_group_no_git_suffix(self):
        dep = DependencyReference.parse("git@gitlab.com:group/subgroup/repo")
        assert dep.repo_url == "group/subgroup/repo"

    def test_ssh_nested_group_with_ref(self):
        dep = DependencyReference.parse("git@gitlab.com:group/subgroup/repo.git#v1.0")
        assert dep.repo_url == "group/subgroup/repo"
        assert dep.reference == "v1.0"

    # --- HTTPS URLs ---

    def test_https_nested_group(self):
        dep = DependencyReference.parse("https://gitlab.com/group/subgroup/repo.git")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "group/subgroup/repo"
        assert dep.is_virtual is False

    def test_https_three_level_group(self):
        dep = DependencyReference.parse("https://gitlab.com/org/team/project/repo.git")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "org/team/project/repo"

    def test_https_nested_group_no_git_suffix(self):
        dep = DependencyReference.parse("https://gitlab.com/group/subgroup/repo")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "group/subgroup/repo"

    # --- ssh:// protocol URLs ---

    def test_ssh_protocol_nested_group(self):
        dep = DependencyReference.parse("ssh://git@gitlab.com/group/subgroup/repo.git")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "group/subgroup/repo"

    # --- Virtual packages with nested groups ---

    def test_nested_group_simple_repo_with_virtual_file(self):
        """Simple 2-segment repo on generic host with virtual file extension."""
        dep = DependencyReference.parse("gitlab.com/acme/repo/design.prompt.md")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/repo"
        assert dep.virtual_path == "design.prompt.md"
        assert dep.is_virtual is True

    def test_nested_group_simple_repo_with_collection(self):
        """Simple 2-segment repo on generic host with collections path."""
        dep = DependencyReference.parse("gitlab.com/acme/repo/collections/security")
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/repo"
        assert dep.virtual_path == "collections/security"
        assert dep.is_virtual is True

    def test_nested_group_virtual_requires_dict_format(self):
        """For nested groups + virtual, dict format is required."""
        dep = DependencyReference.parse_from_dict({
            "git": "gitlab.com/group/subgroup/repo",
            "path": "prompts/review.prompt.md"
        })
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "group/subgroup/repo"
        assert dep.virtual_path == "prompts/review.prompt.md"
        assert dep.is_virtual is True

    # --- Install paths ---

    def test_install_path_nested_group(self):
        dep = DependencyReference.parse("gitlab.com/group/subgroup/repo")
        path = dep.get_install_path(Path("/apm_modules"))
        assert path == Path("/apm_modules/group/subgroup/repo")

    def test_install_path_three_level_group(self):
        dep = DependencyReference.parse("gitlab.com/org/team/project/repo")
        path = dep.get_install_path(Path("/apm_modules"))
        assert path == Path("/apm_modules/org/team/project/repo")

    def test_install_path_simple_generic_host(self):
        dep = DependencyReference.parse("gitlab.com/owner/repo")
        path = dep.get_install_path(Path("/apm_modules"))
        assert path == Path("/apm_modules/owner/repo")

    # --- Canonical form ---

    def test_canonical_nested_group(self):
        dep = DependencyReference.parse("gitlab.com/group/subgroup/repo")
        assert dep.to_canonical() == "gitlab.com/group/subgroup/repo"

    def test_canonical_nested_group_with_ref(self):
        dep = DependencyReference.parse("gitlab.com/group/subgroup/repo#v2.0")
        assert dep.to_canonical() == "gitlab.com/group/subgroup/repo#v2.0"

    def test_canonical_ssh_nested_group(self):
        dep = DependencyReference.parse("git@gitlab.com:group/subgroup/repo.git")
        assert dep.to_canonical() == "gitlab.com/group/subgroup/repo"

    def test_canonical_https_nested_group(self):
        dep = DependencyReference.parse("https://gitlab.com/group/subgroup/repo.git")
        assert dep.to_canonical() == "gitlab.com/group/subgroup/repo"

    # --- to_github_url (clone URL) ---

    def test_to_github_url_nested_group(self):
        dep = DependencyReference.parse("gitlab.com/group/subgroup/repo")
        assert dep.to_github_url() == "https://gitlab.com/group/subgroup/repo"

    # --- GitHub unchanged ---

    def test_github_shorthand_unchanged(self):
        """GitHub 2-segment shorthand is unchanged by nested group support."""
        dep = DependencyReference.parse("owner/repo")
        assert dep.host == "github.com"
        assert dep.repo_url == "owner/repo"
        assert dep.is_virtual is False

    def test_github_virtual_unchanged(self):
        """GitHub 3+ segments still mean virtual package."""
        dep = DependencyReference.parse("owner/repo/file.prompt.md")
        assert dep.repo_url == "owner/repo"
        assert dep.virtual_path == "file.prompt.md"
        assert dep.is_virtual is True

    # --- Rejection cases ---

    # --- Ambiguity: nested group + virtual path (shorthand vs dict) ---

    def test_shorthand_ambiguity_virtual_ext_collapses_repo(self):
        """Shorthand with virtual extension treats owner/repo as 2-segment base.

        gitlab.com/group/subgroup/repo/file.prompt.md → the parser sees the
        .prompt.md extension and assumes a 2-segment repo (group/subgroup)
        with virtual path repo/file.prompt.md. This is WRONG if the user
        meant repo=group/subgroup/repo. That's why dict format is required.
        """
        dep = DependencyReference.parse("gitlab.com/group/subgroup/repo/file.prompt.md")
        # Parser sees virtual indicator → assumes 2-segment base
        assert dep.repo_url == "group/subgroup"
        assert dep.virtual_path == "repo/file.prompt.md"
        assert dep.is_virtual is True

    def test_dict_format_resolves_ambiguity(self):
        """Dict format makes nested-group + virtual path unambiguous.

        The dict format explicitly separates the repo URL from the virtual
        path, so there's no ambiguity about where the repo path ends.
        """
        dep = DependencyReference.parse_from_dict({
            "git": "gitlab.com/group/subgroup/repo",
            "path": "file.prompt.md"
        })
        assert dep.repo_url == "group/subgroup/repo"
        assert dep.virtual_path == "file.prompt.md"
        assert dep.is_virtual is True
        assert dep.host == "gitlab.com"

    def test_dict_format_nested_group_with_collection(self):
        """Dict format works for nested-group repos with collections."""
        dep = DependencyReference.parse_from_dict({
            "git": "gitlab.com/acme/platform/infra/repo",
            "path": "collections/security"
        })
        assert dep.repo_url == "acme/platform/infra/repo"
        assert dep.virtual_path == "collections/security"
        assert dep.is_virtual is True

    def test_dict_format_nested_group_install_path_subdir(self):
        """Install path for dict-based virtual subdirectory nested-group dep."""
        dep = DependencyReference.parse_from_dict({
            "git": "gitlab.com/group/subgroup/repo",
            "path": "skills/code-review"
        })
        path = dep.get_install_path(Path("/apm_modules"))
        # Subdirectory virtual: repo path + virtual path
        assert path == Path("/apm_modules/group/subgroup/repo/skills/code-review")

    def test_dict_format_nested_group_install_path_file(self):
        """Install path for dict-based virtual file nested-group dep."""
        dep = DependencyReference.parse_from_dict({
            "git": "gitlab.com/group/subgroup/repo",
            "path": "prompts/review.prompt.md"
        })
        path = dep.get_install_path(Path("/apm_modules"))
        # Virtual file: first segment / sanitized package name
        assert path == Path("/apm_modules/group/" + dep.get_virtual_package_name())

    def test_dict_format_nested_group_canonical(self):
        """Canonical form for dict-based nested-group dep includes virtual path."""
        dep = DependencyReference.parse_from_dict({
            "git": "gitlab.com/group/subgroup/repo",
            "path": "prompts/review.prompt.md"
        })
        # Canonical includes virtual path since it's a virtual package
        assert dep.to_canonical() == "gitlab.com/group/subgroup/repo/prompts/review.prompt.md"

    def test_dict_format_nested_group_clone_url(self):
        """Clone URL for dict-based nested-group dep."""
        dep = DependencyReference.parse_from_dict({
            "git": "gitlab.com/group/subgroup/repo",
            "path": "prompts/review.prompt.md"
        })
        assert dep.to_github_url() == "https://gitlab.com/group/subgroup/repo"

    def test_dict_format_nested_group_with_ref_and_alias(self):
        """Dict format with all fields on nested-group repo."""
        dep = DependencyReference.parse_from_dict({
            "git": "https://gitlab.com/acme/team/project/repo.git",
            "path": "instructions/security",
            "ref": "v2.0",
            "alias": "sec-rules"
        })
        assert dep.host == "gitlab.com"
        assert dep.repo_url == "acme/team/project/repo"
        assert dep.virtual_path == "instructions/security"
        assert dep.reference == "v2.0"
        assert dep.alias == "sec-rules"
        assert dep.is_virtual is True

    # --- SSH/HTTPS rejection for nested groups with virtual extensions ---

    def test_ssh_nested_group_with_virtual_ext_rejected(self):
        """SSH URLs can't embed virtual paths even with nested groups."""
        with pytest.raises(ValueError, match="virtual file extension"):
            DependencyReference.parse("git@gitlab.com:group/subgroup/file.prompt.md")

    def test_https_nested_group_with_virtual_ext_rejected(self):
        """HTTPS URLs can't embed virtual paths even with nested groups."""
        with pytest.raises(ValueError, match="virtual file extension"):
            DependencyReference.parse("https://gitlab.com/group/subgroup/file.prompt.md")
