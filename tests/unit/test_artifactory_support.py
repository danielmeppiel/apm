"""Tests for JFrog Artifactory VCS repository support.

Tests cover:
- github_host.py: Artifactory path detection, parsing, and URL building
- apm_package.py: DependencyReference parsing for Artifactory URLs (Mode 1 & Mode 2)
- github_downloader.py: Artifactory download methods and proxy routing
- token_manager.py: Artifactory token precedence
"""

import io
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from urllib.parse import urlparse

import pytest

from apm_cli.core.token_manager import GitHubTokenManager
from apm_cli.deps.github_downloader import GitHubPackageDownloader
from apm_cli.models.apm_package import (
    DependencyReference,
    GitReferenceType,
    ResolvedReference,
)
from apm_cli.utils.github_host import (
    build_artifactory_archive_url,
    is_artifactory_path,
    parse_artifactory_path,
)

# ── github_host.py: Artifactory path helpers ──


class TestIsArtifactoryPath:
    """Test is_artifactory_path detection."""

    def test_valid_artifactory_path(self):
        """Standard Artifactory VCS path with 4 segments."""
        assert is_artifactory_path(["artifactory", "github", "microsoft", "apm"])

    def test_valid_artifactory_path_with_virtual(self):
        """Artifactory path with virtual sub-path (5+ segments)."""
        assert is_artifactory_path(
            ["artifactory", "github", "owner", "repo", "skills", "review"]
        )

    def test_case_insensitive(self):
        """Detection should be case-insensitive on the 'artifactory' segment."""
        assert is_artifactory_path(["Artifactory", "github", "owner", "repo"])
        assert is_artifactory_path(["ARTIFACTORY", "github", "owner", "repo"])

    def test_too_few_segments(self):
        """Need at least 4 segments: artifactory/key/owner/repo."""
        assert not is_artifactory_path(["artifactory", "github", "owner"])
        assert not is_artifactory_path(["artifactory", "github"])
        assert not is_artifactory_path(["artifactory"])

    def test_not_artifactory(self):
        """Non-Artifactory paths should return False."""
        assert not is_artifactory_path(["owner", "repo"])
        assert not is_artifactory_path(["github.com", "owner", "repo"])
        assert not is_artifactory_path([])

    def test_different_repo_keys(self):
        """Various Artifactory repo keys should work."""
        assert is_artifactory_path(["artifactory", "github", "owner", "repo"])
        assert is_artifactory_path(["artifactory", "gitlab", "owner", "repo"])
        assert is_artifactory_path(["artifactory", "my-proxy", "owner", "repo"])


class TestParseArtifactoryPath:
    """Test parse_artifactory_path extraction."""

    def test_basic_parse(self):
        """Parse standard artifactory/key/owner/repo."""
        result = parse_artifactory_path(
            ["artifactory", "github", "microsoft", "apm-sample-package"]
        )
        assert result is not None
        prefix, owner, repo, vpath = result
        assert prefix == "artifactory/github"
        assert owner == "microsoft"
        assert repo == "apm-sample-package"
        assert vpath is None

    def test_with_virtual_path(self):
        """Parse path with virtual sub-path after owner/repo."""
        result = parse_artifactory_path(
            ["artifactory", "github", "owner", "repo", "skills", "review"]
        )
        assert result is not None
        prefix, owner, repo, vpath = result
        assert prefix == "artifactory/github"
        assert owner == "owner"
        assert repo == "repo"
        assert vpath == "skills/review"

    def test_returns_none_for_invalid(self):
        """Return None for non-Artifactory paths."""
        assert parse_artifactory_path(["owner", "repo"]) is None
        assert parse_artifactory_path([]) is None
        assert parse_artifactory_path(["artifactory", "key"]) is None

    def test_different_repo_key(self):
        """Repo key is preserved in the prefix."""
        result = parse_artifactory_path(["artifactory", "my-proxy", "team", "project"])
        assert result[0] == "artifactory/my-proxy"


class TestBuildArtifactoryArchiveUrl:
    """Test build_artifactory_archive_url URL construction."""

    def test_default_ref(self):
        """Build URLs with default ref (main) — includes GitHub and GitLab patterns."""
        urls = build_artifactory_archive_url(
            "art.example.com", "artifactory/github", "owner", "repo"
        )
        assert any("/archive/refs/heads/main.zip" in u for u in urls)
        assert any("/-/archive/main/repo-main.zip" in u for u in urls)
        assert any("/archive/refs/tags/main.zip" in u for u in urls)

    def test_custom_ref(self):
        """Build URLs with a custom branch/tag ref."""
        urls = build_artifactory_archive_url(
            "art.example.com", "artifactory/github", "owner", "repo", ref="v1.0.0"
        )
        assert any("/refs/heads/v1.0.0.zip" in u for u in urls)
        assert any("/-/archive/v1.0.0/repo-v1.0.0.zip" in u for u in urls)

    def test_real_artifactory_host(self):
        """Build URLs matching real Artifactory pattern."""
        urls = build_artifactory_archive_url(
            "artifactory.example.com",
            "artifactory/github",
            "microsoft",
            "apm-sample-package",
            ref="main",
        )
        parsed = urlparse(urls[0])
        assert parsed.scheme == "https"
        assert parsed.hostname == "artifactory.example.com"
        assert parsed.path == "/artifactory/github/microsoft/apm-sample-package/archive/refs/heads/main.zip"


# ── apm_package.py: DependencyReference Artifactory parsing ──


class TestDependencyReferenceArtifactory:
    """Test DependencyReference.parse() for Artifactory URLs."""

    def test_parse_explicit_fqdn_mode1(self):
        """Mode 1: Explicit Artifactory FQDN in dependency string."""
        dep = DependencyReference.parse(
            "artifactory.example.com/artifactory/github/microsoft/apm-sample-package"
        )
        assert dep.host == "artifactory.example.com"
        assert dep.artifactory_prefix == "artifactory/github"
        assert dep.repo_url == "microsoft/apm-sample-package"
        assert dep.is_artifactory()

    def test_parse_with_branch_ref(self):
        """Artifactory FQDN with branch reference."""
        dep = DependencyReference.parse(
            "artifactory.example.com/artifactory/github/microsoft/apm-sample-package#develop"
        )
        assert dep.is_artifactory()
        assert dep.reference == "develop"
        assert dep.repo_url == "microsoft/apm-sample-package"

    def test_parse_with_tag_ref(self):
        """Artifactory FQDN with tag reference."""
        dep = DependencyReference.parse(
            "art.example.com/artifactory/github/owner/repo#v1.0.0"
        )
        assert dep.is_artifactory()
        assert dep.reference == "v1.0.0"

    def test_not_artifactory_for_plain_github(self):
        """Plain GitHub refs should NOT be Artifactory."""
        dep = DependencyReference.parse("microsoft/apm-sample-package")
        assert not dep.is_artifactory()
        assert dep.artifactory_prefix is None

    def test_not_artifactory_for_other_fqdn(self):
        """Non-Artifactory FQDN hosts should NOT be Artifactory."""
        dep = DependencyReference.parse("gitlab.com/owner/repo")
        assert not dep.is_artifactory()

    def test_canonical_form_preserves_artifactory(self):
        """Canonical form should include host + artifactory prefix."""
        dep = DependencyReference.parse("art.example.com/artifactory/github/owner/repo")
        canonical = dep.to_canonical()
        assert canonical == "art.example.com/artifactory/github/owner/repo"

    def test_install_path_strips_artifactory(self):
        """Install path should be just owner/repo (no Artifactory prefix)."""
        dep = DependencyReference.parse(
            "art.example.com/artifactory/github/microsoft/apm-sample-package"
        )
        install_path = dep.get_install_path(Path("apm_modules"))
        # Should be just owner/repo, not include artifactory prefix or host
        path_str = str(install_path).replace("\\", "/")
        assert "microsoft/apm-sample-package" in path_str
        assert "artifactory" not in path_str

    def test_to_github_url_artifactory(self):
        """to_github_url should generate correct Artifactory HTTPS URL."""
        dep = DependencyReference.parse("art.example.com/artifactory/github/owner/repo")
        url = dep.to_github_url()
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.hostname == "art.example.com"
        assert parsed.path == "/artifactory/github/owner/repo"

    def test_str_includes_artifactory_prefix(self):
        """String representation should include Artifactory prefix."""
        dep = DependencyReference.parse("art.example.com/artifactory/github/owner/repo")
        s = str(dep)
        parts = s.split("/")
        assert parts[0] == "art.example.com"
        assert parts[1] == "artifactory"
        assert parts[2] == "github"

    def test_get_identity_includes_artifactory(self):
        """Identity string should include Artifactory prefix for uniqueness."""
        dep = DependencyReference.parse("art.example.com/artifactory/github/owner/repo")
        identity = dep.get_identity()
        parts = identity.split("/")
        assert "artifactory" in parts

    def test_resolved_reference_str_no_commit(self):
        """ResolvedReference.__str__ handles None resolved_commit (Artifactory case)."""
        ref = ResolvedReference(
            original_ref="owner/repo#main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit=None,
            ref_name="main",
        )
        assert str(ref) == "main"

    def test_different_repo_keys(self):
        """Different Artifactory repo keys should parse correctly."""
        dep = DependencyReference.parse(
            "art.example.com/artifactory/my-proxy/team/project"
        )
        assert dep.artifactory_prefix == "artifactory/my-proxy"
        assert dep.repo_url == "team/project"


# ── token_manager.py: Artifactory token support ──


class TestArtifactoryTokenManager:
    """Test token manager Artifactory support."""

    def test_artifactory_token_precedence_exists(self):
        """TOKEN_PRECEDENCE should have artifactory_modules entry."""
        manager = GitHubTokenManager()
        assert "artifactory_modules" in manager.TOKEN_PRECEDENCE
        assert (
            "ARTIFACTORY_APM_TOKEN" in manager.TOKEN_PRECEDENCE["artifactory_modules"]
        )

    def test_get_artifactory_token(self):
        """get_token_for_purpose should return Artifactory token."""
        manager = GitHubTokenManager()
        env = {"ARTIFACTORY_APM_TOKEN": "test-art-token"}
        token = manager.get_token_for_purpose("artifactory_modules", env)
        assert token == "test-art-token"

    def test_no_artifactory_token(self):
        """get_token_for_purpose returns None when no Artifactory token set."""
        manager = GitHubTokenManager()
        env = {"GITHUB_TOKEN": "gh-token"}
        token = manager.get_token_for_purpose("artifactory_modules", env)
        assert token is None


# ── github_downloader.py: Artifactory download methods ──


class TestArtifactoryDownloader:
    """Test GitHubPackageDownloader Artifactory methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.downloader = GitHubPackageDownloader()
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_artifactory_token_setup(self):
        """Downloader picks up ARTIFACTORY_APM_TOKEN from environment."""
        with patch.dict(
            os.environ, {"ARTIFACTORY_APM_TOKEN": "art-token-123"}, clear=True
        ):
            dl = GitHubPackageDownloader()
            assert dl.has_artifactory_token is True
            assert dl.artifactory_token == "art-token-123"

    def test_no_artifactory_token(self):
        """Downloader handles missing Artifactory token gracefully."""
        with patch.dict(os.environ, {}, clear=True):
            dl = GitHubPackageDownloader()
            assert dl.has_artifactory_token is False
            assert dl.artifactory_token is None

    def test_get_artifactory_headers_with_token(self):
        """Headers include Bearer token when token is set."""
        with patch.dict(os.environ, {"ARTIFACTORY_APM_TOKEN": "my-token"}, clear=True):
            dl = GitHubPackageDownloader()
            headers = dl._get_artifactory_headers()
            assert headers == {"Authorization": "Bearer my-token"}

    def test_get_artifactory_headers_without_token(self):
        """Headers are empty when no token is set."""
        with patch.dict(os.environ, {}, clear=True):
            dl = GitHubPackageDownloader()
            headers = dl._get_artifactory_headers()
            assert headers == {}

    def test_should_use_artifactory_proxy_github(self):
        """GitHub-hosted deps should route through Artifactory proxy."""
        dep = DependencyReference.parse("microsoft/apm-sample-package")
        assert self.downloader._should_use_artifactory_proxy(dep)

    def test_should_not_proxy_ado(self):
        """Azure DevOps deps should NOT route through Artifactory proxy."""
        dep = DependencyReference.parse("dev.azure.com/myorg/myproject/_git/myrepo")
        assert not self.downloader._should_use_artifactory_proxy(dep)

    def test_should_not_proxy_already_artifactory(self):
        """Already-Artifactory deps should NOT be double-proxied."""
        dep = DependencyReference.parse("art.example.com/artifactory/github/owner/repo")
        assert not self.downloader._should_use_artifactory_proxy(dep)

    def test_should_not_proxy_non_github_fqdn(self):
        """Non-GitHub FQDN hosts should NOT route through Artifactory."""
        dep = DependencyReference.parse("gitlab.com/owner/repo")
        assert not self.downloader._should_use_artifactory_proxy(dep)

    def test_parse_artifactory_base_url_valid(self):
        """Parse valid ARTIFACTORY_BASE_URL."""
        with patch.dict(
            os.environ,
            {"ARTIFACTORY_BASE_URL": "https://art.example.com/artifactory/github"},
        ):
            result = self.downloader._parse_artifactory_base_url()
            assert result is not None
            host, prefix, scheme = result
            assert host == "art.example.com"
            assert prefix == "artifactory/github"
            assert scheme == "https"

    def test_parse_artifactory_base_url_trailing_slash(self):
        """Trailing slash in URL should be stripped."""
        with patch.dict(
            os.environ,
            {"ARTIFACTORY_BASE_URL": "https://art.example.com/artifactory/github/"},
        ):
            result = self.downloader._parse_artifactory_base_url()
            assert result is not None
            host, prefix, scheme = result
            assert prefix == "artifactory/github"

    def test_parse_artifactory_base_url_not_set(self):
        """Returns None when env var is not set."""
        with patch.dict(os.environ, {}, clear=True):
            result = self.downloader._parse_artifactory_base_url()
            assert result is None

    def test_parse_artifactory_base_url_empty(self):
        """Returns None for empty string."""
        with patch.dict(os.environ, {"ARTIFACTORY_BASE_URL": ""}, clear=True):
            result = self.downloader._parse_artifactory_base_url()
            assert result is None


class TestArtifactoryArchiveDownload:
    """Test _download_artifactory_archive zip handling."""

    def setup_method(self):
        self.downloader = GitHubPackageDownloader()
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_zip_bytes(self, root_prefix="repo-main/", files=None):
        """Create a zip archive in memory mimicking GitHub archive structure."""
        if files is None:
            files = {
                "apm.yml": b"name: test-package\nversion: 1.0.0\n",
                "README.md": b"# Test\n",
            }
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(root_prefix, "")  # root directory entry
            for name, content in files.items():
                zf.writestr(f"{root_prefix}{name}", content)
        return buf.getvalue()

    def test_successful_extraction(self):
        """Archive is downloaded and extracted with root prefix stripped."""
        zip_bytes = self._make_zip_bytes()
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.content = zip_bytes

        target = self.temp_dir / "pkg"
        with patch.object(self.downloader, "_resilient_get", return_value=mock_resp):
            self.downloader._download_artifactory_archive(
                "art.example.com",
                "artifactory/github",
                "owner",
                "repo",
                "main",
                target,
            )

        assert (target / "apm.yml").exists()
        assert (target / "README.md").exists()
        # Root prefix directory should NOT appear as a nested folder
        assert not (target / "repo-main").exists()

    def test_falls_back_to_tags_url(self):
        """When heads URL returns 404, falls back to tags URL."""
        zip_bytes = self._make_zip_bytes()
        mock_resp_404 = Mock()
        mock_resp_404.status_code = 404
        mock_resp_200 = Mock()
        mock_resp_200.status_code = 200
        mock_resp_200.content = zip_bytes

        target = self.temp_dir / "pkg"
        with patch.object(
            self.downloader,
            "_resilient_get",
            side_effect=[mock_resp_404, mock_resp_200],
        ):
            self.downloader._download_artifactory_archive(
                "art.example.com",
                "artifactory/github",
                "owner",
                "repo",
                "v1.0.0",
                target,
            )

        assert (target / "apm.yml").exists()

    def test_raises_on_all_failures(self):
        """Raises RuntimeError when both URLs fail."""
        mock_resp = Mock()
        mock_resp.status_code = 404

        target = self.temp_dir / "pkg"
        with patch.object(self.downloader, "_resilient_get", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Failed to download"):
                self.downloader._download_artifactory_archive(
                    "art.example.com",
                    "artifactory/github",
                    "owner",
                    "repo",
                    "main",
                    target,
                )

    def test_raises_on_empty_archive(self):
        """Raises RuntimeError for empty zip archive."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w"):
            pass  # empty zip
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.content = buf.getvalue()

        target = self.temp_dir / "pkg"
        with patch.object(self.downloader, "_resilient_get", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Empty archive"):
                self.downloader._download_artifactory_archive(
                    "art.example.com",
                    "artifactory/github",
                    "owner",
                    "repo",
                    "main",
                    target,
                )

    def test_nested_directories_extracted(self):
        """Nested directories within the archive are properly extracted."""
        files = {
            "apm.yml": b"name: test\nversion: 1.0.0\n",
            "skills/review.prompt.md": b"# Review\n",
            "skills/debug.prompt.md": b"# Debug\n",
        }
        zip_bytes = self._make_zip_bytes(files=files)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.content = zip_bytes

        target = self.temp_dir / "pkg"
        with patch.object(self.downloader, "_resilient_get", return_value=mock_resp):
            self.downloader._download_artifactory_archive(
                "art.example.com",
                "artifactory/github",
                "owner",
                "repo",
                "main",
                target,
            )

        assert (target / "skills" / "review.prompt.md").exists()
        assert (target / "skills" / "debug.prompt.md").exists()


class TestArtifactoryFileDownload:
    """Test _download_file_from_artifactory single-file extraction."""

    def setup_method(self):
        self.downloader = GitHubPackageDownloader()

    def _make_zip_bytes(self, root_prefix="repo-main/", files=None):
        if files is None:
            files = {"apm.yml": b"name: test\nversion: 1.0.0\n"}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(root_prefix, "")
            for name, content in files.items():
                zf.writestr(f"{root_prefix}{name}", content)
        return buf.getvalue()

    def test_extract_single_file(self):
        """Extract a specific file from the archive."""
        zip_bytes = self._make_zip_bytes()
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.content = zip_bytes

        with patch.object(self.downloader, "_resilient_get", return_value=mock_resp):
            content = self.downloader._download_file_from_artifactory(
                "art.example.com",
                "artifactory/github",
                "owner",
                "repo",
                "apm.yml",
                "main",
            )

        assert b"name: test" in content

    def test_file_not_found(self):
        """Raises RuntimeError when file is not in the archive."""
        zip_bytes = self._make_zip_bytes()
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.content = zip_bytes

        with patch.object(self.downloader, "_resilient_get", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Failed to download file"):
                self.downloader._download_file_from_artifactory(
                    "art.example.com",
                    "artifactory/github",
                    "owner",
                    "repo",
                    "nonexistent.txt",
                    "main",
                )


class TestArtifactoryResolveReference:
    """Test resolve_git_reference for Artifactory deps."""

    def setup_method(self):
        self.downloader = GitHubPackageDownloader()

    def test_resolve_artifactory_ref_skips_git(self):
        """Artifactory deps should resolve without git clone."""
        dep = DependencyReference.parse(
            "art.example.com/artifactory/github/owner/repo#develop"
        )
        ref = self.downloader.resolve_git_reference(str(dep))
        # Should resolve without any git operations
        assert ref is not None
        assert ref.ref_name == "develop"
        assert ref.resolved_commit is None
        assert ref.ref_type == GitReferenceType.BRANCH

    def test_resolve_artifactory_default_ref(self):
        """Artifactory deps with no ref should default to main."""
        dep = DependencyReference.parse("art.example.com/artifactory/github/owner/repo")
        ref = self.downloader.resolve_git_reference(str(dep))
        assert ref.ref_name == "main"
        assert ref.resolved_commit is None


# ── Edge case and security tests ──


class TestArtifactoryEdgeCases:
    """Test edge cases and security fail-safes."""

    def setup_method(self):
        self.downloader = GitHubPackageDownloader()
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_zip_bytes(self, root_prefix="repo-main/", files=None):
        if files is None:
            files = {"apm.yml": b"name: test\nversion: 1.0.0\n"}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(root_prefix, "")
            for name, content in files.items():
                zf.writestr(f"{root_prefix}{name}", content)
        return buf.getvalue()

    def test_zip_path_traversal_blocked(self):
        """Zip entries with ../ path traversal are silently skipped (CWE-22)."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("repo-main/", "")
            zf.writestr("repo-main/apm.yml", b"name: test\nversion: 1.0.0\n")
            zf.writestr("repo-main/../../../etc/passwd", b"root:x:0:0")
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.content = buf.getvalue()

        target = self.temp_dir / "pkg"
        with patch.object(self.downloader, "_resilient_get", return_value=mock_resp):
            self.downloader._download_artifactory_archive(
                "art.example.com", "artifactory/github", "owner", "repo", "main", target
            )
        # Legitimate file extracted
        assert (target / "apm.yml").exists()
        # Traversal file must NOT exist anywhere outside target
        assert not (self.temp_dir / "etc").exists()

    def test_oversized_archive_rejected(self):
        """Archives exceeding ARTIFACTORY_MAX_ARCHIVE_MB are rejected."""
        zip_bytes = self._make_zip_bytes()
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.content = zip_bytes

        target = self.temp_dir / "pkg"
        # Set limit to 0 MB so any archive is too large
        with patch.dict(os.environ, {"ARTIFACTORY_MAX_ARCHIVE_MB": "0"}):
            with patch.object(
                self.downloader, "_resilient_get", return_value=mock_resp
            ):
                with pytest.raises(RuntimeError, match="Failed to download"):
                    self.downloader._download_artifactory_archive(
                        "art.example.com",
                        "artifactory/github",
                        "owner",
                        "repo",
                        "main",
                        target,
                    )

    def test_parse_base_url_rejects_ftp_scheme(self):
        """ARTIFACTORY_BASE_URL with non-http(s) scheme is rejected."""
        with patch.dict(
            os.environ,
            {"ARTIFACTORY_BASE_URL": "ftp://art.example.com/artifactory/github"},
        ):
            result = self.downloader._parse_artifactory_base_url()
            assert result is None

    def test_parse_base_url_rejects_no_scheme(self):
        """ARTIFACTORY_BASE_URL without scheme is rejected."""
        with patch.dict(
            os.environ,
            {"ARTIFACTORY_BASE_URL": "art.example.com/artifactory/github"},
        ):
            result = self.downloader._parse_artifactory_base_url()
            assert result is None

    def test_parse_base_url_accepts_http(self):
        """ARTIFACTORY_BASE_URL with http scheme is accepted (local dev)."""
        with patch.dict(
            os.environ,
            {"ARTIFACTORY_BASE_URL": "http://localhost:8081/artifactory/github"},
        ):
            result = self.downloader._parse_artifactory_base_url()
            assert result is not None
            assert result[0] == "localhost"
            assert result[2] == "http"

    def test_malformed_repo_url_raises(self):
        """Malformed repo_url without owner/repo raises ValueError."""
        dep = DependencyReference.parse("art.example.com/artifactory/github/owner/repo")
        # Manually corrupt the repo_url to simulate edge case
        dep.repo_url = "single-segment"
        with pytest.raises(ValueError, match="expected 'owner/repo' format"):
            self.downloader._download_package_from_artifactory(
                dep, self.temp_dir / "pkg"
            )

    def test_no_corporate_values_in_source(self):
        """Verify no corporate/internal hostnames leak into Artifactory-related source files."""
        import pathlib

        src_dir = pathlib.Path(__file__).resolve().parent.parent.parent / "src" / "apm_cli"
        target_files = [
            src_dir / "utils" / "github_host.py",
            src_dir / "deps" / "github_downloader.py",
            src_dir / "models" / "dependency.py",
            src_dir / "commands" / "install.py",
            src_dir / "core" / "token_manager.py",
        ]
        forbidden = ["checkpoint", "chkp"]
        for py_file in target_files:
            if not py_file.exists():
                continue
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for term in forbidden:
                assert (
                    term.lower() not in content.lower()
                ), f"Found forbidden term '{term}' in {py_file}"


# ── ARTIFACTORY_ONLY mode tests ──


class TestArtifactoryOnlyMode:
    """Test ARTIFACTORY_ONLY env var blocking direct git operations."""

    def setup_method(self):
        self.downloader = GitHubPackageDownloader()

    def test_is_artifactory_only_flag(self):
        """_is_artifactory_only reads env var."""
        with patch.dict(os.environ, {"ARTIFACTORY_ONLY": "1"}):
            assert GitHubPackageDownloader._is_artifactory_only()
        with patch.dict(os.environ, {"ARTIFACTORY_ONLY": "true"}):
            assert GitHubPackageDownloader._is_artifactory_only()
        with patch.dict(os.environ, {"ARTIFACTORY_ONLY": "yes"}):
            assert GitHubPackageDownloader._is_artifactory_only()
        with patch.dict(os.environ, {"ARTIFACTORY_ONLY": ""}):
            assert not GitHubPackageDownloader._is_artifactory_only()
        with patch.dict(os.environ, {}, clear=True):
            assert not GitHubPackageDownloader._is_artifactory_only()

    def test_proxy_routes_all_when_artifactory_only(self):
        """ARTIFACTORY_ONLY makes _should_use_artifactory_proxy return True for all non-Artifactory deps."""
        with patch.dict(os.environ, {"ARTIFACTORY_ONLY": "1"}):
            # GitHub dep
            dep = DependencyReference.parse("microsoft/apm-sample-package")
            assert self.downloader._should_use_artifactory_proxy(dep)
            # GitLab dep
            dep = DependencyReference.parse("gitlab.com/owner/repo")
            assert self.downloader._should_use_artifactory_proxy(dep)
            # ADO dep — also routed
            dep = DependencyReference.parse("dev.azure.com/org/project/_git/repo")
            assert self.downloader._should_use_artifactory_proxy(dep)

    def test_proxy_still_skips_explicit_artifactory(self):
        """Already-Artifactory deps should not be double-proxied even with ARTIFACTORY_ONLY."""
        with patch.dict(os.environ, {"ARTIFACTORY_ONLY": "1"}):
            dep = DependencyReference.parse("art.example.com/artifactory/github/owner/repo")
            assert not self.downloader._should_use_artifactory_proxy(dep)

    def test_resolve_ref_skips_git_when_artifactory_only(self):
        """resolve_git_reference skips git for all deps when ARTIFACTORY_ONLY is set."""
        with patch.dict(os.environ, {
            "ARTIFACTORY_ONLY": "1",
            "ARTIFACTORY_BASE_URL": "https://art.example.com/artifactory/github",
        }):
            dl = GitHubPackageDownloader()
            ref = dl.resolve_git_reference("gitlab.com/owner/repo#develop")
            assert ref.ref_name == "develop"
            assert ref.resolved_commit is None

    def test_download_package_errors_without_base_url(self):
        """ARTIFACTORY_ONLY without ARTIFACTORY_BASE_URL raises for non-Artifactory deps."""
        with patch.dict(os.environ, {"ARTIFACTORY_ONLY": "1"}, clear=True):
            dl = GitHubPackageDownloader()
            with pytest.raises(RuntimeError, match="ARTIFACTORY_ONLY is set"):
                dl.download_package("microsoft/some-package", Path("/tmp/test-pkg"))


# ── Lockfile: Artifactory host storage and reproducibility ──


class TestArtifactoryLockfile:
    """Test that lockfile correctly stores Artifactory host for reproducible installs."""

    def test_host_override_in_locked_dependency(self):
        """from_dependency_ref with host_override stores the override, not dep_ref.host."""
        from apm_cli.deps.lockfile import LockedDependency

        dep = DependencyReference.parse("anthropics/skills/skills/skill-creator")
        locked = LockedDependency.from_dependency_ref(
            dep_ref=dep,
            resolved_commit=None,
            depth=1,
            resolved_by=None,
            host_override="artifactory-remote.example.com/artifactory/github",
        )
        assert locked.host == "artifactory-remote.example.com/artifactory/github"
        assert locked.repo_url == "anthropics/skills"

    def test_host_override_none_falls_back_to_dep_ref(self):
        """Without host_override, dep_ref.host is used."""
        from apm_cli.deps.lockfile import LockedDependency

        dep = DependencyReference.parse("anthropics/skills")
        locked = LockedDependency.from_dependency_ref(
            dep_ref=dep,
            resolved_commit="abc123",
            depth=1,
            resolved_by=None,
        )
        assert locked.host == "github.com"

    def test_from_installed_packages_with_host_override(self):
        """from_installed_packages passes 6th tuple element as host_override."""
        from apm_cli.deps.lockfile import LockFile

        dep = DependencyReference.parse("owner/repo")
        packages = [
            (dep, "abc123def", 1, None, False, "art.example.com/artifactory/github"),
        ]
        lock = LockFile.from_installed_packages(packages, dependency_graph=None)
        locked = lock.get_dependency("owner/repo")
        assert locked.host == "art.example.com/artifactory/github"

    def test_from_installed_packages_backward_compat_4_tuple(self):
        """4-element tuples (no host override) still work."""
        from apm_cli.deps.lockfile import LockFile

        dep = DependencyReference.parse("owner/repo")
        packages = [
            (dep, "abc123def", 1, None),
        ]
        lock = LockFile.from_installed_packages(packages, dependency_graph=None)
        locked = lock.get_dependency("owner/repo")
        assert locked.host == "github.com"

    def test_lockfile_round_trip_with_artifactory_host(self):
        """Artifactory host survives write → read round trip."""
        from apm_cli.deps.lockfile import LockedDependency, LockFile

        dep = LockedDependency(
            repo_url="anthropics/skills",
            host="artifactory-remote.example.com/artifactory/github",
            virtual_path="skills/skill-creator",
            is_virtual=True,
        )
        lock = LockFile()
        lock.add_dependency(dep)
        yaml_str = lock.to_yaml()
        lock2 = LockFile.from_yaml(yaml_str)
        dep2 = lock2.get_dependency("anthropics/skills/skills/skill-creator")
        assert dep2.host == "artifactory-remote.example.com/artifactory/github"


# ── drift.py: build_download_ref prefers lockfile host ──


class TestBuildDownloadRefLockfileHost:
    """Test that build_download_ref uses lockfile host over manifest host."""

    def test_uses_lockfile_host_over_dep_ref_host(self):
        """Lockfile host takes precedence for reproducible installs."""
        from apm_cli.deps.lockfile import LockedDependency, LockFile
        from apm_cli.drift import build_download_ref

        dep = DependencyReference.parse("anthropics/skills/skills/skill-creator")
        lock = LockFile()
        locked = LockedDependency(
            repo_url="anthropics/skills",
            host="art.example.com/artifactory/github",
            resolved_commit="abc123def456",
            virtual_path="skills/skill-creator",
            is_virtual=True,
        )
        lock.add_dependency(locked)

        ref = build_download_ref(dep, lock, update_refs=False, ref_changed=False)
        assert ref.host == "art.example.com/artifactory/github"
        assert ref.reference == "abc123def456"

    def test_falls_back_to_dep_ref_host_without_lockfile(self):
        """Without a lockfile, uses dep_ref as-is."""
        from apm_cli.drift import build_download_ref

        dep = DependencyReference.parse("gitlab.example.com/owner/repo#v1.0")
        ref = build_download_ref(dep, None, update_refs=False, ref_changed=False)
        assert ref is dep  # same object — no lockfile, no changes

    def test_update_refs_ignores_lockfile_host(self):
        """--update mode uses manifest ref, not lockfile."""
        from apm_cli.deps.lockfile import LockedDependency, LockFile
        from apm_cli.drift import build_download_ref

        dep = DependencyReference.parse("anthropics/skills")
        lock = LockFile()
        locked = LockedDependency(
            repo_url="anthropics/skills",
            host="art.example.com/artifactory/github",
            resolved_commit="abc123",
        )
        lock.add_dependency(locked)

        ref = build_download_ref(dep, lock, update_refs=True, ref_changed=False)
        assert ref is dep  # --update returns original dep_ref unchanged


# ── ARTIFACTORY_ONLY conflict detection ──


class TestArtifactoryOnlyConflictDetection:
    """Test that ARTIFACTORY_ONLY + github.com lockfile is detected as a conflict."""

    def test_conflict_detected_for_github_locked_deps(self):
        """Lockfile with github.com host + ARTIFACTORY_ONLY should be flagged."""
        from apm_cli.deps.lockfile import LockedDependency, LockFile

        lock = LockFile()
        lock.add_dependency(LockedDependency(
            repo_url="anthropics/skills",
            host="github.com",
            resolved_commit="abc123",
            virtual_path="skills/skill-creator",
            is_virtual=True,
        ))

        # Simulate the conflict check logic from install.py
        github_locked = [
            dep for dep in lock.dependencies.values()
            if dep.source != "local" and dep.host in (None, "github.com")
        ]
        assert len(github_locked) == 1
        assert github_locked[0].repo_url == "anthropics/skills"

    def test_no_conflict_for_artifactory_locked_deps(self):
        """Lockfile with Artifactory host should not be flagged."""
        from apm_cli.deps.lockfile import LockedDependency, LockFile

        lock = LockFile()
        lock.add_dependency(LockedDependency(
            repo_url="anthropics/skills",
            host="art.example.com/artifactory/github",
            virtual_path="skills/skill-creator",
            is_virtual=True,
        ))

        github_locked = [
            dep for dep in lock.dependencies.values()
            if dep.source != "local" and dep.host in (None, "github.com")
        ]
        assert len(github_locked) == 0

    def test_no_conflict_for_local_deps(self):
        """Local dependencies should never be flagged as conflicting."""
        from apm_cli.deps.lockfile import LockedDependency, LockFile

        lock = LockFile()
        lock.add_dependency(LockedDependency(
            repo_url="my-local-pkg",
            host=None,
            source="local",
            local_path="./packages/my-local-pkg",
        ))

        github_locked = [
            dep for dep in lock.dependencies.values()
            if dep.source != "local" and dep.host in (None, "github.com")
        ]
        assert len(github_locked) == 0
