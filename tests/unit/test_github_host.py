import pytest

from apm_cli.utils.github_host import is_valid_fqdn


def test_valid_fqdns():
    valid_hosts = [
        "github.com",
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


def test_sanitize_token_url_in_message():
    host = github_host.default_host()
    msg = f"fatal: Authentication failed for 'https://ghp_secret@{host}/user/repo.git'"
    sanitized = github_host.sanitize_token_url_in_message(msg, host=host)
    assert f"***@{host}" in sanitized
