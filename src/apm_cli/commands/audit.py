"""APM audit command — content integrity scanning for prompt files.

Scans installed APM packages (or arbitrary files) for hidden Unicode
characters that could embed invisible instructions.  This is the first
pillar of ``apm audit``; lock-file consistency (``--ci``) and drift
detection (``--drift``) are planned as future modes.

Exit codes:
    0 — clean (no findings, or info-only)
    1 — critical findings detected
    2 — warnings only (no critical)
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click

from ..deps.lockfile import LockFile, get_lockfile_path
from ..integration.base_integrator import BaseIntegrator
from ..security.content_scanner import ContentScanner, ScanFinding
from ..utils.console import (
    _get_console,
    _rich_echo,
    _rich_error,
    _rich_info,
    _rich_success,
    _rich_warning,
    STATUS_SYMBOLS,
)


# ── Helpers ────────────────────────────────────────────────────────


def _is_safe_lockfile_path(rel_path: str, project_root: Path) -> bool:
    """Return True if a relative path from the lockfile is safe to read.

    Reuses the same logic as ``BaseIntegrator.validate_deploy_path``
    (no ``..``, allowed prefix, resolves within root).
    """
    return BaseIntegrator.validate_deploy_path(rel_path, project_root)


def _scan_files_in_dir(
    dir_path: Path,
    base_label: str,
) -> Tuple[Dict[str, List[ScanFinding]], int]:
    """Recursively scan all files under a directory via SecurityGate.

    Returns (findings_by_file, files_scanned).
    """
    from ..security.gate import REPORT_POLICY, SecurityGate

    verdict = SecurityGate.scan_files(dir_path, policy=REPORT_POLICY)
    # Re-key findings with the base_label prefix for display
    findings: Dict[str, List[ScanFinding]] = {}
    for rel_path, file_findings in verdict.findings_by_file.items():
        label = f"{base_label}/{rel_path}"
        findings[label] = file_findings
    return findings, verdict.files_scanned


def _scan_lockfile_packages(
    project_root: Path,
    package_filter: Optional[str] = None,
) -> Tuple[Dict[str, List[ScanFinding]], int]:
    """Scan deployed files tracked in apm.lock.yaml.

    Returns:
        (findings_by_file, files_scanned) — findings grouped by file path
        and total number of files scanned.
    """
    lockfile_path = get_lockfile_path(project_root)
    lock = LockFile.read(lockfile_path)
    if lock is None:
        return {}, 0

    all_findings: Dict[str, List[ScanFinding]] = {}
    files_scanned = 0

    for dep_key, dep in lock.dependencies.items():
        # Filter to a specific package if requested
        if package_filter and dep_key != package_filter:
            continue

        for rel_path in dep.deployed_files:
            # Path safety: reject traversal attempts from crafted lockfiles
            if not _is_safe_lockfile_path(rel_path.rstrip("/"), project_root):
                continue

            abs_path = project_root / rel_path
            if not abs_path.exists():
                continue

            # Recurse into directories (e.g. skill folders)
            if abs_path.is_dir():
                dir_findings, dir_count = _scan_files_in_dir(abs_path, rel_path.rstrip("/"))
                files_scanned += dir_count
                all_findings.update(dir_findings)
                continue

            files_scanned += 1
            findings = ContentScanner.scan_file(abs_path)
            if findings:
                all_findings[rel_path] = findings

    return all_findings, files_scanned


def _scan_single_file(file_path: Path) -> Tuple[Dict[str, List[ScanFinding]], int]:
    """Scan a single arbitrary file.

    Returns (findings_by_file, files_scanned).
    """
    if not file_path.exists():
        _rich_error(f"File not found: {file_path}")
        sys.exit(1)
    if file_path.is_dir():
        _rich_error(f"Path is a directory, not a file: {file_path}")
        sys.exit(1)

    findings = ContentScanner.scan_file(file_path)
    files_scanned = 1
    if findings:
        # Resolve to absolute so --strip can locate the file reliably
        return {str(file_path.resolve()): findings}, files_scanned
    return {}, files_scanned


def _has_actionable_findings(
    findings_by_file: Dict[str, List[ScanFinding]],
) -> bool:
    """Return True if any finding is critical or warning (not just info)."""
    return any(
        f.severity in ("critical", "warning")
        for ff in findings_by_file.values()
        for f in ff
    )


def _render_findings_table(
    findings_by_file: Dict[str, List[ScanFinding]],
    verbose: bool = False,
) -> None:
    """Render a Rich table of scan findings."""
    console = _get_console()

    # Flatten into rows, sorted by severity (critical first)
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    rows: List[ScanFinding] = []
    for findings in findings_by_file.values():
        rows.extend(findings)
    rows.sort(key=lambda f: (severity_order.get(f.severity, 3), f.file, f.line))

    # Filter out info-level in non-verbose mode
    if not verbose:
        rows = [r for r in rows if r.severity != "info"]

    if not rows:
        return

    if console:
        try:
            from rich.table import Table
            from ..security.audit_report import relative_path_for_report

            table = Table(
                title=f"{STATUS_SYMBOLS['search']} Content Scan Findings",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Severity", style="bold", width=10)
            table.add_column("File", style="white")
            table.add_column("Location", style="dim", width=10)
            table.add_column("Codepoint", style="bold white", width=10)
            table.add_column("Description", style="white")

            sev_styles = {
                "critical": "bold red",
                "warning": "yellow",
                "info": "dim",
            }
            for f in rows:
                table.add_row(
                    f.severity.upper(),
                    relative_path_for_report(f.file),
                    f"{f.line}:{f.column}",
                    f.codepoint,
                    f.description,
                    style=sev_styles.get(f.severity, "white"),
                )
            console.print()
            console.print(table)
            return
        except (ImportError, Exception):
            pass

    # Fallback: plain text
    _rich_echo("")
    _rich_echo(
        f"{STATUS_SYMBOLS['search']} Content Scan Findings",
        color="cyan",
        bold=True,
    )
    for f in rows:
        sev_label = f.severity.upper()
        color = "red" if f.severity == "critical" else (
            "yellow" if f.severity == "warning" else "dim"
        )
        _rich_echo(
            f"  {sev_label:<10} {f.file} {f.line}:{f.column}  "
            f"{f.codepoint}  {f.description}",
            color=color,
        )


def _render_summary(
    findings_by_file: Dict[str, List[ScanFinding]],
    files_scanned: int,
) -> None:
    """Render a summary panel with counts."""
    all_findings: List[ScanFinding] = []
    for findings in findings_by_file.values():
        all_findings.extend(findings)

    counts = ContentScanner.summarize(all_findings)
    critical = counts.get("critical", 0)
    warning = counts.get("warning", 0)
    info = counts.get("info", 0)
    affected = len(findings_by_file)

    _rich_echo("")
    if critical > 0:
        _rich_echo(
            f"{STATUS_SYMBOLS['error']} {critical} critical finding(s) in "
            f"{affected} file(s) — hidden characters detected",
            color="red",
            bold=True,
        )
        _rich_info("  These characters may embed invisible instructions")
        _rich_info("  Review file contents, then run 'apm audit --strip' to remove")
    elif warning > 0:
        _rich_warning(
            f"{STATUS_SYMBOLS['warning']} {warning} warning(s) in "
            f"{affected} file(s) — hidden characters detected"
        )
        _rich_info("  Run 'apm audit --strip' to remove hidden characters")
    elif info > 0:
        _rich_info(
            f"{STATUS_SYMBOLS['info']} {info} info-level finding(s) in "
            f"{affected} file(s) — unusual characters (use --verbose to see)"
        )
    else:
        _rich_success(
            f"{STATUS_SYMBOLS['success']} {files_scanned} file(s) scanned — "
            f"no issues found"
        )

    if info > 0 and (critical > 0 or warning > 0):
        _rich_info(f"  Plus {info} info-level finding(s) (use --verbose to see)")

    _rich_echo(f"  {files_scanned} file(s) scanned", color="dim")


def _apply_strip(
    findings_by_file: Dict[str, List[ScanFinding]],
    project_root: Path,
) -> int:
    """Strip dangerous and suspicious characters from affected files.

    Only modifies files that resolve within *project_root* (for lockfile
    paths) or that are given as absolute paths (for ``--file`` mode).
    Returns number of files modified.
    """
    modified = 0
    for rel_path, findings in findings_by_file.items():

        abs_path = Path(rel_path)
        if not abs_path.is_absolute():
            # Relative path from lockfile: validate within project_root
            abs_path = project_root / rel_path
            try:
                abs_path.resolve().relative_to(project_root.resolve())
            except ValueError:
                _rich_warning(f"  Skipping {rel_path}: outside project root")
                continue

        if not abs_path.exists():
            continue

        try:
            original = abs_path.read_text(encoding="utf-8")
            cleaned = ContentScanner.strip_dangerous(original)
            if cleaned != original:
                abs_path.write_text(cleaned, encoding="utf-8")
                modified += 1
                _rich_info(f"  {STATUS_SYMBOLS['check']} Cleaned: {rel_path}")
        except (OSError, UnicodeDecodeError) as exc:
            _rich_warning(f"  Could not clean {rel_path}: {exc}")

    return modified


def _preview_strip(
    findings_by_file: Dict[str, List[ScanFinding]],
) -> int:
    """Preview what --strip would remove without modifying files.

    Shows a summary of strippable characters per file.
    Returns the number of files that would be modified.
    """
    console = _get_console()
    affected = 0

    for rel_path, findings in findings_by_file.items():
        # Only critical+warning chars are stripped
        strippable = [f for f in findings if f.severity in ("critical", "warning")]
        if not strippable:
            continue
        affected += 1

    if affected == 0:
        _rich_info("Nothing to clean — no strippable characters found")
        return 0

    _rich_echo("")
    _rich_info(f"Dry run — the following would be removed by --strip:", symbol="search")
    _rich_echo("")

    if console:
        try:
            from rich.table import Table

            table = Table(
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("File", style="white")
            table.add_column("Critical", style="bold red", justify="right", width=10)
            table.add_column("Warning", style="yellow", justify="right", width=10)
            table.add_column("Total", style="bold white", justify="right", width=10)

            for rel_path, findings in findings_by_file.items():
                strippable = [f for f in findings if f.severity in ("critical", "warning")]
                if not strippable:
                    continue
                crit = sum(1 for f in strippable if f.severity == "critical")
                warn = sum(1 for f in strippable if f.severity == "warning")
                table.add_row(
                    rel_path,
                    str(crit) if crit else "-",
                    str(warn) if warn else "-",
                    str(len(strippable)),
                )

            console.print(table)
        except (ImportError, Exception):
            # Fallback: plain text
            for rel_path, findings in findings_by_file.items():
                strippable = [f for f in findings if f.severity in ("critical", "warning")]
                if not strippable:
                    continue
                _rich_echo(f"  {rel_path}: {len(strippable)} character(s)", color="white")
    else:
        for rel_path, findings in findings_by_file.items():
            strippable = [f for f in findings if f.severity in ("critical", "warning")]
            if not strippable:
                continue
            _rich_echo(f"  {rel_path}: {len(strippable)} character(s)", color="white")

    _rich_echo("")
    _rich_info(f"{affected} file(s) would be modified")
    _rich_info("Run 'apm audit --strip' to apply")
    return affected


def _render_ci_results(ci_result: "CIAuditResult") -> None:
    """Render CI check results as a Rich table (text format)."""
    from ..policy.ci_checks import CIAuditResult

    console = _get_console()

    if console:
        try:
            from rich.table import Table

            table = Table(
                title=f"{STATUS_SYMBOLS['search']} CI Lockfile Consistency Checks",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Status", style="bold", width=8)
            table.add_column("Check", style="white")
            table.add_column("Message", style="white")

            for check in ci_result.checks:
                status = (
                    f"[green]{STATUS_SYMBOLS['check']}[/green]"
                    if check.passed
                    else f"[red]{STATUS_SYMBOLS['cross']}[/red]"
                )
                table.add_row(status, check.name, check.message)

            console.print()
            console.print(table)

            # Show details for failed checks
            for check in ci_result.failed_checks:
                if check.details:
                    console.print()
                    _rich_echo(
                        f"  {check.name} details:",
                        color="red",
                        bold=True,
                    )
                    for detail in check.details:
                        _rich_echo(f"    - {detail}", color="dim")

            console.print()
            summary = ci_result.to_json()["summary"]
            if ci_result.passed:
                _rich_success(
                    f"{STATUS_SYMBOLS['success']} All {summary['total']} check(s) passed"
                )
            else:
                _rich_error(
                    f"{STATUS_SYMBOLS['error']} {summary['failed']} of "
                    f"{summary['total']} check(s) failed"
                )
            return
        except (ImportError, Exception):
            pass

    # Fallback: plain text
    _rich_echo("")
    _rich_echo(
        f"{STATUS_SYMBOLS['search']} CI Lockfile Consistency Checks",
        color="cyan",
        bold=True,
    )
    for check in ci_result.checks:
        symbol = STATUS_SYMBOLS["check"] if check.passed else STATUS_SYMBOLS["cross"]
        color = "green" if check.passed else "red"
        _rich_echo(f"  {symbol} {check.name}: {check.message}", color=color)
        if not check.passed and check.details:
            for detail in check.details:
                _rich_echo(f"      - {detail}", color="dim")

    _rich_echo("")
    summary = ci_result.to_json()["summary"]
    if ci_result.passed:
        _rich_success(
            f"{STATUS_SYMBOLS['success']} All {summary['total']} check(s) passed"
        )
    else:
        _rich_error(
            f"{STATUS_SYMBOLS['error']} {summary['failed']} of "
            f"{summary['total']} check(s) failed"
        )


# ── Command ────────────────────────────────────────────────────────


@click.command(help="Scan installed packages for hidden Unicode characters")
@click.argument("package", required=False)
@click.option(
    "--file",
    "file_path",
    type=click.Path(exists=False),
    help="Scan an arbitrary file (not just APM-managed files)",
)
@click.option(
    "--strip",
    is_flag=True,
    help="Remove hidden characters from scanned files (preserves emoji and whitespace)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show all findings including harmless ones",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview what --strip would remove without modifying files",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["text", "json", "sarif", "markdown"], case_sensitive=False),
    default="text",
    help="Output format: text (default), json, sarif (GitHub Code Scanning), markdown (step summaries).",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(),
    default=None,
    help="Write output to file (auto-detects format from extension: .sarif, .json, .md).",
)
@click.option(
    "--ci",
    is_flag=True,
    help="Run lockfile consistency checks for CI/CD gates. Exit 0 if clean, 1 if violations found.",
)
@click.option(
    "--policy",
    "policy_source",
    default=None,
    help="Policy source: 'org' (auto-discover), file path, or URL. Used with --ci for policy checks.",
)
@click.option(
    "--no-cache",
    "no_cache",
    is_flag=True,
    help="Force fresh policy fetch (skip cache).",
)
@click.pass_context
def audit(ctx, package, file_path, strip, verbose, dry_run, output_format, output_path, ci, policy_source, no_cache):
    """Scan deployed prompt files for hidden Unicode characters.

    Detects invisible characters that could embed hidden instructions in
    prompt, instruction, and rules files. Dangerous and suspicious
    characters can be removed with --strip.

    With --ci, runs lockfile consistency checks instead of content scanning.
    This validates that the on-disk state matches what the lockfile declares,
    suitable for CI/CD pipeline gates.

    \b
    Exit codes:
        0  Clean, info-only findings, or successful strip
        1  Critical findings detected (or --ci with violations)
        2  Warning-only findings (suspicious but not critical)

    \b
    Examples:
        apm audit                      # Scan all installed packages
        apm audit my-package           # Scan a specific package
        apm audit --file .cursorrules  # Scan any file
        apm audit --strip              # Remove dangerous/suspicious chars
        apm audit --ci                 # Lockfile consistency gate
        apm audit --ci --policy org    # CI gate with org policy checks
        apm audit --ci -f json         # JSON CI report
        apm audit --ci -f sarif        # SARIF for GitHub Code Scanning
        apm audit -o report.sarif      # Write SARIF to file
    """
    project_root = Path.cwd()

    # ── CI mode: lockfile consistency gate ─────────────────────────
    if ci:
        if strip or dry_run or file_path or package:
            _rich_error(
                "--ci cannot be combined with --strip, --dry-run, --file, or PACKAGE"
            )
            sys.exit(1)

        from ..policy.ci_checks import run_baseline_checks, run_policy_checks

        # Always run baseline checks
        ci_result = run_baseline_checks(project_root)

        # Optionally run policy checks
        if policy_source:
            from ..policy.discovery import discover_policy

            fetch_result = discover_policy(
                project_root,
                policy_override=policy_source,
                no_cache=no_cache,
            )

            if fetch_result.error:
                _rich_error(f"Policy fetch failed: {fetch_result.error}")
                sys.exit(1)

            if fetch_result.found:
                policy_result = run_policy_checks(
                    project_root, fetch_result.policy
                )
                ci_result.checks.extend(policy_result.checks)

        # Resolve effective format
        effective_format = output_format
        if output_path and effective_format == "text":
            from ..security.audit_report import detect_format_from_extension

            effective_format = detect_format_from_extension(Path(output_path))

        if effective_format in ("json", "sarif"):
            import json as _json

            payload = (
                ci_result.to_sarif()
                if effective_format == "sarif"
                else ci_result.to_json()
            )
            output = _json.dumps(payload, indent=2)
            if output_path:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_text(output, encoding="utf-8")
                _rich_success(f"CI audit report written to {output_path}")
            else:
                click.echo(output)
        else:
            _render_ci_results(ci_result)

        sys.exit(0 if ci_result.passed else 1)

    # ── Content scan mode ──────────────────────────────────────────

    # Resolve effective format (auto-detect from extension when needed)
    effective_format = output_format
    if output_path and effective_format == "text":
        from ..security.audit_report import detect_format_from_extension

        effective_format = detect_format_from_extension(Path(output_path))

    # --format json/sarif/markdown is incompatible with --strip / --dry-run
    if effective_format != "text" and (strip or dry_run):
        _rich_error(
            f"--format {effective_format} cannot be combined with --strip or --dry-run"
        )
        sys.exit(1)

    if file_path:
        # -- File mode: scan a single arbitrary file --
        findings_by_file, files_scanned = _scan_single_file(Path(file_path))
    else:
        # -- Package mode: scan from lockfile --
        lockfile_path = get_lockfile_path(project_root)
        if not lockfile_path.exists():
            _rich_info(
                "No apm.lock.yaml found — nothing to scan. "
                "Use --file to scan a specific file."
            )
            sys.exit(0)

        if package:
            _rich_info(f"Scanning package: {package}")
        else:
            _rich_info("Scanning all installed packages...")

        findings_by_file, files_scanned = _scan_lockfile_packages(
            project_root, package_filter=package,
        )

        if files_scanned == 0:
            if package:
                _rich_warning(
                    f"Package '{package}' not found in apm.lock.yaml "
                    f"or has no deployed files"
                )
            else:
                _rich_info("No deployed files found in apm.lock.yaml")
            sys.exit(0)

    # -- Warn if --dry-run used without --strip --
    if dry_run and not strip:
        _rich_info("--dry-run only works with --strip (e.g. apm audit --strip --dry-run)")

    # -- Strip mode --
    if strip:
        if not findings_by_file:
            _rich_info("Nothing to clean — no hidden characters found")
            sys.exit(0)
        if dry_run:
            _preview_strip(findings_by_file)
            sys.exit(0)
        modified = _apply_strip(findings_by_file, project_root)
        if modified > 0:
            _rich_success(
                f"{STATUS_SYMBOLS['success']} Cleaned {modified} file(s)"
            )
        else:
            _rich_info("Nothing to clean — no strippable characters found")
        sys.exit(0)

    # -- Display findings --
    # Determine exit code first (shared by all formats)
    if not findings_by_file or not _has_actionable_findings(findings_by_file):
        exit_code = 0
    else:
        all_findings = [f for ff in findings_by_file.values() for f in ff]
        exit_code = 1 if ContentScanner.has_critical(all_findings) else 2

    if effective_format == "text":
        if output_path:
            _rich_error(
                "Text format does not support --output. "
                "Use --format json, sarif, or markdown to write to a file."
            )
            sys.exit(1)
        if findings_by_file:
            _render_findings_table(findings_by_file, verbose=verbose)
        _render_summary(findings_by_file, files_scanned)
    elif effective_format == "markdown":
        from ..security.audit_report import findings_to_markdown

        md_report = findings_to_markdown(findings_by_file, files_scanned=files_scanned)
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(md_report, encoding="utf-8")
            _rich_success(f"Audit report written to {output_path}")
        else:
            click.echo(md_report)
    else:
        from ..security.audit_report import (
            findings_to_json,
            findings_to_sarif,
            serialize_report,
            write_report,
        )

        if effective_format == "sarif":
            report = findings_to_sarif(
                findings_by_file, files_scanned=files_scanned
            )
        else:
            report = findings_to_json(
                findings_by_file,
                files_scanned=files_scanned,
                exit_code=exit_code,
            )

        if output_path:
            write_report(report, Path(output_path))
            _rich_success(f"Audit report written to {output_path}")
        else:
            click.echo(serialize_report(report))

    # -- Exit code --
    sys.exit(exit_code)
