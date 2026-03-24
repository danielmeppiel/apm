"""Tests for the baseline CI checks engine (``apm_cli.policy.ci_checks``)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from apm_cli.policy.ci_checks import (
    _check_config_consistency,
    _check_content_integrity,
    _check_deployed_files_present,
    _check_lockfile_exists,
    _check_no_orphans,
    _check_ref_consistency,
    run_baseline_checks,
)
from apm_cli.policy.models import CIAuditResult, CheckResult
from apm_cli.models.apm_package import clear_apm_yml_cache


# -- Helpers --------------------------------------------------------


def _write_apm_yml(project: Path, *, deps: list[str] | None = None, mcp: list | None = None) -> None:
    """Write a minimal apm.yml with optional dependencies."""
    lines = ["name: test-project", "version: '1.0.0'"]
    if deps or mcp:
        lines.append("dependencies:")
    if deps:
        lines.append("  apm:")
        for d in deps:
            lines.append(f"    - {d}")
    if mcp:
        lines.append("  mcp:")
        for m in mcp:
            if isinstance(m, str):
                lines.append(f"    - {m}")
            elif isinstance(m, dict):
                # Write dict form
                first_key = True
                for k, v in m.items():
                    prefix = "    - " if first_key else "      "
                    lines.append(f"{prefix}{k}: {v}")
                    first_key = False
    (project / "apm.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_lockfile(project: Path, content: str) -> None:
    """Write apm.lock.yaml."""
    (project / "apm.lock.yaml").write_text(content, encoding="utf-8")


def _make_deployed_file(project: Path, rel_path: str, content: str = "clean\n") -> None:
    """Create a file at the given relative path under project."""
    p = project / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# -- Fixtures -------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the APMPackage parse cache between tests."""
    clear_apm_yml_cache()
    yield
    clear_apm_yml_cache()


# -- Lockfile exists ------------------------------------------------


class TestLockfileExists:
    def test_pass_lockfile_present(self, tmp_path):
        _write_apm_yml(tmp_path, deps=["owner/repo"])
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies:
                  - repo_url: owner/repo
                    resolved_ref: main
            """),
        )
        result = _check_lockfile_exists(tmp_path)
        assert result.passed
        assert result.name == "lockfile-exists"

    def test_fail_lockfile_missing(self, tmp_path):
        _write_apm_yml(tmp_path, deps=["owner/repo"])
        result = _check_lockfile_exists(tmp_path)
        assert not result.passed
        assert "missing" in result.message.lower()
        assert len(result.details) > 0

    def test_pass_no_deps_no_lockfile(self, tmp_path):
        _write_apm_yml(tmp_path)  # no deps
        result = _check_lockfile_exists(tmp_path)
        assert result.passed
        assert "not required" in result.message.lower()

    def test_pass_no_apm_yml(self, tmp_path):
        result = _check_lockfile_exists(tmp_path)
        assert result.passed


# -- Ref consistency ------------------------------------------------


class TestRefConsistency:
    def test_pass_refs_match(self, tmp_path):
        _write_apm_yml(tmp_path, deps=["owner/repo#v1.0.0"])
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies:
                  - repo_url: owner/repo
                    resolved_ref: v1.0.0
                    deployed_files: []
            """),
        )
        from apm_cli.models.apm_package import APMPackage
        from apm_cli.deps.lockfile import LockFile, get_lockfile_path

        manifest = APMPackage.from_apm_yml(tmp_path / "apm.yml")
        lock = LockFile.read(get_lockfile_path(tmp_path))
        result = _check_ref_consistency(manifest, lock)
        assert result.passed

    def test_fail_ref_mismatch(self, tmp_path):
        _write_apm_yml(tmp_path, deps=["owner/repo#v2.0.0"])
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies:
                  - repo_url: owner/repo
                    resolved_ref: v1.0.0
                    deployed_files: []
            """),
        )
        from apm_cli.models.apm_package import APMPackage
        from apm_cli.deps.lockfile import LockFile, get_lockfile_path

        manifest = APMPackage.from_apm_yml(tmp_path / "apm.yml")
        lock = LockFile.read(get_lockfile_path(tmp_path))
        result = _check_ref_consistency(manifest, lock)
        assert not result.passed
        assert any("v2.0.0" in d and "v1.0.0" in d for d in result.details)

    def test_fail_dep_not_in_lockfile(self, tmp_path):
        _write_apm_yml(tmp_path, deps=["owner/repo"])
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies: []
            """),
        )
        from apm_cli.models.apm_package import APMPackage
        from apm_cli.deps.lockfile import LockFile, get_lockfile_path

        manifest = APMPackage.from_apm_yml(tmp_path / "apm.yml")
        lock = LockFile.read(get_lockfile_path(tmp_path))
        result = _check_ref_consistency(manifest, lock)
        assert not result.passed
        assert any("not found" in d for d in result.details)


# -- Deployed files present -----------------------------------------


class TestDeployedFilesPresent:
    def test_pass_all_present(self, tmp_path):
        _make_deployed_file(tmp_path, ".github/prompts/test.md")
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies:
                  - repo_url: owner/repo
                    deployed_files:
                      - .github/prompts/test.md
            """),
        )
        from apm_cli.deps.lockfile import LockFile, get_lockfile_path

        lock = LockFile.read(get_lockfile_path(tmp_path))
        result = _check_deployed_files_present(tmp_path, lock)
        assert result.passed

    def test_fail_file_missing(self, tmp_path):
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies:
                  - repo_url: owner/repo
                    deployed_files:
                      - .github/prompts/missing.md
            """),
        )
        from apm_cli.deps.lockfile import LockFile, get_lockfile_path

        lock = LockFile.read(get_lockfile_path(tmp_path))
        result = _check_deployed_files_present(tmp_path, lock)
        assert not result.passed
        assert ".github/prompts/missing.md" in result.details


# -- No orphaned packages ------------------------------------------


class TestNoOrphans:
    def test_pass_no_orphans(self, tmp_path):
        _write_apm_yml(tmp_path, deps=["owner/repo"])
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies:
                  - repo_url: owner/repo
                    deployed_files: []
            """),
        )
        from apm_cli.models.apm_package import APMPackage
        from apm_cli.deps.lockfile import LockFile, get_lockfile_path

        manifest = APMPackage.from_apm_yml(tmp_path / "apm.yml")
        lock = LockFile.read(get_lockfile_path(tmp_path))
        result = _check_no_orphans(manifest, lock)
        assert result.passed

    def test_fail_orphan_in_lockfile(self, tmp_path):
        _write_apm_yml(tmp_path, deps=["owner/repo"])
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies:
                  - repo_url: owner/repo
                    deployed_files: []
                  - repo_url: extra/orphan
                    deployed_files: []
            """),
        )
        from apm_cli.models.apm_package import APMPackage
        from apm_cli.deps.lockfile import LockFile, get_lockfile_path

        manifest = APMPackage.from_apm_yml(tmp_path / "apm.yml")
        lock = LockFile.read(get_lockfile_path(tmp_path))
        result = _check_no_orphans(manifest, lock)
        assert not result.passed
        assert "extra/orphan" in result.details


# -- Config consistency ---------------------------------------------


class TestConfigConsistency:
    def test_pass_no_mcp(self, tmp_path):
        _write_apm_yml(tmp_path, deps=["owner/repo"])
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies:
                  - repo_url: owner/repo
                    deployed_files: []
            """),
        )
        from apm_cli.models.apm_package import APMPackage
        from apm_cli.deps.lockfile import LockFile, get_lockfile_path

        manifest = APMPackage.from_apm_yml(tmp_path / "apm.yml")
        lock = LockFile.read(get_lockfile_path(tmp_path))
        result = _check_config_consistency(manifest, lock)
        assert result.passed

    def test_pass_mcp_configs_match(self, tmp_path):
        _write_apm_yml(tmp_path, mcp=["my-server"])
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies: []
                mcp_configs:
                  my-server:
                    name: my-server
            """),
        )
        from apm_cli.models.apm_package import APMPackage
        from apm_cli.deps.lockfile import LockFile, get_lockfile_path

        manifest = APMPackage.from_apm_yml(tmp_path / "apm.yml")
        lock = LockFile.read(get_lockfile_path(tmp_path))
        result = _check_config_consistency(manifest, lock)
        assert result.passed

    def test_fail_mcp_config_drift(self, tmp_path):
        # Manifest declares server with transport override, lockfile has plain
        _write_apm_yml(
            tmp_path,
            mcp=[{"name": "my-server", "transport": "stdio"}],
        )
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies: []
                mcp_configs:
                  my-server:
                    name: my-server
            """),
        )
        from apm_cli.models.apm_package import APMPackage
        from apm_cli.deps.lockfile import LockFile, get_lockfile_path

        manifest = APMPackage.from_apm_yml(tmp_path / "apm.yml")
        lock = LockFile.read(get_lockfile_path(tmp_path))
        result = _check_config_consistency(manifest, lock)
        assert not result.passed
        assert any("my-server" in d and "differs" in d for d in result.details)


# -- Content integrity ----------------------------------------------


class TestContentIntegrity:
    def test_pass_clean_files(self, tmp_path):
        _make_deployed_file(tmp_path, ".github/prompts/clean.md", "Clean content\n")
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies:
                  - repo_url: owner/repo
                    deployed_files:
                      - .github/prompts/clean.md
            """),
        )
        from apm_cli.deps.lockfile import LockFile, get_lockfile_path

        lock = LockFile.read(get_lockfile_path(tmp_path))
        result = _check_content_integrity(tmp_path, lock)
        assert result.passed

    def test_fail_critical_unicode(self, tmp_path):
        _make_deployed_file(
            tmp_path,
            ".github/prompts/evil.md",
            "Normal text\U000E0001\U000E0068hidden\n",
        )
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies:
                  - repo_url: owner/repo
                    deployed_files:
                      - .github/prompts/evil.md
            """),
        )
        from apm_cli.deps.lockfile import LockFile, get_lockfile_path

        lock = LockFile.read(get_lockfile_path(tmp_path))
        result = _check_content_integrity(tmp_path, lock)
        assert not result.passed
        assert any("evil.md" in d for d in result.details)


# -- Aggregate runner ----------------------------------------------


class TestRunBaselineChecks:
    def test_all_pass(self, tmp_path):
        _write_apm_yml(tmp_path, deps=["owner/repo#v1.0.0"])
        _make_deployed_file(tmp_path, ".github/prompts/test.md")
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies:
                  - repo_url: owner/repo
                    resolved_ref: v1.0.0
                    deployed_files:
                      - .github/prompts/test.md
            """),
        )
        result = run_baseline_checks(tmp_path)
        assert result.passed
        assert len(result.checks) == 6  # all 6 checks ran

    def test_mixed_pass_fail(self, tmp_path):
        # Ref mismatch (fail) + missing file (fail) + clean otherwise
        # Use fail_fast=False to let all checks run
        _write_apm_yml(tmp_path, deps=["owner/repo#v2.0.0"])
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies:
                  - repo_url: owner/repo
                    resolved_ref: v1.0.0
                    deployed_files:
                      - .github/prompts/gone.md
            """),
        )
        result = run_baseline_checks(tmp_path, fail_fast=False)
        assert not result.passed
        assert len(result.failed_checks) >= 2
        failed_names = {c.name for c in result.failed_checks}
        assert "ref-consistency" in failed_names
        assert "deployed-files-present" in failed_names

    def test_no_apm_yml(self, tmp_path):
        result = run_baseline_checks(tmp_path)
        assert result.passed
        assert len(result.checks) == 1  # only lockfile-exists

    def test_stops_early_on_lockfile_missing(self, tmp_path):
        _write_apm_yml(tmp_path, deps=["owner/repo"])
        result = run_baseline_checks(tmp_path)
        assert not result.passed
        assert len(result.checks) == 1
        assert result.checks[0].name == "lockfile-exists"

    def test_fail_fast_stops_after_first_failure(self, tmp_path):
        """fail_fast=True (default) stops after the first failing check."""
        _write_apm_yml(tmp_path, deps=["owner/repo#v2.0.0"])
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies:
                  - repo_url: owner/repo
                    resolved_ref: v1.0.0
                    deployed_files:
                      - .github/prompts/gone.md
            """),
        )
        result = run_baseline_checks(tmp_path, fail_fast=True)
        assert not result.passed
        # Should stop after ref-consistency (first failure), not run deployed-files
        assert len(result.failed_checks) == 1
        assert result.failed_checks[0].name == "ref-consistency"

    def test_fail_fast_false_runs_all_checks(self, tmp_path):
        """fail_fast=False runs all checks even after a failure."""
        _write_apm_yml(tmp_path, deps=["owner/repo#v2.0.0"])
        _write_lockfile(
            tmp_path,
            textwrap.dedent("""\
                lockfile_version: '1'
                generated_at: '2025-01-01T00:00:00Z'
                dependencies:
                  - repo_url: owner/repo
                    resolved_ref: v1.0.0
                    deployed_files:
                      - .github/prompts/gone.md
            """),
        )
        result = run_baseline_checks(tmp_path, fail_fast=False)
        assert not result.passed
        assert len(result.failed_checks) >= 2


# -- Serialization -------------------------------------------------


class TestSerialization:
    def test_to_json(self):
        result = CIAuditResult(
            checks=[
                CheckResult(name="a", passed=True, message="ok"),
                CheckResult(name="b", passed=False, message="bad", details=["x"]),
            ]
        )
        j = result.to_json()
        assert j["passed"] is False
        assert j["summary"]["total"] == 2
        assert j["summary"]["passed"] == 1
        assert j["summary"]["failed"] == 1
        assert len(j["checks"]) == 2

    def test_to_sarif(self):
        result = CIAuditResult(
            checks=[
                CheckResult(name="a", passed=True, message="ok"),
                CheckResult(name="b", passed=False, message="bad", details=["detail1"]),
            ]
        )
        s = result.to_sarif()
        assert s["version"] == "2.1.0"
        runs = s["runs"]
        assert len(runs) == 1
        assert len(runs[0]["results"]) == 1
        assert runs[0]["results"][0]["ruleId"] == "b"
        assert runs[0]["results"][0]["message"]["text"] == "detail1"

    def test_passed_property_all_pass(self):
        result = CIAuditResult(
            checks=[
                CheckResult(name="a", passed=True, message="ok"),
                CheckResult(name="b", passed=True, message="ok"),
            ]
        )
        assert result.passed is True

    def test_passed_property_one_fails(self):
        result = CIAuditResult(
            checks=[
                CheckResult(name="a", passed=True, message="ok"),
                CheckResult(name="b", passed=False, message="bad"),
            ]
        )
        assert result.passed is False

    def test_sarif_no_results_when_all_pass(self):
        result = CIAuditResult(
            checks=[
                CheckResult(name="a", passed=True, message="ok"),
            ]
        )
        s = result.to_sarif()
        assert s["runs"][0]["results"] == []
        assert s["runs"][0]["tool"]["driver"]["rules"] == []

    def test_sarif_uses_message_when_no_details(self):
        result = CIAuditResult(
            checks=[
                CheckResult(name="c", passed=False, message="the message"),
            ]
        )
        s = result.to_sarif()
        assert s["runs"][0]["results"][0]["message"]["text"] == "the message"
