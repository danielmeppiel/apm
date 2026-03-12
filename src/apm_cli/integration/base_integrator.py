"""Base integrator with shared collision detection and sync logic."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from dataclasses import dataclass, field

from apm_cli.compilation.link_resolver import UnifiedLinkResolver
from apm_cli.primitives.discovery import discover_primitives
from apm_cli.utils.console import _rich_warning


@dataclass
class IntegrationResult:
    """Result of a file-level integration operation."""

    files_integrated: int
    files_updated: int  # Kept for CLI compat, always 0 today
    files_skipped: int
    target_paths: List[Path]
    links_resolved: int = 0


class BaseIntegrator:
    """Shared infrastructure for file-level integrators.

    Subclasses only need to override the abstract hooks; the collision
    detection, sync removal, and link resolution logic is
    handled here.
    """

    def __init__(self):
        self.link_resolver: Optional[UnifiedLinkResolver] = None

    # ------------------------------------------------------------------
    # Common behaviour — subclasses inherit directly
    # ------------------------------------------------------------------

    def should_integrate(self, project_root: Path) -> bool:  # noqa: ARG002
        """Check if integration should be performed (always True)."""
        return True

    # ------------------------------------------------------------------
    # Collision detection
    # ------------------------------------------------------------------

    @staticmethod
    def check_collision(
        target_path: Path,
        rel_path: str,
        managed_files: Optional[Set[str]],
        force: bool,
        diagnostics=None,
    ) -> bool:
        """Return True if *target_path* is a user-authored collision.

        A collision exists when **all** of these are true:
        1. ``managed_files`` is not ``None`` (manifest mode)
        2. ``target_path`` already exists on disk
        3. ``rel_path`` is **not** in the managed set (→ user-authored)
        4. ``force`` is ``False``

        When *diagnostics* is provided the skip is recorded there;
        otherwise a warning is emitted via ``_rich_warning``.

        .. note:: Callers must pre-normalize *managed_files* with
           forward-slash separators (see ``normalize_managed_files``).
        """
        if managed_files is None:
            return False
        if not target_path.exists():
            return False
        # managed_files is pre-normalized at the call site — O(1) lookup
        if rel_path.replace("\\", "/") in managed_files:
            return False
        if force:
            return False

        if diagnostics is not None:
            diagnostics.skip(rel_path)
        else:
            _rich_warning(
                f"Skipping {rel_path} — local file exists (not managed by APM). "
                f"Use 'apm install --force' to overwrite."
            )
        return True

    @staticmethod
    def normalize_managed_files(managed_files: Optional[Set[str]]) -> Optional[Set[str]]:
        """Normalize path separators once for O(1) lookups."""
        if managed_files is None:
            return None
        return {p.replace("\\", "/") for p in managed_files}

    # Known integration prefixes that APM is allowed to deploy/remove under
    INTEGRATION_PREFIXES = (".github/", ".claude/")

    @staticmethod
    def validate_deploy_path(
        rel_path: str,
        project_root: Path,
        allowed_prefixes: tuple = (".github/", ".claude/"),
    ) -> bool:
        """Return True if *rel_path* is safe for APM to deploy or remove.

        Centralised security gate for all paths read from ``deployed_files``
        before any filesystem operation.

        Checks:
        1. No path-traversal components (``..``)
        2. Starts with an allowed integration prefix
        3. Resolves within *project_root*
        """
        if ".." in rel_path:
            return False
        if not rel_path.startswith(allowed_prefixes):
            return False
        target = project_root / rel_path
        if not str(target.resolve()).startswith(str(project_root.resolve())):
            return False
        return True

    @staticmethod
    def partition_managed_files(
        managed_files: Set[str],
    ) -> dict:
        """Partition *managed_files* by integration prefix in a single pass.

        Returns a dict with keys ``"prompts"``, ``"agents_github"``,
        ``"agents_claude"``, ``"commands"``, ``"skills"``, ``"hooks"``
        mapping to the subset of paths for each integration type.
        """
        buckets: dict = {
            "prompts": set(),
            "agents_github": set(),
            "agents_claude": set(),
            "commands": set(),
            "skills": set(),
            "hooks": set(),
            "instructions": set(),
        }
        for p in managed_files:
            if p.startswith(".github/prompts/"):
                buckets["prompts"].add(p)
            elif p.startswith(".github/agents/"):
                buckets["agents_github"].add(p)
            elif p.startswith(".claude/agents/"):
                buckets["agents_claude"].add(p)
            elif p.startswith(".claude/commands/"):
                buckets["commands"].add(p)
            elif p.startswith((".github/skills/", ".claude/skills/")):
                buckets["skills"].add(p)
            elif p.startswith((".github/hooks/", ".claude/hooks/")):
                buckets["hooks"].add(p)
            elif p.startswith(".github/instructions/"):
                buckets["instructions"].add(p)
        return buckets

    @staticmethod
    def cleanup_empty_parents(
        deleted_paths: List[Path],
        stop_at: Path,
    ) -> None:
        """Remove empty parent directories in a single bottom-up pass.

        Collects all parent directories of *deleted_paths*, sorts by
        depth descending, and removes each if empty — O(H+D) syscalls
        instead of the per-file O(H×D) approach.

        Args:
            deleted_paths: Paths that were deleted (files or dirs).
            stop_at: Do not remove this directory or any ancestor.
        """
        if not deleted_paths:
            return
        stop_resolved = stop_at.resolve()
        # Collect unique parents (skip stop_at itself)
        candidates: set = set()
        for p in deleted_paths:
            parent = p.parent
            while parent != stop_at and parent.resolve() != stop_resolved:
                candidates.add(parent)
                parent = parent.parent
        # Sort deepest-first for safe bottom-up removal
        for d in sorted(candidates, key=lambda p: len(p.parts), reverse=True):
            try:
                if d.exists() and not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Link resolution helpers
    # ------------------------------------------------------------------

    def init_link_resolver(self, package_info, project_root: Path) -> None:
        """Initialise and register the link resolver for a package."""
        self.link_resolver = UnifiedLinkResolver(project_root)
        try:
            primitives = discover_primitives(package_info.install_path)
            self.link_resolver.register_contexts(primitives)
        except Exception:
            self.link_resolver = None

    def resolve_links(self, content: str, source: Path, target: Path) -> tuple:
        """Resolve context links in *content*.

        Returns:
            ``(resolved_content, links_resolved_count)``
        """
        if not self.link_resolver:
            return content, 0

        resolved = self.link_resolver.resolve_links_for_installation(
            content=content,
            source_file=source,
            target_file=target,
        )
        if resolved == content:
            return content, 0

        link_pattern = re.compile(r'\]\(([^)]+)\)')
        original_links = set(link_pattern.findall(content))
        resolved_links = set(link_pattern.findall(resolved))
        return resolved, len(original_links - resolved_links)

    # ------------------------------------------------------------------
    # Sync (manifest-based file removal)
    # ------------------------------------------------------------------

    @staticmethod
    def sync_remove_files(
        project_root: Path,
        managed_files: Optional[Set[str]],
        prefix: str,
        legacy_glob_dir: Optional[Path] = None,
        legacy_glob_pattern: Optional[str] = None,
    ) -> Dict[str, int]:
        """Remove APM-managed files matching *prefix* from *managed_files*.

        Falls back to a legacy glob when *managed_files* is ``None``.

        Args:
            project_root: Workspace root.
            managed_files: Set of workspace-relative paths.
            prefix: Only process paths that start with this prefix
                    (e.g. ``".github/prompts/"``).
            legacy_glob_dir: Directory to glob inside for the legacy fallback.
            legacy_glob_pattern: Glob pattern for legacy fallback
                                 (e.g. ``"*-apm.prompt.md"``).

        Returns:
            ``{"files_removed": int, "errors": int}``
        """
        stats: Dict[str, int] = {"files_removed": 0, "errors": 0}

        if managed_files is not None:
            for rel_path in managed_files:
                # managed_files is pre-normalized — no .replace() needed
                if not rel_path.startswith(prefix):
                    continue
                if not BaseIntegrator.validate_deploy_path(rel_path, project_root):
                    continue
                target = project_root / rel_path
                if target.exists():
                    try:
                        target.unlink()
                        stats["files_removed"] += 1
                    except Exception:
                        stats["errors"] += 1
        elif legacy_glob_dir and legacy_glob_pattern and legacy_glob_dir.exists():
            for f in legacy_glob_dir.glob(legacy_glob_pattern):
                try:
                    f.unlink()
                    stats["files_removed"] += 1
                except Exception:
                    stats["errors"] += 1

        return stats

    # ------------------------------------------------------------------
    # File-discovery helpers (reusable globs)
    # ------------------------------------------------------------------

    @staticmethod
    def find_files_by_glob(
        package_path: Path,
        pattern: str,
        subdirs: Optional[List[str]] = None,
    ) -> List[Path]:
        """Search *package_path* (and optional subdirectories) for *pattern*.

        Args:
            package_path: Root of the installed package.
            pattern: Glob pattern (e.g. ``"*.prompt.md"``).
            subdirs: Extra subdirectory paths relative to *package_path*
                     to search (e.g. ``[".apm/prompts"]``).

        Returns:
            De-duplicated list of matching ``Path`` objects.
        """
        results: List[Path] = []
        seen: set = set()

        dirs = [package_path]
        if subdirs:
            dirs.extend(package_path / s for s in subdirs)

        for d in dirs:
            if not d.exists():
                continue
            for f in sorted(d.glob(pattern)):
                resolved = f.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    results.append(f)

        return results
