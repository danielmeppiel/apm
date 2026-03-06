"""Tests for --update flag behavior in install command (Bug #190).

Verifies that `apm install --update` bypasses lockfile-pinned SHAs
and re-fetches the latest content, especially for subdirectory packages.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from apm_cli.models.apm_package import (
    DependencyReference,
    GitReferenceType,
)


class TestSkipDownloadWithUpdateFlag:
    """Test that skip_download respects --update (update_refs=True).

    The skip_download condition must NOT skip when update_refs is True,
    even if the package was already resolved by the BFS callback.
    """

    def _build_skip_download(self, *, install_path_exists, is_cacheable, update_refs,
                              already_resolved, lockfile_match):
        """Reproduce the skip_download condition from cli.py."""
        return install_path_exists and (
            (is_cacheable and not update_refs) or (already_resolved and not update_refs) or lockfile_match
        )

    def test_already_resolved_skips_without_update(self):
        """Without --update, already_resolved packages should be skipped."""
        assert self._build_skip_download(
            install_path_exists=True,
            is_cacheable=False,
            update_refs=False,
            already_resolved=True,
            lockfile_match=False,
        ) is True

    def test_already_resolved_does_not_skip_with_update(self):
        """With --update, already_resolved packages must NOT be skipped."""
        assert self._build_skip_download(
            install_path_exists=True,
            is_cacheable=False,
            update_refs=True,
            already_resolved=True,
            lockfile_match=False,
        ) is False

    def test_cacheable_skips_without_update(self):
        """Without --update, cacheable (tag/commit) packages should be skipped."""
        assert self._build_skip_download(
            install_path_exists=True,
            is_cacheable=True,
            update_refs=False,
            already_resolved=False,
            lockfile_match=False,
        ) is True

    def test_cacheable_does_not_skip_with_update(self):
        """With --update, cacheable packages must NOT be skipped."""
        assert self._build_skip_download(
            install_path_exists=True,
            is_cacheable=True,
            update_refs=True,
            already_resolved=False,
            lockfile_match=False,
        ) is False

    def test_lockfile_match_always_skips(self):
        """lockfile_match should always skip (not gated by update_refs because
        the lockfile_match check itself is already gated by `not update_refs`)."""
        assert self._build_skip_download(
            install_path_exists=True,
            is_cacheable=False,
            update_refs=True,
            already_resolved=False,
            lockfile_match=True,
        ) is True

    def test_no_install_path_never_skips(self):
        """If install path doesn't exist, never skip regardless of other flags."""
        assert self._build_skip_download(
            install_path_exists=False,
            is_cacheable=True,
            update_refs=False,
            already_resolved=True,
            lockfile_match=True,
        ) is False


class TestDownloadRefLockfileOverride:
    """Test that lockfile SHA override is gated behind `not update_refs`.

    When --update is used, the download ref should NOT be overridden with
    the lockfile's pinned SHA. The package should be fetched at its
    original reference (or default branch).
    """

    @staticmethod
    def _build_download_ref(dep_ref, existing_lockfile, update_refs):
        """Reproduce the download_ref construction logic from cli.py.

        This mirrors the sequential download path. The same logic applies
        to the parallel pre-download path.
        """
        download_ref = str(dep_ref)
        if existing_lockfile and not update_refs:
            locked_dep = existing_lockfile.get_dependency(dep_ref.get_unique_key())
            if locked_dep and locked_dep.resolved_commit and locked_dep.resolved_commit != "cached":
                base_ref = dep_ref.repo_url
                if dep_ref.virtual_path:
                    base_ref = f"{base_ref}/{dep_ref.virtual_path}"
                download_ref = f"{base_ref}#{locked_dep.resolved_commit}"
        return download_ref

    def _make_subdirectory_dep(self):
        return DependencyReference(
            repo_url="owner/monorepo",
            host="github.com",
            reference=None,
            virtual_path="packages/my-skill",
            is_virtual=True,
        )

    def _make_regular_dep(self):
        return DependencyReference(
            repo_url="owner/repo",
            host="github.com",
            reference="main",
        )

    def _mock_lockfile(self, dep_ref, resolved_commit="abc123def456"):
        lockfile = Mock()
        locked_dep = Mock()
        locked_dep.resolved_commit = resolved_commit
        lockfile.get_dependency = Mock(return_value=locked_dep)
        return lockfile

    def test_subdirectory_lockfile_override_without_update(self):
        """Without --update, subdirectory download ref uses locked SHA."""
        dep = self._make_subdirectory_dep()
        lockfile = self._mock_lockfile(dep)

        ref = self._build_download_ref(dep, lockfile, update_refs=False)
        assert "#abc123def456" in ref
        assert ref == "owner/monorepo/packages/my-skill#abc123def456"

    def test_subdirectory_no_lockfile_override_with_update(self):
        """With --update, subdirectory download ref must NOT use locked SHA."""
        dep = self._make_subdirectory_dep()
        lockfile = self._mock_lockfile(dep)

        ref = self._build_download_ref(dep, lockfile, update_refs=True)
        assert "#abc123def456" not in ref
        assert ref == str(dep)

    def test_regular_lockfile_override_without_update(self):
        """Without --update, regular package download ref uses locked SHA."""
        dep = self._make_regular_dep()
        lockfile = self._mock_lockfile(dep)

        ref = self._build_download_ref(dep, lockfile, update_refs=False)
        assert "#abc123def456" in ref

    def test_regular_no_lockfile_override_with_update(self):
        """With --update, regular package download ref must NOT use locked SHA."""
        dep = self._make_regular_dep()
        lockfile = self._mock_lockfile(dep)

        ref = self._build_download_ref(dep, lockfile, update_refs=True)
        assert "#abc123def456" not in ref

    def test_no_lockfile_returns_original_ref(self):
        """Without a lockfile, download ref is the original dependency string."""
        dep = self._make_subdirectory_dep()
        ref = self._build_download_ref(dep, existing_lockfile=None, update_refs=False)
        assert ref == str(dep)

    def test_cached_lockfile_entry_not_overridden(self):
        """Lockfile entries with resolved_commit='cached' should not override."""
        dep = self._make_subdirectory_dep()
        lockfile = self._mock_lockfile(dep, resolved_commit="cached")

        ref = self._build_download_ref(dep, lockfile, update_refs=False)
        assert ref == str(dep)


class TestPreDownloadRefLockfileOverride:
    """Same as TestDownloadRefLockfileOverride but for the parallel pre-download path."""

    @staticmethod
    def _build_pre_download_ref(dep_ref, existing_lockfile, update_refs):
        """Reproduce the _pd_dlref construction logic from cli.py's pre-download loop."""
        _pd_dlref = str(dep_ref)
        if existing_lockfile and not update_refs:
            _pd_locked = existing_lockfile.get_dependency(dep_ref.get_unique_key())
            if _pd_locked and _pd_locked.resolved_commit and _pd_locked.resolved_commit != "cached":
                _pd_base = dep_ref.repo_url
                if dep_ref.virtual_path:
                    _pd_base = f"{_pd_base}/{dep_ref.virtual_path}"
                _pd_dlref = f"{_pd_base}#{_pd_locked.resolved_commit}"
        return _pd_dlref

    def _make_subdirectory_dep(self):
        return DependencyReference(
            repo_url="owner/monorepo",
            host="github.com",
            reference=None,
            virtual_path="packages/my-skill",
            is_virtual=True,
        )

    def _mock_lockfile(self, dep_ref, resolved_commit="abc123def456"):
        lockfile = Mock()
        locked_dep = Mock()
        locked_dep.resolved_commit = resolved_commit
        lockfile.get_dependency = Mock(return_value=locked_dep)
        return lockfile

    def test_pre_download_no_lockfile_override_with_update(self):
        """With --update, pre-download ref must NOT use locked SHA."""
        dep = self._make_subdirectory_dep()
        lockfile = self._mock_lockfile(dep)

        ref = self._build_pre_download_ref(dep, lockfile, update_refs=True)
        assert "#abc123def456" not in ref

    def test_pre_download_lockfile_override_without_update(self):
        """Without --update, pre-download ref uses locked SHA."""
        dep = self._make_subdirectory_dep()
        lockfile = self._mock_lockfile(dep)

        ref = self._build_pre_download_ref(dep, lockfile, update_refs=False)
        assert "#abc123def456" in ref
