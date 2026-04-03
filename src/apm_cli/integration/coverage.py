"""Primitive coverage validation.

Ensures every primitive registered in ``KNOWN_TARGETS`` has a
corresponding entry in the unified dispatch table.  This check runs
at import time (via test fixtures) to catch wiring omissions that
would otherwise cause silent failures at runtime.
"""

from __future__ import annotations


def check_primitive_coverage(dispatch_table: dict, special_cases: set | None = None) -> None:
    """Assert that every primitive in KNOWN_TARGETS has a handler.

    Args:
        dispatch_table: Mapping of primitive name to ``PrimitiveDispatch``
            (from ``dispatch.get_dispatch_table()``).
        special_cases: Primitive names handled outside the table.
            Typically empty when using the unified dispatch table.

    Raises:
        RuntimeError: If any primitive lacks a handler.
    """
    from apm_cli.integration.targets import KNOWN_TARGETS

    if special_cases is None:
        special_cases = set()

    all_primitives: set[str] = set()
    for target in KNOWN_TARGETS.values():
        all_primitives.update(target.primitives.keys())

    handled = set(dispatch_table.keys()) | special_cases
    missing = all_primitives - handled
    if missing:
        raise RuntimeError(
            f"Primitives {sorted(missing)} are registered in KNOWN_TARGETS "
            f"but have no integrator in the dispatch table. "
            f"Add entries to the dispatch table or to the special_cases set."
        )
