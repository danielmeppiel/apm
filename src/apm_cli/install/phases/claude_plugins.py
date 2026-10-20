"""Publish admitted native Claude plugins only after lock and security gates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apm_cli.claude_plugins.registrar import resync_claude_plugins
from apm_cli.deps.lockfile import LockFile, get_lockfile_path

if TYPE_CHECKING:
    from apm_cli.install.context import InstallContext


def run(ctx: InstallContext) -> None:
    """Use the same reconciliation owner as removal, with scanned new plans."""
    if ctx.apm_modules_dir is None:
        return
    resync_claude_plugins(
        modules_dir=ctx.apm_modules_dir,
        scope=ctx.scope,
        lockfile=LockFile.read(get_lockfile_path(ctx.apm_dir)),
        targets=ctx.targets,
        prepared=ctx.claude_native_plugins,
        allow_executables=ctx.exec_allow_map,
        logger=ctx.logger,
        dry_run=ctx.dry_run,
    )
