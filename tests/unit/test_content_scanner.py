"""Tests for the content scanner module."""

import tempfile
from pathlib import Path

import pytest

from apm_cli.security.content_scanner import ContentScanner, ScanFinding


class TestScanText:
    """Tests for ContentScanner.scan_text()."""

    def test_clean_text_returns_empty(self):
        """Ordinary ASCII+emoji text produces no findings."""
        content = "# My Prompt\n\nDo the thing. 🚀\n"
        findings = ContentScanner.scan_text(content)
        assert findings == []

    def test_empty_string_returns_empty(self):
        findings = ContentScanner.scan_text("")
        assert findings == []

    def test_whitespace_only_returns_empty(self):
        findings = ContentScanner.scan_text("   \n\n\t\t\n")
        assert findings == []

    # ── Critical: tag characters ──

    def test_tag_character_detected_as_critical(self):
        """U+E0001 (language tag) must be flagged as critical."""
        content = f"Hello \U000e0001 world"
        findings = ContentScanner.scan_text(content, filename="test.md")
        assert len(findings) == 1
        assert findings[0].severity == "critical"
        assert findings[0].category == "tag-character"
        assert findings[0].codepoint == "U+E0001"
        assert findings[0].file == "test.md"

    def test_multiple_tag_characters(self):
        """Full range of tag chars embedded in text."""
        # Embed a few tag characters that map to invisible ASCII
        tag_a = chr(0xE0041)  # TAG LATIN CAPITAL LETTER A
        tag_b = chr(0xE0042)  # TAG LATIN CAPITAL LETTER B
        content = f"some{tag_a}text{tag_b}here"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 2
        assert all(f.severity == "critical" for f in findings)
        assert findings[0].codepoint == "U+E0041"
        assert findings[1].codepoint == "U+E0042"

    def test_tag_cancel_detected(self):
        """U+E007F (CANCEL TAG) is also critical."""
        content = f"text{chr(0xE007F)}end"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 1
        assert findings[0].severity == "critical"
        assert findings[0].codepoint == "U+E007F"

    # ── Critical: bidi overrides ──

    def test_bidi_lro_detected(self):
        """U+202D (LRO) left-to-right override."""
        content = f"normal \u202d overridden"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 1
        assert findings[0].severity == "critical"
        assert findings[0].category == "bidi-override"

    def test_bidi_rlo_detected(self):
        """U+202E (RLO) right-to-left override."""
        content = f"normal \u202e reversed"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 1
        assert findings[0].severity == "critical"
        assert findings[0].codepoint == "U+202E"

    def test_bidi_isolates_detected(self):
        """U+2066-U+2069 isolates are critical."""
        content = f"a\u2066b\u2067c\u2068d\u2069e"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 4
        assert all(f.severity == "critical" for f in findings)

    # ── Warning: zero-width characters ──

    def test_zero_width_space_detected(self):
        """U+200B zero-width space."""
        content = f"hello\u200bworld"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 1
        assert findings[0].severity == "warning"
        assert findings[0].category == "zero-width"

    def test_zwj_detected(self):
        """U+200D zero-width joiner."""
        content = f"hello\u200dworld"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 1
        assert findings[0].severity == "warning"
        assert findings[0].codepoint == "U+200D"

    def test_zwnj_detected(self):
        """U+200C zero-width non-joiner."""
        content = f"hello\u200cworld"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 1
        assert findings[0].severity == "warning"

    def test_word_joiner_detected(self):
        """U+2060 word joiner."""
        content = f"hello\u2060world"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 1
        assert findings[0].severity == "warning"

    def test_soft_hyphen_detected(self):
        """U+00AD soft hyphen."""
        content = f"hel\u00adlo"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 1
        assert findings[0].severity == "warning"
        assert findings[0].category == "invisible-formatting"

    # ── Info: unusual whitespace ──

    def test_nbsp_detected_as_info(self):
        """U+00A0 non-breaking space."""
        content = f"hello\u00a0world"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 1
        assert findings[0].severity == "info"
        assert findings[0].category == "unusual-whitespace"

    def test_em_space_detected(self):
        """U+2003 em space (in the U+2000-U+200A range)."""
        content = f"hello\u2003world"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 1
        assert findings[0].severity == "info"

    def test_ideographic_space(self):
        """U+3000 ideographic space."""
        content = f"hello\u3000world"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 1
        assert findings[0].severity == "info"

    # ── BOM handling ──

    def test_bom_at_start_is_info(self):
        """BOM (U+FEFF) at file start is standard — info severity."""
        content = "\ufeff# My Document"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 1
        assert findings[0].severity == "info"
        assert findings[0].category == "bom"
        assert findings[0].line == 1
        assert findings[0].column == 1

    def test_bom_mid_file_is_warning(self):
        """BOM in the middle of a file is suspicious."""
        content = "line one\n\ufeffline two"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 1
        assert findings[0].severity == "warning"
        assert findings[0].category == "zero-width"
        assert findings[0].line == 2

    # ── Position accuracy ──

    def test_line_column_accuracy(self):
        """Findings report correct 1-based line and column numbers."""
        # Place a zero-width space at line 3, col 6
        content = "line1\nline2\nline3\u200brest"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 1
        assert findings[0].line == 3
        assert findings[0].column == 6

    def test_multiple_findings_on_same_line(self):
        content = f"a\u200bb\u200cc"
        findings = ContentScanner.scan_text(content)
        assert len(findings) == 2
        assert findings[0].column == 2
        assert findings[1].column == 4

    # ── Mixed content ──

    def test_mixed_severities(self):
        """Content with chars from all severity levels."""
        content = f"\u00a0visible\u200btext\u202ehidden"
        findings = ContentScanner.scan_text(content)
        severities = {f.severity for f in findings}
        assert severities == {"info", "warning", "critical"}

    def test_normal_unicode_not_flagged(self):
        """Legitimate Unicode (CJK, accented chars, emoji) is fine."""
        content = "日本語テスト café résumé 🎉 ñ ü ö"
        findings = ContentScanner.scan_text(content)
        assert findings == []


class TestScanFile:
    """Tests for ContentScanner.scan_file()."""

    def test_scan_clean_file(self, tmp_path):
        f = tmp_path / "clean.md"
        f.write_text("# Clean file\nNo issues here.", encoding="utf-8")
        findings = ContentScanner.scan_file(f)
        assert findings == []

    def test_scan_file_with_findings(self, tmp_path):
        f = tmp_path / "suspicious.md"
        f.write_text(f"hello\u200bworld", encoding="utf-8")
        findings = ContentScanner.scan_file(f)
        assert len(findings) == 1
        assert findings[0].file == str(f)

    def test_binary_file_returns_empty(self, tmp_path):
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x80\x81\x82\xff\xfe")
        findings = ContentScanner.scan_file(f)
        assert findings == []

    def test_nonexistent_file_returns_empty(self, tmp_path):
        f = tmp_path / "does_not_exist.md"
        findings = ContentScanner.scan_file(f)
        assert findings == []

    def test_latin1_file_returns_empty(self, tmp_path):
        """Non-UTF-8 encoded files should be skipped gracefully."""
        f = tmp_path / "latin1.txt"
        f.write_bytes("Stra\xdfe".encode("latin-1"))
        findings = ContentScanner.scan_file(f)
        assert findings == []

    def test_bom_plus_critical_detected(self, tmp_path):
        """Files with BOM and critical chars should report both."""
        f = tmp_path / "bom_critical.md"
        f.write_text("\ufeff" + "tag\U000e0041char\n", encoding="utf-8")
        findings = ContentScanner.scan_file(f)
        severities = {fnd.severity for fnd in findings}
        assert "critical" in severities
        assert "info" in severities  # Leading BOM is info-level


class TestHasCritical:
    def test_no_findings(self):
        assert ContentScanner.has_critical([]) is False

    def test_only_warnings(self):
        findings = [ScanFinding("f", 1, 1, "", "U+200B", "warning", "zw", "")]
        assert ContentScanner.has_critical(findings) is False

    def test_with_critical(self):
        findings = [ScanFinding("f", 1, 1, "", "U+E0001", "critical", "tag", "")]
        assert ContentScanner.has_critical(findings) is True


class TestSummarize:
    def test_empty(self):
        result = ContentScanner.summarize([])
        assert result == {"critical": 0, "warning": 0, "info": 0}

    def test_mixed(self):
        findings = [
            ScanFinding("f", 1, 1, "", "", "critical", "", ""),
            ScanFinding("f", 1, 2, "", "", "critical", "", ""),
            ScanFinding("f", 1, 3, "", "", "warning", "", ""),
            ScanFinding("f", 1, 4, "", "", "info", "", ""),
        ]
        result = ContentScanner.summarize(findings)
        assert result == {"critical": 2, "warning": 1, "info": 1}


class TestClassify:
    """Tests for ContentScanner.classify() — combined has_critical + summarize."""

    def test_empty_returns_false_and_zero_counts(self):
        has_crit, counts = ContentScanner.classify([])
        assert has_crit is False
        assert counts == {"critical": 0, "warning": 0, "info": 0}

    def test_critical_finding_sets_flag(self):
        findings = [
            ScanFinding("f", 1, 1, "", "U+E0001", "critical", "tag-character", "")
        ]
        has_crit, counts = ContentScanner.classify(findings)
        assert has_crit is True
        assert counts["critical"] == 1

    def test_warning_only_does_not_set_flag(self):
        findings = [ScanFinding("f", 1, 1, "", "U+200B", "warning", "zero-width", "")]
        has_crit, counts = ContentScanner.classify(findings)
        assert has_crit is False
        assert counts["warning"] == 1
        assert counts["critical"] == 0

    def test_mixed_findings_comprehensive(self):
        findings = [
            ScanFinding("f", 1, 1, "", "U+E0041", "critical", "tag-character", ""),
            ScanFinding("f", 1, 2, "", "U+200B", "warning", "zero-width", ""),
            ScanFinding("f", 1, 3, "", "U+00A0", "info", "unusual-whitespace", ""),
        ]
        has_crit, counts = ContentScanner.classify(findings)
        assert has_crit is True
        assert counts == {"critical": 1, "warning": 1, "info": 1}

    def test_multiple_critical_all_counted(self):
        findings = [
            ScanFinding(
                "f", 1, i, "", f"U+E{0x0041 + i:04X}", "critical", "tag-character", ""
            )
            for i in range(3)
        ]
        has_crit, counts = ContentScanner.classify(findings)
        assert has_crit is True
        assert counts["critical"] == 3


class TestStripNonCritical:
    def test_strips_zero_width_chars(self):
        content = f"hello\u200bworld"
        result = ContentScanner.strip_non_critical(content)
        assert result == "helloworld"

    def test_strips_nbsp(self):
        content = f"hello\u00a0world"
        result = ContentScanner.strip_non_critical(content)
        assert result == "helloworld"

    def test_preserves_critical_chars(self):
        """Tag characters and bidi overrides are NOT stripped."""
        tag = chr(0xE0041)
        content = f"hello{tag}world"
        result = ContentScanner.strip_non_critical(content)
        assert tag in result

    def test_strips_leading_bom(self):
        content = f"\ufeff# Title"
        result = ContentScanner.strip_non_critical(content)
        assert result == "# Title"

    def test_strips_mid_file_bom(self):
        content = f"line1\n\ufeffline2"
        result = ContentScanner.strip_non_critical(content)
        assert result == "line1\nline2"

    def test_clean_content_unchanged(self):
        content = "# Normal content\nWith normal text."
        result = ContentScanner.strip_non_critical(content)
        assert result == content

    def test_strips_soft_hyphen(self):
        content = f"hel\u00adlo"
        result = ContentScanner.strip_non_critical(content)
        assert result == "hello"
