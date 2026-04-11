"""Tests for marketplace version resolver -- semver range resolution."""

import pytest

from apm_cli.marketplace.models import VersionEntry
from apm_cli.marketplace.version_resolver import (
    is_version_specifier,
    resolve_version,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _v(version: str, ref: str = "") -> VersionEntry:
    """Shorthand to build a VersionEntry with a default ref."""
    return VersionEntry(version=version, ref=ref or f"sha-{version}")


# A realistic set of versions in *shuffled* order so tests verify that the
# resolver sorts internally rather than relying on input order.
SAMPLE_VERSIONS = [
    _v("2.1.0", "abc111"),
    _v("1.0.0", "abc000"),
    _v("3.0.0", "abc300"),
    _v("0.5.0", "abc050"),
    _v("2.0.0", "abc200"),
    _v("1.5.0", "abc150"),
    _v("0.5.3", "abc053"),
    _v("2.1.1", "abc211"),
    _v("0.0.3", "abc003"),
]


# ---------------------------------------------------------------------------
# resolve_version -- latest (None / empty)
# ---------------------------------------------------------------------------


class TestResolveLatest:
    """When specifier is None or empty, return the highest semver."""

    def test_none_returns_highest(self):
        result = resolve_version(None, SAMPLE_VERSIONS)
        assert result.version == "3.0.0"

    def test_empty_string_returns_highest(self):
        result = resolve_version("", SAMPLE_VERSIONS)
        assert result.version == "3.0.0"

    def test_whitespace_only_returns_highest(self):
        result = resolve_version("   ", SAMPLE_VERSIONS)
        assert result.version == "3.0.0"


# ---------------------------------------------------------------------------
# resolve_version -- exact match
# ---------------------------------------------------------------------------


class TestResolveExact:
    """Exact version specifiers like ``"2.1.0"``."""

    def test_exact_match(self):
        result = resolve_version("2.1.0", SAMPLE_VERSIONS)
        assert result.version == "2.1.0"
        assert result.ref == "abc111"

    def test_exact_match_lowest(self):
        result = resolve_version("1.0.0", SAMPLE_VERSIONS)
        assert result.version == "1.0.0"

    def test_exact_no_match_raises(self):
        with pytest.raises(ValueError, match="No version matches"):
            resolve_version("99.0.0", SAMPLE_VERSIONS)


# ---------------------------------------------------------------------------
# resolve_version -- caret (^)
# ---------------------------------------------------------------------------


class TestResolveCaret:
    """Caret specifier ``^X.Y.Z`` -- compatible-with semantics."""

    def test_caret_major_nonzero(self):
        # ^2.0.0 -> >=2.0.0, <3.0.0 => should pick 2.1.1
        result = resolve_version("^2.0.0", SAMPLE_VERSIONS)
        assert result.version == "2.1.1"

    def test_caret_includes_exact(self):
        # ^2.1.1 -> >=2.1.1, <3.0.0 => only 2.1.1 qualifies
        result = resolve_version("^2.1.1", SAMPLE_VERSIONS)
        assert result.version == "2.1.1"

    def test_caret_zero_major(self):
        # ^0.5.0 -> >=0.5.0, <0.6.0 => picks 0.5.3
        result = resolve_version("^0.5.0", SAMPLE_VERSIONS)
        assert result.version == "0.5.3"

    def test_caret_zero_major_zero_minor(self):
        # ^0.0.3 -> >=0.0.3, <0.0.4 => picks 0.0.3
        result = resolve_version("^0.0.3", SAMPLE_VERSIONS)
        assert result.version == "0.0.3"

    def test_caret_no_match(self):
        # ^5.0.0 -> >=5.0.0, <6.0.0 => nothing
        with pytest.raises(ValueError, match="No version matches"):
            resolve_version("^5.0.0", SAMPLE_VERSIONS)


# ---------------------------------------------------------------------------
# resolve_version -- tilde (~)
# ---------------------------------------------------------------------------


class TestResolveTilde:
    """Tilde specifier ``~X.Y.Z`` -- patch-level changes only."""

    def test_tilde_basic(self):
        # ~2.1.0 -> >=2.1.0, <2.2.0 => picks 2.1.1
        result = resolve_version("~2.1.0", SAMPLE_VERSIONS)
        assert result.version == "2.1.1"

    def test_tilde_exact_patch(self):
        # ~2.1.1 -> >=2.1.1, <2.2.0 => picks 2.1.1
        result = resolve_version("~2.1.1", SAMPLE_VERSIONS)
        assert result.version == "2.1.1"

    def test_tilde_no_match(self):
        # ~2.2.0 -> >=2.2.0, <2.3.0 => nothing in sample
        with pytest.raises(ValueError, match="No version matches"):
            resolve_version("~2.2.0", SAMPLE_VERSIONS)


# ---------------------------------------------------------------------------
# resolve_version -- comparison operators
# ---------------------------------------------------------------------------


class TestResolveComparison:
    """Comparison specifiers like ``>=``, ``>``, ``<``, ``<=``."""

    def test_gte(self):
        # >=1.5.0 -> picks 3.0.0 (highest above 1.5.0)
        result = resolve_version(">=1.5.0", SAMPLE_VERSIONS)
        assert result.version == "3.0.0"

    def test_gt(self):
        # >2.1.0 -> picks 3.0.0 (strictly greater)
        result = resolve_version(">2.1.0", SAMPLE_VERSIONS)
        assert result.version == "3.0.0"

    def test_lte(self):
        # <=1.0.0 -> picks 1.0.0
        result = resolve_version("<=1.0.0", SAMPLE_VERSIONS)
        assert result.version == "1.0.0"

    def test_lt(self):
        # <1.0.0 -> picks 0.5.3
        result = resolve_version("<1.0.0", SAMPLE_VERSIONS)
        assert result.version == "0.5.3"


# ---------------------------------------------------------------------------
# resolve_version -- compound ranges
# ---------------------------------------------------------------------------


class TestResolveCompound:
    """Compound specifiers with comma-separated clauses."""

    def test_range_inclusive(self):
        # >=1.0.0,<3.0.0 -> highest in [1.0.0, 3.0.0) => 2.1.1
        result = resolve_version(">=1.0.0,<3.0.0", SAMPLE_VERSIONS)
        assert result.version == "2.1.1"

    def test_range_with_spaces(self):
        # Whitespace around commas and operators
        result = resolve_version(" >=1.0.0 , <3.0.0 ", SAMPLE_VERSIONS)
        assert result.version == "2.1.1"

    def test_range_tight(self):
        # >=2.0.0,<=2.1.0 -> picks 2.1.0
        result = resolve_version(">=2.0.0,<=2.1.0", SAMPLE_VERSIONS)
        assert result.version == "2.1.0"


# ---------------------------------------------------------------------------
# resolve_version -- edge cases
# ---------------------------------------------------------------------------


class TestResolveEdgeCases:
    """Edge cases and error handling."""

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="No versions available"):
            resolve_version(None, [])

    def test_single_version_none_specifier(self):
        result = resolve_version(None, [_v("1.0.0")])
        assert result.version == "1.0.0"

    def test_single_version_exact_match(self):
        result = resolve_version("1.0.0", [_v("1.0.0")])
        assert result.version == "1.0.0"

    def test_single_version_no_match(self):
        with pytest.raises(ValueError, match="No version matches"):
            resolve_version("2.0.0", [_v("1.0.0")])

    def test_invalid_semver_entries_skipped(self):
        """Entries with non-semver version strings are silently skipped."""
        versions = [
            _v("1.0.0"),
            VersionEntry(version="not-a-version", ref="bad"),
            VersionEntry(version="main", ref="bad2"),
            _v("2.0.0"),
        ]
        result = resolve_version(None, versions)
        assert result.version == "2.0.0"

    def test_all_invalid_semver_raises(self):
        """If every entry has an invalid version string, raise ValueError."""
        versions = [
            VersionEntry(version="main", ref="aaa"),
            VersionEntry(version="bad", ref="bbb"),
        ]
        with pytest.raises(ValueError, match="No version matches"):
            resolve_version(None, versions)

    def test_unordered_input(self):
        """Versions not in order should still resolve correctly."""
        versions = [_v("3.0.0"), _v("1.0.0"), _v("2.0.0")]
        result = resolve_version("^2.0.0", versions)
        assert result.version == "2.0.0"

    def test_preserves_entry_identity(self):
        """The returned VersionEntry is the exact object from the input."""
        entry = _v("2.1.0", "specific-ref")
        versions = [_v("1.0.0"), entry, _v("3.0.0")]
        result = resolve_version("2.1.0", versions)
        assert result is entry

    def test_error_message_includes_available(self):
        """ValueError message should list available versions."""
        versions = [_v("1.0.0"), _v("2.0.0")]
        with pytest.raises(ValueError, match="1.0.0"):
            resolve_version("99.0.0", versions)


# ---------------------------------------------------------------------------
# is_version_specifier
# ---------------------------------------------------------------------------


class TestIsVersionSpecifier:
    """Heuristic to distinguish version specifiers from git refs."""

    # Positive cases -- should be recognized as version specifiers
    def test_exact_version(self):
        assert is_version_specifier("2.1.0") is True

    def test_caret(self):
        assert is_version_specifier("^2.0.0") is True

    def test_tilde(self):
        assert is_version_specifier("~2.1.0") is True

    def test_gte(self):
        assert is_version_specifier(">=1.5.0") is True

    def test_gt(self):
        assert is_version_specifier(">1.0.0") is True

    def test_lte(self):
        assert is_version_specifier("<=3.0.0") is True

    def test_lt(self):
        assert is_version_specifier("<3.0.0") is True

    def test_eq(self):
        assert is_version_specifier("==2.0.0") is True

    def test_compound(self):
        assert is_version_specifier(">=1.0.0,<3.0.0") is True

    def test_compound_with_spaces(self):
        assert is_version_specifier(" >=1.0.0 , <3.0.0 ") is True

    # Negative cases -- should NOT be recognized as version specifiers
    def test_branch_name(self):
        assert is_version_specifier("main") is False

    def test_sha_like(self):
        assert is_version_specifier("abc123def") is False

    def test_feature_branch(self):
        assert is_version_specifier("feature/my-branch") is False

    def test_tag_with_v_prefix(self):
        # "v2.1.0" is a git tag, not a bare specifier
        assert is_version_specifier("v2.1.0") is False

    def test_empty_string(self):
        assert is_version_specifier("") is False

    def test_whitespace_only(self):
        assert is_version_specifier("   ") is False

    def test_partial_version(self):
        # "2.1" is not X.Y.Z
        assert is_version_specifier("2.1") is False

    def test_hex_string(self):
        # 40-char hex could be a SHA
        assert is_version_specifier("a" * 40) is False

    def test_alpha_prefix_with_digits(self):
        assert is_version_specifier("release-2.0") is False
