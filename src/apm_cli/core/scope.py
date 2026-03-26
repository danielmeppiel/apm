"""Installation scope resolution for APM packages.

Defines where packages are deployed based on scope:

- **project** (default): Deploy to the current working directory.
  Manifest, lockfile, and modules live at the project root.
- **user**: Deploy to user-level directories (``~/.claude/``, etc.).
  Manifest, lockfile, and modules live under ``~/.apm/``.

User-scope support varies by target:

- **Claude Code** (fully supported): reads ``~/.claude/`` for global
  commands, agents, skills, and ``CLAUDE.md``.
  Ref: https://docs.anthropic.com/en/docs/claude-code/settings
- **Copilot CLI** (partially supported): reads ``~/.copilot/`` for
  user-level agents, skills, and instructions.  Prompts are NOT
  supported at user scope.
  Ref (agents): https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli
  Ref (skills): https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-skills
  Ref (instructions): https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions
- **VS Code** (partial): supports user-level MCP servers via
  user ``mcp.json``; ``.github/`` is workspace-only.
  Ref: https://code.visualstudio.com/docs/copilot/customization/mcp-servers
- **Cursor** (not supported): user-level rules are managed via the
  Cursor Settings UI, not the filesystem.
  Ref: https://cursor.com/docs/rules
- **OpenCode** (unverified): no official documentation confirms whether
  ``~/.opencode/`` is read at user level.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Dict, List


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_APM_DIR = ".apm"
"""Directory under ``$HOME`` for user-scope metadata."""


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


class InstallScope(Enum):
    """Controls where packages are deployed."""

    PROJECT = "project"
    USER = "user"


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def get_deploy_root(scope: InstallScope) -> Path:
    """Return the root used to construct deployment paths.

    For project scope this is ``Path.cwd()``.
    For user scope this is ``Path.home()`` so that integrators produce
    paths like ``~/.claude/commands/``.
    """
    if scope is InstallScope.USER:
        return Path.home()
    return Path.cwd()


def get_apm_dir(scope: InstallScope) -> Path:
    """Return the directory that holds APM metadata (manifest, lockfile, modules).

    * Project scope: ``<cwd>/``
    * User scope: ``~/.apm/``
    """
    if scope is InstallScope.USER:
        return Path.home() / USER_APM_DIR
    return Path.cwd()


def get_modules_dir(scope: InstallScope) -> Path:
    """Return the ``apm_modules`` directory for *scope*."""
    from ..constants import APM_MODULES_DIR

    return get_apm_dir(scope) / APM_MODULES_DIR


def get_manifest_path(scope: InstallScope) -> Path:
    """Return the ``apm.yml`` path for *scope*."""
    from ..constants import APM_YML_FILENAME

    return get_apm_dir(scope) / APM_YML_FILENAME


def get_lockfile_dir(scope: InstallScope) -> Path:
    """Return the directory containing the lockfile for *scope*."""
    return get_apm_dir(scope)


def ensure_user_dirs() -> Path:
    """Create ``~/.apm/`` and ``~/.apm/apm_modules/`` if they do not exist.

    Returns the user APM root (``~/.apm/``).
    """
    from ..constants import APM_MODULES_DIR

    user_root = Path.home() / USER_APM_DIR
    user_root.mkdir(parents=True, exist_ok=True)
    (user_root / APM_MODULES_DIR).mkdir(exist_ok=True)
    return user_root


# ---------------------------------------------------------------------------
# Per-target user-scope support
#
# Tracks which AI tools natively read from a user-level directory
# (``~/.<tool>/``) so APM can warn when deploying primitives to a
# target that does not support user-scope.
#
# Evidence / references:
#
# * Claude Code -- ``~/.claude/`` is the documented user-level config
#   directory.  Claude reads CLAUDE.md, commands/, agents/, skills/
#   from it and merges them with project-level ``.claude/``.
#   Ref: https://docs.anthropic.com/en/docs/claude-code/settings
#
# * Copilot CLI -- ``~/.copilot/`` is the documented user-level
#   directory for custom agents, skills, and instructions.  These are
#   available across all repositories.  Prompts are NOT supported at
#   user scope.
#   Ref (agents): https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli
#   Ref (skills): https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-skills
#   Ref (instructions): https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions
#
# * VS Code -- supports user-level MCP server configuration through
#   user mcp.json.  ``.github/`` is workspace-scoped only.
#   Ref: https://code.visualstudio.com/docs/copilot/customization/mcp-servers
#
# * Cursor -- user-level rules are configured via the Cursor Settings
#   UI (Settings > Rules for AI).  The ``.cursor/rules/`` directory is
#   project-scoped only.
#   Ref: https://cursor.com/docs/rules
#
# * OpenCode -- no official documentation confirms user-level reading
#   from ``~/.opencode/``.  Marked as unverified.
# ---------------------------------------------------------------------------

USER_SCOPE_TARGETS: Dict[str, Dict[str, object]] = {
    "claude": {
        "supported": True,
        "user_root": "~/.claude",
        "primitives": ["agents", "commands", "skills", "hooks"],
        "description": "User-level Claude commands, agents, and settings",
        "reference": "https://docs.anthropic.com/en/docs/claude-code/settings",
    },
    "copilot_cli": {
        "supported": "partial",
        "user_root": "~/.copilot",
        "primitives": ["agents", "skills", "instructions"],
        "unsupported_primitives": ["prompts"],
        "description": "User-level agents, skills, and instructions for Copilot CLI (prompts not supported)",
        "reference": "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli",
    },
    "vscode": {
        "supported": "partial",
        "user_root": "~/.vscode",
        "primitives": ["mcp_servers"],
        "description": "MCP servers only (via user mcp.json)",
        "reference": "https://code.visualstudio.com/docs/copilot/customization/mcp-servers",
    },
    "cursor": {
        "supported": False,
        "user_root": "~/.cursor",
        "primitives": [],
        "description": "Not supported -- user rules are managed via Cursor Settings UI",
        "reference": "https://cursor.com/docs/rules",
    },
    "opencode": {
        "supported": False,
        "user_root": "~/.opencode",
        "primitives": [],
        "description": "Unverified -- no official documentation for user-level config",
        "reference": "",
    },
}


def get_unsupported_targets() -> List[str]:
    """Return target names that do not support user-scope deployment.

    Targets with ``"partial"`` support are *not* included here -- they
    do work at user scope, just not for every primitive.
    """
    return [
        name for name, info in USER_SCOPE_TARGETS.items()
        if info["supported"] is False
    ]


def warn_unsupported_user_scope() -> str:
    """Return a warning message listing targets that lack user-scope support.

    Also warns about partially-supported targets and primitives that are
    not supported at user scope for those targets (e.g. prompts for
    Copilot CLI).

    Returns an empty string when all targets are fully supported.
    """
    unsupported = get_unsupported_targets()
    fully_supported = [
        name for name, info in USER_SCOPE_TARGETS.items()
        if info["supported"] is True
    ]
    partially_supported = [
        name for name, info in USER_SCOPE_TARGETS.items()
        if info["supported"] == "partial"
    ]

    # Collect per-target unsupported primitives
    partial_warnings: list[str] = []
    for name, info in USER_SCOPE_TARGETS.items():
        unsup_prims = info.get("unsupported_primitives", [])
        if unsup_prims and info["supported"]:
            prims = ", ".join(unsup_prims)
            partial_warnings.append(f"{name} ({prims})")

    parts: list[str] = []
    if unsupported or partially_supported:
        supported_names = ", ".join(fully_supported)
        line = f"[!] User-scope primitives are fully supported by {supported_names}."
        if partially_supported:
            partial_names = ", ".join(partially_supported)
            line += f" Partially supported: {partial_names}."
        if unsupported:
            names = ", ".join(unsupported)
            line += f" Targets without native user-level support: {names}"
        parts.append(line)
    if partial_warnings:
        parts.append(
            "[!] Some primitives are not supported at user scope: "
            + "; ".join(partial_warnings)
        )
    return "\n".join(parts)
