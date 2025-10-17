import os
from apm_cli.utils import github_host


def test_default_host_env_override(monkeypatch):
    monkeypatch.setenv('GITHUB_HOST', 'example.ghe.com')
    assert github_host.default_host() == 'example.ghe.com'
    monkeypatch.delenv('GITHUB_HOST', raising=False)


def test_is_github_hostname_defaults():
    assert github_host.is_github_hostname(github_host.default_host())
    assert github_host.is_github_hostname('org.ghe.com')
    assert not github_host.is_github_hostname('example.com')


def test_sanitize_token_url_in_message():
    host = github_host.default_host()
    msg = f"fatal: Authentication failed for 'https://ghp_secret@{host}/user/repo.git'"
    sanitized = github_host.sanitize_token_url_in_message(msg, host=host)
    assert f'***@{host}' in sanitized
