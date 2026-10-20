"""Publish admitted native Claude plugins only after lock and security gates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apm_cli.claude_plugins.registrar import resync_claude_plugins

if TYPE_CHECKING:
    from apm_cli.install.context import InstallContext


def run(ctx: InstallContext) -> None:
    """Use the same reconciliation owner as removal, with scanned new plans."""
    if ctx.apm_modules_dir is None:
        return
    resync_claude_plugins(
        modules_dir=ctx.apm_modules_dir,
        scope=ctx.scope,
        lockfile=ctx.lockfile,
        targets=ctx.targets,
        prepared=ctx.claude_native_plugins,
        allow_executables=getattr(ctx.apm_package, "allow_executables", None),
        logger=ctx.logger,
        dry_run=ctx.dry_run,
    )
