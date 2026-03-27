"""Tests for exclude pattern filtering during primitive discovery.

Mirrors TestDirectoryExclusion in test_context_optimizer.py to ensure
discovery and optimization exclude behavior stays consistent.
"""

import tempfile
from pathlib import Path

import pytest

from apm_cli.primitives.discovery import (
    _match_glob_recursive,
    _matches_exclude_patterns,
    _matches_pattern,
)


class TestMatchesPattern:
    """Test _matches_pattern against all pattern styles from ContextOptimizer."""

    def test_simple_directory_name(self):
        assert _matches_pattern("tmp/foo/bar.md", "tmp")
        assert _matches_pattern("tmp", "tmp")
        assert not _matches_pattern("src/foo.md", "tmp")

    def test_trailing_slash(self):
        assert _matches_pattern("tmp/foo/bar.md", "tmp/")
        assert _matches_pattern("tmp", "tmp/")
        assert not _matches_pattern("src/foo.md", "tmp/")

    def test_glob_star_star_suffix(self):
        assert _matches_pattern("docs/labs/foo.md", "docs/**")
        assert _matches_pattern("docs/a/b/c.md", "docs/**")
        assert not _matches_pattern("src/docs/foo.md", "docs/**")

    def test_glob_star_star_prefix(self):
        assert _matches_pattern("test-fixtures/foo.md", "**/test-fixtures")
        assert _matches_pattern("src/test-fixtures/foo.md", "**/test-fixtures")
        assert not _matches_pattern("src/foo.md", "**/test-fixtures")

    def test_glob_star_star_both(self):
        assert _matches_pattern("node_modules/pkg/index.js", "**/node_modules/**")
        assert _matches_pattern("src/node_modules/pkg.js", "**/node_modules/**")
        assert not _matches_pattern("src/foo.js", "**/node_modules/**")

    def test_nested_directory(self):
        assert _matches_pattern("projects/packages/apm/src/foo.py", "projects/packages/apm")
        assert _matches_pattern("projects/packages/apm", "projects/packages/apm")
        assert not _matches_pattern("projects/packages/other/foo.py", "projects/packages/apm")

    def test_fnmatch_wildcards(self):
        assert _matches_pattern("tmp123/foo.md", "tmp*")
        assert _matches_pattern("mycache/foo.md", "*cache*")
        assert not _matches_pattern("src/foo.md", "tmp*")

    def test_coverage_star_star_suffix(self):
        assert _matches_pattern("coverage/report/index.html", "coverage/**")
        assert _matches_pattern("coverage", "coverage/**")
        assert not _matches_pattern("src/coverage.py", "coverage/**")


class TestMatchGlobRecursive:
    """Test _match_glob_recursive edge cases."""

    def test_empty_pattern_empty_path(self):
        assert _match_glob_recursive([], [])

    def test_star_star_matches_zero_dirs(self):
        assert _match_glob_recursive(["foo.md"], ["**", "foo.md"])

    def test_star_star_matches_multiple_dirs(self):
        assert _match_glob_recursive(
            ["a", "b", "c", "foo.md"], ["**", "foo.md"]
        )

    def test_trailing_star_star(self):
        assert _match_glob_recursive(["docs", "a", "b"], ["docs", "**"])

    def test_no_match(self):
        assert not _match_glob_recursive(["src", "foo.py"], ["docs", "**"])


class TestMatchesExcludePatterns:
    """Test _matches_exclude_patterns integration with file paths."""

    def test_no_patterns(self):
        assert not _matches_exclude_patterns(Path("/p/foo.md"), Path("/p"), None)
        assert not _matches_exclude_patterns(Path("/p/foo.md"), Path("/p"), [])

    def test_path_outside_base_dir(self):
        assert not _matches_exclude_patterns(
            Path("/other/docs/foo.md"), Path("/project"), ["docs/**"]
        )

    def test_filters_with_real_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "docs" / "labs").mkdir(parents=True)
            (base / "src").mkdir()
            doc_file = base / "docs" / "labs" / "example.instructions.md"
            src_file = base / "src" / "real.instructions.md"
            doc_file.touch()
            src_file.touch()

            patterns = ["docs/**"]
            assert _matches_exclude_patterns(doc_file, base, patterns)
            assert not _matches_exclude_patterns(src_file, base, patterns)

    def test_multiple_patterns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "docs").mkdir()
            (base / "tmp").mkdir()
            (base / "src").mkdir()
            doc = base / "docs" / "foo.md"
            tmp = base / "tmp" / "bar.md"
            src = base / "src" / "real.md"
            doc.touch()
            tmp.touch()
            src.touch()

            patterns = ["docs/**", "tmp"]
            assert _matches_exclude_patterns(doc, base, patterns)
            assert _matches_exclude_patterns(tmp, base, patterns)
            assert not _matches_exclude_patterns(src, base, patterns)
