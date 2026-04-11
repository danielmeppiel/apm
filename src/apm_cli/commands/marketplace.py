"""APM marketplace command group.

Manages plugin marketplace discovery and governance. Follows the same
Click group pattern as ``mcp.py``.
"""

import builtins
import sys

import click

from ..core.command_logger import CommandLogger
from ._helpers import _get_console

# Restore builtins shadowed by subcommand names
list = builtins.list


@click.group(help="Manage plugin marketplaces for discovery and governance")
def marketplace():
    """Register, browse, and search plugin marketplaces."""
    pass


# ---------------------------------------------------------------------------
# marketplace add
# ---------------------------------------------------------------------------


@marketplace.command(help="Register a plugin marketplace")
@click.argument("repo", required=True)
@click.option("--name", "-n", default=None, help="Display name (defaults to repo name)")
@click.option("--branch", "-b", default="main", show_default=True, help="Branch to use")
@click.option("--host", default=None, help="Git host FQDN (default: github.com)")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def add(repo, name, branch, host, verbose):
    """Register a marketplace from OWNER/REPO or HOST/OWNER/REPO."""
    logger = CommandLogger("marketplace-add", verbose=verbose)
    try:
        from ..marketplace.client import _auto_detect_path, fetch_marketplace
        from ..marketplace.models import MarketplaceSource
        from ..marketplace.registry import add_marketplace

        # Parse OWNER/REPO or HOST/OWNER/REPO
        if "/" not in repo:
            logger.error(
                f"Invalid format: '{repo}'. Use 'OWNER/REPO' "
                f"(e.g., 'acme-org/plugin-marketplace')"
            )
            sys.exit(1)

        from ..utils.github_host import default_host, is_valid_fqdn

        parts = repo.split("/")
        if len(parts) == 3 and parts[0] and parts[1] and parts[2]:
            if not is_valid_fqdn(parts[0]):
                logger.error(
                    f"Invalid host: '{parts[0]}'. "
                    f"Use 'OWNER/REPO' or 'HOST/OWNER/REPO' format."
                )
                sys.exit(1)
            if host and host != parts[0]:
                logger.error(
                    f"Conflicting host: --host '{host}' vs '{parts[0]}' in argument."
                )
                sys.exit(1)
            host = parts[0]
            owner, repo_name = parts[1], parts[2]
        elif len(parts) == 2 and parts[0] and parts[1]:
            owner, repo_name = parts[0], parts[1]
        else:
            logger.error(f"Invalid format: '{repo}'. Expected 'OWNER/REPO'")
            sys.exit(1)

        if host is not None:
            normalized_host = host.strip().lower()
            if not is_valid_fqdn(normalized_host):
                logger.error(
                    f"Invalid host: '{host}'. Expected a valid host FQDN "
                    f"(for example, 'github.com')."
                )
                sys.exit(1)
            resolved_host = normalized_host
        else:
            resolved_host = default_host()
        display_name = name or repo_name

        # Validate name is identifier-compatible for NAME@MARKETPLACE syntax
        import re

        if not re.match(r"^[a-zA-Z0-9._-]+$", display_name):
            logger.error(
                f"Invalid marketplace name: '{display_name}'. "
                f"Names must only contain letters, digits, '.', '_', and '-' "
                f"(required for 'apm install plugin@marketplace' syntax)."
            )
            sys.exit(1)

        logger.start(f"Registering marketplace '{display_name}'...", symbol="gear")
        logger.verbose_detail(f"    Repository: {owner}/{repo_name}")
        logger.verbose_detail(f"    Branch: {branch}")
        if resolved_host != "github.com":
            logger.verbose_detail(f"    Host: {resolved_host}")

        # Auto-detect marketplace.json location
        probe_source = MarketplaceSource(
            name=display_name,
            owner=owner,
            repo=repo_name,
            branch=branch,
            host=resolved_host,
        )
        detected_path = _auto_detect_path(probe_source)

        if detected_path is None:
            logger.error(
                f"No marketplace.json found in '{owner}/{repo_name}'. "
                f"Checked: marketplace.json, .github/plugin/marketplace.json, "
                f".claude-plugin/marketplace.json"
            )
            sys.exit(1)

        logger.verbose_detail(f"    Detected path: {detected_path}")

        # Create source with detected path
        source = MarketplaceSource(
            name=display_name,
            owner=owner,
            repo=repo_name,
            branch=branch,
            host=resolved_host,
            path=detected_path,
        )

        # Fetch and validate
        manifest = fetch_marketplace(source, force_refresh=True)
        plugin_count = len(manifest.plugins)

        # Register
        add_marketplace(source)

        logger.success(
            f"Marketplace '{display_name}' registered ({plugin_count} plugins)",
            symbol="check",
        )
        if manifest.description:
            logger.verbose_detail(f"    {manifest.description}")

    except Exception as e:
        logger.error(f"Failed to register marketplace: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# marketplace list
# ---------------------------------------------------------------------------


@marketplace.command(name="list", help="List registered marketplaces")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def list_cmd(verbose):
    """Show all registered marketplaces."""
    logger = CommandLogger("marketplace-list", verbose=verbose)
    try:
        from ..marketplace.registry import get_registered_marketplaces

        sources = get_registered_marketplaces()

        if not sources:
            logger.progress(
                "No marketplaces registered. "
                "Use 'apm marketplace add OWNER/REPO' to register one.",
                symbol="info",
            )
            return

        console = _get_console()
        if not console:
            # Colorama fallback
            logger.progress(
                f"{len(sources)} marketplace(s) registered:", symbol="info"
            )
            for s in sources:
                click.echo(f"  {s.name}  ({s.owner}/{s.repo})")
            return

        from rich.table import Table

        table = Table(
            title="Registered Marketplaces",
            show_header=True,
            header_style="bold cyan",
            border_style="cyan",
        )
        table.add_column("Name", style="bold white", no_wrap=True)
        table.add_column("Repository", style="white")
        table.add_column("Branch", style="cyan")
        table.add_column("Path", style="dim")

        for s in sources:
            table.add_row(s.name, f"{s.owner}/{s.repo}", s.branch, s.path)

        console.print()
        console.print(table)
        console.print(
            f"\n[dim]Use 'apm marketplace browse <name>' to see plugins[/dim]"
        )

    except Exception as e:
        logger.error(f"Failed to list marketplaces: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# marketplace browse
# ---------------------------------------------------------------------------


@marketplace.command(help="Browse plugins in a marketplace")
@click.argument("name", required=True)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def browse(name, verbose):
    """Show available plugins in a marketplace."""
    logger = CommandLogger("marketplace-browse", verbose=verbose)
    try:
        from ..marketplace.client import fetch_marketplace
        from ..marketplace.registry import get_marketplace_by_name

        source = get_marketplace_by_name(name)
        logger.start(f"Fetching plugins from '{name}'...", symbol="search")

        manifest = fetch_marketplace(source, force_refresh=True)

        if not manifest.plugins:
            logger.warning(f"Marketplace '{name}' has no plugins")
            return

        console = _get_console()
        if not console:
            # Colorama fallback
            logger.success(
                f"{len(manifest.plugins)} plugin(s) in '{name}':", symbol="check"
            )
            for p in manifest.plugins:
                desc = f" -- {p.description}" if p.description else ""
                click.echo(f"  {p.name}{desc}")
            click.echo(
                f"\n  Install: apm install <plugin-name>@{name}"
            )
            return

        from rich.table import Table

        table = Table(
            title=f"Plugins in '{name}'",
            show_header=True,
            header_style="bold cyan",
            border_style="cyan",
        )
        table.add_column("Plugin", style="bold white", no_wrap=True)
        table.add_column("Description", style="white", ratio=1)
        table.add_column("Version", style="cyan", justify="center")
        table.add_column("Install", style="green")

        for p in manifest.plugins:
            desc = p.description or "--"
            ver = p.version or "--"
            table.add_row(p.name, desc, ver, f"{p.name}@{name}")

        console.print()
        console.print(table)
        console.print(
            f"\n[dim]Install a plugin: apm install <plugin-name>@{name}[/dim]"
        )

    except Exception as e:
        logger.error(f"Failed to browse marketplace: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# marketplace update
# ---------------------------------------------------------------------------


@marketplace.command(help="Refresh marketplace cache")
@click.argument("name", required=False, default=None)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def update(name, verbose):
    """Refresh cached marketplace data (one or all)."""
    logger = CommandLogger("marketplace-update", verbose=verbose)
    try:
        from ..marketplace.client import clear_marketplace_cache, fetch_marketplace
        from ..marketplace.registry import (
            get_marketplace_by_name,
            get_registered_marketplaces,
        )

        if name:
            source = get_marketplace_by_name(name)
            logger.start(f"Refreshing marketplace '{name}'...", symbol="gear")
            clear_marketplace_cache(name, host=source.host)
            manifest = fetch_marketplace(source, force_refresh=True)
            logger.success(
                f"Marketplace '{name}' updated ({len(manifest.plugins)} plugins)",
                symbol="check",
            )
        else:
            sources = get_registered_marketplaces()
            if not sources:
                logger.progress(
                    "No marketplaces registered.", symbol="info"
                )
                return
            logger.start(
                f"Refreshing {len(sources)} marketplace(s)...", symbol="gear"
            )
            for s in sources:
                try:
                    clear_marketplace_cache(s.name, host=s.host)
                    manifest = fetch_marketplace(s, force_refresh=True)
                    logger.tree_item(
                        f"  {s.name} ({len(manifest.plugins)} plugins)"
                    )
                except Exception as exc:
                    logger.warning(f"  {s.name}: {exc}")
            logger.success("Marketplace cache refreshed", symbol="check")

    except Exception as e:
        logger.error(f"Failed to update marketplace: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# marketplace remove
# ---------------------------------------------------------------------------


@marketplace.command(help="Remove a registered marketplace")
@click.argument("name", required=True)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def remove(name, yes, verbose):
    """Unregister a marketplace."""
    logger = CommandLogger("marketplace-remove", verbose=verbose)
    try:
        from ..marketplace.client import clear_marketplace_cache
        from ..marketplace.registry import get_marketplace_by_name, remove_marketplace

        # Verify it exists first
        source = get_marketplace_by_name(name)

        if not yes:
            confirmed = click.confirm(
                f"Remove marketplace '{source.name}' ({source.owner}/{source.repo})?",
                default=False,
            )
            if not confirmed:
                logger.progress("Cancelled", symbol="info")
                return

        remove_marketplace(name)
        clear_marketplace_cache(name, host=source.host)
        logger.success(f"Marketplace '{name}' removed", symbol="check")

    except Exception as e:
        logger.error(f"Failed to remove marketplace: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# marketplace validate
# ---------------------------------------------------------------------------


@marketplace.command(help="Validate a marketplace manifest")
@click.argument("name", required=True)
@click.option(
    "--check-refs", is_flag=True, help="Verify version refs are reachable (network)"
)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def validate(name, check_refs, verbose):
    """Validate the manifest of a registered marketplace."""
    logger = CommandLogger("marketplace-validate", verbose=verbose)
    try:
        from ..marketplace.client import fetch_marketplace
        from ..marketplace.registry import get_marketplace_by_name
        from ..marketplace.validator import validate_marketplace

        source = get_marketplace_by_name(name)
        logger.start(f"Validating marketplace '{name}'...", symbol="gear")

        manifest = fetch_marketplace(source, force_refresh=True)

        # Count version entries across all plugins
        total_versions = sum(len(p.versions) for p in manifest.plugins)
        logger.progress(
            f"Found {len(manifest.plugins)} plugins, "
            f"{total_versions} version entries",
            symbol="info",
        )

        # Verbose: per-plugin details
        if verbose:
            for p in manifest.plugins:
                source_type = "dict" if isinstance(p.source, dict) else "string"
                logger.verbose_detail(
                    f"    {p.name}: {len(p.versions)} versions, "
                    f"source type: {source_type}"
                )

        # Run validation
        results = validate_marketplace(manifest)

        # Check-refs placeholder
        if check_refs:
            logger.warning(
                "Ref checking not yet implemented -- skipping ref "
                "reachability checks",
                symbol="warning",
            )

        # Render results
        passed = 0
        warning_count = 0
        error_count = 0
        click.echo()
        click.echo("Validation Results:")
        for r in results:
            if r.passed and not r.warnings:
                logger.success(
                    f"  {r.check_name}: all plugins valid", symbol="check"
                )
                passed += 1
            elif r.warnings and not r.errors:
                for w in r.warnings:
                    logger.warning(f"  {r.check_name}: {w}", symbol="warning")
                warning_count += len(r.warnings)
            else:
                for e in r.errors:
                    logger.error(f"  {r.check_name}: {e}", symbol="error")
                for w in r.warnings:
                    logger.warning(f"  {r.check_name}: {w}", symbol="warning")
                error_count += len(r.errors)
                warning_count += len(r.warnings)

        click.echo()
        click.echo(
            f"Summary: {passed} passed, {warning_count} warnings, "
            f"{error_count} errors"
        )

        if error_count > 0:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Failed to validate marketplace: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Top-level search command (registered separately in cli.py)
# ---------------------------------------------------------------------------


@click.command(
    name="search",
    help="Search plugins in a marketplace (QUERY@MARKETPLACE)",
)
@click.argument("expression", required=True)
@click.option("--limit", default=20, show_default=True, help="Max results to show")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def search(expression, limit, verbose):
    """Search for plugins in a specific marketplace.

    Use QUERY@MARKETPLACE format, e.g.:  apm marketplace search security@skills
    """
    logger = CommandLogger("marketplace-search", verbose=verbose)
    try:
        from ..marketplace.client import search_marketplace
        from ..marketplace.registry import get_marketplace_by_name

        if "@" not in expression:
            logger.error(
                f"Invalid format: '{expression}'. "
                "Use QUERY@MARKETPLACE, e.g.: apm marketplace search security@skills"
            )
            sys.exit(1)

        query, marketplace_name = expression.rsplit("@", 1)
        if not query or not marketplace_name:
            logger.error(
                "Both QUERY and MARKETPLACE are required. "
                "Use QUERY@MARKETPLACE, e.g.: apm marketplace search security@skills"
            )
            sys.exit(1)

        try:
            source = get_marketplace_by_name(marketplace_name)
        except Exception:
            logger.error(
                f"Marketplace '{marketplace_name}' is not registered. "
                "Use 'apm marketplace list' to see registered marketplaces."
            )
            sys.exit(1)

        logger.start(
            f"Searching '{marketplace_name}' for '{query}'...", symbol="search"
        )
        results = search_marketplace(query, source)[:limit]

        if not results:
            logger.warning(
                f"No plugins found matching '{query}' in '{marketplace_name}'. "
                f"Try 'apm marketplace browse {marketplace_name}' to see all plugins."
            )
            return

        console = _get_console()
        if not console:
            # Colorama fallback
            logger.success(f"Found {len(results)} plugin(s):", symbol="check")
            for p in results:
                desc = f" -- {p.description}" if p.description else ""
                click.echo(f"  {p.name}@{marketplace_name}{desc}")
            click.echo(
                f"\n  Install: apm install <plugin-name>@{marketplace_name}"
            )
            return

        from rich.table import Table

        table = Table(
            title=f"Search Results: '{query}' in {marketplace_name}",
            show_header=True,
            header_style="bold cyan",
            border_style="cyan",
        )
        table.add_column("Plugin", style="bold white", no_wrap=True)
        table.add_column("Description", style="white", ratio=1)
        table.add_column("Install", style="green")

        for p in results:
            desc = p.description or "--"
            if len(desc) > 60:
                desc = desc[:57] + "..."
            table.add_row(p.name, desc, f"{p.name}@{marketplace_name}")

        console.print()
        console.print(table)
        console.print(
            f"\n[dim]Install: apm install <plugin-name>@{marketplace_name}[/dim]"
        )

    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"Search failed: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# marketplace publish -- helpers
# ---------------------------------------------------------------------------


def _get_git_head_sha():
    """Get the current git HEAD commit SHA.

    Returns:
        The full SHA string, or ``None`` if git is not available or the
        working directory is not a git repository.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _find_local_marketplace_repo(source):
    """Try to find a local clone of the marketplace repo.

    Checks whether the current working directory (or its git root) has a
    remote matching *source*'s ``owner/repo``.

    Returns:
        Repository root path as a string, or ``None``.
    """
    import subprocess

    try:
        # Get git repo root first
        root_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
        )
        if root_result.returncode != 0:
            return None

        repo_root = root_result.stdout.strip()

        # Check all remotes for a match
        result = subprocess.run(
            ["git", "remote", "-v"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            cwd=repo_root,
        )
        if result.returncode != 0:
            return None

        expected = f"{source.owner}/{source.repo}"
        for line in result.stdout.splitlines():
            if expected in line:
                return repo_root
    except Exception:
        pass
    return None


def _clone_marketplace_repo(source):
    """Clone the marketplace repo to a temporary directory.

    Returns:
        Path to the cloned directory.

    Raises:
        RuntimeError: If cloning fails.
    """
    import subprocess
    import tempfile

    clone_url = f"https://{source.host}/{source.owner}/{source.repo}.git"
    tmp_dir = tempfile.mkdtemp(prefix="apm-marketplace-")
    try:
        subprocess.run(
            [
                "git",
                "clone",
                "--depth=1",
                "--branch",
                source.branch,
                clone_url,
                tmp_dir,
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Failed to clone marketplace repo "
            f"'{source.owner}/{source.repo}': {exc.stderr.strip()}"
        ) from exc
    return tmp_dir


def _update_marketplace_file(file_path, plugin_name, version_str, ref, force):
    """Read marketplace.json, add a version entry, and write back.

    Operates on the raw JSON dict so no fields are lost during
    round-tripping through the frozen dataclass layer.

    Args:
        file_path: Absolute path to marketplace.json.
        plugin_name: Plugin to update (case-insensitive match).
        version_str: Semver version string to publish.
        ref: Git ref for the version entry.
        force: When ``True``, overwrite an existing entry with the same
            version string.

    Returns:
        The *file_path* that was written.

    Raises:
        FileNotFoundError: If *file_path* does not exist.
        ValueError: If the plugin is not found in the file.
    """
    import json

    with open(file_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    plugins = data.get("plugins", [])
    target = None
    for entry in plugins:
        if entry.get("name", "").lower() == plugin_name.lower():
            target = entry
            break

    if target is None:
        raise ValueError(
            f"Plugin '{plugin_name}' not found in {file_path}"
        )

    versions = target.get("versions", [])

    # Remove existing version entry when --force is active
    if force:
        versions = [v for v in versions if v.get("version") != version_str]

    versions.append({"version": version_str, "ref": ref})
    target["versions"] = versions

    with open(file_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")

    return file_path


# ---------------------------------------------------------------------------
# marketplace publish
# ---------------------------------------------------------------------------


@marketplace.command(help="Publish a version entry to a marketplace")
@click.option(
    "--marketplace",
    "-m",
    "marketplace_name",
    default=None,
    help="Target marketplace name",
)
@click.option(
    "--version",
    "version_str",
    default=None,
    help="Version to publish (semver X.Y.Z, default: from apm.yml)",
)
@click.option(
    "--ref",
    default=None,
    help="Git ref / commit SHA (default: current HEAD)",
)
@click.option(
    "--plugin",
    "plugin_name",
    default=None,
    help="Plugin name in the marketplace (default: name from apm.yml)",
)
@click.option("--dry-run", is_flag=True, help="Show what would be published without making changes")
@click.option("--force", is_flag=True, help="Overwrite existing version entry with a different ref")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def publish(marketplace_name, version_str, ref, plugin_name, dry_run, force, verbose):
    """Publish a new version entry for a plugin in a marketplace."""
    logger = CommandLogger("marketplace-publish", verbose=verbose, dry_run=dry_run)
    try:
        import os
        from pathlib import Path

        from ..marketplace.client import fetch_marketplace
        from ..marketplace.registry import (
            get_marketplace_by_name,
            get_registered_marketplaces,
        )
        from ..marketplace.version_resolver import _parse_semver
        from ..models.apm_package import APMPackage

        # -- 1. Resolve defaults from apm.yml ---------------------------------
        if not plugin_name or not version_str:
            apm_yml_path = Path("apm.yml")
            if not apm_yml_path.exists():
                missing = []
                if not plugin_name:
                    missing.append("--plugin")
                if not version_str:
                    missing.append("--version")
                logger.error(
                    f"No apm.yml found. Specify {' and '.join(missing)} explicitly."
                )
                sys.exit(1)

            package = APMPackage.from_apm_yml(apm_yml_path)
            if not plugin_name:
                plugin_name = package.name
            if not version_str:
                version_str = package.version

        # -- 2. Validate version -----------------------------------------------
        try:
            _parse_semver(version_str)
        except ValueError as exc:
            logger.error(str(exc))
            sys.exit(1)

        # -- 3. Resolve git ref ------------------------------------------------
        if not ref:
            ref = _get_git_head_sha()
            if not ref:
                logger.error(
                    "Could not determine git HEAD SHA. "
                    "Use --ref to specify a commit."
                )
                sys.exit(1)

        # -- 4. Resolve marketplace --------------------------------------------
        if not marketplace_name:
            sources = get_registered_marketplaces()
            if len(sources) == 0:
                logger.error(
                    "No marketplaces registered. "
                    "Use 'apm marketplace add OWNER/REPO' first."
                )
                sys.exit(1)
            elif len(sources) == 1:
                marketplace_name = sources[0].name
                logger.verbose_detail(
                    f"    Auto-selected marketplace: {marketplace_name}"
                )
            else:
                names = ", ".join(s.name for s in sources)
                logger.error(
                    f"Multiple marketplaces registered ({names}). "
                    f"Use --marketplace to specify which one."
                )
                sys.exit(1)

        source = get_marketplace_by_name(marketplace_name)

        # -- 5. Start output ---------------------------------------------------
        logger.start(
            f"Publishing {plugin_name} v{version_str} "
            f"to marketplace '{marketplace_name}'...",
            symbol="gear",
        )
        logger.progress(f"Ref: {ref}", symbol="info")

        # -- 6. Fetch manifest and validate ------------------------------------
        manifest = fetch_marketplace(source, force_refresh=True)

        plugin = manifest.find_plugin(plugin_name)
        if plugin is None:
            logger.error(
                f"Plugin '{plugin_name}' not found in marketplace "
                f"'{marketplace_name}'. "
                f"Run 'apm marketplace browse {marketplace_name}' "
                f"to see available plugins."
            )
            sys.exit(1)

        # -- 7. Check for existing version -------------------------------------
        for existing in plugin.versions:
            if existing.version == version_str:
                if existing.ref == ref:
                    logger.progress(
                        f"Version {version_str} already published "
                        f"with same ref. Skipping.",
                        symbol="info",
                    )
                    return
                if not force:
                    logger.error(
                        f"Version {version_str} already exists with a "
                        f"different ref ({existing.ref}). "
                        f"Use --force to overwrite."
                    )
                    sys.exit(1)

        # -- 8. Dry-run gate ---------------------------------------------------
        if dry_run:
            logger.dry_run_notice(
                f"Would publish {plugin_name} v{version_str} "
                f"(ref: {ref}) to '{marketplace_name}'"
            )
            return

        # -- 9. Locate or clone marketplace repo and update --------------------
        local_repo = _find_local_marketplace_repo(source)
        cloned = False
        if local_repo is None:
            logger.verbose_detail(
                "    Marketplace repo not found locally, cloning..."
            )
            local_repo = _clone_marketplace_repo(source)
            cloned = True

        marketplace_file = os.path.join(local_repo, source.path)

        if not os.path.isfile(marketplace_file):
            logger.error(
                f"marketplace.json not found at expected path: "
                f"{marketplace_file}"
            )
            sys.exit(1)

        _update_marketplace_file(
            marketplace_file, plugin_name, version_str, ref, force
        )

        logger.success(
            "Version entry added to marketplace.json", symbol="check"
        )
        logger.progress(
            f"Marketplace file: {marketplace_file}", symbol="info"
        )
        logger.progress(
            "Don't forget to commit and push the marketplace repo!",
            symbol="info",
        )
        if cloned:
            logger.progress(
                f"Cloned repo location: {local_repo}", symbol="info"
            )

    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"Failed to publish: {e}")
        sys.exit(1)
