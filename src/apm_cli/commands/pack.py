"""Click commands for ``apm pack`` and ``apm unpack``."""

import sys
from pathlib import Path

import click

from ..bundle.packer import pack_bundle
from ..bundle.unpacker import unpack_bundle
from ..utils.console import _rich_success, _rich_error, _rich_info, _rich_warning


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
    type=click.Choice(["vscode", "claude", "all"]),
    default=None,
    help="Filter files by target (default: auto-detect).",
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
@click.pass_context
def pack_cmd(ctx, fmt, target, archive, output, dry_run):
    """Create a self-contained APM bundle."""
    try:
        result = pack_bundle(
            project_root=Path("."),
            output_dir=Path(output),
            fmt=fmt,
            target=target,
            archive=archive,
            dry_run=dry_run,
        )

        if dry_run:
            _rich_info("Dry run — no files written")
            if result.files:
                _rich_info(f"Would pack {len(result.files)} file(s):")
                for f in result.files:
                    click.echo(f"  {f}")
            else:
                _rich_warning("No files to pack")
            return

        if not result.files:
            _rich_warning("No deployed files found — empty bundle created")
        else:
            _rich_success(f"Packed {len(result.files)} file(s) → {result.bundle_path}")

    except (FileNotFoundError, ValueError) as exc:
        _rich_error(str(exc))
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
@click.pass_context
def unpack_cmd(ctx, bundle_path, output, skip_verify, dry_run):
    """Extract an APM bundle into the project."""
    try:
        result = unpack_bundle(
            bundle_path=Path(bundle_path),
            output_dir=Path(output),
            skip_verify=skip_verify,
            dry_run=dry_run,
        )

        if dry_run:
            _rich_info("Dry run — no files written")
            if result.files:
                _rich_info(f"Would unpack {len(result.files)} file(s):")
                for f in result.files:
                    click.echo(f"  {f}")
            else:
                _rich_warning("No files in bundle")
            return

        if not result.files:
            _rich_warning("No files were unpacked")
        else:
            verified_msg = " (verified)" if result.verified else ""
            _rich_success(f"Unpacked {len(result.files)} file(s){verified_msg}")

    except (FileNotFoundError, ValueError) as exc:
        _rich_error(str(exc))
        sys.exit(1)
