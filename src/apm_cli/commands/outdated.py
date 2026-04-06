"""Check for outdated locked dependencies.

Compares locked dependency commit SHAs against remote tip SHAs.
For tag-pinned deps, also shows the latest available semver tag.
"""

import re
import sys

import click


TAG_RE = re.compile(r"^v?\d+\.\d+\.\d+")


def _is_tag_ref(ref: str) -> bool:
    """Return True when *ref* looks like a semver tag (v1.2.3 or 1.2.3)."""
    return bool(TAG_RE.match(ref)) if ref else False


def _strip_v(ref: str) -> str:
    """Strip leading 'v' prefix from a version string."""
    return ref[1:] if ref and ref.startswith("v") else (ref or "")


def _find_remote_tip(ref_name, remote_refs):
    """Find the tip SHA for a branch ref from remote refs.

    If *ref_name* is empty/None, looks for HEAD or falls back to
    common default branch names (main, master).
    Returns the commit SHA string or None if not found.
    """
    from ..models.dependency.types import GitReferenceType

    if not remote_refs:
        return None

    branch_refs = {r.name: r.commit_sha for r in remote_refs
                   if r.ref_type == GitReferenceType.BRANCH}

    if ref_name:
        return branch_refs.get(ref_name)

    # No ref specified -- find the default branch
    # HEAD is included by git ls-remote; fall back to main/master
    head_refs = [r for r in remote_refs if r.name == "HEAD"]
    if head_refs:
        return head_refs[0].commit_sha

    for default in ("main", "master"):
        if default in branch_refs:
            return branch_refs[default]

    # Last resort: first branch in list
    if branch_refs:
        return next(iter(branch_refs.values()))

    return None


@click.command(name="outdated")
@click.option("--global", "-g", "global_", is_flag=True, default=False,
              help="Check user-scope dependencies (~/.apm/)")
@click.option("--verbose", "-v", is_flag=True, default=False,
              help="Show additional info (e.g., available tags for outdated deps)")
def outdated(global_, verbose):
    """Show outdated locked dependencies.

    Reads the lockfile and compares each locked dependency's resolved ref
    against the latest available remote tag.

    \b
    Examples:
        apm outdated             # Check project deps
        apm outdated --global    # Check user-scope deps
        apm outdated --verbose   # Show available tags
    """
    from ..core.command_logger import CommandLogger
    from ..core.scope import InstallScope, get_apm_dir
    from ..deps.lockfile import LockFile, get_lockfile_path, migrate_lockfile_if_needed
    from ..models.dependency.reference import DependencyReference
    from ..models.dependency.types import GitReferenceType
    from ..utils.version_checker import is_newer_version

    logger = CommandLogger("outdated", verbose=verbose)

    # Resolve scope and lockfile path
    scope = InstallScope.USER if global_ else InstallScope.PROJECT
    project_root = get_apm_dir(scope)

    migrate_lockfile_if_needed(project_root)
    lockfile_path = get_lockfile_path(project_root)
    lockfile = LockFile.read(lockfile_path)

    if lockfile is None:
        scope_hint = "~/.apm/" if global_ else "current directory"
        logger.error(f"No lockfile found in {scope_hint}")
        sys.exit(1)

    if not lockfile.dependencies:
        logger.success("No locked dependencies to check")
        return

    # Lazy-init downloader only when we have deps to check
    from ..core.auth import AuthResolver
    from ..deps.github_downloader import GitHubPackageDownloader

    auth_resolver = AuthResolver()
    downloader = GitHubPackageDownloader(auth_resolver=auth_resolver)

    # Collect results: list of (package, current, latest, status, extra_tags)
    rows = []

    for key, dep in lockfile.dependencies.items():
        # Skip local dependencies
        if dep.source == "local":
            logger.verbose_detail(f"Skipping local dep: {key}")
            continue

        # Skip Artifactory dependencies
        if dep.registry_prefix:
            logger.verbose_detail(f"Skipping Artifactory dep: {key}")
            continue

        current_ref = dep.resolved_ref or ""
        locked_sha = dep.resolved_commit or ""
        package_name = dep.get_unique_key()

        # Build a DependencyReference to query remote refs
        try:
            dep_ref = DependencyReference(
                repo_url=dep.repo_url,
                host=dep.host,
            )
        except Exception as exc:
            logger.verbose_detail(f"Failed to build ref for {key}: {exc}")
            rows.append((package_name, current_ref or "(none)", "-", "unknown", []))
            continue

        # Fetch remote refs
        try:
            remote_refs = downloader.list_remote_refs(dep_ref)
        except Exception as exc:
            logger.verbose_detail(f"Failed to fetch refs for {key}: {exc}")
            rows.append((package_name, current_ref or "(none)", "-", "unknown", []))
            continue

        is_tag = _is_tag_ref(current_ref)

        if is_tag:
            # Tag-pinned: compare semver AND verify SHA matches
            tag_refs = [r for r in remote_refs if r.ref_type == GitReferenceType.TAG]
            if not tag_refs:
                rows.append((package_name, current_ref, "-", "unknown", []))
                continue

            latest_tag = tag_refs[0].name
            current_ver = _strip_v(current_ref)
            latest_ver = _strip_v(latest_tag)

            if is_newer_version(current_ver, latest_ver):
                extra = [r.name for r in tag_refs[:10]] if verbose else []
                rows.append((package_name, current_ref, latest_tag, "outdated", extra))
            else:
                rows.append((package_name, current_ref, latest_tag, "up-to-date", []))
        else:
            # Branch-pinned or no ref: compare locked SHA against remote tip
            remote_tip_sha = _find_remote_tip(current_ref, remote_refs)

            if not remote_tip_sha:
                rows.append((package_name, current_ref or "(none)", "-", "unknown", []))
                continue

            display_ref = current_ref or "(default)"
            if locked_sha and locked_sha != remote_tip_sha:
                latest_display = remote_tip_sha[:8]
                rows.append((package_name, display_ref, latest_display, "outdated", []))
            else:
                rows.append((package_name, display_ref, remote_tip_sha[:8], "up-to-date", []))

    if not rows:
        logger.success("No remote dependencies to check")
        return

    # Check if everything is up-to-date
    has_outdated = any(status == "outdated" for _, _, _, status, _ in rows)
    has_unknown = any(status == "unknown" for _, _, _, status, _ in rows)

    if not has_outdated and not has_unknown:
        logger.success("All dependencies are up-to-date")
        return

    # Render the table
    try:
        from rich.table import Table

        from ._helpers import _get_console

        console = _get_console()
        if console is None:
            raise ImportError("Rich console not available")

        table = Table(
            title="Dependency Status",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Package", style="white", min_width=20)
        table.add_column("Current", style="white", min_width=10)
        table.add_column("Latest", style="white", min_width=10)
        table.add_column("Status", min_width=12)

        status_styles = {
            "up-to-date": "green",
            "outdated": "yellow",
            "unknown": "dim",
        }

        for package, current, latest, status, extra_tags in rows:
            style = status_styles.get(status, "white")
            table.add_row(package, current, latest, f"[{style}]{status}[/{style}]")

            if verbose and extra_tags:
                tags_str = ", ".join(extra_tags)
                table.add_row("", "", f"[dim]tags: {tags_str}[/dim]", "")

        console.print(table)

    except (ImportError, Exception):
        # Fallback: plain text output
        click.echo("Package                 Current      Latest       Status")
        click.echo("-" * 65)
        for package, current, latest, status, extra_tags in rows:
            click.echo(f"{package:<24}{current:<13}{latest:<13}{status}")
            if verbose and extra_tags:
                click.echo(f"{'':24}tags: {', '.join(extra_tags)}")

    # Summary
    outdated_count = sum(1 for _, _, _, s, _ in rows if s == "outdated")
    if outdated_count:
        logger.warning(f"{outdated_count} outdated "
                       f"{'dependency' if outdated_count == 1 else 'dependencies'} found")
    elif has_unknown:
        logger.progress("Some dependencies could not be checked (branch/commit refs)")
