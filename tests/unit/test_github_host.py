import pytest

from apm_cli.utils.github_host import is_valid_fqdn


def test_valid_fqdns():
    valid_hosts = [
        "github.com",
        "github.com/user/repo",
        "example.com",
        "sub.example.co.uk",
        "a1b2.example",
        "xn--example.com",  # punycode-like label
        "my-service.localdomain.com",
    ]

    for host in valid_hosts:
        assert is_valid_fqdn(host), f"Expected '{host}' to be valid FQDN"


def test_invalid_fqdns():
    invalid_hosts = [
        "",
        None,  # function treats falsy values as invalid
        "localhost",
        "no_dot",
        "-startdash.com",
        "enddash-.com",
        "two..dots.com",
        "a.-b.com",
        "invalid_domain",
    ]

    for host in invalid_hosts:
        # allow passing None without raising (function handles falsy)
        assert not is_valid_fqdn(host), f"Expected '{host}' to be invalid FQDN"


import os

from apm_cli.utils import github_host


def test_default_host_env_override(monkeypatch):
    monkeypatch.setenv("GITHUB_HOST", "example.ghe.com")
    assert github_host.default_host() == "example.ghe.com"
    monkeypatch.delenv("GITHUB_HOST", raising=False)


def test_is_github_hostname_defaults():
    assert github_host.is_github_hostname(github_host.default_host())
    assert github_host.is_github_hostname("org.ghe.com")
    assert not github_host.is_github_hostname("example.com")


def test_is_azure_devops_hostname():
    """Test Azure DevOps hostname detection."""
    # Valid Azure DevOps hosts
    assert github_host.is_azure_devops_hostname("dev.azure.com")
    assert github_host.is_azure_devops_hostname("mycompany.visualstudio.com")
    assert github_host.is_azure_devops_hostname("contoso.visualstudio.com")
    
    # Invalid hosts
    assert not github_host.is_azure_devops_hostname("github.com")
    assert not github_host.is_azure_devops_hostname("example.com")
    assert not github_host.is_azure_devops_hostname("azure.com")
    assert not github_host.is_azure_devops_hostname("visualstudio.com")  # Must have org prefix
    assert not github_host.is_azure_devops_hostname(None)
    assert not github_host.is_azure_devops_hostname("")


def test_is_supported_git_host():
    """Test unified Git host detection supporting all platforms."""
    # GitHub hosts
    assert github_host.is_supported_git_host("github.com")
    assert github_host.is_supported_git_host("company.ghe.com")
    
    # Azure DevOps hosts
    assert github_host.is_supported_git_host("dev.azure.com")
    assert github_host.is_supported_git_host("mycompany.visualstudio.com")
    
    # Unsupported hosts
    assert not github_host.is_supported_git_host("gitlab.com")
    assert not github_host.is_supported_git_host("bitbucket.org")
    assert not github_host.is_supported_git_host("example.com")
    assert not github_host.is_supported_git_host(None)
    assert not github_host.is_supported_git_host("")


def test_is_supported_git_host_with_custom_host(monkeypatch):
    """Test that GITHUB_HOST env var adds custom host to supported list."""
    # Set a custom Azure DevOps Server host
    monkeypatch.setenv("GITHUB_HOST", "ado.mycompany.internal")
    
    # Custom host should now be supported
    assert github_host.is_supported_git_host("ado.mycompany.internal")
    
    # Standard hosts should still work
    assert github_host.is_supported_git_host("github.com")
    assert github_host.is_supported_git_host("dev.azure.com")
    
    monkeypatch.delenv("GITHUB_HOST", raising=False)


def test_sanitize_token_url_in_message():
    host = github_host.default_host()
    msg = f"fatal: Authentication failed for 'https://ghp_secret@{host}/user/repo.git'"
    sanitized = github_host.sanitize_token_url_in_message(msg, host=host)
    assert f"***@{host}" in sanitized


# Azure DevOps URL builder tests

def test_build_ado_https_clone_url():
    """Test Azure DevOps HTTPS URL construction."""
    # Without token
    url = github_host.build_ado_https_clone_url("dmeppiel-org", "market-js-app", "compliance-rules")
    assert url == "https://dev.azure.com/dmeppiel-org/market-js-app/_git/compliance-rules"
    
    # With token
    url = github_host.build_ado_https_clone_url("dmeppiel-org", "market-js-app", "compliance-rules", token="mytoken")
    assert url == "https://mytoken@dev.azure.com/dmeppiel-org/market-js-app/_git/compliance-rules"
    
    # With custom host (ADO Server)
    url = github_host.build_ado_https_clone_url("myorg", "myproject", "myrepo", host="ado.company.internal")
    assert url == "https://ado.company.internal/myorg/myproject/_git/myrepo"


def test_build_ado_ssh_url():
    """Test Azure DevOps SSH URL construction."""
    url = github_host.build_ado_ssh_url("dmeppiel-org", "market-js-app", "compliance-rules")
    assert url == "git@ssh.dev.azure.com:v3/dmeppiel-org/market-js-app/compliance-rules"


def test_build_ado_api_url():
    """Test Azure DevOps API URL construction."""
    url = github_host.build_ado_api_url("dmeppiel-org", "market-js-app", "compliance-rules", "apm.yml", "main")
    assert "/_apis/git/repositories/compliance-rules/items" in url
    assert "path=apm.yml" in url
    assert "versionDescriptor.version=main" in url
    assert "api-version=7.0" in url
