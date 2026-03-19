"""APM dependency management commands."""

from .cli import deps, list_packages, tree, clean, update, info
from ._utils import (
    _is_nested_under_package,
    _count_primitives,
    _count_package_files,
    _count_workflows,
    _get_detailed_context_counts,
    _get_package_display_info,
    _get_detailed_package_info,
    _update_single_package,
    _update_all_packages,
)

__all__ = [
    # CLI commands
    "deps",
    "list_packages",
    "tree",
    "clean",
    "update",
    "info",
    # Utility functions (used by tests)
    "_is_nested_under_package",
    "_count_primitives",
    "_count_package_files",
    "_count_workflows",
    "_get_detailed_context_counts",
    "_get_package_display_info",
    "_get_detailed_package_info",
    "_update_single_package",
    "_update_all_packages",
]
