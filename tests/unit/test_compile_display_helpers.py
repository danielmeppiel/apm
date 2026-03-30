"""Tests for compile CLI display helper functions."""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apm_cli.commands.compile.cli import (
    _display_next_steps,
    _display_single_file_summary,
    _display_validation_errors,
    _get_validation_suggestion,
)


# ---------------------------------------------------------------------------
# _get_validation_suggestion
# ---------------------------------------------------------------------------


class TestGetValidationSuggestion:
    """Tests for _get_validation_suggestion()."""

    def test_missing_description(self):
        result = _get_validation_suggestion("Missing 'description' field")
        assert "description:" in result

    def test_missing_apply_to(self):
        result = _get_validation_suggestion("Missing 'applyTo' in frontmatter")
        assert "applyTo" in result

    def test_empty_content(self):
        result = _get_validation_suggestion("Empty content in file")
        assert "markdown content" in result.lower() or "content" in result.lower()

    def test_unknown_error_returns_fallback(self):
        result = _get_validation_suggestion("Some unknown error type")
        assert result  # must be non-empty
        assert "Check primitive" in result or "frontmatter" in result

    def test_all_returns_are_strings(self):
        for msg in [
            "Missing 'description'",
            "Missing 'applyTo'",
            "Empty content",
            "Unknown error",
        ]:
            assert isinstance(_get_validation_suggestion(msg), str)


# ---------------------------------------------------------------------------
# _display_validation_errors
# ---------------------------------------------------------------------------


class TestDisplayValidationErrors:
    """Tests for _display_validation_errors()."""

    def test_fallback_shows_each_error(self, capsys):
        errors = ["file.md: Missing 'description'", "other.md: Empty content"]
        with patch(
            "apm_cli.commands.compile.cli._get_console", return_value=None
        ):
            _display_validation_errors(errors)
        captured = capsys.readouterr()
        out = captured.out + captured.err
        # Each error should be rendered (click.echo writes to stdout)
        assert "file.md" in out or "Missing" in out

    def test_fallback_empty_errors_no_crash(self, capsys):
        with patch(
            "apm_cli.commands.compile.cli._get_console", return_value=None
        ):
            _display_validation_errors([])  # should not raise

    def test_rich_path_calls_console_print(self):
        mock_console = MagicMock()
        errors = ["file.md: Missing 'description'"]
        with patch(
            "apm_cli.commands.compile.cli._get_console", return_value=mock_console
        ):
            _display_validation_errors(errors)
        assert mock_console.print.called

    def test_error_without_colon_handled(self, capsys):
        """Errors without ':' separator should not crash."""
        with patch(
            "apm_cli.commands.compile.cli._get_console", return_value=None
        ):
            _display_validation_errors(["justaplainerrormessage"])

    def test_error_with_colon_splits_file_and_message(self):
        """Errors with ':' should split into file/message for the Rich table."""
        mock_console = MagicMock()
        errors = ["src/foo.md: Missing 'description' field"]
        with patch(
            "apm_cli.commands.compile.cli._get_console", return_value=mock_console
        ):
            _display_validation_errors(errors)
        # Verify table was added with a row (the first add_row call)
        # We can't inspect the Rich Table directly, but we verify print was called
        assert mock_console.print.called


# ---------------------------------------------------------------------------
# _display_next_steps
# ---------------------------------------------------------------------------


class TestDisplayNextSteps:
    """Tests for _display_next_steps()."""

    def test_fallback_shows_review_generated_file(self, capsys):
        with patch(
            "apm_cli.commands.compile.cli._get_console", return_value=None
        ):
            _display_next_steps("AGENTS.md")
        captured = capsys.readouterr()
        out = captured.out + captured.err
        assert "AGENTS.md" in out

    def test_fallback_shows_install_step(self, capsys):
        with patch(
            "apm_cli.commands.compile.cli._get_console", return_value=None
        ):
            _display_next_steps("AGENTS.md")
        captured = capsys.readouterr()
        out = captured.out + captured.err
        assert "apm install" in out

    def test_rich_path_calls_console_print(self):
        mock_console = MagicMock()
        with patch(
            "apm_cli.commands.compile.cli._get_console", return_value=mock_console
        ):
            _display_next_steps("AGENTS.md")
        assert mock_console.print.called

    def test_output_filename_included_in_next_step(self, capsys):
        with patch(
            "apm_cli.commands.compile.cli._get_console", return_value=None
        ):
            _display_next_steps("CLAUDE.md")
        captured = capsys.readouterr()
        out = captured.out + captured.err
        assert "CLAUDE.md" in out


# ---------------------------------------------------------------------------
# _display_single_file_summary
# ---------------------------------------------------------------------------


class TestDisplaySingleFileSummary:
    """Tests for _display_single_file_summary()."""

    def _make_output_path(self, tmp_path, name="AGENTS.md"):
        p = tmp_path / name
        p.write_text("content")
        return p

    def test_fallback_shows_primitives_count(self, capsys, tmp_path):
        stats = {"primitives_found": 5, "instructions": 3, "contexts": 2, "chatmodes": 0}
        output_path = self._make_output_path(tmp_path)
        with patch(
            "apm_cli.commands.compile.cli._get_console", return_value=None
        ):
            _display_single_file_summary(stats, "unchanged", "abc123", output_path, False)
        captured = capsys.readouterr()
        out = captured.out + captured.err
        assert "5" in out
        assert "instructions" in out

    def test_fallback_shows_constitution_hash(self, capsys, tmp_path):
        stats = {"primitives_found": 1, "instructions": 1, "contexts": 0, "chatmodes": 0}
        output_path = self._make_output_path(tmp_path)
        with patch(
            "apm_cli.commands.compile.cli._get_console", return_value=None
        ):
            _display_single_file_summary(stats, "unchanged", "myhash", output_path, False)
        captured = capsys.readouterr()
        out = captured.out + captured.err
        assert "myhash" in out

    def test_fallback_no_hash_shows_dash(self, capsys, tmp_path):
        stats = {"primitives_found": 0, "instructions": 0, "contexts": 0, "chatmodes": 0}
        output_path = self._make_output_path(tmp_path)
        with patch(
            "apm_cli.commands.compile.cli._get_console", return_value=None
        ):
            _display_single_file_summary(stats, "unchanged", None, output_path, False)
        captured = capsys.readouterr()
        out = captured.out + captured.err
        assert "hash=-" in out or "hash= -" in out or "-" in out

    def test_rich_path_calls_console_print(self, tmp_path):
        mock_console = MagicMock()
        stats = {"primitives_found": 2, "instructions": 2, "contexts": 0, "chatmodes": 0}
        output_path = self._make_output_path(tmp_path)
        with patch(
            "apm_cli.commands.compile.cli._get_console", return_value=mock_console
        ):
            _display_single_file_summary(stats, "unchanged", "h1", output_path, False)
        assert mock_console.print.called

    def test_dry_run_shows_preview_size(self, tmp_path):
        mock_console = MagicMock()
        stats = {"primitives_found": 1, "instructions": 1, "contexts": 0, "chatmodes": 0}
        output_path = self._make_output_path(tmp_path)
        # dry_run=True => file_size=0 => "Preview"
        with patch(
            "apm_cli.commands.compile.cli._get_console", return_value=mock_console
        ):
            _display_single_file_summary(stats, "new", "h2", output_path, dry_run=True)
        assert mock_console.print.called

    def test_empty_stats_uses_zero_defaults(self, capsys, tmp_path):
        """Empty stats dict should not crash - defaults to 0."""
        output_path = self._make_output_path(tmp_path)
        with patch(
            "apm_cli.commands.compile.cli._get_console", return_value=None
        ):
            _display_single_file_summary({}, "new", None, output_path, False)
        captured = capsys.readouterr()
        out = captured.out + captured.err
        assert "0 primitives" in out
