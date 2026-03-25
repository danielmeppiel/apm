"""Installation scope resolution for APM packages.

Defines where packages are deployed based on scope:

- **project** (default): Deploy to the current working directory.
  Manifest, lockfile, and modules live at the project root.
- **user**: Deploy to user-level directories (``~/.github/``,
  ``~/.claude/``, etc.).  Manifest, lockfile, and modules live
  under ``~/.apm/``.

User-scope mirrors how each AI tool reads user-level configuration:

- GitHub Copilot: ``~/.github/`` (user-level instructions)
- Claude Code: ``~/.claude/`` (user-level commands, CLAUDE.md)
- Cursor: ``~/.cursor/`` (user-level rules, agents)
- OpenCode: ``~/.opencode/`` (user-level agents, commands)
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Dict


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
    paths like ``~/.github/prompts/`` or ``~/.claude/commands/``.
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
# Per-target user-level support information
# ---------------------------------------------------------------------------

USER_SCOPE_TARGETS: Dict[str, Dict[str, object]] = {
    "copilot": {
        "supported": True,
        "user_root": "~/.github",
        "description": "User-level Copilot instructions and prompts",
    },
    "claude": {
        "supported": True,
        "user_root": "~/.claude",
        "description": "User-level Claude commands and settings",
    },
    "cursor": {
        "supported": True,
        "user_root": "~/.cursor",
        "description": "User-level Cursor rules and agents",
    },
    "opencode": {
        "supported": True,
        "user_root": "~/.opencode",
        "description": "User-level OpenCode agents and commands",
    },
}
