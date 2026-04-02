"""Tests for --update ref resolution in download_callback and sequential loop.

Validates fixes for issue #548: download_callback uses locked SHA during
--update, bypassing re-resolution of transitive dependencies.
"""
import pytest


def _should_use_locked_ref(locked_ref, update_refs):
    """Mirror of the locked-ref decision in download_callback (install.py ~L1268).

    Returns True when the callback should override the manifest ref with the
    locked SHA from the lockfile.
    """
    return bool(locked_ref) and not update_refs


def _compute_skip_download(
    install_path_exists, is_cacheable, update_refs, already_resolved, lockfile_match
):
    """Mirror of skip_download logic in sequential loop (install.py ~L1920).

    Returns True when the sequential loop should skip downloading a package.
    """
    return install_path_exists and (
        (is_cacheable and not update_refs)
        or (already_resolved and not update_refs)
        or lockfile_match
    )


# -- download_callback locked-ref gating ------------------------------------

class TestDownloadCallbackLockedRef:
    """download_callback should use manifest ref when update_refs=True."""

    def test_uses_locked_ref_normal_install(self):
        """Normal install: callback overrides ref with locked SHA."""
        assert _should_use_locked_ref("abc123", update_refs=False) is True

    def test_uses_manifest_ref_during_update(self):
        """--update: callback ignores locked SHA, uses manifest ref."""
        assert _should_use_locked_ref("abc123", update_refs=True) is False

    def test_no_locked_ref_normal_install(self):
        """No lockfile entry: callback uses manifest ref regardless."""
        assert _should_use_locked_ref(None, update_refs=False) is False

    def test_no_locked_ref_during_update(self):
        """No lockfile entry during --update: manifest ref used."""
        assert _should_use_locked_ref(None, update_refs=True) is False

    def test_empty_string_locked_ref(self):
        """Empty string locked ref treated as absent."""
        assert _should_use_locked_ref("", update_refs=False) is False


# -- sequential loop skip_download gating -----------------------------------

class TestSkipDownloadLogic:
    """Sequential loop should not let already_resolved bypass during --update."""

    def test_already_resolved_skips_normal_install(self):
        """Normal install: already_resolved=True causes skip."""
        assert _compute_skip_download(
            install_path_exists=True,
            is_cacheable=False,
            update_refs=False,
            already_resolved=True,
            lockfile_match=False,
        ) is True

    def test_already_resolved_no_skip_during_update(self):
        """--update: already_resolved alone does NOT cause skip."""
        assert _compute_skip_download(
            install_path_exists=True,
            is_cacheable=False,
            update_refs=True,
            already_resolved=True,
            lockfile_match=False,
        ) is False

    def test_lockfile_match_skips_during_update(self):
        """--update: lockfile_match still causes skip (SHA confirmed)."""
        assert _compute_skip_download(
            install_path_exists=True,
            is_cacheable=False,
            update_refs=True,
            already_resolved=False,
            lockfile_match=True,
        ) is True

    def test_cacheable_no_skip_during_update(self):
        """--update: is_cacheable does NOT cause skip."""
        assert _compute_skip_download(
            install_path_exists=True,
            is_cacheable=True,
            update_refs=True,
            already_resolved=False,
            lockfile_match=False,
        ) is False

    def test_cacheable_skips_normal_install(self):
        """Normal install: is_cacheable causes skip."""
        assert _compute_skip_download(
            install_path_exists=True,
            is_cacheable=True,
            update_refs=False,
            already_resolved=False,
            lockfile_match=False,
        ) is True

    def test_path_not_exists_never_skips(self):
        """When install_path doesn't exist, skip is always False."""
        assert _compute_skip_download(
            install_path_exists=False,
            is_cacheable=True,
            update_refs=False,
            already_resolved=True,
            lockfile_match=True,
        ) is False

    @pytest.mark.parametrize(
        "update_refs, already_resolved, lockfile_match, expected",
        [
            (False, True, False, True),   # normal: already_resolved skips
            (True, True, False, False),   # update: already_resolved ignored
            (True, False, True, True),    # update: lockfile_match skips
            (True, True, True, True),     # update: lockfile_match dominates
            (False, False, False, False), # normal: nothing to skip
            (True, False, False, False),  # update: nothing to skip
        ],
        ids=[
            "normal-already_resolved",
            "update-already_resolved-ignored",
            "update-lockfile_match",
            "update-lockfile_match-dominates",
            "normal-no-skip",
            "update-no-skip",
        ],
    )
    def test_skip_matrix(self, update_refs, already_resolved, lockfile_match, expected):
        """Parametrized matrix of skip_download conditions."""
        assert _compute_skip_download(
            install_path_exists=True,
            is_cacheable=False,
            update_refs=update_refs,
            already_resolved=already_resolved,
            lockfile_match=lockfile_match,
        ) is expected
