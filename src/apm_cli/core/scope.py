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
- **Copilot CLI** (partially supported): Copilot CLI reads user-level
  agents, skills, and instructions from ``~/.copilot/``.  Copilot CLI
  does not support prompts.
  Ref: https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli
- **VS Code** (partially supported): VS Code supports user-level MCP
  servers via user ``mcp.json``, but APM's MCP integrator currently
  only writes to workspace ``.vscode/mcp.json``.
  Ref: https://code.visualstudio.com/docs/copilot/customization/mcp-servers
- **Cursor** (not supported): user-level rules are managed via the
  Cursor Settings UI, not the filesystem.
  Ref: https://cursor.com/docs/rules
- **OpenCode** (not supported): no official documentation confirms whether
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
#   directory for custom agents, skills, and instructions.  Copilot CLI
#   does not support prompts.
#   Ref: https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli
#   Ref (skills): https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-skills
#   Ref (instructions): https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions
#
# * VS Code -- supports user-level MCP servers via user mcp.json.
#   APM's MCP integrator currently only writes to workspace
#   ``.vscode/mcp.json``.  User mcp.json support is planned.
#   Ref: https://code.visualstudio.com/docs/copilot/customization/mcp-servers
#
# * Cursor -- user-level rules are configured via the Cursor Settings
#   UI (Settings > Rules for AI).  The ``.cursor/rules/`` directory is
#   project-scoped only.
#   Ref: https://cursor.com/docs/rules
#
# * OpenCode -- no official documentation confirms user-level reading
#   from ``~/.opencode/``.  Marked as not supported.
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
        "description": "Partially supported -- agents, skills, instructions deploy to ~/.copilot/; Copilot CLI does not support prompts",
        "reference": "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli",
        "reference_links": {
            "agents": "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli",
            "skills": "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-skills",
            "instructions": "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions",
        },
    },
    "vscode": {
        "supported": "partial",
        "user_root": "~/.vscode",
        "primitives": ["mcp_servers"],
        "description": "Partially supported -- VS Code reads user-level MCP servers from user mcp.json, but APM currently only writes to workspace .vscode/mcp.json",
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
        "description": "Not supported -- no official documentation for user-level config",
        "reference": "",
    },
}


def get_unsupported_targets() -> List[str]:
    """Return target names that do not support user-scope deployment."""
    return [
        name for name, info in USER_SCOPE_TARGETS.items()
        if info["supported"] is False
    ]


def warn_unsupported_user_scope() -> str:
    """Return a warning message listing targets that lack user-scope support.

    Returns an empty string when all targets are fully supported.

    The message distinguishes three categories:

    * **fully supported** -- ``supported is True``
    * **partially supported** -- ``supported == "partial"``
    * **not supported** -- ``supported is False``

    When some targets have ``unsupported_primitives``, a second line is
    added listing those primitives per target.
    """
    fully_supported = [
        name for name, info in USER_SCOPE_TARGETS.items()
        if info["supported"] is True
    ]
    partially_supported = [
        name for name, info in USER_SCOPE_TARGETS.items()
        if info["supported"] == "partial"
    ]
    unsupported = get_unsupported_targets()

    if not unsupported and not partially_supported:
        return ""

    parts: List[str] = []

    supported_names = ", ".join(fully_supported)
    parts.append(
        f"[!] User-scope primitives are fully supported by {supported_names}."
    )

    if partially_supported:
        partial_names = ", ".join(partially_supported)
        parts[0] += f" Partially supported: {partial_names}."

    if unsupported:
        unsupported_names = ", ".join(unsupported)
        parts[0] += f" Targets without native user-level support: {unsupported_names}"

    # Collect per-target unsupported primitives
    unsupported_prims: List[str] = []
    for name, info in USER_SCOPE_TARGETS.items():
        prims = info.get("unsupported_primitives", [])
        if prims:
            unsupported_prims.append(f"{name} ({', '.join(prims)})")
    if unsupported_prims:
        parts.append(
            "[!] Some primitives are not supported: "
            + "; ".join(unsupported_prims)
        )

    return "\n".join(parts)
