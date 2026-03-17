"""Bundle packer  -- creates self-contained APM bundles from the resolved dependency tree."""

import os
import shutil
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from ..deps.lockfile import LockFile, get_lockfile_path, migrate_lockfile_if_needed
from ..models.apm_package import APMPackage
from ..core.target_detection import detect_target
from .lockfile_enrichment import enrich_lockfile_for_pack


# Target prefix mapping ("copilot" and "vscode" both map to .github/)
_TARGET_PREFIXES = {
    "copilot": [".github/"],
    "vscode": [".github/"],
    "claude": [".claude/"],
    "cursor": [".cursor/"],
    "opencode": [".opencode/"],
    "all": [".github/", ".claude/", ".cursor/", ".opencode/"],
}


@dataclass
class PackResult:
    """Result of a pack operation."""

    bundle_path: Path
    files: List[str] = field(default_factory=list)
    lockfile_enriched: bool = False


def _filter_files_by_target(deployed_files: List[str], target: str) -> List[str]:
    """Filter deployed file paths by target prefix."""
    prefixes = _TARGET_PREFIXES.get(target, _TARGET_PREFIXES["all"])
    return [f for f in deployed_files if any(f.startswith(p) for p in prefixes)]


def pack_bundle(
    project_root: Path,
    output_dir: Path,
    fmt: str = "apm",
    target: Optional[str] = None,
    archive: bool = False,
    dry_run: bool = False,
) -> PackResult:
    """Create a self-contained bundle from installed APM dependencies.

    Args:
        project_root: Root of the project containing ``apm.lock.yaml`` and ``apm.yml``.
        output_dir: Directory where the bundle will be created.
        fmt: Bundle format  -- ``"apm"`` (default) or ``"plugin"``.
        target: Target filter  -- ``"vscode"``, ``"claude"``, ``"all"``, or *None*
            (auto-detect from apm.yml / project structure).
        archive: If *True*, produce a ``.tar.gz`` and remove the directory.
        dry_run: If *True*, resolve the file list but write nothing to disk.

    Returns:
        :class:`PackResult` describing what was (or would be) produced.

    Raises:
        FileNotFoundError: If ``apm.lock.yaml`` is missing.
        ValueError: If deployed files referenced in the lockfile are missing on disk.
    """
    # 1. Read lockfile (migrate legacy apm.lock → apm.lock.yaml if needed)
    migrate_lockfile_if_needed(project_root)
    lockfile_path = get_lockfile_path(project_root)
    lockfile = LockFile.read(lockfile_path)
    if lockfile is None:
        raise FileNotFoundError(
            "apm.lock.yaml not found  -- run 'apm install' first to resolve dependencies."
        )

    # 2. Read apm.yml for name / version / config target
    apm_yml_path = project_root / "apm.yml"
    try:
        package = APMPackage.from_apm_yml(apm_yml_path)
        pkg_name = package.name
        pkg_version = package.version or "0.0.0"
        config_target = package.target

        # Guard: reject local-path dependencies (non-portable)
        for dep_ref in package.get_apm_dependencies():
            if dep_ref.is_local:
                raise ValueError(
                    f"Cannot pack — apm.yml contains local path dependency: "
                    f"{dep_ref.local_path}\n"
                    f"Local dependencies are for development only. Replace them with "
                    f"remote references (e.g., 'owner/repo') before packing."
                )
    except ValueError:
        raise
    except FileNotFoundError:
        pkg_name = project_root.resolve().name
        pkg_version = "0.0.0"
        config_target = None

    # 3. Resolve effective target
    effective_target, _reason = detect_target(
        project_root,
        explicit_target=target,
        config_target=config_target,
    )
    # For packing purposes, "minimal" means nothing to pack  -- treat as "all"
    if effective_target == "minimal":
        effective_target = "all"

    # 4. Collect deployed_files from all dependencies, filtered by target
    all_deployed: List[str] = []
    for dep in lockfile.get_all_dependencies():
        all_deployed.extend(dep.deployed_files)

    filtered_files = _filter_files_by_target(all_deployed, effective_target)
    # Deduplicate while preserving order
    seen = set()
    unique_files: List[str] = []
    for f in filtered_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    # 5. Verify each path is safe (no traversal) and exists on disk
    project_root_resolved = project_root.resolve()
    missing: List[str] = []
    for rel_path in unique_files:
        # Guard against absolute paths or path-traversal entries in deployed_files
        p = Path(rel_path)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(
                f"Refusing to pack unsafe path from lockfile: {rel_path!r}"
            )
        abs_path = project_root / rel_path
        if not abs_path.resolve().is_relative_to(project_root_resolved):
            raise ValueError(
                f"Refusing to pack path that escapes project root: {rel_path!r}"
            )
        # deployed_files may reference directories (ending with /)
        if not abs_path.exists():
            missing.append(rel_path)
    if missing:
        raise ValueError(
            f"The following deployed files are missing on disk  -- "
            f"run 'apm install' to restore them:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )

    # Dry-run: return file list without writing anything
    if dry_run:
        bundle_dir = output_dir / f"{pkg_name}-{pkg_version}"
        return PackResult(
            bundle_path=bundle_dir,
            files=unique_files,
            lockfile_enriched=True,
        )

    # 5b. Scan files for hidden characters before bundling.
    # Intentionally non-blocking (warn only) — pack is an authoring tool.
    # Critical findings here mean the author's own source files contain
    # hidden characters. We surface them so the author can fix before
    # publishing, but don't block the bundle. Consumers are protected by
    # install/unpack which block on critical.
    from ..security.gate import WARN_POLICY, SecurityGate
    from ..utils.console import _rich_warning

    _scan_findings_total = 0
    for rel_path in unique_files:
        src = project_root / rel_path
        if src.is_symlink():
            continue
        if src.is_dir():
            verdict = SecurityGate.scan_files(src, policy=WARN_POLICY)
            _scan_findings_total += len(verdict.all_findings)
        elif src.is_file():
            verdict = SecurityGate.scan_text(
                src.read_text(encoding="utf-8", errors="replace"),
                str(src), policy=WARN_POLICY,
            )
            _scan_findings_total += len(verdict.all_findings)
    if _scan_findings_total:
        _rich_warning(
            f"Bundle contains {_scan_findings_total} hidden character(s) across source files "
            f"— run 'apm audit' to inspect before publishing"
        )

    # 6. Build output directory
    bundle_dir = output_dir / f"{pkg_name}-{pkg_version}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # 7. Copy files preserving directory structure
    for rel_path in unique_files:
        src = project_root / rel_path
        dest = bundle_dir / rel_path
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    # 8. Enrich lockfile copy and write to bundle
    enriched_yaml = enrich_lockfile_for_pack(lockfile, fmt, effective_target)
    (bundle_dir / "apm.lock.yaml").write_text(enriched_yaml, encoding="utf-8")

    result = PackResult(
        bundle_path=bundle_dir,
        files=unique_files,
        lockfile_enriched=True,
    )

    # 10. Archive if requested
    if archive:
        archive_path = output_dir / f"{pkg_name}-{pkg_version}.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(bundle_dir, arcname=bundle_dir.name)
        shutil.rmtree(bundle_dir)
        result.bundle_path = archive_path

    return result
