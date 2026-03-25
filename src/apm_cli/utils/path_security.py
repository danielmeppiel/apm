"""Centralised path-security helpers for APM CLI.

Every filesystem operation whose target is derived from user-controlled
input (dependency strings, ``virtual_path``, ``apm.yml`` fields) **must**
pass through one of these guards before touching the disk.

Design
------
* ``ensure_path_within`` is the single predicate -- resolves both paths and
  asserts containment via ``Path.is_relative_to``.
* ``safe_rmtree`` wraps ``robust_rmtree`` with an ``ensure_path_within``
  check so callers get a drop-in replacement.
* ``PathTraversalError`` is a ``ValueError`` subclass for clear error
  semantics and easy ``except`` targeting.
"""

from __future__ import annotations

from pathlib import Path

from .file_ops import robust_rmtree


class PathTraversalError(ValueError):
    """Raised when a computed path escapes its expected base directory."""


def ensure_path_within(path: Path, base_dir: Path) -> Path:
    """Resolve *path* and assert it lives inside *base_dir*.

    Returns the resolved path on success.  Raises
    :class:`PathTraversalError` if the resolved path escapes *base_dir*.

    This is intentionally strict: symlinks are resolved so that a link
    pointing outside the base is caught as well.
    """
    resolved = path.resolve()
    resolved_base = base_dir.resolve()
    try:
        if not resolved.is_relative_to(resolved_base):
            raise PathTraversalError(
                f"Path '{path}' resolves to '{resolved}' which is outside "
                f"the allowed base directory '{resolved_base}'"
            )
    except (TypeError, ValueError) as exc:
        raise PathTraversalError(
            f"Cannot verify containment of '{path}' within '{base_dir}': {exc}"
        ) from exc
    return resolved


def safe_rmtree(path: Path, base_dir: Path) -> None:
    """Remove *path* only if it resolves within *base_dir*.

    Drop-in replacement for ``shutil.rmtree(path)`` at sites where the
    target is derived from user-controlled input.  Uses retry logic for
    transient file-lock errors (e.g. antivirus scanning on Windows).
    """
    ensure_path_within(path, base_dir)
    robust_rmtree(path)
