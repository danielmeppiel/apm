"""Dependency reference models and Git reference utilities."""

from .lsp import LSPDependency
from .mcp import MCPDependency
from .reference import DependencyReference
from .replacement import (
    GitReplacementSource,
    LocalReplacementSource,
    ReplacementCollisionError,
    ReplacementConfigError,
    ReplacementCycleError,
    ReplacementIndex,
    ReplacementRule,
    ReplacementSelector,
    bind_graph_replacement,
    build_replacement_index,
    detect_local_replacement_cycle,
    parse_replace_block,
    project_effective_reference,
    replacement_rule_to_dict,
    replacement_rules_from_dicts,
    validate_no_replacement_collision,
)
from .types import (
    GitReferenceType,
    RemoteRef,
    ResolvedReference,
    VirtualPackageType,
    parse_git_reference,
)

__all__ = [
    "DependencyReference",
    "GitReferenceType",
    "GitReplacementSource",
    "LSPDependency",
    "LocalReplacementSource",
    "MCPDependency",
    "RemoteRef",
    "ReplacementCollisionError",
    "ReplacementConfigError",
    "ReplacementCycleError",
    "ReplacementIndex",
    "ReplacementRule",
    "ReplacementSelector",
    "ResolvedReference",
    "VirtualPackageType",
    "bind_graph_replacement",
    "build_replacement_index",
    "detect_local_replacement_cycle",
    "parse_git_reference",
    "parse_replace_block",
    "project_effective_reference",
    "replacement_rule_to_dict",
    "replacement_rules_from_dicts",
    "validate_no_replacement_collision",
]
