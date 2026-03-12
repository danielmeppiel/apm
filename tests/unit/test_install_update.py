"""Tests for --update flag behavior in install command (Bug #190).

Verifies that `apm install --update` bypasses lockfile-pinned SHAs
and re-fetches the latest content, especially for subdirectory packages.
"""

from unittest.mock import Mock

from apm_cli.models.apm_package import DependencyReference


class TestSkipDownloadWithUpdateFlag:
    """Test that skip_download respects --update (update_refs=True).

    The skip_download condition must NOT skip when update_refs is True,
    even if the package was already resolved by the BFS callback.
    """

    def _build_skip_download(self, *, install_path_exists, is_cacheable, update_refs,
                              already_resolved, lockfile_match):
        """Reproduce the skip_download condition from cli.py.

        Note: ``already_resolved`` is intentionally NOT gated by ``update_refs``.
        When the BFS resolver callback downloads a package during this run it is
        always a fresh fetch (the callback itself skips lockfile overrides when
        ``update_refs=True``), so re-downloading would be redundant.
        """
        return install_path_exists and (
            (is_cacheable and not update_refs) or already_resolved or lockfile_match
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

    def test_already_resolved_still_skips_with_update(self):
        """With --update, already_resolved packages are still skipped because
        the BFS callback already fetched them fresh in this run."""
        assert self._build_skip_download(
            install_path_exists=True,
            is_cacheable=False,
            update_refs=True,
            already_resolved=True,
            lockfile_match=False,
        ) is True

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


class TestRefChangedDetection:
    """Tests for ref-change detection (manifest ref vs lockfile resolved_ref).

    When the user changes the ref pin in apm.yml (e.g., from v1.0.0 to v2.0.0),
    apm install should detect the drift and re-download without --update.
    """

    @staticmethod
    def _is_ref_changed(dep_ref, existing_lockfile, update_refs):
        """Reproduce the ref_changed logic from install.py."""
        _locked_chk = (
            existing_lockfile.get_dependency(dep_ref.get_unique_key())
            if existing_lockfile and not update_refs
            else None
        )
        return bool(
            dep_ref.reference
            and _locked_chk is not None
            and _locked_chk.resolved_ref
            and dep_ref.reference != _locked_chk.resolved_ref
        )

    @staticmethod
    def _build_download_ref_with_ref_change(dep_ref, existing_lockfile, update_refs, ref_changed):
        """Reproduce the download_ref logic that respects ref_changed."""
        download_ref = str(dep_ref)
        if existing_lockfile and not update_refs and not ref_changed:
            locked_dep = existing_lockfile.get_dependency(dep_ref.get_unique_key())
            if locked_dep and locked_dep.resolved_commit and locked_dep.resolved_commit != "cached":
                base_ref = dep_ref.repo_url
                if dep_ref.virtual_path:
                    base_ref = f"{base_ref}/{dep_ref.virtual_path}"
                download_ref = f"{base_ref}#{locked_dep.resolved_commit}"
        return download_ref

    def _make_dep(self, reference):
        return DependencyReference(
            repo_url="owner/repo",
            host="github.com",
            reference=reference,
        )

    def _mock_lockfile(self, resolved_ref, resolved_commit="abc123"):
        lockfile = Mock()
        locked_dep = Mock()
        locked_dep.resolved_ref = resolved_ref
        locked_dep.resolved_commit = resolved_commit
        lockfile.get_dependency = Mock(return_value=locked_dep)
        return lockfile

    def test_no_drift_when_refs_match(self):
        """No drift when manifest ref matches lockfile resolved_ref."""
        dep = self._make_dep("v1.0.0")
        lockfile = self._mock_lockfile("v1.0.0")
        assert self._is_ref_changed(dep, lockfile, update_refs=False) is False

    def test_drift_when_ref_changed(self):
        """Drift detected when manifest ref changed from v1.0.0 to v2.0.0."""
        dep = self._make_dep("v2.0.0")
        lockfile = self._mock_lockfile("v1.0.0")
        assert self._is_ref_changed(dep, lockfile, update_refs=False) is True

    def test_no_drift_when_dep_has_no_explicit_ref(self):
        """No drift when dep has no explicit ref (using default branch)."""
        dep = self._make_dep(None)  # no explicit ref
        lockfile = self._mock_lockfile("main")
        assert self._is_ref_changed(dep, lockfile, update_refs=False) is False

    def test_no_drift_when_no_lockfile(self):
        """No drift when there is no lockfile (first install)."""
        dep = self._make_dep("v1.0.0")
        assert self._is_ref_changed(dep, None, update_refs=False) is False

    def test_no_drift_when_update_refs(self):
        """With --update, ref_changed is always False (update mode bypasses lockfile)."""
        dep = self._make_dep("v2.0.0")
        lockfile = self._mock_lockfile("v1.0.0")
        assert self._is_ref_changed(dep, lockfile, update_refs=True) is False

    def test_no_drift_when_locked_dep_has_no_resolved_ref(self):
        """No drift when locked dep has no resolved_ref (old lockfile format)."""
        dep = self._make_dep("v2.0.0")
        lockfile = Mock()
        locked_dep = Mock()
        locked_dep.resolved_ref = None
        locked_dep.resolved_commit = "abc123"
        lockfile.get_dependency = Mock(return_value=locked_dep)
        assert self._is_ref_changed(dep, lockfile, update_refs=False) is False

    def test_download_ref_uses_new_ref_when_changed(self):
        """When ref changed, download_ref should NOT use locked commit SHA."""
        dep = self._make_dep("v2.0.0")
        lockfile = self._mock_lockfile("v1.0.0", resolved_commit="abc123")
        ref_changed = self._is_ref_changed(dep, lockfile, update_refs=False)
        assert ref_changed is True
        download_ref = self._build_download_ref_with_ref_change(
            dep, lockfile, update_refs=False, ref_changed=ref_changed
        )
        assert "#abc123" not in download_ref
        assert "v2.0.0" in download_ref or str(dep) == download_ref

    def test_download_ref_uses_locked_sha_when_no_change(self):
        """When ref unchanged, download_ref SHOULD use locked commit SHA."""
        dep = self._make_dep("v1.0.0")
        lockfile = self._mock_lockfile("v1.0.0", resolved_commit="abc123")
        ref_changed = self._is_ref_changed(dep, lockfile, update_refs=False)
        assert ref_changed is False
        download_ref = self._build_download_ref_with_ref_change(
            dep, lockfile, update_refs=False, ref_changed=ref_changed
        )
        assert "#abc123" in download_ref


class TestOrphanDeployedFilesDetection:
    """Tests for detecting deployed files of packages removed from manifest.

    When packages are removed from apm.yml and apm install is run (full install),
    the deployed files should be identified for cleanup.
    """

    @staticmethod
    def _detect_orphans(existing_lockfile, intended_dep_keys, only_packages):
        """Reproduce orphan detection logic from install.py."""
        orphaned_deployed_files = set()
        if not only_packages and existing_lockfile:
            for dep_key, dep in existing_lockfile.dependencies.items():
                if dep_key not in intended_dep_keys:
                    orphaned_deployed_files.update(dep.deployed_files)
        return orphaned_deployed_files

    @staticmethod
    def _should_merge_lockfile_entry(dep_key, lockfile_dependencies, only_packages, intended_dep_keys):
        """Reproduce the lockfile merge condition from install.py.

        Returns True if the dep_key should be merged into the new lockfile.
        Logic: only merge if (a) not already in new lockfile AND
               (b) either partial install OR package still in intended set.
        """
        if dep_key in lockfile_dependencies:
            return False  # already in new lockfile
        return bool(only_packages or dep_key in intended_dep_keys)

    def _mock_lockfile_with_deps(self, deps):
        """Build a mock lockfile with {dep_key: [deployed_files]} entries."""
        lockfile = Mock()
        dep_mocks = {}
        for dep_key, deployed_files in deps.items():
            dep = Mock()
            dep.deployed_files = deployed_files
            dep_mocks[dep_key] = dep
        lockfile.dependencies = dep_mocks
        return lockfile

    def test_no_orphans_when_all_packages_still_in_manifest(self):
        """No orphaned files when all lockfile packages are still in manifest."""
        lockfile = self._mock_lockfile_with_deps({
            "owner/pkg-a": [".github/prompts/a.prompt.md"],
            "owner/pkg-b": [".github/prompts/b.prompt.md"],
        })
        intended = {"owner/pkg-a", "owner/pkg-b"}
        orphans = self._detect_orphans(lockfile, intended, only_packages=None)
        assert orphans == set()

    def test_orphaned_files_when_package_removed(self):
        """Deployed files for removed package should be detected as orphans."""
        lockfile = self._mock_lockfile_with_deps({
            "owner/pkg-a": [".github/prompts/a.prompt.md"],
            "owner/pkg-removed": [
                ".github/prompts/removed.prompt.md",
                ".github/instructions/removed.instructions.md",
            ],
        })
        intended = {"owner/pkg-a"}  # pkg-removed not in new manifest
        orphans = self._detect_orphans(lockfile, intended, only_packages=None)
        assert orphans == {
            ".github/prompts/removed.prompt.md",
            ".github/instructions/removed.instructions.md",
        }

    def test_no_orphans_for_partial_install(self):
        """Orphan detection is skipped for partial installs (only_packages)."""
        lockfile = self._mock_lockfile_with_deps({
            "owner/pkg-a": [".github/prompts/a.prompt.md"],
            "owner/pkg-removed": [".github/prompts/removed.prompt.md"],
        })
        intended = {"owner/pkg-a"}
        orphans = self._detect_orphans(lockfile, intended, only_packages=["owner/pkg-a"])
        assert orphans == set()

    def test_no_orphans_when_no_lockfile(self):
        """No orphaned files when there is no existing lockfile."""
        orphans = self._detect_orphans(None, {"owner/pkg-a"}, only_packages=None)
        assert orphans == set()

    def test_lockfile_merge_drops_orphan_in_full_install(self):
        """In a full install, orphaned lockfile entries should NOT be merged."""
        # Simulate: new lockfile has pkg-a, old lockfile has pkg-a + pkg-removed
        new_lockfile_deps = {"owner/pkg-a"}
        intended = {"owner/pkg-a"}  # pkg-removed no longer in manifest

        # pkg-removed should NOT be merged (orphan)
        assert not self._should_merge_lockfile_entry(
            "owner/pkg-removed", new_lockfile_deps, only_packages=None, intended_dep_keys=intended
        )

    def test_lockfile_merge_preserves_failed_download_in_full_install(self):
        """In a full install, failed downloads (still in manifest) should be preserved."""
        new_lockfile_deps = {"owner/pkg-a"}  # pkg-b failed to download
        intended = {"owner/pkg-a", "owner/pkg-b"}  # both in manifest

        # pkg-b should be preserved (still in manifest, just failed)
        assert self._should_merge_lockfile_entry(
            "owner/pkg-b", new_lockfile_deps, only_packages=None, intended_dep_keys=intended
        )

    def test_lockfile_merge_preserves_all_for_partial_install(self):
        """For partial installs, ALL old lockfile entries should be preserved."""
        new_lockfile_deps = {"owner/pkg-a"}
        intended = {"owner/pkg-a"}  # pkg-removed not in new manifest

        # pkg-removed should STILL be preserved in a partial install
        assert self._should_merge_lockfile_entry(
            "owner/pkg-removed", new_lockfile_deps, only_packages=["owner/pkg-a"], intended_dep_keys=intended
        )
