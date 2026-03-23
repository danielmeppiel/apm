"""Cross-platform path utilities for APM CLI.

Centralises the resolve-then-relativise-then-posixify pattern so every
call site gets Windows-safe, forward-slash relative paths by default.
"""

from __future__ import annotations

from pathlib import Path


def portable_relpath(path: Path, base: Path) -> str:
    """Return a forward-slash relative path, resolving both sides first.

    Handles Windows 8.3 short names (e.g. ``RUNNER~1`` vs ``runneradmin``)
    and ensures consistent POSIX output on every platform.

    Falls back to ``str(path)`` when *path* is not under *base*.
    """
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return str(path)
