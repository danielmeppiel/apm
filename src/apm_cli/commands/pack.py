"""Click commands for ``apm pack`` and ``apm unpack``."""

import sys
from pathlib import Path

import click

from ..bundle.packer import pack_bundle
from ..bundle.unpacker import unpack_bundle
from ..core.command_logger import CommandLogger


@click.command(name="pack", help="Create a self-contained bundle from installed dependencies")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["apm", "plugin"]),
    default="apm",
    help="Bundle format.",
)
@click.option(
    "--target",
    "-t",
    type=click.Choice(["copilot", "vscode", "claude", "cursor", "opencode", "all"]),
    default=None,
    help="Filter files by target (default: auto-detect). 'copilot' is an alias for 'vscode'.",
)
@click.option("--archive", is_flag=True, default=False, help="Produce a .tar.gz archive.")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default="./build",
    help="Output directory (default: ./build).",
)
@click.option("--dry-run", is_flag=True, default=False, help="Show what would be packed without writing.")
@click.option("--force", is_flag=True, default=False, help="On collision, last writer wins.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed packing information")
@click.pass_context
def pack_cmd(ctx, fmt, target, archive, output, dry_run, force, verbose):
    """Create a self-contained APM bundle."""
    logger = CommandLogger("pack", verbose=verbose, dry_run=dry_run)
    try:
        result = pack_bundle(
            project_root=Path("."),
            output_dir=Path(output),
            fmt=fmt,
            target=target,
            archive=archive,
            dry_run=dry_run,
            force=force,
            logger=logger,
        )

        if dry_run:
            logger.dry_run_notice("No files written")
            if result.files:
                logger.progress(f"Would pack {len(result.files)} file(s):")
                for f in result.files:
                    logger.tree_item(f"  └─ {f}")
            else:
                logger.warning("No files to pack")
            return

        if not result.files:
            logger.warning("No deployed files found -- empty bundle created")
        else:
            logger.success(f"Packed {len(result.files)} file(s) -> {result.bundle_path}")
            for f in result.files:
                logger.verbose_detail(f"    └─ {f}")
            if fmt == "plugin":
                logger.progress(
                    "Plugin bundle ready -- contains plugin.json and "
                    "plugin-native directories (agents/, skills/, commands/, ...). "
                    "No APM-specific files included."
                )

    except (FileNotFoundError, ValueError) as exc:
        logger.error(str(exc))
        sys.exit(1)


@click.command(name="unpack", help="Extract an APM bundle into the current project")
@click.argument("bundle_path", type=click.Path(exists=True))
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=".",
    help="Target directory (default: current directory).",
)
@click.option("--skip-verify", is_flag=True, default=False, help="Skip bundle completeness check.")
@click.option("--dry-run", is_flag=True, default=False, help="Show what would be unpacked without writing.")
@click.option("--force", is_flag=True, default=False, help="Deploy despite critical hidden-character findings.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed unpacking information")
@click.pass_context
def unpack_cmd(ctx, bundle_path, output, skip_verify, dry_run, force, verbose):
    """Extract an APM bundle into the project."""
    logger = CommandLogger("unpack", verbose=verbose, dry_run=dry_run)
    try:
        logger.start(f"Unpacking {bundle_path} -> {output}")

        result = unpack_bundle(
            bundle_path=Path(bundle_path),
            output_dir=Path(output),
            skip_verify=skip_verify,
            dry_run=dry_run,
            force=force,
        )

        if dry_run:
            logger.dry_run_notice("No files written")
            if result.files:
                logger.progress(f"Would unpack {len(result.files)} file(s):")
                _log_unpack_file_list(result, logger)
            else:
                logger.warning("No files in bundle")
            return

        if not result.files:
            logger.warning("No files were unpacked")
        else:
            _log_unpack_file_list(result, logger)
            if result.skipped_count > 0:
                logger.warning(
                    f"  {result.skipped_count} file(s) skipped (missing from bundle)"
                )
            if result.security_critical > 0:
                logger.warning(
                    f"  Deployed with --force despite {result.security_critical} "
                    f"critical hidden-character finding(s)"
                )
            elif result.security_warnings > 0:
                logger.warning(
                    f"  {result.security_warnings} hidden-character warning(s) "
                    f"-- run 'apm audit' to inspect"
                )
            verified_msg = " (verified)" if result.verified else ""
            logger.success(f"Unpacked {len(result.files)} file(s){verified_msg}")

    except (FileNotFoundError, ValueError) as exc:
        logger.error(str(exc))
        sys.exit(1)


def _log_unpack_file_list(result, logger):
    """Log unpacked files grouped by dependency, using tree-style output."""
    if result.dependency_files:
        for dep_name, dep_files in result.dependency_files.items():
            logger.progress(f"  {dep_name}")
            for f in dep_files:
                logger.tree_item(f"    └─ {f}")
    else:
        for f in result.files:
            logger.tree_item(f"  └─ {f}")
