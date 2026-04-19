"""Baseline CI checks for lockfile consistency.

These checks run without any policy file -- they validate that the on-disk
state matches what the lockfile declares.  This is the "Terraform plan for
agent config" gate: if anything is out of sync, the check fails and the CI
pipeline should block the merge.

Exit-code contract (consumed by the ``apm audit --ci`` command):
  * All checks pass -> exit 0
  * Any check fails  -> exit 1
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from .models import CIAuditResult, CheckResult


# -- Individual checks ---------------------------------------------


def _check_lockfile_exists(project_root: Path) -> CheckResult:
    """Check that ``apm.lock.yaml`` is present when ``apm.yml`` has deps."""
    from ..deps.lockfile import get_lockfile_path

    apm_yml_path = project_root / "apm.yaml"
    if not apm_yml_path.exists():
        return CheckResult(
            name="lockfile-exists",
            passed=True,
            message="No apm.yml found -- nothing to check",
        )

    from ..models.apm_package import APMPackage

    try:
        manifest = APMPackage.from_apm_yml(apm_yml_path)
    except (ValueError, FileNotFoundError):
        return CheckResult(
            name="lockfile-exists",
            passed=True,
            message="Could not parse apm.yml -- skipping lockfile check",
        )

    has_deps = manifest.has_apm_dependencies() or bool(manifest.get_mcp_dependencies())
    if not has_deps:
        return CheckResult(
            name="lockfile-exists",
            passed=True,
            message="No dependencies declared -- lockfile not required",
        )

    lockfile_path = get_lockfile_path(project_root)
    if lockfile_path.exists():
        return CheckResult(
            name="lockfile-exists",
            passed=True,
            message="Lockfile present",
        )

    return CheckResult(
        name="lockfile-exists",
        passed=False,
        message="Lockfile missing -- run 'apm install' to generate apm.lock.yaml",
        details=["apm.yml declares dependencies but apm.lock.yaml is absent"],
    )


def _check_ref_consistency(
    manifest: "APMPackage",
    lock: "LockFile",
) -> CheckResult:
    """Verify every dependency's manifest ref matches lockfile resolved_ref."""
    from ..drift import detect_ref_change

    mismatches: List[str] = []
    for dep_ref in manifest.get_apm_dependencies():
        key = dep_ref.get_unique_key()
        locked_dep = lock.get_dependency(key)
        if locked_dep is None:
            mismatches.append(f"{key}: not found in lockfile")
            continue
        if detect_ref_change(dep_ref, locked_dep):
            manifest_ref = dep_ref.reference or "(default branch)"
            locked_ref = locked_dep.resolved_ref or "(default branch)"
            mismatches.append(
                f"{key}: manifest ref '{manifest_ref}' != lockfile ref '{locked_ref}'"
            )

    if not mismatches:
        return CheckResult(
            name="ref-consistency",
            passed=True,
            message="All dependency refs match lockfile",
        )
    return CheckResult(
        name="ref-consistency",
        passed=False,
        message=f"{len(mismatches)} ref mismatch(es) -- run 'apm install' to update lockfile",
        details=mismatches,
    )


def _check_deployed_files_present(
    project_root: Path,
    lock: "LockFile",
) -> CheckResult:
    """Verify all files listed in lockfile deployed_files exist on disk."""
    from ..integration.base_integrator import BaseIntegrator

    missing: List[str] = []
    for _dep_key, dep in lock.dependencies.items():
        for rel_path in dep.deployed_files:
            safe_path = rel_path.rstrip("/")
            if not BaseIntegrator.validate_deploy_path(safe_path, project_root):
                continue  # skip unsafe paths silently
            abs_path = project_root / rel_path
            if not abs_path.exists():
                missing.append(rel_path)

    if not missing:
        return CheckResult(
            name="deployed-files-present",
            passed=True,
            message="All deployed files present on disk",
        )
    return CheckResult(
        name="deployed-files-present",
        passed=False,
        message=(
            f"{len(missing)} deployed file(s) missing -- "
            "run 'apm install' to restore"
        ),
        details=missing,
    )


def _check_no_orphans(
    manifest: "APMPackage",
    lock: "LockFile",
) -> CheckResult:
    """Verify no packages in lockfile are absent from manifest."""
    manifest_keys = {dep.get_unique_key() for dep in manifest.get_apm_dependencies()}
    orphaned = [
        dep_key
        for dep_key in lock.dependencies
        if dep_key not in manifest_keys
    ]
    if not orphaned:
        return CheckResult(
            name="no-orphaned-packages",
            passed=True,
            message="No orphaned packages in lockfile",
        )
    return CheckResult(
        name="no-orphaned-packages",
        passed=False,
        message=(
            f"{len(orphaned)} orphaned package(s) in lockfile -- "
            "run 'apm install' to clean up"
        ),
        details=orphaned,
    )


def _check_config_consistency(
    manifest: "APMPackage",
    lock: "LockFile",
) -> CheckResult:
    """Verify MCP server configs match lockfile baseline."""
    from ..drift import detect_config_drift
    from ..integration.mcp_integrator import MCPIntegrator

    mcp_deps = manifest.get_mcp_dependencies()
    current_configs = MCPIntegrator.get_server_configs(mcp_deps)
    stored_configs = lock.mcp_configs or {}

    # No MCP deps at all -- nothing to check
    if not current_configs and not stored_configs:
        return CheckResult(
            name="config-consistency",
            passed=True,
            message="No MCP configs to check",
        )

    details: List[str] = []

    # Detect drift on servers that exist in both sets
    drifted = detect_config_drift(current_configs, stored_configs)
    for name in sorted(drifted):
        details.append(f"{name}: config differs from lockfile baseline")

    # Servers in lockfile but not in manifest (orphaned MCP)
    for name in sorted(stored_configs):
        if name not in current_configs:
            details.append(f"{name}: in lockfile but not in manifest")

    # Servers in manifest but not in lockfile (new, not installed)
    for name in sorted(current_configs):
        if name not in stored_configs:
            details.append(f"{name}: in manifest but not in lockfile")

    if not details:
        return CheckResult(
            name="config-consistency",
            passed=True,
            message="MCP configs match lockfile baseline",
        )
    return CheckResult(
        name="config-consistency",
        passed=False,
        message=(
            f"{len(details)} MCP config inconsistenc(ies) -- "
            "run 'apm install' to reconcile"
        ),
        details=details,
    )


def _check_content_integrity(
    project_root: Path,
    lock: "LockFile",
) -> CheckResult:
    """Check deployed files for critical hidden Unicode characters."""
    from ..security.file_scanner import scan_lockfile_packages

    findings_by_file, _files_scanned = scan_lockfile_packages(project_root)

    # Only critical findings fail this check
    critical_files: List[str] = []
    for rel_path, findings in findings_by_file.items():
        if any(f.severity == "critical" for f in findings):
            critical_files.append(rel_path)

    if not critical_files:
        return CheckResult(
            name="content-integrity",
            passed=True,
            message="No critical hidden Unicode characters detected",
        )
    return CheckResult(
        name="content-integrity",
        passed=False,
        message=(
            f"{len(critical_files)} file(s) contain critical hidden Unicode -- "
            "run 'apm audit --strip' to clean"
        ),
        details=critical_files,
    )


# -- Aggregate runner ----------------------------------------------


def run_baseline_checks(
    project_root: Path,
    *,
    fail_fast: bool = True,
) -> CIAuditResult:
    """Run all baseline CI checks against a project directory.

    When *fail_fast* is ``True`` (default), stops after the first
    failing check to skip expensive I/O (e.g. content integrity scan).
    Returns :class:`CIAuditResult` with individual check results.
    """
    from ..deps.lockfile import LockFile, get_lockfile_path
    from ..models.apm_package import APMPackage, clear_apm_yml_cache

    result = CIAuditResult()

    # Check 1: Lockfile exists
    result.checks.append(_check_lockfile_exists(project_root))

    # If lockfile doesn't exist or isn't needed, remaining checks can't run
    if not result.checks[0].passed:
        return result

    apm_yml_path = project_root / "apm.yaml"
    lockfile_path = get_lockfile_path(project_root)

    # If there's no apm.yml or no lockfile, the first check already passed
    # (no deps needed).  Skip remaining checks.
    if not apm_yml_path.exists() or not lockfile_path.exists():
        return result

    try:
        clear_apm_yml_cache()
        manifest = APMPackage.from_apm_yml(apm_yml_path)
    except (ValueError, FileNotFoundError):
        return result

    lock = LockFile.read(lockfile_path)
    if lock is None:
        return result

    def _run(check: CheckResult) -> bool:
        """Append check and return True if fail-fast should stop."""
        result.checks.append(check)
        return fail_fast and not check.passed

    # Check 2: Ref consistency
    if _run(_check_ref_consistency(manifest, lock)):
        return result

    # Check 3: Deployed files present
    if _run(_check_deployed_files_present(project_root, lock)):
        return result

    # Check 4: No orphaned packages
    if _run(_check_no_orphans(manifest, lock)):
        return result

    # Check 5: Config consistency (MCP)
    if _run(_check_config_consistency(manifest, lock)):
        return result

    # Check 6: Content integrity
    _run(_check_content_integrity(project_root, lock))

    return result
