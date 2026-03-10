"""APM uninstall command."""

from .cli import uninstall
from .engine import (
    _parse_dependency_entry,
    _validate_uninstall_packages,
    _dry_run_uninstall,
    _remove_packages_from_disk,
    _cleanup_transitive_orphans,
    _sync_integrations_after_uninstall,
    _cleanup_stale_mcp,
)

__all__ = [
    "uninstall",
    "_parse_dependency_entry",
    "_validate_uninstall_packages",
    "_dry_run_uninstall",
    "_remove_packages_from_disk",
    "_cleanup_transitive_orphans",
    "_sync_integrations_after_uninstall",
    "_cleanup_stale_mcp",
]
