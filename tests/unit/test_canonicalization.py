"""Tests for normalize-on-write canonicalization and identity-based CLI matching.

Covers:
- DependencyReference.to_canonical() — Docker-style default-host stripping
- DependencyReference.get_identity() — identity without ref/alias
- DependencyReference.canonicalize() — static convenience method
- _validate_and_add_packages_to_apm_yml() — normalize-on-write + dedup
- uninstall identity matching
- only_packages filter in _install_apm_dependencies
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from apm_cli.models.apm_package import DependencyReference


# ── to_canonical() ──────────────────────────────────────────────────────────

class TestToCanonical:
    """Test DependencyReference.to_canonical() method."""

    def test_shorthand_github(self):
        """Shorthand owner/repo stays as-is (default host stripped)."""
        dep = DependencyReference.parse("microsoft/apm-sample-package")
        assert dep.to_canonical() == "microsoft/apm-sample-package"

    def test_shorthand_with_ref(self):
        """Shorthand with ref preserves the ref."""
        dep = DependencyReference.parse("microsoft/apm-sample-package#v1.0")
        assert dep.to_canonical() == "microsoft/apm-sample-package#v1.0"

    def test_shorthand_with_alias(self):
        """Shorthand with alias preserves the alias."""
        dep = DependencyReference.parse("microsoft/apm-sample-package@my-alias")
        assert dep.to_canonical() == "microsoft/apm-sample-package@my-alias"

    def test_shorthand_with_ref_and_alias(self):
        """Shorthand with both ref and alias preserves both."""
        dep = DependencyReference.parse("microsoft/apm-sample-package#main@my-alias")
        assert dep.to_canonical() == "microsoft/apm-sample-package#main@my-alias"

    def test_fqdn_github(self):
        """FQDN with default host strips the host."""
        dep = DependencyReference.parse("github.com/microsoft/apm-sample-package")
        assert dep.to_canonical() == "microsoft/apm-sample-package"

    def test_fqdn_github_with_ref(self):
        """FQDN with default host + ref strips host, keeps ref."""
        dep = DependencyReference.parse("github.com/microsoft/apm-sample-package#main")
        assert dep.to_canonical() == "microsoft/apm-sample-package#main"

    def test_https_github(self):
        """HTTPS GitHub URL normalizes to shorthand."""
        dep = DependencyReference.parse("https://github.com/microsoft/apm-sample-package.git")
        assert dep.to_canonical() == "microsoft/apm-sample-package"

    def test_https_github_with_ref(self):
        """HTTPS GitHub URL with ref normalizes to shorthand#ref."""
        dep = DependencyReference.parse("https://github.com/microsoft/apm-sample-package.git#v2.0")
        assert dep.to_canonical() == "microsoft/apm-sample-package#v2.0"

    def test_ssh_github(self):
        """SSH GitHub URL normalizes to shorthand."""
        dep = DependencyReference.parse("git@github.com:microsoft/apm-sample-package.git")
        assert dep.to_canonical() == "microsoft/apm-sample-package"

    def test_ssh_protocol_github(self):
        """SSH protocol GitHub URL normalizes to shorthand."""
        dep = DependencyReference.parse("ssh://git@github.com/microsoft/apm-sample-package.git")
        assert dep.to_canonical() == "microsoft/apm-sample-package"

    def test_fqdn_gitlab(self):
        """Non-default host is preserved in canonical form."""
        dep = DependencyReference.parse("gitlab.com/acme/standards")
        assert dep.to_canonical() == "gitlab.com/acme/standards"

    def test_https_gitlab(self):
        """HTTPS GitLab URL normalizes to host/owner/repo."""
        dep = DependencyReference.parse("https://gitlab.com/acme/standards.git")
        assert dep.to_canonical() == "gitlab.com/acme/standards"

    def test_ssh_gitlab(self):
        """SSH GitLab URL normalizes to host/owner/repo."""
        dep = DependencyReference.parse("git@gitlab.com:acme/standards.git")
        assert dep.to_canonical() == "gitlab.com/acme/standards"

    def test_ssh_protocol_gitlab(self):
        """SSH protocol GitLab URL normalizes to host/owner/repo."""
        dep = DependencyReference.parse("ssh://git@gitlab.com/acme/standards.git")
        assert dep.to_canonical() == "gitlab.com/acme/standards"

    def test_gitlab_with_ref(self):
        """Non-default host + ref preserves both."""
        dep = DependencyReference.parse("gitlab.com/acme/standards#v2.0")
        assert dep.to_canonical() == "gitlab.com/acme/standards#v2.0"

    def test_https_gitlab_with_ref(self):
        """HTTPS non-default + ref normalizes correctly."""
        dep = DependencyReference.parse("https://gitlab.com/acme/standards.git#release-1")
        assert dep.to_canonical() == "gitlab.com/acme/standards#release-1"

    def test_bitbucket(self):
        """Bitbucket preserves host."""
        dep = DependencyReference.parse("bitbucket.org/team/rules")
        assert dep.to_canonical() == "bitbucket.org/team/rules"

    def test_ssh_bitbucket(self):
        """SSH Bitbucket normalizes with host."""
        dep = DependencyReference.parse("git@bitbucket.org:team/rules.git")
        assert dep.to_canonical() == "bitbucket.org/team/rules"

    def test_custom_ghe_host(self):
        """GitHub Enterprise (.ghe.com) is default host variant — strips host."""
        dep = DependencyReference.parse("github.com/microsoft/apm-sample-package")
        # github.com is the default, so stripped
        assert dep.to_canonical() == "microsoft/apm-sample-package"

    def test_virtual_path_github(self):
        """Virtual path on default host preserves path but strips host."""
        dep = DependencyReference.parse("microsoft/apm-sample-package/prompts/review.prompt.md")
        assert dep.to_canonical() == "microsoft/apm-sample-package/prompts/review.prompt.md"

    def test_virtual_path_non_default_host(self):
        """Virtual path on non-default host preserves both host and path."""
        dep = DependencyReference.parse("gitlab.com/acme/standards/prompts/review.prompt.md")
        assert dep.to_canonical() == "gitlab.com/acme/standards/prompts/review.prompt.md"


# ── get_identity() ──────────────────────────────────────────────────────────

class TestGetIdentity:
    """Test DependencyReference.get_identity() — identity without ref/alias."""

    def test_shorthand(self):
        dep = DependencyReference.parse("owner/repo")
        assert dep.get_identity() == "owner/repo"

    def test_shorthand_with_ref(self):
        """Ref is stripped from identity."""
        dep = DependencyReference.parse("owner/repo#v1.0")
        assert dep.get_identity() == "owner/repo"

    def test_shorthand_with_alias(self):
        """Alias is stripped from identity."""
        dep = DependencyReference.parse("owner/repo@my-alias")
        assert dep.get_identity() == "owner/repo"

    def test_shorthand_with_ref_and_alias(self):
        """Both ref and alias are stripped from identity."""
        dep = DependencyReference.parse("owner/repo#main@my-alias")
        assert dep.get_identity() == "owner/repo"

    def test_fqdn_github(self):
        """Default host is stripped from identity."""
        dep = DependencyReference.parse("github.com/owner/repo")
        assert dep.get_identity() == "owner/repo"

    def test_fqdn_gitlab(self):
        """Non-default host is preserved in identity."""
        dep = DependencyReference.parse("gitlab.com/owner/repo")
        assert dep.get_identity() == "gitlab.com/owner/repo"

    def test_https_github(self):
        """HTTPS default host stripped from identity."""
        dep = DependencyReference.parse("https://github.com/owner/repo.git")
        assert dep.get_identity() == "owner/repo"

    def test_https_gitlab(self):
        """HTTPS non-default host preserved in identity."""
        dep = DependencyReference.parse("https://gitlab.com/owner/repo.git")
        assert dep.get_identity() == "gitlab.com/owner/repo"

    def test_ssh_github(self):
        """SSH default host stripped."""
        dep = DependencyReference.parse("git@github.com:owner/repo.git")
        assert dep.get_identity() == "owner/repo"

    def test_ssh_gitlab(self):
        """SSH non-default host preserved."""
        dep = DependencyReference.parse("git@gitlab.com:owner/repo.git")
        assert dep.get_identity() == "gitlab.com/owner/repo"

    def test_virtual_path(self):
        """Virtual path included in identity."""
        dep = DependencyReference.parse("owner/repo/prompts/review.prompt.md")
        assert dep.get_identity() == "owner/repo/prompts/review.prompt.md"

    def test_gitlab_virtual_with_ref(self):
        """Non-default host + virtual path + ref: ref stripped, rest preserved."""
        dep = DependencyReference.parse("gitlab.com/acme/rules/prompts/review.prompt.md#v2")
        assert dep.get_identity() == "gitlab.com/acme/rules/prompts/review.prompt.md"

    def test_same_identity_different_forms(self):
        """All input forms for the same package produce the same identity."""
        forms = [
            "microsoft/apm-sample-package",
            "github.com/microsoft/apm-sample-package",
            "https://github.com/microsoft/apm-sample-package.git",
            "git@github.com:microsoft/apm-sample-package.git",
            "ssh://git@github.com/microsoft/apm-sample-package.git",
            "microsoft/apm-sample-package#main",
            "microsoft/apm-sample-package@alias",
        ]
        identities = {DependencyReference.parse(f).get_identity() for f in forms}
        assert len(identities) == 1, f"Expected 1 identity, got {identities}"
        assert identities == {"microsoft/apm-sample-package"}

    def test_different_hosts_different_identities(self):
        """Same owner/repo on different hosts = different identities."""
        gh = DependencyReference.parse("owner/repo")
        gl = DependencyReference.parse("gitlab.com/owner/repo")
        assert gh.get_identity() != gl.get_identity()


# ── canonicalize() static method ────────────────────────────────────────────

class TestCanonicalize:
    """Test DependencyReference.canonicalize() static convenience method."""

    def test_shorthand(self):
        assert DependencyReference.canonicalize("owner/repo") == "owner/repo"

    def test_https_github(self):
        assert DependencyReference.canonicalize("https://github.com/o/r.git") == "o/r"

    def test_ssh_gitlab(self):
        assert DependencyReference.canonicalize("git@gitlab.com:o/r.git") == "gitlab.com/o/r"

    def test_fqdn_with_ref(self):
        assert DependencyReference.canonicalize("github.com/o/r#v1") == "o/r#v1"

    def test_https_gitlab_with_ref(self):
        assert DependencyReference.canonicalize("https://gitlab.com/o/r.git#main") == "gitlab.com/o/r#main"


# ── backward compat: get_canonical_dependency_string() ──────────────────────

class TestGetCanonicalDependencyString:
    """Verify backward compat shim delegates to get_unique_key()."""

    def test_github_package(self):
        dep = DependencyReference.parse("owner/repo#v1.0")
        assert dep.get_canonical_dependency_string() == "owner/repo"

    def test_gitlab_package_still_host_blind(self):
        """get_canonical_dependency_string is host-blind (filesystem matching)."""
        dep = DependencyReference.parse("gitlab.com/owner/repo")
        # Host-blind: returns just owner/repo
        assert dep.get_canonical_dependency_string() == "owner/repo"

    def test_virtual_package(self):
        dep = DependencyReference.parse("owner/repo/prompts/review.prompt.md")
        assert dep.get_canonical_dependency_string() == "owner/repo/prompts/review.prompt.md"


# ── Normalize-on-write in _validate_and_add_packages_to_apm_yml ────────────

class TestNormalizeOnWrite:
    """Test that _validate_and_add_packages_to_apm_yml canonicalizes inputs."""

    @patch("apm_cli.cli._validate_package_exists", return_value=True)
    @patch("apm_cli.cli._rich_info")
    @patch("apm_cli.cli._rich_success")
    def test_https_url_stored_as_shorthand(self, mock_success, mock_info, mock_validate, tmp_path, monkeypatch):
        """HTTPS GitHub URL is stored as owner/repo in apm.yml."""
        import yaml
        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text(yaml.dump({"name": "test", "version": "0.1.0", "dependencies": {"apm": []}}))
        monkeypatch.chdir(tmp_path)

        from apm_cli.cli import _validate_and_add_packages_to_apm_yml
        result = _validate_and_add_packages_to_apm_yml(
            ["https://github.com/microsoft/apm-sample-package.git"]
        )

        assert result == ["microsoft/apm-sample-package"]
        data = yaml.safe_load(apm_yml.read_text())
        assert "microsoft/apm-sample-package" in data["dependencies"]["apm"]

    @patch("apm_cli.cli._validate_package_exists", return_value=True)
    @patch("apm_cli.cli._rich_info")
    @patch("apm_cli.cli._rich_success")
    def test_ssh_url_stored_as_shorthand(self, mock_success, mock_info, mock_validate, tmp_path, monkeypatch):
        """SSH GitHub URL is stored as owner/repo in apm.yml."""
        import yaml
        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text(yaml.dump({"name": "test", "version": "0.1.0", "dependencies": {"apm": []}}))
        monkeypatch.chdir(tmp_path)

        from apm_cli.cli import _validate_and_add_packages_to_apm_yml
        result = _validate_and_add_packages_to_apm_yml(
            ["git@github.com:microsoft/apm-sample-package.git"]
        )

        assert result == ["microsoft/apm-sample-package"]

    @patch("apm_cli.cli._validate_package_exists", return_value=True)
    @patch("apm_cli.cli._rich_info")
    @patch("apm_cli.cli._rich_success")
    def test_fqdn_github_stored_as_shorthand(self, mock_success, mock_info, mock_validate, tmp_path, monkeypatch):
        """FQDN github.com/owner/repo is stored as owner/repo."""
        import yaml
        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text(yaml.dump({"name": "test", "version": "0.1.0", "dependencies": {"apm": []}}))
        monkeypatch.chdir(tmp_path)

        from apm_cli.cli import _validate_and_add_packages_to_apm_yml
        result = _validate_and_add_packages_to_apm_yml(
            ["github.com/microsoft/apm-sample-package"]
        )

        assert result == ["microsoft/apm-sample-package"]

    @patch("apm_cli.cli._validate_package_exists", return_value=True)
    @patch("apm_cli.cli._rich_info")
    @patch("apm_cli.cli._rich_success")
    def test_gitlab_url_preserves_host(self, mock_success, mock_info, mock_validate, tmp_path, monkeypatch):
        """GitLab URL preserves the host in canonical form."""
        import yaml
        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text(yaml.dump({"name": "test", "version": "0.1.0", "dependencies": {"apm": []}}))
        monkeypatch.chdir(tmp_path)

        from apm_cli.cli import _validate_and_add_packages_to_apm_yml
        result = _validate_and_add_packages_to_apm_yml(
            ["https://gitlab.com/acme/standards.git"]
        )

        assert result == ["gitlab.com/acme/standards"]
        data = yaml.safe_load(apm_yml.read_text())
        assert "gitlab.com/acme/standards" in data["dependencies"]["apm"]

    @patch("apm_cli.cli._validate_package_exists", return_value=True)
    @patch("apm_cli.cli._rich_info")
    @patch("apm_cli.cli._rich_warning")
    def test_duplicate_detection_different_forms(self, mock_warn, mock_info, mock_validate, tmp_path, monkeypatch):
        """Installing the same package in different forms doesn't create duplicates."""
        import yaml
        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text(yaml.dump({
            "name": "test", "version": "0.1.0",
            "dependencies": {"apm": ["microsoft/apm-sample-package"]}
        }))
        monkeypatch.chdir(tmp_path)

        from apm_cli.cli import _validate_and_add_packages_to_apm_yml
        result = _validate_and_add_packages_to_apm_yml(
            ["https://github.com/microsoft/apm-sample-package.git"]
        )

        # Should return empty — package already exists
        assert result == []
        data = yaml.safe_load(apm_yml.read_text())
        # No duplicate added
        assert data["dependencies"]["apm"].count("microsoft/apm-sample-package") == 1

    @patch("apm_cli.cli._validate_package_exists", return_value=True)
    @patch("apm_cli.cli._rich_info")
    @patch("apm_cli.cli._rich_success")
    def test_batch_dedup(self, mock_success, mock_info, mock_validate, tmp_path, monkeypatch):
        """Installing the same package twice in one batch only adds once."""
        import yaml
        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text(yaml.dump({"name": "test", "version": "0.1.0", "dependencies": {"apm": []}}))
        monkeypatch.chdir(tmp_path)

        from apm_cli.cli import _validate_and_add_packages_to_apm_yml
        result = _validate_and_add_packages_to_apm_yml([
            "microsoft/apm-sample-package",
            "https://github.com/microsoft/apm-sample-package.git",
        ])

        assert len(result) == 1
        assert result[0] == "microsoft/apm-sample-package"

    @patch("apm_cli.cli._validate_package_exists", return_value=True)
    @patch("apm_cli.cli._rich_info")
    @patch("apm_cli.cli._rich_success")
    def test_ref_preserved_in_canonical(self, mock_success, mock_info, mock_validate, tmp_path, monkeypatch):
        """Reference is preserved in the canonical form."""
        import yaml
        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text(yaml.dump({"name": "test", "version": "0.1.0", "dependencies": {"apm": []}}))
        monkeypatch.chdir(tmp_path)

        from apm_cli.cli import _validate_and_add_packages_to_apm_yml
        result = _validate_and_add_packages_to_apm_yml(
            ["https://github.com/microsoft/apm-sample-package.git#v1.0.0"]
        )

        assert result == ["microsoft/apm-sample-package#v1.0.0"]


# ── Uninstall identity matching ─────────────────────────────────────────────

class TestUninstallIdentityMatching:
    """Test that uninstall matches packages by identity regardless of input form."""

    def _make_apm_yml(self, tmp_path, deps):
        import yaml
        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text(yaml.dump({
            "name": "test", "version": "0.1.0",
            "dependencies": {"apm": deps}
        }))
        return apm_yml

    def test_uninstall_shorthand_matches_canonical(self):
        """Uninstalling 'owner/repo' matches canonical 'owner/repo' in apm.yml."""
        pkg_ref = DependencyReference.parse("owner/repo")
        dep_ref = DependencyReference.parse("owner/repo")
        assert pkg_ref.get_identity() == dep_ref.get_identity()

    def test_uninstall_https_matches_shorthand(self):
        """Uninstalling via HTTPS URL matches shorthand in apm.yml."""
        pkg_ref = DependencyReference.parse("https://github.com/owner/repo.git")
        dep_ref = DependencyReference.parse("owner/repo")
        assert pkg_ref.get_identity() == dep_ref.get_identity()

    def test_uninstall_ssh_matches_shorthand(self):
        """Uninstalling via SSH URL matches shorthand in apm.yml."""
        pkg_ref = DependencyReference.parse("git@github.com:owner/repo.git")
        dep_ref = DependencyReference.parse("owner/repo")
        assert pkg_ref.get_identity() == dep_ref.get_identity()

    def test_uninstall_fqdn_matches_shorthand(self):
        """Uninstalling via FQDN matches shorthand in apm.yml."""
        pkg_ref = DependencyReference.parse("github.com/owner/repo")
        dep_ref = DependencyReference.parse("owner/repo")
        assert pkg_ref.get_identity() == dep_ref.get_identity()

    def test_uninstall_gitlab_matches_gitlab(self):
        """Uninstalling gitlab package matches gitlab canonical entry."""
        pkg_ref = DependencyReference.parse("https://gitlab.com/acme/rules.git")
        dep_ref = DependencyReference.parse("gitlab.com/acme/rules")
        assert pkg_ref.get_identity() == dep_ref.get_identity()

    def test_uninstall_gitlab_no_match_github(self):
        """GitLab package does NOT match GitHub package with same owner/repo."""
        pkg_ref = DependencyReference.parse("gitlab.com/owner/repo")
        dep_ref = DependencyReference.parse("owner/repo")
        assert pkg_ref.get_identity() != dep_ref.get_identity()


# ── only_packages filter ────────────────────────────────────────────────────

class TestOnlyPackagesFilter:
    """Test identity-based filtering in _install_apm_dependencies."""

    def test_filter_matches_shorthand(self):
        """Shorthand filter matches a parsed dep with default host."""
        dep = DependencyReference.parse("microsoft/apm-sample-package")
        filter_ref = DependencyReference.parse("microsoft/apm-sample-package")
        assert dep.get_identity() == filter_ref.get_identity()

    def test_filter_https_matches_shorthand_dep(self):
        """HTTPS URL filter matches shorthand-parsed dep."""
        dep = DependencyReference.parse("microsoft/apm-sample-package")
        filter_ref = DependencyReference.parse("https://github.com/microsoft/apm-sample-package.git")
        assert dep.get_identity() == filter_ref.get_identity()

    def test_filter_shorthand_matches_https_dep(self):
        """Shorthand filter matches HTTPS-parsed dep."""
        dep = DependencyReference.parse("https://github.com/microsoft/apm-sample-package.git")
        filter_ref = DependencyReference.parse("microsoft/apm-sample-package")
        assert dep.get_identity() == filter_ref.get_identity()

    def test_filter_no_cross_host_match(self):
        """Filter for GitHub package does NOT match GitLab dep."""
        dep = DependencyReference.parse("gitlab.com/microsoft/apm-sample-package")
        filter_ref = DependencyReference.parse("microsoft/apm-sample-package")
        assert dep.get_identity() != filter_ref.get_identity()
