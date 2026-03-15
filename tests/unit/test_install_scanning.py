"""Tests for install-time content scanning integration.

Verifies that ``_pre_deploy_security_scan()`` blocks deployment on
critical findings and allows deployment on warnings/clean, and that
``BaseIntegrator.scan_deployed_files()`` correctly pushes findings
into a ``DiagnosticCollector``.
"""

from pathlib import Path

import pytest

from apm_cli.commands.install import _pre_deploy_security_scan
from apm_cli.integration.base_integrator import BaseIntegrator
from apm_cli.utils.diagnostics import DiagnosticCollector


@pytest.fixture
def clean_files(tmp_path):
    """Create several clean text files."""
    paths = []
    for name in ("a.md", "b.md", "c.md"):
        p = tmp_path / name
        p.write_text(f"# {name}\nClean content.\n", encoding="utf-8")
        paths.append(p)
    return paths


@pytest.fixture
def mixed_files(tmp_path):
    """Create files with varying severity levels."""
    clean = tmp_path / "clean.md"
    clean.write_text("No issues here.\n", encoding="utf-8")

    warning = tmp_path / "warning.md"
    warning.write_text("Has zero\u200Bwidth.\n", encoding="utf-8")

    critical = tmp_path / "critical.md"
    critical.write_text("Has tag\U000E0041char.\n", encoding="utf-8")

    return [clean, warning, critical]


class TestScanDeployedFiles:
    """Tests for BaseIntegrator.scan_deployed_files()."""

    def test_clean_files_no_diagnostics(self, clean_files):
        diag = DiagnosticCollector()
        BaseIntegrator.scan_deployed_files(clean_files, diagnostics=diag, package="pkg")
        assert not diag.has_diagnostics
        assert diag.security_count == 0

    def test_warning_files_recorded(self, tmp_path):
        p = tmp_path / "warn.md"
        p.write_text("zero\u200Bwidth\n", encoding="utf-8")
        diag = DiagnosticCollector()
        BaseIntegrator.scan_deployed_files([p], diagnostics=diag, package="pkg")
        assert diag.security_count == 1
        assert not diag.has_critical_security

    def test_critical_files_recorded(self, tmp_path):
        p = tmp_path / "evil.md"
        p.write_text("tag\U000E0001char\n", encoding="utf-8")
        diag = DiagnosticCollector()
        BaseIntegrator.scan_deployed_files([p], diagnostics=diag, package="pkg")
        assert diag.security_count == 1
        assert diag.has_critical_security

    def test_mixed_files_all_recorded(self, mixed_files):
        diag = DiagnosticCollector()
        BaseIntegrator.scan_deployed_files(mixed_files, diagnostics=diag, package="pkg")
        assert diag.security_count == 2  # warning + critical
        assert diag.has_critical_security

    def test_skips_missing_files(self, tmp_path):
        missing = tmp_path / "gone.md"
        diag = DiagnosticCollector()
        BaseIntegrator.scan_deployed_files([missing], diagnostics=diag, package="pkg")
        assert not diag.has_diagnostics

    def test_scans_files_inside_directories(self, tmp_path):
        """When a deployed path is a directory, scan its files recursively."""
        d = tmp_path / "skill-dir"
        d.mkdir()
        (d / "SKILL.md").write_text("skill\u200Bcontent\n", encoding="utf-8")
        (d / "clean.md").write_text("clean\n", encoding="utf-8")
        sub = d / "nested"
        sub.mkdir()
        (sub / "deep.md").write_text("deep\U000E0001file\n", encoding="utf-8")

        diag = DiagnosticCollector()
        BaseIntegrator.scan_deployed_files([d], diagnostics=diag, package="pkg")
        # SKILL.md (warning) + deep.md (critical) = 2 findings
        assert diag.security_count == 2
        assert diag.has_critical_security

    def test_none_diagnostics_noop(self, clean_files):
        # Should not raise when diagnostics is None
        BaseIntegrator.scan_deployed_files(clean_files, diagnostics=None, package="pkg")

    def test_package_name_in_diagnostic(self, tmp_path):
        p = tmp_path / "warn.md"
        p.write_text("has\u200Bchar\n", encoding="utf-8")
        diag = DiagnosticCollector()
        BaseIntegrator.scan_deployed_files([p], diagnostics=diag, package="my-pkg")
        groups = diag.by_category()
        security_items = groups.get("security", [])
        assert len(security_items) == 1
        assert security_items[0].package == "my-pkg"


class TestDiagnosticsSecurityRendering:
    """Tests for security category rendering in DiagnosticCollector."""

    def test_render_summary_includes_security(self, mixed_files, capsys):
        diag = DiagnosticCollector()
        BaseIntegrator.scan_deployed_files(mixed_files, diagnostics=diag, package="pkg")
        diag.render_summary()
        captured = capsys.readouterr()
        assert "Diagnostics" in captured.out or "security" in captured.out.lower()

    def test_critical_security_flag(self, tmp_path):
        p = tmp_path / "evil.md"
        p.write_text("x\U000E0001y\n", encoding="utf-8")
        diag = DiagnosticCollector()
        BaseIntegrator.scan_deployed_files([p], diagnostics=diag, package="pkg")
        assert diag.has_critical_security is True

    def test_no_critical_when_only_warnings(self, tmp_path):
        p = tmp_path / "warn.md"
        p.write_text("x\u200By\n", encoding="utf-8")
        diag = DiagnosticCollector()
        BaseIntegrator.scan_deployed_files([p], diagnostics=diag, package="pkg")
        assert diag.has_critical_security is False


# ── Pre-deploy security scan tests ───────────────────────────────


class TestPreDeploySecurityScan:
    """Tests for _pre_deploy_security_scan() — the pre-deployment gate."""

    def test_clean_package_allows_deploy(self, tmp_path):
        (tmp_path / "prompt.md").write_text("Clean content\n", encoding="utf-8")
        diag = DiagnosticCollector()
        assert _pre_deploy_security_scan(tmp_path, diag, package_name="pkg") is True
        assert diag.security_count == 0

    def test_critical_chars_block_deploy(self, tmp_path):
        (tmp_path / "evil.md").write_text(
            "hidden\U000E0001tag\n", encoding="utf-8"
        )
        diag = DiagnosticCollector()
        result = _pre_deploy_security_scan(
            tmp_path, diag, package_name="pkg", force=False,
        )
        assert result is False
        assert diag.has_critical_security

    def test_critical_chars_with_force_allows_deploy(self, tmp_path):
        (tmp_path / "evil.md").write_text(
            "hidden\U000E0001tag\n", encoding="utf-8"
        )
        diag = DiagnosticCollector()
        result = _pre_deploy_security_scan(
            tmp_path, diag, package_name="pkg", force=True,
        )
        assert result is True
        assert diag.has_critical_security  # still records the finding

    def test_warnings_allow_deploy(self, tmp_path):
        (tmp_path / "warn.md").write_text(
            "zero\u200Bwidth\n", encoding="utf-8"
        )
        diag = DiagnosticCollector()
        result = _pre_deploy_security_scan(
            tmp_path, diag, package_name="pkg",
        )
        assert result is True
        assert diag.security_count == 1
        assert not diag.has_critical_security

    def test_scans_nested_files(self, tmp_path):
        """Source files in subdirectories are scanned."""
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "deep.md").write_text("tag\U000E0041char\n", encoding="utf-8")
        diag = DiagnosticCollector()
        result = _pre_deploy_security_scan(
            tmp_path, diag, package_name="pkg", force=False,
        )
        assert result is False

    def test_empty_package_allows_deploy(self, tmp_path):
        diag = DiagnosticCollector()
        assert _pre_deploy_security_scan(tmp_path, diag) is True
        assert diag.security_count == 0

    def test_package_name_in_diagnostic(self, tmp_path):
        (tmp_path / "x.md").write_text("z\u200Bw\n", encoding="utf-8")
        diag = DiagnosticCollector()
        _pre_deploy_security_scan(tmp_path, diag, package_name="my-pkg")
        items = diag.by_category().get("security", [])
        assert len(items) == 1
        assert items[0].package == "my-pkg"
