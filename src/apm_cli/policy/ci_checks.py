"""Baseline CI checks for lockfile consistency.

These checks run without any policy file — they validate that the on-disk
state matches what the lockfile declares.  This is the "Terraform plan for
agent config" gate: if anything is out of sync, the check fails and the CI
pipeline should block the merge.

Exit-code contract (consumed by the ``apm audit --ci`` command):
  * All checks pass → exit 0
  * Any check fails  → exit 1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# ── Result data classes ───────────────────────────────────────────


@dataclass
class CheckResult:
    """Result of a single CI check."""

    name: str  # e.g., "lockfile-exists"
    passed: bool
    message: str  # human-readable description
    details: List[str] = field(default_factory=list)  # individual violations


@dataclass
class CIAuditResult:
    """Aggregate result of all CI checks."""

    checks: List[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failed_checks(self) -> List[CheckResult]:
        return [c for c in self.checks if not c.passed]

    def to_json(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "passed": self.passed,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.checks
            ],
            "summary": {
                "total": len(self.checks),
                "passed": sum(1 for c in self.checks if c.passed),
                "failed": sum(1 for c in self.checks if not c.passed),
            },
        }

    def to_sarif(self) -> dict:
        """Serialize to SARIF v2.1.0 format for GitHub Code Scanning."""
        results = []
        for check in self.checks:
            if not check.passed:
                for detail in check.details or [check.message]:
                    results.append(
                        {
                            "ruleId": check.name,
                            "level": "error",
                            "message": {"text": detail},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {
                                            "uri": "apm.lock.yaml",
                                        },
                                    },
                                }
                            ],
                        }
                    )
        return {
            "$schema": (
                "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/"
                "main/sarif-2.1/schema/sarif-schema-2.1.0.json"
            ),
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "apm-audit",
                            "version": "1.0.0",
                            "informationUri": "https://github.com/microsoft/apm",
                            "rules": [
                                {
                                    "id": check.name,
                                    "shortDescription": {"text": check.message},
                                }
                                for check in self.checks
                                if not check.passed
                            ],
                        },
                    },
                    "results": results,
                }
            ],
        }


# ── Individual checks ─────────────────────────────────────────────


def _check_lockfile_exists(project_root: Path) -> CheckResult:
    """Check that ``apm.lock.yaml`` is present when ``apm.yml`` has deps."""
    from ..deps.lockfile import get_lockfile_path

    apm_yml_path = project_root / "apm.yml"
    if not apm_yml_path.exists():
        return CheckResult(
            name="lockfile-exists",
            passed=True,
            message="No apm.yml found — nothing to check",
        )

    from ..models.apm_package import APMPackage

    try:
        manifest = APMPackage.from_apm_yml(apm_yml_path)
    except (ValueError, FileNotFoundError):
        return CheckResult(
            name="lockfile-exists",
            passed=True,
            message="Could not parse apm.yml — skipping lockfile check",
        )

    has_deps = manifest.has_apm_dependencies() or bool(manifest.get_mcp_dependencies())
    if not has_deps:
        return CheckResult(
            name="lockfile-exists",
            passed=True,
            message="No dependencies declared — lockfile not required",
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
        message="Lockfile missing — run 'apm install' to generate apm.lock.yaml",
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
        message=f"{len(mismatches)} ref mismatch(es) — run 'apm install' to update lockfile",
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
            f"{len(missing)} deployed file(s) missing — "
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
            f"{len(orphaned)} orphaned package(s) in lockfile — "
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

    # No MCP deps at all — nothing to check
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
            f"{len(details)} MCP config inconsistenc(ies) — "
            "run 'apm install' to reconcile"
        ),
        details=details,
    )


def _check_content_integrity(
    project_root: Path,
    lock: "LockFile",
) -> CheckResult:
    """Check deployed files for critical hidden Unicode characters."""
    from ..commands.audit import _scan_lockfile_packages

    findings_by_file, _files_scanned = _scan_lockfile_packages(project_root)

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
            f"{len(critical_files)} file(s) contain critical hidden Unicode — "
            "run 'apm audit --strip' to clean"
        ),
        details=critical_files,
    )


# ── Policy checks ─────────────────────────────────────────────────


def _load_raw_apm_yml(project_root: Path) -> Optional[dict]:
    """Load raw apm.yml as a dict for policy checks that inspect raw fields."""
    import yaml

    apm_yml_path = project_root / "apm.yml"
    if not apm_yml_path.exists():
        return None
    try:
        with open(apm_yml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _check_dependency_allowlist(
    deps: List["DependencyReference"],
    policy: "DependencyPolicy",
) -> CheckResult:
    """Check 1: every dependency matches policy allow list."""
    from .matcher import check_dependency_allowed

    if not policy.allow:
        return CheckResult(
            name="dependency-allowlist",
            passed=True,
            message="No dependency allow list configured",
        )

    violations: List[str] = []
    for dep in deps:
        ref = dep.get_canonical_dependency_string()
        allowed, reason = check_dependency_allowed(ref, policy)
        if not allowed and "not in allowed" in reason:
            violations.append(f"{ref}: {reason}")

    if not violations:
        return CheckResult(
            name="dependency-allowlist",
            passed=True,
            message="All dependencies match allow list",
        )
    return CheckResult(
        name="dependency-allowlist",
        passed=False,
        message=f"{len(violations)} dependency(ies) not in allow list",
        details=violations,
    )


def _check_dependency_denylist(
    deps: List["DependencyReference"],
    policy: "DependencyPolicy",
) -> CheckResult:
    """Check 2: no dependency matches policy deny list."""
    from .matcher import check_dependency_allowed

    if not policy.deny:
        return CheckResult(
            name="dependency-denylist",
            passed=True,
            message="No dependency deny list configured",
        )

    violations: List[str] = []
    for dep in deps:
        ref = dep.get_canonical_dependency_string()
        allowed, reason = check_dependency_allowed(ref, policy)
        if not allowed and "denied by pattern" in reason:
            violations.append(f"{ref}: {reason}")

    if not violations:
        return CheckResult(
            name="dependency-denylist",
            passed=True,
            message="No dependencies match deny list",
        )
    return CheckResult(
        name="dependency-denylist",
        passed=False,
        message=f"{len(violations)} dependency(ies) match deny list",
        details=violations,
    )


def _check_required_packages(
    deps: List["DependencyReference"],
    policy: "DependencyPolicy",
) -> CheckResult:
    """Check 3: every required package is in manifest deps."""
    if not policy.require:
        return CheckResult(
            name="required-packages",
            passed=True,
            message="No required packages configured",
        )

    dep_refs = {dep.get_canonical_dependency_string() for dep in deps}
    missing: List[str] = []
    for req in policy.require:
        pkg_name = req.split("#")[0]
        found = any(ref.startswith(pkg_name) for ref in dep_refs)
        if not found:
            missing.append(pkg_name)

    if not missing:
        return CheckResult(
            name="required-packages",
            passed=True,
            message="All required packages present in manifest",
        )
    return CheckResult(
        name="required-packages",
        passed=False,
        message=f"{len(missing)} required package(s) missing from manifest",
        details=missing,
    )


def _check_required_packages_deployed(
    deps: List["DependencyReference"],
    lock: Optional["LockFile"],
    policy: "DependencyPolicy",
) -> CheckResult:
    """Check 4: required packages appear in lockfile with deployed files."""
    if not policy.require or lock is None:
        return CheckResult(
            name="required-packages-deployed",
            passed=True,
            message="No required packages to verify deployment",
        )

    dep_refs = {dep.get_canonical_dependency_string() for dep in deps}
    not_deployed: List[str] = []
    for req in policy.require:
        pkg_name = req.split("#")[0]
        if not any(ref.startswith(pkg_name) for ref in dep_refs):
            continue  # not in manifest — check 3 handles this

        # Find in lockfile
        found_deployed = False
        for _key, locked in lock.dependencies.items():
            lock_ref = locked.get_unique_key()
            if lock_ref.startswith(pkg_name) and locked.deployed_files:
                found_deployed = True
                break
        if not found_deployed:
            not_deployed.append(pkg_name)

    if not not_deployed:
        return CheckResult(
            name="required-packages-deployed",
            passed=True,
            message="All required packages deployed",
        )
    return CheckResult(
        name="required-packages-deployed",
        passed=False,
        message=f"{len(not_deployed)} required package(s) not deployed",
        details=not_deployed,
    )


def _check_required_package_version(
    deps: List["DependencyReference"],
    lock: Optional["LockFile"],
    policy: "DependencyPolicy",
) -> CheckResult:
    """Check 5: required packages with version pins match per resolution strategy."""
    pinned = [(r, r.split("#", 1)) for r in policy.require if "#" in r]
    if not pinned or lock is None:
        return CheckResult(
            name="required-package-version",
            passed=True,
            message="No version-pinned required packages",
        )

    resolution = policy.require_resolution
    violations: List[str] = []
    warnings: List[str] = []

    for _req, parts in pinned:
        pkg_name, expected_ref = parts[0], parts[1]

        # Find in lockfile
        for _key, locked in lock.dependencies.items():
            lock_ref = locked.get_unique_key()
            if lock_ref.startswith(pkg_name):
                actual_ref = locked.resolved_ref or ""
                if actual_ref != expected_ref:
                    detail = (
                        f"{pkg_name}: expected ref '{expected_ref}', "
                        f"got '{actual_ref}'"
                    )
                    if resolution == "block":
                        violations.append(detail)
                    elif resolution == "policy-wins":
                        violations.append(detail)
                    else:  # project-wins
                        warnings.append(detail)
                break

    if not violations:
        return CheckResult(
            name="required-package-version",
            passed=True,
            message="Required package versions match"
            + (f" (warnings: {len(warnings)})" if warnings else ""),
            details=warnings,
        )
    return CheckResult(
        name="required-package-version",
        passed=False,
        message=f"{len(violations)} version mismatch(es)",
        details=violations,
    )


def _check_transitive_depth(
    lock: Optional["LockFile"],
    policy: "DependencyPolicy",
) -> CheckResult:
    """Check 6: no lockfile dep exceeds max_depth."""
    if lock is None or policy.max_depth >= 50:
        return CheckResult(
            name="transitive-depth",
            passed=True,
            message="No transitive depth limit configured"
            if policy.max_depth >= 50
            else "No lockfile to check",
        )

    violations: List[str] = []
    for key, dep in lock.dependencies.items():
        if dep.depth > policy.max_depth:
            violations.append(
                f"{key}: depth {dep.depth} exceeds limit {policy.max_depth}"
            )

    if not violations:
        return CheckResult(
            name="transitive-depth",
            passed=True,
            message=f"All dependencies within depth limit ({policy.max_depth})",
        )
    return CheckResult(
        name="transitive-depth",
        passed=False,
        message=f"{len(violations)} dependency(ies) exceed max depth {policy.max_depth}",
        details=violations,
    )


def _check_mcp_allowlist(
    mcp_deps: List,
    policy: "McpPolicy",
) -> CheckResult:
    """Check 7: MCP server names match allow list."""
    from .matcher import check_mcp_allowed

    if not policy.allow:
        return CheckResult(
            name="mcp-allowlist",
            passed=True,
            message="No MCP allow list configured",
        )

    violations: List[str] = []
    for mcp in mcp_deps:
        allowed, reason = check_mcp_allowed(mcp.name, policy)
        if not allowed and "not in allowed" in reason:
            violations.append(f"{mcp.name}: {reason}")

    if not violations:
        return CheckResult(
            name="mcp-allowlist",
            passed=True,
            message="All MCP servers match allow list",
        )
    return CheckResult(
        name="mcp-allowlist",
        passed=False,
        message=f"{len(violations)} MCP server(s) not in allow list",
        details=violations,
    )


def _check_mcp_denylist(
    mcp_deps: List,
    policy: "McpPolicy",
) -> CheckResult:
    """Check 8: no MCP server matches deny list."""
    from .matcher import check_mcp_allowed

    if not policy.deny:
        return CheckResult(
            name="mcp-denylist",
            passed=True,
            message="No MCP deny list configured",
        )

    violations: List[str] = []
    for mcp in mcp_deps:
        allowed, reason = check_mcp_allowed(mcp.name, policy)
        if not allowed and "denied by pattern" in reason:
            violations.append(f"{mcp.name}: {reason}")

    if not violations:
        return CheckResult(
            name="mcp-denylist",
            passed=True,
            message="No MCP servers match deny list",
        )
    return CheckResult(
        name="mcp-denylist",
        passed=False,
        message=f"{len(violations)} MCP server(s) match deny list",
        details=violations,
    )


def _check_mcp_transport(
    mcp_deps: List,
    policy: "McpPolicy",
) -> CheckResult:
    """Check 9: MCP transport values match policy allow list."""
    allowed_transports = policy.transport.allow
    if not allowed_transports:
        return CheckResult(
            name="mcp-transport",
            passed=True,
            message="No MCP transport restrictions configured",
        )

    violations: List[str] = []
    for mcp in mcp_deps:
        if mcp.transport and mcp.transport not in allowed_transports:
            violations.append(
                f"{mcp.name}: transport '{mcp.transport}' not in allowed {allowed_transports}"
            )

    if not violations:
        return CheckResult(
            name="mcp-transport",
            passed=True,
            message="All MCP transports comply with policy",
        )
    return CheckResult(
        name="mcp-transport",
        passed=False,
        message=f"{len(violations)} MCP transport violation(s)",
        details=violations,
    )


def _check_mcp_self_defined(
    mcp_deps: List,
    policy: "McpPolicy",
) -> CheckResult:
    """Check 10: self-defined MCP servers comply with policy."""
    self_defined_policy = policy.self_defined
    if self_defined_policy == "allow":
        return CheckResult(
            name="mcp-self-defined",
            passed=True,
            message="Self-defined MCP servers allowed",
        )

    self_defined = [m for m in mcp_deps if m.registry is False]
    if not self_defined:
        return CheckResult(
            name="mcp-self-defined",
            passed=True,
            message="No self-defined MCP servers found",
        )

    details = [f"{m.name}: self-defined server" for m in self_defined]
    if self_defined_policy == "deny":
        return CheckResult(
            name="mcp-self-defined",
            passed=False,
            message=f"{len(self_defined)} self-defined MCP server(s) denied by policy",
            details=details,
        )
    # warn — pass but with details
    return CheckResult(
        name="mcp-self-defined",
        passed=True,
        message=f"{len(self_defined)} self-defined MCP server(s) (warn)",
        details=details,
    )


def _check_compilation_target(
    raw_yml: Optional[dict],
    policy: "CompilationPolicy",
) -> CheckResult:
    """Check 11: compilation target matches policy."""
    enforce = policy.target.enforce
    allow = policy.target.allow

    if not enforce and not allow:
        return CheckResult(
            name="compilation-target",
            passed=True,
            message="No compilation target restrictions configured",
        )

    target = (raw_yml or {}).get("target")
    if not target:
        return CheckResult(
            name="compilation-target",
            passed=True,
            message="No compilation target set in manifest",
        )

    if enforce:
        if target != enforce:
            return CheckResult(
                name="compilation-target",
                passed=False,
                message=f"Target '{target}' does not match enforced '{enforce}'",
                details=[f"target: {target}, enforced: {enforce}"],
            )
    elif allow and target not in allow:
        return CheckResult(
            name="compilation-target",
            passed=False,
            message=f"Target '{target}' not in allowed list {allow}",
            details=[f"target: {target}, allowed: {allow}"],
        )

    return CheckResult(
        name="compilation-target",
        passed=True,
        message="Compilation target compliant",
    )


def _check_compilation_strategy(
    raw_yml: Optional[dict],
    policy: "CompilationPolicy",
) -> CheckResult:
    """Check 12: compilation strategy matches policy."""
    enforce = policy.strategy.enforce
    if not enforce:
        return CheckResult(
            name="compilation-strategy",
            passed=True,
            message="No compilation strategy enforced",
        )

    compilation = (raw_yml or {}).get("compilation", {})
    strategy = compilation.get("strategy") if isinstance(compilation, dict) else None
    if not strategy:
        return CheckResult(
            name="compilation-strategy",
            passed=True,
            message="No compilation strategy set in manifest",
        )

    if strategy != enforce:
        return CheckResult(
            name="compilation-strategy",
            passed=False,
            message=f"Strategy '{strategy}' does not match enforced '{enforce}'",
            details=[f"strategy: {strategy}, enforced: {enforce}"],
        )
    return CheckResult(
        name="compilation-strategy",
        passed=True,
        message="Compilation strategy compliant",
    )


def _check_source_attribution(
    raw_yml: Optional[dict],
    policy: "CompilationPolicy",
) -> CheckResult:
    """Check 13: source attribution enabled if policy requires."""
    if not policy.source_attribution:
        return CheckResult(
            name="source-attribution",
            passed=True,
            message="Source attribution not required by policy",
        )

    compilation = (raw_yml or {}).get("compilation", {})
    attribution = (
        compilation.get("source_attribution")
        if isinstance(compilation, dict)
        else None
    )
    if attribution is True:
        return CheckResult(
            name="source-attribution",
            passed=True,
            message="Source attribution enabled",
        )
    return CheckResult(
        name="source-attribution",
        passed=False,
        message="Source attribution required by policy but not enabled in manifest",
        details=["Set compilation.source_attribution: true in apm.yml"],
    )


def _check_required_manifest_fields(
    raw_yml: Optional[dict],
    policy: "ManifestPolicy",
) -> CheckResult:
    """Check 14: all required fields are present with non-empty values."""
    if not policy.required_fields:
        return CheckResult(
            name="required-manifest-fields",
            passed=True,
            message="No required manifest fields configured",
        )

    data = raw_yml or {}
    missing: List[str] = []
    for field_name in policy.required_fields:
        value = data.get(field_name)
        if not value:  # None, empty string, missing
            missing.append(field_name)

    if not missing:
        return CheckResult(
            name="required-manifest-fields",
            passed=True,
            message="All required manifest fields present",
        )
    return CheckResult(
        name="required-manifest-fields",
        passed=False,
        message=f"{len(missing)} required manifest field(s) missing",
        details=missing,
    )


def _check_scripts_policy(
    raw_yml: Optional[dict],
    policy: "ManifestPolicy",
) -> CheckResult:
    """Check 15: scripts section absent if policy denies it."""
    if policy.scripts != "deny":
        return CheckResult(
            name="scripts-policy",
            passed=True,
            message="Scripts allowed by policy",
        )

    scripts = (raw_yml or {}).get("scripts")
    if scripts:
        return CheckResult(
            name="scripts-policy",
            passed=False,
            message="Scripts section present but denied by policy",
            details=list(scripts.keys()) if isinstance(scripts, dict) else ["scripts"],
        )
    return CheckResult(
        name="scripts-policy",
        passed=True,
        message="No scripts section (compliant with deny policy)",
    )


_DEFAULT_GOVERNANCE_DIRS = [
    ".github/agents",
    ".github/instructions",
    ".github/hooks",
    ".cursor/rules",
    ".claude",
    ".opencode",
]


def _check_unmanaged_files(
    project_root: Path,
    lock: Optional["LockFile"],
    policy: "UnmanagedFilesPolicy",
) -> CheckResult:
    """Check 16: no untracked files in governance directories."""
    if policy.action == "ignore":
        return CheckResult(
            name="unmanaged-files",
            passed=True,
            message="Unmanaged files check disabled (action: ignore)",
        )

    dirs = policy.directories if policy.directories else _DEFAULT_GOVERNANCE_DIRS

    # Build set of deployed files from lockfile
    deployed: set = set()
    if lock:
        for _key, dep in lock.dependencies.items():
            for f in dep.deployed_files:
                deployed.add(f.rstrip("/"))

    unmanaged: List[str] = []
    for gov_dir in dirs:
        dir_path = project_root / gov_dir
        if not dir_path.exists() or not dir_path.is_dir():
            continue
        for file_path in dir_path.rglob("*"):
            if file_path.is_file():
                rel = file_path.relative_to(project_root).as_posix()
                if rel not in deployed:
                    unmanaged.append(rel)

    if not unmanaged:
        return CheckResult(
            name="unmanaged-files",
            passed=True,
            message="No unmanaged files in governance directories",
        )

    if policy.action == "warn":
        return CheckResult(
            name="unmanaged-files",
            passed=True,
            message=f"{len(unmanaged)} unmanaged file(s) found (warn)",
            details=unmanaged,
        )

    # action == "deny"
    return CheckResult(
        name="unmanaged-files",
        passed=False,
        message=f"{len(unmanaged)} unmanaged file(s) in governance directories",
        details=unmanaged,
    )


def run_policy_checks(
    project_root: Path,
    policy: "ApmPolicy",
) -> CIAuditResult:
    """Run policy checks against a project.

    These checks are ADDED to baseline checks — caller runs both.
    Returns :class:`CIAuditResult` with individual check results.
    """
    from ..deps.lockfile import LockFile, get_lockfile_path
    from ..models.apm_package import APMPackage, clear_apm_yml_cache

    result = CIAuditResult()

    # Load manifest
    apm_yml_path = project_root / "apm.yml"
    if not apm_yml_path.exists():
        return result

    try:
        clear_apm_yml_cache()
        manifest = APMPackage.from_apm_yml(apm_yml_path)
    except (ValueError, FileNotFoundError):
        return result

    # Load lockfile (optional — some checks work without it)
    lockfile_path = get_lockfile_path(project_root)
    lock = LockFile.read(lockfile_path) if lockfile_path.exists() else None

    # Load raw YAML for field-level checks
    raw_yml = _load_raw_apm_yml(project_root)

    # Get dependencies
    apm_deps = manifest.get_apm_dependencies()
    mcp_deps = manifest.get_mcp_dependencies()

    # Dependency checks (1-6)
    result.checks.append(_check_dependency_allowlist(apm_deps, policy.dependencies))
    result.checks.append(_check_dependency_denylist(apm_deps, policy.dependencies))
    result.checks.append(_check_required_packages(apm_deps, policy.dependencies))
    result.checks.append(
        _check_required_packages_deployed(apm_deps, lock, policy.dependencies)
    )
    result.checks.append(
        _check_required_package_version(apm_deps, lock, policy.dependencies)
    )
    result.checks.append(_check_transitive_depth(lock, policy.dependencies))

    # MCP checks (7-10)
    result.checks.append(_check_mcp_allowlist(mcp_deps, policy.mcp))
    result.checks.append(_check_mcp_denylist(mcp_deps, policy.mcp))
    result.checks.append(_check_mcp_transport(mcp_deps, policy.mcp))
    result.checks.append(_check_mcp_self_defined(mcp_deps, policy.mcp))

    # Compilation checks (11-13)
    result.checks.append(_check_compilation_target(raw_yml, policy.compilation))
    result.checks.append(_check_compilation_strategy(raw_yml, policy.compilation))
    result.checks.append(_check_source_attribution(raw_yml, policy.compilation))

    # Manifest checks (14-15)
    result.checks.append(_check_required_manifest_fields(raw_yml, policy.manifest))
    result.checks.append(_check_scripts_policy(raw_yml, policy.manifest))

    # Unmanaged files check (16)
    result.checks.append(
        _check_unmanaged_files(project_root, lock, policy.unmanaged_files)
    )

    return result


# ── Aggregate runner ──────────────────────────────────────────────


def run_baseline_checks(project_root: Path) -> CIAuditResult:
    """Run all baseline CI checks against a project directory.

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

    apm_yml_path = project_root / "apm.yml"
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

    # Check 2: Ref consistency
    result.checks.append(_check_ref_consistency(manifest, lock))

    # Check 3: Deployed files present
    result.checks.append(_check_deployed_files_present(project_root, lock))

    # Check 4: No orphaned packages
    result.checks.append(_check_no_orphans(manifest, lock))

    # Check 5: Config consistency (MCP)
    result.checks.append(_check_config_consistency(manifest, lock))

    # Check 6: Content integrity
    result.checks.append(_check_content_integrity(project_root, lock))

    return result
