"""Semver range resolution for marketplace plugin versions.

Resolves a user-provided version specifier against a list of available
VersionEntry objects from a marketplace plugin definition.
"""

import logging
import re
from typing import List, Optional, Sequence, Tuple

from .models import VersionEntry

logger = logging.getLogger(__name__)

# Strict semver pattern: X.Y.Z with integer components only.
# Pre-release and build metadata are intentionally unsupported.
_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

# Regex for quick classification of version specifiers.
# Matches: "X.Y.Z", "^X.Y.Z", "~X.Y.Z", ">=X.Y.Z", ">X.Y.Z", etc.
_SPECIFIER_RE = re.compile(
    r"^\s*"
    r"(?:"
    r"[~^]?\d+\.\d+\.\d+"  # Optional ^ or ~ prefix, then X.Y.Z
    r"|[><=!]+\s*\d+\.\d+\.\d+"  # Comparison operator then X.Y.Z
    r")"
    r"\s*$"
)

# Comparison operators at the start of a constraint clause.
_OP_RE = re.compile(r"^(>=|<=|!=|>|<|==)\s*(.+)$")

# Type alias for parsed version tuples.
SemverTuple = Tuple[int, int, int]

# Type alias for a single constraint: (operator, version_tuple).
Constraint = Tuple[str, SemverTuple]


def _parse_semver(version_str: str) -> SemverTuple:
    """Parse a strict ``X.Y.Z`` version string into an integer tuple.

    Args:
        version_str: Version string to parse (e.g. ``"2.1.0"``).

    Returns:
        Tuple of ``(major, minor, patch)``.

    Raises:
        ValueError: If the string is not valid ``X.Y.Z`` semver.
    """
    s = version_str.strip()
    m = _SEMVER_RE.match(s)
    if not m:
        raise ValueError(
            f"Invalid semver version: '{version_str}'. "
            f"Expected format: X.Y.Z (e.g. '2.1.0')"
        )
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _version_matches(version: SemverTuple, constraints: List[Constraint]) -> bool:
    """Check whether *version* satisfies every constraint in the list.

    Constraints are ``(operator, target_tuple)`` pairs where operator is one
    of ``==``, ``!=``, ``>=``, ``>``, ``<=``, ``<``.
    """
    for op, target in constraints:
        if op == "==" and not (version == target):
            return False
        elif op == "!=" and not (version != target):
            return False
        elif op == ">=" and not (version >= target):
            return False
        elif op == ">" and not (version > target):
            return False
        elif op == "<=" and not (version <= target):
            return False
        elif op == "<" and not (version < target):
            return False
    return True


def _expand_caret(ver: SemverTuple) -> List[Constraint]:
    """Expand caret (``^``) specifier to constraint list.

    Caret means "compatible with": the upper bound increments the leftmost
    non-zero component.

    - ``^1.2.3`` -> ``>=1.2.3, <2.0.0``
    - ``^0.5.0`` -> ``>=0.5.0, <0.6.0``
    - ``^0.0.3`` -> ``>=0.0.3, <0.0.4``
    - ``^0.0.0`` -> ``>=0.0.0, <0.0.1``
    """
    major, minor, patch = ver
    if major != 0:
        upper = (major + 1, 0, 0)
    elif minor != 0:
        upper = (0, minor + 1, 0)
    else:
        upper = (0, 0, patch + 1)
    return [(">=", ver), ("<", upper)]


def _expand_tilde(ver: SemverTuple) -> List[Constraint]:
    """Expand tilde (``~``) specifier to constraint list.

    Tilde means "patch-level changes only":
    ``~X.Y.Z`` -> ``>=X.Y.Z, <X.(Y+1).0``
    """
    major, minor, _patch = ver
    return [(">=", ver), ("<", (major, minor + 1, 0))]


def _parse_single_clause(clause: str) -> List[Constraint]:
    """Parse one clause of a version specifier into constraints.

    Supported forms:
    - ``"2.1.0"`` (exact match)
    - ``"^2.0.0"`` (caret / compatible)
    - ``"~2.1.0"`` (tilde / patch-level)
    - ``">=1.5.0"``, ``">1.0.0"``, ``"<3.0.0"``, ``"<=2.0.0"``, ``"!=1.0.0"``
    """
    s = clause.strip()
    if not s:
        raise ValueError("Empty version clause")

    # Caret prefix
    if s.startswith("^"):
        ver = _parse_semver(s[1:])
        return _expand_caret(ver)

    # Tilde prefix
    if s.startswith("~"):
        ver = _parse_semver(s[1:])
        return _expand_tilde(ver)

    # Comparison operator
    m = _OP_RE.match(s)
    if m:
        op = m.group(1)
        ver = _parse_semver(m.group(2))
        return [(op, ver)]

    # Bare version -> exact match
    ver = _parse_semver(s)
    return [("==", ver)]


def _expand_specifier(specifier: Optional[str]) -> List[Constraint]:
    """Expand a full specifier string into a flat list of constraints.

    Supports comma-separated compound specifiers like ``">=1.0.0,<3.0.0"``.
    Returns an empty list when *specifier* is ``None`` or empty (meaning
    "latest / no constraint").
    """
    if not specifier or not specifier.strip():
        return []

    constraints: List[Constraint] = []
    for clause in specifier.split(","):
        constraints.extend(_parse_single_clause(clause))
    return constraints


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_version(
    specifier: Optional[str],
    versions: Sequence["VersionEntry"],
) -> "VersionEntry":
    """Resolve a version specifier against available versions.

    Args:
        specifier: Version specifier string, or ``None`` for latest.
            Supported formats:

            - ``None`` or empty -> latest (highest semver)
            - ``"2.1.0"`` -> exact match
            - ``"^2.0.0"`` -> compatible (``>=2.0.0, <3.0.0``)
            - ``"~2.1.0"`` -> patch-level (``>=2.1.0, <2.2.0``)
            - ``">=1.5.0"`` -> minimum version
            - ``">=1.0.0,<3.0.0"`` -> compound range

        versions: Available versions from marketplace plugin.

    Returns:
        The best matching ``VersionEntry`` (highest version satisfying
        the constraint).

    Raises:
        ValueError: If no version matches the specifier, or the
            versions list is empty.
    """
    if not versions:
        raise ValueError("No versions available to resolve against")

    constraints = _expand_specifier(specifier)

    # Build candidates: skip entries whose version string is not valid semver.
    candidates: List[Tuple[SemverTuple, "VersionEntry"]] = []
    for entry in versions:
        try:
            parsed = _parse_semver(entry.version)
        except ValueError:
            logger.debug(
                "Skipping version entry with invalid semver: '%s'",
                entry.version,
            )
            continue
        if _version_matches(parsed, constraints):
            candidates.append((parsed, entry))

    if not candidates:
        spec_desc = specifier if specifier else "latest"
        available = ", ".join(
            e.version for e in versions if _SEMVER_RE.match(e.version.strip())
        )
        raise ValueError(
            f"No version matches specifier '{spec_desc}'. "
            f"Available versions: {available or '(none valid)'}"
        )

    # Sort by semver tuple descending and return the highest match.
    candidates.sort(key=lambda c: c[0], reverse=True)
    return candidates[0][1]


def is_version_specifier(value: str) -> bool:
    """Check if a string looks like a semver version specifier.

    Returns ``True`` for values that should be interpreted as version
    constraints (e.g. ``"2.1.0"``, ``"^2.0.0"``, ``"~2.1.0"``,
    ``">=1.5.0"``).

    Returns ``False`` for values that look like git refs (e.g.
    ``"main"``, ``"abc123def"``, ``"feature/branch"``).

    This is a heuristic used for routing: when a user passes a string
    that could be either a version or a git ref, this function decides
    which interpretation to use.
    """
    if not value or not value.strip():
        return False

    # Check each comma-separated clause independently.
    for clause in value.split(","):
        clause = clause.strip()
        if not clause:
            return False
        if not _SPECIFIER_RE.match(clause):
            return False
    return True
