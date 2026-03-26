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
- **Copilot CLI** (supported): reads ``~/.copilot/agents/`` for
  user-level custom agents.
  Ref: https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli
- **VS Code** (partial): supports user-level MCP servers via
  VS Code user ``settings.json``; ``.github/`` is workspace-only.
  Ref: https://code.visualstudio.com/docs/configure/settings
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
# * Copilot CLI -- ``~/.copilot/agents/`` is the documented user-level
#   directory for custom agents.  Agents placed here are available
#   across all repositories.
#   Ref: https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli
#
# * VS Code -- supports user-level MCP server configuration through
#   VS Code user settings.json.  ``.github/`` is workspace-scoped only.
#   Ref: https://code.visualstudio.com/docs/configure/settings
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
        "supported": True,
        "user_root": "~/.copilot",
        "primitives": ["agents"],
        "description": "User-level custom agents for Copilot CLI",
        "reference": "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli",
    },
    "vscode": {
        "supported": True,
        "user_root": "~/.vscode",
        "primitives": ["mcp_servers"],
        "description": "MCP servers only (via VS Code user settings.json)",
        "reference": "https://code.visualstudio.com/docs/configure/settings",
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
    """Return target names that do not support user-scope deployment."""
    return [
        name for name, info in USER_SCOPE_TARGETS.items()
        if not info["supported"]
    ]


def warn_unsupported_user_scope() -> str:
    """Return a warning message listing targets that lack user-scope support.

    Returns an empty string when all targets are supported.
    """
    unsupported = get_unsupported_targets()
    if not unsupported:
        return ""
    names = ", ".join(unsupported)
    supported = [
        name for name, info in USER_SCOPE_TARGETS.items()
        if info["supported"]
    ]
    supported_names = ", ".join(supported)
    return (
        f"[!] User-scope primitives are supported by {supported_names}. "
        f"Targets without native user-level support: {names}"
    )
